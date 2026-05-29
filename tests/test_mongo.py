"""Unit tests for Mongo backtest sync helpers."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mongo import MongoClient
from tests.helpers import named_case


@pytest.mark.parametrize(
    ("case_name", "exam", "expected"),
    [
        named_case(
            "sort_key_quiz_without_number",
            {"type": "Quiz", "tests": []},
            (1, 0),
        ),
        named_case(
            "sort_key_exam_with_numeric_suffix",
            {"type": "Exam 2", "tests": []},
            (2, 2),
        ),
        named_case(
            "sort_key_midterm_non_digit_suffix_sorts_last",
            {"type": "Midterm X", "tests": []},
            (3, float("inf")),
        ),
    ],
)
def test_sort_key(
    case_name: str, exam: dict, expected: tuple[int, int | float]
) -> None:
    _ = case_name
    assert MongoClient.sort_key(exam) == expected


@pytest.mark.parametrize(
    ("case_name", "tests", "expected"),
    [
        named_case(
            "sort_tests_orders_newest_year_then_season",
            ["Spring 2024", "Fall 2023", "Summer 2025"],
            ["Summer 2025", "Spring 2024", "Fall 2023"],
        ),
        named_case(
            "sort_tests_same_year_orders_fall_before_spring_descending_season_rank",
            ["Fall 2024", "Spring 2024"],
            ["Fall 2024", "Spring 2024"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_sort_tests(
    case_name: str, tests: list[str], expected: list[str]
) -> None:
    _ = case_name
    assert await MongoClient.sort_tests(tests) == expected


@pytest.mark.parametrize(
    (
        "case_name",
        "current_tests",
        "expect_insert",
        "expect_update",
    ),
    [
        named_case(
            "process_class_inserts_when_no_backtest_doc",
            None,
            True,
            False,
        ),
        named_case(
            "process_class_updates_when_tests_differ",
            {"_id": 99, "tests": [{"type": "Quiz", "tests": ["Fall 2020"]}]},
            False,
            True,
        ),
        named_case(
            "process_class_noop_when_tests_equal",
            {
                "_id": 99,
                "tests": [{"type": "Quiz 1", "tests": ["Fall 2024"]}],
            },
            False,
            False,
        ),
    ],
)
@pytest.mark.asyncio
async def test_process_class_writes(
    case_name: str,
    current_tests: dict | None,
    expect_insert: bool,
    expect_update: bool,
    test_logger: logging.Logger,
) -> None:
    _ = case_name
    client = object.__new__(MongoClient)
    client.logger = test_logger
    client.backtest_courses_collection = AsyncMock()
    client.backtest_collection = AsyncMock()
    client.backtest_courses_collection.find_one = AsyncMock(
        return_value={"_id": 1, "name": "CSCI-1200 Data Structures"}
    )
    client.backtest_collection.find_one = AsyncMock(return_value=current_tests)
    client.backtest_collection.insert_one = AsyncMock()
    client.backtest_collection.update_one = AsyncMock()

    exams = [{"type": "Quiz 1", "tests": ["Fall 2024"]}]
    current_courses = {"CSCI-1200 Data Structures": 1}

    await client.process_class("CSCI-1200 Data Structures", exams, current_courses)

    if expect_insert:
        client.backtest_collection.insert_one.assert_awaited_once()
        client.backtest_collection.update_one.assert_not_called()
    elif expect_update:
        client.backtest_collection.update_one.assert_awaited_once()
        client.backtest_collection.insert_one.assert_not_called()
    else:
        client.backtest_collection.insert_one.assert_not_called()
        client.backtest_collection.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_process_class_missing_course_raises(test_logger: logging.Logger) -> None:
    client = object.__new__(MongoClient)
    client.logger = test_logger
    client.backtest_courses_collection = AsyncMock()
    client.backtest_collection = AsyncMock()
    client.backtest_courses_collection.find_one = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="not found"):
        await client.process_class("MISSING-0000 None", [], {})


@pytest.mark.parametrize(
    (
        "case_name",
        "existing_codes",
        "incoming_codes",
        "expect_insert_many",
        "expect_delete_many",
    ),
    [
        named_case(
            "update_course_codes_adds_only_new",
            {"CSCI"},
            {"CSCI", "MATH"},
            {"MATH"},
            set(),
        ),
        named_case(
            "update_course_codes_removes_stale",
            {"CSCI", "MATH"},
            {"CSCI"},
            set(),
            {"MATH"},
        ),
        named_case(
            "update_course_codes_noops_when_in_sync",
            {"CSCI"},
            {"CSCI"},
            set(),
            set(),
        ),
    ],
)
@pytest.mark.asyncio
async def test_update_course_codes(
    case_name: str,
    existing_codes: set[str],
    incoming_codes: set[str],
    expect_insert_many: set[str],
    expect_delete_many: set[str],
    test_logger: logging.Logger,
) -> None:
    _ = case_name
    client = object.__new__(MongoClient)
    client.logger = test_logger
    coll = MagicMock()
    coll.insert_many = AsyncMock()
    coll.delete_many = AsyncMock()

    async def fake_find() -> Any:
        for code in sorted(existing_codes):
            yield {"course_code": code}

    coll.find = lambda *a, **k: fake_find()
    client.backtest_course_code_collection = coll

    await client.update_course_codes(incoming_codes)

    if expect_insert_many:
        coll.insert_many.assert_awaited_once()
        inserted = coll.insert_many.await_args.args[0]
        got = {doc["course_code"] for doc in inserted}
        assert got == expect_insert_many
    else:
        coll.insert_many.assert_not_called()

    if expect_delete_many:
        coll.delete_many.assert_awaited_once()
        fil = coll.delete_many.await_args.args[0]
        assert set(fil["course_code"]["$in"]) == expect_delete_many
    else:
        coll.delete_many.assert_not_called()


class _FakeFindCursor:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = items

    def __aiter__(self) -> _FakeFindCursor:
        self._idx = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


class _RecordingCollection:
    """Minimal async collection for add_to_mongo happy-path tests."""

    def __init__(self) -> None:
        self._id = 1
        self.docs: list[dict[str, Any]] = []
        self.insert_many_calls: list[list[dict[str, Any]]] = []
        self.insert_one_calls: list[dict[str, Any]] = []
        self.delete_many_calls: list[dict[str, Any]] = []

    def find(self, query: dict | None = None) -> _FakeFindCursor:
        if not query:
            return _FakeFindCursor(list(self.docs))
        if "name" in query and "$in" in query["name"]:
            names = set(query["name"]["$in"])
            return _FakeFindCursor([d for d in self.docs if d.get("name") in names])
        return _FakeFindCursor(list(self.docs))

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        if "name" in query:
            for d in self.docs:
                if d.get("name") == query["name"]:
                    return dict(d)
        if "course_ids" in query:
            wanted = query["course_ids"].get("$in", [])
            for d in self.docs:
                if set(d.get("course_ids", [])) & set(wanted):
                    return dict(d)
        return None

    async def insert_many(self, items: list[dict[str, Any]]) -> None:
        self.insert_many_calls.append(items)
        for doc in items:
            row = dict(doc)
            if "_id" not in row:
                row["_id"] = self._id
                self._id += 1
            self.docs.append(row)

    async def insert_one(self, doc: dict[str, Any]) -> None:
        self.insert_one_calls.append(doc)
        row = dict(doc)
        if "_id" not in row:
            row["_id"] = self._id
            self._id += 1
        self.docs.append(row)

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> None:
        _id = query["_id"]
        for d in self.docs:
            if d.get("_id") == _id:
                if "$set" in update:
                    d.update(update["$set"])
                return

    async def delete_many(self, query: dict[str, Any]) -> None:
        self.delete_many_calls.append(query)
        if "name" in query and isinstance(query["name"], dict):
            names = set(query["name"].get("$in", []))
            if names:
                self.docs = [d for d in self.docs if d.get("name") not in names]
            return
        if "course_ids" in query and isinstance(query["course_ids"], dict):
            wanted = set(query["course_ids"].get("$in", []))
            if not wanted:
                return

            def _keep(row: dict[str, Any]) -> bool:
                cids = set(row.get("course_ids", []))
                return cids.isdisjoint(wanted)

            self.docs = [d for d in self.docs if _keep(d)]


@pytest.mark.parametrize(
    (
        "case_name",
        "seed_course_codes",
        "seed_courses",
        "seed_backtests",
        "results",
        "all_dpts",
        "all_classnames",
        "expect_new_course_name",
    ),
    [
        named_case(
            "add_to_mongo_inserts_new_course_and_tests",
            [],
            [],
            [],
            {
                "CSCI-1200 Data Structures": [
                    {"type": "Quiz 1", "tests": ["Spring 2024"]},
                ]
            },
            {"CSCI"},
            {"CSCI-1200 Data Structures": ["CSCI", "1200", 0]},
            "CSCI-1200 Data Structures",
        ),
    ],
)
@pytest.mark.asyncio
async def test_add_to_mongo_happy_path(
    case_name: str,
    seed_course_codes: list[dict[str, Any]],
    seed_courses: list[dict[str, Any]],
    seed_backtests: list[dict[str, Any]],
    results: dict,
    all_dpts: set[str],
    all_classnames: dict,
    expect_new_course_name: str,
    test_logger: logging.Logger,
) -> None:
    _ = case_name
    client = object.__new__(MongoClient)
    client.logger = test_logger
    client.client = MagicMock(close=AsyncMock())

    codes = _RecordingCollection()
    codes.docs = list(seed_course_codes)
    courses = _RecordingCollection()
    courses.docs = list(seed_courses)
    backtests = _RecordingCollection()
    backtests.docs = list(seed_backtests)

    client.backtest_course_code_collection = codes  # type: ignore[assignment]
    client.backtest_courses_collection = courses  # type: ignore[assignment]
    client.backtest_collection = backtests  # type: ignore[assignment]

    await client.add_to_mongo(results, all_dpts, all_classnames)

    names = {d["name"] for d in courses.docs if "name" in d}
    assert expect_new_course_name in names

    course_row = next(
        d for d in courses.docs if d.get("name") == expect_new_course_name
    )
    cid = course_row["_id"]
    match = next(
        (d for d in backtests.docs if d.get("course_ids") == [cid] and d.get("tests")),
        None,
    )
    assert match is not None
    assert match["tests"] == results[expect_new_course_name]


@pytest.mark.asyncio
async def test_add_to_mongo_removes_stale_classes_not_in_drive(
    test_logger: logging.Logger,
) -> None:
    """Stale courses and their backtest docs are removed when absent from Drive."""
    client = object.__new__(MongoClient)
    client.logger = test_logger
    client.client = MagicMock(close=AsyncMock())

    codes = _RecordingCollection()
    codes.docs = [{"course_code": "CSCI"}]
    courses = _RecordingCollection()
    courses.docs = [
        {"_id": 10, "name": "OLD-1000 Retired", "course_code": "OLD"},
    ]
    backtests = _RecordingCollection()
    backtests.docs = [
        {
            "_id": 1,
            "course_ids": [10],
            "tests": [{"type": "Quiz 1", "tests": ["Fall 2020"]}],
        }
    ]

    client.backtest_course_code_collection = codes  # type: ignore[assignment]
    client.backtest_courses_collection = courses  # type: ignore[assignment]
    client.backtest_collection = backtests  # type: ignore[assignment]

    results = {
        "CSCI-1200 Data Structures": [
            {"type": "Quiz 1", "tests": ["Spring 2024"]},
        ]
    }
    all_dpts = {"CSCI", "OLD"}
    all_classnames = {"CSCI-1200 Data Structures": ["CSCI", "1200", 0]}

    await client.add_to_mongo(results, all_dpts, all_classnames)

    assert "OLD-1000 Retired" not in {d.get("name") for d in courses.docs}
    assert any(
        q.get("name", {}).get("$in") == ["OLD-1000 Retired"]
        for q in courses.delete_many_calls
    )
    backtest_delete_queries = [
        q for q in backtests.delete_many_calls if "course_ids" in q
    ]
    assert backtest_delete_queries
    assert any(
        set(q["course_ids"]["$in"]) == {10} for q in backtest_delete_queries
    )
    assert not any(10 in d.get("course_ids", []) for d in backtests.docs)
    assert "CSCI-1200 Data Structures" in {d.get("name") for d in courses.docs}
