// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditorView } from "codemirror";
import { ConfigEditorModal } from "./ConfigEditorModal";
import { fetchConfigContent, openConfigFile } from "../api/client";
import type { ConfigContentData } from "../api/types";

vi.mock("../api/client", () => ({
  fetchConfigContent: vi.fn(),
  openConfigFile: vi.fn(),
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

const SAMPLE_YAML = 'release: "1.0"\nsearch_dir: "C:/data"\n';

function makeContent(overrides: Partial<ConfigContentData> = {}): ConfigContentData {
  return {
    filename: "machine.profiles",
    content: SAMPLE_YAML,
    config_path: "/home/user/.profiles/machine.profiles",
    session_trial: false,
    ...overrides,
  };
}

function renderModal(overrides: { open?: boolean } = {}) {
  const onClose = vi.fn();
  render(<ConfigEditorModal open={overrides.open ?? true} onClose={onClose} />);
  return { onClose };
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
});
