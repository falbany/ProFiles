import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  captureVideoFrame,
  startBarcodePoller,
} from "./barcodeDecoder";

describe("captureVideoFrame", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubCanvas() {
    const drawImage = vi.fn();
    const toDataURL = vi.fn(() => "data:image/jpeg;base64,QUJD");
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn(() => ({ drawImage })),
      toDataURL,
    };
    vi.stubGlobal("document", { createElement: vi.fn(() => canvas) });
    return { canvas, drawImage, toDataURL };
  }

  it("draws the central square crop downscaled to the max size", () => {
    const { canvas, drawImage } = stubCanvas();
    const video = { videoWidth: 1280, videoHeight: 720 } as HTMLVideoElement;

    const frame = captureVideoFrame(video);

    expect(canvas.width).toBe(400);
    expect(canvas.height).toBe(400);
    // 720x720 centre square of the 1280x720 frame, scaled into 400x400
    expect(drawImage).toHaveBeenCalledWith(video, 280, 0, 720, 720, 0, 0, 400, 400);
    expect(frame).toBe("QUJD");
  });

  it("never upscales a small frame beyond its own size", () => {
    const { canvas } = stubCanvas();
    const video = { videoWidth: 320, videoHeight: 240 } as HTMLVideoElement;

    captureVideoFrame(video);

    expect(canvas.width).toBe(240);
    expect(canvas.height).toBe(240);
  });

  it("returns null before the video has a frame", () => {
    stubCanvas();
    const video = { videoWidth: 0, videoHeight: 0 } as HTMLVideoElement;

    expect(captureVideoFrame(video)).toBeNull();
  });

  it("returns null when canvas 2D context is unavailable", () => {
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn(() => null),
    };
    vi.stubGlobal("document", { createElement: vi.fn(() => canvas) });
    const video = { videoWidth: 1280, videoHeight: 720 } as HTMLVideoElement;

    expect(captureVideoFrame(video)).toBeNull();
  });
});

describe("startBarcodePoller", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("decodes captured frames and reports the first hit once", async () => {
    const capture = vi.fn(() => "frame");
    const decode = vi.fn(async () => ({ decoded: "dir=/tmp;scan=1" }));
    const onDetected = vi.fn();
    const onError = vi.fn();

    const stop = startBarcodePoller({ capture, decode, intervalMs: 250 }, { onDetected, onError });
    await vi.advanceTimersByTimeAsync(1000);

    expect(onDetected).toHaveBeenCalledTimes(1);
    expect(onDetected).toHaveBeenCalledWith("dir=/tmp;scan=1");
    expect(onError).not.toHaveBeenCalled();
    // The loop stops on the first hit: only the initial tick decodes.
    expect(decode).toHaveBeenCalledTimes(1);
    expect(capture).toHaveBeenCalledTimes(1);
    stop();
  });

  it("keeps polling while frames decode to null", async () => {
    const capture = vi.fn(() => "frame");
    const decode = vi.fn(async () => ({ decoded: null }));
    const onDetected = vi.fn();

    const stop = startBarcodePoller({ capture, decode, intervalMs: 250 }, { onDetected, onError: vi.fn() });
    await vi.advanceTimersByTimeAsync(1000);

    expect(decode).toHaveBeenCalledTimes(4);
    expect(onDetected).not.toHaveBeenCalled();
    stop();
  });

  it("skips a tick while the previous request is still in flight", async () => {
    const capture = vi.fn(() => "frame");
    let resolveDecode: (value: { decoded: string | null }) => void = () => {};
    const decode = vi.fn(
      () => new Promise<{ decoded: string | null }>((resolve) => { resolveDecode = resolve; }),
    );

    const stop = startBarcodePoller({ capture, decode, intervalMs: 250 }, { onDetected: vi.fn(), onError: vi.fn() });
    await vi.advanceTimersByTimeAsync(1000);

    expect(decode).toHaveBeenCalledTimes(1);
    expect(capture).toHaveBeenCalledTimes(1);

    resolveDecode({ decoded: null });
    await vi.advanceTimersByTimeAsync(250);
    expect(decode).toHaveBeenCalledTimes(2);
    stop();
  });

  it("skips ticks when the camera has no frame yet", async () => {
    const capture = vi.fn(() => null);
    const decode = vi.fn(async () => ({ decoded: "x" }));

    const stop = startBarcodePoller({ capture, decode, intervalMs: 250 }, { onDetected: vi.fn(), onError: vi.fn() });
    await vi.advanceTimersByTimeAsync(1000);

    expect(decode).not.toHaveBeenCalled();
    stop();
  });

  it("stops and reports an error when decoding fails", async () => {
    const capture = vi.fn(() => "frame");
    const decode = vi.fn(async () => {
      throw new Error("Failed to decode frame (HTTP 503)");
    });
    const onDetected = vi.fn();
    const onError = vi.fn();

    const stop = startBarcodePoller({ capture, decode, intervalMs: 250 }, { onDetected, onError });
    await vi.advanceTimersByTimeAsync(1000);

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith("Failed to decode frame (HTTP 503)");
    expect(onDetected).not.toHaveBeenCalled();
    expect(decode).toHaveBeenCalledTimes(1);
    stop();
  });

  it("ignores in-flight results after stop", async () => {
    const capture = vi.fn(() => "frame");
    let resolveDecode: (value: { decoded: string | null }) => void = () => {};
    const decode = vi.fn(
      () => new Promise<{ decoded: string | null }>((resolve) => { resolveDecode = resolve; }),
    );
    const onDetected = vi.fn();

    const stop = startBarcodePoller({ capture, decode, intervalMs: 250 }, { onDetected, onError: vi.fn() });
    await vi.advanceTimersByTimeAsync(250);
    stop();

    resolveDecode({ decoded: "late hit" });
    expect(onDetected).not.toHaveBeenCalled();
  });

  it("stops ticking after the stop function is called", async () => {
    const capture = vi.fn(() => "frame");
    const decode = vi.fn(async () => ({ decoded: null }));

    const stop = startBarcodePoller({ capture, decode, intervalMs: 250 }, { onDetected: vi.fn(), onError: vi.fn() });
    stop();
    await vi.advanceTimersByTimeAsync(1000);

    expect(capture).not.toHaveBeenCalled();
    expect(decode).not.toHaveBeenCalled();
  });
});
