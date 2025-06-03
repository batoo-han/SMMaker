# src/modules/vk/vk_stats_collector.py

"""
vk_stats_collector.py

Модуль для сбора статистики VK-постов и сохранения её в SQLite.

Структура базы данных (SQLite):
  - posts: хранит посты, опубликованные через наш паблишер:
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      post_id      INTEGER NOT NULL,  -- атомарный ID поста VK (без owner_id)
      owner_id     INTEGER NOT NULL,  -- ID владельца стены (например, -123456789)
      published_at TEXT NOT NULL      -- время публикации (ISO-строка)

  - stats: хранит исторические метрики для каждого поста:
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      post_id       INTEGER NOT NULL,    -- соответствует полю post_id из posts
      collected_at  TEXT NOT NULL,       -- время сбора статистики (ISO-строка UTC)
      views         INTEGER,
      likes         INTEGER,
      comments      INTEGER,
      reposts       INTEGER,
      FOREIGN KEY(post_id) REFERENCES posts(post_id)

Функции:
  - init_db(): создание БД и таблиц, если их ещё нет.
  - register_post(post_id: int, owner_id: int, published_at: str): добавить новый пост в таблицу posts.
  - collect_stats(): обходит все записи из posts, запрашивает у VK API актуальные метрики
                     через VKStats, после чего записывает их в таблицу stats.
"""

import os
import sqlite3
import logging
from datetime import datetime

from src.modules.vk.vk_stats import VKStats
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Пути к файлу SQLite. Можно вынести в settings, но по умолчанию храним рядом с проектом.
DB_DIR = os.path.join(os.getcwd(), "data")
DB_PATH = os.path.join(DB_DIR, "vk_stats.db")


def init_db() -> None:
    """
    Создаёт (если не существует) директорию для БД и сам файл SQLite с нужными таблицами.
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица для опубликованных постов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        owner_id INTEGER NOT NULL,
        published_at TEXT NOT NULL
    );
    """)

    # Таблица для хранения статистики
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        collected_at TEXT NOT NULL,
        views INTEGER,
        likes INTEGER,
        comments INTEGER,
        reposts INTEGER,
        FOREIGN KEY(post_id) REFERENCES posts(post_id)
    );
    """)

    conn.commit()
    conn.close()
    logger.info(f"[vk_stats_collector] Инициализирована БД: {DB_PATH}")


def register_post(post_id: int, owner_id: int, published_at: str) -> None:
    """
    Добавляет новый пост в таблицу posts.
    Если таблицы ещё нет, инициализирует БД.

    :param post_id: атомарный ID поста VK (без owner_id)
    :param owner_id: ID владельца стены VK (например, -123456789)
    :param published_at: ISO-строка времени публикации (например, "2025-06-03T12:34:56Z")
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO posts (post_id, owner_id, published_at) VALUES (?, ?, ?);",
            (post_id, owner_id, published_at)
        )
        conn.commit()
        logger.info(f"[vk_stats_collector] Зарегистрирован пост: {owner_id}_{post_id} в {published_at}")
    except Exception as e:
        logger.error(f"[vk_stats_collector] Не удалось зарегистрировать пост {owner_id}_{post_id}: {e}")
    finally:
        conn.close()


def collect_stats() -> None:
    """
    Обходит все записи из таблицы posts, для каждого поста запрашивает у VK API
    текущие метрики через класс VKStats и сохраняет результат в таблицу stats.

    Для каждого поста создаётся новая запись в stats с полями:
      post_id, collected_at, views, likes, comments, reposts
    """
    init_db()
    # Получаем все зарегистрированные посты
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT post_id, owner_id FROM posts;")
        rows = cursor.fetchall()
    except Exception as e:
        logger.error(f"[vk_stats_collector] Ошибка при чтении таблицы posts: {e}")
        conn.close()
        return

    if not rows:
        logger.info("[vk_stats_collector] Нет зарегистрированных постов для сбора статистики")
        conn.close()
        return

    vk_stats = VKStats()  # использует настройки из settings.VK_TOKEN и settings.VK_OWNER_ID

    for post_id, owner_id in rows:
        # Если owner_id в БД отличается от settings.VK_OWNER_ID, временно переопределим
        if owner_id != settings.VK_OWNER_ID:
            # Переинициализируем VKStats с другим owner_id
            try:
                vk_stats = VKStats()
                vk_stats.owner_id = owner_id
            except Exception as e:
                logger.error(f"[vk_stats_collector] Не удалось установить owner_id={owner_id}: {e}")
                continue

        try:
            stats = vk_stats.get_post_stats(post_id)
            if not stats:
                continue

            collected_at = datetime.utcnow().isoformat()
            views = stats.get("views", 0)
            likes = stats.get("likes", 0)
            comments = stats.get("comments", 0)
            reposts = stats.get("reposts", 0)

            cursor.execute(
                """
                INSERT INTO stats (post_id, collected_at, views, likes, comments, reposts)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (post_id, collected_at, views, likes, comments, reposts)
            )
            logger.info(
                f"[vk_stats_collector] Собрана статистика для {owner_id}_{post_id}: "
                f"views={views}, likes={likes}, comments={comments}, reposts={reposts}"
            )
        except Exception as e:
            logger.error(f"[vk_stats_collector] Ошибка при сборе статистики для {owner_id}_{post_id}: {e}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    """
    При прямом запуске скрипта:
      1) Инициализирует БД, если нужно.
      2) Вызывает функцию collect_stats(), чтобы сразу собрать статистику для всех постов.
    """
    logging.basicConfig(level=logging.INFO)
    collect_stats()
