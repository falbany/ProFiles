/**
 * CSV export utility.
 *
 * Produces a properly-formatted CSV (RFC 4180 compliant) with two sections:
 * 1. Metadata rows (key, value pairs) — app version, config path, etc.
 * 2. A blank separator line, then the file data table with column headers.
 *
 * Uses CRLF (\r\n) line endings per RFC 4180.
 */

import type { AppConfigData, ScannedFileItem } from "../api/types";

/**
 * Sanitize a value for CSV output — wraps in quotes if it contains
 * commas, quotes, or newlines, and escapes embedded quotes by doubling.
 * Per RFC 4180, fields containing these characters MUST be quoted.
 */
function csvCell(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

/**
 * Build a RFC 4180-compliant CSV string with metadata followed by file data.
 *
 * @param files — the scanned file items to export
 * @param columnNames — column names from config (display names)
 * @param config — the active app config (for metadata)
 * @param filterText — the active filter text (may differ from config.filters[0])
 */
export function exportToCsv(
  files: ScannedFileItem[],
  columnNames: string[],
  config?: AppConfigData,
  filterText?: string,
): string {
  const lines: string[] = [];
  const now = new Date();

  // --- Metadata section ---
  // Each metadata line is a "Key,Value" pair for easy parsing.
  const metadata: [string, string][] = [
    ["Exported", now.toISOString()],
    ["App Version", config?.release ?? "unknown"],
    ["Config File", config?.config_path ?? "none"],
    ["Config Exists", String(config?.config_exists ?? false)],
    ["Directory", config?.active_directory ?? ""],
    ["Extensions", config?.extensions?.join(" | ") ?? ""],
    ["Filter Text", filterText ?? config?.filters?.[0] ?? ""],
    ["Recursive", String(config?.recursive_search ?? true)],
    ["Title", config?.title ?? ""],
    ["Release", config?.release ?? ""],
  ];

  for (const [key, val] of metadata) {
    lines.push(`${csvCell(key)},${csvCell(val)}`);
  }

  // Blank separator line between metadata and data
  lines.push("");

  // --- Data section ---
  // Determine which column keys to pull from each file item.
  // columnNames from config are display names; we try them as keys into
  // both column_values and top-level ScannedFileItem fields.
  const dataColumns: string[] = columnNames.length > 0 ? columnNames : ["filename", "path", "rel_path"];

  // Header row
  lines.push(dataColumns.map(csvCell).join(","));

  // Data rows
  for (const file of files) {
    const row = dataColumns.map((col) => {
      // Try column_values first, then top-level fields.
      if (col in file) {
        return csvCell(String((file as unknown as Record<string, unknown>)[col] ?? ""));
      }
      return csvCell(file.column_values[col] ?? "");
    });
    lines.push(row.join(","));
  }

  // RFC 4180: use CRLF line endings
  return lines.join("\r\n");
}
