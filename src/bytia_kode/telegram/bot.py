"""Telegram bot interface for BytIA KODE."""
from __future__ import annotations

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bytia_kode import __version__
from bytia_kode.agent import Agent
from bytia_kode.config import AppConfig, load_config
from bytia_kode.session import SessionStore

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, config: AppConfig):
        self.config = config
        self.session_store = SessionStore(config.data_dir / "sessions.db")
        self._agents: dict[str, Agent] = {}  # chat_id -> Agent
        self._processing: set[str] = set()  # chat_ids currently processing
        self.app = Application.builder().token(config.telegram.bot_token).build()
        self._setup_handlers()

    def _get_agent(self, chat_id: str) -> Agent:
        """Get or create an Agent for a specific chat_id (session isolation)."""
        if chat_id not in self._agents:
            session_id = f"telegram_{chat_id}"
            if self.session_store.get_metadata(session_id):
                self._agents[chat_id] = Agent(self.config)
                self._agents[chat_id].load_session_by_id(session_id)
                logger.info("Loaded existing session for chat %s", chat_id)
            else:
                self._agents[chat_id] = Agent(self.config)
                self._agents[chat_id].set_session(source="telegram", source_ref=chat_id)
                logger.info("New agent for chat %s", chat_id)
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
                f"BytIA KODE v{__version__}\n"
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
        logger.info("Starting BytIA KODE Telegram bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


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
