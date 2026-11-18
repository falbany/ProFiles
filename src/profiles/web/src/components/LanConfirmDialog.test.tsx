// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanConfirmDialog } from "./LanConfirmDialog";
import {
  fetchSystemInfo,
  generateBarcode,
  setLanEnabled,
  waitForLanState,
} from "../api/client";
import type { SystemInfo } from "../api/types";

vi.mock("../api/client", async (importOriginal) => {
  // Keep the real module: the dialog only needs the flow functions mocked
  // (ConfigEditorModal precedent for direct-imported api clients).
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    setLanEnabled: vi.fn(),
    waitForLanState: vi.fn(),
    fetchSystemInfo: vi.fn(),
    generateBarcode: vi.fn(),
  };
});

const setLanSpy = vi.mocked(setLanEnabled);
const waitSpy = vi.mocked(waitForLanState);
const fetchSpy = vi.mocked(fetchSystemInfo);
const qrSpy = vi.mocked(generateBarcode);

const QR_IMAGE = "data:image/png;base64,FAKEQR";

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

/** Manually-resolved promise so enabling-state timing is deterministic. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
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
  const utils = render(<LanConfirmDialog {...props} />);
  return { ...props, rerender: utils.rerender };
}

/** Click "Enable LAN" and hold the flow on the enabling state via a gate.
 *  QR behavior is left to the caller / the beforeEach default. */
async function enableThroughEnablingGate() {
  const gate = deferred<SystemInfo | null>();
  waitSpy.mockReturnValue(gate.promise);
  const props = renderDialog({ pending: true });
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Enable LAN" }));
  return { gate, props, user };
}

beforeEach(() => {
  setLanSpy.mockResolvedValue({ host: "st-465", lan_enabled: true, status: "ok" });
  waitSpy.mockResolvedValue(makeSystemInfo());
  fetchSpy.mockResolvedValue(makeSystemInfo());
  qrSpy.mockResolvedValue({ image: QR_IMAGE, content: "any" });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("LanConfirmDialog — confirm phase", () => {
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
    expect(screen.getByText(`http://${sys.hostname}:${window.location.port}`)).toBeInTheDocument();
    expect(screen.getByText(`http://${sys.ip}:${window.location.port}`)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy hostname URL" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy IP URL" })).toBeInTheDocument();
  });

  it("offers the loopback URL as a clickable link (issue #199)", () => {
    renderDialog({ pending: true });

    const loopback = screen.getByRole("link", { name: /127\.0\.0\.1/ });
    expect(loopback).toHaveAttribute(
      "href",
      `http://127.0.0.1:${window.location.port}`
    );
    expect(loopback).toHaveAttribute("target", "_blank");
    expect(loopback).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("renders no QR while LAN is not enabled yet (issue #198)", () => {
    renderDialog({ pending: true });

    expect(screen.queryByRole("img", { name: /QR/i })).toBeNull();
    expect(qrSpy).not.toHaveBeenCalled();
  });

  it("renders the restrict message when disabling", () => {
    renderDialog({ pending: false });

    expect(screen.getByText("Restrict to this machine?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restrict" })).toBeInTheDocument();
    expect(screen.getByText("ProFiles will be reachable only on this machine.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy hostname URL" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy IP URL" })).toBeNull();
  });

  it("cancel in the confirm phase closes without touching the API", async () => {
    const user = userEvent.setup();
    const { onCancel } = renderDialog({ pending: true });

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(setLanSpy).not.toHaveBeenCalled();
    expect(waitSpy).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(qrSpy).not.toHaveBeenCalled();
  });
});

describe("LanConfirmDialog — enable flow panel (issue #197)", () => {
  it("keeps the modal open through the flow and lands on the enabled panel", async () => {
    const sys = makeSystemInfo();
    const { gate, props } = await enableThroughEnablingGate();

    // No dialog-closes-first anymore: the modal stays up, flow inside.
    expect(props.onCancel).not.toHaveBeenCalled();
    expect(screen.getByText("Enabling LAN…")).toBeInTheDocument();

    gate.resolve(sys);
    expect(await screen.findByText("LAN access enabled")).toBeInTheDocument();

    expect(props.onConfirmed).toHaveBeenCalledWith(sys);
    expect(props.onCancel).not.toHaveBeenCalled();
    // Inline status replaces the toasts while the panel is open.
    expect(props.showToast).not.toHaveBeenCalled();
    expect(screen.getByText(/reachable on (this|the local) network/i)).toBeInTheDocument();
    // The URLs survive the toggle — the user can copy them now (issue #197).
    expect(screen.getByRole("button", { name: "Copy hostname URL" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy IP URL" })).toBeInTheDocument();
  });

  it("shows the instruction line and the loopback link in the enabled panel", async () => {
    const { gate } = await enableThroughEnablingGate();
    gate.resolve(makeSystemInfo());
    await screen.findByText("LAN access enabled");

    expect(
      screen.getByText(/On another device on this network/)
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /127\.0\.0\.1/ })).toBeInTheDocument();
  });

  it("closes from the enabled panel via the ❌ button", async () => {
    const { gate, props, user } = await enableThroughEnablingGate();
    gate.resolve(makeSystemInfo());
    await screen.findByText("LAN access enabled");

    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(props.onCancel).toHaveBeenCalledTimes(1);
  });

  it("closes the panel with Escape mid-flow and falls back to toasts", async () => {
    const sys = makeSystemInfo();
    const { gate, props, user } = await enableThroughEnablingGate();
    expect(screen.getByText("Enabling LAN…")).toBeInTheDocument();

    const close = screen.getByRole("button", { name: "Close" });
    await waitFor(() => expect(close).toHaveFocus());
    await user.keyboard("{Escape}");
    expect(props.onCancel).toHaveBeenCalledTimes(1);
    // App answers onCancel by closing: the dialog unmounts its panel while
    // the flow keeps running (same component instance, pending null).
    props.rerender(
      <LanConfirmDialog
        pending={null}
        systemInfo={makeSystemInfo()}
        showToast={props.showToast}
        onConfirmed={props.onConfirmed}
        onCancel={props.onCancel}
      />
    );

    // The flow completes behind the closed panel; the toast is now the only
    // feedback channel.
    gate.resolve(sys);
    await waitFor(() => expect(props.onConfirmed).toHaveBeenCalledWith(sys));
    expect(props.showToast).toHaveBeenCalledWith(
      "ProFiles is now reachable on the local network.",
      "info"
    );
  });

  it("observed disagreement lands on the failed panel, inline and silent", async () => {
    // The bind response said ok, but the observed state never caught up:
    // the outcome branch reads waitForLanState's sys, not the response.
    const stale = makeSystemInfo({ lan_enabled: false });
    waitSpy.mockResolvedValue(stale);
    const user = userEvent.setup();
    const { onConfirmed, showToast } = renderDialog({ pending: true });

    await user.click(screen.getByRole("button", { name: "Enable LAN" }));

    expect(await screen.findByText("LAN update failed")).toBeInTheDocument();
    expect(screen.getByText(/previous address is still active/)).toBeInTheDocument();
    expect(onConfirmed).toHaveBeenCalledWith(stale);
    // Panel open → the failure is inline, not toast-only (issue #197).
    expect(showToast).not.toHaveBeenCalled();
  });

  it("rejected bind lands on the failed panel and refetches system info", async () => {
    setLanSpy.mockRejectedValue(new Error("boom"));
    const refetched = makeSystemInfo({ lan_enabled: false });
    fetchSpy.mockResolvedValue(refetched);
    const user = userEvent.setup();
    const { onConfirmed } = renderDialog({ pending: true });

    await user.click(screen.getByRole("button", { name: "Enable LAN" }));

    expect(await screen.findByText("LAN update failed")).toBeInTheDocument();
    expect(screen.getByText(/Failed to update LAN binding: boom/)).toBeInTheDocument();
    await waitFor(() => expect(onConfirmed).toHaveBeenCalledWith(refetched));
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});

describe("LanConfirmDialog — QR code (issue #198)", () => {
  it("renders a QR of the IP URL once LAN is enabled", async () => {
    const sys = makeSystemInfo();
    const { gate } = await enableThroughEnablingGate();
    gate.resolve(sys);

    const qr = await screen.findByRole("img", { name: /QR/i });
    expect(qr).toHaveAttribute("src", QR_IMAGE);
    expect(qrSpy).toHaveBeenCalledTimes(1);
    expect(qrSpy).toHaveBeenCalledWith({
      content: `http://${sys.ip}:${window.location.port}`,
    });
  });

  it("degrades to an inline message when QR generation fails", async () => {
    qrSpy.mockRejectedValue(new Error("qr boom"));
    const { gate } = await enableThroughEnablingGate();
    gate.resolve(makeSystemInfo());

    expect(await screen.findByText(/qr boom/)).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /QR/i })).toBeNull();
    expect(screen.getByText("LAN access enabled")).toBeInTheDocument();
  });
});

describe("LanConfirmDialog — restrict flow (unchanged)", () => {
  it("confirm closes the dialog first and still completes the flow", async () => {
    const sys = makeSystemInfo({ lan_enabled: false });
    waitSpy.mockResolvedValue(sys);
    const user = userEvent.setup();
    const { onCancel, onConfirmed, showToast } = renderDialog({ pending: false });

    await user.click(screen.getByRole("button", { name: "Restrict" }));

    // Dialog-closes-first quirk preserved on the restrict path: the close
    // action (onCancel) fires before the API call, yet the flow still
    // completes behind the closed dialog.
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(setLanSpy).toHaveBeenCalledWith(false);
    expect(onCancel.mock.invocationCallOrder[0]).toBeLessThan(
      setLanSpy.mock.invocationCallOrder[0]
    );
    await waitFor(() => expect(onConfirmed).toHaveBeenCalledWith(sys));
    expect(onConfirmed).toHaveBeenCalledTimes(1);
    expect(showToast).toHaveBeenCalledWith(
      "Restricting ProFiles to this machine…",
      "info"
    );
    expect(showToast).toHaveBeenCalledWith(
      "ProFiles is restricted to this machine.",
      "info"
    );
  });

  it("waitForLanState disagreement toasts the still-active failure", async () => {
    const stale = makeSystemInfo({ lan_enabled: true });
    waitSpy.mockResolvedValue(stale);
    const user = userEvent.setup();
    const { onConfirmed, showToast } = renderDialog({ pending: false });

    await user.click(screen.getByRole("button", { name: "Restrict" }));

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
      "ProFiles is restricted to this machine.",
      expect.anything()
    );
  });
});
