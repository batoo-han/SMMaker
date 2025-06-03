# src/modules/generators/openai_generator.py

"""
openai_generator.py

Реализация GeneratorInterface для OpenAI (ChatGPT) через новый клиент openai-python v1+.

Обновлено для совместимости с openai>=1.0.0:
  - Вместо openai.ChatCompletion.create используется openai.chat.completions.create.
  - Обработка параметров остаётся прежней.
"""

import logging
import openai
from typing import Tuple, Dict, Optional

from src.core.interfaces import GeneratorInterface
from src.config.settings import settings

logger = logging.getLogger(__name__)


class OpenAIGenerator(GeneratorInterface):
    """
    Генератор текстов через OpenAI Chat Completions API.
    Методы:
      - generate_text(prompt, model, temperature) → Tuple[str, Dict]
      - generate_image(...) → NotImplementedError
    """

    def __init__(self):
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY не задан в settings")
        openai.api_key = api_key

        # Модель и температура по умолчанию (берутся из настроек)
        self.default_model = settings.OPENAI_MODEL
        try:
            self.default_temperature = float(settings.OPENAI_TEMPERATURE)
        except Exception:
            self.default_temperature = 1.0

    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Tuple[Optional[str], Dict[str, Optional[float]]]:
        """
        Генерирует текст через OpenAI Chat Completions API.

        :param prompt: строка-запрос (prompt). Если пустая, возвращает (None, {'tokens': None, 'cost': None}).
        :param model:  имя модели (e.g., "gpt-4o" или "gpt-3.5-turbo"), переопределяет default_model.
        :param temperature: температурный параметр, переопределяет default_temperature.
        :return: (сгенерированный текст или None, meta), meta = {'tokens': usage_total, 'cost': None}.
        """
        if not prompt or not prompt.strip():
            return None, {"tokens": None, "cost": None}

        prompt_stripped = prompt.strip()
        model_to_use = model or self.default_model
        temp = temperature if temperature is not None else self.default_temperature

        # Логирование первых 200 символов prompt
        preview = (prompt_stripped[:200] + "...") if len(prompt_stripped) > 200 else prompt_stripped
        logger.debug(
            "[OpenAI] ChatCompletion (model=%s, temp=%.3f). Prompt preview: «%s»",
            model_to_use, temp, preview
        )

        try:
            # Новый интерфейс: openai.chat.completions.create
            response = openai.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "user", "content": prompt_stripped}],
                temperature=temp,
                max_tokens=2048
            )
        except Exception as e:
            logger.error(f"[OpenAI] Ошибка при вызове chat.completions.create: {e}")
            return None, {"tokens": None, "cost": None}

        # Извлекаем текст из ответа
        try:
            choice = response.choices[0]
            text = choice.message.content
        except Exception as e:
            logger.error(f"[OpenAI] Не удалось извлечь текст из ответа: {e}")
            return None, {"tokens": None, "cost": None}

        # Извлекаем количество токенов использования
        try:
            usage = response.usage
            total_tokens = usage.total_tokens if hasattr(usage, "total_tokens") else None
            total_tokens = int(total_tokens) if total_tokens is not None else None
        except Exception:
            total_tokens = None

        meta = {"tokens": total_tokens, "cost": None}
        return text.strip(), meta

    def generate_image(self, prompt: str, model: Optional[str] = None) -> bytes:
        """
        Этот класс не поддерживает генерацию изображений.
        """
        raise NotImplementedError("OpenAIGenerator поддерживает только generate_text()")
