// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanModal } from "./LanModal";
import {
  fetchSystemInfo,
  generateBarcode,
  setLanEnabled,
  waitForLanState,
} from "../api/client";
import type { SystemInfo } from "../api/types";

vi.mock("../api/client", async (importOriginal) => {
  // Keep the real module: the modal only needs the flow functions mocked
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

/** LAN-enabled machine fixture; realistic for the modal's URLs. */
function makeSystemInfo(overrides: Partial<SystemInfo> = {}): SystemInfo {
  return {
    hostname: "st-465",
    ip: "172.16.41.65",
    username: "operator",
    os_release: "TestOS 1.0",
    lan_enabled: false,
    ...overrides,
  };
}

/** Manually-resolved promise so in-flight timing is deterministic. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

function renderModal(
  overrides: { open?: boolean; systemInfo?: SystemInfo | null } = {},
) {
  const props = {
    open: overrides.open ?? true,
    systemInfo:
      overrides.systemInfo !== undefined
        ? overrides.systemInfo
        : makeSystemInfo(),
    showToast: vi.fn(),
    onConfirmed: vi.fn(),
    onClose: vi.fn(),
  };
  const utils = render(<LanModal {...props} />);
  return { ...props, rerender: utils.rerender };
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

describe("LanModal — visibility & state display", () => {
  it("renders nothing when open is false and generates no QR", () => {
    renderModal({ open: false });

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(qrSpy).not.toHaveBeenCalled();
  });

  it("shows the restricted state with an Enable LAN footer button", () => {
    renderModal({ systemInfo: makeSystemInfo({ lan_enabled: false }) });

    // Status lives in the header now (icon chip + full sentence).
    expect(
      screen.getByText("LAN Access — Restricted to the host machine.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/ProFiles is restricted/)).toBeNull();
    expect(screen.getByRole("button", { name: "Enable LAN" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
    // Same URLs either way — informational, plus the loopback link (#199).
    expect(screen.getByRole("button", { name: "Copy hostname URL" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy IP URL" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /127\.0\.0\.1/ })).toBeInTheDocument();
  });

  it("shows the enabled state with a Disable LAN footer button", () => {
    renderModal({ systemInfo: makeSystemInfo({ lan_enabled: true }) });

    expect(
      screen.getByText("LAN Access — Reachable on this network.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/ProFiles is reachable/)).toBeNull();
    // The instruction line was removed (user review): the header + QR speak
    // for themselves.
    expect(screen.queryByText(/On another device on this network/)).toBeNull();
    expect(screen.getByRole("button", { name: "Disable LAN" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("always displays the QR, even while LAN is disabled (issue #198 override)", async () => {
    const sys = makeSystemInfo({ lan_enabled: false });
    renderModal({ systemInfo: sys });

    const qr = await screen.findByRole("img", { name: /QR/i });
    expect(qr).toHaveAttribute("src", QR_IMAGE);
    expect(qrSpy).toHaveBeenCalledWith({
      content: `http://${sys.ip}:${window.location.port}`,
    });
  });

  it("degrades to an inline message when QR generation fails", async () => {
    qrSpy.mockRejectedValue(new Error("qr boom"));
    renderModal();

    expect(await screen.findByText(/qr boom/)).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /QR/i })).toBeNull();
    expect(screen.getByRole("button", { name: "Enable LAN" })).toBeEnabled();
  });
});

describe("LanModal — enable flow (stays open)", () => {
  it("runs in place and flips the modal to the enabled state", async () => {
    const sys = makeSystemInfo({ lan_enabled: true });
    const gate = deferred<SystemInfo | null>();
    waitSpy.mockReturnValue(gate.promise);
    const props = renderModal({ systemInfo: makeSystemInfo() });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Enable LAN" }));

    // No dialog-closes-first: the modal stays up, flow inside.
    expect(props.onClose).not.toHaveBeenCalled();
    // In-flight progress is announced from the footer's left slot.
    expect(screen.getByRole("status")).toHaveTextContent("Updating the LAN binding…");
    expect(screen.getByRole("button", { name: "Enable LAN" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();

    gate.resolve(sys);
    await waitFor(() => expect(props.onConfirmed).toHaveBeenCalledWith(sys));
    // App answers onConfirmed by updating systemInfo → the modal reflects it.
    props.rerender(<LanModal {...props} systemInfo={sys} />);
    expect(
      screen.getByText("LAN Access — Reachable on this network.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disable LAN" })).toBeEnabled();
    // Inline outcome replaces toasts while the modal is open.
    expect(props.showToast).not.toHaveBeenCalled();
  });

  it("observed disagreement shows the failure inline, silent while open", async () => {
    const stale = makeSystemInfo({ lan_enabled: false });
    waitSpy.mockResolvedValue(stale);
    const user = userEvent.setup();
    const props = renderModal({ systemInfo: makeSystemInfo() });

    await user.click(screen.getByRole("button", { name: "Enable LAN" }));

    expect(await screen.findByText(/previous address is still active/)).toBeInTheDocument();
    expect(props.onConfirmed).toHaveBeenCalledWith(stale);
    expect(props.showToast).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Enable LAN" })).toBeEnabled();
  });

  it("rejected bind shows the failure inline and refetches system info", async () => {
    setLanSpy.mockRejectedValue(new Error("boom"));
    const refetched = makeSystemInfo({ lan_enabled: false });
    fetchSpy.mockResolvedValue(refetched);
    const user = userEvent.setup();
    const props = renderModal({ systemInfo: makeSystemInfo() });

    await user.click(screen.getByRole("button", { name: "Enable LAN" }));

    expect(await screen.findByText(/Failed to update LAN binding: boom/)).toBeInTheDocument();
    await waitFor(() => expect(props.onConfirmed).toHaveBeenCalledWith(refetched));
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});

describe("LanModal — disable flow (same UX, issue #197 override)", () => {
  it("runs in place and flips the modal back to the restricted state", async () => {
    const sys = makeSystemInfo({ lan_enabled: false });
    const gate = deferred<SystemInfo | null>();
    waitSpy.mockReturnValue(gate.promise);
    const props = renderModal({ systemInfo: makeSystemInfo({ lan_enabled: true }) });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Disable LAN" }));

    expect(props.onClose).not.toHaveBeenCalled();
    expect(setLanSpy).toHaveBeenCalledWith(false);
    expect(screen.getByText("Updating the LAN binding…")).toBeInTheDocument();

    gate.resolve(sys);
    await waitFor(() => expect(props.onConfirmed).toHaveBeenCalledWith(sys));
    props.rerender(<LanModal {...props} systemInfo={sys} />);
    expect(
      screen.getByText("LAN Access — Restricted to the host machine.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enable LAN" })).toBeEnabled();
    expect(props.showToast).not.toHaveBeenCalled();
  });

  it("observed disagreement shows the failure inline", async () => {
    const stale = makeSystemInfo({ lan_enabled: true });
    waitSpy.mockResolvedValue(stale);
    const user = userEvent.setup();
    const props = renderModal({ systemInfo: makeSystemInfo({ lan_enabled: true }) });

    await user.click(screen.getByRole("button", { name: "Disable LAN" }));

    expect(await screen.findByText(/previous address is still active/)).toBeInTheDocument();
    expect(props.onConfirmed).toHaveBeenCalledWith(stale);
    expect(props.showToast).not.toHaveBeenCalled();
  });
});

describe("LanModal — closing", () => {
  it("❌ and Escape both close the modal", async () => {
    const user = userEvent.setup();
    const props = renderModal();

    const cancel = screen.getByRole("button", { name: "Cancel" });
    await waitFor(() => expect(cancel).toHaveFocus());
    await user.keyboard("{Escape}");
    expect(props.onClose).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(props.onClose).toHaveBeenCalledTimes(2);
  });

  it("cancel closes without touching the API when idle", async () => {
    const user = userEvent.setup();
    const props = renderModal();

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(props.onClose).toHaveBeenCalledTimes(1);
    expect(setLanSpy).not.toHaveBeenCalled();
    expect(waitSpy).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("cancel mid-flow falls back to toasts when the flow completes", async () => {
    const sys = makeSystemInfo({ lan_enabled: true });
    const gate = deferred<SystemInfo | null>();
    waitSpy.mockReturnValue(gate.promise);
    const props = renderModal({ systemInfo: makeSystemInfo() });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Enable LAN" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(props.onClose).toHaveBeenCalledTimes(1);
    // App answers onClose by closing: the modal unmounts its content while
    // the flow keeps running (same component instance, open false).
    props.rerender(<LanModal {...props} open={false} />);

    gate.resolve(sys);
    await waitFor(() => expect(props.onConfirmed).toHaveBeenCalledWith(sys));
    expect(props.showToast).toHaveBeenCalledWith(
      "ProFiles is now reachable on the local network.",
      "info"
    );
  });
});
