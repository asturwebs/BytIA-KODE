"""Tests del puente herdr (src/bytia_kode/herdr.py)."""
import threading
import time

import pytest

from bytia_kode.herdr import HerdrBridge, LABEL, map_status


class Recorder:
    """Sustituto de HerdrBridge._run que graba los comandos invocados."""

    def __init__(self):
        self.cmds: list[list[str]] = []
        self.lock = threading.Lock()

    def __call__(self, cmd, **kwargs):
        with self.lock:
            self.cmds.append(list(cmd))

    def wait_for(self, n: int, timeout: float = 2.0) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                if len(self.cmds) >= n:
                    return True
            time.sleep(0.01)
        return False


def _make_bridge(monkeypatch, **kwargs) -> HerdrBridge:
    monkeypatch.setenv("HERDR_PANE_ID", "w9:p1")
    monkeypatch.setattr("bytia_kode.herdr.shutil.which", lambda _: "/usr/bin/herdr")
    bridge = HerdrBridge(**kwargs)
    rec = Recorder()
    bridge._run = rec
    return bridge, rec


# ---------------------------------------------------------------- activación

def test_inactivo_sin_pane(monkeypatch):
    monkeypatch.delenv("HERDR_PANE_ID", raising=False)
    assert HerdrBridge().enabled is False


def test_inactivo_sin_binario(monkeypatch):
    monkeypatch.setenv("HERDR_PANE_ID", "w9:p1")
    monkeypatch.setattr("bytia_kode.herdr.shutil.which", lambda _: None)
    assert HerdrBridge().enabled is False


def test_kill_switch(monkeypatch):
    monkeypatch.setenv("HERDR_PANE_ID", "w9:p1")
    monkeypatch.setenv("BYTIA_KODE_HERDR", "0")
    monkeypatch.setattr("bytia_kode.herdr.shutil.which", lambda _: "/usr/bin/herdr")
    assert HerdrBridge().enabled is False


# ------------------------------------------------------------------- mapeo

@pytest.mark.parametrize("status,esperado", [
    ("ready", "idle"),
    ("thinking", "working"),
    ("tool", "working"),
    ("skill", "working"),
    ("blocked", "blocked"),
    ("error", "idle"),
    ("desconocido", "unknown"),
])
def test_map_status(status, esperado):
    assert map_status(status) == esperado


# --------------------------------------------------------------- reportes

def test_primer_notify_identifica_y_reporta(monkeypatch):
    bridge, rec = _make_bridge(monkeypatch)
    bridge.notify_state("thinking")

    assert rec.wait_for(2)  # identify + report
    identify, report = rec.cmds[0], rec.cmds[1]

    # Sintaxis canónica: positional del pane antes que las opciones (gotcha parser 0.8.2)
    assert identify[:5] == ["herdr", "pane", "report-agent-session", "w9:p1", "--source"]
    assert LABEL in identify
    assert report[:5] == ["herdr", "pane", "report-agent", "w9:p1", "--source"]
    assert "--state" in report and "working" in report
    assert report[report.index("--seq") + 1] == "1"


def test_dedup_estados_repetidos(monkeypatch):
    bridge, rec = _make_bridge(monkeypatch)
    bridge.notify_state("thinking")
    bridge.notify_state("thinking")
    bridge.notify_state("thinking")

    assert rec.wait_for(2)
    time.sleep(0.05)
    with rec.lock:
        assert len(rec.cmds) == 2  # identify + un solo report


def test_transicion_de_estado_y_seq(monkeypatch):
    bridge, rec = _make_bridge(monkeypatch)
    bridge.notify_state("thinking")
    bridge.notify_state("tool", detail="tool:bash")
    bridge.notify_state("ready")

    assert rec.wait_for(4)  # identify + 3 reportes
    time.sleep(0.05)
    with rec.lock:
        reports = [c for c in rec.cmds if "report-agent-session" not in c]
        seqs = [int(c[c.index("--seq") + 1]) for c in reports]
        states = [c[c.index("--state") + 1] for c in reports]
    assert seqs == [1, 2, 3]
    assert states == ["working", "working", "idle"]


def test_message_solo_en_working(monkeypatch):
    bridge, rec = _make_bridge(monkeypatch)
    bridge.notify_state("tool", detail="tool:bash")
    bridge.notify_state("ready")

    assert rec.wait_for(3)
    time.sleep(0.05)
    with rec.lock:
        reports = [c for c in rec.cmds if "report-agent-session" not in c]
    assert "--message" in reports[0]
    assert reports[0][reports[0].index("--message") + 1] == "tool:bash"
    assert "--message" not in reports[1]


def test_detail_no_marca_dedup_entre_working(monkeypatch):
    bridge, rec = _make_bridge(monkeypatch)
    bridge.notify_state("tool", detail="tool:bash")
    bridge.notify_state("tool", detail="tool:read")

    assert rec.wait_for(3)  # identify + 2 reportes (detail distinto = no dedup)


# ------------------------------------------------------------- robustez

def test_fallo_del_cli_no_propaga(monkeypatch):
    bridge, _ = _make_bridge(monkeypatch)

    def boom(cmd, **kwargs):
        raise RuntimeError("herdr caído")

    bridge._run = boom
    bridge._process("state", "working", "")  # no debe levantar
    bridge._process("state", "ready", "")


def test_timeout_y_flags_de_subprocess(monkeypatch):
    capturado = {}

    def fake_run(cmd, timeout, stdout, stderr, check):
        capturado.update(timeout=timeout, check=check)

    monkeypatch.setattr("bytia_kode.herdr.subprocess.run", fake_run)
    HerdrBridge(timeout=1.5)._run(["herdr", "test"])
    assert capturado["timeout"] == 1.5
    assert capturado["check"] is False


# ------------------------------------------------------------------ sesión

def test_notify_session_reporta_el_id(monkeypatch):
    bridge, rec = _make_bridge(monkeypatch)
    bridge.notify_session("sess_abc")

    assert rec.wait_for(1)
    with rec.lock:
        identify = rec.cmds[0]
    assert "report-agent-session" in identify
    assert identify[identify.index("--agent-session-id") + 1] == "sess_abc"


def test_notify_session_dedup(monkeypatch):
    bridge, rec = _make_bridge(monkeypatch)
    bridge.notify_session("sess_abc")
    bridge.notify_session("sess_abc")

    assert rec.wait_for(1)
    time.sleep(0.05)
    with rec.lock:
        assert len(rec.cmds) == 1


def test_cambio_de_sesion_reancla(monkeypatch):
    bridge, rec = _make_bridge(monkeypatch)
    sid = {"v": None}
    bridge._session_id_fn = lambda: sid["v"]

    bridge.notify_state("ready")        # identify sin sesión + report idle
    assert rec.wait_for(2)              # sincroniza: el worker ya procesó el primero
    sid["v"] = "sess_1"
    bridge.notify_state("thinking")     # re-ancla con sess_1 + report working

    assert rec.wait_for(4)
    time.sleep(0.05)
    with rec.lock:
        identifies = [c for c in rec.cmds if "report-agent-session" in c]
        assert len(identifies) == 2
        assert "--agent-session-id" not in identifies[0]
        assert identifies[1][identifies[1].index("--agent-session-id") + 1] == "sess_1"


def test_session_id_fn_que_falla_degrada(monkeypatch):
    bridge, rec = _make_bridge(monkeypatch)

    def roto():
        raise RuntimeError("TUI no montada")

    bridge._session_id_fn = roto
    bridge.notify_state("thinking")

    assert rec.wait_for(2)
    with rec.lock:
        identify = [c for c in rec.cmds if "report-agent-session" in c][0]
    assert "--agent-session-id" not in identify  # degradó a None sin crash
