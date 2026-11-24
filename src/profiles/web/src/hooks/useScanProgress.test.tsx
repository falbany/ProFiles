// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";

/**
 * Unit tests for the `useScanProgress` hook (issue #152) — the SSE client
 * for `/api/scan/events`. They pin the EventSource lifecycle (open while a
 * scan this window initiated is active, close on end/unmount), the status
 * payload parsing (`progress` + `in_progress`), the silent degraded mode
 * on stream errors (progress → null, no toasts, auto-reconnect resume),
 * malformed-event tolerance, the no-EventSource guard (jsdom/exotic
 * browsers), and remount safety.
 */
import { useScanProgress } from "./useScanProgress";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  closed = false;
  handlers = new Map<string, (ev: unknown) => void>();
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  addEventListener(name: string, cb: (ev: unknown) => void) {
    this.handlers.set(name, cb);
  }
  close() {
    this.closed = true;
  }
  emitStatus(data: unknown) {
    this.handlers.get("status")?.({ data: JSON.stringify(data) });
  }
  emitError() {
    this.handlers.get("error")?.({});
  }
}

const lastInstance = () => FakeEventSource.instances.at(-1) as FakeEventSource;

beforeEach(() => {
  FakeEventSource.instances = [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any).EventSource = FakeEventSource;
});

afterEach(() => {
  cleanup();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete (window as any).EventSource;
});

describe("useScanProgress", () => {
  it("opens one EventSource while active and closes it when inactive", () => {
    const { result, rerender, unmount } = renderHook(({ active }) => useScanProgress(active), {
      initialProps: { active: true },
    });

    expect(FakeEventSource.instances).toHaveLength(1);
    expect(lastInstance().url).toBe("/api/scan/events");
    expect(result.current).toEqual({ progress: null, inProgress: false });

    rerender({ active: false });
    expect(lastInstance().closed).toBe(true);

    unmount();
    expect(lastInstance().closed).toBe(true);
  });

  it("parses status events into progress and inProgress", () => {
    const { result } = renderHook(() => useScanProgress(true));

    act(() => lastInstance().emitStatus({ in_progress: true, count: 9, progress: 1234, directory: "/x" }));

    expect(result.current).toEqual({ progress: 1234, inProgress: true });
  });

  it("degrades silently on stream errors and resumes after reconnect", () => {
    const { result } = renderHook(() => useScanProgress(true));

    act(() => lastInstance().emitStatus({ in_progress: true, count: 9, progress: 500, directory: "/x" }));
    expect(result.current.progress).toBe(500);

    act(() => lastInstance().emitError());
    expect(result.current).toEqual({ progress: null, inProgress: true });

    // Browser auto-reconnects; the next tick restores the counts.
    act(() => lastInstance().emitStatus({ in_progress: true, count: 9, progress: 600, directory: "/x" }));
    expect(result.current).toEqual({ progress: 600, inProgress: true });
  });

  it("ignores malformed status payloads without throwing", () => {
    const { result } = renderHook(() => useScanProgress(true));
    const before = result.current;

    act(() => lastInstance().handlers.get("status")?.({ data: "not json" }));

    expect(result.current).toBe(before);
  });

  it("stays inert when EventSource is unavailable", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (window as any).EventSource;
    const { result } = renderHook(() => useScanProgress(true));

    expect(result.current).toEqual({ progress: null, inProgress: false });
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it("closes the previous source across a remount", () => {
    const first = renderHook(() => useScanProgress(true));
    first.unmount();
    expect(lastInstance().closed).toBe(true);

    renderHook(() => useScanProgress(true));

    expect(FakeEventSource.instances).toHaveLength(2);
    expect(lastInstance().closed).toBe(false);
  });
});
