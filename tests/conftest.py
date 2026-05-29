"""Pytest fixtures shared across tests."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def caplog_debug(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture
def test_logger() -> logging.Logger:
    logger = logging.getLogger("tests.backtest_compilation")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def fake_gdrive_client() -> MagicMock:
    client = MagicMock()
    client.get_structure = AsyncMock(return_value={})
    client.get_recursive_structure = AsyncMock(return_value={})
    client.rename_file = AsyncMock()
    client.cache_check = AsyncMock(return_value=False)
    client.update_cache = AsyncMock()
    return client


@pytest.fixture
def fake_sheet_client() -> MagicMock:
    client = MagicMock()
    client.write_all_errors = AsyncMock()
    client.update_counts = AsyncMock()
    client.check_error_cache = AsyncMock(return_value=False)
    client.check_class_cache = AsyncMock(return_value=False)
    return client
