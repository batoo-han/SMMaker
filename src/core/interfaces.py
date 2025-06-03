# src/core/interfaces.py

"""
interfaces.py

Здесь определяются интерфейсы (абстрактные базовые классы) для генераторов и паблишеров.
Каждый подкласс должен реализовать указанные методы.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Dict, Optional

from src.core.models import Post


class GeneratorInterface(ABC):
    """
    Интерфейс для генератора (LLM или другой нейросети).
    """

    @abstractmethod
    def generate_text(self, prompt: str, model: str = None, temperature: float = None) -> Tuple[str, Dict]:
        """
        Генерирует текст по заданному prompt.

        Args:
            prompt (str): текстовый запрос.
            model (str, optional): конкретная модель для генерации (override).
            temperature (float, optional): степень креативности (override).

        Returns:
            Tuple[str, Dict]: кортеж (сгенерированный текст, метаданные),
                где метаданные включают ключи 'tokens' и 'cost'.
        """
        raise NotImplementedError


    @abstractmethod
    def generate_image(self, prompt: str, model: str = None) -> bytes:
        """
        Генерирует изображение по заданному prompt.

        Args:
            prompt (str): текстовый запрос для генерации изображения.
            model (str, optional): конкретная модель для генерации (override).

        Returns:
            bytes: байты изображения (напрямую для отправки в соцсеть).
        """
        raise NotImplementedError


class PublisherInterface(ABC):
    """
    Интерфейс для паблишера (VK, Telegram и т.д.).
    """

    @abstractmethod
    def publish(self, post: Post) -> Optional[str]:
        """
        Публикует контент (текст + опциональное изображение) в соответствующую соцсеть.

        Args:
            post (Post): объект Post с полями:
                - idea (строка, содержащая заголовок и текст статьи),
                - image_bytes (байты, если есть иллюстрация).

        Returns:
            Optional[str]: URL опубликованного поста или None при неудаче.
        """
        raise NotImplementedError


def get_generator(name: str) -> GeneratorInterface:
    """
    Возвращает экземпляр генератора по имени:
      - "chatgpt" → OpenAIGenerator
      - "yandexgpt" → YandexGenerator (если реализован)
    """
    key = name.lower()
    if key in ("chatgpt", "openai"):
        from src.modules.generators.openai_generator import OpenAIGenerator
        return OpenAIGenerator()
    elif key in ("yandexgpt", "yandex"):
        from src.modules.generators.yandex_generator import YandexGenerator
        return YandexGenerator()
    else:
        raise ValueError(f"Unsupported generator: {name}")


def get_publisher(name: str) -> PublisherInterface:
    """
    Возвращает экземпляр паблишера по имени:
      - "vk" → VKPublisher
      - "telegram" → TelegramPublisher
    """
    key = name.lower()
    if key == "vk":
        from src.modules.vk.vk_publisher import VKPublisher
        return VKPublisher()
    elif key in ("tg", "telegram"):
        from src.modules.telegram.tg_publisher import TelegramPublisher
        return TelegramPublisher()
    else:
        raise ValueError(f"Unsupported publisher module: {name}")
