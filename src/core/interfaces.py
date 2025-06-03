# src/core/interfaces.py

"""
interfaces.py

Здесь определяются абстрактные интерфейсы для:
  1) Генераторов (LLM и image‐провайдеров)
  2) Публикаторов (VK, Telegram, и т.д.)

Каждый конкретный класс-реализация должен наследоваться от соответствующего интерфейса и
реализовать все объявленные методы.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Dict, Optional

from src.core.models import Post


class GeneratorInterface(ABC):
    """
    Общий интерфейс для всех «генераторов» (текстовых LLM и image‐провайдеров).
    Классы‐наследники обязаны реализовать оба метода, но для «чисто текстовых»
    или «чисто image» провайдеров один из методов может бросать NotImplementedError.
    """

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Tuple[str, Dict]:
        """
        Генерирует текст по заданному prompt.

        Args:
            prompt (str): строка‐запрос.
            model (Optional[str]): при необходимости переопределить модель (override).
            temperature (Optional[float]): степень креативности (override).

        Returns:
            Tuple[str, Dict]:
              - сгенерированный текст (str),
              - словарь метаданных, например {'tokens': int, 'cost': float}.
        """
        raise NotImplementedError

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None
    ) -> bytes:
        """
        Генерирует изображение по заданному prompt.

        Args:
            prompt (str): строка‐описание картинки.
            model (Optional[str]): при необходимости переопределить модель (override).

        Returns:
            bytes: «сырые» байты изображения (PNG, JPEG и т.д.).
        """
        raise NotImplementedError


class PublisherInterface(ABC):
    """
    Интерфейс для «публикаторов» (VK, Telegram и т.д.).
    Конкретный публикатор отвечает за то, чтобы взять объект Post и
    отправить его «в сеть», вернув ссылку/ID опубликованного поста.
    """

    @abstractmethod
    def publish(self, post: Post) -> Optional[str]:
        """
        Публикует содержимое объекта Post в соответствующей социальной сети.

        Args:
            post (Post): объект с полями:
                - id (str)          — идентификатор публикации (из ScheduleConfig.id).
                - title (str)       — заголовок/имя поста
                - content (str)     — текст
                - image_bytes (bytes) — изображение
                - metadata (Dict)   — дополнительные данные (model, tokens, cost)

        Returns:
            Optional[str]: URL или уникальный идентификатор опубликованного поста.
                           Если публикация не удалась, вернуть None или бросить исключение.
        """
        raise NotImplementedError
