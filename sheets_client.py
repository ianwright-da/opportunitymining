"""Google Sheets access helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from normalize import RESULT_HEADERS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


class SheetsClient:
    """Thin wrapper around gspread for this CLI's sheet operations."""

    def __init__(self, creds_path: Path):
        credentials = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
        self.client = gspread.authorize(credentials)

    def open_by_url(self, sheet_url: str) -> gspread.Spreadsheet:
        """Open a spreadsheet by URL."""

        return self.client.open_by_url(sheet_url)

    @staticmethod
    def get_worksheet(
        spreadsheet: gspread.Spreadsheet,
        tab_name: str | None,
        default_index: int,
    ) -> gspread.Worksheet:
        """Get a worksheet by name, or by default zero-based index."""

        if tab_name:
            return spreadsheet.worksheet(tab_name)
        worksheets = spreadsheet.worksheets()
        try:
            return worksheets[default_index]
        except IndexError as exc:
            human_index = default_index + 1
            raise ValueError(
                f"Spreadsheet does not have a default worksheet at position {human_index}. "
                "Create it or pass an explicit tab name."
            ) from exc

    @staticmethod
    def read_queries(
        worksheet: gspread.Worksheet,
        query_column: str,
        limit: int | None = None,
    ) -> list[str]:
        """Read all nonblank query strings from a worksheet column."""

        column_index = column_to_index(query_column)
        values = worksheet.col_values(column_index)
        queries = [value.strip() for value in values if value and value.strip()]
        if limit is not None:
            return queries[:limit]
        return queries

    @staticmethod
    def ensure_results_header(worksheet: gspread.Worksheet) -> None:
        """Add result headers when the worksheet is empty."""

        if worksheet.row_count == 0:
            worksheet.resize(rows=1, cols=len(RESULT_HEADERS))

        all_values = worksheet.get_all_values()
        if not any(any(cell.strip() for cell in row) for row in all_values):
            worksheet.update("A1", [RESULT_HEADERS])

    @staticmethod
    def append_rows(worksheet: gspread.Worksheet, rows: list[list[Any]]) -> None:
        """Append rows in one batch request."""

        if not rows:
            return
        worksheet.append_rows(rows, value_input_option="RAW")


def column_to_index(column: str) -> int:
    """Convert a Google Sheets column label, such as A or AA, to a 1-based index."""

    cleaned = column.strip().upper()
    if not re.fullmatch(r"[A-Z]+", cleaned):
        raise ValueError(f"Invalid column label: {column!r}")

    index = 0
    for char in cleaned:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index
