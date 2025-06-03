# src/config/settings.py

"""
settings.py

Конфигурация проекта SMMaker:
  - Настройки для Google Sheets (отдельные листы VK и TG).
  - Параметры для OpenAI и YandexGPT.
  - Настройки генерации изображений.
  - Токены и ID для VK, TG.
  - Настройки ChromaDB.
  - Загрузка prompts и schedules из YAML (если потребуется).
"""

import os
from typing import Dict, List, Optional
from pathlib import Path

import yaml
# Pydantic v2: BaseSettings импорт из pydantic_settings
try:
    from pydantic_settings import BaseSettings
except ImportError as e:
    raise ImportError(
        "Для корректной работы нужно установить пакет 'pydantic-settings'. "
        "Выполните: pip install pydantic-settings"
    ) from e

from pydantic import Field

from src.core.models import ScheduleConfig

class Settings(BaseSettings):
    # 1) Google Sheets
    GOOGLE_CREDENTIALS_PATH: str = Field(..., env='GOOGLE_CREDENTIALS_PATH')
    SHEETS_SPREADSHEET: str = Field(..., env='SHEETS_SPREADSHEET')
    VK_SHEETS_TAB: str = Field(..., env='VK_SHEETS_TAB')
    TG_SHEETS_TAB: str = Field(..., env='TG_SHEETS_TAB')

    # 2) Соцсети: токены и идентификаторы
    VK_TOKEN: Optional[str] = Field(None, env='VK_TOKEN')
    VK_OWNER_ID: Optional[int] = Field(None, env='VK_OWNER_ID')
    TG_TOKEN: Optional[str] = Field(None, env='TG_TOKEN')
    TG_CHAT_ID: Optional[str] = Field(None, env='TG_CHAT_ID')

    # 3) Включение/отключение публикаций
    ENABLE_VK: bool = Field(True, env='ENABLE_VK')
    ENABLE_TG: bool = Field(False, env='ENABLE_TG')

    # 4) Параметры генерации текста (OpenAI + Yandex)
    OPENAI_API_KEY: str = Field(..., env='OPENAI_API_KEY')
    OPENAI_MODEL: str = Field('gpt-4o', env='OPENAI_MODEL')
    OPENAI_TEMPERATURE: float = Field(0.7, env='OPENAI_TEMPERATURE')

    YANDEX_API_KEY: str = Field(..., env='YANDEX_API_KEY')
    YANDEX_CLOUD_FOLDER_ID: str = Field(..., env='YANDEX_CLOUD_FOLDER_ID')
    YANDEXGPT_MODEL: str = Field('sberbank-ai/stablelm', env='YANDEXGPT_MODEL')
    YANDEXGPT_TEMPERATURE: float = Field(0.6, env='YANDEXGPT_TEMPERATURE')

    # 5) Генерация изображений
    IMAGE_NETWORK: str = Field('openai', env='IMAGE_NETWORK')
    IMAGE_MODEL: str = Field('dall-e-3', env='IMAGE_MODEL')

    # 6) ChromaDB
    CHROMA_PERSIST_DIR: str = Field('.chroma_db', env='CHROMA_PERSIST_DIR')
    CHROMA_COLLECTION_NAME: str = Field('smm_posts', env='CHROMA_COLLECTION_NAME')
    OPENAI_EMBEDDING_MODEL: str = Field('text-embedding-ada-002', env='OPENAI_EMBEDDING_MODEL')

    # 7) Путь к YAML-конфигу (для prompts и schedules)
    CONFIG_YAML_PATH: str = Field('config.yaml', env='CONFIG_YAML_PATH')

    # 8) После инициализации будут загружены из YAML
    PROMPT_TEXTS: Dict[str, str] = {}
    SCHEDULES: List[ScheduleConfig] = []

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        extra = 'ignore'  # незнакомые переменные окружения игнорируем

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Проверяем обязательные параметры
        missing = []
        if not self.GOOGLE_CREDENTIALS_PATH:
            missing.append('GOOGLE_CREDENTIALS_PATH')
        if not self.SHEETS_SPREADSHEET:
            missing.append('SHEETS_SPREADSHEET')
        if not self.VK_SHEETS_TAB:
            missing.append('VK_SHEETS_TAB')
        if not self.TG_SHEETS_TAB:
            missing.append('TG_SHEETS_TAB')
        if not self.OPENAI_API_KEY:
            missing.append('OPENAI_API_KEY')
        if not self.YANDEX_API_KEY:
            missing.append('YANDEX_API_KEY')
        if not self.YANDEX_CLOUD_FOLDER_ID:
            missing.append('YANDEX_CLOUD_FOLDER_ID')
        if missing:
            raise ValueError(f"Отсутствуют обязательные настройки: {', '.join(missing)}")

        # Если VK включён, но нет VK_TOKEN или VK_OWNER_ID
        if self.ENABLE_VK:
            if not self.VK_TOKEN or self.VK_OWNER_ID is None:
                raise ValueError("Для публикации в VK нужно задать VK_TOKEN и VK_OWNER_ID")

        # Если TG включён, но нет TG_TOKEN или TG_CHAT_ID
        if self.ENABLE_TG:
            if not self.TG_TOKEN or not self.TG_CHAT_ID:
                raise ValueError("Для публикации в Telegram нужно задать TG_TOKEN и TG_CHAT_ID")

        # Загружаем prompts и schedules из config.yaml
        yaml_path = Path(self.CONFIG_YAML_PATH)
        if yaml_path.exists():
            data = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
            prompts = data.get('prompts', {})
            if isinstance(prompts, dict):
                self.PROMPT_TEXTS = prompts
            schedules_raw = data.get('schedules', [])
            parsed = []
            for item in schedules_raw:
                try:
                    parsed.append(ScheduleConfig(**item))
                except Exception:
                    continue
            self.SCHEDULES = parsed

# Единственный экземпляр настроек
settings = Settings()
