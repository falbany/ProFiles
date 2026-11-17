// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { act, cleanup, fireEvent, render, renderHook } from "@testing-library/react";

/**
 * Unit tests for the `useBarcodeMode` hook (issue #148, PR 4) — the barcode
 * slice moved verbatim from `App.tsx`: the wedge-scanner capture listener,
 * `handleBarcodeToggle`, `applyBarcodeValues`, and `handleCameraDetected`.
 * They pin the toggle's buffer reset, the key=value / plain-filter apply
 * paths with their 50 ms deferred rescans, the preserved quirks
 * (`scan=0`-only and unknown-key barcodes leave the mode ON, the
 * empty-buffer Enter returns BEFORE preventDefault, editable targets are
 * ignored), the mechanism ruling (sync reads captured at subscription time
 * vs. latest-ref reads inside the two 50 ms timeouts — issue #34), the
 * camera path's ordering + single-match prompt, and the unmount teardown.
 *
 * Toast-string erratum vs. the task brief: `applyBarcodeValues`'s summary
 * template `${k}=${v}` stringifies parsed BOOLEANS, so `scan=1` renders as
 * `scan=true` and `scan=0` as `scan=false` (same as the App code these
 * tests characterize; see Task 1's pinned `Barcode applied: filter=.py`).
 */
import { useBarcodeMode } from "./useBarcodeMode";
import type { BarcodeModeDeps } from "./useBarcodeMode";
import { useGlobalShortcuts } from "./useGlobalShortcuts";
import type { GlobalShortcutsDeps } from "./useGlobalShortcuts";
import type { ScanParams, ScanOutcome } from "./useScanController";
import type { ScannedFileItem } from "../api/types";

function makeFile(n: number): ScannedFileItem {
  return {
    column_values: {},
    filename: `file-${n}.txt`,
    rel_path: `file-${n}.txt`,
    path: `/data/file-${n}.txt`,
  };
}

/** The params the default `getScanParams` mock hands out. */
const BASE_PARAMS: ScanParams = {
  directory: "C:/base",
  extension: ".mttl",
  filter_text: "",
  recursive: false,
};

function makeDeps(overrides: Partial<BarcodeModeDeps> = {}): BarcodeModeDeps {
  return {
    showToast: vi.fn(),
    scanWith: vi.fn().mockResolvedValue({ ok: false }),
    getScanParams: vi.fn(() => BASE_PARAMS),
    onApplyValues: vi.fn(),
    onSingleMatch: vi.fn(),
    onCameraClose: vi.fn(),
    setFilterText: vi.fn(),
    ...overrides,
  };
}

/** Mutable deps the renderHook callback reads on every render. */
let deps: BarcodeModeDeps;

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  deps = makeDeps();
});

afterEach(() => {
  vi.useRealTimers();
  cleanup();
  // Remove the fixture DOM the scenarios installed.
  document.body.innerHTML = "";
});

/** Enable barcode mode the way Ctrl+B / the toolbar toggle do. */
function enableMode(result: { current: ReturnType<typeof useBarcodeMode> }): void {
  act(() => {
    result.current.setBarcodeMode(true);
  });
}

/** Wedge-scanner keystroke: printable char on a non-editable target. */
function typeWedge(text: string): void {
  for (const ch of text) fireEvent.keyDown(document.body, { key: ch });
}

/** Keydown on document.body; returns false when the handler called preventDefault. */
function pressKey(
  key: string,
  mods: { ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean; shiftKey?: boolean } = {},
): boolean {
  return fireEvent.keyDown(document.body, { key, ...mods });
}

describe("useBarcodeMode", () => {
  it("toggle toasts and resets the buffer", () => {
    const { result } = renderHook(() => useBarcodeMode(deps));
    expect(result.current.barcodeMode).toBe(false);

    act(() => {
      result.current.handleBarcodeToggle();
    });
    expect(result.current.barcodeMode).toBe(true);
    expect(deps.showToast).toHaveBeenCalledWith("Barcode mode ON — scan a barcode now.");

    // Chars typed while ON accumulate in the wedge buffer.
    typeWedge("ab");

    act(() => {
      result.current.handleBarcodeToggle();
    });
    expect(result.current.barcodeMode).toBe(false);
    expect(deps.showToast).toHaveBeenCalledWith("Barcode mode OFF.");

    // Toggle back ON — the buffer must have been reset by BOTH toggles.
    act(() => {
      result.current.handleBarcodeToggle();
    });
    expect(result.current.barcodeMode).toBe(true);

    // Empty-buffer Enter: no parse toast, no scan — and the quirk that it
    // returns BEFORE e.preventDefault() (fireEvent: not canceled).
    const notCanceled = pressKey("Enter");
    expect(notCanceled).toBe(true);
    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(deps.scanWith).not.toHaveBeenCalled();
    expect(deps.onApplyValues).not.toHaveBeenCalled();
    expect(deps.showToast).not.toHaveBeenCalledWith(expect.stringContaining("Barcode applied"));
    expect(deps.showToast).not.toHaveBeenCalledWith(expect.stringContaining("Barcode filter"));
  });

  it("key=value barcode applies values, disables mode, rescans after 50 ms", () => {
    const { result } = renderHook(() => useBarcodeMode(deps));
    enableMode(result);

    typeWedge("filter=x;scan=1");
    const canceled = pressKey("Enter");
    expect(canceled).toBe(false); // non-empty buffer → preventDefault runs

    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith("Barcode applied: filter=x, scan=true");
    expect(deps.onApplyValues).toHaveBeenCalledWith({ filter: "x", scan: true });
    expect(result.current.barcodeMode).toBe(false);

    // The rescan waits out the 50 ms commit deferral.
    expect(deps.scanWith).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(deps.scanWith).toHaveBeenCalledTimes(1);
    expect(deps.scanWith).toHaveBeenCalledWith(BASE_PARAMS, { errorPrefix: "Scan failed" });
  });

  it("plain-filter barcode sets filter and rescans", () => {
    const { result } = renderHook(() => useBarcodeMode(deps));
    enableMode(result);

    typeWedge("hello");
    pressKey("Enter");

    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith("Barcode filter: hello");
    expect(deps.setFilterText).toHaveBeenCalledWith("hello");
    expect(result.current.barcodeMode).toBe(false);

    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(deps.scanWith).toHaveBeenCalledTimes(1);
    expect(deps.scanWith).toHaveBeenCalledWith(BASE_PARAMS, { errorPrefix: "Scan failed" });
  });

  it("quirk: scan=0-only barcode does not scan and mode stays on", () => {
    const { result } = renderHook(() => useBarcodeMode(deps));
    enableMode(result);

    typeWedge("scan=0");
    pressKey("Enter");

    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith("Barcode applied: scan=false");
    expect(deps.onApplyValues).toHaveBeenCalledWith({ scan: false });

    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(deps.scanWith).not.toHaveBeenCalled();
    expect(result.current.barcodeMode).toBe(true);
  });

  it("quirk: unknown-key barcode applies nothing and mode stays on", () => {
    const { result } = renderHook(() => useBarcodeMode(deps));
    enableMode(result);

    typeWedge("foo=bar");
    pressKey("Enter");

    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith("Barcode applied: ");
    expect(deps.onApplyValues).toHaveBeenCalledWith({});

    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(deps.scanWith).not.toHaveBeenCalled();
    expect(result.current.barcodeMode).toBe(true);
  });

  it("escape cancels barcode mode", () => {
    const { result } = renderHook(() => useBarcodeMode(deps));
    enableMode(result);
    typeWedge("abc");

    pressKey("Escape");

    expect(result.current.barcodeMode).toBe(false);
    expect(deps.showToast).toHaveBeenCalledWith("Barcode mode cancelled.");
    expect(deps.scanWith).not.toHaveBeenCalled();
  });

  it("editable targets are ignored (issue #58)", () => {
    const input = document.createElement("input");
    document.body.appendChild(input);
    const { result } = renderHook(() => useBarcodeMode(deps));
    enableMode(result);

    // Wedge keystrokes landing in a focused input belong to that input —
    // neither its chars nor its Enter may feed the wedge buffer.
    for (const ch of "filter=x") fireEvent.keyDown(input, { key: ch });
    fireEvent.keyDown(input, { key: "Enter" });

    // Enter on body then hits an EMPTY buffer → no-op.
    pressKey("Enter");
    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(deps.onApplyValues).not.toHaveBeenCalled();
    expect(deps.setFilterText).not.toHaveBeenCalled();
    expect(deps.showToast).not.toHaveBeenCalledWith(expect.stringContaining("Barcode applied"));
    expect(deps.scanWith).not.toHaveBeenCalled();
  });

  it("modifier combos are not accumulated", () => {
    const { result } = renderHook(() => useBarcodeMode(deps));
    enableMode(result);

    pressKey("r", { ctrlKey: true });
    pressKey("Enter");

    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(deps.scanWith).not.toHaveBeenCalled();
    expect(deps.onApplyValues).not.toHaveBeenCalled();
    expect(result.current.barcodeMode).toBe(true);
  });

  it("50 ms timeout reads the LATEST getScanParams (issue #34)", () => {
    const paramsA: ScanParams = { directory: "C:/a", extension: ".mttl", filter_text: "", recursive: false };
    deps = makeDeps({ getScanParams: vi.fn(() => paramsA) });
    const { result, rerender } = renderHook(() => useBarcodeMode(deps));
    enableMode(result);

    // App re-rendered with fresh deps (new getScanParams → C:/b) while the
    // mode dep is unchanged → NO re-subscription: the listener keeps its
    // subscription-time closures, only the timeout's latest-ref sees C:/b.
    const paramsB: ScanParams = { directory: "C:/b", extension: ".mttl", filter_text: "z", recursive: false };
    deps = makeDeps({ getScanParams: vi.fn(() => paramsB) });
    rerender();

    typeWedge("scan=1");
    pressKey("Enter");
    act(() => {
      vi.advanceTimersByTime(50);
    });

    expect(deps.scanWith).toHaveBeenCalledTimes(1);
    expect(deps.scanWith).toHaveBeenCalledWith(paramsB, { errorPrefix: "Scan failed" });
    expect(deps.scanWith).not.toHaveBeenCalledWith(paramsA, { errorPrefix: "Scan failed" });
  });

  it("camera detection applies, scans with Scan error prefix, prompts on single match", async () => {
    const file = makeFile(7);
    deps = makeDeps({
      scanWith: vi.fn().mockResolvedValue({
        ok: true,
        firstPage: { items: [file], count: 1 },
      } satisfies ScanOutcome),
    });
    const { result } = renderHook(() => useBarcodeMode(deps));

    await act(async () => {
      await result.current.handleCameraDetected("dir=C:/cam;filter=q");
    });

    // Today's order: close the camera surface FIRST, then the toast.
    expect(deps.onCameraClose).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith("Barcode detected!");
    const closeSpy = deps.onCameraClose as Mock;
    const toastSpy = deps.showToast as Mock;
    expect(closeSpy.mock.invocationCallOrder[0]).toBeLessThan(toastSpy.mock.invocationCallOrder[0]);

    expect(deps.onApplyValues).toHaveBeenCalledWith({ dir: "C:/cam", filter: "q" });
    expect(deps.scanWith).toHaveBeenCalledTimes(1);
    expect(deps.scanWith).toHaveBeenCalledWith(
      { directory: "C:/cam", extension: ".mttl", filter_text: "q", recursive: false },
      { errorPrefix: "Scan error" },
    );
    expect(deps.onSingleMatch).toHaveBeenCalledTimes(1);
    expect(deps.onSingleMatch).toHaveBeenCalledWith(file);
  });

  it("camera multi-match and failed scans do not prompt", async () => {
    deps = makeDeps({
      scanWith: vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          firstPage: { items: [makeFile(1), makeFile(2)], count: 2 },
        } satisfies ScanOutcome)
        .mockResolvedValueOnce({ ok: false } satisfies ScanOutcome),
    });
    const { result } = renderHook(() => useBarcodeMode(deps));

    await act(async () => {
      await result.current.handleCameraDetected("dir=C:/x");
    });
    expect(deps.onSingleMatch).not.toHaveBeenCalled();

    await act(async () => {
      await result.current.handleCameraDetected("dir=C:/y");
    });
    expect(deps.onSingleMatch).not.toHaveBeenCalled();
    expect(deps.scanWith).toHaveBeenCalledTimes(2);
  });

  it("unmount removes the listener", () => {
    const { result, unmount } = renderHook(() => useBarcodeMode(deps));
    enableMode(result);
    unmount();

    // Keystrokes after unmount must not crash nor fire anything.
    expect(() => {
      typeWedge("scan=1");
      pressKey("Enter");
      pressKey("Escape");
    }).not.toThrow();
    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(deps.scanWith).not.toHaveBeenCalled();
    expect(deps.showToast).not.toHaveBeenCalledWith("Barcode mode cancelled.");
  });
});

/**
 * Cross-hook isolation tests (issue #187): App mounts BOTH the wedge
 * capture listener (useBarcodeMode, document, capture phase) and the
 * global-shortcuts listener (useGlobalShortcuts, window, bubble phase).
 * These fixtures mirror that wiring so the tests can see whether
 * wedge-consumed keydowns leak into the shortcuts handler.
 */
describe("wedge/shortcuts isolation (issue #187)", () => {
  let capturedBarcode: ReturnType<typeof useBarcodeMode> | null = null;

  function CrosstalkHarness({ b, s }: { b: BarcodeModeDeps; s: GlobalShortcutsDeps }) {
    capturedBarcode = useBarcodeMode(b);
    useGlobalShortcuts(s);
    return null;
  }

  function makeShortcutsDeps(overrides: Partial<GlobalShortcutsDeps> = {}): GlobalShortcutsDeps {
    return {
      anyModalOpen: false,
      visibleFiles: [makeFile(1)],
      selectedIndex: 0,
      activeDirectory: "C:/base",
      activeExtension: ".mttl",
      filterText: "",
      recursive: false,
      barcodeMode: true,
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
      setBarcodeMode: vi.fn(),
      setShowCameraScanner: vi.fn(),
      moveSelection: vi.fn(),
      ...overrides,
    };
  }

  it("wedge-consumed keys do not reach the global shortcuts listener", () => {
    const properties = vi.fn();
    const execute = vi.fn();
    const shortcuts = makeShortcutsDeps({ onProperties: properties, onExecute: execute });
    render(<CrosstalkHarness b={deps} s={shortcuts} />);
    act(() => {
      capturedBarcode!.setBarcodeMode(true);
    });

    // The reported case 1: blind-typed "p" (e.g. in "filter=.pdf") with a
    // selected file must not open the Properties modal — the wedge buffer
    // just accumulates the char.
    fireEvent.keyDown(document.body, { key: "p" });
    expect(properties).not.toHaveBeenCalled();

    // The reported case 2: the terminating Enter applies the plain filter
    // but must not ALSO execute the selected file.
    pressKey("Enter");
    expect(execute).not.toHaveBeenCalled();

    // The wedge path itself still consumed both keys.
    expect(deps.setFilterText).toHaveBeenCalledWith("p");
    expect(deps.showToast).toHaveBeenCalledWith("Barcode filter: p");
  });

  it("typed '?' does not open the shortcuts modal either", () => {
    const setShowShortcuts = vi.fn();
    const shortcuts = makeShortcutsDeps({ setShowShortcuts });
    render(<CrosstalkHarness b={deps} s={shortcuts} />);
    act(() => {
      capturedBarcode!.setBarcodeMode(true);
    });

    pressKey("?", { shiftKey: true });
    expect(setShowShortcuts).not.toHaveBeenCalled();
  });

  it("escape still reaches the global shortcuts on purpose (modal-close preserved)", () => {
    const onEscape = vi.fn();
    const shortcuts = makeShortcutsDeps({ onEscape });
    render(<CrosstalkHarness b={deps} s={shortcuts} />);
    act(() => {
      capturedBarcode!.setBarcodeMode(true);
    });

    pressKey("Escape");
    // Both consumers fire, as today: the wedge mode cancels AND the
    // shortcuts close any open surfaces.
    expect(deps.showToast).toHaveBeenCalledWith("Barcode mode cancelled.");
    expect(onEscape).toHaveBeenCalledTimes(1);
  });
});
