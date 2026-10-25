import { Clock, PauseCircle, PlayCircle, Timer, X } from "lucide-react";

export interface TimerPreset {
  label: string;
  seconds: number;
}

export interface TimerModalProps {
  isOpen: boolean;
  currentInterval: number;
  onClose: () => void;
  onSetInterval: (seconds: number) => void;
}

const PRESETS: TimerPreset[] = [
  { label: "5 seconds", seconds: 5 },
  { label: "10 seconds", seconds: 10 },
  { label: "30 seconds", seconds: 30 },
  { label: "1 minute", seconds: 60 },
  { label: "5 minutes", seconds: 300 },
];

export function TimerModal({
  isOpen,
  currentInterval,
  onClose,
  onSetInterval,
}: TimerModalProps) {
  if (!isOpen) return null;

  const isActive = currentInterval > 0;

  const handlePreset = (seconds: number) => {
    onSetInterval(seconds);
  };

  const handleCustom = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const input = form.elements.namedItem("custom-interval") as HTMLInputElement;
    const val = parseInt(input.value, 10);
    if (!isNaN(val) && val > 0) {
      onSetInterval(val);
    }
  };

  const handleStop = () => {
    onSetInterval(0);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-[420px] max-w-full rounded-2xl border border-frame-line glass-panel p-5">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between border-b border-line pb-3">
          <div className="flex items-center gap-2 font-semibold text-ink">
            <Timer className="h-5 w-5 text-indigo-400" />
            <span>Auto-Rescan Timer</span>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-ink-muted hover:bg-elevated hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Current status */}
        <div className="mb-4 rounded-lg bg-elevated/50 px-3 py-2 text-xs">
          {isActive ? (
            <div className="flex items-center gap-2 text-emerald-400">
              <PlayCircle className="h-4 w-4 animate-pulse" />
              <span>Auto-rescan every {currentInterval}s</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-ink-secondary">
              <PauseCircle className="h-4 w-4" />
              <span>Auto-rescan is disabled</span>
            </div>
          )}
        </div>

        {/* Presets */}
        <div className="mb-4 space-y-1 text-xs">
          <p className="text-ink-muted">Presets:</p>
          <div className="grid grid-cols-2 gap-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.seconds}
                onClick={() => handlePreset(preset.seconds)}
                className="rounded-lg border border-line bg-elevated/50 px-3 py-1.5 text-left font-medium text-ink-secondary hover:border-indigo-500 hover:bg-indigo-600/10 hover:text-indigo-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        {/* Custom interval */}
        <form onSubmit={handleCustom} className="mb-4">
          <label className="flex items-center gap-2 text-xs font-medium text-ink-secondary">
            <Clock className="h-3.5 w-3.5" />
            <span>Custom interval (seconds):</span>
          </label>
          <div className="mt-1 flex gap-2">
            <input
              type="number"
              name="custom-interval"
              min="1"
              placeholder="e.g. 45"
              className="flex-1 rounded-lg border border-line bg-app px-2 py-1 text-xs text-ink placeholder-ink-faint focus:border-indigo-500 focus:outline-none"
            />
            <button
              type="submit"
              className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-semibold text-white hover:bg-indigo-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              Set
            </button>
          </div>
        </form>

        {/* Stop button — only show when active */}
        {isActive && (
          <button
            onClick={handleStop}
            className="mb-4 w-full rounded-lg border border-line bg-elevated/50 px-3 py-2 text-xs font-medium text-amber-300 hover:border-amber-500 hover:bg-amber-600/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
          >
            Stop Auto-Rescan
          </button>
        )}

        {/* Footer */}
        <div className="flex justify-end gap-2 border-t border-line pt-3">
          <button
            onClick={onClose}
            className="rounded-lg border border-line bg-elevated px-4 py-2 text-xs font-semibold text-ink-secondary hover:bg-elevated/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
