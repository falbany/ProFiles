import { FileText, HardDrive, Keyboard, Moon, Settings, Sun, User } from "lucide-react";
import type { SystemInfo } from "../api/types";

interface StatusBarProps {
  systemInfo: SystemInfo | null;
  activeDirectory: string;
  fileCount: number;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onOpenLog: () => void;
  onOpenConfig: () => void;
  onShowShortcuts: () => void;
}

export function StatusBar({
  systemInfo,
  activeDirectory,
  fileCount,
  theme,
  onToggleTheme,
  onOpenLog,
  onOpenConfig,
  onShowShortcuts,
}: StatusBarProps) {
  return (
    <footer className="flex items-center justify-between border-t border-slate-800 bg-slate-950 px-4 py-2 text-[11px] text-slate-400">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <User className="h-3 w-3 text-slate-500" />
          <span>{systemInfo?.username || "operator"}</span>
        </div>
        <div className="flex items-center gap-1.5 font-mono text-slate-400">
          <HardDrive className="h-3 w-3 text-slate-500" />
          <span className="truncate max-w-[280px]">{activeDirectory || "No directory selected"}</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span>
          <strong className="text-slate-200">{fileCount}</strong> files found
        </span>

        <span className="text-slate-700">|</span>

        {/* Shortcuts Button */}
        <button
          onClick={onShowShortcuts}
          title="Keyboard shortcuts (?)"
          className="flex items-center gap-1 text-slate-400 hover:text-slate-200"
        >
          <Keyboard className="h-3 w-3" />
          <span>Shortcuts</span>
        </button>

        {/* Log Button */}
        <button
          onClick={onOpenLog}
          title="Open log file"
          className="flex items-center gap-1 text-slate-400 hover:text-slate-200"
        >
          <FileText className="h-3 w-3" />
          <span>Log</span>
        </button>

        {/* Config Button */}
        <button
          onClick={onOpenConfig}
          title="Open configuration file"
          className="flex items-center gap-1 text-slate-400 hover:text-slate-200"
        >
          <Settings className="h-3 w-3" />
          <span>Config</span>
        </button>

        {/* Theme Toggle Button */}
        <button
          onClick={onToggleTheme}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 text-slate-400 hover:bg-slate-800 hover:text-amber-300"
        >
          {theme === "dark" ? <Sun className="h-3 w-3 text-amber-400" /> : <Moon className="h-3 w-3 text-indigo-400" />}
          <span>{theme === "dark" ? "Light" : "Dark"}</span>
        </button>
      </div>
    </footer>
  );
}
