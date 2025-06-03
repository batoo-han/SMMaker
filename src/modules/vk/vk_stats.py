"""
vk_stats.py

Реализация StatsInterface для ВКонтакте: сбор статистики по публикации.
"""
import os
import logging
from typing import Dict, Optional

import vk_api
from vk_api.exceptions import ApiError

from src.core.interfaces import StatsInterface
from src.config.settings import settings

logger = logging.getLogger(__name__)


class VKStats(StatsInterface):
    """
    Сбор статистики по постам ВКонтакте: лайки, репосты, комментарии.
    """

    def __init__(self):
        token = os.getenv('VK_TOKEN') or settings.VK_TOKEN
        if not token:
            raise ValueError("VK_TOKEN не задан")
        self.vk = vk_api.VkApi(token=token).get_api()
        self.owner_id = int(os.getenv('VK_OWNER_ID', 0))

    def collect(self, post_url: str) -> Optional[Dict]:
        """
        Сбор статистики по URL поста.
        Возвращает словарь: likes, reposts, comments, views.
        """
        try:
            # Извлекаем owner_id и post_id из URL вида https://vk.com/wall{owner_id}_{post_id}
            parts = post_url.strip().split('wall')[-1]
            owner_str, post_str = parts.split('_')
            owner_id = int(owner_str)
            post_id = int(post_str)
            response = self.vk.wall.getById(posts=f"{owner_id}_{post_id}")
            if not response:
                return None
            post_info = response[0]
            stats = post_info.get('comments'), post_info.get('likes'), post_info.get('reposts'), post_info.get('views')
            return {
                'comments': stats[0].get('count'),
                'likes': stats[1].get('count'),
                'reposts': stats[2].get('count'),
                'views': stats[3].get('count')
            }
        except ApiError as e:
            logger.error(f"Ошибка VK API при сборе статистики: {e}")
            return None
        except Exception as e:
            logger.error(f"Некорректный URL поста: {post_url}, ошибка: {e}")
            return None
