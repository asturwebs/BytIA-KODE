"""Stub del Bot API de Telegram para tests y demo de ciclo de vida (AST-32).

Responde a los endpoints que python-telegram-bot toca en un arranque polling:
getMe, deleteWebhook (fase bootstrap), getUpdates (long-poll simulado) y un
catch-all (`close`, `logout`, …). Stdlib pura, sin dependencias del proyecto.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GET_UPDATES_DELAY = 1.0  # simula long-poll para que el fetcher no bucle en caliente


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # silencia el log por defecto
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        endpoint = self.path.rsplit("/", 1)[-1]

        if endpoint == "getUpdates":
            # Respeta el timeout del long-poll del cliente si es menor
            try:
                client_timeout = int(body.split("timeout=")[1].split("&")[0])
            except (IndexError, ValueError):
                client_timeout = 10
            time.sleep(min(GET_UPDATES_DELAY, max(client_timeout - 1, 0.2)))
            result = []
        elif endpoint == "getMe":
            result = {
                "id": 123456,
                "is_bot": True,
                "first_name": "BytIA KODE test",
                "username": "bytia_kode_test_bot",
            }
        else:
            result = True

        payload = json.dumps({"ok": True, "result": result}).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            # El cliente (PTB) canceló el long-poll durante el teardown — normal
            pass


def start_fake_api() -> ThreadingHTTPServer:
    """Levanta el stub en 127.0.0.1:<puerto libre> y lo devuelve listo.

    El caller es dueño del apagado: `server.shutdown(); server.server_close()`.
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
