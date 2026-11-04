import Tooltip from "./Tooltip";
import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ChevronRight, Folder, FolderOpen, Home, Loader2, Save } from "lucide-react";

import { browseDirectory } from "../api/client";
import type { BrowseResult } from "../api/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { useModalA11y } from "../utils/useModalA11y";

export interface SaveAsDialogProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: (params: { filename: string; directory: string; overwrite: boolean }) => void;
}

/** Extensions the server whitelists for a save-as target — mirrored client-side. */
const SAVE_AS_EXTENSIONS = [".profiles", ".profiles.yaml"];

/**
 * Normalize the user-typed filename against the server's extension
 * whitelist, which is case-insensitive (`name.lower().endswith(...)` in
 * `routes/config.py`) — mirrored here so e.g. `BACKUP.PROFILES` is
 * accepted and sent verbatim (the server handles its own casing). A bare
 * name gets `.profiles` appended; an empty stem (`".profiles"`) or a
 * stray space before the extension is rejected; anything else is
 * rejected. Returns `null` when the name cannot be saved as-is.
 */
function normalizeSaveAsFilename(raw: string): string | null {
  const name = raw.trim();
  if (!name) return null;
  const lowered = name.toLowerCase();
  const matched = SAVE_AS_EXTENSIONS.find((ext) => lowered.endsWith(ext));
  if (matched !== undefined) {
    const stem = name.slice(0, name.length - matched.length);
    if (!stem.trim() || stem !== stem.trimEnd()) return null;
    return name;
  }
  if (!lowered.includes(".")) return `${name}.profiles`;
  return null;
}

/**
 * "Save configuration as" dialog (issue #95): pick a directory via the
 * shared /api/fs/browse listing (same pattern as DirectoryPickerModal),
 * type a target filename, and hand `{filename, directory, overwrite}` to
 * the caller. Overwrite is only confirmed with true when the chosen name
 * matches a file in the current listing and the user accepts the
 * "Replace?" prompt; the server still guards with 409. Validation of the
 * content itself is the caller's compliance gate — this dialog is pure
 * target selection.
 */
export function SaveAsDialog({ open, onCancel, onConfirm }: SaveAsDialogProps) {
  const [browseData, setBrowseData] = useState<BrowseResult | null>(null);
  const [pathInput, setPathInput] = useState<string>("");
  const [filename, setFilename] = useState<string>("");
  const [filenameError, setFilenameError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** Overwrite target parked behind the "Replace configuration?" prompt. */
  const [pendingOverwrite, setPendingOverwrite] = useState<{
    filename: string;
    directory: string;
  } | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const filenameInputRef = useRef<HTMLInputElement>(null);
  const pathInputRef = useRef<HTMLInputElement>(null);

  const browse = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await browseDirectory(path);
      setBrowseData(data);
      setPathInput(data.current_path);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    setFilename("");
    setFilenameError(null);
    setPendingOverwrite(null);
    // Reuse the last browsed location across opens (pathInput persists
    // while the modal stays mounted); first open lands on the home dir.
    void browse(pathInput);
    const focusFrame = requestAnimationFrame(() => filenameInputRef.current?.focus());
    return () => cancelAnimationFrame(focusFrame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const handleDialogKeyDown = useModalA11y({
    isOpen: open,
    onClose: onCancel,
    dialogRef,
    initialFocusRef: filenameInputRef,
  });

  function handleConfirm() {
    if (!browseData) return;
    const normalized = normalizeSaveAsFilename(filename);
    if (normalized === null) {
      setFilenameError(
        "Not a ProFiles configuration file. Allowed extensions: .profiles, .profiles.yaml",
      );
      return;
    }
    setFilenameError(null);
    const directory = pathInput.trim() || browseData.current_path;
    // The overwrite check is only sound for the directory whose listing is
    // on screen: a typed-but-not-browsed Location has unknown contents, so
    // confirming against it could consent to replacing a file that was
    // never listed. Such targets go through with overwrite:false and the
    // server's 409 guard answers instead.
    const browsedHere = pathInput.trim() === browseData.current_path;
    const exists =
      browsedHere && browseData.items.some((item) => !item.is_dir && item.name === normalized);
    if (exists) {
      setPendingOverwrite({ filename: normalized, directory });
      return;
    }
    onConfirm({ filename: normalized, directory, overwrite: false });
  }

  if (!open) return null;

  const directories = browseData?.items.filter((item) => item.is_dir) ?? [];

  return (
    <>
      <div
        className="animate-overlay-in fixed inset-0 z-[var(--z-modal)] flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
        onClick={onCancel}
      >
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="save-as-dialog-title"
          onKeyDown={handleDialogKeyDown}
          onClick={(e) => e.stopPropagation()}
          className="animate-modal-in flex max-h-[calc(100dvh-2rem)] w-[min(94vw,560px)] flex-col overflow-hidden rounded-xl border border-frame-line glass-panel sm:rounded-2xl"
        >
          {/* Header bar */}
          <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-3">
            <div className="flex min-w-0 items-center gap-2.5">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-chip-indigo-bg">
                <Save className="h-4 w-4 text-chip-indigo-text" />
              </span>
              <div className="min-w-0">
                <h2 id="save-as-dialog-title" className="text-sm font-semibold text-ink">
                  Save configuration as
                </h2>
                <p className="truncate font-mono text-xs text-ink-muted">
                  {browseData?.current_path || "\u2026"}
                </p>
              </div>
            </div>
          </div>

          {/* Target directory navigation — DirectoryPickerModal's pattern. */}
          <div className="border-b border-line px-5 py-3">
            <label
              htmlFor="save-as-path"
              className="mb-1.5 block text-xs font-medium text-ink-secondary"
            >
              Location
            </label>
            <div className="flex min-w-0 items-center gap-1.5">
              <input
                ref={pathInputRef}
                id="save-as-path"
                type="text"
                value={pathInput}
                onChange={(e) => setPathInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void browse(pathInput.trim());
                }}
                placeholder="/path/to/directory"
                className="h-9 min-w-0 flex-1 rounded-lg border border-line bg-elevated px-2.5 font-mono text-sm text-ink outline-none placeholder:text-ink-faint transition-colors hover:bg-surface-strong focus-visible:border-indigo-500 focus-visible:ring-2 focus-visible:ring-indigo-500/30"
              />
              <button
                type="button"
                onClick={() => void browse(pathInput.trim())}
                className="inline-flex h-9 shrink-0 items-center rounded-lg border border-line bg-elevated px-3 text-sm font-medium text-ink-secondary transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
              >
                Go
              </button>
              <Tooltip text="Home directory" block={false}>
                <button
                  type="button"
                  onClick={() => void browse("")}
                  aria-label="Home directory"
                  className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-line bg-elevated text-ink-secondary transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                >
                  <Home className="h-4 w-4" />
                </button>
              </Tooltip>
              {browseData?.parent_path && (
                <Tooltip text="Parent directory" block={false}>
                  <button
                    type="button"
                    onClick={() => void browse(browseData.parent_path!)}
                    aria-label="Parent directory"
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-line bg-elevated text-ink-secondary transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                  >
                    <ChevronRight className="h-4 w-4 rotate-180" />
                  </button>
                </Tooltip>
              )}
            </div>
          </div>

          {/* Directory listing */}
          <div className="min-h-24 flex-1 overflow-y-auto px-2 py-2 sm:px-3" aria-busy={loading}>
            {loading ? (
              <div className="flex h-full items-center justify-center gap-2.5 text-sm text-ink-muted">
                <Loader2 className="h-5 w-5 animate-spin text-chip-indigo-text" />
                <span role="status">Loading directories…</span>
              </div>
            ) : error ? (
              <div
                role="alert"
                className="flex h-full flex-col items-center justify-center gap-2.5 text-center"
              >
                <p className="text-sm text-status-danger-text">{error}</p>
                <button
                  type="button"
                  onClick={() => void browse(pathInput || browseData?.current_path || "")}
                  className="min-h-9 rounded-lg border border-line bg-elevated px-3.5 text-sm text-ink-secondary hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                >
                  Retry
                </button>
              </div>
            ) : (
              <ul className="space-y-0.5">
                {directories.map((item) => (
                  <li key={item.path}>
                    <button
                      type="button"
                      onClick={() => void browse(item.path)}
                      className="flex min-h-9 w-full items-center gap-2.5 rounded-lg px-3 py-1.5 text-left text-sm text-ink-secondary transition-colors hover:bg-elevated hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-400"
                    >
                      <Folder className="h-4 w-4 shrink-0 text-chip-indigo-text" />
                      <span className="truncate">{item.name}</span>
                    </button>
                  </li>
                ))}
                {directories.length === 0 && (
                  <li className="flex min-h-16 flex-col items-center justify-center gap-2 text-center text-sm text-ink-muted">
                    <FolderOpen className="h-6 w-6 text-ink-faint" />
                    No subdirectories found
                  </li>
                )}
              </ul>
            )}
          </div>

          {/* Filename + actions */}
          <div className="shrink-0 border-t border-line px-5 py-3">
            <label
              htmlFor="save-as-filename"
              className="mb-1.5 block text-xs font-medium text-ink-secondary"
            >
              File name
            </label>
            <input
              ref={filenameInputRef}
              id="save-as-filename"
              type="text"
              value={filename}
              onChange={(e) => {
                setFilename(e.target.value);
                setFilenameError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && filename.trim()) handleConfirm();
              }}
              placeholder="machine.profiles"
              className="h-9 w-full rounded-lg border border-line bg-elevated px-2.5 font-mono text-sm text-ink outline-none placeholder:text-ink-faint transition-colors hover:bg-surface-strong focus-visible:border-indigo-500 focus-visible:ring-2 focus-visible:ring-indigo-500/30"
            />
            {filenameError && (
              <p role="alert" data-testid="save-as-error" className="mt-1.5 text-xs text-status-danger-text">
                {filenameError}
              </p>
            )}
            <div className="mt-3 flex justify-end gap-1.5">
              <button
                type="button"
                onClick={onCancel}
                className="min-h-9 rounded-lg border border-line bg-elevated px-3.5 text-sm text-ink-secondary transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                disabled={!filename.trim() || !browseData || loading}
                title="Save the configuration to the selected folder"
                className="btn btn-primary min-h-9 rounded-lg px-4 text-sm font-semibold"
              >
                <Check className="h-4 w-4" />
                Save
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Replace prompt — only when the typed name matches a listed file. */}
      <ConfirmDialog
        isOpen={pendingOverwrite !== null}
        title="Replace configuration?"
        message={`A configuration named "${pendingOverwrite?.filename}" already exists in this folder.\nSaving will replace it.`}
        confirmLabel="Replace"
        cancelLabel="Keep existing"
        danger
        onConfirm={() => {
          const target = pendingOverwrite;
          setPendingOverwrite(null);
          if (target) onConfirm({ ...target, overwrite: true });
        }}
        onCancel={() => setPendingOverwrite(null)}
      />
    </>
  );
}
