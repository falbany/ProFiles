// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StatusBar } from "./StatusBar";
import type { SystemInfo } from "../api/types";

const systemInfo: SystemInfo = {
  hostname: "st-465",
  ip: "172.16.41.65",
  username: "operator",
  os_release: "Windows 11",
  lan_enabled: false,
};

/** Build minimal StatusBar props for each scenario. */
function baseProps() {
  return {
    systemInfo,
    fileCount: 1,
    theme: "dark" as const,
    onToggleTheme: vi.fn(),
    onOpenLog: vi.fn(),
    onOpenConfig: vi.fn(),
    onShowShortcuts: vi.fn(),
  };
}

afterEach(() => cleanup());

describe("StatusBar LAN toggle", () => {
  it("shows the LAN switch and forwards the requested next state", async () => {
    const onToggleLan = vi.fn();
    render(<StatusBar {...baseProps()} lanEnabled={false} onToggleLan={onToggleLan} />);
    const sw = screen.getByRole("button", { name: /lan/i });
    expect(sw).not.toBeDisabled();
    await userEvent.click(sw);
    expect(onToggleLan).toHaveBeenCalledWith(true);
  });

  it("reflects the enabled state via aria-pressed", () => {
    render(<StatusBar {...baseProps()} lanEnabled={true} onToggleLan={vi.fn()} />);
    expect(screen.getByRole("button", { name: /lan/i })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  it("disables the switch while the bind state is unknown", () => {
    render(<StatusBar {...baseProps()} lanEnabled={null} onToggleLan={vi.fn()} />);
    expect(screen.getByRole("button", { name: /lan/i })).toBeDisabled();
  });

  it("renders no LAN switch without a toggle handler", () => {
    render(<StatusBar {...baseProps()} lanEnabled={false} />);
    expect(screen.queryByRole("button", { name: /lan/i })).toBeNull();
  });
});
