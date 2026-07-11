import os
import logging
from telegram import Bot
from telegram.ext import Application

logger = logging.getLogger(__name__)

class TelegramService:
    """
    A service class for interacting with the Telegram Bot API.
    """
    def __init__(self):
        self._bot_token = os.getenv("TELEGRAM_BOT_API_KEY", "")
        self._app: Application | None = None

    async def get_bot(self) -> Bot:
        """
        Initialize and return the underlying Telegram Bot instance.
        Uses the Application builder for robust initialization.
        """
        if self._app is None:
            if not self._bot_token:
                raise RuntimeError("TELEGRAM_BOT_API_KEY is not set")
            self._app = Application.builder().token(self._bot_token).build()
            await self._app.initialize()
        return self._app.bot

    async def send_message(self, chat_id: str | int, text: str, parse_mode: str | None = None, **kwargs):
        """
        Helper method to send a text message directly to a specific chat ID.
        
        Args:
            chat_id: The target Telegram chat ID.
            text: The message content to send.
            parse_mode: E.g., "Markdown", "HTML". Defaults to None.
            **kwargs: Any other arguments supported by bot.send_message.
        """
        try:
            bot = await self.get_bot()
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, **kwargs)
        except Exception as e:
            logger.error("Failed to send telegram message to %s: %s", chat_id, e)
            raise e

# Module-level singleton
telegram_service = TelegramService()
