// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";

/**
 * Unit tests for the `useExternalEvents` hook (issue #148, PR 2) — the
 * config-handoff notification poll extracted verbatim from `App.tsx`. They
 * pin the 4000ms poll period with per-event toasts, the config_applied
 * ordering (re-apply before the toast), the lastEventId advancement (the
 * max seen id feeds the next poll), the silent fetch-failure retry on the
 * next tick, the best-effort onConfigApplied (rejection swallowed, toast
 * still fires), the latest-ref deps read without re-arming the interval,
 * and the unmount teardown.
 */
import { useExternalEvents } from "./useExternalEvents";
import { fetchNotifications } from "../api/client";
import type { ExternalEvent } from "../api/types";

vi.mock("../api/client", () => ({
  fetchNotifications: vi.fn(),
}));

const fetchNotificationsSpy = vi.mocked(fetchNotifications);

/** The deps bag shape the hook consumes (App passes it fresh every render). */
type ExternalEventsDeps = Parameters<typeof useExternalEvents>[0];
type ShowToast = ExternalEventsDeps["showToast"];

function makeEvent(overrides: Partial<ExternalEvent> = {}): ExternalEvent {
  return {
    id: 1,
    kind: "config_handoff",
    message: "handoff",
    config_applied: false,
    ...overrides,
  };
}

/**
 * Deps mocks, typed with their hook signatures so the bag stays assignable
 * to `deps`. App passes fresh closure identities every render, so the tests
 * re-assign `deps` and `rerender()` to mimic that.
 */
let onConfigApplied: Mock<() => Promise<void>>;
let showToast: Mock<ShowToast>;
let deps: ExternalEventsDeps;

beforeEach(() => {
  vi.clearAllMocks();
  onConfigApplied = vi.fn<() => Promise<void>>();
  showToast = vi.fn<ShowToast>();
  deps = { onConfigApplied, showToast };
});

afterEach(() => {
  cleanup();
  // The poll scenarios run under fake timers; restore real ones so the
  // other scenarios are unaffected.
  if (vi.isFakeTimers()) vi.useRealTimers();
});

describe("useExternalEvents", () => {
  it("polls every 4000ms and toasts each event message", async () => {
    vi.useFakeTimers();
    fetchNotificationsSpy.mockResolvedValueOnce({
      events: [
        makeEvent({ id: 1, message: "First handoff" }),
        makeEvent({ id: 2, message: "Second handoff" }),
      ],
    });
    renderHook(() => useExternalEvents(deps));

    // First poll fires at t = 4000, not before.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3999);
    });
    expect(fetchNotificationsSpy).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(fetchNotificationsSpy).toHaveBeenCalledTimes(1);
    expect(fetchNotificationsSpy).toHaveBeenNthCalledWith(1, 0);
    expect(showToast).toHaveBeenCalledTimes(2);
    expect(showToast).toHaveBeenNthCalledWith(1, "First handoff");
    expect(showToast).toHaveBeenNthCalledWith(2, "Second handoff");

    // The interval re-arms: the next tick polls again (4000ms later).
    fetchNotificationsSpy.mockResolvedValueOnce({ events: [] });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(fetchNotificationsSpy).toHaveBeenCalledTimes(2);
    expect(showToast).toHaveBeenCalledTimes(2);
  });

  it("config_applied events trigger onConfigApplied before the toast", async () => {
    vi.useFakeTimers();
    fetchNotificationsSpy.mockResolvedValueOnce({
      events: [makeEvent({ id: 5, message: "Config applied", config_applied: true })],
    });
    const order: string[] = [];
    onConfigApplied.mockImplementation(async () => {
      order.push("apply");
    });
    showToast.mockImplementation((msg: string) => {
      order.push(`toast:${msg}`);
    });
    renderHook(() => useExternalEvents(deps));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(onConfigApplied).toHaveBeenCalledTimes(1);
    expect(order).toEqual(["apply", "toast:Config applied"]);
  });

  it("advances lastEventId and passes it to the next poll", async () => {
    vi.useFakeTimers();
    // Two events out of order: the max seen id (7) must win, not the last.
    fetchNotificationsSpy
      .mockResolvedValueOnce({
        events: [makeEvent({ id: 7, message: "older" }), makeEvent({ id: 3, message: "stale" })],
      })
      .mockResolvedValueOnce({ events: [] });
    renderHook(() => useExternalEvents(deps));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(fetchNotificationsSpy).toHaveBeenNthCalledWith(1, 0);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    // The second poll starts after the max id seen (7), not the last (3).
    expect(fetchNotificationsSpy).toHaveBeenNthCalledWith(2, 7);
  });

  it("fetch failures are silent and retried on the next tick", async () => {
    vi.useFakeTimers();
    fetchNotificationsSpy
      .mockRejectedValueOnce(new Error("server unreachable"))
      .mockResolvedValueOnce({ events: [makeEvent({ id: 1, message: "Recovered" })] });
    renderHook(() => useExternalEvents(deps));

    // Failed poll: no toast, no throw.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(showToast).not.toHaveBeenCalled();

    // The next tick retries and toasts normally.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(showToast).toHaveBeenCalledTimes(1);
    expect(showToast).toHaveBeenCalledWith("Recovered");
  });

  it("onConfigApplied failures are swallowed; the toast still fires", async () => {
    vi.useFakeTimers();
    fetchNotificationsSpy.mockResolvedValueOnce({
      events: [makeEvent({ id: 2, message: "Applied anyway", config_applied: true })],
    });
    onConfigApplied.mockRejectedValue(new Error("rescan blew up"));
    renderHook(() => useExternalEvents(deps));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(onConfigApplied).toHaveBeenCalledTimes(1);
    expect(showToast).toHaveBeenCalledTimes(1);
    expect(showToast).toHaveBeenCalledWith("Applied anyway");
  });

  it("uses the latest onConfigApplied identity without re-subscribing", async () => {
    vi.useFakeTimers();
    // Spy AFTER installing fake timers so the spy wraps (and calls through
    // to) the fake setInterval — callCount == armed intervals.
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    fetchNotificationsSpy.mockResolvedValue({
      events: [makeEvent({ id: 1, message: "Handoff", config_applied: true })],
    });
    const firstApply = vi.fn<() => Promise<void>>();
    deps.onConfigApplied = firstApply;
    const { rerender } = renderHook(() => useExternalEvents(deps));
    const intervalsArmedAtMount = setIntervalSpy.mock.calls.length;
    expect(intervalsArmedAtMount).toBe(1);

    // App re-rendered with fresh closure identities (its per-render deps).
    const latestApply = vi.fn<() => Promise<void>>();
    const latestToast = vi.fn<ShowToast>();
    deps = { onConfigApplied: latestApply, showToast: latestToast };
    rerender();

    // No re-subscription: exactly one interval remains armed.
    expect(setIntervalSpy.mock.calls.length).toBe(intervalsArmedAtMount);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    // The LATEST identity is the one invoked.
    expect(latestApply).toHaveBeenCalledTimes(1);
    expect(firstApply).not.toHaveBeenCalled();
    expect(latestToast).toHaveBeenCalledWith("Handoff");
    setIntervalSpy.mockRestore();
  });

  it("unmount stops the poll", async () => {
    vi.useFakeTimers();
    fetchNotificationsSpy.mockResolvedValue({ events: [] });
    const { unmount } = renderHook(() => useExternalEvents(deps));
    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(12000);
    });
    expect(fetchNotificationsSpy).not.toHaveBeenCalled();
    expect(showToast).not.toHaveBeenCalled();
  });
});
