// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditorView } from "codemirror";
import { ConfigEditorModal } from "./ConfigEditorModal";
import {
  fetchConfigContent,
  fetchConfigTemplate,
  loadConfigContent,
  openConfigFile,
  validateConfigContent,
} from "../api/client";
import type { AppConfigData, ConfigContentData, ValidationIssue } from "../api/types";

vi.mock("../api/client", () => ({
  fetchConfigContent: vi.fn(),
  openConfigFile: vi.fn(),
  fetchConfigTemplate: vi.fn(),
  validateConfigContent: vi.fn(),
  loadConfigContent: vi.fn(),
}));

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

function renderModal(overrides: { open?: boolean } = {}) {
  const onClose = vi.fn();
  const onApplied = vi.fn();
  render(
    <ConfigEditorModal
      open={overrides.open ?? true}
      onClose={onClose}
      onApplied={onApplied}
    />,
  );
  return { onClose, onApplied };
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
    // Header identifies the backing file.
    expect(screen.getByText("machine.profiles")).toBeTruthy();
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
    screen.getByRole("button", { name: /open in os/i }).focus();
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
});
