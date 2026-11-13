"""Static web asset mounting and SPA fallback routing."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_static_app(app: FastAPI, static_dir: Path | None = None) -> None:
    """Mount static assets built by Vite into the FastAPI app."""
    if static_dir is None:
        # Default to src/profiles/web/dist relative to package
        static_dir = Path(__file__).resolve().parent.parent / "web" / "dist"

    if not static_dir.exists():
        return

    resolved_static_dir = static_dir.resolve()

    # Mount assets directory
    assets_dir = resolved_static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Serve index.html and SPA fallback for client-side routing
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path:
            try:
                requested = (resolved_static_dir / full_path).resolve()
                is_contained_file = (
                    requested.is_relative_to(resolved_static_dir) and requested.is_file()
                )
            except (OSError, ValueError):
                is_contained_file = False
            if is_contained_file:
                return FileResponse(requested)
        index_file = resolved_static_dir / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        return {"detail": "Frontend assets not found"}
