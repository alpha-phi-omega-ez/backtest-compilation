"""Unit tests for main orchestration and helpers."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import main
from tests.helpers import named_case


@pytest.mark.parametrize(
    ("case_name", "level_str", "expected_level"),
    [
        named_case("log_level_debug_upper", "DEBUG", logging.DEBUG),
        named_case("log_level_info_mixed_case", "InFo", logging.INFO),
        named_case("log_level_unknown_defaults_info", "NOT_A_LEVEL", logging.INFO),
    ],
)
def test_get_log_level(case_name: str, level_str: str, expected_level: int) -> None:
    _ = case_name
    assert main.get_log_level(level_str) == expected_level


@pytest.mark.parametrize(
    ("case_name", "raise_in_mongo"),
    [
        named_case("main_closes_mongo_after_success", False),
        named_case("main_closes_mongo_when_mongo_raises", True),
    ],
)
@pytest.mark.asyncio
async def test_main_orchestration_and_mongo_cleanup(
    case_name: str,
    raise_in_mongo: bool,
) -> None:
    _ = case_name
    settings_dict = {
        "FOLDER_ID": "folder",
        "DELEGATE_EMAIL": "u@example.com",
        "SHEET_URL": "https://example.com/sheet",
        "MONGO_URI": "mongodb://localhost",
        "LOG_LEVEL": "INFO",
        "SENTRY_DSN": "",
        "SENTRY_TRACE_RATE": 1.0,
    }

    gdrive_instance = MagicMock()
    gdrive_instance.get_structure = AsyncMock(return_value={"root": {"name": "x"}})

    sheet_instance = MagicMock()
    sheet_instance.update_counts = AsyncMock()

    mongo_instance = MagicMock()
    mongo_instance.add_to_mongo = AsyncMock(
        side_effect=RuntimeError("boom") if raise_in_mongo else None
    )
    mongo_instance.close = AsyncMock()

    interpret = AsyncMock(
        return_value=(
            {"CSCI-1200 X": []},
            {"CSCI"},
            {"CSCI-1200 X": ["CSCI", "1200", 1]},
        )
    )

    tick = {"v": 0.0}

    def fake_time() -> float:
        out = tick["v"]
        tick["v"] += 1.0
        return out

    with (
        patch.object(main, "get_settings", return_value=settings_dict),
        patch.object(main, "sentry_sdk") as mock_sentry,
        patch.object(main, "GoogleDriveClient", return_value=gdrive_instance),
        patch.object(main, "GoogleSheetClient", return_value=sheet_instance),
        patch.object(main, "MongoClient", return_value=mongo_instance),
        patch.object(main, "interpret_backtests", interpret),
        patch.object(main, "time", fake_time),
    ):
        mock_sentry.init = MagicMock()

        if raise_in_mongo:
            with pytest.raises(RuntimeError, match="boom"):
                await main.main()
        else:
            await main.main()

    gdrive_instance.get_structure.assert_awaited_once()
    interpret.assert_awaited_once()

    if raise_in_mongo:
        mongo_instance.add_to_mongo.assert_awaited_once()
        mongo_instance.close.assert_awaited_once()
        sheet_instance.update_counts.assert_not_called()
    else:
        mongo_instance.add_to_mongo.assert_awaited_once()
        assert mongo_instance.close.await_count == 2
        sheet_instance.update_counts.assert_awaited_once()
