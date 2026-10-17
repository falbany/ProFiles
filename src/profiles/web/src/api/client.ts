import type {
  AppConfigData,
  BrowseResult,
  LogLevel,
  LogResponse,
  ScanResultsResponse,
  SystemInfo,
  WorkflowSessionState,
} from "./types";

export async function openLogFile(): Promise<{ status: string; message: string }> {
  const res = await fetch("/api/actions/open-log", {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to open log file");
  return res.json();
}

/** Fetch the tail of `profiles.log` as structured entries (oldest first). */
export async function fetchLogEntries(params?: {
  limit?: number;
  level?: LogLevel | null;
  search?: string;
}): Promise<LogResponse> {
  const search = new URLSearchParams();
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.level) search.set("level", params.level);
  if (params?.search) search.set("search", params.search);
  const res = await fetch(`/api/logs?${search.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch log entries");
  return res.json();
}

export async function fetchSystemInfo(): Promise<SystemInfo> {
  const res = await fetch("/api/system");
  if (!res.ok) throw new Error("Failed to fetch system info");
  return res.json();
}

export async function fetchConfig(): Promise<AppConfigData> {
  const res = await fetch("/api/config");
  if (!res.ok) throw new Error("Failed to fetch app configuration");
  return res.json();
}

export async function selectDirectory(directory: string): Promise<AppConfigData> {
  const res = await fetch("/api/config/select-directory", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ directory }),
  });
  if (!res.ok) throw new Error("Failed to select directory");
  return res.json();
}

export async function loadConfigFile(configPath: string): Promise<AppConfigData> {
  const res = await fetch("/api/config/load", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config_path: configPath }),
  });
  if (!res.ok) throw new Error("Failed to load config file");
  return res.json();
}

export async function createConfigFile(directory: string): Promise<AppConfigData> {
  const res = await fetch("/api/config/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ directory }),
  });
  if (!res.ok) throw new Error("Failed to create config file");
  return res.json();
}

export async function browseForConfigFiles(path: string): Promise<BrowseResult> {
  const url = `/api/fs/browse?path=${encodeURIComponent(path)}&include_hidden=true`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to browse config files");
  return res.json();
}

export async function browseDirectory(path: string): Promise<BrowseResult> {
  const url = `/api/fs/browse?path=${encodeURIComponent(path)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to browse directory");
  return res.json();
}

export async function executeScan(params: {
  directory?: string;
  extension: string;
  filter_text: string;
  recursive: boolean;
}): Promise<{ count: number; directory: string }> {
  const res = await fetch("/api/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("Failed to execute scan");
  return res.json();
}

export type SortDirection = "asc" | "desc";

export async function fetchScanResults(params?: {
  offset?: number;
  limit?: number;
  /** Column name to sort the full result set by (e.g. `"Path"`). */
  sort_by?: string;
  /** Sort direction; alternating clicks flip between `"asc"` and `"desc"`. */
  sort_dir?: SortDirection;
}): Promise<ScanResultsResponse> {
  const search = new URLSearchParams();
  if (params?.offset != null) search.set("offset", String(params.offset));
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.sort_by) search.set("sort_by", params.sort_by);
  if (params?.sort_dir) search.set("sort_dir", params.sort_dir);
  const qs = search.toString();
  const url = `/api/scan/results${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch scan results");
  return res.json();
}

export async function launchFile(params: {
  directory: string;
  filename: string;
  release?: string;
  args?: string;
}): Promise<{ status: string; message: string; path?: string }> {
  const res = await fetch("/api/actions/launch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("Failed to launch file");
  return res.json();
}

export async function revealFile(filePath: string): Promise<{ success: boolean }> {
  const res = await fetch("/api/actions/reveal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath }),
  });
  if (!res.ok) throw new Error("Failed to reveal file");
  return res.json();
}

export async function openFolder(filePath: string): Promise<{ success: boolean }> {
  const res = await fetch("/api/actions/open-folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath }),
  });
  if (!res.ok) throw new Error("Failed to open folder");
  return res.json();
}

export async function openTerminal(filePath: string): Promise<{ status: string; message: string }> {
  const res = await fetch("/api/actions/open-terminal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath }),
  });
  if (!res.ok) throw new Error("Failed to open terminal");
  return res.json();
}

export async function launchWithArgs(filePath: string, args: string): Promise<{ status: string; message: string }> {
  const res = await fetch("/api/actions/launch-with-args", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath, args }),
  });
  if (!res.ok) throw new Error("Failed to launch with arguments");
  return res.json();
}

export async function computeHash(filePath: string, algorithm: "md5" | "sha256"): Promise<{ algorithm: string; hash: string }> {
  const res = await fetch("/api/actions/hash", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath, algorithm }),
  });
  if (!res.ok) throw new Error("Failed to compute hash");
  return res.json();
}

export async function openConfigFile(): Promise<{ status: string; message: string }> {
  const res = await fetch("/api/actions/open-config", {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to open config file");
  return res.json();
}

/** Generate a QR-code PNG encoding the file location or arbitrary text. */
export async function generateBarcode(params: { filePath?: string; file_path?: string; content?: string }): Promise<{ image: string; content: string }> {
  const payload = {
    file_path: params.file_path || params.filePath,
    content: params.content,
  };
  const res = await fetch("/api/actions/barcode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to generate barcode");
  return res.json();
}

export async function startWorkflowSession(params: {
  directory: string;
  filename: string;
  release?: string;
  args?: string;
}): Promise<WorkflowSessionState> {
  const res = await fetch("/api/workflow/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Failed to start workflow session" }));
    throw new Error(errorData.detail || "Failed to start workflow session");
  }
  return res.json();
}

export async function fetchWorkflowSession(sessionId: string): Promise<WorkflowSessionState> {
  const res = await fetch(`/api/workflow/${sessionId}`);
  if (!res.ok) throw new Error("Failed to fetch workflow session");
  return res.json();
}

export async function respondWorkflowSession(
  sessionId: string,
  action: "yes" | "skip" | "no" | "ack",
): Promise<WorkflowSessionState> {
  const res = await fetch(`/api/workflow/${sessionId}/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error("Failed to respond to workflow prompt");
  return res.json();
}
