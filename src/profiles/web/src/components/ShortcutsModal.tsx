import { Keyboard, X } from "lucide-react";

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ShortcutsModal({ isOpen, onClose }: ShortcutsModalProps) {
  if (!isOpen) return null;

  const shortcuts = [
    { key: "F5", desc: "Refresh / re-scan file list" },
    { key: "Ctrl + R", desc: "Reload configuration & scan" },
    { key: "Enter", desc: "Execute / launch selected file" },
    { key: "P", desc: "Open properties for selected file" },
    { key: "↑ / ↓", desc: "Navigate file list" },
    { key: "Ctrl + D", desc: "Focus Directory field" },
    { key: "Ctrl + E", desc: "Focus Extension field" },
    { key: "Ctrl + F", desc: "Focus Filter / Search field" },
    { key: "Ctrl + L", desc: "Focus File List" },
    { key: "Ctrl + Shift + L", desc: "Open the log viewer" },
    { key: "Ctrl + ,", desc: "Open config file" },
    { key: "Ctrl + Shift + T", desc: "Toggle theme (Dark / Light)" },
    { key: "Ctrl + B", desc: "Toggle barcode scanner mode" },
    { key: "Ctrl + T", desc: "Open auto-rescan timer modal" },
    { key: "Ctrl + H", desc: "Set directory to home folder" },
    { key: "? or Ctrl + /", desc: "Show keyboard shortcuts" },
    { key: "Escape", desc: "Close dialogs / context menu" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-[450px] max-w-full rounded-2xl border border-line bg-surface p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between border-b border-line pb-3">
          <div className="flex items-center gap-2 font-semibold text-ink">
            <Keyboard className="h-5 w-5 text-indigo-400" />
            <span>Keyboard Shortcuts</span>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-ink-muted hover:bg-elevated hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1 text-xs">
          {shortcuts.map(({ key, desc }) => (
            <div
              key={key}
              className="flex items-center justify-between rounded-lg bg-elevated/50 px-3 py-2"
            >
              <span className="text-ink-secondary">{desc}</span>
              <kbd className="rounded bg-app px-2 py-0.5 font-mono text-[11px] font-semibold text-indigo-300 border border-line">
                {key}
              </kbd>
            </div>
          ))}
        </div>

        <div className="mt-5 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
