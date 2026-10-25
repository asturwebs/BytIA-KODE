"""Parser y validación del protocolo de secciones (F1).

Formato: el modelo devuelve secciones precedidas por un heading. Se aceptan
``### NOTES``, ``## NOTES``, ``**NOTES**`` y ``NOTES:``; las claves se
normalizan a mayúsculas. Todo lo que no sea heading pertenece a la sección
abierta. Las secciones desconocidas se conservan para que la validación las
pueda rechazar (un heading colado en NOTES es una violación de protocolo).
"""

from __future__ import annotations

import re

# Solo estas secciones son headings. Cualquier otra línea con forma de
# heading (un `# comentario` en un fence, `**Importante**`, `Ejemplo:`) es
# texto de la sección abierta: el worker agéntico escribe prosa y comandos,
# y tratarlos como secciones abortaba la tarea (revisión F1, C1).
KNOWN_SECTIONS = frozenset({"PLAN", "TASKS", "NOTES", "NEXT", "STATUS", "CODE"})

_HASH_HEADING = re.compile(
    r"^\s{0,3}#{1,6}\s*([A-Za-z][A-Za-z0-9_]*)\s*(?::\s*(.*))?$"
)
_BOLD_HEADING = re.compile(r"^\s{0,3}\*\*([A-Za-z][A-Za-z0-9_]*)\*\*\s*$")
_COLON_HEADING = re.compile(r"^\s{0,3}([A-Za-z][A-Za-z0-9_]*):\s*$")


def _heading(line: str) -> tuple[str, str] | None:
    """(SECCIÓN, contenido_inline) si la línea abre una sección conocida."""
    match = _HASH_HEADING.match(line)
    if match and match.group(1).upper() in KNOWN_SECTIONS:
        return match.group(1).upper(), (match.group(2) or "").strip()
    match = _BOLD_HEADING.match(line)
    if match and match.group(1).upper() in KNOWN_SECTIONS:
        return match.group(1).upper(), ""
    match = _COLON_HEADING.match(line)
    if match and match.group(1).upper() in KNOWN_SECTIONS:
        return match.group(1).upper(), ""
    return None


def parse_sections(text: str) -> dict[str, str]:
    """Devuelve {SECCIÓN: contenido} para las secciones conocidas del texto."""
    collected: dict[str, list[str]] = {}
    current: str | None = None
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            if current is not None:
                collected[current].append(line)
            continue
        if not in_fence:
            heading = _heading(line)
            if heading is not None:
                current, inline = heading
                collected.setdefault(current, [])
                if inline:
                    collected[current].append(inline)
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
