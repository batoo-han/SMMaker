# src/modules/telegram/tg_publisher.py

import os
import logging
import io
import asyncio
import re
from typing import Optional

from telegram import Bot, InputFile
from telegram.constants import ParseMode
from telegram.error import TelegramError

from src.core.interfaces import PublisherInterface
from src.core.models import Post
from src.config.settings import settings

logger = logging.getLogger(__name__)


class TelegramPublisher(PublisherInterface):
    """
    Публикатор для Telegram. Публикует сначала картинку, затем текст отдельным сообщением.
    Сохраняет Markdown-разметку (конвертирует **bold** → *bold*).
    Всегда возвращает полноценную ссылку на пост в формате https://t.me/<username>/<message_id>.
    """

    def __init__(self):
        token = os.getenv("TG_TOKEN") or settings.TG_TOKEN
        if not token:
            raise ValueError("TG_TOKEN не задан")
        self.token = token

        raw_chat_id = os.getenv("TG_CHAT_ID") or settings.TG_CHAT_ID
        if not raw_chat_id:
            raise ValueError("TG_CHAT_ID не задан")
        self.chat_id = raw_chat_id

    def _sanitize_markdown(self, text: str) -> str:
        """
        Конвертирует двойные звездочки **текст** → *текст* для корректного Markdown в Telegram.
        """
        return re.sub(r"\*\*(.*?)\*\*", r"*\1*", text, flags=re.DOTALL)

    def publish(self, post: Post) -> Optional[str]:
        """
        Публикует фотографию, затем текст, и возвращает URL текстового сообщения.
        Если не удалось получить username для ссылки – возвращает None.
        """

        if not post.idea or not post.image_bytes:
            logger.error("[telegram] Невозможно опубликовать: текст или изображение отсутствует.")
            return None

        # Конвертируем Markdown
        original_text = post.idea
        sanitized_text = self._sanitize_markdown(original_text)

        async def _publish_async(token: str, chat_id: str, image_data: bytes, text: str) -> Optional[str]:
            bot = Bot(token=token)

            # Получаем username чата (нужно для формирования ссылки)
            try:
                chat = await bot.get_chat(chat_id)
                username = chat.username
                if not username:
                    logger.error(f"[telegram async] У чата нет username (chat_id={chat_id})")
                    return None
            except TelegramError as e:
                logger.error(f"[telegram async] Ошибка при получении информации о чате: {e}")
                return None

            # 1) Отправляем фото
            bio = io.BytesIO(image_data)
            bio.name = "image.jpg"
            input_file = InputFile(bio, filename="image.jpg")

            try:
                logger.debug(f"[telegram async] send_photo: chat_id={chat_id}")
                photo_obj = await bot.send_photo(
                    chat_id=chat_id,
                    photo=input_file,
                    disable_notification=False
                )
                logger.debug(f"[telegram async] Ответ от send_photo: {photo_obj!r}")
            except TelegramError as e:
                logger.error(f"[telegram async] Ошибка при отправке фото: {e}")
                return None

            # 2) Отправляем текст с Markdown
            try:
                logger.debug(
                    "[telegram async] send_message (Markdown): chat_id=%s, первые 50 символов: %s",
                    chat_id, text[:50]
                )
                text_obj = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_notification=False

                )
                logger.debug(f"[telegram async] Ответ от send_message: {text_obj!r}")
            except TelegramError as e:
                logger.error(f"[telegram async] Ошибка при отправке текста: {e}")
                return None

            message_id = getattr(text_obj, "message_id", None)
            if message_id is None:
                logger.error(f"[telegram async] send_message вернул объект без message_id: {text_obj!r}")
                return None

            # 3) Формируем URL по username и message_id
            url = f"https://t.me/{username}/{message_id}"
            logger.info(f"[telegram async] Текстовое сообщение отправлено, URL: {url}")
            return url

        try:
            url = asyncio.run(_publish_async(self.token, self.chat_id, post.image_bytes, sanitized_text))
            return url
        except Exception as e:
            logger.error(f"[telegram] Неожиданная ошибка при публикации: {e}")
            return None
