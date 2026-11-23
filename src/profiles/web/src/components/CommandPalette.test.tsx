// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CommandPalette } from "./CommandPalette";
import type { Command } from "../utils/commands";
import type { ScannedFileItem } from "../api/types";

/**
 * Component tests for the command palette (issue #224).
 */

function command(id: string, title: string, extra: Partial<Command> = {}): Command {
  return { id, title, group: "view", enabled: true, run: vi.fn(), ...extra };
}

function makeFile(filename: string, relPath: string = filename): ScannedFileItem {
  return { column_values: {}, filename, rel_path: relPath, path: `/data/${relPath}` };
}

/** Fresh spies for every test. */
function makeCommands(): Command[] {
  return [
    command("scan.run", "Rescan the file list", { group: "file-list", keys: [{ key: "F5" }] }),
    command("file.copyPath", "Copy full path", {
      group: "selection",
      enabled: false,
      disabledReason: "Select a file first",
    }),
    command("view.theme", "Switch theme (dark / light)", {
      keys: [{ key: "t", ctrl: true, shift: true }],
    }),
    command("list.next", "Move to the next file", { palette: false }),
  ];
}

const FILES = [makeFile("report_final.log", "logs/report_final.log"), makeFile("readme.md")];

function renderPalette(
  options: { isOpen?: boolean; recentIds?: string[]; commands?: Command[]; files?: ScannedFileItem[] } = {},
) {
  const commands = options.commands ?? makeCommands();
  const props = {
    onClose: vi.fn(),
    commands,
    files: options.files ?? FILES,
    onOpenFile: vi.fn(),
    recentIds: options.recentIds ?? [],
    onCommandUsed: vi.fn(),
  };
  const view = render(<CommandPalette {...props} isOpen={options.isOpen ?? true} />);
  return { ...props, commands, ...view };
}

const searchField = () => screen.getByRole("combobox", { name: "Search commands and files" });

afterEach(() => {
  cleanup();
});

describe("CommandPalette", () => {
  it("renders nothing while closed", () => {
    const { container } = renderPalette({ isOpen: false });
    expect(container.firstChild).toBeNull();
  });

  it("focuses the search field on open and lists the palette commands by group", async () => {
    renderPalette();

    await waitFor(() => expect(searchField()).toHaveFocus());
    expect(screen.getByRole("dialog", { name: "Command palette" })).toBeInTheDocument();

    expect(screen.getByRole("group", { name: "File list" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Selected file" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "View" })).toBeInTheDocument();

    // Key-only commands stay out; files are only searched, never listed.
    expect(screen.queryByText("Move to the next file")).toBeNull();
    expect(screen.queryByRole("group", { name: "Files" })).toBeNull();

    // Every listed command is an option of one listbox.
    expect(screen.getAllByRole("option")).toHaveLength(3);
    expect(screen.getByRole("listbox", { name: "Results" })).toBeInTheDocument();
  });

  it("shows the key binding next to each bound command", () => {
    renderPalette();

    expect(screen.getByText("F5")).toBeInTheDocument();
    expect(screen.getByText("Ctrl + Shift + T")).toBeInTheDocument();
  });

  it("lists recent commands first, without repeating them", () => {
    renderPalette({ recentIds: ["view.theme"] });

    const recent = screen.getByRole("group", { name: "Recent" });
    expect(recent).toBeInTheDocument();
    expect(recent.querySelectorAll('[role="option"]')).toHaveLength(1);
    // Once in "Recent", no longer under its own group.
    expect(screen.getAllByText("Switch theme (dark / light)")).toHaveLength(1);
    expect(screen.getAllByRole("option")[0]).toHaveTextContent("Switch theme");
  });

  it("narrows the commands and lists matching files as the query is typed", async () => {
    const user = userEvent.setup();
    renderPalette();

    await user.type(searchField(), "cop");

    expect(screen.getByRole("option", { name: /Copy full path/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Switch theme/ })).toBeNull();

    await user.clear(searchField());
    await user.type(searchField(), "report");

    const files = screen.getByRole("group", { name: "Files" });
    expect(files).toHaveTextContent("report_final.log");
    expect(files).not.toHaveTextContent("readme.md");
    // The relative folder is shown beside the name.
    expect(files).toHaveTextContent("logs");
  });

  it("puts the files above a weak command match when the query names a file", async () => {
    const user = userEvent.setup();
    // A scattered subsequence of this command's keywords — a real, but
    // incidental, match for "readme". Enter must open the file, not run it.
    const terminal = command("file.openTerminal", "Open a terminal in the containing folder", {
      keywords: ["shell", "cmd", "command line"],
    });
    const { onOpenFile } = renderPalette({ commands: [terminal] });

    await user.type(searchField(), "readme");
    const groups = screen.getAllByRole("group").map((group) => group.getAttribute("aria-label"));
    expect(groups).toEqual(["Files", "Commands"]);

    await user.keyboard("{Enter}");
    expect(onOpenFile).toHaveBeenCalledWith(FILES[1]);
    expect(terminal.run).not.toHaveBeenCalled();
  });

  it("keeps the commands above the files when a command is the better match", async () => {
    const user = userEvent.setup();
    // "log" only grazes "catalog.md" (three trailing letters), while it
    // names the command — the command leads.
    const logViewer = command("view.logViewer", "Open the log viewer");
    renderPalette({ commands: [logViewer], files: [makeFile("catalog.md")] });

    await user.type(searchField(), "log");

    const groups = screen.getAllByRole("group").map((group) => group.getAttribute("aria-label"));
    expect(groups).toEqual(["Commands", "Files"]);
  });

  it("runs the active command, records it, and closes BEFORE running it", async () => {
    const user = userEvent.setup();
    // Closing restores focus to the element focused before the palette
    // opened; a command that moves focus or opens a dialog must land after
    // that restore, or it is undone. The call order pins the contract.
    const order: string[] = [];
    const theme = command("view.theme", "Switch theme (dark / light)", {
      run: vi.fn(() => order.push("run")),
    });
    const { onClose, onCommandUsed } = renderPalette({
      commands: [theme],
    });
    const onCloseSpy = onClose as ReturnType<typeof vi.fn>;
    onCloseSpy.mockImplementation(() => order.push("close"));

    await user.type(searchField(), "theme");
    await user.keyboard("{Enter}");

    expect(onCommandUsed).toHaveBeenCalledWith("view.theme");
    await waitFor(() => expect(order).toEqual(["close", "run"]));
  });

  it("opens a file from the quick-open list with Enter", async () => {
    const user = userEvent.setup();
    const { onClose, onOpenFile } = renderPalette();

    await user.type(searchField(), "report");
    await user.keyboard("{Enter}");

    expect(onOpenFile).toHaveBeenCalledWith(FILES[0]);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("moves the active row with the arrow keys and skips disabled commands", async () => {
    const user = userEvent.setup();
    renderPalette();
    await waitFor(() => expect(searchField()).toHaveFocus());

    const scan = screen.getByRole("option", { name: /Rescan the file list/ });
    const theme = screen.getByRole("option", { name: /Switch theme/ });
    expect(scan).toHaveAttribute("aria-selected", "true");
    expect(searchField()).toHaveAttribute("aria-activedescendant", scan.id);

    // Copy full path sits between the two and is disabled: skipped over.
    await user.keyboard("{ArrowDown}");
    expect(theme).toHaveAttribute("aria-selected", "true");
    expect(searchField()).toHaveAttribute("aria-activedescendant", theme.id);

    // Clamped at both ends.
    await user.keyboard("{ArrowDown}");
    expect(theme).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(scan).toHaveAttribute("aria-selected", "true");
  });

  it("explains a disabled command and refuses to run it", async () => {
    const user = userEvent.setup();
    const { onClose, commands } = renderPalette();
    const copyPath = commands.find((c) => c.id === "file.copyPath");

    const option = screen.getByRole("option", { name: /Copy full path/ });
    expect(option).toHaveAttribute("aria-disabled", "true");
    expect(option).toHaveTextContent("Select a file first");

    await user.click(option);
    expect(copyPath?.run).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes on Escape without letting the key reach the window", () => {
    const { onClose } = renderPalette();
    const windowListener = vi.fn();
    window.addEventListener("keydown", windowListener);

    fireEvent.keyDown(searchField(), { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(windowListener).not.toHaveBeenCalled();
    window.removeEventListener("keydown", windowListener);
  });

  it("closes on a backdrop click, but not on a click inside the panel", async () => {
    const user = userEvent.setup();
    const { onClose } = renderPalette();
    const dialog = screen.getByRole("dialog", { name: "Command palette" });
    const backdrop = dialog.parentElement as HTMLElement;

    // Clicking the search field, a section label or empty panel space does
    // not dismiss the palette.
    await user.click(searchField());
    await user.click(screen.getByText("File list"));
    await user.click(dialog);
    expect(onClose).not.toHaveBeenCalled();

    await user.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes from its close button", async () => {
    const user = userEvent.setup();
    const { onClose } = renderPalette();

    await user.click(screen.getByRole("button", { name: "Close the command palette" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("runs a command from a click", async () => {
    const user = userEvent.setup();
    const { onClose, onCommandUsed, commands } = renderPalette();
    const scan = commands.find((c) => c.id === "scan.run");

    await user.click(screen.getByRole("option", { name: /Rescan the file list/ }));

    expect(onCommandUsed).toHaveBeenCalledWith("scan.run");
    expect(onClose).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(scan?.run).toHaveBeenCalledTimes(1));
  });

  it("shows an empty state when nothing matches", async () => {
    const user = userEvent.setup();
    renderPalette();

    await user.type(searchField(), "zzzz");

    expect(screen.getByText(/No command or file matches/)).toBeInTheDocument();
    expect(screen.queryAllByRole("option")).toHaveLength(0);
    await user.keyboard("{Enter}");
  });

  it("forgets the query when reopened", async () => {
    const user = userEvent.setup();
    const props = {
      onClose: vi.fn(),
      commands: makeCommands(),
      files: FILES,
      onOpenFile: vi.fn(),
      recentIds: [],
      onCommandUsed: vi.fn(),
    };
    const { rerender } = render(<CommandPalette {...props} isOpen />);

    await user.type(searchField(), "theme");
    rerender(<CommandPalette {...props} isOpen={false} />);
    rerender(<CommandPalette {...props} isOpen />);

    expect(searchField()).toHaveValue("");
  });

  it("restores focus to the element focused before it opened", async () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();

    const props = {
      onClose: vi.fn(),
      commands: makeCommands(),
      files: FILES,
      onOpenFile: vi.fn(),
      recentIds: [],
      onCommandUsed: vi.fn(),
    };
    const { rerender } = render(<CommandPalette {...props} isOpen />);
    await waitFor(() => expect(searchField()).toHaveFocus());

    rerender(<CommandPalette {...props} isOpen={false} />);
    expect(trigger).toHaveFocus();
    trigger.remove();
  });
});
