import { useEffect, useState } from "react";
import { Check, ChevronRight, FileUp, Folder, FolderOpen, Home, X } from "lucide-react";

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

  useEffect(() => {
    if (!isOpen) return;
    setError(null);
    browse(initialPath || "");
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

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-xl border border-line bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4 text-indigo-400" />
            <h2 className="text-sm font-semibold text-ink">Select a directory</h2>
          </div>
          <button
            onClick={onClose}
            title="Cancel (Esc)"
            className="rounded p-1 text-ink-muted hover:bg-elevated hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Path input */}
        <div className="flex gap-2 border-b border-line px-4 py-2.5">
          <input
            type="text"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") browse(pathInput.trim());
            }}
            placeholder="/path/to/directory"
            className="flex-1 rounded-md border border-line bg-elevated px-3 py-1.5 font-mono text-xs text-ink outline-none focus:border-indigo-500"
          />
          <button
            onClick={() => browse(pathInput.trim())}
            className="rounded-md border border-line bg-elevated px-2.5 text-xs text-ink-secondary hover:text-white"
          >
            Go
          </button>
          <button
            onClick={() => browse("")}
            title="Home directory"
            className="rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:text-white"
          >
            <Home className="h-3.5 w-3.5" />
          </button>
          {browseData?.parent_path && (
            <button
              onClick={() => browse(browseData.parent_path!)}
              title="Parent directory"
              className="rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:text-white"
            >
              <ChevronRight className="h-3.5 w-3.5 rotate-180" />
            </button>
          )}
        </div>

        {/* Directory listing */}
        <div className="h-72 overflow-y-auto px-2 py-2">
          {loading ? (
            <div className="flex h-full items-center justify-center text-xs text-ink-muted">
              Loading...
            </div>
          ) : error ? (
            <div className="px-4 py-8 text-center text-xs text-rose-400">
              {error}
            </div>
          ) : (
            <ul className="space-y-0.5">
              {browseData?.items
                .filter((item) => item.is_dir)
                .map((item) => (
                  <li key={item.path}>
                    <button
                      onClick={() => browse(item.path)}
                      onDoubleClick={() => {
                        setPathInput(item.path);
                        onSelect(item.path);
                        onClose();
                      }}
                      className={`flex w-full items-center justify-between rounded-md px-3 py-1.5 text-left text-xs transition-colors ${
                        selectedDir === item.path
                          ? "bg-indigo-600/20 text-indigo-200"
                          : "text-ink-secondary hover:bg-elevated"
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <Folder className="h-3.5 w-3.5 text-indigo-400" />
                        {item.name}
                      </span>
                      {selectedDir === item.path && <Check className="h-3.5 w-3.5 text-indigo-400" />}
                    </button>
                  </li>
                ))}
              {browseData?.items.filter((item) => item.is_dir).length === 0 && (
                <li className="px-4 py-6 text-center text-xs text-ink-faint">
                  No subdirectories found
                </li>
              )}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-line px-4 py-3">
          <div className="flex items-center gap-1.5 text-[11px] text-ink-faint">
            <FileUp className="h-3 w-3" />
            <span className="max-w-[280px] truncate font-mono">{selectedDir || pathInput}</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-md px-3 py-1.5 text-xs text-ink-muted hover:text-ink"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={!pathInput.trim()}
              className="flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              <FolderOpen className="h-3.5 w-3.5" />
              Select
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
