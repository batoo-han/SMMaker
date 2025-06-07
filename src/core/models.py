# src/core/models.py

"""
models.py

Здесь собраны Pydantic-модели данных, используемые в проекте:

  1) ScheduleConfig  — конфигурация одного задания по расписанию
  2) Post            — объект, который отправляется «в сеть» (VK, Telegram и т.д.)
  3) VectorEntry     — единица данных для записи в векторную БД (ChromaDB)
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict


class ScheduleConfig(BaseModel):
    """
    Конфигурация одного «расписания» (задачи) для Scheduler.

    Атрибуты:
      - id: str                 — уникальное имя задания (например, "vk_morning_post")
      - module: str             — куда будет публиковаться ("vk" или "telegram")
      - cron: str               — cron-выражение (строка из 5 полей, e.g. "0 9 * * *")
      - prompt_key: str         — ключ шаблона в settings.PROMPT_TEXTS (например, "daily_vk")
      - generator: str          — имя текстового LLM для генерации текста ("ChatGPT", "YandexGPT" и т.п.)
      - image_generator: str    — имя картинного генератора для создания изображений ("fusionbrain", "dall-e" и т.п.)
      - enabled: bool           — включено ли задание (по умолчанию True)
    """
    id: str
    module: str
    cron: str
    prompt_key: str
    generator: str = "openai"
    image_generator: Optional[str] = None
    enabled: bool = True


class Post(BaseModel):
    """
    Модель данных «поста», который отправляем в социальную сеть.

    Атрибуты:
      - id: str                 — идентификатор (должен совпадать с ScheduleConfig.id)
      - title: str              — заголовок или имя поста (часто складывается из id и timestamp)
      - content: str            — сгенерированный текст
      - image_bytes: bytes      — байты изображения (PNG, JPEG)
      - metadata: Dict[str, str] — доп. данные (например, model, tokens, cost и т.д.)
    """
    id: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    image_bytes: Optional[bytes] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    # Fields used in Sheets tests
    idea: Optional[str] = None
    status: Optional[str] = None
    scheduled: Optional[str] = None
    socialnet: Optional[str] = None
    url: Optional[str] = None
    ai: Optional[str] = None
    model: Optional[str] = None
    notes: Optional[str] = None


class VectorEntry(BaseModel):
    """
    Модель записи в векторную базу (ChromaDB).

    Содержит:
      - id: str                 — идентификатор (можно взять из post.id или сгенерировать новый)
      - title: str              — заголовок поста (тот же, что и в Post)
      - content: str            — текст (используется для embedding)
      - created_at: datetime    — время добавления (по умолчанию now)
      - metadata: Dict[str, str] — любые доп. параметры (model, cost, tokens и т.д.)
      - network: str            — куда публиковали ("vk" или "telegram")
      - url: Optional[str]      — ссылка/ID опубликованного поста (если удалось получить)
    """
    id: str
    title: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, str] = Field(default_factory=dict)
    network: str
    url: Optional[str] = None
