import sys
import os
# Добавляем корень проекта (project-root) в PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.insert(0, os.path.join(project_root, 'stubs'))

import pytest
from src.sheets.sheets_client import SheetsClient
from src.core.models import Post

# Заглушки для Google Sheets API
class DummySheet:
    def __init__(self, records):
        # Храним изначальные записи и отслеживаем обновления
        self._records = records
        self.updated = None

    def get_all_records(self):
        return self._records

    def update(self, cell_range, values):
        # Сохраняем, какие данные были переданы в update
        self.updated = (cell_range, values)


class DummySpreadsheet:
    def __init__(self, sheet):
        self._sheet = sheet

    def worksheet(self, name):
        return self._sheet


class DummyGspreadClient:
    def __init__(self, sheet):
        self._sheet = sheet

    def open(self, name):
        # Возвращаем объект с методом worksheet()
        return DummySpreadsheet(self._sheet)


class DummyCredentials:
    pass


@pytest.fixture
def dummy_sheet(monkeypatch):
    """
    Фикстура, которая подменяет авторизацию Google Sheets
    и возвращает DummySheet с одной записью в статусе 'ожидание'.
    """

    # Подготовим «лист» с ровно одной записью: status = 'ожидание'
    records = [
        {"idea": "Idea1", "status": "ожидание", "scheduled": "", "socialnet": "",
         "url": "", "ai": "", "model": "", "notes": ""}
    ]
    sheet = DummySheet(records)

    # Замокать Credentials.from_service_account_file → возвращает DummyCredentials
    monkeypatch.setattr(
        "src.sheets.sheets_client.Credentials.from_service_account_file",
        lambda path, scopes: DummyCredentials()
    )

    # Замокать gspread.authorize → возвращает DummyGspreadClient(sheet)
    monkeypatch.setattr(
        "src.sheets.sheets_client.gspread.authorize",
        lambda creds: DummyGspreadClient(sheet)
    )

    return sheet


def test_get_next_post(dummy_sheet):
    """
    Проверяем, что get_next_post() вернёт Post с полем idea="Idea1"
    и номер строки 2 (учитывая, что header – это строка 1).
    """
    client = SheetsClient(
        credentials_json_path="fake_path.json",
        spreadsheet_name="press",
        sheet_name="smm"
    )

    post, idx = client.get_next_post()
    # Должны вернуть модель Post и индекс 2
    assert isinstance(post, Post)
    assert post.idea == "Idea1"
    assert idx == 2  # первая строка – header, вторая – наша запись


def test_update_post(dummy_sheet):
    """
    Проверяем, что update_post() обновляет нужный диапазон ("A2:H2")
    и передаёт корректные значения.
    """
    client = SheetsClient(
        credentials_json_path="fake_path.json",
        spreadsheet_name="press",
        sheet_name="smm"
    )

    # Создаём фиктивный Post с обновлёнными полями
    post = Post(
        idea="Idea1",
        status="выполнено",
        scheduled="2025-06-01 10:00",
        socialnet="vk",
        url="https://vk.com/wall-12345_6789",
        ai="ChatGPT",
        model="gpt-4o",
        notes="Tokens: 100, Cost: 0.02"
    )
    client.update_post(2, post)

    # sheet.updated должен быть установлен кортежем (cell_range, values)
    assert dummy_sheet.updated is not None

    cell_range, values = dummy_sheet.updated
    # Проверяем, что диапазон для обновления правильный
    assert cell_range == "A2:H2"
    # values — вложенный список, первая строка – это [idea, status, scheduled, ...]
    assert values[0][0] == "Idea1"
    assert values[0][1] == "выполнено"
    assert values[0][2] == "2025-06-01 10:00"
    assert values[0][3] == "vk"
    assert values[0][4] == "https://vk.com/wall-12345_6789"
    assert values[0][5] == "ChatGPT"
    assert values[0][6] == "gpt-4o"
    assert values[0][7] == "Tokens: 100, Cost: 0.02"
