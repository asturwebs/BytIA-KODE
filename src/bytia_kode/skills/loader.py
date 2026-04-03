"""Skill loading system - SKILL.md pattern."""
from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    name: str
    description: str = ""
    trigger: str = ""
    instructions: str = ""
    path: Path | None = None
    verified: bool = False


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
        verified = False

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
                elif line.startswith("verified:"):
                    verified = line.split(":", 1)[1].strip().lower() == "true"

        instructions = "\n".join(lines[body_start:]).strip()

        return Skill(
            name=name,
            description=description,
            trigger=trigger,
            instructions=instructions,
            path=path,
            verified=verified,
        )

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def save_skill(self, name: str, content: str, description: str = "", trigger: str = "") -> Path:
        """Save a new skill to the first skill directory."""
        if not self.skill_dirs:
            raise ValueError("No skill directories configured")
        skill_dir = self.skill_dirs[0]
        skill_path = skill_dir / name / self.SKILL_FILE
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        fm = f"---\nname: {name}\ndescription: {description}\n"
        if trigger:
            fm += f"trigger: {trigger}\n"
        fm += "verified: false\n---\n\n"
        skill_path.write_text(fm + content, encoding="utf-8")
        parsed = self._parse_skill(skill_path)
        if parsed:
            self._skills[name] = parsed
        logger.info(f"Skill saved: {skill_path}")
        return skill_path

    def list_skill_names(self) -> list[str]:
        """List all skill names."""
        return list(self._skills.keys())

    def verify_skill(self, name: str) -> bool:
        """Mark a skill as verified."""
        skill = self._skills.get(name)
        if not skill or not skill.path:
            return False
        content = skill.path.read_text()
        content = content.replace("verified: false", "verified: true", 1)
        skill.path.write_text(content, encoding="utf-8")
        skill.verified = True
        return True

    def get_relevant(self, query: str) -> list[Skill]:
        """Get skills whose trigger, description, or content matches the query."""
        relevant = []
        q = query.lower()
        for skill in self._skills.values():
            score = 0
            if skill.trigger:
                for kw in skill.trigger.lower().split(","):
                    if kw.strip() in q:
                        score += 3
            if skill.description and skill.description.lower() in q:
                score += 2
            if skill.instructions and q in skill.instructions.lower():
                score += 1
            if score > 0:
                relevant.append((score, skill))
        relevant.sort(key=lambda x: -x[0])
        return [s for _, s in relevant[:5]]

    def skill_summary(self) -> str:
        """Generate a summary of loaded skills for system prompt."""
        if not self._skills:
            return ""
        lines = ["## Available Skills\n"]
        for name, skill in self._skills.items():
            desc = skill.description or "(no description)"
            lines.append(f"- **{name}**: {desc}")
        return "\n".join(lines)
