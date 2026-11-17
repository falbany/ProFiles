// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";

/**
 * Unit tests for the `useTheme` hook (issue #148, PR 5 — fixes #129). They
 * pin the #129 restore behavior (a stored "light" preference wins at mount;
 * missing, invalid, or unreadable stored values fall back to "dark"), the
 * provenance-controlled persistence (`persist: true` writes localStorage at
 * call time, `persist: false` leaves storage untouched), the ref-based
 * toggle (flips the CURRENT theme in both directions), and the `data-theme`
 * attribute following every path — including the restore at mount.
 */
import { useTheme } from "./useTheme";

const STORAGE_KEY = "profiles-theme";

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("useTheme", () => {
  it("initial state restores a stored light preference", () => {
    localStorage.setItem(STORAGE_KEY, "light");

    const { result } = renderHook(() => useTheme());

    expect(result.current.theme).toBe("light");
  });

  it("initial state falls back to dark for missing, invalid, or unreadable stored values", () => {
    // Table: stored value → expected initial theme. Only "dark"/"light" are
    // valid persisted values (#129: a stored "auto" or garbage falls back to
    // "dark"; the matchMedia-driven "auto" is a non-goal follow-up).
    const table: Array<[string | null, string]> = [
      [null, "dark"], // no key at all
      ["garbage", "dark"], // invalid value
      ["auto", "dark"], // "auto" is not a persisted theme
      ["dark", "dark"], // valid value restored as-is
    ];
    for (const [seed, expected] of table) {
      if (seed === null) {
        localStorage.removeItem(STORAGE_KEY);
      } else {
        localStorage.setItem(STORAGE_KEY, seed);
      }
      const { result } = renderHook(() => useTheme());
      expect(result.current.theme).toBe(expected);
      cleanup();
    }

    // Unreadable storage: a throwing getItem still starts "dark".
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("deny");
    });
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
  });

  it("applyTheme with persist true sets the theme, updates data-theme, and writes localStorage", () => {
    const { result } = renderHook(() => useTheme());

    act(() => result.current.applyTheme("light", { persist: true }));

    expect(result.current.theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("light");
  });

  it("applyTheme with persist false sets the theme and data-theme but leaves storage untouched", () => {
    // Pre-existing stored value survives: no write, no delete (the #129
    // trial-theme path — session change without stealing the stored pref).
    localStorage.setItem(STORAGE_KEY, "dark");
    const { result } = renderHook(() => useTheme());

    act(() => result.current.applyTheme("light", { persist: false }));

    expect(result.current.theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark");
  });

  it("toggleTheme with persist true flips and persists, both directions", () => {
    // Fresh session (no stored key): the hook starts "dark".
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");

    act(() => result.current.toggleTheme({ persist: true }));
    expect(result.current.theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("light");

    act(() => result.current.toggleTheme({ persist: true }));
    expect(result.current.theme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark");
  });

  it("toggleTheme with persist false flips without persisting", () => {
    const { result } = renderHook(() => useTheme());

    act(() => result.current.toggleTheme({ persist: false }));

    expect(result.current.theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("data-theme attribute follows restore at mount", () => {
    localStorage.setItem(STORAGE_KEY, "light");

    renderHook(() => useTheme());

    // The attribute effect runs on mount with the restored value.
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
