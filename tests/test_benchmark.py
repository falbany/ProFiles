"""Tests for the root ``benchmark.py`` scan-benchmark harness (dev tool, #227).

``benchmark.py`` lives at the repo root (next to ``probe_webview_camera.py``)
and is not part of the ``profiles`` package, so it is loaded by file path via
``importlib`` — path setup never matters.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_BENCHMARK_PATH = Path(__file__).resolve().parents[1] / "benchmark.py"

_spec = importlib.util.spec_from_file_location("benchmark", _BENCHMARK_PATH)
assert _spec is not None and _spec.loader is not None
benchmark = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("benchmark", benchmark)
_spec.loader.exec_module(benchmark)

#: Small files planted per subdirectory (4 subdirs × 10 files).
_SMALL_FILES_PER_DIR = 10
_SUBDIRS = 4
#: Files bigger than the ``size:>10mb`` operator threshold (11 MiB each).
_BIG_FILES = 2
_TOTAL_FILES = _SUBDIRS * _SMALL_FILES_PER_DIR + _BIG_FILES
_BENCHMARK_RUNS = 2


def _plant_tree(root: Path) -> None:
    """Plant a small deterministic tree: 40 tiny files in 4 dirs + 2 big files.

    The two sparse >10 MiB files give the ``operators`` scenario
    (``size:>10mb``) something to match; sparse writes keep the tree cheap.
    """
    for dir_idx in range(_SUBDIRS):
        subdir = root / f"dir{dir_idx}"
        subdir.mkdir()
        for file_idx in range(_SMALL_FILES_PER_DIR):
            (subdir / f"file_{dir_idx}_{file_idx}.txt").write_text("x" * 64, encoding="utf-8")
    for big_idx in range(_BIG_FILES):
        with (root / f"big_{big_idx}.bin").open("wb") as fh:
            fh.seek(11 * 1024 * 1024 - 1)
            fh.write(b"\0")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Temporary tree with a known file count for scan benchmarks."""
    _plant_tree(tmp_path)
    return tmp_path


def _run_benchmark(tree_path: Path) -> list[benchmark.ScenarioResult]:
    """Run all scenarios on ``tree_path`` with the fast test settings."""
    return benchmark.run_all(str(tree_path), runs=_BENCHMARK_RUNS)


def _save_and_load(results: list[benchmark.ScenarioResult], path: Path) -> dict[str, object]:
    """Save ``results`` as a baseline at ``path`` and load it back."""
    benchmark.save_baseline(path, results)
    return benchmark.load_baseline(path)


class TestRunAll:
    """Scenario coverage of ``run_all`` on a planted tree."""

    def test_run_all_reports_three_scenarios_with_stable_counts(self, tree: Path) -> None:
        """Verify run_all returns plain/operators/columns with correct counts.

        Given: A tree of 42 files (40 small + 2 bigger than 10 MiB)
        When: run_all executes every scenario with 2 measured runs
        Then: The three scenarios appear in order, plain/columns see all
              files, operators sees only the big files, and every median is
              strictly positive
        """
        results = _run_benchmark(tree)

        assert [result.name for result in results] == ["plain", "operators", "columns"]
        assert results[0].files == _TOTAL_FILES
        assert results[1].files == _BIG_FILES
        assert results[2].files == _TOTAL_FILES
        assert all(len(result.runs) == _BENCHMARK_RUNS for result in results)
        assert all(result.median_rate > 0 for result in results)
        assert all(result.median_duration_ms > 0 for result in results)


class TestBaselineRoundTrip:
    """Save → load → compare with untouched numbers."""

    def test_identical_run_compares_all_pass(self, tree: Path, tmp_path: Path) -> None:
        """Verify comparing a run against its own baseline passes everywhere.

        Given: Results from one run and the baseline saved from them
        When: The baseline is loaded and compared against the same results
        Then: Every verdict is PASS with a zero delta, the schema keys are
              intact, and a main()-style compare exit would be 0 (no
              REGRESSION verdict)
        """
        results = _run_benchmark(tree)
        baseline = _save_and_load(results, tmp_path / "baseline.json")

        assert set(baseline) == {"created_utc", "python", "directory", "runs", "scenarios"}

        comparisons = benchmark.compare(results, baseline)

        assert [comp.verdict for comp in comparisons] == ["PASS"] * 3
        assert all(comp.delta_pct == pytest.approx(0.0) for comp in comparisons)
        assert not any(comp.verdict == "REGRESSION" for comp in comparisons)


class TestRegressionDetection:
    """Rate drop beyond the ±10% gate."""

    def test_ten_times_slower_baseline_flags_regression(self, tree: Path, tmp_path: Path) -> None:
        """Verify a doctored (×10 rate) baseline flags REGRESSION only there.

        Given: A baseline whose ``plain`` median_rate is inflated tenfold
        When: The same results are compared against it
        Then: ``plain`` is REGRESSION (−90% delta, below the −10% gate) while
              the untouched scenarios stay PASS
        """
        results = _run_benchmark(tree)
        baseline = _save_and_load(results, tmp_path / "baseline.json")
        for entry in baseline["scenarios"]:
            if entry["name"] == "plain":
                entry["median_rate"] *= 10

        comparisons = benchmark.compare(results, baseline)
        by_name = {comp.scenario: comp for comp in comparisons}

        assert by_name["plain"].verdict == "REGRESSION"
        assert by_name["plain"].delta_pct == pytest.approx(-90.0)
        assert by_name["operators"].verdict == "PASS"
        assert by_name["columns"].verdict == "PASS"


class TestStaleTreeDetection:
    """File-count drift between baseline and current tree."""

    def test_file_count_drift_flags_stale_tree_but_keeps_delta(
        self, tree: Path, tmp_path: Path
    ) -> None:
        """Verify a >1% file-count drift yields STALE-TREE with the delta shown.

        Given: A baseline whose scenario file counts are drifted ~5% upward
               (at least +1 file) and whose ``plain`` rate is inflated by 50%
        When: The same results are compared against it
        Then: Every scenario is STALE-TREE (warning, not failure) instead of
              PASS/REGRESSION, and the rate delta is still computed (plain
              shows −33.3%, not a NaN)
        """
        results = _run_benchmark(tree)
        baseline = _save_and_load(results, tmp_path / "baseline.json")
        for entry in baseline["scenarios"]:
            entry["files"] += max(1, round(entry["files"] * 0.05))
            if entry["name"] == "plain":
                entry["median_rate"] *= 1.5

        comparisons = benchmark.compare(results, baseline)

        assert [comp.verdict for comp in comparisons] == ["STALE-TREE"] * 3
        by_name = {comp.scenario: comp for comp in comparisons}
        assert by_name["plain"].delta_pct == pytest.approx(-100.0 / 3.0)
        assert by_name["operators"].delta_pct == pytest.approx(0.0)
