"""Contrato de specs y prompts (F1).

Las plantillas de cada rol deben emitir exactamente las secciones que el
parser reconoce. Si la plantilla pide una sección que el validador no admite
(o al revés), el bucle se rompe en producción, no en test.
"""

from __future__ import annotations

from bytia_kode.orchestrator.prompts import ROLE_PROMPTS
from bytia_kode.orchestrator.specs import CODE_REPO

EXPECTED_ROLES = ("primary_plan", "ideation", "worker", "primary_manage")


class TestCodeReproSpec:
    def test_defines_the_four_roles(self):
        assert set(CODE_REPO.roles) == set(EXPECTED_ROLES)

    def test_worker_requires_three_sections(self):
        worker = CODE_REPO.roles["worker"]

        assert worker.required == ("NOTES", "NEXT", "STATUS")
        assert worker.allowed_status == ("continue", "solved")

    def test_manage_recommends_next_when_continuing(self):
        manage = CODE_REPO.roles["primary_manage"]

        assert manage.required == ("STATUS", "TASKS")
        assert manage.recommended_when_continuing == ("NEXT",)
        assert manage.allowed_status == ("continue", "done")

    def test_ideation_requires_only_notes(self):
        # M2: el NEXT de ideation se pedía, se parseaba y se descartaba.
        # E2E real: qwen38 devolvía PLAN/TASKS; se toleran y se ignoran.
        ideation = CODE_REPO.roles["ideation"]
        assert ideation.required == ("NOTES",)
        assert set(ideation.allowed_extra) == {"NEXT", "PLAN", "TASKS"}


class TestRolePrompts:
    def test_every_role_has_a_prompt(self):
        assert set(ROLE_PROMPTS) == set(EXPECTED_ROLES)

    def test_prompts_emit_the_sections_the_parser_expects(self):
        for role in EXPECTED_ROLES:
            prompt = ROLE_PROMPTS[role]
            for section in CODE_REPO.roles[role].required:
                assert f"### {section}" in prompt, (role, section)

    def test_worker_prompt_forbids_nested_headings(self):
        assert "no headings" in ROLE_PROMPTS["worker"].lower()

    def test_ideation_prompt_forbids_plan(self):
        # E2E real: qwen38 devolvió un PLAN en la fase de ideación.
        assert "no devuelvas un plan" in ROLE_PROMPTS["ideation"].lower()

    def test_worker_prompt_does_not_ask_for_code_in_text(self):
        prompt = ROLE_PROMPTS["worker"].lower()
        assert "no devuelvas el código" in prompt

    def test_prompts_do_not_reintroduce_the_code_section(self):
        assert len(ROLE_PROMPTS) == len(EXPECTED_ROLES)
        for prompt in ROLE_PROMPTS.values():
            assert "### CODE" not in prompt

    def test_manage_prompt_explains_conditional_next(self):
        prompt = ROLE_PROMPTS["primary_manage"].lower()
        assert "omite" in prompt and "done" in prompt
