from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.pnl.email_prompt import PROMPT_VERSION, build_monthly_pnl_email_prompt_messages


class _FakeTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters_eq: dict = {}
        self._limit_n: int | None = None
        self._insert_data: dict | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, col, val):
        self._filters_eq[col] = val
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def order(self, *_args, **_kwargs):
        return self

    def insert(self, data):
        self._insert_data = data
        return self

    def execute(self):
        filtered = self._rows
        if self._filters_eq:
            filtered = [
                row for row in filtered
                if all(row.get(col) == val for col, val in self._filters_eq.items())
            ]
        if self._limit_n:
            filtered = filtered[: self._limit_n]
        resp = MagicMock()
        if self._insert_data is not None:
            resp.data = [{**self._insert_data, "id": "pnl-draft-1", "created_at": "2026-03-23T17:00:00Z"}]
        else:
            resp.data = filtered
        return resp


class _FakeDB:
    def __init__(self, tables: dict[str, list[dict]] | None = None):
        self._tables = {name: list(rows) for name, rows in (tables or {}).items()}

    def table(self, name: str):
        return _FakeTable(self._tables.get(name, []))


def _make_brief() -> dict:
    return {
        "client": {"client_id": "c1", "client_name": "Whoosh"},
        "report_month": "2026-02-01",
        "report_month_label": "Feb 2026",
        "comparison_mode_requested": "auto",
        "comparison_mode_used": "yoy_preferred",
        "marketplace_scope": ["US", "CA"],
        "sections": [
            {
                "profile_id": "pp1",
                "marketplace_code": "US",
                "currency_code": "USD",
                "comparison_mode_used": "yoy_preferred",
                "latest_month_has_yoy": True,
                "ytd_has_yoy": True,
                "snapshot_metrics": [
                    {
                        "key": "total_net_revenue",
                        "label": "Total Net Revenue",
                        "latest_month_value": "287589.00",
                        "latest_month_yoy_percent_change": "9.80",
                        "ytd_value": "584324.00",
                        "ytd_yoy_percent_change": "7.60",
                    },
                    {
                        "key": "net_earnings_pct_of_net_revenue",
                        "label": "Net Earnings % of Net Revenue",
                        "latest_month_value": "34.40",
                        "latest_month_yoy_pp_change": "-1.70",
                        "ytd_value": "33.60",
                        "ytd_yoy_pp_change": "-0.20",
                    },
                ],
                "positive_drivers": [{"title": "Net Earnings margin", "evidence": "Improved margin signal."}],
                "negative_drivers": [{"title": "Advertising share", "evidence": "Ad ratio remains elevated."}],
                "financial_health": {"verdict": "Excellent", "reason": "Margins remain strong."},
                "data_quality_notes": [],
            },
            {
                "profile_id": "pp2",
                "marketplace_code": "CA",
                "currency_code": "CAD",
                "comparison_mode_used": "yoy_preferred",
                "latest_month_has_yoy": True,
                "ytd_has_yoy": True,
                "snapshot_metrics": [],
                "positive_drivers": [],
                "negative_drivers": [],
                "financial_health": {"verdict": "Good", "reason": "Profitable with some pressure."},
                "data_quality_notes": [],
            },
        ],
        "overall_summary_points": [
            "Best latest-month Net Earnings margin: US at 34.4%.",
            "Weakest latest-month Net Earnings margin: CA at 23.2%.",
        ],
        "data_quality_notes": [],
        "unavailable_marketplaces": [],
    }


class TestBuildMonthlyPNLEmailPromptMessages:
    def test_returns_system_and_user_messages(self):
        messages = build_monthly_pnl_email_prompt_messages(brief=_make_brief(), recipient_name="Billy")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_prompt_version_is_set(self):
        assert PROMPT_VERSION == "monthly_pnl_email_v1"

    def test_user_message_contains_brief_json(self):
        messages = build_monthly_pnl_email_prompt_messages(brief=_make_brief(), recipient_name="Billy")
        content = messages[1]["content"]
        assert "structured brief" in content
        assert '"client_name": "Whoosh"' in content
        assert '"marketplace_code": "US"' in content


class TestGenerateMonthlyPNLEmailDraft:
    @pytest.mark.asyncio
    async def test_generates_and_persists_draft(self, monkeypatch):
        from app.services.pnl.email_drafts import generate_email_draft

        monkeypatch.setattr(
            "app.services.pnl.email_drafts.PNLEmailBriefService",
            MagicMock(return_value=MagicMock(build_client_brief_async=AsyncMock(return_value=_make_brief()))),
        )
        monkeypatch.setattr(
            "app.services.theclaw.openai_client.call_chat_completion",
            AsyncMock(
                return_value={
                    "content": json.dumps(
                        {
                            "subject": "Whoosh — Amazon P&L highlights | Feb 2026 results",
                            "body": "Hi Billy,\n\nPlease find the attached Amazon P&L highlights...\n\nBest regards,",
                        }
                    ),
                    "model": "gpt-5-mini",
                }
            ),
        )

        db = _FakeDB(tables={"monthly_pnl_email_drafts": []})
        result = await generate_email_draft(
            db,
            "c1",
            report_month="2026-02-01",
            marketplace_codes=["US", "CA"],
            recipient_name="Billy",
            created_by="user-1",
        )

        assert result["id"] == "pnl-draft-1"
        assert result["draft_kind"] == "monthly_pnl_highlights_email"
        assert result["marketplace_scope"] == "US,CA"
        assert result["profile_ids"] == ["pp1", "pp2"]
        assert result["subject"] == "Whoosh — Amazon P&L highlights | Feb 2026 results"
        assert "Hi Billy" in result["body"]
        assert result["prompt_version"] == PROMPT_VERSION

    @pytest.mark.asyncio
    async def test_raises_on_invalid_llm_json(self, monkeypatch):
        from app.services.pnl.email_drafts import generate_email_draft

        monkeypatch.setattr(
            "app.services.pnl.email_drafts.PNLEmailBriefService",
            MagicMock(return_value=MagicMock(build_client_brief_async=AsyncMock(return_value=_make_brief()))),
        )
        monkeypatch.setattr(
            "app.services.theclaw.openai_client.call_chat_completion",
            AsyncMock(return_value={"content": "not json", "model": "gpt-5-mini"}),
        )

        db = _FakeDB(tables={"monthly_pnl_email_drafts": []})
        with pytest.raises(ValueError, match="invalid JSON"):
            await generate_email_draft(db, "c1", report_month="2026-02-01")

    @pytest.mark.asyncio
    async def test_raises_on_empty_body(self, monkeypatch):
        from app.services.pnl.email_drafts import generate_email_draft

        monkeypatch.setattr(
            "app.services.pnl.email_drafts.PNLEmailBriefService",
            MagicMock(return_value=MagicMock(build_client_brief_async=AsyncMock(return_value=_make_brief()))),
        )
        monkeypatch.setattr(
            "app.services.theclaw.openai_client.call_chat_completion",
            AsyncMock(return_value={"content": json.dumps({"subject": "Subj", "body": ""}), "model": "gpt-5-mini"}),
        )

        db = _FakeDB(tables={"monthly_pnl_email_drafts": []})
        with pytest.raises(ValueError, match="empty email body"):
            await generate_email_draft(db, "c1", report_month="2026-02-01")
