/**
 * Search query parser supporting Google-style operators — TypeScript port of
 * `src/profiles/utils/search_parser.py` (Python parity is normative).
 *
 * Public API:
 *   describeQuery(query) -> { error: string | null, groups: { includes, excludes }[] }
 *   matchFilter(filename, query) -> boolean
 *
 * Grammar:
 *   `a b`        — AND: every term in a group must appear
 *   `a OR b`     — alternative groups (case-insensitive keyword)
 *   `-a`         — NOT: term must not appear
 *   `+a`         — explicit include (same as a plain term)
 *   `"a b"`      — exact phrase, matched verbatim (quotes stripped)
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
 * Case-insensitive match of a filename against a filter query.
 * Alternatives (OR groups) match on any; AND terms inside a group all
 * apply. An empty or whitespace-only query matches everything.
 */
export function matchFilter(filename: string, query: string): boolean {
  const { groups } = parseForMatching(query);
  if (groups.length === 0) return true;
  const target = filename.toLowerCase();
  return groups.some((groupItem) => groupMatches(target, groupItem));
}
