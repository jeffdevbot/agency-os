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
                "Search Term": "travel size screen cleaner",
                "Impression": 100,
                "Click": 10,
                "Spend": 8.5,
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
        ai_prefills={
            "Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf": {
                "mono": ["travel", "travel", "size"],
                "bi": ["travel size"],
                "tri": ["travel size screen"],
            }
        },
    )

    try:
        wb = load_workbook(workbook_path, data_only=False)
        ws = wb[wb.sheetnames[1]]

        assert ws["AX6"].value == "Monogram"
        assert ws["AY6"].value == "Bigram"
        assert ws["AZ6"].value == "Trigram"

        assert ws["AX7"].value == "travel"
        assert ws["AX8"].value == "size"
        assert ws["AY7"].value == "travel size"
        assert ws["AZ7"].value == "travel size screen"

        assert isinstance(ws["K7"].value, str)
        assert "MATCH(A7,AX:AX,0)" in ws["K7"].value
    finally:
        os.unlink(workbook_path)
