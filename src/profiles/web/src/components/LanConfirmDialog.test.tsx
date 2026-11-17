// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanConfirmDialog } from "./LanConfirmDialog";
import { fetchSystemInfo, setLanEnabled, waitForLanState } from "../api/client";
import type { SystemInfo } from "../api/types";

vi.mock("../api/client", async (importOriginal) => {
  // Keep the real module: the dialog only needs the three flow functions
  // mocked (ConfigEditorModal precedent for direct-imported api clients).
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    setLanEnabled: vi.fn(),
    waitForLanState: vi.fn(),
    fetchSystemInfo: vi.fn(),
  };
});

const setLanSpy = vi.mocked(setLanEnabled);
const waitSpy = vi.mocked(waitForLanState);
const fetchSpy = vi.mocked(fetchSystemInfo);

/** LAN-enabled machine fixture; realistic for the dialog's URLs. */
function makeSystemInfo(overrides: Partial<SystemInfo> = {}): SystemInfo {
  return {
    hostname: "st-465",
    ip: "172.16.41.65",
    username: "operator",
    os_release: "TestOS 1.0",
    lan_enabled: true,
    ...overrides,
  };
}

function renderDialog(
  overrides: { pending?: boolean | null; systemInfo?: SystemInfo | null } = {},
) {
  const props = {
    pending: overrides.pending ?? null,
    systemInfo: overrides.systemInfo ?? makeSystemInfo(),
    showToast: vi.fn(),
    onConfirmed: vi.fn(),
    onCancel: vi.fn(),
  };
  render(<LanConfirmDialog {...props} />);
  return props;
}

beforeEach(() => {
  setLanSpy.mockResolvedValue({ host: "st-465", lan_enabled: true, status: "ok" });
  waitSpy.mockResolvedValue(makeSystemInfo());
  fetchSpy.mockResolvedValue(makeSystemInfo());
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("LanConfirmDialog", () => {
  it("renders nothing when pending is null", () => {
    renderDialog({ pending: null });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders the LAN-on message with copyable URLs when enabling", () => {
    const sys = makeSystemInfo();
    renderDialog({ pending: true, systemInfo: sys });

    expect(screen.getByText("Enable LAN access?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enable LAN" })).toBeInTheDocument();
    expect(screen.getByText(/reachable by anyone on this network/)).toBeInTheDocument();
    // The hostname/IP URLs use the app port — same construction as App's
    // message body (moved verbatim).
    expect(screen.getByText(`http://${sys.hostname}:${window.location.port}`)).toBeInTheDocument();
    expect(screen.getByText(`http://${sys.ip}:${window.location.port}`)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy hostname URL" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy IP URL" })).toBeInTheDocument();
  });

  it("renders the restrict message when disabling", () => {
    renderDialog({ pending: false });

    expect(screen.getByText("Restrict to this machine?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restrict" })).toBeInTheDocument();
    expect(screen.getByText("ProFiles will be reachable only on this machine.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy hostname URL" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy IP URL" })).toBeNull();
  });

  it("confirm closes the dialog first and still completes the flow", async () => {
    const sys = makeSystemInfo();
    waitSpy.mockResolvedValue(sys);
    const user = userEvent.setup();
    const { onCancel, onConfirmed, showToast } = renderDialog({ pending: true });

    await user.click(screen.getByRole("button", { name: "Enable LAN" }));

    // Dialog-closes-first quirk: the close action (onCancel) fires before
    // the API call, yet the flow still completes behind the closed dialog.
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(setLanSpy).toHaveBeenCalledWith(true);
    expect(onCancel.mock.invocationCallOrder[0]).toBeLessThan(
      setLanSpy.mock.invocationCallOrder[0]
    );
    await waitFor(() => expect(onConfirmed).toHaveBeenCalledWith(sys));
    expect(onConfirmed).toHaveBeenCalledTimes(1);
    expect(showToast).toHaveBeenCalledWith("Updating LAN binding…", "info");
    expect(showToast).toHaveBeenCalledWith(
      "ProFiles is now reachable on the local network.",
      "info"
    );
  });

  it("waitForLanState disagreement toasts the still-active failure", async () => {
    // The bind response said ok, but the observed state never caught up:
    // the outcome branch reads waitForLanState's sys, not the response.
    const stale = makeSystemInfo({ lan_enabled: false });
    waitSpy.mockResolvedValue(stale);
    const user = userEvent.setup();
    const { onConfirmed, showToast } = renderDialog({ pending: true });

    await user.click(screen.getByRole("button", { name: "Enable LAN" }));

    await waitFor(() =>
      expect(showToast).toHaveBeenCalledWith(
        "Failed to update LAN binding — the previous address is still active.",
        "error"
      )
    );
    expect(onConfirmed).toHaveBeenCalledTimes(1);
    expect(onConfirmed).toHaveBeenCalledWith(stale);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(showToast).not.toHaveBeenCalledWith(
      "ProFiles is now reachable on the local network.",
      expect.anything()
    );
  });

  it("rejected setLanEnabled toasts the failure and refetches system info", async () => {
    setLanSpy.mockRejectedValue(new Error("boom"));
    const refetched = makeSystemInfo({ lan_enabled: false });
    fetchSpy.mockResolvedValue(refetched);
    const user = userEvent.setup();
    const { onConfirmed, showToast } = renderDialog({ pending: true });

    await user.click(screen.getByRole("button", { name: "Enable LAN" }));

    await waitFor(() => expect(onConfirmed).toHaveBeenCalledWith(refetched));
    expect(showToast).toHaveBeenCalledWith("Failed to update LAN binding: boom", "error");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    // The transitional toast ships only after the awaited bind call —
    // a rejection skips it entirely.
    expect(showToast).not.toHaveBeenCalledWith("Updating LAN binding…", expect.anything());
  });

  it("cancel calls onCancel", async () => {
    const user = userEvent.setup();
    const { onCancel } = renderDialog({ pending: true });

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(setLanSpy).not.toHaveBeenCalled();
    expect(waitSpy).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
