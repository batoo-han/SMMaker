import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.telegram.tg_publisher import TelegramPublisher
from src.core.models import Post
import types
import telegram


def make_post():
    return Post(id="1", title="t", content="text", image_bytes=b"img")


def test_publish_no_event_loop(monkeypatch):
    monkeypatch.setenv("TG_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "@chat")

    called = {}

    def fake_get_running_loop():
        raise RuntimeError

    async def dummy_coro():
        return "should not run"

    def fake_run(coro):
        assert asyncio.iscoroutine(coro)
        called["run"] = True
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    class DummyBot:
        def __init__(self, token):
            pass
        async def get_chat(self, chat_id):
            return types.SimpleNamespace(username="u")
        async def send_photo(self, chat_id, photo, disable_notification=False):
            return types.SimpleNamespace()
        async def send_message(self, chat_id, text, parse_mode=None, disable_notification=False):
            return types.SimpleNamespace(message_id=1)

    class DummyInputFile:
        def __init__(self, *a, **k):
            pass

    monkeypatch.setattr(asyncio, "get_running_loop", fake_get_running_loop)
    monkeypatch.setattr(asyncio, "run", fake_run)
    monkeypatch.setattr("src.modules.telegram.tg_publisher.Bot", DummyBot)
    monkeypatch.setattr("src.modules.telegram.tg_publisher.InputFile", DummyInputFile)

    pub = TelegramPublisher()
    url = pub.publish(make_post())
    assert called.get("run")
    assert url == "https://t.me/u/1"


def test_publish_with_event_loop(monkeypatch):
    monkeypatch.setenv("TG_TOKEN", "token")
    monkeypatch.setenv("TG_CHAT_ID", "@chat")

    called = {}

    class DummyLoop:
        def is_running(self):
            return True

    def fake_get_running_loop():
        return DummyLoop()

    class DummyFuture:
        def __init__(self, coro):
            self._coro = coro
        def result(self):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._coro)
            finally:
                loop.close()

    def fake_run_threadsafe(coro, loop):
        assert isinstance(loop, DummyLoop)
        assert asyncio.iscoroutine(coro)
        called["threadsafe"] = True
        return DummyFuture(coro)

    def fail_run(coro):
        raise AssertionError("asyncio.run should not be called")

    class DummyBot:
        def __init__(self, token):
            pass
        async def get_chat(self, chat_id):
            return types.SimpleNamespace(username="u")
        async def send_photo(self, chat_id, photo, disable_notification=False):
            return types.SimpleNamespace()
        async def send_message(self, chat_id, text, parse_mode=None, disable_notification=False):
            return types.SimpleNamespace(message_id=1)

    class DummyInputFile:
        def __init__(self, *a, **k):
            pass

    monkeypatch.setattr(asyncio, "get_running_loop", fake_get_running_loop)
    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", fake_run_threadsafe)
    monkeypatch.setattr(asyncio, "run", fail_run)
    monkeypatch.setattr("src.modules.telegram.tg_publisher.Bot", DummyBot)
    monkeypatch.setattr("src.modules.telegram.tg_publisher.InputFile", DummyInputFile)

    pub = TelegramPublisher()
    url = pub.publish(make_post())
    assert called.get("threadsafe")
    assert url == "https://t.me/u/1"
