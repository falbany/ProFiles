/**
 * Search query parser supporting Google-style operators — TypeScript port of
 * `src/profiles/utils/search_parser.py` (Python parity is normative).
 *
 * Public API:
 *   describeQuery(query) -> { error: string | null, groups: { includes, excludes }[] }
 *   matchFilter(filename, query) -> boolean
 *   matchFilter(filename, query, attrs, now?) -> boolean   (operator mode)
 *   FileAttrs { size_bytes, mtime, birthtime }
 *
 * Grammar:
 *   `a b`        — AND: every term in a group must appear
 *   `a OR b`     — alternative groups (case-insensitive keyword)
 *   `-a`         — NOT: term must not appear
 *   `+a`         — explicit include (same as a plain term)
 *   `"a b"`      — exact phrase, matched verbatim (quotes stripped)
 *
 * Attribute operators (`#227`; mirrors Python `match_file`; shared
 * conformance fixture: `searchOperators.fixture.json`, replayed by both
 * `tests/utils/test_search_parser_fixture.py` and
 * `searchSyntax.fixture.test.ts`):
 *   size:>10mb           — size strictly above 10 MiB (binary units)
 *   size:<500kb          — size strictly below 500 KiB
 *   size:1048576         — size equal to the operand (bare magnitude)
 *   size:1kb..1mb        — size range, inclusive on both ends
 *   modified:<7d         — modified within the last 7 days (s m h d w)
 *   modified:>7d         — modified more than 7 days ago
 *   modified:1d..7d      — age between 1 and 7 days, inclusive
 *   modified:>2026-11-01 — modified on/after that day's local midnight
 *   modified:<2026-11-01 — modified strictly before that local midnight
 *   modified:2026-11-01  — modified during that local day
 *   modified:today       — same, anchored to the local midnight of `now`
 *   created:…            — same grammar as `modified`, on the birth time
 *   -size:>10mb          — negation flips the operator outcome
 *   "size:>10mb"         — quoted: literal substring, never an operator
 *
 * Parity notes (must stay in sync with the Python module):
 *   - `matchFilter(filename, query)` (2-arg call; `attrs == null` covers
 *     both `null` and `undefined`) keeps the exact legacy behavior:
 *     operator-shaped terms remain plain includes/excludes. This mirrors
 *     Python `match_filter` — deliberately NOT `match_file(..., None)`.
 *   - `matchFilter(filename, query, attrs, now?)` with non-null `attrs` is
 *     Python `match_file` parity: `key:value` tokens with a known key and
 *     parseable value are evaluated against `attrs`; quoted tokens and
 *     malformed operators (size:abc, kind mismatches like modified:>10mb,
 *     bare durations like modified:7d, 2+ `..` ranges) fall back to literal
 *     substring matching. `now` defaults to `Date.now() / 1000` and anchors
 *     "today" and duration (age) comparisons.
 *   - Age semantics follow GNU find: `modified:<7d` means age < 7d, i.e.
 *     mtime > now - 7d (recent); `modified:>7d` means mtime < now - 7d
 *     (older); range bounds are inclusive (age_le / age_ge).
 *   - `>date` is on/after that day's local midnight; `<date` is strictly
 *     before that midnight (the whole day excluded); a bare date is the
 *     whole day [midnight, midnight + 86400) using a FIXED +86400 seconds
 *     offset — next-day midnight is NOT used, even across DST shifts.
 *   - Sizes use binary units (b/kb/mb/gb/tb × 1024^n), decimals are floored
 *     via Math.floor, keys and units are case-insensitive, and `size_bytes`
 *     aliases `size`.
 *   - Calendar dates are validated by real Date construction (month 1-12,
 *     day valid for the month) before being accepted as operands.
 *
 * Semantics notes (must stay in sync with the Python module):
 *   - Only double quotes act as phrase delimiters; any other quote
 *     character travels inside its own token as an ordinary character.
 *   - An unmatched quote stays glued to its bare token (best-effort parse)
 *     and tokenization continues normally afterwards.
 *   - Empty or whitespace-only tokens (e.g. from empty quoted phrases) are
 *     dropped, so a quote-only filter matches everything.
 *   - An empty group (trailing/leading/consecutive OR) trivially matches,
 *     so such a query matches everything too.
 *   - Matching is case-insensitive substring matching; compiled queries are
 *     memoized per distinct query string with a 256-entry LRU cache.
 *
 * Example:
 *   matchFilter("report_a.sample", "alpha")        // -> true
 *   matchFilter("report_b.sample", "alpha -beta")  // -> true
 *   matchFilter("report_a.sample", "alpha -beta")  // -> false
 *   matchFilter("dump.log", "size:>1mb", { size_bytes: 10485760, mtime: 0, birthtime: 0 })  // -> true
 */

export interface QueryGroup {
  includes: string[];
  excludes: string[];
}

export interface QueryDescription {
  error: string | null;
  groups: QueryGroup[];
}

// ── tokenize ──────────────────────────────────────────────────────────────

/**
 * Double-quote phrase *or* bare word — mirrors the Python regex
 * `"([^"]*)"|(\S+)` so token boundaries stay identical.
 */
const PHRASE_OR_WORD_RE = /"([^"]*)"|(\S+)/g;

/** Paired double quotes used to detect stray (unmatched) quotes. */
const PAIRED_QUOTES_RE = /"([^"]*)"/g;

/** Error reported by describeQuery when a quote could not be paired. */
const UNMATCHED_QUOTE_ERROR = "Unmatched quote";

interface TokenizedQuery {
  /** Ordered terms: plain token, `-exclude`, `+include`, or `OR` marker. */
  terms: string[];
  error: string | null;
}

/**
 * Tokenize a query into ordered terms.
 *
 * Quoted phrases become single terms with the quotes stripped; empty or
 * whitespace-only phrases are dropped, as are blank bare words. An
 * unmatched quote is kept verbatim inside its token and reported as a
 * best-effort parse via `error` (a UI affordance; matching itself is
 * unaffected — the Python layer has no error concept).
 */
function tokenizeQuery(query: string): TokenizedQuery {
  // 1) Collect tokens with exact Python-regex parity.
  const terms: string[] = [];
  let m: RegExpExecArray | null;
  PHRASE_OR_WORD_RE.lastIndex = 0;
  while ((m = PHRASE_OR_WORD_RE.exec(query)) !== null) {
    const token = m[1] !== undefined ? m[1] : m[2];
    if (token && token.trim()) terms.push(token);
  }

  // 2) Unpaired-quote detection: strip every successfully paired span; a
  //    quote remaining in the residue was never part of a phrase.
  let residue = "";
  let last = 0;
  PAIRED_QUOTES_RE.lastIndex = 0;
  let pair: RegExpExecArray | null;
  while ((pair = PAIRED_QUOTES_RE.exec(query)) !== null) {
    residue += query.slice(last, pair.index);
    last = pair.index + pair[0].length;
  }
  residue += query.slice(last);

  return {
    terms,
    error: residue.includes('"') ? UNMATCHED_QUOTE_ERROR : null,
  };
}

// ── describeQuery ─────────────────────────────────────────────────────────

/**
 * Describe a query for live feedback: split into OR groups and separate
 * `-` excludes from plain/`+` includes within each group.
 */
export function describeQuery(query: string): QueryDescription {
  const trimmed = query.trim();
  if (!trimmed) return { error: null, groups: [] };

  const { terms, error } = tokenizeQuery(trimmed);
  if (terms.length === 0) return { error, groups: [] };

  const groups: QueryGroup[] = [];
  let current: QueryGroup = { includes: [], excludes: [] };

  for (const term of terms) {
    if (term.toUpperCase() === "OR") {
      groups.push(current);
      current = { includes: [], excludes: [] };
      continue;
    }
    if (term === "-" || term === "+") {
      continue; // operator prefix without a term: dropped
    }
    if (term.startsWith("-") && term.length > 1) {
      current.excludes.push(term.slice(1));
    } else if (term.startsWith("+") && term.length > 1) {
      current.includes.push(term.slice(1));
    } else {
      current.includes.push(term);
    }
  }
  groups.push(current);

  return { error, groups };
}

// ── matchFilter ───────────────────────────────────────────────────────────

interface CachedQuery {
  /** OR groups with terms lower-cased (Python: `term.lower() in text`). */
  groups: QueryGroup[];
}

const CACHE_LIMIT = 256;
const descriptionCache = new Map<string, CachedQuery>();

function cacheTerm(term: string): string {
  return term.toLowerCase();
}

/**
 * Compile a query into lower-cased OR groups, memoized per distinct query
 * string (256 entries, least-recently-used eviction — mirrors the Python
 * `@lru_cache(maxsize=256)` decorator).
 */
function parseForMatching(query: string): CachedQuery {
  const cached = descriptionCache.get(query);
  if (cached) {
    // Refresh recency for LRU semantics.
    descriptionCache.delete(query);
    descriptionCache.set(query, cached);
    return cached;
  }

  const { groups } = describeQuery(query);
  const parsed: CachedQuery = {
    groups: groups.map((groupItem) => ({
      includes: groupItem.includes.map(cacheTerm),
      excludes: groupItem.excludes.map(cacheTerm),
    })),
  };

  if (descriptionCache.size >= CACHE_LIMIT) {
    // Evict the least-recently-used entry.
    const oldest = descriptionCache.keys().next().value;
    if (oldest !== undefined) descriptionCache.delete(oldest);
  }
  descriptionCache.set(query, parsed);
  return parsed;
}

/**
 * One OR group matches when every include term is a substring of the
 * (lower-cased) target and no exclude term is.
 */
function groupMatches(
  target: string,
  groupItem: { includes: string[]; excludes: string[] },
): boolean {
  return (
    groupItem.includes.every((term) => target.includes(term)) &&
    !groupItem.excludes.some((term) => target.includes(term))
  );
}

/**
 * Legacy substring matcher — the exact pre-operator behavior, mirroring
 * Python `match_filter`. Alternatives (OR groups) match on any; AND terms
 * inside a group all apply. An empty or whitespace-only query matches
 * everything.
 */
function matchFilterSubstring(filename: string, query: string): boolean {
  const { groups } = parseForMatching(query);
  if (groups.length === 0) return true;
  const target = filename.toLowerCase();
  return groups.some((groupItem) => groupMatches(target, groupItem));
}

/**
 * Structural snapshot required by attribute operators (mirrors the Python
 * `FileAttrs` NamedTuple from
 * `profiles.core.processing.file_metadata`).
 */
export interface FileAttrs {
  size_bytes: number;
  mtime: number;
  birthtime: number;
}

/**
 * Case-insensitive match of a filename against a filter query.
 *
 * 2-arg / null-attrs call (`attrs == null` covers both `null` and
 * `undefined`): legacy substring behavior, byte-identical to the
 * pre-operator engine — operator-shaped terms remain plain
 * includes/excludes (Python `match_filter` parity).
 *
 * 3-arg call with non-null `attrs`: operator mode (Python `match_file`
 * parity) — `key:value` tokens with a known key and a parseable value are
 * evaluated against the attribute snapshot, everything else stays a literal
 * substring test. `now` (optional) anchors "today" and age comparisons and
 * defaults to `Date.now() / 1000`.
 */
export function matchFilter(
  filename: string,
  query: string,
  attrs?: FileAttrs | null,
  now?: number,
): boolean {
  if (attrs == null) {
    // 2-arg parity (Python match_filter): operator-shaped terms stay plain
    // includes/excludes — see the header parity notes.
    return matchFilterSubstring(filename, query);
  }
  // Operator mode (Python match_file).
  return matchFileAttrs(filename, query, attrs, now ?? Date.now() / 1000);
}

// ── Attribute operators (field comparisons) ───────────────────────────────
//
// Grammar: `key:value` where *key* is one of `size`/`size_bytes`,
// `modified`, `created` (case-insensitive) and *value* is a magnitude
// (`10`, `10mb`, `1.5kb` — binary units, floored), a duration (`7d`,
// `12h` — units s m h d w, floored), a calendar date (`2026-11-01`) or
// `today`, optionally prefixed by `>`/`<` or expressed as an inclusive
// `a..b` range. Anything that does not parse as an operator is matched as
// a literal substring instead. Mirrors the normative Python section of
// `src/profiles/utils/search_parser.py` (`_tokenize_spans` … `match_file`).

const SIZE_FIELD = "size_bytes";

const ATTR_FIELD: Record<string, string> = {
  size: SIZE_FIELD,
  size_bytes: SIZE_FIELD,
  modified: "mtime",
  created: "birthtime",
};

const SIZE_UNITS: Record<string, number> = {
  "": 1,
  b: 1,
  kb: 1024,
  mb: 1024 ** 2,
  gb: 1024 ** 3,
  tb: 1024 ** 4,
};

const DURATION_UNITS: Record<string, number> = {
  s: 1,
  m: 60,
  h: 3600,
  d: 86400,
  w: 604800,
};

const DAY_SECONDS = 86400;

// Magnitude: optional decimal number + optional binary unit; the number is
// required for a valid operand (checked via group 1).
const MAGNITUDE_RE = /^(\d+(?:\.\d+)?)?(b|kb|mb|gb|tb)?$/i;
// Duration: number with a mandatory unit letter.
const DURATION_RE = /^(\d+(?:\.\d+)?)([smhdw])$/i;
// Calendar date in ISO order, validated by real Date construction.
const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** One field comparison extracted from an attribute operator token. */
interface AttrComparator {
  field: string;
  op: string;
  operand: number | string;
}

/** Parsed attribute operator: canonical key plus its comparators. */
interface AttrTerm {
  key: string;
  comparators: AttrComparator[];
}

/** One token of an AND-group in operator mode. */
interface AttrGroupTerm {
  negated: boolean;
  text: string;
  attrTerm: AttrTerm | null;
}

/**
 * Split a query into `(token, was_quoted)` pairs — mirrors Python
 * `_tokenize_spans` exactly (same regex, same dropping of empty tokens).
 * Quoted tokens are never attribute operators.
 */
function tokenizeSpans(query: string): Array<[string, boolean]> {
  const spans: Array<[string, boolean]> = [];
  let m: RegExpExecArray | null;
  PHRASE_OR_WORD_RE.lastIndex = 0;
  while ((m = PHRASE_OR_WORD_RE.exec(query)) !== null) {
    let token: string;
    let quoted: boolean;
    if (m[1] !== undefined) {
      token = m[1];
      quoted = true;
    } else {
      token = m[2];
      quoted = false;
    }
    if (token && token.trim()) spans.push([token, quoted]);
  }
  return spans;
}

/**
 * Parse a magnitude operand (`10`, `10mb`, `1.5kb`) into bytes. Returns
 * whole bytes (binary units, floored), or null when *text* is not a
 * magnitude (a number is required).
 */
function resolveSize(text: string): number | null {
  const m = MAGNITUDE_RE.exec(text);
  if (m === null || m[1] === undefined) return null;
  const unit = m[2] !== undefined ? m[2].toLowerCase() : "";
  // Operands are non-negative, so flooring equals Python int() truncation.
  return Math.floor(parseFloat(m[1]) * SIZE_UNITS[unit]);
}

/**
 * Parse a duration operand (`7d`, `12h`, `0.5w`) into whole seconds
 * (floored), or null when *text* is not a duration (unit letter required).
 */
function resolveDuration(text: string): number | null {
  const m = DURATION_RE.exec(text);
  if (m === null) return null;
  return Math.floor(parseFloat(m[1]) * DURATION_UNITS[m[2].toLowerCase()]);
}

/** Calendar validity: month 1-12 and a day valid for that month/year. */
function isCalendarDate(year: number, month: number, day: number): boolean {
  if (month < 1 || month > 12 || day < 1) return false;
  // Day 0 of the *next* month is the last day of `month`.
  return day <= new Date(year, month, 0).getDate();
}

/**
 * Return *text* when it is a valid calendar date (`YYYY-MM-DD`), else null.
 * Shape is checked by DATE_RE, calendar values by real Date construction.
 */
function resolveDate(text: string): string | null {
  const m = DATE_RE.exec(text);
  if (m === null) return null;
  if (!isCalendarDate(Number(m[1]), Number(m[2]), Number(m[3]))) return null;
  return text;
}

/**
 * Resolve a temporal operand to a timestamp: numbers pass through,
 * `"today"` anchors to the local midnight of *now*, `"YYYY-MM-DD"` to that
 * day's local midnight (local timezone, like Python `datetime.timestamp`).
 */
function localMidnight(operand: number | string, now: number): number {
  if (typeof operand === "number") return operand;
  if (operand === "today") {
    const local = new Date(now * 1000);
    local.setHours(0, 0, 0, 0);
    return local.getTime() / 1000;
  }
  const [year, month, day] = operand.split("-").map(Number);
  return new Date(year, month - 1, day).getTime() / 1000;
}

/**
 * Build comparators for a date/today operand with optional prefix.
 * `>date` → on/after the day start; `<date` → strictly before the day
 * start (the whole day is excluded); a bare date → the whole local day
 * (start inclusive, end exclusive, fixed +86400 offset).
 */
function dateComparators(operand: string, opChar: string): AttrComparator[] {
  if (opChar === ">") {
    return [{ field: "mtime", op: "since_day_start", operand }];
  }
  if (opChar === "<") {
    // `<date` excludes the entire day: t < midnight(date).
    return [{ field: "mtime", op: "lt", operand }];
  }
  return [
    { field: "mtime", op: "since_day_start", operand },
    { field: "mtime", op: "before_day_end", operand },
  ];
}

/**
 * Parse one operand with optional `>`/`<` prefix. Magnitudes yield
 * gt/lt/eq on size_bytes; dates and "today" yield day-window comparators
 * on mtime; prefixed durations yield age comparators on mtime. Bare
 * durations are not valid operands.
 */
function parseSingle(text: string): AttrComparator[] | null {
  let opChar = "";
  let value = text;
  if (value.startsWith(">") || value.startsWith("<")) {
    opChar = value[0];
    value = value.slice(1);
  }
  if (!value) return null;
  const size = resolveSize(value);
  if (size !== null) {
    if (opChar === ">") return [{ field: SIZE_FIELD, op: "gt", operand: size }];
    if (opChar === "<") return [{ field: SIZE_FIELD, op: "lt", operand: size }];
    return [{ field: SIZE_FIELD, op: "eq", operand: size }];
  }
  const date = resolveDate(value);
  if (date !== null) return dateComparators(date, opChar);
  if (value.toLowerCase() === "today") {
    return dateComparators("today", opChar);
  }
  const duration = resolveDuration(value);
  if (duration !== null) {
    if (opChar === ">") {
      return [{ field: "mtime", op: "age_gt", operand: duration }];
    }
    if (opChar === "<") {
      return [{ field: "mtime", op: "age_lt", operand: duration }];
    }
    return null; // bare duration is not a valid operand
  }
  return null;
}

/**
 * Parse one side of an `a..b` range (prefix-less) into its bound
 * comparator: sizes map to ge/le, dates and "today" to
 * since_day_start/before_day_end, durations to age_ge/age_le.
 */
function parseRangeSide(text: string, lower: boolean): AttrComparator | null {
  const size = resolveSize(text);
  if (size !== null) {
    return { field: SIZE_FIELD, op: lower ? "ge" : "le", operand: size };
  }
  const date = resolveDate(text);
  if (date !== null) {
    return {
      field: "mtime",
      op: lower ? "since_day_start" : "before_day_end",
      operand: date,
    };
  }
  if (text.toLowerCase() === "today") {
    return {
      field: "mtime",
      op: lower ? "since_day_start" : "before_day_end",
      operand: "today",
    };
  }
  const duration = resolveDuration(text);
  if (duration !== null) {
    return {
      field: "mtime",
      op: lower ? "age_ge" : "age_le",
      operand: duration,
    };
  }
  return null;
}

/**
 * Parse an `a..b` range into an inclusive pair of bound comparators.
 * Both sides must be prefix-less operands; more than one `..` or an empty
 * side is a parse failure, as are mixed size/temporal bounds.
 */
function parseRange(text: string): AttrComparator[] | null {
  const sides = text.split("..");
  if (sides.length !== 2 || !sides[0] || !sides[1]) return null;
  const lower = parseRangeSide(sides[0], true);
  const upper = parseRangeSide(sides[1], false);
  if (lower === null || upper === null) return null;
  if ((lower.field === SIZE_FIELD) !== (upper.field === SIZE_FIELD)) {
    return null; // mixed size / temporal bounds are invalid
  }
  return [lower, upper];
}

/**
 * Parse a `key:value` token into an AttrTerm. Any leading `-`/`+` prefix
 * must already be stripped by the caller. Unknown keys, missing
 * separators, malformed values, kind mismatches (e.g. `modified:>10mb`)
 * and bare durations are parse failures (→ substring fallback).
 */
function parseAttrToken(term: string): AttrTerm | null {
  const sepIndex = term.indexOf(":");
  if (sepIndex === -1) return null;
  const key = term.slice(0, sepIndex);
  const value = term.slice(sepIndex + 1);
  if (!value) return null;
  const canonical = key.toLowerCase();
  const field = ATTR_FIELD[canonical];
  if (field === undefined) return null;
  const comparators = value.includes("..")
    ? parseRange(value)
    : parseSingle(value);
  if (comparators === null) return null;
  const resolved: AttrComparator[] = [];
  for (const comparator of comparators) {
    const isSize = comparator.field === SIZE_FIELD;
    if (isSize !== (field === SIZE_FIELD)) {
      return null; // operand kind does not match the attribute kind
    }
    resolved.push({ ...comparator, field });
  }
  return { key: canonical, comparators: resolved };
}

/**
 * Evaluate one comparator against *attrs* at time *now* — the same 11 ops
 * as the Python `_comparator_matches`. Age ops follow the GNU-find
 * reading: the operand bounds the file's *age*, e.g. `age_lt(x)` ⇔
 * `t > now - x` (recent).
 */
function comparatorMatches(
  comparator: AttrComparator,
  attrs: FileAttrs,
  now: number,
): boolean {
  const value = Number(attrs[comparator.field as keyof FileAttrs]);
  const op = comparator.op;
  if (op === "gt") return value > localMidnight(comparator.operand, now);
  if (op === "lt") return value < localMidnight(comparator.operand, now);
  if (op === "ge") return value >= localMidnight(comparator.operand, now);
  if (op === "le") return value <= localMidnight(comparator.operand, now);
  if (op === "eq") return value === localMidnight(comparator.operand, now);
  if (op === "since_day_start") {
    return value >= localMidnight(comparator.operand, now);
  }
  if (op === "before_day_end") {
    return value < localMidnight(comparator.operand, now) + DAY_SECONDS;
  }
  if (op === "age_lt") return value > now - Number(comparator.operand); // age < operand ⇔ t > now - operand
  if (op === "age_gt") return value < now - Number(comparator.operand); // age > operand ⇔ t < now - operand
  if (op === "age_le") return value >= now - Number(comparator.operand); // age <= operand ⇔ t >= now - operand
  // op === "age_ge": age >= operand ⇔ timestamp <= now - operand
  return value <= now - Number(comparator.operand);
}

const attrGroupsCache = new Map<string, AttrGroupTerm[][]>();

/**
 * Compile *query* into OR-groups of operator-mode tokens, memoized per
 * distinct query string (256 entries, LRU — mirrors Python
 * `_compile_attr_groups` with `@lru_cache(maxsize=256)`). Quoted tokens
 * always carry `attrTerm = null` (never operators).
 */
function parseAttrGroups(query: string): AttrGroupTerm[][] {
  const cached = attrGroupsCache.get(query);
  if (cached) {
    // Refresh recency for LRU semantics.
    attrGroupsCache.delete(query);
    attrGroupsCache.set(query, cached);
    return cached;
  }

  const groups: AttrGroupTerm[][] = [];
  let current: AttrGroupTerm[] = [];
  for (const [token, quoted] of tokenizeSpans(query)) {
    if (token.toUpperCase() === "OR") {
      groups.push(current);
      current = [];
      continue;
    }
    let negated = false;
    let text = token;
    if (text.startsWith("-")) {
      negated = true;
      text = text.slice(1);
    } else if (text.startsWith("+")) {
      text = text.slice(1);
    }
    const attrTerm = quoted ? null : parseAttrToken(text);
    current.push({ negated, text, attrTerm });
  }
  groups.push(current);

  if (attrGroupsCache.size >= CACHE_LIMIT) {
    // Evict the least-recently-used entry.
    const oldest = attrGroupsCache.keys().next().value;
    if (oldest !== undefined) attrGroupsCache.delete(oldest);
  }
  attrGroupsCache.set(query, groups);
  return groups;
}

/**
 * Evaluate one AND-group in operator mode (mirrors `_attr_group_matches`):
 * attribute terms require *attrs* (they evaluate to false without data
 * while negation still flips them); every other token — quoted tokens and
 * malformed operators included — is a case-insensitive substring test.
 */
function attrGroupMatches(
  filenameLower: string,
  group: AttrGroupTerm[],
  attrs: FileAttrs | null,
  now: number,
): boolean {
  for (const term of group) {
    if (!term.text) continue; // skip empties (bare "-", consecutive OR, …)
    let outcome: boolean;
    if (term.attrTerm !== null) {
      if (attrs === null) {
        outcome = false; // operator mode without data → term fails
      } else {
        outcome = term.attrTerm.comparators.every((comparator) =>
          comparatorMatches(comparator, attrs, now),
        );
      }
    } else {
      outcome = filenameLower.includes(term.text.toLowerCase());
    }
    if (term.negated) {
      if (outcome) return false;
    } else if (!outcome) {
      return false;
    }
  }
  return true;
}

/**
 * Operator-mode matcher mirroring Python `match_file` (called with
 * non-null attrs by `matchFilter`; the null branch of the group evaluator
 * is kept for exact structural parity).
 */
function matchFileAttrs(
  filename: string,
  query: string,
  attrs: FileAttrs | null,
  now: number,
): boolean {
  const filenameLower = filename.toLowerCase();
  return parseAttrGroups(query).some((group) =>
    attrGroupMatches(filenameLower, group, attrs, now),
  );
}
