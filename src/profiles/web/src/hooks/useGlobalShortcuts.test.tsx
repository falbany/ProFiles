// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { cleanup, fireEvent, renderHook } from "@testing-library/react";

/**
 * Unit tests for the `useGlobalShortcuts` hook (issue #148, PR 3) — the
 * global keydown effect extracted verbatim from `App.tsx`. They pin the
 * Escape-before-modal-guard ordering, the issue-#55 inert-while-modal guard,
 * the target routing guards, the context-menu position math (rect + 24 /
 * center, 24 fallbacks), every action shortcut's callback, the combobox
 * focus shortcuts, the exact clamp/identity semantics of the navigation
 * computes (Home/End identity-preserving returns included), the
 * subscription-time callback capture (the staleness profile of the original
 * inline effect — the double-Ctrl+R quirk's survival proof), and the
 * unmount teardown.
 */
import { useGlobalShortcuts } from "./useGlobalShortcuts";
import type { GlobalShortcutsDeps } from "./useGlobalShortcuts";
import type { ScannedFileItem } from "../api/types";

function makeFile(n: number): ScannedFileItem {
  return {
    column_values: {},
    filename: `file-${n}.txt`,
    rel_path: `file-${n}.txt`,
    path: `/data/file-${n}.txt`,
  };
}

/**
 * One SHARED visibleFiles array: the effect's dep list contains the array
 * identity, so tests that must NOT re-subscribe (the staleness scenario)
 * rely on rerenders keeping this exact reference.
 */
const FILES: ScannedFileItem[] = Array.from({ length: 10 }, (_, i) => makeFile(i));

function makeDeps(overrides: Partial<GlobalShortcutsDeps> = {}): GlobalShortcutsDeps {
  return {
    anyModalOpen: false,
    visibleFiles: FILES,
    selectedIndex: 0,
    activeDirectory: "/data",
    activeExtension: ".txt",
    filterText: "",
    recursive: true,
    barcodeMode: false,
    onEscape: vi.fn(),
    onContextMenu: vi.fn(),
    onExecute: vi.fn(),
    onScan: vi.fn(),
    onReloadConfig: vi.fn(),
    onGoHome: vi.fn(),
    onProperties: vi.fn(),
    onToggleTheme: vi.fn(),
    setShowLogViewer: vi.fn(),
    setShowShortcuts: vi.fn(),
    setShowTimerModal: vi.fn(),
    setShowConfigEditor: vi.fn(),
    setShowLanModal: vi.fn(),
    setBarcodeMode: vi.fn(),
    setShowCameraScanner: vi.fn(),
    moveSelection: vi.fn(),
    ...overrides,
  };
}

/** Mutable deps the renderHook callback reads on every render. */
let deps: GlobalShortcutsDeps;

beforeEach(() => {
  vi.clearAllMocks();
  deps = makeDeps();
});

afterEach(() => {
  cleanup();
  // Remove the fixture DOM the scenarios installed.
  document.body.innerHTML = "";
});

/** Fixture DOM matching the real surface the shortcuts act on. */
function installFixture(options: { rowIndex?: number } = {}): HTMLElement {
  const list = document.createElement("div");
  list.setAttribute("data-testid", "file-list");
  list.tabIndex = -1;
  document.body.appendChild(list);

  for (const id of ["directory-combobox", "extension-combobox", "filter-combobox"]) {
    const input = document.createElement("input");
    input.id = id;
    document.body.appendChild(input);
  }

  if (options.rowIndex !== undefined) {
    const row = document.createElement("div");
    row.setAttribute("data-row-index", String(options.rowIndex));
    document.body.appendChild(row);
  }
  return list;
}

/** Fire a keydown on window (the hook listens there, target = window). */
function press(
  key: string,
  mods: { ctrlKey?: boolean; shiftKey?: boolean } = {},
): void {
  fireEvent.keyDown(window, {
    key,
    ctrlKey: mods.ctrlKey ?? false,
    shiftKey: mods.shiftKey ?? false,
  });
}

describe("useGlobalShortcuts", () => {
  it("escape closes surfaces even when a modal is open", () => {
    installFixture();
    deps = makeDeps({ anyModalOpen: true });
    renderHook(() => useGlobalShortcuts(deps));

    press("Escape");
    expect(deps.onEscape).toHaveBeenCalledTimes(1);

    // A plain key while the modal is up must not reach the shortcuts.
    press("a");
    expect(deps.onEscape).toHaveBeenCalledTimes(1);
  });

  it("shortcuts are inert while a modal is open", () => {
    installFixture();
    deps = makeDeps({ anyModalOpen: true });
    renderHook(() => useGlobalShortcuts(deps));

    press("F5");
    press("r", { ctrlKey: true });
    press("Enter");
    press("ArrowDown");
    press("p");

    expect(deps.onScan).not.toHaveBeenCalled();
    expect(deps.onReloadConfig).not.toHaveBeenCalled();
    expect(deps.onExecute).not.toHaveBeenCalled();
    expect(deps.onProperties).not.toHaveBeenCalled();
    expect(deps.moveSelection).not.toHaveBeenCalled();
  });

  it("ctrl+L focuses the file list", () => {
    const list = installFixture();
    deps = makeDeps();
    renderHook(() => useGlobalShortcuts(deps));

    press("l", { ctrlKey: true });
    expect(document.activeElement).toBe(list);
    expect(deps.setShowLogViewer).not.toHaveBeenCalled();

    // Shift+L variant does NOT focus — it toggles the log viewer instead.
    list.blur();
    press("l", { ctrlKey: true, shiftKey: true });
    expect(document.activeElement).not.toBe(list);
    expect(deps.setShowLogViewer).toHaveBeenCalledTimes(1);
    expect(deps.setShowLogViewer).toHaveBeenCalledWith(expect.any(Function));
  });

  it("target guards route keys correctly", () => {
    installFixture();
    const directoryInput = document.getElementById(
      "directory-combobox",
    ) as HTMLInputElement;
    const button = document.createElement("button");
    document.body.appendChild(button);
    deps = makeDeps();
    renderHook(() => useGlobalShortcuts(deps));

    // Enter in an input is the scan trigger.
    fireEvent.keyDown(directoryInput, { key: "Enter" });
    expect(deps.onScan).toHaveBeenCalledTimes(1);

    // Enter on a control that handles activation itself must not leak.
    fireEvent.keyDown(button, { key: "Enter" });
    expect(deps.onScan).toHaveBeenCalledTimes(1);
    expect(deps.onExecute).not.toHaveBeenCalled();

    // Enter on body executes the selected file.
    fireEvent.keyDown(document.body, { key: "Enter" });
    expect(deps.onExecute).toHaveBeenCalledTimes(1);
    expect(deps.onScan).toHaveBeenCalledTimes(1);
  });

  it("context menu opens at the selected row", () => {
    installFixture({ rowIndex: 1 });
    deps = makeDeps({ visibleFiles: [FILES[0], FILES[1]], selectedIndex: 1 });
    renderHook(() => useGlobalShortcuts(deps));

    // jsdom rects are all zeros → x = 0 + 24, y = 0 + 0 / 2.
    press("ContextMenu");
    expect(deps.onContextMenu).toHaveBeenCalledTimes(1);
    expect(deps.onContextMenu).toHaveBeenCalledWith({ x: 24, y: 0, file: FILES[1] });

    // Shift+F10 variant with a meaningful rect: x = 100 + 24, y = 50 + 28/2.
    const row = document.querySelector<HTMLElement>('[data-row-index="1"]');
    Object.defineProperty(row, "getBoundingClientRect", {
      value: () => ({
        x: 100,
        y: 50,
        left: 100,
        top: 50,
        right: 300,
        bottom: 78,
        width: 200,
        height: 28,
      }),
    });
    press("F10", { shiftKey: true });
    expect(deps.onContextMenu).toHaveBeenCalledTimes(2);
    expect(deps.onContextMenu).toHaveBeenLastCalledWith({ x: 124, y: 64, file: FILES[1] });

    // No row in the DOM → the 24/24 fallbacks.
    document.querySelector('[data-row-index="1"]')?.remove();
    press("ContextMenu");
    expect(deps.onContextMenu).toHaveBeenCalledTimes(3);
    expect(deps.onContextMenu).toHaveBeenLastCalledWith({ x: 24, y: 24, file: FILES[1] });

    // No file at the selection → the branch bails before anything fires.
    cleanup();
    deps = makeDeps({ visibleFiles: [FILES[0]], selectedIndex: 5 });
    renderHook(() => useGlobalShortcuts(deps));
    press("ContextMenu");
    expect(deps.onContextMenu).not.toHaveBeenCalled();
  });

  it("action shortcuts fire their callbacks", () => {
    installFixture();
    deps = makeDeps({ selectedIndex: 2 });
    renderHook(() => useGlobalShortcuts(deps));

    press("F5");
    expect(deps.onScan).toHaveBeenCalledTimes(1);

    press("r", { ctrlKey: true });
    expect(deps.onReloadConfig).toHaveBeenCalledTimes(1);

    press("h", { ctrlKey: true });
    expect(deps.onGoHome).toHaveBeenCalledTimes(1);

    press("p");
    expect(deps.onProperties).toHaveBeenCalledTimes(1);
    expect(deps.onProperties).toHaveBeenCalledWith(FILES[2]);

    press("t", { ctrlKey: true, shiftKey: true });
    expect(deps.onToggleTheme).toHaveBeenCalledTimes(1);

    press("b", { ctrlKey: true });
    expect(deps.setBarcodeMode).toHaveBeenCalledTimes(1);
    expect(deps.setBarcodeMode).toHaveBeenCalledWith(expect.any(Function));

    press("b", { ctrlKey: true, shiftKey: true });
    expect(deps.setShowCameraScanner).toHaveBeenCalledTimes(1);
    expect(deps.setShowCameraScanner).toHaveBeenCalledWith(expect.any(Function));

    press("t", { ctrlKey: true });
    expect(deps.setShowTimerModal).toHaveBeenCalledTimes(1);
    expect(deps.setShowTimerModal).toHaveBeenCalledWith(true);

    press(",", { ctrlKey: true });
    expect(deps.setShowConfigEditor).toHaveBeenCalledTimes(1);
    expect(deps.setShowConfigEditor).toHaveBeenCalledWith(true);

    press("k", { ctrlKey: true });
    expect(deps.setShowLanModal).toHaveBeenCalledTimes(1);
    expect(deps.setShowLanModal).toHaveBeenCalledWith(true);

    // Ctrl+Shift+K stays free (the disambiguation convention of this table).
    press("k", { ctrlKey: true, shiftKey: true });
    expect(deps.setShowLanModal).toHaveBeenCalledTimes(1);

    press("?");
    expect(deps.setShowShortcuts).toHaveBeenCalledTimes(1);
    expect(deps.setShowShortcuts).toHaveBeenCalledWith(expect.any(Function));

    press("/", { ctrlKey: true });
    expect(deps.setShowShortcuts).toHaveBeenCalledTimes(2);
    expect(deps.setShowShortcuts).toHaveBeenLastCalledWith(expect.any(Function));
  });

  it("focus shortcuts target the comboboxes", () => {
    installFixture();
    const directoryInput = document.getElementById(
      "directory-combobox",
    ) as HTMLInputElement;
    const extensionInput = document.getElementById(
      "extension-combobox",
    ) as HTMLInputElement;
    const filterInput = document.getElementById("filter-combobox") as HTMLInputElement;
    deps = makeDeps();
    renderHook(() => useGlobalShortcuts(deps));

    press("d", { ctrlKey: true });
    expect(document.activeElement).toBe(directoryInput);

    press("e", { ctrlKey: true });
    expect(document.activeElement).toBe(extensionInput);

    press("f", { ctrlKey: true });
    expect(document.activeElement).toBe(filterInput);
  });

  it("navigation moves selection via functional computes", () => {
    installFixture();
    deps = makeDeps();
    renderHook(() => useGlobalShortcuts(deps));

    const computeFor = (key: string): (prev: number, count: number) => number => {
      press(key);
      const spy = deps.moveSelection as Mock<
        (compute: (currentIndex: number, visibleCount: number) => number) => void
      >;
      const calls = spy.mock.calls;
      return calls[calls.length - 1][0];
    };

    const down = computeFor("ArrowDown");
    expect(down(0, 10)).toBe(1);
    expect(down(9, 10)).toBe(9); // clamped at the last row

    const up = computeFor("ArrowUp");
    expect(up(0, 10)).toBe(0); // identity at the first row
    expect(up(5, 10)).toBe(4);

    const home = computeFor("Home");
    expect(home(5, 10)).toBe(0);
    expect(home(0, 10)).toBe(0); // identity — no no-op re-render

    const end = computeFor("End");
    expect(end(3, 10)).toBe(9);
    expect(end(9, 10)).toBe(9); // identity — no no-op re-render

    const pageUp = computeFor("PageUp");
    expect(pageUp(25, 100)).toBe(5);

    const pageDown = computeFor("PageDown");
    expect(pageDown(0, 100)).toBe(20);
    expect(pageDown(95, 100)).toBe(99); // clamped at the last row
  });

  it("captures callbacks at subscription time (staleness profile preserved)", () => {
    installFixture();
    // v1 is the closure alive when the effect subscribes.
    const v1 = vi.fn();
    const v2 = vi.fn();
    const v3 = vi.fn();
    deps = makeDeps({ onReloadConfig: v1 });
    const { rerender } = renderHook(() => useGlobalShortcuts(deps));

    // App re-rendered with fresh callback identities but UNCHANGED state
    // deps (same FILES reference, same primitives) → no re-subscription.
    deps = makeDeps({ onReloadConfig: v2 });
    rerender();

    press("r", { ctrlKey: true });
    expect(v1).toHaveBeenCalledTimes(1); // the subscription-time closure
    expect(v2).not.toHaveBeenCalled();

    // A dep-changing state update (filterText) re-subscribes: the new
    // handler captures v3.
    deps = makeDeps({ onReloadConfig: v3, filterText: "abc" });
    rerender();

    press("r", { ctrlKey: true });
    expect(v3).toHaveBeenCalledTimes(1);
    expect(v1).toHaveBeenCalledTimes(1); // v1 never gained a second call
    expect(v2).not.toHaveBeenCalled();
  });

  it("unmount removes the listener", () => {
    installFixture();
    deps = makeDeps();
    const { unmount } = renderHook(() => useGlobalShortcuts(deps));
    unmount();

    press("r", { ctrlKey: true });
    press("F5");
    press("Enter");
    press("Escape");

    expect(deps.onReloadConfig).not.toHaveBeenCalled();
    expect(deps.onScan).not.toHaveBeenCalled();
    expect(deps.onExecute).not.toHaveBeenCalled();
    expect(deps.onEscape).not.toHaveBeenCalled();
  });
});
