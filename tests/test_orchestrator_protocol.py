"""Contrato del parser de secciones del orquestador (F1).

El worker agéntico devuelve texto con tres secciones (### NOTES / ### NEXT /
### STATUS). El manager usa PLAN/TASKS/STATUS/NEXT. El parser debe ser
tolerante con la forma del heading pero estricto con el contenido: una
sección desconocida dentro de NOTES es una violación de protocolo, no texto.
"""

from __future__ import annotations

import pytest

from bytia_kode.orchestrator.protocol import parse_sections, validate_sections


class TestParseSections:
    def test_three_sections_happy_path(self):
        text = (
            "### NOTES\n"
            "El enfoque es X.\n"
            "### NEXT\n"
            "Implementar Y.\n"
            "### STATUS\n"
            "continue\n"
        )

        parsed = parse_sections(text)

        assert parsed["NOTES"] == "El enfoque es X."
        assert parsed["NEXT"] == "Implementar Y."
        assert parsed["STATUS"] == "continue"

    def test_tolerates_heading_variants(self):
        text = "## NOTES\na\n**NEXT**\nb\nSTATUS:\ncontinue\n"

        parsed = parse_sections(text)

        assert parsed["NOTES"] == "a"
        assert parsed["NEXT"] == "b"
        assert parsed["STATUS"] == "continue"

    def test_multiline_content_is_preserved(self):
        text = "### NOTES\nlinea 1\nlinea 2\n### NEXT\nb\n### STATUS\ncontinue\n"

        parsed = parse_sections(text)

        assert parsed["NOTES"] == "linea 1\nlinea 2"

    def test_text_without_sections_returns_empty(self):
        assert parse_sections("no hay secciones aqui") == {}

    def test_unknown_hash_heading_is_treated_as_text(self):
        text = "### NOTES\na\n### RANDOM\nz\n### NEXT\nb\n### STATUS\ncontinue\n"

        parsed = parse_sections(text)

        assert "RANDOM" not in parsed
        assert "z" in parsed["NOTES"]

    def test_hash_comment_inside_fence_is_not_a_heading(self):
        text = (
            "### NOTES\n"
            "Verificado con:\n"
            "```bash\n"
            "# verificar\n"
            "pytest -q\n"
            "```\n"
            "### NEXT\nb\n### STATUS\ncontinue\n"
        )

        parsed = parse_sections(text)

        assert "VERIFICAR" not in parsed
        assert "# verificar" in parsed["NOTES"]

    def test_bold_text_is_not_a_heading(self):
        text = "### NOTES\n**Importante**\ncontenido\n### NEXT\nb\n### STATUS\ncontinue\n"

        parsed = parse_sections(text)

        assert "IMPORTANTE" not in parsed
        assert "**Importante**" in parsed["NOTES"]

    def test_colon_line_is_not_a_heading(self):
        text = "### NOTES\nEjemplo:\ncontenido\n### NEXT\nb\n### STATUS\ncontinue\n"

        parsed = parse_sections(text)

        assert "EJEMPLO" not in parsed
        assert "Ejemplo:" in parsed["NOTES"]

    def test_inline_status_value_is_parsed(self):
        parsed = parse_sections("### NOTES\na\n### NEXT\nb\n### STATUS: solved\n")

        assert parsed["STATUS"] == "solved"


class TestValidateSections:
    def test_valid_output_has_no_errors(self):
        parsed = {"NOTES": "a", "NEXT": "b", "STATUS": "continue"}

        errors = validate_sections(
            parsed,
            required=("NOTES", "NEXT", "STATUS"),
            allowed_status=("continue", "solved"),
        )

        assert errors == []

    def test_missing_section_reported(self):
        parsed = {"NOTES": "a", "STATUS": "continue"}

        errors = validate_sections(parsed, required=("NOTES", "NEXT", "STATUS"))

        assert "missing: NEXT" in errors

    def test_empty_section_reported(self):
        parsed = {"NOTES": "   ", "NEXT": "b", "STATUS": "continue"}

        errors = validate_sections(parsed, required=("NOTES", "NEXT", "STATUS"))

        assert "empty: NOTES" in errors

    def test_status_is_case_insensitive(self):
        parsed = {"NOTES": "a", "NEXT": "b", "STATUS": "CONTINUE"}

        errors = validate_sections(
            parsed,
            required=("NOTES", "NEXT", "STATUS"),
            allowed_status=("continue", "solved"),
        )

        assert errors == []

    def test_invalid_status_reported(self):
        parsed = {"NOTES": "a", "NEXT": "b", "STATUS": "donee"}

        errors = validate_sections(
            parsed,
            required=("NOTES", "NEXT", "STATUS"),
            allowed_status=("continue", "solved"),
        )

        assert "invalid STATUS: donee" in errors

    def test_section_from_another_role_is_unexpected(self):
        parsed = {"NOTES": "a", "NEXT": "b", "STATUS": "continue", "PLAN": "colado"}

        errors = validate_sections(
            parsed,
            required=("NOTES", "NEXT", "STATUS"),
            allowed=("NOTES", "NEXT", "STATUS"),
            allowed_status=("continue", "solved"),
        )

        assert "unexpected section: PLAN" in errors
