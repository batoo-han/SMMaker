# src/scheduler/scheduler.py

"""
scheduler.py

Основной модуль планировщика. Использует APScheduler для запуска задач по расписанию.
Обрабатывает публикации для VK и Telegram, обновляет Google Sheets и сохраняет данные в VectorDB.
Публикация в любую сеть выполняется только если успешно сгенерированы и текст, и изображение.
"""

import logging
from datetime import datetime
import pytz

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import settings
from src.core.models import ScheduleConfig, Post
from src.modules import get_publisher, get_generator
from src.vector_db.vector_client import VectorClient
from src.sheets.sheets_client import SheetsClient

logger = logging.getLogger(__name__)

# Временная зона Московского времени
MOSCOW_TZ = pytz.timezone("Europe/Moscow")


def publish_for_vk(schedule: ScheduleConfig):
    """
    Публикация для VK: берёт первую строку со статусом "ожидание" из Google Sheets,
    генерирует текст и изображение, публикует во VK, сохраняет в VectorDB и обновляет
    строку в Google Sheets со всеми нужными полями, включая полную ссылку на пост.
    Публикация происходит только если и текст, и изображение успешно сгенерированы.
    """
    try:
        sheets = SheetsClient()
        row_idx, row_data = sheets.get_next_post(sheet_name=settings.VK_SHEETS_TAB)
        if row_idx is None or row_data is None:
            logger.info("[vk] Нет записей со status='ожидание'")
            return
    except Exception as e:
        logger.error(f"[vk] Ошибка доступа к Google Sheets: {e}", exc_info=True)
        return

    topic = row_data.get("idea", "").strip()
    if not topic:
        logger.error("[vk] В строке нет поля 'idea'")
        return

    # Получаем последний текст из VectorDB, чтобы использовать как пример
    try:
        vector_client = VectorClient(
            persist_directory=settings.CHROMA_PERSIST_DIR,
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_model=settings.OPENAI_EMBEDDING_MODEL,
        )
        last_vk = vector_client.get_last_by_network("vk") or ""
    except Exception as e:
        logger.error(f"[vk] Ошибка доступа к ChromaDB: {e}", exc_info=True)
        return

    # Формируем prompt по шаблону
    prompt_key_vk = f"{schedule.prompt_key}_vk"
    template = settings.PROMPT_TEXTS.get(prompt_key_vk) or settings.PROMPT_TEXTS.get(schedule.prompt_key, "")
    if not template:
        logger.error(f"[vk] Шаблон промпта '{prompt_key_vk}' и '{schedule.prompt_key}' не найдены.")
        return

    prompt = template.replace("{idea}", topic).replace("{example}", last_vk)

    # Выбираем текстовый генератор в зависимости от schedule.generator
    ai_name = getattr(schedule, "generator", "ChatGPT")
    ai_key = ai_name.strip().lower()
    if ai_key in ("chatgpt", "openai"):
        text_model = settings.OPENAI_MODEL
        text_temperature = settings.OPENAI_TEMPERATURE
        text_generator = get_generator("openai-text")
    elif ai_key in ("yandexgpt", "yandex"):
        text_model = settings.YANDEXGPT_MODEL
        text_temperature = settings.YANDEXGPT_TEMPERATURE
        text_generator = get_generator("yandex")
    else:
        logger.error(f"[vk] Неподдерживаемый текстовый генератор: {ai_name}")
        return

    # Генерируем текст
    try:
        generated_text, meta = text_generator.generate_text(
            prompt=prompt,
            model=text_model,
            temperature=text_temperature,
        )
    except Exception as e:
        logger.error(f"[vk] Ошибка при генерации текста: {e}", exc_info=True)
        return

    if not generated_text:
        logger.error("[vk] Генерация текста вернула пустой результат, публикация отменена")
        return

    # Выбираем генератор изображений
    image_prompt = generated_text
    image_network_key = settings.IMAGE_NETWORK.strip().lower()
    try:
        image_generator = get_generator(image_network_key)
    except ValueError:
        logger.error(f"[vk] Неподдерживаемый IMAGE_NETWORK: {settings.IMAGE_NETWORK}")
        return

    image_model = settings.IMAGE_MODEL
    try:
        image_bytes = image_generator.generate_image(
            prompt=image_prompt,
            model=image_model,
        )
    except Exception as e:
        logger.error(f"[vk] Ошибка при генерации изображения: {e}", exc_info=True)
        return

    if not image_bytes:
        logger.error("[vk] Генерация изображения вернула пустой результат, публикация отменена")
        return

    # Формируем объект Post и публикуем во VK
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
        publisher = get_publisher("vk")
        raw_vk_id = publisher.publish(post)  # Вернёт строку вида "<owner_id>_<post_id>"
        if not raw_vk_id:
            logger.error("[vk] Публикация вернула пустой URL/ID")
            return
        # Преобразуем "<owner_id>_<post_id>" в полную ссылку
        try:
            owner_id, post_id = raw_vk_id.split("_", 1)
            full_vk_url = f"https://vk.com/wall{owner_id}_{post_id}"
        except Exception:
            full_vk_url = raw_vk_id  # если не в формате, оставляем как есть
    except Exception as e:
        logger.error(f"[vk] Ошибка при публикации в VK: {e}", exc_info=True)
        return

    # Сохраняем запись в VectorDB
    try:
        vector_client.add_post(
            network="vk",
            post_id=post.id,
            text=generated_text,
            url=full_vk_url,
            metadata=post.metadata,
        )
    except Exception as e:
        logger.error(f"[vk] Ошибка при сохранении в VectorDB: {e}", exc_info=True)

    # Обновляем Google Sheets всеми необходимыми полями
    try:
        scheduled_str = datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M:%S")
        status = "выполнено"
        ai_used = ai_name
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
            notes=notes
        )
    except Exception as e:
        logger.error(f"[vk] Ошибка при обновлении Google Sheets: {e}", exc_info=True)


def publish_for_telegram(schedule: ScheduleConfig):
    """
    Публикация для Telegram: берёт первую строку со статусом "ожидание" из Google Sheets,
    генерирует текст и изображение, публикует в Telegram, сохраняет в VectorDB и обновляет
    строку в Google Sheets со всеми нужными полями, включая полную ссылку.
    Публикация происходит только если сгенерированы и текст, и изображение.
    """
    try:
        sheets = SheetsClient()
        row_idx, row_data = sheets.get_next_post(sheet_name=settings.TG_SHEETS_TAB)
        if row_idx is None or row_data is None:
            logger.info("[telegram] Нет записей со status='ожидание'")
            return
    except Exception as e:
        logger.error(f"[telegram] Ошибка доступа к Google Sheets: {e}", exc_info=True)
        return

    topic = row_data.get("idea", "").strip()
    if not topic:
        logger.error("[telegram] В строке нет поля 'idea'")
        return

    # Получаем последний текст из VectorDB
    try:
        vector_client = VectorClient(
            persist_directory=settings.CHROMA_PERSIST_DIR,
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_model=settings.OPENAI_EMBEDDING_MODEL,
        )
        last_tg = vector_client.get_last_by_network("telegram") or ""
    except Exception as e:
        logger.error(f"[telegram] Ошибка доступа к ChromaDB: {e}", exc_info=True)
        return

    # Формируем prompt по шаблону
    prompt_key_tg = f"{schedule.prompt_key}_telegram"
    template = settings.PROMPT_TEXTS.get(prompt_key_tg) or settings.PROMPT_TEXTS.get(schedule.prompt_key, "")
    if not template:
        logger.error(f"[telegram] Шаблон промпта '{prompt_key_tg}' и '{schedule.prompt_key}' не найдены.")
        return

    prompt = template.replace("{idea}", topic).replace("{example}", last_tg)

    # Выбираем текстовый генератор
    ai_name = getattr(schedule, "generator", "ChatGPT")
    ai_key = ai_name.strip().lower()
    if ai_key in ("chatgpt", "openai"):
        text_model = settings.OPENAI_MODEL
        text_temperature = settings.OPENAI_TEMPERATURE
        text_generator = get_generator("openai-text")
    elif ai_key in ("yandexgpt", "yandex"):
        text_model = settings.YANDEXGPT_MODEL
        text_temperature = settings.YANDEXGPT_TEMPERATURE
        text_generator = get_generator("yandex")
    else:
        logger.error(f"[telegram] Неподдерживаемый текстовый генератор: {ai_name}")
        return

    # Генерируем текст
    try:
        generated_text, meta = text_generator.generate_text(
            prompt=prompt,
            model=text_model,
            temperature=text_temperature,
        )
    except Exception as e:
        logger.error(f"[telegram] Ошибка при генерации текста: {e}", exc_info=True)
        return

    if not generated_text:
        logger.error("[telegram] Генерация текста вернула пустой результат, публикация отменена")
        return

    # Выбираем генератор изображений
    image_prompt = generated_text
    image_network_key = settings.IMAGE_NETWORK.strip().lower()
    try:
        image_generator = get_generator(image_network_key)
    except ValueError:
        logger.error(f"[telegram] Неподдерживаемый IMAGE_NETWORK: {settings.IMAGE_NETWORK}")
        return

    image_model = settings.IMAGE_MODEL
    try:
        image_bytes = image_generator.generate_image(
            prompt=image_prompt,
            model=image_model,
        )
    except Exception as e:
        logger.error(f"[telegram] Ошибка при генерации изображения: {e}", exc_info=True)
        return

    if not image_bytes:
        logger.error("[telegram] Генерация изображения вернула пустой результат, публикация отменена")
        return

    # Формируем Post и публикуем в Telegram
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
        publisher = get_publisher("telegram")
        raw_tg_id = publisher.publish(post)  # Вернёт message_id как строку
        if not raw_tg_id:
            logger.error("[telegram] Публикация вернула пустой URL/ID")
            return
        # Преобразуем message_id в полную ссылку
        tg_username = getattr(settings, "TG_CHAT_USERNAME", "").strip()
        if tg_username:
            full_tg_url = f"https://t.me/{tg_username}/{raw_tg_id}"
        else:
            full_tg_url = raw_tg_id
    except Exception as e:
        logger.error(f"[telegram] Ошибка при публикации в Telegram: {e}", exc_info=True)
        return

    # Сохраняем запись в VectorDB
    try:
        vector_client.add_post(
            network="telegram",
            post_id=post.id,
            text=generated_text,
            url=full_tg_url,
            metadata=post.metadata,
        )
    except Exception as e:
        logger.error(f"[telegram] Ошибка при сохранении в VectorDB: {e}", exc_info=True)

    # Обновляем Google Sheets всеми необходимыми полями
    try:
        scheduled_str = datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M:%S")
        status = "выполнено"
        ai_used = ai_name
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
            notes=notes
        )
    except Exception as e:
        logger.error(f"[telegram] Ошибка при обновлении Google Sheets: {e}", exc_info=True)


class Scheduler:
    """
    Обёртка над APScheduler: при инициализации создаёт расписания для всех активных задач
    из settings.SCHEDULES. Закрытие через shutdown().
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=MOSCOW_TZ)

        for schedule in settings.SCHEDULES:
            if not schedule.enabled:
                continue

            module_key = schedule.module.strip().lower()
            trigger = CronTrigger.from_crontab(schedule.cron, timezone=MOSCOW_TZ)

            if module_key == "vk":
                self.scheduler.add_job(
                    func=publish_for_vk,
                    trigger=trigger,
                    args=[schedule],
                    id=f"vk_{schedule.id}",
                    replace_existing=True
                )
                logger.info(f"[Scheduler] Добавлено задание VK '{schedule.id}' с cron '{schedule.cron}'")
            elif module_key == "telegram":
                self.scheduler.add_job(
                    func=publish_for_telegram,
                    trigger=trigger,
                    args=[schedule],
                    id=f"tg_{schedule.id}",
                    replace_existing=True
                )
                logger.info(f"[Scheduler] Добавлено задание Telegram '{schedule.id}' с cron '{schedule.cron}'")
            else:
                logger.warning(f"[Scheduler] Пропущено неизвестное module '{schedule.module}' в расписании '{schedule.id}'")

        # Запускаем планировщик
        self.scheduler.start()
        logger.info("[Scheduler] Планировщик запущен")

    def shutdown(self):
        """
        Останавливает APScheduler.
        """
        self.scheduler.shutdown()
        logger.info("[Scheduler] Планировщик остановлен")
