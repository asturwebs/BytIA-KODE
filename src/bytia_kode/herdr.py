"""Puente de ciclo de vida BytIA-KODE → herdr (multiplexor agent-native).

Si el proceso corre dentro de un pane de herdr (env HERDR_PANE_ID), reporta la
identidad y el estado del agente vía el CLI de herdr para que la sesión aparezca
en el panel de agentes del multiplexor con su nombre y estados working/idle.

Fuera de herdr el bridge queda inactivo: cero overhead, cero fallos. Los
errores de reporte se degradan a log debug — nunca rompen la TUI.

Sintaxis CLI verificada contra herdr 0.8.2 (positional del pane ANTES que las
opciones; el parser rechaza valores espaciados si las opciones van primero):

    herdr pane report-agent-session <PANE> --source L --agent L [--agent-session-id ID]
    herdr pane report-agent <PANE> --source L --agent L --state S --seq N [--message M]
"""
from __future__ import annotations

import logging
import os
import queue
import shutil
import subprocess
import threading
from itertools import count

log = logging.getLogger(__name__)

#: Label con el que B-KODE se presenta en el panel de agentes de herdr.
LABEL = "bytia-kode"

#: Mapeo del status del ActivityIndicator → estado de herdr.
HERDR_STATE = {
    "ready": "idle",
    "thinking": "working",
    "tool": "working",
    "skill": "working",
    "blocked": "blocked",
    "error": "idle",
}


def map_status(status: str) -> str:
    """Traduce un status interno del TUI a un estado válido de herdr."""
    return HERDR_STATE.get(status, "unknown")


class HerdrBridge:
    """Reporta identidad y estado del agente a herdr (fire-and-forget).

    Los reportes se ejecutan en un thread daemon con cola: ``notify_state``
    nunca bloquea el event loop de Textual. Los fallos del CLI (herdr cerrado,
    versión sin soporte, timeout) se tragan con log debug.
    """

    def __init__(self, pane_id: str | None = None, label: str = LABEL, timeout: float = 3.0):
        self._pane_id = pane_id if pane_id is not None else os.environ.get("HERDR_PANE_ID", "")
        self._label = label
        self._timeout = timeout
        self._seq = count(1)
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._last_report: tuple[str, str] | None = None
        self._identified = False
        self.enabled = (
            bool(self._pane_id)
            and shutil.which("herdr") is not None
            and os.environ.get("BYTIA_KODE_HERDR", "") != "0"
        )
        if self.enabled:
            threading.Thread(target=self._drain, daemon=True, name="herdr-bridge").start()

    def notify_state(self, status: str, detail: str = "") -> None:
        """Punto de enganche: el ActivityIndicator le pasa cada cambio de status.

        No bloquea nunca. De-duplica reportes idénticos (``set_status`` repite
        valores constantemente durante un turno).
        """
        if not self.enabled:
            return
        state = map_status(status)
        message = detail if state == "working" else ""
        if (state, message) == self._last_report:
            return
        self._last_report = (state, message)
        self._queue.put((state, message))

    # ------------------------------------------------------------------
    # Thread worker

    def _drain(self) -> None:
        while True:
            state, message = self._queue.get()
            self._process(state, message)

    def _process(self, state: str, message: str) -> None:
        try:
            if not self._identified:
                self._identify()
                self._identified = True
            self._report(state, message)
        except Exception:
            log.debug("herdr: reporte de estado falló", exc_info=True)

    def _identify(self) -> None:
        self._run([
            "herdr", "pane", "report-agent-session", self._pane_id,
            "--source", self._label, "--agent", self._label,
        ])

    def _report(self, state: str, message: str) -> None:
        cmd = [
            "herdr", "pane", "report-agent", self._pane_id,
            "--source", self._label, "--agent", self._label,
            "--state", state, "--seq", str(next(self._seq)),
        ]
        if message:
            cmd += ["--message", message]
        self._run(cmd)

    def _run(self, cmd: list[str]) -> None:
        subprocess.run(
            cmd,
            timeout=self._timeout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
