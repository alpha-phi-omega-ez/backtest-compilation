"""Unit tests for Drive backtest interpretation."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

import process_data
from process_data import (
    interpret_backtests,
    process_course,
    process_department,
    process_test,
)
from tests.helpers import named_case


@pytest.fixture
def patch_current_year(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_data, "current_year", 25)


@pytest.mark.parametrize(
    (
        "case_name",
        "children",
        "filename",
        "dptname",
        "classnum",
        "expect_error_folder",
        "expect_invalid",
        "expect_rename",
    ),
    [
        named_case(
            "process_test_rejects_nested_folder",
            {"x": 1},
            "anything.pdf",
            "CSCI",
            "1200",
            True,
            False,
            False,
        ),
        named_case(
            "process_test_invalid_filename_no_match",
            None,
            "not-a-valid-exam.pdf",
            "CSCI",
            "1200",
            False,
            True,
            False,
        ),
        named_case(
            "process_test_valid_quiz_no_rename",
            None,
            "CSCI-1200 QF24.pdf",
            "CSCI",
            "1200",
            False,
            False,
            False,
        ),
        named_case(
            "process_test_triggers_rename_when_canonical_differs",
            None,
            "csci-1200 q f24.pdf",
            "CSCI",
            "1200",
            False,
            False,
            True,
        ),
    ],
)
@pytest.mark.usefixtures("patch_current_year")
async def test_process_test_errors_and_rename(
    case_name: str,
    children: dict | None,
    filename: str,
    dptname: str,
    classnum: str,
    expect_error_folder: bool,
    expect_invalid: bool,
    expect_rename: bool,
    test_logger: logging.Logger,
) -> None:
    _ = case_name
    gdrive = AsyncMock()
    errors: list[str] = []
    invalid_filenames: list[str] = []
    full_classname = f"{dptname}-{classnum} Data Structures"
    all_classnames = {full_classname: [dptname, classnum, 0]}
    results: dict = {}

    await process_test(
        children,
        filename,
        dptname,
        classnum,
        "file-id-1",
        results,
        full_classname,
        all_classnames,
        test_logger,
        errors,
        invalid_filenames,
        gdrive,
    )

    if expect_error_folder:
        assert errors and "Folder" in errors[0]
        assert not invalid_filenames
        gdrive.rename_file.assert_not_called()
        return

    if expect_invalid:
        assert invalid_filenames
        assert "Invalid filename" in invalid_filenames[0]
        gdrive.rename_file.assert_not_called()
        return

    if expect_rename:
        gdrive.rename_file.assert_awaited_once()
    else:
        gdrive.rename_file.assert_not_called()

    assert full_classname in results
    assert all_classnames[full_classname][2] == 1


@pytest.mark.parametrize(
    (
        "case_name",
        "filename",
        "dptname",
        "year_suffix",
        "expect_invalid_year",
    ),
    [
        named_case(
            "process_test_future_year_blocked_for_csci",
            "CSCI-1200 E1 F26.pdf",
            "CSCI",
            "26",
            True,
        ),
        named_case(
            "process_test_future_year_allowed_for_bear",
            "BEAR-1000 E1 F26.pdf",
            "BEAR",
            "26",
            False,
        ),
    ],
)
async def test_process_test_year_gate(
    case_name: str,
    filename: str,
    dptname: str,
    year_suffix: str,
    expect_invalid_year: bool,
    monkeypatch: pytest.MonkeyPatch,
    test_logger: logging.Logger,
) -> None:
    _ = year_suffix
    _ = case_name
    monkeypatch.setattr(process_data, "current_year", 25)
    gdrive = AsyncMock()
    errors: list[str] = []
    invalid_filenames: list[str] = []
    classnum = "1200" if dptname == "CSCI" else "1000"
    full_classname = f"{dptname}-{classnum} Sample"
    all_classnames = {full_classname: [dptname, classnum, 0]}
    results: dict = {}

    await process_test(
        None,
        filename,
        dptname,
        classnum,
        "fid",
        results,
        full_classname,
        all_classnames,
        test_logger,
        errors,
        invalid_filenames,
        gdrive,
    )

    if expect_invalid_year:
        assert any("Invalid year" in m for m in invalid_filenames)
        assert full_classname not in results
    else:
        assert full_classname in results
        assert not any("Invalid year" in m for m in invalid_filenames)


@pytest.mark.parametrize(
    (
        "case_name",
        "files",
        "classname",
        "dptname",
        "expect_duplicate_class_error",
    ),
    [
        named_case(
            "process_course_flags_non_class_file",
            None,
            "not-a-class",
            "CSCI",
            False,
        ),
        named_case(
            "process_course_duplicate_class_number",
            {},
            "CSCI-1200 Data Structures",
            "CSCI",
            True,
        ),
    ],
)
async def test_process_course_branching(
    case_name: str,
    files: dict | None,
    classname: str,
    dptname: str,
    expect_duplicate_class_error: bool,
    test_logger: logging.Logger,
) -> None:
    _ = case_name
    gdrive = AsyncMock()
    all_classnums: set[tuple[str, str]] = set()
    if expect_duplicate_class_error:
        all_classnums.add((dptname, "1200"))
    all_classnames: dict = {}
    results: dict = {}
    errors: list[str] = []
    crosslisted: list[str] = []
    invalid_filenames: list[str] = []

    await process_course(
        files,
        classname,
        dptname,
        all_classnums,
        all_classnames,
        results,
        test_logger,
        errors,
        crosslisted,
        invalid_filenames,
        gdrive,
    )

    if files is None:
        assert errors and "not a CLASS" in errors[0]
        return

    if expect_duplicate_class_error:
        assert any("Duplicate CLASS" in e for e in errors)
        return

    assert not crosslisted


@pytest.mark.asyncio
async def test_process_course_same_title_across_depts_crosslists(
    test_logger: logging.Logger,
) -> None:
    """Same title across departments is reported as crosslisted."""
    gdrive = AsyncMock()
    all_classnums: set[tuple[str, str]] = set()
    all_classnames: dict = {}
    results: dict = {}
    errors: list[str] = []
    crosslisted: list[str] = []
    invalid_filenames: list[str] = []

    await process_course(
        {},
        "CSCI-1200 Shared Title",
        "CSCI",
        all_classnums,
        all_classnames,
        results,
        test_logger,
        errors,
        crosslisted,
        invalid_filenames,
        gdrive,
    )

    await process_course(
        {},
        "MATH-2200 Shared Title",
        "MATH",
        all_classnums,
        all_classnames,
        results,
        test_logger,
        errors,
        crosslisted,
        invalid_filenames,
        gdrive,
    )

    assert crosslisted == [
        "Crosslisted CLASS: MATH-2200 Shared Title is CSCI-1200 and MATH-2200"
    ]
    assert "CSCI-1200 Shared Title" in all_classnames
    assert "MATH-2200 Shared Title" in all_classnames


@pytest.mark.parametrize(
    (
        "case_name",
        "dept_folder_name",
        "expect_invalid_department",
        "expect_duplicate_department",
    ),
    [
        named_case(
            "process_department_invalid_name_no_match",
            "###",
            True,
            False,
        ),
        named_case(
            "process_department_valid_prefix",
            "xCSCI",
            False,
            False,
        ),
        named_case(
            "process_department_duplicate_department_code",
            "yCSCI",
            False,
            True,
        ),
    ],
)
async def test_process_department_validation(
    case_name: str,
    dept_folder_name: str,
    expect_invalid_department: bool,
    expect_duplicate_department: bool,
    test_logger: logging.Logger,
) -> None:
    _ = case_name
    gdrive = AsyncMock()
    did = "dept-1"
    structure = {
        did: {
            "name": dept_folder_name,
            "children": {},
        }
    }
    all_dpts: set[str] = set()
    if expect_duplicate_department:
        all_dpts.add("CSCI")
    all_classnums: set[tuple[str, str]] = set()
    all_classnames: dict = {}
    results: dict = {}
    errors: list[str] = []
    crosslisted: list[str] = []
    invalid_filenames: list[str] = []

    await process_department(
        structure,
        did,
        all_dpts,
        all_classnums,
        all_classnames,
        results,
        test_logger,
        errors,
        crosslisted,
        invalid_filenames,
        gdrive,
    )

    if expect_invalid_department:
        assert any("Invalid DEPARTMENT" in e for e in errors)
        return

    if expect_duplicate_department:
        assert any("Duplicate DEPARTMENT" in e for e in errors)
        return

    assert "CSCI" in all_dpts


async def test_interpret_backtests_calls_sheet_and_returns_aggregate(
    test_logger: logging.Logger,
) -> None:
    sheet = AsyncMock()
    gdrive = AsyncMock()
    structure = {
        "d1": {
            "name": "zDEPT",
            "children": None,
        }
    }

    results, dpts, classnames = await interpret_backtests(
        test_logger, structure, sheet, gdrive
    )

    sheet.write_all_errors.assert_awaited_once()
    assert isinstance(results, dict)
    assert isinstance(dpts, set)
    assert isinstance(classnames, dict)


@pytest.mark.asyncio
async def test_process_course_department_name_mismatch(
    test_logger: logging.Logger,
) -> None:
    gdrive = AsyncMock()
    all_classnums: set[tuple[str, str]] = set()
    all_classnames: dict = {}
    results: dict = {}
    errors: list[str] = []
    crosslisted: list[str] = []
    invalid_filenames: list[str] = []

    await process_course(
        {},
        "MATH-1200 Linear Algebra",
        "CSCI",
        all_classnums,
        all_classnames,
        results,
        test_logger,
        errors,
        crosslisted,
        invalid_filenames,
        gdrive,
    )

    assert any("Department name does not match" in e for e in errors)


@pytest.mark.asyncio
async def test_process_department_skips_when_children_is_none(
    test_logger: logging.Logger,
) -> None:
    gdrive = AsyncMock()
    did = "d1"
    structure = {
        did: {
            "name": "xCSCI",
            "children": None,
        }
    }
    all_dpts: set[str] = set()
    all_classnums: set[tuple[str, str]] = set()
    all_classnames: dict = {}
    results: dict = {}
    errors: list[str] = []
    crosslisted: list[str] = []
    invalid_filenames: list[str] = []

    await process_department(
        structure,
        did,
        all_dpts,
        all_classnums,
        all_classnames,
        results,
        test_logger,
        errors,
        crosslisted,
        invalid_filenames,
        gdrive,
    )

    assert not errors
    assert all_dpts == set()


@pytest.mark.asyncio
async def test_process_department_skips_when_folder_name_too_long(
    test_logger: logging.Logger,
) -> None:
    gdrive = AsyncMock()
    did = "d1"
    structure = {
        did: {
            "name": "TOOLONG",
            "children": {},
        }
    }
    all_dpts: set[str] = set()
    all_classnums: set[tuple[str, str]] = set()
    all_classnames: dict = {}
    results: dict = {}
    errors: list[str] = []
    crosslisted: list[str] = []
    invalid_filenames: list[str] = []

    await process_department(
        structure,
        did,
        all_dpts,
        all_classnums,
        all_classnames,
        results,
        test_logger,
        errors,
        crosslisted,
        invalid_filenames,
        gdrive,
    )

    assert not errors
    assert all_dpts == set()
