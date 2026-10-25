"""Parser y validación del protocolo de secciones (F1).

Formato: el modelo devuelve secciones precedidas por un heading. Se aceptan
``### NOTES``, ``## NOTES``, ``**NOTES**`` y ``NOTES:``; las claves se
normalizan a mayúsculas. Todo lo que no sea heading pertenece a la sección
abierta. Las secciones desconocidas se conservan para que la validación las
pueda rechazar (un heading colado en NOTES es una violación de protocolo).
"""

from __future__ import annotations

import re

_HEADING_PATTERNS = (
    re.compile(r"^\s{0,3}#{1,6}\s*([A-Za-z][A-Za-z0-9_]*)\s*$"),
    re.compile(r"^\s{0,3}\*\*([A-Za-z][A-Za-z0-9_]*)\*\*\s*$"),
    re.compile(r"^\s{0,3}([A-Za-z][A-Za-z0-9_]*):\s*$"),
)


def _heading_name(line: str) -> str | None:
    for pattern in _HEADING_PATTERNS:
        match = pattern.match(line)
        if match:
            return match.group(1).upper()
    return None


def parse_sections(text: str) -> dict[str, str]:
    """Devuelve {SECCIÓN: contenido} para todas las secciones del texto."""
    collected: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        name = _heading_name(line)
        if name is not None:
            current = name
            collected.setdefault(current, [])
            continue
        if current is not None:
            collected[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in collected.items()}


def validate_sections(
    parsed: dict[str, str],
    required: tuple[str, ...],
    *,
    allowed: tuple[str, ...] | None = None,
    allowed_status: tuple[str, ...] | None = None,
) -> list[str]:
    """Lista de errores de protocolo; vacía si el output es válido."""
    errors: list[str] = []
    for name in required:
        if name not in parsed:
            errors.append(f"missing: {name}")
        elif not parsed[name].strip():
            errors.append(f"empty: {name}")

    if allowed is not None:
        allowed_set = {name.upper() for name in allowed}
        for name in parsed:
            if name not in allowed_set:
                errors.append(f"unexpected section: {name}")

    if allowed_status is not None and "STATUS" in parsed:
        status_text = parsed["STATUS"].strip()
        value = status_text.split()[0].lower() if status_text else ""
        if value not in {status.lower() for status in allowed_status}:
            errors.append(f"invalid STATUS: {value}")
    return errors
