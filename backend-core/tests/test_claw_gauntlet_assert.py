from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "claw_gauntlet_assert.py"
_SPEC = importlib.util.spec_from_file_location("claw_gauntlet_assert", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
validate_transcript = _MODULE.validate_transcript


def _base_transcript() -> list[dict]:
    return [
        {"name": "baseline_1", "messages": [{"text": "I can help with SOP support."}]},
        {"name": "baseline_2", "messages": [{"text": "Clients include Test and others."}]},
        {"name": "baseline_3", "messages": [{"text": "Brands for Test are listed."}]},
        {"name": "sop_1", "messages": [{"text": "Found KB context from: coupon SOP"}]},
        {"name": "sop_2", "messages": [{"text": "Task Title: X\nTask Description: Y"}]},
        {
            "name": "sop_3",
            "messages": [{"text": "Before task is execution-ready: Owner/assignee, ASIN/SKU scope"}],
        },
        {
            "name": "meeting_fixture",
            "messages": [{"text": "Draft tasks (approval only) with SOP mapping"}],
        },
        {
            "name": "meeting_extract",
            "messages": [{"text": "Draft tasks (approval only) with SOP mapping"}],
        },
        {"name": "novice_1", "messages": [{"text": "Start with this first"}]},
        {"name": "novice_3", "messages": [{"text": "I only need these missing inputs"}]},
        {"name": "mutation_create", "messages": [{"text": "Reply `confirm` to proceed"}]},
        {"name": "mutation_confirm_1", "messages": [{"text": "A task was already created."}]},
        {"name": "mutation_confirm_2", "messages": [{"text": "There isn't a pending task proposal."}]},
        {"name": "planner_1", "messages": [{"text": "ClickUp Mapping Audit ... missing: clickup_space_id"}]},
        {"name": "planner_2", "messages": [{"text": "Two-sprint plan ... Open questions"}]},
    ]


def test_validate_transcript_passes_for_contract_shape() -> None:
    errors = validate_transcript(_base_transcript())
    assert errors == []


def test_validate_transcript_fails_when_required_token_missing() -> None:
    payload = _base_transcript()
    payload[9]["messages"][0]["text"] = "Need a few inputs."
    errors = validate_transcript(payload)
    assert any("novice_3" in item for item in errors)
