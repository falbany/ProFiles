// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BarcodeModal } from "./BarcodeModal";
import { generateBarcode } from "../api/client";

vi.mock("../api/client", () => ({
  generateBarcode: vi.fn(),
  saveImageToDisk: vi.fn(),
}));

const generateSpy = vi.mocked(generateBarcode);

/** Wait out the modal's 250 ms generate debounce. */
const settleDebounce = () => new Promise((resolve) => setTimeout(resolve, 320));

function renderModal(props: Partial<Parameters<typeof BarcodeModal>[0]> = {}) {
  return render(
    <BarcodeModal isOpen onClose={() => {}} {...props} />,
  );
}

/** The key/value inputs exist per pair row — seed one empty pair first. */
async function addEmptyPair(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /add field/i }));
  return screen.getByPlaceholderText("key");
}

beforeEach(() => {
  vi.clearAllMocks();
  generateSpy.mockResolvedValue({ image: "data:image/png;base64,NEW", content: "" });
});

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});

describe("BarcodeModal", () => {
  it("test_edits_debounce_into_single_generate", async () => {
    const user = userEvent.setup();
    renderModal();

    // Typing several characters into a key field schedules one debounced
    // generate per edit burst, not one per keystroke (issue #140).
    const keyInput = await addEmptyPair(user);
    await user.type(keyInput, "abc");
    await waitFor(() => expect(generateSpy).toHaveBeenCalled());
    expect(generateSpy).toHaveBeenCalledTimes(1);
    expect(generateSpy).toHaveBeenCalledWith({ content: "abc=" });

    // The field keeps the newest content — the preview mirrors it.
    expect(keyInput).toHaveValue("abc");
    expect(screen.getByText("abc=")).toBeTruthy();
  });

  it("test_stale_generate_response_is_dropped", async () => {
    const user = userEvent.setup();

    let resolveFirst: (value: { image: string; content: string }) => void = () => {};
    generateSpy
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce({ image: "data:image/png;base64,SECOND", content: "" });

    renderModal();
    const keyInput = await addEmptyPair(user);
    await user.type(keyInput, "a");
    await waitFor(() => expect(generateSpy).toHaveBeenCalledTimes(1));

    // A second edit fires a newer generate that resolves before the first.
    await user.type(screen.getByPlaceholderText("value"), "b");
    await waitFor(() => expect(generateSpy).toHaveBeenCalledTimes(2));
    const img = await screen.findByAltText("QR Code");
    await waitFor(() => expect(img.getAttribute("src")).toBe("data:image/png;base64,SECOND"));

    // The stale first response lands last — it must not win (issue #140).
    resolveFirst({ image: "data:image/png;base64,STALE", content: "" });
    await settleDebounce();
    expect(img.getAttribute("src")).toBe("data:image/png;base64,SECOND");
  });

  it("test_generate_failure_is_surfaced", async () => {
    const user = userEvent.setup();
    generateSpy.mockRejectedValue(new Error("barcode engine exploded"));
    renderModal();

    const keyInput = await addEmptyPair(user);
    await user.type(keyInput, "a");
    // Failure must appear in the modal's alert area, not only the console
    // (issue #140 — No Silent Failures).
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/barcode engine exploded/);
  });

  it("test_empty_content_clears_image_and_error", async () => {
    const user = userEvent.setup();
    renderModal();

    const keyInput = await addEmptyPair(user);
    await user.type(keyInput, "a");
    await screen.findByAltText("QR Code");

    // Removing the field empties the payload: the image and any previous
    // generate error go away, with no further request.
    await user.clear(keyInput);
    await waitFor(() => expect(screen.queryByAltText("QR Code")).toBeNull());
    expect(screen.queryByRole("alert")).toBeNull();
    expect(generateSpy).toHaveBeenCalledTimes(1);
  });
});
