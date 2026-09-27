"""Entry point for `python -m bytia_kode` and the `bytia-kode` console script.

Ambos caminos despachan igual (AST-22): antes, `--bot` sólo funcionaba vía
`python -m bytia_kode`, y el console script arrancaba la TUI sin mirar argv —
`bytia-kode --bot` iniciaba la TUI en silencio.
"""
from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--bot":
        from bytia_kode.telegram.bot import main as bot_main

        bot_main()
    else:
        from bytia_kode.tui import run_tui

        run_tui()


if __name__ == "__main__":
    main()
