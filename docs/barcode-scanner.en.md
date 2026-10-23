# Barcode Scanner Mode

> 🏠 **[Documentation Home](./README.md)** |
> ⚙️ **[Configuration](./configuration-profile.en.md)** |
> 🚀 **[Advanced Guide](./advanced/advanced-guide.en.md)** |
> 🇫🇷 **[Version Française](./barcode-scanner.fr.md)**

---

## Overview

ProFiles supports **barcode scanner input** via USB HID (Human Interface Device) wedge scanners. When enabled, a connected barcode scanner acts as a keyboard, typing out the barcode content character-by-character and pressing `Enter` at the end. ProFiles intercepts this input and parses it into structured `key=value` pairs, auto-applying them to the scan controls and triggering an immediate scan.

This feature is ideal for kiosk deployments, inventory management, and rapid file launch workflows.

---

## Enabling Barcode Mode

### Via the UI

1. Click the **Barcode** button in the **SearchBar** (rightmost group, beside the Timer).
2. The button icon (`QrCode`) will begin **pulsing** to indicate that barcode mode is active.
3. The button's aria-label changes to "Disable barcode mode" while active.

### Via Keyboard Shortcut

- Press **`Ctrl+B`** to toggle barcode mode on or off.

### Global Key Listener

When barcode mode is active, ProFiles installs a **document-level `keydown` listener** that captures every keystroke. A debouncing mechanism (default: 50 ms) groups characters into a single scan payload. When the terminating `Enter` key is detected, the accumulated input is dispatched to the barcode parser.

---

## Barcode Payload Format

### Structured Format (`key=value;key=value`)

Barcode content is parsed as semicolon-delimited key=value pairs:

```
filter=.py;ext=toml;recursive=0;dir=/Users/me/docs;scan=1
```

| Key | Alias(es) | Description |
|-----|-----------|-------------|
| `filter` | `query`, `search`, `filter_text` | Text filter applied to the file list |
| `ext` | `extension`, `filetype` | File extension filter (e.g., `.py`, `.toml`) |
| `recursive` | `recurse`, `recursive_search` | `1`/`true`/`on` → recursive; `0`/`false`/`off` → non-recursive |
| `dir` | `directory`, `path`, `folder` | Directory path to scan. `~` expands to the OS home directory |
| `scan` | — | `1`/`true` → auto-trigger scan after applying values; `0`/`false` → apply only |

### Plain-Text Fallback

If the barcode content contains **no `=` delimiter**, the entire string is treated as a plain filter value:

```
project-report-final
```

This sets the filter field to `project-report-final` and (if `scan` is not specified) does **not** auto-scan.

---

## Auto-Apply & Auto-Scan

When a barcode is scanned:

1. **Parsed values are applied** to the controls (directory in the header bar; filter, extension, recursive toggle in the search bar).
2. If the `scan=1` key is present (or if the payload is a structured `key=value` set), ProFiles **automatically triggers a scan** with the new criteria.
3. A **toast notification** confirms the scan was initiated.

---

## UI Indicators

### SearchBar Button

| State | Icon | Behavior |
|-------|------|----------|
| **Inactive** | `QrCode` (static) | Click to enable barcode mode |
| **Active** | `QrCode` + `animate-pulse` | Click to disable; keystrokes are captured |

The button uses consistent app styling:
- `border border-line bg-elevated`
- `hover:border-indigo-500 hover:text-ink`
- `focus-visible:ring-2 focus-visible:ring-indigo-500`
- `transition-colors`

### Toast Notifications

| Scenario | Toast Message |
|----------|---------------|
| Barcode parsed & scan triggered | `Barcode scanned: applied N field(s) and triggered scan.` |
| Barcode parsed (no scan flag) | `Barcode scanned: applied N field(s).` |
| Barcode mode disabled | `Barcode mode disabled.` |
| Barcode mode enabled | `Barcode mode enabled. Scan a barcode to auto-fill controls and trigger a scan.` |

---

## Technical Architecture

```
┌─────────────────────────────────────────────────┐
│  Barcode Scanner (USB HID)                      │
│  — Acts as keyboard —                         │
│  Types: filter=pdf;ext=pdf;dir=~/docs;scan=1    │
│  Presses: Enter                                │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  App.tsx — Global keydown listener              │
│  — Captures keystrokes                         │
│  — Debounces into raw string                    │
│  — Dispatches to parseBarcodeInput()            │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  barcodeScanner.ts — parseBarcodeInput(raw)     │
│  — Splits on ";" delimiter                      │
│  — Splits each segment on "="                   │
│  — Normalizes keys via normalizeKey()           │
│  — Returns { values, isPlainFilter }            │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  App.tsx — handleBarcodeSubmit()                 │
│  — Applies values to search/header controls     │
│  — Triggers scan if scan=1                      │
│  — Shows toast notification                     │
└──────────────────────────────────────────────────┘
```

### Key Functions

| Function | File | Description |
|----------|------|-------------|
| `parseBarcodeInput(raw)` | `utils/barcodeScanner.ts` | Parses the raw barcode string into `{ values, isPlainFilter }` |
| `normalizeKey(key)` | `utils/barcodeScanner.ts` | Maps aliases (e.g., `directory` → `dir`, `recurse` → `recursive`) |
| `handleBarcodeToggle()` | `App.tsx` | Toggles barcode mode and manages the global keydown listener |
| `handleBarcodeSubmit(raw)` | `App.tsx` | Applies parsed values and optionally triggers a scan |

---

## Use Cases

### Kiosk / Inventory Station

1. Enable barcode mode (`Ctrl+B` or click the QrCode button).
2. Scan a barcode sticker on a file folder or product.
3. The barcode contains `dir=/path/to/assets;ext=png;scan=1`.
4. ProFiles immediately scans the directory and displays all PNG files.

### Rapid Filter Assignment

1. Scan a barcode containing `filter=urgent;scan=1`.
2. ProFiles sets the filter input to "urgent" and scans the current directory.

### Home Directory Navigation

1. Scan a barcode containing `dir=~;scan=1`.
2. ProFiles sets the directory to your OS home folder and scans.

---

## QR Code Generation

### Sharing File Locations

ProFiles can **generate QR codes** encoding a file's location as a barcode payload, so recipients can scan it directly into their own ProFiles instance:

1. Right-click any file in the results list.
2. Select **Generate QR Code** from the context menu.
3. A modal appears showing the QR code image and the encoded payload (e.g. `dir=/path/to/dir;filter=filename.ext;ext=.ext;scan=1`).
4. Print or share the QR code — the recipient enables barcode mode (`Ctrl+B`) and scans the QR. ProFiles auto-fills the directory, filter, and extension, then triggers a scan.

### How It Works

| Component | Description |
|-----------|-------------|
| `POST /api/actions/barcode` | Backend endpoint that builds the payload and generates a QR PNG |
| `generateBarcode()` | Frontend client function that fetches the QR image + payload |
| `ContextMenu.tsx` | Adds the "Generate QR Code" item (with `QrCode` icon) |
| `App.tsx` | Renders the QR modal and manages open/close state |

The payload format is identical to what the barcode scanner consumes, ensuring full round-trip compatibility.

---

## Accessibility

- The barcode button has an `aria-label` that updates with the toggle state.
- The barcode button includes a `title` tooltip: "Toggle barcode scanner mode (USB HID)."
- When active, the pulsing animation respects `motion-reduce: animate-none`.
- Toast notifications are announced by screen readers.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Barcode input not detected | Ensure barcode mode is active (button is pulsing). Check that no other input field is focused. |
| Keys appearing in filter field | Barcode mode may have been disabled mid-scan. Re-enable and retry. |
| `~` not expanding to home | Verify the backend's `Path.expanduser()` is available (POSIX systems). |
| Too few characters captured | Increase the debounce interval in `App.tsx` if scanning very slowly. |
| Barcode scanned but no scan triggered | Ensure the payload includes `scan=1`. |
