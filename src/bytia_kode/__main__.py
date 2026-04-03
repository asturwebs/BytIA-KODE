"""Entry point for python -m bytia_kode"""
import sys

if len(sys.argv) > 1 and sys.argv[1] == "--bot":
    from bytia_kode.telegram.bot import main as bot_main
    bot_main()
else:
    from bytia_kode.tui import run_tui
    run_tui()
