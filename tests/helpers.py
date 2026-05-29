"""Shared helpers for tests."""

from __future__ import annotations

import pytest


def named_case(case_name: str, *values: object) -> pytest.ParameterSet:
    """
    Build a pytest.mark.parametrize case with an explicit unique id.

    :param case_name: Stable, human-readable id (also used as pytest param id).
    :param values: Remaining positional values passed to the test (after ``case_name``).
    """
    return pytest.param(case_name, *values, id=case_name)
