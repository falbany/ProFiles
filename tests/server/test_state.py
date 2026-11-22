"""Tests for ServerState: external-event buffer and toast telemetry (issue #194)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from profiles.core.config.models import AppConfig
from profiles.server.state import ServerState


@pytest.fixture(autouse=True)
def _reset_profiles_logger() -> None:
    """The ``profiles`` logger is global — start and leave it handler-free."""
    logger = logging.getLogger("profiles")
    logger.handlers.clear()
    yield
    logger.handlers.clear()


@pytest.fixture
def state(tmp_path: Path) -> ServerState:
    return ServerState(config=AppConfig(title="Test Bench", search_dir=str(tmp_path)))


class TestExternalEventBuffer:
    def test_ids_are_monotonic_and_payload_complete(self, state: ServerState) -> None:
        first = state.record_external_event("config_handoff", "first", config_applied=True)
        second = state.record_external_event("config_handoff_failed", "second")

        assert first == 1
        assert second == 2
        assert state.external_events_after(0) == [
            {
                "id": 1,
                "kind": "config_handoff",
                "message": "first",
                "config_applied": True,
            },
            {
                "id": 2,
                "kind": "config_handoff_failed",
                "message": "second",
                "config_applied": False,
            },
        ]

    def test_external_events_after_filters_by_id(self, state: ServerState) -> None:
        state.record_external_event("info", "first")
        state.record_external_event("info", "second")

        remaining = state.external_events_after(1)

        assert [event["message"] for event in remaining] == ["second"]

    def test_buffer_is_capped(self, state: ServerState) -> None:
        for i in range(60):  # over the 50-event cap
            state.record_external_event("info", f"event {i}")

        events = state.external_events_after(0)

        assert len(events) == 50
        assert events[0]["message"] == "event 10"
        assert events[-1]["message"] == "event 59"


class TestExternalEventTelemetry:
    """Every external event mirrors a TOAST record at DEBUG (issue #194)."""

    def test_emits_toast_with_applied_true(
        self, caplog: pytest.LogCaptureFixture, state: ServerState
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="profiles"):
            state.record_external_event(
                "config_handoff", "Configuration 'X' applied", config_applied=True
            )

        assert (
            "TOAST source=server kind=config_handoff applied=true "
            "msg=\"Configuration 'X' applied\"" in caplog.text
        )

    def test_applied_defaults_to_false(
        self, caplog: pytest.LogCaptureFixture, state: ServerState
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="profiles"):
            state.record_external_event("config_handoff_failed", "Could not apply 'X'")

        assert "TOAST source=server kind=config_handoff_failed applied=false" in caplog.text

    def test_default_log_level_stays_quiet(
        self, caplog: pytest.LogCaptureFixture, state: ServerState
    ) -> None:
        """DEBUG by design: the default (INFO) log must not gain toast noise."""
        with caplog.at_level(logging.INFO, logger="profiles"):
            state.record_external_event(
                "config_handoff", "Configuration 'X' applied", config_applied=True
            )

        assert "TOAST" not in caplog.text
