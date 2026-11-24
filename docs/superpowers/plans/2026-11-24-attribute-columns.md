# File-Attribute Columns & Search Operators (#227) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Built-in `size` / `size_bytes` / `modified` / `created` / `path` columns plus `size:` / `modified:` / `created:` search operators, with zero stat cost on plain scans.

**Architecture:** One `FileAttrs` snapshot per row (collected only when an attribute operator or column demands it) flows through a 4-tuple candidate pipeline into column extraction; the operator grammar lives in the normative Python `search_parser` and is mirrored in TypeScript, pinned together by one shared JSON fixture. The server sorts attribute columns by raw bytes/epoch and serves raw `attrs` for client-side operator filtering.

**Tech Stack:** Python 3.11+ (stdlib only: `os.stat`, `datetime`, `dataclasses`), FastAPI/pydantic, React 18 + TypeScript + vitest, pytest + pytest-cov.

**Spec:** `docs/superpowers/specs/2026-11-24-attribute-columns-design.md` — read it first; this plan argues from it.

## Deviation from spec §4 (flagged for reviewer)

The spec's `path` keyword said "display path verbatim". The starter template
**already has a `Path` column** meaning *containing directory* (regex
`(.+[\\/])`, `default: "."`), and the implicit `File` column already shows the
full display path — a "verbatim path" keyword would duplicate `File` and
collide with `Path`. **Plan decision: `path` returns the parent directory of
the display path** (`"."` for root files — same as the template's current
default), and the template's `Path` column switches from regex to the keyword.
Still string-derived, no stat, not an operator key. Everything else in §4
stands.

## Global Constraints

- **Perf gate (spec, user constraint):** plain scans (no attribute column configured, no attribute operator in query) issue **zero** stat calls from the new code path; A/B SCAN_METRICS median rate within ±10% of baseline (22,244–22,245 files @ 16,518–18,385 files/s, this repo, ext=All, filter="", recursive).
- `match_filter(filename, query)` and `compile_query(query)` signatures stay byte-identical; operator-shaped tokens fall back to substring there (extension filter unchanged).
- Quoted phrases are never operators; `size:abc` (bad value shape) is substring; `-`/`+` prefixes compose; keys/units case-insensitive.
- Units binary (1 KB = 1024 B); duration units `s m h d w`; decimals allowed, floored to whole bytes/seconds; ranges inclusive at named granularity; `>`/`<` strict; `today` = local midnight of evaluation time; `now` read at match time, injectable via the `now` parameter.
- Missing attrs semantics: Python `match_file(..., attrs=None)` ⇒ attribute terms False; `match_filter` (no attrs param) ⇒ substring. TS `attrs == null` (null or undefined) ⇒ substring fallback (parity with 2-arg call).
- `utils/` stays framework-agnostic: `search_parser.py` defines a structural `FileAttrsProtocol` (it must not import from `core/`).
- Layering: stat collection only in `core/`; `server/`/`web/` only serialize/render; `core/` imports no UI.
- Every new test file is registered in `tests/AGENTS.md` in the same commit (it mirrors the tests tree 1:1); no new `src/` module paths, so root `AGENTS.md` tree needs no structural update — but its imports-extracts must stay valid.
- Commit style: conventional commits (`feat(core): …`, `test(web): …`), one commit per task.

## Review Focus

Spec-implied inputs no single task's happy path exercises; each is pinned by the named test:

1. **Filename containing a literal `size:>10mb`** must still substring-match — Task 3 fixture (`substring_cases`) + Task 2 unit.
2. **File deleted between walk and stat** — `collect_file_attrs` returns `None`, attribute terms evaluate False, row still includable — Task 6 test.
3. **Duration/`today` queries must not depend on the real clock** (midnight-crossing flakiness) — Task 3 fixture pins `now` per case; suite must fail if clock leaks in — Task 4 mirrors.
4. **Zero-byte and boundary-size files** — `0 B` formats as `"0 B"`, `size:<1kb` matches a 500-byte file, exact 1048576-byte file does NOT match `size:>1mb` — Task 5/2 tests.
5. **Sorting rows that lack attrs** (e.g. deleted mid-scan) sort to the end in *both* directions — Task 7 test.

---

### Task 1: `FileAttrs` snapshot + `collect_file_attrs`

**Files:**
- Modify: `src/profiles/core/processing/file_metadata.py`
- Test: `tests/core/processing/test_file_metadata.py` (existing — extend)

**Interfaces:**
- Produces: `FileAttrs` NamedTuple `(size_bytes: int, mtime: float, birthtime: float)`;
  `collect_file_attrs(path: Path) -> FileAttrs | None` (one `os.stat`; `None` on `OSError`).
  Everything downstream (Tasks 2, 5, 6, 7) consumes exactly these.

- [ ] **Step 1: Write failing tests** in `tests/core/processing/test_file_metadata.py`:

```python
class TestCollectFileAttrs:
    def test_returns_size_mtime_birthtime(self, tmp_path: Path) -> None:
        f = tmp_path / "a.log"
        f.write_text("x" * 1234)
        attrs = collect_file_attrs(f)
        assert attrs is not None
        assert attrs.size_bytes == 1234
        assert attrs.mtime == pytest.approx(f.stat().st_mtime)
        assert attrs.birthtime == pytest.approx(f.stat().st_ctime)  # Linux fallback path

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert collect_file_attrs(tmp_path / "gone.log") is None

    def test_birthtime_prefers_st_birthtime(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        f = tmp_path / "a.log"
        f.write_text("x")
        st = f.stat()
        monkeypatch.setattr(os, "stat_result", os.stat_result, raising=False)

        # Simulate an OS with st_birthtime: build a stat_result-like shim
        class _Shim:
            st_size = st.st_size
            st_mtime = st.st_mtime + 5.0
            st_ctime = st.st_ctime
            st_birthtime = st.st_mtime + 5.0

        monkeypatch.setattr("profiles.core.processing.file_metadata._stat_path", lambda p: _Shim())
        attrs = collect_file_attrs(f)
        assert attrs is not None and attrs.birthtime == pytest.approx(st.st_mtime + 5.0)
```

(Step 1b: the test above assumes a module-internal indirection `_stat_path(path) -> os.stat_result` — that indirection is part of the implementation, added in Step 3, so birthtime selection is testable without faking OSes.)

- [ ] **Step 2: Run** `uv run pytest tests/core/processing/test_file_metadata.py::TestCollectFileAttrs -v` → FAIL (function not defined).

- [ ] **Step 3: Implement** in `file_metadata.py`:

```python
class FileAttrs(NamedTuple):
    """Minimal stat snapshot for attribute columns and search operators."""

    size_bytes: int
    mtime: float
    birthtime: float


def _stat_path(path: Path) -> os.stat_result:
    """Indirection so tests can shim stat results (birthtime selection)."""
    return os.stat(path)


def collect_file_attrs(path: Path) -> FileAttrs | None:
    """One-stat snapshot; None when the file cannot be statted (deleted mid-scan)."""
    try:
        st = _stat_path(path)
    except OSError:
        return None
    birthtime = getattr(st, "st_birthtime", None)
    if birthtime is None:
        birthtime = st.st_ctime  # Linux: inode-change time (documented caveat)
    return FileAttrs(int(st.st_size), st.st_mtime, float(birthtime))
```

Import `NamedTuple` from `typing`. Follow the module's existing docstring style.

- [ ] **Step 4: Run** the tests → PASS.
- [ ] **Step 5: Commit** `feat(core): add FileAttrs stat snapshot for attribute columns (#227)`.

---

### Task 2: Operator grammar in `utils/search_parser.py` (normative)

**Files:**
- Modify: `src/profiles/utils/search_parser.py`
- Test: `tests/utils/test_search_parser.py` (existing — extend)

**Interfaces:**
- Consumes: `FileAttrsProtocol` defined here (structural: `size_bytes: int`, `mtime: float`, `birthtime: float` attributes).
- Produces (exact signatures):
  - `query_needs_attributes(query: str) -> bool` — True iff any unquoted, non-`OR` token parses as an attribute operator. `@lru_cache(maxsize=256)`.
  - `match_file(filename: str, query: str, attrs: FileAttrsProtocol | None, *, now: float | None = None) -> bool` — operator mode; `attrs=None` ⇒ attribute terms False (substring terms still apply); `now=None` ⇒ `time.time()` at call.
  - Internal (exported for tests only): `AttrTerm` frozen dataclass with `key: str` (canonical `size|modified|created`) and `comparators: tuple[_Comparator, ...]`; `_Comparator` frozen dataclass `(field: str, op: str, operand: float | str)` with `field ∈ {size_bytes, mtime, birthtime}` and `op ∈ {gt, lt, ge, le, eq, since_day_start, before_day_end, age_lt, age_gt, age_le, age_ge}`; `_parse_attr_token(term: str) -> AttrTerm | None`.

- [ ] **Step 1: Write failing unit tests** (new classes in `tests/utils/test_search_parser.py`). Each case: `(attrs, query, expected)` with `NOW = 1_700_000_000.0` and attrs built from it. Cover at least:
  - `size:>10mb`: 10485760 → False (strict); 10485761 → True; 900*1024 → False.
  - `size:<500kb` on 500*1024 → False (strict), 500*1024−1 → True.
  - `size:1kb..1mb` on 1024 → True, 1048576 → True, 1023 → False, 1048577 → False (inclusive both ends).
  - `size:1048576` on 1048576 → True (bare = equality), 1048577 → False.
  - `size:1.5mb` on 1572864 → True (decimal, exact); `size:1.5mb` on 1572863 → False (floored).
  - `SIZE:>10MB` / `10Mb` → same result (case-insensitive key and unit).
  - `size:abc` → operator parse fails; with attrs None it is substring: `match_file("report_size:abc.log", "size:abc", None)` → True; with attrs present and filename not containing it → False.
  - `modified:<7d`: mtime = NOW−3600 → True (recent); NOW−8*86400 → False.
  - `modified:>7d`: NOW−8*86400 → True; NOW−3600 → False.
  - `modified:1d..7d`: NOW−3*86400 → True; NOW−3600 → False; NOW−8*86400 → False.
  - `modified:>2026-11-01` with mtime = local-midnight(2026-11-01)+3600 → True; mtime = local-midnight(2026-10-31)+3600 → False (dates are local midnights; construct via `datetime(2026,11,1).timestamp()+3600`).
  - `modified:<2026-11-01` with mtime = midnight(2026-10-31)+3600 → True; midnight(2026-11-01)+3600 → False.
  - `modified:2026-11-01` with mtime = midnight+3600 → True; midnight+86401 (Nov 2) → False (bare date = whole local day).
  - `modified:today` with `now=NOW` fixed: mtime = midnight-of-NOW+3600 → True; midnight-of-NOW−3600 → False (anchor = local midnight of the injected now).
  - `created:>2026-11-01` evaluating `birthtime` (mtime far older must not matter).
  - Negation/prefix: `-size:>10mb` small file → True; `+size:>10mb` big file → True; `big OR size:<1kb` small file → True; `report -modified:<1d` old file → True (mixed substring + operator in one group).
  - attrs=None: `size:>10mb` term → False (operator mode, no data) while `report size:>10mb`-style substring terms in the same query still work.
  - `query_needs_attributes`: `""` → False; `"datalog"` → False; `"size:>10mb"` → True; `"datalog modified:<7d"` → True; `"size:abc"` → False (bad shape); `'"size:>10mb"'` → False (quoted); `"report -size:>1gb"` → True.
  - `match_filter` unchanged: `match_filter("size:>10mb.log", "size:>10mb")` → True (substring — regression guard).

- [ ] **Step 2: Run** `uv run pytest tests/utils/test_search_parser.py -v` → FAIL (names not defined).

- [ ] **Step 3: Implement** in `search_parser.py` (module stays stdlib-only: `re`, `time`, `dataclasses`, `datetime`, `functools`, `typing.Protocol`):
  - `_tokenize_spans(query)` returning `list[tuple[str, bool]]` (token, was-quoted) — regex `r'"([^"]*)"|(\S+)'`, quoted iff group 1 matched; drop empty tokens exactly like `tokenize` (so public `tokenize()` stays untouched).
  - `_ATTR_FIELD = {"size": "size_bytes", "size_bytes": "size_bytes", "modified": "mtime", "created": "birthtime"}`.
  - `_MagnitudeRe = ^(\d+(?:\.\d+)?)?(b|kb|mb|gb|tb)?$` (number required, else invalid), `_DurationRe = ^(\d+(?:\.\d+)?)([smhdw])$`, `_DateRe = ^(\d{4})-(\d{2})-(\d{2})$` validated by `datetime()` construction. Unit map `{"": 1, "b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}`; bytes/seconds `floor()`-ed.
  - `_parse_single(text)` → `list[_Comparator]` | None: optional leading `>`/`<`; magnitude → `gt/lt/eq` on `size_bytes`; date → `since_day_start`/`before_day_end`/both (bare) with the date string as operand; `today` → same ops with operand `"today"`; bare duration → invalid (`None`).
  - Range: value contains one `..`, both sides parse as **prefix-less singles**, AND the comparator lists; `a..b` sizes → `ge`/`le`; dates/today → `since_day_start(a)` + `before_day_end(b)`; durations → `age_ge(a)` (t ≤ now−a) + `age_le(b)` (t ≥ now−b). Mixed date/duration sides allowed, each resolved by its own kind. Split failure (empty side, 2+ `..`) → None.
  - `_parse_attr_token(term)` — strip one leading `-`/`+` is done by callers; here: split first `:`, key lookup (case-insensitive), value parse → `AttrTerm` or None.
  - `_local_midnight(operand, now)`: `"today"` → `datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()`; date → `datetime(y, m, d).timestamp()`.
  - `_comparator_matches(c, attrs, now)` eval switch: `gt/lt/ge/le/eq` direct on `getattr(attrs, c.field)`; `since_day_start` → `t >= _local_midnight(c.operand, now)`; `before_day_end` → `t < _local_midnight(...) + 86400`; `age_lt` → `t < now - c.operand`; `age_gt` → `t > now - c.operand`; `age_le` → `t >= now - c.operand`; `age_ge` → `t <= now - c.operand`.
  - Internal `_compile_attr_groups(query) -> list[list[_AttrGroupTerm]]` where `_AttrGroupTerm = (negated: bool, text: str, attr_term: AttrTerm | None)`; quoted tokens always `attr_term=None`.
  - `match_file`: split OR groups, `now = time.time() if now is None else now`; per token: attr_term present **and** attrs not None → all comparators must match; attr_term present and attrs None → False; else substring (case-insensitive, same as `_term_matches`); negation flips the outcome.
  - `query_needs_attributes`: any unquoted token whose bare form (strip `-`/`+`) parses → True.
  - Update the module docstring's operator table with the new grammar (concise; examples verbatim from spec §3).

- [ ] **Step 4: Run** `uv run pytest tests/utils/test_search_parser.py -v` → PASS, and `uv run pytest tests/utils/ tests/core/processing/` → no regressions.
- [ ] **Step 5: Commit** `feat(utils): attribute field operators in search grammar (#227)`.

---

### Task 3: Shared fixture + pytest consumer

**Files:**
- Create: `src/profiles/web/src/utils/searchOperators.fixture.json`
- Create: `tests/utils/test_search_parser_fixture.py`
- Modify: `tests/AGENTS.md` (register the new test file)

**Interfaces:**
- Consumes: `match_file`, `match_filter` (Task 2).
- Produces: the fixture both suites read. Schema:
```json
{ "operator_cases": [ { "name": "...", "query": "size:>10mb", "now": 1700000000,
    "filename": "dump.log",
    "attrs": { "size_bytes": 10485761,
               "mtime": {"from": "now", "offset_seconds": -3600},
               "birthtime": {"from": "today", "offset_seconds": -7200} },
    "expected": true } ],
  "substring_cases": [ { "name": "...", "query": "size:>10mb", "filename": "report_size:>10mb.log", "expected": true } ] }
```
`attrs` may be `null` (operator mode, terms False). Anchor `"from"` ∈ `"now"` | `"today"` (local midnight of the case's `now`) | `"date"` (plus `"date": "YYYY-MM-DD"`); epoch = anchor + `offset_seconds`. Every case pins `now`; no epoch literals derived from the real clock; day/date cases construct from the same local midnight the evaluator uses, so any TZ passes.

- [ ] **Step 1: Write the fixture** with ≥ 26 operator cases covering, at minimum: every query/attrs pair listed in Task 2 Step 1 (same values, now fixture-encoded); the spec's `10 MB`/`900 KB` pair — sizes 10485760 and 921600 each against `size:>1mb` (True/False) and against `size:>1gb` (False/False); two `attrs: null` cases (`size:>10mb` → False; `-size:>10mb` → True); quoted-phrase-as-operator (`"size:>10mb"` — operator mode, attrs null, filename containing the text → substring True; note in `name` this is a substring case in operator mode); `size:abc` fallback in operator mode; the `datalog modified:<7d` mixed group. Plus ≥ 6 substring cases: literal `size:>10mb` in filename, `size:abc`, `"size:>10mb"` quoted, plain keyword, `-tag`, empty query.
- [ ] **Step 2: Write failing test** `tests/utils/test_search_parser_fixture.py`:

```python
FIXTURE = (
    Path(__file__).resolve().parents[2] / "src/profiles/web/src/utils/searchOperators.fixture.json"
)


def _anchor_epoch(
    spec: dict, now: float
) -> float: ...  # now / today / date anchor + offset_seconds, per the schema above


@pytest.mark.parametrize(
    "case", json.loads(FIXTURE.read_text())["operator_cases"], ids=lambda c: c["name"]
)
def test_operator_case(case: dict) -> None:
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


@pytest.mark.parametrize(
    "case", json.loads(FIXTURE.read_text())["substring_cases"], ids=lambda c: c["name"]
)
def test_substring_case(case: dict) -> None:
    assert match_filter(case["filename"], case["query"]) is case["expected"]
```

- [ ] **Step 3: Run** `uv run pytest tests/utils/test_search_parser_fixture.py -v` → PASS (Task 2 already correct; failures here mean fixture/impl drift — fix before proceeding).
- [ ] **Step 4: Register** the test file in `tests/AGENTS.md` (same commit).
- [ ] **Step 5: Commit** `test(core): shared Py/TS operator fixture, pytest consumer (#227)`.

---

### Task 4: TypeScript port + vitest fixture consumer

**Files:**
- Modify: `src/profiles/web/src/utils/searchSyntax.ts`
- Create: `src/profiles/web/src/utils/searchSyntax.fixture.test.ts`

**Interfaces:**
- Consumes: fixture (Task 3); existing `matchFilter` export.
- Produces: `export interface FileAttrs { size_bytes: number; mtime: number; birthtime: number }`; `matchFilter(filename: string, query: string, attrs?: FileAttrs | null, now?: number): boolean` — `attrs == null` ⇒ substring fallback for operator-shaped terms (Python 2-arg parity); `now` defaults to `Date.now() / 1000`. Existing exports (`describeQuery`, 2-arg `matchFilter`) keep their exact behavior — operator-shaped terms remain plain includes there.

- [ ] **Step 1: Write failing tests** in `searchSyntax.fixture.test.ts`: import the JSON fixture, mirror the Python anchor helper (epoch = anchor + offset; `today` → `new Date(nowMs); setHours(0,0,0,0)`; `date` → `new Date(y, m-1, d).getTime()/1000`), drive every `operator_case` through `matchFilter(filename, query, attrs, now)` and every `substring_case` through 2-arg `matchFilter`. Also unit cases: 2-arg call with operator query on a non-matching filename → False, on a filename containing the literal → True.
- [ ] **Step 2: Run** (from `src/profiles/web/`) `npx vitest run src/utils/searchSyntax.fixture.test.ts` → FAIL (signature/behavior missing).
- [ ] **Step 3: Implement** in `searchSyntax.ts`, mirroring Task 2's internals exactly: quoted-aware tokenization (the existing `PHRASE_OR_WORD_RE` loop already knows quoted vs bare — keep `m[1] !== undefined`), `_ATTR_FIELD` map, magnitude/duration/date regexes (same shapes, binary units, `Math.floor`), range split on `..`, comparator objects with the same 11 ops, `localMidnight(operand, now)` (local TZ), and the negation/substring/nulled-attrs rules. Extend the header doc-comment's parity notes (null-vs-undefined rule, `now` injection). Keep `describeQuery` and `parseForMatching`'s substring cache untouched for non-operator groups.
- [ ] **Step 4: Run** the fixture suite **and the existing `searchSyntax.test.ts`** → PASS (parity proven: same JSON green on both ecosystems). Also `npx tsc --noEmit` clean.
- [ ] **Step 5: Commit** `feat(web): attribute operators in TS search parser, fixture parity (#227)`.

---

### Task 5: Attribute & `path` columns in `column_extractor.py`

**Files:**
- Modify: `src/profiles/core/processing/column_extractor.py`
- Test: `tests/core/processing/test_column_extractor.py` (extend)

**Interfaces:**
- Consumes: `FileAttrs` (Task 1).
- Produces: `ATTRIBUTE_KEYWORDS: set[str] = {"size", "size_bytes", "modified", "created"}`; `DEFAULT_ATTR_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"`; `ColumnRule.is_attribute` property; `ColumnRule.extract_attr(attrs: FileAttrs | None) -> str`; `format_human_size(n: int) -> str` (module-level, shared style for reuse); `ColumnExtractor.extract_all(filename: str, column_names: tuple[str, ...], attrs: FileAttrs | None = None) -> dict[str, str]` (positional callers unaffected); `ColumnExtractor.has_attribute_rules(column_names: tuple[str, ...]) -> bool` (True only if an attribute rule's name is in `column_names` — `path` does NOT count, it never stats); `path` keyword handled in `extract_all`: `str(Path(filename).parent)`.

- [ ] **Step 1: Write failing tests**: rules with `match: size` / `size_bytes` / `modified` / `created` given a `FileAttrs(1572864, 1795545600.0, 1790000000.0)`:
  - `size` → `"1.5 MB"`; `size_bytes` → `"1572864"`; `size` with 0 → `"0 B"`; with 512 → `"512 B"`; with 1048576 → `"1 MB"` (`.0` stripped); with 1023 → `"1023 B"`.
  - `modified` default format → `datetime.fromtimestamp(1795545600.0).strftime("%Y-%m-%d %H:%M:%S")`; `transform: "%d/%m/%Y"` → that strftime; `created` uses `birthtime`.
  - `attrs=None` → the rule's `default` (all four keywords).
  - `is_attribute` False for `match: ".*"` and for raw regex; `path` rule returns `str(Path("sub/dir/dump.log").parent)` for input `"sub/dir/dump.log"` and `"."` for `"dump.log"`; `transform` ignored for `path`.
  - `extract_all(("File", "Size", "Modified"), attrs)` fills all three; `has_attribute_rules(("Size",))` True, `(("File",))` False, `(("Path",))` False.
- [ ] **Step 2: Run** `uv run pytest tests/core/processing/test_column_extractor.py -v` → FAIL.
- [ ] **Step 3: Implement** per Interfaces: `is_attribute` short-circuits before `compiled()`; `extract_attr` branches on key (`format_human_size` / `str(int)` / `strftime` with `transform or DEFAULT_ATTR_DATETIME_FORMAT`, local time); `format_human_size`: `< 1024` → `f"{n} B"`, else divide by 1024 through `KB MB GB TB`, one decimal via `f"{v:.1f}"` then `.rstrip("0").rstrip(".")`, `f"{s} {unit}"`; `path` branch in `extract_all` before the generic regex path; keep the class's immutability/thread-safety comments intact (no new mutable state).
- [ ] **Step 4: Run** the suite → PASS; `uv run pytest tests/core/processing/` → no regressions.
- [ ] **Step 5: Commit** `feat(core): attribute and path column keywords with formatting (#227)`.

---

### Task 6: Scanner pipeline — 4-tuple candidates, stat placement, zero-stat gate

**Files:**
- Modify: `src/profiles/core/processing/scanner.py`
- Test: `tests/core/processing/test_scanner.py` (extend)

**Interfaces:**
- Consumes: `query_needs_attributes` (Task 2), `collect_file_attrs`/`FileAttrs` (Task 1), `extract_all`/`has_attribute_rules` (Task 5).
- Produces: candidate tuples become `(path: Path, display_path: str, full_suffix: str, attrs: FileAttrs | None)` throughout the private pipeline (`_scan_and_filter` yield, `files_to_process` buffer, `_process_files`, workers). Worker signature: `(file_path, display_path, full_suffix, attrs) -> T`. `ScannedFileDynamic` gains trailing `attrs: FileAttrs | None = None`. Public signatures (`scan_and_process`, `scan_and_process_dynamic`) unchanged.

- [ ] **Step 1: Write failing tests** in `test_scanner.py`:
  - Operator filter: tree with files sized 100 B and 10 MiB (write exact byte counts); `scan_and_process(dir, filter_text="size:>1mb")` → only the big file; `scan_and_process_dynamic(dir, filter_text="datalog modified:<7d", column_names=("File",), columns=…)` mixes substring + operator (fresh mtimes → all pass; one file's mtime untouched → still passes; a file with `os.utime` set to 30 days ago is filtered when paired with `modified:<7d`).
  - Attrs passthrough: dynamic scan with `columns={"Size": ColumnConfiguration(name="Size", match="size")}` → row `column_values["Size"] == "1 MB"` for the 1048576-byte file, and `row.attrs.size_bytes == 1048576`.
  - One-stat-per-row (both needs): with attribute column AND operator query → patch `profiles.core.processing.scanner.collect_file_attrs` with a counting wrapper: on a 3-file tree where the operator filter passes only 1 row, the wrapper is called exactly **3** times (once per extension-passing candidate — collection loop), never re-called by workers; result rows == 1.
  - Column-only stat site: no operator query, attribute column configured → `collect_file_attrs` called once per row (from workers); plain query + no attribute column → **zero calls**.
  - **Zero-stat gate**: `monkeypatch.setattr("profiles.core.processing.scanner.collect_file_attrs", counting_wrapper)`; run plain `scan_and_process` and `scan_and_process_dynamic` (config without attribute columns, filter "") → wrapper call count == 0. Docstring: `collect_file_attrs` is the only stat path added by #227, so 0 calls here proves the plain pipeline gained no stat cost.
  - Deleted-mid-scan resilience: patch `collect_file_attrs` to return None → operator query `size:>1mb` excludes rows (attr terms False) without raising; scan returns the rows matching the remaining substring terms.
  - `ScannedFileDynamic(("p", "v", Path("x")))` still constructs positionally (default attrs).
- [ ] **Step 2: Run** `uv run pytest tests/core/processing/test_scanner.py -v` → FAIL.
- [ ] **Step 3: Implement**:
  - `_scan_and_filter`: compute `collect_attrs = bool(filter_text) and query_needs_attributes(filter_text)` once per scan; yield 4-tuples, `collect_file_attrs(file_path) if collect_attrs else None`.
  - `_run_scan_pipeline` / `_process_files`: 4-tuple unpacking; `worker` typed `Callable[[Path, str, str, FileAttrs | None], T]`; `_process_file` gains the 4th param and ignores it; `scan_and_process` passes it through.
  - `_process_file_dynamic`: 4th param; `if attrs is None and extractor.has_attribute_rules(column_names): attrs = collect_file_attrs(file_path)`; call `extract_all(str(display_path), column_names, attrs)`; construct `ScannedFileDynamic(file_path, column_values, display_path, attrs)`.
  - Update the candidate-buffer type comments (extends the 494dc3c typing).
- [ ] **Step 4: Run** `uv run pytest tests/core/processing/ -v` → PASS (dedupe/parity/error suites included).
- [ ] **Step 5: Commit** `feat(core): stat-backed scan pipeline with zero-cost plain path (#227)`.

---

### Task 7: Server — typed sort + `attrs` payload

**Files:**
- Modify: `src/profiles/server/routes/scan.py`
- Test: `tests/server/routes/test_scan.py` (extend)

**Interfaces:**
- Consumes: `ATTRIBUTE_KEYWORDS` (Task 5), `ScannedFileDynamic.attrs` (Task 6).
- Produces: `/api/scan/results` items gain `"attrs": {"size_bytes": int, "mtime": float, "birthtime": float} | None`; `sort_by` on an attribute-backed column sorts by the raw field (rows with `attrs=None` last in both directions); other columns keep natural-text sort.

- [ ] **Step 1: Write failing tests** (build `ScannedFileDynamic` rows directly into `state.cached_results`, config columns `Size→match: size`, `Modified→match: modified`):
  - Rows with sizes mapping to `"10 MB"` (10485760) and `"900 KB"` (921600): `GET /api/scan/results?sort_by=Size&sort_dir=asc` → `900 KB` row first (text sort would put `10 MB` first — pin the typed key).
  - `sort_dir=desc` → reversed among attr rows.
  - Rows where one has `attrs=None` → last in asc AND in desc.
  - Non-attribute column (`File`) → unchanged natural sort.
  - Items payload: row with attrs → `attrs.size_bytes` matches; row with `attrs=None` → `"attrs": null`.
  - Column not attribute-backed but present in `column_values` → natural key (guard against keying everything by attrs).
- [ ] **Step 2: Run** `uv run pytest tests/server/routes/test_scan.py -v` → FAIL.
- [ ] **Step 3: Implement**: `_attr_field(column, config) -> str | None` via `config.columns[column].match.lower()` → `{"size": "size_bytes", "size_bytes": "size_bytes", "modified": "mtime", "created": "birthtime"}` (import `ATTRIBUTE_KEYWORDS` for the guard); in `get_scan_results`, if the requested column resolves to an attribute field: split cached rows into with/without attrs, sort the first by `getattr(r.attrs, field)` with `reverse=descending`, concatenate (`without` last), `sort_applied = bool(with_attrs)`; else existing path. Payload: serialize attrs to the dict-or-None shape above.
- [ ] **Step 4: Run** the suite → PASS; `uv run pytest tests/server/` → no regressions.
- [ ] **Step 5: Commit** `feat(server): typed sort and attrs payload for scan results (#227)`.

---

### Task 8: Starter template defaults

**Files:**
- Modify: `src/profiles/core/config/template.py`
- Test: `tests/core/config/test_template.py` (create if absent; else extend — check first with `ls tests/core/config/`)

**Interfaces:**
- Produces: template `columns:` = `File` (unchanged), `Path` (`match: path`, `default: "."`, width 200 — keyword replaces the regex), `FileName` (unchanged), `Size` (`match: size`, width 110), `Modified` (`match: modified`, width 150). `Type` and `Version` entries removed; the built-in keyword comment table gains `size`, `size_bytes`, `modified`, `created`, `path` rows (with the one-line examples style already used) and keeps `version` / `type` documented as available-but-not-default.

- [ ] **Step 1: Write failing test**: `propose_config_creation`/template output (whatever the existing template test surface is — if none exists, render the template string) contains `match: size` and `match: modified`, does **not** contain `match: "(PRO|ENG|DEV|TMP|DEBUG)"` nor the Version regex, and the keyword table mentions `modified` and `path`. Assert column keys exactly: `{File, Path, FileName, Size, Modified}`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Edit** the template per Interfaces (keep the `{{group:N}}` comment conventions; the Modified column comment notes `transform` accepts a strftime pattern).
- [ ] **Step 4: Run** → PASS; `uv run pytest tests/core/config/ tests/test_config.py` → no regressions.
- [ ] **Step 5: Commit** `feat(config): starter template ships Size and Modified columns (#227)`.

---

### Task 9: Web — attrs plumbing, operator tooltip, placeholder

**Files:**
- Modify: `src/profiles/web/src/api/types.ts`, `src/profiles/web/src/App.tsx` (line ~227), `src/profiles/web/src/components/SearchBar.tsx` (lines 7–23 `OPERATOR_HELP`, line 89 placeholder)
- Test: `src/profiles/web/src/components/SearchBar.test.tsx` (extend; exists per `ActionBar.test.tsx` convention — check; if absent, create following `SearchBar` render tests in `EditableCombobox.test.tsx` style)

**Interfaces:**
- Consumes: server `attrs` payload (Task 7), `matchFilter(filename, query, attrs?, now?)` (Task 4).
- Produces: `ScannedFileItem.attrs?: FileAttrsInfo | null` (new exported `interface FileAttrsInfo { size_bytes: number; mtime: number; birthtime: number }` in `api/types.ts`); `App.tsx:227` → `matchFilter(f.rel_path, prefilterQuery, f.attrs)`; `OPERATOR_HELP` gains the operator rows; placeholder updated.

Mechanism note: the spec §6b says "native `title` tooltip" — the SearchBar already wraps the filter in the app's styled `<Tooltip text={OPERATOR_HELP}>` (SearchBar.tsx:71), which is the established tooltip affordance. Extending `OPERATOR_HELP` **supersedes** the native-title wording; do not add a second `title` attribute.

- [ ] **Step 1: Write failing tests**: render `SearchBar`, assert the tooltip content includes `size:>10mb` and `modified:<7d` (query the `OPERATOR_HELP` region by its existing markup, e.g. `getByText("size:>10mb")`), and the filter combobox placeholder contains `size:>10mb`.
- [ ] **Step 2: Run** (from `src/profiles/web/`) `npx vitest run src/components/SearchBar.test.tsx` → FAIL.
- [ ] **Step 3: Implement**: extend `OPERATOR_HELP` with rows — `size:>10mb` — larger than, `size:1kb..1mb` — size range, `modified:<7d` — within the last 7 days, `modified:>2026-11-01` — after a date, `modified:today` — today only — matching the existing `code` + em-dash row pattern; placeholder → `"Filter files: keyword, size:>10mb, modified:<7d, a OR b, -tag..."`; add `FileAttrsInfo` to types and pass `f.attrs` at `App.tsx:227`.
- [ ] **Step 4: Run** the test → PASS; (from `src/profiles/web/`) `npx tsc --noEmit` clean and `npx vitest run` (whole web suite) → PASS.
- [ ] **Step 5: Commit** `feat(web): surface attribute operators in the filter bar (#227)`.

---

### Task 10: Command-palette filter presets

**Files:**
- Modify: `src/profiles/web/src/hooks/useAppCommands.ts`, `src/profiles/web/src/App.tsx` (deps wiring near the `useAppCommands` call, line ~885)
- Test: `src/profiles/web/src/hooks/useAppCommands.test.ts` (create if absent; else extend)

**Interfaces:**
- Consumes: `Command` shape (`{id, title, group, keywords, enabled, run}`), `focusField` helper, `#filter-combobox` id (Task 9 context).
- Produces: `AppCommandsDeps` gains `onAppendFilterTerm: (term: string) => void`; three commands in group `"file-list"`: `filter.largeFiles` → `"size:>100mb"`, `filter.modifiedToday` → `"modified:today"`, `filter.modifiedLastWeek` → `"modified:<7d"`. Append semantics live in App: trim; empty → term alone; term already present as a whole token → no-op; else single-space join (`datalog` + `modified:today` → `datalog modified:today`).

- [ ] **Step 1: Write failing tests**: with a fake deps object (pattern of the existing command tests), each command's `run()` calls `onAppendFilterTerm` with its exact term; titles match the spec table; `group === "file-list"`; `enabled: true`. Append-logic tests target the App handler (or extract it as a pure `appendFilterTerm(current: string, term: string): string` in `useAppCommands.ts` and unit-test that instead — preferred): `("", "modified:today")` → `"modified:today"`; `("datalog", "modified:today")` → `"datalog modified:today"`; `("datalog modified:today", "modified:today")` → unchanged; `("  datalog  ", "size:>100mb")` → `"datalog size:>100mb"`.
- [ ] **Step 2: Run** (from `src/profiles/web/`) `npx vitest run src/hooks/useAppCommands.test.ts` → FAIL.
- [ ] **Step 3: Implement**: pure `appendFilterTerm` export + three command entries (each `run: () => { deps.onAppendFilterTerm(<term>); focusField("#filter-combobox")(); }`); App adds `handleAppendFilterTerm` (setFilterText with the pure function) and passes the dep.
- [ ] **Step 4: Run** → PASS; full vitest suite + `npx tsc --noEmit` clean.
- [ ] **Step 5: Commit** `feat(web): palette filter presets append attribute operators (#227)`.

---

### Task 11: Documentation

**Files:**
- Modify: `docs/columns-guide.en.md`, `docs/columns-guide.fr.md`, `docs/column-library.md`, `docs/configuration-profile.en.md`, `docs/configuration-profile.fr.md`

**Interfaces:** Consumes the final grammar (Task 2) and column keywords (Task 5). Produces: docs consistent with implementation; no behavior.

- [ ] **Step 1: Update the built-in keyword tables** (columns guides EN/FR and column library): add `size` (human-readable, e.g. `12.4 MB`, binary 1024), `size_bytes` (raw), `modified` / `created` (`transform` = strftime, default `%Y-%m-%d %H:%M:%S`; **Linux caveat: `created` falls back to inode-change time**), `path` (containing directory, `"."` for root). State that attribute columns cost one `stat` per file, in parallel, only when configured.
- [ ] **Step 2: Add an operator-grammar section** (columns guides + configuration reference EN/FR): full grammar from spec §3 — keys, comparison/range/bare/date/duration/`today` forms, **duration reading** (`modified:<7d` = recent, `modified:>7d` = older — say it with both examples), binary units, decimals, quoted-phrases-stay-literal, `size:abc` fallback, AND/OR/`-` composition, and that date/duration queries read the clock at evaluation time. Keep EN/FR texts mirror-content.
- [ ] **Step 3: Add ready-to-paste column blocks** to the column library: Size, Modified (with strftime `transform` example), Path (`match: path`), plus one example query per operator.
- [ ] **Step 4: Verify**: every code literal in the docs matches implementation constants (spot-check against `ATTRIBUTE_KEYWORDS`, `DEFAULT_ATTR_DATETIME_FORMAT`, the placeholder text); if a docs link check exists in CI (`grep -rn "docs" .github/workflows/`), run it — skip if none.
- [ ] **Step 5: Commit** `docs: attribute columns and operator grammar EN/FR (#227)`.

---

### Task 12: Perf gate, dist rebuild, full verification

**Files:**
- Modify: `src/profiles/web/dist/` (build output, committed — precedent: PR #234)

**Interfaces:** Consumes everything. Produces: green local CI parity + the spec's A/B rate measurement.

- [ ] **Step 1: Baseline A/B (spec gate 2).** From a clean tree:
```bash
git stash -u   # or run on a worktree of main
for i in 1 2 3; do uv run python -c "
import logging; logging.basicConfig(level=logging.DEBUG)
from profiles.core.processing.scanner import scan_and_process_dynamic
from profiles.core.config.models import AppConfig
scan_and_process_dynamic(r'<REPO_DIR>', extension='All', filter_text='', recursive=True, log_metrics=True, config=None, column_names=('File',), columns={})
"; done 2>&1 | grep SCAN_METRICS
git stash pop
```
Repeat on the feature branch; median rates within ±10%, `errors=0`. Also one run with `filter_text='size:>10mb'` and one with the template-default columns to record the opt-in cost (report, don't gate).
- [ ] **Step 2: Quality gates:** `ruff format . && ruff check --fix .` → `uv run pylint src/profiles --fail-under=8.0` → `uv run pyright src/profiles` (pre-existing macOS pyobjc noise exempt, per PR #234 precedent) → `uv run pytest --cov=src/profiles --cov-fail-under=85`.
- [ ] **Step 3: Web gates:** from `src/profiles/web/`: `npm ci && npx tsc --noEmit && npx vitest run` → all green.
- [ ] **Step 4: Rebuild dist:** determine the build command (`grep -n "build" src/profiles/web/package.json` and `src/profiles/web/build.py` — expect `npm run build` from `src/profiles/web/`) and run it; verify `dist/` contains the new parser (`grep -rl "size_bytes" src/profiles/web/dist/assets/`).
- [ ] **Step 5: Tree sync check:** `git status` — new test files listed in `tests/AGENTS.md`; `src/profiles/core/__init__.py` surface unchanged; no stray TODOs.
- [ ] **Step 6: Commit** `build(web): rebuild dist with attribute columns (#227)` and push the branch.
