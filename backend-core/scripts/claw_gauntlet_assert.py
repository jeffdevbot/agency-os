#!/usr/bin/env python3
"""Machine-checkable assertions for Claw Gauntlet transcript JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_GENERIC_FALLBACK_MARKERS = (
    "could you rephrase and try again",
    "i couldn't complete that flow",
    "i hit an issue while processing",
)


def _first_text_by_name(transcript: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in transcript:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        messages = row.get("messages")
        if not isinstance(messages, list) or not messages:
            out[name] = ""
            continue
        first = messages[0]
        if not isinstance(first, dict):
            out[name] = ""
            continue
        out[name] = str(first.get("text") or "")
    return out


def validate_transcript(transcript: list[dict]) -> list[str]:
    errors: list[str] = []
    by_name = _first_text_by_name(transcript)

    checks: list[tuple[str, tuple[str, ...]]] = [
        ("baseline_1", ("I can help with", "SOP")),
        ("baseline_2", ("Test",)),
        ("baseline_3", ("Brands", "Test")),
        ("sop_1", ("Found KB context",)),
        ("sop_2", ("Task Title:", "Task Description:")),
        ("sop_3", ("execution-ready", "Owner/assignee", "ASIN/SKU scope")),
        ("meeting_fixture", ("Draft tasks (approval only) with SOP mapping",)),
        ("meeting_extract", ("Draft tasks (approval only) with SOP mapping",)),
        ("novice_1", ("Start with this first",)),
        ("novice_3", ("only need these missing inputs",)),
        ("mutation_create", ("Reply `confirm` to proceed",)),
        ("mutation_confirm_2", ("pending task proposal",)),
        ("planner_1", ("ClickUp Mapping Audit", "missing:")),
        ("planner_2", ("Two-sprint plan", "Open questions")),
    ]

    for name, required_tokens in checks:
        text = by_name.get(name)
        if text is None:
            errors.append(f"Missing turn: {name}")
            continue
        lowered = text.lower()
        for token in required_tokens:
            if token.lower() not in lowered:
                errors.append(f"Turn {name} missing token: {token}")

    mutation_confirm_1 = by_name.get("mutation_confirm_1", "")
    if mutation_confirm_1:
        lowered = mutation_confirm_1.lower()
        if "already created" not in lowered and "created task" not in lowered:
            errors.append("Turn mutation_confirm_1 did not acknowledge create-or-dedupe outcome.")
    else:
        errors.append("Missing turn: mutation_confirm_1")

    for row in transcript:
        name = str(row.get("name") or "").strip() or "<unnamed>"
        messages = row.get("messages")
        if not isinstance(messages, list):
            continue
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            text = str(msg.get("text") or "").strip().lower()
            if any(marker in text for marker in _GENERIC_FALLBACK_MARKERS):
                errors.append(f"Turn {name} contains generic fallback text.")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Claw Gauntlet transcript assertions.")
    parser.add_argument("transcript_path", help="Path to transcript JSON file")
    args = parser.parse_args()

    path = Path(args.transcript_path)
    if not path.exists():
        print(f"[fail] transcript file not found: {path}")
        return 2

    try:
        payload = json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001
        print(f"[fail] could not parse JSON: {exc}")
        return 2
    if not isinstance(payload, list):
        print("[fail] transcript root must be a JSON array")
        return 2

    errors = validate_transcript(payload)
    if errors:
        print(f"[fail] {len(errors)} assertion(s) failed for {path}:")
        for item in errors:
            print(f" - {item}")
        return 1

    print(f"[pass] Claw Gauntlet assertions passed: {path}")
    print(f"[pass] turns={len(payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
