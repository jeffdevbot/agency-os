from __future__ import annotations

import os

import pandas as pd
from openpyxl import load_workbook

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


def test_build_workbook_writes_ai_prefills_to_scratchpad_columns():
    raw = pd.DataFrame(
        [
            {
                "Search Term": "travel size",
                "Impression": 100,
                "Click": 10,
                "Spend": 8.5,
                "Order 14d": 0,
                "Sales 14d": 0,
                "NE/NP": "",
                "Comments": "",
            },
            {
                "Search Term": "travel size screen cleaner",
                "Impression": 80,
                "Click": 8,
                "Spend": 6.2,
                "Order 14d": 0,
                "Sales 14d": 0,
                "NE/NP": "",
                "Comments": "",
            }
        ]
    )

    campaign_items = [
        {
            "campaign_name": "Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf",
            "category_raw": "Pro",
            "category_key": "pro",
            "mono": _make_ngram_df(["travel", "size"]),
            "bi": _make_ngram_df(["travel size"]),
            "tri": _make_ngram_df(["travel size screen"]),
            "raw": raw,
            "notes": [],
        }
    ]

    workbook_path = build_workbook(
        campaign_items,
        "test-version",
        ai_term_reviews={
            "Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf": {
                "travel size": {
                    "recommendation": "NEGATE",
                    "confidence": "HIGH",
                    "reason_tag": "wrong_size_variant",
                },
                "travel size screen cleaner": {
                    "recommendation": "NEGATE",
                    "confidence": "MEDIUM",
                    "reason_tag": "ambiguous_intent",
                }
            }
        },
        ai_summary={
            "preview_run_id": "preview-run-123",
            "model": "gpt-5.4-mini-2026-03-17",
            "prompt_version": "ngram_step3_calibrated_v2026_03_30",
            "spend_threshold": "1.0",
        },
    )

    try:
        wb = load_workbook(workbook_path, data_only=False)
        summary_ws = wb["Summary"]
        ws = wb[wb.sheetnames[1]]

        assert summary_ws["J3"].value == "AI Preview Run: preview-run-123"
        assert summary_ws["J4"].value == "AI Model: gpt-5.4-mini-2026-03-17"
        assert summary_ws["J5"].value == "AI Prompt Version: ngram_step3_calibrated_v2026_03_30"
        assert summary_ws["J6"].value == "AI Threshold: 1.0"

        assert ws["AV6"].value == "AI Recommendation"
        assert ws["AW6"].value == "AI Confidence"
        assert ws["AX6"].value == "AI Reason"
        assert ws["AV7"].value == "NEGATE"
        assert ws["AW7"].value == "HIGH"
        assert ws["AX7"].value == "wrong_size_variant"
        assert ws["AV8"].value == "NEGATE"
        assert ws["AW8"].value == "MEDIUM"
        assert ws["AX8"].value == "ambiguous_intent"
        assert ws["AT8"].value == "NE"

        assert ws["AZ6"].value == "Monogram"
        assert ws["BA6"].value == "Bigram"
        assert ws["BB6"].value == "Trigram"
        assert ws["AY6"].value in (None, "")
        assert ws["BA7"].value == "travel size"

        assert isinstance(ws["K7"].value, str)
        assert "MATCH(A7,AZ:AZ,0)" in ws["K7"].value
        assert isinstance(ws["X7"].value, str)
        assert "MATCH(N7,BA:BA,0)" in ws["X7"].value
    finally:
        os.unlink(workbook_path)
