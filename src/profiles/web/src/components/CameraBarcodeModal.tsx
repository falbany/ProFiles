import { useEffect, useRef, useState } from "react";
import { Camera, X, AlertCircle } from "lucide-react";

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

export function CameraBarcodeModal({ isOpen, onClose, onDetected }: CameraBarcodeModalProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSupported, setIsSupported] = useState<boolean>(true);

  // Stop video stream and cleanup
  const stopStream = () => {
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

      // Check for secure context first (browsers block mediaDevices on insecure origins)
      if (typeof window !== "undefined" && !window.isSecureContext && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
        setIsSupported(false);
        setError("Camera access requires HTTPS or localhost. If connecting across a local network IP (e.g. 192.168.x.x), modern browsers disable camera access for insecure HTTP.");
        return;
      }

      const getMedia =
        navigator.mediaDevices?.getUserMedia?.bind(navigator.mediaDevices) ||
        (navigator as any).getUserMedia?.bind(navigator) ||
        (navigator as any).webkitGetUserMedia?.bind(navigator) ||
        (navigator as any).mozGetUserMedia?.bind(navigator);

      if (!getMedia) {
        setIsSupported(false);
        setError(
          !window.isSecureContext
            ? "Camera access is blocked because the page is not served over a secure origin (HTTPS or localhost/127.0.0.1)."
            : "Camera access is not supported by your browser or environment."
        );
        return;
      }

      try {
        const stream: MediaStream = await getMedia({
          video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
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

        // Start scanning frames
        scanFrames();
      } catch (err: any) {
        if (!active) return;
        console.error("Camera access error:", err);
        setError(
          err.name === "NotAllowedError" || err.name === "PermissionDeniedError"
            ? "Camera permission denied. Please allow camera access in your browser settings."
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

  const scanFrames = () => {
    if (!("BarcodeDetector" in window)) {
      setIsSupported(false);
      return;
    }

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
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg rounded-2xl border border-frame-line glass-panel p-6 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between border-b border-line pb-3">
          <div className="flex items-center gap-2 font-semibold text-ink">
            <Camera className="h-5 w-5 text-indigo-400" />
            <span>Scan with Camera</span>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-ink-muted hover:bg-elevated hover:text-ink transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="rounded-full bg-red-500/10 p-3 text-red-400 mb-3">
              <AlertCircle className="h-6 w-6" />
            </div>
            <p className="text-xs text-red-400 max-w-xs">{error}</p>
            <button
              onClick={onClose}
              className="mt-6 rounded-md bg-elevated px-4 py-2 text-xs font-medium text-ink hover:bg-surface border border-line"
            >
              Close
            </button>
          </div>
        ) : !isSupported ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="rounded-full bg-amber-500/10 p-3 text-amber-400 mb-3">
              <AlertCircle className="h-6 w-6" />
            </div>
            <h4 className="text-sm font-medium text-ink">Barcode Detector API Unavailable</h4>
            <p className="mt-1 text-xs text-ink-muted max-w-sm">
              Your browser does not natively support the Barcode Detection API. Consider using Chrome, Edge, Safari 17+, or Chrome for Android.
            </p>
            <button
              onClick={onClose}
              className="mt-6 rounded-md bg-elevated px-4 py-2 text-xs font-medium text-ink hover:bg-surface border border-line"
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
              Hold a QR code or barcode steady in front of your camera to auto-scan.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
