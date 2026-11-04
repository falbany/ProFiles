import { useCallback, useEffect, useRef, useState } from "react";
import { basicSetup, EditorView } from "codemirror";
import { yaml } from "@codemirror/lang-yaml";
import {
  CircleDot,
  ExternalLink,
  FileCode2,
  FilePlus2,
  FlaskConical,
  Play,
  RotateCcw,
  Save,
  SaveAll,
  X,
} from "lucide-react";

import {
  ApiError,
  fetchConfigContent,
  fetchConfigTemplate,
  loadConfigContent,
  openConfigFile,
  saveConfigFile,
  saveConfigFileAs,
  validateConfigContent,
} from "../api/client";
import type { AppConfigData, ConfigContentData, ValidationIssue } from "../api/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { SaveAsDialog } from "./SaveAsDialog";
import { useModalA11y } from "../utils/useModalA11y";

export interface ConfigEditorModalProps {
  open: boolean;
  onClose: () => void;
  /** Called after Apply/Save/Save As succeed, with the fresh AppConfigData. */
  onApplied?: (data: AppConfigData) => void;
}

/** Load lifecycle of the configuration text behind the editor. */
type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: ConfigContentData };

/** Inline feedback banner shown above the editor after a toolbar action. */
type EditorStatus = { kind: "ok" | "error"; text: string } | null;

/** Toolbar action parked behind the "Replace current edits?" confirmation. */
type PendingAction = "new" | "revert";

/** Kinds of the async toolbar actions — the dispatch runner's key. */
type ToolbarActionKind = "new" | "test" | "revert" | "apply" | "save" | "save-as";

/** Target chosen in the Save As dialog, handed back to the save-as flow. */
type SaveAsTarget = { filename: string; directory: string; overwrite: boolean };

/**
 * Compliance gate parked on an in-flight save action: the validation
 * issues block the write until the user either dismisses the gate
 * (resolve(false)) or force-saves (resolve(true)).
 */
type SaveGate = { issues: ValidationIssue[]; resolve: (force: boolean) => void };

/** Save As dialog parked on an in-flight save-as action. */
type SaveAsPrompt = { resolve: (target: SaveAsTarget | null) => void };

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
 * Describe a failed save/save-as for the banner. A 400 whose detail is a
 * validation issue list (the compliance gate contract) renders its issues
 * as data; every other failure — session-trial refusal, hygiene or
 * extension error, 409 existing target, network error — is plain text.
 */
function describeSaveError(err: unknown): { text: string; issues: ValidationIssue[] } {
  if (err instanceof ApiError && Array.isArray(err.detail)) {
    return { text: err.message, issues: err.detail };
  }
  return { text: err instanceof Error ? err.message : String(err), issues: [] };
}

/**
 * Full-screen YAML configuration editor (issue #95). This shell owns the
 * CodeMirror 6 instance, load-on-open, dirty tracking and the guarded
 * Escape/✕ close. The toolbar carries the content actions — New (starter
 * template), Test (in-memory validation), Revert (reload from disk),
 * Apply (session-trial the current text), Save (write the disk-anchored
 * file) and Save As (write a new file, which also anchors a session
 * trial). Save and Save As run the compliance gate first: the text is
 * validated client-side, and issues block the write behind a
 * "Go back and fix / Force save anyway" prompt. The header bar carries
 * the "Open in OS" shortcut, which hands the disk-anchored file to the
 * OS default editor via the existing client call (hidden for a session
 * trial — there is no file behind it to open).
 */
export function ConfigEditorModal({ open, onClose, onApplied }: ConfigEditorModalProps) {
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [dirty, setDirty] = useState(false);
  const [confirmDiscardOpen, setConfirmDiscardOpen] = useState(false);
  /** Banner above the editor — toolbar action outcomes. */
  const [status, setStatus] = useState<EditorStatus>(null);
  /** Validation issues from the Test action and the save gate, listed under the banner. */
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  /** Action awaiting its "Replace current edits?" confirmation. */
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  /** Compliance gate parked on an in-flight save/save-as action. */
  const [gate, setGate] = useState<SaveGate | null>(null);
  /** Save As dialog parked on an in-flight save-as action. */
  const [saveAsPrompt, setSaveAsPrompt] = useState<SaveAsPrompt | null>(null);

  const dialogRef = useRef<HTMLDivElement>(null);
  const editorHostRef = useRef<HTMLDivElement>(null);
  const editorViewRef = useRef<EditorView | null>(null);
  /** Text the editor was seeded with — the baseline for the dirty check. */
  const loadedTextRef = useRef<string>("");
  /**
   * Monotonic id of the most recent toolbar-action dispatch. Each dispatch
   * tags its round trip with the id current at dispatch time; a resolution
   * whose id is no longer current — superseded by a newer action (Test
   * landing after a New replaced the document) or left over from a closed
   * session — is dropped before it can setState.
   */
  const actionSeqRef = useRef(0);
  /** In-flight registry: action kind → seq of its live dispatch. A kind already registered rejects duplicate dispatches (double-click Apply fires one request). */
  const inFlightActionsRef = useRef<Map<ToolbarActionKind, number>>(new Map());

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
      setStatus(null);
      setIssues([]);
      setPendingAction(null);
      setGate(null);
      setSaveAsPrompt(null);
      // Invalidate in-flight toolbar actions so a resolution that lands
      // after close/reopen cannot leak into the next session's state.
      actionSeqRef.current += 1;
      inFlightActionsRef.current.clear();
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

  /** Current editor text — falls back to the baseline before the view mounts. */
  function currentDocText(): string {
    return editorViewRef.current?.state.doc.toString() ?? loadedTextRef.current;
  }

  /**
   * Shared dispatch runner for the four async toolbar actions. Two guards,
   * applied uniformly:
   * 1. Duplicate dispatch — a kind already in flight (double-click) is
   *    swallowed synchronously, so exactly one request leaves per click
   *    burst and `onApplied` fires once per successful Apply.
   * 2. Stale resolution — every dispatch tags its round trip with the
   *    monotonic seq; `work` checks it before any setState so results from
   *    a superseded action or a closed session never render.
   */
  const runToolbarAction = useCallback(
    async (kind: ToolbarActionKind, work: (seq: number) => Promise<void>): Promise<void> => {
      if (inFlightActionsRef.current.has(kind)) return;
      const seq = ++actionSeqRef.current;
      inFlightActionsRef.current.set(kind, seq);
      try {
        await work(seq);
      } finally {
        // Release the gate only if this dispatch still owns it — a
        // close+reopen may already have started a newer dispatch.
        if (inFlightActionsRef.current.get(kind) === seq) {
          inFlightActionsRef.current.delete(kind);
        }
      }
    },
    [],
  );

  /**
   * Replace the editor document with the starter template (New action).
   * The template text becomes the new dirty baseline, so an untouched
   * template is not flagged as unsaved. Only `load` fields that describe
   * the text are updated — the CodeMirror view remounts from it.
   */
  const loadTemplateIntoEditor = useCallback(
    () =>
      runToolbarAction("new", async (seq) => {
        setStatus(null);
        setIssues([]);
        try {
          const template = await fetchConfigTemplate();
          if (seq !== actionSeqRef.current) return; // superseded — drop stale results
          const content = toEditorText(template.content);
          loadedTextRef.current = content;
          setDirty(false);
          setLoad(
            (prev): LoadState =>
              prev.status === "ready"
                ? {
                    status: "ready",
                    data: { ...prev.data, filename: template.filename, content, config_path: null },
                  }
                : prev,
          );
          setStatus({ kind: "ok", text: "New configuration template loaded." });
        } catch (err: unknown) {
          if (seq !== actionSeqRef.current) return;
          setStatus({ kind: "error", text: err instanceof Error ? err.message : String(err) });
        }
      }),
    [runToolbarAction],
  );

  /** Reload the active configuration file from the server (Revert action). */
  const reloadFromServer = useCallback(
    () =>
      runToolbarAction("revert", async (seq) => {
        setStatus(null);
        setIssues([]);
        try {
          const data = await fetchConfigContent();
          if (seq !== actionSeqRef.current) return;
          const content = toEditorText(data.content);
          loadedTextRef.current = content;
          setDirty(false);
          setLoad({ status: "ready", data: { ...data, content } });
          setStatus({ kind: "ok", text: "Configuration reloaded from disk." });
        } catch (err: unknown) {
          if (seq !== actionSeqRef.current) return;
          setStatus({ kind: "error", text: err instanceof Error ? err.message : String(err) });
        }
      }),
    [runToolbarAction],
  );

  /** New action: a dirty editor confirms before its edits are discarded. */
  function requestNew() {
    if (isDirty(editorViewRef.current, loadedTextRef.current)) {
      setPendingAction("new");
      return;
    }
    void loadTemplateIntoEditor();
  }

  /** Revert action: same guarded pattern as New, reloading from the server. */
  function requestRevert() {
    if (isDirty(editorViewRef.current, loadedTextRef.current)) {
      setPendingAction("revert");
      return;
    }
    void reloadFromServer();
  }

  /**
   * Test action: validate the current text in memory. A valid result
   * lights the ok banner; issues are listed above the editor verbatim.
   */
  const runValidation = useCallback(
    () =>
      runToolbarAction("test", async (seq) => {
        if (load.status !== "ready") return;
        try {
          const result = await validateConfigContent(load.data.filename, currentDocText());
          if (seq !== actionSeqRef.current) return; // superseded — drop stale results
          setIssues(result.issues);
          setStatus(
            result.valid
              ? { kind: "ok", text: "Configuration is valid." }
              : {
                  kind: "error",
                  text: `Validation failed with ${result.issues.length} issue${result.issues.length === 1 ? "" : "s"}.`,
                },
          );
        } catch (err: unknown) {
          if (seq !== actionSeqRef.current) return;
          setIssues([]);
          setStatus({ kind: "error", text: err instanceof Error ? err.message : String(err) });
        }
      }),
    [load, runToolbarAction],
  );

  /**
   * Apply action: trial the current text as the session configuration.
   * Success fires `onApplied` with the applied AppConfigData; a 400
   * rejection surfaces the server's plain-string detail in the banner.
   */
  const applyContent = useCallback(
    () =>
      runToolbarAction("apply", async (seq) => {
        if (load.status !== "ready") return;
        try {
          const data = await loadConfigContent(load.data.filename, currentDocText());
          if (seq !== actionSeqRef.current) return; // superseded — drop stale results
          setStatus({ kind: "ok", text: "Configuration applied (session trial)." });
          onApplied?.(data);
        } catch (err: unknown) {
          if (seq !== actionSeqRef.current) return;
          setStatus({ kind: "error", text: err instanceof Error ? err.message : String(err) });
        }
      }),
    [load, onApplied, runToolbarAction],
  );

  /**
   * Park the compliance gate on the in-flight action: the gate's buttons
   * resolve the promise the save flow is awaiting. Clearing the gate state
   * happens inside the resolver so either exit closes it immediately,
   * even when the action turns out superseded (stale-seq check at the
   * call site drops the write but still closes the dialog).
   */
  const awaitGateDecision = useCallback(
    (issues: ValidationIssue[]) =>
      new Promise<boolean>((resolve) => {
        setGate({
          issues,
          resolve: (force: boolean) => {
            setGate(null);
            resolve(force);
          },
        });
      }),
    [],
  );

  /** Park the Save As dialog on the in-flight save-as action (null = cancelled). */
  const awaitSaveAsTarget = useCallback(
    () =>
      new Promise<SaveAsTarget | null>((resolve) => {
        setSaveAsPrompt({
          resolve: (target: SaveAsTarget | null) => {
            setSaveAsPrompt(null);
            resolve(target);
          },
        });
      }),
    [],
  );

  /**
   * Shared success surface for Save and Save As: the saved text becomes
   * the new dirty baseline, the response's fresh AppConfigData refreshes
   * the header (a Save As re-anchors the file, re-enabling Save) and
   * drives the same `onApplied` path as Apply.
   */
  const markSaved = useCallback(
    (data: AppConfigData, savedText: string) => {
      loadedTextRef.current = savedText;
      setDirty(false);
      setIssues([]);
      setGate(null);
      setSaveAsPrompt(null);
      if (data.config_path) {
        const name =
          data.config_path.split(/[\\/]/).pop() || data.title || "configuration";
        setLoad((prev): LoadState => {
          if (prev.status !== "ready") return prev;
          // Only a changed anchor (Save As re-target, session trial now
          // anchored) refreshes `load` — and with it the CodeMirror view,
          // which remounts from `data.content`, so the saved text must
          // ride along. An unchanged anchor (plain Save) must NOT bump the
          // load object: the remount would rebuild the view from the stale
          // pre-edit `content` and silently discard the user's edits.
          const anchorChanged =
            prev.data.filename !== name ||
            prev.data.config_path !== data.config_path ||
            prev.data.session_trial;
          if (!anchorChanged) return prev;
          return {
            status: "ready",
            data: {
              ...prev.data,
              filename: name,
              config_path: data.config_path,
              session_trial: false,
              content: savedText,
            },
          };
        });
      }
      onApplied?.(data);
    },
    [onApplied],
  );

  /** Shared error surface for Save and Save As (validation lists render as data). */
  const reportSaveError = useCallback((err: unknown) => {
    const described = describeSaveError(err);
    setGate(null);
    setSaveAsPrompt(null);
    setIssues(described.issues);
    setStatus({ kind: "error", text: described.text });
  }, []);

  /**
   * Validate → decide → write flow shared by Save and Save As. The
   * client-side validation runs first so the gate can offer "force"
   * before anything is written; the decision (and, for Save As, the
   * dialog) parks on the in-flight action, so duplicate clicks are
   * swallowed and a superseding action (close, New) invalidates the
   * parked flow via the stale-seq check.
   */
  const runSaveFlow = useCallback(
    (kind: Extract<ToolbarActionKind, "save" | "save-as">, filename: string) =>
      runToolbarAction(kind, async (seq) => {
        if (load.status !== "ready") return;
        const text = currentDocText();
        setStatus(null);
        setIssues([]);
        try {
          const result = await validateConfigContent(filename, text);
          if (seq !== actionSeqRef.current) return; // superseded — drop stale results
          let force = false;
          if (!result.valid) {
            setIssues(result.issues);
            force = await awaitGateDecision(result.issues);
            if (seq !== actionSeqRef.current) return; // superseded while parked
            if (!force) {
              setStatus({
                kind: "error",
                text: "Save cancelled — fix the listed issues, or force-save anyway.",
              });
              return;
            }
          }
          if (kind === "save-as") {
            const target = await awaitSaveAsTarget();
            if (seq !== actionSeqRef.current) return; // superseded while parked
            if (target === null) return; // cancelled — no save call
            const data = await saveConfigFileAs({
              content: text,
              filename: target.filename,
              directory: target.directory,
              force,
              overwrite: target.overwrite,
            });
            if (seq !== actionSeqRef.current) return;
            markSaved(data, text);
            setStatus({ kind: "ok", text: `Configuration saved as ${target.filename}.` });
          } else {
            const data = await saveConfigFile(text, force);
            if (seq !== actionSeqRef.current) return;
            markSaved(data, text);
            setStatus({ kind: "ok", text: `Configuration saved to ${filename}.` });
          }
        } catch (err: unknown) {
          if (seq !== actionSeqRef.current) return;
          reportSaveError(err);
        }
      }),
    [awaitGateDecision, awaitSaveAsTarget, load, markSaved, reportSaveError, runToolbarAction],
  );

  const runSave = useCallback(
    () => runSaveFlow("save", load.status === "ready" ? load.data.filename : ""),
    [load, runSaveFlow],
  );

  const runSaveAs = useCallback(
    () => runSaveFlow("save-as", load.status === "ready" ? load.data.filename : ""),
    [load, runSaveFlow],
  );

  /**
   * Ctrl/Cmd+S: Save on a disk-anchored config, Apply fallback for a
   * session trial (nothing to write to). Capture-phase window listener so
   * it wins over CodeMirror and the browser's own save dialog; the
   * latest-ref indirection keeps the listener registered once while
   * always dispatching through current state. Parked dialogs (gate, Save
   * As, discard warnings) swallow the shortcut.
   */
  const modSHandlerRef = useRef<() => void>(() => {});
  modSHandlerRef.current = () => {
    if (load.status !== "ready") return;
    if (gate !== null || saveAsPrompt !== null || confirmDiscardOpen || pendingAction !== null) {
      return;
    }
    if (load.data.config_path !== null) void runSave();
    else void applyContent();
  };
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        (event.metaKey || event.ctrlKey) &&
        !event.altKey &&
        !event.shiftKey &&
        event.key.toLowerCase() === "s"
      ) {
        event.preventDefault();
        event.stopPropagation();
        modSHandlerRef.current();
      }
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  const filename = load.status === "ready" ? load.data.filename : "";
  const sessionTrial = load.status === "ready" ? load.data.session_trial : false;
  const toolbarDisabled = load.status !== "ready";
  /** Save only exists when the text is anchored to a file on disk. */
  const diskAnchored = load.status === "ready" && load.data.config_path !== null;

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
              {/* Only meaningful for a disk-anchored config: on a session
                  trial the open-config action would hand the OS the
                  CWD-resolved fallback — possibly an unrelated pre-existing
                  .profiles file or a NOT_FOUND — so the shortcut hides, the
                  same way Save does. */}
              {diskAnchored && (
                <button
                  type="button"
                  onClick={handleOpenInOS}
                  title="Open the configuration file with the OS default editor"
                  className="btn inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-secondary hover:bg-elevated hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  Open in OS
                </button>
              )}
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

          {/* Toolbar — content actions and persistence. */}
          <div
            data-testid="editor-toolbar"
            className="flex shrink-0 items-center gap-2 border-b border-line px-5 py-2"
          >
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={requestNew}
                disabled={toolbarDisabled}
                title="Load the starter configuration template"
                className="btn btn-secondary px-3 py-1.5"
              >
                <FilePlus2 className="h-3.5 w-3.5" />
                New
              </button>
              <button
                type="button"
                onClick={() => void runValidation()}
                disabled={toolbarDisabled}
                title="Validate the editor content in memory"
                className="btn btn-secondary px-3 py-1.5"
              >
                <FlaskConical className="h-3.5 w-3.5" />
                Test
              </button>
              <button
                type="button"
                onClick={requestRevert}
                disabled={toolbarDisabled}
                title="Discard edits and reload the file from disk"
                className="btn btn-secondary px-3 py-1.5"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Revert
              </button>
              {/* Hidden for a session trial (and after New): nothing on disk
                  to overwrite — Save As is the way to anchor those. */}
              {diskAnchored && (
                <button
                  type="button"
                  onClick={() => void runSave()}
                  disabled={toolbarDisabled}
                  title="Save to the configuration file on disk (Ctrl/Cmd+S)"
                  className="btn btn-secondary px-3 py-1.5"
                >
                  <Save className="h-3.5 w-3.5" />
                  Save
                </button>
              )}
              <button
                type="button"
                onClick={() => void runSaveAs()}
                disabled={toolbarDisabled}
                title="Save the configuration to a new file — also anchors a session trial onto disk"
                className="btn btn-secondary px-3 py-1.5"
              >
                <SaveAll className="h-3.5 w-3.5" />
                Save As
              </button>
              <button
                type="button"
                onClick={() => void applyContent()}
                disabled={toolbarDisabled}
                title="Trial the editor content as the session configuration"
                className="btn btn-primary px-3 py-1.5 font-semibold"
              >
                <Play className="h-3.5 w-3.5" />
                Apply
              </button>
            </div>
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

          {/* Inline feedback banner + validation issue list (Test outcome). */}
          {(status !== null || issues.length > 0) && (
            <div className="shrink-0 border-b border-line px-5 py-2">
              {status !== null && (
                <div
                  data-testid="editor-status"
                  aria-live="polite"
                  className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
                    status.kind === "ok"
                      ? "border-status-success-border bg-status-success-bg text-status-success-text"
                      : "border-status-danger-border bg-status-danger-bg text-status-danger-text"
                  }`}
                >
                  {status.text}
                </div>
              )}
              {issues.length > 0 && (
                <ul data-testid="editor-issues" className="mt-1 space-y-1">
                  {issues.map((issue, index) => (
                    <li
                      key={`${issue.severity}-${index}`}
                      className={`rounded-md border px-3 py-1.5 text-xs ${
                        issue.severity === "error"
                          ? "border-status-danger-border bg-status-danger-bg text-status-danger-text"
                          : "border-chip-amber-border bg-chip-amber-bg text-chip-amber-text"
                      }`}
                    >
                      {issue.message}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

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

      {/* Same discard-warning pattern for New/Revert on a dirty editor. */}
      <ConfirmDialog
        isOpen={pendingAction !== null}
        title="Replace current edits?"
        message={
          pendingAction === "revert"
            ? "The editor contains unsaved changes.\nReverting will discard them and reload the file from disk."
            : "The editor contains unsaved changes.\nLoading the starter template will discard them."
        }
        confirmLabel="Replace"
        cancelLabel="Keep editing"
        danger
        onConfirm={() => {
          const action = pendingAction;
          setPendingAction(null);
          if (action === "new") void loadTemplateIntoEditor();
          else if (action === "revert") void reloadFromServer();
        }}
        onCancel={() => setPendingAction(null)}
      />

      {/* Compliance gate: issues found by the client-side pre-validation
          block the write until dismissed or force-saved (issue #95). */}
      <ConfirmDialog
        isOpen={gate !== null}
        title="Save with validation issues?"
        danger
        message={
          <>
            <p>
              Saving will write these issues to disk; the file may fail to load
              until they are fixed.
            </p>
            <ul className="mt-2 space-y-1">
              {gate?.issues.map((issue, index) => (
                <li
                  key={`${issue.severity}-${index}`}
                  className={`rounded-md border px-3 py-1.5 text-xs ${
                    issue.severity === "error"
                      ? "border-status-danger-border bg-status-danger-bg text-status-danger-text"
                      : "border-chip-amber-border bg-chip-amber-bg text-chip-amber-text"
                  }`}
                >
                  {issue.message}
                </li>
              ))}
            </ul>
          </>
        }
        confirmLabel="Force save anyway"
        cancelLabel="Go back and fix"
        onConfirm={() => gate?.resolve(true)}
        onCancel={() => gate?.resolve(false)}
      />

      {/* Target selection for Save As; overwrite is confirmed inside. */}
      <SaveAsDialog
        open={saveAsPrompt !== null}
        onCancel={() => saveAsPrompt?.resolve(null)}
        onConfirm={(target) => saveAsPrompt?.resolve(target)}
      />
    </>
  );
}
