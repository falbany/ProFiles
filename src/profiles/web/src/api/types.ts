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
}

export interface ScanResultsResponse {
  count: number;
  in_progress: boolean;
  items: ScannedFileItem[];
  offset?: number;
  limit?: number;
  has_more?: boolean;
}
