import { useEffect, useRef, useState } from "react";
import { Camera, X, AlertCircle } from "lucide-react";

import { decodeBarcodeImage } from "../api/client";
import {
  DECODE_FORMATS,
  captureVideoFrame,
  startBarcodePoller,
} from "../utils/barcodeDecoder";

interface CameraBarcodeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDetected: (content: string) => void;
}

declare global {
  interface Window {
    BarcodeDetector?: any;
  }
}

/** How long to wait for getUserMedia before showing an error. */
const CAMERA_START_TIMEOUT_MS = 8000;

export function CameraBarcodeModal({ isOpen, onClose, onDetected }: CameraBarcodeModalProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const pollerStopRef = useRef<(() => void) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isServerFallback, setIsServerFallback] = useState<boolean>(false);

  // Stop video stream and cleanup
  const stopStream = () => {
    if (pollerStopRef.current) {
      pollerStopRef.current();
      pollerStopRef.current = null;
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  useEffect(() => {
    if (!isOpen) {
      stopStream();
      setError(null);
      return;
    }

    let active = true;

    async function startCamera() {
      setError(null);
      setIsServerFallback(false);

      // Check for secure context first (browsers block mediaDevices on insecure origins)
      if (typeof window !== "undefined" && !window.isSecureContext && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
        setError("Camera access requires HTTPS or localhost. If connecting across a local network IP (e.g. 192.168.x.x), modern browsers disable camera access for insecure HTTP.");
        return;
      }

      const getMedia =
        navigator.mediaDevices?.getUserMedia?.bind(navigator.mediaDevices) ||
        (navigator as any).getUserMedia?.bind(navigator) ||
        (navigator as any).webkitGetUserMedia?.bind(navigator) ||
        (navigator as any).mozGetUserMedia?.bind(navigator);

      if (!getMedia) {
        setError(
          !window.isSecureContext
            ? "Camera access is blocked because the page is not served over a secure origin (HTTPS or localhost/127.0.0.1)."
            : "Camera access is not supported by your browser or environment."
        );
        return;
      }

      try {
        // Some embedded webviews park getUserMedia forever when camera capture
        // is unavailable (e.g. macOS bare-Python runs without an app bundle);
        // time out so the modal surfaces an error instead of a black frame.
        let timeoutId: number | undefined;
        const stream: MediaStream = await Promise.race([
          getMedia({
            video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
          }),
          new Promise<never>((_, reject) => {
            timeoutId = window.setTimeout(
              () => reject(new DOMException("Camera did not start in time", "TimeoutError")),
              CAMERA_START_TIMEOUT_MS,
            );
          }),
        ]).finally(() => {
          if (timeoutId !== undefined) window.clearTimeout(timeoutId);
        });

        if (!active) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }

        // Start scanning frames: natively when BarcodeDetector exists,
        // otherwise via the server decode route.
        if ("BarcodeDetector" in window) {
          scanFrames();
        } else {
          startServerScanning();
        }
      } catch (err: any) {
        if (!active) return;
        console.error("Camera access error:", err);
        setError(
          err.name === "NotAllowedError" || err.name === "PermissionDeniedError"
            ? "Camera permission denied. Please allow camera access in your browser settings."
            : err.name === "TimeoutError"
              ? "The camera did not start in time. On macOS, camera capture needs the packaged desktop app — a bare Python process cannot access the camera. Alternatively, open ProFiles in Chrome, Edge or Safari."
              : `Could not access camera: ${err.message || "Unknown error"}`
        );
      }
    }

    void startCamera();

    return () => {
      active = false;
      stopStream();
    };
  }, [isOpen]);

  const startServerScanning = () => {
    setIsServerFallback(true);
    pollerStopRef.current = startBarcodePoller(
      {
        capture: () => (videoRef.current ? captureVideoFrame(videoRef.current) : null),
        decode: (imageBase64) =>
          decodeBarcodeImage({ imageBase64, formats: [...DECODE_FORMATS] }),
      },
      {
        onDetected: (content) => {
          stopStream();
          onDetected(content);
        },
        onError: (message) => {
          stopStream();
          setError(message);
        },
      },
    );
  };

  const scanFrames = () => {
    const formats = [
      "qr_code",
      "code_128",
      "code_39",
      "ean_13",
      "ean_8",
      "upc_a",
      "upc_e",
      "data_matrix",
    ];

    let detector: any;
    try {
      detector = new window.BarcodeDetector({ formats });
    } catch (err) {
      console.warn("BarcodeDetector formats unsupported:", err);
      detector = new window.BarcodeDetector();
    }

    const detect = async () => {
      if (!videoRef.current || videoRef.current.readyState < 2) {
        animationFrameRef.current = requestAnimationFrame(detect);
        return;
      }

      try {
        const barcodes = await detector.detect(videoRef.current);
        if (barcodes && barcodes.length > 0) {
          const rawValue = barcodes[0].rawValue;
          if (rawValue) {
            stopStream();
            onDetected(rawValue);
            return;
          }
        }
      } catch (err) {
        console.debug("Frame detection error:", err);
      }

      animationFrameRef.current = requestAnimationFrame(detect);
    };

    animationFrameRef.current = requestAnimationFrame(detect);
  };

  if (!isOpen) return null;

  return (
    <div
      className="animate-overlay-in fixed inset-0 z-[var(--z-modal)] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Camera barcode scanner"
        className="relative w-full max-w-lg rounded-2xl border border-frame-line glass-panel p-6 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between border-b border-line pb-3">
          <div className="flex items-center gap-2 font-semibold text-ink">
            <Camera className="h-5 w-5 text-chip-indigo-text" />
            <span>Scan with Camera</span>
          </div>
          <button
            onClick={onClose}
            className="focus-ring rounded-lg p-1 text-ink-muted hover:bg-elevated hover:text-ink transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="rounded-full bg-status-danger-bg p-3 text-status-danger-text mb-3">
              <AlertCircle className="h-6 w-6" />
            </div>
            <p className="text-xs text-status-danger-text max-w-xs">{error}</p>
            <button
              onClick={onClose}
              className="btn btn-secondary mt-6 px-4 py-2"
            >
              Close
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center">
            <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-black border border-line flex items-center justify-center">
              <video
                ref={videoRef}
                playsInline
                muted
                className="h-full w-full object-cover"
              />

              {/* Viewfinder Target Overlay */}
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="relative h-48 w-48 rounded-lg border-2 border-dashed border-indigo-400/80 bg-indigo-500/5 shadow-[0_0_0_9999px_rgba(0,0,0,0.45)]">
                  <div className="absolute top-0 left-0 h-4 w-4 border-t-2 border-l-2 border-indigo-400" />
                  <div className="absolute top-0 right-0 h-4 w-4 border-t-2 border-r-2 border-indigo-400" />
                  <div className="absolute bottom-0 left-0 h-4 w-4 border-b-2 border-l-2 border-indigo-400" />
                  <div className="absolute bottom-0 right-0 h-4 w-4 border-b-2 border-r-2 border-indigo-400" />
                </div>
              </div>
            </div>

            <p className="mt-4 text-center text-xs text-ink-muted">
              {isServerFallback
                ? "Hold a QR code or barcode steady in front of your camera — frames are decoded by the local ProFiles server (no native Barcode Detector in this browser)."
                : "Hold a QR code or barcode steady in front of your camera to auto-scan."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
