"""Guard de tamaño para resultados de herramientas.

Incidente 2026-11-15: un ``file_read`` del HANDOFF (201 686 chars, 500 líneas
de líneas larguísimas) agotó la ventana de contexto del motor y el modelo
empezó a devolver respuestas vacías con HTTP 200. ``file_read`` limitaba
líneas, no bytes, así que nada lo frenaba.

Este guard es el **único** punto donde se recorta lo que entra al contexto:

- cabeza + cola legibles (los errores suelen estar al final),
- el original completo en disco (hasta ``MAX_SPILL_BYTES``), con la ruta en el
  marcador para que el modelo lea el resto por partes con ``file_read`` o
  ``grep``.

Política única: ninguna herramienta recorta por su cuenta (``bash`` ya no
corta a 50 000 chars); el límite se decide aquí.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 48_000
MAX_SPILL_BYTES = 5_000_000
SPILL_RETENTION_DAYS = 7
HEAD_RATIO = 0.60
TAIL_RATIO = 0.25

ENV_LIMIT = "KODE_MAX_TOOL_RESULT_CHARS"


def max_chars() -> int:
    """Límite efectivo por resultado (env ``KODE_MAX_TOOL_RESULT_CHARS``)."""
    raw = os.environ.get(ENV_LIMIT, "")
    if not raw:
        return DEFAULT_MAX_CHARS
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r no es un entero; usando %d", ENV_LIMIT, raw, DEFAULT_MAX_CHARS)
        return DEFAULT_MAX_CHARS
    return value if value > 0 else DEFAULT_MAX_CHARS


def _safe_component(value: str, fallback: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in value)[:40]
    return cleaned or fallback


def _purge_old(root: Path) -> None:
    """Borra spills de más de SPILL_RETENTION_DAYS. Nunca propaga errores."""
    cutoff = time.time() - SPILL_RETENTION_DAYS * 86_400
    try:
        for path in root.rglob("*.txt"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue
    except OSError:
        pass


def _spill(text: str, tool_name: str, session_id: str | None, root: Path) -> tuple[Path, bool]:
    """Escribe el original en disco. Devuelve (ruta, guardado_completo)."""
    directory = root / _safe_component(session_id or "nosession", "nosession")
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:8]
    path = directory / f"{_safe_component(tool_name, 'tool')}-{digest}-{int(time.time())}.txt"
    payload = text[:MAX_SPILL_BYTES]
    path.write_text(payload, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    _purge_old(root)
    return path, len(payload) == len(text)


def guard_tool_output(
    output: str,
    tool_name: str,
    *,
    session_id: str | None = None,
    data_dir: Path | str | None = None,
) -> str:
    """Recorta un resultado de herramienta si supera el límite.

    Por debajo del límite devuelve el texto intacto (sin tocar disco).
    """
    text = output or ""
    limit = max_chars()
    if len(text) <= limit:
        return text

    base = Path(data_dir) if data_dir else Path.home() / ".bytia-kode"
    try:
        path, complete = _spill(text, tool_name, session_id, base / "tool-results")
    except OSError as exc:
        # Sin disco no hay spill; mejor un recorte honesto que un fallo de turno.
        logger.warning("No se pudo guardar el resultado completo: %s", exc)
        path, complete = None, False

    head_n = int(limit * HEAD_RATIO)
    tail_n = int(limit * TAIL_RATIO)
    head = text[:head_n]
    tail = text[-tail_n:] if tail_n else ""

    if path is not None:
        destino = (
            f"Original completo: {path}"
            if complete
            else f"Original (primeros {MAX_SPILL_BYTES:,} chars): {path}"
        )
    else:
        destino = "No se pudo guardar el original en disco."

    marker = (
        f"\n\n… [resultado truncado: {len(text):,} chars → {limit:,} "
        f"(cabeza {head_n:,} + cola {tail_n:,}). {destino}. "
        "Usa file_read con offset/limit, o grep, sobre esa ruta para ver el resto.] …\n\n"
    )
    logger.info(
        "Tool output recortado: %s %s → %s chars", tool_name, f"{len(text):,}", f"{limit:,}"
    )
    return f"{head}{marker}{tail}"
