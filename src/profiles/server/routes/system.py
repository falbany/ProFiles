"""System and health check endpoints."""

from __future__ import annotations

import platform

from fastapi import APIRouter

from profiles.core.environment import system

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for process readiness."""
    return {"status": "ok"}


@router.get("/system")
async def system_info() -> dict[str, str]:
    """Return local host and user diagnostic information."""
    info = system.collect_system_info()
    return {
        "hostname": info.hostname,
        "ip": info.ip,
        "username": info.username,
        "os_release": platform.platform(),
    }
