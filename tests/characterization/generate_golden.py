"""Generate the golden scan baseline for the characterization suite.

Run ONCE on the unmodified tree (before any improvement task)::

    python tests/characterization/generate_golden.py

Writes ``golden/scan_baseline.json`` next to this file. Any later change
to the pipeline that diff these outputs must be intentional and listed
in the PR notes of the task that caused it.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
_SRC = _REPO_ROOT / "src"

for _path in (str(_HERE), str(_SRC)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import fixtures  # noqa: E402  (local characterization fixture module)

from profiles.core.processing.scanner import (  # noqa: E402
    scan_and_process,
    scan_and_process_dynamic,
)


def main() -> None:
    """Build the fixture tree and freeze both scan pipelines' output."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "scan_root"
        fixtures.build_tree(root)

        payload: dict[str, object] = {"cases": {}, "dynamic_case_keys": {}}
        cases: dict[str, dict[str, list[list[object]]]] = {}
        for recursive, ext, flt in fixtures.SCAN_CASES:
            static = scan_and_process(
                str(root), extension=ext, filter_text=flt, recursive=recursive
            )
            dynamic = scan_and_process_dynamic(
                str(root), extension=ext, filter_text=flt, recursive=recursive
            )
            cases[fixtures.case_key(recursive, ext, flt)] = {
                "static": [[r.filename, r.version] for r in static],
                "dynamic": [[r.rel_path, r.column_values] for r in dynamic],
            }

        dyn: dict[str, list[list[object]]] = {}
        for ext, column_names, columns in fixtures.DYNAMIC_CASES:
            results = scan_and_process_dynamic(
                str(root),
                extension=ext,
                column_names=column_names,
                columns=columns,
                recursive=True,
            )
            dyn[fixtures.dynamic_case_key(ext, column_names, columns)] = [
                [r.rel_path, r.column_values] for r in results
            ]

        payload["cases"] = cases
        payload["dynamic_case_keys"] = dyn

    out = _HERE / "golden" / "scan_baseline.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    total_rows = sum(len(v["static"]) for v in cases.values())
    print(f"wrote {out} ({len(cases)} cases, {total_rows} static rows)")


if __name__ == "__main__":
    main()
