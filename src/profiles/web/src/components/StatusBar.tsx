import Tooltip from "./Tooltip";
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
    <footer className="flex items-center justify-between border-t border-line bg-app px-4 py-2 text-[11px] text-ink-muted transition-colors duration-200">
      <div className="flex items-center gap-4">
        {/* Identity pill — hostname / IP links plus the session user. */}
        {systemInfo && (
          <div className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-0.5 text-ink-secondary">
            <Activity className="h-3 w-3 text-status-success-text" />
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
            <span className="text-ink-faint">|</span>
            <span className="flex items-center gap-1" title="Session user">
              <User className="h-3 w-3 text-ink-faint" />
              <span>{systemInfo.username || "operator"}</span>
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span>
          <strong className="text-ink">{fileCount}</strong> files found
        </span>

        <span className="text-ink-faint">|</span>

        {/* Shortcuts Button */}
        <Tooltip text="Keyboard shortcuts (?)" block={false}>
        <button
          onClick={onShowShortcuts}

          className="focus-ring flex items-center gap-1 text-ink-muted hover:text-ink"
        >
          <Keyboard className="h-3 w-3" />
          <span>Shortcuts</span>
        </button>
        </Tooltip>

        {/* Log Viewer Button */}
        <Tooltip text="Open the application log viewer" block={false}>
        <button
          onClick={onOpenLog}

          className="focus-ring flex items-center gap-1 text-ink-muted hover:text-ink"
        >
          <FileText className="h-3 w-3" />
          <span>Logs</span>
        </button>
        </Tooltip>

        <span className="text-ink-faint">|</span>

        {/* Reload Config Button */}
        {onReloadConfig && (
          <Tooltip text="Reload configuration from disk" block={false}>
          <button
            onClick={onReloadConfig}

            className="focus-ring flex items-center gap-1 text-ink-muted hover:text-ink"
          >
            <RefreshCw className="h-3 w-3" />
            <span>Reload</span>
          </button>
          </Tooltip>
        )}

        {/* Export CSV Button (advanced feature relocated from the action bar) */}
        {onExport && (
          <Tooltip text="Export the current results as CSV" block={false}>
          <button
            onClick={onExport}
            disabled={exportDisabled}

            className="focus-ring flex items-center gap-1 rounded text-ink-muted hover:text-ink disabled:opacity-40 disabled:hover:text-ink-muted"
          >
            <Download className="h-3 w-3" />
            <span>Export CSV</span>
          </button>
          </Tooltip>
        )}

        {/* Language Switcher */}
        {onLanguageChange && (
          <div className="flex items-center overflow-hidden rounded border border-line text-[10px]">
            <Tooltip text="English" block={false}>
            <button
              onClick={() => onLanguageChange("en")}

              className={`flex items-center gap-1 px-1.5 py-0.5 transition-colors ${
                language === "en" ? "bg-indigo-600 text-white" : "text-ink-muted hover:text-ink focus-ring"
              }`}
            >
              <Globe className="h-3 w-3" />
              <span>EN</span>
            </button>
            </Tooltip>
            <Tooltip text="Français" block={false}>
            <button
              onClick={() => onLanguageChange("fr")}

              className={`flex items-center gap-1 px-1.5 py-0.5 transition-colors ${
                language === "fr" ? "bg-indigo-600 text-white" : "text-ink-muted hover:text-ink focus-ring"
              }`}
            >
              <span>FR</span>
            </button>
            </Tooltip>
          </div>
        )}

        {/* Load Config Button */}
        {onLoadConfig && (
          <Tooltip text={activeConfigName ? `Load a different .profiles file (active: ${activeConfigName})` : "Load a .profiles file"} block={false}>
          <button
            onClick={onLoadConfig}
            className="focus-ring flex items-center gap-1 text-ink-muted hover:text-ink"
          >
            <FileCog className="h-3 w-3" />
            <span>Load config…</span>
          </button>
          </Tooltip>
        )}

        {/* Config Button */}
        <Tooltip text="Open configuration file" block={false}>
        <button
          onClick={onOpenConfig}

          className="focus-ring flex items-center gap-1 text-ink-muted hover:text-ink"
        >
          <Settings className="h-3 w-3" />
          <span>Config</span>
        </button>
        </Tooltip>

        {/* Theme Toggle Button */}
        <Tooltip text={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} block={false}>
        <button
          onClick={onToggleTheme}
          className="focus-ring flex items-center gap-1 rounded px-1.5 py-0.5 text-ink-muted hover:bg-elevated hover:text-status-warning-text"
        >
          {theme === "dark" ? <Sun className="h-3 w-3 text-status-warning-text" /> : <Moon className="h-3 w-3 text-chip-indigo-text" />}
          <span>{theme === "dark" ? "Light" : "Dark"}</span>
        </button>
        </Tooltip>
      </div>
    </footer>
  );
}
