"""AST-32: ciclo de vida de `bytia-kode --bot` — banner real y apagado limpio.

Reporte del Socio: el bot arrancaba mudo (logger.info sin handler) y el doble
Ctrl+C interrumpía el teardown de PTB ("Event loop is closed"). Estos tests
ejercitan el proceso REAL (`python -m bytia_kode --bot`) contra un stub local
del Bot API (fake_telegram_api.py, vía TELEGRAM_API_BASE) y le inyectan SIGINT
— el equivalente no-interactivo de Ctrl+C en un terminal.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("telegram", reason="python-telegram-bot not installed")

from fake_telegram_api import start_fake_api  # noqa: E402  (hermana de tests/)

REPO = Path(__file__).resolve().parents[1]
FAKE_TOKEN = "123456:TEST-fake-token-abcdefghijklmnopqrstuvwxyz"


def _spawn_bot(tmp_path: Path, port: int, token: str = FAKE_TOKEN) -> subprocess.Popen:
    """Lanza `python -m bytia_kode --bot` aislado (HOME/cwd/DATA_DIR en tmp)."""
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    home.mkdir(parents=True, exist_ok=True)
    cwd.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        HOME=str(home),
        DATA_DIR=str(home / ".bytia-kode"),
        TELEGRAM_BOT_TOKEN=token,
        TELEGRAM_ALLOWED_USERS="424242",
        TELEGRAM_API_BASE=f"http://127.0.0.1:{port}/bot",
        # El hijo resuelve bytia_kode y sus deps del MISMO árbol/deps que esta
        # sesión de tests (funciona en checkout, worktree y CI por igual)
        PYTHONPATH=os.pathsep.join(p for p in sys.path if p),
    )
    return subprocess.Popen(
        [sys.executable, "-m", "bytia_kode", "--bot"],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_banner(proc: subprocess.Popen, timeout: float = 10.0) -> str:
    """Espera a que el proceso produzca stdout (banner) sin consumir el pipe."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return ""  # murió antes de producir nada — el assert del caller pinta el cuadro
        time.sleep(0.2)
    return ""


class TestMaskToken:
    def test_mask_conserva_bot_id_y_borra_secreto(self):
        from bytia_kode.telegram.bot import _mask_token

        masked = _mask_token(FAKE_TOKEN)
        assert masked.startswith("123456:")
        assert FAKE_TOKEN.split(":", 1)[1] not in masked
        assert masked.endswith("…xyz")

    def test_mask_token_malformado(self):
        from bytia_kode.telegram.bot import _mask_token

        assert _mask_token("") == "***"
        assert _mask_token("sin-dos-puntos") == "***"
        assert _mask_token("123456:abc") == "***"  # secreto demasiado corto


class TestBannerVisible:
    def test_banner_stdout_y_token_enmascarado(self, tmp_path):
        server = start_fake_api()
        port = server.server_address[1]
        try:
            proc = _spawn_bot(tmp_path, port)
            try:
                _wait_banner(proc)
                # Deja que PTB complete bootstrap y entre en polling
                time.sleep(1.5)
                assert proc.poll() is None, "el bot debe seguir vivo en polling"
            finally:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGINT)
            out, err = proc.communicate(timeout=15)
            assert "Bot de Telegram activo" in out
            assert "usuarios permitidos: 1" in out
            assert "(Ctrl+C para parar)" in out
            assert FAKE_TOKEN not in out, "el token completo NO puede aparecer en stdout"
            assert "123456:TES…xyz" in out
            assert "Traceback" not in err
            assert proc.returncode == 0
        finally:
            server.shutdown()
            server.server_close()


class TestShutdownLimpio:
    def test_un_sigint_muere_limpio(self, tmp_path):
        server = start_fake_api()
        port = server.server_address[1]
        try:
            proc = _spawn_bot(tmp_path, port)
            _wait_banner(proc)
            time.sleep(1.5)  # polling activo
            proc.send_signal(signal.SIGINT)  # UN solo Ctrl+C
            out, err = proc.communicate(timeout=15)
            assert proc.returncode == 0
            assert "Traceback" not in err
            assert "Event loop is closed" not in err
            assert "Bot detenido." in out
        finally:
            server.shutdown()
            server.server_close()

    def test_doble_sigint_no_rompe_teardown(self, tmp_path):
        """Regresión del reporte: el 2º ^C debe ser no-op, no un SystemExit
        que interrumpa el finally de PTB."""
        server = start_fake_api()
        port = server.server_address[1]
        try:
            proc = _spawn_bot(tmp_path, port)
            _wait_banner(proc)
            time.sleep(1.5)
            proc.send_signal(signal.SIGINT)
            time.sleep(0.02)  # cae dentro de la ventana de teardown
            proc.send_signal(signal.SIGINT)
            out, err = proc.communicate(timeout=15)
            assert proc.returncode == 0
            assert "Traceback" not in err
            assert "Event loop is closed" not in err
        finally:
            server.shutdown()
            server.server_close()

    def test_sin_token_sale_con_error_claro(self, tmp_path):
        proc = _spawn_bot(tmp_path, port=1, token="")
        out, err = proc.communicate(timeout=15)
        assert proc.returncode == 1
        assert "TELEGRAM_BOT_TOKEN not set" in out
        assert "Traceback" not in err
