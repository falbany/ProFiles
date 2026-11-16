import { useEffect, useRef, useState } from "react";
import { executeScan, fetchScanResults } from "../api/client";
import type { ScanResultsResponse, ScanSort, ScannedFileItem } from "../api/types";
import { SCAN_PAGE_SIZE } from "../components/FileListTable";

/** Debounce for the deferred server auto-rescan after the last filter keystroke. */
const AUTO_RESCAN_DEBOUNCE_MS = 800;

export type ScanParams = Parameters<typeof executeScan>[0];

export type ScanOutcome =
  | { ok: true; firstPage: { items: ScannedFileItem[]; count: number } }
  | { ok: false };

export interface ScanControllerDeps {
  showToast: (msg: string, kind?: "info" | "error") => void;
  /** Latest-state scan params; read through the latest-ref at call time. */
  getScanParams: () => ScanParams;
  /** Called after each successful fresh first page (App re-anchors selection). */
  onFreshResults: () => void;
}

export interface ScanController {
  files: ScannedFileItem[];
  totalCount: number;
  hasScanned: boolean;
  loadingMore: boolean;
  scanning: boolean;
  sort: ScanSort | null;
  beginScan(): number;
  claimGeneration(): number;
  isCurrentScan(generation: number): boolean;
  finishScan(generation: number): void;
  runScan(generation: number, params: ScanParams): Promise<boolean>;
  scanWith(params: ScanParams, opts?: { errorPrefix?: string }): Promise<ScanOutcome>;
  scanWithGeneration(gen: number, params: ScanParams, opts?: { errorPrefix?: string }): Promise<ScanOutcome>;
  applySort(next: ScanSort | null): void;
  handleLoadMore(): Promise<void>;
  scheduleDeferredRescan(): void;
}

/**
 * Scan state machine for the file list (extracted verbatim from `App.tsx`,
 * issue #148): the loaded page, the generation protocol that keeps racing
 * scans from corrupting each other, the deferred server auto-rescan, and
 * the sort/paging reloads. UI concerns (toasts, selection anchoring) stay
 * in App via the `deps` callbacks.
 *
 * Generation protocol: every new authoritative scan claims a monotonically
 * increasing generation (`beginScan`/`claimGeneration`) and aborts the
 * previous one's in-flight fetches. State writes and toasts from an older
 * generation are dropped (`isCurrentScan`), so a slow earlier scan can
 * never overwrite a newer result (issue #34).
 */
export function useScanController(deps: ScanControllerDeps): ScanController {
  const [files, setFiles] = useState<ScannedFileItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [hasScanned, setHasScanned] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  /** Column the list is ordered by, or `null` for scan order. */
  const [sort, setSort] = useState<ScanSort | null>(null);
  const [scanning, setScanning] = useState<boolean>(false);
  const scanGenerationRef = useRef(0);
  /** Controller for the current generation's scan fetches; aborted when superseded. */
  const scanAbortRef = useRef<AbortController | null>(null);
  /** Timeout id of the deferred server auto-rescan scheduled on filter typing. */
  const pendingAutoRescanRef = useRef<NodeJS.Timeout | null>(null);

  // Latest deps for deferred callbacks (avoids stale closures above — the
  // `handleScanRef` pattern from App.tsx generalized to the whole deps bag).
  const depsRef = useRef(deps);
  useEffect(() => {
    depsRef.current = deps;
  });

  // Teardown: drop any pending deferred rescan and abort in-flight scan fetches.
  useEffect(
    () => () => {
      if (pendingAutoRescanRef.current) {
        clearTimeout(pendingAutoRescanRef.current);
        pendingAutoRescanRef.current = null;
      }
      scanAbortRef.current?.abort();
    },
    [],
  );

  /**
   * Claim a fresh generation WITHOUT touching UI state: abort + new
   * AbortController + bump only. This is `runInitialLoad`'s supersede
   * protocol — a retry must abort any in-flight scan fetch from the failed
   * load instead of racing it (issue #34); no spinner here, the init panel
   * owns the feedback.
   */
  const claimGeneration = () => {
    // Abort superseded in-flight scan fetches from the previous generation.
    scanAbortRef.current?.abort();
    scanAbortRef.current = new AbortController();
    return ++scanGenerationRef.current;
  };

  const beginScan = () => {
    // Collision rule: any explicit scan (Enter, Scan button, programmatic
    // filter change, barcode apply…) supersedes a pending deferred
    // auto-rescan so the two never double-scan.
    if (pendingAutoRescanRef.current) {
      clearTimeout(pendingAutoRescanRef.current);
      pendingAutoRescanRef.current = null;
    }
    const generation = claimGeneration();
    setScanning(true);
    setLoadingMore(false);
    return generation;
  };

  const isCurrentScan = (generation: number) => generation === scanGenerationRef.current;

  const finishScan = (generation: number) => {
    if (isCurrentScan(generation)) setScanning(false);
  };

  /**
   * Fetch the first page of scan results and replace the list.
   * Paging keeps the JSON payload small (500 rows instead of 25k+).
   *
   * @param sortOrder Sort to request; defaults to the current sort state.
   *   Callers that just changed the sort must pass the new value, because
   *   the state update will not have been applied yet.
   * @returns The fetched response, or `null` when the generation was
   *   superseded mid-flight (the caller must then paint nothing).
   */
  const loadScanResults = async (
    generation: number,
    sortOrder: ScanSort | null = sort,
  ): Promise<ScanResultsResponse | null> => {
    const res = await fetchScanResults({
      offset: 0,
      limit: SCAN_PAGE_SIZE,
      sort_by: sortOrder?.column,
      sort_dir: sortOrder?.direction,
      signal: scanAbortRef.current?.signal,
    });
    if (!isCurrentScan(generation)) return null;
    setFiles(res.items);
    setTotalCount(res.count);
    setHasScanned(true);
    return res;
  };

  /**
   * Execute + load for a pre-claimed generation, WITHOUT error handling or
   * spinner teardown: the init/reload/directory flows call this and own
   * their catch/finally (they surface errors with their own prefix).
   *
   * @returns Whether the scan produced a fresh authoritative first page.
   */
  const runScan = async (generation: number, params: ScanParams): Promise<boolean> => {
    if (!isCurrentScan(generation)) return false;
    const scanRes = await executeScan(params, scanAbortRef.current?.signal);
    // A 200 with a `warning` (e.g. scanned a missing directory) must not
    // masquerade as a normal empty list (issue #130).
    if (scanRes.warning && isCurrentScan(generation)) {
      depsRef.current.showToast(scanRes.warning, "error");
    }
    if (!isCurrentScan(generation) || !(await loadScanResults(generation))) return false;
    // Fresh authoritative results — App re-anchors selection via
    // onFreshResults (selection stays in App, not in the hook).
    depsRef.current.onFreshResults();
    return true;
  };

  /**
   * The `handleScan` flow for an already-claimed generation: execute + page
   * 1 load, with the error toast (site-configurable prefix), the spinner
   * teardown, and an outcome instead of a bare boolean. Superseded
   * generations still execute but stay completely silent.
   */
  const scanWithGeneration = async (
    generation: number,
    params: ScanParams,
    opts?: { errorPrefix?: string },
  ): Promise<ScanOutcome> => {
    // No active directory → silent no-op: no request, no toast, spinner untouched.
    if (!params.directory) return { ok: false };
    try {
      const scanRes = await executeScan(params, scanAbortRef.current?.signal);
      // A 200 with a `warning` (e.g. scanned a missing directory) must not
      // masquerade as a normal empty list (issue #130).
      if (scanRes.warning && isCurrentScan(generation)) {
        depsRef.current.showToast(scanRes.warning, "error");
      }
      const res = await loadScanResults(generation);
      if (!res) return { ok: false };
      // Fresh authoritative results — App re-anchors selection.
      depsRef.current.onFreshResults();
      return { ok: true, firstPage: { items: res.items, count: res.count } };
    } catch (err: unknown) {
      if (isCurrentScan(generation)) {
        const prefix = opts?.errorPrefix ?? "Scan failed";
        depsRef.current.showToast(`${prefix}: ${(err as Error)?.message ?? String(err)}`, "error");
      }
      return { ok: false };
    } finally {
      finishScan(generation);
    }
  };

  /** Run a full scan with the collision rule + empty-directory guard up front. */
  const scanWith = async (
    params: ScanParams,
    opts?: { errorPrefix?: string },
  ): Promise<ScanOutcome> => {
    // Guard BEFORE beginScan: an empty directory must not flash the spinner
    // or clear a pending rescan for nothing.
    if (!params.directory) return { ok: false };
    const generation = beginScan();
    return scanWithGeneration(generation, params, opts);
  };

  /**
   * Sort-change handler (FileListTable `onSortChange`). A sort is a new
   * authoritative scan: it re-anchors selection (onFreshResults), aborts
   * any in-flight scan fetch, and cancels a pending deferred auto-rescan
   * (via beginScan) so neither can overwrite the sorted result out-of-order
   * (issue #34) — then reloads page 1 from the server cache with the new
   * sort. It never re-runs the scan itself.
   */
  const applySort = (next: ScanSort | null) => {
    setSort(next);
    depsRef.current.onFreshResults();
    const generation = beginScan();
    void loadScanResults(generation, next)
      .catch((err: unknown) => {
        if (isCurrentScan(generation)) {
          depsRef.current.showToast(`Sort failed: ${(err as Error)?.message ?? String(err)}`, "error");
        }
      })
      .finally(() => finishScan(generation));
  };

  /** Fetch the next page and append it to the list. */
  const handleLoadMore = async () => {
    if (loadingMore || files.length >= totalCount) return;
    const generation = scanGenerationRef.current;
    setLoadingMore(true);
    try {
      const res = await fetchScanResults({
        offset: files.length,
        limit: SCAN_PAGE_SIZE,
        sort_by: sort?.column,
        sort_dir: sort?.direction,
      });
      if (!isCurrentScan(generation)) return;
      // Guard against duplicated rows if the cache changed mid-request.
      const existing = new Set(files.map((f) => f.path || f.filename));
      setFiles((prev) => [...prev, ...res.items.filter((f) => !existing.has(f.path || f.filename))]);
      setTotalCount(res.count);
    } catch {
      // Paging failure is non-fatal; retry happens on the next scroll attempt.
      depsRef.current.showToast("Couldn't load more results — scroll to try again.", "error");
    } finally {
      if (isCurrentScan(generation)) setLoadingMore(false);
    }
  };

  /**
   * Schedule the deferred server auto-rescan 800ms after the last filter
   * keystroke / recursive toggle / extension change. The timer callback
   * reads the scan params at FIRE time through the latest-ref, so the
   * latest state wins (issue #34 semantics) — an explicit scan inside the
   * window cancels it via beginScan's collision rule.
   */
  const scheduleDeferredRescan = () => {
    if (pendingAutoRescanRef.current) clearTimeout(pendingAutoRescanRef.current);
    pendingAutoRescanRef.current = setTimeout(() => {
      pendingAutoRescanRef.current = null;
      void scanWith(depsRef.current.getScanParams());
    }, AUTO_RESCAN_DEBOUNCE_MS);
  };

  return {
    files,
    totalCount,
    hasScanned,
    loadingMore,
    scanning,
    sort,
    beginScan,
    claimGeneration,
    isCurrentScan,
    finishScan,
    runScan,
    scanWith,
    scanWithGeneration,
    applySort,
    handleLoadMore,
    scheduleDeferredRescan,
  };
}
