"""Skill loader — parses SKILL.md files (YAML frontmatter + markdown body)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


@dataclass
class Skill:
    name: str
    description: str = ""
    body: str = ""


def load_skill(path: Path) -> Skill:
    """Parse a SKILL.md file into a Skill dataclass."""
    text = path.read_text()
    match = _FRONTMATTER_RE.match(text)

    if match:
        frontmatter_raw = match.group(1)
        body = text[match.end():].strip()
        try:
            meta = yaml.safe_load(frontmatter_raw) or {}
        except yaml.YAMLError:
            meta = {}
    else:
        meta = {}
        body = text.strip()

    name = str(meta.get("name", path.stem))
    description = str(meta.get("description", ""))
    return Skill(name=name, description=description, body=body)


def load_skills(
    skills_dir: Path,
    names: list[str] | None = None,
) -> list[Skill]:
    """Load all *.md files from skills_dir, optionally filtered by name."""
    if not skills_dir.exists():
        return []
    skills = [load_skill(p) for p in sorted(skills_dir.glob("*.md"))]
    if names is not None:
        skills = [s for s in skills if s.name in names]
    return skills
