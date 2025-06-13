# src/main.py

"""
main.py

Точка входа приложения. Настройка логирования и запуск Scheduler или немедленная обработка.
"""

import sys
import os
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from src.config.settings import settings
from src.scheduler.scheduler import Scheduler, publish_for_vk, publish_for_telegram


def setup_logging():
    """
    Настройка логирования:
      - Консоль (stdout) — уровень INFO и выше.
      - Файл logs/app.log — ротация каждую ночь, хранить 60 файлов.
    """
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(logs_dir, "app.log"),
        when="midnight",
        interval=1,
        backupCount=60,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("Logging настроен: console и файл logs/app.log (ротация 60 дней).")


def process_immediate():
    """
    Если нет активных расписаний — сразу запускаем публикацию для всех включённых модулей.
    """
    logger = logging.getLogger("main")
    logger.info("Нет активных расписаний публикации — запускаем немедленную обработку")

    # VK
    if settings.ENABLE_VK:
        vk_sched = next((s for s in settings.SCHEDULES if s.module.lower() == "vk" and s.enabled), None)
        if vk_sched:
            logger.info("[vk] Немедленная публикация для VK")
            try:
                publish_for_vk(vk_sched)
            except Exception as e:
                logger.error(f"[vk] Ошибка при немедленной публикации: {e}", exc_info=True)
        else:
            logger.info("[vk] Нет включённого расписания для VK — пропускаем")

    # Telegram
    if settings.ENABLE_TG:
        tg_sched = next((s for s in settings.SCHEDULES if s.module.lower() == "telegram" and s.enabled), None)
        if tg_sched:
            logger.info("[telegram] Немедленная публикация для Telegram")
            try:
                publish_for_telegram(tg_sched)
            except Exception as e:
                logger.error(f"[telegram] Ошибка при немедленной публикации: {e}", exc_info=True)
        else:
            logger.info("[telegram] Нет включённого расписания для Telegram — пропускаем")


def main():
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("Запуск приложения SMMaker")

    scheduler = Scheduler()

    has_vk_schedule = any(s.module.lower() == "vk" and s.enabled for s in settings.SCHEDULES)
    has_tg_schedule = any(s.module.lower() == "telegram" and s.enabled for s in settings.SCHEDULES)

    if has_vk_schedule or has_tg_schedule:
        logger.info("Найдены активные расписания — запускаем Scheduler")
        scheduler.start()
        try:
            while True:
                pass  # keep the scheduler running
        except (KeyboardInterrupt, SystemExit):
            logger.info("Остановка Scheduler по сигналу")
            scheduler.shutdown()
    else:
        process_immediate()


if __name__ == "__main__":
    main()
