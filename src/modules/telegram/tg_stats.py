"""
tg_stats.py

Реализация StatsInterface для Telegram: сбор статистики по публикации.
"""
import logging

from src.core.interfaces import StatsInterface

logger = logging.getLogger(__name__)


class TelegramStats(StatsInterface):
    """
    Сбор статистики по постам Telegram.
    На данный момент возвращает пустой словарь (API ограничен).
    """

    def __init__(self):
        # В будущем можно добавить методы получения статистики через Bot API или Analytics
        pass

    def collect(self, post_url: str):
        """
        Сбор статистики не поддерживается Telegram Bot API.

        Args:
            post_url (str): URL опубликованного сообщения

        Returns:
            dict: пустой или базовый словарь
        """
        logger.warning(f"Сбор статистики в Telegram не реализован (URL: {post_url})")
        return {}
