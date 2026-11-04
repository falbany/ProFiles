// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SaveAsDialog } from "./SaveAsDialog";
import { browseDirectory } from "../api/client";
import type { BrowseResult } from "../api/types";

vi.mock("../api/client", () => ({
  browseDirectory: vi.fn(),
}));

const browseSpy = vi.mocked(browseDirectory);

function makeBrowse(overrides: Partial<BrowseResult> = {}): BrowseResult {
  return {
    current_path: "/home/user/configs",
    parent_path: "/home/user",
    items: [
      { name: "archive", path: "/home/user/configs/archive", is_dir: true },
      { name: "machines", path: "/home/user/configs/machines", is_dir: true },
      {
        name: "other.profiles",
        path: "/home/user/configs/other.profiles",
        is_dir: false,
        is_config: true,
      },
    ],
    ...overrides,
  };
}

function renderDialog(overrides: { open?: boolean } = {}) {
  const onCancel = vi.fn();
  const onConfirm = vi.fn();
  render(
    <SaveAsDialog
      open={overrides.open ?? true}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />,
  );
  return { onCancel, onConfirm };
}

beforeEach(() => {
  vi.clearAllMocks();
  browseSpy.mockResolvedValue(makeBrowse());
});

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});

describe("SaveAsDialog", () => {
  it("test_lists_directories_via_browse", async () => {
    const user = userEvent.setup();
    renderDialog();

    // Opening browses from the home root (no initial path pinned in props).
    await waitFor(() => expect(browseSpy).toHaveBeenCalledWith(""));
    const dialog = await screen.findByRole("dialog", { name: /save configuration as/i });
    await screen.findByRole("button", { name: /machines/i });
    expect(dialog.textContent).toContain("archive");
    expect(dialog.textContent).toContain("/home/user/configs");

    // Clicking a listed subdirectory navigates into it.
    await user.click(screen.getByRole("button", { name: /machines/i }));
    await waitFor(() =>
      expect(browseSpy).toHaveBeenCalledWith("/home/user/configs/machines"),
    );

    // The listing offers the parent directory for going back up.
    await waitFor(() => {
      expect(
        within(dialog).getByRole("button", { name: /parent directory/i }),
      ).toBeTruthy();
    });
  });

  it("test_filename_extension_restricted", async () => {
    const user = userEvent.setup();
    const { onConfirm } = renderDialog();
    const input = await screen.findByLabelText(/file name/i);

    // A bare name is normalized to the .profiles extension on confirm.
    await user.type(input, "myconfig");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));
    expect(onConfirm.mock.calls[0][0]).toEqual({
      filename: "myconfig.profiles",
      directory: "/home/user/configs",
      overwrite: false,
    });

    // A non-whitelisted extension is rejected inline, with no save call.
    await user.clear(input);
    await user.type(input, "report.txt");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/\.profiles/);
    expect(onConfirm).toHaveBeenCalledTimes(1);

    // An already-whitelisted double extension is kept verbatim.
    await user.clear(input);
    await user.type(input, "backup.profiles.yaml");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(2));
    expect(onConfirm.mock.calls[1][0].filename).toBe("backup.profiles.yaml");

    // The server whitelist is case-insensitive: an uppercase variant is
    // accepted and sent verbatim (the server handles its own casing).
    await user.clear(input);
    await user.type(input, "BACKUP.PROFILES");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(3));
    expect(onConfirm.mock.calls[2][0].filename).toBe("BACKUP.PROFILES");

    // An empty stem (bare ".profiles") is rejected client-side…
    await user.clear(input);
    await user.type(input, ".profiles");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await screen.findByRole("alert");
    expect(onConfirm).toHaveBeenCalledTimes(3);

    // …as is a stray space before the extension.
    await user.clear(input);
    await user.type(input, "notes .profiles");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await screen.findByRole("alert");
    expect(onConfirm).toHaveBeenCalledTimes(3);
  });

  it("test_replace_prompt_only_for_browsed_directory", async () => {
    browseSpy.mockResolvedValue(makeBrowse());
    const user = userEvent.setup();
    const { onConfirm } = renderDialog();
    await screen.findByRole("dialog", { name: /save configuration as/i });
    await screen.findByRole("button", { name: /machines/i });

    // Type a Location without navigating to it: its contents are unknown,
    // so the overwrite check must not lean on the browsed listing.
    await user.clear(screen.getByLabelText(/location/i));
    await user.type(screen.getByLabelText(/location/i), "/elsewhere");
    await user.type(screen.getByLabelText(/file name/i), "other.profiles");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    // No Replace prompt — and overwrite:false, leaving the server's 409
    // guard to answer for the unbrowsed directory.
    expect(screen.queryByRole("dialog", { name: /replace configuration\?/i })).toBeNull();
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));
    expect(onConfirm.mock.calls[0][0]).toEqual({
      filename: "other.profiles",
      directory: "/elsewhere",
      overwrite: false,
    });
  });

  it("test_save_disabled_while_browse_unavailable", async () => {
    browseSpy.mockRejectedValue(new Error("Navigation failed"));
    const user = userEvent.setup();
    const { onConfirm } = renderDialog();

    // Browse failure surfaces as an error state with a retry…
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/navigation failed/i);
    // …and Save stays disabled even with a well-formed filename, since
    // there is no listing to name a target directory from.
    await user.type(screen.getByLabelText(/file name/i), "machine.profiles");
    expect(screen.getByRole("button", { name: /^save$/i })).toBeDisabled();

    // A successful retry restores the listing and re-enables Save.
    browseSpy.mockResolvedValue(makeBrowse());
    await user.click(screen.getByRole("button", { name: /retry/i }));
    await screen.findByRole("button", { name: /machines/i });
    expect(screen.getByRole("button", { name: /^save$/i })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));
    expect(onConfirm.mock.calls[0][0].directory).toBe("/home/user/configs");
  });

  it("test_overwrite_confirmation", async () => {
    browseSpy.mockResolvedValue(makeBrowse());
    const user = userEvent.setup();
    const { onConfirm } = renderDialog();
    const input = await screen.findByLabelText(/file name/i);

    // Targeting an existing file asks "Replace?" before confirming…
    await user.type(input, "other.profiles");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    const replace = screen.getByRole("dialog", { name: /replace configuration\?/i });
    expect(replace).toBeTruthy();
    expect(onConfirm).not.toHaveBeenCalled();

    // …and declining keeps the target dialog open with no save call.
    await user.click(within(replace).getByRole("button", { name: /keep existing/i }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog", { name: /replace configuration\?/i })).toBeNull();

    // A fresh name goes through without the replace gate (overwrite: false).
    await user.clear(input);
    await user.type(input, "fresh.profiles");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));
    expect(onConfirm.mock.calls[0][0]).toEqual({
      filename: "fresh.profiles",
      directory: "/home/user/configs",
      overwrite: false,
    });

    // Forcing the replace goes through with overwrite: true.
    await user.clear(input);
    await user.type(input, "other.profiles");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    const replaceAgain = screen.getByRole("dialog", { name: /replace configuration\?/i });
    await user.click(within(replaceAgain).getByRole("button", { name: /^replace$/i }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(2));
    expect(onConfirm.mock.calls[1][0]).toEqual({
      filename: "other.profiles",
      directory: "/home/user/configs",
      overwrite: true,
    });
  });

  it("test_cancel", async () => {
    const user = userEvent.setup();
    const { onCancel, onConfirm } = renderDialog();
    await screen.findByRole("dialog", { name: /save configuration as/i });

    await user.click(screen.getByRole("button", { name: /^cancel$/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();

    // Escape shares the same cancel path.
    await user.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledTimes(2);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
