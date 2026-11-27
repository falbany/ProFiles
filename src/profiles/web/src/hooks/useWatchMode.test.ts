// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";

/**
 * Unit tests for the watch-mode hook (`useWatchMode`, issue #223) — the
 * SSE-driven rescan toggle on top of the shared status feed. They pin the
 * seq edge-trigger semantics (baseline tick never fires, bump fires once,
 * mid-scan bumps drain exactly ONE trailing scan on the first settled
 * tick), the server-truth reconciliation (server-driven un-toggles are
 * silent without an error, one error toast per distinct message with one),
 * and the client-caused transitions (exactly one enable/disable toast,
 * error toast with the toggle left off when the request fails).
 */
import { useWatchMode } from "./useWatchMode";

// The toggle endpoint is replaced wholesale: tests drive the hook through
// resolved/rejected responses only.
vi.mock("../api/client", () => ({
  setWatchMode: vi.fn(),
}));

import { setWatchMode } from "../api/client";

const setWatchModeMock = vi.mocked(setWatchMode);

/**
 * Minimal EventSource double (same pattern as `useScanStatusFeed.test.ts`):
 * a static registry of constructed instances and manual event delivery of
 * raw JSON payloads, so tests drive ticks with
 * `act(() => instances[0].emit("status", json))`.
 */
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  closed = false;
  handlers = new Map<string, (event: { data?: string }) => void>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, handler: (event: { data?: string }) => void): void {
    this.handlers.set(event, handler);
  }

  /** Deliver an event with its raw JSON payload, as the browser would. */
  emit(event: string, dataJson: string): void {
    this.handlers.get(event)?.({ data: dataJson });
  }

  close(): void {
    this.closed = true;
  }
}

const lastSource = (): MockEventSource => {
  const source = MockEventSource.instances.at(-1);
  if (!source) throw new Error("No MockEventSource was opened");
  return source;
};

/** Deps double: spies for scan/toast and a mutable mid-scan flag. */
function makeDeps() {
  let scanning = false;
  return {
    scan: vi.fn(),
    showToast: vi.fn(),
    isScanning: vi.fn(() => scanning),
    setScanning: (next: boolean) => {
      scanning = next;
    },
  };
}

/** Full snake_case status payload the server streams every second. */
const status = (overrides: Record<string, unknown>): string => {
  const payload = {
    in_progress: false,
    progress: null,
    directory: "/d",
    watching: false,
    watch_interval_s: null,
    watch_seq: null,
    watch_error: null,
    ...overrides,
  };
  return JSON.stringify(payload);
};

beforeEach(() => {
  MockEventSource.instances = [];
  (globalThis as { EventSource?: unknown }).EventSource = MockEventSource;
  setWatchModeMock.mockReset();
});

afterEach(() => {
  cleanup();
  delete (globalThis as { EventSource?: unknown }).EventSource;
});

describe("useWatchMode", () => {
  it("test_first_tick_records_baseline_no_scan", () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useWatchMode(deps));

    // First tick carrying a watch seq: records the baseline, never fires.
    act(() => lastSource().emit("status", status({ watch_seq: 1 })));

    expect(deps.scan).not.toHaveBeenCalled();
    expect(result.current.watching).toBe(false);
  });

  it("test_seq_bump_triggers_single_scan", async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useWatchMode(deps));
    setWatchModeMock.mockResolvedValue({ watching: true, interval_s: 1.5 });

    await act(async () => {
      await result.current.handleWatchSet(true);
    });
    expect(result.current.watching).toBe(true);

    act(() =>
      lastSource().emit(
        "status",
        status({ watching: true, watch_interval_s: 1.5, watch_seq: 2 }),
      ),
    );
    expect(deps.scan).toHaveBeenCalledTimes(1);

    // Same seq again: edge-triggered, no refire.
    act(() =>
      lastSource().emit(
        "status",
        status({ watching: true, watch_interval_s: 1.5, watch_seq: 2 }),
      ),
    );
    expect(deps.scan).toHaveBeenCalledTimes(1);
  });

  it("test_bump_during_scan_defers_one_trailing_scan", async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useWatchMode(deps));
    setWatchModeMock.mockResolvedValue({ watching: true, interval_s: 1 });

    await act(async () => {
      await result.current.handleWatchSet(true);
    });

    // Bump observed while a scan is running (client AND server busy):
    // deferred, no immediate scan.
    deps.setScanning(true);
    act(() =>
      lastSource().emit(
        "status",
        status({ in_progress: true, progress: 5, watching: true, watch_interval_s: 1, watch_seq: 3 }),
      ),
    );
    expect(deps.scan).not.toHaveBeenCalled();

    // First settled tick (server progress done AND client idle) drains
    // exactly ONE trailing scan.
    deps.setScanning(false);
    act(() =>
      lastSource().emit(
        "status",
        status({ watching: true, watch_interval_s: 1, watch_seq: 3 }),
      ),
    );
    expect(deps.scan).toHaveBeenCalledTimes(1);

    // The drained seq is consumed: no refire on the next tick.
    act(() =>
      lastSource().emit(
        "status",
        status({ watching: true, watch_interval_s: 1, watch_seq: 3 }),
      ),
    );
    expect(deps.scan).toHaveBeenCalledTimes(1);
  });

  it("test_server_untoggle_silent_without_error", async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useWatchMode(deps));
    setWatchModeMock.mockResolvedValue({ watching: true, interval_s: 1 });

    await act(async () => {
      await result.current.handleWatchSet(true);
    });
    deps.showToast.mockClear();

    // The server stopped watching on its own; no error recorded: the
    // toggle follows the feed silently.
    act(() => lastSource().emit("status", status({ watch_seq: 1 })));

    expect(result.current.watching).toBe(false);
    expect(deps.showToast).not.toHaveBeenCalled();
    expect(deps.scan).not.toHaveBeenCalled();
  });

  it("test_server_untoggle_toasts_once_on_error", async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useWatchMode(deps));
    setWatchModeMock.mockResolvedValue({ watching: true, interval_s: 1 });

    await act(async () => {
      await result.current.handleWatchSet(true);
    });
    deps.showToast.mockClear();

    // Same error payload twice (the feed repeats the snapshot every
    // second): exactly one error toast for the distinct message.
    const payload = status({
      watch_seq: 1,
      watch_error: "Watch stopped: directory does not exist",
    });
    act(() => lastSource().emit("status", payload));
    act(() => lastSource().emit("status", payload));

    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith(
      "Watch stopped: directory does not exist",
      "error",
    );
    expect(result.current.watching).toBe(false);
  });

  it("test_enable_disable_toast_once", async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useWatchMode(deps));
    setWatchModeMock.mockResolvedValue({ watching: true, interval_s: 1.5 });

    await act(async () => {
      await result.current.handleWatchSet(true);
    });
    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith("Watching for changes.");
    expect(result.current.watching).toBe(true);

    setWatchModeMock.mockResolvedValue({ watching: false, interval_s: null });
    await act(async () => {
      await result.current.handleWatchSet(false);
    });
    expect(deps.showToast).toHaveBeenCalledTimes(2);
    expect(deps.showToast).toHaveBeenLastCalledWith("Watch disabled.");
    expect(result.current.watching).toBe(false);
  });

  it("test_enable_failure_toasts_error", async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useWatchMode(deps));
    setWatchModeMock.mockRejectedValue(new Error("Active directory is not set"));

    await act(async () => {
      await result.current.handleWatchSet(true);
    });

    expect(result.current.watching).toBe(false);
    expect(deps.showToast).toHaveBeenCalledTimes(1);
    expect(deps.showToast).toHaveBeenCalledWith(
      "Watch failed: Active directory is not set",
      "error",
    );
  });
});
