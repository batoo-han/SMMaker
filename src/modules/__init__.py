# src/modules/__init__.py

"""
Модуль-«фабрика» для генераторов и публикаторов.

Функция get_generator(name: str) возвращает экземпляр нужного генератора:
  - "chatgpt" или "openai" → OpenAIGenerator
  - "yandexgpt" или "yandex" → YandexGenerator

Аналогично, get_publisher(name: str) отдаёт нужный класс-публикатор
(например, VKPublisher, TelegramPublisher).
"""

from typing import Any

# Импортируем все генераторы
from src.modules.generators.openai_generator import OpenAIGenerator
from src.modules.generators.yandex_generator import YandexGenerator

# Импортируем публикаторы
from src.modules.vk.vk_publisher import VKPublisher
from src.modules.telegram.tg_publisher import TelegramPublisher


def get_generator(name: str) -> Any:
    """
    Возвращает экземпляр генератора текста или изображения по имени:
      - Для текста:
          "chatgpt" / "openai"   → OpenAIGenerator
          "yandexgpt" / "yandex" → YandexGenerator
      - Для изображений:
          "openai"  → OpenAIGenerator (часть работы image)
          # В будущем можно добавить "stable_diffusion" → StableDiffusionGenerator и т. д.
    """
    key = name.strip().lower()
    if key in ("chatgpt", "openai"):
        return OpenAIGenerator()
    if key in ("yandexgpt", "yandex"):
        return YandexGenerator()

    # Если имя совпадает с engine для изображений, тоже возвращаем OpenAIGenerator (DALL·E)
    if key in ("dall-e-3", "dall-e3", "dalle-3", "dalle3"):
        # В модуле OpenAIGenerator реализована и генерация картинок (DALL·E)
        return OpenAIGenerator()

    raise ValueError(f"Unsupported generator: {name}")


def get_publisher(name: str) -> Any:
    """
    Возвращает экземпляр публикатора по имени:
      - "vk" → VKPublisher
      - "telegram" → TelegramPublisher
      # В будущем добавите "instagram" → InstagramPublisher и т. д.
    """
    key = name.strip().lower()
    if key == "vk":
        return VKPublisher()
    if key == "telegram":
        return TelegramPublisher()

    raise ValueError(f"Unsupported publisher module: {name}")
