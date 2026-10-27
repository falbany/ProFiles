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

export interface ContextMenuPosition {
  x: number;
  y: number;
  file: ScannedFileItem;
}

interface ContextMenuProps {
  position: ContextMenuPosition | null;
  onClose: () => void;
  onLaunch: (file: ScannedFileItem) => void;
  onLaunchWithArgs: (file: ScannedFileItem, args: string) => void;
  onReveal: (file: ScannedFileItem) => void;
  onOpenFolder: (file: ScannedFileItem) => void;
  onOpenTerminal: (file: ScannedFileItem) => void;
  onScanDirectory: (directory: string) => void;
  onFilterFolder: (folder: string) => void;
  onFilterExtension: (ext: string) => void;
  onCopyPath: (file: ScannedFileItem, forwardSlash?: boolean) => void;
  onCopyFilename: (file: ScannedFileItem, withoutExt?: boolean) => void;
  onCopyUri: (file: ScannedFileItem) => void;
  onComputeHash: (file: ScannedFileItem, algorithm: "md5" | "sha256") => void;
  onVerifyHash: (file: ScannedFileItem, algorithm: "md5" | "sha256") => void;
  onProperties: (file: ScannedFileItem) => void;
  onClearFile: (file: ScannedFileItem) => void;
  onGenerateBarcode: (file: ScannedFileItem) => void;
  showToast?: (message: string) => void;
}

export function ContextMenu({
  position,
  onClose,
  onLaunch,
  onLaunchWithArgs,
  onReveal,
  onOpenFolder,
  onOpenTerminal,
  onScanDirectory,
  onFilterFolder,
  onFilterExtension,
  onCopyPath,
  onCopyFilename,
  onCopyUri,
  onComputeHash,
  onVerifyHash,
  onProperties,
  onClearFile,
  onGenerateBarcode,
  showToast,
}: Readonly<ContextMenuProps>) {
  const [showArgsModal, setShowArgsModal] = useState(false);
  const [argsValue, setArgsValue] = useState("");
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

  const handleArgsSubmit = () => {
    onLaunchWithArgs(file, argsValue);
    setShowArgsModal(false);
    onClose();
  };

  const getExt = (filename: string) => {
    const idx = filename.lastIndexOf(".");
    return idx !== -1 ? filename.slice(idx) : "";
  };

  const getDirectoryPath = (fullPath: string) => {
    const lastSep = Math.max(fullPath.lastIndexOf("/"), fullPath.lastIndexOf("\\"));
    return lastSep !== -1 ? fullPath.slice(0, lastSep) : fullPath;
  };

  const getRelativeFolderPath = (relPath: string) => {
    const lastSep = Math.max(relPath.lastIndexOf("/"), relPath.lastIndexOf("\\"));
    return lastSep !== -1 ? relPath.slice(0, lastSep) : "";
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
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
        className="fixed z-50 max-h-[calc(100dvh-16px)] w-56 max-w-[calc(100vw-16px)] overflow-y-auto rounded-lg border border-line bg-surface-glass py-1 text-xs text-ink shadow-2xl backdrop-blur-md"
        style={menuCoordinates ?? { left: x, top: y, visibility: "hidden" }}
      >
        <div className="border-b border-line px-3 py-2 font-medium text-ink-muted truncate">
          {file.filename}
        </div>

        {/* Launch actions */}
        <button
          role="menuitem"
          onClick={() => { onLaunch(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-3 min-h-[44px] hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Launch ${file.filename}`}
        >
          <Play className="h-3.5 w-3.5 fill-current text-status-success-text" />
          <span>Launch</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { setShowArgsModal(true); }}
          className="flex w-full items-center gap-2 px-3 py-3 min-h-[44px] hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Launch ${file.filename} with arguments`}
        >
          <Play className="h-3.5 w-3.5 text-chip-indigo-text" />
          <span>Launch with arguments...</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Folder actions */}
        <button
          role="menuitem"
          onClick={() => { onReveal(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Reveal ${file.filename} in file manager`}
        >
          <Eye className="h-3.5 w-3.5 text-chip-sky-text" />
          <span>Reveal in File Manager</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onOpenFolder(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Open folder containing ${file.filename}`}
        >
          <FolderOpen className="h-3.5 w-3.5 text-chip-amber-text" />
          <span>Open Folder</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onOpenTerminal(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Open terminal in directory containing ${file.filename}`}
        >
          <Terminal className="h-3.5 w-3.5 text-status-success-text" />
          <span>Open Terminal in Directory</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onGenerateBarcode(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={'Generate QR Code'}
        >
          <QrCode className="h-3.5 w-3.5 text-fuchsia-400" />
          <span>Generate QR Code</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Directory & Filter actions */}
        <button
          role="menuitem"
          onClick={() => {
            const dir = getDirectoryPath(file.path);
            onScanDirectory(dir);
            onClose();
          }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={'Scan to Directory'}
        >
          <FolderOpen className="h-3.5 w-3.5 text-chip-indigo-text" />
          <span>Scan to Directory</span>
        </button>
        <button
          role="menuitem"
          onClick={() => {
            const relFolder = getRelativeFolderPath(file.rel_path);
            if (relFolder) {
              onFilterFolder(relFolder);
            }
            onClose();
          }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Filter view to folder ${file.filename} is in`}
        >
          <FileCode className="h-3.5 w-3.5 text-chip-indigo-text" />
          <span>Filter to Folder</span>
        </button>
        <button
          role="menuitem"
          onClick={() => {
            const ext = getExt(file.filename);
            if (ext) onFilterExtension(ext);
            onClose();
          }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Filter view by extension ${getExt(file.filename)}`}
        >
          <FileCode className="h-3.5 w-3.5 text-chip-indigo-text" />
          <span>Filter by Extension</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Copy actions */}
        <button
          role="menuitem"
          onClick={() => { onCopyPath(file, false); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Copy full path of ${file.filename}`}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span className="truncate">Copy Full Path</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyPath(file, true); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Copy path of ${file.filename} with forward slashes`}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span className="truncate">Copy Path (Forward Slashes)</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyFilename(file, false); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Copy filename of ${file.filename}`}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span className="truncate">Copy Filename</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyFilename(file, true); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Copy filename of ${file.filename} without extension`}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span className="truncate">Copy Filename (no ext)</span>
        </button>
        <button
          role="menuitem"
          onClick={() => {
            const dirPath = getDirectoryPath(file.path);
            navigator.clipboard.writeText(dirPath);
            onClose();
            showToast?.('Copy Directory');
          }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={'Copy Directory'}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span className="truncate">Copy Directory</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyUri(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Copy URI of ${file.filename}`}
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span className="truncate">Copy URI</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Hashes */}
        <button
          role="menuitem"
          onClick={() => { onComputeHash(file, "md5"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Compute MD5 hash of ${file.filename}`}
        >
          <Hash className="h-3.5 w-3.5 text-chip-purple-text" />
          <span>Compute MD5 Hash</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onComputeHash(file, "sha256"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Compute SHA256 hash of ${file.filename}`}
        >
          <Hash className="h-3.5 w-3.5 text-chip-purple-text" />
          <span>Compute SHA256 Hash</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onVerifyHash(file, "md5"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Verify MD5 hash of ${file.filename}`}
        >
          <Hash className="h-3.5 w-3.5 text-chip-purple-text" />
          <span>Verify MD5 Hash</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onVerifyHash(file, "sha256"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Verify SHA256 hash of ${file.filename}`}
        >
          <Hash className="h-3.5 w-3.5 text-chip-purple-text" />
          <span>Verify SHA256 Hash</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Info + utility */}
        <button
          role="menuitem"
          onClick={() => { onProperties(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`View properties of ${file.filename}`}
        >
          <Eye className="h-3.5 w-3.5 text-chip-sky-text" />
          <span>Properties</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onClearFile(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 active:scale-95 transition-transform"
          aria-label={`Remove ${file.filename} from list`}
        >
          <Trash2 className="h-3.5 w-3.5 text-status-danger-text" />
          <span>Delete</span>
        </button>
      </div>

      {/* Launch with Args Modal */}
      {showArgsModal && (
        <dialog
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 rounded-xl"
          aria-modal="true"
          aria-labelledby="args-modal-title"
        >
          <div className="w-96 rounded-xl border border-frame-line glass-panel p-4">
            <h3 id="args-modal-title" className="mb-2 text-sm font-semibold text-ink">Launch with Arguments</h3>
            <p className="mb-3 text-xs text-ink-muted truncate">{file.filename}</p>
            <input
              type="text"
              autoFocus
              placeholder="Arguments (e.g. --verbose --port 80)"
              value={argsValue}
              onChange={(e) => setArgsValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleArgsSubmit();
                if (e.key === "Escape") setShowArgsModal(false);
              }}
              className="mb-4 w-full rounded-md border border-line bg-elevated px-3 py-2 text-xs text-ink outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
              aria-label="Command line arguments"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowArgsModal(false)}
                className="rounded-md px-3 py-1.5 text-xs text-ink-muted hover:bg-elevated hover:text-ink focus:outline-none focus:ring-2 focus:ring-indigo-500"
                aria-label="Cancel launch"
              >
                Cancel
              </button>
              <button
                onClick={handleArgsSubmit}
                className="btn btn-primary px-3 py-1.5"
                aria-label={`Launch ${file.filename} with arguments`}
              >
                Launch
              </button>
            </div>
          </div>
        </dialog>
      )}
    </>
  );
}
