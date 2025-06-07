import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from src.modules.telegram.tg_stats import TelegramStats


class DummyResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_collect_success(monkeypatch):
    """TelegramStats.collect returns parsed counters."""

    def fake_get(url, params=None, timeout=15):
        assert params["chat_id"] == "@test"
        assert params["message_id"] == 42
        return DummyResponse({"ok": True, "result": {"views": 10, "forwards": 3}})

    import requests
    monkeypatch.setattr(requests, "get", fake_get, raising=False)
    stats = TelegramStats(token="123")
    result = stats.collect("https://t.me/test/42")
    assert result == {"views": 10, "forwards": 3}


def test_collect_api_error(monkeypatch):
    """Method handles request exceptions gracefully."""

    def fake_get(url, params=None, timeout=15):
        raise Exception("fail")

    import requests
    monkeypatch.setattr(requests, "get", fake_get, raising=False)
    stats = TelegramStats(token="123")
    result = stats.collect("https://t.me/test/42")
    assert result == {}

