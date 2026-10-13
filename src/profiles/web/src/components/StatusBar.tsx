import { FileText, Globe, HardDrive, Keyboard, Moon, RefreshCw, Settings, Sun, User } from "lucide-react";
import type { SystemInfo } from "../api/types";

type Language = "en" | "fr";

interface StatusBarProps {
  systemInfo: SystemInfo | null;
  activeDirectory: string;
  fileCount: number;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onOpenLog: () => void;
  onOpenConfig: () => void;
  onShowShortcuts: () => void;
  onReloadConfig?: () => void;
  language?: Language;
  onLanguageChange?: (lang: Language) => void;
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
  onReloadConfig,
  language = "en",
  onLanguageChange,
}: StatusBarProps) {
  return (
    <footer className="flex items-center justify-between border-t border-line bg-app px-4 py-2 text-[11px] text-ink-muted">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <User className="h-3 w-3 text-ink-faint" />
          <span>{systemInfo?.username || "operator"}</span>
        </div>
        <div className="flex items-center gap-1.5 font-mono text-ink-muted">
          <HardDrive className="h-3 w-3 text-ink-faint" />
          <span className="truncate max-w-[280px]">{activeDirectory || "No directory selected"}</span>
        </div>
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

        {/* Log Button */}
        <button
          onClick={onOpenLog}
          title="Open log file"
          className="flex items-center gap-1 text-ink-muted hover:text-ink"
        >
          <FileText className="h-3 w-3" />
          <span>Log</span>
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
