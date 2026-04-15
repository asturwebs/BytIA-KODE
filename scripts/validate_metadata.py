from __future__ import annotations

from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
PROMPT = ROOT / "src" / "bytia_kode" / "prompts" / "kernel.default.yaml"
TEMP_PATTERNS = ["*.bak", "*.backup.*", "fix_*.py", "patch_*.py"]

with PYPROJECT.open("rb") as fh:
    data = tomllib.load(fh)

project = data["project"]
version = project.get("version", "")
authors = project.get("authors", [])
if authors != [{"name": "Pedro Luis Cuevas Villarrubia", "email": "pedro@asturwebs.es"}]:
    raise SystemExit("authors no coincide con la autoría oficial")
if not version:
    raise SystemExit("version vacía en pyproject.toml")
if not PROMPT.exists():
    raise SystemExit("faltan recursos YAML de identidad")

readme = README.read_text(encoding="utf-8")
if "uv run bytia-kode" not in readme:
    raise SystemExit("README no refleja instalación oficial")

changelog = CHANGELOG.read_text(encoding="utf-8")
if f"## [{version}]" not in changelog:
    raise SystemExit(f"CHANGELOG no contiene la entrada para v{version}")

for pattern in TEMP_PATTERNS:
    matches = [p for p in ROOT.rglob(pattern) if ".venv" not in p.parts and ".git" not in p.parts and "dist" not in p.parts]
    if matches:
        raise SystemExit(f"se detectaron archivos temporales prohibidos para el release: {matches}")

print("metadata validation OK")
