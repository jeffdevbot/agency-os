"""Tests for WBR campaign exclusion service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.wbr.campaign_exclusions import CampaignExclusionService
from app.services.wbr.profiles import WBRValidationError


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.in_.return_value = table
    table.eq.return_value = table
    table.range.return_value = table
    table.limit.return_value = table
    table.order.return_value = table
    table.execute.return_value = MagicMock(data=response_data if response_data is not None else [])
    return table


def _multi_table_db(mapping: dict[str, list[MagicMock]]) -> MagicMock:
    iterators = {name: iter(tables) for name, tables in mapping.items()}

    def router(name: str) -> MagicMock:
        return next(iterators[name])

    db = MagicMock()
    db.table.side_effect = router
    return db


def test_list_exclusions_returns_active_items():
    db = _multi_table_db(
        {
            "wbr_profiles": [_chain_table([{"id": "p1"}])],
            "wbr_campaign_exclusions": [
                _chain_table(
                    [
                        {
                            "id": "e1",
                            "profile_id": "p1",
                            "campaign_name": "Legacy Campaign",
                            "exclusion_source": "manual",
                            "exclusion_reason": "Out of scope",
                            "active": True,
                        }
                    ]
                )
            ],
        }
    )

    items = CampaignExclusionService(db).list_exclusions("p1")

    assert len(items) == 1
    assert items[0]["campaign_name"] == "Legacy Campaign"


def test_export_exclusions_csv_includes_all_known_campaigns_with_blank_default():
    db = _multi_table_db(
        {
            "wbr_profiles": [_chain_table([{"id": "p1"}])],
            "wbr_campaign_exclusions": [
                _chain_table([{"id": "e1", "campaign_name": "Legacy Campaign"}]),
                _chain_table([{"campaign_name": "Legacy Campaign"}]),
            ],
            "wbr_ads_campaign_daily": [
                _chain_table(
                    [
                        {"campaign_name": "Legacy Campaign"},
                        {"campaign_name": "Brand Campaign"},
                    ]
                )
            ],
        }
    )

    csv_text = CampaignExclusionService(db).export_exclusions_csv("p1")

    assert csv_text.startswith("campaign_name,scope_status\n")
    assert "Brand Campaign,\n" in csv_text
    assert "Legacy Campaign,excluded\n" in csv_text


def test_import_exclusions_csv_adds_new_exclusions():
    csv_text = (
        "campaign_name,scope_status,exclusion_reason\n"
        "Legacy Campaign,excluded,Not agency managed\n"
    ).encode("utf-8")

    db = _multi_table_db(
        {
            "wbr_profiles": [_chain_table([{"id": "p1"}])],
            "wbr_campaign_exclusions": [
                _chain_table([]),
                _chain_table([{"id": "e1"}]),
            ],
        }
    )

    summary = CampaignExclusionService(db).import_exclusions_csv(
        profile_id="p1",
        file_name="campaign-exclusions.csv",
        file_bytes=csv_text,
        user_id="u1",
    )

    assert summary == {
        "rows_read": 1,
        "rows_excluded": 1,
        "rows_cleared": 0,
        "rows_unchanged": 0,
    }


def test_import_exclusions_csv_rejects_invalid_scope_status():
    csv_text = (
        "campaign_name,scope_status\n"
        "Legacy Campaign,maybe\n"
    ).encode("utf-8")

    db = _multi_table_db(
        {
            "wbr_profiles": [_chain_table([{"id": "p1"}])],
            "wbr_campaign_exclusions": [_chain_table([])],
        }
    )

    with pytest.raises(WBRValidationError, match="unsupported scope_status"):
        CampaignExclusionService(db).import_exclusions_csv(
            profile_id="p1",
            file_name="campaign-exclusions.csv",
            file_bytes=csv_text,
            user_id="u1",
        )
