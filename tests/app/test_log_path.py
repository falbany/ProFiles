"""Log path defaults must be CWD-independent.

Briefcase bundles launch the app with CWD=/ (read-only on macOS), so a
CWD-relative default crashes with ``OSError: [Errno 30]`` at first log
write. The default must live under the user folder: ``~/.profiles/``.

Related: 2026-10-23-native-installer-design.md §7.2 (bundle boots).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import profiles.app as app_module


def test_default_log_path_is_under_home_profiles(tmp_path, monkeypatch) -> None:
    """Default log path resolves to ~/.profiles/profiles.log, not CWD."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fakehome")

    app = app_module.ProFileApp()

    assert app._log_path == tmp_path / "fakehome" / ".profiles" / "profiles.log"
    assert app._log_path.is_absolute()


def test_setup_logging_writes_log_under_home(tmp_path, monkeypatch) -> None:
    """_setup_logging creates and writes the log under ~/.profiles, never CWD."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fakehome")

    # configure_logger mutates the global "profiles" singleton (level, handlers)
    # and install_crash_hook swaps sys.excepthook — restore both afterwards so
    # later tests see pristine logging state.
    profile_logger = logging.getLogger("profiles")
    pre_level = profile_logger.level
    pre_propagate = profile_logger.propagate
    pre_excepthook = sys.excepthook

    app = app_module.ProFileApp()
    logger = app._setup_logging()
    try:
        assert (tmp_path / "fakehome" / ".profiles" / "profiles.log").exists()
        assert not (tmp_path / "profiles.log").exists()  # nothing in CWD
    finally:
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
        profile_logger.setLevel(pre_level)
        profile_logger.propagate = pre_propagate
        sys.excepthook = pre_excepthook


def test_explicit_log_path_override_still_works(tmp_path, monkeypatch) -> None:
    """Passing log_path explicitly keeps overriding the default."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fakehome")

    custom = tmp_path / "custom.log"
    app = app_module.ProFileApp(log_path=custom)

    assert app._log_path == custom
