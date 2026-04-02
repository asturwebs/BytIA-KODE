"""CLI interface - simple fallback without Textual."""
from __future__ import annotations

import asyncio
import sys

from rich.console import Console
from rich.markdown import Markdown
from prompt_toolkit import PromptSession

from bytia_kode.config import load_config
from bytia_kode.agent import Agent


console = Console()


async def repl():
    config = load_config()
    agent = Agent(config)

    console.print("\n[bold #7ee787]BytIA KODE[/bold #7ee787] v0.1.0 (simple mode)")
    console.print(f"[dim]Model: {config.provider.model} | Provider: {config.provider.base_url}[/dim]")
    console.print("[dim]/help for commands, /quit to exit[/dim]\n")

    session: PromptSession = PromptSession()

    while True:
        try:
            user_input = await asyncio.to_thread(session.prompt, "kode> ")
        except (EOFError, KeyboardInterrupt):
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input in ("/quit", "/exit", "/q"):
            break
        elif user_input == "/help":
            console.print("[bold]Commands:[/bold] /help /quit /reset /clear /model /tools /skills /provider /memory")
            continue
        elif user_input == "/reset":
            agent.reset()
            console.print("[yellow]Reset.[/yellow]")
            continue
        elif user_input == "/clear":
            console.clear()
            continue
        elif user_input in ("/model", "/provider"):
            console.print(f"[bold]Model:[/bold] {config.provider.model} @ {config.provider.base_url}")
            continue
        elif user_input == "/tools":
            console.print(f"[bold]Tools:[/bold] {', '.join(agent.tools.list_tools())}")
            continue
        elif user_input.startswith("/skills"):
            skills = agent.skills.load_all()
            for n, s in (skills or {}).items():
                console.print(f"  [bold]{n}[/bold]: {s.description}")
            continue
        elif user_input.startswith("/memory"):
            ctx = agent.memory.get_context()
            console.print(Markdown(ctx) if ctx else "[dim]No memories.[/dim]")
            continue

        try:
            full = ""
            async for chunk in agent.chat(user_input):
                full += chunk
            if full:
                console.print()
                console.print(Markdown(full))
                console.print()
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]\n")

    await agent.close()
    console.print("[dim]Bye![/dim]")


def main():
    asyncio.run(repl())


if __name__ == "__main__":
    main()
