// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import {
  MAX_RECENT_COMMANDS,
  parseRecentCommands,
  pushRecentCommand,
  useRecentCommands,
} from "./useRecentCommands";

const KEY = "profiles-recent-commands";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

describe("parseRecentCommands", () => {
  it("reads a stored list and caps it", () => {
    expect(parseRecentCommands('["a","b"]')).toEqual(["a", "b"]);
    expect(parseRecentCommands(JSON.stringify(Array.from({ length: 20 }, (_, i) => `c${i}`)))).toHaveLength(
      MAX_RECENT_COMMANDS,
    );
  });

  it("treats anything unexpected as no recents", () => {
    expect(parseRecentCommands(null)).toEqual([]);
    expect(parseRecentCommands("")).toEqual([]);
    expect(parseRecentCommands("not json")).toEqual([]);
    expect(parseRecentCommands('{"id":"a"}')).toEqual([]);
    expect(parseRecentCommands('["a", 42, null, "b"]')).toEqual(["a", "b"]);
  });
});

describe("pushRecentCommand", () => {
  it("promotes the command, drops the duplicate and caps the list", () => {
    expect(pushRecentCommand(["a", "b", "c"], "b")).toEqual(["b", "a", "c"]);
    expect(pushRecentCommand([], "x")).toEqual(["x"]);
    expect(pushRecentCommand(["a", "b", "c"], "d", 2)).toEqual(["d", "a"]);
  });
});

describe("useRecentCommands", () => {
  it("starts from the stored list and persists each touch, newest first", () => {
    window.localStorage.setItem(KEY, '["scan.run"]');
    const { result } = renderHook(() => useRecentCommands());
    expect(result.current.recentIds).toEqual(["scan.run"]);

    act(() => result.current.touch("view.theme"));
    act(() => result.current.touch("scan.run"));

    expect(result.current.recentIds).toEqual(["scan.run", "view.theme"]);
    expect(JSON.parse(window.localStorage.getItem(KEY) ?? "[]")).toEqual(["scan.run", "view.theme"]);
  });

  it("survives a corrupt stored value by rewriting a clean list", () => {
    window.localStorage.setItem(KEY, "{broken");
    const { result } = renderHook(() => useRecentCommands());

    expect(result.current.recentIds).toEqual([]);
    expect(window.localStorage.getItem(KEY)).toBe("[]");
  });

  it("keeps working when storage is blocked", () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    const { result } = renderHook(() => useRecentCommands());
    act(() => result.current.touch("file.launch"));

    expect(result.current.recentIds).toEqual(["file.launch"]);

    getItem.mockRestore();
    setItem.mockRestore();
  });
});
