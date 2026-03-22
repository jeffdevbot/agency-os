from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app import auth
from app.config import settings
from app.services.reports.amazon_spapi_auth import (
    create_spapi_signed_state,
    verify_spapi_signed_state,
)
from app.services.wbr.amazon_ads_auth import create_signed_state, verify_signed_state


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _build_rsa_jwk():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": "test-rsa-key",
        "n": _b64url_uint(public_numbers.n),
        "e": _b64url_uint(public_numbers.e),
    }
    return private_pem, jwk


@pytest.fixture(autouse=True)
def _reset_auth_state():
    auth._reset_supabase_jwks_cache()
    yield
    auth._reset_supabase_jwks_cache()


def test_verify_supabase_jwt_accepts_hs256_tokens(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret")
    monkeypatch.setattr(settings, "supabase_jwt_audience", "authenticated")
    monkeypatch.setattr(settings, "supabase_issuer", "https://example.supabase.co/auth/v1")

    token = jwt.encode(
        {
            "sub": "user-123",
            "email": "jeff@example.com",
            "aud": settings.supabase_jwt_audience,
            "iss": settings.supabase_issuer,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )

    payload = auth.verify_supabase_jwt(token)

    assert payload["sub"] == "user-123"
    assert payload["email"] == "jeff@example.com"


def test_verify_supabase_jwt_accepts_rs256_tokens_via_jwks(monkeypatch):
    private_pem, jwk = _build_rsa_jwk()
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(settings, "supabase_jwt_audience", "authenticated")
    monkeypatch.setattr(settings, "supabase_issuer", "https://example.supabase.co/auth/v1")
    monkeypatch.setattr(auth, "_get_cached_supabase_jwks", lambda: {"keys": [jwk]})

    token = jwt.encode(
        {
            "sub": "user-456",
            "email": "jeff@example.com",
            "aud": settings.supabase_jwt_audience,
            "iss": settings.supabase_issuer,
        },
        private_pem,
        algorithm="RS256",
        headers={"kid": jwk["kid"]},
    )

    payload = auth.verify_supabase_jwt(token)

    assert payload["sub"] == "user-456"
    assert payload["email"] == "jeff@example.com"


def test_amazon_oauth_state_signing_secret_takes_precedence(monkeypatch):
    monkeypatch.setenv("OAUTH_STATE_SIGNING_SECRET", "state-secret")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "legacy-jwt-secret")

    ads_state = create_signed_state(
        profile_id="prof-1",
        initiated_by="user-1",
        return_path="/reports/test/us/wbr/sync/ads-api",
    )
    spapi_state = create_spapi_signed_state(
        client_id="client-1",
        region_code="NA",
        initiated_by="user-1",
        return_path="/reports/api-access",
    )

    monkeypatch.setenv("SUPABASE_JWT_SECRET", "different-legacy-secret")

    assert verify_signed_state(ads_state)["pid"] == "prof-1"
    assert verify_spapi_signed_state(spapi_state)["cid"] == "client-1"
