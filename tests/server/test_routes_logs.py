"""Tests for the log viewer endpoint and the `profiles.log` parser."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.core.telemetry.log_viewer import (
    parse_log_line,
    read_log_entries,
)
from profiles.server.app import create_app
from profiles.server.state import ServerState

GOOD_LINE = (
    "2026-08-29 13:01:15 - INFO  - MACBOOKFA.LOCAL: "
    'SCAN_COMPLETE dir="base" ext=.mttl files=284 recursive=True'
)
ERROR_LINE = '2026-08-29 13:02:44 - ERROR - MACBOOKFA.LOCAL: SCAN_FAILED dir="base" error=missing'
TORN_LINE = "Traceback (most recent call last):"


@pytest.fixture
def log_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ServerState:
    """State whose log file lives in a temp dir, isolated from the repo."""
    monkeypatch.chdir(tmp_path)
    return ServerState(config=AppConfig(title="Test Bench"))


def test_parse_log_line_extracts_level_source_and_event() -> None:
    entry = parse_log_line(GOOD_LINE)

    assert entry.level == "INFO"
    assert entry.source == "MACBOOKFA.LOCAL"
    assert entry.event == "SCAN_COMPLETE"
    assert entry.timestamp == "2026-08-29 13:01:15"
    assert entry.message == 'SCAN_COMPLETE dir="base" ext=.mttl files=284 recursive=True'
    assert not entry.is_error


def test_parse_log_line_flags_warning_and_above_as_errors() -> None:
    assert parse_log_line(ERROR_LINE).is_error
    assert parse_log_line(
        "2026-08-29 13:02:44 - WARNING - HOST: THEME_SWITCHED value=light"
    ).is_error


def test_parse_log_line_handles_user_host_source() -> None:
    """Sources in ``user@host`` form (e.g. f.albany@ST-465) stay intact."""
    entry = parse_log_line(
        '2026-10-22 15:05:22 - INFO  - f.albany@ST-465: SCAN_COMPLETE dir="base" '
        "ext=.mttl filter=Tester files=51 recursive=true"
    )

    assert entry.source == "f.albany@ST-465"
    assert entry.level == "INFO"
    assert entry.event == "SCAN_COMPLETE"


def test_parse_log_line_preserves_unrecognised_lines() -> None:
    entry = parse_log_line(TORN_LINE)

    # A torn line must never be dropped: it stays visible, unparsed.
    assert entry.level == "UNKNOWN"
    assert entry.message == TORN_LINE
    assert entry.raw == TORN_LINE
    assert not entry.is_error


def test_read_log_entries_returns_empty_when_file_missing(tmp_path: Path) -> None:
    assert read_log_entries(tmp_path / "absent.log") == []


def test_read_log_entries_filters_by_severity(tmp_path: Path) -> None:
    log = tmp_path / "profiles.log"
    log.write_text("\n".join([GOOD_LINE, ERROR_LINE, TORN_LINE]) + "\n", encoding="utf-8")

    # Unparsed lines bypass the severity filter so a torn line is never hidden.
    assert [e.level for e in read_log_entries(log, level="ERROR")] == ["ERROR", "UNKNOWN"]
    # DEBUG keeps every level.
    assert len(read_log_entries(log, level="DEBUG")) == 3


def test_read_log_entries_filters_by_substring(tmp_path: Path) -> None:
    log = tmp_path / "profiles.log"
    log.write_text("\n".join([GOOD_LINE, ERROR_LINE]) + "\n", encoding="utf-8")

    hits = read_log_entries(log, search="scan_")

    assert len(hits) == 2
    assert all("SCAN_" in entry.message for entry in hits)


def test_read_log_entries_respects_limit(tmp_path: Path) -> None:
    log = tmp_path / "profiles.log"
    log.write_text(
        "\n".join([f"2026-08-29 13:01:{i:02d} - INFO  - HOST: EVENT n={i}" for i in range(10)])
        + "\n",
        encoding="utf-8",
    )

    tail = read_log_entries(log, limit=3)

    # Newest last, oldest first.
    assert len(tail) == 3
    assert tail[-1].message.endswith("n=9")


@pytest.mark.anyio
async def test_get_logs_returns_entries_and_size(log_state: ServerState) -> None:
    Path("profiles.log").write_text(GOOD_LINE + "\n" + ERROR_LINE + "\n", encoding="utf-8")
    app = create_app(log_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/logs")

    assert response.status_code == 200
    data = response.json()
    assert data["path"] == "profiles.log"
    assert data["total_returned"] == 2
    assert data["size_bytes"] > 0
    assert data["entries"][0]["event"] == "SCAN_COMPLETE"
    assert data["entries"][1]["level"] == "ERROR"


@pytest.mark.anyio
async def test_get_logs_empty_file_is_not_an_error(log_state: ServerState) -> None:
    app = create_app(log_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/logs")

    assert response.status_code == 200
    assert response.json()["entries"] == []


@pytest.mark.anyio
async def test_get_logs_rejects_unknown_level(log_state: ServerState) -> None:
    app = create_app(log_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/logs?level=VERBOSE")

    assert response.status_code == 400
    assert "VERBOSE" in response.json()["detail"]


@pytest.mark.anyio
async def test_get_logs_honours_limit(log_state: ServerState) -> None:
    lines = "\n".join(f"2026-08-29 13:01:{i:02d} - INFO  - HOST: EVENT n={i}" for i in range(5))
    Path("profiles.log").write_text(lines + "\n", encoding="utf-8")
    app = create_app(log_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/logs?limit=2")

    assert response.json()["total_returned"] == 2
