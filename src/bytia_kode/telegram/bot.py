"""Telegram bot interface for BytIA KODE."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bytia_kode import __version__
from bytia_kode.agent import Agent
from bytia_kode.config import AppConfig, load_config

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, config: AppConfig):
        self.config = config
        self.agent = Agent(config)
        self.app = Application.builder().token(config.telegram.bot_token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("reset", self._reset))
        self.app.add_handler(CommandHandler("help", self._help))
        self.app.add_handler(CommandHandler("model", self._model))
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
        self.agent.reset()
        await update.message.reply_text("Conversation reset.")

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
            "/help - This message\n\n"
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

    async def _chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await self._deny(update)
            return

        user_text = update.message.text
        logger.info("TG [%s]", update.effective_user.id)

        try:
            response_text = ""
            async for chunk in self.agent.chat(user_text):
                response_text += chunk

            if len(response_text) > 4000:
                for i in range(0, len(response_text), 4000):
                    await update.message.reply_text(response_text[i:i + 4000])
            else:
                await update.message.reply_text(response_text or "(no response)")
        except Exception as exc:
            logger.error("Chat error: %s", exc)
            await update.message.reply_text("Error interno en el procesamiento")

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
