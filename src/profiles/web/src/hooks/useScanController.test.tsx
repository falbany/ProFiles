// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";

/**
 * Unit tests for the `useScanController` hook (issue #148, PR 1) — the scan
 * state machine extracted verbatim from `App.tsx`. They pin the generation
 * protocol (superseded generations execute but paint nothing, stay silent,
 * and leave the spinner to the newer generation), the empty-directory guard
 * (no side effects), the 200-with-warning toast, the error-prefix text
 * (including non-`Error` rejections), the sort-triggered page-1 reload,
 * load-more paging with path dedup, the deferred auto-rescan reading the
 * latest params through the latest-ref, and the unmount teardown (pending
 * timer cleared, in-flight fetch aborted).
 */
import { useScanController } from "./useScanController";
import type { ScanControllerDeps, ScanParams } from "./useScanController";
import { executeScan, fetchScanResults } from "../api/client";
import { SCAN_PAGE_SIZE } from "../components/FileListTable";
import type { ScannedFileItem } from "../api/types";

vi.mock("../api/client", () => ({
  executeScan: vi.fn(),
  fetchScanResults: vi.fn(),
}));

const executeScanSpy = vi.mocked(executeScan);
const scanResultsSpy = vi.mocked(fetchScanResults);

function makeFile(name: string, path?: string): ScannedFileItem {
  return {
    column_values: {},
    filename: name,
    rel_path: name,
    path: path ?? `C:/data/${name}`,
  } as ScannedFileItem;
}

/** Mutable scan params: the deps' `getScanParams` returns THIS object. */
function makeParams(): ScanParams {
  return { directory: "C:/data", extension: "", filter_text: "", max_depth: 10 };
}

function makeDeps(params: ScanParams): ScanControllerDeps {
  return {
    showToast: vi.fn(),
    getScanParams: () => params,
    onFreshResults: vi.fn(),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  executeScanSpy.mockResolvedValue({ count: 0, directory: "C:/data" });
  scanResultsSpy.mockResolvedValue({ count: 0, in_progress: false, items: [] });
});

afterEach(() => {
  cleanup();
  // The deferred-rescan scenarios run under fake timers; restore real ones
  // so the other scenarios are unaffected.
  if (vi.isFakeTimers()) vi.useRealTimers();
});

describe("useScanController", () => {
  it("scanWith empty-directory guard", async () => {
    const params = makeParams();
    const deps = makeDeps(params);
    const { result } = renderHook(() => useScanController(deps));
    const outcome = await act(() => result.current.scanWith({ ...params, directory: "" }));
    expect(outcome).toEqual({ ok: false });
    expect(executeScanSpy).not.toHaveBeenCalled();
    expect(scanResultsSpy).not.toHaveBeenCalled();
    expect(deps.showToast).not.toHaveBeenCalled();
    expect(deps.onFreshResults).not.toHaveBeenCalled();
    expect(result.current.scanning).toBe(false);
  });

  it("scanWith happy path", async () => {
    const f1 = makeFile("a.txt");
    const params = makeParams();
    const deps = makeDeps(params);
    scanResultsSpy.mockResolvedValue({ count: 1, in_progress: false, items: [f1] });
    const { result } = renderHook(() => useScanController(deps));

    let outcome: Awaited<ReturnType<typeof result.current.scanWith>> | undefined;
    await act(async () => {
      outcome = await result.current.scanWith(params);
    });

    expect(outcome).toEqual({ ok: true, firstPage: { items: [f1], count: 1 } });
    expect(result.current.files).toEqual([f1]);
    expect(result.current.totalCount).toBe(1);
    expect(result.current.hasScanned).toBe(true);
    expect(result.current.scanning).toBe(false);
    expect(deps.onFreshResults).toHaveBeenCalledTimes(1);
    expect(deps.showToast).not.toHaveBeenCalled();
  });

  it("scanWith surfaces 200-with-warning as error toast", async () => {
    const params = makeParams();
    const deps = makeDeps(params);
    executeScanSpy.mockResolvedValue({ count: 0, directory: "C:/data", warning: "dir gone" });
    const { result } = renderHook(() => useScanController(deps));

    let outcome: Awaited<ReturnType<typeof result.current.scanWith>> | undefined;
    await act(async () => {
      outcome = await result.current.scanWith(params);
    });

    expect(deps.showToast).toHaveBeenCalledWith("dir gone", "error");
    // The warning must not masquerade as a failure — the scan completes.
    expect(outcome).toEqual({ ok: true, firstPage: { items: [], count: 0 } });
    expect(result.current.hasScanned).toBe(true);
  });

  it("scanWith error prefix", async () => {
    // Error rejection → default "Scan failed" prefix.
    const deps1 = makeDeps(makeParams());
    executeScanSpy.mockRejectedValueOnce(new Error("boom"));
    const { result: r1 } = renderHook(() => useScanController(deps1));
    let outcome1: Awaited<ReturnType<typeof r1.current.scanWith>> | undefined;
    await act(async () => {
      outcome1 = await r1.current.scanWith(makeParams());
    });
    expect(deps1.showToast).toHaveBeenCalledWith("Scan failed: boom", "error");
    expect(outcome1).toEqual({ ok: false });
    expect(r1.current.scanning).toBe(false);

    // Custom prefix (directory-change flow).
    const deps2 = makeDeps(makeParams());
    executeScanSpy.mockRejectedValueOnce(new Error("boom"));
    const { result: r2 } = renderHook(() => useScanController(deps2));
    await act(async () => {
      await r2.current.scanWith(makeParams(), { errorPrefix: "Directory change failed" });
    });
    expect(deps2.showToast).toHaveBeenCalledWith("Directory change failed: boom", "error");

    // Non-Error rejection (thrown string) — never "Scan failed: undefined".
    const deps3 = makeDeps(makeParams());
    executeScanSpy.mockRejectedValueOnce("boom");
    const { result: r3 } = renderHook(() => useScanController(deps3));
    await act(async () => {
      await r3.current.scanWith(makeParams());
    });
    expect(deps3.showToast).toHaveBeenCalledWith("Scan failed: boom", "error");
  });

  it("superseded generation stays silent", async () => {
    const params = makeParams();
    const deps = makeDeps(params);
    const { result } = renderHook(() => useScanController(deps));

    let g1 = 0;
    act(() => {
      g1 = result.current.beginScan();
      result.current.beginScan();
    });
    expect(result.current.scanning).toBe(true);

    // Capture the signal the execute call receives via the mock's call args.
    let capturedSignal: AbortSignal | undefined;
    executeScanSpy.mockImplementation(async (_params, signal) => {
      capturedSignal = signal;
      return { count: 0, directory: "C:/data" };
    });

    let outcome: Awaited<ReturnType<typeof result.current.scanWithGeneration>> | undefined;
    await act(async () => {
      outcome = await result.current.scanWithGeneration(g1, params);
    });

    // The stale generation's fetch still fires, but paints nothing, says
    // nothing, and leaves the spinner to the newer generation.
    expect(executeScanSpy).toHaveBeenCalledTimes(1);
    expect(capturedSignal).toBeDefined();
    expect(outcome).toEqual({ ok: false });
    expect(result.current.files).toEqual([]);
    expect(result.current.hasScanned).toBe(false);
    expect(deps.onFreshResults).not.toHaveBeenCalled();
    expect(deps.showToast).not.toHaveBeenCalled();
    expect(result.current.scanning).toBe(true);
  });

  it("applySort reloads with sort params", async () => {
    const f1 = makeFile("a.txt");
    const deps = makeDeps(makeParams());
    scanResultsSpy.mockResolvedValue({ count: 1, in_progress: false, items: [f1] });
    const { result } = renderHook(() => useScanController(deps));

    await act(async () => {
      result.current.applySort({ column: "filename", direction: "asc" });
    });

    // A sort reloads the first page from the server cache — it never
    // re-runs the scan itself.
    expect(executeScanSpy).not.toHaveBeenCalled();
    expect(scanResultsSpy.mock.calls[0][0]).toMatchObject({
      offset: 0,
      limit: SCAN_PAGE_SIZE,
      sort_by: "filename",
      sort_dir: "asc",
    });
    expect(result.current.sort).toEqual({ column: "filename", direction: "asc" });
    expect(deps.onFreshResults).toHaveBeenCalledTimes(1);
    expect(result.current.files).toEqual([f1]);
    expect(result.current.scanning).toBe(false);

    // Rejection surfaces under the "Sort failed" prefix and releases the spinner.
    const deps2 = makeDeps(makeParams());
    scanResultsSpy.mockRejectedValueOnce(new Error("boom"));
    const { result: r2 } = renderHook(() => useScanController(deps2));
    await act(async () => {
      r2.current.applySort({ column: "filename", direction: "asc" });
    });
    expect(deps2.showToast).toHaveBeenCalledWith("Sort failed: boom", "error");
    expect(r2.current.scanning).toBe(false);
  });

  it("handleLoadMore appends with path dedup", async () => {
    const f1 = makeFile("a.txt");
    const f2 = makeFile("b.txt");
    const f1dup = makeFile("a-dup.txt", "C:/data/a.txt"); // same path as f1
    const f3 = makeFile("c.txt");
    const params = makeParams();
    const deps = makeDeps(params);
    scanResultsSpy.mockResolvedValueOnce({ count: 3, in_progress: false, items: [f1, f2] });
    scanResultsSpy.mockResolvedValueOnce({ count: 3, in_progress: false, items: [f1dup, f3] });
    const { result } = renderHook(() => useScanController(deps));

    await act(async () => {
      const outcome = await result.current.scanWith(params);
      expect(outcome.ok).toBe(true);
    });
    expect(result.current.files).toEqual([f1, f2]);

    await act(async () => {
      await result.current.handleLoadMore();
    });

    // f1dup (same path as f1) is dropped — the cache changed mid-request.
    expect(result.current.files).toEqual([f1, f2, f3]);
    expect(result.current.totalCount).toBe(3);
    expect(result.current.loadingMore).toBe(false);
    expect(scanResultsSpy.mock.calls[1][0]).toMatchObject({
      offset: 2,
      limit: SCAN_PAGE_SIZE,
    });

    // Guard: the list is complete (files.length >= totalCount) — no fetch.
    scanResultsSpy.mockClear();
    await act(async () => {
      await result.current.handleLoadMore();
    });
    expect(scanResultsSpy).not.toHaveBeenCalled();

    // Paging failure is non-fatal: toast + spinner released.
    const deps2 = makeDeps(makeParams());
    scanResultsSpy.mockClear();
    scanResultsSpy.mockResolvedValueOnce({
      count: 3,
      in_progress: false,
      items: [makeFile("a.txt")],
    });
    scanResultsSpy.mockRejectedValueOnce(new Error("boom"));
    const { result: r2 } = renderHook(() => useScanController(deps2));
    await act(async () => {
      await r2.current.scanWith(makeParams());
    });
    await act(async () => {
      await r2.current.handleLoadMore();
    });
    expect(deps2.showToast).toHaveBeenCalledWith(
      "Couldn't load more results — scroll to try again.",
      "error",
    );
    expect(r2.current.loadingMore).toBe(false);
  });

  it("scheduleDeferredRescan uses latest params; explicit scan cancels it", async () => {
    vi.useFakeTimers();
    const params = makeParams();
    params.filter_text = "v1";
    const deps = makeDeps(params);
    const { result } = renderHook(() => useScanController(deps));

    // Schedule, THEN mutate the params the deps return — the timer callback
    // must read them at fire time (latest-ref), not capture them stale.
    act(() => {
      result.current.scheduleDeferredRescan();
    });
    params.filter_text = "v2";
    await act(async () => {
      vi.advanceTimersByTime(800);
    });
    expect(executeScanSpy).toHaveBeenCalledTimes(1);
    expect(executeScanSpy.mock.calls[0][0]).toMatchObject({ filter_text: "v2" });

    // Fresh hook: an explicit scan inside the window cancels the pending
    // deferred rescan — exactly one execute call total.
    executeScanSpy.mockClear();
    const deps2 = makeDeps(params);
    const { result: r2 } = renderHook(() => useScanController(deps2));
    act(() => {
      r2.current.scheduleDeferredRescan();
    });
    await act(async () => {
      await r2.current.scanWith(params);
    });
    act(() => {
      vi.advanceTimersByTime(800);
    });
    expect(executeScanSpy).toHaveBeenCalledTimes(1);
  });

  it("unmount cleanup", async () => {
    vi.useFakeTimers();
    executeScanSpy.mockImplementation(
      () => new Promise<{ count: number; directory: string }>(() => {}),
    );
    const params = makeParams();
    const deps = makeDeps(params);
    const { result, unmount } = renderHook(() => useScanController(deps));

    // In-flight scan — capture the signal it executes with from the mock's
    // call args.
    let g = 0;
    act(() => {
      g = result.current.beginScan();
    });
    act(() => {
      void result.current.scanWithGeneration(g, params);
    });
    const signal = executeScanSpy.mock.calls[0]?.[1] as AbortSignal | undefined;
    expect(signal).toBeDefined();

    // Pending deferred rescan scheduled while the scan is in flight.
    act(() => {
      result.current.scheduleDeferredRescan();
    });

    unmount();
    act(() => {
      vi.advanceTimersByTime(800);
    });

    // The pending rescan never fired and the in-flight fetch was aborted.
    expect(executeScanSpy).toHaveBeenCalledTimes(1);
    expect(signal?.aborted).toBe(true);
  });

  it("claimGeneration", async () => {
    const params = makeParams();
    const deps = makeDeps(params);
    const { result } = renderHook(() => useScanController(deps));

    // A completed scan leaves the spinner off; its controller stays current.
    await act(async () => {
      await result.current.scanWith(params);
    });
    const signal = executeScanSpy.mock.calls[0]?.[1] as AbortSignal | undefined;
    expect(signal).toBeDefined();
    expect(result.current.scanning).toBe(false);

    // claimGeneration bumps WITHOUT the spinner and aborts the prior
    // generation's fetch (runInitialLoad's supersede protocol).
    let g = 0;
    act(() => {
      g = result.current.claimGeneration();
    });
    expect(typeof g).toBe("number");
    expect(result.current.isCurrentScan(g)).toBe(true);
    expect(result.current.scanning).toBe(false);
    expect(signal?.aborted).toBe(true);
  });
});
