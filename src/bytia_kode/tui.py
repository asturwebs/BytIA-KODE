"""BytIA KODE TUI - Theme-aware CLI interface with Textual. v4"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual import events
from textual.binding import Binding
from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Header, Footer, Static, TextArea, Button
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

SPINNER_FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

BANNER_TEMPLATE = """[bold {accent}]██████╗      ██╗  ██╗ ██████╗ ██████╗ ███████╗    [dim italic]by AsturWebs & BytIA[/]
[bold {accent}]██╔══██╗      ██║ ██╔╝██╔═══██╗██╔══██╗██╔════╝[/]
[bold {accent}]██████╔╝      █████╔╝ ██║   ██║██║  ██║█████╗  [/]
[bold {accent}]██╔══██╗      ██╔═██╗ ██║   ██║██║  ██║██╔══╝  [/]
[bold {accent}]██████╔╝      ██║  ██╗╚██████╔╝██████╔╝███████╗[/]
[bold {accent}]╚═════╝       ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝[/]"""

_THEME_FILE = Path.home() / ".bytia-kode" / "theme.json"
DARK_THEMES = ["gruvbox", "monokai", "nord", "dracula", "catppuccin-mocha", "tokyo-night",
                   "catppuccin-latte", "solarized-light", "rose-pine-dawn"]
DEFAULT_THEME = "gruvbox"


def _load_theme() -> str:
    try:
        if _THEME_FILE.exists():
            t = json.loads(_THEME_FILE.read_text()).get("theme", DEFAULT_THEME)
            return t if t in DARK_THEMES else DEFAULT_THEME
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
            content = self.msg_content[:2000]
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
            return


class StatusBar(Static):
    def __init__(self, **kwargs):
        self._st_cwd = os.getcwd()
        self._st_model = ""
        self._st_provider = ""
        self._st_processing = False
        self._st_spinner_idx = 0
        self._st_tokens_in = 0
        self._st_tokens_out = 0
        super().__init__("[bold green]Ready[/]", id="status-bar", **kwargs)

    def update_status(self, model: str = "", provider: str = "",
                      processing: bool = False, tokens_in: int = 0, tokens_out: int = 0):
        if model:
            self._st_model = model
        if provider:
            self._st_provider = provider
        self._st_processing = processing
        if tokens_in:
            self._st_tokens_in = tokens_in
        if tokens_out:
            self._st_tokens_out = tokens_out
        self._st_cwd = os.getcwd()
        self._refresh_display()

    def tick_spinner(self):
        self._st_spinner_idx = (self._st_spinner_idx + 1) % len(SPINNER_FRAMES)
        self._refresh_display()

    def _refresh_display(self):
        parts = []
        if self._st_processing:
            spinner = SPINNER_FRAMES[self._st_spinner_idx]
            parts.append(f"[bold yellow]{spinner} Thinking...[/]")
        else:
            parts.append("[bold green]Ready[/]")

        parts.append(f"[cyan]{self._st_model}[/]")
        parts.append(f"[dim]{self._st_provider}[/]")

        if self._st_tokens_in or self._st_tokens_out:
            parts.append(f"[dim]in:{self._st_tokens_in} out:{self._st_tokens_out}[/]")

        cwd = os.path.expanduser(self._st_cwd)
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        if len(cwd) > 40:
            cwd = "..." + cwd[-37:]
        parts.append(f"[dim]{cwd}[/]")

        self.update("  |  ".join(parts))


class BytIAKODEApp(App):
    TITLE = "BytIA KODE"
    SUB_TITLE = "Agentic Coding Assistant"
    CSS_PATH = "tui.css"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+r", "reset_conversation", "Reset", show=True),
        Binding("ctrl+l", "clear_screen", "Clear", show=True),
        Binding("ctrl+m", "show_model", "Model", show=True),
        Binding("ctrl+t", "show_tools", "Tools", show=True),
        Binding("ctrl+s", "show_skills", "Skills", show=True),
        Binding("ctrl+e", "toggle_safe_mode", "Safe", show=True),
        Binding("ctrl+x", "copy_last_code", "Copy Code", show=True),
        Binding("f2", "change_theme", "Theme", show=True, priority=True),
        Binding("f3", "switch_provider", "Provider", show=True, priority=True),
        Binding("up", "history_up", "", show=False),
        Binding("down", "history_down", "", show=False),
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
        self._history: list[str] = []
        self._history_pos = -1
        self._spinner_timer = None

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
        yield StatusBar()
        with Horizontal(id="input-area"):
            yield PromptTextArea(id="input-field", show_line_numbers=False, language="markdown")
            yield Button("➜", id="send-button")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#input-field", TextArea).focus()

        status = self.query_one(StatusBar)
        status.update_status(
            model=self.config.provider.model,
            provider=self._provider_name(),
        )

        chat = self.query_one("#chat-area", VerticalScroll)
        c = self._get_theme_colors()
        chat.mount(Static(Panel(
            Text.from_markup(self._render_banner()),
            border_style=c["accent"],
            padding=(1, 2),
            expand=False,
        ), id="banner-panel"))

        chat.mount(Static(Panel(
            Text.from_markup(
                f"[cyan]Model:[/] {self.config.provider.model} | "
                f"[cyan]Provider:[/] {self._provider_name()} | "
                f"[cyan]Theme:[/] {self.theme} | "
                f"[cyan]Version:[/] {__version__}\n"
                "[dim italic]Tip: Hold Shift + Drag Mouse to select text. Ctrl+X copies last code.[/]"
            ),
            title="[dim]Session Info[/]",
            border_style="cyan",
            padding=(0, 1),
            expand=False,
        ), id="info-panel"))

        chat.mount(Static(""))
        chat.scroll_end(animate=False)

        if self.safe_mode:
            t = Text("Safe mode ON (dangerous cmds require confirmation)")
            t.stylize("dim italic")
            chat.mount(Static(t))

    def watch_theme(self, theme_name: str) -> None:
        _save_theme(theme_name)
        c = self._get_theme_colors()
        try:
            self.query_one("#banner-panel", Static).update(Panel(
                Text.from_markup(self._render_banner()),
                border_style=c["accent"],
                padding=(1, 2),
                expand=False,
            ))
        except Exception:
            pass
        try:
            info = self.query_one("#info-panel", Static)
            info.update(Panel(
                Text.from_markup(
                    f"[{c['secondary']}]Model:[/] {self.config.provider.model} | "
                    f"[{c['secondary']}]Provider:[/] {self._provider_name()} | "
                    f"[{c['secondary']}]Theme:[/] {theme_name} | "
                    f"[{c['secondary']}]Version:[/] {__version__}\n"
                    "[dim italic]Tip: Hold Shift + Drag Mouse to select text. Ctrl+X copies last code.[/]"
                ),
                title="[dim]Session Info[/]",
                border_style=c["secondary"],
                padding=(0, 1),
                expand=False,
            ))
        except Exception:
            pass

    def action_change_theme(self) -> None:
        current = self.theme
        try:
            idx = DARK_THEMES.index(current)
            next_idx = (idx + 1) % len(DARK_THEMES)
        except ValueError:
            next_idx = 0
        self.theme = DARK_THEMES[next_idx]
        self._add_system_message(f"Theme: {self.theme}")

    def _provider_name(self) -> str:
        url = self.config.provider.base_url
        if "z.ai" in url:
            return "Z.AI"
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
        status = self.query_one(StatusBar)
        status.update_status(processing=True)
        self._spinner_timer = self.set_interval(0.1, self._tick_spinner)

    def _stop_spinner(self):
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None
        status = self.query_one(StatusBar)
        status.update_status(processing=False)

    def _tick_spinner(self):
        self.query_one(StatusBar).tick_spinner()

    def _count_tokens(self) -> tuple[int, int]:
        tokens_in = 0
        tokens_out = 0
        for m in self.agent.messages:
            if m.content:
                chars = len(m.content)
                if m.role == "user":
                    tokens_in += chars // 4
                elif m.role == "assistant":
                    tokens_out += chars // 4
                elif m.role == "tool":
                    tokens_in += chars // 4
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
        if not text:
            return
        self.query_one("#input-field", TextArea).text = ""
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
        elif cmd == "/models":
            self._show_models()
        elif cmd.lower().startswith("/use "):
            model_name = cmd_raw[5:].strip()
            self._use_model(model_name)
        else:
            self._add_system_message(f"Unknown command: {cmd_raw}  |  /help for list")

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
            ("/clear", "Clear screen", "Ctrl+L"),
            ("/model", "Show model info", "Ctrl+M"),
            ("/tools", "List tools", "Ctrl+T"),
            ("/skills", "List skills", "Ctrl+S"),
            ("/safe", "Toggle safe mode", "Ctrl+E"),
            ("/models", "List local models", ""),
            ("/use <model>", "Select local model", ""),
            ("/history", "Show history", ""),
            ("/cwd", "Show current directory", ""),
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

    def _show_skills(self):
        skills = self.agent.skills.load_all()
        if skills:
            for name, skill in skills.items():
                self._add_system_message(f"  {name}: {skill.description or '(no desc)'}")
        else:
            self._add_system_message("No skills loaded.")

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
        status = self.query_one(StatusBar)
        status.update_status(
            model=provider_client.model,
            provider=f"{name} [{self._provider_name()}]",
        )

    def _use_model(self, model_name: str):
        if not model_name:
            return
        self.agent.providers.set_model(self.active_provider, model_name)
        self._add_system_message(f"Model set to: {model_name}")
        status = self.query_one(StatusBar)
        status.update_status(
            model=model_name,
            provider=self._provider_display_name(self.active_provider),
        )

    @work(exclusive=True)
    async def _show_models(self):
        self._add_system_message("Fetching models...")
        try:
            client = self.agent.providers.get(self.active_provider)
            models = await client.list_models()
        except Exception as e:
            self._add_system_message(f"Error: {e}")
            return
        if not models:
            self._add_system_message("No models found. Is Ollama/llama running?")
            return
        table = Table(title=f"Models ({self._provider_display_name(self.active_provider)})",
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

            async for chunk in self.agent.chat(text, provider=self.active_provider):
                response_text += chunk

            tokens_in, tokens_out = self._count_tokens()

            if response_text:
                self._add_message("assistant", response_text)

            status = self.query_one(StatusBar)
            status.update_status(
                model=self.config.provider.model,
                provider=self._provider_name(),
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )

        except Exception as e:
            logger.error(f"Chat error: {e}")
            self._add_message("error", str(e))
        finally:
            self._stop_spinner()
            self.is_processing = False

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
