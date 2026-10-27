import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Check, ChevronRight, Folder, FolderOpen, Home, Loader2, X } from "lucide-react";

export interface DirectoryPickerModalProps {
  isOpen: boolean;
  initialPath?: string;
  onClose: () => void;
  onSelect: (path: string) => void;
}

interface BrowseEntry {
  name: string;
  path: string;
  is_dir: boolean;
}

interface BrowseResult {
  current_path: string;
  parent_path: string | null;
  items: BrowseEntry[];
}

export function DirectoryPickerModal({
  isOpen,
  initialPath,
  onClose,
  onSelect,
}: DirectoryPickerModalProps) {
  const [browseData, setBrowseData] = useState<BrowseResult | null>(null);
  const [selectedDir, setSelectedDir] = useState<string | null>(null);
  const [pathInput, setPathInput] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const pathInputRef = useRef<HTMLInputElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) {
      previousFocusRef.current?.focus();
      return;
    }

    previousFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    setError(null);
    void browse(initialPath || "");
    const focusFrame = requestAnimationFrame(() => pathInputRef.current?.focus());

    return () => {
      cancelAnimationFrame(focusFrame);
      previousFocusRef.current?.focus();
    };
  }, [isOpen]);

  const browse = async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/fs/browse?path=${encodeURIComponent(path)}`);
      if (!res.ok) throw new Error("Failed to browse directory");
      const data: BrowseResult = await res.json();
      setBrowseData(data);
      setSelectedDir(data.current_path);
      setPathInput(data.current_path);
    } catch (err: any) {
      setError(err.message || "Navigation failed");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = () => {
    const target = pathInput.trim() || selectedDir;
    if (target) {
      onSelect(target);
      onClose();
    }
  };

  const handleDialogKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;

    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable?.length) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-3 backdrop-blur-sm sm:p-6"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="directory-picker-title"
        onKeyDown={handleDialogKeyDown}
        className="flex h-[min(84dvh,760px)] max-h-[calc(100dvh-1.5rem)] w-[min(94vw,960px)] min-h-0 flex-col overflow-hidden rounded-xl border border-frame-line glass-panel sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-chip-indigo-bg">
              <FolderOpen className="h-5 w-5 text-chip-indigo-text" />
            </span>
            <div className="min-w-0">
              <h2 id="directory-picker-title" className="text-sm font-semibold text-ink">
                Select a directory
              </h2>
              <p className="truncate font-mono text-xs text-ink-muted">
                {browseData?.current_path || ""}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close directory picker"
            title="Close"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-ink-muted transition-colors hover:bg-elevated hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="border-b border-line px-4 py-3 sm:px-5">
          <label
            htmlFor="directory-picker-path"
            className="mb-1.5 block text-xs font-medium text-ink-secondary"
          >
            Location
          </label>
          <div className="flex min-w-0 items-center gap-1.5">
          <input
            ref={pathInputRef}
            id="directory-picker-path"
            type="text"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") browse(pathInput.trim());
            }}
            placeholder="/path/to/directory"
            className="h-10 min-w-0 flex-1 rounded-lg border border-line bg-elevated px-2.5 font-mono text-sm text-ink outline-none placeholder:text-ink-faint transition-colors hover:bg-surface-strong focus-visible:border-indigo-500 focus-visible:ring-2 focus-visible:ring-indigo-500/30"
          />
          <button
            type="button"
            onClick={() => browse(pathInput.trim())}
            className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-lg border border-line bg-elevated px-3.5 text-sm font-medium text-ink-secondary transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
          >
            Go
          </button>
          <button
            type="button"
            onClick={() => browse("")}
            aria-label="Home directory"
            title="Home directory"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-line bg-elevated text-ink-secondary transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
          >
            <Home className="h-4 w-4" />
          </button>
          {browseData?.parent_path && (
            <button
              type="button"
              onClick={() => browse(browseData.parent_path!)}
              aria-label="Parent directory"
              title="Parent directory"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-line bg-elevated text-ink-secondary transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            >
              <ChevronRight className="h-4 w-4 rotate-180" />
            </button>
          )}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2 sm:px-3 sm:py-3" aria-busy={loading}>
          {loading ? (
            <div className="flex h-full items-center justify-center gap-2.5 text-sm text-ink-muted">
              <Loader2 className="h-5 w-5 animate-spin text-chip-indigo-text" />
              <span role="status">Loading directories…</span>
            </div>
          ) : error ? (
            <div role="alert" className="flex h-full flex-col items-center justify-center gap-2.5 text-center">
              <p className="text-sm text-status-danger-text">{error}</p>
              <button
                type="button"
                onClick={() => browse(pathInput || browseData?.current_path || "")}
                className="min-h-10 rounded-lg border border-line bg-elevated px-3.5 text-sm text-ink-secondary hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
              >
                Retry
              </button>
            </div>
          ) : (
            <ul className="space-y-0.5">
              {browseData?.items
                .filter((item) => item.is_dir)
                .map((item) => (
                  <li key={item.path}>
                    <button
                      type="button"
                      onClick={() => browse(item.path)}
                      onDoubleClick={() => {
                        setPathInput(item.path);
                        onSelect(item.path);
                        onClose();
                      }}
                      className={`flex min-h-10 w-full items-center justify-between rounded-lg px-3 py-1.5 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-400 ${
                        selectedDir === item.path
                          ? "bg-chip-indigo-bg text-chip-indigo-text"
                          : "text-ink-secondary hover:bg-elevated hover:text-ink"
                      }`}
                    >
                      <span className="flex min-w-0 items-center gap-2.5">
                        <Folder className="h-5 w-5 shrink-0 text-chip-indigo-text" />
                        <span className="truncate">{item.name}</span>
                      </span>
                      {selectedDir === item.path && <Check className="h-4 w-4 shrink-0 text-chip-indigo-text" />}
                    </button>
                  </li>
                ))}
              {browseData?.items.filter((item) => item.is_dir).length === 0 && (
                <li className="flex h-full min-h-36 flex-col items-center justify-center gap-2.5 text-center text-sm text-ink-muted">
                  <FolderOpen className="h-7 w-7 text-ink-faint" />
                  No subdirectories found
                </li>
              )}
            </ul>
          )}
        </div>

        <div className="flex flex-col gap-2 border-t border-line px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div className="min-w-0 flex-1">
            <p className="mb-0.5 text-xs font-medium text-ink-muted">Selected folder</p>
            <p
              className="truncate font-mono text-sm text-ink"
              title={selectedDir || pathInput}
            >
              {selectedDir || pathInput || "—"}
            </p>
          </div>
          <div className="flex shrink-0 justify-end gap-1.5">
            <button
              type="button"
              onClick={onClose}
              className="min-h-10 rounded-lg border border-line bg-elevated px-3.5 text-sm text-ink-secondary transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400">
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={!pathInput.trim()}
              className="btn btn-primary min-h-10 rounded-lg px-4 text-sm font-semibold"
            >
              <FolderOpen className="h-4 w-4" />
              Select folder
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
