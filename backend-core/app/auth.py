from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import settings


auth_scheme = HTTPBearer(auto_error=True)


def verify_supabase_jwt(token: str):
    if not settings.supabase_jwt_secret:
        raise RuntimeError("SUPABASE_JWT_SECRET not configured.")
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_audience,
            options={"verify_iss": True},
            issuer=settings.supabase_issuer,
        )
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def require_user(creds: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    token = creds.credentials
    return verify_supabase_jwt(token)
