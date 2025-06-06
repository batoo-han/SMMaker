# src/sheets/sheets_client.py

"""
sheets_client.py

Клиент для работы с Google Sheets через gspread + google-auth.
Добавлен универсальный метод update_row_fields для записи любых колонок по имени.
"""

import logging
import time
from typing import Tuple, Optional, Dict, List
from src.core.models import Post

import gspread
from google.oauth2.service_account import Credentials
from http.client import RemoteDisconnected
from requests.exceptions import ConnectionError

from src.config.settings import settings

logger = logging.getLogger(__name__)


class SheetsClient:
    """
    Клиент для взаимодействия с Google Sheets через gspread + google-auth.
    """

    def __init__(self, credentials_json_path: str | None = None, spreadsheet_name: str | None = None, sheet_name: str | None = None):
        self.default_sheet = sheet_name
        creds_path = credentials_json_path or settings.GOOGLE_CREDENTIALS_PATH
        if not creds_path:
            raise ValueError("GOOGLE_CREDENTIALS_PATH не задан в settings")

        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        try:
            credentials = Credentials.from_service_account_file(creds_path, scopes=scope)
            self.gc = gspread.authorize(credentials)
        except Exception as e:
            logger.error(f"[SheetsClient] Ошибка авторизации через gspread:\n{e}", exc_info=True)
            raise

        spreadsheet_ref = spreadsheet_name or settings.SHEETS_SPREADSHEET
        if not spreadsheet_ref:
            raise ValueError("SHEETS_SPREADSHEET не задан в settings")

        try:
            self.spreadsheet = self.gc.open(spreadsheet_ref)
        except Exception as e:
            logger.error(f"[SheetsClient] Не удалось открыть таблицу '{spreadsheet_ref}': {e}", exc_info=True)
            raise

    def _open_sheet(self, sheet_name: str):
        """
        Возвращает объект Worksheet по его имени, с повторными попытками при RemoteDisconnected.
        """
        max_retries = 3
        delay = 1  # секунды между попытками
        for attempt in range(1, max_retries + 1):
            try:
                return self.spreadsheet.worksheet(sheet_name)
            except (RemoteDisconnected, ConnectionError) as conn_err:
                logger.warning(
                    f"[SheetsClient] Попытка {attempt}/{max_retries}: проблема соединения при открытии листа '{sheet_name}': {conn_err}"
                )
                if attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                else:
                    logger.error(f"[SheetsClient] Не удалось открыть лист '{sheet_name}' после {max_retries} попыток", exc_info=True)
                    raise
            except Exception as e:
                logger.error(f"[SheetsClient] Не удалось открыть лист '{sheet_name}': {e}", exc_info=True)
                raise

    def get_next_post(self, sheet_name: str | None = None) -> Tuple[Optional[int], Optional[Dict[str, str]]]:
        if sheet_name is None:
            sheet_name = self.default_sheet
        """
        Ищет в указанном листе первую строку, где колонка "status" == "ожидание".
        Возвращает (row_number, row_data) или (None, None).
        """
        try:
            sheet = self._open_sheet(sheet_name)
            records = sheet.get_all_records()
            if not records:
                return None, None

            for idx, row in enumerate(records, start=2):
                status = row.get("status", "").strip().lower()
                if status == "ожидание":
                    post = Post(**{k: str(v) for k, v in row.items()})
                    return post, idx

            return None, None

        except Exception as e:
            logger.error(f"[SheetsClient] Ошибка при get_next_post('{sheet_name}'): {e}", exc_info=True)
            return None, None

    def update_row_fields(
        self,
        sheet_name: str | None,
        row_index: int,
        fields: Dict[str, str]
    ) -> None:
        """
        Обновляет в указанной строке произвольные колонки по их именам.

        :param sheet_name: имя листа (worksheet) в таблице.
        :param row_index:  номер строки (1-based).
        :param fields:     словарь {column_header: new_value}, где column_header – название колонки в первой строке.
        """
        if sheet_name is None:
            sheet_name = self.default_sheet
        try:
            sheet = self._open_sheet(sheet_name)
            header = list(sheet.get_all_records()[0].keys())
            values = []
            for col_name in header:
                key = col_name.strip().lower()
                values.append(fields.get(key, ""))
            start = "A"  # всегда начинаем с A
            end = chr(ord("A") + len(header) - 1)
            cell_range = f"{start}{row_index}:{end}{row_index}"
            sheet.update(cell_range, [values])

        except Exception as e:
            logger.error(f"[SheetsClient] Ошибка при update_row_fields('{sheet_name}', {row_index}, {fields}): {e}", exc_info=True)

    def update_post_status_and_meta(
        self,
        sheet_name: str | None,
        row_index: int,
        status: str,
        scheduled: str,
        url: str,
        ai: str,
        model: str,
        notes: str
    ) -> None:
        """
        Удобный метод для проекта: обновляет сразу все колонки:
        status, scheduled, url, ai, model, notes.
        """
        fields = {
            "status": status,
            "scheduled": scheduled,
            "url": url,
            "ai": ai,
            "model": model,
            "notes": notes
        }
        self.update_row_fields(sheet_name, row_index, fields)

    def update_post(self, row_index: int, post: Post, sheet_name: str | None = None) -> None:
        fields = {
            "idea": post.idea,
            "status": post.status,
            "scheduled": post.scheduled,
            "socialnet": post.socialnet,
            "url": post.url,
            "ai": post.ai,
            "model": post.model,
            "notes": post.notes,
        }
        self.update_row_fields(sheet_name, row_index, fields)
