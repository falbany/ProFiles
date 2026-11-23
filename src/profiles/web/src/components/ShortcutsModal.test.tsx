// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ShortcutsModal } from "./ShortcutsModal";
import type { Command } from "../utils/commands";

/**
 * The shortcuts sheet is the command registry (issue #224): every keyed
 * command is listed with the binding the dispatcher actually matches on.
 */

function command(id: string, title: string, extra: Partial<Command> = {}): Command {
  return { id, title, group: "view", enabled: true, run: vi.fn(), ...extra };
}

const commands: Command[] = [
  command("scan.run", "Rescan the file list", { group: "file-list", keys: [{ key: "F5" }] }),
  command("file.copyPath", "Copy full path", { group: "selection" }), // no key → not a shortcut
  command("view.logViewer", "Open the log viewer", {
    keys: [{ key: "l", ctrl: true, shift: true }],
  }),
  command("focus.filter", "Focus the filter field", {
    group: "focus",
    keys: [{ key: "f", ctrl: true }],
    // Listed even when it cannot run right now: the shortcut still exists.
    enabled: false,
  }),
];

function renderModal(isOpen = true) {
  const onClose = vi.fn();
  render(<ShortcutsModal isOpen={isOpen} onClose={onClose} commands={commands} />);
  return { onClose };
}

afterEach(() => cleanup());

describe("ShortcutsModal", () => {
  it("renders nothing while closed", () => {
    renderModal(false);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("lists every keyed command under its group, and only those", () => {
    renderModal();

    expect(screen.getByText("Rescan the file list")).toBeInTheDocument();
    expect(screen.getByText("Open the log viewer")).toBeInTheDocument();
    expect(screen.getByText("Focus the filter field")).toBeInTheDocument();
    expect(screen.queryByText("Copy full path")).toBeNull();

    expect(screen.getByRole("region", { name: "File list" })).toHaveTextContent("F5");
    expect(screen.getByRole("region", { name: "View" })).toHaveTextContent("Ctrl + Shift + L");
    expect(screen.getByRole("region", { name: "Focus" })).toHaveTextContent("Ctrl + F");
  });

  it("formats the bindings the way the dispatcher matches them", () => {
    renderModal();

    // Shift is pinned on L, so it is shown; it is not part of F5's rule.
    expect(screen.getByText("Ctrl + Shift + L")).toBeInTheDocument();
    expect(screen.getByText("F5")).toBeInTheDocument();
  });

  it("keeps the keys that belong to dialogs, not to commands", () => {
    renderModal();

    const dialogs = screen.getByRole("region", { name: "In dialogs" });
    expect(dialogs).toHaveTextContent("Y / S / N");
    expect(dialogs).toHaveTextContent("Confirm active workflow prompt (prompt open)");
    expect(dialogs).toHaveTextContent("Close dialogs / context menu");
  });

  it("closes with its button and with Escape", async () => {
    const user = userEvent.setup();
    const { onClose } = renderModal();

    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(screen.getByRole("dialog", { name: "Keyboard Shortcuts" }), { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
