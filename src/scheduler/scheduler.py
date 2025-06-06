# src/scheduler/scheduler.py

"""
scheduler.py

Основной модуль планировщика. Использует APScheduler для запуска задач по расписанию.
Обрабатывает публикации для VK и Telegram, обновляет Google Sheets и сохраняет данные в VectorDB.

Теперь для генерации изображения используется отдельный шаблон из PROMPT_TEXTS:
  - Для каждого schedule.prompt_key ищем ключ "{prompt_key}_image" в PROMPT_TEXTS.
  - Если такой шаблон найден, подставляем туда {idea}.
  - Иначе используем сгенерированный текст в качестве промпта для изображения.
"""

import logging
from datetime import datetime
import pytz

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import settings
from src.core.models import ScheduleConfig, Post
from src.vector_db.vector_client import VectorClient
from src.sheets.sheets_client import SheetsClient

from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)
MOSCOW_TZ = pytz.timezone("Europe/Moscow")


def publish_for_vk(schedule: ScheduleConfig):
    module = "vk"
    try:
        sheets = SheetsClient()
        row_idx, row_data = sheets.get_next_post(sheet_name=settings.VK_SHEETS_TAB)
        if row_idx is None:
            logger.info(f"[{module}] Нет записей со status='ожидание'")
            return
    except Exception as e:
        logger.error(f"[{module}] Ошибка доступа к Google Sheets: {e}", exc_info=True)
        return

    topic = row_data.get("idea", "").strip()
    if not topic:
        logger.error(f"[{module}] В строке нет поля 'idea'")
        return

    try:
        vector_client = VectorClient(
            persist_directory=settings.CHROMA_PERSIST_DIR,
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_model=settings.OPENAI_EMBEDDING_MODEL,
        )
        last_vk = vector_client.get_last_by_network("vk") or ""
    except Exception as e:
        logger.error(f"[{module}] Ошибка доступа к ChromaDB: {e}", exc_info=True)
        return

    prompt_key_vk = f"{schedule.prompt_key}_vk"
    template = settings.PROMPT_TEXTS.get(prompt_key_vk) or settings.PROMPT_TEXTS.get(schedule.prompt_key, "")
    if not template:
        logger.error(f"[{module}] Шаблон '{prompt_key_vk}' и '{schedule.prompt_key}' не найдены.")
        return

    prompt = template.replace("{idea}", topic).replace("{example}", last_vk)

    text_key = schedule.generator.strip().lower()
    if text_key in ("chatgpt", "openai", "openai-text"):
        text_model = settings.OPENAI_MODEL
        text_temperature = settings.OPENAI_TEMPERATURE
    elif text_key in ("yandexgpt", "yandex"):
        text_model = settings.YANDEXGPT_MODEL
        text_temperature = settings.YANDEXGPT_TEMPERATURE
    else:
        logger.error(f"[{module}] Неподдерживаемый текстовый генератор: {schedule.generator}")
        return

    try:
        from src.modules import get_generator
        text_generator = get_generator(text_key)
    except ValueError as e:
        logger.error(f"[{module}] {e}", exc_info=True)
        return

    try:
        generated_text, meta = text_generator.generate_text(
            prompt=prompt,
            model=text_model,
            temperature=text_temperature,
        )
    except Exception as e:
        logger.error(f"[{module}] Ошибка при генерации текста: {e}", exc_info=True)
        return

    if not generated_text:
        logger.error(f"[{module}] Генерация текста вернула пустой результат, публикация отменена")
        return

    # Определяем промпт для изображения: ищем шаблон "{prompt_key}_image"
    image_prompt_key = f"{schedule.prompt_key}_vk_image"
    image_template = settings.PROMPT_TEXTS.get(image_prompt_key)
    if image_template:
        image_prompt = image_template.replace("{idea}", topic)
        logger.debug(f"[{module}] Использован шаблон для изображения: '{image_prompt_key}' → {image_prompt[:60]}...")
    else:
        image_prompt = generated_text
        logger.debug(f"[{module}] Шаблон для изображения не найден, используется сгенерированный текст")

    if schedule.image_generator:
        img_key = schedule.image_generator.strip().lower()
    else:
        img_key = settings.IMAGE_NETWORK.strip().lower()

    try:
        from src.modules import get_generator
        image_generator = get_generator(img_key)
    except ValueError as e:
        logger.error(f"[{module}] {e}", exc_info=True)
        return

    try:
        image_bytes = image_generator.generate_image(
            prompt=image_prompt,
            model=settings.IMAGE_MODEL,
        )
    except Exception as e:
        logger.error(f"[{module}] Ошибка при генерации изображения: {e}", exc_info=True)
        return

    if not image_bytes:
        logger.error(f"[{module}] Генерация изображения вернула пустой результат, публикация отменена")
        return


    # Уменьшаем изображение
    TARGET_WIDTH_VK = 640
    TARGET_HEIGHT_VK = 480

    logger.debug(f"[{module}] Уменьшаем изображение")
    orig_img = Image.open(BytesIO(image_bytes))
    orig_img.thumbnail((TARGET_WIDTH_VK, TARGET_HEIGHT_VK), Image.LANCZOS)
    buf = BytesIO()
    orig_img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    image_bytes = buf.read()

    post = Post(
        id=schedule.id,
        title=f"{schedule.id}_{datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')}",
        content=generated_text,
        image_bytes=image_bytes,
        metadata={
            "model": text_model,
            "tokens": str(meta.get("tokens", "")),
            "cost": str(meta.get("cost", "")),
        },
    )

    try:
        from src.modules import get_publisher
        publisher = get_publisher("vk")
        raw_vk_id = publisher.publish(post)
        if not raw_vk_id:
            logger.error(f"[{module}] Публикация вернула пустой ID")
            return
        owner_id, post_id = raw_vk_id.split("_", 1)
        full_vk_url = f"https://vk.com/wall{owner_id}_{post_id}"
    except Exception as e:
        logger.error(f"[{module}] Ошибка при публикации в VK: {e}", exc_info=True)
        return

    try:
        vector_client.add_post(
            network="vk",
            post_id=post.id,
            text=generated_text,
            url=full_vk_url,
            metadata=post.metadata,
        )
    except Exception as e:
        logger.error(f"[{module}] Ошибка при сохранении в VectorDB: {e}", exc_info=True)

    try:
        scheduled_str = datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M:%S")
        status = "выполнено"
        ai_used = schedule.generator
        model_used = text_model
        tokens = meta.get("tokens", "")
        cost = meta.get("cost", "")
        notes = f"tokens={tokens},cost={cost}"

        sheets.update_post_status_and_meta(
            sheet_name=settings.VK_SHEETS_TAB,
            row_index=row_idx,
            status=status,
            scheduled=scheduled_str,
            url=full_vk_url,
            ai=ai_used,
            model=model_used,
            notes=notes,
        )
    except Exception as e:
        logger.error(f"[{module}] Ошибка при обновлении Google Sheets: {e}", exc_info=True)


def publish_for_telegram(schedule: ScheduleConfig):
    module = "telegram"
    try:
        sheets = SheetsClient()
        row_idx, row_data = sheets.get_next_post(sheet_name=settings.TG_SHEETS_TAB)
        if row_idx is None:
            logger.info(f"[{module}] Нет записей со status='ожидание'")
            return
    except Exception as e:
        logger.error(f"[{module}] Ошибка доступа к Google Sheets: {e}", exc_info=True)
        return

    topic = row_data.get("idea", "").strip()
    if not topic:
        logger.error(f"[{module}] В строке нет поля 'idea'")
        return

    try:
        vector_client = VectorClient(
            persist_directory=settings.CHROMA_PERSIST_DIR,
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_model=settings.OPENAI_EMBEDDING_MODEL,
        )
        last_tg = vector_client.get_last_by_network("telegram") or ""
    except Exception as e:
        logger.error(f"[{module}] Ошибка доступа к ChromaDB: {e}", exc_info=True)
        return

    prompt_key_tg = f"{schedule.prompt_key}_telegram"
    template = settings.PROMPT_TEXTS.get(prompt_key_tg) or settings.PROMPT_TEXTS.get(schedule.prompt_key, "")
    if not template:
        logger.error(f"[{module}] Шаблон '{prompt_key_tg}' и '{schedule.prompt_key}' не найдены.")
        return

    prompt = template.replace("{idea}", topic).replace("{example}", last_tg)

    text_key = schedule.generator.strip().lower()
    if text_key in ("chatgpt", "openai", "openai-text"):
        text_model = settings.OPENAI_MODEL
        text_temperature = settings.OPENAI_TEMPERATURE
    elif text_key in ("yandexgpt", "yandex"):
        text_model = settings.YANDEXGPT_MODEL
        text_temperature = settings.YANDEXGPT_TEMPERATURE
    else:
        logger.error(f"[{module}] Неподдерживаемый текстовый генератор: {schedule.generator}")
        return

    try:
        from src.modules import get_generator
        text_generator = get_generator(text_key)
    except ValueError as e:
        logger.error(f"[{module}] {e}", exc_info=True)
        return

    try:
        generated_text, meta = text_generator.generate_text(
            prompt=prompt,
            model=text_model,
            temperature=text_temperature,
        )
    except Exception as e:
        logger.error(f"[{module}] Ошибка при генерации текста: {e}", exc_info=True)
        return

    if not generated_text:
        logger.error(f"[{module}] Генерация текста вернула пустой результат, публикация отменена")
        return

    image_prompt_key = f"{schedule.prompt_key}_telegram_image"
    image_template = settings.PROMPT_TEXTS.get(image_prompt_key)
    if image_template:
        image_prompt = image_template.replace("{idea}", topic)
        logger.debug(f"[{module}] Использован шаблон для изображения: '{image_prompt_key}' → {image_prompt[:60]}...")
    else:
        image_prompt = generated_text
        logger.debug(f"[{module}] Шаблон для изображения не найден, используется сгенерированный текст")

    if schedule.image_generator:
        img_key = schedule.image_generator.strip().lower()
    else:
        img_key = settings.IMAGE_NETWORK.strip().lower()

    try:
        from src.modules import get_generator
        image_generator = get_generator(img_key)
    except ValueError as e:
        logger.error(f"[{module}] {e}", exc_info=True)
        return

    try:
        image_bytes = image_generator.generate_image(
            prompt=image_prompt,
            model=settings.IMAGE_MODEL,
        )
    except Exception as e:
        logger.error(f"[{module}] Ошибка при генерации изображения: {e}", exc_info=True)
        return

    if not image_bytes:
        logger.error(f"[{module}] Генерация изображения вернула пустой результат, публикация отменена")
        return

    # Уменьшаем изображение
    TARGET_WIDTH_TG = 640
    TARGET_HEIGHT_TG = 480

    logger.debug(f"[{module}] Уменьшаем изображение")
    orig_img = Image.open(BytesIO(image_bytes))
    orig_img.thumbnail((TARGET_WIDTH_TG, TARGET_HEIGHT_TG), Image.LANCZOS)
    buf = BytesIO()
    orig_img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    image_bytes = buf.read()

    post = Post(
        id=schedule.id,
        title=f"{schedule.id}_{datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')}",
        content=generated_text,
        image_bytes=image_bytes,
        metadata={
            "model": text_model,
            "tokens": str(meta.get("tokens", "")),
            "cost": str(meta.get("cost", "")),
        },
    )

    try:
        from src.modules import get_publisher
        publisher = get_publisher("telegram")
        raw_tg_id = publisher.publish(post)
        if not raw_tg_id:
            logger.error(f"[{module}] Публикация вернула пустой ID")
            return
        tg_username = getattr(settings, "TG_CHAT_USERNAME", "").strip()
        if tg_username:
            full_tg_url = f"https://t.me/{tg_username}/{raw_tg_id}"
        else:
            full_tg_url = raw_tg_id
    except Exception as e:
        logger.error(f"[{module}] Ошибка при публикации в Telegram: {e}", exc_info=True)
        return

    try:
        vector_client.add_post(
            network="telegram",
            post_id=post.id,
            text=generated_text,
            url=full_tg_url,
            metadata=post.metadata,
        )
    except Exception as e:
        logger.error(f"[{module}] Ошибка при сохранении в VectorDB: {e}", exc_info=True)

    try:
        scheduled_str = datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M:%S")
        status = "выполнено"
        ai_used = schedule.generator
        model_used = text_model
        tokens = meta.get("tokens", "")
        cost = meta.get("cost", "")
        notes = f"tokens={tokens},cost={cost}"

        sheets.update_post_status_and_meta(
            sheet_name=settings.TG_SHEETS_TAB,
            row_index=row_idx,
            status=status,
            scheduled=scheduled_str,
            url=full_tg_url,
            ai=ai_used,
            model=model_used,
            notes=notes,
        )
    except Exception as e:
        logger.error(f"[{module}] Ошибка при обновлении Google Sheets: {e}", exc_info=True)


def publish_job(schedule: ScheduleConfig):
    """Вызывает функцию публикации в зависимости от типа модуля."""
    module_key = schedule.module.strip().lower()
    if module_key == "vk":
        publish_for_vk(schedule)
    elif module_key == "telegram":
        publish_for_telegram(schedule)


class Scheduler:
    """
    Обёртка над APScheduler: при инициализации создаёт расписания для всех активных задач
    из settings.SCHEDULES.
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=MOSCOW_TZ)

    def start(self):
        """Регистрирует задания из settings и запускает планировщик."""
        for schedule in settings.SCHEDULES:
            if not schedule.enabled:
                continue
            self.add_schedule(schedule)
        self.scheduler.start()
        logger.info("[Scheduler] Планировщик запущен")

    def add_schedule(self, schedule: ScheduleConfig):
        trigger = CronTrigger.from_crontab(schedule.cron, timezone=MOSCOW_TZ)
        module_key = schedule.module.strip().lower()
        job_id = schedule.id

        if module_key == "vk":
            func = publish_for_vk
        elif module_key == "telegram":
            func = publish_for_telegram
        else:
            logger.warning(
                f"[Scheduler] Пропущено неизвестное module '{schedule.module}' в расписании '{schedule.id}'"
            )
            return

        self.scheduler.add_job(
            func=func,
            trigger=trigger,
            args=[schedule],
            id=job_id,
            replace_existing=True,
        )

    def remove_schedule(self, schedule_id: str):
        self.scheduler.remove_job(schedule_id)

    def shutdown(self):
        """
        Останавливает APScheduler.
        """
        self.scheduler.shutdown()
        logger.info("[Scheduler] Планировщик остановлен")
