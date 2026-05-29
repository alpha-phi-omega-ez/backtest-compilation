"""Unit tests for settings loading."""

from __future__ import annotations

import pytest

import settings
from tests.helpers import named_case


@pytest.mark.parametrize(
    (
        "case_name",
        "env",
        "expected_subset",
    ),
    [
        named_case(
            "settings_all_env_set",
            {
                "FOLDER_ID": "fid",
                "DELEGATE_EMAIL": "u@example.com",
                "SHEET_URL": "https://sheet",
                "MONGO_URI": "mongodb://mongo:27017",
                "LOG_LEVEL": "DEBUG",
                "SENTRY_DSN": "https://sentry",
                "SENTRY_TRACE_RATE": "0.5",
            },
            {
                "FOLDER_ID": "fid",
                "DELEGATE_EMAIL": "u@example.com",
                "SHEET_URL": "https://sheet",
                "MONGO_URI": "mongodb://mongo:27017",
                "LOG_LEVEL": "DEBUG",
                "SENTRY_DSN": "https://sentry",
                "SENTRY_TRACE_RATE": "0.5",
            },
        ),
        named_case(
            "settings_defaults_for_optional_keys",
            {
                "FOLDER_ID": None,
                "DELEGATE_EMAIL": None,
                "SHEET_URL": None,
            },
            {
                "MONGO_URI": "mongodb://localhost:27017",
                "LOG_LEVEL": "INFO",
                "SENTRY_DSN": "",
                "SENTRY_TRACE_RATE": 1.0,
            },
        ),
    ],
)
def test_get_settings(
    case_name: str,
    env: dict[str, str | None],
    expected_subset: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = case_name
    monkeypatch.setattr(settings, "load_dotenv", lambda *_a, **_k: None)
    for key, value in env.items():
        monkeypatch.setenv(key, value) if value is not None else monkeypatch.delenv(
            key, raising=False
        )
    for key in (
        "FOLDER_ID",
        "DELEGATE_EMAIL",
        "SHEET_URL",
        "MONGO_URI",
        "LOG_LEVEL",
        "SENTRY_DSN",
        "SENTRY_TRACE_RATE",
    ):
        if key not in env:
            monkeypatch.delenv(key, raising=False)

    result = settings.get_settings()
    for k, v in expected_subset.items():
        assert result[k] == v
