"""Telegram bot interface for BytIA KODE."""
from __future__ import annotations

import logging
import signal
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bytia_kode import version_label
from bytia_kode.agent import Agent
from bytia_kode.config import AppConfig, load_config
from bytia_kode.session import SessionStore

logger = logging.getLogger(__name__)


def _mask_token(token: str) -> str:
    """Enmascara un token `<bot_id>:<secreto>` para el banner: conserva el
    bot_id y 3+3 caracteres del secreto — reconocible para el operador,
    inútil para quien le eche un ojo a la pantalla."""
    if ":" in token:
        bot_id, secret = token.split(":", 1)
        if len(secret) >= 8:
            return f"{bot_id}:{secret[:3]}…{secret[-3:]}"
    return "***"


class TelegramBot:
    def __init__(self, config: AppConfig):
        self.config = config
        self.session_store = SessionStore(config.data_dir / "sessions.db")
        self._agents: dict[str, Agent] = {}  # chat_id -> Agent
        self._processing: set[str] = set()  # chat_ids currently processing
        builder = Application.builder().token(config.telegram.bot_token)
        if config.telegram.api_base:
            builder = builder.base_url(config.telegram.api_base).base_file_url(
                config.telegram.api_base.rstrip("/") + "/file/bot"
            )
        self.app = builder.build()
        self._setup_handlers()

    def _get_agent(self, chat_id: str) -> Agent:
        """Get or create an Agent for a specific chat_id (session isolation)."""
        if chat_id not in self._agents:
            agent = Agent(self.config)
            # H3 (parcial): same wiring as tui.py — without this callback,
            # /kill never sees the bash subprocess and can't terminate it.
            def _on_subprocess(process, _agent=agent):
                _agent._active_subprocess = process
            agent.on_subprocess.append(_on_subprocess)
            # H4: resume via (source, source_ref) — create_session now mints a
            # deterministic telegram_<chat_id> id, so both paths converge.
            existing = self.session_store.find_session_by_ref("telegram", chat_id)
            if existing and agent.load_session_by_id(existing.session_id):
                logger.info("Loaded existing session for chat %s", chat_id)
            else:
                agent.set_session(source="telegram", source_ref=chat_id)
                logger.info("New agent for chat %s", chat_id)
            self._agents[chat_id] = agent
        return self._agents[chat_id]

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("reset", self._reset))
        self.app.add_handler(CommandHandler("stop", self._stop))
        self.app.add_handler(CommandHandler("kill", self._kill))
        self.app.add_handler(CommandHandler("help", self._help))
        self.app.add_handler(CommandHandler("model", self._model))
        self.app.add_handler(CommandHandler("sessions", self._sessions))
        self.app.add_handler(CommandHandler("context", self._context))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._chat))

    def _is_allowed(self, user_id: int) -> bool:
        allowed = self.config.telegram.allowed_users
        if not allowed:
            return False
        return str(user_id) in allowed

    async def _deny(self, update: Update) -> None:
        if update.message:
            await update.message.reply_text("Not authorized.")

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await self._deny(update)
            return
        await update.message.reply_text(
                f"BytIA KODE v{version_label()}\n"
                f"Model: {self.config.provider.model}\n"
                "Send me a message to start coding!"
        )

    async def _reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await self._deny(update)
            return
        agent = self._get_agent(str(update.effective_user.id))
        agent.reset()
        await update.message.reply_text("Conversation reset.")

    async def _stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await self._deny(update)
            return
        chat_id = str(update.effective_user.id)
        if chat_id in self._processing:
            agent = self._get_agent(chat_id)
            agent.interrupt()
            await update.message.reply_text("Interrupting...")
        else:
            await update.message.reply_text("Nothing to stop.")

    async def _kill(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await self._deny(update)
            return
        chat_id = str(update.effective_user.id)
        if chat_id in self._processing:
            agent = self._get_agent(chat_id)
            await agent.kill()
            self._processing.discard(chat_id)
            await update.message.reply_text("Killed. Session preserved.")
        else:
            await update.message.reply_text("Nothing to kill.")

    async def _help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await self._deny(update)
            return
        await update.message.reply_text(
            "/start - Info\n"
            "/reset - Clear conversation\n"
            "/model - Current model\n"
            "/help - This message\n"
            "/sessions - List available sessions\n"
            "/context - Regenerate workspace context\n\n"
            "Just send a message to chat!"
        )

    async def _model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await self._deny(update)
            return
        await update.message.reply_text(
            f"Provider: {self.config.provider.base_url}\n"
            f"Model: {self.config.provider.model}"
        )

    async def _sessions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await self._deny(update)
            return
        sessions = self._get_agent(str(update.effective_user.id)).list_sessions()
        if not sessions:
            await update.message.reply_text("No saved sessions.")
            return
        text = "Recent sessions:\n\n"
        for s in sessions[:10]:
            source = s.get("source", "?")
            title = s.get("title", "Untitled")[:50]
            count = s.get("message_count", 0)
            updated = s.get("updated_at", "")[:16]
            sid = s.get("session_id", "")
            text += f"  {sid} ({source}) {title} - {count} msgs ({updated})\n"
        await update.message.reply_text(text)

    async def _context(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await self._deny(update)
            return
        from bytia_kode.context import CONTEXTS_DIR, context_path, generate_context

        CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
        path = context_path(".")
        content = generate_context(Path.cwd())
        path.write_text(content, encoding="utf-8")
        await update.message.reply_text(f"Context regenerated: {path.name}")

    async def _chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await self._deny(update)
            return

        user_text = update.message.text
        logger.info("TG [%s]", update.effective_user.id)
        chat_id = str(update.effective_user.id)

        if chat_id in self._processing:
            await update.message.reply_text("Still processing previous message. Use /stop to interrupt.")
            return

        self._processing.add(chat_id)
        try:
            response_text = ""
            agent = self._get_agent(chat_id)
            async for chunk in agent.chat(user_text, provider="primary"):
                if isinstance(chunk, tuple) and chunk[0] == "system":
                    await update.message.reply_text(f"ℹ️ {chunk[1]}")
                    continue
                if isinstance(chunk, tuple) and chunk[0] == "error":
                    await update.message.reply_text(f"⚠️ {chunk[1]}")
                    return
                if isinstance(chunk, tuple):
                    continue
                response_text += chunk

            if len(response_text) > 4000:
                for i in range(0, len(response_text), 4000):
                    await update.message.reply_text(response_text[i:i + 4000])
            else:
                await update.message.reply_text(response_text or "(no response)")
        except Exception as exc:
            logger.error("Chat error: %s", exc)
            await update.message.reply_text("Error interno en el procesamiento")
        finally:
            self._processing.discard(chat_id)

    def run(self):
        """Arranca el polling con banner visible y apagado limpio (AST-32).

        Antes: el arranque se anunciaba con `logger.info` — sin handler, INFO
        no llegaba a ningún sitio y el bot parecía muerto con el polling vivo.
        El doble Ctrl+C interrumpía el teardown de PTB (SystemExit dentro del
        `finally`) y escupía el traceback "Event loop is closed".

        Ahora: banner REAL por stdout antes del polling, y las señales las
        gestionamos nosotros con `stop_signals=None` — un handler idempotente
        que en la fase de polling llama `Application.stop_running()` (parada
        graceful documentada de PTB) e IGNORA señales adicionales: el teardown
        corre de principio a fin sin carrera posible. Antes de entrar en
        `run_forever` (bootstrap) se conserva la semántica por defecto
        (KeyboardInterrupt) porque aún no hay nada que desmontar.
        """
        allowed = self.config.telegram.allowed_users
        print(
            f"Bot de Telegram activo · token {_mask_token(self.config.telegram.bot_token)} · "
            f"usuarios permitidos: {len(allowed)} · esperando mensajes (Ctrl+C para parar)",
            flush=True,
        )
        if not allowed:
            print(
                "⚠ TELEGRAM_ALLOWED_USERS vacío: el bot deniega todos los mensajes "
                "(fail-secure).",
                flush=True,
            )

        stop_requested = False

        def _handle_stop(signum, frame):
            nonlocal stop_requested
            if stop_requested:
                return  # 2º Ctrl+C durante el apagado: ya está corriendo, ignorar
            stop_requested = True
            if self.app.running:
                self.app.stop_running()
            else:
                raise KeyboardInterrupt  # bootstrap: semántica por defecto

        previous = {}
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, _handle_stop)
        try:
            self.app.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)
        except (KeyboardInterrupt, SystemExit):
            pass  # parada por señal — el teardown de PTB ya corrió en su `finally`
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        print("Bot detenido.", flush=True)


def main():
    import sys

    config = load_config()
    if not config.telegram.bot_token:
        print("Error: TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    bot = TelegramBot(config)
    bot.run()


if __name__ == "__main__":
    main()
