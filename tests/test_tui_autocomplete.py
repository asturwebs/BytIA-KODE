"""Tests del autocompletado de comandos y de la fuente única TUI_COMMANDS.

Cubre la función pura `filter_commands`, la coherencia de TUI_COMMANDS con
/help y Ctrl+P, y el popup pilotado con el Pilot de Textual (sin providers:
el agent se inyecta como en test_tui_interruption.py).
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from bytia_kode.tui import (
    BytIAKODEApp,
    CommandMenuScreen,
    CommandSuggestions,
    InputScreen,
    PromptTextArea,
    TUI_COMMANDS,
    build_help_table,
    filter_commands,
)


class FakeAgent:
    """Agent de mentira: chat inmediato y close no-op."""

    def __init__(self):
        self.config = MagicMock()
        self.on_tool_call = []
        self.on_tool_done = []
        self.on_subprocess = []
        self._bkode_path = None
        self.providers = None  # los workers de arranque prueban providers y se tragan el fallo

    def set_session(self, source="tui", source_ref=""):
        return "test_session"

    def interrupt(self):
        raise AssertionError("no debía interrumpirse")

    async def kill(self):
        pass

    async def close(self):
        pass

    async def chat(self, text, provider=None):
        yield "ok"


async def _wait_for(pilot, predicate, timeout=8.0, what="condición"):
    """Espera activa con tope procesando la cola de mensajes (patrón AST-24)."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError(f"timeout esperando: {what}")
        await pilot.pause()
        await asyncio.sleep(0.02)


def _names(commands) -> list[str]:
    return [command.name for command in commands]


def _popup(app) -> CommandSuggestions:
    return app.query_one(CommandSuggestions)


def _field(app) -> PromptTextArea:
    return app.query_one("#input-field", PromptTextArea)


class TestFilterCommands:
    """`filter_commands` es pura: sin app, sin widgets."""

    def test_empty_input_means_no_popup(self):
        assert filter_commands("") == []

    def test_normal_text_never_opens_popup(self):
        assert filter_commands("hello world") == []
        # El "/" debe ser el PRIMER carácter del input.
        assert filter_commands(" /escalate") == []

    def test_slash_alone_lists_all_slash_commands(self):
        result = filter_commands("/")
        assert result
        assert _names(result) == [command.name for command in TUI_COMMANDS if command.name]

    def test_prefix_filters_down_to_escalate(self):
        assert _names(filter_commands("/esc")) == ["/escalate"]

    def test_filter_is_case_insensitive(self):
        assert _names(filter_commands("/ESC")) == ["/escalate"]

    def test_trailing_space_means_argument_typing(self):
        assert filter_commands("/escalate ") == []
        assert filter_commands("/escalate fix the bug") == []

    def test_multiword_subcommands_match_by_usage_prefix(self):
        assert _names(filter_commands("/skills sa")) == ["/skills save"]
        assert _names(filter_commands("/skills sh")) == ["/skills show"]
        assert _names(filter_commands("/skills v")) == ["/skills verify"]

    def test_no_duplicates(self):
        names = _names(filter_commands("/"))
        assert len(names) == len(set(names))


class TestCommandSource:
    """TUI_COMMANDS es la única fuente de /help, autocompletado y Ctrl+P."""

    def test_tui_commands_include_escalate(self):
        assert "/escalate" in _names(TUI_COMMANDS)
        escalate = next(command for command in TUI_COMMANDS if command.name == "/escalate")
        # Aceptar el comando deja el cursor listo para escribir la tarea.
        assert escalate.insert_text == "/escalate "

    def test_tui_commands_include_verify(self):
        assert "/verify" in _names(TUI_COMMANDS)
        assert "/verify" in _names(filter_commands("/ver"))
        verify = next(command for command in TUI_COMMANDS if command.name == "/verify")
        assert verify.menu_action == "verify_repo"

    def test_tui_commands_include_init(self):
        assert "/init" in _names(TUI_COMMANDS)
        assert "/init" in _names(filter_commands("/in"))
        init = next(command for command in TUI_COMMANDS if command.name == "/init")
        assert init.menu_action == "init_project"

    def test_menu_is_derived_from_tui_commands(self):
        expected = [
            (command.menu_label, command.menu_action)
            for command in TUI_COMMANDS
            if command.menu_action
        ]
        assert list(CommandMenuScreen.COMMANDS) == expected

    def test_every_menu_action_exists_on_app(self):
        missing = [
            action
            for _, action in CommandMenuScreen.COMMANDS
            if not hasattr(BytIAKODEApp, f"action_{action}")
        ]
        assert missing == []

    def test_help_table_covers_every_command(self):
        console = Console(record=True, width=200)
        console.print(build_help_table())
        output = console.export_text()
        for command in TUI_COMMANDS:
            if command.usage:
                assert command.usage in output


class TestAutocompletePopup:
    """Popup pilotado con el Pilot de Textual (sin providers)."""

    @pytest.mark.asyncio
    async def test_typing_slash_opens_the_full_list(self):
        app = BytIAKODEApp(agent=FakeAgent())
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.pause()

            popup = _popup(app)
            assert popup.display is True
            assert _names(popup.matches) == [
                command.name for command in TUI_COMMANDS if command.name
            ]
            assert _field(app).suggestions_open is True

    @pytest.mark.asyncio
    async def test_typing_filters_the_list(self):
        app = BytIAKODEApp(agent=FakeAgent())
        async with app.run_test() as pilot:
            await pilot.press("/", "e", "s", "c")
            await pilot.pause()

            assert _names(_popup(app).matches) == ["/escalate"]
            assert _field(app).text == "/esc"

    @pytest.mark.asyncio
    async def test_enter_applies_the_selected_command_without_submitting(self):
        app = BytIAKODEApp(agent=FakeAgent())
        async with app.run_test() as pilot:
            await pilot.press("/", "e", "s", "c")
            await pilot.press("enter")
            await pilot.pause()

            field = _field(app)
            assert field.text == "/escalate "
            assert field.suggestions_open is False
            assert _popup(app).display is False
            # Enter aplicó el comando; no lo ejecutó ni lo envió al agente.
            assert app._history == []
            assert app.is_processing is False

    @pytest.mark.asyncio
    async def test_tab_applies_the_selected_command(self):
        app = BytIAKODEApp(agent=FakeAgent())
        async with app.run_test() as pilot:
            await pilot.press("/", "q", "u")
            await pilot.press("tab")
            await pilot.pause()

            assert _field(app).text == "/quit"
            assert _field(app).suggestions_open is False

    @pytest.mark.asyncio
    async def test_up_down_move_the_highlight(self):
        app = BytIAKODEApp(agent=FakeAgent())
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.pause()
            popup = _popup(app)
            assert popup.selected_name == "/quit"

            await pilot.press("down")
            await pilot.pause()
            assert popup.selected_name == "/reset"

            await pilot.press("up")
            await pilot.pause()
            assert popup.selected_name == "/quit"
            # Navegar no toca el texto del prompt.
            assert _field(app).text == "/"

    @pytest.mark.asyncio
    async def test_escape_closes_the_list_without_interrupting(self):
        app = BytIAKODEApp(agent=FakeAgent())
        async with app.run_test() as pilot:
            app.is_processing = True  # incluso con un turno en vuelo
            await pilot.press("/", "e", "s", "c")
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            field = _field(app)
            assert field.suggestions_open is False
            assert _popup(app).display is False
            assert field.text == "/esc"  # no se pierde lo tecleado
            # Esc cerró la lista en vez de interrumpir al agente.
            assert app.is_processing is True

    @pytest.mark.asyncio
    async def test_normal_text_is_unaffected_and_enter_still_submits(self):
        app = BytIAKODEApp(agent=FakeAgent())
        async with app.run_test() as pilot:
            await pilot.press("h", "i")
            await pilot.pause()
            assert _field(app).text == "hi"
            assert _popup(app).display is False

            await pilot.press("enter")
            await _wait_for(
                pilot,
                lambda: app._history == ["hi"] and not app.is_processing,
                what="turno normal completado",
            )

