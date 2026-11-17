// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";

/**
 * Unit tests for the `useAutoRescanTimer` hook (issue #148, PR 2) — the
 * periodic auto-rescan timer extracted verbatim from `App.tsx`. They pin the
 * disabled default (interval 0 never arms a timer), the 30s tick period with
 * its exact enable toast, the disable path ("Auto-rescan disabled."), the
 * timer replacement on interval change (no stacked intervals), the latest-ref
 * deps read without re-arming the interval, and the unmount teardown.
 */
import { useAutoRescanTimer } from "./useAutoRescanTimer";

/**
 * Deps mocks, typed with their hook signatures so the bag stays assignable
 * to `deps`. App passes fresh closure identities every render, so the tests
 * re-assign `deps` and `rerender()` to mimic that.
 */
type AutoRescanDeps = Parameters<typeof useAutoRescanTimer>[0];
type ShowToast = AutoRescanDeps["showToast"];

let scan: Mock<() => void>;
let showToast: Mock<ShowToast>;
let deps: AutoRescanDeps;

beforeEach(() => {
  vi.clearAllMocks();
  scan = vi.fn<() => void>();
  showToast = vi.fn<ShowToast>();
  deps = { scan, showToast };
});

afterEach(() => {
  cleanup();
  // Restore the setInterval spy from the latest-closure scenario FIRST —
  // restoring after useRealTimers() would stamp the fake implementation
  // over the real one. Doing it here also keeps a failing assertion from
  // leaking the spy into sibling tests.
  vi.restoreAllMocks();
  // The tick scenarios run under fake timers; restore real ones so the
  // other scenarios are unaffected.
  if (vi.isFakeTimers()) vi.useRealTimers();
});

describe("useAutoRescanTimer", () => {
  it("interval 0 never ticks", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useAutoRescanTimer(deps));
    expect(result.current.autoRescanInterval).toBe(0);

    // A full minute passes — nothing was armed, nothing fires.
    act(() => vi.advanceTimersByTime(60000));
    expect(scan).not.toHaveBeenCalled();
    expect(showToast).not.toHaveBeenCalled();
  });

  it("handleTimerSet(30) toasts and ticks scan every 30s", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useAutoRescanTimer(deps));

    act(() => result.current.handleTimerSet(30));
    expect(showToast).toHaveBeenCalledTimes(1);
    expect(showToast).toHaveBeenCalledWith("Auto-rescan every 30s.");

    // First tick at t = 30s, not before.
    act(() => vi.advanceTimersByTime(29999));
    expect(scan).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(scan).toHaveBeenCalledTimes(1);

    // Second tick at t = 60s: the interval re-armed.
    act(() => vi.advanceTimersByTime(30000));
    expect(scan).toHaveBeenCalledTimes(2);
  });

  it('handleTimerSet(0) stops ticking and toasts "Auto-rescan disabled."', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useAutoRescanTimer(deps));

    act(() => result.current.handleTimerSet(30));
    act(() => vi.advanceTimersByTime(30000));
    expect(scan).toHaveBeenCalledTimes(1);

    act(() => result.current.handleTimerSet(0));
    expect(showToast).toHaveBeenLastCalledWith("Auto-rescan disabled.");

    // The running timer was cleared: minutes pass without a further tick.
    act(() => vi.advanceTimersByTime(120000));
    expect(scan).toHaveBeenCalledTimes(1);
  });

  it("changing the interval replaces the running timer", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useAutoRescanTimer(deps));

    act(() => result.current.handleTimerSet(30));
    act(() => vi.advanceTimersByTime(20 * 1000)); // t = 20s: mid-cycle swap
    act(() => result.current.handleTimerSet(60)); // re-arms 60s from t = 20s

    // t = 60s: a stacked old 30s interval would tick here (its second beat);
    // the replacement fires only at t = 80s, i.e. 60s after the re-arm.
    act(() => vi.advanceTimersByTime(40 * 1000));
    expect(scan).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(20 * 1000)); // t = 80s
    expect(scan).toHaveBeenCalledTimes(1);
  });

  it("uses the latest scan closure without re-subscribing", () => {
    vi.useFakeTimers();
    // Spy AFTER installing fake timers so the spy wraps (and calls through
    // to) the fake setInterval — callCount == armed intervals.
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    const firstScan = vi.fn<() => void>();
    const firstToast = vi.fn<ShowToast>();
    deps = { scan: firstScan, showToast: firstToast };
    const { result, rerender } = renderHook(() => useAutoRescanTimer(deps));
    act(() => result.current.handleTimerSet(30));
    const intervalsArmedAtEnable = setIntervalSpy.mock.calls.length;
    expect(intervalsArmedAtEnable).toBe(1);

    // App re-rendered with fresh closure identities (its per-render deps).
    const latestScan = vi.fn<() => void>();
    const latestToast = vi.fn<ShowToast>();
    deps = { scan: latestScan, showToast: latestToast };
    rerender();

    // No churn: the deps swap neither armed another interval nor tore the
    // running one down.
    expect(setIntervalSpy.mock.calls.length).toBe(intervalsArmedAtEnable);

    act(() => vi.advanceTimersByTime(30000));
    // The LATEST scan identity is the one the tick invokes.
    expect(latestScan).toHaveBeenCalledTimes(1);
    expect(firstScan).not.toHaveBeenCalled();

    // The handler reads the latest toast identity too.
    act(() => result.current.handleTimerSet(0));
    expect(latestToast).toHaveBeenCalledWith("Auto-rescan disabled.");
    expect(firstToast).not.toHaveBeenCalledWith("Auto-rescan disabled.");
  });

  it("unmount stops the interval", () => {
    vi.useFakeTimers();
    const { result, unmount } = renderHook(() => useAutoRescanTimer(deps));
    act(() => result.current.handleTimerSet(30));
    unmount();

    act(() => vi.advanceTimersByTime(120000));
    expect(scan).not.toHaveBeenCalled();
  });
});
