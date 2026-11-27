// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoadConfigModal } from "./LoadConfigModal";
import { browseForConfigFiles, createConfigFile, loadConfigFile } from "../api/client";
import type { AppConfigData, BrowseResult } from "../api/types";

/**
 * Unit tests for the config picker's explicit mode (issue #192): the
 * caller tells the component WHY it opened — an explicit load action or
 * the first-run create prompt — instead of the component inferring it
 * from the global config state (`configExists === false`).
 */

vi.mock("../api/client", () => ({
  browseForConfigFiles: vi.fn(),
  createConfigFile: vi.fn(),
  loadConfigFile: vi.fn(),
}));

const browseSpy = vi.mocked(browseForConfigFiles);
const createSpy = vi.mocked(createConfigFile);
const loadSpy = vi.mocked(loadConfigFile);

function makeBrowse(overrides: Partial<BrowseResult> = {}): BrowseResult {
  return {
    current_path: "/home/user/.profiles",
    parent_path: "/home/user",
    items: [
      {
        name: "other.profiles",
        path: "/home/user/.profiles/other.profiles",
        is_dir: false,
        is_config: true,
      },
    ],
    ...overrides,
  };
}

function makeLoadedConfig(overrides: Partial<AppConfigData> = {}): AppConfigData {
  return {
    title: "other",
    release: "1.0",
    search_dir: "/home/user/data",
    max_search_depth: 10,
    theme: "dark",
    directories: ["/home/user/data"],
    extensions: [".mttl"],
    filters: [],
    active_directory: "/home/user/data",
    config_path: "/home/user/.profiles/other.profiles",
    config_exists: true,
    column_headers: [],
    column_names: [],
    row_colors: [],
    ...overrides,
  };
}

function renderModal(overrides: { mode?: "load" | "create"; isOpen?: boolean } = {}) {
  const onClose = vi.fn();
  const onLoaded = vi.fn();
  render(
    <LoadConfigModal
      isOpen={overrides.isOpen ?? true}
      mode={overrides.mode ?? "load"}
      activeConfigPath="/home/user/.profiles/.profiles"
      onClose={onClose}
      onLoaded={onLoaded}
    />,
  );
  return { onClose, onLoaded };
}

beforeEach(() => {
  vi.clearAllMocks();
  browseSpy.mockResolvedValue(makeBrowse());
});

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});

describe("LoadConfigModal modes (issue #192)", () => {
  it("mode=create renders the create title, banner and primary button", async () => {
    renderModal({ mode: "create" });

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Create configuration" })).toBeTruthy();
    expect(
      within(dialog).getByText(/no configuration file was found/i),
    ).toBeTruthy();
    expect(
      await within(dialog).findByRole("button", { name: /create configuration/i }),
    ).toBeTruthy();
    expect(browseSpy).toHaveBeenCalled();
  });

  it("mode=create creates the config in the typed directory", async () => {
    createSpy.mockResolvedValue(makeLoadedConfig());
    const { onLoaded, onClose } = renderModal({ mode: "create" });

    const dialog = await screen.findByRole("dialog");
    await userEvent.setup().click(
      await within(dialog).findByRole("button", { name: /create configuration/i }),
    );

    await waitFor(() => expect(createSpy).toHaveBeenCalledWith("/home/user/.profiles"));
    await waitFor(() => expect(onLoaded).toHaveBeenCalledWith(makeLoadedConfig()));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("mode=load renders the load title and primary button without the create banner", async () => {
    renderModal({ mode: "load" });

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Load configuration" })).toBeTruthy();
    expect(within(dialog).queryByText(/no configuration file was found/i)).toBeNull();
    expect(
      await within(dialog).findByRole("button", { name: /^load configuration$/i }),
    ).toBeTruthy();
  });

  it("mode=load keeps the load button disabled until a config is selected", async () => {
    renderModal({ mode: "load" });

    const loadButton = () =>
      screen.getByRole("button", { name: /^load configuration$/i }) as HTMLButtonElement;
    await waitFor(() => expect(loadButton()).toBeTruthy());
    expect(loadButton().disabled).toBe(true);

    // Selecting a configuration file enables the load action.
    await userEvent.setup().click(screen.getByRole("button", { name: /other\.profiles/i }));
    expect(loadButton().disabled).toBe(false);
  });

  it("mode=load loads the selected config file", async () => {
    loadSpy.mockResolvedValue(makeLoadedConfig());
    const { onLoaded, onClose } = renderModal({ mode: "load" });

    await userEvent
      .setup()
      .click(await screen.findByRole("button", { name: /other\.profiles/i }));
    await userEvent.setup().click(screen.getByRole("button", { name: /^load configuration$/i }));

    await waitFor(() => expect(loadSpy).toHaveBeenCalledWith("/home/user/.profiles/other.profiles"));
    await waitFor(() => expect(onLoaded).toHaveBeenCalledWith(makeLoadedConfig()));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("closed modal renders nothing", () => {
    renderModal({ isOpen: false });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
