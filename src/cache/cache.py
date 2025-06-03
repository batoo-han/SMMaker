"""
cache.py

Утилиты для кеширования:
  - In-memory LRU-кэш через functools.lru_cache
  - TTL-кэш для функций с указанием времени жизни
  - Заглушка для подключения Redis-кеша (при наличии настроек)
"""
import os
import time
from functools import lru_cache, wraps
from collections import OrderedDict


class TTLCache:
    """
    Простой in-memory кеш с ограничением по размеру и TTL.

    Attributes:
        maxsize (int): максимальное число элементов в кеше
        ttl (int): время жизни элементов в sek.
    """
    def __init__(self, maxsize: int = 128, ttl: int = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()

    def get(self, key):
        """Получить значение из кеша или None, если отсутствует или устарело."""
        if key in self._cache:
            value, expires_at = self._cache.pop(key)
            if expires_at >= time.time():
                # Обновляем порядок для LRU
                self._cache[key] = (value, expires_at)
                return value
        return None

    def set(self, key, value):
        """Установить значение в кеш с учётом TTL."""
        expires_at = time.time() + self.ttl
        if key in self._cache:
            # Удаляем старую запись для обновления порядка
            self._cache.pop(key)
        elif len(self._cache) >= self.maxsize:
            # Удаляем наименее недавно использованный элемент
            self._cache.popitem(last=False)
        self._cache[key] = (value, expires_at)

    def decorator(self, fn=None, *, maxsize=None, ttl=None):
        """
        Декоратор для кеширования вызовов функции.

        Usage:
            cache = TTLCache(maxsize=256, ttl=600)

            @cache.decorator
            def expensive_func(...):
                ...
        """
        if fn is None:
            # Параметризованный декоратор
            return lambda f: self.decorator(f, maxsize=maxsize, ttl=ttl)

        @wraps(fn)
        def wrapped(*args, **kwargs):
            # Новый ключ на основе имени функции и аргументов
            key = (fn.__name__, args, frozenset(kwargs.items()))
            result = self.get(key)
            if result is not None:
                return result
            result = fn(*args, **kwargs)
            self.set(key, result)
            return result

        return wrapped


# Пример использования: декоратор LRU-кеша без TTL
# @lru_cache(maxsize=128)
def lru_cache_decorator(maxsize: int = 128):
    """Возвращает декоратор functools.lru_cache с заданным размером."""
    return lru_cache(maxsize=maxsize)


# Инициализация глобального кеша (можно перенастроить через .env)
CACHE_MAXSIZE = int(os.getenv('CACHE_MAXSIZE', 256))
CACHE_TTL = int(os.getenv('CACHE_TTL', 600))
cache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)
