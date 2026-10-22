/**
 * Tests for the search filter engine (port of the Python search-parser
 * test suite). All sample filenames/queries are generic and
 * non-confidential.
 * @see ./searchSyntax.ts
 */

import { describe, expect, it } from "vitest";
import { describeQuery, matchFilter } from "./searchSyntax";

// Shared generic sample corpus (single source of truth for file fixtures) ──
const SAMPLE_FILES = [
  "alpha_delta_charlie_0866_v1-r2.3.1.sample",
  "beta_gamma_v2.sample",
  "alpha_zulu_v3.dts",
  "readme.txt",
  "config.ini",
];

/** Filter the full corpus with a query. */
function filterAll(query: string): string[] {
  return SAMPLE_FILES.filter((f) => matchFilter(f, query));
}

// Helpers ─────────────────────────────────────────────────────────────────

function group(
  includes: string[],
  excludes: string[] = [],
): { includes: string[]; excludes: string[] } {
  return { includes, excludes };
}

// ── describeQuery ─────────────────────────────────────────────────────────

describe("describeQuery", () => {
  it("returns a single group for a plain AND query", () => {
    expect(describeQuery("alpha delta")).toEqual({
      error: null,
      groups: [group(["alpha", "delta"])],
    });
  });

  it("splits OR alternatives", () => {
    expect(describeQuery("alpha OR beta")).toEqual({
      error: null,
      groups: [group(["alpha"]), group(["beta"])],
    });
  });

  it("handles multiple OR", () => {
    expect(describeQuery("A OR B OR C")).toEqual({
      error: null,
      groups: [group(["A"]), group(["B"]), group(["C"])],
    });
  });

  it("keeps AND tokens inside OR groups", () => {
    expect(describeQuery("A B OR C D")).toEqual({
      error: null,
      groups: [group(["A", "B"]), group(["C", "D"])],
    });
  });

  it("treats lowercase or as the separator", () => {
    expect(describeQuery("a or b")).toEqual({
      error: null,
      groups: [group(["a"]), group(["b"])],
    });
  });

  it("preserves trailing OR empty group", () => {
    expect(describeQuery("A OR")).toEqual({
      error: null,
      groups: [group(["A"]), group([])],
    });
  });

  it("preserves leading OR empty group", () => {
    expect(describeQuery("OR A")).toEqual({
      error: null,
      groups: [group([]), group(["A"])],
    });
  });

  it("collects excludes separately from includes", () => {
    expect(describeQuery("abc -temp")).toEqual({
      error: null,
      groups: [group(["abc"], ["temp"])],
    });
  });

  it("strips the + prefix (same as plain term)", () => {
    expect(describeQuery("+abc")).toEqual({
      error: null,
      groups: [group(["abc"])],
    });
  });

  it("skips a bare dash", () => {
    expect(describeQuery("-")).toEqual({
      error: null,
      groups: [group([])],
    });
    expect(describeQuery("a - OR b")).toEqual({
      error: null,
      groups: [group(["a"]), group(["b"])],
    });
  });

  it("returns quoted phrases without quotes", () => {
    expect(describeQuery('"Hello World"')).toEqual({
      error: null,
      groups: [group(["Hello World"])],
    });
  });

  it("mixes quoted and unquoted tokens", () => {
    expect(describeQuery('alpha "delta v1"')).toEqual({
      error: null,
      groups: [group(["alpha", "delta v1"])],
    });
  });

  // Note: the Python-faithful token order places the quoted phrase in the
  // FIRST group here, even though some contract sketches show it in the
  // second — token position relative to OR decides the group.
  it("decomposes a mixed excludes/phrase/OR query", () => {
    expect(describeQuery('abc -temp "x y" OR def')).toEqual({
      error: null,
      groups: [group(["abc", "x y"], ["temp"]), group(["def"])],
    });
  });

  it("returns empty groups for empty and whitespace queries", () => {
    expect(describeQuery("")).toEqual({ error: null, groups: [] });
    expect(describeQuery("   ")).toEqual({ error: null, groups: [] });
  });

  it("drops empty quoted phrases", () => {
    expect(describeQuery('a "" b')).toEqual({
      error: null,
      groups: [group(["a", "b"])],
    });
    expect(describeQuery('""')).toEqual({ error: null, groups: [] });
    expect(describeQuery('"  "')).toEqual({ error: null, groups: [] });
  });

  it("flags an unmatched trailing quote", () => {
    expect(describeQuery('abc"')).toEqual({
      error: "Unmatched quote",
      groups: [group(['abc"'])],
    });
  });

  it("flags an unmatched quote on a best-effort tokenized query", () => {
    expect(describeQuery('alpha "unclosed')).toEqual({
      error: "Unmatched quote",
      groups: [group(["alpha", '"unclosed'])],
    });
  });

  it("does not flag balanced quotes", () => {
    expect(describeQuery('"a" OR "b"').error).toBeNull();
    expect(describeQuery('say "hi" then').error).toBeNull();
  });
});

// ── matchFilter ───────────────────────────────────────────────────────────

describe("matchFilter — empty / edge cases", () => {
  it("empty query matches everything", () => {
    expect(matchFilter("alpha_delta.sample", "")).toBe(true);
  });

  it("whitespace-only query matches everything", () => {
    expect(matchFilter("alpha_delta.sample", "   ")).toBe(true);
  });

  it("quote-only query matches everything (empty tokens dropped)", () => {
    expect(matchFilter("anything.pdf", '""')).toBe(true);
    expect(matchFilter("anything.pdf", '"  "')).toBe(true);
  });
});

describe("matchFilter — simple keyword", () => {
  it("matches a single keyword", () => {
    expect(matchFilter("alpha_delta.sample", "alpha")).toBe(true);
  });

  it("rejects a non-matching keyword", () => {
    expect(matchFilter("beta_gamma.log", "alpha")).toBe(false);
  });

  it("is case-insensitive (both directions)", () => {
    expect(matchFilter("alpha_delta.sample", "ALPHA")).toBe(true);
    expect(matchFilter("ALPHA_DELTA.sample", "alpha")).toBe(true);
  });

  it("matches substrings", () => {
    expect(matchFilter("alpha_delta.sample", "del")).toBe(true);
  });

  it("handles single-character terms", () => {
    expect(matchFilter("A_file.log", "A")).toBe(true);
    expect(matchFilter("B_file.log", "A")).toBe(false);
  });

  it("ignores leading and trailing spaces", () => {
    expect(matchFilter("alpha.sample", "  alpha")).toBe(true);
    expect(matchFilter("alpha.sample", "alpha  ")).toBe(true);
  });

  it("collapses multiple spaces", () => {
    expect(describeQuery("alpha    delta")).toEqual({
      error: null,
      groups: [group(["alpha", "delta"])],
    });
  });

  it("keeps special characters intact", () => {
    expect(matchFilter("my Special_File.a_b-c", "a_b-c")).toBe(true);
  });
});

describe("matchFilter — AND (space-separated)", () => {
  it("requires all terms", () => {
    expect(matchFilter("alpha_delta_v1.sample", "alpha delta")).toBe(true);
    expect(matchFilter("alpha_delta.sample", "alpha wxyz")).toBe(false);
    expect(matchFilter("beta_gamma.log", "alpha delta")).toBe(false);
  });

  it("supports three or more terms", () => {
    expect(
      matchFilter("alpha_delta_charlie_v1.sample", "alpha delta v1"),
    ).toBe(true);
  });

  it("works with substrings", () => {
    expect(matchFilter("alpha_zulu_v3.dts", "al v3")).toBe(true);
  });

  it("works with many terms", () => {
    const fname = "alpha_delta_charlie_0866_v1-r2.3.1.sample";
    expect(
      matchFilter(fname, "alpha delta charlie 0866 v1 r2.3.1"),
    ).toBe(true);
    expect(matchFilter(fname, "alpha delta charlie nope")).toBe(false);
  });
});

describe("matchFilter — OR", () => {
  const q = "alpha OR beta";

  it("matches when either alternative matches", () => {
    expect(matchFilter("alpha_delta.sample", q)).toBe(true);
    expect(matchFilter("beta_gamma.log", q)).toBe(true);
    expect(matchFilter("alpha_beta_delta.sample", q)).toBe(true);
  });

  it("rejects when neither alternative matches", () => {
    expect(matchFilter("readme.txt", q)).toBe(false);
  });

  it("supports three alternatives", () => {
    expect(matchFilter("readme.txt", "alpha OR beta OR readme")).toBe(true);
    expect(matchFilter("readme.txt", "alpha OR beta OR wxyz")).toBe(false);
  });

  it("is case-insensitive on terms and the keyword", () => {
    expect(matchFilter("ALPHA.sample", "alpha or beta")).toBe(true);
  });

  it("requires AND within the second group", () => {
    expect(matchFilter("A_B.log", "A OR B C")).toBe(true);
    expect(matchFilter("A_C.log", "A OR B C")).toBe(true);
    expect(matchFilter("B.log", "A OR B C")).toBe(false);
  });
});

describe("matchFilter — mixed AND + OR", () => {
  const q = "alpha delta OR beta";

  it("matches via the first group", () => {
    expect(matchFilter("alpha_delta.sample", q)).toBe(true);
  });

  it("matches via the second group", () => {
    expect(matchFilter("beta_gamma.log", q)).toBe(true);
  });

  it("rejects when neither group matches", () => {
    expect(matchFilter("readme.txt", q)).toBe(false);
  });

  it("handles complex two-term groups", () => {
    const q2 = "alpha charlie OR beta v2";
    expect(matchFilter("beta_gamma_v2.sample", q2)).toBe(true);
    expect(matchFilter("alpha_charlie.sample", q2)).toBe(true);
    expect(matchFilter("readme.txt", q2)).toBe(false);
  });
});

describe("matchFilter — NOT (-prefix)", () => {
  it("excludes matching terms", () => {
    expect(matchFilter("alpha_delta_v1.sample", "alpha -v1")).toBe(false);
  });

  it("allows non-matching exclusions", () => {
    expect(matchFilter("alpha_delta.sample", "alpha -v1")).toBe(true);
  });

  it("combines with OR", () => {
    expect(matchFilter("beta_gamma.log", "alpha OR -beta")).toBe(false);
    expect(matchFilter("readme.txt", "alpha OR -beta")).toBe(true);
  });

  it("works alone", () => {
    expect(matchFilter("alpha.sample", "-alpha")).toBe(false);
    expect(matchFilter("readme.txt", "-alpha")).toBe(true);
  });

  it("ignores a bare dash", () => {
    expect(matchFilter("alpha.sample", "-")).toBe(true);
  });

  it("is case-insensitive in the exclusion", () => {
    expect(matchFilter("ALPHA.sample", "-alpha")).toBe(false);
  });

  it("works with single characters", () => {
    expect(matchFilter("AB.log", "A -B")).toBe(false);
    expect(matchFilter("A.log", "A -B")).toBe(true);
  });
});

describe("matchFilter — + prefix", () => {
  it("behaves exactly like a plain term", () => {
    expect(matchFilter("alpha_delta.sample", "+alpha")).toBe(true);
    expect(matchFilter("beta_gamma.log", "+alpha")).toBe(false);
    expect(matchFilter("alpha_delta_v1.sample", "+alpha +delta")).toBe(true);
    expect(matchFilter("alpha_delta.sample", "+alpha +delta")).toBe(true);
  });
});

describe("matchFilter — exact phrase (quoted)", () => {
  it("matches verbatim phrases", () => {
    expect(matchFilter("alpha_delta_v1.sample", '"alpha_delta"')).toBe(true);
    expect(matchFilter("alpha_delta.sample", '"beta_gamma"')).toBe(false);
  });

  it("matches spaces inside quoted phrases", () => {
    expect(matchFilter("my file.sample", '"my file"')).toBe(true);
    expect(matchFilter("my_file.sample", '"my file"')).toBe(false);
  });

  it("combines with plain terms", () => {
    expect(
      matchFilter("alpha_delta_v1.sample", 'alpha "delta_v1"'),
    ).toBe(true);
    expect(
      matchFilter("alpha_delta_v1.sample", 'alpha "bad_phrase"'),
    ).toBe(false);
  });

  it("combines with OR", () => {
    const q = '"alpha" OR "beta"';
    expect(matchFilter("alpha.sample", q)).toBe(true);
    expect(matchFilter("beta.sample", q)).toBe(true);
    expect(matchFilter("readme.txt", q)).toBe(false);
  });

  it("matches an exact version string", () => {
    const matches = filterAll('"v1-r2.3.1"');
    expect(matches).toEqual(["alpha_delta_charlie_0866_v1-r2.3.1.sample"]);
  });
});

describe("matchFilter — unmatched quote (best effort)", () => {
  it("keeps the stray quote as part of the token", () => {
    // Tokens: ['alpha', '"unclosed'] — the group fails unless the
    // target literally contains `alpha` and `"unclosed`.
    expect(matchFilter('alpha_"unclosed.sample', 'alpha "unclosed')).toBe(
      true,
    );
    expect(matchFilter("alpha file", 'alpha "unclosed')).toBe(false);
  });
});

describe("matchFilter — real-world scenarios", () => {
  // Uses the shared SAMPLE_FILES corpus defined at the top of this file.

  it("filters alpha files", () => {
    const matches = filterAll("alpha");
    expect(matches).toContain("alpha_delta_charlie_0866_v1-r2.3.1.sample");
    expect(matches).toContain("alpha_zulu_v3.dts");
    expect(matches).not.toContain("beta_gamma_v2.sample");
  });

  it("finds alpha delta files", () => {
    const matches = filterAll("alpha delta");
    expect(matches).toEqual(["alpha_delta_charlie_0866_v1-r2.3.1.sample"]);
  });

  it("excludes the 0866 version", () => {
    const matches = filterAll("alpha -0866");
    expect(matches).toEqual(["alpha_zulu_v3.dts"]);
  });

  it("selects alpha or beta files", () => {
    expect(filterAll("alpha OR beta")).toHaveLength(3);
  });
});

describe("matchFilter — memoization", () => {
  it("returns consistent results for repeated queries", () => {
    expect(matchFilter("A.log", "A OR B")).toBe(true);
    expect(matchFilter("B.log", "A OR B")).toBe(true);
    expect(matchFilter("C.log", "A OR B")).toBe(false);
  });

  it("survives more than 256 distinct queries (cache eviction)", () => {
    for (let i = 0; i < 300; i++) {
      expect(matchFilter(`t${i}z.sample`, `t${i}z`)).toBe(true);
      expect(matchFilter(`t${i}z.sample`, `-t${i}z nohit`)).toBe(false);
    }
  });
});
