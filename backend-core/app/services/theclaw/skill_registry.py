"""Markdown skill registry helpers for The Claw."""

from __future__ import annotations

from dataclasses import dataclass
import html
import logging
import os
from pathlib import Path
import re
import threading
import time

_logger = logging.getLogger(__name__)

_SKILLS_BASE_DIR = Path(__file__).resolve().parent / "skills"
_FRONTMATTER_DELIM = "---"
_P_AND_L_ALIASES = {"p&l", "pnl", "p and l", "p_and_l", "p/l"}
_DEFAULT_SKILL_CACHE_TTL_SECONDS = 60.0
_skill_cache_lock = threading.Lock()
_skill_cache: tuple["TheClawSkill", ...] | None = None
_skill_cache_loaded_at: float = 0.0


@dataclass(frozen=True)
class TheClawSkill:
    skill_id: str
    name: str
    description: str
    primary_category: str
    categories: tuple[str, ...]
    when_to_use: str
    trigger_hints: tuple[str, ...]
    system_prompt: str
    path: Path


def _normalize_category(value: str) -> str:
    category = (value or "").strip().lower()
    if category in _P_AND_L_ALIASES:
        return "p&l"
    return category


def _parse_csv(value: str) -> tuple[str, ...]:
    if not value:
        return tuple()
    items = [item.strip() for item in value.split(",")]
    normalized = [item for item in items if item]
    return tuple(normalized)


def _parse_frontmatter(raw_text: str) -> tuple[dict[str, str], str]:
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return {}, raw_text

    end_index = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            end_index = i
            break
    if end_index == -1:
        return {}, raw_text

    metadata: dict[str, str] = {}
    for line in lines[1:end_index]:
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip().lower()
        value = raw_value.strip()
        if key:
            metadata[key] = value

    body = "\n".join(lines[end_index + 1 :]).strip()
    return metadata, body


def _parse_markdown_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    def _commit_current() -> None:
        nonlocal current_name, current_lines
        if current_name is None:
            return
        sections[current_name] = "\n".join(current_lines).strip()
        current_name = None
        current_lines = []

    for line in body.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            _commit_current()
            current_name = match.group(1).strip().lower()
            continue
        if current_name is not None:
            current_lines.append(line)
    _commit_current()
    return sections


def _load_skill_file(path: Path) -> TheClawSkill | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        _logger.warning("Failed reading The Claw skill file %s: %s", path, exc)
        return None

    metadata, body = _parse_frontmatter(raw)
    sections = _parse_markdown_sections(body)
    skill_id = (metadata.get("id") or path.parent.name).strip()
    name = (metadata.get("name") or skill_id).strip()
    description = (metadata.get("description") or metadata.get("when_to_use") or name).strip()
    primary_category = _normalize_category(metadata.get("category") or "")
    if not primary_category:
        primary_category = "general"

    configured_categories = tuple(
        _normalize_category(category)
        for category in _parse_csv(metadata.get("categories", ""))
        if _normalize_category(category)
    )
    categories = tuple(dict.fromkeys((primary_category, *configured_categories)).keys())
    when_to_use = (metadata.get("when_to_use") or "").strip()
    trigger_hints = tuple(
        hint.lower()
        for hint in _parse_csv(metadata.get("trigger_hints", ""))
        if hint.strip()
    )
    system_prompt = (sections.get("system prompt") or "").strip()

    if not skill_id or not system_prompt:
        _logger.warning("Skipping invalid The Claw skill file: %s", path)
        return None

    return TheClawSkill(
        skill_id=skill_id,
        name=name,
        description=description,
        primary_category=primary_category,
        categories=categories,
        when_to_use=when_to_use,
        trigger_hints=trigger_hints,
        system_prompt=system_prompt,
        path=path,
    )


def _get_skill_cache_ttl_seconds() -> float:
    raw = os.environ.get("THECLAW_SKILL_CACHE_TTL_SECONDS", "").strip()
    if not raw:
        return _DEFAULT_SKILL_CACHE_TTL_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_SKILL_CACHE_TTL_SECONDS
    return value


def _load_skills_from_disk() -> tuple[TheClawSkill, ...]:
    if not _SKILLS_BASE_DIR.exists():
        return tuple()

    skill_files = sorted(_SKILLS_BASE_DIR.rglob("SKILL.md"))
    loaded = [_load_skill_file(path) for path in skill_files]
    return tuple(skill for skill in loaded if skill is not None)


def invalidate_skills_cache() -> None:
    global _skill_cache, _skill_cache_loaded_at  # noqa: PLW0603
    with _skill_cache_lock:
        _skill_cache = None
        _skill_cache_loaded_at = 0.0


def load_skills(*, force_reload: bool = False) -> tuple[TheClawSkill, ...]:
    global _skill_cache, _skill_cache_loaded_at  # noqa: PLW0603

    ttl_seconds = _get_skill_cache_ttl_seconds()
    now = time.monotonic()
    with _skill_cache_lock:
        cache_valid = (
            _skill_cache is not None
            and ttl_seconds > 0
            and (now - _skill_cache_loaded_at) < ttl_seconds
        )
        if not force_reload and cache_valid:
            return _skill_cache

    loaded = _load_skills_from_disk()
    with _skill_cache_lock:
        _skill_cache = loaded
        _skill_cache_loaded_at = time.monotonic()
        return _skill_cache


def get_skill_by_id(skill_id: str) -> TheClawSkill | None:
    target = (skill_id or "").strip().lower()
    if not target:
        return None
    for skill in load_skills():
        if skill.skill_id.lower() == target:
            return skill
    return None


def _xml_escape(value: str) -> str:
    return html.escape(value or "", quote=True)


def build_available_skills_xml(*, skills: tuple[TheClawSkill, ...] | None = None) -> str:
    selected = skills if skills is not None else load_skills()
    lines = ["<available_skills>"]
    for skill in selected:
        trigger_hints = [hint for hint in skill.trigger_hints if hint]
        lines.extend(
            [
                "  <skill>",
                f"    <id>{_xml_escape(skill.skill_id)}</id>",
                f"    <name>{_xml_escape(skill.name)}</name>",
                f"    <description>{_xml_escape(skill.description)}</description>",
                f"    <when_to_use>{_xml_escape(skill.when_to_use)}</when_to_use>",
                "    <trigger_hints>",
            ]
        )
        for hint in trigger_hints:
            lines.append(f"      <hint>{_xml_escape(hint)}</hint>")
        lines.extend(
            [
                "    </trigger_hints>",
                f"    <location>{_xml_escape(str(skill.path.parent))}</location>",
                "  </skill>",
            ]
        )
    lines.append("</available_skills>")
    return "\n".join(lines)
