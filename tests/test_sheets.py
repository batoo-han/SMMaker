import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest

from src.sheets.sheets_client import SheetsClient
from src.config.settings import settings


class DummySheet:
    def __init__(self, rows):
        self.rows = rows
        self.updated_cells = []

    def get_all_values(self):
        return self.rows

    def row_values(self, idx):
        return self.rows[idx - 1]

    def update_cell(self, row, col, value):
        while len(self.rows) < row:
            self.rows.append([])
        row_list = self.rows[row - 1]
        while len(row_list) < col:
            row_list.append('')
        row_list[col - 1] = value
        self.updated_cells.append((row, col, value))


class DummySpreadsheet:
    def __init__(self, sheet):
        self._sheet = sheet

    def worksheet(self, name):
        return self._sheet


class DummyGspreadClient:
    def __init__(self, sheet):
        self._sheet = sheet

    def open_by_key(self, key):
        return DummySpreadsheet(self._sheet)

    def open_by_url(self, url):
        return DummySpreadsheet(self._sheet)


class DummyCredentials:
    @classmethod
    def from_service_account_file(cls, path, scopes=None):
        return cls()


@pytest.fixture
def dummy_sheet(monkeypatch):
    rows = [
        ["idea", "status", "scheduled", "socialnet", "url", "ai", "model", "notes"],
        ["Idea1", "ожидание", "", "", "", "", "", ""],
    ]
    sheet = DummySheet(rows)

    monkeypatch.setattr(
        "src.sheets.sheets_client.Credentials.from_service_account_file",
        lambda path, scopes=None: DummyCredentials(),
    )
    monkeypatch.setattr(
        "src.sheets.sheets_client.gspread.authorize",
        lambda creds: DummyGspreadClient(sheet),
    )
    monkeypatch.setattr(settings, "GOOGLE_CREDENTIALS_PATH", "fake.json", raising=False)
    monkeypatch.setattr(settings, "SHEETS_SPREADSHEET", "dummy", raising=False)

    return sheet


def test_get_next_post(dummy_sheet):
    client = SheetsClient()
    idx, row = client.get_next_post(sheet_name="smm")
    assert idx == 2
    assert row["idea"] == "Idea1"


def test_update_post_status_and_meta(dummy_sheet):
    client = SheetsClient()
    client.update_post_status_and_meta(
        sheet_name="smm",
        row_index=2,
        status="выполнено",
        scheduled="2025-06-01 10:00",
        url="https://vk.com/wall-12345_6789",
        ai="ChatGPT",
        model="gpt-4o",
        notes="Tokens: 100, Cost: 0.02",
    )
    row = dummy_sheet.rows[1]
    assert row[1] == "выполнено"
    assert row[2] == "2025-06-01 10:00"
    assert row[4] == "https://vk.com/wall-12345_6789"
    assert row[5] == "ChatGPT"
    assert row[6] == "gpt-4o"
    assert row[7] == "Tokens: 100, Cost: 0.02"
