import { HardDrive, Settings, User } from "lucide-react";
import type { SystemInfo } from "../api/types";

interface StatusBarProps {
  systemInfo: SystemInfo | null;
  activeDirectory: string;
  fileCount: number;
}

export function StatusBar({ systemInfo, activeDirectory, fileCount }: StatusBarProps) {
  return (
    <footer className="flex items-center justify-between border-t border-slate-800 bg-slate-950 px-4 py-2 text-[11px] text-slate-400">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <User className="h-3 w-3 text-slate-500" />
          <span>{systemInfo?.username || "operator"}</span>
        </div>
        <div className="flex items-center gap-1.5 font-mono text-slate-400">
          <HardDrive className="h-3 w-3 text-slate-500" />
          <span>{activeDirectory || "No directory selected"}</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <span>
          <strong className="text-slate-200">{fileCount}</strong> files found
        </span>
        <button
          onClick={() => window.open("/api/config", "_blank")}
          className="flex items-center gap-1 text-slate-400 hover:text-slate-200"
        >
          <Settings className="h-3 w-3" />
          <span>Config</span>
        </button>
      </div>
    </footer>
  );
}
