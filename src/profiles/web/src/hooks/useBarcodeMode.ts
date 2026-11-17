import { useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { barcodeShouldScan, parseBarcodeInput } from "../utils/barcodeScanner";
import type { BarcodeParsedInput } from "../utils/barcodeScanner";
import type { ScanParams, ScanOutcome } from "./useScanController";
import type { ScannedFileItem } from "../api/types";

export interface BarcodeModeDeps {
  showToast: (msg: string, kind?: "info" | "error") => void;
  scanWith: (params: ScanParams, opts?: { errorPrefix?: string }) => Promise<ScanOutcome>;
  getScanParams: () => ScanParams;
  onApplyValues: (values: Partial<BarcodeParsedInput>) => void;
  onSingleMatch: (file: ScannedFileItem) => void;
  onCameraClose: () => void;
  setFilterText: Dispatch<SetStateAction<string>>;
}

/**
 * Barcode scanner mode (issue #148 PR 4), moved verbatim from `App.tsx`:
 * the `barcodeMode` state + buffer, the wedge-scanner capture-phase keydown
 * listener, `handleBarcodeToggle`, the internal `applyBarcodeValues`, and
 * the camera-detected handler.
 *
 * Mechanism ruling (PR 3 precedent, see `useGlobalShortcuts`): the keydown
 * effect captures `const d = deps` INSIDE the effect body — once per
 * subscription, never through a per-render ref — and keeps the original
 * `[barcodeMode]` dep list, so its synchronous reads (`d.showToast`,
 * `d.setFilterText`, the per-render `applyBarcodeValues` captured at
 * subscription, and the hook's own `setBarcodeMode`/`barcodeBufferRef`,
 * which App's original effect closure captured the same way — useState's
 * setter and the ref are stable identities) keep the exact staleness
 * windows the original inline effect had. The ONLY latest-ref reads are
 * inside the two 50 ms timeouts: `depsRef.current.scanWith(
 * depsRef.current.getScanParams(), …)` (depsRef kept current by a
 * per-render effect, the `useAutoRescanTimer` idiom) — exactly what
 * today's `handleScanRef.current()` read-at-fire gave: the rescan sees the
 * just-applied values, not this render's (issue #34).
 *
 * Preserved quirks — do NOT "fix" (behavior-preserving extraction):
 * - the empty-buffer Enter returns BEFORE e.preventDefault();
 * - the 50 ms timeouts are fire-and-forget (no cleanup on unmount);
 * - the mode stays ON when `barcodeShouldScan` is false (`scan=0`-only
 *   and unknown-key barcodes apply nothing and leave the listener armed).
 *
 * Superseded quirk (behavior change sanctioned by issue #187): the handler
 * originally never called stopPropagation, so wedge-consumed keydowns also
 * reached the global-shortcuts window listener — a typed "p" opened
 * Properties, "?" opened the shortcuts modal, and the terminating Enter
 * executed the selected file. Wedge-CONSUMED keys (printable accumulation;
 * Enter with a non-empty buffer) now stopPropagation. Escape and the
 * empty-buffer Enter still propagate DELIBERATELY: Escape keeps closing
 * open surfaces while cancelling the mode, and an empty-buffer Enter keeps
 * the manual execute shortcut.
 */
export function useBarcodeMode(deps: BarcodeModeDeps): {
  barcodeMode: boolean;
  setBarcodeMode: Dispatch<SetStateAction<boolean>>;
  handleBarcodeToggle: () => void;
  handleCameraDetected: (rawCode: string) => Promise<void>;
} {
  // Barcode scanner mode — when active, the next Enter-terminated
  // keypress sequence is captured as barcode input.
  const [barcodeMode, setBarcodeMode] = useState<boolean>(false);
  const barcodeBufferRef = useRef<string>("");

  // Latest deps for the 50 ms timeout callbacks only (avoids stale
  // closures without re-subscribing the listener).
  const depsRef = useRef(deps);
  useEffect(() => {
    depsRef.current = deps;
  });

  const handleCameraDetected = async (rawCode: string) => {
    deps.onCameraClose();
    deps.showToast("Barcode detected!");

    const result = parseBarcodeInput(rawCode);
    const vals = result.values;

    // Fields the barcode doesn't set fall back to the current scan params.
    const params = deps.getScanParams();
    const nextDir = vals.dir !== undefined ? vals.dir : params.directory;
    const nextExt = vals.ext !== undefined ? vals.ext : params.extension;
    const nextFilter = vals.filter !== undefined ? vals.filter : params.filter_text;
    const nextRecursive = vals.recursive !== undefined ? vals.recursive : params.recursive;

    deps.onApplyValues(vals);

    if (nextDir) {
      const outcome = await deps.scanWith(
        {
          directory: nextDir,
          extension: nextExt,
          filter_text: nextFilter,
          recursive: nextRecursive,
        },
        { errorPrefix: "Scan error" },
      );
      if (outcome.ok && outcome.firstPage.count === 1 && outcome.firstPage.items.length === 1) {
        deps.onSingleMatch(outcome.firstPage.items[0]);
      }
    }
  };

  const handleBarcodeToggle = () => {
    setBarcodeMode((prev) => {
      const next = !prev;
      if (next) {
        barcodeBufferRef.current = "";
        deps.showToast("Barcode mode ON — scan a barcode now.");
      } else {
        barcodeBufferRef.current = "";
        deps.showToast("Barcode mode OFF.");
      }
      return next;
    });
  };

  const applyBarcodeValues = (values: Partial<BarcodeParsedInput>) => {
    deps.onApplyValues(values);

    // If scan=1 or any value was applied, trigger a rescan
    if (barcodeShouldScan(values)) {
      // Disable barcode mode after applying
      setBarcodeMode(false);
      barcodeBufferRef.current = "";
      // Use a short timeout so the state updates above commit before the
      // scan starts; depsRef.current guarantees the scan reads the NEW
      // values, not the ones captured by this render (issue #34).
      setTimeout(() => {
        void depsRef.current.scanWith(depsRef.current.getScanParams(), {
          errorPrefix: "Scan failed",
        });
      }, 50);
    }
  };

  // Barcode scanner input — global keypress listener when barcodeMode is active.
  // USB/wedge scanners emit keystrokes + Enter; we accumulate until Enter.
  useEffect(() => {
    if (!barcodeMode) return;

    const d = deps;
    const handleKeydown = (e: KeyboardEvent) => {
      // Keystrokes typed into an editable element belong to that element —
      // never accumulate them into the wedge buffer or hijack its Enter
      // (issue #58). A wedge scanner "typing" while an input is focused
      // lands in the input, which is the correct destination anyway.
      const target = e.target;
      const isEditable =
        target instanceof HTMLElement &&
        (target.isContentEditable ||
          target instanceof HTMLInputElement ||
          target instanceof HTMLTextAreaElement ||
          target instanceof HTMLSelectElement);
      if (isEditable) return;

      if (e.key === "Enter") {
        const raw = barcodeBufferRef.current;
        if (!raw) {
          barcodeBufferRef.current = "";
          return;
        }

        e.preventDefault();
        // This Enter is the scanner's terminator — the wedge path consumed
        // it, so it must not ALSO reach the global-shortcuts window listener
        // (its Enter branch would execute the selected file mid-scan,
        // issue #187).
        e.stopPropagation();
        barcodeBufferRef.current = "";

        const result = parseBarcodeInput(raw);

        if (result.isPlainFilter) {
          d.showToast(`Barcode filter: ${result.values.filter}`);
          d.setFilterText(result.values.filter || "");
          setBarcodeMode(false);
          // depsRef: scan with the just-set filter, not this render's
          // stale closure (issue #34).
          setTimeout(() => {
            void depsRef.current.scanWith(depsRef.current.getScanParams(), {
              errorPrefix: "Scan failed",
            });
          }, 50);
        } else {
          // Parsed key=value pairs — apply all and auto-scan
          const vals = result.values;
          const summary = Object.entries(vals)
            .map(([k, v]) => `${k}=${v}`)
            .join(", ");
          d.showToast(`Barcode applied: ${summary}`);
          applyBarcodeValues(vals);
        }
      } else if (e.key === "Escape") {
        // Allow user to cancel barcode mode
        setBarcodeMode(false);
        barcodeBufferRef.current = "";
        d.showToast("Barcode mode cancelled.");
      } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        // Accumulate printable characters. Isolate the wedge stream from
        // the global shortcuts: a scanner (or blind-typed) payload
        // containing "p" must not open Properties, nor "?" the shortcuts
        // modal (issue #187).
        e.stopPropagation();
        barcodeBufferRef.current += e.key;
      }
    };

    document.addEventListener("keydown", handleKeydown, true);
    return () => document.removeEventListener("keydown", handleKeydown, true);
  }, [barcodeMode]);

  return { barcodeMode, setBarcodeMode, handleBarcodeToggle, handleCameraDetected };
}
