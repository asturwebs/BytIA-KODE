"""Puente de ciclo de vida BytIA-KODE → herdr (multiplexor agent-native).

Si el proceso corre dentro de un pane de herdr (env HERDR_PANE_ID), reporta la
identidad y el estado del agente vía el CLI de herdr para que la sesión aparezca
en el panel de agentes del multiplexor con su nombre y estados working/idle.

Fuera de herdr el bridge queda inactivo: cero overhead, cero fallos. Los
errores de reporte se degradan a log debug — nunca rompen la TUI.

Sintaxis CLI verificada contra herdr 0.9.5 (positional del pane ANTES que las
opciones; el parser rechaza valores espaciados si las opciones van primero):

    herdr pane report-agent-session <PANE> --source L --agent L --seq N [--agent-session-id ID]
    herdr pane report-agent <PANE> --source L --agent L --state S --seq N [--message M]

Seq: herdr exige que --seq CREZCA estrictamente por source — también entre
sesiones y reinicios del agente (doc oficial 0.9.5: "a timestamp works well") —
y descarta en silencio los reportes que no superan al último aceptado (rc=0,
invisible). Por eso el seq es un timestamp en ms con guarda anti-colisión dentro
del mismo milisegundo, no un contador por proceso: count(1) hacía invisible
toda TUI reiniciada (incidente 15-nov-26: bytia-kode desaparecía del panel).

Sesión: si hay `session_id_fn`, el bridge re-ancla la identidad cuando el id de
sesión activa cambia (con lag de un ciclo de estado; `notify_session` lo hace
inmediato tras /load o /new). `--agent-session-id` se envía siempre que exista
(forward-compatibility si la versión de turno no lo expone para self-reported).
"""
from __future__ import annotations

import logging
import os
import queue
import shutil
import subprocess
import threading
import time

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

    def __init__(
        self,
        pane_id: str | None = None,
        label: str = LABEL,
        timeout: float = 3.0,
        session_id_fn: "callable | None" = None,
    ):
        self._pane_id = pane_id if pane_id is not None else os.environ.get("HERDR_PANE_ID", "")
        self._label = label
        self._timeout = timeout
        self._session_id_fn = session_id_fn
        self._seq = 0
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._last_report: tuple[str, str] | None = None
        self._last_session: str | None = None
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
        self._queue.put(("state", state, message))

    def notify_session(self, session_id: str | None) -> None:
        """(Re)ancla la identidad de sesión en herdr (tras /load o /new).

        Inmediato, sin esperar al próximo cambio de estado. De-duplica ids
        repetidos y no hace nada sin sesión activa.
        """
        if not self.enabled or not session_id or session_id == self._last_session:
            return
        self._last_session = session_id
        self._queue.put(("session", session_id, ""))

    def _current_session(self) -> str | None:
        """Lee el id de sesión activa vía el callback de la TUI (thread-safe)."""
        if self._session_id_fn is None:
            return None
        try:
            return self._session_id_fn() or None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Thread worker

    def _drain(self) -> None:
        while True:
            kind, a, b = self._queue.get()
            self._process(kind, a, b)

    def _process(self, kind: str, a: str, b: str) -> None:
        try:
            if kind == "session":
                self._identify(a)
                return
            state, message = a, b
            sid = self._current_session()
            if not self._identified or sid != self._last_session:
                self._identify(sid)
                self._identified = True
                self._last_session = sid
            self._report(state, message)
        except Exception:
            log.debug("herdr: reporte de estado falló", exc_info=True)

    def _next_seq(self) -> int:
        """Seq estrictamente creciente entre reportes y entre reinicios.

        Timestamp en ms — el patrón que recomienda la doc de herdr — con guarda
        para dos reportes dentro del mismo milisegundo.
        """
        self._seq = max(int(time.time() * 1000), self._seq + 1)
        return self._seq

    def _identify(self, session_id: str | None = None) -> None:
        cmd = [
            "herdr", "pane", "report-agent-session", self._pane_id,
            "--source", self._label, "--agent", self._label,
            "--seq", str(self._next_seq()),
        ]
        if session_id:
            cmd += ["--agent-session-id", session_id]
        self._run(cmd)

    def _report(self, state: str, message: str) -> None:
        cmd = [
            "herdr", "pane", "report-agent", self._pane_id,
            "--source", self._label, "--agent", self._label,
            "--state", state, "--seq", str(self._next_seq()),
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
