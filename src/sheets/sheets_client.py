# src/sheets/sheets_client.py

"""
sheets_client.py

Клиент для работы с Google Sheets через gspread + google-auth.
Добавлен универсальный метод update_row_fields для записи любых колонок по имени.
"""

import logging
import time
from typing import Tuple, Optional, Dict, List

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

    def __init__(self):
        creds_path = settings.GOOGLE_CREDENTIALS_PATH
        if not creds_path:
            raise ValueError("GOOGLE_CREDENTIALS_PATH не задан в settings")

        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        try:
            credentials = Credentials.from_service_account_file(creds_path, scopes=scope)
            self.gc = gspread.authorize(credentials)
        except Exception as e:
            logger.error(f"[SheetsClient] Ошибка авторизации через gspread:\n{e}", exc_info=True)
            raise

        spreadsheet_ref = settings.SHEETS_SPREADSHEET
        if not spreadsheet_ref:
            raise ValueError("SHEETS_SPREADSHEET не задан в settings")

        # Попытки открыть таблицу: open_by_key или open_by_url
        try:
            self.spreadsheet = self.gc.open_by_key(spreadsheet_ref)
            logger.info(f"[SheetsClient] Открыта таблица по ID: {spreadsheet_ref}")
        except Exception as e_key:
            logger.warning(f"[SheetsClient] Не удалось открыть по ключу (ID='{spreadsheet_ref}'): {e_key}")
            # Если указан полный URL
            if "/spreadsheets/" in spreadsheet_ref:
                try:
                    self.spreadsheet = self.gc.open_by_url(spreadsheet_ref)
                    logger.info(f"[SheetsClient] Открыта таблица по URL: {spreadsheet_ref}")
                except Exception as e_url:
                    error_msg = (
                        f"[SheetsClient] Не удалось открыть таблицу '{spreadsheet_ref}':\n"
                        f"  Ошибка по ID: {e_key}\n"
                        f"  Ошибка по URL: {e_url}\n"
                        "  Проверьте правильность ID/URL и доступ сервисного аккаунта."
                    )
                    logger.error(error_msg, exc_info=True)
                    raise ValueError(error_msg)
            else:
                error_msg = (
                    f"[SheetsClient] Не удалось открыть таблицу '{spreadsheet_ref}' по ID: {e_key}\n"
                    "  Проверьте, что SHEETS_SPREADSHEET — корректный Spreadsheet ID или URL,\n"
                    "  и что сервисный аккаунт добавлен в редакторы таблицы."
                )
                logger.error(error_msg, exc_info=True)
                raise ValueError(error_msg)

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

    def get_next_post(self, sheet_name: str) -> Tuple[Optional[int], Optional[Dict[str, str]]]:
        """
        Ищет в указанном листе первую строку, где колонка "status" == "ожидание".
        Возвращает (row_number, row_data) или (None, None).
        """
        try:
            sheet = self._open_sheet(sheet_name)
            all_values: List[List[str]] = sheet.get_all_values()
            if not all_values or len(all_values) < 2:
                return None, None

            header = all_values[0]
            # Находим индекс колонки "status"
            status_col_idx = None
            for idx, col_name in enumerate(header):
                if col_name.strip().lower() == "status":
                    status_col_idx = idx
                    break
            if status_col_idx is None:
                logger.error(f"[SheetsClient] В шапке листа '{sheet_name}' нет колонки 'status'")
                return None, None

            # Проходим по строкам, начиная со 2-й (row_idx = 2 и далее)
            for row_idx, row in enumerate(all_values[1:], start=2):
                if len(row) > status_col_idx and row[status_col_idx].strip().lower() == "ожидание":
                    row_data: Dict[str, str] = {}
                    for col_idx, col_name in enumerate(header):
                        cell_value = ""
                        if len(row) > col_idx:
                            cell_value = row[col_idx].strip()
                        row_data[col_name.strip()] = cell_value
                    return row_idx, row_data

            return None, None

        except Exception as e:
            logger.error(f"[SheetsClient] Ошибка при get_next_post('{sheet_name}'): {e}", exc_info=True)
            return None, None

    def update_row_fields(
        self,
        sheet_name: str,
        row_index: int,
        fields: Dict[str, str]
    ) -> None:
        """
        Обновляет в указанной строке произвольные колонки по их именам.

        :param sheet_name: имя листа (worksheet) в таблице.
        :param row_index:  номер строки (1-based).
        :param fields:     словарь {column_header: new_value}, где column_header – название колонки в первой строке.
        """
        try:
            sheet = self._open_sheet(sheet_name)
            header = sheet.row_values(1)  # первая строка: заголовок

            # Составляем mapping: "header_name_lower" -> column_index (1-based)
            header_map = {}
            for idx, col_name in enumerate(header):
                header_map[col_name.strip().lower()] = idx + 1

            # Проходим по всем ключам из fields и обновляем ячейки
            for col_name, new_value in fields.items():
                col_key = col_name.strip().lower()
                if col_key not in header_map:
                    logger.warning(f"[SheetsClient] В шапке '{sheet_name}' нет колонки '{col_name}' — пропускаем")
                    continue
                col_idx = header_map[col_key]
                sheet.update_cell(row_index, col_idx, new_value)

        except Exception as e:
            logger.error(f"[SheetsClient] Ошибка при update_row_fields('{sheet_name}', {row_index}, {fields}): {e}", exc_info=True)

    def update_post_status_and_meta(
        self,
        sheet_name: str,
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
