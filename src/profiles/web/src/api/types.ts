export interface SystemInfo {
  hostname: string;
  ip: string;
  username: string;
  os_release: string;
}

export interface AppConfigData {
  title: string;
  release: string;
  search_dir: string;
  recursive_search: boolean;
  theme: "light" | "dark" | "auto";
  directories: string[];
  extensions: string[];
  filters: string[];
  search_exclude_dirs?: string[];
  search_exclude_files?: string[];
  active_directory: string;
  config_path: string;
  config_exists: boolean;
  column_headers: string[];
  column_names: string[];
  row_colors: [string, string][];
}

export interface BrowseEntry {
  name: string;
  path: string;
  is_dir: boolean;
  is_config?: boolean;
  extension?: string;
}

export interface BrowseResult {
  current_path: string;
  parent_path: string | null;
  items: BrowseEntry[];
}

export interface ScannedFileItem {
  filename: string;
  path: string;
  column_values: Record<string, string>;
  rel_path: string;
  has_hook?: boolean;
  hook_pattern?: string | null;
}

export interface ScanResultsResponse {
  count: number;
  in_progress: boolean;
  items: ScannedFileItem[];
  offset?: number;
  limit?: number;
  has_more?: boolean;
  /** Column name the result set was sorted by, when a sort is active. */
  sort_by?: string;
  /** Direction the result set was sorted in, when a sort is active. */
  sort_dir?: "asc" | "desc";
}

/** Which column the list is sorted by, and in which direction. */
export interface ScanSort {
  column: string;
  direction: "asc" | "desc";
}

/** Severity levels accepted by the log viewer, most verbose first. */
export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

/** A single parsed `profiles.log` line. */
export interface LogEntry {
  /** `YYYY-MM-DD HH:MM:SS`; empty for unparsed lines. */
  timestamp: string;
  /** One of the `LogLevel` values, or `"UNKNOWN"` for unparsed lines. */
  level: LogLevel | "UNKNOWN";
  /** Machine/source identifier emitted by the logger. */
  source: string;
  /** Event name plus any structured `key=value` payload. */
  message: string;
  /** Leading UPPER_SNAKE_CASE event name, empty when absent. */
  event: string;
  /** The original, untouched line. */
  raw: string;
}

export interface LogResponse {
  path: string;
  size_bytes: number;
  total_returned: number;
  entries: LogEntry[];
}
