"""Reusable scan-benchmark harness for ProFiles (A/B basis for perf work).

This dev tool (repo root — pytest never collects it, like its dev-script
sibling ``scripts/dev/probe_webview_camera.py``) formalizes the manual A/B
procedure used for #227's performance gate (see PR #235): it measures
``scan_and_process_dynamic`` throughput on a fixed tree, saves the numbers as
a machine-local JSON baseline, and compares future runs against it.

Scenarios (all run with ``extension="All"``, ``recursive=True``,
``column_names=("File",)``):

1. ``plain``     — no filter, no columns: the zero-cost invariant. The
   ±10% regression gate applies to THIS scenario.
2. ``operators`` — ``size:>10mb`` filter: the collection-loop stat path.
   Rate semantics: matched-files per scan-second — the numerator is the
   files passing the filter (e.g. 4 on the current repo tree), not the
   whole tree — so use its ``duration_ms`` for throughput comparisons;
   the ±10% gate applies to ``plain`` only.
3. ``columns``   — template-default column mirrors: the worker-pool stat
   path.

Usage::

    uv run python benchmark.py                    # report on the repo tree
    uv run python benchmark.py --runs 5           # more measured runs
    uv run python benchmark.py --save             # write benchmark-baseline.json
    uv run python benchmark.py --compare          # vs baseline; exit 1 on regression
    uv run python benchmark.py --directory /path  # measure another tree
    uv run python benchmark.py --save --compare   # compare pre-run file, then save

Baselines are machine-local (git-ignored): only compare numbers recorded on
the same machine, Python version and tree. Exit codes: 0 = pass/no regression,
1 = at least one REGRESSION verdict, 2 = baseline file missing or unreadable.
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import statistics
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from profiles.core.config.models import ColumnConfiguration
from profiles.core.processing.scanner import ScannedFileDynamic, scan_and_process_dynamic

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent
DEFAULT_BASELINE: Final[Path] = REPO_ROOT / "benchmark-baseline.json"
DEFAULT_RUNS: Final[int] = 3
REGRESSION_THRESHOLD: Final[float] = 0.10  # ±10% median rate

#: Verdict values used in :class:`Comparison`.
VERDICT_PASS: Final[str] = "PASS"
VERDICT_REGRESSION: Final[str] = "REGRESSION"
VERDICT_STALE_TREE: Final[str] = "STALE-TREE"
VERDICT_NEW: Final[str] = "NEW"

#: Tree drift (relative difference in file count) above which a comparison is
#: flagged STALE-TREE — a warning, not a failure.
STALE_TREE_THRESHOLD: Final[float] = 0.01  # >1% difference


@dataclass(frozen=True)
class RunResult:
    """One measured scan run.

    Attributes:
        duration_ms: Wall-clock duration of the scan in milliseconds.
        rate: Throughput in files per second (files / seconds).
        files: Number of files returned by the scan.
    """

    duration_ms: float
    rate: float
    files: int


@dataclass(frozen=True)
class ScenarioResult:
    """Aggregated result of one benchmark scenario.

    Attributes:
        name: Scenario name (``plain``, ``operators`` or ``columns``).
        runs: The individual measured runs (warm-up excluded).
        median_rate: Median throughput in files per second.
        median_duration_ms: Median scan duration in milliseconds.
        files: File count shared by every measured run.
    """

    name: str
    runs: tuple[RunResult, ...]
    median_rate: float
    median_duration_ms: float
    files: int


@dataclass(frozen=True)
class Comparison:
    """Outcome of comparing a current scenario against a baseline.

    Attributes:
        scenario: Scenario name.
        base_rate: Baseline median rate (files/s); 0.0 for NEW scenarios.
        new_rate: Current median rate (files/s).
        delta_pct: Percentage change of the rate (negative = slower).
        verdict: ``PASS``, ``REGRESSION``, ``STALE-TREE`` or ``NEW``.
    """

    scenario: str
    base_rate: float
    new_rate: float
    delta_pct: float
    verdict: str


def _template_default_columns() -> dict[str, ColumnConfiguration]:
    """Return the template-default column mirrors for the ``columns`` scenario.

    These mirror the ``[COLUMN_*]`` sections shipped by
    ``STARTER_CONFIG_TEMPLATE`` so the worker-pool stat path is exercised the
    way a default user configuration would.

    Returns:
        Column configurations keyed by column name.
    """
    return {
        "File": ColumnConfiguration(name="File", match=".*", transform="{group:0}", priority=100),
        "Path": ColumnConfiguration(name="Path", match="path", default="."),
        "FileName": ColumnConfiguration(name="FileName", match=r"([^/\\]+)$"),
        "Size": ColumnConfiguration(name="Size", match="size"),
        "Modified": ColumnConfiguration(name="Modified", match="modified"),
    }


#: (name, filter_text, columns) triples measured by :func:`run_all`.
SCENARIOS: Final[tuple[tuple[str, str, dict[str, ColumnConfiguration] | None], ...]] = (
    ("plain", "", None),
    ("operators", "size:>10mb", None),
    ("columns", "", _template_default_columns()),
)


def run_scenario(
    name: str,
    directory: str,
    *,
    filter_text: str,
    columns: dict[str, ColumnConfiguration] | None,
    runs: int,
) -> ScenarioResult:
    """Run one benchmark scenario and aggregate the measured runs.

    One warm-up run is executed and discarded (page cache, lazy imports),
    then ``runs`` measured runs are timed with ``time.perf_counter()``.
    ``log_metrics=True`` is passed so the familiar ``SCAN_METRICS`` DEBUG
    lines are emitted for every run.

    Args:
        name: Scenario name for the report.
        directory: Filesystem path to scan.
        filter_text: Keyword filter expression (supports operators).
        columns: Column configurations, or ``None`` for none.
        runs: Number of measured runs (warm-up excluded).

    Returns:
        Aggregated :class:`ScenarioResult` with medians over the measured runs.

    Raises:
        ValueError: If the measured runs disagree on the file count, i.e. the
            tree changed mid-benchmark (results would not be comparable).
    """

    def _scan() -> list[ScannedFileDynamic]:
        """Run one scan with the fixed benchmark parameters for this scenario."""
        return scan_and_process_dynamic(
            directory,
            extension="All",
            filter_text=filter_text,
            recursive=True,
            log_metrics=True,
            config=None,
            column_names=("File",),
            columns=columns,
        )

    # Warm-up run, discarded: stabilizes caches and lazy imports.
    _scan()

    measured: list[RunResult] = []
    for _ in range(runs):
        start = time.perf_counter()
        results = _scan()
        duration_s = time.perf_counter() - start
        files = len(results)
        measured.append(
            RunResult(
                duration_ms=duration_s * 1000.0,
                rate=(files / duration_s) if duration_s > 0 else 0.0,
                files=files,
            )
        )

    file_counts = {run.files for run in measured}
    if len(file_counts) > 1:
        raise ValueError(
            f"Scenario {name!r}: unstable tree mid-benchmark — measured runs "
            f"reported different file counts: {sorted(file_counts)}"
        )

    return ScenarioResult(
        name=name,
        runs=tuple(measured),
        median_rate=statistics.median(run.rate for run in measured),
        median_duration_ms=statistics.median(run.duration_ms for run in measured),
        files=measured[0].files,
    )


def run_all(directory: str, runs: int = DEFAULT_RUNS) -> list[ScenarioResult]:
    """Run every scenario in :data:`SCENARIOS`.

    Args:
        directory: Filesystem path to scan.
        runs: Number of measured runs per scenario (warm-up excluded).

    Returns:
        One :class:`ScenarioResult` per scenario, in :data:`SCENARIOS` order.
    """
    return [
        run_scenario(name, directory, filter_text=filter_text, columns=columns, runs=runs)
        for name, filter_text, columns in SCENARIOS
    ]


def format_report(results: Sequence[ScenarioResult], directory: str = "") -> str:
    """Format benchmark results as an aligned report table.

    Args:
        results: Results to render, in display order.
        directory: Scanned tree, shown in the context line (may be empty).

    Returns:
        Multi-line report: context line (directory, Python version, UTC
        timestamp) followed by an aligned table of medians per scenario.
    """
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        "Scan benchmark",
        f"Directory : {directory or '(not recorded)'}",
        f"Python    : {platform.python_version()}",
        f"Timestamp : {timestamp} (UTC)",
        "",
        f"{'scenario':<12} {'runs':>6} {'files':>8} {'median_ms':>12} {'median_files/s':>16}",
    ]
    for result in results:
        lines.append(
            f"{result.name:<12} {len(result.runs):>6} {result.files:>8} "
            f"{result.median_duration_ms:>12.1f} {result.median_rate:>16.1f}"
        )
    return "\n".join(lines)


def format_comparisons(
    comparisons: Sequence[Comparison], threshold: float = REGRESSION_THRESHOLD
) -> str:
    """Format baseline comparisons as an aligned table.

    Args:
        comparisons: Comparisons to render.
        threshold: Regression threshold shown in the footer (fraction).

    Returns:
        Multi-line table with scenario, baseline and current rates, delta
        percentage and verdict per scenario.
    """
    lines = [
        "Comparison vs baseline",
        f"{'scenario':<12} {'base_files/s':>14} {'new_files/s':>14} {'delta_%':>9}  verdict",
    ]
    for comp in comparisons:
        lines.append(
            f"{comp.scenario:<12} {comp.base_rate:>14.1f} {comp.new_rate:>14.1f} "
            f"{comp.delta_pct:>+9.1f}  {comp.verdict}"
        )
    lines.append(f"threshold: ±{threshold:.0%} median rate (gate applies to the 'plain' scenario)")
    return "\n".join(lines)


def save_baseline(
    path: Path | str,
    results: Sequence[ScenarioResult],
    directory: str = "",
) -> None:
    """Write benchmark results to a baseline JSON file.

    Args:
        path: Destination file path.
        results: Results to serialize.
        directory: Scanned tree recorded for context (may be empty).

    Note:
        Baselines are machine-local; ``benchmark-baseline.json`` is
        git-ignored and must never be committed.
    """
    payload: dict[str, object] = {
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "directory": directory,
        "runs": len(results[0].runs) if results else 0,
        "scenarios": [
            {
                "name": result.name,
                "median_rate": result.median_rate,
                "median_duration_ms": result.median_duration_ms,
                "files": result.files,
                "runs": [
                    {
                        "duration_ms": run.duration_ms,
                        "rate": run.rate,
                        "files": run.files,
                    }
                    for run in result.runs
                ],
            }
            for result in results
        ],
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_baseline(path: Path | str) -> dict[str, object]:
    """Load a baseline JSON file.

    Args:
        path: Baseline file path.

    Returns:
        Parsed baseline payload (see the module docstring for the schema).

    Raises:
        FileNotFoundError: If the file does not exist (``main`` turns this
            into a clean message and exit code 2).
        json.JSONDecodeError: If the file is not valid JSON.
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare(
    results: Sequence[ScenarioResult],
    baseline: dict[str, object],
    threshold: float = REGRESSION_THRESHOLD,
) -> list[Comparison]:
    """Compare current results against a loaded baseline.

    For each scenario present in both: the rate delta is
    ``(new - base) / base * 100``; the verdict is ``PASS`` when
    ``delta_pct >= -threshold * 100`` (improvements pass), ``REGRESSION``
    below it, and ``STALE-TREE`` (warning, delta still shown) when the
    baseline file count differs from the current one by more than 1% — the
    trees are not comparable. Scenarios missing from the baseline get
    verdict ``NEW`` with ``base_rate = 0.0`` and ``delta_pct = 0.0``.
    Baseline-only scenarios are ignored.

    Args:
        results: Current benchmark results.
        baseline: Payload as returned by :func:`load_baseline`.
        threshold: Relative median-rate gate (fraction, e.g. 0.10).

    Returns:
        One :class:`Comparison` per current scenario, in result order.
    """
    baseline_scenarios = {
        entry["name"]: entry for entry in baseline.get("scenarios", []) if "name" in entry
    }

    comparisons: list[Comparison] = []
    for result in results:
        entry = baseline_scenarios.get(result.name)
        if entry is None:
            comparisons.append(
                Comparison(
                    scenario=result.name,
                    base_rate=0.0,
                    new_rate=result.median_rate,
                    delta_pct=0.0,
                    verdict=VERDICT_NEW,
                )
            )
            continue

        base_rate = float(entry.get("median_rate", 0.0))
        base_files = int(entry.get("files", result.files))
        delta_pct = ((result.median_rate - base_rate) / base_rate * 100.0) if base_rate > 0 else 0.0

        stale_tree = (
            base_files > 0 and abs(result.files - base_files) / base_files > STALE_TREE_THRESHOLD
        )
        if stale_tree:
            verdict = VERDICT_STALE_TREE
        elif delta_pct >= -threshold * 100.0:
            verdict = VERDICT_PASS
        else:
            verdict = VERDICT_REGRESSION

        comparisons.append(
            Comparison(
                scenario=result.name,
                base_rate=base_rate,
                new_rate=result.median_rate,
                delta_pct=delta_pct,
                verdict=verdict,
            )
        )
    return comparisons


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point: run the benchmark, optionally save and compare.

    The benchmark always runs and its report is printed. ``--save`` adds a
    baseline write (path printed). ``--compare`` loads the baseline file,
    prints a comparison table and returns 1 if any verdict is REGRESSION.
    Combining ``--save --compare`` compares against the pre-run file, then
    saves the fresh numbers.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code: 0 = ok, 1 = regression detected, 2 = baseline
        file missing or unreadable.
    """
    parser = argparse.ArgumentParser(
        description="ProFiles scan-benchmark harness (A/B basis for perf work).",
        epilog="Baselines are machine-local (benchmark-baseline.json is git-ignored).",
    )
    parser.add_argument(
        "--directory", default=str(REPO_ROOT), help="Tree to scan (default: repo root)."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"Measured runs per scenario, minimum 1 (default: {DEFAULT_RUNS}).",
    )
    parser.add_argument("--save", action="store_true", help="Save the results as the baseline.")
    parser.add_argument(
        "--compare", action="store_true", help="Compare against the saved baseline."
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Baseline file path (default: benchmark-baseline.json).",
    )
    args = parser.parse_args(argv)

    runs = max(1, args.runs)
    directory = str(Path(args.directory))

    # The scanner logger inherits the root WARNING level, so the SCAN_METRICS
    # DEBUG lines requested via ``log_metrics=True`` would be dropped before
    # events.py ever emits them; raise the root level so they actually print.
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

    print(f"Scanning {directory} ({runs} measured run(s) per scenario)...")
    results = run_all(directory, runs)
    print(format_report(results, directory=directory))

    exit_code = 0
    if args.compare:
        try:
            baseline = load_baseline(args.baseline)
        except FileNotFoundError:
            print(f"Baseline file not found: {args.baseline}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as exc:
            print(f"Baseline file is not valid JSON: {args.baseline} ({exc})", file=sys.stderr)
            return 2
        comparisons = compare(results, baseline)
        print(format_comparisons(comparisons))
        if any(comp.verdict == VERDICT_REGRESSION for comp in comparisons):
            exit_code = 1

    if args.save:
        save_baseline(args.baseline, results, directory=directory)
        print(f"Baseline saved: {args.baseline}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
