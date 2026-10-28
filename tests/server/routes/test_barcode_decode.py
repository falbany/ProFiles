"""Tests for the server-side barcode decode endpoint (POST /barcode/decode).

The endpoint is the fallback path for webviews without the native
BarcodeDetector API (desktop WebView2 / WebKitGTK shells): the client posts
downscaled JPEG frames of its camera viewfinder and the server decodes them
with zxing-cpp.
"""

from __future__ import annotations

import base64
import io
import sys
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
from profiles.server.state import ServerState

SCANNER_PAYLOAD = "dir=/tmp/bench;filter=test;scan=1"


@pytest.fixture
def test_state() -> ServerState:
    return ServerState(config=AppConfig(title="Test Bench"))


def _qr_png_bytes(content: str) -> bytes:
    """Render a QR code PNG the same way the /barcode generator does."""
    import qrcode

    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _to_jpeg_frame(image_bytes: bytes, size: int = 400) -> bytes:
    """Simulate the client: center-square crop, downscale, JPEG-encode."""
    img = Image.open(io.BytesIO(image_bytes))
    side = min(img.size)
    img = img.crop(
        (
            (img.width - side) // 2,
            (img.height - side) // 2,
            (img.width + side) // 2,
            (img.height + side) // 2,
        )
    ).resize((size, size))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


@pytest.mark.anyio
async def test_decodes_qr_camera_frame(test_state: ServerState) -> None:
    """Given a JPEG camera frame of a QR code, the endpoint returns its text."""
    app = create_app(test_state)
    frame = _to_jpeg_frame(_qr_png_bytes(SCANNER_PAYLOAD))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/actions/barcode/decode",
            json={"image_base64": _b64(frame), "formats": ["qr_code", "code_128"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decoded"] == SCANNER_PAYLOAD
    assert payload["format"] == "QR Code"


@pytest.mark.anyio
async def test_accepts_data_url_prefix(test_state: ServerState) -> None:
    """A data-URL-prefixed payload is tolerated (clients may send either form)."""
    app = create_app(test_state)
    frame = _to_jpeg_frame(_qr_png_bytes(SCANNER_PAYLOAD))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/actions/barcode/decode",
            json={"image_base64": f"data:image/jpeg;base64,{_b64(frame)}"},
        )

    assert response.status_code == 200
    assert response.json()["decoded"] == SCANNER_PAYLOAD


@pytest.mark.anyio
async def test_returns_null_when_no_barcode_visible(test_state: ServerState) -> None:
    """A frame without any barcode decodes to null, not an error."""
    app = create_app(test_state)
    blank = Image.new("RGB", (400, 400), "white")
    buf = io.BytesIO()
    blank.save(buf, format="JPEG", quality=70)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/actions/barcode/decode", json={"image_base64": _b64(buf.getvalue())}
        )

    assert response.status_code == 200
    assert response.json() == {"decoded": None}


@pytest.mark.anyio
async def test_format_filter_restricts_decoding(test_state: ServerState) -> None:
    """A QR code is not found when the requested formats exclude QR."""
    app = create_app(test_state)
    frame = _to_jpeg_frame(_qr_png_bytes(SCANNER_PAYLOAD))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/actions/barcode/decode",
            json={"image_base64": _b64(frame), "formats": ["code_128", "ean_13"]},
        )

    assert response.status_code == 200
    assert response.json() == {"decoded": None}


@pytest.mark.anyio
async def test_unknown_format_names_are_ignored(test_state: ServerState) -> None:
    """Unknown format names are skipped as long as one valid name remains."""
    app = create_app(test_state)
    frame = _to_jpeg_frame(_qr_png_bytes(SCANNER_PAYLOAD))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/actions/barcode/decode",
            json={"image_base64": _b64(frame), "formats": ["qr_code", "not_a_format"]},
        )

    assert response.status_code == 200
    assert response.json()["decoded"] == SCANNER_PAYLOAD


@pytest.mark.anyio
async def test_rejects_payload_with_only_unknown_formats(test_state: ServerState) -> None:
    """A request naming only unknown formats is a client error, not a broad scan."""
    app = create_app(test_state)
    frame = _to_jpeg_frame(_qr_png_bytes(SCANNER_PAYLOAD))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/actions/barcode/decode",
            json={"image_base64": _b64(frame), "formats": ["not_a_format"]},
        )

    assert response.status_code == 400
    assert "formats" in response.json()["detail"]


@pytest.mark.anyio
async def test_rejects_invalid_base64(test_state: ServerState) -> None:
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/actions/barcode/decode", json={"image_base64": "!!!not-base64!!!"}
        )

    assert response.status_code == 400
    assert "base64" in response.json()["detail"]


@pytest.mark.anyio
async def test_rejects_non_image_payload(test_state: ServerState) -> None:
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/actions/barcode/decode",
            json={"image_base64": _b64(b"definitely not an image")},
        )

    assert response.status_code == 400
    assert "image" in response.json()["detail"]


@pytest.mark.anyio
async def test_rejects_oversized_payload(test_state: ServerState) -> None:
    """The payload cap fails fast on oversized bodies (abuse guard)."""
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/actions/barcode/decode", json={"image_base64": "x" * 2_000_001}
        )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_rejects_missing_payload(test_state: ServerState) -> None:
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/actions/barcode/decode", json={})

    assert response.status_code == 422


@pytest.mark.anyio
async def test_returns_503_when_zxing_cpp_missing(test_state: ServerState) -> None:
    """Without zxing-cpp the endpoint degrades to an explicit 503."""
    app = create_app(test_state)

    with patch.dict(sys.modules, {"zxingcpp": None}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/actions/barcode/decode", json={"image_base64": _b64(b"whatever")}
            )

    assert response.status_code == 503
    assert "zxing-cpp" in response.json()["detail"]
