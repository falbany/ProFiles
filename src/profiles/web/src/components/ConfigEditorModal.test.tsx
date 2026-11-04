// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { EditorView } from "codemirror";
import { ConfigEditorModal } from "./ConfigEditorModal";
import {
  ApiError,
  browseDirectory,
  fetchConfigContent,
  fetchConfigTemplate,
  loadConfigContent,
  openConfigFile,
  saveConfigFile,
  saveConfigFileAs,
  validateConfigContent,
} from "../api/client";
import type {
  AppConfigData,
  BrowseResult,
  ConfigContentData,
  ValidationIssue,
} from "../api/types";
import type { ConfigSaveResult } from "../api/client";

vi.mock("../api/client", async (importOriginal) => {
  // Keep the real ApiError: the staleness-conflict flow (issue #116)
  // branches on `err instanceof ApiError && err.status === 409`.
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    fetchConfigContent: vi.fn(),
    openConfigFile: vi.fn(),
    fetchConfigTemplate: vi.fn(),
    validateConfigContent: vi.fn(),
    loadConfigContent: vi.fn(),
    saveConfigFile: vi.fn(),
    saveConfigFileAs: vi.fn(),
    browseDirectory: vi.fn(),
  };
});

// jsdom gap (not a CodeMirror mock): the view's measurement code calls
// Range geometry APIs that jsdom does not implement. Empty geometry is
// enough — the editor never becomes visible under jsdom, and every other
// geometry API it uses exists (Element.getClientRects, DOMRect).
const rangeProto = Range.prototype as unknown as {
  getClientRects?: () => DOMRect[];
  getBoundingClientRect?: () => DOMRect;
};
rangeProto.getClientRects ??= () => [];
rangeProto.getBoundingClientRect ??= () => new DOMRect(0, 0, 0, 0);

const fetchContentSpy = vi.mocked(fetchConfigContent);
const openInOSSpy = vi.mocked(openConfigFile);
const templateSpy = vi.mocked(fetchConfigTemplate);
const validateSpy = vi.mocked(validateConfigContent);
const loadContentSpy = vi.mocked(loadConfigContent);
const saveSpy = vi.mocked(saveConfigFile);
const saveAsSpy = vi.mocked(saveConfigFileAs);
const browseSpy = vi.mocked(browseDirectory);

const SAMPLE_YAML = 'release: "1.0"\nsearch_dir: "C:/data"\n';
/** Starter template served with CRLF endings — realistic for Windows hosts. */
const TEMPLATE_YAML = 'release: "2.0"\r\nsearch_dir: "D:/data"\r\n';
const TEMPLATE_YAML_LF = 'release: "2.0"\nsearch_dir: "D:/data"\n';

function makeContent(overrides: Partial<ConfigContentData> = {}): ConfigContentData {
  return {
    filename: "machine.profiles",
    content: SAMPLE_YAML,
    config_path: "/home/user/.profiles/machine.profiles",
    session_trial: false,
    ...overrides,
  };
}

function makeAppConfig(): AppConfigData {
  return {
    title: "machine",
    release: "1.0",
    search_dir: "C:/data",
    recursive_search: false,
    theme: "dark",
    directories: [],
    extensions: [".mttl"],
    filters: [],
    active_directory: "C:/data",
    config_path: "/home/user/.profiles/machine.profiles",
    config_exists: true,
    column_headers: [],
    column_names: [],
    row_colors: [],
  };
}

/** Successful save/save-as payload: applied config + written-text hash. */
function makeSaveResult(config: AppConfigData = makeAppConfig(), contentHash = "written-hash"): ConfigSaveResult {
  return { config, contentHash };
}

/** Listing served by /api/fs/browse for the Save As dialog. */
function makeBrowseResult(overrides: Partial<BrowseResult> = {}): BrowseResult {
  return {
    current_path: "/home/user/configs",
    parent_path: "/home/user",
    items: [
      { name: "other.profiles", path: "/home/user/configs/other.profiles", is_dir: false, is_config: true },
    ],
    ...overrides,
  };
}

function renderModal(
  overrides: {
    open?: boolean;
    /** Issue #101: injected picker-raiser spy. */
    onLoadConfig?: () => void;
    /** Issue #101: reload key that must re-run the load-on-open fetch. */
    reloadKey?: number,
  } = {},
) {
  const onClose = vi.fn();
  const onApplied = vi.fn();
  const initialProps = {
    open: overrides.open ?? true,
    onClose,
    onApplied,
    onLoadConfig: overrides.onLoadConfig,
    reloadKey: overrides.reloadKey,
  };
  const view = render(<ConfigEditorModal {...initialProps} />);
  return {
    onClose,
    onApplied,
    /** Re-render with changed props (issue #101 reload / open cycling). */
    rerenderWith: (next: { open?: boolean; reloadKey?: number }) => {
      view.rerender(<ConfigEditorModal {...initialProps} {...next} />);
    },
  };
}

/**
 * Wait for the CodeMirror view to be mounted inside the editor dialog and
 * return it. Uses the public `EditorView.findFromDOM` seam — the real
 * editor instance, no mocks.
 */
async function readyEditorView(): Promise<EditorView> {
  const dialog = await screen.findByRole("dialog", { name: /configuration editor/i });
  let view: EditorView | null = null;
  await waitFor(() => {
    const editorDom = dialog.querySelector(".cm-editor");
    expect(editorDom).toBeTruthy();
    view = EditorView.findFromDOM(editorDom as HTMLElement) ?? null;
    expect(view).not.toBeNull();
  });
  return view as unknown as EditorView;
}

beforeEach(() => {
  vi.clearAllMocks();
  fetchContentSpy.mockResolvedValue(makeContent());
});

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});

describe("ConfigEditorModal", () => {
  it("test_renders_fullscreen_overlay_when_open", async () => {
    // Closed: nothing renders at all.
    const closed = render(<ConfigEditorModal open={false} onClose={vi.fn()} />);
    expect(screen.queryByRole("dialog")).toBeNull();
    closed.unmount();

    renderModal();
    const dialog = await screen.findByRole("dialog", { name: /configuration editor/i });
    // Full-screen overlay pinned to the shared modal z-scale token layer
    // (issue #59 scale) — same pattern as the barcode modals.
    expect(dialog.className).toContain("fixed inset-0");
    expect(dialog.className).toContain("z-[var(--z-modal)]");
  });

  it("test_loads_content_on_open", async () => {
    fetchContentSpy.mockResolvedValue(makeContent({ content: SAMPLE_YAML }));
    renderModal();

    // One fetch per open, and the fetched text lands in the real editor.
    await waitFor(() => expect(fetchContentSpy).toHaveBeenCalledTimes(1));
    const view = await readyEditorView();
    expect(view.state.doc.toString()).toBe(SAMPLE_YAML);
    // The document is actually drawn into the DOM (first line visible).
    const content = document.querySelector(".cm-content");
    expect(content?.textContent).toContain('release: "1.0"');
    // Header identifies the backing file (the footer status bar shows it
    // too — issue #105 — so scope to the header).
    expect(within(screen.getByTestId("editor-header")).getByText("machine.profiles")).toBeTruthy();
  });

  it("test_dirty_indicator_and_escape_warning", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    const user = userEvent.setup();
    const { onClose } = renderModal();

    const view = await readyEditorView();
    // Simulate a user edit through the real editor transaction seam.
    await act(async () => {
      view.dispatch({ changes: { from: 0, insert: "# edited\n" } });
    });

    // The dirty indicator appears in the toolbar row.
    expect(screen.getByRole("status")).toHaveTextContent(/unsaved changes/i);

    // Escape with a dirty doc opens the discard warning, not a close.
    screen.getByRole("button", { name: /open in os/i }).focus();
    await user.keyboard("{Escape}");
    const warning = screen.getByRole("dialog", { name: /discard changes\?/i });
    expect(warning).toBeTruthy();
    expect(onClose).not.toHaveBeenCalled();

    // Declining keeps the editor open (and still dirty).
    await user.click(screen.getByRole("button", { name: /keep editing/i }));
    expect(screen.queryByRole("dialog", { name: /discard changes\?/i })).toBeNull();
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: /configuration editor/i })).toBeTruthy();
    expect(screen.getByRole("status")).toHaveTextContent(/unsaved changes/i);
  });

  it("test_clean_close_without_warning", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    const user = userEvent.setup();
    const { onClose } = renderModal();

    await readyEditorView();
    // No edits: Escape closes immediately, no discard warning.
    screen.getByRole("button", { name: /open in os/i }).focus();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog", { name: /discard changes\?/i })).toBeNull();

    // The ✕ button shares the same guard-free path when clean.
    await user.click(screen.getByRole("button", { name: /close editor/i }));
    expect(onClose).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("dialog", { name: /discard changes\?/i })).toBeNull();
  });

  it("does not flag a freshly opened CRLF file as dirty (regression)", async () => {
    // CodeMirror stores LF line endings; the dirty baseline must be
    // normalized the same way or an untouched CRLF .profiles file would
    // trigger "Discard changes?" on its first close request.
    fetchContentSpy.mockResolvedValue(makeContent({ content: "a: 1\r\nb: 2\r\n" }));
    const user = userEvent.setup();
    const { onClose } = renderModal();

    await readyEditorView();
    // Untouched file: no dirty chip, and the fetched text round-trips
    // through the editor as LF.
    expect(screen.queryByRole("status")).toBeNull();
    const view = EditorView.findFromDOM(
      document.querySelector(".cm-editor") as HTMLElement,
    );
    expect(view?.state.doc.toString()).toBe("a: 1\nb: 2\n");

    // Escape closes immediately — no discard warning.
    screen.getByRole("button", { name: /open in os/i }).focus();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog", { name: /discard changes\?/i })).toBeNull();
  });

  it("test_header_open_in_os_calls_open_config_file", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    openInOSSpy.mockResolvedValue({ status: "SUCCESS", message: "Opened" });
    const user = userEvent.setup();
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    renderModal();

    const button = await screen.findByRole("button", { name: /open in os/i });
    await user.click(button);
    await waitFor(() => expect(openInOSSpy).toHaveBeenCalledTimes(1));
    expect(consoleSpy).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  it("test_open_in_os_visibility_follows_disk_anchor", async () => {
    // Session trial: nothing on disk backs the editor, and the open-config
    // action would hand the OS the CWD-resolved fallback — possibly an
    // unrelated pre-existing .profiles or a NOT_FOUND. Hidden like Save.
    fetchContentSpy.mockResolvedValue(
      makeContent({ filename: "session-trial", config_path: null, session_trial: true }),
    );
    renderModal();
    await readyEditorView();
    expect(screen.queryByRole("button", { name: /open in os/i })).toBeNull();
    expect(openInOSSpy).not.toHaveBeenCalled();
    cleanup();

    // Disk-anchored: the shortcut is back.
    fetchContentSpy.mockResolvedValue(makeContent());
    renderModal();
    await readyEditorView();
    expect(screen.getByRole("button", { name: /open in os/i })).toBeTruthy();
    expect(openInOSSpy).not.toHaveBeenCalled();
  });

  /** Dispatch a user edit through the real editor transaction seam. */
  async function editDoc(insert: string): Promise<string> {
    const view = await readyEditorView();
    await act(async () => {
      view.dispatch({ changes: { from: 0, insert } });
    });
    return view.state.doc.toString();
  }

  it("test_new_loads_template_after_confirm", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    templateSpy.mockResolvedValue({ content: TEMPLATE_YAML, filename: "starter.profiles" });
    const user = userEvent.setup();
    const { onClose } = renderModal();

    await editDoc("# edited\n");
    expect(screen.getByRole("status")).toHaveTextContent(/unsaved changes/i);

    // Dirty: New must ask before replacing.
    await user.click(screen.getByRole("button", { name: /^new$/i }));
    const warning = screen.getByRole("dialog", { name: /replace current edits\?/i });
    expect(warning).toBeTruthy();
    expect(templateSpy).not.toHaveBeenCalled();

    // Confirming loads the starter template into the real editor.
    await user.click(screen.getByRole("button", { name: /^replace$/i }));
    expect(templateSpy).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      const view = EditorView.findFromDOM(document.querySelector(".cm-editor") as HTMLElement);
      expect(view?.state.doc.toString()).toBe(TEMPLATE_YAML_LF);
    });
    // Dirty cleared (CRLF template text becomes the new baseline).
    expect(screen.queryByRole("status")).toBeNull();
    // Escape now closes immediately — the baseline moved with the template.
    // (The template is not disk-anchored, so Open in OS is hidden — the
    // close button is the focus target here.)
    screen.getByRole("button", { name: /close editor/i }).focus();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog", { name: /discard changes\?/i })).toBeNull();
  });

  it("test_new_without_dirty_loads_immediately", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    templateSpy.mockResolvedValue({ content: TEMPLATE_YAML_LF, filename: "starter.profiles" });
    const user = userEvent.setup();
    renderModal();

    await readyEditorView();
    await user.click(screen.getByRole("button", { name: /^new$/i }));
    expect(templateSpy).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      const view = EditorView.findFromDOM(document.querySelector(".cm-editor") as HTMLElement);
      expect(view?.state.doc.toString()).toBe(TEMPLATE_YAML_LF);
    });
    expect(screen.queryByRole("dialog", { name: /replace current edits\?/i })).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("test_test_shows_valid_badge", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    const user = userEvent.setup();
    renderModal();

    await readyEditorView();
    await user.click(screen.getByRole("button", { name: /^test$/i }));
    await waitFor(() =>
      expect(validateSpy).toHaveBeenCalledWith("machine.profiles", SAMPLE_YAML),
    );
    const banner = await screen.findByTestId("editor-status");
    expect(banner.textContent).toMatch(/valid/i);
    expect(banner.className).toContain("status-success");
    expect(screen.queryByTestId("editor-issues")).toBeNull();
  });

  it("test_test_shows_issue_list", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({
      valid: false,
      issues: [
        { severity: "error", message: "unknown key 'foo' at line 3" },
        { severity: "warning", message: "search_dir does not exist" },
      ],
    });
    const user = userEvent.setup();
    renderModal();

    await readyEditorView();
    await user.click(screen.getByRole("button", { name: /^test$/i }));
    const list = await screen.findByTestId("editor-issues");
    expect(list.textContent).toContain("unknown key 'foo' at line 3");
    expect(list.textContent).toContain("search_dir does not exist");
    const banner = screen.getByTestId("editor-status");
    expect(banner.className).toContain("status-danger");
    expect(banner.textContent).toMatch(/2/);
  });

  it("test_apply_calls_load_content_and_reports_success", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    const applied = makeAppConfig();
    loadContentSpy.mockResolvedValue(applied);
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    // The applied text is the current doc, edits included.
    const edited = await editDoc("# edited\n");
    await user.click(screen.getByRole("button", { name: /^apply$/i }));
    await waitFor(() =>
      expect(loadContentSpy).toHaveBeenCalledWith("machine.profiles", edited),
    );
    await waitFor(() => expect(onApplied).toHaveBeenCalledTimes(1));
    expect(onApplied.mock.calls[0][0]).toBe(applied);
    const banner = screen.getByTestId("editor-status");
    expect(banner.className).toContain("status-success");
    expect(banner.textContent).toMatch(/applied/i);
  });

  it("test_apply_error_shows_server_message", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    loadContentSpy.mockRejectedValue(new Error("unknown key 'filters_xyz' at line 4"));
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    await readyEditorView();
    await user.click(screen.getByRole("button", { name: /^apply$/i }));
    const banner = await screen.findByTestId("editor-status");
    expect(banner.textContent).toContain("unknown key 'filters_xyz' at line 4");
    expect(banner.className).toContain("status-danger");
    expect(onApplied).not.toHaveBeenCalled();
  });

  it("test_apply_double_click_dispatches_once", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    // Deferred apply: the first request stays pending across both clicks.
    let resolveApply!: (value: AppConfigData) => void;
    loadContentSpy.mockReturnValue(
      new Promise<AppConfigData>((resolve) => {
        resolveApply = resolve;
      }),
    );
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    const applyButton = await screen.findByRole("button", { name: /^apply$/i });
    await user.click(applyButton);
    // Second click while the first apply is in flight must be swallowed.
    await user.click(applyButton);
    expect(loadContentSpy).toHaveBeenCalledTimes(1);

    // The in-flight apply still completes exactly once.
    resolveApply(makeAppConfig());
    await waitFor(() => expect(onApplied).toHaveBeenCalledTimes(1));
    expect(loadContentSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("editor-status").textContent).toMatch(/applied/i);

    // The gate is released once the action settles — a follow-up works.
    loadContentSpy.mockResolvedValue(makeAppConfig());
    await user.click(applyButton);
    await waitFor(() => expect(loadContentSpy).toHaveBeenCalledTimes(2));
    expect(onApplied).toHaveBeenCalledTimes(2);
  });

  it("test_stale_test_resolution_dropped_after_new", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    templateSpy.mockResolvedValue({ content: TEMPLATE_YAML_LF, filename: "starter.profiles" });
    // Deferred validate: the Test round-trip stays pending on purpose.
    let resolveValidate!: (value: { valid: boolean; issues: ValidationIssue[] }) => void;
    validateSpy.mockReturnValue(
      new Promise((resolve) => {
        resolveValidate = resolve;
      }),
    );
    const user = userEvent.setup();
    renderModal();

    // Dirty doc so New routes through the confirm dialog.
    await editDoc("# edited\n");

    // Test dispatches; its response is still pending…
    await user.click(screen.getByRole("button", { name: /^test$/i }));
    expect(validateSpy).toHaveBeenCalledTimes(1);

    // …when New + confirm dispatch and complete.
    await user.click(screen.getByRole("button", { name: /^new$/i }));
    await user.click(screen.getByRole("button", { name: /^replace$/i }));
    await waitFor(() => {
      const view = EditorView.findFromDOM(document.querySelector(".cm-editor") as HTMLElement);
      expect(view?.state.doc.toString()).toBe(TEMPLATE_YAML_LF);
    });

    // The stale Test resolution lands after New completed: it belongs to the
    // discarded document and must not render its issues over the template.
    await act(async () => {
      resolveValidate({
        valid: false,
        issues: [{ severity: "error", message: "stale issue from discarded doc" }],
      });
    });
    expect(screen.queryByTestId("editor-issues")).toBeNull();
    const banner = screen.getByTestId("editor-status");
    expect(banner.className).toContain("status-success");
    expect(banner.textContent).toMatch(/template loaded/i);
  });

  it("test_revert_reloads_from_server_after_confirm", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    const user = userEvent.setup();
    const { onClose } = renderModal();

    await editDoc("# edited\n");
    expect(fetchContentSpy).toHaveBeenCalledTimes(1);

    // Dirty: Revert must confirm before discarding, like New.
    await user.click(screen.getByRole("button", { name: /^revert$/i }));
    expect(screen.getByRole("dialog", { name: /replace current edits\?/i })).toBeTruthy();
    expect(fetchContentSpy).toHaveBeenCalledTimes(1);

    // Confirming re-fetches the server content and restores the doc.
    await user.click(screen.getByRole("button", { name: /^replace$/i }));
    await waitFor(() => expect(fetchContentSpy).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      const view = EditorView.findFromDOM(document.querySelector(".cm-editor") as HTMLElement);
      expect(view?.state.doc.toString()).toBe(SAMPLE_YAML);
    });
    expect(screen.queryByRole("status")).toBeNull();
    // Clean again: Escape closes immediately.
    screen.getByRole("button", { name: /open in os/i }).focus();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog", { name: /discard changes\?/i })).toBeNull();
  });

  it("test_save_validates_then_saves", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    const savedConfig = makeAppConfig();
    saveSpy.mockResolvedValue(makeSaveResult(savedConfig));
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    // The saved text is the current doc, edits included.
    const edited = await editDoc("# edited\n");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    // The client-side gate validation runs first, on the current doc text…
    await waitFor(() => expect(validateSpy).toHaveBeenCalledWith("machine.profiles", edited));
    // …then the save endpoint writes it, unforced, with the staleness
    // baseline from the load (no content_hash served → null).
    await waitFor(() => expect(saveSpy).toHaveBeenCalledWith(edited, false, { baselineHash: null }));
    expect(saveAsSpy).not.toHaveBeenCalled();

    // Success surface: ok banner, dirty cleared (baseline = saved text),
    // onApplied with the fresh AppConfigData.
    const banner = screen.getByTestId("editor-status");
    expect(banner.className).toContain("status-success");
    expect(banner.textContent).toMatch(/saved/i);
    expect(screen.queryByRole("status")).toBeNull();
    await waitFor(() => expect(onApplied).toHaveBeenCalledTimes(1));
    expect(onApplied.mock.calls[0][0]).toBe(savedConfig);

    // Ctrl/Cmd+S on a disk-anchored editor triggers the same save flow.
    await user.keyboard("{Control>}s");
    await waitFor(() => expect(validateSpy).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(saveSpy).toHaveBeenCalledTimes(2));
    expect(saveSpy.mock.calls[1]).toEqual([edited, false, { baselineHash: "written-hash" }]);
    expect(onApplied).toHaveBeenCalledTimes(2);
  });

  it("test_save_invalid_shows_gate_with_force_option", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({
      valid: false,
      issues: [
        { severity: "error", message: "unknown key 'foo' at line 3" },
        { severity: "warning", message: "search_dir does not exist" },
      ],
    });
    const user = userEvent.setup();
    renderModal();

    await readyEditorView();
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    // The gate lists the issues and offers both exits; nothing is saved yet.
    const gate = await screen.findByRole("dialog", { name: /validation issues/i });
    expect(gate.textContent).toContain("unknown key 'foo' at line 3");
    expect(gate.textContent).toContain("search_dir does not exist");
    expect(screen.getByRole("button", { name: /go back and fix/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /force save anyway/i })).toBeTruthy();
    expect(saveSpy).not.toHaveBeenCalled();

    // "Go back and fix" dismisses the gate back to the editor, issues listed.
    await user.click(screen.getByRole("button", { name: /go back and fix/i }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: /validation issues/i })).toBeNull(),
    );
    expect(saveSpy).not.toHaveBeenCalled();
    expect(screen.getByTestId("editor-issues").textContent).toContain(
      "unknown key 'foo' at line 3",
    );
    const banner = screen.getByTestId("editor-status");
    expect(banner.className).toContain("status-danger");
    expect(banner.textContent).toMatch(/cancel/i);

    // Saving again re-validates and re-opens the gate.
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(validateSpy).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("dialog", { name: /validation issues/i })).toBeTruthy();
    expect(saveSpy).not.toHaveBeenCalled();
  });

  it("test_force_save_proceeds", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({
      valid: false,
      issues: [{ severity: "error", message: "unknown key 'foo' at line 3" }],
    });
    saveSpy.mockResolvedValue(makeSaveResult());
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    const edited = await editDoc("# edited\n");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await screen.findByRole("dialog", { name: /validation issues/i });

    // Force is the escape hatch: exactly one save call, with force=true.
    await user.click(screen.getByRole("button", { name: /force save anyway/i }));
    await waitFor(() => expect(saveSpy).toHaveBeenCalledTimes(1));
    expect(saveSpy).toHaveBeenCalledWith(edited, true, { baselineHash: null });
    expect(saveSpy.mock.calls[0]).toEqual([edited, true, { baselineHash: null }]);

    // Gate cleared, ok banner, dirty cleared, onApplied fired.
    expect(screen.queryByRole("dialog", { name: /validation issues/i })).toBeNull();
    const banner = screen.getByTestId("editor-status");
    expect(banner.className).toContain("status-success");
    expect(banner.textContent).toMatch(/saved/i);
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByTestId("editor-issues")).toBeNull();
    await waitFor(() => expect(onApplied).toHaveBeenCalledTimes(1));
  });

  it("test_save_disabled_without_disk_path", async () => {
    // Session trial: nothing on disk to overwrite — Save must not offer itself.
    fetchContentSpy.mockResolvedValue(
      makeContent({ filename: "session-trial", config_path: null, session_trial: true }),
    );
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    saveSpy.mockResolvedValue(makeSaveResult());
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    await readyEditorView();
    expect(screen.queryByRole("button", { name: /^save$/i })).toBeNull();
    // Save As stays available — it is the way to anchor a trial onto disk.
    expect(screen.getByRole("button", { name: /^save as$/i })).toBeTruthy();

    // Ctrl/Cmd+S falls back to Apply for a session trial.
    await user.keyboard("{Control>}s");
    await waitFor(() =>
      expect(loadContentSpy).toHaveBeenCalledWith("session-trial", SAMPLE_YAML),
    );
    expect(saveSpy).not.toHaveBeenCalled();
    expect(saveAsSpy).not.toHaveBeenCalled();
    await waitFor(() => expect(onApplied).toHaveBeenCalledTimes(1));
  });

  it("test_save_double_click_dispatches_once", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    // Deferred save: the first request stays pending across both clicks.
    let resolveSave!: (value: ConfigSaveResult) => void;
    saveSpy.mockReturnValue(
      new Promise<ConfigSaveResult>((resolve) => {
        resolveSave = resolve;
      }),
    );
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    const saveButton = await screen.findByRole("button", { name: /^save$/i });
    await user.click(saveButton);
    // Second click while the first save is in flight must be swallowed.
    await user.click(saveButton);
    await waitFor(() => expect(saveSpy).toHaveBeenCalledTimes(1));
    expect(validateSpy).toHaveBeenCalledTimes(1);

    // The in-flight save still completes exactly once.
    resolveSave(makeSaveResult());
    await waitFor(() => expect(onApplied).toHaveBeenCalledTimes(1));
    expect(saveSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("editor-status").textContent).toMatch(/saved/i);

    // The gate is released once the action settles — a follow-up works.
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    saveSpy.mockResolvedValue(makeSaveResult());
    await user.click(saveButton);
    await waitFor(() => expect(saveSpy).toHaveBeenCalledTimes(2));
    expect(onApplied).toHaveBeenCalledTimes(2);
  });

  it("test_stale_save_resolution_dropped_after_new", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    templateSpy.mockResolvedValue({ content: TEMPLATE_YAML_LF, filename: "starter.profiles" });
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    // Deferred save: the save round-trip stays pending on purpose.
    let resolveSave!: (value: ConfigSaveResult) => void;
    saveSpy.mockReturnValue(
      new Promise<ConfigSaveResult>((resolve) => {
        resolveSave = resolve;
      }),
    );
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    await editDoc("# edited\n");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(saveSpy).toHaveBeenCalledTimes(1));

    // New + confirm dispatches and completes while the save is pending.
    await user.click(screen.getByRole("button", { name: /^new$/i }));
    await user.click(screen.getByRole("button", { name: /^replace$/i }));
    await waitFor(() => {
      const view = EditorView.findFromDOM(document.querySelector(".cm-editor") as HTMLElement);
      expect(view?.state.doc.toString()).toBe(TEMPLATE_YAML_LF);
    });

    // The stale save resolution lands after New completed: it belongs to the
    // discarded document and must not mark it saved or fire onApplied.
    await act(async () => {
      resolveSave(makeSaveResult());
    });
    expect(onApplied).not.toHaveBeenCalled();
    const view = EditorView.findFromDOM(document.querySelector(".cm-editor") as HTMLElement);
    expect(view?.state.doc.toString()).toBe(TEMPLATE_YAML_LF);
    const banner = screen.getByTestId("editor-status");
    expect(banner.textContent).toMatch(/template loaded/i);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("test_save_as_runs_gate_then_dialog_then_saves", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({
      valid: false,
      issues: [{ severity: "error", message: "unknown key 'foo' at line 3" }],
    });
    saveAsSpy.mockResolvedValue(makeSaveResult());
    browseSpy.mockResolvedValue(makeBrowseResult());
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    const edited = await editDoc("# edited\n");
    await user.click(screen.getByRole("button", { name: /^save as$/i }));

    // The SAME compliance gate runs first — no dialog, no save call yet.
    await waitFor(() =>
      expect(validateSpy).toHaveBeenCalledWith("machine.profiles", edited),
    );
    expect(screen.queryByRole("dialog", { name: /save configuration as/i })).toBeNull();
    await user.click(await screen.findByRole("button", { name: /force save anyway/i }));

    // Then the Save As dialog opens, listing directories via browseDirectory.
    const dialog = await screen.findByRole("dialog", { name: /save configuration as/i });
    await waitFor(() => expect(browseSpy).toHaveBeenCalled());
    expect(dialog.textContent).toContain("/home/user/configs");

    // Confirming hands the normalized name to saveConfigFileAs, force carried.
    await user.type(await screen.findByLabelText(/file name/i), "copy");
    await user.click(within(dialog).getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(saveAsSpy).toHaveBeenCalledTimes(1));
    expect(saveAsSpy).toHaveBeenCalledWith({
      content: edited,
      filename: "copy.profiles",
      directory: "/home/user/configs",
      force: true,
      overwrite: false,
    });

    // Same success surface as Save: banner, clean editor, onApplied.
    const banner = screen.getByTestId("editor-status");
    expect(banner.className).toContain("status-success");
    expect(banner.textContent).toMatch(/saved/i);
    expect(screen.queryByRole("status")).toBeNull();
    await waitFor(() => expect(onApplied).toHaveBeenCalledTimes(1));
    expect(saveSpy).not.toHaveBeenCalled();
  });
  it("test_save_409_offers_reload_or_overwrite_and_overwrite_wins", async () => {
    // The load serves a baseline hash; the file changes on disk before Save.
    fetchContentSpy.mockResolvedValue(makeContent({ content_hash: "baseline-hash" }));
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    const conflict = new ApiError(
      "The configuration file changed on disk since it was loaded (edited externally?).",
      409,
    );
    saveSpy.mockRejectedValueOnce(conflict).mockResolvedValueOnce(makeSaveResult());
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    const edited = await editDoc("# edited\n");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    // First save carries the load's baseline; the 409 parks the conflict
    // dialog instead of clobbering (issue #116).
    await waitFor(() =>
      expect(saveSpy).toHaveBeenCalledWith(edited, false, { baselineHash: "baseline-hash" }),
    );
    const conflictDialog = await screen.findByRole("dialog", { name: /file changed on disk/i });
    expect(conflictDialog.textContent).toContain("Overwrite anyway");
    expect(conflictDialog.textContent).toContain("Reload disk version");

    // "Overwrite anyway" retries the SAME text with overwrite_changes.
    await user.click(within(conflictDialog).getByRole("button", { name: /overwrite anyway/i }));
    await waitFor(() => expect(saveSpy).toHaveBeenCalledTimes(2));
    expect(saveSpy.mock.calls[1]).toEqual([
      edited,
      false,
      { baselineHash: "baseline-hash", overwriteChanges: true },
    ]);

    // Success surface: saved banner, onApplied once (the retry is not a
    // second Apply), conflict dialog gone.
    const banner = screen.getByTestId("editor-status");
    expect(banner.textContent).toMatch(/saved/i);
    expect(onApplied).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog", { name: /file changed on disk/i })).toBeNull();
  });

  it("test_save_409_reload_adopts_disk_version", async () => {
    // First /content serves the editor's baseline; the second (after the
    // user picks "Reload disk version") serves the external edits.
    fetchContentSpy.mockReset();
    fetchContentSpy
      .mockResolvedValueOnce(makeContent({ content_hash: "baseline-hash" }))
      .mockResolvedValueOnce(
        makeContent({ content: 'defaults:\n  title: "External"\n', content_hash: "external-hash" }),
      );
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    saveSpy.mockRejectedValueOnce(
      new ApiError("The configuration file changed on disk since it was loaded.", 409),
    );
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    await editDoc("# edited\n");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    const conflictDialog = await screen.findByRole("dialog", { name: /file changed on disk/i });

    // "Reload disk version" re-fetches and the disk text replaces the
    // editor's document — the external edits are adopted, nothing written.
    await user.click(within(conflictDialog).getByRole("button", { name: /reload disk version/i }));
    await waitFor(() => expect(fetchContentSpy).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      const view = EditorView.findFromDOM(document.querySelector(".cm-editor") as HTMLElement);
      expect(view?.state.doc.toString()).toBe('defaults:\n  title: "External"\n');
    });
    expect(saveSpy).toHaveBeenCalledTimes(1);
    expect(onApplied).not.toHaveBeenCalled();
    expect(screen.getByTestId("editor-status").textContent).toMatch(/reloaded from disk/i);
    expect(screen.queryByRole("dialog", { name: /file changed on disk/i })).toBeNull();
  });

  it("test_save_refreshes_the_staleness_baseline_after_each_save", async () => {
    // The load's hash guards the first save; the written hash returned by
    // the first save guards the second (issue #116).
    fetchContentSpy.mockResolvedValue(makeContent({ content_hash: "baseline-hash" }));
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    saveSpy.mockResolvedValue(makeSaveResult(undefined, "written-hash"));
    const user = userEvent.setup();
    const { onApplied } = renderModal();

    const edited = await editDoc("# edited\n");
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(saveSpy).toHaveBeenCalledWith(edited, false, { baselineHash: "baseline-hash" }));

    await user.keyboard("{Control>}s");
    await waitFor(() => expect(saveSpy).toHaveBeenCalledTimes(2));
    expect(saveSpy.mock.calls[1]).toEqual([edited, false, { baselineHash: "written-hash" }]);
    expect(onApplied).toHaveBeenCalledTimes(2);
  });
});

/**
 * Editor feedback tests (issues #102 + #100): editing must clear stale
 * Test/validation feedback immediately, and validation must re-run
 * automatically ~800ms after the user stops typing.
 */
describe("ConfigEditorModal live validation (issues #102/#100)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("test_editing_clears_stale_validation_feedback", async () => {
    validateSpy.mockResolvedValue({ valid: false, issues: [{ severity: "error", message: "boom" }] });
    const user = userEvent.setup();
    renderModal();

    const view = await readyEditorView();
    // Run Test: the banner + issue list describe the pre-edit document.
    await user.click(screen.getByRole("button", { name: /test/i }));
    await waitFor(() => expect(screen.getByTestId("editor-status")).toBeTruthy());
    expect(screen.getByTestId("editor-issues")).toBeTruthy();

    // One keystroke invalidates that feedback — it must vanish immediately.
    await act(async () => {
      view.dispatch({ changes: { from: 0, insert: "# edited\n" } });
    });
    expect(screen.queryByTestId("editor-status")).toBeNull();
    expect(screen.queryByTestId("editor-issues")).toBeNull();
  });

  it("test_live_validation_fires_after_debounce", async () => {
    renderModal();
    const view = await readyEditorView();
    // Freeze time only after the editor is ready: RTL waitFor relies on
    // real timers while probing the mounted view.
    vi.useFakeTimers();
    validateSpy.mockResolvedValue({ valid: true, issues: [] });

    await act(async () => {
      view.dispatch({ changes: { from: 0, insert: "# edited\n" } });
    });
    // A pause shorter than the debounce fires nothing.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(799);
    });
    expect(validateSpy).not.toHaveBeenCalled();

    // At 800ms after the last change, exactly one validation leaves —
    // carrying the current document text.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(validateSpy).toHaveBeenCalledTimes(1);
    expect(validateSpy.mock.calls[0][1]).toContain("# edited\n");
  });

  it("test_live_validation_coalesces_rapid_typing", async () => {
    renderModal();
    const view = await readyEditorView();
    vi.useFakeTimers();
    validateSpy.mockResolvedValue({ valid: true, issues: [] });

    // Three changes inside the debounce window coalesce into one request.
    await act(async () => {
      view.dispatch({ changes: { from: 0, insert: "a\n" } });
      await vi.advanceTimersByTimeAsync(300);
      view.dispatch({ changes: { from: 1, insert: "b\n" } });
      await vi.advanceTimersByTimeAsync(300);
      view.dispatch({ changes: { from: 2, insert: "c\n" } });
      await vi.advanceTimersByTimeAsync(800);
    });
    expect(validateSpy).toHaveBeenCalledTimes(1);
    expect(validateSpy.mock.calls[0][1]).toContain("c\n");
  });

  it("test_explicit_test_cancels_pending_debounce", async () => {
    renderModal();
    const view = await readyEditorView();
    vi.useFakeTimers();
    validateSpy.mockResolvedValue({ valid: true, issues: [] });

    await act(async () => {
      view.dispatch({ changes: { from: 0, insert: "# edited\n" } });
    });
    // The explicit Test button short-circuits the pending debounce.
    await act(async () => {
      screen.getByRole("button", { name: /test/i }).click();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(validateSpy).toHaveBeenCalledTimes(1);

    // The canceled timer must not re-fire later.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(validateSpy).toHaveBeenCalledTimes(1);
  });

  it("test_live_validation_rechecks_after_in_flight_completes", async () => {
    renderModal();
    const view = await readyEditorView();
    vi.useFakeTimers();
    let resolveFirst!: (value: { valid: boolean; issues: never[] }) => void;
    validateSpy.mockImplementationOnce(
      () => new Promise((resolve) => { resolveFirst = resolve; }),
    );

    await act(async () => {
      view.dispatch({ changes: { from: 0, insert: "x\n" } });
      await vi.advanceTimersByTimeAsync(800);
    });
    expect(validateSpy).toHaveBeenCalledTimes(1); // in flight

    // A second edit while validation is in flight must not be swallowed —
    // it re-schedules and re-fires once the round trip lands.
    await act(async () => {
      view.dispatch({ changes: { from: 0, insert: "y\n" } });
      await vi.advanceTimersByTimeAsync(800);
    });
    expect(validateSpy).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveFirst({ valid: true, issues: [] });
      await vi.advanceTimersByTimeAsync(800);
    });
    expect(validateSpy).toHaveBeenCalledTimes(2);
  });

  it("test_live_validation_skipped_while_gate_parked", async () => {
    // The compliance gate (invalid save confirm) is a blocking modal: no
    // auto-validation churn behind it.
    validateSpy.mockResolvedValue({
      valid: false,
      issues: [{ severity: "error", message: "boom" }],
    });
    const user = userEvent.setup();
    renderModal();
    const view = await readyEditorView();

    await user.click(screen.getByRole("button", { name: /^save$/i }));
    expect(await screen.findByRole("dialog", { name: /save with validation issues\?/i })).toBeTruthy();

    vi.useFakeTimers();
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    await act(async () => {
      view.dispatch({ changes: { from: 0, insert: "# edited\n" } });
      await vi.advanceTimersByTimeAsync(2000);
    });
    // Only the save pre-validation ran — no live cycle behind the gate.
    expect(validateSpy).toHaveBeenCalledTimes(1);
  });
});

/**
 * Editor chrome tests (issues #98 + #99): the CodeMirror surface must be
 * solid and token-backed (never the frosted modal glass), the gutter must
 * be opaque, and the editor must sit inside a padded bordered card that
 * separates it from the modal chrome.
 */
describe("ConfigEditorModal editor chrome (issues #98/#99)", () => {
  it("test_editor_theme_is_solid_and_token_backed", async () => {
    renderModal();
    await readyEditorView();

    // CodeMirror injects the compiled theme as real <style> rules; those
    // declarations are the honest thing to assert on. Only the stylesheet
    // of the editor's own theme module is inspected — CodeMirror separately
    // mounts built-in base-theme styles (which may use transparent) and
    // they are not this modal's responsibility.
    const themeModuleStyles = Array.from(document.querySelectorAll("style"))
      .map((node) => node.textContent ?? "")
      .filter((cssText) => cssText.includes("--app-editor-bg"))
      .join("\n");

    // Editor canvas: solid, sourced from the new editor token (issue #98).
    expect(themeModuleStyles).toMatch(/background-color:\s*var\(--app-editor-bg\)/);
    // Gutter: opaque background from its own token.
    expect(themeModuleStyles).toMatch(/background-color:\s*var\(--app-editor-gutter-bg\)/);
    // Static guard against regression to the old bug (the theme root
    // painting `transparent` over the frosted modal glass): the shipped
    // theme object must never set a transparent background. CodeMirror
    // additionally mounts built-in base-theme <style> rules that may
    // legitimately use transparent — that is why this is asserted on the
    // source rather than the merged stylesheet.
    const modalSource = (await import("./ConfigEditorModal.tsx?raw")).default;
    expect(modalSource).not.toMatch(/backgroundColor:\s*"transparent"/);
  });

  it("test_editor_tokens_defined_for_both_themes", async () => {
    // The index.css token sheet defines the editor tokens in BOTH the
    // dark and light theme blocks — the same single-attribute flip as
    // every other --app-* token. (A plain node:fs read: vitest serves
    // source files through virtual paths, so import.meta URLs cannot be
    // dereferenced here.)
    const css = readFileSync(join(process.cwd(), "src", "index.css"), "utf8");
    expect(css).not.toBe("");
    const darkBlock = css.slice(0, css.indexOf('[data-theme="light"]'));
    const lightBlock = css.slice(css.indexOf('[data-theme="light"]'));
    for (const token of [
      "--app-editor-bg",
      "--app-editor-gutter-bg",
      "--app-editor-active-line",
      "--app-editor-selection",
      "--app-editor-border",
    ]) {
      expect(darkBlock).toContain(`${token}:`);
      expect(lightBlock).toContain(`${token}:`);
    }
  });

  it("test_editor_sits_inside_padded_bordered_card", async () => {
    renderModal();
    const dialog = await screen.findByRole("dialog", { name: /configuration editor/i });
    await readyEditorView();

    // The bordered card wraps the editor — padding on the body, a
    // rounded border on the card (issue #99).
    const card = dialog.querySelector('[data-testid="editor-card"]');
    expect(card).toBeTruthy();
    expect(card!.className).toContain("rounded-lg");
    expect(card!.className).toContain("border");
    const cardParent = card!.parentElement!;
    expect(
      cardParent.className.includes("p-3") || cardParent.className.includes("p-4"),
    ).toBe(true);
    // The editor really lives inside the card.
    expect(card!.querySelector(".cm-editor")).toBeTruthy();
  });

  it("test_syntax_highlighting_is_token_backed_not_the_light_default", async () => {
    // basicSetup ships the default highlight style — a light-background
    // palette (#940 browns, #164 teals, #00c dark blues…) that is nearly
    // unreadable on the dark editor canvas. The editor must configure its
    // OWN non-fallback highlight style whose colors come from
    // --app-editor-syntax-* tokens (VSCode Dark+ / Light+ counterparts).
    renderModal();
    await readyEditorView();

    // Our highlight style is mounted: its rules reference the syntax
    // tokens (the default style hardcodes hex colors, never var()).
    const injectedStyles = Array.from(document.querySelectorAll("style"))
      .map((node) => node.textContent ?? "")
      .join("\n");
    expect(injectedStyles).toContain("var(--app-editor-syntax-key)");
    expect(injectedStyles).toContain("var(--app-editor-syntax-comment)");
    expect(injectedStyles).toContain("var(--app-editor-syntax-string)");

    // Static guard: the shipped source configures the non-fallback style.
    const modalSource = (await import("./ConfigEditorModal.tsx?raw")).default;
    expect(modalSource).toContain("syntaxHighlighting(yamlHighlightStyle)");

    // The tokens are defined in BOTH theme blocks, like every --app-editor-*
    // token (issue #98 pattern).
    const css = readFileSync(join(process.cwd(), "src", "index.css"), "utf8");
    expect(css).not.toBe("");
    const darkBlock = css.slice(0, css.indexOf('[data-theme="light"]'));
    const lightBlock = css.slice(css.indexOf('[data-theme="light"]'));
    for (const token of [
      "--app-editor-syntax-comment",
      "--app-editor-syntax-key",
      "--app-editor-syntax-string",
      "--app-editor-syntax-keyword",
      "--app-editor-syntax-label",
    ]) {
      expect(darkBlock).toContain(`${token}:`);
      expect(lightBlock).toContain(`${token}:`);
    }
  });
});

/**
 * Header consolidation tests (issue #101): every action lives in the header
 * bar — the standalone toolbar row is gone — and loading another .profiles
 * file is raised from inside the editor via the injected `onLoadConfig`.
 */
describe("ConfigEditorModal header consolidation (issue #101)", () => {
  it("test_header_carries_all_actions_and_toolbar_row_is_gone", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    renderModal();
    const dialog = await screen.findByRole("dialog", { name: /configuration editor/i });
    await readyEditorView();

    // No second chrome band: the standalone toolbar row is gone.
    expect(dialog.querySelector('[data-testid="editor-toolbar"]')).toBeNull();

    // All actions — including the unmovable Open in OS / ✕ — live in the
    // header bar (disk-anchored doc, so Save exists too).
    const header = within(dialog).getByTestId("editor-header");
    for (const name of [/^new$/i, /^test$/i, /^revert$/i, /^save$/i, /^save as$/i, /^apply$/i, /open in os/i, /close editor/i]) {
      expect(within(header).getByRole("button", { name })).toBeTruthy();
    }
  });

  it("test_load_config_file_button_invokes_onLoadConfig", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    const onLoadConfig = vi.fn();
    renderModal({ onLoadConfig });
    await readyEditorView();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /load config file/i }));
    expect(onLoadConfig).toHaveBeenCalledTimes(1);
  });

  it("test_load_config_file_button_absent_without_wiring", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    renderModal(); // no onLoadConfig prop
    await readyEditorView();
    expect(screen.queryByRole("button", { name: /load config file/i })).toBeNull();
  });

  it("test_reload_key_change_reloads_editor_content", async () => {
    fetchContentSpy.mockResolvedValueOnce(makeContent());
    const modal = renderModal({ reloadKey: 0 });
    const view = await readyEditorView();
    expect(fetchContentSpy).toHaveBeenCalledTimes(1);

    // A different .profiles file was picked outside; the reload key bumps
    // and the editor must swap to the freshly served content — no stale
    // text left behind.
    fetchContentSpy.mockResolvedValueOnce(
      makeContent({ filename: "other.profiles", content: 'release: "2.0"\nsearch_dir: "E:/other"\n' }),
    );
    modal.rerenderWith({ reloadKey: 1 });
    await waitFor(() => expect(fetchContentSpy).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      const reloaded = EditorView.findFromDOM(document.querySelector(".cm-editor") as HTMLElement);
      expect(reloaded?.state.doc.toString()).toBe('release: "2.0"\nsearch_dir: "E:/other"\n');
    });
    expect(view.state.doc.toString()).not.toBeNull(); // original view object captured above
    // The header (and footer) now announce the freshly picked file.
    expect(within(screen.getByTestId("editor-header")).getByText("other.profiles")).toBeTruthy();
  });
});

/**
 * Status bar + Problems panel tests (issue #105): a thin always-visible
 * footer (validity chip, unsaved dot, cursor position, format + filename)
 * and a collapsible right Problems panel that auto-opens on validation
 * failure. The inline banner block is gone — the footer is THE feedback
 * surface.
 */
describe("ConfigEditorModal status bar and problems panel (issue #105)", () => {
  it("test_status_bar_present_with_chip_cursor_and_format", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    renderModal();
    await readyEditorView();

    const footer = screen.getByTestId("editor-footer");
    // Validity chip exists even before the first validation (unknown state).
    expect(within(footer).getByTestId("validity-chip")).toBeTruthy();
    // Cursor position, format and filename decorate the right side.
    expect(footer.textContent).toMatch(/ln 1, col 1/i);
    expect(footer.textContent).toMatch(/yaml/i);
    expect(footer.textContent).toContain("machine.profiles");
  });

  it("test_cursor_position_tracks_selection", async () => {
    fetchContentSpy.mockResolvedValue(
      makeContent({ content: 'release: "1.0"\nsearch_dir: "C:/data"\nrecursive_search: false\ntheme: dark\n' }),
    );
    renderModal();
    const view = await readyEditorView();

    // Put the caret on the last line's first character.
    const doc = view.state.doc;
    await act(async () => {
      view.dispatch({ selection: { anchor: doc.line(4).from } });
    });
    const footer = screen.getByTestId("editor-footer");
    expect(footer.textContent).toMatch(/ln 4, col 1/i);
  });

  it("test_failed_validation_auto_opens_panel_and_lists_issues", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({
      valid: false,
      issues: [
        { severity: "error", message: "unknown key 'foo' at line 3" },
        { severity: "warning", message: "search_dir does not exist" },
      ],
    });
    const user = userEvent.setup();
    renderModal();
    await readyEditorView();

    await user.click(screen.getByRole("button", { name: /^test$/i }));

    // The panel auto-opens on failure: issues listed inside it.
    const panel = await screen.findByTestId("problems-panel");
    const list = within(panel).getByTestId("editor-issues");
    expect(list.textContent).toContain("unknown key 'foo' at line 3");
    expect(list.textContent).toContain("search_dir does not exist");
    // The two rows carry their severity styling (error red, warning amber).
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0].className).toContain("status-danger");
    expect(rows[1].className).toContain("chip-amber");

    // The validity chip reads "✗ 2 issues" (danger styling).
    const chip = within(screen.getByTestId("editor-footer")).getByTestId("validity-chip");
    expect(chip.textContent).toMatch(/2 issues/i);
    expect(chip.className).toContain("status-danger");
  });

  it("test_valid_result_shows_valid_chip", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    const user = userEvent.setup();
    renderModal();
    await readyEditorView();

    await user.click(screen.getByRole("button", { name: /^test$/i }));

    const chip = await screen.findByTestId("validity-chip");
    expect(chip.textContent).toMatch(/valid/i);
    expect(chip.className).toContain("status-success");
    // No issues list materializes; the panel stays closed.
    expect(screen.queryByTestId("editor-issues")).toBeNull();
    expect(screen.queryByTestId("problems-panel")).toBeNull();
  });

  it("test_chip_reads_validating_while_a_validation_is_in_flight", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    // Deferred validation: the round trip stays pending on purpose.
    let resolveValidate!: (value: { valid: boolean; issues: ValidationIssue[] }) => void;
    validateSpy.mockReturnValue(
      new Promise((resolve) => {
        resolveValidate = resolve;
      }),
    );
    const user = userEvent.setup();
    renderModal();
    await readyEditorView();

    await user.click(screen.getByRole("button", { name: /^test$/i }));
    const chip = within(screen.getByTestId("editor-footer")).getByTestId("validity-chip");
    expect(chip.textContent).toMatch(/validating/i);

    await act(async () => {
      resolveValidate({ valid: true, issues: [] });
    });
    await waitFor(() => expect(chip.textContent).toMatch(/valid/i));
  });

  it("test_issues_chip_toggles_panel_and_close_button_closes_it", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({
      valid: false,
      issues: [{ severity: "error", message: "unknown key 'foo' at line 3" }],
    });
    const user = userEvent.setup();
    renderModal();
    await readyEditorView();
    await user.click(screen.getByRole("button", { name: /^test$/i }));
    expect(await screen.findByTestId("problems-panel")).toBeTruthy();

    // Close button collapses the panel.
    await user.click(screen.getByRole("button", { name: /close problems/i }));
    expect(screen.queryByTestId("problems-panel")).toBeNull();

    // The chip re-opens it — toggling from the status bar.
    await user.click(screen.getByTestId("validity-chip"));
    expect(screen.getByTestId("problems-panel")).toBeTruthy();
  });

  it("test_unsaved_dot_lives_in_the_status_bar", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    renderModal();
    const view = await readyEditorView();
    await act(async () => {
      view.dispatch({ changes: { from: 0, insert: "# edited\n" } });
    });

    const footer = screen.getByTestId("editor-footer");
    const dot = within(footer).getByRole("status");
    expect(dot.textContent).toMatch(/unsaved changes/i);
  });

  it("test_status_message_renders_in_the_footer_no_inline_banner", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({ valid: true, issues: [] });
    const user = userEvent.setup();
    renderModal();
    await readyEditorView();

    await user.click(screen.getByRole("button", { name: /^test$/i }));
    const footer = screen.getByTestId("editor-footer");
    // The old inline banner is gone; the action outcome speaks from the footer.
    const status = within(footer).getByTestId("editor-status");
    expect(status.textContent).toMatch(/valid/i);
    expect(status.className).toContain("status-success");
  });

  it("test_panel_resets_on_close_and_reopen", async () => {
    fetchContentSpy.mockResolvedValue(makeContent());
    validateSpy.mockResolvedValue({
      valid: false,
      issues: [{ severity: "error", message: "unknown key 'foo' at line 3" }],
    });
    const user = userEvent.setup();
    const modal = renderModal();
    await readyEditorView();
    await user.click(screen.getByRole("button", { name: /^test$/i }));
    expect(await screen.findByTestId("problems-panel")).toBeTruthy();

    // Close and reopen: the panel must not resurrect the session's state.
    modal.rerenderWith({ open: false });
    await waitFor(() => expect(screen.queryByTestId("problems-panel")).toBeNull());
    modal.rerenderWith({ open: true });
    await waitFor(() => expect(fetchContentSpy).toHaveBeenCalledTimes(2));
    await readyEditorView();
    expect(screen.queryByTestId("problems-panel")).toBeNull();
  });

});
