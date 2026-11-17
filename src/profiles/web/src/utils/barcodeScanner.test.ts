import { describe, expect, it } from "vitest";

import { barcodeShouldScan, type BarcodeParsedInput } from "./barcodeScanner";

describe("barcodeShouldScan", () => {
  it.each([
    {
      values: { scan: true },
      expected: true,
      because: "scan=1 alone triggers a rescan",
    },
    {
      values: { filter: "x" },
      expected: true,
      because: "filter presence triggers a rescan",
    },
    {
      values: { ext: ".py" },
      expected: true,
      because: "ext presence triggers a rescan",
    },
    {
      values: { recursive: false },
      expected: true,
      because: "recursive presence (not truthiness) triggers a rescan",
    },
    {
      values: { dir: "C:/d" },
      expected: true,
      because: "dir presence triggers a rescan",
    },
    {
      values: {},
      expected: false,
      because: "no values at all means nothing to apply",
    },
    {
      values: { scan: false },
      expected: false,
      because: "scan explicitly disabled with no other values",
    },
    {
      values: { scan: false, filter: undefined },
      expected: false,
      because: "explicit undefined is not a value",
    },
  ])(
    "$values -> $expected — $because",
    ({ values, expected }) => {
      expect(barcodeShouldScan(values as Partial<BarcodeParsedInput>)).toBe(expected);
    },
  );
});
