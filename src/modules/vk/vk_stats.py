# src/modules/vk/vk_stats.py

"""
vk_stats.py

Модуль для получения статистики по постам ВКонтакте. Позволяет:
  - Получить список последних N постов со стены сообщества/пользователя.
  - Получить детальную статистику (лайки, комментарии, репосты, просмотры) для конкретного поста.

Использует VK API версии 5.131.

Настройки:
  - VK_TOKEN    — токен доступа (сообщества или пользователя)
  - VK_OWNER_ID — ID владельца стены (отрицательное для сообществ, положительное для пользователей)
"""

import logging
from typing import List, Dict, Optional

import requests

from src.config.settings import settings

logger = logging.getLogger(__name__)


class VKStats:
    API_VERSION = "5.131"

    def __init__(self):
        token = settings.VK_TOKEN
        owner_id = settings.VK_OWNER_ID

        if not token:
            raise ValueError("VK_TOKEN не задан в settings")
        if owner_id is None:
            raise ValueError("VK_OWNER_ID не задан в settings")

        self.token = token
        self.owner_id = owner_id
        self.base_url = "https://api.vk.com/method"

    def get_last_posts(self, count: int = 5) -> List[Dict]:
        """
        Возвращает список последних постов со стены (до count штук).
        Каждый элемент списка — словарь с полями:
          - post_id: ID поста
          - date:   время публикации (unix timestamp)
          - text:   текст поста
        :param count: количество последних постов
        :return: список постов (может быть меньше, если постов меньше)
        """
        url = f"{self.base_url}/wall.get"
        params = {
            "access_token": self.token,
            "v": self.API_VERSION,
            "owner_id": self.owner_id,
            "count": count,
            "filter": "owner"  # только посты владельца
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[VKStats] Ошибка при вызове wall.get: {e}")
            return []

        if "error" in data:
            err = data["error"]
            logger.error(f"[VKStats] VK API error {err.get('error_code')}: {err.get('error_msg')}")
            return []

        items = data.get("response", {}).get("items", [])
        posts = []
        for item in items:
            posts.append({
                "post_id": item.get("id"),
                "date": item.get("date"),
                "text": item.get("text", "")
            })
        return posts

    def get_post_stats(self, post_id: int) -> Optional[Dict]:
        """
        Возвращает детальную статистику для указанного поста:
          - likes:     количество лайков
          - comments:  количество комментариев
          - reposts:   количество репостов
          - views:     количество просмотров (если доступно)
        :param post_id: ID поста (целое число)
        :return: словарь статистики или None при ошибке
        """
        url = f"{self.base_url}/wall.getById"
        params = {
            "access_token": self.token,
            "v": self.API_VERSION,
            "posts": f"{self.owner_id}_{post_id}",
            "fields": "likes,comments,reposts,views"
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[VKStats] Ошибка при вызове wall.getById: {e}")
            return None

        if "error" in data:
            err = data["error"]
            logger.error(f"[VKStats] VK API error {err.get('error_code')}: {err.get('error_msg')}")
            return None

        items = data.get("response", [])
        if not items:
            logger.warning(f"[VKStats] Нет данных для поста {self.owner_id}_{post_id}")
            return None

        post = items[0]
        stats = {
            "post_id": post_id,
            "date": post.get("date"),
            "text": post.get("text", ""),
            "likes": post.get("likes", {}).get("count", 0),
            "comments": post.get("comments", {}).get("count", 0),
            "reposts": post.get("reposts", {}).get("count", 0),
            "views": post.get("views", {}).get("count", 0)
        }
        return stats

    def get_stats_for_last_posts(self, count: int = 5) -> List[Dict]:
        """
        Сочетает get_last_posts и get_post_stats: возвращает список статистик
        для последних count постов.
        :param count: количество последних постов для анализа
        :return: список словарей статистики (может быть меньше, если постов меньше)
        """
        posts = self.get_last_posts(count=count)
        stats_list = []
        for p in posts:
            pid = p.get("post_id")
            if pid is None:
                continue
            stats = self.get_post_stats(pid)
            if stats:
                stats_list.append(stats)
        return stats_list
