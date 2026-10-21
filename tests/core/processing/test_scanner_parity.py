"""Tests for the single processing path — Task 9.

``_process_files`` replaces ``_process_files_sequential`` and
``_process_files_parallel``: inline below ``max_workers <= 1``, thread
pool otherwise, results always in submission (input) order.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import profiles.core.processing.scanner as scanner
from profiles.core.processing.scanner import _process_files


class TestErrorParity:
    """Worker failures produce identical results and counts on both modes."""

    @pytest.fixture
    def files(self, tmp_path: Path) -> list[tuple[Path, str, str]]:
        out = []
        for i in range(150):
            p = tmp_path / f"f{i:03d}.mttl"
            p.write_text("x", encoding="utf-8")
            out.append((p, f"f{i:03d}.mttl", ".mttl"))
        return out

    @staticmethod
    def flaky_worker(file_path: Path, _display: str, _suffix: str) -> str | None:
        # Every tenth file (f000, f010, ...) fails
        if int(file_path.stem[1:]) % 10 == 0:
            raise RuntimeError("boom")
        return file_path.name

    def test_sequential_and_parallel_same_results(self, files: list[tuple[Path, str, str]]) -> None:
        import logging

        logging.getLogger("profiles.core.processing.scanner").setLevel(logging.CRITICAL)
        seq_results, seq_errors = _process_files(files, self.flaky_worker, 1)
        par_results, par_errors = _process_files(files, self.flaky_worker, 8)

        assert seq_results == par_results
        assert seq_errors == par_errors == 15
        assert len(seq_results) == 135
        # All non-failing present
        assert set(seq_results) == {f"f{i:03d}.mttl" for i in range(150) if i % 10 != 0}

    def test_order_preserved(self, files: list[tuple[Path, str, str]]) -> None:
        results, _errors = _process_files(files, lambda p, d, s: d, 8)
        assert [r for r in results] == [d for _p, d, _s in files]


class TestThreshold:
    """Pool is built only at/above _PARALLEL_THRESHOLD (>=)."""

    def _files(self, tmp_path: Path, count: int) -> list[tuple[Path, str, str]]:
        out = []
        for i in range(count):
            p = tmp_path / f"x{i:03d}.mttl"
            p.write_text("x", encoding="utf-8")
            out.append((p, f"x{i:03d}.mttl", ".mttl"))
        return out

    def test_below_threshold_no_pool(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = []
        real_executor = scanner.concurrent.futures.ThreadPoolExecutor

        class Spy:
            def __call__(self, *args: object, **kwargs: object) -> object:
                calls.append((args, kwargs))
                return real_executor(*args, **kwargs)

        monkeypatch.setattr(scanner.concurrent.futures, "ThreadPoolExecutor", Spy())
        files = self._files(tmp_path, 99)
        _process_files(files, lambda p, d, _s: d, 1)
        assert calls == []

    def test_at_threshold_pool_built(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = []
        real_executor = scanner.concurrent.futures.ThreadPoolExecutor

        class Spy:
            def __call__(self, *args: object, **kwargs: object) -> object:
                calls.append((args, kwargs))
                return real_executor(*args, **kwargs)

        monkeypatch.setattr(scanner.concurrent.futures, "ThreadPoolExecutor", Spy())
        files = self._files(tmp_path, 100)
        _process_files(files, lambda p, d, _s: d, 8)
        assert len(calls) == 1
