import sys
import os
# Добавляем корень проекта (project-root) в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from apscheduler.triggers.cron import CronTrigger
from src.scheduler.scheduler import Scheduler, publish_for_vk
from src.core.models import ScheduleConfig
from src.config.settings import settings


def test_schedule_added_and_removed(monkeypatch):
    """Проверяем, что Scheduler создаёт и удаляет задания APScheduler."""

    sched = ScheduleConfig(
        id="testjob",
        module="vk",
        cron="*/5 * * * *",
        enabled=True,
        prompt_key="post_intro",
    )

    monkeypatch.setattr(settings, "SCHEDULES", [sched])

    scheduler = Scheduler()

    job_id = f"vk_{sched.id}"
    job = scheduler.scheduler.get_job(job_id)
    assert job is not None
    assert isinstance(job.trigger, CronTrigger)
    assert "*/5" in str(job.trigger)

    scheduler.scheduler.remove_job(job_id)
    assert scheduler.scheduler.get_job(job_id) is None
    scheduler.shutdown()


def test_scheduler_registers_jobs(monkeypatch):
    """Проверяем, что Scheduler регистрирует задания из settings.SCHEDULES."""

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

    job_id = "vk_job1"
    job = scheduler.scheduler.get_job(job_id)
    assert job is not None
    # Остановим планировщик, чтобы не оставлять фоновые потоки
    scheduler.shutdown()


def test_publish_for_vk_no_tasks(monkeypatch):
    """Проверяем, что publish_for_vk ничего не делает без заданий."""
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
    publish_for_vk(fake_sched)
