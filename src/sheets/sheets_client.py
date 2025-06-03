# src/sheets/sheets_client.py

"""
sheets_client.py

Клиент для работы с Google Sheets:
  - get_next_post(): возвращает первую строку, где status == "ожидание".
  - update_post(): теперь обновляет только колонки B–G (status, scheduled, url, ai, model, notes),
    не трогая колонку A (idea), т. е. не перезаписывает тему.
"""

import os
import logging
from typing import Optional, Tuple

import gspread
from google.auth.exceptions import GoogleAuthError

from src.core.models import Post

logger = logging.getLogger(__name__)


class SheetsClient:
    def __init__(self, credentials_json_path: str, spreadsheet_name: str, sheet_name: str):
        """
        Инициализирует соединение с Google Sheets:
          - credentials_json_path: путь к service_account.json
          - spreadsheet_name: имя или ID таблицы
          - sheet_name: имя листа внутри таблицы
        """
        if not os.path.exists(credentials_json_path):
            raise FileNotFoundError(f"Google credentials not found: {credentials_json_path}")
        self.spreadsheet_name = spreadsheet_name
        self.sheet_name = sheet_name

        try:
            self.client = gspread.service_account(filename=credentials_json_path)
        except (GoogleAuthError, Exception) as e:
            raise ValueError(f"Не удалось авторизоваться в Google Sheets: {e}")

        try:
            self.spreadsheet = self.client.open(spreadsheet_name)
        except Exception as e:
            raise ValueError(f"Не удалось открыть таблицу '{spreadsheet_name}': {e}")

        try:
            self.sheet = self.spreadsheet.worksheet(sheet_name)
        except Exception as e:
            raise ValueError(f"Не удалось открыть лист '{sheet_name}': {e}")

    def get_all_values(self):
        """
        Возвращает все строки из листа (включая заголовок).
        """
        return self.sheet.get_all_values()

    def get_next_post(self) -> Tuple[Optional[Post], Optional[int]]:
        """
        Ищет первую строку, где status == "ожидание".
        Возвращает (Post, row_index), где row_index — номер строки в листе (1-based).
        Если таких строк нет, возвращает (None, None).
        """
        all_values = self.get_all_values()
        if len(all_values) < 2:
            return None, None

        for idx, row in enumerate(all_values[1:], start=2):
            # row: [idea, status, scheduled, url, ai, model, notes]
            status = row[1].strip().lower() if len(row) >= 2 else ""
            if status == "ожидание":
                # Забираем тему (idea) из колонки A, и сохраняем остальные поля если нужно
                idea = row[0].strip() if len(row) >= 1 else ""
                post = Post(
                    idea=idea,                            # только для генерации, не будем её потом перезаписывать
                    status=status,
                    scheduled=(row[2].strip() if len(row) >= 3 else None),
                    url=(row[3].strip() if len(row) >= 4 else None),
                    ai=(row[4].strip() if len(row) >= 5 else None),
                    model=(row[5].strip() if len(row) >= 6 else None),
                    notes=(row[6].strip() if len(row) >= 7 else None),
                    image_bytes=None
                )
                return post, idx
        return None, None

    def update_post(self, row_idx: int, post: Post) -> None:
        """
        Обновляет в строке row_idx (1-based) колонки B–G:
          B (status), C (scheduled), D (url), E (ai), F (model), G (notes).
        Не трогает колонку A (idea), чтобы не перезаписывать тему.
        """
        # Формируем список значений именно для колонок B–G
        values = [
            post.status or "",      # B
            post.scheduled or "",   # C
            post.url or "",         # D
            post.ai or "",          # E
            post.model or "",       # F
            post.notes or ""        # G
        ]

        # Диапазон обновления B{row_idx}:G{row_idx}
        cell_range = f"B{row_idx}:G{row_idx}"
        try:
            self.sheet.update(cell_range, [values])
        except Exception as e:
            logger.error(f"Ошибка при обновлении строки {row_idx}: {e}")
            raise
