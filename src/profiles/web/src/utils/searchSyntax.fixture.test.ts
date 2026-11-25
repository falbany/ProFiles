/**
 * Fixture-driven conformance tests for the shared Py/TS operator fixture.
 *
 * Reads `searchOperators.fixture.json` — the anti-drift contract between the
 * normative Python grammar (`src/profiles/utils/search_parser.py`) and this
 * TypeScript port — and replays every case through `matchFilter` in operator
 * mode (attrs + now injected) or substring mode (2-arg call), mirroring
 * `tests/utils/test_search_parser_fixture.py`. Expectations in the fixture
 * are hand-derived from the documented semantics, never generated from the
 * implementation.
 * @see ./searchSyntax.ts
 */

import { describe, expect, it } from "vitest";
import fixtureJson from "./searchOperators.fixture.json";
import { matchFilter, type FileAttrs } from "./searchSyntax";

// Fixture schema (mirrors tests/utils/test_search_parser_fixture.py) ───────

interface AnchorSpec {
  from: "now" | "today" | "date";
  offset_seconds?: number;
  date?: string;
}

interface FixtureAttrs {
  size_bytes: number;
  mtime: AnchorSpec;
  birthtime: AnchorSpec;
}

interface OperatorCase {
  name: string;
  query: string;
  now: number;
  filename: string;
  attrs: FixtureAttrs | null;
  expected: boolean;
}

interface SubstringCase {
  name: string;
  query: string;
  filename: string;
  expected: boolean;
}

interface FixtureData {
  operator_cases: OperatorCase[];
  substring_cases: SubstringCase[];
}

const fixture = fixtureJson as unknown as FixtureData;

/**
 * Resolve a fixture anchor spec into an epoch timestamp — mirrors the Python
 * consumer's `_anchor_epoch`: "now" passes `now` through, "today" is the
 * local midnight of `now`, and "date" is the local midnight of its
 * `YYYY-MM-DD` day. `offset_seconds` is added in every case.
 */
function anchorEpoch(spec: AnchorSpec, now: number): number {
  const offset = spec.offset_seconds ?? 0;
  if (spec.from === "now") return now + offset;
  if (spec.from === "today") {
    const local = new Date(now * 1000);
    local.setHours(0, 0, 0, 0);
    return local.getTime() / 1000 + offset;
  }
  const [year, month, day] = (spec.date ?? "").split("-").map(Number);
  return new Date(year, month - 1, day).getTime() / 1000 + offset;
}

// ── operator cases (matchFilter(filename, query, attrs, now)) ─────────────

describe("searchOperators fixture — operator cases", () => {
  for (const operatorCase of fixture.operator_cases) {
    it(operatorCase.name, () => {
      const attrs: FileAttrs | null =
        operatorCase.attrs === null
          ? null
          : {
              size_bytes: operatorCase.attrs.size_bytes,
              mtime: anchorEpoch(operatorCase.attrs.mtime, operatorCase.now),
              birthtime: anchorEpoch(
                operatorCase.attrs.birthtime,
                operatorCase.now,
              ),
            };
      expect(
        matchFilter(
          operatorCase.filename,
          operatorCase.query,
          attrs,
          operatorCase.now,
        ),
      ).toBe(operatorCase.expected);
    });
  }
});

// ── substring cases (2-arg matchFilter — legacy parity) ───────────────────

describe("searchOperators fixture — substring cases", () => {
  for (const substringCase of fixture.substring_cases) {
    it(substringCase.name, () => {
      expect(
        matchFilter(substringCase.filename, substringCase.query),
      ).toBe(substringCase.expected);
    });
  }
});

// ── 2-arg unit cases (operator-shaped terms stay plain includes) ──────────

describe("matchFilter 2-arg parity for operator-shaped queries", () => {
  it("treats an operator query as a plain include on a non-matching filename", () => {
    expect(matchFilter("dump.log", "size:>10mb")).toBe(false);
  });

  it("treats an operator query as a plain include when the filename contains the literal", () => {
    expect(matchFilter("report_size:>10mb.log", "size:>10mb")).toBe(true);
  });

  it("keeps negated operator-shaped terms as plain excludes", () => {
    expect(matchFilter("dump.log", "-size:>10mb")).toBe(true);
    expect(matchFilter("report_size:>10mb.log", "-size:>10mb")).toBe(false);
  });
});
