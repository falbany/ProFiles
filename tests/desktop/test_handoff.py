"""Handoff decision logic: identify the busy port owner, forward or fall back.

Covers the issue #4 acceptance matrix: ProFiles owner (handoff applies
the config), foreign owner (rejected), manifest-less owner (rejected),
and handoff HTTP failure (falls back). The two-instance test simulates
the full double-click sequence over real loopback HTTP.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

from profiles.core.config.models import AppConfig
from profiles.desktop.handoff import (
    forward_config_to_running_instance,
    probe_instance_identity,
)
from profiles.desktop.instance import (
    InstanceManifest,
    manifest_path,
    read_manifest,
    write_manifest,
)
from profiles.desktop.lifecycle import BackgroundServer

VALID_CONFIG_BODY = "defaults:\n  title: Forwarded\n"


@pytest.fixture
def temp_tempdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate the manifest temp dir so tests never touch the real one."""
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    return tmp_path


@pytest.fixture
def running_server(temp_tempdir: Path):
    """A real background server with its manifest published (instance A)."""
    server = BackgroundServer(config=AppConfig(title="Instance A"), port=0)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def forwarded_config(tmp_path: Path) -> Path:
    """The .profiles file the 'second launch' would forward."""
    config_file = tmp_path / ".profiles"
    config_file.write_text(VALID_CONFIG_BODY, encoding="utf-8")
    return config_file


class TestForwardToRunningInstance:
    """The decision matrix of forward_config_to_running_instance."""

    def test_profiles_owner_gets_the_config(
        self, running_server: BackgroundServer, forwarded_config: Path
    ) -> None:
        result = forward_config_to_running_instance(
            running_server.port, forwarded_config, timeout=5.0
        )

        assert result.status == "handed_off"
        # The running instance applied the forwarded config...
        assert running_server.state.config_path == forwarded_config.resolve()
        assert running_server.state.config.title == "Forwarded"
        # ...and buffered a UI notification about the handoff.
        events = running_server.state.external_events_after(0)
        assert len(events) == 1
        assert events[0]["config_applied"] is True
        assert ".profiles" in events[0]["message"]

    def test_foreign_owner_is_rejected(self, temp_tempdir: Path, forwarded_config: Path) -> None:
        """A live manifest pointing at a non-ProFiles listener must never
        pass the handshake — the caller falls back to a free port."""
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        foreign_port = blocker.getsockname()[1]
        try:
            # Live PID so the manifest itself is not pruned — the identity
            # handshake is what must reject the foreign listener.
            write_manifest(
                InstanceManifest(
                    pid=os.getpid(),
                    port=foreign_port,
                    host="127.0.0.1",
                    version="0.9.0",
                    token="secret-the-foreign-process-cannot-know",
                )
            )
            result = forward_config_to_running_instance(foreign_port, forwarded_config, timeout=0.5)
            assert result.status == "owner_not_profiles"
            assert result.status != "handed_off"
        finally:
            blocker.close()

    def test_missing_manifest_short_circuits_without_network(
        self, temp_tempdir: Path, forwarded_config: Path, mocker
    ) -> None:  # type: ignore[no-untyped-def]
        probe_spy = mocker.patch(
            "profiles.desktop.handoff.probe_instance_identity", return_value={}
        )

        result = forward_config_to_running_instance(9200, forwarded_config)

        assert result.status == "owner_not_profiles"
        probe_spy.assert_not_called()

    def test_handoff_http_failure_falls_back(
        self, running_server: BackgroundServer, tmp_path: Path
    ) -> None:
        """A confirmed ProFiles owner that rejects the forward (here: a
        config path that does not exist) must yield handoff_failed, not
        an exception — the caller then starts on a free port."""
        missing = tmp_path / "missing.profiles"
        result = forward_config_to_running_instance(running_server.port, missing, timeout=5.0)

        assert result.status == "handoff_failed"
        assert "does not exist" in result.detail

    def test_stale_manifest_pid_is_never_trusted(
        self, temp_tempdir: Path, forwarded_config: Path, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """A manifest whose PID died (crashed instance) is cleaned and the
        port is treated as foreign even if something re-uses it."""
        monkeypatch.setattr("profiles.desktop.instance.pid_alive", lambda pid: False)
        write_manifest(
            InstanceManifest(
                pid=2**30,
                port=9201,
                host="127.0.0.1",
                version="0.9.0",
                token="stale",
            )
        )

        result = forward_config_to_running_instance(9201, forwarded_config)

        assert result.status == "owner_not_profiles"
        assert read_manifest(9201) is None  # cleaned on read


class TestIdentityHandshake:
    """The token gate that keeps impostors out of the handoff."""

    def test_correct_token_confirms_profiles_instance(
        self, running_server: BackgroundServer
    ) -> None:
        manifest = read_manifest(running_server.port)
        assert manifest is not None  # published by start()

        identity = probe_instance_identity(running_server.port, manifest.token, timeout=5.0)

        assert identity is not None
        assert identity["app"] == "ProFiles"
        assert identity["pid"] == os.getpid()

    def test_wrong_token_is_rejected(self, running_server: BackgroundServer) -> None:
        identity = probe_instance_identity(running_server.port, "wrong-token", timeout=5.0)
        assert identity is None

    def test_no_server_on_port_is_rejected(self, temp_tempdir: Path) -> None:
        # Nothing listens here: the probe fails fast and returns None.
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", 0))
        free_port = blocker.getsockname()[1]  # bound but NOT listening
        blocker.close()

        assert probe_instance_identity(free_port, "any", timeout=0.5) is None


class TestManifestLifecycleOnServer:
    """BackgroundServer publishes its manifest when serving, removes on stop."""

    def test_manifest_published_while_running_and_removed_on_stop(self, temp_tempdir: Path) -> None:
        server = BackgroundServer(config=AppConfig(title="Lifecycle"), port=0)
        server.start()
        try:
            manifest = read_manifest(server.port)
            assert manifest is not None
            assert manifest.pid == os.getpid()
            assert manifest.token == server.state.instance_token
        finally:
            server.stop()
        assert manifest_path(server.port).exists() is False

    def test_failed_start_never_publishes_a_manifest(self, temp_tempdir: Path) -> None:
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        taken_port = blocker.getsockname()[1]
        try:
            server = BackgroundServer(config=AppConfig(title="doomed"), port=taken_port)
            with pytest.raises(Exception, match="failed to start"):
                server.start()
            assert manifest_path(taken_port).exists() is False
        finally:
            blocker.close()
