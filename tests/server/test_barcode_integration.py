from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
from profiles.server.state import ServerState


@pytest.fixture
def test_state() -> ServerState:
    return ServerState(config=AppConfig(title="Test Bench"))


@pytest.mark.anyio
async def test_generate_barcode_from_content(test_state: ServerState) -> None:
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/actions/barcode", json={"content": "test;content"})

    assert response.status_code == 200
    data = response.json()
    assert "image" in data
    assert data["image"].startswith("data:image/png;base64,")
    assert data["content"] == "test;content"


@pytest.mark.anyio
async def test_generate_barcode_from_file_path(test_state: ServerState, tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("sample")
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/actions/barcode", json={"file_path": str(target)})

    assert response.status_code == 200
    data = response.json()
    assert "image" in data
    assert "dir=" in data["content"]
    assert "filter=sample.txt" in data["content"]


@pytest.mark.anyio
async def test_generate_barcode_invalid_request(test_state: ServerState) -> None:
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/actions/barcode", json={})

    assert response.status_code == 400
