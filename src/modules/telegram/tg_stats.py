"""Telegram statistics collector."""

import logging
import os
from typing import Dict, Optional
from urllib.parse import urlparse

import requests

from src.config.settings import settings
from src.core.interfaces import StatsInterface

logger = logging.getLogger(__name__)


class TelegramStats(StatsInterface):
    """Сбор статистики по постам Telegram через Bot API."""

    API_METHOD = "getMessageStatistics"

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or os.getenv("TG_TOKEN") or settings.TG_TOKEN
        if not self.token:
            raise ValueError("TG_TOKEN не задан")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def _parse_url(self, url: str) -> Optional[tuple[str, int]]:
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        if len(parts) < 2:
            return None
        try:
            return parts[-2], int(parts[-1])
        except ValueError:
            return None

    def collect(self, post_url: str) -> Dict:
        """Возвращает число просмотров и пересылок сообщения."""

        parsed = self._parse_url(post_url)
        if not parsed:
            logger.error(f"[TelegramStats] Некорректный URL: {post_url}")
            return {}

        username, message_id = parsed
        url = f"{self.base_url}/{self.API_METHOD}"
        params = {"chat_id": f"@{username}", "message_id": message_id}

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[TelegramStats] Ошибка запроса: {e}")
            return {}

        if not data.get("ok"):
            logger.error(
                f"[TelegramStats] API error: {data.get('description', 'unknown')}"
            )
            return {}

        result = data.get("result", {})
        # В некоторых версиях API статистика находится в подполе interaction_counters
        counters = result.get("interaction_counters", result)
        views = counters.get("views") or counters.get("view_count", 0)
        forwards = counters.get("forwards") or counters.get("forward_count", 0)
        return {"views": views, "forwards": forwards}
