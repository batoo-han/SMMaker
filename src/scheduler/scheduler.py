# src/scheduler/scheduler.py

"""
scheduler.py

Обёртка для APScheduler: по расписанию запускаются задачи для VK и Telegram.
Теперь отдельно выбираем:
  - text‐generator (ChatGPT или YandexGPT) в зависимости от schedule.generator
  - image‐generator (DALL·E или другие) в зависимости от settings.IMAGE_NETWORK
"""

import logging
from datetime import datetime
import pytz

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import settings
from src.sheets.sheets_client import SheetsClient
from src.core.models import ScheduleConfig, Post
from src.modules import get_publisher, get_generator
from src.vector_db.vector_client import VectorClient

logger = logging.getLogger(__name__)
MOSCOW_TZ = pytz.timezone("Europe/Moscow")


def publish_for_vk(schedule: ScheduleConfig):
    """
    Публикация для VK:
      1) Берём строку с status="ожидание" из листа VK_SHEETS_TAB.
      2) Определяем text_generator на основе schedule.generator:
           - "ChatGPT" или "YandexGPT"
      3) Определяем image_generator на основе settings.IMAGE_NETWORK (по умолчанию "openai").
      4) Генерируем текст и изображение.
      5) Публикуем в ВК.
      6) Обновляем Google Sheets (колонки B–G).
    """
    sheets = SheetsClient(
        credentials_json_path=settings.GOOGLE_CREDENTIALS_PATH,
        spreadsheet_name=settings.SHEETS_SPREADSHEET,
        sheet_name=settings.VK_SHEETS_TAB
    )
    post, row_idx = sheets.get_next_post()
    if not post:
        logger.info("[vk] Нет задач со статусом 'ожидание' в листе VK.")
        return

    topic = post.idea.strip()
    if not topic:
        logger.error(f"[vk] Пустая тема (row {row_idx}), пропускаем.")
        return

    # --- Получаем пример из ChromaDB ---
    try:
        vector_client = VectorClient(
            persist_directory=settings.CHROMA_PERSIST_DIR,
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_model=settings.OPENAI_EMBEDDING_MODEL
        )
        last_vk = vector_client.get_last_by_network("vk") or ""
    except Exception as e:
        logger.error(f"[vk] Ошибка доступа к ChromaDB: {e}")
        return

    # --- Загружаем шаблон промпта ---
    prompt_key = f"{schedule.prompt_key}_vk"
    template = settings.PROMPT_TEXTS.get(prompt_key) or settings.PROMPT_TEXTS.get(schedule.prompt_key, "")
    if not template:
        logger.error(f"[vk] Шаблон промпта '{prompt_key}' и '{schedule.prompt_key}' не найдены.")
        return

    # Подставляем {idea} и {example}
    prompt = template.replace("{idea}", topic).replace("{example}", last_vk)

    # --- Выбор text_generator ---
    ai_name = getattr(schedule, "generator", "ChatGPT")
    if ai_name.lower() in ("chatgpt", "openai"):
        text_model = settings.OPENAI_MODEL
        text_temperature = settings.OPENAI_TEMPERATURE
    elif ai_name.lower() in ("yandexgpt", "yandex"):
        text_model = settings.YANDEXGPT_MODEL
        text_temperature = settings.YANDEXGPT_TEMPERATURE
    else:
        logger.error(f"[vk] Неподдерживаемый текстовый генератор: {ai_name}")
        return

    try:
        generator = get_generator(ai_name)  # вернёт OpenAIGenerator или YandexGenerator
        article_text, article_meta = generator.generate_text(
            prompt=prompt,
            model=text_model,
            temperature=text_temperature
        )
    except Exception as e:
        logger.error(f"[vk] Ошибка генерации текста ({ai_name}, {text_model}): {e}")
        return

    # Разбираем заголовок + тело
    lines = article_text.splitlines()
    # if not lines or not lines[0].startswith("**") or not lines[0].endswith("**"):
    #     logger.error(f"[vk] Некорректный формат заголовка для row {row_idx}.")
    #     return
    title_line = lines[0]
    body_text = "\n".join(lines[1:]).strip()
    if not body_text:
        logger.error(f"[vk] Пустой текст статьи после заголовка для row {row_idx}.")
        return

    full_text = f"{title_line}\n\n{body_text}"

    # --- Генерация изображения ---
    image_network = settings.IMAGE_NETWORK.lower()  # например "openai" или позже "stable_diffusion"
    # По умолчанию пока поддерживаем только DALL·E (через OpenAI)
    image_model = settings.IMAGE_MODEL  # обычно "dall-e-3"
    try:
        image_generator = get_generator(image_network)
        image_bytes = image_generator.generate_image(
            prompt=template.replace("{idea}", topic).replace("{example}", last_vk),
            model=image_model
        )
    except Exception as e:
        logger.error(f"[vk] Ошибка генерации иллюстрации ({image_network}, {image_model}): {e}")
        return

    # --- Публикация в VK ---
    post.idea = full_text
    post.image_bytes = image_bytes

    try:
        publisher = get_publisher("vk")
        url = publisher.publish(post)
    except Exception as e:
        logger.error(f"[vk] Ошибка публикации: {e}")
        return

    if not url:
        logger.error(f"[vk] Публикация не удалась для row {row_idx}.")
        return

    # --- Обновляем Google Sheets (B–G), не трогая A ---
    msk_time = datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M:%S")
    post.status = "выполнено"
    post.scheduled = msk_time
    post.url = url
    post.ai = ai_name
    post.model = text_model
    post.notes = f"tokens={article_meta.get('tokens', 0)},cost={article_meta.get('cost', 0.0)}"

    try:
        sheets.update_post(row_idx, post)
        logger.info(f"[vk] Google Sheets: строка {row_idx} обновлена (status=выполнено, url={url}).")
    except Exception as e:
        logger.error(f"[vk] Ошибка обновления Google Sheets для row {row_idx}: {e}")


def publish_for_telegram(schedule: ScheduleConfig):
    """
    Публикация для Telegram:
      1) Берём строку с status="ожидание" из листа TG_SHEETS_TAB.
      2) Выбираем text_generator по schedule.generator (ChatGPT или YandexGPT).
      3) Выбираем image_generator по settings.IMAGE_NETWORK (по умолчанию "openai").
      4) Генерируем текст, разбираем заголовок+тело.
      5) Генерируем изображение, отправляем: сначала картинку, потом текст.
      6) Обновляем Google Sheets (B–G).
    """
    sheets = SheetsClient(
        credentials_json_path=settings.GOOGLE_CREDENTIALS_PATH,
        spreadsheet_name=settings.SHEETS_SPREADSHEET,
        sheet_name=settings.TG_SHEETS_TAB
    )
    post, row_idx = sheets.get_next_post()
    if not post:
        logger.info("[telegram] Нет задач со статусом 'ожидание' в листе Telegram.")
        return

    topic = post.idea.strip()
    if not topic:
        logger.error(f"[telegram] Пустая тема (row {row_idx}), пропускаем.")
        return

    try:
        vector_client = VectorClient(
            persist_directory=settings.CHROMA_PERSIST_DIR,
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_model=settings.OPENAI_EMBEDDING_MODEL
        )
        last_tg = vector_client.get_last_by_network("telegram") or ""
    except Exception as e:
        logger.error(f"[telegram] Ошибка доступа к ChromaDB: {e}")
        return

    prompt_key = f"{schedule.prompt_key}_telegram"
    template = settings.PROMPT_TEXTS.get(prompt_key) or settings.PROMPT_TEXTS.get(schedule.prompt_key, "")
    if not template:
        logger.error(f"[telegram] Шаблон промпта '{prompt_key}' и '{schedule.prompt_key}' не найдены.")
        return

    prompt = template.replace("{idea}", topic).replace("{example}", last_tg)

    # --- Выбор text_generator ---
    ai_name = getattr(schedule, "generator", "ChatGPT")
    if ai_name.lower() in ("chatgpt", "openai"):
        text_model = settings.OPENAI_MODEL
        text_temperature = settings.OPENAI_TEMPERATURE
    elif ai_name.lower() in ("yandexgpt", "yandex"):
        text_model = settings.YANDEXGPT_MODEL
        text_temperature = settings.YANDEXGPT_TEMPERATURE
    else:
        logger.error(f"[telegram] Неподдерживаемый текстовый генератор: {ai_name}")
        return

    try:
        generator = get_generator(ai_name)
        article_text, article_meta = generator.generate_text(
            prompt=prompt,
            model=text_model,
            temperature=text_temperature
        )
    except Exception as e:
        logger.error(f"[telegram] Ошибка генерации текста ({ai_name}, {text_model}): {e}")
        return

    lines = article_text.splitlines()
    # if not lines or not lines[0].startswith("**") or not lines[0].endswith("**"):
    #     logger.error(f"[telegram] Некорректный формат заголовка для row {row_idx}.")
    #     return
    title_line = lines[0]
    body_text = "\n".join(lines[1:]).strip()
    if not body_text:
        logger.error(f"[telegram] Пустой текст статьи после заголовка для row {row_idx}.")
        return

    full_text = f"{title_line}\n\n{body_text}"

    # --- Генерация изображения ---
    image_network = settings.IMAGE_NETWORK.lower()
    image_model = settings.IMAGE_MODEL
    try:
        image_generator = get_generator(image_network)
        image_bytes = image_generator.generate_image(
            prompt=template.replace("{idea}", topic).replace("{example}", last_tg),
            model=image_model
        )
    except Exception as e:
        logger.error(f"[telegram] Ошибка генерации иллюстрации ({image_network}, {image_model}): {e}")
        return

    # --- Публикация в Telegram: сначала фото, затем текст ---
    post.idea = full_text
    post.image_bytes = image_bytes

    try:
        publisher = get_publisher("telegram")
        url = publisher.publish(post)  # Вернёт URL текстового сообщения
    except Exception as e:
        logger.error(f"[telegram] Ошибка публикации: {e}")
        return

    if not url:
        logger.error(f"[telegram] Публикация не удалась для row {row_idx}.")
        return

    msk_time = datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M:%S")
    post.status = "выполнено"
    post.scheduled = msk_time
    post.url = url
    post.ai = ai_name
    post.model = text_model
    post.notes = f"tokens={article_meta.get('tokens', 0)},cost={article_meta.get('cost', 0.0)}"

    try:
        sheets.update_post(row_idx, post)
        logger.info(f"[telegram] Google Sheets: строка {row_idx} обновлена (status=выполнено, url={url}).")
    except Exception as e:
        logger.error(f"[telegram] Ошибка обновления Google Sheets для row {row_idx}: {e}")


class Scheduler:
    """
    Класс-обёртка над APScheduler для управления задачами из настроек и динамически.
    """
    def __init__(self):
        self.scheduler = BackgroundScheduler(
            jobstores={'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')}
        )

    def start(self):
        for sched in settings.SCHEDULES:
            module = sched.module.lower()
            if module == "vk" and settings.ENABLE_VK and sched.enabled:
                try:
                    trigger = CronTrigger.from_crontab(sched.cron)
                    self.scheduler.add_job(
                        publish_for_vk,
                        trigger=trigger,
                        args=[sched],
                        id=sched.id,
                        replace_existing=True
                    )
                    logger.info(f"[vk] Добавлено расписание: id={sched.id}, cron={sched.cron}")
                except Exception as e:
                    logger.error(f"[vk] Ошибка при добавлении расписания: {e}")

            if module == "telegram" and settings.ENABLE_TG and sched.enabled:
                try:
                    trigger = CronTrigger.from_crontab(sched.cron)
                    self.scheduler.add_job(
                        publish_for_telegram,
                        trigger=trigger,
                        args=[sched],
                        id=sched.id,
                        replace_existing=True
                    )
                    logger.info(f"[telegram] Добавлено расписание: id={sched.id}, cron={sched.cron}")
                except Exception as e:
                    logger.error(f"[telegram] Ошибка при добавлении расписания: {e}")

        self.scheduler.start()
        logger.info("Scheduler запущен.")

    def shutdown(self):
        self.scheduler.shutdown()
        logger.info("Scheduler остановлен.")
