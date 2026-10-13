import { Activity, Terminal } from "lucide-react";
import type { SystemInfo } from "../api/types";

interface HeaderBarProps {
  title: string;
  release: string;
  systemInfo: SystemInfo | null;
}

export function HeaderBar({ title, release, systemInfo }: HeaderBarProps) {
  return (
    <header className="flex items-center justify-between border-b border-line bg-app/80 px-4 py-2.5 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/20 text-indigo-400">
          <Terminal className="h-4 w-4" />
        </div>
        <div>
          <h1 className="text-sm font-semibold tracking-wide text-ink">
            ProFiles {title ? `— ${title}` : ""}
          </h1>
          <p className="text-xs text-ink-muted">By Florent ALBANY • v{release || "2026.8.0"}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs">
        {systemInfo && (
          <div className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-ink-secondary">
            <Activity className="h-3 w-3 text-emerald-400" />
            <span>{systemInfo.hostname}</span>
            <span className="text-ink-faint">|</span>
            <span className="font-mono text-ink-muted">{systemInfo.ip}</span>
          </div>
        )}
      </div>
    </header>
  );
}
