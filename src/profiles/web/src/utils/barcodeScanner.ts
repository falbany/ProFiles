/**
 * Barcode scanner parsing utility.
 *
 * USB/wedge barcode scanners act as HID keyboards: they type out the
 * barcode content as keystrokes and terminate with `Enter`. This module
 * parses key=value pairs separated by `;` into a structured object, with
 * a fallback to plain-text filter assignment when no pairs are detected.
 */

export interface BarcodeParsedInput {
  filter: string;
  ext: string;
  recursive: boolean;
  dir: string;
  scan: boolean;
}

export interface BarcodeParseResult {
  values: Partial<BarcodeParsedInput>;
  isPlainFilter: boolean;
}

/** Delimiters and keys recognized in the barcode payload. */
const PAIR_DELIMITER = ";";
const KEY_VALUE_DELIMITER = "=";

/**
 * Normalise a key from the barcode to match our internal field names.
 */
function normalizeKey(key: string): string {
  const k = key.trim().toLowerCase();
  // Accept common aliases
  if (k === "extension" || k === "file_ext" || k === "filetype") return "ext";
  if (k === "directory" || k === "path" || k === "folder") return "dir";
  if (k === "recurse" || k === "recursive_search") return "recursive";
  if (k === "filter_text" || k === "query" || k === "search") return "filter";
  return k;
}

/**
 * Parse a raw barcode string into structured key=value pairs.
 *
 * Format: `key=value;key=value;...`
 * Example: `filter=.py;ext=toml;recursive=0;dir=/Users/me/docs;scan=1`
 *
 * If the string contains no `=` at all, it is treated as a plain filter
 * value (isPlainFilter = true).
 */
export function parseBarcodeInput(raw: string): BarcodeParseResult {
  const trimmed = raw.trim();

  // Fallback: no key=value pairs → treat as plain filter
  if (!trimmed.includes(KEY_VALUE_DELIMITER)) {
    return {
      values: { filter: trimmed },
      isPlainFilter: true,
    };
  }

  const values: Partial<BarcodeParsedInput> = {};

  for (const segment of trimmed.split(PAIR_DELIMITER)) {
    const seg = segment.trim();
    if (!seg) continue;

    const eqIdx = seg.indexOf(KEY_VALUE_DELIMITER);
    if (eqIdx === -1) continue;

    const key = normalizeKey(seg.slice(0, eqIdx));
    const value = seg.slice(eqIdx + 1).trim();

    switch (key) {
      case "filter":
        values.filter = value;
        break;
      case "ext":
        values.ext = value;
        break;
      case "recursive":
        values.recursive = parseBoolean(value, true);
        break;
      case "dir":
        values.dir = value;
        break;
      case "scan":
        values.scan = parseBoolean(value, false);
        break;
      // Unknown keys are silently ignored
    }
  }

  return { values, isPlainFilter: false };
}

/**
 * Parse a human-readable boolean. Accepts 0/1, true/false, yes/no, on/off.
 * Defaults to `defaultValue` when the string can't be recognized.
 */
function parseBoolean(value: string, defaultValue: boolean): boolean {
  const v = value.toLowerCase();
  if (["0", "false", "no", "off"].includes(v)) return false;
  if (["1", "true", "yes", "on"].includes(v)) return true;
  return defaultValue;
}
