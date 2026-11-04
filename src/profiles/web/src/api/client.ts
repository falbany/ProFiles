import type {
  AppConfigData,
  BrowseResult,
  ConfigContentData,
  ExternalEvent,
  FileMetadata,
  LogLevel,
  LogResponse,
  ScanResultsResponse,
  SystemInfo,
  ValidationIssue,
  WorkflowSessionState,
} from "./types";

/**
 * Error carrying the HTTP status so callers can react to specific codes —
 * e.g. 404 from the workflow session routes means the server-side session
 * expired or was purged (TTL), and the UI can offer recovery (#79). When
 * the body's detail is not a plain string (a validation issue list from
 * the config editor save endpoints), it is preserved verbatim in
 * `detail` instead of being flattened into the message.
 */
export class ApiError extends Error {
  status: number;
  /** Raw body detail when it is not a plain string (e.g. ValidationIssue[]). */
  detail?: string | ValidationIssue[];
  constructor(message: string, status: number, detail?: string | ValidationIssue[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Build an ApiError from a failed Response, preferring the body's detail. */
async function apiError(res: Response, fallback: string): Promise<ApiError> {
  let message = fallback;
  let detail: string | ValidationIssue[] | undefined;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string" && body.detail) {
      message = body.detail;
      detail = body.detail;
    } else if (Array.isArray(body?.detail)) {
      // Heterogeneous 400 detail from the config editor save endpoints: a
      // validation issue list. Keep the raw array for callers that render
      // it as data (editor gate modal) instead of flattening it to text.
      detail = body.detail;
    }
  } catch {
    // keep the fallback message
  }
  return new ApiError(message, res.status, detail);
}

/** Fetch UI events recorded after *afterId* (config handoff notifications). */
export async function fetchNotifications(afterId: number): Promise<{ events: ExternalEvent[] }> {
  const res = await fetch(`/api/notifications?after=${afterId}`);
  if (!res.ok) throw new Error("Failed to fetch notifications");
  return res.json();
}

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

/** Flip the running server between LAN exposure and loopback-only.
 *
 * The rebind runs after the response ships, so the returned state is the
 * *requested* one — observe the actual outcome with waitForLanState().
 */
export async function setLanEnabled(
  lan: boolean
): Promise<{ host: string; lan_enabled: boolean; status: string }> {
  const res = await fetch("/api/system/bind", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lan }),
  });
  if (!res.ok) {
    let detail = "Failed to update LAN binding";
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // keep the fallback message
    }
    throw new Error(detail);
  }
  return res.json();
}

/**
 * Poll /api/system until the LAN state matches the request, or timeout.
 * The rebind runs on the server after the bind response, so the state
 * needs a moment to catch up — and the server may briefly refuse
 * connections mid-restart, so failed polls are tolerated.
 */
export async function waitForLanState(
  target: boolean,
  timeoutMs = 10000
): Promise<SystemInfo | null> {
  const deadline = Date.now() + timeoutMs;
  let last: SystemInfo | null = null;
  while (Date.now() < deadline) {
    try {
      last = await fetchSystemInfo();
      if (last.lan_enabled === target) return last;
    } catch {
      // the server may be mid-restart; keep polling until the deadline
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return last;
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

export async function loadConfigContent(filename: string, content: string): Promise<AppConfigData> {
  const res = await fetch("/api/config/load-content", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, content }),
  });
  if (!res.ok) {
    let detail = `Failed to apply dropped config (${filename})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // keep the generic message
    }
    throw new Error(detail);
  }
  return res.json();
}

/** Re-read the active configuration file from disk (Reload button). */
export async function reloadConfig(): Promise<AppConfigData> {
  const res = await fetch("/api/config/reload", { method: "POST" });
  if (!res.ok) {
    let detail = "Failed to reload configuration";
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // keep the generic message
    }
    throw new Error(detail);
  }
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

/** Fetch the active configuration file's text for the YAML editor (404 when the recorded file vanished). */
export async function fetchConfigContent(): Promise<ConfigContentData> {
  const res = await fetch("/api/config/content");
  if (!res.ok) throw await apiError(res, "Failed to fetch config content");
  return res.json();
}

/**
 * Validate editor content in memory. Invalid content is answered as data
 * (HTTP 200 with `valid: false` and the issue list), never as an HTTP
 * error, so drafts can be shown without try/catch.
 */
export async function validateConfigContent(
  filename: string,
  content: string,
): Promise<{ valid: boolean; issues: ValidationIssue[] }> {
  const res = await fetch("/api/config/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, content }),
  });
  if (!res.ok) throw await apiError(res, "Failed to validate config content");
  return res.json();
}

/** Generate starter configuration content without touching the session state. */
export async function fetchConfigTemplate(): Promise<{ content: string; filename: string }> {
  const res = await fetch("/api/config/template", { method: "POST" });
  if (!res.ok) throw await apiError(res, "Failed to fetch config template");
  return res.json();
}

/**
 * Result of a successful save/save-as: the applied config plus the hash
 * of what was written — the next save's staleness baseline (issue #116).
 */
export interface ConfigSaveResult {
  config: AppConfigData;
  contentHash: string | null;
}

/** Options of `saveConfigFile` — the staleness-guard contract (issue #116). */
export interface SaveBaselineOptions {
  /** Baseline hash from the content/save response the editor loaded. */
  baselineHash?: string | null;
  /** True after the user answers the 409 conflict with "overwrite anyway". */
  overwriteChanges?: boolean;
}

/**
 * Write editor content to the active configuration file and apply it.
 * Rejects with an ApiError whose `detail` is either a plain message
 * (e.g. a session-trial refusal), a `ValidationIssue[]` gate list, or a
 * 409 staleness conflict when the file changed on disk since the
 * baseline hash was taken (issue #116) — callers rendering the
 * compliance gate / conflict dialog should inspect `detail` and `status`.
 */
export async function saveConfigFile(
  content: string,
  force: boolean,
  options: SaveBaselineOptions = {},
): Promise<ConfigSaveResult> {
  const res = await fetch("/api/config/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content,
      force,
      baseline_hash: options.baselineHash ?? null,
      overwrite_changes: options.overwriteChanges ?? false,
    }),
  });
  if (!res.ok) throw await apiError(res, "Failed to save configuration");
  const payload: { config: AppConfigData; content_hash?: string | null } = await res.json();
  return { config: payload.config, contentHash: payload.content_hash ?? null };
}

/**
 * Write editor content to a new configuration file and apply it; also
 * anchors a session trial onto disk. A 409 ApiError means the target
 * exists and `overwrite` was false; a 400 carries a plain message or a
 * `ValidationIssue[]` gate list in `detail`.
 */
export async function saveConfigFileAs(params: {
  content: string;
  filename: string;
  directory: string;
  force: boolean;
  overwrite: boolean;
}): Promise<ConfigSaveResult> {
  const res = await fetch("/api/config/save-as", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw await apiError(res, "Failed to save configuration as");
  const payload: { config: AppConfigData; content_hash?: string | null } = await res.json();
  return { config: payload.config, contentHash: payload.content_hash ?? null };
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

export async function executeScan(
  params: {
    directory?: string;
    extension: string;
    filter_text: string;
    recursive: boolean;
  },
  signal?: AbortSignal,
): Promise<{ count: number; directory: string }> {
  const res = await fetch("/api/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
    signal,
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
  /** Abort signal so superseded in-flight requests can be cancelled. */
  signal?: AbortSignal;
}): Promise<ScanResultsResponse> {
  const search = new URLSearchParams();
  if (params?.offset != null) search.set("offset", String(params.offset));
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.sort_by) search.set("sort_by", params.sort_by);
  if (params?.sort_dir) search.set("sort_dir", params.sort_dir);
  const qs = search.toString();
  const url = `/api/scan/results${qs ? `?${qs}` : ""}`;
  const res = await fetch(url, { signal: params?.signal });
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

/** Decode a base64 camera frame server-side (fallback for webviews without BarcodeDetector). */
export async function decodeBarcodeImage(params: { imageBase64: string; formats?: string[] }): Promise<{ decoded: string | null; format?: string }> {
  const res = await fetch("/api/actions/barcode/decode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_base64: params.imageBase64, formats: params.formats }),
  });
  if (!res.ok) {
    if (res.status === 503) throw new Error("Server-side barcode decoding is unavailable");
    throw new Error(`Failed to decode frame (HTTP ${res.status})`);
  }
  return res.json();
}

/** Fetch metadata (size, hashes, timestamps, attributes) for a single file. */
export async function fetchFileMetadata(filePath: string, signal?: AbortSignal): Promise<FileMetadata> {
  const res = await fetch("/api/actions/metadata", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath }),
    signal,
  });
  if (!res.ok) throw new Error("Failed to fetch metadata");
  return res.json();
}

/** Save CSV content to disk via the server (browser downloads don't work in the desktop webview). */
export async function exportCsvToDisk(content: string, filename: string): Promise<{ status: string; message: string; path?: string | null }> {
  const res = await fetch("/api/actions/export-csv", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, filename }),
  });
  if (!res.ok) throw new Error("Failed to export CSV");
  return res.json();
}

/**
 * Save an image (data URL or bare base64) via the server, which writes it
 * to ~/Downloads — browser downloads are a no-op in the desktop webview
 * (issue #31).
 */
export async function saveImageToDisk(image: string, filename: string): Promise<{ status: string; message: string; path?: string | null }> {
  const res = await fetch("/api/actions/save-image", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_base64: image, filename }),
  });
  if (!res.ok) throw new Error("Failed to save image");
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
  if (!res.ok) throw await apiError(res, "Failed to start workflow session");
  return res.json();
}

export async function fetchWorkflowSession(sessionId: string): Promise<WorkflowSessionState> {
  const res = await fetch(`/api/workflow/${sessionId}`);
  if (!res.ok) throw await apiError(res, "Failed to fetch workflow session");
  return res.json();
}

export async function respondWorkflowSession(
  sessionId: string,
  action: "yes" | "skip" | "no" | "ack" | "bypass",
): Promise<WorkflowSessionState> {
  const res = await fetch(`/api/workflow/${sessionId}/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw await apiError(res, "Failed to respond to workflow prompt");
  return res.json();
}

/** Abort a still-interactive workflow session (modal closed mid-workflow). */
export async function abortWorkflowSession(sessionId: string): Promise<WorkflowSessionState> {
  const res = await fetch(`/api/workflow/${sessionId}/abort`, { method: "POST" });
  if (!res.ok) throw await apiError(res, "Failed to abort workflow session");
  return res.json();
}
