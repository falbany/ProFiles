// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { cleanup, renderHook } from "@testing-library/react";

/**
 * Unit tests for the command catalog (`useAppCommands`, issue #224) — the
 * single description of every user action, consumed by the key dispatcher,
 * the shortcuts modal and the palette.
 *
 * They carry the shortcut pins of the original inline handler (each key →
 * its callback with the exact arguments; the navigation computes with their
 * clamp/identity semantics; the context-menu anchor math), and add the
 * guarantees the registry exists for: unique ids, a displayable binding for
 * every keyed command, no key combination claimed twice, and a disabled
 * command that always says why.
 */
import { appendFilterTerm, useAppCommands } from "./useAppCommands";
import type { AppCommandsDeps } from "./useAppCommands";
import { findCommand, formatKeys } from "../utils/commands";
import type { Command, ShortcutEvent, ShortcutSpec } from "../utils/commands";
import type { ScannedFileItem } from "../api/types";

function makeFile(name: string, relPath: string = name): ScannedFileItem {
  return { column_values: {}, filename: name, rel_path: relPath, path: `/data/${relPath}` };
}

const FILES: ScannedFileItem[] = Array.from({ length: 10 }, (_, i) => makeFile(`file-${i}.txt`));

function makeDeps(overrides: Partial<AppCommandsDeps> = {}): AppCommandsDeps {
  return {
    visibleFiles: FILES,
    selectedIndex: 0,
    activeDirectory: "/data",
    filterText: "",
    recursive: true,
    canExport: true,
    moveSelection: vi.fn(),
    onContextMenu: vi.fn(),
    onScan: vi.fn(),
    onExecute: vi.fn(),
    onProperties: vi.fn(),
    onReloadConfig: vi.fn(),
    onGoHome: vi.fn(),
    onToggleTheme: vi.fn(),
    onBrowseDirectory: vi.fn(),
    onGoToParentDirectory: vi.fn(),
    onOpenActiveDirectory: vi.fn(),
    onOpenDirectoryInTerminal: vi.fn(),
    onClearFilter: vi.fn(),
    onAppendFilterTerm: vi.fn(),
    onDisableRecursive: vi.fn(),
    onLoadConfig: vi.fn(),
    onExport: vi.fn(),
    onReveal: vi.fn(),
    onOpenFolder: vi.fn(),
    onOpenTerminal: vi.fn(),
    onScanDirectory: vi.fn(),
    onFilterFolder: vi.fn(),
    onFilterExtension: vi.fn(),
    onCopyPath: vi.fn(),
    onCopyFilename: vi.fn(),
    onCopyDirectory: vi.fn(),
    onCopyUri: vi.fn(),
    onComputeHash: vi.fn(),
    onVerifyHash: vi.fn(),
    onClearFile: vi.fn(),
    onGenerateBarcode: vi.fn(),
    onRequestLaunchWithArgs: vi.fn(),
    setShowLogViewer: vi.fn(),
    setShowTimerModal: vi.fn(),
    setShowConfigEditor: vi.fn(),
    setShowLanModal: vi.fn(),
    setShowCameraScanner: vi.fn(),
    setShowCommandPalette: vi.fn(),
    setBarcodeMode: vi.fn(),
    ...overrides,
  };
}

function keyEvent(
  key: string,
  mods: { ctrlKey?: boolean; shiftKey?: boolean; altKey?: boolean } = {},
): ShortcutEvent {
  return {
    key,
    ctrlKey: mods.ctrlKey ?? false,
    shiftKey: mods.shiftKey ?? false,
    altKey: mods.altKey ?? false,
  };
}

/** Fixture DOM matching the real surface the focus commands act on. */
function installFixture(rowIndex?: number): HTMLElement {
  const list = document.createElement("div");
  list.setAttribute("data-testid", "file-list");
  list.tabIndex = -1;
  document.body.appendChild(list);
  for (const id of ["directory-combobox", "extension-combobox", "filter-combobox"]) {
    const input = document.createElement("input");
    input.id = id;
    document.body.appendChild(input);
  }
  if (rowIndex !== undefined) {
    const row = document.createElement("div");
    row.setAttribute("data-row-index", String(rowIndex));
    document.body.appendChild(row);
  }
  return list;
}

/** Mount the catalog and return lookup helpers over its current list. */
function mount(overrides: Partial<AppCommandsDeps> = {}) {
  const deps = makeDeps(overrides);
  const { result } = renderHook(() => useAppCommands(deps));
  const commands = result.current;
  const byId = (id: string): Command => {
    const command = commands.find((c) => c.id === id);
    if (!command) throw new Error(`No command with id "${id}"`);
    return command;
  };
  /** Run the command a key press reaches once the target guards have passed. */
  const press = (key: string, mods?: Parameters<typeof keyEvent>[1]): Command | undefined => {
    const command = findCommand(commands, keyEvent(key, mods), (c) => !c.beforeTargetGuard);
    command?.run();
    return command;
  };
  return { deps, commands, byId, press };
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});

describe("useAppCommands — catalog guarantees", () => {
  it("gives every command a unique id, a group and a truthful disabled state", () => {
    const { commands } = mount();
    const ids = commands.map((command) => command.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const command of commands) {
      expect(command.title).not.toBe("");
      expect(command.group).toBeTruthy();
      if (!command.enabled) expect(command.disabledReason).toBeTruthy();
    }
  });

  it("describes a displayable binding for every keyed command", () => {
    const { commands } = mount();
    const keyed = commands.filter((command) => command.keys?.length);
    // The commands the shortcuts table lists — one row per binding.
    expect(keyed.map((command) => command.id)).toEqual([
      "scan.run",
      "file.launch",
      "file.properties",
      "file.contextMenu",
      "list.next",
      "list.previous",
      "list.first",
      "list.last",
      "list.pageUp",
      "list.pageDown",
      "directory.home",
      "view.logViewer",
      "view.theme",
      "view.commandPalette",
      "config.reload",
      "config.editor",
      "tools.barcodeMode",
      "tools.cameraScanner",
      "tools.autoRescan",
      "tools.lan",
      "focus.directory",
      "focus.extension",
      "focus.filter",
      "focus.fileList",
    ]);
    for (const command of keyed) expect(formatKeys(command.keys)).not.toBe("");
  });

  it("never claims one key combination for two commands", () => {
    const { commands } = mount();
    // Two specs overlap when they name the same key and no modifier is
    // required by one and forbidden by the other.
    const overlaps = (a: ShortcutSpec, b: ShortcutSpec): boolean => {
      if (a.key.toLowerCase() !== b.key.toLowerCase()) return false;
      return (["ctrl", "shift", "alt"] as const).every(
        (modifier) => a[modifier] === undefined || b[modifier] === undefined || a[modifier] === b[modifier],
      );
    };
    const clashes: string[] = [];
    for (const [i, a] of commands.entries()) {
      for (const b of commands.slice(i + 1)) {
        if (a.keys?.some((x) => b.keys?.some((y) => overlaps(x, y)))) {
          clashes.push(`${a.id} ↔ ${b.id}`);
        }
      }
    }
    expect(clashes).toEqual([]);
  });

  it("runs only the file-list focus shortcut before the target guards", () => {
    const { commands } = mount();
    expect(commands.filter((c) => c.beforeTargetGuard).map((c) => c.id)).toEqual(["focus.fileList"]);
    expect(commands.filter((c) => c.fromInputEnter).map((c) => c.id)).toEqual(["scan.run"]);
  });
});

describe("useAppCommands — action shortcuts", () => {
  it("binds each key to its callback with the original arguments", () => {
    installFixture();
    const { deps, press } = mount({ selectedIndex: 2 });

    press("F5");
    expect(deps.onScan).toHaveBeenCalledTimes(1);

    press("r", { ctrlKey: true });
    expect(deps.onReloadConfig).toHaveBeenCalledTimes(1);

    press("h", { ctrlKey: true });
    expect(deps.onGoHome).toHaveBeenCalledTimes(1);

    press("p", { ctrlKey: true });
    expect(deps.onProperties).toHaveBeenCalledTimes(1);
    expect(deps.onProperties).toHaveBeenCalledWith(FILES[2]);

    press("t", { ctrlKey: true, shiftKey: true });
    expect(deps.onToggleTheme).toHaveBeenCalledTimes(1);

    press("t", { ctrlKey: true });
    expect(deps.setShowTimerModal).toHaveBeenCalledWith(true);

    press(",", { ctrlKey: true });
    expect(deps.setShowConfigEditor).toHaveBeenCalledWith(true);

    press("p", { ctrlKey: true, shiftKey: true });
    expect(deps.setShowCommandPalette).toHaveBeenCalledWith(true);

    // The bare printable "p" claims nothing (issue #247): it used to open
    // Properties while the user typed — e.g. in the config editor's
    // CodeMirror — so only the Ctrl-qualified combo binds the command.
    expect(press("p")).toBeUndefined();
    expect(deps.onProperties).toHaveBeenCalledTimes(1);
  });

  it("qualifies the printable-char bindings with Ctrl (issue #247)", () => {
    const { byId } = mount();
    expect(byId("file.properties").keys).toEqual([
      { key: "p", ctrl: true, shift: false, alt: false },
    ]);
    expect(byId("view.commandPalette").keys).toContainEqual({ key: "?", ctrl: true });
  });

  it("toggles the surfaces that toggle", () => {
    installFixture();
    const { deps, press } = mount();
    const toggled = (setter: AppCommandsDeps["setShowLogViewer"]) => {
      // The deps bag carries plain `vi.fn()`s; read the updater they got.
      const spy = setter as unknown as Mock<(updater: (prev: boolean) => boolean) => void>;
      const updater = spy.mock.calls.at(-1)?.[0];
      if (!updater) throw new Error("setter was not called");
      return [updater(true), updater(false)];
    };

    press("b", { ctrlKey: true });
    expect(toggled(deps.setBarcodeMode)).toEqual([false, true]);

    press("b", { ctrlKey: true, shiftKey: true });
    expect(toggled(deps.setShowCameraScanner)).toEqual([false, true]);

    press("l", { ctrlKey: true, shiftKey: true });
    expect(toggled(deps.setShowLogViewer)).toEqual([false, true]);
  });

  it("opens the palette from every one of its bindings — Ctrl+?, Ctrl+/ and Ctrl+Shift+P", () => {
    installFixture();
    const { deps, press } = mount();

    press("?", { ctrlKey: true });
    press("/", { ctrlKey: true });
    press("p", { ctrlKey: true, shiftKey: true });

    expect(deps.setShowCommandPalette).toHaveBeenCalledTimes(3);
    for (const call of (deps.setShowCommandPalette as Mock).mock.calls) {
      expect(call[0]).toBe(true); // open, never toggle closed
    }

    // The bare printable "?" claims nothing (issue #247): typing it — in a
    // sentence, or in the config editor — must not open the palette.
    press("?");
    expect(deps.setShowCommandPalette).toHaveBeenCalledTimes(3);
  });

  it("keeps Ctrl+Shift+K free — Shift disambiguates K, L, T and B", () => {
    installFixture();
    const { deps, press } = mount();

    press("k", { ctrlKey: true });
    expect(deps.setShowLanModal).toHaveBeenCalledTimes(1);
    expect(press("k", { ctrlKey: true, shiftKey: true })).toBeUndefined();
    expect(deps.setShowLanModal).toHaveBeenCalledTimes(1);

    expect(press("l", { ctrlKey: true, shiftKey: true })?.id).toBe("view.logViewer");
    expect(press("t", { ctrlKey: true, shiftKey: true })?.id).toBe("view.theme");
    expect(press("b", { ctrlKey: true, shiftKey: true })?.id).toBe("tools.cameraScanner");
  });

  it("targets the comboboxes with the focus shortcuts", () => {
    installFixture();
    const { press } = mount();

    press("d", { ctrlKey: true });
    expect(document.activeElement).toBe(document.getElementById("directory-combobox"));

    press("e", { ctrlKey: true });
    expect(document.activeElement).toBe(document.getElementById("extension-combobox"));

    press("f", { ctrlKey: true });
    expect(document.activeElement).toBe(document.getElementById("filter-combobox"));
  });

  it("focuses the file list with Ctrl+L", () => {
    const list = installFixture();
    const { byId } = mount();
    byId("focus.fileList").run();
    expect(document.activeElement).toBe(list);
  });
});

describe("useAppCommands — list navigation", () => {
  it("moves the selection through the functional computes, clamped as before", () => {
    installFixture();
    const { deps, press } = mount();
    const computeFor = (key: string): ((prev: number, count: number) => number) => {
      press(key);
      const spy = deps.moveSelection as Mock<
        (compute: (prev: number, count: number) => number) => void
      >;
      const compute = spy.mock.calls.at(-1)?.[0];
      if (!compute) throw new Error(`"${key}" did not move the selection`);
      return compute;
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
    expect(end(9, 10)).toBe(9); // identity

    const pageUp = computeFor("PageUp");
    expect(pageUp(25, 100)).toBe(5);

    const pageDown = computeFor("PageDown");
    expect(pageDown(0, 100)).toBe(20);
    expect(pageDown(95, 100)).toBe(99); // clamped
  });
});

describe("useAppCommands — context menu", () => {
  it("anchors the menu at the selected row", () => {
    installFixture(1);
    const { deps, press } = mount({ visibleFiles: [FILES[0], FILES[1]], selectedIndex: 1 });

    // jsdom rects are all zeros → x = 0 + 24, y = 0 + 0 / 2.
    press("ContextMenu");
    expect(deps.onContextMenu).toHaveBeenCalledWith({ x: 24, y: 0, file: FILES[1] });

    // Shift+F10 variant with a meaningful rect: x = 100 + 24, y = 50 + 28/2.
    const row = document.querySelector<HTMLElement>('[data-row-index="1"]');
    if (row) {
      Object.defineProperty(row, "getBoundingClientRect", {
        value: () => ({ left: 100, top: 50, width: 200, height: 28 }) as DOMRect,
      });
    }
    press("F10", { shiftKey: true });
    expect(deps.onContextMenu).toHaveBeenLastCalledWith({ x: 124, y: 64, file: FILES[1] });

    // Row scrolled out of the virtual window → the 24/24 fallback.
    row?.remove();
    press("ContextMenu");
    expect(deps.onContextMenu).toHaveBeenLastCalledWith({ x: 24, y: 24, file: FILES[1] });
  });

  it("is not reachable without a selected file", () => {
    installFixture();
    const { deps, byId, press } = mount({ visibleFiles: [FILES[0]], selectedIndex: 5 });

    expect(press("ContextMenu")).toBeUndefined();
    expect(deps.onContextMenu).not.toHaveBeenCalled();
    expect(byId("file.properties").enabled).toBe(false);
    expect(byId("file.properties").disabledReason).toBe("Select a file first");
  });
});

describe("useAppCommands — selected-file commands", () => {
  const nested = makeFile("a.log", "logs/run/a.log");

  it("passes the selected file and the original action arguments", () => {
    const { deps, byId } = mount({ visibleFiles: [nested], selectedIndex: 0 });

    byId("file.launchWithArgs").run();
    expect(deps.onRequestLaunchWithArgs).toHaveBeenCalledWith(nested);

    byId("file.copyPath").run();
    expect(deps.onCopyPath).toHaveBeenLastCalledWith(nested, false);

    byId("file.copyPathForwardSlashes").run();
    expect(deps.onCopyPath).toHaveBeenLastCalledWith(nested, true);

    byId("file.copyFilenameWithoutExtension").run();
    expect(deps.onCopyFilename).toHaveBeenLastCalledWith(nested, true);

    byId("file.copyDirectory").run();
    expect(deps.onCopyDirectory).toHaveBeenLastCalledWith(nested);

    byId("file.hashSha256").run();
    expect(deps.onComputeHash).toHaveBeenLastCalledWith(nested, "sha256");

    byId("file.verifyMd5").run();
    expect(deps.onVerifyHash).toHaveBeenLastCalledWith(nested, "md5");

    byId("file.filterFolder").run();
    expect(deps.onFilterFolder).toHaveBeenLastCalledWith("logs/run");

    byId("file.filterExtension").run();
    expect(deps.onFilterExtension).toHaveBeenLastCalledWith(".log");

    byId("file.scanDirectory").run();
    expect(deps.onScanDirectory).toHaveBeenLastCalledWith("/data/logs/run");

    byId("file.delete").run();
    expect(deps.onClearFile).toHaveBeenLastCalledWith(nested);

    byId("file.qrCode").run();
    expect(deps.onGenerateBarcode).toHaveBeenLastCalledWith(nested);
  });

  it("disables the two filter actions when they have nothing to filter on", () => {
    const { byId } = mount({ visibleFiles: [makeFile("README", "README")], selectedIndex: 0 });

    expect(byId("file.filterFolder").enabled).toBe(false);
    expect(byId("file.filterFolder").disabledReason).toBe("The file is at the root of the scan");
    expect(byId("file.filterExtension").enabled).toBe(false);
    expect(byId("file.filterExtension").disabledReason).toBe("The file has no extension");
  });

  it("lists every selected-file command as disabled, and inert, without a selection", () => {
    const { deps, commands } = mount({ visibleFiles: [] });

    const selection = commands.filter((command) => command.group === "selection");
    expect(selection.length).toBeGreaterThan(15);
    for (const command of selection) {
      expect(command.enabled).toBe(false);
      expect(command.disabledReason).toBe("Select a file first");
      command.run();
    }
    expect(deps.onReveal).not.toHaveBeenCalled();
    expect(deps.onClearFile).not.toHaveBeenCalled();
    expect(deps.onCopyPath).not.toHaveBeenCalled();
    expect(deps.onFilterFolder).not.toHaveBeenCalled();
  });
});

describe("useAppCommands — commands gated by view state", () => {
  it("follows the filter, recursion, directory and export state", () => {
    const off = mount({
      filterText: "   ",
      recursive: false,
      activeDirectory: "",
      canExport: false,
    });
    expect(off.byId("filter.clear").enabled).toBe(false);
    expect(off.byId("scan.disableRecursive").enabled).toBe(false);
    expect(off.byId("directory.parent").enabled).toBe(false);
    expect(off.byId("directory.open").enabled).toBe(false);
    expect(off.byId("directory.terminal").enabled).toBe(false);
    expect(off.byId("tools.exportCsv").enabled).toBe(false);
    expect(off.byId("tools.exportCsv").disabledReason).toBe("Nothing to export");

    const on = mount({
      filterText: "report",
      recursive: true,
      activeDirectory: "/data",
      canExport: true,
    });
    for (const id of [
      "filter.clear",
      "scan.disableRecursive",
      "directory.parent",
      "directory.open",
      "directory.terminal",
      "tools.exportCsv",
    ]) {
      expect(on.byId(id).enabled).toBe(true);
      expect(on.byId(id).disabledReason).toBeUndefined();
    }
  });

  it("keeps Rescan and Launch enabled even with nothing loaded", () => {
    // F5 and Enter must stay claimed so the browser never acts on them; the
    // handlers themselves no-op without a directory or a selection.
    const { deps, byId } = mount({ visibleFiles: [], activeDirectory: "" });

    expect(byId("scan.run").enabled).toBe(true);
    byId("scan.run").run();
    expect(deps.onScan).toHaveBeenCalledTimes(1);

    expect(byId("file.launch").enabled).toBe(true);
    byId("file.launch").run();
    expect(deps.onExecute).toHaveBeenCalledTimes(1);
  });
});

describe("useAppCommands — appendFilterTerm (pure)", () => {
  it("composes the preset term into the current filter as an implicit AND", () => {
    expect(appendFilterTerm("", "modified:today")).toBe("modified:today");
    expect(appendFilterTerm("datalog", "modified:today")).toBe("datalog modified:today");
    expect(appendFilterTerm("  datalog  ", "size:>100mb")).toBe("datalog size:>100mb");
  });

  it("treats the term as present only when it is a whole token (idempotent)", () => {
    // Already present as a whole token → no-op.
    expect(appendFilterTerm("datalog modified:today", "modified:today")).toBe(
      "datalog modified:today",
    );
    // Glued into a larger token → NOT present, still appended.
    expect(appendFilterTerm("sizemodified:today", "modified:today")).toBe(
      "sizemodified:today modified:today",
    );
    // Partial token at the end → NOT present either.
    expect(appendFilterTerm("modified:todayextra", "modified:today")).toBe(
      "modified:todayextra modified:today",
    );
  });
});

describe("useAppCommands — filter preset commands", () => {
  const PRESETS = [
    { id: "filter.largeFiles", title: "Show only files larger than 100 MB", term: "size:>100mb" },
    { id: "filter.modifiedToday", title: "Show only files modified today", term: "modified:today" },
    {
      id: "filter.modifiedLastWeek",
      title: "Show only files from the last 7 days",
      term: "modified:<7d",
    },
  ] as const;

  it("lists the three operator presets in the file-list group, always enabled", () => {
    const { byId } = mount();

    for (const { id, title } of PRESETS) {
      const command = byId(id);
      expect(command.title).toBe(title);
      expect(command.group).toBe("file-list");
      expect(command.enabled).toBe(true);
      expect(command.keywords?.length).toBeGreaterThan(0);
      expect(command.disabledReason).toBeUndefined();
    }
  });

  it("appends each preset's exact term to the current filter and refocuses the field", () => {
    installFixture();
    const { deps, byId } = mount({ filterText: "datalog" });

    for (const { id, term } of PRESETS) {
      byId(id).run();
      expect(deps.onAppendFilterTerm).toHaveBeenLastCalledWith(term);
    }
    expect(deps.onAppendFilterTerm).toHaveBeenCalledTimes(3);
    expect(document.activeElement).toBe(document.getElementById("filter-combobox"));
  });

  // Issue #227 follow-up: the created / small-size / old-modified presets,
  // shipped on the same live grammar (created mirrors modified on birthtime,
  // >duration reads as older, size < is strict).
  const MORE_PRESETS = [
    {
      id: "filter.createdToday",
      title: "Show only files created today",
      term: "created:today",
    },
    {
      id: "filter.createdLastWeek",
      title: "Show only files created within the last 7 days",
      term: "created:<7d",
    },
    {
      id: "filter.smallFiles",
      title: "Show only files smaller than 1 MB",
      term: "size:<1mb",
    },
    {
      id: "filter.modifiedOld",
      title: "Show only files modified more than 30 days ago",
      term: "modified:>30d",
    },
  ] as const;

  for (const { id, title, term } of MORE_PRESETS) {
    it(`lists ${id} and runs it to the exact term ${term}`, () => {
      installFixture();
      const { deps, byId } = mount();

      const command = byId(id);
      expect(command.title).toBe(title);
      expect(command.group).toBe("file-list");
      expect(command.enabled).toBe(true);

      command.run();
      expect(deps.onAppendFilterTerm).toHaveBeenCalledTimes(1);
      expect(deps.onAppendFilterTerm).toHaveBeenCalledWith(term);
      expect(document.activeElement).toBe(document.getElementById("filter-combobox"));
    });
  }
});
