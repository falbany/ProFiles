import { Activity, Link2, Terminal } from "lucide-react";
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
            <a
              href={`http://${systemInfo.hostname}:8088`}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Open ProFiles on ${systemInfo.hostname}:8088`}
              className="font-mono hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 rounded px-1 py-0.5"
            >
              {systemInfo.hostname}
              <Link2 className="ml-1 h-3 w-3 text-ink-muted inline-block" />
            </a>
            <span className="text-ink-faint">|</span>
            <a
              href={`http://${systemInfo.ip}:8088`}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Open ProFiles on ${systemInfo.ip}:8088`}
              className="font-mono hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 rounded px-1 py-0.5"
            >
              <Link2 className="mr-1 h-3 w-3 text-ink-muted inline-block" />
              {systemInfo.ip}
            </a>
          </div>
        )}
      </div>
    </header>
  );
}
