# src/modules/vk/vk_publisher.py

import os
import logging
import requests
from typing import Optional

import vk_api
from vk_api.exceptions import ApiError

from src.core.interfaces import PublisherInterface
from src.core.models import Post
from src.config.settings import settings

logger = logging.getLogger(__name__)


class VKPublisher(PublisherInterface):
    """
    Публикатор для ВКонтакте (группа).
    Алгоритм:
      1) Проверяем, что post.idea (текст) и post.image_bytes (байты картинки) непустые.
      2) photos.getWallUploadServer(group_id=<pos_group_id>) → получаем upload_url.
      3) Загрузка POST multipart: files={'photo': ('image.jpg', <bytes>, 'image/jpeg')}.
      4) photos.saveWallPhoto(group_id=<pos_group_id>, photo=..., server=..., hash=...) → save_resp.
      5) Формируем attachment = "photo{owner_id}_{media_id}[_access_key]".
      6) wall.post(owner_id=-<group_id>, from_group=1, message=..., attachments=attachment).
      7) Возвращаем URL опубликованного поста или None.
    """

    def __init__(self):
        token = os.getenv("VK_TOKEN") or settings.VK_TOKEN
        if not token:
            raise ValueError("VK_TOKEN не задан")
        self.vk_session = vk_api.VkApi(token=token)
        self.api = self.vk_session.get_api()

        raw_owner = os.getenv("VK_OWNER_ID") or str(settings.VK_OWNER_ID)
        try:
            owner_id_int = int(raw_owner)
        except ValueError:
            raise ValueError("VK_OWNER_ID должна быть целым числом (с минусом для группы)")
        self.owner_id = owner_id_int

        if self.owner_id >= 0:
            raise ValueError("VK_OWNER_ID должен быть отрицательным числом (ID группы)")

        # Для getWallUploadServer и saveWallPhoto требуем положительный group_id:
        self.group_id = abs(self.owner_id)

    def publish(self, post: Post) -> Optional[str]:
        """
        Публикует пост (текст + изображение) в группу.
        Если текст или изображение отсутствуют, возвращает None.
        """
        if not post.idea or not post.image_bytes:
            logger.error("[vk] Невозможно опубликовать: текст или изображение отсутствует.")
            return None

        try:
            # 1) Получаем upload_url для фотографии
            upload_resp = self.api.photos.getWallUploadServer(group_id=self.group_id)
            upload_url = upload_resp.get("upload_url")
            if not upload_url:
                logger.error(f"[vk] Не удалось получить upload_url: {upload_resp}")
                return None

            # 2) Загружаем байты изображения multipart-запросом
            files = {
                "photo": ("image.jpg", post.image_bytes, "image/jpeg")
            }
            upload_result = requests.post(upload_url, files=files).json()
            logger.debug(f"[vk] upload_result: {upload_result}")

            # 3) Сохраняем фотографию в альбом стены группы
            save_resp = self.api.photos.saveWallPhoto(
                group_id=self.group_id,
                photo=upload_result.get("photo"),
                server=upload_result.get("server"),
                hash=upload_result.get("hash"),
            )
            logger.debug(f"[vk] save_resp: {save_resp}")

            if not save_resp or not isinstance(save_resp, list):
                logger.error(f"[vk] Не удалось сохранить фото: {save_resp}")
                return None

            photo_info = save_resp[0]
            media_id_vk = photo_info.get("id")        # ID фото
            owner_vk = photo_info.get("owner_id")    # отрицательный ID группы
            access_key = photo_info.get("access_key")  # возможно None

            # 4) Формируем строку attachments
            if access_key:
                attachment = f"photo{owner_vk}_{media_id_vk}_{access_key}"
            else:
                attachment = f"photo{owner_vk}_{media_id_vk}"

            # 5) Публикуем пост с текстом и фото
            publish_params = {
                "owner_id": self.owner_id,  # отрицательный ID группы
                "from_group": 1,
                "message": post.idea,
                "attachments": attachment,
            }
            response = self.api.wall.post(**publish_params)
            post_id = response.get("post_id")
            if not post_id:
                logger.error(f"[vk] wall.post вернул без post_id: {response}")
                return None

            url = f"https://vk.com/wall{self.owner_id}_{post_id}"
            logger.info(f"[vk] Пост опубликован: {url}")
            return url

        except ApiError as e:
            logger.error(f"[vk] Ошибка VK API при публикации: {e}")
            return None
        except Exception as e:
            logger.error(f"[vk] Неожиданная ошибка при публикации в VK: {e}")
            return None
