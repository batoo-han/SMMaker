# src/config/settings.py

"""
settings.py

Конфигурация проекта SMMaker:
  - Настройки для Google Sheets (листы VK и TG).
  - Параметры для OpenAI и YandexGPT (генерация текста).
  - Настройки генерации изображений (DALL·E, FusionBrain).
  - Токены и ID для VK, TG.
  - Настройки ChromaDB.
  - Параметры кэша и VK-статистики.
  - Загрузка prompts и schedules из YAML (config.yaml).
"""

import os
from typing import Dict, List, Optional
from pathlib import Path

import yaml
# Pydantic v2: BaseSettings теперь в пакете pydantic_settings
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
    # ----------------------------------------
    # 1) Google Sheets
    # ----------------------------------------
    GOOGLE_CREDENTIALS_PATH: str = Field(..., env="GOOGLE_CREDENTIALS_PATH")
    SHEETS_SPREADSHEET: str = Field(..., env="SHEETS_SPREADSHEET")
    VK_SHEETS_TAB: str = Field(..., env="VK_SHEETS_TAB")
    TG_SHEETS_TAB: str = Field(..., env="TG_SHEETS_TAB")

    # ----------------------------------------
    # 2) Соцсети: токены и идентификаторы
    # ----------------------------------------
    VK_TOKEN: Optional[str] = Field(None, env="VK_TOKEN")
    VK_OWNER_ID: Optional[int] = Field(None, env="VK_OWNER_ID")
    TG_TOKEN: Optional[str] = Field(None, env="TG_TOKEN")
    TG_CHAT_ID: Optional[str] = Field(None, env="TG_CHAT_ID")
    TG_CHAT_USERNAME: Optional[str] = Field("", env="TG_CHAT_USERNAME")

    # ----------------------------------------
    # 3) Включение/отключение публикаций
    # ----------------------------------------
    ENABLE_VK: bool = Field(True, env="ENABLE_VK")
    ENABLE_TG: bool = Field(False, env="ENABLE_TG")

    # ----------------------------------------
    # 4) Параметры генерации текста (OpenAI + Yandex)
    # ----------------------------------------
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field("gpt-4o", env="OPENAI_MODEL")
    OPENAI_TEMPERATURE: float = Field(0.7, env="OPENAI_TEMPERATURE")

    YANDEX_API_KEY: str = Field(..., env="YANDEX_API_KEY")
    YANDEX_CLOUD_FOLDER_ID: str = Field(..., env="YANDEX_CLOUD_FOLDER_ID")
    YANDEXGPT_MODEL: str = Field("sberbank-ai/stablelm", env="YANDEXGPT_MODEL")
    YANDEXGPT_TEMPERATURE: float = Field(0.6, env="YANDEXGPT_TEMPERATURE")

    # ----------------------------------------
    # 5) Генерация изображений
    # ----------------------------------------
    IMAGE_NETWORK: str = Field("openai", env="IMAGE_NETWORK")
    IMAGE_MODEL: str = Field("dall-e-3", env="IMAGE_MODEL")

    # --- Новые поля для FusionBrain ---
    FUSIONBRAIN_API_KEY: Optional[str] = Field(None, env="FUSIONBRAIN_API_KEY")
    FUSIONBRAIN_API_SECRET: str = Field(..., env="FUSIONBRAIN_API_SECRET")
    FUSIONBRAIN_API_BASE_URL: str = Field(
        "https://api.fusionbrain.ai/v1", env="FUSIONBRAIN_API_BASE_URL"
    )
    FUSIONBRAIN_DEFAULT_MODEL: str = Field(
        "stable-diffusion-1", env="FUSIONBRAIN_DEFAULT_MODEL"
    )

    # ----------------------------------------
    # 6) ChromaDB / VectorDB
    # ----------------------------------------
    CHROMA_PERSIST_DIR: str = Field(".chroma_db", env="CHROMA_PERSIST_DIR")
    CHROMA_COLLECTION_NAME: str = Field("smm_posts", env="CHROMA_COLLECTION_NAME")
    OPENAI_EMBEDDING_MODEL: str = Field("text-embedding-ada-002", env="OPENAI_EMBEDDING_MODEL")

    # ----------------------------------------
    # 7) Кэширование
    # ----------------------------------------
    CACHE_MAXSIZE: int = Field(256, env="CACHE_MAXSIZE")
    CACHE_TTL: int = Field(600, env="CACHE_TTL")

    # ----------------------------------------
    # 8) VK-статистика
    # ----------------------------------------
    ENABLE_VK_STATS: bool = Field(False, env="ENABLE_VK_STATS")
    VK_STATS_DB_PATH: str = Field("stats/", env="VK_STATS_DB_PATH")
    VK_STATS_CRON: str = Field("0 21 * * *", env="VK_STATS_CRON")

    # ----------------------------------------
    # 9) Путь к YAML-конфигу (для prompts и schedules)
    # ----------------------------------------
    CONFIG_YAML_PATH: str = Field("config.yaml", env="CONFIG_YAML_PATH")

    # ----------------------------------------
    # 10) После инициализации будут загружены из YAML
    # ----------------------------------------
    PROMPT_TEXTS: Dict[str, str] = Field(default_factory=dict)
    SCHEDULES: List[ScheduleConfig] = Field(default_factory=list)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # незнакомые переменные окружения игнорируем

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 1) Проверка обязательных параметров Google Sheets
        missing = []
        if not self.GOOGLE_CREDENTIALS_PATH:
            missing.append("GOOGLE_CREDENTIALS_PATH")
        if not self.SHEETS_SPREADSHEET:
            missing.append("SHEETS_SPREADSHEET")
        if not self.VK_SHEETS_TAB:
            missing.append("VK_SHEETS_TAB")
        if not self.TG_SHEETS_TAB:
            missing.append("TG_SHEETS_TAB")

        # 2) Проверка обязательных параметров для генерации текста
        if not self.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if not self.YANDEX_API_KEY:
            missing.append("YANDEX_API_KEY")
        if not self.YANDEX_CLOUD_FOLDER_ID:
            missing.append("YANDEX_CLOUD_FOLDER_ID")

        # 3) Если выбран FusionBrain в IMAGE_NETWORK, проверяем API-ключ
        if self.IMAGE_NETWORK.lower() == "fusionbrain" and not self.FUSIONBRAIN_API_KEY:
            missing.append("FUSIONBRAIN_API_KEY")

        if missing:
            raise ValueError(f"Отсутствуют обязательные настройки: {missing}")

        # 4) Загрузка prompts и schedules из YAML (config.yaml)
        yaml_path = Path(self.CONFIG_YAML_PATH)
        if yaml_path.exists():
            try:
                data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                prompts = data.get("prompts", {})
                if isinstance(prompts, dict):
                    self.PROMPT_TEXTS = prompts
                schedules_raw = data.get("schedules", [])
                parsed: List[ScheduleConfig] = []
                for item in schedules_raw:
                    try:
                        parsed.append(ScheduleConfig(**item))
                    except Exception:
                        continue
                self.SCHEDULES = parsed
            except Exception:
                # Игнорируем ошибки парсинга YAML, если файл повреждён
                pass


# Единственный глобальный экземпляр настроек
settings = Settings()
