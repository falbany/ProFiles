// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";

/**
 * Unit tests for the `useToast` hook (issue #148, PR 2) — the transient-toast
 * state extracted verbatim from `App.tsx`. They pin the info toast's 3500ms
 * auto-dismiss, the error toast's longer 10000ms lifetime, the empty-message
 * guard (never blank an existing toast), the pending-timer replacement when a
 * new toast arrives, the immediate `dismissToast` clearing, and the default
 * `info` kind.
 */
import { useToast } from "./useToast";

afterEach(() => {
  cleanup();
  // The auto-dismiss scenarios run under fake timers; restore real ones so
  // the other scenarios are unaffected.
  if (vi.isFakeTimers()) vi.useRealTimers();
});

describe("useToast", () => {
  it("showToast sets an info toast and auto-dismisses after 3500ms", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useToast());
    expect(result.current.toastMessage).toBeNull();

    act(() => result.current.showToast("Hello"));
    expect(result.current.toastMessage).toEqual({ message: "Hello", kind: "info" });

    act(() => vi.advanceTimersByTime(3499));
    expect(result.current.toastMessage).toEqual({ message: "Hello", kind: "info" });

    act(() => vi.advanceTimersByTime(1));
    expect(result.current.toastMessage).toBeNull();
  });

  it("error toasts stay for 10000ms", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useToast());

    act(() => result.current.showToast("Boom", "error"));
    expect(result.current.toastMessage).toEqual({ message: "Boom", kind: "error" });

    // Still present past the info-toast lifetime.
    act(() => vi.advanceTimersByTime(3500));
    expect(result.current.toastMessage).toEqual({ message: "Boom", kind: "error" });

    act(() => vi.advanceTimersByTime(6499));
    expect(result.current.toastMessage).toEqual({ message: "Boom", kind: "error" });

    act(() => vi.advanceTimersByTime(1));
    expect(result.current.toastMessage).toBeNull();
  });

  it("empty messages are ignored", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useToast());

    act(() => result.current.showToast(""));
    expect(result.current.toastMessage).toBeNull();

    // No timer was armed: advancing past every lifetime changes nothing.
    act(() => vi.advanceTimersByTime(10000));
    expect(result.current.toastMessage).toBeNull();
  });

  it("a new toast replaces the pending timer", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useToast());

    act(() => result.current.showToast("first"));
    act(() => vi.advanceTimersByTime(1000));
    act(() => result.current.showToast("second", "error"));
    expect(result.current.toastMessage).toEqual({ message: "second", kind: "error" });

    // t = 3500: the first toast's timer was cleared, the error toast remains.
    act(() => vi.advanceTimersByTime(2500));
    expect(result.current.toastMessage).toEqual({ message: "second", kind: "error" });

    // t = 10999: the error toast (armed at t = 1000) is still there…
    act(() => vi.advanceTimersByTime(7499));
    expect(result.current.toastMessage).toEqual({ message: "second", kind: "error" });

    // …and dismisses exactly 10000ms after it was shown, i.e. at t = 11000.
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.toastMessage).toBeNull();
  });

  it("dismissToast clears immediately", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useToast());

    act(() => result.current.showToast("Bye"));
    act(() => result.current.dismissToast());
    expect(result.current.toastMessage).toBeNull();

    // The pending auto-dismiss timer was cleared too.
    act(() => vi.advanceTimersByTime(10000));
    expect(result.current.toastMessage).toBeNull();
  });

  it("kind defaults to info", () => {
    const { result } = renderHook(() => useToast());
    act(() => result.current.showToast("Default"));
    expect(result.current.toastMessage).toEqual({ message: "Default", kind: "info" });
  });
});
