# Design — File-attribute columns & search operators (#227)

**Status:** draft for review · **Issue:** falbany/ProFiles#227 · **Date:** 2026-11-24

## Intent & why

Columns and search only see the file *name*. Two things bench users filter on
constantly — how big, how recent — are invisible in the list and not askable in
a query. This feature adds four built-in column keywords backed by `stat()`
(`size`, `size_bytes`, `modified`, `created`) and field operators in the
existing search grammar (`size:>10mb`, `modified:<7d`, `modified:today`, …),
so "the dumps over 100 MB from this week" becomes a typeable query.

The binding constraint from the user: **plain scans must not get slower.**
Baseline on the maintainer's machine (2026-11-24, this repo, ext=All,
filter="", recursive): 22,244–22,245 files, 1209–1347 ms, rate
16,518–18,385 files/s (SCAN_METRICS). All stat work is opt-in per scan;
inert scans issue zero stat calls.

## Goals

- Four built-in column keywords resolved from file stat, declared like any
  column: `match: size | size_bytes | modified | created` — plus a fifth,
  string-derived keyword `path` (display path, no stat).
- Field operators in the existing Google-style grammar, composable with
  `AND` (space) / `OR` / `-` / `+`:
  - `size:>10mb`, `size:<500kb`, `size:1kb..1mb`, `size:1048576`
  - `modified:>2026-11-01`, `modified:<7d`, `modified:1d..7d`,
    `modified:today`, `modified:2026-11-01` (that whole day)
  - `created:` mirrors `modified:` on birthtime
- Typed sort: attribute columns sort by bytes / epoch, not text
  (`10 MB` before `900 KB`).
- Python parser stays normative; TypeScript port follows; a single shared
  JSON fixture of (query, row, expected) cases is consumed by **both**
  pytest and vitest so the grammars cannot drift.
- Docs: columns guide EN/FR, column library, configuration reference.
- Search-bar affordance (USER DIRECTED): the filter input advertises the
  new operators via an updated `placeholder` and a native `title`
  tooltip cheatsheet (§6b), plus command-palette entries (§6c).

## Non-goals

- Content search (grep inside files).
- Arbitrary stat-derived columns beyond the four keywords.
- `yesterday` / `thisweek` keywords; time-of-day in operator dates
  (dates are day-granularity, local time).
- UI chrome for adding attribute columns (they are ordinary configured
  columns; the existing table/columns UI renders them as-is).
- Operator-awareness in `describeQuery` chips (attribute terms display as
  plain includes for now).
- Refactoring `scan_directory` to carry `DirEntry` stat out of the walk
  (documented future optimization if Windows operator-scans disappoint).

## Anti-goals (failure even if it works)

- Any stat call on a scan with no attribute column configured and no
  attribute operator in the query.
- A token that looks like an operator but isn't (`size:abc`, filename
  containing `size:`) silently losing substring semantics.
- Python/TS grammar drift (the shared fixture going green on one side only).
- A file deleted mid-scan crashing the pipeline (stat failure degrades to
  "no attributes", never an error).

## User-decided semantics

- **Duration reading (GNU find style):** `modified:<7d` = age under 7 days =
  *recent*; `modified:>7d` = older than a week. Durations compare the file's
  **age**; absolute dates compare **timestamps** (`modified:>2026-11-01` =
  modified after that day begins). Note: the issue body's parenthetical says
  the opposite — a comment on the issue will correct it when this lands.
- All operators listed in the issue are in scope.

## Design

### 1. Attributes snapshot — `core/processing/file_metadata.py`

New `FileAttrs` NamedTuple: `size_bytes: int`, `mtime: float`,
`birthtime: float` (epoch seconds). New pure helper:

```python
def collect_file_attrs(path: Path) -> FileAttrs | None
```

One `os.stat`; returns `None` on `OSError` (deleted / unreadable mid-scan).
`birthtime` = `st_birthtime` where the OS provides it (macOS, Windows via
ctime-as-creation), else `st_ctime` (Linux: inode-change time — documented
caveat). No new module: lives beside `FileMetadata`, so the AGENTS.md tree
stays unchanged.

### 2. Stat placement — one stat per row, only when needed

Needs fall into three cases, decided once per scan:

| Case | Who stats | Where it runs |
|---|---|---|
| query has attribute operators | collection loop, per candidate, before `match_filter` | sequential, opt-in |
| attribute column configured, plain query | worker | parallel pool, ~free |
| both | collection stats once, value passes through | workers reuse |

**When nothing attribute-backed is requested** — no attribute column
configured **and** no attribute operator in the query — nothing stats: the
pipeline is byte-identical to today's, which the zero-stat acceptance gate
(§ Performance gate) pins with a unit test. The partial cases: operators
but no attribute column ⇒ stat happens (it must, to evaluate the filter)
and rows carry `attrs` for the client, but no column displays them;
attribute column with a plain query ⇒ worker-pool stat only, always opt-in
via config. `path` (§4) is string-derived and never stats.

Detection helpers on `utils/search_parser.py`: `query_needs_attributes(query)
-> bool` (true iff any token parses as an attribute operator). Column side:
`ColumnRule.is_attribute` (`match.lower()` in `ATTRIBUTE_KEYWORDS`).

- `_scan_and_filter` gains an attrs-aware branch: when
  `query_needs_attributes(filter_text)`, each candidate passing the
  extension filter is statted (`collect_file_attrs`) and yielded with the
  result. Stat failure ⇒ `attrs=None`; attribute terms then evaluate False,
  substring terms still apply, file still includable.
- Candidate tuples become 4-tuples `(path, display_path, full_suffix,
  attrs_or_None)`; `_process_file` ignores the 4th slot,
  `_process_file_dynamic` passes it to the extractor and only re-stats when
  `attrs is None` and an attribute column is configured. This extends the
  worker-input tuple typing introduced in 494dc3c — contained to
  `scanner.py`.
- Plain path (`ScannedFile`) is untouched; only `ScannedFileDynamic` gains a
  trailing `attrs: FileAttrs | None = None` field (default keeps positional
  construction valid).

### 3. Operator grammar — `utils/search_parser.py` (normative)

A token is an attribute operator iff, after stripping a leading `-`/`+`:

1. it splits on the **first** `:` into `key:value`;
2. `key.lower()` ∈ `{size, size_bytes, modified, created}` (`size_bytes`
   aliases `size` — same bytes, different display; deliberately no `path`
   key — plain terms already substring-match the display path, so a path
   operator would be redundant);
3. `value` matches the value grammar below.

Anything else — including quoted phrases (quotes are literal, never
operators) — falls back to plain substring. Value grammar:

- **Magnitude:** `number unit?`, unit ∈ `b|kb|mb|gb|tb`, case-insensitive,
  binary (1 KB = 1024 B). Default unit B. `number` accepts decimals
  (`1.5mb`); the result is floored to whole bytes.
- **Date:** `YYYY-MM-DD`, local time. A date denotes its local midnight
  instant; `today` denotes today's local midnight.
- **Duration:** `number unit` with unit ∈ `s|m|h|d|w`. `number` accepts
  decimals (`<0.5d` = 12 h); converted to float seconds.
- **Single:** optional leading `>` or `<` then magnitude / date / duration.
  Bare forms: size ⇒ equality; date (incl. `today`) ⇒ the whole local day
  `[midnight, midnight+1d)`; bare duration ⇒ invalid (substring fallback).
- **Range:** `single..single` (no spaces), each side independent
  (date/duration mixed allowed). Range = lower bound AND upper bound,
  inclusive at the named granularity: bytes inclusive; duration ages
  inclusive (`1d..7d` = 1d ≤ age ≤ 7d ⇔ now−7d ≤ mtime ≤ now−1d); date
  bounds include their whole day.
- `>` / `<` are strict comparisons at the resolved instant
  (`>2026-11-01` = after midnight, so Nov 1 files match; `<7d` = age < 7d).

Evaluation: `now` is read **at match time**, never frozen into the compiled
query (durations stay honest across a long-lived server process; the
`lru_cache`d `compile_query` remains safe). Public API additions:
`match_file(filename, query, attrs, *, now=None) -> bool` and
`query_needs_attributes(query) -> bool`. `now=None` means the real clock;
tests and the shared fixture pass an explicit epoch so duration / `today`
cases are deterministic with **no test-side clock faking** on either
ecosystem. `match_filter(filename, query)` and `compile_query(query)` keep
their exact signatures; when attrs are **not supplied**, attribute-shaped
terms behave as substrings (this is what keeps the extension filter and
every existing caller byte-identical).

**Quoted-phrase implementation note** (builder-check settled): `tokenize()`
strips quotes, so the operator detector cannot tell `size:>10mb` from
`"size:>10mb"` at token level. The attrs-aware compile path therefore
re-tokenizes internally with quote-span tracking (an internal helper
yielding `(token, was_quoted)` alongside the existing public `tokenize()`,
which stays byte-identical); quoted tokens are barred from operator
detection. The TS port mirrors the same span tracking. Public signatures on
both sides are untouched.

### 4. Column extraction — `core/processing/column_extractor.py`

`ATTRIBUTE_KEYWORDS = {"size", "size_bytes", "modified", "created"}`.
`ColumnRule.is_attribute` short-circuits before `compiled()` (no regex).
`ColumnExtractor.extract_all(filename, column_names, attrs=None)` resolves
attribute rules from `attrs`; `attrs is None` ⇒ the column's `default`.

Formats:

- `size`: human binary — `<1 KB` in B (`0 B`, `512 B`), else one decimal
  with trailing `.0` stripped (`12.4 MB`, `1 GB`). `size_bytes`: raw int.
- `modified` / `created`: `strftime` on the epoch. The column's existing
  `transform` field is reused as the strftime pattern when set (MY CALL —
  flagged below); default `%Y-%m-%d %H:%M:%S`, local time.

`path` is a new **string-derived** builtin keyword, no stat involved: it
returns the extractor's input string verbatim — the display path relative
to the scan root (e.g. `subdir/dump_V2.mttl`). `transform` is ignored for
it (raw-regex `match` already covers path splitting, since extraction runs
on the display path). It joins `filename` / `extension` in the built-in
keyword tables and short-circuits before `compiled()` exactly like the
attribute keywords.

### 4b. Starter template defaults — `core/config/template.py`

`STARTER_CONFIG_TEMPLATE`'s default `columns:` become `File`, `Size`
(`match: size`), `Modified` (`match: modified`) — replacing the `Version`
(`match: version`) and `Type` (`match: type`) entries, which leave the
template (the keywords themselves remain available). The template's inline
comments document the new keywords, as user-facing documentation (USER
DIRECTED). Consequence stated plainly: configs generated from the new
template stat every row by default — in the parallel worker pool, so
wall-clock impact is small — and deleting the two attribute columns
restores a zero-stat scan. Existing user configs are untouched; nothing
changes for them.

### 5. Typed sort — `server/routes/scan.py`

`get_scan_results` already sorts on `sort_by` when the column appears in
`column_values`; attribute columns qualify automatically once configured.
The route resolves the column through `state.config.columns[name].match`:
attribute-backed ⇒ key = `row.attrs.size_bytes` (both size columns) or
`.mtime` / `.birthtime`; rows with `attrs=None` sort to the end regardless
of direction (has-attr flag, then key). Non-attribute columns keep the
natural-text key. `/api/scan/results` items gain `"attrs"` (raw values for
the client), present when the scan carried attributes.

### 6. TypeScript port — `web/src/utils/searchSyntax.ts`

Mirror of §3: `matchFilter(filename, query, attrs?, now?)` plus the
`FileAttrs` interface (`{ size_bytes: number; mtime: number; birthtime:
number }`).
Missing/undefined attrs ⇒ substring fallback (parity rule from §3).
`App.tsx:227` passes `f.attrs`. Web `ScanResultItem` type gains optional
`attrs`. Column rendering and header-sort calls work unchanged against the
server; the only UI changes are §6b and §6c.

### 6c. Command-palette entries (USER DIRECTED)

`web/src/hooks/useAppCommands.ts` — three new commands in the existing
`file-list` group. **They append to the current filter as an implicit AND,
never replace it** (USER DIRECTED): filter `datalog` + "Show only files
modified today" ⇒ `datalog modified:today`. Empty filter ⇒ the operator
text alone; surrounding whitespace is normalized (single space join).
Append is idempotent — if the exact operator term is already present in
the query, the command is a no-op rather than stacking a duplicate. After
appending, the command focuses the search bar — the composed query doubles
as live syntax documentation, with the §6b tooltip one hover away:

| id | title | appends |
|---|---|---|
| `filter.largeFiles` | Show only files larger than 100 MB | `size:>100mb` |
| `filter.modifiedToday` | Show only files modified today | `modified:today` |
| `filter.modifiedLastWeek` | Show only files from the last 7 days | `modified:<7d` |

Titles are phrased as outcomes, not syntax (the palette search matches on
them); the operator text lives in the filter box. If the scan query
carries no attribute operators when the command fires, the server rescan
picks them up automatically (operators trigger stat capture per §2), so
no extra plumbing is needed. Vitest: one test per command asserting the
installed filter text — including the append cases: onto `datalog`
(⇒ `datalog modified:today`), onto an empty filter, and a repeat
invocation (no duplicate term).

### 6b. Search-bar tooltip (USER DIRECTED)

`web/src/components/SearchBar.tsx`:

- The filter input's `placeholder` gains operator examples, e.g.
  `Filter files: keyword, size:>10mb, modified:<7d, a OR b, -tag, "exact"...`
  (keep it short — the placeholder is a hint, not documentation).
- The input gains a native `title` tooltip with a compact cheatsheet:
  existing grammar (`a b` AND, `a OR b`, `-tag`, `"exact phrase"`) plus the
  new operators with one example each — `size:>10mb`, `size:1kb..1mb`,
  `modified:<7d` (recent), `modified:>2026-11-01`, `modified:today`. Static
  text only: no new dependency, no live parsing, `FilterSyntaxHelper`
  unchanged (operator-aware chips stay a non-goal).
- Vitest: assert the filter input carries the `title` and the updated
  `placeholder`.

### 7. Shared fixture (anti-drift)

One JSON file, imported by vitest and read by pytest (path:
`src/profiles/web/src/utils/searchOperators.fixture.json`; pytest resolves
it relative to the test file). Entries: `{query, row-spec, expected}` where
`row-spec` holds `size_bytes`, and mtime/birthtime as **offsets in seconds
from an explicit per-case `now`** (and `date`-anchored offsets for absolute
date cases), so no timezone-fragile epoch literals are hardcoded. The
per-case `now` flows through the `now` parameter of `match_file` /
`matchFilter` (§3) — both suites run the identical arithmetic, no
test-side clock faking, no midnight-crossing flakiness. `expected` is a
literal boolean in the fixture — that is the drift protection. Cases must
cover at minimum: substring fallback for `size:abc` and filenames
containing `size:`; every operator/range/bare form from §3 including
fractional magnitudes/durations (`size:1.5mb`, `modified:<0.5d`); quoted
phrase staying literal; `-`/`+` prefixes; stat-less rows (attrs null); the
`10 MB` vs `900 KB` sort-adjacent pair as matching/non-matching pairs.

### 8. Docs

- `docs/columns-guide.en.md` and `docs/columns-guide.fr.md`: new keyword
  rows (`size`, `size_bytes`, `modified`, `created`, `path`) in the
  built-in keywords table + an operator-grammar section (USER DIRECTED to
  name these files explicitly).
- `docs/column-library.md`: keyword table extended with the same rows;
  ready-to-paste Size / Modified / Path column blocks.
- `src/profiles/core/config/template.py`: new default columns + inline
  comments documenting the keywords (user-facing doc surface, §4b).
- Configuration reference: `match` keyword table + operator grammar + the
  Linux `created` caveat. Search-syntax prose wherever the grammar is
  documented today (builder locates the exact anchors).

## Constraints

- Layering: stat collection stays in `core` + `utils`; server/web only
  serialize and render. `utils/search_parser.py` stays framework-agnostic
  (no Path/os imports beyond `time`).
- Public non-breaking: `match_filter`, `compile_query`, `scan_directory`,
  `ScannedFile`, config schema unchanged (additive only). Semver risk low.
- Pylint > 8.0, ruff, pyright, pytest > 85% coverage, web vitest/tsc — all
  as per CI.

## Performance gate (acceptance)

1. **Zero-stat test:** unit test monkeypatching `os.stat` /
   `Path.stat` with a counting wrapper — plain `scan_and_process` and
   `scan_and_process_dynamic` (config with **no** attribute columns, no
   operators — explicit config, since the new default template ships
   attribute columns) must issue zero new stat calls end-to-end.
2. **A/B rate gate:** on the baseline directory above, ext=All, filter="",
   recursive, 3 runs before (stash) vs after; median SCAN_METRICS rate
   within ±10% of the pre-change median, errors=0.
3. Operator- and column-active scans (including a template-default config,
   which stats in workers) are measured and reported (expect a
   sequential-stat cost only in the operator case; column-only stats run in
   the parallel pool) — documented, not gated.

## Acceptance (functional)

- Shared fixture green on pytest **and** vitest from the same file.
- Server sort: `Size` column sorts `900 KB` before `10 MB` ascending
  (pinned by a Python test through the results endpoint).
- `path` column resolves to the display path verbatim (unit test); the
  starter template generates with `File` / `Size` / `Modified` (template
  test).
- Search bar: filter input exposes the operator cheatsheet via `title` and
  the updated `placeholder` (vitest, §6b).
- Command palette: `filter.largeFiles` / `filter.modifiedToday` /
  `filter.modifiedLastWeek` install their documented filter text (vitest,
  §6c).
- `modified:today` / duration cutoffs verified through the explicit `now`
  parameter (no real-clock dependence anywhere in the test suites).
- Existing suites untouched and green.

## Decisions made (my calls — rejectable, flagged for review)

1. Binary units (1024), Explorer-style display, one decimal.
2. Duration units `s m h d w`.
3. `created` → `st_ctime` fallback on Linux, documented.
4. Ranges inclusive at named granularity; bare `>`/`<` strict; bare
   duration invalid (substring fallback); bare size = equality.
5. Keys and units case-insensitive; `today` = local midnight.
6. `transform` reused as strftime pattern for date columns (alternative
   rejected: new `format` field = schema churn for no gain).
7. Missing attrs ⇒ substring fallback everywhere (simplest parity rule).
8. 4-tuple candidate pipeline (extends 494dc3c's typing) rather than an
   attrs side-map.
9. No new telemetry fields; the existing SCAN_METRICS line is the
   benchmark instrument.
10. Quoted-phrase exemption implemented via internal quote-span tracking
    in the attrs-aware compile path (public `tokenize()` untouched,
    mirrored in TS) — builder-check call.
11. Clock injection via an optional keyword-only `now` parameter on the
    new `match_file` / TS `matchFilter`; `now=None` = real clock; fixture
    per-case `now` flows through it — builder-check call.
12. Grammar numbers accept decimals, floored to whole bytes / seconds —
    builder-check call.
13. (USER DIRECTED) Starter template default columns swap: `Size` +
    `Modified` replace `Version` + `Type`; template comments document the
    keywords; consequence (template configs stat by default) accepted.
14. (USER DIRECTED) `path` builtin keyword — string-derived, no stat,
    `transform` ignored, deliberately not an operator key.
15. (USER DIRECTED) Search-bar tooltip as native `title` cheatsheet +
    updated `placeholder` (§6b); richer popover UI and operator-aware
    `describeQuery` chips remain out of scope.
16. (USER DIRECTED) Palette entries as outcome-phrased filter presets
    (§6c) — `size:>100mb` / `modified:today` / `modified:<7d` — that
    **append as implicit AND** to the current filter (idempotent), chosen
    over a docs-opening command because the composed query is
    self-demonstrating and the presets are usable in their own right.

## Left to the builder

- Exact fixture case list and harness plumbing (both suites).
- Test placement per `tests/AGENTS.md` (mirroring `src/profiles/` 1:1).
- Locating current search-syntax doc anchors for §8.
- Confirming no hidden `Path.stat` in the plain pipeline when writing the
  zero-stat test (baseline the counter, assert delta zero).
