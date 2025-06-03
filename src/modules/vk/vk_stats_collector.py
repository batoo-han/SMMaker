"""
vk_stats_collector.py

Модуль для сбора статистики VK-постов и сохранения её в SQLite.

Структура базы данных (SQLite):
    - posts: хранит посты, опубликованные через наш паблишер (post_id, owner_id, published_at)
    - stats: хранит исторические метрики для каждого поста (id, post_id, collected_at, views, likes, comments, reposts)

Функции:
    - init_db(): создание БД и таблиц, если их ещё нет.
    - register_post(post_id: int, owner_id: int, published_at: str): добавить новый пост в таблицу posts.
    - collect_stats(): обходит все записи из posts и запрашивает у VK API актуальные метрики,
                       после чего записывает их в таблицу stats.
"""

import os
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Tuple

import vk_api
from vk_api.exceptions import ApiError

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Путь к файлу SQLite (можно изменить, если нужно)
DB_PATH = os.getenv('VK_STATS_DB_PATH', 'vk_stats.sqlite3')


def init_db():
    """
    Инициализирует SQLite-базу: создаёт таблицы posts и stats, если их нет.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица для списка опубликованных постов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        post_id INTEGER PRIMARY KEY,
        owner_id INTEGER NOT NULL,
        published_at TEXT NOT NULL
    );
    """)

    # Таблица для хранения метрик (история)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        collected_at TEXT NOT NULL,
        views INTEGER,
        likes INTEGER,
        comments INTEGER,
        reposts INTEGER,
        FOREIGN KEY (post_id) REFERENCES posts(post_id)
    );
    """)

    conn.commit()
    conn.close()


def register_post(post_id: int, owner_id: int, published_at: str):
    """
    Регистрирует новый опубликованный пост в таблице posts.

    Args:
        post_id (int): ID поста (без owner_id)
        owner_id (int): ID владельца (отрицательное число для группы)
        published_at (str): дата/время публикации (ISO-формат)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Используем INSERT OR IGNORE, чтобы не дублировать запись, если такой post_id уже есть
    cursor.execute("""
    INSERT OR IGNORE INTO posts (post_id, owner_id, published_at)
    VALUES (?, ?, ?);
    """, (post_id, owner_id, published_at))

    conn.commit()
    conn.close()


def get_registered_posts() -> List[Tuple[int, int]]:
    """
    Возвращает список кортежей (post_id, owner_id) из таблицы posts.
    Используется для обхода всех опубликованных постов и сбора их статистики.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT post_id, owner_id FROM posts;")
    rows = cursor.fetchall()

    conn.close()
    return rows


def collect_stats():
    """
    Сбор текущей статистики для всех зарегистрированных постов VK.
    Для каждого поста:
      - Получает данные через VK API (wall.getById)
      - Извлекает метрики: views, likes, comments, reposts
      - Записывает запись в таблицу stats (с привязкой к post_id и текущему времени)
    """
    # Инициализируем БД (если первый запуск)
    init_db()

    # Проверяем, включён ли сбор статистики
    if not settings.ENABLE_VK_STATS:
        logger.info("Сбор статистики VK отключён (ENABLE_VK_STATS=false).")
        return

    # Авторизация в VK API
    token = settings.VK_TOKEN
    owner_id = settings.VK_OWNER_ID
    if not token or owner_id is None:
        logger.error("Невозможно собрать статистику VK: не заданы VK_TOKEN или VK_OWNER_ID.")
        return

    try:
        vk_session = vk_api.VkApi(token=token)
        vk = vk_session.get_api()
    except Exception as e:
        logger.error(f"Ошибка авторизации VK для сбора статистики: {e}")
        return

    # Получаем список постов
    posts = get_registered_posts()
    if not posts:
        logger.info("Нет зарегистрированных постов для сбора статистики.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for post_id, p_owner_id in posts:
        try:
            # Запрашиваем информацию о посте
            response = vk.wall.getById(posts=f"{p_owner_id}_{post_id}")
            if not response:
                logger.warning(f"VK API вернул пустой ответ для поста {p_owner_id}_{post_id}")
                continue

            post_info = response[0]
            # Извлекаем метрики
            views = post_info.get('views', {}).get('count', 0)
            likes = post_info.get('likes', {}).get('count', 0)
            comments = post_info.get('comments', {}).get('count', 0)
            reposts = post_info.get('reposts', {}).get('count', 0)

            collected_at = datetime.utcnow().isoformat()

            # Записываем в таблицу stats
            cursor.execute("""
            INSERT INTO stats (post_id, collected_at, views, likes, comments, reposts)
            VALUES (?, ?, ?, ?, ?, ?);
            """, (post_id, collected_at, views, likes, comments, reposts))

            logger.info(f"Собрана статистика VK для поста {p_owner_id}_{post_id}: "
                        f"views={views}, likes={likes}, comments={comments}, reposts={reposts}")
        except ApiError as e:
            logger.error(f"VK API Error при getById для {p_owner_id}_{post_id}: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при сборе статистики VK для {p_owner_id}_{post_id}: {e}")

    conn.commit()
    conn.close()
