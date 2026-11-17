// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, renderHook } from "@testing-library/react";

/**
 * Unit tests for the `useDragDropConfig` hook (issue #148, PR 6) — the
 * window-level drag/drop slice extracted verbatim from `App.tsx`. They pin
 * the WIRING, not the reducer math (pinned by `utils/configDrop.test.ts`):
 * overlay visibility across nested enter/leave pairs, accepted-file routing
 * (.profiles accepted; other files toast, no files silent), the synchronous
 * drop-time reset, the latest-deps apply chain (render-scope dropHandlerRef
 * reassignment), `resetDrop`'s hard reset (depth zeroed — the WKWebView
 * Escape seam), and the unmount teardown.
 */
import { useDragDropConfig } from "./useDragDropConfig";
import { loadConfigContent } from "../api/client";
import type { AppConfigData } from "../api/types";

vi.mock("../api/client", () => ({
  loadConfigContent: vi.fn(),
}));

const loadConfigContentSpy = vi.mocked(loadConfigContent);

/** The deps bag shape the hook consumes (App passes it fresh every render). */
type DragDropDeps = Parameters<typeof useDragDropConfig>[0];
type ShowToast = DragDropDeps["showToast"];

/** Minimal `AppConfigData` fixture resolved by the loadConfigContent mock. */
function makeConfig(): AppConfigData {
  return {
    title: "Dropped config",
    release: "test",
    search_dir: "/tmp/project",
    recursive_search: false,
    theme: "auto",
    directories: [],
    extensions: [],
    filters: [],
    active_directory: "",
    config_path: "",
    config_exists: false,
    column_headers: [],
    column_names: [],
    row_colors: [],
  };
}

/** Fresh deps mocks per mount; `rerender()` swaps identities like App does. */
function makeDeps(): DragDropDeps {
  return {
    onConfigLoaded: vi.fn<(cfg: AppConfigData) => Promise<void>>(),
    showToast: vi.fn<ShowToast>(),
  };
}

let deps: DragDropDeps;

beforeEach(() => {
  vi.clearAllMocks();
  loadConfigContentSpy.mockResolvedValue(makeConfig());
  deps = makeDeps();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** Window-level drag helpers carrying a plain (jsdom-safe) dataTransfer. */
function dragEnterWindow(types: string[]) {
  act(() => {
    fireEvent.dragEnter(window, { dataTransfer: { types } });
  });
}

function dragLeaveWindow(types: string[]) {
  act(() => {
    fireEvent.dragLeave(window, { dataTransfer: { types } });
  });
}

/** Drop fires the fire-and-forget apply chain; drain its microtasks. */
async function dropWindow(files: File[], types: string[] = ["Files"]) {
  await act(async () => {
    fireEvent.drop(window, { dataTransfer: { types, files } });
  });
  await act(async () => {});
}

describe("useDragDropConfig", () => {
  it("dragenter with files shows the overlay", () => {
    const { result } = renderHook(() => useDragDropConfig(deps));
    expect(result.current.dropOverlayVisible).toBe(false);
    dragEnterWindow(["Files"]);
    expect(result.current.dropOverlayVisible).toBe(true);
  });

  it("dragenter without files does not show the overlay", () => {
    const { result } = renderHook(() => useDragDropConfig(deps));
    dragEnterWindow(["text/plain"]);
    expect(result.current.dropOverlayVisible).toBe(false);
  });

  it("overlay tracks nested enter/leave pairs and hides only at depth zero", () => {
    const { result } = renderHook(() => useDragDropConfig(deps));
    dragEnterWindow(["Files"]);
    dragEnterWindow(["Files"]);
    expect(result.current.dropOverlayVisible).toBe(true);
    dragLeaveWindow(["Files"]);
    // First leave of a nested pair: the overlay stays up.
    expect(result.current.dropOverlayVisible).toBe(true);
    dragLeaveWindow(["Files"]);
    expect(result.current.dropOverlayVisible).toBe(false);
  });

  it("drop with an accepted file hides the overlay and applies the config", async () => {
    const fixture = makeConfig();
    loadConfigContentSpy.mockResolvedValue(fixture);
    const { result } = renderHook(() => useDragDropConfig(deps));
    dragEnterWindow(["Files"]);
    expect(result.current.dropOverlayVisible).toBe(true);
    await dropWindow([new File(["content"], "machine.profiles")]);
    // The drop resets the overlay synchronously, before the apply chain.
    expect(result.current.dropOverlayVisible).toBe(false);
    expect(loadConfigContentSpy).toHaveBeenCalledTimes(1);
    expect(loadConfigContentSpy).toHaveBeenCalledWith("machine.profiles", "content");
    expect(deps.onConfigLoaded).toHaveBeenCalledTimes(1);
    expect(deps.onConfigLoaded).toHaveBeenCalledWith(fixture);
    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith("Session config applied: machine.profiles");
  });

  it("drop with a non-config file toasts the error and does not apply", async () => {
    const { result } = renderHook(() => useDragDropConfig(deps));
    dragEnterWindow(["Files"]);
    expect(result.current.dropOverlayVisible).toBe(true);
    await dropWindow([new File(["notes"], "notes.txt")]);
    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith("Not a ProFiles configuration file.", "error");
    expect(deps.onConfigLoaded).not.toHaveBeenCalled();
    expect(loadConfigContentSpy).not.toHaveBeenCalled();
    expect(result.current.dropOverlayVisible).toBe(false);
  });

  it("drop with no files is silent", async () => {
    const { result } = renderHook(() => useDragDropConfig(deps));
    dragEnterWindow(["Files"]);
    await dropWindow([]);
    expect(deps.showToast).not.toHaveBeenCalled();
    expect(deps.onConfigLoaded).not.toHaveBeenCalled();
    expect(result.current.dropOverlayVisible).toBe(false);
  });

  it("loadConfigContent failure toasts the server message", async () => {
    loadConfigContentSpy.mockRejectedValueOnce(new Error("Bad YAML"));
    const { result } = renderHook(() => useDragDropConfig(deps));
    dragEnterWindow(["Files"]);
    await dropWindow([new File(["junk"], "machine.profiles")]);
    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith("Bad YAML", "error");
    expect(deps.onConfigLoaded).not.toHaveBeenCalled();
    // The overlay was already hidden by the drop reset, not by the catch.
    expect(result.current.dropOverlayVisible).toBe(false);
  });

  it("loadConfigContent failure without a message toasts the fallback", async () => {
    loadConfigContentSpy.mockRejectedValueOnce("");
    const { result } = renderHook(() => useDragDropConfig(deps));
    dragEnterWindow(["Files"]);
    await dropWindow([new File(["junk"], "machine.profiles")]);
    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith("Failed to apply dropped configuration", "error");
    expect(result.current.dropOverlayVisible).toBe(false);
  });

  it("drop uses the LATEST onConfigLoaded (rerender between mount and drop)", async () => {
    const firstApply = vi.fn<(cfg: AppConfigData) => Promise<void>>();
    const secondApply = vi.fn<(cfg: AppConfigData) => Promise<void>>();
    deps.onConfigLoaded = firstApply;
    const { rerender } = renderHook(() => useDragDropConfig(deps));
    dragEnterWindow(["Files"]);
    // App re-rendered with a fresh deps BAG — a new object identity holding
    // the new closure (its per-render deps literal). Replacing the bag
    // (not mutating it in place) is what pins the render-scope
    // dropHandlerRef reassignment: a mount-time capture of the bag would
    // still read firstApply and fail this test.
    deps = { ...deps, onConfigLoaded: secondApply };
    rerender();
    await dropWindow([new File(["content"], "machine.profiles")]);
    expect(secondApply).toHaveBeenCalledTimes(1);
    expect(firstApply).not.toHaveBeenCalled();
  });

  it("resetDrop hides the overlay and resets the depth tracker", () => {
    const { result } = renderHook(() => useDragDropConfig(deps));
    dragEnterWindow(["Files"]);
    expect(result.current.dropOverlayVisible).toBe(true);
    act(() => {
      result.current.resetDrop();
    });
    expect(result.current.dropOverlayVisible).toBe(false);
    // Depth was zeroed: a fresh enter re-shows from depth 1, and one leave
    // hides again. (A leaky reset — depth still 1 — would make this enter
    // depth 2 and the single leave would leave the overlay visible.)
    dragEnterWindow(["Files"]);
    expect(result.current.dropOverlayVisible).toBe(true);
    dragLeaveWindow(["Files"]);
    expect(result.current.dropOverlayVisible).toBe(false);
  });

  it("applyConfigFile applies a picked file without any drag events", async () => {
    const fixture = makeConfig();
    loadConfigContentSpy.mockResolvedValue(fixture);
    const { result } = renderHook(() => useDragDropConfig(deps));
    // No drag events were fired: the overlay must stay down throughout.
    expect(result.current.dropOverlayVisible).toBe(false);
    await act(async () => {
      result.current.applyConfigFile(new File(["content"], "machine.profiles"));
    });
    await act(async () => {});
    expect(result.current.dropOverlayVisible).toBe(false);
    expect(loadConfigContentSpy).toHaveBeenCalledTimes(1);
    expect(loadConfigContentSpy).toHaveBeenCalledWith("machine.profiles", "content");
    expect(deps.onConfigLoaded).toHaveBeenCalledTimes(1);
    expect(deps.onConfigLoaded).toHaveBeenCalledWith(fixture);
    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith("Session config applied: machine.profiles");
  });

  it("unmount removes the window listeners", async () => {
    const { unmount } = renderHook(() => useDragDropConfig(deps));
    unmount();
    dragEnterWindow(["Files"]);
    await dropWindow([new File(["content"], "machine.profiles")]);
    expect(deps.showToast).not.toHaveBeenCalled();
    expect(deps.onConfigLoaded).not.toHaveBeenCalled();
    expect(loadConfigContentSpy).not.toHaveBeenCalled();
  });
});
