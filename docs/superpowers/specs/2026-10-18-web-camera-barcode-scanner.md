# Implementation Plan: Web Camera Barcode & QR Scanner

## Overview
Add a live camera barcode and QR code scanner to the ProFiles web app using laptop webcams or mobile devices. When a barcode or QR code is detected, it automatically parses criteria (`dir`, `filter`, `ext`, `recursive`), applies them to the controls, triggers a scan, and if exactly 1 matching file is found, prompts the user to launch it (supporting workflows/hooks via `handleLaunch`).

---

## 1. Objectives & Behavior
1. **Activation:**
   - Controls bar camera button (`Camera` icon from `lucide-react`) next to the USB barcode scanner toggle.
   - Global keyboard shortcut: `Ctrl + Shift + B` (or `Cmd + Shift + B` on Mac).
   - Shows shortcut in `ShortcutsModal`.
2. **Viewfinder & Media Stream:**
   - `CameraBarcodeModal` component displaying live webcam video feed with a targeting guide overlay.
   - Uses browser `BarcodeDetector` API where available, with a lightweight fallback or canvas extraction.
   - Clean lifecycle management: starts stream on open, stops all tracks when closed, detected, or unmounted.
   - Friendly handling of camera permission errors or lack of video input devices.
3. **Scan Execution & Single Match Prompt:**
   - On barcode detection, play quick confirmation visual / audio feedback.
   - Closes the camera modal immediately.
   - Parses the payload using existing `parseBarcodeInput(raw)`.
   - Populates `activeDirectory`, `filterText`, `activeExtension`, `recursive`.
   - Triggers `runScan`.
   - If scan result count is exactly `1`:
     - Displays a single-match launch confirmation dialog: *"1 file matched: `<filename>`. Launch now? (Enter / Esc)"*.
     - Confirming with `Enter` calls `handleLaunch(matchedFile)` which automatically routes through `has_hook` to the workflow runner if present.
     - Pressing `Esc` or clicking Dismiss dismisses the prompt and leaves the file highlighted in the table.
   - If 0 or >1 matches:
     - No intrusive popup; list renders matching files as normal.

---

## 2. Technical Breakdown

### A. Camera Barcode Scanner Component (`CameraBarcodeModal.tsx`)
- Location: `src/profiles/web/src/components/CameraBarcodeModal.tsx`
- State:
  - Video stream `MediaStream | null`
  - Camera permission status (`requesting`, `active`, `denied`, `unsupported`)
  - Target reticle animation / scanning animation
- Detection engine:
  - Standard `window.BarcodeDetector` API supported in Chrome, Edge, Safari 17+, Opera.
  - Fallback frame analyzer if `BarcodeDetector` is unsupported in specific desktop browsers.
- Props:
  - `isOpen: boolean`
  - `onClose: () => void`
  - `onDetected: (content: string) => void`

### B. ControlsBar Updates (`ControlsBar.tsx`)
- Add `Camera` icon button next to the USB barcode scanner toggle.
- Tooltip: *"Scan barcode / QR with camera (Ctrl + Shift + B)"*.
- Props: `onOpenScanCamera: () => void`.

### C. Single Match Launch Confirmation Dialog (`SingleMatchLaunchModal.tsx` or inline in `App.tsx`)
- Modal/banner when `singleMatchFile` is present.
- Shows file name, path, and whether a hook is associated with it.
- Keyboard bindings: `Enter` to launch, `Escape` to cancel.

### D. App Orchestration (`App.tsx`)
- Register `Ctrl + Shift + B` shortcut.
- Implement detection handler:
  ```ts
  const handleCameraDetected = async (rawCode: string) => {
    setShowCameraModal(false);
    // Parse values
    const result = parseBarcodeInput(rawCode);
    // Apply values & runScan
    // Check returned count and set singleMatchFile if count === 1
  };
  ```

---

## 3. Verification & Testing
- Unit test for parsing and single-match logic.
- Run `npm run build` in `src/profiles/web`.
- Run `make lint` and pytest suites.
- Verify camera permission handling and stream track termination.
