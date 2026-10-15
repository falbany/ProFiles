import { useEffect, useRef, useState } from "react";
import { X, File, Folder, Calendar, Hash, ChevronDown, ChevronRight, Copy, Check } from "lucide-react";
import type { ScannedFileItem } from "../api/types";

export interface FilePropertiesModalProps {
  isOpen: boolean;
  file: ScannedFileItem | null;
  onClose: () => void;
}

interface FileMetadata {
  name: string;
  path: string;
  size_bytes: number;
  modified: string;
  created: string;
  type: string;
  md5: string;
  sha256: string;
  attributes: Record<string, any>;
}

interface CollapsibleSection {
  id: string;
  title: string;
  icon: React.ReactNode;
  content: React.ReactNode;
}

export function FilePropertiesModal({ isOpen, file, onClose }: FilePropertiesModalProps) {
  const [metadata, setMetadata] = useState<FileMetadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(["basic", "hashes", "timestamps", "system"]));
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) {
      previousFocusRef.current?.focus();
      // Reset expanded sections when closing
      setExpandedSections(new Set(["basic", "hashes", "timestamps", "system"]));
      return;
    }

    previousFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;

    if (file) {
      void fetchMetadata(file.path);
    }

    const focusFrame = requestAnimationFrame(() => {
      dialogRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    });

    return () => {
      cancelAnimationFrame(focusFrame);
      previousFocusRef.current?.focus();
    };
  }, [isOpen, file]);

  const fetchMetadata = async (filePath: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/actions/metadata`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: filePath }),
      });
      if (!res.ok) throw new Error("Failed to fetch metadata");
      const meta: FileMetadata = await res.json();
      setMetadata(meta);
    } catch (err: any) {
      setError(err.message || "Failed to load properties");
    } finally {
      setLoading(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

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
                    {renderPropertyRow(
                      "Directory",
                      metadata.path.slice(0, metadata.path.lastIndexOf("\\") || metadata.path.lastIndexOf("/")),
                      "directory",
                      true
                    )}
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
              Click the copy icon next to any field to copy its value
            </p>
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
  );
}
