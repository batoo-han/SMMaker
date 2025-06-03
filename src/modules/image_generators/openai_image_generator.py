# src/modules/image_generators/openai_image_generator.py

"""
openai_image_generator.py

Реализация GeneratorInterface для генерации изображений через OpenAI Image API,
обновлённая для openai-python>=1.0.0.

Теперь вместо устаревшего `openai.Image.create(...)` используется `openai.images.generate(...)`.
См. миграцию: :contentReference[oaicite:0]{index=0}
"""

import logging
import openai
from typing import Optional

from src.core.interfaces import GeneratorInterface
from src.config.settings import settings

logger = logging.getLogger(__name__)


class OpenAIImageGenerator(GeneratorInterface):
    """
    Генератор изображений через OpenAI Image API (DALL·E и др.).
    Методы:
      - generate_image(prompt, model) → bytes
      - generate_text(...) → NotImplementedError
    """

    def __init__(self):
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY не задан в settings")
        openai.api_key = api_key

        # Модель по умолчанию (например, "dall-e-3")
        self.default_model = settings.IMAGE_MODEL or "dall-e-3"

    def generate_image(self, prompt: str, model: Optional[str] = None) -> bytes:
        """
        Генерирует изображение по заданному prompt.

        :param prompt: строка-описание изображения.
        :param model:  имя модели (например, "dall-e-3"), переопределяет default_model.
        :return: байты изображения (PNG).
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt для генерации изображения не может быть пустым")

        prompt_str = prompt.strip()
        model_to_use = model or self.default_model

        logger.debug("[OpenAIImage] Генерация изображения (model=%s). Prompt: «%s»",
                     model_to_use, prompt_str)

        try:
            # Новый метод для генерации: openai.images.generate
            response = openai.images.generate(
                model=model_to_use,
                prompt=prompt_str,
                n=1,
                size="1024x1024"
            )
        except Exception as e:
            logger.error(f"[OpenAIImage] Ошибка при вызове images.generate: {e}")
            raise

        # Извлекаем URL первого сгенерированного изображения
        try:
            image_url = response.data[0].url
        except Exception as e:
            logger.error(f"[OpenAIImage] Не удалось получить URL из ответа: {e}")
            raise

        # Скачиваем изображение по URL
        try:
            import requests
            img_resp = requests.get(image_url, timeout=30)
            img_resp.raise_for_status()
            return img_resp.content
        except Exception as e:
            logger.error(f"[OpenAIImage] Ошибка при скачивании изображения: {e}")
            raise

    def generate_text(self, prompt: str, model: Optional[str] = None, temperature: Optional[float] = None):
        """
        Этот класс не поддерживает генерацию текста.
        """
        raise NotImplementedError("OpenAIImageGenerator поддерживает только generate_image()")
