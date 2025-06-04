# src/modules/image_generators/fusionbrain_image_generator.py

"""
fusionbrain_image_generator.py

Класс FusionBrainImageGenerator отвечает за генерацию изображений через FusionBrain AI API.

Изменения:
 - FusionBrain может возвращать либо URL, либо Base64-строку.
 - Если файл возвращён в виде Base64, декодируем и возвращаем байты.
 - Если файл возвращается через URL, скачиваем как раньше.

Документация FusionBrain:
https://fusionbrain.ai/docs/ru/doc/api-dokumentaciya/

Этапы:
 1. GET  {root_url}/api/v1/pipelines
    — получить список pipeline, взять первый id.
 2. POST {root_url}/api/v1/pipeline/run
    — multipart/form-data:
         * pipeline_id  — ID конвейера
         * params       — JSON с опциями генерации
    В ответе получаем {"uuid": "<ID_задачи>", ...}.
 3. GET {root_url}/api/v1/pipeline/status/{uuid}
    — опрашиваем, пока status != "DONE".
    Когда status == "DONE", data["result"]["files"] содержит список, элементами которого
    могут быть URL или Base64-строка.
 4. Если элемент начинается с "http", делаем GET по URL.
    Иначе считаем, что это Base64-строка, декодируем через base64.b64decode.
"""

import time
import json
import logging
import requests
import re
import base64
from typing import Optional

from src.core.interfaces import GeneratorInterface
from src.config.settings import settings

logger = logging.getLogger(__name__)


class FusionBrainImageGenerator(GeneratorInterface):
    """
    Генератор изображений через FusionBrain API.
    Реализует только generate_image; generate_text не поддерживается.
    """

    def __init__(self):
        api_key = settings.FUSIONBRAIN_API_KEY
        if not api_key:
            raise ValueError("FUSIONBRAIN_API_KEY не задан в settings")

        secret_key = getattr(settings, "FUSIONBRAIN_API_SECRET", None)
        if not secret_key:
            raise ValueError("FUSIONBRAIN_API_SECRET не задан в settings")

        self.api_key = api_key
        self.secret_key = secret_key

        raw_base = settings.FUSIONBRAIN_API_BASE_URL.rstrip("/")
        # Если base_url заканчивается на "/api/v1", убираем эту часть
        self.root_url = re.sub(r"/api/v1$", "", raw_base)

        logger.debug(f"[FusionBrainImage] Исходный FUSIONBRAIN_API_BASE_URL: {settings.FUSIONBRAIN_API_BASE_URL}")
        logger.debug(f"[FusionBrainImage] Вычисленный root_url: {self.root_url}")

        self.default_model = settings.FUSIONBRAIN_DEFAULT_MODEL

        self.auth_headers = {
            "X-Key": f"Key {self.api_key}",
            "X-Secret": f"Secret {self.secret_key}",
        }

    def generate_text(self, prompt: str, model: Optional[str] = None) -> None:
        raise NotImplementedError("FusionBrainImageGenerator поддерживает только generate_image()")

    def _get_pipeline_id(self) -> str:
        url = f"{self.root_url}/key/api/v1/pipelines"
        logger.debug(f"[FusionBrainImage] GET pipelines URL: {url}")
        try:
            resp = requests.get(url, headers=self.auth_headers, timeout=10)
            logger.debug(f"[FusionBrainImage] Ответ GET pipelines: status={resp.status_code}, body={resp.text}")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[FusionBrainImage] Ошибка получения pipeline_id: {e}")
            raise

        try:
            pipeline_id = data[0]["id"]
            logger.debug(f"[FusionBrainImage] Получен pipeline_id: {pipeline_id}")
        except Exception as e:
            logger.error(f"[FusionBrainImage] Не удалось извлечь pipeline_id из ответа: {data} — {e}")
            raise

        return pipeline_id

    def _submit_generation(self, prompt: str, pipeline_id: str, width: int, height: int) -> str:
        url = f"{self.root_url}/key/api/v1/pipeline/run"
        logger.debug(f"[FusionBrainImage] POST run URL: {url}")
        params = {
            "type": "GENERATE",
            "numImages": 1,
            "width": width,
            "height": height,
            "generateParams": {"query": prompt},
        }
        files = {
            "pipeline_id": (None, pipeline_id),
            "params": (None, json.dumps(params), "application/json"),
        }
        logger.debug(f"[FusionBrainImage] submit_generation payload: pipeline_id={pipeline_id}, params={params}")
        try:
            resp = requests.post(url, headers=self.auth_headers, files=files, timeout=30)
            logger.debug(f"[FusionBrainImage] Ответ POST run: status={resp.status_code}, body={resp.text}")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[FusionBrainImage] Ошибка при отправке задачи генерации: {e}")
            raise

        try:
            request_id = data["uuid"]
            logger.debug(f"[FusionBrainImage] Получен request_id: {request_id}")
        except Exception as e:
            logger.error(f"[FusionBrainImage] Не удалось получить UUID задачи из ответа: {data} — {e}")
            raise

        return request_id

    def _poll_until_done(self, request_id: str, attempts: int = 20, delay: int = 5) -> list:
        status_url = f"{self.root_url}/key/api/v1/pipeline/status/{request_id}"
        logger.debug(f"[FusionBrainImage] Опрос статуса URL: {status_url}")
        for attempt in range(attempts):
            try:
                resp = requests.get(status_url, headers=self.auth_headers, timeout=10)
                logger.debug(f"[FusionBrainImage] Ответ GET status (attempt {attempt+1}): status={resp.status_code}, body={resp.text}")
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"[FusionBrainImage] Ошибка при проверке статуса (попытка {attempt+1}): {e}")
                raise

            status = data.get("status")
            logger.debug(f"[FusionBrainImage] Статус задачи: {status}")
            if status == "DONE":
                files = data.get("result", {}).get("files", [])
                if not files:
                    logger.error(f"[FusionBrainImage] Пустой список files в ответе: {data}")
                    raise ValueError("В ответе FusionBrain нет URL или Base64 для картинки")
                logger.debug(f"[FusionBrainImage] files: {files}")
                return files

            if status == "FAIL":
                logger.error(f"[FusionBrainImage] Статус задачи 'FAIL', ответ: {data}")
                raise RuntimeError("Задача FusionBrain завершилась с ошибкой")

            logger.debug(f"[FusionBrainImage] Задача не готова, ждем {delay} секунд...")
            time.sleep(delay)

        logger.error(f"[FusionBrainImage] Превышено число попыток проверки статуса ({attempts})")
        raise TimeoutError("Не удалось дождаться завершения задачи FusionBrain")

    def generate_image(self, prompt: str, model: Optional[str] = None) -> bytes:
        logger.info(f"[FusionBrainImage] Запрос генерации изображения по промпту: {prompt[:50]}...")
        try:
            pipeline_id = self._get_pipeline_id()
        except Exception as e:
            raise RuntimeError(f"Не удалось получить pipeline_id: {e}")

        try:
            request_id = self._submit_generation(prompt, pipeline_id, width=1024, height=1024)
        except Exception as e:
            raise RuntimeError(f"Ошибка при создании задачи: {e}")

        try:
            files = self._poll_until_done(request_id)
        except Exception as e:
            raise RuntimeError(f"Ошибка при ожидании завершения генерации: {e}")

        file_entry = files[0]
        logger.debug(f"[FusionBrainImage] Содержимое files[0]: {file_entry[:100]}{'...' if len(file_entry) > 100 else ''}")

        # Если file_entry — URL (начинается с http/https), скачиваем
        if file_entry.startswith("http://") or file_entry.startswith("https://"):
            logger.debug(f"[FusionBrainImage] Определено как URL, скачиваем: {file_entry}")
            try:
                resp_img = requests.get(file_entry, timeout=30)
                logger.debug(f"[FusionBrainImage] Ответ GET image: status={resp_img.status_code}")
                resp_img.raise_for_status()
                logger.info(f"[FusionBrainImage] Изображение успешно скачано, размер: {len(resp_img.content)} байт")
                return resp_img.content
            except Exception as e:
                logger.error(f"[FusionBrainImage] Ошибка при скачивании изображения с {file_entry}: {e}")
                raise

        # Иначе считаем, что это Base64-строка
        logger.debug("[FusionBrainImage] Определено как Base64-строка, декодируем")
        try:
            # Если строка содержит префикс data:image/...;base64,, убираем его
            if "," in file_entry and file_entry.lower().startswith("data:"):
                base64_data = file_entry.split(",", 1)[1]
            else:
                base64_data = file_entry
            image_bytes = base64.b64decode(base64_data, validate=True)
            logger.info(f"[FusionBrainImage] Изображение декодировано из Base64, размер: {len(image_bytes)} байт")
            return image_bytes
        except Exception as e:
            logger.error(f"[FusionBrainImage] Ошибка декодирования Base64: {e}")
            raise
