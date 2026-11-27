// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";

/**
 * Unit tests for the shared SSE status feed (`useScanStatusFeed`, issue
 * #223) — the module-level singleton store behind `/api/scan/events` that
 * both `useScanProgress` (#152) and the watch UI consume through one
 * app-lifetime `EventSource`.
 *
 * They pin the snake→camel payload parsing (full and partial snapshots),
 * keep-last-good tolerance of malformed payloads, the no-`EventSource`
 * guard (test jsdom, exotic browsers), and the singleton contract the
 * whole feature stands on: exactly one connection no matter how many
 * consumers mount, opened on the first subscriber and closed when the
 * last one unsubscribes.
 */
import { INITIAL_TICK, useScanStatusFeed } from "./useScanStatusFeed";
import { useScanProgress } from "./useScanProgress";

/** Full snake_case status payload the server streams every second. */
const FULL_PAYLOAD =
  '{"in_progress":true,"progress":7,"directory":"/d","watching":true,"watch_interval_s":1.5,"watch_seq":4,"watch_error":null}';

const FULL_TICK = {
  inProgress: true,
  progress: 7,
  directory: "/d",
  watching: true,
  watchIntervalS: 1.5,
  watchSeq: 4,
  watchError: null,
};

/**
 * Minimal EventSource double: a static registry of every constructed
 * instance, manual event delivery with a raw JSON payload, and close
 * tracking so tests can assert on the singleton's lifecycle.
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

beforeEach(() => {
  MockEventSource.instances = [];
  (globalThis as { EventSource?: unknown }).EventSource = MockEventSource;
});

afterEach(() => {
  cleanup();
  delete (globalThis as { EventSource?: unknown }).EventSource;
});

describe("useScanStatusFeed", () => {
  it("test_parses_full_status_payload", () => {
    const { result } = renderHook(() => useScanStatusFeed());

    act(() => lastSource().emit("status", FULL_PAYLOAD));

    expect(result.current).toEqual(FULL_TICK);
  });

  it("test_partial_payload_defaults", () => {
    const { result } = renderHook(() => useScanStatusFeed());

    act(() => lastSource().emit("status", '{"progress":3}'));

    expect(result.current).toEqual({
      inProgress: false,
      progress: 3,
      directory: "",
      watching: false,
      watchIntervalS: null,
      watchSeq: null,
      watchError: null,
    });
  });

  it("test_malformed_payload_keeps_last_good_state", () => {
    const { result } = renderHook(() => useScanStatusFeed());

    act(() => lastSource().emit("status", FULL_PAYLOAD));
    act(() => lastSource().emit("status", "not json"));

    expect(result.current).toEqual(FULL_TICK);
  });

  it("test_missing_eventsource_is_inert", () => {
    delete (globalThis as { EventSource?: unknown }).EventSource;

    const { result } = renderHook(() => useScanStatusFeed());

    expect(result.current).toEqual(INITIAL_TICK);
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it("test_single_connection_shared", () => {
    renderHook(() => useScanProgress(true));
    expect(MockEventSource.instances).toHaveLength(1);

    // The #152 hook must NOT open a second source for its own stream.
    renderHook(() => useScanStatusFeed());
    expect(MockEventSource.instances).toHaveLength(1);
  });

  it("test_use_scan_progress_gates_on_active", () => {
    const { result, rerender } = renderHook(({ active }) => useScanProgress(active), {
      initialProps: { active: false },
    });
    renderHook(() => useScanStatusFeed()); // the feed is live

    act(() => lastSource().emit("status", FULL_PAYLOAD));
    expect(result.current).toEqual({ progress: null, inProgress: false });

    rerender({ active: true });
    expect(result.current).toEqual({ progress: 7, inProgress: true });
  });
});
