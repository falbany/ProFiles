import { Play, Sparkles } from "lucide-react";

interface ActionBarProps {
  onExecute: () => void;
  scanning: boolean;
  hasSelection: boolean;
}

export function ActionBar({
  onExecute,
  scanning,
  hasSelection,
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
