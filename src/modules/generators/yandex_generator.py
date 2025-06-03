# src/modules/generators/yandex_generator.py

"""
yandex_generator.py

Реализация GeneratorInterface для YandexGPT через Yandex Cloud Foundation Models API.

Формат запроса:
{
  "modelUri": "gpt://<folder_id>/<model_name>/latest",
  "completionOptions": {
    "temperature": <float>,
    "maxTokens": <int>
  },
  "messages": [
    { "role": "user", "text": "<prompt>" }
  ]
}

Заголовки:
  Authorization: Api-Key <YANDEX_API_KEY>
  X-Yandex-Cloud-Folder-Id: <YANDEX_CLOUD_FOLDER_ID>
  Content-Type: application/json

Возвращает:
  - text (str) или None при ошибке
  - meta: {'tokens': <int>|None, 'cost': None}
"""

import logging
import requests
from typing import Tuple, Dict, Optional

from src.core.interfaces import GeneratorInterface
from src.config.settings import settings

logger = logging.getLogger(__name__)


class YandexGenerator(GeneratorInterface):
    def __init__(self):
        # 1) Берём API-ключ и folder_id из настроек
        api_key = settings.YANDEX_API_KEY
        if not api_key:
            raise ValueError("YANDEX_API_KEY не задан в settings")
        self.api_key = api_key

        folder_id = settings.YANDEX_CLOUD_FOLDER_ID
        if not folder_id:
            raise ValueError("YANDEX_CLOUD_FOLDER_ID не задан в settings")
        self.folder_id = folder_id

        # 2) Имя текстовой модели и температура
        self.text_model = settings.YANDEXGPT_MODEL
        try:
            self.text_temperature = float(settings.YANDEXGPT_TEMPERATURE)
        except Exception:
            self.text_temperature = 0.6

        # 3) URL для синхронного completion Yandex Foundation Models
        self.completion_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Tuple[Optional[str], Dict[str, Optional[int]]]:
        """
        Генерирует текст через Yandex Cloud Foundation Models.

        :param prompt: исходный текст-запрос
        :param model:  имя модели, переопределяет self.text_model
        :param temperature: float, переопределяет self.text_temperature
        :return: (сгенерированный текст или None, meta={'tokens': <int>|None, 'cost': None})
        """
        # 1) Проверка непустого prompt
        if not prompt or not prompt.strip():
            logger.error("[Yandex] Пустой prompt после .strip().")
            return None, {"tokens": None, "cost": None}

        prompt_stripped = prompt.strip()

        # 2) Определяем модель и температуру
        model_name = model or self.text_model
        temp = temperature if temperature is not None else self.text_temperature

        # 3) Формируем modelUri
        model_uri = f"gpt://{self.folder_id}/{model_name}/latest"

        # 4) Заголовки
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "X-Yandex-Cloud-Folder-Id": self.folder_id,
            "Content-Type": "application/json"
        }

        # 5) Тело запроса
        body = {
            "modelUri": model_uri,
            "completionOptions": {
                "temperature": temp,
                "maxTokens": 2048
            },
            "messages": [
                {"role": "user", "text": prompt_stripped}
            ]
        }

        # 6) Логирование тела запроса (первые 200 символов)
        preview = prompt_stripped[:200] + "..." if len(prompt_stripped) > 200 else prompt_stripped
        logger.debug(
            "[Yandex] POST %s body: modelUri=%s, messages[0].text (len=%d): «%s»",
            self.completion_url, model_uri, len(prompt_stripped), preview
        )

        # 7) Выполняем запрос
        try:
            resp = requests.post(self.completion_url, headers=headers, json=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.HTTPError as http_err:
            status = http_err.response.status_code
            text_resp = http_err.response.text
            logger.error("[Yandex] HTTP %d при вызове API. Ответ: %s", status, text_resp)
            return None, {"tokens": None, "cost": None}
        except Exception as e:
            logger.error("[Yandex] Ошибка при вызове API: %s", e)
            return None, {"tokens": None, "cost": None}

        # 8) Логируем первые 200 символов ответа (если есть)
        try:
            alt = data.get("result", {}).get("alternatives", [])
            if alt:
                response_preview = alt[0].get("message", {}).get("text", "")
                preview_resp = response_preview[:200] + "..." if len(response_preview) > 200 else response_preview
                logger.debug("[Yandex] Успешный ответ (первые 200 chars): «%s»", preview_resp)
        except Exception:
            pass

        # 9) Извлекаем сгенерированный текст
        try:
            choice = data["result"]["alternatives"][0]
            text = choice["message"]["text"]
            if text is None:
                logger.error("[Yandex] Пустой текст в ответе API")
                return None, {"tokens": None, "cost": None}
        except Exception as e:
            logger.error("[Yandex] Не удалось извлечь текст из ответа: %s", e)
            return None, {"tokens": None, "cost": None}

        # 10) Получаем количество токенов
        try:
            total_tokens = data["result"]["usage"]["totalTokens"]
            total_tokens = int(total_tokens) if total_tokens is not None else None
        except Exception as e:
            logger.warning("[Yandex] Некорректный формат totalTokens: %s", e)
            total_tokens = None

        # 11) Возвращаем текст и meta
        meta = {"tokens": total_tokens, "cost": None}
        return text.strip(), meta

    def generate_image(self, prompt: str, model: Optional[str] = None) -> bytes:
        """
        Генерация изображений через Yandex GPT пока не поддерживается.
        """
        raise NotImplementedError("Yandex image generation не поддерживается.")
