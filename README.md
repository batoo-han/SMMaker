# SMM Auto Publisher

Проект предназначен для автоматизации создания и публикации контента в социальных сетях (VK, Telegram) с использованием LLM (ChatGPT, YandexGPT) и генерацией изображений (DALL·E). Контент извлекается из Google Sheets, а также сохраняется в векторную БД Chroma для анализа.

## Основные возможности

- **Интеграция с Google Sheets**: проект забирает первую запись со статусом `ожидание`, генерирует контент и публикует в соцсети.
- **Планировщик (Scheduler)**: поддержка cron-расписаний через APScheduler. Задачи автоматически регистрируются из `.env`.
- **LLM генерация**: поддерживаются модели OpenAI (ChatGPT) и YandexGPT. Генерация текста и изображений.
- **Соцсети**: публикация в VK и Telegram.
- **Кеширование**: локальный TTL-кеш для ускорения повторных запросов.
- **Векторная БД**: Chroma DB для сохранения эмбеддингов и последующего анализа.

## Структура проекта

```
project-root/
├── .env
├── README.md
├── requirements.txt
├── src/
│   ├── main.py
│   ├── config/
│   │   └── settings.py
│   ├── core/
│   │   ├── interfaces.py
│   │   └── models.py
│   ├── modules/
│   │   ├── vk/
│   │   │   ├── vk_publisher.py
│   │   │   └── vk_stats.py
│   │   ├── telegram/
│   │   │   ├── tg_publisher.py
│   │   │   └── tg_stats.py
│   │   └── generators/
│   │       ├── openai_generator.py
│   │       └── yandex_generator.py
│   ├── sheets/
│   │   └── sheets_client.py
│   ├── scheduler/
│   │   └── scheduler.py
│   ├── cache/
│   │   └── cache.py
│   └── vector_db/
│       └── vector_client.py
└── tests/
    ├── test_sheets.py
    └── test_scheduler.py
```

## Установка

1. Клонируйте репозиторий или распакуйте файлы в директорию проекта.
2. Создайте и активируйте виртуальное окружение:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # для Linux/macOS
   .\.venv\Scripts\activate  # для Windows
   ```
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Создайте файл `.env` согласно шаблону:
   ```dotenv
   OPENAI_API_KEY=your_openai_api_key
   YANDEX_API_KEY=your_yandex_api_key
   YANDEX_CLOUD_FOLDER_ID=your_yandex_folder_id
   VK_TOKEN=your_vk_token
   VK_OWNER_ID=-<group_id>
   TG_TOKEN=your_telegram_bot_token
   TG_CHAT_ID=@your_channel_or_chat_id
   GOOGLE_CREDENTIALS_PATH=/path/to/service_account.json
   SHEETS_NAME=press
   SHEETS_TAB=smm

   ENABLE_VK=true
   ENABLE_TG=true

   OPENAI_MODEL=gpt-4o
   OPENAI_TEMPERATURE=0.7
   YANDEXGPT_MODEL=YandexGPT_5_Pro
   YANDEXGPT_TEMPERATURE=0.6

   IMAGE_NETWORK=openai
   IMAGE_MODEL=DALL-E-3

   CACHE_MAXSIZE=256
   CACHE_TTL=600

   CHROMA_PERSIST_DIR=.chroma_db
   CHROMA_COLLECTION_NAME=smm_posts
   OPENAI_EMBEDDING_MODEL=text-embedding-ada-002

   SCHEDULES=[
     {"id":"vk_morning","module":"vk","cron":"0 9 * * *","enabled":true,"prompt_key":"post_intro"},
     {"id":"tg_evening","module":"telegram","cron":"0 18 * * *","enabled":false,"prompt_key":"post_summary"}
   ]

   PROMPT_TEXTS={
     "post_intro":"Напиши вступление к статье о ...",
     "post_summary":"Сделай краткое резюме для поста."
   }
   ```

## Запуск приложения

```bash
python src/main.py
```

- При наличии активных расписаний (`SCHEDULES` в `.env`) автоматически стартует планировщик и ждёт cron-событий.
- Если расписания отсутствуют или все `enabled=false`, приложение сразу выполнит одну задачу из Google Sheets и завершится.

## Тестирование

Для запуска тестов (необходимо реализовать тесты в `tests/`):
```bash
pytest
```

## Настройка модулей

- **VK**: укажите `VK_TOKEN` и `VK_OWNER_ID`. Паблишер публикует текст из поля `idea`.
- **Telegram**: укажите `TG_TOKEN` и `TG_CHAT_ID`. Паблишер публикует текст из поля `idea`.
- **LLM**: меняйте `OPENAI_MODEL`, `YANDEXGPT_MODEL` и температуры в `.env`.
- **Изображения**: для генерации DALL·E используйте `IMAGE_NETWORK=openai` и `IMAGE_MODEL=DALL-E-3`.

## Кеширование

- В проекте используется простейшийTTL-кеш (`src/cache/cache.py`). Параметры `CACHE_MAXSIZE` и `CACHE_TTL` можно менять в `.env`.

## Векторная БД Chroma

- После генерации текстов проект сохраняет эмбеддинги в Chroma DB. Параметры `CHROMA_PERSIST_DIR`, `CHROMA_COLLECTION_NAME` и `OPENAI_EMBEDDING_MODEL` настраиваются через `.env`.

## Логирование

- Логи пишутся в консоль и файл `app.log` (код в `src/main.py`).

---

**Примечание**. Некоторые модули (статистика Telegram, поддержка изображений для YandexGPT и т.п.) реализованы как заглушки и могут быть доработаны при необходимости.
