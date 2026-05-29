"""Unit tests for Google Sheet client helpers."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from gspread.exceptions import WorksheetNotFound

import gsheet
from gsheet import GoogleSheetClient


@pytest.mark.asyncio
async def test_get_or_create_tab_returns_existing(test_logger) -> None:
    ws = MagicMock()
    client = object.__new__(GoogleSheetClient)
    client.logger = test_logger
    client.sheet = MagicMock()
    client.sheet.worksheet.return_value = ws

    out = await client.get_or_create_tab("Errors in Drive")
    assert out is ws
    client.sheet.worksheet.assert_called_once_with("Errors in Drive")
    client.sheet.add_worksheet.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_tab_creates_when_missing(test_logger) -> None:
    new_ws = MagicMock()
    client = object.__new__(GoogleSheetClient)
    client.logger = test_logger
    client.sheet = MagicMock()
    client.sheet.worksheet.side_effect = WorksheetNotFound(None)
    client.sheet.add_worksheet.return_value = new_ws

    out = await client.get_or_create_tab("New Tab", rows=50, cols=2)
    assert out is new_ws
    client.sheet.add_worksheet.assert_called_once_with(
        title="New Tab", rows=50, cols=2
    )


@pytest.mark.asyncio
async def test_check_error_cache_no_file_updates_and_returns_false(
    test_logger,
) -> None:
    client = object.__new__(GoogleSheetClient)
    client.logger = test_logger
    with (
        patch.object(gsheet.path, "exists", return_value=False),
        patch.object(client, "update_error_cache", new_callable=AsyncMock) as upd,
    ):
        out = await client.check_error_cache(["e1"], [], [])
    assert out is False
    upd.assert_awaited_once_with(["e1"], [], [])


@pytest.mark.asyncio
async def test_check_error_cache_matches_returns_true(test_logger) -> None:
    client = object.__new__(GoogleSheetClient)
    client.logger = test_logger
    payload = json.dumps(
        {"errors": [], "invalid_filenames": [], "crosslisted_output": []}
    )
    with (
        patch.object(gsheet.path, "exists", return_value=True),
        patch("builtins.open", mock_open(read_data=payload)),
        patch.object(client, "update_error_cache", new_callable=AsyncMock) as upd,
    ):
        out = await client.check_error_cache([], [], [])
    assert out is True
    upd.assert_not_called()


@pytest.mark.asyncio
async def test_check_error_cache_read_permission_error_returns_false(
    test_logger,
) -> None:
    client = object.__new__(GoogleSheetClient)
    client.logger = test_logger
    with (
        patch.object(gsheet.path, "exists", return_value=True),
        patch("builtins.open", MagicMock(side_effect=PermissionError("denied"))),
        patch.object(client, "update_error_cache", new_callable=AsyncMock) as upd,
    ):
        out = await client.check_error_cache([], [], [])
    assert out is False
    upd.assert_not_called()


@pytest.mark.asyncio
async def test_write_all_errors_short_circuits_when_cache_matches(
    test_logger,
) -> None:
    client = object.__new__(GoogleSheetClient)
    client.logger = test_logger
    client.check_error_cache = AsyncMock(return_value=True)
    client.get_or_create_tab = AsyncMock()

    await client.write_all_errors(["x"], [], [])
    client.get_or_create_tab.assert_not_called()


@pytest.mark.asyncio
async def test_check_class_cache_no_file_updates_and_returns_false(
    test_logger,
) -> None:
    client = object.__new__(GoogleSheetClient)
    client.logger = test_logger
    data = {"CSCI-1": ["CSCI", "1", 0]}
    with (
        patch.object(gsheet.path, "exists", return_value=False),
        patch.object(client, "update_class_cache", new_callable=AsyncMock) as upd,
    ):
        out = await client.check_class_cache(data)
    assert out is False
    upd.assert_awaited_once_with(data)


@pytest.mark.asyncio
async def test_check_class_cache_matches_returns_true(test_logger) -> None:
    client = object.__new__(GoogleSheetClient)
    client.logger = test_logger
    data = {"CSCI-1": ["CSCI", "1", 2]}
    payload = json.dumps(data)
    with (
        patch.object(gsheet.path, "exists", return_value=True),
        patch("builtins.open", mock_open(read_data=payload)),
        patch.object(client, "update_class_cache", new_callable=AsyncMock) as upd,
    ):
        out = await client.check_class_cache(data)
    assert out is True
    upd.assert_not_called()
