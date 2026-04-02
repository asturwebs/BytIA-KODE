"""Skill loading system - SKILL.md pattern."""
from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    name: str
    description: str = ""
    trigger: str = ""
    instructions: str = ""
    path: Path | None = None


class SkillLoader:
    """Discovers and loads SKILL.md files from skill directories."""

    SKILL_FILE = "SKILL.md"

    def __init__(self, skill_dirs: list[Path] | None = None):
        self.skill_dirs = skill_dirs or []
        self._skills: dict[str, Skill] = {}

    def add_dir(self, path: Path):
        self.skill_dirs.append(path)

    def load_all(self) -> dict[str, Skill]:
        """Scan all skill directories and load SKILL.md files."""
        for d in self.skill_dirs:
            if not d.exists():
                continue
            for item in d.iterdir():
                skill_file = item / self.SKILL_FILE if item.is_dir() else None
                if skill_file and skill_file.exists():
                    skill = self._parse_skill(skill_file)
                    if skill:
                        self._skills[skill.name] = skill
                        logger.debug(f"Loaded skill: {skill.name}")
        return self._skills

    def _parse_skill(self, path: Path) -> Skill | None:
        """Parse a SKILL.md file."""
        try:
            content = path.read_text()
        except Exception as e:
            logger.warning(f"Failed to read {path}: {e}")
            return None

        name = path.parent.name.lower().replace(" ", "-")
        description = ""
        instructions = content
        trigger = ""

        # Extract frontmatter-like metadata
        lines = content.split("\n")
        in_frontmatter = False
        body_start = 0

        for i, line in enumerate(lines):
            if i == 0 and line.strip() == "---":
                in_frontmatter = True
                continue
            if in_frontmatter and line.strip() == "---":
                body_start = i + 1
                break
            if in_frontmatter:
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip().lower()
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                elif line.startswith("trigger:"):
                    trigger = line.split(":", 1)[1].strip()

        instructions = "\n".join(lines[body_start:]).strip()

        return Skill(
            name=name,
            description=description,
            trigger=trigger,
            instructions=instructions,
            path=path,
        )

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def get_relevant(self, query: str) -> list[Skill]:
        """Get skills whose trigger or description matches the query."""
        relevant = []
        q = query.lower()
        for skill in self._skills.values():
            if skill.trigger and skill.trigger.lower() in q:
                relevant.append(skill)
            elif skill.description and skill.description.lower() in q:
                relevant.append(skill)
        return relevant

    def skill_summary(self) -> str:
        """Generate a summary of loaded skills for system prompt."""
        if not self._skills:
            return ""
        lines = ["## Available Skills\n"]
        for name, skill in self._skills.items():
            desc = skill.description or "(no description)"
            lines.append(f"- **{name}**: {desc}")
        return "\n".join(lines)
