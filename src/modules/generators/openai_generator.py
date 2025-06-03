# src/modules/generators/openai_generator.py

"""
openai_generator.py

Реализация GeneratorInterface для OpenAI (ChatGPT и DALL·E), совместимая с openai>=1.0.0.
Исправлено получение usage.total_tokens из объекта CompletionUsage вместо .get().
"""

import base64
import logging
import openai
import requests
from typing import Tuple, Dict, Optional

from src.core.interfaces import GeneratorInterface
from src.config.settings import settings

logger = logging.getLogger(__name__)


class OpenAIGenerator(GeneratorInterface):
    def __init__(self):
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY не задан в settings")
        openai.api_key = api_key

        self.text_model = settings.OPENAI_MODEL
        try:
            self.text_temperature = float(settings.OPENAI_TEMPERATURE)
        except Exception:
            self.text_temperature = 1.0  # используем 1.0 по умолчанию

        self.image_model = settings.IMAGE_MODEL

    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Tuple[str, Dict]:
        """
        Генерирует текст через OpenAI Chat API (openai>=1.0.0).
        Если модель не поддерживает параметр temperature, повторяем без него.
        Возвращаем (text, meta), где meta содержит 'tokens' (int) и 'cost' (float).
        """
        model_to_use = model or self.text_model
        temp = temperature if temperature is not None else self.text_temperature

        def _chat_request(include_temp: bool):
            kwargs = {
                "model": model_to_use,
                "messages": [{"role": "user", "content": prompt}],
            }
            if include_temp:
                kwargs["temperature"] = temp
            return openai.chat.completions.create(**kwargs)

        # Первая попытка с параметром temperature
        try:
            response = _chat_request(include_temp=True)
        except openai.error.InvalidRequestError as e:
            # Проверяем, связана ли ошибка с неподдержкой temperature
            err_msg = ""
            try:
                err_data = e.args[0]
                err_msg = err_data.get("error", {}).get("message", "") if isinstance(err_data, dict) else str(e)
            except Exception:
                err_msg = str(e)

            if "Unsupported value: 'temperature'" in err_msg:
                logger.warning("[OpenAI] Модель %s не поддерживает temperature=%s, повтор без этого параметра",
                               model_to_use, temp)
                try:
                    response = _chat_request(include_temp=False)
                except Exception as e2:
                    logger.error(f"[OpenAI] Ошибка повторного вызова без temperature: {e2}")
                    raise
            else:
                logger.error(f"[OpenAI] Ошибка при вызове chat.completions.create: {err_msg}")
                raise
        except Exception as e:
            logger.error(f"[OpenAI] Ошибка при вызове chat.completions.create: {e}")
            raise

        # Извлекаем текст из ответа
        try:
            message_obj = response.choices[0].message
            text = message_obj.content
        except Exception as e:
            logger.error(f"[OpenAI] Не удалось извлечь текст из ответа: {e}")
            raise

        # Извлекаем usage.total_tokens из объекта CompletionUsage
        try:
            usage = response.usage  # это объект CompletionUsage
            total_tokens = getattr(usage, "total_tokens", 0) or 0
        except Exception:
            total_tokens = 0

        # Рассчитываем примерную стоимость
        cost_per_1k = {
            'gpt-4o': 0.03,
            'gpt-4.5': 0.06,
            'gpt-3.5-turbo': 0.002
        }.get(model_to_use, 0.002)
        cost = (total_tokens / 1000) * cost_per_1k

        meta = {
            'tokens': total_tokens,
            'cost': round(cost, 6)
        }
        return text, meta

    def generate_image(self, prompt: str, model: Optional[str] = None) -> bytes:
        """
        Генерация изображения через OpenAI Images API (DALL·E) в openai>=1.0.0.
        Возвращает байты изображения (расшифрованные из base64).
        """
        model_to_use = model or self.image_model

        try:
            response = openai.images.generate(
                model=model_to_use,
                prompt=prompt,
                n=1,
                size="1024x1024",
                response_format="b64_json"
            )
        except Exception as e:
            logger.error(f"[OpenAI] Ошибка при вызове images.generate: {e}")
            raise

        try:
            b64_json = response.data[0].b64_json
            image_data = base64.b64decode(b64_json)
        except Exception as e:
            logger.error(f"[OpenAI] Не удалось декодировать изображение: {e}")
            raise

        return image_data
