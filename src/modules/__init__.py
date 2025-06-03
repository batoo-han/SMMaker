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

# Публикаторы (оставляем без изменений, если они были)
from src.modules.vk.vk_publisher import VKPublisher
from src.modules.telegram.tg_publisher import TelegramPublisher


def get_generator(name: str) -> Any:
    """
    Возвращает экземпляр генератора по ключу `name`.

    Ключи для текстовых генераторов:
      - "openai" или "chatgpt"       → OpenAIGenerator
      - "yandex" или "yandexgpt"     → YandexGenerator

    Ключи для image-генераторов:
      - "openai-image" или "openai"  → OpenAIImageGenerator
      - "fusionbrain"                → FusionBrainImageGenerator

    Замечание: если вы вызываете get_generator("openai") в контексте текcта,
    лучше использовать "chatgpt" или "openai-text", чтобы не было путаницы.
    Однако, по умолчанию "openai" тоже вернёт OpenAIImageGenerator.

    :param name: строка-ключ провайдера
    :return: экземпляр класса, у которого будут методы generate_text() или generate_image().
    :raises: ValueError, если ключ не поддерживается.
    """
    key = name.strip().lower()

    # -------- Текстовые генераторы --------
    if key in ("openai-text", "chatgpt"):
        return OpenAIGenerator()
    if key in ("yandex", "yandexgpt"):
        return YandexGenerator()

    # -------- Image-генераторы --------
    # Чтобы не ломать обратную совместимость:
    # если name = "openai", возвращаем OpenAIImageGenerator
    if key in ("openai-image", "openai"):
        return OpenAIImageGenerator()
    if key == "fusionbrain":
        return FusionBrainImageGenerator()

    raise ValueError(f"Unsupported generator module: {name}")


def get_publisher(name: str) -> Any:
    """
    Возвращает экземпляр публикатора по имени:
      - "vk"       → VKPublisher
      - "telegram" или "tg" → TelegramPublisher

    :param name: строка-ключ публикатора
    :return: экземпляр класса Publisher
    """
    key = name.strip().lower()
    if key == "vk":
        return VKPublisher()
    if key in ("telegram", "tg"):
        return TelegramPublisher()

    raise ValueError(f"Unsupported publisher module: {name}")
