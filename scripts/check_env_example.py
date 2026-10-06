"""Gate CI: la plantilla .env.example no declara variables vacías (AST-36).

Incidente: el 2026-10-06 el servicio del bot llevaba 6.253 reinicios en bucle
(`TELEGRAM_BOT_TOKEN not set in .env`) pese a que el global
`~/.bytia-kode/.env` tenía el token desde el 2026-10-01. Causa raíz: una
copia sin rellenar de la plantilla declaraba `TELEGRAM_BOT_TOKEN=` y
`TELEGRAM_ALLOWED_USERS=` VACÍAS; con la cadena de carga de config.py
(`./.env` del CWD primero, global después, ambas `override=False`) una
variable declarada vacía queda «presente» y el global ya no puede
rellenarla — tampoco se aplica el default del código.

Contrato: NINGUNA línea `VAR=` (o `VAR=""` / `VAR=''`) DESCOMENTADA en la
plantilla — cubre y excede el criterio literal `^[A-Z_]+=$` del issue
(atribuimos dígitos, espacios alrededor del `=` y vacío entrecomillado).
Los placeholders van comentados (`# VAR=`): documentan sin secuestrar.
Fail cerrado: una sola línea violatoria → rc=1 citando línea y variable.
Sin red, sin dependencias fuera de la stdlib.

Uso:
    python scripts/check_env_example.py                 # plantilla del repo
    python scripts/check_env_example.py --template PATH # tests del gate
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DEFAULT = ROOT / ".env.example"

# Declaración de variable con valor VACÍO, descomentada: el nombre admite
# dígitos (GPT4_API_KEY) y el vacío puede ir entrecomillado o con espacios.
# (Raw string de comillas SIMPLES: el patrón contiene "" y '' — con
# delimitadores dobles, las comillas del patrón romperían la delimitación.)
_EMPTY_DECL_RE = re.compile(r'''^([A-Z][A-Z0-9_]*)\s*=\s*(?:""|'')?\s*$''')


def check_template(template: Path) -> list[tuple[int, str]]:
    """Devuelve (número_de_línea, texto) de cada declaración vacía."""
    violations: list[tuple[int, str]] = []
    for lineno, line in enumerate(
        template.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if line.lstrip().startswith("#"):
            continue  # placeholder comentado: la forma que la plantilla usa
        if _EMPTY_DECL_RE.match(line):
            violations.append((lineno, line))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gate de plantilla .env.example: sin placeholders vacíos descomentados (AST-36)"
    )
    parser.add_argument(
        "--template", type=Path, default=TEMPLATE_DEFAULT,
        help="plantilla alternativa (sólo para tests del propio gate)",
    )
    args = parser.parse_args(argv)

    template = args.template if args.template.is_absolute() else ROOT / args.template
    print(f"== .env.example hygiene gate (AST-36) — {template} ==")
    if not template.exists():
        print(f"GATE EN ROJO: la plantilla no existe: {template}")
        return 1

    violations = check_template(template)
    if violations:
        print("[FALLOS — declaraciones vacías descomentadas (bloquean global y default)]")
        for lineno, line in violations:
            print(f"  ✘ {template.name}:{lineno}: {line}")
        print()
        print(f"RESULTADO: {len(violations)} placeholders vacíos descomentados")
        print(
            "GATE EN ROJO: comenta el placeholder (`# VAR=`) o ponle un valor real — "
            "una variable declarada vacía pisa el .env global (AST-36)."
        )
        return 1

    total = len(template.read_text(encoding="utf-8").splitlines())
    print(f"RESULTADO: {total} líneas de plantilla, 0 placeholders vacíos descomentados")
    print("GATE EN VERDE: la plantilla documenta sin secuestrar variables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
