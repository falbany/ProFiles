import { useEffect, useRef, useState } from "react";
import { X, File, Folder, Calendar, Hash, ChevronDown, ChevronRight, Copy, Check, QrCode, Eye, Play, FolderOpen } from "lucide-react";
import type { FileMetadata, ScannedFileItem } from "../api/types";
import { fetchFileMetadata, launchFile, openFolder, revealFile } from "../api/client";
import { BarcodeModal } from "./BarcodeModal";
import { buildPropertiesSummary, formatFileSize, parentDirectory } from "../utils/fileProperties";

export interface FilePropertiesModalProps {
  isOpen: boolean;
  file: ScannedFileItem | null;
  onClose: () => void;
}

interface CollapsibleSection {
  id: string;
  title: string;
  icon: React.ReactNode;
  content: React.ReactNode;
}

/** Sections expanded when the modal opens or resets. */
const DEFAULT_EXPANDED_SECTIONS = ["basic", "hashes", "timestamps", "system"];

export function FilePropertiesModal({ isOpen, file, onClose }: FilePropertiesModalProps) {
  const [metadata, setMetadata] = useState<FileMetadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(DEFAULT_EXPANDED_SECTIONS));
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
      // Reset expanded sections when closing
      setExpandedSections(new Set(DEFAULT_EXPANDED_SECTIONS));
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

  const toggleSection = (sectionId: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
      }
      return next;
    });
  };

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
      reveal: "bg-sky-600/20 text-sky-300 hover:bg-sky-600/30 border-sky-500/30 focus-visible:ring-sky-400/60",
      launch: "bg-emerald-600 text-white hover:bg-emerald-500 border-emerald-500/30 font-semibold focus-visible:ring-emerald-400",
      folder: "bg-amber-600/20 text-amber-300 hover:bg-amber-600/30 border-amber-500/30 focus-visible:ring-amber-400/60",
    };
    return `inline-flex items-center gap-1 rounded-md border px-3 py-2 text-xs ${
      styles[actionId] ?? "bg-indigo-600/20 text-indigo-400 hover:bg-indigo-600/30 border-indigo-500/30"
    } disabled:opacity-40 disabled:cursor-not-allowed`;
  };

  const renderPropertyRow = (
    label: string,
    value: string,
    fieldId: string,
    isMonospace = false
  ) => (
    <div className="flex items-start gap-2 py-1.5 group">
      <span className="text-ink-muted min-w-[100px] text-xs">{label}:</span>
      <div className="flex-1 min-w-0">
        <span className={`text-ink text-xs break-all ${isMonospace ? "font-mono" : ""}`}>
          {value}
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

  const renderCollapsibleSection = (section: CollapsibleSection) => {
    const isExpanded = expandedSections.has(section.id);
    return (
      <div className="rounded-lg bg-elevated overflow-hidden">
        <button
          onClick={() => toggleSection(section.id)}
          className="w-full flex items-center gap-2 px-4 py-3 hover:bg-surface transition-colors"
          aria-expanded={isExpanded}
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-ink-muted" />
          ) : (
            <ChevronRight className="h-4 w-4 text-ink-muted" />
          )}
          <div className="flex items-center gap-2">
            {section.icon}
            <span className="text-sm font-medium text-ink">{section.title}</span>
          </div>
        </button>
        {isExpanded && (
          <div className="px-4 pb-4 pt-2 border-t border-line">
            <div className="pt-2">{section.content}</div>
          </div>
        )}
      </div>
    );
  };

  if (!isOpen || !file) return null;
  // Captures the narrowed file so JSX callbacks keep a non-null type.
  const activeFile = file;
  const directory = parentDirectory(activeFile.path);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="properties-modal-title"
    >
      {/* Backdrop */}
      <div onClick={onClose} onContextMenu={(e) => { e.preventDefault(); onClose(); }} />

      {/* Modal content */}
      <div
        ref={dialogRef}
        className="relative w-full max-w-2xl max-h-[90vh] overflow-hidden rounded-xl border border-line bg-surface shadow-2xl flex flex-col"
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
                className="ml-2 flex items-center gap-1 rounded-md bg-indigo-600/20 p-1.5 text-indigo-400 hover:bg-indigo-600/30 border border-indigo-500/30 disabled:opacity-50"
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
                className="rounded-md bg-indigo-600/20 p-1.5 text-indigo-400 hover:bg-indigo-600/30 border border-indigo-500/30"
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
            <div className="space-y-3">
              {/* Basic Information */}
              {renderCollapsibleSection({
                id: "basic",
                title: "Basic Information",
                icon: <File className="h-4 w-4 text-indigo-400" />,
                content: (
                  <div className="space-y-0.5">
                    {renderPropertyRow("Name", metadata.name, "name")}
                    {renderPropertyRow("Type", metadata.type, "type")}
                    {renderPropertyRow("Size", formatFileSize(metadata.size_bytes), "size")}
                    {renderPropertyRow("Extension", metadata.name.includes(".") ? metadata.name.slice(metadata.name.lastIndexOf(".")) : "None", "extension")}
                  </div>
                ),
              })}

              {/* Cryptographic Hashes */}
              {renderCollapsibleSection({
                id: "hashes",
                title: "Cryptographic Hashes",
                icon: <Hash className="h-4 w-4 text-purple-400" />,
                content: (
                  <div className="space-y-0.5">
                    {renderPropertyRow("MD5", metadata.md5, "md5", true)}
                    {renderPropertyRow("SHA256", metadata.sha256, "sha256", true)}
                  </div>
                ),
              })}

              {/* Timestamps */}
              {renderCollapsibleSection({
                id: "timestamps",
                title: "Timestamps",
                icon: <Calendar className="h-4 w-4 text-sky-400" />,
                content: (
                  <div className="space-y-0.5">
                    {renderPropertyRow("Created", metadata.created, "created", true)}
                    {renderPropertyRow("Modified", metadata.modified, "modified", true)}
                  </div>
                ),
              })}

              {/* File Location */}
              {renderCollapsibleSection({
                id: "location",
                title: "File Location",
                icon: <Folder className="h-4 w-4 text-amber-400" />,
                content: (
                  <div className="space-y-0.5">
                    {renderPropertyRow("Full Path", metadata.path, "path", true)}
                    {renderPropertyRow("Directory", parentDirectory(metadata.path) || "None", "directory", true)}
                  </div>
                ),
              })}

              {/* System Attributes */}
              {renderCollapsibleSection({
                id: "system",
                title: "System Attributes",
                icon: <File className="h-4 w-4 text-emerald-400" />,
                content: (
                  <div className="space-y-0.5">
                    {renderPropertyRow(
                      "File Type",
                      metadata.attributes.is_file ? "Regular File" : metadata.attributes.is_dir ? "Directory" : "Other",
                      "fileType"
                    )}
                    {metadata.attributes.extension && renderPropertyRow("Extension", metadata.attributes.extension, "attrExt")}
                    {metadata.attributes.stem && renderPropertyRow("Filename (no ext)", metadata.attributes.stem, "attrStem")}
                    {metadata.attributes.permissions && renderPropertyRow("Permissions", metadata.attributes.permissions, "permissions", true)}
                    {metadata.attributes.is_readonly !== undefined && renderPropertyRow(
                      "Read-only",
                      metadata.attributes.is_readonly ? "Yes" : "No",
                      "readonly"
                    )}
                    {metadata.attributes.is_hidden !== undefined && renderPropertyRow(
                      "Hidden",
                      metadata.attributes.is_hidden ? "Yes" : "No",
                      "hidden"
                    )}
                    {metadata.attributes.is_symlink && renderPropertyRow(
                      "Symlink",
                      "Yes",
                      "symlink"
                    )}
                    {metadata.attributes.owner_uid !== undefined && renderPropertyRow(
                      "Owner UID",
                      String(metadata.attributes.owner_uid),
                      "ownerUid"
                    )}
                    {metadata.attributes.group_gid !== undefined && renderPropertyRow(
                      "Group GID",
                      String(metadata.attributes.group_gid),
                      "groupGid"
                    )}
                  </div>
                ),
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 border-t border-line px-6 py-3">
          <div className="flex justify-between items-center gap-2">
            <p className="text-xs text-ink-muted">
              {actionMessage ?? "Click the copy icon next to any field to copy its value"}
            </p>
            <div className="flex items-center gap-2 flex-wrap justify-end">
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
                className="rounded-md bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500"
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
