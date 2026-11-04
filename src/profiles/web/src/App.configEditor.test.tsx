// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditorView } from "codemirror";

/**
 * App-level integration seam for the YAML config editor (issue #95): the
 * StatusBar "Config" button must open the in-app ConfigEditorModal (the
 * OS-launch shortcut moved into the modal header), and Apply must drive the
 * same app-state refresh path a config swap uses (`handleConfigLoaded`,
 * shared with LoadConfigModal and the drag/drop trial).
 *
 * The whole `App` tree is rendered against a fully mocked API client —
 * heavier than a component test, but it pins the actual user-facing wiring
 * (button → modal → refresh) instead of a prop-level approximation.
 */
import App from "./App";
import {
  executeScan,
  fetchConfig,
  fetchConfigContent,
  fetchNotifications,
  fetchScanResults,
  fetchSystemInfo,
  loadConfigContent,
  openConfigFile,
} from "./api/client";
import type { AppConfigData, ConfigContentData, ScanResultsResponse, SystemInfo } from "./api/types";

vi.mock("./api/client", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchSystemInfo: vi.fn(),
  fetchConfig: vi.fn(),
  fetchScanResults: vi.fn(),
  fetchNotifications: vi.fn(),
  executeScan: vi.fn(),
  fetchConfigContent: vi.fn(),
  loadConfigContent: vi.fn(),
  openConfigFile: vi.fn(),
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
const fetchContentSpy = vi.mocked(fetchConfigContent);
const loadContentSpy = vi.mocked(loadConfigContent);
const openInOSSpy = vi.mocked(openConfigFile);

// jsdom gaps (same treatment as ConfigEditorModal.test.tsx):
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

const STARTUP_YAML = 'release: "1.0"\nsearch_dir: "C:/data"\n';
/** Text sitting in the editor when the user hits Apply (startup doc + edit). */
const EDITED_YAML = `# applied by the editor\n${STARTUP_YAML}`;

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

function makeContent(overrides: Partial<ConfigContentData> = {}): ConfigContentData {
  return {
    filename: "machine.profiles",
    content: STARTUP_YAML,
    config_path: "C:/configs/machine.profiles",
    session_trial: false,
    ...overrides,
  };
}

function emptyScanResults(): ScanResultsResponse {
  return { count: 0, in_progress: false, items: [] };
}

beforeEach(() => {
  vi.clearAllMocks();
  notificationsSpy.mockResolvedValue({ events: [] });
  executeScanSpy.mockResolvedValue({ count: 0, directory: "C:/data" });
  scanResultsSpy.mockResolvedValue(emptyScanResults());
  systemInfoSpy.mockResolvedValue(makeSystemInfo());
  fetchConfigSpy.mockResolvedValue(makeAppConfig());
  fetchContentSpy.mockResolvedValue(makeContent());
  // Clean default so a stray OS-launch keeps the output quiet; the tests
  // below assert it is NOT called.
  openInOSSpy.mockResolvedValue({ status: "SUCCESS", message: "Opened" });
  // POST /api/config/load-content applies content as a session trial:
  // not anchored to disk, and carrying the freshly derived values the
  // app must pick up (new directory/extension/recursive).
  loadContentSpy.mockResolvedValue(
    makeAppConfig({
      release: "9.9",
      search_dir: "E:/applied",
      active_directory: "E:/applied",
      directories: ["E:/applied"],
      extensions: [".yaml"],
      recursive_search: true,
      session_trial: true,
    }),
  );
});

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
  window.localStorage.clear();
});

describe("App config editor integration", () => {
  it("test_status_bar_config_button_opens_editor_and_apply_refreshes_app", async () => {
    const user = userEvent.setup();
    render(<App />);

    // Startup: the initial config drove exactly one scan with its own values.
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(1));
    expect(executeScanSpy.mock.calls[0][0]).toEqual({
      directory: "C:/data",
      extension: ".mttl",
      filter_text: "",
      recursive: false,
    });

    // The StatusBar "Config" button opens the in-app editor — it must NOT
    // hand the file to the OS anymore (that shortcut lives in the modal
    // header now).
    await user.click(screen.getByRole("button", { name: /^config$/i }));
    const editor = await screen.findByRole("dialog", { name: /configuration editor/i });
    expect(openInOSSpy).not.toHaveBeenCalled();
    // The editor loaded the active file's content into the real CodeMirror
    // view; then the user edits it like any keystroke would.
    await waitFor(() => expect(fetchContentSpy).toHaveBeenCalledTimes(1));
    await waitFor(() => {
      expect(editor.querySelector(".cm-editor")).toBeTruthy();
    });
    const view = EditorView.findFromDOM(editor.querySelector(".cm-editor") as HTMLElement);
    expect(view).not.toBeNull();
    await act(async () => {
      view!.dispatch({ changes: { from: 0, insert: "# applied by the editor\n" } });
    });

    // Apply trials the edited text server-side and refreshes the app state
    // through the shared config-swap path: a fresh scan runs with the
    // APPLIED config's values (not the stale startup ones).
    await user.click(within(editor).getByRole("button", { name: /^apply$/i }));
    await waitFor(() =>
      expect(loadContentSpy).toHaveBeenCalledWith("machine.profiles", EDITED_YAML),
    );
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(2));
    expect(executeScanSpy.mock.calls[1][0]).toEqual({
      directory: "E:/applied",
      extension: ".yaml",
      filter_text: "",
      recursive: true,
    });
    await waitFor(() => expect(scanResultsSpy).toHaveBeenCalled());
    expect(openInOSSpy).not.toHaveBeenCalled();
  });

  it("test_ctrl_comma_opens_editor_without_os_launch", async () => {
    const user = userEvent.setup();
    render(<App />);

    // Startup settled: the shortcut handler is active and no modal is open.
    await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(1));

    // Ctrl+, must open the in-app editor — the old OS-launch behavior is
    // gone from the app shell entirely (it lives in the modal header).
    await user.keyboard("{Control>},{/Control}");
    const editor = await screen.findByRole("dialog", { name: /configuration editor/i });
    expect(openInOSSpy).not.toHaveBeenCalled();

    // The editor is fully functional (content fetched, view mounted).
    await waitFor(() => expect(fetchContentSpy).toHaveBeenCalledTimes(1));
    await waitFor(() => {
      expect(editor.querySelector(".cm-editor")).toBeTruthy();
    });
    expect(openInOSSpy).not.toHaveBeenCalled();
  });
});
