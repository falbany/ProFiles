"""Test static file mounting and SPA fallback."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
from profiles.server.state import ServerState


@pytest.fixture
def mock_static_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>ProFiles Root</body></html>")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "bundle.js").write_text("console.log('bundled');")
    return dist


@pytest.mark.anyio
async def test_static_index_and_fallback(mock_static_dir: Path) -> None:
    state = ServerState(config=AppConfig(title="Test"))
    app = create_app(state, static_dir=mock_static_dir)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Root index
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "ProFiles Root" in resp.text

        # Unknown route fallbacks to index.html
        resp = await client.get("/some/subroute")
        assert resp.status_code == 200
        assert "ProFiles Root" in resp.text

        # Static asset route
        resp = await client.get("/assets/bundle.js")
        assert resp.status_code == 200
        assert "console.log" in resp.text


@pytest.mark.anyio
async def test_static_spa_fallback_prevents_path_traversal(mock_static_dir: Path) -> None:
    secret_file = mock_static_dir.parent / "secret.txt"
    secret_file.write_text("TOP_SECRET_DATA")
    (mock_static_dir / "favicon.svg").write_text("<svg>icon</svg>")

    state = ServerState(config=AppConfig(title="Test"))
    app = create_app(state, static_dir=mock_static_dir)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Legitimate static file inside static_dir is still served
        resp = await client.get("/favicon.svg")
        assert resp.status_code == 200
        assert "<svg>icon</svg>" in resp.text

        # Percent-encoded path traversal attempts must not escape static_dir
        for traversal_path in (
            "/..%2fsecret.txt",
            "/..%2f..%2f..%2fetc%2fpasswd",
            "/sub/..%2f..%2fsecret.txt",
            "/..%5csecret.txt",
        ):
            resp = await client.get(traversal_path)
            assert resp.status_code == 200
            assert "TOP_SECRET_DATA" not in resp.text
            assert "ProFiles Root" in resp.text

