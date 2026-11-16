// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/**
 * Characterization safety net for the App scan flow (issue #148, PR 1):
 * these tests pin the CURRENT scan behavior of `App.tsx` — the init scan
 * derived from the loaded config, a 200-with-warning surfaced as an error
 * toast, and the "Scan failed:" error prefix — so the scan-controller
 * extraction in later tasks can be verified behavior-preserving. They must
 * stay green throughout the refactor; a red result means the test misread
 * current behavior, not that `App.tsx` changed.
 *
 * The whole `App` tree is rendered against a fully mocked API client —
 * heavier than a component test, but it pins the actual user-facing wiring
 * (init → scan → results, Scan button → toast) instead of a prop-level
 * approximation. Pattern: App.configEditor.test.tsx.
 */
import App from "./App";
import {
  executeScan,
  fetchConfig,
  fetchNotifications,
  fetchScanResults,
  fetchSystemInfo,
  selectDirectory,
} from "./api/client";
import type { AppConfigData, ScannedFileItem, SystemInfo } from "./api/types";

vi.mock("./api/client", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchSystemInfo: vi.fn(),
  fetchConfig: vi.fn(),
  fetchScanResults: vi.fn(),
  fetchNotifications: vi.fn(),
  executeScan: vi.fn(),
  selectDirectory: vi.fn(),
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
const selectDirectorySpy = vi.mocked(selectDirectory);

// jsdom gaps (same treatment as App.configEditor.test.tsx):
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
    recursive_search: false,
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

beforeEach(() => {
  vi.clearAllMocks();
  systemInfoSpy.mockResolvedValue(makeSystemInfo());
  fetchConfigSpy.mockResolvedValue(makeAppConfig());
  notificationsSpy.mockResolvedValue({ events: [] });
  executeScanSpy.mockResolvedValue({ count: 0, directory: "C:/data" });
  scanResultsSpy.mockResolvedValue({ count: 0, in_progress: false, items: [] });
  selectDirectorySpy.mockResolvedValue(makeAppConfig());
});

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
  window.localStorage.clear();
});

describe("App scan flow (characterization)", () => {
  it("initial load scans with config-derived params and renders results", async () => {
    fetchConfigSpy.mockResolvedValue(makeAppConfig({ filters: ["all"] }));
    scanResultsSpy.mockResolvedValue({
      count: 2,
      in_progress: false,
      items: [makeFile("a.txt"), makeFile("b.txt")],
    });

    render(<App />);
    await screen.findByText("a.txt");

    // The init scan used the config-derived values (first merged extension,
    // first filter, server-resolved active directory), not the raw defaults.
    expect(executeScanSpy).toHaveBeenCalledTimes(1);
    expect(executeScanSpy.mock.calls[0][0]).toEqual({
      directory: "C:/data",
      extension: ".mttl",
      filter_text: "all",
      recursive: false,
    });
  });

  it("scan 200-with-warning surfaces the warning as an error toast", async () => {
    const user = userEvent.setup();
    render(<App />);

    // Init settled: the config-derived scan already ran once.
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(1));

    // A 200 response may carry a machine-readable `warning` (issue #130).
    executeScanSpy.mockResolvedValue({
      count: 0,
      directory: "C:/data",
      warning: "Directory does not exist",
    });
    await user.click(screen.getByRole("button", { name: "Scan" }));

    // The warning is surfaced as a toast (rendered in ActionBar with
    // role="status"), NOT silently swallowed as a bare empty list.
    expect((await screen.findByRole("status")).textContent).toContain("Directory does not exist");
  });

  it("scan failure shows the site's error prefix", async () => {
    const user = userEvent.setup();
    render(<App />);

    // Init settled: the config-derived scan already ran once.
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(1));

    executeScanSpy.mockRejectedValueOnce(new Error("boom"));
    await user.click(screen.getByRole("button", { name: "Scan" }));

    expect((await screen.findByRole("status")).textContent).toContain("Scan failed: boom");
  });
});
