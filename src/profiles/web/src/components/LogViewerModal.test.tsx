// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LogViewerModal } from "./LogViewerModal";
import { fetchLogEntries } from "../api/client";
import type { LogEntry, LogResponse } from "../api/types";

vi.mock("../api/client", () => ({
  fetchLogEntries: vi.fn(),
}));

const fetchSpy = vi.mocked(fetchLogEntries);

function makeEntry(message: string): LogEntry {
  return {
    timestamp: "2026-11-07 10:00:00",
    level: "INFO",
    source: "test",
    message,
    event: "",
    raw: message,
  };
}

function makeResponse(message: string): LogResponse {
  return { path: "profiles.log", size_bytes: 128, total_returned: 1, entries: [makeEntry(message)] };
}

/** Wait out the modal's 250 ms filter debounce. */
const settleDebounce = () => new Promise((resolve) => setTimeout(resolve, 320));

function renderModal() {
  return render(<LogViewerModal isOpen onClose={() => {}} />);
}

beforeEach(() => {
  vi.clearAllMocks();
  fetchSpy.mockResolvedValue(makeResponse("fresh"));
});

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});

describe("LogViewerModal", () => {
  it("test_single_fetch_on_open", async () => {
    renderModal();
    await screen.findByText("fresh");

    // Opening must load once: the debounced filter effect re-fires 250 ms
    // after open, but must skip its first run (issue #139).
    await settleDebounce();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("test_filter_change_refetches_after_debounce", async () => {
    const user = userEvent.setup();
    fetchSpy
      .mockResolvedValueOnce(makeResponse("fresh"))
      .mockResolvedValueOnce(makeResponse("filtered"));
    renderModal();
    await screen.findByText("fresh");

    await user.type(screen.getByLabelText("Filter log lines"), "abc");
    await waitFor(
      () => expect(screen.getByText("filtered")).toBeTruthy(),
      { timeout: 3000 },
    );
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("test_stale_response_never_overwrites_newer_results", async () => {
    const user = userEvent.setup();

    // The initial open load stalls; a filter change resolves first.
    let resolveInitial: (value: LogResponse) => void = () => {};
    fetchSpy
      .mockImplementationOnce(() => new Promise<LogResponse>((resolve) => { resolveInitial = resolve; }))
      .mockResolvedValueOnce(makeResponse("filtered results"));

    renderModal();
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));

    await user.type(screen.getByLabelText("Filter log lines"), "x");
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));
    await screen.findByText("filtered results");

    // The stale response for the *initial* filter lands last — it must be
    // dropped instead of overwriting the newer results (issue #139).
    resolveInitial(makeResponse("stale initial results"));
    await settleDebounce();
    expect(screen.queryByText("stale initial results")).toBeNull();
    expect(screen.getByText("filtered results")).toBeTruthy();
  });

  it("test_shortcut_hint_matches_binding", async () => {
    renderModal();
    await screen.findByText("fresh");
    // Ctrl+Shift+L toggles the viewer in App — the footer must say so
    // (issue #139), not claim it opens the file externally.
    expect(screen.getByText("toggles this viewer")).toBeTruthy();
    expect(screen.queryByText("opens externally")).toBeNull();
  });
});
