import { Activity, Terminal } from "lucide-react";
import type { SystemInfo } from "../api/types";

interface HeaderBarProps {
  title: string;
  release: string;
  systemInfo: SystemInfo | null;
}

export function HeaderBar({ title, release, systemInfo }: HeaderBarProps) {
  return (
    <header className="flex items-center justify-between border-b border-line bg-app/90 px-5 py-3 backdrop-blur-xl shadow-xs transition-all">
      <div className="flex items-center gap-3.5">
        <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 text-indigo-400 border border-indigo-500/30 shadow-xs">
          <Terminal className="h-4 w-4" />
          <span className="absolute -bottom-0.5 -right-0.5 flex h-2.5 w-2.5 items-center justify-center rounded-full bg-emerald-500 ring-2 ring-app" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-bold tracking-tight text-ink font-heading">
              ProFiles
            </h1>
            {title && (
              <>
                <span className="text-ink-faint">/</span>
                <span className="text-xs font-medium text-indigo-400/90 bg-indigo-500/10 px-2 py-0.5 rounded-md border border-indigo-500/20">
                  {title}
                </span>
              </>
            )}
          </div>
          <p className="text-[11px] font-medium text-ink-muted tracking-wide mt-0.5">
            Crafted by <span className="text-ink font-semibold">Florent ALBANY</span> • <span className="font-mono text-indigo-400">v{release || "2026.8.0"}</span>
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs">
        {systemInfo && (
          <div className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-ink-secondary">
            <Activity className="h-3 w-3 text-emerald-400" />
            <a
              href={`http://${systemInfo.hostname}:${window.location.port}`}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Open ProFiles on ${systemInfo.hostname}`}
              className="font-mono hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 rounded px-1 py-0.5"
            >
              {systemInfo.hostname}
            </a>
            <span className="text-ink-faint">|</span>
            <a
              href={`http://${systemInfo.ip}:${window.location.port}`}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Open ProFiles on ${systemInfo.ip}`}
              className="font-mono hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 rounded px-1 py-0.5"
            >
              {systemInfo.ip}
            </a>
          </div>
        )}
      </div>
    </header>
  );
}
