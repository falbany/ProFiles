import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  Copy,
  Eye,
  FileCode,
  FolderOpen,
  Hash,
  Play,
  Terminal,
  Trash2,
  RotateCcw,
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
  onFilterFolder: (folder: string) => void;
  onFilterExtension: (ext: string) => void;
  onCopyPath: (file: ScannedFileItem, forwardSlash?: boolean) => void;
  onCopyFilename: (file: ScannedFileItem, withoutExt?: boolean) => void;
  onCopyUri: (file: ScannedFileItem) => void;
  onComputeHash: (file: ScannedFileItem, algorithm: "md5" | "sha256") => void;
  onVerifyHash: (file: ScannedFileItem, algorithm: "md5" | "sha256") => void;
  onProperties: (file: ScannedFileItem) => void;
  onClearFile: (file: ScannedFileItem) => void;
  onRefreshList: () => void;
}

export function ContextMenu({
  position,
  onClose,
  onLaunch,
  onLaunchWithArgs,
  onReveal,
  onOpenFolder,
  onOpenTerminal,
  onFilterFolder,
  onFilterExtension,
  onCopyPath,
  onCopyFilename,
  onCopyUri,
  onComputeHash,
  onVerifyHash,
  onProperties,
  onClearFile,
  onRefreshList,
}: ContextMenuProps) {
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

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40" onClick={onClose} onContextMenu={(e) => { e.preventDefault(); onClose(); }} />

      {/* Menu popup */}
      <div
        ref={menuRef}
        role="menu"
        aria-label={`Actions for ${file.filename}`}
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
        <div className="border-b border-line px-3 py-1.5 font-medium text-ink-muted truncate">
          {file.filename}
        </div>

        {/* Launch actions */}
        <button
          role="menuitem"
          onClick={() => { onLaunch(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Play className="h-3.5 w-3.5 fill-current text-emerald-400" />
          <span>Launch</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { setShowArgsModal(true); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Play className="h-3.5 w-3.5 text-indigo-400" />
          <span>Launch with arguments...</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Folder actions */}
        <button
          role="menuitem"
          onClick={() => { onReveal(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Eye className="h-3.5 w-3.5 text-sky-400" />
          <span>Reveal in File Manager</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onOpenFolder(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <FolderOpen className="h-3.5 w-3.5 text-amber-400" />
          <span>Open Folder</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onOpenTerminal(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Terminal className="h-3.5 w-3.5 text-emerald-400" />
          <span>Open Terminal in Directory</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Filter actions */}
        <button
          role="menuitem"
          onClick={() => {
            const parts = file.path.split(/[/\\]/);
            const parent = parts.length > 1 ? parts[parts.length - 2] : "";
            if (parent) onFilterFolder(parent);
            onClose();
          }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <FileCode className="h-3.5 w-3.5 text-indigo-400" />
          <span>Filter to Folder</span>
        </button>
        <button
          role="menuitem"
          onClick={() => {
            const ext = getExt(file.filename);
            if (ext) onFilterExtension(ext);
            onClose();
          }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <FileCode className="h-3.5 w-3.5 text-indigo-400" />
          <span>Filter by Extension</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Copy actions */}
        <button
          role="menuitem"
          onClick={() => { onCopyPath(file, false); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span>Copy Full Path</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyPath(file, true); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span>Copy Path (Forward Slashes)</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyFilename(file, false); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span>Copy Filename</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyFilename(file, true); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span>Copy Filename (without extension)</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyPath(file, false); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span>Copy Directory</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onCopyUri(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Copy className="h-3.5 w-3.5 text-ink-muted" />
          <span>Copy URI</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Hashes */}
        <button
          role="menuitem"
          onClick={() => { onComputeHash(file, "md5"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Hash className="h-3.5 w-3.5 text-purple-400" />
          <span>Compute MD5 Hash</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onComputeHash(file, "sha256"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Hash className="h-3.5 w-3.5 text-purple-400" />
          <span>Compute SHA256 Hash</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onVerifyHash(file, "md5"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Hash className="h-3.5 w-3.5 text-purple-400" />
          <span>Verify MD5 Hash</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onVerifyHash(file, "sha256"); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Hash className="h-3.5 w-3.5 text-purple-400" />
          <span>Verify SHA256 Hash</span>
        </button>

        <div className="my-1 border-t border-line" />

        {/* Info + utility */}
        <button
          role="menuitem"
          onClick={() => { onProperties(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Eye className="h-3.5 w-3.5 text-sky-400" />
          <span>Properties</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onClearFile(file); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <Trash2 className="h-3.5 w-3.5 text-red-400" />
          <span>Delete</span>
        </button>
        <button
          role="menuitem"
          onClick={() => { onRefreshList(); onClose(); }}
          className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-indigo-600 hover:text-white"
        >
          <RotateCcw className="h-3.5 w-3.5 text-amber-400" />
          <span>Refresh List</span>
        </button>
      </div>

      {/* Launch with Args Modal */}
      {showArgsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-96 rounded-xl border border-line bg-surface p-4 shadow-2xl">
            <h3 className="mb-2 text-sm font-semibold text-ink">Launch with Arguments</h3>
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
              className="mb-4 w-full rounded-md border border-line bg-elevated px-3 py-2 text-xs text-ink outline-none focus:border-indigo-500"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowArgsModal(false)}
                className="rounded-md px-3 py-1.5 text-xs text-ink-muted hover:bg-elevated hover:text-ink"
              >
                Cancel
              </button>
              <button
                onClick={handleArgsSubmit}
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
              >
                Launch
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
