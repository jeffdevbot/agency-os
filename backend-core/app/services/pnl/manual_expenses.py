"""Shared definitions for manual Monthly P&L expense rows."""

from __future__ import annotations

from typing import Final


MANUAL_EXPENSE_TYPES: Final = [
    {
        "key": "fbm_fulfillment_fees",
        "label": "FBM Fulfillment Fees",
        "category": "expenses",
        "placement": "after_fba_fees",
    },
    {
        "key": "agency_fees",
        "label": "Agency Fees",
        "category": "expenses",
        "placement": "end",
    },
    {
        "key": "freight",
        "label": "Freight",
        "category": "expenses",
        "placement": "end",
    },
]

MANUAL_EXPENSE_TYPE_BY_KEY: Final = {
    expense_type["key"]: expense_type for expense_type in MANUAL_EXPENSE_TYPES
}

MANUAL_EXPENSE_KEYS: Final = tuple(MANUAL_EXPENSE_TYPE_BY_KEY.keys())
