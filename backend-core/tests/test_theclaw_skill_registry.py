from __future__ import annotations

from pathlib import Path
import threading
import time

import app.services.theclaw.skill_registry as skill_registry
from app.services.theclaw.skill_registry import (
    TheClawSkill,
    build_available_skills_xml,
    get_skill_by_id,
    invalidate_skills_cache,
    load_skills,
)


def _fake_skill(*, skill_id: str = "fake_skill") -> TheClawSkill:
    return TheClawSkill(
        skill_id=skill_id,
        name="Fake Skill",
        description="Fake description",
        primary_category="ppc",
        categories=("ppc",),
        when_to_use="When fake input appears.",
        trigger_hints=("fake", "testing"),
        system_prompt="You are fake.",
        path=Path("/tmp/fake/SKILL.md"),
    )


def test_load_skills_includes_task_extraction_markdown_skill():
    skills = load_skills()
    assert skills

    task_extraction = get_skill_by_id("task_extraction")
    assert task_extraction is not None
    assert task_extraction.name == "Task Extraction"
    assert task_extraction.primary_category == "core"
    assert "core" in task_extraction.categories
    assert "ppc" in task_extraction.categories
    assert "wbr" in task_extraction.categories
    assert "meeting summaries" in task_extraction.description.lower()
    assert "the claw: task extraction" in task_extraction.system_prompt.lower()
    assert "task template:" in task_extraction.system_prompt.lower()
    assert "marketplace:" in task_extraction.system_prompt.lower()
    assert "deliverables / requirements" in task_extraction.system_prompt.lower()


def test_build_available_skills_xml_contains_expected_tags():
    xml = build_available_skills_xml()
    assert "<available_skills>" in xml
    assert "<id>task_extraction</id>" in xml
    assert "<description>" in xml
    assert "<when_to_use>" in xml
    assert "<trigger_hints>" in xml
    assert "<hint>" in xml
    assert "<location>" in xml


def test_load_skills_uses_ttl_cache(monkeypatch):
    invalidate_skills_cache()
    calls = {"count": 0}
    fake = _fake_skill()

    def _fake_load() -> tuple[TheClawSkill, ...]:
        calls["count"] += 1
        return (fake,)

    monkeypatch.setenv("THECLAW_SKILL_CACHE_TTL_SECONDS", "999")
    monkeypatch.setattr(skill_registry, "_load_skills_from_disk", _fake_load)

    first = load_skills()
    second = load_skills()

    assert first == (fake,)
    assert second == (fake,)
    assert calls["count"] == 1
    invalidate_skills_cache()


def test_load_skills_zero_ttl_disables_cache(monkeypatch):
    invalidate_skills_cache()
    calls = {"count": 0}

    def _fake_load() -> tuple[TheClawSkill, ...]:
        calls["count"] += 1
        return (_fake_skill(skill_id=f"fake_skill_{calls['count']}"),)

    monkeypatch.setenv("THECLAW_SKILL_CACHE_TTL_SECONDS", "0")
    monkeypatch.setattr(skill_registry, "_load_skills_from_disk", _fake_load)

    _ = load_skills()
    _ = load_skills()

    assert calls["count"] == 2
    invalidate_skills_cache()


def test_load_skills_concurrent_calls_only_load_once(monkeypatch):
    invalidate_skills_cache()
    calls = {"count": 0}
    fake = _fake_skill()
    start_barrier = threading.Barrier(2)

    def _fake_load() -> tuple[TheClawSkill, ...]:
        calls["count"] += 1
        time.sleep(0.05)
        return (fake,)

    monkeypatch.setenv("THECLAW_SKILL_CACHE_TTL_SECONDS", "999")
    monkeypatch.setattr(skill_registry, "_load_skills_from_disk", _fake_load)

    results: list[tuple[TheClawSkill, ...] | None] = [None, None]

    def _runner(index: int) -> None:
        start_barrier.wait()
        results[index] = load_skills()

    threads = [threading.Thread(target=_runner, args=(0,)), threading.Thread(target=_runner, args=(1,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls["count"] == 1
    assert results[0] == (fake,)
    assert results[1] == (fake,)
    invalidate_skills_cache()
