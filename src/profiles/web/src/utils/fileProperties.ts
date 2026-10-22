import type { FileMetadata } from "../api/types";

/** Human-readable size units, smallest first. */
const SIZE_UNITS = ["Bytes", "KB", "MB", "GB", "TB"];

/**
 * Format a byte count as a human-readable size string ("1.5 KB").
 *
 * Args:
 *   bytes: File size in bytes.
 *
 * Returns:
 *   Size formatted with two decimal places and a unit suffix.
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const i = Math.max(0, Math.min(SIZE_UNITS.length - 1, Math.floor(Math.log(bytes) / Math.log(k))));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + SIZE_UNITS[i];
}

/**
 * Return the parent directory portion of a Windows or POSIX path.
 *
 * Handles both separators; returns "" for a bare filename.
 */
export function parentDirectory(path: string): string {
  const idx = Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/"));
  return idx === -1 ? "" : path.slice(0, idx);
}

/**
 * Build a multi-line plain-text summary of the most useful file properties,
 * suitable for pasting into tickets or QC records.
 */
export function buildPropertiesSummary(metadata: FileMetadata): string {
  const lines: string[] = [
    `File Properties: ${metadata.name}`,
    `Path: ${metadata.path}`,
    `Type: ${metadata.type}`,
    `Size: ${formatFileSize(metadata.size_bytes)}`,
    `Created: ${metadata.created}`,
    `Modified: ${metadata.modified}`,
  ];
  if (metadata.md5) lines.push(`MD5: ${metadata.md5}`);
  if (metadata.sha256) lines.push(`SHA256: ${metadata.sha256}`);
  return lines.join("\n");
}

/**
 * Shorten a long string by keeping the leading `head` and trailing `tail`
 * characters separated by an ellipsis ("12345678…l234").
 *
 * Values shorter than head + tail + 1 are returned unchanged.
 */
export function truncateMiddle(value: string, head: number, tail: number): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

/**
 * Compact a long filesystem path for single-line display: keeps the first
 * two segments and the final two, joined by "…" ("C:\dir\…\path\file.txt").
 * Short paths are returned unchanged.
 */
export function compactPath(path: string): string {
  const separator = path.includes("\\") ? "\\" : "/";
  const segments = path.split(/[\\/]/);
  if (segments.length <= 5) return path;
  return [segments[0], segments[1], "…", segments[segments.length - 2], segments[segments.length - 1]].join(separator);
}

/** Suffixes for humanized relative times, smallest first. */
const AGE_UNITS: Array<{ ms: number; unit: string }> = [
  { ms: 1000 * 60, unit: "minute" },
  { ms: 1000 * 60 * 60, unit: "hour" },
  { ms: 1000 * 60 * 60 * 24, unit: "day" },
  { ms: 1000 * 60 * 60 * 24 * 30, unit: "month" },
  { ms: 1000 * 60 * 60 * 24 * 365, unit: "year" },
];

/**
 * Humanize a timestamp ("YYYY-MM-DD HH:MM:SS") as a relative age
 * ("15 minutes ago", "just now", "2 days ago"). Future values count as
 * "just now"; an unparseable value falls back to "just now".
 */
export function humanizeTimestamp(dateString: string, now: Date = new Date()): string {
  const date = new Date(dateString.replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return "just now";
  const diff = now.getTime() - date.getTime();
  if (diff < 60_000) return "just now";
  let result = "just now";
  for (const { ms, unit } of AGE_UNITS) {
    if (diff < ms) break;
    const count = Math.floor(diff / ms);
    result = `${count} ${unit}${count === 1 ? "" : "s"} ago`;
  }
  return result;
}
