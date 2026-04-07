"""BytIA KODE TUI - Theme-aware CLI interface with Textual. v4"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from textual import work, on
from textual.app import App, ComposeResult
from textual import events
from textual.binding import Binding
from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Header, Footer, Static, TextArea, Button, ListView, ListItem, Label, Input
from textual.screen import ModalScreen
from textual.reactive import reactive
from textual.message import Message as TextualMessage
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.table import Table
from rich import box

from bytia_kode.config import load_config
from bytia_kode.agent import Agent
from bytia_kode.providers.client import Message
from bytia_kode import __version__

logger = logging.getLogger(__name__)

BANNER_TEMPLATE = """[bold {accent}]██████╗      ██╗  ██╗ ██████╗ ██████╗ ███████╗    [dim italic]by AsturWebs & BytIA[/]
[bold {accent}]██╔══██╗      ██║ ██╔╝██╔═══██╗██╔══██╗██╔════╝[/]
[bold {accent}]██████╔╝      █████╔╝ ██║   ██║██║  ██║█████╗  [/]
[bold {accent}]██╔══██╗      ██╔═██╗ ██║   ██║██║  ██║██╔══╝  [/]
[bold {accent}]██████╔╝      ██║  ██╗╚██████╔╝██████╔╝███████╗[/]
[bold {accent}]╚═════╝       ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝[/]
[dim italic]Agente + Skills + Terminal = Enterprise Automation[/]
[dim]Commands: /reset · /model · /context · /help | Ctrl+P menu[/dim]"""

_THEME_FILE = Path.home() / ".bytia-kode" / "theme.json"
ALL_THEMES = [
    "gruvbox", "monokai", "nord", "dracula", "catppuccin-mocha", "tokyo-night",
    "atom-one-dark", "atom-one-light", "catppuccin-frappe", "catppuccin-latte",
    "catppuccin-macchiato", "flexoki", "rose-pine", "rose-pine-dawn",
    "rose-pine-moon", "solarized-dark", "solarized-light", "textual-dark",
    "textual-light",
]
LIGHT_THEMES = {"atom-one-light", "catppuccin-latte", "flexoki", "rose-pine", "rose-pine-dawn", "solarized-light", "textual-light"}
DEFAULT_THEME = "gruvbox"


def _load_theme() -> str:
    try:
        if _THEME_FILE.exists():
            t = json.loads(_THEME_FILE.read_text()).get("theme", DEFAULT_THEME)
            return t if t in ALL_THEMES else DEFAULT_THEME
    except Exception:
        pass
    return DEFAULT_THEME


def _save_theme(theme: str):
    try:
        _THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
        _THEME_FILE.write_text(json.dumps({"theme": theme}))
    except Exception:
        pass


class ChatMessage(Static):
    def __init__(self, role: str, content: str, **kwargs):
        self.role = role
        self.msg_content = content
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        self._update_content()
        self.watch(self.app, "theme", self._on_theme_changed)

    def _on_theme_changed(self, old_theme: str, new_theme: str) -> None:
        self._update_content()

    def _update_content(self):
        c = self.app._get_theme_colors()
        if self.role == "user":
            self.update(Panel(
                Text(self.msg_content, style=f"bold {c['secondary']}"),
                title=f"[bold {c['secondary']}]You[/]",
                title_align="left",
                border_style=c["secondary"],
                padding=(0, 1),
                expand=False,
            ))
        elif self.role == "assistant":
            self.update(Panel(
                Markdown(self.msg_content),
                title=f"[bold {c['accent']}]KODE[/]",
                title_align="left",
                border_style=c["accent"],
                padding=(0, 1),
                expand=False,
            ))
        elif self.role == "tool":
            content = self.msg_content[:10000]
            if len(content) > 50:
                body = Syntax(content, "bash", theme="monokai", line_numbers=False)
            else:
                body = Text(content, style=c["warning"])
            self.update(Panel(
                body,
                title=f"[bold {c['warning']}]Tool[/]",
                title_align="left",
                border_style=c["warning"],
                padding=(0, 1),
                expand=False,
            ))
        elif self.role == "error":
            self.update(Panel(
                Text(self.msg_content, style=f"bold {c['error']}"),
                title=f"[bold {c['error']}]Error[/]",
                title_align="left",
                border_style=c["error"],
                padding=(0, 1),
                expand=False,
            ))
        elif self.role == "system":
            self.update(Text(f"  {self.msg_content}", style="dim italic"))


class PromptTextArea(TextArea):
    class Submitted(TextualMessage):
        def __init__(self, text: str):
            self.text = text
            super().__init__()

    def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted(self.text))


class ActivityIndicator(Static):
    """Dynamic status bar showing agent state and context usage."""

    def __init__(self, **kwargs):
        self._status = "ready"
        self._detail = ""
        self._router_ctx_size = 0
        self._router_prompt_tokens = 0
        super().__init__("", id="activity-indicator", **kwargs)

    def on_mount(self) -> None:
        self._refresh()
        self.watch(self.app, "theme", lambda *_: self._refresh())

    def set_status(self, status: str, detail: str = ""):
        self._status = status
        self._detail = detail
        self._refresh()

    def set_router_info(self, ctx_size: int, prompt_tokens: int):
        self._router_ctx_size = ctx_size
        self._router_prompt_tokens = prompt_tokens

    def _refresh(self):
        try:
            c = self.app._get_theme_colors()
        except Exception:
            c = {"accent": "#7ee787", "warning": "#f0883e", "error": "#ff5555"}
        a, w, e = c.get("accent", "#7ee787"), c.get("warning", "#f0883e"), c.get("error", "#ff5555")

        ctx_info = ""
        model_info = ""
        try:
            agent = self.app.agent
            client = agent.providers.get(self.app.active_provider)
            provider = self.app._provider_name()

            if self._router_ctx_size > 0:
                used = agent._estimate_tokens()
                total = self._router_ctx_size
                ctx_info = f" | ctx ~{used // 1000}k/{total // 1000}k"
            else:
                used = agent._estimate_tokens()
                total = agent._max_context_tokens
                ctx_info = f" | ctx ~{used // 1000}k/{total // 1000}k"

            model_info = f" | {provider} | {client.model}"
        except Exception:
            pass

        if self._status == "ready":
            self.update(f"  [bold {a}]\u25cf Ready{model_info}{ctx_info}[/]")
        elif self._status == "thinking":
            self.update(f"  [bold {w}]\u25d0 Thinking...{model_info}{ctx_info}[/]")
        elif self._status == "tool":
            self.update(f"  [bold {a}]\u2699 {self._detail}{model_info}{ctx_info}[/]")
        elif self._status == "error":
            self.update(f"  [bold {e}]\u2717 Error[/]")
        elif self._status == "skill":
            self.update(f"  [bold {w}]\u270e {self._detail}{model_info}{ctx_info}[/]")
        else:
            self.update(f"  [bold {a}]\u25cf Ready{model_info}{ctx_info}[/]")


class ThinkingBlock(Static):
    """Collapsible reasoning/thinking block. Click or Ctrl+D to toggle."""

    can_focus = True

    BINDINGS = [
        Binding("enter", "toggle", "Toggle", show=False),
    ]

    _expanded: reactive[bool] = reactive(False)

    def __init__(self, content: str, **kwargs):
        self.thinking_content = content
        super().__init__("", **kwargs)

    def on_mount(self) -> None:
        self._update_display()
        self.watch(self, "_expanded", lambda *_: self._update_display())

    def on_click(self) -> None:
        self.toggle()

    def action_toggle(self) -> None:
        self.toggle()

    def toggle(self):
        self._expanded = not self._expanded

    def append(self, delta: str):
        self.thinking_content += delta
        self._update_display()

    def _update_display(self):
        try:
            c = self.app._get_theme_colors()
        except Exception:
            c = {"warning": "#f0883e", "accent": "#7ee787"}
        w = c.get("warning", "#f0883e")
        lines = self.thinking_content.strip().split("\n")
        n_lines = len(lines)
        if self._expanded:
            preview = self.thinking_content[:10000]
            if len(self.thinking_content) > 10000:
                preview += f"\n... ({n_lines} lines total)"
            self.update(Panel(
                Text(preview, style=f"italic {w}"),
                title=f"[bold {w}]\U0001f4ad Reasoning ({n_lines} lines)[/] [dim]click/Ctrl+D collapse[/]",
                title_align="left",
                border_style=w,
                padding=(0, 1),
                expand=False,
            ))
        else:
            self.update(Panel(
                Text(f"  {n_lines} lines of reasoning", style=f"dim italic {w}"),
                title=f"[bold {w}]\U0001f4ad Reasoning[/] [dim]click/Ctrl+D expand[/]",
                title_align="left",
                border_style=w,
                padding=(0, 1),
                expand=False,
            ))


class ToolBlock(Static):
    """Collapsible tool execution block. Click to toggle."""

    can_focus = True

    BINDINGS = [
        Binding("enter", "toggle", "Toggle", show=False),
    ]

    _expanded: reactive[bool] = reactive(False)

    def __init__(self, tool_name: str, output: str, error: bool = False, **kwargs):
        self.tool_name = tool_name
        self.tool_output = output
        self.tool_error = error
        super().__init__("", **kwargs)

    def on_mount(self) -> None:
        self._update_display()
        self.watch(self, "_expanded", lambda *_: self._update_display())

    def on_click(self) -> None:
        self.toggle()

    def action_toggle(self) -> None:
        self.toggle()

    def toggle(self):
        self._expanded = not self._expanded

    def _update_display(self):
        try:
            c = self.app._get_theme_colors()
        except Exception:
            c = {"warning": "#f0883e", "accent": "#7ee787", "error": "#ff5555"}
        a = c.get("accent", "#7ee787")
        e = c.get("error", "#ff5555")
        color = e if self.tool_error else a
        icon = "\u274c" if self.tool_error else "\u2705"
        lines = self.tool_output.strip().split("\n")
        n_lines = len(lines)
        if self._expanded:
            preview = self.tool_output[:5000]
            if n_lines > 200:
                preview = "\n".join(lines[:200])
                preview += f"\n... ({n_lines} lines total)"
            body = Syntax(preview, "bash", theme="monokai", line_numbers=False)
        else:
            body = Text(f"  {n_lines} lines of output", style=f"dim italic {color}")
        self.update(Panel(
            body,
            title=f"[bold {color}]{icon} {self.tool_name}[/] [dim]click expand[/]",
            title_align="left",
            border_style=color,
            padding=(0, 1),
            expand=False,
        ))


class InputScreen(ModalScreen):
    """Simple modal that prompts for a single line of text."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, title: str, placeholder: str = "") -> None:
        super().__init__()
        self._title = title
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield Label(self._title, id="prompt-label")
        yield Input(placeholder=self._placeholder, id="prompt-input")

    def on_mount(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    @on(Input.Submitted, "#prompt-input")
    def _on_submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_cancel(self) -> None:
        self.dismiss("")


class CommandMenuScreen(ModalScreen):
    """Ctrl+P popup with available commands."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("up", "cursor_up", "", show=False),
        Binding("down", "cursor_down", "", show=False),
        Binding("enter", "select", "", show=False),
    ]

    COMMANDS = [
        ("\u2630  Quit", "quit"),
        ("\u21ba  Reset conversation", "reset_conversation"),
        ("\U0001f4dd  New session", "new_session"),
        ("\U0001f4c3  List sessions", "list_sessions"),
        ("\U0001f4c2  Load session", "load_session"),
        ("\u2715  Clear screen", "clear_screen"),
        ("\U0001f527  List tools", "show_tools"),
        ("\U0001f4da  List skills", "show_skills"),
        ("\U0001f504  Select model", "select_model"),
        ("\U0001f4c1  List available models", "show_models"),
        ("\U0001f4ac  Show input history", "show_history"),
        ("\u26a1  Toggle safe mode", "toggle_safe_mode"),
        ("\U0001f9e0  Toggle reasoning", "toggle_reasoning"),
        ("\U0001f3a8  Change theme", "change_theme"),
        ("\u21c4  Switch provider", "switch_provider"),
        ("\U0001f4cb  Copy last code block", "copy_last_code"),
        ("\U0001f4cc  Copy last full response", "copy_last_response"),
        ("\u2139  Show model info", "show_model"),
        ("\U0001f4c4  Regenerate context", "regenerate_context"),
    ]

    def compose(self) -> ComposeResult:
        yield ListView(
            *[ListItem(Label(cmd), id=f"cmd-{i}") for i, (cmd, _) in enumerate(self.COMMANDS)],
            id="command-list",
            initial_index=0,
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        try:
            idx = self.query_one("#command-list", ListView).index
            _, action = self.COMMANDS[idx]
            self.dismiss(action)
        except Exception:
            self.dismiss(None)


class BytIAKODEApp(App):
    TITLE = "BytIA KODE"
    SUB_TITLE = "Agentic Coding Assistant"
    CSS_PATH = "tui.css"
    COMMAND_PALETTE_BINDING = ""

    BINDINGS = [
        Binding("ctrl+p", "show_command_menu", "Menu", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("ctrl+r", "reset_conversation", "Reset", show=False),
        Binding("ctrl+l", "clear_screen", "Clear", show=False),
        Binding("ctrl+m", "show_model", "Model info", show=False),
        Binding("ctrl+t", "show_tools", "List tools", show=False),
        Binding("ctrl+s", "show_skills", "List skills", show=False),
        Binding("ctrl+d", "toggle_reasoning", "Reasoning", show=False),
        Binding("ctrl+e", "toggle_safe_mode", "Safe mode", show=False),
        Binding("ctrl+x", "copy_last_code", "Copy code", show=False),
        Binding("ctrl+shift+c", "copy_last_response", "Copy response", show=False),
        Binding("f2", "change_theme", "Theme", show=False, priority=True),
        Binding("f3", "switch_provider", "Provider", show=False, priority=True),
        Binding("up", "history_up", "History prev", show=False),
        Binding("down", "history_down", "History next", show=False),
    ]

    is_processing: reactive[bool] = reactive(False)
    msg_count: reactive[int] = reactive(0)
    safe_mode: reactive[bool] = reactive(True)
    active_provider: reactive[str] = reactive("primary")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme = _load_theme()
        self.config = load_config()
        self.agent = Agent(self.config)
        self.agent.on_tool_call.append(self._on_agent_tool_call)
        self.agent.on_tool_done.append(self._on_agent_tool_done)
        self._history: list[str] = []
        self._history_pos = -1
        self._spinner_timer = None

    def _on_agent_tool_call(self, tool_name: str):
        self.query_one(ActivityIndicator).set_status("tool", detail=f"tool:{tool_name}")

    def _on_agent_tool_done(self, tool_name: str, output: str, error: bool = False):
        chat = self.query_one("#chat-area", VerticalScroll)
        chat.mount(ToolBlock(tool_name, output, error=error))
        chat.scroll_end(animate=False)
        self.set_timer(0.5, lambda: self.query_one(ActivityIndicator).set_status("thinking"))

    def _get_theme_colors(self) -> dict[str, str]:
        t = self.current_theme
        return {
            "accent": t.accent or t.primary or "#7ee787",
            "secondary": t.secondary or "#58a6ff",
            "warning": t.warning or "#f0883e",
            "error": t.error or "#ff5555",
            "success": t.success or "#7ee787",
            "text": t.foreground or "#c9d1d9",
        }

    def _render_banner(self) -> str:
        c = self._get_theme_colors()
        return BANNER_TEMPLATE.replace("{accent}", c["accent"])

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(id="chat-area")
        yield ActivityIndicator()
        with Horizontal(id="input-area"):
            yield PromptTextArea(id="input-field", show_line_numbers=False, language="markdown")
            yield Button("\u25b6", id="send-button")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#input-field", TextArea).focus()
        self.watch(self, "active_provider", self._on_provider_changed)

        self.agent.set_session(source="tui")

        self.run_worker(self._auto_detect_model, exclusive=True, group="model_detect")
        self.run_worker(self._poll_router_info, exclusive=True, group="router_poll")
        self._poll_timer = self.set_interval(5.0, self._poll_router_info)

        activity = self.query_one(ActivityIndicator)
        activity.set_status("ready")

        chat = self.query_one("#chat-area", VerticalScroll)
        c = self._get_theme_colors()
        chat.mount(Static(Panel(
            Text.from_markup(self._render_banner()),
            border_style=c["accent"],
            padding=(1, 2),
            expand=False,
        ), id="banner-panel"))

        bk_status = f"[green]B-KODE.md[/]" if self.agent._bkode_path else "[dim]no B-KODE.md[/]"
        chat.mount(Static(
            Text.from_markup(
                f"  {bk_status} | v{__version__} | Ctrl+P menu | /context | Shift+Drag select"
            ),
            id="info-line",
        ))

        chat.mount(Static(""))
        chat.scroll_end(animate=False)

        if self.safe_mode:
            t = Text("Safe mode ON (dangerous cmds require confirmation)")
            t.stylize("dim italic")
            chat.mount(Static(t))

    def _on_provider_changed(self, old_provider: str, new_provider: str) -> None:
        self._add_system_message(f"Switched to: {self._provider_display_name(new_provider)}")
        self.query_one(ActivityIndicator)._refresh()
        self.run_worker(self._auto_detect_model, exclusive=True)

    async def _auto_detect_model(self) -> None:
        """Auto-detect loaded model from router on startup/provider switch."""
        try:
            detected = await self.agent.providers.auto_detect_model()
            if detected:
                self.query_one(ActivityIndicator)._refresh()
        except Exception as exc:
            logger.debug("Auto-detect model failed: %s", exc)

    _poll_failures: reactive[int] = reactive(0)

    async def _poll_router_info(self) -> None:
        """Poll router every 5s for model changes and real ctx metrics."""
        try:
            client = self.agent.providers.get(self.active_provider)
            info = await client.get_router_info()
            if info.get("model") and info["model"] != client.model:
                client.model = info["model"]
            if info.get("ctx_size"):
                self.agent.update_context_limit(info["ctx_size"])
            activity = self.query_one(ActivityIndicator)
            activity.set_router_info(
                ctx_size=info.get("ctx_size", 0),
                prompt_tokens=info.get("prompt_tokens", 0),
            )
            activity._refresh()
            self._poll_failures = 0
        except Exception as exc:
            self._poll_failures += 1
            logger.debug("Router poll failed (%d): %s", self._poll_failures, exc)
            if self._poll_failures == 3:
                activity = self.query_one(ActivityIndicator)
                activity.set_status("error")
                self._add_system_message(f"Router unreachable ({self._poll_failures} consecutive failures)")

    def watch_theme(self, theme_name: str) -> None:
        _save_theme(theme_name)
        try:
            self.query_one(ActivityIndicator)._refresh()
        except Exception:
            pass
        try:
            c = self._get_theme_colors()
            self.query_one("#banner-panel", Static).update(Panel(
                Text.from_markup(self._render_banner()),
                border_style=c["accent"],
                padding=(1, 2),
                expand=False,
            ))
        except Exception:
            pass

    def action_change_theme(self) -> None:
        current = self.theme
        try:
            idx = ALL_THEMES.index(current)
            next_idx = (idx + 1) % len(ALL_THEMES)
        except ValueError:
            next_idx = 0
        self.theme = ALL_THEMES[next_idx]
        self._add_system_message(f"Theme: {self.theme}")

    def _provider_name(self) -> str:
        try:
            client = self.agent.providers.get(self.active_provider)
            url = client.base_url
        except Exception:
            url = self.config.provider.base_url
        if "z.ai" in url:
            return "Z.AI"
        if ":11434" in url:
            return "Ollama"
        if ":8080" in url:
            return "Llama"
        if "localhost" in url or "127.0.0.1" in url:
            return "Local"
        if "openrouter" in url:
            return "OpenRouter"
        if "minimax" in url:
            return "MiniMax"
        return url.split("//")[1].split("/")[0] if "//" in url else url

    def _add_system_message(self, text: str):
        chat = self.query_one("#chat-area", VerticalScroll)
        chat.mount(ChatMessage("system", text))
        chat.scroll_end(animate=False)

    def _add_rich_message(self, rich_content):
        chat = self.query_one("#chat-area", VerticalScroll)
        chat.mount(Static(rich_content))
        chat.scroll_end(animate=False)

    def _add_message(self, role: str, content: str):
        chat = self.query_one("#chat-area", VerticalScroll)
        chat.mount(ChatMessage(role, content))
        chat.scroll_end(animate=False)
        if role in ("user", "assistant"):
            self.msg_count += 1

    def _start_spinner(self):
        self.query_one(ActivityIndicator).set_status("thinking")
        self._spinner_timer = self.set_interval(0.1, self._tick_spinner)

    def _stop_spinner(self):
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None
        self.query_one(ActivityIndicator).set_status("ready")

    def _tick_spinner(self):
        pass  # ActivityIndicator handles its own refresh

    def _count_tokens(self) -> tuple[int, int]:
        tokens_in = 0
        tokens_out = 0
        for m in self.agent.messages:
            if m.content:
                t = Agent.estimate_tokens(m.content)
                if m.role == "user":
                    tokens_in += t
                elif m.role == "assistant":
                    tokens_out += t
                elif m.role == "tool":
                    tokens_in += t
        return tokens_in, tokens_out

    def on_prompt_text_area_submitted(self, event: PromptTextArea.Submitted) -> None:
        self._submit_prompt(event.text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-button":
            self._submit_prompt(self.query_one("#input-field", TextArea).text)

    def _submit_prompt(self, raw_text: str) -> None:
        if self.is_processing:
            return
        text = (raw_text or "").strip()
        self.query_one("#input-field", TextArea).text = ""
        # Skill capture mode: accumulate lines until empty line
        if getattr(self, "_skill_capturing", False):
            if not text:
                # Empty line → finalize skill
                self._finalize_skill_capture()
            else:
                self._skill_save_lines.append(text)
            return
        if not text:
            return
        self._history.append(text)
        self._history_pos = len(self._history)
        if text.startswith("/"):
            self._handle_command(text)
            return
        self._add_message("user", text)
        self.is_processing = True
        self._start_spinner()
        self._process_message(text)

    def _handle_command(self, cmd: str):
        cmd_raw = cmd
        cmd = cmd.lower().strip()
        if cmd in ("/quit", "/exit", "/q"):
            self.exit()
        elif cmd == "/help":
            self._show_help()
        elif cmd == "/reset":
            self.agent.reset()
            self._add_system_message("Conversation reset.")
        elif cmd == "/clear":
            chat = self.query_one("#chat-area", VerticalScroll)
            chat.remove_children()
            self._add_system_message("Screen cleared.")
        elif cmd in ("/model", "/provider"):
            self._show_model_info()
        elif cmd == "/tools":
            self._show_tools()
        elif cmd == "/skills":
            self._show_skills()
        elif cmd.startswith("/skills save "):
            parts = cmd_raw[13:].strip().split(maxsplit=1)
            if not parts or not parts[0]:
                self._add_system_message("Usage: /skills save <name> [description]")
                return
            name = parts[0]
            description = parts[1] if len(parts) > 1 else ""
            self._skill_save_name = name
            self._skill_save_desc = description
            self._skill_save_lines: list[str] = []
            self._skill_capturing = True
            self._add_system_message(f"Writing skill '{name}' — type content (empty line to finish):")
        elif cmd.startswith("/skills show "):
            name = cmd_raw[13:].strip()
            skill = self.agent.skills.get(name)
            if skill:
                from rich.panel import Panel
                chat = self.query_one("#chat-area", VerticalScroll)
                chat.mount(Static(Panel(skill.instructions, title=f"Skill: {name}", border_style="cyan")))
                chat.scroll_end(animate=False)
            else:
                self._add_system_message(f"Skill not found: {name}")
        elif cmd.startswith("/skills verify "):
            name = cmd_raw[15:].strip()
            if self.agent.skills.verify_skill(name):
                self._add_system_message(f"Skill verified: {name}")
            else:
                self._add_system_message(f"Skill not found: {name}")
        elif cmd == "/sessions":
            self._show_sessions()
        elif cmd.startswith("/load "):
            sid = cmd_raw[6:].strip()
            self._load_session(sid)
        elif cmd == "/new":
            self._new_session()
        elif cmd == "/history":
            lines = self._history[-20:]
            self._add_system_message(
                "\n".join(f"  {i+1}. {h}" for i, h in enumerate(lines))
                or "No history."
            )
        elif cmd == "/safe":
            self.action_toggle_safe_mode()
        elif cmd == "/cwd":
            self._add_system_message(f"CWD: {os.getcwd()}")
        elif cmd == "/context":
            self._regenerate_context()
        elif cmd == "/models":
            self._show_models()
        elif cmd.lower().startswith("/use "):
            model_name = cmd_raw[5:].strip()
            self._use_model(model_name)
        else:
            self._add_system_message(f"Unknown command: {cmd_raw}  |  /help for list")

    def _regenerate_context(self):
        from bytia_kode.context import context_path, generate_context, CONTEXTS_DIR
        CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
        path = context_path(os.getcwd())
        content = generate_context(Path(os.getcwd()))
        path.write_text(content, encoding="utf-8")
        self._add_system_message(f"Context regenerated: {path.name}")

    def _show_help(self):
        table = Table(title="BytIA KODE Commands", box=box.SIMPLE_HEAVY,
                      show_lines=False, padding=(0, 1), collapse_padding=True)
        table.add_column("Command", style="bold cyan", min_width=12)
        table.add_column("Description", min_width=20)
        table.add_column("Key", style="dim", min_width=8)
        for cmd, desc, key in [
            ("/help", "Show this help", ""),
            ("/quit", "Exit", "Ctrl+Q"),
            ("/reset", "Reset conversation", "Ctrl+R"),
            ("/new", "New session", ""),
            ("/sessions", "List saved sessions", ""),
            ("/load <id>", "Load session", ""),
            ("/clear", "Clear screen", "Ctrl+L"),
            ("/model", "Show model info", "Ctrl+M"),
            ("/tools", "List tools", "Ctrl+T"),
            ("/skills", "List skills", ""),
            ("/skills save <name>", "Create skill", ""),
            ("/skills show <name>", "Show skill content", ""),
            ("/skills verify <name>", "Mark skill verified", ""),
            ("/safe", "Toggle safe mode", "Ctrl+E"),
            ("", "Toggle reasoning view", "Ctrl+D"),
            ("/models", "List local models", ""),
            ("/use <model>", "Select local model", ""),
            ("/history", "Show history", ""),
            ("/cwd", "Show current directory", ""),
            ("/context", "Regenerate workspace context", ""),
            ("", "Copy last code block", "Ctrl+X"),
            ("", "Copy last full response", "Ctrl+Shift+C"),
        ]:
            table.add_row(cmd, desc, key)
        chat = self.query_one("#chat-area", VerticalScroll)
        chat.mount(Static(table))
        chat.scroll_end(animate=False)

    def _show_model_info(self):
        table = Table(title="Providers", box=box.SIMPLE_HEAVY,
                      padding=(0, 1), collapse_padding=True)
        table.add_column("Type", style="bold", min_width=10)
        table.add_column("URL", style="cyan", min_width=30)
        table.add_column("Model", style="green")
        table.add_row("Primary", self.config.provider.base_url, self.config.provider.model)
        if self.config.provider.fallback_url:
            table.add_row("Fallback", self.config.provider.fallback_url, self.config.provider.fallback_model)
        if self.config.provider.local_url:
            table.add_row("Local", self.config.provider.local_url, self.config.provider.local_model or "-")
        chat = self.query_one("#chat-area", VerticalScroll)
        chat.mount(Static(table))
        chat.scroll_end(animate=False)

    def _show_tools(self):
        tools = self.agent.tools.list_tools()
        self._add_system_message(f"Tools: {', '.join(tools)}")

    def _show_sessions(self):
        sessions = self.agent.list_sessions()
        if not sessions:
            self._add_system_message("No saved sessions.")
            return
        table = Table(title="Sessions", box=box.SIMPLE_HEAVY,
                      padding=(0, 1), collapse_padding=True)
        table.add_column("ID", style="bold cyan", min_width=14)
        table.add_column("Source", min_width=8)
        table.add_column("Title", min_width=20)
        table.add_column("Msgs", style="dim", min_width=4)
        table.add_column("Updated", style="dim", min_width=16)
        for s in sessions[:15]:
            table.add_row(
                s.get("session_id", "?"),
                s.get("source", "?"),
                (s.get("title", "") or "Untitled")[:40],
                str(s.get("message_count", 0)),
                (s.get("updated_at", "") or "")[:16],
            )
        chat = self.query_one("#chat-area", VerticalScroll)
        chat.mount(Static(table))
        chat.scroll_end(animate=False)
        self._add_system_message("Use /load <session_id> to switch.")

    def _load_session(self, session_id: str):
        if not session_id:
            self._add_system_message("Usage: /load <session_id>")
            return
        if self.agent.load_session_by_id(session_id):
            self._add_system_message(f"Session loaded: {session_id}")
            self.query_one(ActivityIndicator)._refresh()
        else:
            self._add_system_message(f"Session not found: {session_id}")

    def _new_session(self):
        self.agent.reset()
        self.agent.set_session(source="tui")
        self._add_system_message("New session started. Auto-save enabled.")

    def _show_skills(self):
        names = self.agent.skills.list_skill_names()
        if names:
            for name in names:
                skill = self.agent.skills.get(name)
                verified = " [verified]" if skill and skill.verified else ""
                desc = f": {skill.description}" if skill and skill.description else ""
                self._add_system_message(f"  {name}{verified}{desc}")
        else:
            self._add_system_message("No skills saved. Use /skills save <name> to create one.")

    def _finalize_skill_capture(self):
        content = "\n".join(self._skill_save_lines)
        name = self._skill_save_name or ""
        description = self._skill_save_desc or ""
        self._skill_capturing = False
        try:
            path = self.agent.skills.save_skill(name, content, description)
            self._add_system_message(f"Skill saved: {path}")
        except Exception as e:
            self._add_system_message(f"Error saving skill: {e}")
        self._skill_save_name = None
        self._skill_save_desc = None
        self._skill_save_lines = []

    def _provider_display_name(self, provider: str) -> str:
        names = {"primary": "Primary", "fallback": "Fallback", "local": "Local"}
        return names.get(provider, provider)

    def action_switch_provider(self) -> None:
        available = self.agent.providers.list_available()
        try:
            idx = available.index(self.active_provider)
            next_idx = (idx + 1) % len(available)
        except ValueError:
            next_idx = 0
        self.active_provider = available[next_idx]
        provider_client = self.agent.providers.get(self.active_provider)
        name = self._provider_display_name(self.active_provider)
        self._add_system_message(f"Switched to: {name} ({provider_client.model})")

    def _use_model(self, model_name: str):
        if not model_name:
            return
        self.agent.providers.set_model(self.active_provider, model_name)
        self._add_system_message(f"Model set to: {model_name}")

    @work(exclusive=True)
    async def _show_models(self):
        provider = self._provider_display_name(self.active_provider)
        self._add_system_message(f"Fetching models from {provider}...")
        try:
            client = self.agent.providers.get(self.active_provider)
            models = await client.list_models()
        except Exception as e:
            self._add_system_message(f"Error: {e}")
            return
        if not models:
            self._add_system_message(f"No models found on {provider}. Try F3 to switch to Local (Ollama).")
            return
        table = Table(title=f"Models ({provider})",
                      box=box.SIMPLE_HEAVY, padding=(0, 1), collapse_padding=True)
        table.add_column("#", style="dim", min_width=3)
        table.add_column("Model", style="cyan")
        for i, m in enumerate(models, 1):
            table.add_row(str(i), m)
        chat = self.query_one("#chat-area", VerticalScroll)
        chat.mount(Static(table))
        chat.scroll_end(animate=False)
        self._add_system_message("Use /use <model_name> to select.")

    @work(exclusive=True)
    async def _process_message(self, text: str):
        try:
            response_text = ""
            reasoning_text = ""
            thinking_block: ThinkingBlock | None = None
            stream_widget: Static | None = None
            chat = self.query_one("#chat-area", VerticalScroll)
            async for chunk in self.agent.chat(text, provider=self.active_provider):
                if isinstance(chunk, tuple) and chunk[0] == "reasoning":
                    reasoning_text += chunk[1]
                    if thinking_block is None:
                        thinking_block = ThinkingBlock("")
                        await chat.mount(thinking_block)
                    thinking_block.append(chunk[1])
                    chat.scroll_end(animate=False)
                elif isinstance(chunk, str):
                    response_text += chunk
                    if stream_widget is None:
                        stream_widget = Static("", id="streaming-output")
                        await chat.mount(stream_widget)
                    stream_widget.update(Markdown(response_text))
                    chat.scroll_end(animate=False)
                elif isinstance(chunk, tuple) and chunk[0] == "error":
                    if stream_widget and stream_widget.is_mounted:
                        stream_widget.remove()
                    self._add_message("error", chunk[1])

            # Finalize: remove streaming widget, add formatted message
            if stream_widget and stream_widget.is_mounted:
                stream_widget.remove()
            if response_text:
                self._add_message("assistant", response_text)
            chat.scroll_end(animate=False)

        except Exception as e:
            logger.error(f"Chat error: {e}")
            self._add_message("error", str(e))
        finally:
            self._stop_spinner()
            self.is_processing = False

    def action_show_command_menu(self) -> None:
        def on_dismiss(action: str | None):
            if action:
                handler = getattr(self, f"action_{action}", None)
                if handler:
                    handler()
        self.push_screen(CommandMenuScreen(), on_dismiss)

    def action_reset_conversation(self):
        self.agent.reset()
        self._add_system_message("Conversation reset.")

    def action_clear_screen(self):
        chat = self.query_one("#chat-area", VerticalScroll)
        chat.remove_children()
        self._add_system_message("Screen cleared.")

    def action_show_model(self):
        self._show_model_info()

    def action_show_tools(self):
        self._show_tools()

    def action_show_skills(self):
        self._show_skills()

    def action_toggle_safe_mode(self):
        self.safe_mode = not self.safe_mode
        if self.safe_mode:
            self._add_rich_message(Text("Safe mode: ON", style="bold green"))
        else:
            self._add_rich_message(Text("Safe mode: OFF", style="bold yellow"))

    def action_toggle_reasoning(self):
        blocks = self.query(ThinkingBlock)
        if blocks:
            blocks.last().toggle()

    def action_new_session(self):
        self._new_session()

    def action_list_sessions(self):
        self._show_sessions()

    def action_load_session(self):
        self._prompt_session_id()

    def action_select_model(self):
        self._prompt_model_name()

    def action_show_history(self):
        lines = self._history[-20:]
        self._add_system_message(
            "\n".join(f"  {i+1}. {h}" for i, h in enumerate(lines))
            or "No history."
        )

    def _prompt_session_id(self) -> None:
        def on_dismiss(value: str | None):
            if value:
                self._load_session(value)
        self.push_screen(InputScreen("Session ID:", "tui_abc12345"), on_dismiss)

    def _prompt_model_name(self) -> None:
        def on_dismiss(value: str | None):
            if value:
                self._use_model(value)
        self.push_screen(InputScreen("Model name:", "gemma-4-26b"), on_dismiss)

    def action_copy_last_code(self):
        if not self.agent.messages:
            return
        last_msg = None
        for msg in reversed(self.agent.messages):
            if msg.role in ("assistant", "tool"):
                last_msg = msg
                break
        if last_msg and last_msg.content:
            import re
            code_blocks = re.findall(r"`[a-zA-Z0-9]*\
(.*?)\
`", last_msg.content, re.DOTALL)
            if code_blocks:
                self.copy_to_clipboard(code_blocks[-1].strip())
                self.notify("Code copied to clipboard!")
            else:
                self.copy_to_clipboard(last_msg.content.strip())
                self.notify("Message copied to clipboard!")

    def action_copy_last_response(self):
        if not self.agent.messages:
            return
        last_msg = None
        for msg in reversed(self.agent.messages):
            if msg.role == "assistant" and msg.content:
                last_msg = msg
                break
        if last_msg:
            self.copy_to_clipboard(last_msg.content.strip())
            self.notify("Last response copied to clipboard!")
        else:
            self.notify("No response to copy", severity="warning")

    def action_history_up(self):
        if self._history and self._history_pos > 0:
            self._history_pos -= 1
            self.query_one("#input-field", TextArea).text = self._history[self._history_pos]

    def action_history_down(self):
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            self.query_one("#input-field", TextArea).text = self._history[self._history_pos]
        else:
            self._history_pos = len(self._history)
            self.query_one("#input-field", TextArea).text = ""

    async def on_shutdown(self) -> None:
        self._stop_spinner()
        await self.agent.close()


def run_tui():
    app = BytIAKODEApp()
    app.run()


if __name__ == "__main__":
    run_tui()
