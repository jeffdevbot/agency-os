"""Tests for WBR Pacvue import parsing and service behavior."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import MagicMock

import pytest
from openpyxl import Workbook

from app.services.wbr.pacvue_imports import PacvueImportService, parse_pacvue_workbook
from app.services.wbr.profiles import WBRValidationError


def _build_workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _build_multisheet_workbook_bytes(sheet_rows: list[tuple[str, list[list[object]]]]) -> bytes:
    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    for title, rows in sheet_rows:
        sheet = workbook.create_sheet(title)
        for row in rows:
            sheet.append(row)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _force_bad_dimension(file_bytes: bytes, sheet_name: str = "xl/worksheets/sheet1.xml") -> bytes:
    source = io.BytesIO(file_bytes)
    output = io.BytesIO()

    with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(output, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == sheet_name:
                data = data.replace(b'<dimension ref="A1:C3"/>', b'<dimension ref="A1"/>')
                data = data.replace(b'<dimension ref="A1:C4"/>', b'<dimension ref="A1"/>')
                data = data.replace(b'<dimension ref="A1:C6"/>', b'<dimension ref="A1"/>')
            zout.writestr(item, data)

    return output.getvalue()


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.delete.return_value = table
    table.eq.return_value = table
    table.in_.return_value = table
    table.gte.return_value = table
    table.lte.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.range.return_value = table
    resp = MagicMock()
    resp.data = response_data if response_data is not None else []
    table.execute.return_value = resp
    return table


def _multi_table_db(mapping: dict[str, list[MagicMock]]) -> MagicMock:
    iterators = {name: iter(tables) for name, tables in mapping.items()}

    def router(name: str) -> MagicMock:
        return next(iterators[name])

    db = MagicMock()
    db.table.side_effect = router
    return db


class TestParsePacvueWorkbook:
    def test_detects_header_after_metadata_rows(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Level", "Campaign"],
                ["Time Range", "03/02/2026 - 03/08/2026"],
                ["Download Time", "2026-03-12 12:21:38"],
                [],
                ["Name", "state", "CampaignTagNames"],
                ["Screen Shine - Duo | SPM", "enabled", "Screen Shine | Duo / Perf"],
            ]
        )

        parsed = parse_pacvue_workbook(file_bytes)

        assert parsed.header_row_index == 4
        assert parsed.rows_read == 1
        assert parsed.records[0].campaign_name == "Screen Shine - Duo | SPM"
        assert parsed.records[0].leaf_row_label == "Screen Shine | Duo"
        assert parsed.records[0].goal_code == "Perf"

    def test_dedupes_identical_campaign_rows(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Name", "CampaignTagNames"],
                ["Campaign A", "Screen Shine | Pro / Perf"],
                ["Campaign A", "Screen Shine | Pro / Perf"],
            ]
        )

        parsed = parse_pacvue_workbook(file_bytes)

        assert parsed.rows_read == 2
        assert parsed.duplicate_rows_skipped == 1
        assert len(parsed.records) == 1

    def test_detects_header_on_non_active_sheet(self):
        file_bytes = _build_multisheet_workbook_bytes(
            [
                ("Intro", [["Level", "Campaign"], ["Download Time", "2026-03-12 12:21:38"]]),
                (
                    "Campaigns",
                    [
                        ["Level", "Campaign"],
                        ["Time Range", "03/02/2026 - 03/08/2026"],
                        [],
                        ["Name", "state", "CampaignTagNames"],
                        ["Screen Shine - Duo | SPM", "enabled", "Screen Shine | Duo / Perf"],
                    ],
                ),
            ]
        )

        parsed = parse_pacvue_workbook(file_bytes)

        assert parsed.sheet_title == "Campaigns"
        assert parsed.header_row_index == 3
        assert parsed.records[0].campaign_name == "Screen Shine - Duo | SPM"

    def test_rejects_conflicting_duplicate_campaign_rows(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Name", "CampaignTagNames"],
                ["Campaign A", "Screen Shine | Pro / Perf"],
                ["Campaign A", "Screen Shine | Pro / Harv"],
            ]
        )

        with pytest.raises(WBRValidationError, match="conflicting Pacvue tags"):
            parse_pacvue_workbook(file_bytes)

    def test_prefers_live_row_over_archived_zero_conflict(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Name", "state", "CampaignTagNames", "Impression", "Click", "Spend", "Sales", "Orders"],
                ["Campaign A", "enabled", "Screen Shine | Pro / Rsrch", 31905, 269, 604.84, 3335.59, 15],
                ["Campaign A", "archived", "Screen Shine | Pro / Perf", 0, 0, 0, 0, 0],
            ]
        )

        parsed = parse_pacvue_workbook(file_bytes)

        assert parsed.rows_read == 2
        assert parsed.duplicate_rows_skipped == 1
        assert len(parsed.records) == 1
        assert parsed.records[0].goal_code == "Rsrch"
        assert parsed.records[0].raw_tag == "Screen Shine | Pro / Rsrch"

    def test_rejects_unsupported_goal_suffix(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Name", "CampaignTagNames"],
                ["Campaign A", "Screen Shine | Pro / Weird"],
            ]
        )

        with pytest.raises(WBRValidationError, match="unsupported goal suffix"):
            parse_pacvue_workbook(file_bytes)

    def test_accepts_category_as_comp_goal_suffix(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Name", "CampaignTagNames"],
                ["Campaign A", "Screen Shine | Pro / Category"],
            ]
        )

        parsed = parse_pacvue_workbook(file_bytes)

        assert parsed.records[0].goal_code == "Comp"

    def test_accepts_competitor_as_comp_goal_suffix(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Name", "CampaignTagNames"],
                ["Campaign A", "Screen Shine | Pro / Competitor"],
            ]
        )

        parsed = parse_pacvue_workbook(file_bytes)

        assert parsed.records[0].goal_code == "Comp"

    def test_skips_invalid_tag_rows_and_keeps_valid_rows(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Name", "CampaignTagNames"],
                ["Valid Campaign", "Screen Shine | Pro / Perf"],
                ["Invalid Campaign", "Screen Shine | Pro / Weird"],
                ["Also Invalid", "Screen Shine | Duo / Perf, Screen Shine | Pro / Rank"],
            ]
        )

        parsed = parse_pacvue_workbook(file_bytes)

        assert parsed.rows_read == 3
        assert parsed.invalid_rows_skipped == 2
        assert len(parsed.records) == 1
        assert parsed.records[0].campaign_name == "Valid Campaign"
        assert any("unsupported goal suffix" in warning for warning in parsed.warnings)
        assert any("must contain exactly one tag value" in warning for warning in parsed.warnings)

    def test_handles_bad_sheet_dimension_metadata(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Level", "Campaign", None],
                ["Time Range", "03/02/2026 - 03/08/2026", None],
                [],
                ["Name", "state", "CampaignTagNames"],
                ["Screen Shine - Duo | SPM", "enabled", "Screen Shine | Duo / Perf"],
            ]
        )
        broken_bytes = _force_bad_dimension(file_bytes)

        parsed = parse_pacvue_workbook(broken_bytes)

        assert parsed.header_row_index == 3
        assert parsed.rows_read == 1
        assert parsed.records[0].leaf_row_label == "Screen Shine | Duo"

    def test_skips_placeholder_unmapped_tags(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Name", "state", "CampaignTagNames"],
                ["Mapped Campaign", "enabled", "Screen Shine | Duo / Perf"],
                ["Unmapped Campaign", "paused", "--"],
            ]
        )

        parsed = parse_pacvue_workbook(file_bytes)

        assert parsed.rows_read == 2
        assert parsed.unmapped_rows_skipped == 1
        assert len(parsed.records) == 1
        assert parsed.records[0].campaign_name == "Mapped Campaign"

    def test_skips_total_footer_row_without_tag(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Name", "state", "CampaignTagNames"],
                ["Mapped Campaign", "enabled", "Screen Shine | Duo / Perf"],
                ["total:", None, None],
            ]
        )

        parsed = parse_pacvue_workbook(file_bytes)

        assert parsed.rows_read == 1
        assert len(parsed.records) == 1
        assert parsed.records[0].campaign_name == "Mapped Campaign"

    def test_accepts_new_pacvue_header_format(self):
        # Pacvue 2026 export renamed columns: "Name" → "Campaign Name",
        # "CampaignTagNames" → "Campaign Tag Name", "state" → "State".
        file_bytes = _build_workbook_bytes(
            [
                ["Level", "Campaign"],
                ["Compare Date", "03/09/2026 - 05/07/2026 vs 01/08/2026 - 03/08/2026"],
                ["Download Time", "2026-05-07 13:42:08"],
                [],
                ["Campaign Name", "State", "Campaign Targeting Type", "Campaign Tag Name", "Spend", "Sales", "Orders"],
                ["Campaign A", "enabled", "manual", "Screen Shine | Pro / Perf", 5428.4, 72289.79, 1535],
                ["total:", None, None, None, 38109.86, 204675.96, 4483],
            ]
        )

        parsed = parse_pacvue_workbook(file_bytes)

        assert parsed.header_row_index == 4
        assert parsed.rows_read == 1
        assert len(parsed.records) == 1
        assert parsed.records[0].campaign_name == "Campaign A"
        assert parsed.records[0].leaf_row_label == "Screen Shine | Pro"
        assert parsed.records[0].goal_code == "Perf"

    def test_archived_zero_dedupe_handles_new_state_column_casing(self):
        # New Pacvue format capitalizes "State" — the archived/zero duplicate
        # detector must remain case-insensitive so live rows still win.
        file_bytes = _build_workbook_bytes(
            [
                ["Campaign Name", "State", "Campaign Tag Name", "Spend", "Sales", "Orders"],
                ["Campaign A", "enabled", "Screen Shine | Pro / Rsrch", 604.84, 3335.59, 15],
                ["Campaign A", "archived", "Screen Shine | Pro / Perf", 0, 0, 0],
            ]
        )

        parsed = parse_pacvue_workbook(file_bytes)

        assert parsed.rows_read == 2
        assert parsed.duplicate_rows_skipped == 1
        assert len(parsed.records) == 1
        assert parsed.records[0].goal_code == "Rsrch"


class TestPacvueImportService:
    def test_import_reactivates_existing_leaf_and_refreshes_mappings(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Name", "CampaignTagNames"],
                ["Campaign A", "Screen Shine | Pro / Perf"],
            ]
        )
        profile = {"id": "p1"}
        batch = {"id": "b1", "import_status": "running"}
        finished_batch = {"id": "b1", "import_status": "success", "rows_read": 1, "rows_loaded": 1}
        inactive_leaf = {"id": "r1", "row_label": "Screen Shine | Pro", "active": False, "sort_order": 10}
        active_leaf = {"id": "r1", "row_label": "Screen Shine | Pro"}

        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([profile])],
                "wbr_pacvue_import_batches": [
                    _chain_table([batch]),
                    _chain_table([finished_batch]),
                ],
                "wbr_rows": [
                    _chain_table([inactive_leaf]),   # existing leaf query
                    _chain_table([inactive_leaf]),   # reactivation update
                    _chain_table([active_leaf]),     # active leaf lookup for mapping insert
                ],
                "wbr_pacvue_campaign_map": [
                    _chain_table([{"id": "m1"}]),    # insert inactive mappings
                    _chain_table([]),                # deactivate old active mappings
                    _chain_table([{"id": "m1"}]),    # activate new batch mappings
                ],
            }
        )

        svc = PacvueImportService(db)
        result = svc.import_workbook(
            profile_id="p1",
            file_name="pacvue.xlsx",
            file_bytes=file_bytes,
            user_id="u1",
        )

        assert result["batch"]["import_status"] == "success"
        assert result["summary"]["rows_loaded"] == 1
        assert result["summary"]["reactivated_leaf_rows"] == 1
        assert result["summary"]["created_leaf_rows"] == 0
        assert result["summary"]["unmapped_rows_skipped"] == 0
        assert result["summary"]["invalid_rows_skipped"] == 0

    def test_import_skips_invalid_rows_and_returns_warning_summary(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Name", "CampaignTagNames"],
                ["Campaign A", "Screen Shine | Pro / Perf"],
                ["Campaign B", "Screen Shine | Pro / Weird"],
            ]
        )
        profile = {"id": "p1"}
        batch = {"id": "b1", "import_status": "running"}
        finished_batch = {
            "id": "b1",
            "import_status": "success",
            "rows_read": 2,
            "rows_loaded": 1,
            "error_message": "Skipped 1 invalid Pacvue row.",
        }
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([profile])],
                "wbr_pacvue_import_batches": [
                    _chain_table([batch]),
                    _chain_table([finished_batch]),
                ],
                "wbr_rows": [
                    _chain_table([]),
                    _chain_table([{"id": "leaf-1", "row_label": "Screen Shine | Pro"}]),
                    _chain_table([{"id": "leaf-1", "row_label": "Screen Shine | Pro"}]),
                ],
                "wbr_pacvue_campaign_map": [
                    _chain_table([{"id": "m1"}]),
                    _chain_table([]),
                    _chain_table([{"id": "m1"}]),
                ],
            }
        )

        svc = PacvueImportService(db)
        result = svc.import_workbook(
            profile_id="p1",
            file_name="pacvue.xlsx",
            file_bytes=file_bytes,
            user_id="u1",
        )

        assert result["batch"]["import_status"] == "success"
        assert result["summary"]["rows_loaded"] == 1
        assert result["summary"]["invalid_rows_skipped"] == 1
        assert result["summary"]["warnings"]
        assert "unsupported goal suffix" in result["summary"]["warnings"][0]
        assert (
            "Unmapped / Legacy Campaigns"
            in svc._warning_summary(
                parse_pacvue_workbook(file_bytes)
            )
        )

    def test_rejects_non_xlsx_files(self):
        svc = PacvueImportService(MagicMock())

        with pytest.raises(WBRValidationError, match=".xlsx and .xlsm"):
            svc._validate_file_name("pacvue.csv")

    def test_import_sticky_deactivate_scoped_to_incoming_campaigns(self):
        """Pacvue import should only deactivate prior mappings for campaigns it
        actually re-tags. Manual mappings for campaigns not in the new batch
        must remain active so user-edited mappings survive future imports."""

        file_bytes = _build_workbook_bytes(
            [
                ["Name", "CampaignTagNames"],
                ["Campaign A", "Screen Shine | Pro / Perf"],
            ]
        )
        profile = {"id": "p1"}
        batch = {"id": "b1", "import_status": "running"}
        finished_batch = {"id": "b1", "import_status": "success", "rows_read": 1, "rows_loaded": 1}
        active_leaf = {"id": "r1", "row_label": "Screen Shine | Pro", "active": True, "sort_order": 10}

        # The deactivate update step is the third call on the mappings table
        # (after insert and before activate). Its call args are what we're
        # asserting against.
        deactivate_table = _chain_table([])

        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([profile])],
                "wbr_pacvue_import_batches": [
                    _chain_table([batch]),
                    _chain_table([finished_batch]),
                ],
                "wbr_rows": [
                    _chain_table([active_leaf]),
                    _chain_table([active_leaf]),
                ],
                "wbr_pacvue_campaign_map": [
                    _chain_table([{"id": "m1"}]),  # insert new (inactive) mappings
                    deactivate_table,              # deactivate prior actives
                    _chain_table([{"id": "m1"}]),  # activate new batch mappings
                ],
            }
        )

        svc = PacvueImportService(db)
        result = svc.import_workbook(
            profile_id="p1",
            file_name="pacvue.xlsx",
            file_bytes=file_bytes,
            user_id="u1",
        )

        assert result["summary"]["rows_loaded"] == 1

        # The deactivate step must scope to the incoming campaign names via
        # `.in_("campaign_name", [...])`. Without this scoping, manual mappings
        # for campaigns not in the new batch would also be deactivated.
        in_calls = deactivate_table.in_.call_args_list
        assert in_calls, "expected deactivate step to call .in_(...) on the table"
        in_field, in_values = in_calls[0].args
        assert in_field == "campaign_name"
        assert list(in_values) == ["Campaign A"]

    def test_deactivate_chunks_campaign_names_to_avoid_url_length_limit(self):
        # Pacvue imports with many long campaign names previously sent a single
        # `.in_(...)` filter, blowing past the Supabase gateway URL-length cap
        # and surfacing as a generic "Bad Request" error. Confirm chunking.
        from app.services.wbr.pacvue_imports import _DEACTIVATE_CHUNK_SIZE

        n_campaigns = _DEACTIVATE_CHUNK_SIZE * 2 + 5  # forces 3 chunks
        rows = [["Name", "CampaignTagNames"]]
        for i in range(n_campaigns):
            rows.append([f"Campaign {i:04d}", "Screen Shine | Pro / Perf"])
        file_bytes = _build_workbook_bytes(rows)

        profile = {"id": "p1"}
        batch = {"id": "b1", "import_status": "running"}
        finished_batch = {
            "id": "b1",
            "import_status": "success",
            "rows_read": n_campaigns,
            "rows_loaded": n_campaigns,
        }
        active_leaf = {"id": "r1", "row_label": "Screen Shine | Pro", "active": True, "sort_order": 10}

        # Each deactivate chunk re-acquires a fresh table mock, so we need one
        # _chain_table per chunk (3) in addition to insert + activate.
        deactivate_tables = [_chain_table([]) for _ in range(3)]

        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([profile])],
                "wbr_pacvue_import_batches": [
                    _chain_table([batch]),
                    _chain_table([finished_batch]),
                ],
                "wbr_rows": [
                    _chain_table([active_leaf]),
                    _chain_table([active_leaf]),
                ],
                "wbr_pacvue_campaign_map": [
                    _chain_table([{"id": "m1"}]),
                    *deactivate_tables,
                    _chain_table([{"id": "m1"}]),
                ],
            }
        )

        svc = PacvueImportService(db)
        svc.import_workbook(
            profile_id="p1",
            file_name="pacvue.xlsx",
            file_bytes=file_bytes,
            user_id="u1",
        )

        chunk_sizes = [
            len(list(table.in_.call_args_list[0].args[1]))
            for table in deactivate_tables
            if table.in_.call_args_list
        ]
        assert len(chunk_sizes) == 3, (
            f"expected 3 deactivate chunks for {n_campaigns} campaigns at "
            f"chunk size {_DEACTIVATE_CHUNK_SIZE}, got {len(chunk_sizes)}"
        )
        for size in chunk_sizes:
            assert size <= _DEACTIVATE_CHUNK_SIZE
        assert sum(chunk_sizes) == n_campaigns
