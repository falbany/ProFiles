import { Activity, Terminal } from "lucide-react";
import type { SystemInfo } from "../api/types";

interface HeaderBarProps {
  title: string;
  release: string;
  systemInfo: SystemInfo | null;
}

export function HeaderBar({ title, release, systemInfo }: HeaderBarProps) {
  return (
    <header className="flex items-center justify-between border-b border-slate-800 bg-slate-950/80 px-4 py-2.5 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/20 text-indigo-400">
          <Terminal className="h-4 w-4" />
        </div>
        <div>
          <h1 className="text-sm font-semibold tracking-wide text-slate-100">
            ProFiles {title ? `— ${title}` : ""}
          </h1>
          <p className="text-xs text-slate-400">By Florent ALBANY • v{release || "2026.8.0"}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs">
        {systemInfo && (
          <div className="flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-slate-300">
            <Activity className="h-3 w-3 text-emerald-400" />
            <span>{systemInfo.hostname}</span>
            <span className="text-slate-600">|</span>
            <span className="font-mono text-slate-400">{systemInfo.ip}</span>
          </div>
        )}
      </div>
    </header>
  );
}
