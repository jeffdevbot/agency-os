from __future__ import annotations

import tempfile

from fastapi.testclient import TestClient

from app.main import app
from app.routers import ngram
from app.services.ngram.native import NativeNgramWorkbookResult


class _FakeNativeWorkbookService:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.db = object()

    def build_workbook_from_search_term_facts(
        self,
        *,
        profile_id: str,
        ad_product: str,
        date_from,
        date_to,
        respect_legacy_exclusions: bool,
        app_version: str,
        ai_prefills,
        ai_term_reviews,
        ai_summary,
    ) -> NativeNgramWorkbookResult:
        self.calls.append(
            {
                "profile_id": profile_id,
                "ad_product": ad_product,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "respect_legacy_exclusions": respect_legacy_exclusions,
                "ai_prefills": ai_prefills,
                "ai_term_reviews": ai_term_reviews,
                "ai_summary": ai_summary,
            }
        )

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        temp_file.write(b"fake-xlsx")
        temp_file.flush()
        temp_file.close()

        return NativeNgramWorkbookResult(
            workbook_path=temp_file.name,
            filename="whoosh_ca_2026-03-16_2026-03-29_native_ngrams.xlsx",
            rows_processed=96,
            campaigns_included=6,
            campaigns_skipped=0,
            ad_product=ad_product,
        )


def _override_user():
    return {"sub": "user-123", "email": "tester@example.com"}


def test_native_prefilled_workbook_route_uses_saved_preview_run(monkeypatch):
    fake_service = _FakeNativeWorkbookService()
    app.dependency_overrides[ngram.require_user] = _override_user
    app.dependency_overrides[ngram._get_native_service] = lambda: fake_service

    monkeypatch.setattr(
        ngram,
        "_load_saved_preview_run",
        lambda service, preview_run_id: {
            "id": preview_run_id,
            "profile_id": "profile-1",
            "ad_product": "SPONSORED_PRODUCTS",
            "date_from": "2026-03-16",
            "date_to": "2026-03-29",
            "spend_threshold": 1,
            "respect_legacy_exclusions": True,
            "model": "gpt-5.4-mini-2026-03-17",
            "prompt_version": "ngram_step3_calibrated_v2026_03_30",
            "preview_payload": {
                "model": "gpt-5.4-mini-2026-03-17",
                "prompt_version": "ngram_step3_calibrated_v2026_03_30",
                "campaigns": [
                    {
                        "campaignName": "Screen Shine - Pro 2 | SPM | MKW",
                        "modelPrefills": {
                            "exact": ["portable monitor travel case"],
                            "mono": [],
                            "bi": ["laptop cloth"],
                            "tri": [],
                        },
                        "synthesizedPrefills": {
                            "mono": [{"gram": "travel"}],
                            "bi": [{"gram": "travel size"}],
                            "tri": [{"gram": "travel size screen"}],
                        },
                        "evaluations": [
                            {
                                "search_term": "travel size screen cleaner",
                                "recommendation": "REVIEW",
                                "confidence": "MEDIUM",
                                "reason_tag": "ambiguous_intent",
                            }
                        ],
                    }
                ],
            },
        },
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/ngram/native-workbook-prefilled",
                json={
                    "profile_id": "profile-1",
                    "ad_product": "SPONSORED_PRODUCTS",
                    "date_from": "2026-03-16",
                    "date_to": "2026-03-29",
                    "respect_legacy_exclusions": True,
                    "preview_run_id": "preview-run-123",
                },
            )
    finally:
        app.dependency_overrides.pop(ngram.require_user, None)
        app.dependency_overrides.pop(ngram._get_native_service, None)

    assert response.status_code == 200
    assert fake_service.calls == [
        {
            "profile_id": "profile-1",
            "ad_product": "SPONSORED_PRODUCTS",
            "date_from": "2026-03-16",
            "date_to": "2026-03-29",
            "respect_legacy_exclusions": True,
            "ai_prefills": {
                "Screen Shine - Pro 2 | SPM | MKW": {
                    "exact": ["portable monitor travel case"],
                    "mono": ["travel"],
                    "bi": ["travel size"],
                    "tri": ["travel size screen"],
                }
            },
            "ai_term_reviews": {
                "Screen Shine - Pro 2 | SPM | MKW": {
                    "travel size screen cleaner": {
                        "recommendation": "REVIEW",
                        "confidence": "MEDIUM",
                        "reason_tag": "ambiguous_intent",
                    }
                }
            },
            "ai_summary": {
                "preview_run_id": "preview-run-123",
                "model": "gpt-5.4-mini-2026-03-17",
                "prompt_version": "ngram_step3_calibrated_v2026_03_30",
                "spend_threshold": 1.0,
            },
        }
    ]
