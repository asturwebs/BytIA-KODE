"""Specs de dominio del orquestador (F1).

Un ``DomainSpec`` declara, por rol, qué secciones exige el protocolo y qué
valores de STATUS acepta. El runner valida el output de cada llamada contra
esta spec; las plantillas de ``prompts.py`` emiten exactamente esas secciones.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleSpec:
    required: tuple[str, ...]
    # Recomendación del prompt, NO validación (M1): el runner tolera su
    # ausencia y aplica el invariante «continue sin NEXT → primera tarea».
    recommended_when_continuing: tuple[str, ...] = ()
    # Secciones toleradas pero no requeridas (p. ej. NEXT en ideation, que el
    # protocolo anterior pedía y el modelo puede seguir emitiendo).
    allowed_extra: tuple[str, ...] = ()
    allowed_status: tuple[str, ...] | None = None


@dataclass(frozen=True)
class DomainSpec:
    name: str
    roles: dict[str, RoleSpec]


CODE_REPO = DomainSpec(
    name="code_repo",
    roles={
        "primary_plan": RoleSpec(required=("PLAN", "TASKS")),
        "ideation": RoleSpec(required=("NOTES",), allowed_extra=("NEXT",)),
        "worker": RoleSpec(
            required=("NOTES", "NEXT", "STATUS"),
            allowed_status=("continue", "solved"),
        ),
        "primary_manage": RoleSpec(
            required=("STATUS", "TASKS"),
            recommended_when_continuing=("NEXT",),
            allowed_status=("continue", "done"),
        ),
    },
)
