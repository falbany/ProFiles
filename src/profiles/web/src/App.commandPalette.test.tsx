// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/**
 * App-level tests for the command palette wiring (issue #224) — the same
 * full-`App`-against-a-mocked-API pattern as `App.scanFlow.test.tsx`. They
 * pin the user-facing contract: the palette opens from its shortcut and from
 * the status bar, makes the rest of the UI inert while open, acts on the real
 * selection, quick-opens files, remembers what it ran, and reaches the
 * argumented-launch dialog. The catalog itself is covered by
 * `useAppCommands.test.tsx`, the palette surface by `CommandPalette.test.tsx`.
 */
import App from "./App";
import {
  executeScan,
  fetchConfig,
  fetchNotifications,
  fetchScanResults,
  fetchSystemInfo,
  launchFile,
  revealFile,
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
  launchFile: vi.fn(),
  revealFile: vi.fn(),
}));

vi.mock("./components/CameraBarcodeModal", () => ({
  CameraBarcodeModal: ({ isOpen }: { isOpen: boolean }) => (isOpen ? <div>camera</div> : null),
}));

// `__APP_VERSION__` is injected by vite.config's `define` at build time.
(globalThis as unknown as Record<string, unknown>).__APP_VERSION__ ??= "0.0.0-test";

const fetchConfigSpy = vi.mocked(fetchConfig);
const scanResultsSpy = vi.mocked(fetchScanResults);
const executeScanSpy = vi.mocked(executeScan);
const launchFileSpy = vi.mocked(launchFile);
const revealFileSpy = vi.mocked(revealFile);

// jsdom gaps (same treatment as App.scanFlow.test.tsx).
const rangeProto = Range.prototype as unknown as {
  getClientRects?: () => DOMRect[];
  getBoundingClientRect?: () => DOMRect;
};
rangeProto.getClientRects ??= () => [];
rangeProto.getBoundingClientRect ??= () => new DOMRect(0, 0, 0, 0);
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver?: unknown }).ResizeObserver ??= ResizeObserverStub;

function makeAppConfig(overrides: Partial<AppConfigData> = {}): AppConfigData {
  return {
    title: "machine",
    release: "1.0",
    search_dir: "C:/data",
    max_search_depth: 10,
    theme: "dark",
    directories: ["C:/data"],
    extensions: [".txt"],
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

function makeFile(name: string): ScannedFileItem {
  return { column_values: {}, filename: name, rel_path: name, path: `C:/data/${name}` };
}

/** Mount App with *names* listed and wait for the initial load to settle. */
async function launchWith(names: string[]): Promise<void> {
  scanResultsSpy.mockResolvedValue({
    count: names.length,
    in_progress: false,
    items: names.map(makeFile),
  });
  render(<App />);
  if (names.length) {
    await screen.findByText(names[0]);
  }
  await waitFor(() => expect(executeScanSpy).toHaveBeenCalledTimes(1));
}

const palette = () => screen.getByRole("dialog", { name: "Command palette" });
const searchField = () => within(palette()).getByRole("combobox");

async function openPalette(): Promise<void> {
  fireEvent.keyDown(window, { key: "p", ctrlKey: true, shiftKey: true });
  await waitFor(() => expect(palette()).toBeInTheDocument());
  await waitFor(() => expect(searchField()).toHaveFocus());
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchSystemInfo).mockResolvedValue({
    hostname: "workstation",
    ip: "192.168.1.10",
    username: "operator",
    os_release: "Windows 11",
    lan_enabled: false,
  } satisfies SystemInfo);
  fetchConfigSpy.mockResolvedValue(makeAppConfig());
  vi.mocked(fetchNotifications).mockResolvedValue({ events: [] });
  executeScanSpy.mockResolvedValue({ count: 0, directory: "C:/data" });
  scanResultsSpy.mockResolvedValue({ count: 0, in_progress: false, items: [] });
  vi.mocked(selectDirectory).mockResolvedValue(makeAppConfig());
  launchFileSpy.mockResolvedValue({ status: "SUCCESS", message: "Launched" });
  revealFileSpy.mockResolvedValue({ status: "SUCCESS", message: "Revealed" });
});

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
  window.localStorage.clear();
});

describe("App command palette", () => {
  it("opens with Ctrl+Shift+P and from the status bar, and closes with Escape", async () => {
    const user = userEvent.setup();
    await launchWith([]);

    await openPalette();
    expect(screen.getByText("Commands")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Command palette" })).toBeNull());

    await user.click(screen.getByRole("button", { name: /commands/i }));
    expect(palette()).toBeInTheDocument();
  });

  it("keeps the rest of the UI inert while it is open", async () => {
    const user = userEvent.setup();
    await launchWith(["a.txt", "b.txt"]);
    const scansBefore = executeScanSpy.mock.calls.length;

    await openPalette();
    // A query with no result: Enter has nothing to run in the palette. If
    // the global dispatcher were still live, the same keys would open the
    // properties modal (Ctrl+P), the palette (Ctrl+?) and trigger a rescan
    // (Enter inside an input).
    await user.type(searchField(), "zzzz");
    fireEvent.keyDown(searchField(), { key: "?", ctrlKey: true });
    await user.keyboard("{Enter}");

    expect(screen.queryByRole("dialog", { name: "Keyboard Shortcuts" })).toBeNull();
    expect(screen.queryByRole("dialog", { name: /properties/i })).toBeNull();
    expect(executeScanSpy.mock.calls.length).toBe(scansBefore);
    expect(palette()).toBeInTheDocument();
  });

  it("acts on the real selection", async () => {
    const user = userEvent.setup();
    await launchWith(["a.txt", "b.txt"]);
    await user.click(screen.getByText("b.txt"));

    await openPalette();
    await user.type(searchField(), "reveal");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(revealFileSpy).toHaveBeenCalledWith("C:/data/b.txt"));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Command palette" })).toBeNull(),
    );
  });

  it("quick-opens a file by name", async () => {
    const user = userEvent.setup();
    await launchWith(["a.txt", "b.txt"]);

    await openPalette();
    await user.type(searchField(), "b.tx");
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(launchFileSpy).toHaveBeenCalledWith({
        directory: "C:/data",
        filename: "b.txt",
        release: "1.0",
        args: undefined,
      }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("Launched b.txt");
  });

  it("remembers the commands it ran and lists them first next time", async () => {
    const user = userEvent.setup();
    await launchWith([]);
    expect(document.documentElement.dataset.theme).toBe("dark");

    await openPalette();
    await user.type(searchField(), "theme");
    await user.keyboard("{Enter}");

    // The command itself took effect…
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
    // …and was recorded.
    expect(JSON.parse(window.localStorage.getItem("profiles-recent-commands") ?? "[]")).toContain(
      "view.theme",
    );

    await openPalette();
    const recent = within(palette()).getByRole("group", { name: "Recent" });
    expect(recent).toHaveTextContent("Switch theme");
  });

  it("asks for the arguments before an argumented launch", async () => {
    // jsdom does not implement the native <dialog> API. A closed dialog is
    // inaccessible to role queries, so the stub must do the one thing that
    // matters here: mark it open, as showModal() does.
    HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
    };
    const user = userEvent.setup();
    await launchWith(["a.txt"]);
    await user.click(screen.getByText("a.txt"));

    await openPalette();
    await user.type(searchField(), "arguments");
    await user.keyboard("{Enter}");

    const argsField = await screen.findByRole("textbox", { name: "Command line arguments" });
    expect(screen.getByText("Launch with Arguments")).toBeInTheDocument();
    expect(launchFileSpy).not.toHaveBeenCalled();

    await user.type(argsField, "--verbose{Enter}");

    await waitFor(() =>
      expect(launchFileSpy).toHaveBeenCalledWith({
        directory: "C:/data",
        filename: "a.txt",
        release: "1.0",
        args: "--verbose",
      }),
    );
  });

  it("also opens from the Ctrl+? and Ctrl+/ bindings", async () => {
    await launchWith([]);

    // Ctrl-qualified (issue #247): the bare printable "?" fired while the
    // user typed and must not open anything any more.
    fireEvent.keyDown(window, { key: "?", ctrlKey: true });
    expect(await screen.findByRole("dialog", { name: "Command palette" })).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    fireEvent.keyDown(window, { key: "/", ctrlKey: true });
    expect(await screen.findByRole("dialog", { name: "Command palette" })).toBeInTheDocument();
  });
});
