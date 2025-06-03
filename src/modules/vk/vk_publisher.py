# src/modules/vk/vk_publisher.py

"""
vk_publisher.py

Реализация PublisherInterface для VK. Отвечает за публикацию объекта Post
(текст + изображение) на стену ВКонтакте.

Использует методы VK API:
  1) photos.getWallUploadServer    — получить URL для загрузки изображения
  2) photos.saveWallPhoto          — сохранить загружённое изображение на сервере VK
  3) wall.post                     — опубликовать пост с текстом и прикреплённой фотографией

Настройки берутся из src/config/settings.py:
  - VK_TOKEN     — токен доступа (user или group)
  - VK_OWNER_ID  — ID владельца стены (отрицательное для сообществ, положительное для пользователей)
"""

import json
import logging
import requests
from typing import Optional

from src.core.interfaces import PublisherInterface
from src.core.models import Post
from src.config.settings import settings

logger = logging.getLogger(__name__)


class VKPublisher(PublisherInterface):
    """
    PublisherInterface для VK API.

    При наличии post.image_bytes:
      1) Запрос photos.getWallUploadServer для получения upload_url.
      2) Загружаем байты изображения по этому URL.
      3) Сохраняем фото методом photos.saveWallPhoto, получаем media_id и owner_id.
      4) Формируем attachment в формате "photo{owner_id}_{media_id}".
      5) Вызываем wall.post с текстом и attachment.

    Если post.image_bytes пуст:
      - Вызываем wall.post только с текстом.

    Возвращает ID опубликованного поста в формате "<owner_id>_<post_id>" или None при ошибке.
    """

    API_VERSION = "5.131"  # актуальная версия VK API

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

    def publish(self, post: Post) -> Optional[str]:
        """
        Публикует Post в VK.

        :param post: объект Post с полями id, title, content, image_bytes, metadata
        :return: строка "<owner_id>_<post_id>" при успехе или None при ошибке
        """
        try:
            if post.image_bytes:
                attachment = self._upload_photo(post.image_bytes)
                if not attachment:
                    return None
                return self._post_wall(text=post.content, attachment=attachment)
            else:
                return self._post_wall(text=post.content)
        except Exception as e:
            logger.error(f"[VKPublisher] Ошибка при публикации: {e}")
            return None

    def _upload_photo(self, image_bytes: bytes) -> Optional[str]:
        """
        Загружает изображение на сервер VK и возвращает attachment-строку.

        :param image_bytes: байты изображения (PNG, JPEG)
        :return: attachment в формате "photo{owner_id}_{media_id}" или None при ошибке
        """
        # 1) Получаем URL для загрузки
        params = {
            "access_token": self.token,
            "v": self.API_VERSION,
            "owner_id": self.owner_id,
        }
        try:
            resp = requests.get(
                f"{self.base_url}/photos.getWallUploadServer",
                params=params,
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            upload_url = data["response"]["upload_url"]
        except Exception as e:
            logger.error(f"[VKPublisher] Не удалось получить upload_url: {e}")
            return None

        # 2) Загружаем изображение
        files = {
            "photo": ('image.jpg', image_bytes)
        }
        try:
            upload_resp = requests.post(upload_url, files=files, timeout=60)
            upload_resp.raise_for_status()
            upload_data = upload_resp.json()
            server = upload_data.get("server")
            photo = upload_data.get("photo")
            photo_hash = upload_data.get("hash")
            if not (server and photo and photo_hash):
                raise ValueError("В ответе upload-сервера отсутствуют server/photo/hash")
        except Exception as e:
            logger.error(f"[VKPublisher] Ошибка при загрузке изображения на upload_server: {e}")
            return None

        # 3) Сохраняем фото методом photos.saveWallPhoto
        save_params = {
            "access_token": self.token,
            "v": self.API_VERSION,
            "owner_id": self.owner_id,
            "server": server,
            "photo": photo,
            "hash": photo_hash
        }
        try:
            save_resp = requests.post(
                f"{self.base_url}/photos.saveWallPhoto",
                data=save_params,
                timeout=30
            )
            save_resp.raise_for_status()
            save_data = save_resp.json()
            saved = save_data["response"][0]
            photo_owner_id = saved["owner_id"]
            media_id = saved["id"]
        except Exception as e:
            logger.error(f"[VKPublisher] Не удалось сохранить фото через photos.saveWallPhoto: {e}")
            return None

        # 4) Формируем строку attachment
        return f"photo{photo_owner_id}_{media_id}"

    def _post_wall(self, text: str, attachment: Optional[str] = None) -> Optional[str]:
        """
        Публикует запись на стену VK.

        :param text: текст поста
        :param attachment: строка attachment для фото, или None
        :return: строка "<owner_id>_<post_id>" при успехе или None при ошибке
        """
        params = {
            "access_token": self.token,
            "v": self.API_VERSION,
            "owner_id": self.owner_id,
            "message": text or "",
        }
        if attachment:
            params["attachments"] = attachment

        try:
            resp = requests.post(
                f"{self.base_url}/wall.post",
                data=params,
                timeout=30
            )
            resp.raise_for_status()
            result = resp.json()
            if "error" in result:
                err = result["error"]
                raise ValueError(f"VK API error {err.get('error_code')}: {err.get('error_msg')}")
            post_id = result["response"]["post_id"]
            return f"{self.owner_id}_{post_id}"
        except Exception as e:
            logger.error(f"[VKPublisher] Ошибка при вызове wall.post: {e}")
            return None
