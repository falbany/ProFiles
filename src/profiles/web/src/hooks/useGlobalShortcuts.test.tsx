// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, createEvent, fireEvent, renderHook } from "@testing-library/react";

/**
 * Unit tests for the `useGlobalShortcuts` dispatcher (issue #148 PR 3,
 * reshaped onto the command registry by issue #224). The handler owns the
 * ORDER of the guards; which key does what is the registry's business
 * (`useAppCommands.test.tsx`). These tests mount a hand-built command list
 * and pin: Escape-before-modal-guard, the issue-#55 inert-while-modal guard,
 * the before-target-guard phase, the target routing guards (incl. the
 * Enter-in-input rule and its unpreserved default), first-match-wins with
 * enabled gating, the subscription-time capture (the staleness profile of
 * the original inline effect — the double-Ctrl+R quirk's survival proof),
 * and the unmount teardown.
 */
import { useGlobalShortcuts } from "./useGlobalShortcuts";
import type { GlobalShortcutsDeps } from "./useGlobalShortcuts";
import type { Command, ShortcutSpec } from "../utils/commands";
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
    commands: [],
    onEscape: vi.fn(),
    ...overrides,
  };
}

/** A keyed test command whose `run` is a fresh spy (`vi.mocked(c.run)`). */
function keyed(keys: ShortcutSpec[], extra: Partial<Omit<Command, "keys" | "run">> = {}): Command {
  return {
    id: `command-${keys[0].key}`,
    title: "test",
    group: "view",
    keys,
    enabled: true,
    ...extra,
    run: vi.fn(),
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
function installFixture(): HTMLElement {
  const list = document.createElement("div");
  list.setAttribute("data-testid", "file-list");
  list.tabIndex = -1;
  document.body.appendChild(list);

  for (const id of ["directory-combobox", "extension-combobox", "filter-combobox"]) {
    const input = document.createElement("input");
    input.id = id;
    document.body.appendChild(input);
  }
  return list;
}

/** Fire a keydown on window (the hook listens there, target = window). */
function press(
  key: string,
  mods: { ctrlKey?: boolean; shiftKey?: boolean } = {},
): Event {
  const event = createEvent.keyDown(window, {
    key,
    ctrlKey: mods.ctrlKey ?? false,
    shiftKey: mods.shiftKey ?? false,
    cancelable: true,
  });
  fireEvent(window, event);
  return event;
}

describe("useGlobalShortcuts", () => {
  it("escape closes surfaces even when a modal is open", () => {
    installFixture();
    deps = makeDeps({ anyModalOpen: true });
    renderHook(() => useGlobalShortcuts(deps));

    press("Escape");
    expect(deps.onEscape).toHaveBeenCalledTimes(1);

    // A plain key while the modal is up must not reach the commands.
    press("a");
    expect(deps.onEscape).toHaveBeenCalledTimes(1);
  });

  it("shortcuts are inert while a modal is open", () => {
    installFixture();
    const scan = keyed([{ key: "F5" }]);
    const reload = keyed([{ key: "r", ctrl: true }]);
    const launch = keyed([{ key: "Enter" }]);
    const next = keyed([{ key: "ArrowDown" }]);
    const properties = keyed([{ key: "p" }]);
    deps = makeDeps({ anyModalOpen: true, commands: [scan, reload, launch, next, properties] });
    renderHook(() => useGlobalShortcuts(deps));

    press("F5");
    press("r", { ctrlKey: true });
    press("Enter");
    press("ArrowDown");
    press("p");

    for (const command of [scan, reload, launch, next, properties]) {
      expect(command.run).not.toHaveBeenCalled();
    }
  });

  it("runs the first enabled command bound to the key and claims the key", () => {
    installFixture();
    const first = keyed([{ key: "F5" }], { id: "first" });
    const second = keyed([{ key: "F5" }], { id: "second" });
    deps = makeDeps({ commands: [first, second] });
    renderHook(() => useGlobalShortcuts(deps));

    expect(press("F5").defaultPrevented).toBe(true);
    expect(first.run).toHaveBeenCalledTimes(1);
    expect(second.run).not.toHaveBeenCalled();
  });

  it("leaves an unbound key — and a key bound only to disabled commands — to the browser", () => {
    installFixture();
    const disabled = keyed([{ key: "F5" }], { enabled: false, disabledReason: "nope" });
    const other = keyed([{ key: "F5" }], { id: "other", enabled: false });
    deps = makeDeps({ commands: [disabled, other] });
    renderHook(() => useGlobalShortcuts(deps));

    expect(press("F5").defaultPrevented).toBe(false);
    expect(press("F12").defaultPrevented).toBe(false);
    expect(disabled.run).not.toHaveBeenCalled();
    expect(other.run).not.toHaveBeenCalled();
  });

  it("skips a disabled command and runs the next one bound to the same key", () => {
    installFixture();
    const disabled = keyed([{ key: "F5" }], { enabled: false });
    const enabled = keyed([{ key: "F5" }], { id: "enabled" });
    deps = makeDeps({ commands: [disabled, enabled] });
    renderHook(() => useGlobalShortcuts(deps));

    press("F5");
    expect(disabled.run).not.toHaveBeenCalled();
    expect(enabled.run).toHaveBeenCalledTimes(1);
  });

  it("runs a before-target-guard command from inside an input, but no other", () => {
    installFixture();
    const directoryInput = document.getElementById("directory-combobox") as HTMLInputElement;
    const focusList = keyed([{ key: "l", ctrl: true, shift: false }], {
      id: "focus-list",
      beforeTargetGuard: true,
    });
    const focusDirectory = keyed([{ key: "d", ctrl: true }], { id: "focus-directory" });
    deps = makeDeps({ commands: [focusList, focusDirectory] });
    renderHook(() => useGlobalShortcuts(deps));

    // Ctrl+L is the one shortcut that works while the caret is in a field…
    fireEvent.keyDown(directoryInput, { key: "l", ctrlKey: true });
    expect(focusList.run).toHaveBeenCalledTimes(1);

    // …Ctrl+D is stopped by the input guard, as before the registry.
    fireEvent.keyDown(directoryInput, { key: "d", ctrlKey: true });
    expect(focusDirectory.run).not.toHaveBeenCalled();
  });

  it("target guards route keys correctly", () => {
    installFixture();
    const directoryInput = document.getElementById("directory-combobox") as HTMLInputElement;
    const button = document.createElement("button");
    document.body.appendChild(button);
    const scan = keyed([{ key: "F5" }], { id: "scan", fromInputEnter: true });
    const launch = keyed([{ key: "Enter" }], { id: "launch" });
    deps = makeDeps({ commands: [scan, launch] });
    renderHook(() => useGlobalShortcuts(deps));

    // Enter in an input is the scan trigger — and the key is deliberately
    // NOT claimed (the combobox keeps it too, as in the original handler).
    const inInput = createEvent.keyDown(directoryInput, { key: "Enter", cancelable: true });
    fireEvent(directoryInput, inInput);
    expect(scan.run).toHaveBeenCalledTimes(1);
    expect(inInput.defaultPrevented).toBe(false);

    // Enter on a control that handles activation itself must not leak.
    fireEvent.keyDown(button, { key: "Enter" });
    expect(scan.run).toHaveBeenCalledTimes(1);
    expect(launch.run).not.toHaveBeenCalled();

    // Enter on body executes the selected file.
    expect(press("Enter").defaultPrevented).toBe(true);
    expect(launch.run).toHaveBeenCalledTimes(1);
    expect(scan.run).toHaveBeenCalledTimes(1);
  });

  it("Enter inside an input runs only the command flagged for it", () => {
    installFixture();
    const filterInput = document.getElementById("filter-combobox") as HTMLInputElement;
    const launch = keyed([{ key: "Enter" }], { id: "launch" });
    const scan = keyed([{ key: "F5" }], { id: "scan", fromInputEnter: true, enabled: false });
    deps = makeDeps({ commands: [launch, scan] });
    renderHook(() => useGlobalShortcuts(deps));

    fireEvent.keyDown(filterInput, { key: "Enter" });
    expect(launch.run).not.toHaveBeenCalled();
    expect(scan.run).not.toHaveBeenCalled();

    // Any other key typed in the field reaches no command at all.
    fireEvent.keyDown(filterInput, { key: "F5" });
    fireEvent.keyDown(filterInput, { key: "p" });
    expect(launch.run).not.toHaveBeenCalled();
    expect(scan.run).not.toHaveBeenCalled();
  });

  it("captures commands at subscription time (staleness profile preserved)", () => {
    installFixture();
    // v1 is the closure alive when the effect subscribes.
    const v1 = vi.fn();
    const v2 = vi.fn();
    const v3 = vi.fn();
    const reload =
      (run: () => void): Command =>
      ({ ...keyed([{ key: "r", ctrl: true }]), run });
    deps = makeDeps({ commands: [reload(v1)] });
    const { rerender } = renderHook(() => useGlobalShortcuts(deps));

    // App re-rendered with a fresh command list (new closures) but UNCHANGED
    // state deps (same FILES reference, same primitives) → no re-subscription.
    deps = makeDeps({ commands: [reload(v2)] });
    rerender();

    press("r", { ctrlKey: true });
    expect(v1).toHaveBeenCalledTimes(1); // the subscription-time closure
    expect(v2).not.toHaveBeenCalled();

    // A dep-changing state update (filterText) re-subscribes: the new
    // handler captures v3.
    deps = makeDeps({ commands: [reload(v3)], filterText: "abc" });
    rerender();

    press("r", { ctrlKey: true });
    expect(v3).toHaveBeenCalledTimes(1);
    expect(v1).toHaveBeenCalledTimes(1); // v1 never gained a second call
    expect(v2).not.toHaveBeenCalled();
  });

  it("unmount removes the listener", () => {
    installFixture();
    const reload = keyed([{ key: "r", ctrl: true }]);
    const scan = keyed([{ key: "F5" }]);
    const launch = keyed([{ key: "Enter" }]);
    deps = makeDeps({ commands: [reload, scan, launch] });
    const { unmount } = renderHook(() => useGlobalShortcuts(deps));
    unmount();

    press("r", { ctrlKey: true });
    press("F5");
    press("Enter");
    press("Escape");

    expect(reload.run).not.toHaveBeenCalled();
    expect(scan.run).not.toHaveBeenCalled();
    expect(launch.run).not.toHaveBeenCalled();
    expect(deps.onEscape).not.toHaveBeenCalled();
  });
});
