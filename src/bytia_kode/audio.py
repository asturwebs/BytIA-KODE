"""Salida de voz de BytIA-KODE.

Adaptado 21-sep-26 a la era Omarchy: la era WSL usaba `edge-tts` (nube de
Microsoft) + mpv; aquí NO existía ese binario y el altavoz estaba roto.
Ahora usa `bytia-tts` (contrato OMA), el mismo TTS local de BytIA Voice y
Hermes: piper `es_AR-daniela-high` 100% local, voz homogénea del ecosistema.

API pública intacta para tui.py: play_speech(), stop(), is_playing(), TextCleaner.
"""
import re
import logging
import asyncio
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class TextCleaner:
    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'[*_#~>]', '', text)
        text = re.sub(r'http\S+', '', text)
        text = re.sub(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text


_active_player: asyncio.subprocess.Process | None = None
_reap_task: asyncio.Task | None = None


def _child_env() -> dict:
    """PATH con ~/.local/bin garantizado (bytia-tts llama a `piper` sin ruta)."""
    env = dict(os.environ)
    local_bin = str(Path.home() / ".local" / "bin")
    if local_bin not in env.get("PATH", ""):
        env["PATH"] = env.get("PATH", "") + os.pathsep + local_bin
    return env


def stop():
    global _active_player, _reap_task
    if _active_player is not None and _active_player.returncode is None:
        try:
            _active_player.terminate()  # el reaper hace el reap al salir
        except ProcessLookupError:
            pass
    _active_player = None
    _reap_task = None


def is_playing() -> bool:
    return _active_player is not None and _active_player.returncode is None


async def _launch(clean_text: str) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        "bytia-tts", "--", clean_text,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        env=_child_env(),
    )


async def play_speech(text: str) -> asyncio.Task | None:
    """Habla el texto con bytia-tts (piper local). No bloquea: lanza el proceso
    y devuelve inmediatamente una tarea que COMPLETA CUANDO TERMINA EL HABLA
    (o None si no había nada que reproducir). stop() puede cortar en cualquier
    momento; en ese caso la tarea también completa."""
    global _active_player, _reap_task

    clean_text = TextCleaner.clean(text)
    if not clean_text:
        logger.warning("play_speech: texto vacío después de limpiar")
        return None

    try:
        proc = await _launch(clean_text)
    except Exception as e:
        logger.error(f"play_speech error: {e}")
        return None

    _active_player = proc
    logger.info("bytia-tts lanzado (pid=%s, %d chars)", proc.pid, len(clean_text))

    async def _reap(proc: asyncio.subprocess.Process) -> None:
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("bytia-tts failed (rc=%s): %s",
                         proc.returncode, (stderr or b"").decode()[:200])

    _reap_task = asyncio.create_task(_reap(proc))
    return _reap_task


if __name__ == "__main__":
    import sys

    async def _main() -> None:
        task = await play_speech(sys.argv[1] if len(sys.argv) > 1 else "Hola Pedro, esto es una prueba")
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=120)
            except asyncio.TimeoutError:
                stop()
        proc = _active_player
        print(f"bytia-tts rc={proc.returncode if proc else None}")

    asyncio.run(_main())
