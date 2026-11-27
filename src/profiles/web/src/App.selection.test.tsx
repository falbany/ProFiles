// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/**
 * Selection preservation across scan refreshes (issue #218): the previously
 * selected row is re-anchored by path — never silently reset to row 0 or
 * left pointing at an unrelated file. Three user-facing behaviors are pinned:
 *
 * 1. the selection FOLLOWS its row when a refresh reorders the list (RED
 *    before the fix: `onFreshResults` reset the anchor to row 0);
 * 2. a row that vanished from a fully-loaded set clears the selection to an
 *    inert "nothing selected" (`aria-activedescendant` disappears — a `-1`
 *    id must never be announced);
 * 3. a row that moved beyond the loaded window is restored by one `find_path`
 *    lookup plus ONE window fetch, then re-selected at its new index.
 *
 * The whole `App` tree is rendered against a fully mocked API client —
 * heavier than a component test, but these are App-level orchestration
 * behaviors (reconcile effect + restoreSelection) with no narrower seam.
 * Pattern: App.scanFlow.test.tsx.
 */
import App from "./App";
import {
  executeScan,
  fetchConfig,
  fetchNotifications,
  fetchScanResults,
  fetchSystemInfo,
  findScanResultsPath,
} from "./api/client";
import type { AppConfigData, ScannedFileItem, SystemInfo } from "./api/types";

vi.mock("./api/client", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchSystemInfo: vi.fn(),
  fetchConfig: vi.fn(),
  fetchScanResults: vi.fn(),
  fetchNotifications: vi.fn(),
  executeScan: vi.fn(),
  findScanResultsPath: vi.fn(),
}));

// `__APP_VERSION__` is injected by vite.config's `define` at build time;
// vitest.config carries no define, so HeaderBar's bare reference must be
// backed by a global before the first render.
(globalThis as unknown as Record<string, unknown>).__APP_VERSION__ ??= "0.0.0-test";

const systemInfoSpy = vi.mocked(fetchSystemInfo);
const fetchConfigSpy = vi.mocked(fetchConfig);
const scanResultsSpy = vi.mocked(fetchScanResults);
const notificationsSpy = vi.mocked(fetchNotifications);
const executeScanSpy = vi.mocked(executeScan);
const findPathSpy = vi.mocked(findScanResultsPath);

// jsdom gaps (same treatment as App.scanFlow.test.tsx):
// - CodeMirror's measurement code calls Range geometry APIs jsdom lacks.
const rangeProto = Range.prototype as unknown as {
  getClientRects?: () => DOMRect[];
  getBoundingClientRect?: () => DOMRect;
};
rangeProto.getClientRects ??= () => [];
rangeProto.getBoundingClientRect ??= () => new DOMRect(0, 0, 0, 0);
// - FileListTable's virtualizer observes its scroller with ResizeObserver.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver?: unknown }).ResizeObserver ??= ResizeObserverStub;

function makeSystemInfo(): SystemInfo {
  return {
    hostname: "workstation",
    ip: "192.168.1.10",
    username: "operator",
    os_release: "Windows 11",
    lan_enabled: false,
  };
}

function makeAppConfig(overrides: Partial<AppConfigData> = {}): AppConfigData {
  return {
    title: "machine",
    release: "1.0",
    search_dir: "C:/data",
    max_search_depth: 10,
    theme: "dark",
    directories: ["C:/data"],
    extensions: [".mttl"],
    filters: [],
    active_directory: "C:/data",
    config_path: "C:/configs/machine.profiles",
    config_exists: true,
    column_headers: [],
    column_names: [],
    row_colors: [],
    ...overrides,
  };
}

function makeFile(name: string, path?: string): ScannedFileItem {
  // column_values is part of ScannedFileItem and FileListTable reads it
  // unguarded while rendering cells — the rows crash without it.
  return {
    column_values: {},
    filename: name,
    rel_path: name,
    path: path ?? `C:/data/${name}`,
  } as ScannedFileItem;
}

/** The grid's announced selected row id, or null when nothing is selected. */
function activeDescendant(): string | null {
  return screen.getByTestId("file-list").getAttribute("aria-activedescendant");
}

beforeEach(() => {
  vi.clearAllMocks();
  systemInfoSpy.mockResolvedValue(makeSystemInfo());
  fetchConfigSpy.mockResolvedValue(makeAppConfig());
  notificationsSpy.mockResolvedValue({ events: [] });
  executeScanSpy.mockResolvedValue({ count: 0, directory: "C:/data" });
  scanResultsSpy.mockResolvedValue({ count: 0, in_progress: false, items: [] });
  findPathSpy.mockResolvedValue({ count: 0, offset: -1 });
});

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
  window.localStorage.clear();
});

describe("App selection preservation (#218)", () => {
  it("refresh that reorders the list: the selection follows the moved row", async () => {
    const user = userEvent.setup();
    scanResultsSpy.mockResolvedValue({
      count: 3,
      in_progress: false,
      items: [makeFile("a.txt"), makeFile("b.txt"), makeFile("c.txt")],
    });
    render(<App />);
    await screen.findByText("c.txt");

    // Select row 2 ("c.txt").
    await user.click(screen.getByText("c.txt"));
    expect(activeDescendant()).toBe("file-row-2");

    // A refresh reorders the set — "c.txt" moved from index 2 to index 1.
    // RED before the #218 fix: onFreshResults reset the anchor, so the
    // selection snapped back to row 0 instead of following the path.
    scanResultsSpy.mockResolvedValueOnce({
      count: 3,
      in_progress: false,
      items: [makeFile("a.txt"), makeFile("c.txt"), makeFile("b.txt")],
    });
    await user.click(screen.getByRole("button", { name: "Scan" }));

    await waitFor(() => expect(activeDescendant()).toBe("file-row-1"));
    // The row really moved: no reset to row 0, no clamp onto a neighbour.
    expect(screen.getByText("c.txt").closest("[data-row-index]")?.getAttribute("data-row-index")).toBe("1");
  });

  it("refresh where the selected row is gone (all rows loaded): selection clears", async () => {
    const user = userEvent.setup();
    scanResultsSpy.mockResolvedValue({
      count: 3,
      in_progress: false,
      items: [makeFile("a.txt"), makeFile("b.txt"), makeFile("c.txt")],
    });
    render(<App />);
    await screen.findByText("b.txt");

    await user.click(screen.getByText("b.txt"));
    expect(activeDescendant()).toBe("file-row-1");

    // The refresh drops "b.txt" (count 2, fully loaded) — restoreSelection
    // decides locally (no server lookup needed) and clears: the selection
    // becomes an inert "nothing selected" instead of landing on a neighbour.
    scanResultsSpy.mockResolvedValueOnce({
      count: 2,
      in_progress: false,
      items: [makeFile("a.txt"), makeFile("c.txt")],
    });
    await user.click(screen.getByRole("button", { name: "Scan" }));
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(2));

    await waitFor(() => expect(activeDescendant()).toBeNull());
    // No row announces itself as selected.
    expect(document.querySelectorAll('[aria-selected="true"]')).toHaveLength(0);
  });

  it("selected row moved beyond the loaded window: find_path + ONE fetch restore it", async () => {
    const user = userEvent.setup();
    // Init page: 3 of 3 rows — "c.txt" selected at index 2.
    scanResultsSpy.mockImplementationOnce(() =>
      Promise.resolve({
        count: 3,
        in_progress: false,
        items: [makeFile("a.txt"), makeFile("b.txt"), makeFile("c.txt")],
      }),
    );
    // From the refresh on: page 1 answers offset 0, the restore window
    // answers any other offset.
    scanResultsSpy.mockImplementation((params) => {
      if (params?.offset === 0) {
        return Promise.resolve({
          count: 6,
          in_progress: false,
          items: [makeFile("a.txt"), makeFile("b.txt"), makeFile("d.txt")],
        });
      }
      return Promise.resolve({
        count: 6,
        in_progress: false,
        items: [makeFile("x.txt"), makeFile("c.txt")],
      });
    });
    render(<App />);
    await screen.findByText("c.txt");
    await user.click(screen.getByText("c.txt"));
    expect(activeDescendant()).toBe("file-row-2");

    // The refresh grows the set to 6 rows; the loaded page (a, b, d) no
    // longer contains "c.txt" — the server holds it at offset 4.
    findPathSpy.mockResolvedValue({ count: 6, offset: 4 });
    await user.click(screen.getByRole("button", { name: "Scan" }));

    // The restore asked the server where the row went (with the list's
    // current sort — none here).
    await waitFor(() =>
      expect(findPathSpy).toHaveBeenCalledWith({
        path: "C:/data/c.txt",
        sort_by: undefined,
        sort_dir: undefined,
      }),
    );
    // …then fetched the missing span in ONE request: offsets 3..4 → 2 rows.
    await waitFor(() => {
      const windowCall = scanResultsSpy.mock.calls.find(([p]) => p?.offset === 3);
      expect(windowCall?.[0]).toMatchObject({ offset: 3, limit: 2 });
    });
    // The appended rows re-select the followed path at its new index.
    await waitFor(() => expect(activeDescendant()).toBe("file-row-4"));
    expect(screen.getByText("c.txt").closest("[data-row-index]")?.getAttribute("data-row-index")).toBe("4");
  });

  it("restore bails when the user re-anchors mid-lookup (ownership guard)", async () => {
    const user = userEvent.setup();
    // Init page: 3 of 3 rows — "c.txt" selected at index 2.
    scanResultsSpy.mockImplementationOnce(() =>
      Promise.resolve({
        count: 3,
        in_progress: false,
        items: [makeFile("a.txt"), makeFile("b.txt"), makeFile("c.txt")],
      }),
    );
    // From the refresh on: 6 rows total, loaded page (a, b, d) — "c.txt"
    // left the loaded window, so the reconcile effect hands the path to
    // restoreSelection and the lookup begins.
    scanResultsSpy.mockImplementation((params) => {
      if (params?.offset === 0) {
        return Promise.resolve({
          count: 6,
          in_progress: false,
          items: [makeFile("a.txt"), makeFile("b.txt"), makeFile("d.txt")],
        });
      }
      return Promise.resolve({
        count: 6,
        in_progress: false,
        items: [makeFile("x.txt"), makeFile("c.txt")],
      });
    });
    render(<App />);
    await screen.findByText("c.txt");
    await user.click(screen.getByText("c.txt"));
    expect(activeDescendant()).toBe("file-row-2");

    // Deferred lookup: it resolves only after the user has re-clicked.
    let releaseFind!: (value: { count: number; offset: number }) => void;
    findPathSpy.mockImplementation(
      () =>
        new Promise<{ count: number; offset: number }>((resolve) => {
          releaseFind = resolve;
        }),
    );
    await user.click(screen.getByRole("button", { name: "Scan" }));
    await waitFor(() => expect(findPathSpy).toHaveBeenCalledTimes(1));

    // Mid-lookup the user selects "d.txt" (now at index 2 of the loaded
    // page) — the in-flight restore no longer owns the selection.
    await user.click(screen.getByText("d.txt"));
    expect(activeDescendant()).toBe("file-row-2");

    // The lookup answers "genuinely gone" (offset -1): the pre-fix code
    // unconditionally cleared here, wiping the fresh "d.txt" selection.
    releaseFind({ count: 6, offset: -1 });
    await waitFor(() => expect(findPathSpy).toHaveBeenCalledTimes(1));
    // The user's selection survives the resolution…
    expect(activeDescendant()).toBe("file-row-2");
    expect(screen.getByText("d.txt").closest("[data-row-index]")?.getAttribute("data-row-index")).toBe("2");
    // …and the restore bailed before any window fetch.
    const strayFetch = scanResultsSpy.mock.calls.find(([params]) => params?.offset !== 0);
    expect(strayFetch).toBeUndefined();
  });
});
