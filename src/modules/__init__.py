# src/modules/__init__.py

"""
Модуль «фабрика» для генераторов (text + image) и публикаторов.
get_generator(name) → возвращает нужный генератор по имени.
get_publisher(name) → возвращает нужный публикатор по имени.
"""

from typing import Any

# Текстовые генераторы
from src.modules.generators.openai_generator import OpenAIGenerator
from src.modules.generators.yandex_generator import YandexGenerator

# Image-генераторы
from src.modules.image_generators.openai_image_generator import OpenAIImageGenerator
from src.modules.image_generators.fusionbrain_image_generator import FusionBrainImageGenerator

# Публикаторы
from src.modules.vk.vk_publisher import VKPublisher
from src.modules.telegram.tg_publisher import TelegramPublisher


def get_generator(name: str) -> Any:
    """
    Возвращает экземпляр генератора по ключу `name`.

    Текстовые генераторы:
      - "openai", "openai-text" или "chatgpt"  → OpenAIGenerator
      - "yandex" или "yandexgpt"              → YandexGenerator

    Image-генераторы:
      - "dall-e", "dalle" или "openai-image"  → OpenAIImageGenerator
      - "fusionbrain"                         → FusionBrainImageGenerator
    """
    key = name.strip().lower()

    # ----- Текстовые генераторы -----
    if key in ("openai", "openai-text", "chatgpt"):
        return OpenAIGenerator()
    if key in ("yandex", "yandexgpt"):
        return YandexGenerator()

    # ----- Image-генераторы -----
    if key in ("dall-e", "dalle", "openai-image"):
        return OpenAIImageGenerator()
    if key == "fusionbrain":
        return FusionBrainImageGenerator()

    raise ValueError(f"Unsupported generator module: {name}")


def get_publisher(name: str) -> Any:
    """
    Возвращает экземпляр публикатора по имени:
      - "vk"       → VKPublisher
      - "telegram" или "tg" → TelegramPublisher
    """
    key = name.strip().lower()
    if key == "vk":
        return VKPublisher()
    if key in ("telegram", "tg"):
        return TelegramPublisher()

    raise ValueError(f"Unsupported publisher module: {name}")
