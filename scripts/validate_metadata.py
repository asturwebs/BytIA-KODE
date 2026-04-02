from __future__ import annotations

from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
PROMPT = ROOT / "src" / "bytia_kode" / "prompts" / "core_identity.yaml"
TEMP_PATTERNS = ["*.bak", "*.backup.*", "fix_*.py", "patch_*.py"]

with PYPROJECT.open("rb") as fh:
    data = tomllib.load(fh)

project = data["project"]
authors = project.get("authors", [])
if authors != [{"name": "Pedro Luis Cuevas Villarrubia", "email": "pedro@asturwebs.es"}]:
    raise SystemExit("authors no coincide con la autoría oficial de la 0.3.0")
if project.get("version") != "0.3.0":
    raise SystemExit("version no coincide con 0.3.0")
if not PROMPT.exists():
    raise SystemExit("faltan recursos YAML de identidad")

readme = README.read_text(encoding="utf-8")
if "pip install ./dist/*.whl" not in readme or "Formato de identidad del sistema: `YAML`" not in readme:
    raise SystemExit("README no refleja instalación oficial o identidad YAML")

changelog = CHANGELOG.read_text(encoding="utf-8")
if "v0.3.0 - Arquitectura Constitucional Modular y Empaquetado de Recursos" not in changelog:
    raise SystemExit("CHANGELOG no contiene el cierre formal de 0.3.0")

for pattern in TEMP_PATTERNS:
    matches = [p for p in ROOT.rglob(pattern) if ".venv" not in p.parts and ".git" not in p.parts and "dist" not in p.parts]
    if matches:
        raise SystemExit(f"se detectaron archivos temporales prohibidos para el release: {matches}")

print("metadata validation OK")
