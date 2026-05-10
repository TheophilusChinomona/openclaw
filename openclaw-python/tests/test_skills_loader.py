"""Tests for the SkillsLoader."""

from pathlib import Path

import pytest

from openclaw.skills.loader import Skill, load_skill, load_skills


SKILL_CONTENT = """\
---
name: my-skill
description: Does something useful
---
## My Skill

This skill does something useful.
More instructions here.
"""


def test_load_skill_parses_frontmatter(tmp_path: Path):
    skill_file = tmp_path / "my-skill.md"
    skill_file.write_text(SKILL_CONTENT)
    skill = load_skill(skill_file)
    assert skill.name == "my-skill"
    assert skill.description == "Does something useful"
    assert "My Skill" in skill.body
    assert "More instructions" in skill.body


def test_load_skill_body_excludes_frontmatter(tmp_path: Path):
    skill_file = tmp_path / "s.md"
    skill_file.write_text(SKILL_CONTENT)
    skill = load_skill(skill_file)
    assert "---" not in skill.body


def test_load_skills_loads_all(tmp_path: Path):
    for name in ["alpha", "beta", "gamma"]:
        (tmp_path / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: {name} skill\n---\n# {name}\nContent."
        )
    skills = load_skills(tmp_path)
    names = [s.name for s in skills]
    assert "alpha" in names
    assert "beta" in names
    assert "gamma" in names


def test_load_skills_filtered_by_name(tmp_path: Path):
    for name in ["alpha", "beta", "gamma"]:
        (tmp_path / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: desc\n---\nBody."
        )
    skills = load_skills(tmp_path, names=["alpha", "gamma"])
    names = [s.name for s in skills]
    assert "alpha" in names
    assert "gamma" in names
    assert "beta" not in names


def test_load_skills_empty_dir(tmp_path: Path):
    skills = load_skills(tmp_path)
    assert skills == []


def test_skill_missing_frontmatter(tmp_path: Path):
    skill_file = tmp_path / "plain.md"
    skill_file.write_text("# Just a plain markdown file\nNo frontmatter here.")
    skill = load_skill(skill_file)
    # Falls back to filename as name, empty description
    assert skill.name == "plain"
    assert "plain markdown file" in skill.body
