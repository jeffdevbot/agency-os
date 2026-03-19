"""Tests for WBR weekly email draft generation, persistence, and Claw integration."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.wbr.email_drafts import (
    gather_client_snapshots,
    _marketplace_sort_key,
)
from app.services.wbr.email_prompt import (
    PROMPT_VERSION,
    build_email_prompt_messages,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters_eq: dict = {}
        self._limit_n: int | None = None
        self._insert_data: dict | None = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, col, val):
        self._filters_eq[col] = val
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def order(self, *args, **kwargs):
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
            resp.data = [{**self._insert_data, "id": "draft-1", "created_at": "2026-03-19T12:00:00Z"}]
        else:
            resp.data = filtered
        return resp


class _FakeDB:
    def __init__(self, tables: dict[str, list[dict]] | None = None):
        self._tables = {name: list(rows) for name, rows in (tables or {}).items()}

    def table(self, name: str):
        return _FakeTable(self._tables.get(name, []))


def _make_digest(marketplace_code: str = "US", week_ending: str = "2026-03-15") -> dict:
    return {
        "digest_version": "wbr_digest_v1",
        "profile": {"marketplace_code": marketplace_code, "client_name": "Whoosh"},
        "window": {"week_ending": week_ending, "weeks_shown": 4},
        "headline_metrics": {
            "total_sales": {"current": 12500, "wow_change_pct": 5.2},
            "unit_sales": {"current": 450, "wow_change_pct": 3.1},
        },
        "wins": ["Strong US performance"],
        "concerns": [],
        "section_summaries": [],
    }


# ---------------------------------------------------------------------------
# Marketplace sort order
# ---------------------------------------------------------------------------


class TestMarketplaceSortKey:
    def test_us_before_ca(self):
        assert _marketplace_sort_key("US") < _marketplace_sort_key("CA")

    def test_ca_before_uk(self):
        assert _marketplace_sort_key("CA") < _marketplace_sort_key("UK")

    def test_unknown_after_known(self):
        assert _marketplace_sort_key("ZZ") > _marketplace_sort_key("AU")

    def test_case_insensitive(self):
        assert _marketplace_sort_key("us") == _marketplace_sort_key("US")


# ---------------------------------------------------------------------------
# gather_client_snapshots
# ---------------------------------------------------------------------------


class TestGatherClientSnapshots:
    def test_returns_empty_when_no_profiles(self):
        db = _FakeDB(tables={"wbr_profiles": []})
        result = gather_client_snapshots(db, "c1")
        assert result == []

    def test_gathers_snapshots_in_marketplace_order(self, monkeypatch):
        db = _FakeDB(tables={
            "wbr_profiles": [
                {"id": "p1", "client_id": "c1", "marketplace_code": "CA", "display_name": "Whoosh CA", "status": "active"},
                {"id": "p2", "client_id": "c1", "marketplace_code": "US", "display_name": "Whoosh US", "status": "active"},
            ],
        })

        digest_us = _make_digest("US")
        digest_ca = _make_digest("CA")

        class _FakeSnapshotSvc:
            def __init__(self, db):
                pass

            def get_or_create_snapshot(self, profile_id):
                if profile_id == "p2":
                    return {"id": "snap-us", "digest": digest_us, "source_run_at": "2026-03-18T10:00:00Z"}
                return {"id": "snap-ca", "digest": digest_ca, "source_run_at": "2026-03-18T10:00:00Z"}

        monkeypatch.setattr("app.services.wbr.email_drafts.WBRSnapshotService", _FakeSnapshotSvc)

        result = gather_client_snapshots(db, "c1")
        assert len(result) == 2
        # US should come first (preferred order)
        assert result[0]["marketplace_code"] == "US"
        assert result[1]["marketplace_code"] == "CA"

    def test_skips_profiles_with_no_digest(self, monkeypatch):
        db = _FakeDB(tables={
            "wbr_profiles": [
                {"id": "p1", "client_id": "c1", "marketplace_code": "US", "display_name": "Whoosh US", "status": "active"},
            ],
        })

        class _EmptySnapshotSvc:
            def __init__(self, db):
                pass

            def get_or_create_snapshot(self, profile_id):
                return {"id": "snap-1", "digest": None}

        monkeypatch.setattr("app.services.wbr.email_drafts.WBRSnapshotService", _EmptySnapshotSvc)

        result = gather_client_snapshots(db, "c1")
        assert result == []

    def test_injects_source_run_at_into_digest(self, monkeypatch):
        db = _FakeDB(tables={
            "wbr_profiles": [
                {"id": "p1", "client_id": "c1", "marketplace_code": "US", "display_name": "Whoosh US", "status": "active"},
            ],
        })
        digest = _make_digest("US")

        class _FakeSnapshotSvc:
            def __init__(self, db):
                pass

            def get_or_create_snapshot(self, profile_id):
                return {"id": "snap-1", "digest": digest, "source_run_at": "2026-03-18T10:00:00Z"}

        monkeypatch.setattr("app.services.wbr.email_drafts.WBRSnapshotService", _FakeSnapshotSvc)

        result = gather_client_snapshots(db, "c1")
        assert result[0]["digest"]["source_run_at"] == "2026-03-18T10:00:00Z"


# ---------------------------------------------------------------------------
# Email prompt construction
# ---------------------------------------------------------------------------


class TestBuildEmailPromptMessages:
    def test_returns_system_and_user_messages(self):
        digests = [_make_digest("US"), _make_digest("CA")]
        messages = build_email_prompt_messages(digests=digests)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_user_message_contains_marketplace_labels(self):
        digests = [_make_digest("US"), _make_digest("CA")]
        messages = build_email_prompt_messages(digests=digests)
        user_content = messages[1]["content"]
        assert "--- Marketplace: US ---" in user_content
        assert "--- Marketplace: CA ---" in user_content

    def test_user_message_contains_digest_json(self):
        digests = [_make_digest("US")]
        messages = build_email_prompt_messages(digests=digests)
        user_content = messages[1]["content"]
        assert "wbr_digest_v1" in user_content
        assert "Whoosh" in user_content

    def test_system_prompt_has_json_output_instruction(self):
        messages = build_email_prompt_messages(digests=[_make_digest("US")])
        system = messages[0]["content"]
        assert '{"subject":' in system or '"subject"' in system
        assert "JSON" in system

    def test_prompt_version_is_set(self):
        assert PROMPT_VERSION == "wbr_email_v2"

    def test_system_prompt_prefers_bullets_not_code_blocks(self):
        messages = build_email_prompt_messages(digests=[_make_digest("US")])
        system = messages[0]["content"]
        assert "real bullet characters `•`" in system
        assert "Do not use markdown fences" in system


# ---------------------------------------------------------------------------
# generate_email_draft (end-to-end with mocks)
# ---------------------------------------------------------------------------


class TestGenerateEmailDraft:
    @pytest.mark.asyncio
    async def test_generates_and_persists_draft(self, monkeypatch):
        from app.services.wbr.email_drafts import generate_email_draft

        digest_us = _make_digest("US")
        digest_ca = _make_digest("CA")

        snapshot_entries = [
            {
                "snapshot_id": "snap-us",
                "profile_id": "p1",
                "marketplace_code": "US",
                "display_name": "Whoosh US",
                "digest": digest_us,
            },
            {
                "snapshot_id": "snap-ca",
                "profile_id": "p2",
                "marketplace_code": "CA",
                "display_name": "Whoosh CA",
                "digest": digest_ca,
            },
        ]

        monkeypatch.setattr(
            "app.services.wbr.email_drafts.gather_client_snapshots",
            lambda db, cid: snapshot_entries,
        )

        llm_response = {
            "content": json.dumps({
                "subject": "Weekly WBR — Whoosh Performance Update — Wk 2026-03-15",
                "body": "Hi Team,\n\nHere is your weekly update...\n\nThanks,",
            }),
            "model": "gpt-5-0125",
        }
        monkeypatch.setattr(
            "app.services.theclaw.openai_client.call_chat_completion",
            AsyncMock(return_value=llm_response),
        )

        db = _FakeDB(tables={
            "agency_clients": [{"id": "c1", "name": "Whoosh"}],
            "wbr_email_drafts": [],
        })

        result = await generate_email_draft(db, "c1", created_by="user-1")

        assert result["subject"] == "Weekly WBR — Whoosh Performance Update — Wk 2026-03-15"
        assert "Hi Team" in result["body"]
        assert result["marketplace_scope"] == "US,CA"
        assert result["snapshot_ids"] == ["snap-us", "snap-ca"]
        assert result["week_ending"] == "2026-03-15"
        assert result["id"] == "draft-1"

    @pytest.mark.asyncio
    async def test_raises_when_no_snapshots(self, monkeypatch):
        from app.services.wbr.email_drafts import generate_email_draft

        monkeypatch.setattr(
            "app.services.wbr.email_drafts.gather_client_snapshots",
            lambda db, cid: [],
        )

        db = _FakeDB()
        with pytest.raises(ValueError, match="No active WBR profiles"):
            await generate_email_draft(db, "c1")

    @pytest.mark.asyncio
    async def test_raises_when_week_endings_disagree(self, monkeypatch):
        from app.services.wbr.email_drafts import generate_email_draft

        snapshot_entries = [
            {
                "snapshot_id": "snap-us",
                "profile_id": "p1",
                "marketplace_code": "US",
                "display_name": "Whoosh US",
                "digest": _make_digest("US", week_ending="2026-03-15"),
            },
            {
                "snapshot_id": "snap-ca",
                "profile_id": "p2",
                "marketplace_code": "CA",
                "display_name": "Whoosh CA",
                "digest": _make_digest("CA", week_ending="2026-03-08"),
            },
        ]

        monkeypatch.setattr(
            "app.services.wbr.email_drafts.gather_client_snapshots",
            lambda db, cid: snapshot_entries,
        )

        db = _FakeDB()
        with pytest.raises(ValueError, match="different week_ending"):
            await generate_email_draft(db, "c1")

    @pytest.mark.asyncio
    async def test_succeeds_when_all_week_endings_match(self, monkeypatch):
        from app.services.wbr.email_drafts import generate_email_draft

        snapshot_entries = [
            {
                "snapshot_id": "snap-us",
                "profile_id": "p1",
                "marketplace_code": "US",
                "display_name": "Whoosh US",
                "digest": _make_digest("US", week_ending="2026-03-15"),
            },
            {
                "snapshot_id": "snap-ca",
                "profile_id": "p2",
                "marketplace_code": "CA",
                "display_name": "Whoosh CA",
                "digest": _make_digest("CA", week_ending="2026-03-15"),
            },
        ]

        monkeypatch.setattr(
            "app.services.wbr.email_drafts.gather_client_snapshots",
            lambda db, cid: snapshot_entries,
        )

        llm_response = {
            "content": json.dumps({"subject": "WBR Update", "body": "Hi Team,\nUpdate.\nThanks,"}),
            "model": "gpt-5",
        }
        monkeypatch.setattr(
            "app.services.theclaw.openai_client.call_chat_completion",
            AsyncMock(return_value=llm_response),
        )

        db = _FakeDB(tables={"wbr_email_drafts": []})
        result = await generate_email_draft(db, "c1")
        assert result["week_ending"] == "2026-03-15"
        assert result["snapshot_group_key"] == "week_ending:2026-03-15"

    @pytest.mark.asyncio
    async def test_raises_on_invalid_llm_json(self, monkeypatch):
        from app.services.wbr.email_drafts import generate_email_draft

        monkeypatch.setattr(
            "app.services.wbr.email_drafts.gather_client_snapshots",
            lambda db, cid: [{"snapshot_id": "s1", "profile_id": "p1", "marketplace_code": "US", "display_name": "X", "digest": _make_digest("US")}],
        )
        monkeypatch.setattr(
            "app.services.theclaw.openai_client.call_chat_completion",
            AsyncMock(return_value={"content": "not json", "model": "gpt-5"}),
        )

        db = _FakeDB(tables={"wbr_email_drafts": []})
        with pytest.raises(ValueError, match="invalid JSON"):
            await generate_email_draft(db, "c1")

    @pytest.mark.asyncio
    async def test_raises_on_empty_body(self, monkeypatch):
        from app.services.wbr.email_drafts import generate_email_draft

        monkeypatch.setattr(
            "app.services.wbr.email_drafts.gather_client_snapshots",
            lambda db, cid: [{"snapshot_id": "s1", "profile_id": "p1", "marketplace_code": "US", "display_name": "X", "digest": _make_digest("US")}],
        )
        monkeypatch.setattr(
            "app.services.theclaw.openai_client.call_chat_completion",
            AsyncMock(return_value={"content": json.dumps({"subject": "Subj", "body": ""}), "model": "gpt-5"}),
        )

        db = _FakeDB(tables={"wbr_email_drafts": []})
        with pytest.raises(ValueError, match="empty email body"):
            await generate_email_draft(db, "c1")


# ---------------------------------------------------------------------------
# Skill tools registry — wbr_weekly_email_draft
# ---------------------------------------------------------------------------


class TestEmailDraftSkillTools:
    def test_skill_registered_with_correct_tools(self):
        from app.services.theclaw.skill_tools import get_skill_tool_definitions

        defs = get_skill_tool_definitions("wbr_weekly_email_draft")
        assert defs is not None
        assert len(defs) == 2
        names = {d["function"]["name"] for d in defs}
        assert names == {"draft_wbr_email", "list_wbr_profiles"}

    def test_draft_wbr_email_is_mutating(self):
        from app.services.theclaw.skill_tools import tool_mutates

        assert tool_mutates("wbr_weekly_email_draft", "draft_wbr_email") is True

    def test_list_wbr_profiles_is_not_mutating(self):
        from app.services.theclaw.skill_tools import tool_mutates

        assert tool_mutates("wbr_weekly_email_draft", "list_wbr_profiles") is False

    @pytest.mark.asyncio
    async def test_execute_draft_wbr_email_calls_bridge(self, monkeypatch):
        from app.services.theclaw.skill_tools import execute_skill_tool_call

        fake_draft = {
            "id": "draft-1",
            "subject": "Weekly WBR",
            "body": "Hi Team,",
            "marketplace_scope": "US,CA",
            "week_ending": "2026-03-15",
        }
        monkeypatch.setattr(
            "app.services.theclaw.wbr_skill_bridge.generate_wbr_email_draft",
            AsyncMock(return_value=fake_draft),
        )

        tool_result = await execute_skill_tool_call(
            skill_id="wbr_weekly_email_draft",
            tool_name="draft_wbr_email",
            arguments_json='{"client":"Whoosh"}',
        )
        result = json.loads(tool_result["content"])
        assert result["subject"] == "Weekly WBR"
        assert tool_result["outcome"] == "mutation_executed"

    @pytest.mark.asyncio
    async def test_execute_draft_wbr_email_error_on_missing_client(self):
        from app.services.theclaw.skill_tools import execute_skill_tool_call

        tool_result = await execute_skill_tool_call(
            skill_id="wbr_weekly_email_draft",
            tool_name="draft_wbr_email",
            arguments_json='{"client":""}',
        )
        result = json.loads(tool_result["content"])
        assert "error" in result
        # Error on mutating tool -> mutation_not_executed
        assert tool_result["outcome"] == "mutation_not_executed"

    def test_wbr_summary_skill_not_affected(self):
        """Ensure existing wbr_summary skill still works correctly."""
        from app.services.theclaw.skill_tools import get_skill_tool_definitions

        defs = get_skill_tool_definitions("wbr_summary")
        assert defs is not None
        assert len(defs) == 2
        names = {d["function"]["name"] for d in defs}
        assert names == {"lookup_wbr", "list_wbr_profiles"}


# ---------------------------------------------------------------------------
# Bridge: resolve_client_id
# ---------------------------------------------------------------------------


class TestResolveClientId:
    """resolve_client_id only considers clients with active WBR profiles
    and requires unambiguous matches for partial lookups."""

    def _patch(self, monkeypatch, tables):
        monkeypatch.setattr("supabase.create_client", lambda url, key: _FakeDB(tables=tables))
        monkeypatch.setattr("app.config.settings", MagicMock(supabase_url="http://fake", supabase_service_role="key"))

    def test_exact_wbr_enabled_match(self, monkeypatch):
        from app.services.theclaw.wbr_skill_bridge import resolve_client_id

        self._patch(monkeypatch, {
            "agency_clients": [{"id": "c1", "name": "Basari World"}],
            "wbr_profiles": [{"client_id": "c1", "status": "active"}],
        })
        assert resolve_client_id("Basari World") == "c1"

    def test_case_insensitive_match(self, monkeypatch):
        from app.services.theclaw.wbr_skill_bridge import resolve_client_id

        self._patch(monkeypatch, {
            "agency_clients": [{"id": "c1", "name": "Basari World"}],
            "wbr_profiles": [{"client_id": "c1", "status": "active"}],
        })
        assert resolve_client_id("basari world") == "c1"

    def test_unique_partial_wbr_match(self, monkeypatch):
        from app.services.theclaw.wbr_skill_bridge import resolve_client_id

        self._patch(monkeypatch, {
            "agency_clients": [{"id": "c1", "name": "Basari World"}],
            "wbr_profiles": [{"client_id": "c1", "status": "active"}],
        })
        assert resolve_client_id("basari") == "c1"

    def test_ambiguous_partial_returns_none(self, monkeypatch):
        """Two WBR-enabled clients both match 'brand' → ambiguous → None."""
        from app.services.theclaw.wbr_skill_bridge import resolve_client_id

        self._patch(monkeypatch, {
            "agency_clients": [
                {"id": "c1", "name": "Brand Alpha"},
                {"id": "c2", "name": "Brand Beta"},
            ],
            "wbr_profiles": [
                {"client_id": "c1", "status": "active"},
                {"client_id": "c2", "status": "active"},
            ],
        })
        assert resolve_client_id("brand") is None

    def test_non_wbr_client_not_selected(self, monkeypatch):
        """Client exists but has no active WBR profiles → not eligible."""
        from app.services.theclaw.wbr_skill_bridge import resolve_client_id

        self._patch(monkeypatch, {
            "agency_clients": [{"id": "c1", "name": "Whoosh"}],
            "wbr_profiles": [],  # no active profiles
        })
        assert resolve_client_id("Whoosh") is None

    def test_draft_profile_not_counted(self, monkeypatch):
        """Client with only draft (non-active) profiles → not eligible."""
        from app.services.theclaw.wbr_skill_bridge import resolve_client_id

        self._patch(monkeypatch, {
            "agency_clients": [{"id": "c1", "name": "Whoosh"}],
            "wbr_profiles": [{"client_id": "c1", "status": "draft"}],
        })
        assert resolve_client_id("Whoosh") is None

    def test_returns_none_when_no_match(self, monkeypatch):
        from app.services.theclaw.wbr_skill_bridge import resolve_client_id

        self._patch(monkeypatch, {
            "agency_clients": [{"id": "c1", "name": "Whoosh"}],
            "wbr_profiles": [{"client_id": "c1", "status": "active"}],
        })
        assert resolve_client_id("NoSuchClient") is None

    def test_returns_none_for_empty_input(self, monkeypatch):
        from app.services.theclaw.wbr_skill_bridge import resolve_client_id

        self._patch(monkeypatch, {
            "agency_clients": [],
            "wbr_profiles": [],
        })
        assert resolve_client_id("") is None

    def test_partial_match_ignores_non_wbr_clients(self, monkeypatch):
        """Partial 'who' matches both Whoosh (WBR) and Wholefoods (no WBR).
        Only Whoosh has active profiles → unambiguous → resolves."""
        from app.services.theclaw.wbr_skill_bridge import resolve_client_id

        self._patch(monkeypatch, {
            "agency_clients": [
                {"id": "c1", "name": "Whoosh"},
                {"id": "c2", "name": "Wholefoods"},
            ],
            "wbr_profiles": [
                {"client_id": "c1", "status": "active"},
                # c2 has no profile
            ],
        })
        assert resolve_client_id("who") == "c1"


# ---------------------------------------------------------------------------
# Bridge: generate_wbr_email_draft (bridge layer)
# ---------------------------------------------------------------------------


class TestBridgeGenerateWbrEmailDraft:
    @pytest.mark.asyncio
    async def test_returns_no_client_when_not_found(self, monkeypatch):
        from app.services.theclaw.wbr_skill_bridge import generate_wbr_email_draft

        monkeypatch.setattr(
            "app.services.theclaw.wbr_skill_bridge.resolve_client_id",
            lambda name: None,
        )

        result = await generate_wbr_email_draft("UnknownClient")
        assert result["status"] == "no_client"

    @pytest.mark.asyncio
    async def test_returns_no_data_on_value_error(self, monkeypatch):
        from app.services.theclaw.wbr_skill_bridge import generate_wbr_email_draft

        monkeypatch.setattr(
            "app.services.theclaw.wbr_skill_bridge.resolve_client_id",
            lambda name: "c1",
        )
        monkeypatch.setattr("supabase.create_client", lambda url, key: MagicMock())
        monkeypatch.setattr("app.config.settings", MagicMock(supabase_url="http://fake", supabase_service_role="key"))
        monkeypatch.setattr(
            "app.services.wbr.email_drafts.generate_email_draft",
            AsyncMock(side_effect=ValueError("No active WBR profiles")),
        )

        result = await generate_wbr_email_draft("Whoosh")
        assert result["status"] == "no_data"

    @pytest.mark.asyncio
    async def test_returns_draft_on_success(self, monkeypatch):
        from app.services.theclaw.wbr_skill_bridge import generate_wbr_email_draft

        fake_draft = {"id": "d1", "subject": "WBR Update", "body": "Hi Team,"}

        monkeypatch.setattr(
            "app.services.theclaw.wbr_skill_bridge.resolve_client_id",
            lambda name: "c1",
        )
        monkeypatch.setattr("supabase.create_client", lambda url, key: MagicMock())
        monkeypatch.setattr("app.config.settings", MagicMock(supabase_url="http://fake", supabase_service_role="key"))
        monkeypatch.setattr(
            "app.services.wbr.email_drafts.generate_email_draft",
            AsyncMock(return_value=fake_draft),
        )

        result = await generate_wbr_email_draft("Whoosh")
        assert result["id"] == "d1"
        assert result["subject"] == "WBR Update"


# ---------------------------------------------------------------------------
# SKILL.md presence
# ---------------------------------------------------------------------------


class TestSkillMdPresence:
    def test_skill_md_exists_and_has_correct_id(self):
        import pathlib

        skill_path = pathlib.Path(__file__).parent.parent / "app" / "services" / "theclaw" / "skills" / "wbr" / "wbr_weekly_email_draft" / "SKILL.md"
        assert skill_path.exists(), f"SKILL.md not found at {skill_path}"
        content = skill_path.read_text()
        assert "id: wbr_weekly_email_draft" in content
        assert "draft_wbr_email" in content
        assert "list_wbr_profiles" in content
        assert "not inside a code block" in content
        assert "normal Slack mrkdwn text" in content
        assert "Treat follow-up instructions as revision constraints" in content
        assert "don't mention inventory" in content
