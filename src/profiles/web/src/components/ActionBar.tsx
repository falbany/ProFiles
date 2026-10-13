import { Play, Sparkles } from "lucide-react";

interface ActionBarProps {
  onExecute: () => void;
  closeOnLaunch: boolean;
  onCloseOnLaunchChange: (val: boolean) => void;
  scanning: boolean;
  hasSelection: boolean;
}

export function ActionBar({
  onExecute,
  closeOnLaunch,
  onCloseOnLaunchChange,
  scanning,
  hasSelection,
}: ActionBarProps) {
  return (
    <div className="flex items-center justify-between border-t border-line bg-surface-glass px-4 py-2.5 text-xs">
      <div className="flex items-center gap-3">
        <label className="flex cursor-pointer select-none items-center gap-2 text-ink-secondary">
          <input
            type="checkbox"
            checked={closeOnLaunch}
            onChange={(e) => onCloseOnLaunchChange(e.target.checked)}
            className="rounded border-line text-indigo-600 focus:ring-0"
          />
          <span>Close ProFiles after launching a file</span>
        </label>
        {scanning && (
          <div className="flex items-center gap-2 text-indigo-400">
            <Sparkles className="h-3.5 w-3.5 animate-pulse" />
            <span>Scanning directory...</span>
          </div>
        )}
      </div>

      <button
        onClick={onExecute}
        disabled={!hasSelection || scanning}
        className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2 font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-40"
      >
        <Play className="h-3.5 w-3.5 fill-current" />
        <span>Execute</span>
        <kbd className="rounded bg-emerald-800/60 px-1.5 py-0.5 text-[10px] text-emerald-200">↵</kbd>
      </button>
    </div>
  );
}
