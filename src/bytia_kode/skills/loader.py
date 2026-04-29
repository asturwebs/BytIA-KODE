"""Skill loading system - SKILL.md pattern with vendor/user/bytia layers."""

from __future__ import annotations

import logging
import shutil
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
    verified: bool = False
    source: str = "unknown"


class SkillLoader:
    """Discovers and loads SKILL.md files from layered skill directories.

    Layer priority (highest to lowest):
    1. bytia - BytIA ecosystem (~/bytia/skills/) - optional, if exists
    2. user - User-created skills (~/.bytia-kode/skills/user/) - writable
    3. vendor - Bundled skills (~/.bytia-kode/skills/vendor/) - read-only

    Higher layers override lower layers with the same skill name.
    """

    SKILL_FILE = "SKILL.md"
    LAYER_VENDOR = "vendor"
    LAYER_USER = "user"
    LAYER_BYTIA = "bytia"

    def __init__(self, skills_home: Path | None = None, bytia_home: Path | None = None):
        self.skills_home = skills_home or Path("~/.bytia-kode/skills").expanduser()
        self.bytia_home = bytia_home or Path("~/bytia").expanduser()
        self._skills: dict[str, Skill] = {}
        self._layers_configured = False

    def configure_layers(self):
        """Set up directory structure for vendor/user/bytia layers."""
        if self._layers_configured:
            return

        self.skills_home.mkdir(parents=True, exist_ok=True)

        vendor_dir = self.skills_home / self.LAYER_VENDOR
        user_dir = self.skills_home / self.LAYER_USER

        vendor_dir.mkdir(exist_ok=True)
        user_dir.mkdir(exist_ok=True)

        self._layers_configured = True
        logger.debug(f"Skills layers configured at {self.skills_home}")

    def get_layer_dirs(self) -> list[tuple[Path, str]]:
        """Return skill directories in priority order (highest first)."""
        layers = []

        bytia_dir = self.bytia_home / "skills"
        if bytia_dir.exists() and bytia_dir.is_dir():
            layers.append((bytia_dir, self.LAYER_BYTIA))
            logger.debug(f"BytIA ecosystem layer: {bytia_dir}")

        user_dir = self.skills_home / self.LAYER_USER
        if user_dir.exists():
            layers.append((user_dir, self.LAYER_USER))
            logger.debug(f"User layer: {user_dir}")

        vendor_dir = self.skills_home / self.LAYER_VENDOR
        if vendor_dir.exists():
            layers.append((vendor_dir, self.LAYER_VENDOR))
            logger.debug(f"Vendor layer: {vendor_dir}")

        return layers

    def load_all(self) -> dict[str, Skill]:
        """Scan all skill layers and load SKILL.md files.

        Higher priority layers (bytia, user) override lower (vendor).
        """
        self.configure_layers()

        self._skills.clear()

        for layer_dir, layer_name in reversed(self.get_layer_dirs()):
            if not layer_dir.exists():
                continue

            for item in layer_dir.iterdir():
                if not item.is_dir():
                    continue

                skill_file = item / self.SKILL_FILE
                if not skill_file.exists():
                    continue

                skill = self._parse_skill(skill_file, layer_name)
                if skill:
                    if skill.name in self._skills:
                        logger.debug(
                            f"Skill '{skill.name}' overridden by {layer_name} layer"
                        )
                    self._skills[skill.name] = skill
                    logger.debug(f"Loaded skill: {skill.name} from {layer_name}")

        logger.info(
            f"Loaded {len(self._skills)} skills from {len(self.get_layer_dirs())} layers"
        )
        return self._skills

    def _parse_skill(self, path: Path, source: str = "unknown") -> Skill | None:
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
            source=source,
        )

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def save_skill(
        self, name: str, content: str, description: str = "", trigger: str = ""
    ) -> Path:
        """Save a new skill to the user layer (not vendor)."""
        self.configure_layers()

        user_dir = self.skills_home / self.LAYER_USER
        user_dir.mkdir(parents=True, exist_ok=True)

        skill_dir = user_dir / name
        skill_path = skill_dir / self.SKILL_FILE
        skill_dir.mkdir(parents=True, exist_ok=True)

        fm = f"---\nname: {name}\ndescription: {description}\n"
        if trigger:
            fm += f"trigger: {trigger}\n"
        fm += "verified: false\n---\n\n"
        skill_path.write_text(fm + content, encoding="utf-8")

        parsed = self._parse_skill(skill_path, self.LAYER_USER)
        if parsed:
            self._skills[name] = parsed

        logger.info(f"Skill saved to user layer: {skill_path}")
        return skill_path

    def list_skill_names(self) -> list[str]:
        """List all skill names."""
        return list(self._skills.keys())

    def verify_skill(self, name: str) -> bool:
        """Mark a skill as verified."""
        skill = self._skills.get(name)
        if not skill or not skill.path:
            return False

        if skill.source == self.LAYER_VENDOR:
            logger.warning(
                f"Cannot verify vendor skill '{name}' - copying to user layer"
            )
            return self._copy_to_user_and_verify(skill)

        content = skill.path.read_text()
        content = content.replace("verified: false", "verified: true", 1)
        skill.path.write_text(content, encoding="utf-8")
        skill.verified = True
        return True

    def _copy_to_user_and_verify(self, skill: Skill) -> bool:
        """Copy vendor skill to user layer and verify it."""
        if not skill.path:
            return False

        user_dir = self.skills_home / self.LAYER_USER
        user_dir.mkdir(parents=True, exist_ok=True)

        user_path = user_dir / skill.name / self.SKILL_FILE
        user_path.parent.mkdir(parents=True, exist_ok=True)

        content = skill.path.read_text()
        content = content.replace("verified: false", "verified: true", 1)
        user_path.write_text(content, encoding="utf-8")

        parsed = self._parse_skill(user_path, self.LAYER_USER)
        if parsed:
            self._skills[skill.name] = parsed

        logger.info(f"Vendor skill '{skill.name}' copied to user layer and verified")
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

    def install_vendor_skills(self, vendor_source: Path):
        """Install vendor skills from source directory to vendor layer."""
        self.configure_layers()

        vendor_dir = self.skills_home / self.LAYER_VENDOR

        if not vendor_source.exists():
            logger.warning(f"Vendor source not found: {vendor_source}")
            return

        for item in vendor_source.iterdir():
            if not item.is_dir():
                continue

            skill_name = item.name
            dest = vendor_dir / skill_name

            if dest.exists():
                if dest.is_symlink():
                    dest.unlink()
                else:
                    backup = vendor_dir / f"{skill_name}.backup"
                    if backup.exists():
                        shutil.rmtree(backup)
                    shutil.move(str(dest), str(backup))
                    logger.debug(f"Backed up existing skill: {skill_name}")

            shutil.copytree(item, dest)
            logger.info(f"Installed vendor skill: {skill_name}")

        logger.info(f"Vendor skills installed from {vendor_source}")

    def get_skill_info(self) -> dict:
        """Get info about loaded skills and layers."""
        layers = self.get_layer_dirs()
        return {
            "skills_home": str(self.skills_home),
            "bytia_home": str(self.bytia_home) if self.bytia_home.exists() else None,
            "layers": [
                {
                    "path": str(p),
                    "name": n,
                    "count": sum(
                        1
                        for _ in p.iterdir()
                        if _.is_dir() and (_ / self.SKILL_FILE).exists()
                    ),
                }
                for p, n in layers
            ],
            "total_skills": len(self._skills),
            "skills": [
                {"name": s.name, "source": s.source, "verified": s.verified}
                for s in self._skills.values()
            ],
        }
