"""
Storage for user specific tokens and API keys.

Values are persisted in a small SQLite database and encrypted
using :mod:`src.db.crypto` before saving.
"""

import os
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from .crypto import encrypt, decrypt

DB_DIR = os.path.join(os.getcwd(), 'data')
DB_PATH = os.path.join(DB_DIR, 'user_settings.db')


def init_db() -> None:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def set_value(key: str, value: Optional[str]) -> None:
    init_db()
    enc = encrypt(value) if value is not None else ''
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "REPLACE INTO settings (key, value) VALUES (?, ?);",
        (key, enc)
    )
    conn.commit()
    conn.close()


def get_value(key: str) -> Optional[str]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?;", (key,))
    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        return decrypt(row[0])
    return None


@dataclass
class UserSetting:
    """Model representing stored API keys and tokens."""

    vk_token: Optional[str] = field(default=None)
    tg_token: Optional[str] = field(default=None)
    openai_api_key: Optional[str] = field(default=None)
    yandex_api_key: Optional[str] = field(default=None)
    fusionbrain_api_key: Optional[str] = field(default=None)
    fusionbrain_api_secret: Optional[str] = field(default=None)

    def save(self) -> None:
        set_value('VK_TOKEN', self.vk_token)
        set_value('TG_TOKEN', self.tg_token)
        set_value('OPENAI_API_KEY', self.openai_api_key)
        set_value('YANDEX_API_KEY', self.yandex_api_key)
        set_value('FUSIONBRAIN_API_KEY', self.fusionbrain_api_key)
        set_value('FUSIONBRAIN_API_SECRET', self.fusionbrain_api_secret)

    @classmethod
    def load(cls) -> "UserSetting":
        return cls(
            vk_token=get_value('VK_TOKEN'),
            tg_token=get_value('TG_TOKEN'),
            openai_api_key=get_value('OPENAI_API_KEY'),
            yandex_api_key=get_value('YANDEX_API_KEY'),
            fusionbrain_api_key=get_value('FUSIONBRAIN_API_KEY'),
            fusionbrain_api_secret=get_value('FUSIONBRAIN_API_SECRET'),
        )
