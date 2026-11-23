import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  Copy,
  Eye,
  FileCode,
  FolderOpen,
  Hash,
  Play,
  QrCode,
  Terminal,
  Trash2,
} from "lucide-react";
import type { ScannedFileItem } from "../api/types";
import { fileExtension, parentDirectory } from "../utils/fileProperties";

export interface ContextMenuPosition {
  x: number;
  y: number;
  file: ScannedFileItem;
}

interface ContextMenuProps {
  position: ContextMenuPosition | null;
  onClose: () => void;
  onLaunch: (file: ScannedFileItem) => void;
  /** Ask for command-line arguments, then launch through the normal path. */
  onRequestLaunchWithArgs: (file: ScannedFileItem) => void;
  onReveal: (file: ScannedFileItem) => void;
  onOpenFolder: (file: ScannedFileItem) => void;
  onOpenTerminal: (file: ScannedFileItem) => void;
  onScanDirectory: (directory: string) => void;
  onFilterFolder: (folder: string) => void;
  onFilterExtension: (ext: string) => void;
  onCopyPath: (file: ScannedFileItem, forwardSlash?: boolean) => void;
  onCopyFilename: (file: ScannedFileItem, withoutExt?: boolean) => void;
  onCopyDirectory: (file: ScannedFileItem) => void;
  onCopyUri: (file: ScannedFileItem) => void;
  onComputeHash: (file: ScannedFileItem, algorithm: "md5" | "sha256") => void;
  onVerifyHash: (file: ScannedFileItem, algorithm: "md5" | "sha256") => void;
  onProperties: (file: ScannedFileItem) => void;
  onClearFile: (file: ScannedFileItem) => void;
  onGenerateBarcode: (file: ScannedFileItem) => void;
}

export function ContextMenu({
  position,
  onClose,
  onLaunch,
  onRequestLaunchWithArgs,
  onReveal,
  onOpenFolder,
  onOpenTerminal,
  onScanDirectory,
  onFilterFolder,
  onFilterExtension,
  onCopyPath,
  onCopyFilename,
  onCopyDirectory,
  onCopyUri,
  onComputeHash,
  onVerifyHash,
  onProperties,
  onClearFile,
  onGenerateBarcode,
}: Readonly<ContextMenuProps>) {
  const menuRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const [menuCoordinates, setMenuCoordinates] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    if (!position) {
      setMenuCoordinates(null);
      return;
    }

    const updatePosition = () => {
      const menu = menuRef.current;
      if (!menu) return;
      const bounds = menu.getBoundingClientRect();
      const margin = 8;
      setMenuCoordinates({
        left: Math.max(margin, Math.min(position.x, window.innerWidth - bounds.width - margin)),
        top: Math.max(margin, Math.min(position.y, window.innerHeight - bounds.height - margin)),
      });
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    return () => window.removeEventListener("resize", updatePosition);
  }, [position]);

  useEffect(() => {
    if (!position) return;
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = window.requestAnimationFrame(() => {
      menuRef.current?.querySelector<HTMLButtonElement>("[role='menuitem']")?.focus();
    });
    return () => {
      window.cancelAnimationFrame(frame);
      previousFocusRef.current?.focus();
    };
  }, [position]);

  if (!position) return null;

  const { file, x, y } = position;

  const extension = fileExtension(file.filename);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[calc(var(--z-context-menu)-1)]"
        onClick={onClose}
        onContextMenu={(e) => { e.preventDefault(); onClose(); }}
        aria-hidden="true"
      />

      {/* Menu popup */}
      <div
        ref={menuRef}
        role="menu"
        aria-label={`Actions for ${file.filename}`}
        tabIndex={0}
        onKeyDown={(event) => {
          if (["Escape", "ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
            event.stopPropagation();
          }
          const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>("[role='menuitem']") ?? []);
          const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
          if (event.key === "Escape") {
            event.preventDefault();
            onClose();
          } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const delta = event.key === "ArrowDown" ? 1 : -1;
            items[(currentIndex + delta + items.length) % items.length]?.focus();
          } else if (event.key === "Home") {
            event.preventDefault();
            items[0]?.focus();
          } else if (event.key === "End") {
            event.preventDefault();
            items.at(-1)?.focus();
          }
        }}
        className="animate-modal-in fixed z-[var(--z-context-menu)] max-h-[calc(100dvh-16px)] w-56 max-w-[calc(100vw-16px)] overflow-y-auto rounded-lg border border-line bg-surface-glass py-1 text-xs text-ink shadow-2xl backdrop-blur-md"
        style={menuCoordinates ?? { left: x, top: y, visibility: "hidden" }}
      >
        <div className="border-b border-line px-3 py-2 font-medium text-ink-muted truncate">
          {file.filename}
        </div>

        {/* Launch actions */}
        <button
          role="menuitem"
          onClick={() => { onLaunch(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-3 min-h-[44px] hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Launch ${file.filename}`}
        >
          <Play className="h-3.5 w-3.5 fill-current text-status-success-text group-hover:text-white" />
          <span>Launch</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onRequestLaunchWithArgs(file); }}
          className="flex w-full items-center gap-2 px-3 py-3 min-h-[44px] hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Launch ${file.filename} with arguments`}
        >
          <Play className="h-3.5 w-3.5 text-chip-indigo-text group-hover:text-white" />
          <span>Launch with arguments...</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Folder actions */}
        <button
          role="menuitem"
          onClick={() => { onReveal(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Reveal ${file.filename} in file manager`}
        >
          <Eye className="h-3.5 w-3.5 text-chip-sky-text group-hover:text-white" />
          <span>Reveal in File Manager</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onOpenFolder(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Open folder containing ${file.filename}`}
        >
          <FolderOpen className="h-3.5 w-3.5 text-chip-amber-text group-hover:text-white" />
          <span>Open Folder</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onOpenTerminal(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Open terminal in directory containing ${file.filename}`}
        >
          <Terminal className="h-3.5 w-3.5 text-status-success-text group-hover:text-white" />
          <span>Open Terminal in Directory</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onGenerateBarcode(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={'Generate QR Code'}
        >
          <QrCode className="h-3.5 w-3.5 text-chip-fuchsia-text group-hover:text-white" />
          <span>Generate QR Code</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Directory & Filter actions */}
        <button
          role="menuitem"
          onClick={() => {
            onScanDirectory(parentDirectory(file.path));
            onClose();
          }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={'Scan to Directory'}
        >
          <FolderOpen className="h-3.5 w-3.5 text-chip-indigo-text group-hover:text-white" />
          <span>Scan to Directory</span>
        </button>
        <button
          role="menuitem"
          onClick={() => {
            const relFolder = parentDirectory(file.rel_path);
            if (relFolder) {
              onFilterFolder(relFolder);
            }
            onClose();
          }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Filter view to folder ${file.filename} is in`}
        >
          <FileCode className="h-3.5 w-3.5 text-chip-indigo-text group-hover:text-white" />
          <span>Filter to Folder</span>
        </button>
        <button
          role="menuitem"
          onClick={() => {
            if (extension) onFilterExtension(extension);
            onClose();
          }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Filter view by extension ${extension}`}
        >
          <FileCode className="h-3.5 w-3.5 text-chip-indigo-text group-hover:text-white" />
          <span>Filter by Extension</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Copy actions */}
        <button
          role="menuitem"
          onClick={() => { onCopyPath(file, false); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Copy full path of ${file.filename}`}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted group-hover:text-white" />
          <span className="truncate">Copy Full Path</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyPath(file, true); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Copy path of ${file.filename} with forward slashes`}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted group-hover:text-white" />
          <span className="truncate">Copy Path (Forward Slashes)</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyFilename(file, false); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Copy filename of ${file.filename}`}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted group-hover:text-white" />
          <span className="truncate">Copy Filename</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyFilename(file, true); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Copy filename of ${file.filename} without extension`}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted group-hover:text-white" />
          <span className="truncate">Copy Filename (no ext)</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyDirectory(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={'Copy Directory'}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted group-hover:text-white" />
          <span className="truncate">Copy Directory</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyUri(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Copy URI of ${file.filename}`}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted group-hover:text-white" />
          <span className="truncate">Copy URI</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Hashes */}
        <button
          role="menuitem"
          onClick={() => { onComputeHash(file, "md5"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Compute MD5 hash of ${file.filename}`}
        >
          <Hash className="h-3.5 w-3.5 text-chip-purple-text group-hover:text-white" />
          <span>Compute MD5 Hash</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onComputeHash(file, "sha256"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Compute SHA256 hash of ${file.filename}`}
        >
          <Hash className="h-3.5 w-3.5 text-chip-purple-text group-hover:text-white" />
          <span>Compute SHA256 Hash</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onVerifyHash(file, "md5"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Verify MD5 hash of ${file.filename}`}
        >
          <Hash className="h-3.5 w-3.5 text-chip-purple-text group-hover:text-white" />
          <span>Verify MD5 Hash</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onVerifyHash(file, "sha256"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Verify SHA256 hash of ${file.filename}`}
        >
          <Hash className="h-3.5 w-3.5 text-chip-purple-text group-hover:text-white" />
          <span>Verify SHA256 Hash</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Info + utility */}
        <button
          role="menuitem"
          onClick={() => { onProperties(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`View properties of ${file.filename}`}
        >
          <Eye className="h-3.5 w-3.5 text-chip-sky-text group-hover:text-white" />
          <span>Properties</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onClearFile(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform group"
          aria-label={`Remove ${file.filename} from list`}
        >
          <Trash2 className="h-3.5 w-3.5 text-status-danger-text group-hover:text-white" />
          <span>Delete</span>
        </button>
      </div>
    </>
  );
}
