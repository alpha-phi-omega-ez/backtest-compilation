"""Unit tests for Google Drive client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from googleapiclient.errors import HttpError

import gdrive
from gdrive import GoogleDriveClient


@pytest.fixture
def drive_client(test_logger):
    settings = {"DELEGATE_EMAIL": "delegated@test.com"}
    mock_creds = MagicMock()
    mock_creds.with_subject.return_value = MagicMock()
    p1 = patch(
        "gdrive.service_account.Credentials.from_service_account_file",
        return_value=mock_creds,
    )
    p2 = patch("gdrive.build", return_value=MagicMock())
    p1.start()
    p2.start()
    client = GoogleDriveClient(settings, test_logger)
    yield client
    p1.stop()
    p2.stop()


@pytest.mark.asyncio
async def test_cache_check_missing_file_updates_and_returns_false(
    drive_client: GoogleDriveClient,
) -> None:
    structure = {"root": {"k": 1}}
    with (
        patch.object(gdrive.path, "exists", return_value=False),
        patch.object(drive_client, "update_cache", new_callable=AsyncMock) as upd,
    ):
        out = await drive_client.cache_check(structure)
    assert out is False
    upd.assert_awaited_once_with(structure)


@pytest.mark.asyncio
async def test_cache_check_cache_matches_returns_true(
    drive_client: GoogleDriveClient,
) -> None:
    structure = {"root": {"k": 1}}
    payload = json.dumps(structure)
    with (
        patch.object(gdrive.path, "exists", return_value=True),
        patch("builtins.open", mock_open(read_data=payload)),
        patch.object(drive_client, "update_cache", new_callable=AsyncMock) as upd,
    ):
        out = await drive_client.cache_check(structure)
    assert out is True
    upd.assert_not_called()


@pytest.mark.asyncio
async def test_cache_check_read_permission_error_returns_false(
    drive_client: GoogleDriveClient,
) -> None:
    structure = {"a": 1}
    with (
        patch.object(gdrive.path, "exists", return_value=True),
        patch("builtins.open", MagicMock(side_effect=PermissionError("denied"))),
        patch.object(drive_client, "update_cache", new_callable=AsyncMock) as upd,
    ):
        out = await drive_client.cache_check(structure)
    assert out is False
    upd.assert_not_called()


@pytest.mark.asyncio
async def test_get_structure_raises_system_exit_when_cache_matches(
    drive_client: GoogleDriveClient,
) -> None:
    structure = {"x": 1}
    with (
        patch.object(
            drive_client,
            "get_recursive_structure",
            new_callable=AsyncMock,
            return_value=structure,
        ),
        patch.object(
            drive_client, "cache_check", new_callable=AsyncMock, return_value=True
        ),
    ):
        with pytest.raises(SystemExit):
            await drive_client.get_structure("fid", "drive-id")


@pytest.mark.asyncio
async def test_get_recursive_structure_empty_folder(
    drive_client: GoogleDriveClient,
) -> None:
    list_builder = MagicMock()
    list_builder.execute.return_value = {"files": []}
    files_api = MagicMock()
    files_api.list.return_value = list_builder
    drive_client.service.files.return_value = files_api

    out = await drive_client.get_recursive_structure("root", "drive-id")
    assert out == {}
    drive_client.service.files.assert_called()


@pytest.mark.asyncio
async def test_rename_file_succeeds_first_attempt(
    drive_client: GoogleDriveClient,
) -> None:
    update_builder = MagicMock()
    update_builder.execute.return_value = {}
    files_api = MagicMock()
    files_api.update.return_value = update_builder
    drive_client.service.files.return_value = files_api

    await drive_client.rename_file("fid-1", "new.pdf", "old.pdf")
    files_api.update.assert_called_once()
    update_builder.execute.assert_called_once()


@pytest.mark.asyncio
async def test_rename_file_logs_warning_after_http_errors(
    drive_client: GoogleDriveClient,
) -> None:
    resp = MagicMock(status=500)
    err = HttpError(resp, b"{}")
    update_builder = MagicMock()
    update_builder.execute.side_effect = [err, err, err]
    files_api = MagicMock()
    files_api.update.return_value = update_builder
    drive_client.service.files.return_value = files_api

    await drive_client.rename_file("fid-1", "new.pdf", "old.pdf")
    assert update_builder.execute.call_count == 3
