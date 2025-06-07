import os
import sqlite3

import pytest

# Добавляем project root
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core import user_db


@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(user_db, "DB_PATH", str(db_path))
    user_db.init_db()
    yield db_path


def test_create_user(temp_db):
    user_db.create_user("alice", "password")
    conn = sqlite3.connect(user_db.DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE username='alice'")
    row = cur.fetchone()
    conn.close()
    assert row[0] == "alice"


def test_authentication(temp_db):
    user_db.create_user("bob", "secret")
    assert user_db.authenticate("bob", "secret") is True
    assert user_db.authenticate("bob", "wrong") is False
    assert user_db.authenticate("ghost", "secret") is False


def test_settings(temp_db):
    user_db.set_setting("foo", "bar")
    assert user_db.get_setting("foo") == "bar"
    assert user_db.get_setting("unknown") is None
