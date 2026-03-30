from __future__ import annotations

import os

import pandas as pd
from openpyxl import load_workbook

from app.services.ngram.override_capture import _build_override_payload
from app.services.ngram.workbook import build_workbook


def _make_ngram_df(grams: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "N-gram": gram,
                "Impression": 10,
                "Click": 2,
                "Spend": 1.5,
                "Order 14d": 0,
                "Sales 14d": 0,
                "CTR": 0.2,
                "CVR": 0.0,
                "CPC": 0.75,
                "ACOS": 0.0,
                "NE/NP": "",
                "Comments": "",
            }
            for gram in grams
        ]
    )


def test_build_override_payload_compares_ai_recommendations_to_reviewed_workbook():
    raw = pd.DataFrame(
        [
            {
                "Search Term": "laptop cloth",
                "Impression": 100,
                "Click": 10,
                "Spend": 8.5,
                "Order 14d": 0,
                "Sales 14d": 0,
                "NE/NP": "",
                "Comments": "",
            },
            {
                "Search Term": "screen cleaner spray",
                "Impression": 80,
                "Click": 8,
                "Spend": 6.2,
                "Order 14d": 0,
                "Sales 14d": 0,
                "NE/NP": "",
                "Comments": "",
            },
        ]
    )

    campaign_name = "Screen Shine - Duo | SPA | Cls. | Rsrch"
    workbook_path = build_workbook(
        [
            {
                "campaign_name": campaign_name,
                "category_raw": "Duo",
                "category_key": "duo",
                "mono": _make_ngram_df(["laptop", "screen"]),
                "bi": _make_ngram_df(["laptop cloth", "screen cleaner"]),
                "tri": _make_ngram_df(["screen cleaner spray"]),
                "raw": raw,
                "notes": [],
            }
        ],
        "test-version",
        ai_term_reviews={
            campaign_name: {
                "laptop cloth": {
                    "recommendation": "NEGATE",
                    "confidence": "HIGH",
                    "reason_tag": "cloth_primary_intent",
                },
                "screen cleaner spray": {
                    "recommendation": "KEEP",
                    "confidence": "HIGH",
                    "reason_tag": "core_use_case",
                },
            }
        },
        ai_summary={
            "preview_run_id": "preview-run-123",
            "model": "gpt-5.4-2026-03-05",
            "prompt_version": "ngram_step3_calibrated_v2026_03_30",
            "spend_threshold": "1.0",
        },
    )

    try:
        wb = load_workbook(workbook_path)
        ws = wb[wb.sheetnames[1]]
        ws["AT7"] = "NE"
        ws["X7"] = "NP"
        wb.save(workbook_path)

        reviewed_wb = load_workbook(workbook_path, data_only=True)
        payload = _build_override_payload(
            reviewed_wb,
            {
                "id": "preview-run-123",
                "profile_id": "profile-1",
                "model": "gpt-5.4-2026-03-05",
                "prompt_version": "ngram_step3_calibrated_v2026_03_30",
                "preview_payload": {
                    "campaigns": [
                        {
                            "campaignName": campaign_name,
                            "synthesizedPrefills": {
                                "mono": [],
                                "bi": [{"gram": "laptop cloth"}],
                                "tri": [],
                            },
                            "evaluations": [
                                {
                                    "search_term": "laptop cloth",
                                    "recommendation": "NEGATE",
                                    "confidence": "HIGH",
                                    "reason_tag": "cloth_primary_intent",
                                },
                                {
                                    "search_term": "screen cleaner spray",
                                    "recommendation": "KEEP",
                                    "confidence": "HIGH",
                                    "reason_tag": "core_use_case",
                                },
                            ],
                        }
                    ]
                },
            },
        )

        assert payload is not None
        assert payload["prompt_version"] == "ngram_step3_calibrated_v2026_03_30"
        assert payload["summary"]["term_status_counts"]["ai_negate_accepted"] == 1
        assert payload["summary"]["term_status_counts"]["unchanged_non_negative"] == 1

        campaign_payload = payload["campaigns"][0]
        laptop_diff = next(item for item in campaign_payload["term_diffs"] if item["search_term"] == "laptop cloth")
        keep_diff = next(
            item for item in campaign_payload["term_diffs"] if item["search_term"] == "screen cleaner spray"
        )

        assert laptop_diff["analyst_outcome"] == "negated"
        assert laptop_diff["analyst_source"] == "exact"
        assert laptop_diff["decision_status"] == "matched"
        assert keep_diff["analyst_outcome"] == "not_negated"
        assert keep_diff["decision_status"] == "matched"

        bi_diff = next(item for item in campaign_payload["gram_diffs"]["bi"] if item["gram"] == "laptop cloth")
        assert bi_diff["status"] == "matched"
    finally:
        os.unlink(workbook_path)
