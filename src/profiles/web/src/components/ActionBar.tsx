import { Download, Play, Sparkles } from "lucide-react";

interface ActionBarProps {
  onExecute: () => void;
  scanning: boolean;
  hasSelection: boolean;
  fileCount: number;
  onExport?: () => void;
}

export function ActionBar({
  onExecute,
  scanning,
  hasSelection,
  fileCount,
  onExport,
}: ActionBarProps) {
  return (
    <div className="flex items-center justify-between border-t border-line bg-surface-glass px-4 py-2.5 text-xs">
      <div className="flex items-center gap-3">
        {scanning && (
          <div className="flex items-center gap-2 text-indigo-400">
            <Sparkles className="h-3.5 w-3.5 animate-pulse motion-reduce:animate-none" />
            <span>Scanning directory...</span>
          </div>
        )}
        {onExport && (
          <button
            onClick={onExport}
            disabled={fileCount === 0 || scanning}
            className="flex shrink-0 items-center gap-1.5 rounded-md border border-line bg-elevated px-3 py-1.5 text-xs font-medium text-ink-secondary hover:border-indigo-500 hover:text-indigo-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:opacity-40"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Export CSV</span>
          </button>
        )}
      </div>

      <button
        onClick={onExecute}
        disabled={!hasSelection || scanning}
        className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2 font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
      >
        <Play className="h-3.5 w-3.5 fill-current" />
        <span>Execute</span>
        <kbd className="rounded bg-emerald-800/60 px-1.5 py-0.5 text-[10px] text-emerald-200">↵</kbd>
      </button>
    </div>
  );
}
