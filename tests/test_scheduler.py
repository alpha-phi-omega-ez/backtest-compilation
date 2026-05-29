"""Unit tests for scheduler time helpers."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from scheduler import (
    EASTERN_TZ,
    calculate_sleep_seconds,
    get_next_scheduled_hour,
    should_run,
)
from tests.helpers import named_case


@pytest.mark.parametrize(
    ("case_name", "hour", "expected"),
    [
        named_case("should_run_hour_8_outside_window", 8, False),
        named_case("should_run_hour_9_start_window", 9, True),
        named_case("should_run_hour_15_mid_window", 15, True),
        named_case("should_run_hour_20_end_window", 20, True),
        named_case("should_run_hour_21_outside_window", 21, False),
    ],
)
def test_should_run(case_name: str, hour: int, expected: bool) -> None:
    _ = case_name
    fixed = datetime(2026, 6, 15, hour, 30, 0, tzinfo=EASTERN_TZ)
    with patch("scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        assert should_run() is expected


@pytest.mark.parametrize(
    ("case_name", "current_hour", "expected_next"),
    [
        named_case("next_hour_before_first_slot", 8, 9),
        named_case("next_hour_after_9_before_11", 9, 11),
        named_case("next_hour_after_11_before_13", 11, 13),
        named_case("next_hour_after_17_before_19", 17, 19),
        named_case("next_hour_at_19_none", 19, None),
        named_case("next_hour_late_evening_none", 22, None),
    ],
)
def test_get_next_scheduled_hour(
    case_name: str, current_hour: int, expected_next: int | None
) -> None:
    _ = case_name
    assert get_next_scheduled_hour(current_hour) == expected_next


@pytest.mark.parametrize(
    (
        "case_name",
        "now_dt",
        "expected_seconds",
    ),
    [
        named_case(
            "sleep_before_9am_same_day",
            datetime(2026, 1, 10, 7, 0, 0, tzinfo=EASTERN_TZ),
            7327,
        ),
        named_case(
            "sleep_after_9pm_next_morning",
            datetime(2026, 1, 10, 21, 0, 0, tzinfo=EASTERN_TZ),
            43327,
        ),
        named_case(
            "sleep_inside_window_until_next_slot",
            datetime(2026, 6, 15, 9, 0, 0, 0, tzinfo=EASTERN_TZ),
            7327,
        ),
        named_case(
            "sleep_at_1930_moves_to_next_day_9am",
            datetime(2026, 6, 15, 19, 30, 0, 0, tzinfo=EASTERN_TZ),
            48727,
        ),
    ],
)
def test_calculate_sleep_seconds_exact(
    case_name: str,
    now_dt: datetime,
    expected_seconds: int,
) -> None:
    _ = case_name
    with patch("scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = now_dt
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        assert calculate_sleep_seconds() == expected_seconds
