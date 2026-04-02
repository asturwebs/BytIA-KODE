"""Telegram bot interface for BytIA KODE."""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from bytia_kode.config import load_config, AppConfig
from bytia_kode.agent import Agent

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
            return True  # No filter = open to all
        return str(user_id) in allowed

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("Not authorized.")
            return
        await update.message.reply_text(
            "BytIA KODE v0.1.0\n"
            f"Model: {self.config.provider.model}\n"
            "Send me a message to start coding!"
        )

    async def _reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("Not authorized.")
            return
        self.agent.reset()
        await update.message.reply_text("Conversation reset.")

    async def _help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        await update.message.reply_text(
            "/start - Info\n"
            "/reset - Clear conversation\n"
            "/model - Current model\n"
            "/help - This message\n\n"
            "Just send a message to chat!"
        )

    async def _model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        await update.message.reply_text(
            f"Provider: {self.config.provider.base_url}\n"
            f"Model: {self.config.provider.model}"
        )

    async def _chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text or not update.effective_user:
            return
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("Not authorized.")
            return

        user_text = update.message.text
        logger.info(f"TG [{update.effective_user.id}]")

        try:
            response_text = ""
            async for chunk in self.agent.chat(user_text):
                response_text += chunk

            # Telegram has 4096 char limit
            if len(response_text) > 4000:
                for i in range(0, len(response_text), 4000):
                    await update.message.reply_text(response_text[i:i+4000])
            else:
                await update.message.reply_text(response_text or "(no response)")

        except Exception as e:
            logger.error(f"Chat error: {e}")
            await update.message.reply_text(f"Error: {e}")

    def run(self):
        """Start the bot (blocking)."""
        logger.info("Starting BytIA KODE Telegram bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Entry point for telegram bot."""
    import sys
    config = load_config()

    if not config.telegram.bot_token:
        print("Error: TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    bot = TelegramBot(config)

    # Agent needs async, but run_polling is blocking, so we handle it
    bot.run()


if __name__ == "__main__":
    main()
