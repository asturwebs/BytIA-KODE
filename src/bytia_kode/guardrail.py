"""Jev-based pre-execution guardrail (TypeSafe System One model).

Classifies every tool call before execution and can block risky ones.

Modes (env JEVAL_MODE, default "off"):
  off     - no classification, near-zero overhead (one cached env read)
  shadow  - classify + log every tool call, NEVER block (evaluation mode)
  enforce - block tool calls classified as risky with noul >= JEVAL_THRESHOLD

Fail-open: any Jev error/timeout -> allow the tool call. Jev never breaks the loop.

Env vars:
  JEVAL_MODE      off | shadow | enforce   (default: off)
  JEVAL_THRESHOLD float, 0..1             (default: 0.7)
  JEVAL_TIMEOUT   seconds                 (default: 2.0)
  TYPESAFE_API_KEY API key; fallback file ~/.config/typesafe/env

Decision log (JSONL, 600): ~/.local/state/jev-router/kode-guardrail.jsonl
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import time
import urllib.request

logger = logging.getLogger(__name__)

API_URL = "https://api.typesafe.ai/v1/systemone"
STATE_DIR = pathlib.Path.home() / ".local" / "state" / "jev-router"

RISKY_QUESTION = {
    "is_risky": {
        "type": "noul",
        "instructions": (
            "Executing this tool call could destroy or overwrite data outside the "
            "workspace, exfiltrate credentials/secrets or personal data to external "
            "services, or disrupt system integrity (rm -rf, force push, dd, chmod on "
            "system files, piping secrets to network tools, disabling firewalls). "
            "Read-only operations, workspace-scoped edits and normal dev commands are NOT risky."
        ),
    }
}


def _load_key() -> str | None:
    key = os.getenv("TYPESAFE_API_KEY")
    if key:
        return key
    env_file = pathlib.Path.home() / ".config" / "typesafe" / "env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("export TYPESAFE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


class JevalGate:
    """Gate around the TypeSafe API. Instantiate once, reuse."""

    def __init__(self) -> None:
        self.mode = os.getenv("JEVAL_MODE", "off").strip().lower()
        if self.mode not in ("off", "shadow", "enforce"):
            logger.warning("JEVAL_MODE invalid (%s), falling back to off", self.mode)
            self.mode = "off"
        self.threshold = float(os.getenv("JEVAL_THRESHOLD", "0.7"))
        self.timeout_s = float(os.getenv("JEVAL_TIMEOUT", "2.0"))
        self._key = _load_key() if self.mode != "off" else None
        if self.mode != "off" and not self._key:
            logger.warning("JEVAL_MODE=%s but no TYPESAFE_API_KEY found -> disabling", self.mode)
            self.mode = "off"
        self.enabled = self.mode != "off"

    # --- internals -------------------------------------------------------

    def _log(self, rec: dict) -> None:
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            os.chmod(STATE_DIR, 0o700)
            log_path = STATE_DIR / "kode-guardrail.jsonl"
            if not log_path.exists():
                log_path.touch(mode=0o600)
            with open(log_path, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:  # logging must never break the agent
            logger.debug("JEVAL log write failed", exc_info=True)

    def _ask_sync(self, state: str) -> dict:
        body = json.dumps(
            {"model": "jev-latest", "state": state, "questions": RISKY_QUESTION}
        ).encode()
        req = urllib.request.Request(
            API_URL, data=body, method="POST",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode())

    # --- public API ------------------------------------------------------

    async def check(self, tool_name: str, arguments: dict) -> dict:
        """Return {'blocked': bool, 'reason': str, 'mode': self.mode}."""
        if not self.enabled:
            return {"blocked": False, "reason": "off", "mode": self.mode}

        state = f"Tool: {tool_name}\nArguments: {json.dumps(arguments, ensure_ascii=False)[:1500]}"
        t0 = time.perf_counter()
        rec_id = f"{int(time.time()*1000):x}"[-12:]
        try:
            j = await asyncio.to_thread(self._ask_sync, state)
            ms = round((time.perf_counter() - t0) * 1000)
        except Exception as e:
            self._log({"rec_id": rec_id, "ts": round(time.time(), 3), "consumer": "kode-guardrail",
                       "mode": self.mode, "tool": tool_name, "state_head": state[:160],
                       "error": f"{type(e).__name__}: {e}", "ms": None})
            logger.debug("JEVAL unavailable (%s) -> fail-open", e)
            return {"blocked": False, "reason": f"fail-open: {e}", "mode": self.mode}

        a = (j.get("answers") or {}).get("is_risky") or {}
        noul = float(a.get("noul", 0.0))
        risky = noul >= self.threshold
        blocked = bool(risky and self.mode == "enforce")
        self._log({"rec_id": rec_id, "ts": round(time.time(), 3), "consumer": "kode-guardrail",
                   "mode": self.mode, "tool": tool_name, "state_head": state[:160],
                   "noul": noul, "risky": risky, "blocked": blocked, "ms": ms,
                   "usage": j.get("usage")})
        logger.info("JEVAL[%s] %s noul=%.2f risky=%s blocked=%s (%dms)",
                    self.mode, tool_name, noul, risky, blocked, ms)
        reason = (f"risky tool call (noul={noul:.2f} >= {self.threshold}): {tool_name}"
                  if blocked else "allowed")
        return {"blocked": blocked, "reason": reason, "mode": self.mode, "noul": noul}


_gate: JevalGate | None = None


def get_gate() -> JevalGate:
    global _gate
    if _gate is None:
        _gate = JevalGate()
    return _gate


async def jeval_check(tool_name: str, arguments: dict) -> dict:
    """Module-level entry for the agent loop. Fast no-op when mode=off."""
    gate = get_gate()
    if not gate.enabled:
        return {"blocked": False, "reason": "off", "mode": "off"}
    return await gate.check(tool_name, arguments)
