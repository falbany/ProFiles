"""Tests for the find_path offset lookup on GET /api/scan/results (#218)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig, ColumnConfiguration
from profiles.core.processing.file_metadata import FileAttrs
from profiles.core.processing.scanner import ScannedFileDynamic
from profiles.server.app import create_app
from profiles.server.state import ServerState


def _row(
    path: Path,
    column_values: dict[str, str],
    attrs: FileAttrs | None = None,
) -> ScannedFileDynamic:
    """Build a cached-result row for server tests (filename = path.name)."""
    return ScannedFileDynamic(
        path=path, column_values=column_values, rel_path=path.name, attrs=attrs
    )


@pytest.fixture
def test_state(tmp_path: Path) -> ServerState:
    test_dir = tmp_path / "programs"
    test_dir.mkdir()
    config = AppConfig(
        title="Test Bench",
        search_dir=str(test_dir),
        extensions=(".mttl",),
    )
    return ServerState(config=config, active_directory=test_dir)


@pytest.mark.anyio
async def test_find_path_returns_offset_in_scan_order(test_state: ServerState) -> None:
    """find_path returns the row's offset in the cached scan order.

    The response carries only count/offset — item serialization is
    skipped entirely so large caches answer cheaply.
    """
    root = test_state.active_directory
    assert root is not None
    test_state.cached_results = [
        _row(root / "a.mttl", {}),
        _row(root / "b.mttl", {}),
        _row(root / "c.mttl", {}),
    ]

    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/scan/results", params={"find_path": str(root / "b.mttl")})

    payload = response.json()
    assert payload == {"count": 3, "offset": 1}
    assert "items" not in payload


@pytest.mark.anyio
async def test_find_path_respects_sort(test_state: ServerState) -> None:
    """The offset is the position in the SORTED set, not the scan order."""
    root = test_state.active_directory
    assert root is not None
    test_state.cached_results = [
        _row(root / "zeta.mttl", {"Rank": "3"}),
        _row(root / "mid.mttl", {"Rank": "2"}),
        _row(root / "alpha.mttl", {"Rank": "1"}),
    ]

    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ascending = await client.get(
            "/api/scan/results",
            params={"find_path": str(root / "alpha.mttl"), "sort_by": "Rank"},
        )
        descending = await client.get(
            "/api/scan/results",
            params={
                "find_path": str(root / "alpha.mttl"),
                "sort_by": "Rank",
                "sort_dir": "desc",
            },
        )

    # Scan order puts alpha.mttl at index 2; sorting by Rank moves it to 0
    # ascending and back to 2 descending.
    assert ascending.json() == {"count": 3, "offset": 0}
    assert descending.json() == {"count": 3, "offset": 2}


@pytest.mark.anyio
async def test_find_path_missing_returns_minus_one(test_state: ServerState) -> None:
    """An unknown path yields offset -1 rather than an error."""
    root = test_state.active_directory
    assert root is not None
    test_state.cached_results = [_row(root / "a.mttl", {}), _row(root / "b.mttl", {})]

    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/scan/results", params={"find_path": str(root / "ghost.mttl")}
        )

    assert response.json() == {"count": 2, "offset": -1}


_10_MB = FileAttrs(10485760, 1700000000.0, 1699000000.0)
_900_KB = FileAttrs(921600, 1700000001.0, 1699000001.0)


@pytest.mark.anyio
async def test_find_path_attribute_sort_uses_typed_order(test_state: ServerState) -> None:
    """find_path rides the typed attr sort: 900 KB ranks before 10 MB by bytes.

    A text sort would put "10 MB" first (10 < 900); the attribute-backed
    column sorts on size_bytes, so offsets mirror :func:`_sorted_results`.
    """
    root = test_state.active_directory
    assert root is not None
    test_state.config.columns = {"Size": ColumnConfiguration(match="size")}
    big = _row(root / "big_10mb.mttl", {"Size": "10 MB"}, _10_MB)
    small = _row(root / "small_900kb.mttl", {"Size": "900 KB"}, _900_KB)
    test_state.cached_results = [big, small]

    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ascending = await client.get(
            "/api/scan/results",
            params={"find_path": str(big.path), "sort_by": "Size", "sort_dir": "asc"},
        )
        descending = await client.get(
            "/api/scan/results",
            params={"find_path": str(big.path), "sort_by": "Size", "sort_dir": "desc"},
        )

    assert ascending.json() == {"count": 2, "offset": 1}
    assert descending.json() == {"count": 2, "offset": 0}
