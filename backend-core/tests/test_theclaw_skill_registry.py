from __future__ import annotations

from app.services.theclaw.skill_registry import (
    build_available_skills_xml,
    get_skill_by_id,
    load_skills,
)


def test_load_skills_includes_task_extraction_markdown_skill():
    skills = load_skills()
    assert skills

    task_extraction = get_skill_by_id("task_extraction")
    assert task_extraction is not None
    assert task_extraction.name == "Task Extraction"
    assert task_extraction.primary_category == "ppc"
    assert "ppc" in task_extraction.categories
    assert "wbr" in task_extraction.categories
    assert "meeting summaries" in task_extraction.description.lower()
    assert "the claw: task extraction" in task_extraction.system_prompt.lower()


def test_build_available_skills_xml_contains_expected_tags():
    xml = build_available_skills_xml()
    assert "<available_skills>" in xml
    assert "<id>task_extraction</id>" in xml
    assert "<description>" in xml
    assert "<location>" in xml
