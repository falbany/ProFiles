import { useCallback, useEffect, useRef, useState } from "react";
import { basicSetup, EditorView } from "codemirror";
import { yaml } from "@codemirror/lang-yaml";
import { CircleDot, ExternalLink, FileCode2, X } from "lucide-react";

import { fetchConfigContent, openConfigFile } from "../api/client";
import type { AppConfigData, ConfigContentData } from "../api/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { useModalA11y } from "../utils/useModalA11y";

export interface ConfigEditorModalProps {
  open: boolean;
  onClose: () => void;
  /** Called after a save/apply succeeds (Save/Save As — Tasks 7–8). */
  onApplied?: (data: AppConfigData) => void;
}

/** Load lifecycle of the configuration text behind the editor. */
type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: ConfigContentData };

/**
 * Editor theme built from the app's `data-theme` CSS tokens (index.css
 * `--app-*` variables). Only `var()` references are used — the editor
 * follows the light/dark switch automatically, like every other surface.
 */
const configEditorTheme = EditorView.theme({
  "&": {
    height: "100%",
    fontSize: "12.5px",
    color: "var(--app-text-primary)",
    backgroundColor: "transparent",
  },
  ".cm-scroller": {
    fontFamily: "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
    lineHeight: "1.6",
  },
  ".cm-content": { caretColor: "var(--color-indigo-500, #6366f1)" },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--color-indigo-500, #6366f1)" },
  "&.cm-focused": { outline: "none" },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": {
    backgroundColor: "var(--app-hover)",
  },
  ".cm-activeLine": { backgroundColor: "var(--app-elevated)" },
  ".cm-gutters": {
    backgroundColor: "transparent",
    color: "var(--app-text-faint)",
    border: "none",
    borderRight: "1px solid var(--app-border)",
  },
  ".cm-activeLineGutter": {
    backgroundColor: "var(--app-elevated)",
    color: "var(--app-text-secondary)",
  },
  ".cm-panels": {
    backgroundColor: "var(--app-glass-panel-strong)",
    color: "var(--app-text-primary)",
  },
  ".cm-tooltip": {
    border: "1px solid var(--app-border)",
    backgroundColor: "var(--app-glass-panel-strong)",
    color: "var(--app-text-primary)",
  },
});

/**
 * Normalize fetched content to the LF line endings CodeMirror stores
 * (CRLF is normalized away when the doc is created). The dirty check
 * compares the doc against this baseline; without it an untouched CRLF
 * file — realistic for .profiles files on Windows hosts — would read as
 * dirty on its very first Escape/✕/backdrop close.
 */
function toEditorText(content: string): string {
  return content.replace(/\r\n?/g, "\n");
}

/** True when the editor document differs from the text it was loaded with. */
function isDirty(view: EditorView | null, loadedText: string): boolean {
  return view !== null && view.state.doc.toString() !== loadedText;
}

/**
 * Full-screen YAML configuration editor (issue #95). This shell owns the
 * CodeMirror 6 instance, load-on-open, dirty tracking and the guarded
 * Escape/✕ close; the toolbar action buttons (Save, Reload, …) are wired
 * in Tasks 7–8. The header bar carries the "Open in OS" shortcut, which
 * hands the file to the OS default editor via the existing client call.
 */
export function ConfigEditorModal({ open, onClose, onApplied: _onApplied }: ConfigEditorModalProps) {
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [dirty, setDirty] = useState(false);
  const [confirmDiscardOpen, setConfirmDiscardOpen] = useState(false);

  const dialogRef = useRef<HTMLDivElement>(null);
  const editorHostRef = useRef<HTMLDivElement>(null);
  const editorViewRef = useRef<EditorView | null>(null);
  /** Text the editor was seeded with — the baseline for the dirty check. */
  const loadedTextRef = useRef<string>("");

  const handleDialogKeyDown = useModalA11y({
    isOpen: open,
    onClose: requestClose,
    dialogRef,
  });

  // Load-on-open; reset everything on close so a re-open starts clean.
  useEffect(() => {
    if (!open) {
      loadedTextRef.current = "";
      editorViewRef.current = null;
      setLoad({ status: "loading" });
      setDirty(false);
      setConfirmDiscardOpen(false);
      return;
    }
    let cancelled = false;
    fetchConfigContent()
      .then((data) => {
        if (cancelled) return;
        const content = toEditorText(data.content);
        loadedTextRef.current = content;
        setLoad({ status: "ready", data: { ...data, content } });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        loadedTextRef.current = "";
        setLoad({ status: "error", message: err instanceof Error ? err.message : String(err) });
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  // Mount the CodeMirror view once the content is on screen; destroy it on
  // close/unmount. Depends on `load` so the host div is guaranteed mounted.
  useEffect(() => {
    if (!open || load.status !== "ready") return;
    const host = editorHostRef.current;
    if (!host) return;
    const view = new EditorView({
      doc: load.data.content,
      extensions: [
        basicSetup,
        yaml(),
        configEditorTheme,
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            setDirty(isDirty(update.view, loadedTextRef.current));
          }
        }),
      ],
      parent: host,
    });
    editorViewRef.current = view;
    return () => {
      view.destroy();
      editorViewRef.current = null;
    };
  }, [open, load]);

  /**
   * Close request shared by Escape, the ✕ button and backdrop clicks.
   * A dirty editor (per the shared isDirty predicate) gets the discard
   * warning instead; a clean editor closes immediately.
   */
  function requestClose() {
    if (isDirty(editorViewRef.current, loadedTextRef.current)) {
      setConfirmDiscardOpen(true);
      return;
    }
    onClose();
  }

  const handleOpenInOS = useCallback(() => {
    openConfigFile().catch((err: unknown) => {
      console.error("Failed to open config file in OS editor:", err);
    });
  }, []);

  if (!open) return null;

  const filename = load.status === "ready" ? load.data.filename : "";
  const sessionTrial = load.status === "ready" ? load.data.session_trial : false;

  return (
    <>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="config-editor-title"
        onKeyDown={handleDialogKeyDown}
        onClick={requestClose}
        className="animate-overlay-in fixed inset-0 z-[var(--z-modal)] flex items-center justify-center bg-black/65 p-3 backdrop-blur-sm sm:p-6"
      >
        <div
          className="animate-modal-in flex h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-frame-line glass-panel"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header bar */}
          <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-3">
            <div className="flex min-w-0 items-center gap-2.5">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-chip-indigo-bg text-chip-indigo-text">
                <FileCode2 className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <h2 id="config-editor-title" className="text-sm font-semibold text-ink">
                  Configuration Editor
                </h2>
                <p className="truncate text-xs text-ink-muted">
                  {filename || "\u2026"}
                  {sessionTrial ? " • session trial (not anchored to disk)" : ""}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <button
                type="button"
                onClick={handleOpenInOS}
                title="Open the configuration file with the OS default editor"
                className="btn inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-secondary hover:bg-elevated hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Open in OS
              </button>
              <button
                type="button"
                onClick={requestClose}
                aria-label="Close editor"
                className="rounded-md p-1.5 text-ink-muted hover:bg-elevated hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Toolbar placeholder — action buttons (Save, Reload, …) are wired
              here in Tasks 7–8; for now it carries the dirty indicator. */}
          <div
            data-testid="editor-toolbar"
            className="flex shrink-0 items-center gap-2 border-b border-line px-5 py-2"
          >
            {dirty && (
              <span
                role="status"
                className="inline-flex items-center gap-1 rounded-full border border-chip-amber-border bg-chip-amber-bg px-2 py-0.5 text-[10px] font-bold text-chip-amber-text"
              >
                <CircleDot className="h-3 w-3" />
                Unsaved changes
              </span>
            )}
          </div>

          {/* Editor body */}
          <div className="min-h-0 flex-1 overflow-hidden">
            {load.status === "loading" ? (
              <div className="flex h-full items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
              </div>
            ) : load.status === "error" ? (
              <div className="flex h-full items-center justify-center p-6">
                <div className="max-w-md rounded-md border border-status-danger-border bg-status-danger-bg p-4 text-center text-xs text-status-danger-text">
                  {load.message}
                </div>
              </div>
            ) : (
              <div ref={editorHostRef} className="h-full" />
            )}
          </div>
        </div>
      </div>

      <ConfirmDialog
        isOpen={confirmDiscardOpen}
        title="Discard changes?"
        message={
          "The editor contains unsaved changes.\nClosing now will discard them."
        }
        confirmLabel="Discard"
        cancelLabel="Keep editing"
        danger
        onConfirm={() => {
          setConfirmDiscardOpen(false);
          onClose();
        }}
        onCancel={() => setConfirmDiscardOpen(false)}
      />
    </>
  );
}
