import { useEffect, useRef, useState } from "react";
import { X, File, Folder, Calendar, Hash, Copy, Check, QrCode, Eye, Play, FolderOpen, Lock, EyeOff, Link2 } from "lucide-react";
import type { FileMetadata, ScannedFileItem } from "../api/types";
import { fetchFileMetadata, launchFile, openFolder, revealFile } from "../api/client";
import { BarcodeModal } from "./BarcodeModal";
import {
  buildPropertiesSummary,
  compactPath,
  formatFileSize,
  humanizeTimestamp,
  parentDirectory,
  truncateMiddle,
} from "../utils/fileProperties";

export interface FilePropertiesModalProps {
  isOpen: boolean;
  file: ScannedFileItem | null;
  onClose: () => void;
}

export function FilePropertiesModal({ isOpen, file, onClose }: FilePropertiesModalProps) {
  const [metadata, setMetadata] = useState<FileMetadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [showQrModal, setShowQrModal] = useState(false);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  /** Controller of the in-flight metadata request; older epochs never write state. */
  const activeFetchRef = useRef<AbortController | null>(null);

  // Restore focus and reset transient UI state when the modal closes.
  useEffect(() => {
    if (!isOpen) {
      previousFocusRef.current?.focus();
      setShowQrModal(false);
    }
  }, [isOpen]);

  // Fetch metadata for the opened file; aborts on close or file change so a
  // slow response for a previous file can never overwrite the current one.
  useEffect(() => {
    if (!isOpen || !file) return;

    const controller = new AbortController();
    activeFetchRef.current = controller;
    setMetadata(null);
    setActionMessage(null);
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const meta = await fetchFileMetadata(file.path, controller.signal);
        if (activeFetchRef.current !== controller) return;
        setMetadata(meta);
      } catch (err) {
        if (activeFetchRef.current !== controller) return;
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load properties");
      } finally {
        if (activeFetchRef.current === controller) setLoading(false);
      }
    })();

    return () => {
      activeFetchRef.current = null;
      controller.abort();
    };
  }, [isOpen, file]);

  // Lock background scrolling while the modal is open.
  useEffect(() => {
    if (!isOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen]);

  // Escape closes the modal; Tab is trapped inside the dialog.
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        // The nested barcode modal handles its own Escape.
        if (showQrModal) return;
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const dialog = dialogRef.current;
      if (!dialog) return;
      const focusable = Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
      ).filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      if (event.shiftKey) {
        if (active === first || !dialog.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, showQrModal, onClose]);

  // Initial focus goes to the dialog's first button.
  useEffect(() => {
    if (!isOpen) return;
    const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    previousFocusRef.current = active;
    const focusFrame = requestAnimationFrame(() => {
      dialogRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    });
    return () => cancelAnimationFrame(focusFrame);
  }, [isOpen]);

  const copyToClipboard = async (text: string, fieldId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(fieldId);
      setTimeout(() => setCopiedField(null), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const runFileAction = async (
    actionId: string,
    successMessage: string,
    run: () => Promise<unknown>,
  ) => {
    setActionBusy(actionId);
    setActionMessage(null);
    try {
      await run();
      setActionMessage(successMessage);
    } catch {
      setActionMessage("Action failed");
    } finally {
      setActionBusy(null);
    }
  };

  const actionButtonClass = (actionId: string) => {
    const styles: Record<string, string> = {
      reveal: "bg-chip-sky-bg text-chip-sky-text hover:brightness-95 border-chip-sky-border focus-visible:ring-sky-400/60",
      launch: "bg-emerald-600 text-white hover:bg-emerald-500 border-emerald-500/30 font-semibold focus-visible:ring-emerald-400",
      folder: "bg-chip-amber-bg text-chip-amber-text hover:brightness-95 border-chip-amber-border focus-visible:ring-amber-400/60",
    };
    return `inline-flex items-center gap-1 rounded-md border px-3 py-2 text-xs ${
      styles[actionId] ?? "bg-chip-indigo-bg text-chip-indigo-text hover:brightness-95 border-chip-indigo-border"
    } disabled:opacity-40 disabled:cursor-not-allowed`;
  };

  const renderPropertyRow = (
    label: string,
    value: string,
    fieldId: string,
    isMonospace = false,
    displayValue?: string
  ) => (
    <div className="flex items-start gap-2 py-1.5 group">
      <span className="text-ink-muted min-w-[100px] text-xs">{label}:</span>
      <div className="flex-1 min-w-0">
        <span className={`text-ink text-xs break-all ${isMonospace ? "font-mono" : ""}`}>
          {displayValue ?? value}
        </span>
      </div>
      <button
        onClick={() => copyToClipboard(value, fieldId)}
        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-elevated"
        title="Copy to clipboard"
        aria-label={`Copy ${label}`}
      >
        {copiedField === fieldId ? (
          <Check className="h-3.5 w-3.5 text-emerald-400" />
        ) : (
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
        )}
      </button>
    </div>
  );

  const renderCard = (title: string, icon: React.ReactNode, content: React.ReactNode) => (
    <div className="rounded-lg border border-line bg-elevated p-4">
      <div className="mb-1 flex items-center gap-2">
        {icon}
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</span>
      </div>
      {content}
    </div>
  );

  /** Full-width clickable path bar; copies the complete path on click. */
  const renderPathBar = () => (
    <button
      onClick={() => void copyToClipboard(metadata!.path, "path")}
      className="group mb-3 flex w-full items-center gap-2 rounded-lg border border-line bg-elevated px-3 py-2 text-left hover:bg-surface"
      title="Click to copy full path"
    >
      <Folder className="text-amber-400 h-4 w-4 flex-shrink-0" />
      <span className="text-ink min-w-0 flex-1 truncate font-mono text-xs">
        {compactPath(metadata!.path)}
      </span>
      {copiedField === "path" ? (
        <Check className="text-emerald-400 h-3.5 w-3.5" />
      ) : (
        <Copy className="text-ink-muted h-3.5 w-3.5" />
      )}
    </button>
  );

  if (!isOpen || !file) return null;
  // Captures the narrowed file so JSX callbacks keep a non-null type.
  const activeFile = file;
  const directory = parentDirectory(activeFile.path);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="properties-modal-title"
    >
      {/* Backdrop — covers the whole overlay; clicking outside closes */}
      <div className="absolute inset-0" onClick={onClose} onContextMenu={(e) => { e.preventDefault(); onClose(); }} />

      {/* Modal content */}
      <div
        ref={dialogRef}
        className="relative w-full max-w-4xl max-h-[90vh] overflow-hidden rounded-xl border border-frame-line glass-panel flex flex-col"
      >
        {/* Header */}
        <div className="flex-shrink-0 border-b border-line px-6 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className="rounded-lg bg-indigo-600 p-2 flex-shrink-0">
                <File className="h-5 w-5 text-white" />
              </div>
              <div className="min-w-0 flex-1">
                <h3
                  id="properties-modal-title"
                  className="text-base font-semibold text-ink truncate"
                >
                  File Properties
                </h3>
                <p className="text-xs text-ink-muted truncate">
                  {file.filename}
                </p>
              </div>
              <button
                onClick={() => {
                  if (!metadata) return;
                  void copyToClipboard(buildPropertiesSummary(metadata), "all");
                }}
                disabled={!metadata || loading || error !== null}
                className="ml-2 flex items-center gap-1 rounded-md bg-chip-indigo-bg p-1.5 text-chip-indigo-text hover:brightness-95 border border-chip-indigo-border disabled:opacity-50"
                title="Copy all properties to clipboard"
                aria-label="Copy all properties"
              >
                {copiedField === "all" ? (
                  <Check className="h-4 w-4 text-emerald-400" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </button>
              <button
                onClick={() => setShowQrModal(true)}
                className="rounded-md bg-chip-indigo-bg p-1.5 text-chip-indigo-text hover:brightness-95 border border-chip-indigo-border"
                title="Generate Barcode/QR Code"
              >
                <QrCode className="h-4 w-4" />
              </button>
            </div>
            <button
              onClick={onClose}
              className="rounded-md p-1 text-ink-muted hover:bg-elevated hover:text-ink flex-shrink-0"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <div className="flex flex-col items-center gap-2">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
                <p className="text-xs text-ink-muted">Loading properties...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-4 text-center">
              <p className="text-xs text-red-400">{error}</p>
            </div>
          )}

          {metadata && !loading && !error && (
            <div>
              {/* Hero strip: type, size, relative age — always visible */}
              <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-lg border border-line bg-elevated px-4 py-2.5">
                <span className="inline-flex items-center gap-1 rounded-md border border-chip-indigo-border bg-chip-indigo-bg px-2 py-0.5 text-xs font-semibold text-chip-indigo-text">
                  {metadata.type}
                </span>
                {metadata.attributes.extension && (
                  <span className="inline-flex items-center rounded-md border border-line bg-surface px-2 py-0.5 text-xs font-medium text-ink-muted">
                    {metadata.attributes.extension}
                  </span>
                )}
                <span className="text-xs text-ink-muted" title={`${metadata.size_bytes} bytes`}>
                  Size <strong className="text-ink font-medium">{formatFileSize(metadata.size_bytes)}</strong>
                </span>
                <span className="text-xs text-ink-muted" title={metadata.created}>
                  Created <strong className="text-ink font-medium">{humanizeTimestamp(metadata.created)}</strong>
                </span>
                <span className="text-xs text-ink-muted" title={metadata.modified}>
                  Modified <strong className="text-ink font-medium">{humanizeTimestamp(metadata.modified)}</strong>
                </span>
                {metadata.md5 && (
                  <span className="inline-flex items-center rounded-md border border-chip-purple-border bg-chip-purple-bg px-2 py-0.5 font-mono text-xs font-medium text-chip-purple-text" title={`MD5 ${metadata.md5}`}>
                    {truncateMiddle(metadata.md5, 4, 4)}
                  </span>
                )}
                {metadata.attributes.is_symlink && (
                  <span className="inline-flex items-center gap-1 rounded-md border border-chip-fuchsia-border bg-chip-fuchsia-bg px-2 py-0.5 text-xs font-medium text-chip-fuchsia-text">
                    <Link2 className="h-3 w-3" /> Symlink
                  </span>
                )}
              </div>

              {/* Click-to-copy full path */}
              {renderPathBar()}

              {/* All-visible card grid */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {/* Hashes */}
                {renderCard(
                  "Hashes",
                  <Hash className="text-purple-400 h-3.5 w-3.5" />,
                  <div className="space-y-0.5">
                    {renderPropertyRow("MD5", metadata.md5, "md5", true, truncateMiddle(metadata.md5, 10, 6))}
                    {renderPropertyRow("SHA256", metadata.sha256, "sha256", true, truncateMiddle(metadata.sha256, 10, 6))}
                  </div>
                )}

                {/* Timestamps */}
                {renderCard(
                  "Timestamps",
                  <Calendar className="text-sky-400 h-3.5 w-3.5" />,
                  <div className="space-y-0.5">
                    {renderPropertyRow("Created", metadata.created, "created", true)}
                    {renderPropertyRow("Modified", metadata.modified, "modified", true)}
                  </div>
                )}

                {/* Identity */}
                {renderCard(
                  "Identity",
                  <File className="text-indigo-400 h-3.5 w-3.5" />,
                  <div className="space-y-0.5">
                    {renderPropertyRow("Type", metadata.type, "type")}
                    {metadata.attributes.stem && renderPropertyRow("Stem", metadata.attributes.stem, "attrStem")}
                    {renderPropertyRow(
                      "Extension",
                      metadata.name.includes(".") ? metadata.name.slice(metadata.name.lastIndexOf(".")) : "None",
                      "extension"
                    )}
                    {renderPropertyRow("Directory", parentDirectory(metadata.path) || "None", "directory", true)}
                  </div>
                )}

                {/* System */}
                {renderCard(
                  "System",
                  <File className="text-emerald-400 h-3.5 w-3.5" />,
                  <div>
                    <div className="mb-1 flex min-h-[24px] flex-wrap items-center gap-1.5">
                      {metadata.attributes.is_readonly && (
                        <span className="inline-flex items-center gap-1 rounded-md border border-rose-500/30 bg-rose-600/20 px-2 py-0.5 text-xs text-rose-300">
                          <Lock className="h-3 w-3" /> Read-only
                        </span>
                      )}
                      {metadata.attributes.is_hidden && (
                        <span className="inline-flex items-center gap-1 rounded-md border border-slate-500/30 bg-slate-600/20 px-2 py-0.5 text-xs text-slate-300">
                          <EyeOff className="h-3 w-3" /> Hidden
                        </span>
                      )}
                      {!metadata.attributes.is_readonly && !metadata.attributes.is_hidden && !metadata.attributes.is_symlink && (
                        <span className="text-xs text-ink-muted">No special flags</span>
                      )}
                    </div>
                    <div className="space-y-0.5">
                      {renderPropertyRow(
                        "File Type",
                        metadata.attributes.is_file ? "Regular File" : metadata.attributes.is_dir ? "Directory" : "Other",
                        "fileType"
                      )}
                      {metadata.attributes.permissions && renderPropertyRow("Permissions", metadata.attributes.permissions, "permissions", true)}
                      {metadata.attributes.owner_uid !== undefined && renderPropertyRow("Owner UID", String(metadata.attributes.owner_uid), "ownerUid")}
                      {metadata.attributes.group_gid !== undefined && renderPropertyRow("Group GID", String(metadata.attributes.group_gid), "groupGid")}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 border-t border-line px-6 py-3">
          <div className="flex justify-between items-center gap-2">
            <p className="text-xs text-ink-muted truncate">
              {actionMessage ?? "Click the copy icon next to any field to copy its value"}
            </p>
            <div className="flex items-center gap-2 whitespace-nowrap">
              <button
                onClick={() => void runFileAction("reveal", "Revealed in Explorer", () => revealFile(activeFile.path))}
                disabled={actionBusy !== null}
                className={actionButtonClass("reveal")}
                title="Show file in Explorer"
              >
                <Eye className="h-3.5 w-3.5" /> Reveal
              </button>
              <button
                onClick={() => void runFileAction("launch", "Launched", () => launchFile({ directory, filename: activeFile.filename }))}
                disabled={actionBusy !== null}
                className={actionButtonClass("launch")}
                title="Launch file with default association"
              >
                <Play className="h-3.5 w-3.5" /> Launch
              </button>
              <button
                onClick={() => void runFileAction("folder", "Opened folder", () => openFolder(activeFile.path))}
                disabled={actionBusy !== null}
                className={actionButtonClass("folder")}
                title="Open containing folder"
              >
                <FolderOpen className="h-3.5 w-3.5" /> Open Folder
              </button>
              <button
                onClick={onClose}
                className="rounded-md border border-transparent bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>

      <BarcodeModal
        isOpen={showQrModal}
        onClose={() => setShowQrModal(false)}
        initialFilePath={file.path}
        md5={metadata?.md5}
      />
    </div>
  );
}
