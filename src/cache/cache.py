# src/cache.py

"""
cache.py

Простой модуль для кэширования результатов генерации текста и изображений.
Используется для:
  - Хранения текстовых ответов LLM по ключу (prompt + model).
  - Хранения байт изображений по ключу (prompt + model).

Кэш основан на файловой системе: для каждого ключа создаётся отдельный файл,
имя которого — SHA256-хэш от строки "<тип>#<model>#<prompt>".
Файлы для текстов сохраняются в папке cache/text/, для изображений — в cache/image/.

Это позволяет при повторных вызовах с одинаковым prompt и model не отправлять
запросы в API заново, а брать результат из локального хранилища.
"""

import os
import hashlib
import pickle
from pathlib import Path
from typing import Optional, Tuple

# Папка для кэша (в корне проекта)
_BASE_CACHE_DIR = Path("cache")
_TEXT_CACHE_DIR = _BASE_CACHE_DIR / "text"
_IMAGE_CACHE_DIR = _BASE_CACHE_DIR / "image"

# Убедимся, что директории существуют
for d in (_TEXT_CACHE_DIR, _IMAGE_CACHE_DIR):
    os.makedirs(d, exist_ok=True)


def _make_key(type_prefix: str, model: str, prompt: str) -> str:
    """
    Формирует SHA256-хэш от строки "<type_prefix>#<model>#<prompt>".
    type_prefix: "text" или "image".
    """
    key_string = f"{type_prefix}#{model}#{prompt}".encode("utf-8")
    return hashlib.sha256(key_string).hexdigest()


def get_cached_text(model: str, prompt: str) -> Optional[str]:
    """
    Пытается получить из кэша ранее сгенерированный текст для данного model и prompt.
    Если файл найден, возвращает строку, иначе — None.
    """
    key = _make_key("text", model, prompt)
    cache_path = _TEXT_CACHE_DIR / f"{key}.pkl"
    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "rb") as f:
            text = pickle.load(f)
            if isinstance(text, str):
                return text
    except Exception:
        # Если файл повреждён или не удалось прочитать, удалим его
        try:
            cache_path.unlink()
        except Exception:
            pass
    return None


def set_cached_text(model: str, prompt: str, text: str) -> None:
    """
    Сохраняет сгенерированный текст в кэш.
    """
    key = _make_key("text", model, prompt)
    cache_path = _TEXT_CACHE_DIR / f"{key}.pkl"
    try:
        with open(cache_path, "wb") as f:
            pickle.dump(text, f)
    except Exception:
        # Если не удалось сохранить, просто пропускаем
        pass


def get_cached_image(model: str, prompt: str) -> Optional[bytes]:
    """
    Пытается получить из кэша ранее сгенерированное изображение (байты) для данного model и prompt.
    Если файл найден, возвращает bytes, иначе — None.
    """
    key = _make_key("image", model, prompt)
    cache_path = _IMAGE_CACHE_DIR / f"{key}.bin"
    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "rb") as f:
            img_bytes = f.read()
            if isinstance(img_bytes, (bytes, bytearray)):
                return img_bytes
    except Exception:
        # Если файл повреждён, удалим его
        try:
            cache_path.unlink()
        except Exception:
            pass
    return None


def set_cached_image(model: str, prompt: str, image_bytes: bytes) -> None:
    """
    Сохраняет байты изображения в кэш для данного model и prompt.
    """
    key = _make_key("image", model, prompt)
    cache_path = _IMAGE_CACHE_DIR / f"{key}.bin"
    try:
        with open(cache_path, "wb") as f:
            f.write(image_bytes)
    except Exception:
        # Если не удалось сохранить, пропускаем
        pass
