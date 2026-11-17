// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/**
 * Characterization safety net for the App scan flow (issue #148, PR 1):
 * these tests pin the CURRENT scan behavior of `App.tsx` — the init scan
 * derived from the loaded config, a 200-with-warning surfaced as an error
 * toast, the "Scan failed:" error prefix, the deferred auto-rescan after
 * filter typing (and how an explicit scan cancels it), the directory-change
 * preference merge with its empty-site fallback, the sort-triggered page-1
 * reload, the silent no-op scan without an active directory, and the
 * config-handoff notification poll driving a full config re-apply + rescan
 * (pinned before the PR 3 global-shortcuts rewire touches `App.tsx`) — so
 * the scan-controller extraction in later tasks can be verified
 * behavior-preserving. They must stay green throughout the refactor; a red
 * result means the test misread current behavior, not that `App.tsx` changed.
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
  // Scenario "typing schedules a deferred rescan" runs under fake timers;
  // restore real ones so the other scenarios are unaffected.
  if (vi.isFakeTimers()) vi.useRealTimers();
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

  it("typing schedules a deferred rescan; an explicit scan inside the window wins", async () => {
    // Fake timers drive the 800ms deferred-rescan window. `shouldAdvanceTime`
    // keeps RTL's waitFor polling alive under vitest fake timers (testing
    // library only auto-detects the `jest` global, which vitest lacks).
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<App />);

    // Init settled: the config-derived scan already ran once.
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(1));
    executeScanSpy.mockClear();
    scanResultsSpy.mockClear();

    // Each keystroke (re)schedules the 800ms deferred auto-rescan; only the
    // last one fires — with the full typed filter.
    await user.type(screen.getByLabelText("File filter"), "ab");
    act(() => vi.advanceTimersByTime(800));
    await waitFor(() => expect(scanResultsSpy).toHaveBeenCalledTimes(1));
    expect(executeScanSpy).toHaveBeenCalledTimes(1);
    expect(executeScanSpy.mock.calls[0][0]).toEqual({
      directory: "C:/data",
      extension: ".mttl",
      filter_text: "ab",
      recursive: false,
    });

    // Fresh render: typing "a" schedules the deferred rescan, but pressing
    // Enter inside the window runs the explicit scan, whose beginScan()
    // cancels the pending one — the explicit scan wins, the deferred timer
    // adds nothing.
    cleanup();
    executeScanSpy.mockClear();
    scanResultsSpy.mockClear();
    render(<App />);
    // The clears above wipe phase-1 residue, so this gate genuinely waits
    // for the fresh init scan; the second wait covers its page-1 load, and
    // the clears below give the explicit-scan window a clean slate.
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(scanResultsSpy).toHaveBeenCalledTimes(1));
    executeScanSpy.mockClear();
    scanResultsSpy.mockClear();

    await user.type(screen.getByLabelText("File filter"), "a");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(scanResultsSpy).toHaveBeenCalledTimes(1));
    act(() => vi.advanceTimersByTime(800));
    // Exactly one call — the explicit Enter scan; the deferred timer added none.
    expect(executeScanSpy).toHaveBeenCalledTimes(1);
    expect(executeScanSpy.mock.calls[0][0]).toEqual({
      directory: "C:/data",
      extension: ".mttl",
      filter_text: "a",
      recursive: false,
    });
  });

  it("directory change merges preferences with the changed-site empty fallback", async () => {
    const user = userEvent.setup();
    fetchConfigSpy.mockResolvedValue(makeAppConfig({ filters: ["all"] }));
    render(<App />);

    // Init settled: the config-derived scan already ran once.
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(1));
    executeScanSpy.mockClear();
    scanResultsSpy.mockClear();

    // The new site lists ".mttl" → current extension kept; its filters don't
    // contain "all" → current filter replaced by the site's first one.
    selectDirectorySpy.mockResolvedValueOnce(
      makeAppConfig({ active_directory: "C:/other", extensions: [".py", ".mttl"], filters: ["prod"] }),
    );
    const directoryInput = screen.getByLabelText("Directory");
    await user.clear(directoryInput);
    await user.type(directoryInput, "C:/other{Enter}");
    await waitFor(() => expect(scanResultsSpy).toHaveBeenCalledTimes(1));
    expect(executeScanSpy).toHaveBeenCalledTimes(1);
    expect(executeScanSpy.mock.lastCall?.[0]).toEqual({
      directory: "C:/other",
      extension: ".mttl",
      filter_text: "prod",
      recursive: false,
    });

    // The changed site's empty extension/filter lists fall back to "" —
    // NOT keep-current (an empty site resets both search criteria).
    selectDirectorySpy.mockResolvedValueOnce(
      makeAppConfig({ active_directory: "C:/empty", extensions: [], filters: [] }),
    );
    await user.clear(screen.getByLabelText("Directory"));
    await user.type(screen.getByLabelText("Directory"), "C:/empty{Enter}");
    await waitFor(() => expect(scanResultsSpy).toHaveBeenCalledTimes(2));
    expect(executeScanSpy).toHaveBeenCalledTimes(2);
    expect(executeScanSpy.mock.lastCall?.[0]).toEqual({
      directory: "C:/empty",
      extension: "",
      filter_text: "",
      recursive: false,
    });
  });

  it("sort change reloads page 1 with sort params", async () => {
    const user = userEvent.setup();
    fetchConfigSpy.mockResolvedValue(
      makeAppConfig({ column_names: ["filename"], column_headers: ["Name"] }),
    );
    scanResultsSpy.mockResolvedValue({
      count: 2,
      in_progress: false,
      items: [makeFile("a.txt"), makeFile("b.txt")],
    });
    render(<App />);

    // Init settled: the config-derived scan already ran once.
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(1));
    executeScanSpy.mockClear();
    scanResultsSpy.mockClear();

    // Click the "Name" columnheader. Its computed accessible name also
    // carries the inline resize handle's aria-label ("Name Resize Name
    // column"), so the match is anchored at the start instead of exact.
    await user.click(screen.getByRole("columnheader", { name: /^Name/ }));
    await waitFor(() => expect(scanResultsSpy).toHaveBeenCalledTimes(1));

    // A sort reloads the first page from the server cache — it never
    // re-runs the scan itself.
    expect(executeScanSpy).not.toHaveBeenCalled();
    expect(scanResultsSpy.mock.calls[0][0]).toMatchObject({
      offset: 0,
      sort_by: "filename",
      sort_dir: "asc",
    });
  });

  it("no active directory: scan is a silent no-op", async () => {
    const user = userEvent.setup();
    fetchConfigSpy.mockResolvedValue(makeAppConfig({ active_directory: "", directories: [] }));
    render(<App />);

    // Init settled: without an active directory no config-derived scan ran.
    await waitFor(() => expect(fetchConfigSpy).toHaveBeenCalledTimes(1));
    expect(executeScanSpy).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Scan" }));

    // The scan is refused silently — no request, no error toast.
    expect(executeScanSpy).not.toHaveBeenCalled();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("config_applied notification re-applies config and rescans", async () => {
    // Fake timers drive the 4s notification poll (same treatment as the
    // deferred-rescan scenario above; `shouldAdvanceTime` keeps RTL's
    // waitFor polling alive under vitest fake timers). No pointer/keyboard
    // interaction happens here, so no userEvent advanceTimers wiring is set.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<App />);

    // Init settled: the config-derived scan already ran once, and the init
    // itself only polls from t=4000 — the mocks below are in place first.
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(1));

    // The next poll tick delivers a config-handoff event (issue #4), and
    // the config it must re-fetch now describes the second launch's machine.
    notificationsSpy.mockResolvedValue({
      events: [
        {
          id: 1,
          kind: "config_handoff",
          message: "Config applied by second launch.",
          config_applied: true,
        },
      ],
    });
    fetchConfigSpy.mockResolvedValueOnce(
      makeAppConfig({ filters: ["handoff"], extensions: [".yaml"], active_directory: "C:/handoff" }),
    );

    // One poll tick — which also passes the 3.5s auto-dismiss of the init
    // "Loaded config: …" info toast, so the status toast visible after this
    // tick is the event's message, not init residue.
    act(() => vi.advanceTimersByTime(4000));

    // Poll → event consumed → config re-fetched (init + apply) →
    // handleConfigLoaded re-applied it → fresh scan with the NEW config's
    // derived params.
    await waitFor(() => expect(fetchConfigSpy).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(2));

    // The first tick polls from event id 0 — nothing seen before it.
    expect(notificationsSpy).toHaveBeenCalledWith(0);
    expect(executeScanSpy.mock.lastCall?.[0]).toEqual({
      directory: "C:/handoff",
      extension: ".yaml",
      filter_text: "handoff",
      recursive: false,
    });

    // The event's message toasts via the action bar's status role.
    expect((await screen.findByRole("status")).textContent).toContain(
      "Config applied by second launch.",
    );
  });
});
