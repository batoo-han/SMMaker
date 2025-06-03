# src/modules/image_generators/fusionbrain_image_generator.py

"""
fusionbrain_image_generator.py

Класс FusionBrainImageGenerator отвечает за генерацию изображений через FusionBrain AI API.
Документация: https://fusionbrain.ai/docs/ru/doc/api-dokumentaciya/
"""

import base64
import io
import logging
import requests
from typing import Optional

from src.core.interfaces import GeneratorInterface
from src.config.settings import settings

logger = logging.getLogger(__name__)


class FusionBrainImageGenerator(GeneratorInterface):
    """
    Генератор изображений через FusionBrain API.
    Реализует generate_image, generate_text бросает NotImplementedError.
    """

    def __init__(self):
        # Проверяем наличие API-ключа FusionBrain
        api_key = settings.FUSIONBRAIN_API_KEY
        if not api_key:
            raise ValueError("FUSIONBRAIN_API_KEY не задан в settings")
        self.api_key = api_key

        # Базовый URL из настроек
        self.base_url = settings.FUSIONBRAIN_API_BASE_URL.rstrip('/')
        # Модель по умолчанию (например, "stable-diffusion-1")
        self.default_model = settings.FUSIONBRAIN_DEFAULT_MODEL

    def generate_text(self, prompt: str, model: Optional[str] = None) -> None:
        """
        Этот класс не отвечает за генерацию текста.
        """
        raise NotImplementedError("FusionBrainImageGenerator поддерживает только generate_image()")

    def generate_image(self, prompt: str, model: Optional[str] = None) -> bytes:
        """
        Генерирует изображение через FusionBrain API.

        :param prompt: строка с описанием картинки
        :param model: необязательное имя модели FusionBrain (например, "stable-diffusion-1")
                      Если None, используется self.default_model.
        :return: байты изображения (PNG/JPEG).
        :raises: Exception, если запрос упал или нельзя декодировать ответ.
        """
        model_to_use = model or self.default_model
        url = f"{self.base_url}/images/generate"

        # Примерный JSON-тело; точный формат может отличаться по документации FusionBrain,
        # нужно свериться с актуальной документацией на момент интеграции.
        payload = {
            "model": model_to_use,
            "prompt": prompt,
            "width": 1024,
            "height": 1024,
            # Если в FusionBrain есть другие параметры (cfg_scale, seed и т. д.),
            # можно их тоже здесь передавать через настройки.
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"[FusionBrainImage] Ошибка при запросе к {url}: {e}")
            raise

        # Предположим, что FusionBrain возвращает JSON:
        # { "data": { "image_base64": "<...>" } }
        # Но если реальная API возвращает бинарь (Content-Type: image/png),
        # нужно обрабатывать это отдельно.

        content_type = resp.headers.get("Content-Type", "")
        try:
            if content_type.startswith("application/json"):
                data = resp.json()
                b64img = data["data"].get("image_base64")
                if not b64img:
                    raise ValueError("В ответе FusionBrain нет поля image_base64")
                image_bytes = base64.b64decode(b64img)
            elif content_type.startswith("image/"):
                # Если API вернул чистые байты картинки, просто забираем их
                image_bytes = resp.content
            else:
                raise ValueError(f"Неподдерживаемый Content-Type: {content_type}")
        except Exception as e:
            logger.error(f"[FusionBrainImage] Ошибка при обработке ответа: {e}")
            raise

        return image_bytes
