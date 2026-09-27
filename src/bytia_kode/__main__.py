"""Entry point for `python -m bytia_kode` and the `bytia-kode` console script.

Ambos caminos despachan igual (AST-22): antes, `--bot` sólo funcionaba vía
`python -m bytia_kode`, y el console script arrancaba la TUI sin mirar argv —
`bytia-kode --bot` iniciaba la TUI en silencio.

`--version` (AST-23) es cortesía para usuarios de pip: imprime la versión
(con build id si existe) y sale 0 sin arrancar nada interactivo. Gana el
primer flag — `--version --bot` imprime la versión igual que `--version` solo.
"""
from __future__ import annotations

import sys


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else ""

    if arg == "--version":
        from bytia_kode import version_label

        print(version_label())
        return

    if arg == "--bot":
        from bytia_kode.telegram.bot import main as bot_main

        bot_main()
    else:
        from bytia_kode.tui import run_tui

        run_tui()


if __name__ == "__main__":
    main()
