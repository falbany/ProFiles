/**
 * Server-assisted barcode decoding for browsers without the native
 * BarcodeDetector API (desktop WebView2 / WebKitGTK shells).
 *
 * The modal keeps its getUserMedia stream and, at a modest rate, JPEG-encodes
 * a downscaled copy of the viewfinder region and POSTs it to the server
 * decode route (`/api/actions/barcode/decode`). One request is in flight at a
 * time and the loop stops on the first hit — frames never leave the machine
 * in the desktop shell, where the server is localhost.
 */

/** Formats requested from the server — mirrors the modal's BarcodeDetector list. */
export const DECODE_FORMATS = [
  "qr_code",
  "code_128",
  "code_39",
  "ean_13",
  "ean_8",
  "upc_a",
  "upc_e",
  "data_matrix",
] as const;

/** ~4 fps: responsive enough for a hand-held code, light on the server. */
export const SCAN_INTERVAL_MS = 250;
/** Viewfinder frames are downscaled to at most this many pixels per side. */
export const MAX_FRAME_SIZE = 400;
export const JPEG_QUALITY = 0.7;

/**
 * Grab the central square of the current video frame and return it as
 * raw base64 JPEG (no data-URL prefix), or null when the video has no
 * frame yet.
 */
export function captureVideoFrame(
  video: HTMLVideoElement,
  maxSize: number = MAX_FRAME_SIZE,
  quality: number = JPEG_QUALITY,
): string | null {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) return null;

  const side = Math.min(width, height);
  const canvas = document.createElement("canvas");
  canvas.width = Math.min(maxSize, side);
  canvas.height = canvas.width;

  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  ctx.drawImage(
    video,
    (width - side) / 2,
    (height - side) / 2,
    side,
    side,
    0,
    0,
    canvas.width,
    canvas.height,
  );
  const dataUrl = canvas.toDataURL("image/jpeg", quality);
  return dataUrl.slice(dataUrl.indexOf(",") + 1);
}

export interface BarcodePollerDeps {
  /** Capture one frame as base64 JPEG; return null to skip the tick. */
  capture: () => string | null;
  /** Decode one frame; reject to abort scanning with an error. */
  decode: (imageBase64: string) => Promise<{ decoded: string | null }>;
  intervalMs?: number;
}

export interface BarcodePollerCallbacks {
  onDetected: (content: string) => void;
  onError: (message: string) => void;
}

/**
 * Poll the decode endpoint until a barcode is found or decoding fails.
 *
 * Returns a stop function; after stop(), pending decode results are
 * ignored and no further ticks fire.
 */
export function startBarcodePoller(
  deps: BarcodePollerDeps,
  callbacks: BarcodePollerCallbacks,
): () => void {
  const intervalMs = deps.intervalMs ?? SCAN_INTERVAL_MS;
  let stopped = false;
  let inFlight = false;

  const stop = () => {
    stopped = true;
    clearInterval(timer);
  };

  const timer = setInterval(() => {
    if (stopped || inFlight) return;
    const frame = deps.capture();
    if (!frame) return; // video not showing a frame yet

    inFlight = true;
    void deps
      .decode(frame)
      .then((result) => {
        if (stopped) return;
        if (result.decoded) {
          stop();
          callbacks.onDetected(result.decoded);
        }
      })
      .catch((err: unknown) => {
        if (stopped) return;
        stop();
        callbacks.onError(err instanceof Error ? err.message : "Frame decoding failed");
      })
      .finally(() => {
        inFlight = false;
      });
  }, intervalMs);

  return stop;
}
