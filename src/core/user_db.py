"""src/core/user_db.py

Модуль для управления пользователями и настройками приложения через SQLite.
Используется простая база данных `data/app.db` с двумя таблицами:
  - users(username TEXT UNIQUE, password_hash TEXT)
  - settings(key TEXT PRIMARY KEY, value TEXT)
"""

import os
import sqlite3
import hashlib

DB_PATH = os.path.join(os.getcwd(), "data", "app.db")


def init_db() -> None:
    """Создаёт базу данных и таблицы, если их ещё нет."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_user(username: str, password: str) -> None:
    """Добавляет нового пользователя."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?);",
        (username, _hash_password(password)),
    )
    conn.commit()
    conn.close()


def authenticate(username: str, password: str) -> bool:
    """Проверяет имя пользователя и пароль."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE username = ?;", (username,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    return row[0] == _hash_password(password)


def set_setting(key: str, value: str) -> None:
    """Сохраняет значение параметра в таблицу settings."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?);",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_setting(key: str) -> str | None:
    """Возвращает значение параметра или None."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?;", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None
