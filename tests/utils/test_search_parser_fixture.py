"""Fixture-driven conformance tests for the shared Py/TS operator fixture.

Reads ``src/profiles/web/src/utils/searchOperators.fixture.json`` — the
anti-drift contract between this Python grammar (normative) and the
TypeScript port in ``profiles.web`` — and replays every case through
:func:`match_file` (operator mode) or :func:`match_filter` (substring
mode). Expectations in the fixture are hand-derived from the documented
semantics, never generated from the implementation.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from profiles.core.processing.file_metadata import FileAttrs
from profiles.utils.search_parser import match_file, match_filter

FIXTURE = (
    Path(__file__).resolve().parents[2] / "src/profiles/web/src/utils/searchOperators.fixture.json"
)

_FIXTURE_DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _anchor_epoch(spec: dict, now: float) -> float:
    """Resolve a fixture anchor spec into an epoch timestamp.

    Mirrors the evaluator's anchoring: ``"now"`` passes *now* through,
    ``"today"`` is the local midnight of *now*, and ``"date"`` is the
    local midnight of its ``YYYY-MM-DD`` day. ``offset_seconds`` is added
    in every case.
    """
    origin = spec["from"]
    offset = float(spec.get("offset_seconds", 0))
    if origin == "now":
        return now + offset
    if origin == "today":
        local = datetime.fromtimestamp(now)
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight.timestamp() + offset
    year, month, day = str(spec["date"]).split("-")
    return datetime(int(year), int(month), int(day)).timestamp() + offset


@pytest.mark.parametrize("case", _FIXTURE_DATA["operator_cases"], ids=lambda case: case["name"])
def test_operator_case(case: dict) -> None:
    """Replay one operator-mode fixture case through ``match_file``."""
    attrs = (
        None
        if case["attrs"] is None
        else FileAttrs(
            case["attrs"]["size_bytes"],
            _anchor_epoch(case["attrs"]["mtime"], case["now"]),
            _anchor_epoch(case["attrs"]["birthtime"], case["now"]),
        )
    )
    assert match_file(case["filename"], case["query"], attrs, now=case["now"]) is case["expected"]


@pytest.mark.parametrize("case", _FIXTURE_DATA["substring_cases"], ids=lambda case: case["name"])
def test_substring_case(case: dict) -> None:
    """Replay one substring-mode fixture case through ``match_filter``."""
    assert match_filter(case["filename"], case["query"]) is case["expected"]
