import { Activity, Download, FileCog, FileText, Globe, Keyboard, Moon, RefreshCw, Settings, Sun, User } from "lucide-react";
import type { SystemInfo } from "../api/types";

type Language = "en" | "fr";

interface StatusBarProps {
  systemInfo: SystemInfo | null;
  fileCount: number;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onOpenLog: () => void;
  onOpenConfig: () => void;
  onLoadConfig?: () => void;
  onShowShortcuts: () => void;
  onReloadConfig?: () => void;
  /** Export the current results as CSV; the button renders only when set. */
  onExport?: () => void;
  /** Disable export while a scan runs or nothing is loaded yet. */
  exportDisabled?: boolean;
  language?: Language;
  onLanguageChange?: (lang: Language) => void;
  activeConfigName?: string;
}

export function StatusBar({
  systemInfo,
  fileCount,
  theme,
  onToggleTheme,
  onOpenLog,
  onOpenConfig,
  onLoadConfig,
  onShowShortcuts,
  onReloadConfig,
  onExport,
  exportDisabled = false,
  language = "en",
  onLanguageChange,
  activeConfigName,
}: StatusBarProps) {
  return (
    <footer className="flex items-center justify-between border-t border-line bg-app px-4 py-2 text-[11px] text-ink-muted">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <User className="h-3 w-3 text-ink-faint" />
          <span>{systemInfo?.username || "operator"}</span>
        </div>
        {/* Hostname / IP links — moved here from the header. */}
        {systemInfo && (
          <div className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-0.5 text-ink-secondary">
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

      <div className="flex items-center gap-3">
        <span>
          <strong className="text-ink">{fileCount}</strong> files found
        </span>

        <span className="text-ink-faint">|</span>

        {/* Shortcuts Button */}
        <button
          onClick={onShowShortcuts}
          title="Keyboard shortcuts (?)"
          className="flex items-center gap-1 text-ink-muted hover:text-ink"
        >
          <Keyboard className="h-3 w-3" />
          <span>Shortcuts</span>
        </button>

        {/* Log Viewer Button */}
        <button
          onClick={onOpenLog}
          title="Open the application log viewer"
          className="flex items-center gap-1 text-ink-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
        >
          <FileText className="h-3 w-3" />
          <span>Logs</span>
        </button>

        <span className="text-ink-faint">|</span>

        {/* Reload Config Button */}
        {onReloadConfig && (
          <button
            onClick={onReloadConfig}
            title="Reload configuration from disk"
            className="flex items-center gap-1 text-ink-muted hover:text-ink"
          >
            <RefreshCw className="h-3 w-3" />
            <span>Reload</span>
          </button>
        )}

        {/* Export CSV Button (advanced feature relocated from the action bar) */}
        {onExport && (
          <button
            onClick={onExport}
            disabled={exportDisabled}
            title="Export the current results as CSV"
            className="flex items-center gap-1 rounded text-ink-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 disabled:opacity-40 disabled:hover:text-ink-muted"
          >
            <Download className="h-3 w-3" />
            <span>Export CSV</span>
          </button>
        )}

        {/* Language Switcher */}
        {onLanguageChange && (
          <div className="flex items-center overflow-hidden rounded border border-line text-[10px]">
            <button
              onClick={() => onLanguageChange("en")}
              title="English"
              className={`flex items-center gap-1 px-1.5 py-0.5 transition-colors ${
                language === "en" ? "bg-indigo-600 text-white" : "text-ink-muted hover:text-ink"
              }`}
            >
              <Globe className="h-3 w-3" />
              <span>EN</span>
            </button>
            <button
              onClick={() => onLanguageChange("fr")}
              title="Français"
              className={`flex items-center gap-1 px-1.5 py-0.5 transition-colors ${
                language === "fr" ? "bg-indigo-600 text-white" : "text-ink-muted hover:text-ink"
              }`}
            >
              <span>FR</span>
            </button>
          </div>
        )}

        {/* Load Config Button */}
        {onLoadConfig && (
          <button
            onClick={onLoadConfig}
            title={activeConfigName ? `Load a different .profiles file (active: ${activeConfigName})` : "Load a .profiles file"}
            className="flex items-center gap-1 text-ink-muted hover:text-ink"
          >
            <FileCog className="h-3 w-3" />
            <span>Load config…</span>
          </button>
        )}

        {/* Config Button */}
        <button
          onClick={onOpenConfig}
          title="Open configuration file"
          className="flex items-center gap-1 text-ink-muted hover:text-ink"
        >
          <Settings className="h-3 w-3" />
          <span>Config</span>
        </button>

        {/* Theme Toggle Button */}
        <button
          onClick={onToggleTheme}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 text-ink-muted hover:bg-elevated hover:text-amber-300"
        >
          {theme === "dark" ? <Sun className="h-3 w-3 text-amber-400" /> : <Moon className="h-3 w-3 text-indigo-400" />}
          <span>{theme === "dark" ? "Light" : "Dark"}</span>
        </button>
      </div>
    </footer>
  );
}
