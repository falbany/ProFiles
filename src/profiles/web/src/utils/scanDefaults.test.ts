import { describe, expect, it } from "vitest";

import { mergeDirectoryPreference } from "./scanDefaults";

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
