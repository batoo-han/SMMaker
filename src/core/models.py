# src/core/models.py

"""
models.py

Определения Pydantic-моделей данных для проекта: Post, ScheduleConfig и других.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict


class ScheduleConfig(BaseModel):
    """
    Конфигурация одного задания в Scheduler.
    Поля:
      - id: уникальный идентификатор джобы
      - module: имя модуля соцсети (e.g. 'vk', 'telegram')
      - cron: cron-строка для APScheduler
      - enabled: включено ли задание
      - prompt_key: ключ шаблона промпта из config.yaml
      - generator: имя LLM ('ChatGPT' или 'YandexGPT') — по умолчанию 'ChatGPT'
    """
    id: str = Field(..., description="ID задания в планировщике")
    module: str = Field(..., description="Модуль соцсети")
    cron: str = Field(..., description="Cron-выражение для расписания")
    enabled: bool = Field(True, description="Включено ли расписание")
    prompt_key: str = Field(..., description="Ключ шаблона промпта")
    generator: Optional[str] = Field("ChatGPT", description="LLM для генерации текста")


class Post(BaseModel):
    """
    Модель данных задачи публикации (операции над одной строкой Google Sheets).
    Поля соответствуют колонкам таблицы + служебные:
      - idea: тема/заголовок (колонка A)
      - status: статус выполнения (колонка B)
      - scheduled: время публикации (МСK, колонка C)
      - url: ссылка на опубликованный пост (колонка D)
      - ai: имя LLM, использованной для генерации (B–E; колонка E)
      - model: модель LLM, использованная (колонка F)
      - notes: дополнительные заметки (e.g. токены/стоимость; колонка G)
      - image_bytes: байты иллюстрации (не сохраняется в таблице, но нужен для publish)
    """
    idea: str
    status: Optional[str] = None
    scheduled: Optional[str] = None
    url: Optional[str] = None
    ai: Optional[str] = None
    model: Optional[str] = None
    notes: Optional[str] = None

    # Служебное поле для байтов изображения (не записывается в Google Sheets)
    image_bytes: Optional[bytes] = None


class VectorEntry(BaseModel):
    """
    Модель записи в векторную БД.
    Поля:
      - id: уникальный идентификатор (uuid или строка)
      - title: заголовок статьи
      - content: текст статьи
      - created_at: дата добавления
      - metadata: дополнительные данные (модель, токены, cost)
    """
    id: str
    title: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, str] = Field(default_factory=dict)
