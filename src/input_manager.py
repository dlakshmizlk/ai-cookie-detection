"""Reads the list of websites + tracking-pixel patterns from a Google Sheet.

Authenticates with a Google service account whose JSON credentials file
must already exist on disk. The service account's email must be added
as a viewer (or editor) on the target spreadsheet.
"""

from __future__ import annotations

import logging
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from src import config
from src.helper_funcs import normalize_url

log = logging.getLogger(__name__)


class InputManager:
    def __init__(self, credentials_file: str | Path) -> None:
        cred_file = Path(credentials_file)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        log.debug("Loading Google service-account credentials from %s", cred_file)
        creds = Credentials.from_service_account_file(cred_file, scopes=scopes)
        client = gspread.authorize(creds)

        log.debug("Opening spreadsheet '%s'", config.SPREADSHEET_NAME)
        spreadsheet = client.open(config.SPREADSHEET_NAME)
        self.sheet = spreadsheet.sheet1

        self.pixels = self.get_column_by_name("pixels")
        self.websites = [normalize_url(w) for w in self.get_column_by_name("websites")]

        log.info(
            "Sheet '%s' loaded: %d websites, %d pixel patterns",
            config.SPREADSHEET_NAME, len(self.websites), len(self.pixels),
        )

    def get_column_by_name(self, column_name: str) -> list[str]:
        headers = self.sheet.row_values(1)
        try:
            col_index = headers.index(column_name) + 1  # gspread is 1-based
        except ValueError as exc:
            raise ValueError(
                f"Column '{column_name}' not found. Available columns: {headers}"
            ) from exc

        return self.sheet.col_values(col_index)[1:]  # skip header row
