import { useEffect, useRef } from "react";
import { Play, X, FileText, Workflow } from "lucide-react";
import type { ScannedFileItem } from "../api/types";

interface SingleMatchPromptModalProps {
  isOpen: boolean;
  file: ScannedFileItem | null;
  onConfirm: () => void;
  onDismiss: () => void;
}

export function SingleMatchPromptModal({
  isOpen,
  file,
  onConfirm,
  onDismiss,
}: SingleMatchPromptModalProps) {
  const confirmButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Enter") {
          e.preventDefault();
          onConfirm();
        } else if (e.key === "Escape") {
          e.preventDefault();
          onDismiss();
        }
      };
      window.addEventListener("keydown", handleKeyDown);
      confirmButtonRef.current?.focus();
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [isOpen, onConfirm, onDismiss]);

  if (!isOpen || !file) return null;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onDismiss}
    >
      <div
        className="w-full max-w-sm rounded-xl border border-line bg-surface p-5 shadow-2xl flex flex-col gap-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line pb-3">
          <div className="flex items-center gap-2 font-semibold text-ink text-sm">
            {file.has_hook ? (
              <Workflow className="h-4 w-4 text-purple-400" />
            ) : (
              <Play className="h-4 w-4 text-emerald-400" />
            )}
            <span>1 File Matched</span>
          </div>
          <button
            onClick={onDismiss}
            className="rounded p-1 text-ink-muted hover:bg-elevated hover:text-ink"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-start gap-3 rounded-lg border border-line bg-elevated/50 p-3">
          <FileText className="h-5 w-5 text-indigo-400 shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <h4 className="text-xs font-semibold text-ink truncate">{file.filename}</h4>
            <p className="text-[11px] text-ink-muted truncate mt-0.5">{file.rel_path || file.path}</p>
            {file.has_hook && (
              <span className="inline-block mt-1 text-[10px] text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded border border-purple-500/20 font-medium">
                Workflow Hook Configured
              </span>
            )}
          </div>
        </div>

        <p className="text-xs text-ink-muted text-center">
          Launch this file now?
        </p>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onDismiss}
            className="flex-1 rounded-md border border-line bg-elevated px-3 py-1.5 text-xs font-medium text-ink hover:bg-surface"
          >
            Dismiss (Esc)
          </button>
          <button
            ref={confirmButtonRef}
            type="button"
            onClick={onConfirm}
            className="flex-1 flex items-center justify-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 shadow-md"
          >
            <Play className="h-3 w-3 fill-current" />
            Launch (Enter)
          </button>
        </div>
      </div>
    </div>
  );
}
