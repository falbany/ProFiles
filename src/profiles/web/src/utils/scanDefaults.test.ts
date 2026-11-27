import { describe, expect, it } from "vitest";

import {
  MIN_UI_SCAN_CAP,
  UNLIMITED_SCAN_DEPTH,
  barcodeRecursiveToDepth,
  buildDepthOptions,
  clampDepth,
  mergeDirectoryPreference,
} from "./scanDefaults";

describe("mergeDirectoryPreference", () => {
  it.each([
    {
      current: ".txt",
      candidates: [".txt", ".py"],
      fallback: ".keep",
      expected: ".txt",
      because: "keeps current when it is among the candidates",
    },
    {
      current: ".py",
      candidates: [".txt"],
      fallback: ".keep",
      expected: ".txt",
      because: "selects the first candidate when current misses",
    },
    {
      current: ".py",
      candidates: undefined,
      fallback: ".keep",
      expected: ".keep",
      because: "falls back when there are no candidates (undefined config)",
    },
    {
      current: ".py",
      candidates: [],
      fallback: ".keep",
      expected: ".keep",
      because: "picked-site fallback keeps the current value",
    },
    {
      current: ".py",
      candidates: [],
      fallback: "",
      expected: "",
      because: "changed-site fallback resets to empty",
    },
    {
      current: ".py",
      candidates: [],
      fallback: "all",
      expected: "all",
      because: "passes the fallback through unchanged",
    },
    {
      current: "",
      candidates: ["a"],
      fallback: "",
      expected: "a",
      because: "empty current never matches, so the first candidate wins",
    },
  ])(
    "($current, $candidates, $fallback) -> $expected — $because",
    ({ current, candidates, fallback, expected }) => {
      expect(mergeDirectoryPreference(current, candidates, fallback)).toBe(expected);
    },
  );
});

describe("depth constants", () => {
  it("exposes the UI minimum cap and the unlimited sentinel", () => {
    expect(MIN_UI_SCAN_CAP).toBe(25);
    expect(UNLIMITED_SCAN_DEPTH).toBe(2147483647);
  });
});

describe("buildDepthOptions", () => {
  it("lists 1..25 when the config depth is the default 10", () => {
    expect(buildDepthOptions(10)).toEqual(Array.from({ length: 25 }, (_, i) => i + 1));
  });
  it("extends to the configured depth — config 40 offers exactly 40", () => {
    const opts = buildDepthOptions(40);
    expect(opts.length).toBe(40);
    expect(opts[39]).toBe(40);
  });
  it("config 0 still yields 1..25 (root-only stays selectable)", () => {
    expect(buildDepthOptions(0)).toEqual(Array.from({ length: 25 }, (_, i) => i + 1));
  });
});
describe("clampDepth", () => {
  it("floors at 1", () => {
    expect(clampDepth(0)).toBe(1);
    expect(clampDepth(-5)).toBe(1);
  });
  it("never clamps above", () => {
    expect(clampDepth(40)).toBe(40);
  });
});
describe("barcodeRecursiveToDepth", () => {
  it("false → 1", () => expect(barcodeRecursiveToDepth(false, 5, 10)).toBe(1));
  it("true → config depth", () => expect(barcodeRecursiveToDepth(true, 3, 10)).toBe(10));
  it("undefined → current", () => expect(barcodeRecursiveToDepth(undefined, 3, 10)).toBe(3));
});
