# src/modules/image_generators/__init__.py

"""
Пакет image_generators содержит классы, реализующие генерацию изображений
через различные провайдеры (OpenAI DALL·E, FusionBrain и т.д.).
"""

# Здесь можно явно указать, какие имена экспортируются при `from image_generators import *`
__all__ = [
    "OpenAIImageGenerator",
    "FusionBrainImageGenerator",
]
