"""Data access layer for recipient records.

Fetches data from Google Sheets located in a Google Drive folder.
Each sheet's name ends with a jotform_id (e.g. "Výprava - 260482905363055").
Records are cached in memory with a two-level structure: jotform_id → hash → Record.
"""

import logging
import os
import re
import time
from typing import Any, TypedDict

import gspread
from google.auth import default

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300  # 5 minutes

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class Record(TypedDict):
    """A recipient record from the Google Sheet."""

    parent_first: str
    parent_last: str
    child_first: str
    child_last: str
    address: str
    phone: str


# Two-level cache: jotform_id → {hash_code → Record}
_cache: dict[str, dict[str, Record]] = {}
_cache_timestamp: float = 0.0


def _get_folder_id() -> str:
    """Return the Google Drive folder ID from environment."""
    try:
        return os.environ["DRIVE_FOLDER_ID"]
    except KeyError:
        raise RuntimeError("DRIVE_FOLDER_ID environment variable is not set") from None


def _list_sheets_in_folder(client: gspread.Client) -> dict[str, str]:
    """List Google Sheets in the configured Drive folder.

    Returns:
        Mapping of jotform_id → spreadsheet_id.
    """
    folder_id = _get_folder_id()
    files: list[dict[str, Any]] = client.list_spreadsheet_files(folder_id=folder_id)

    mapping: dict[str, str] = {}
    for file_info in files:
        match = re.search(r"(\d{10,})$", file_info["name"].strip())
        if match:
            mapping[match.group(1)] = file_info["id"]
        else:
            logger.warning("Cannot extract jotform_id from sheet: %s", file_info["name"])

    logger.info("Found %d sheets in folder %s", len(mapping), folder_id)
    return mapping


def _load_sheet_records(client: gspread.Client, spreadsheet_id: str) -> dict[str, Record]:
    """Load all records from a single Google Sheet."""
    sheet = client.open_by_key(spreadsheet_id).sheet1
    rows: list[dict[str, Any]] = sheet.get_all_records()
    records: dict[str, Record] = {}

    for row in rows:
        hash_code = str(row.get("ID", "")).strip()
        if not hash_code:
            continue

        records[hash_code] = {
            "parent_first": str(row.get("Jméno rodiče", "")).strip(),
            "parent_last": str(row.get("Příjmení rodiče", "")).strip(),
            "child_first": str(row.get("Jméno dítěte", "")).strip(),
            "child_last": str(row.get("Příjmení dítěte", "")).strip(),
            "address": str(row.get("Adresa bydliště", "")).strip(),
            "phone": str(row.get("Telefon rodiče", "")).strip(),
        }

    return records


def _refresh_cache() -> None:
    """Fetch all records from all Google Sheets in the folder and rebuild cache."""
    global _cache, _cache_timestamp

    credentials, _ = default(scopes=GOOGLE_SCOPES)
    client = gspread.authorize(credentials)

    sheet_mapping = _list_sheets_in_folder(client)
    new_cache: dict[str, dict[str, Record]] = {}

    for jotform_id, spreadsheet_id in sheet_mapping.items():
        records = _load_sheet_records(client, spreadsheet_id)
        new_cache[jotform_id] = records
        logger.info("Loaded %d records for jotform_id=%s", len(records), jotform_id)

    _cache = new_cache
    _cache_timestamp = time.monotonic()
    logger.info(
        "Cache refreshed: %d sheets, %d total records",
        len(_cache),
        sum(len(r) for r in _cache.values()),
    )


def _ensure_cache() -> None:
    """Refresh cache if empty or expired."""
    if not _cache or (time.monotonic() - _cache_timestamp) > CACHE_TTL_SECONDS:
        try:
            _refresh_cache()
        except Exception:
            logger.exception("Failed to refresh cache from Google Sheets")
            if _cache:
                logger.warning("Serving stale data from previous cache")
            else:
                raise


def get_record(jotform_id: str, hash_code: str) -> Record | None:
    """Look up a recipient record by jotform_id and hash code.

    Args:
        jotform_id: Identifies which Google Sheet (form/event) to search in.
        hash_code: Alphanumeric hash identifying the recipient.

    Returns:
        Record with personal data, or None if not found.
    """
    _ensure_cache()

    form_records = _cache.get(jotform_id)
    if form_records is None:
        logger.warning("No sheet found for jotform_id=%s", jotform_id)
        return None

    return form_records.get(hash_code)
