import sys
import os
# Добавляем корень проекта (project-root) в PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.insert(0, os.path.join(project_root, 'stubs'))

import pytest
from apscheduler.triggers.cron import CronTrigger
from src.scheduler.scheduler import Scheduler, publish_job
from src.core.models import ScheduleConfig
from src.config.settings import settings


def test_add_and_remove_schedule():
    """
    Проверяем, что методы add_schedule и remove_schedule
    корректно добавляют и удаляют задачу из APScheduler.
    """
    scheduler = Scheduler()
    # Изначально список задач пуст
    assert scheduler.scheduler.get_jobs() == []

    # Создаём тестовый ScheduleConfig
    sched = ScheduleConfig(
        id="testjob",
        module="vk",
        cron="*/5 * * * *",  # раз в 5 минут
        enabled=True,
        prompt_key="post_intro"
    )

    # Добавляем задачу
    scheduler.add_schedule(sched)
    job = scheduler.scheduler.get_job("testjob")
    assert job is not None
    # Проверяем, что триггер задачи — это CronTrigger
    trigger = job.trigger
    assert isinstance(trigger, CronTrigger)
    # Проверяем, что в представлении триггера есть нужная часть "*/5"
    assert "*/5" in str(trigger)

    # Удаляем задачу
    scheduler.remove_schedule("testjob")
    job = scheduler.scheduler.get_job("testjob")
    assert job is None


def test_start_registers_jobs(monkeypatch):
    """
    Проверяем, что при вызове start() задачи из settings.SCHEDULES регистрируются.
    """
    # Подменим список расписаний в настройках
    monkeypatch.setattr(
        settings,
        "SCHEDULES",
        [
            ScheduleConfig(
                id="job1",
                module="vk",
                cron="*/1 * * * *",  # каждую минуту
                enabled=True,
                prompt_key="post_intro"
            )
        ]
    )

    scheduler = Scheduler()
    scheduler.start()

    # Проверяем, что задача появилась в планировщике
    job = scheduler.scheduler.get_job("job1")
    assert job is not None
    # Остановим планировщик, чтобы не оставлять фоновые потоки
    scheduler.shutdown()


def test_publish_job_no_tasks(monkeypatch):
    """
    Проверяем, что publish_job ничего не делает, если в Google Sheets нет записей со статусом 'ожидание'.
    Для этого подменим SheetsClient.get_next_post, чтобы он всегда возвращал (None, None).
    """
    # Подменяем SheetsClient.get_next_post
    monkeypatch.setattr(
        "src.scheduler.scheduler.SheetsClient.get_next_post",
        lambda self: (None, None)
    )

    fake_sched = ScheduleConfig(
        id="no_task_job",
        module="vk",
        cron="*/1 * * * *",
        enabled=True,
        prompt_key="post_intro"
    )
    # Должно пройти без исключений
    publish_job(fake_sched)
