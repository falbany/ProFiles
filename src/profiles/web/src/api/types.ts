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
  directories: string[];
  extensions: string[];
  filters: string[];
  active_directory: string;
  column_headers: string[];
  column_names: string[];
  row_colors: [string, string][];
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
}
