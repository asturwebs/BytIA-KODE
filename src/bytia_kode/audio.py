import re
import logging
import asyncio
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

TEMP_DIR = Path("/tmp/bytia_audio")


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


_active_player: subprocess.Popen | None = None


def stop():
    global _active_player
    if _active_player and _active_player.poll() is None:
        _active_player.terminate()
        try:
            _active_player.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _active_player.kill()
    _active_player = None


def is_playing() -> bool:
    return _active_player is not None and _active_player.poll() is None


async def play_speech(text: str) -> None:
    global _active_player

    clean_text = TextCleaner.clean(text)
    if not clean_text:
        logger.warning("play_speech: texto vacío después de limpiar")
        return

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = TEMP_DIR / f"speech_{hash(clean_text)}.mp3"

    try:
        proc = await asyncio.create_subprocess_exec(
            "edge-tts",
            "--voice", "es-MX-DaliaNeural",
            "--text", clean_text,
            "--write-media", str(audio_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f"edge-tts failed: {stderr.decode()[:200]}")
            return

        if not audio_path.exists():
            logger.error(f"audio file not created: {audio_path}")
            return

        _active_player = subprocess.Popen(
            ["mpv", "--no-video", "--af=adelay=0.3", str(audio_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(f"playing audio: {audio_path.name} (pid={_active_player.pid})")

    except Exception as e:
        logger.error(f"play_speech error: {e}")


if __name__ == "__main__":
    import sys
    test_text = sys.argv[1] if len(sys.argv) > 1 else "Hola Pedro, esto es una prueba"
    asyncio.run(play_speech(test_text))
