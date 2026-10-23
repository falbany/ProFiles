"""The web backend must run with tkinter unavailable (Briefcase embeddable Python).

Related spec: docs/superpowers/specs/2026-10-23-native-installer-design.md §5.2.
"""

from __future__ import annotations

import importlib
import logging
import sys

import pytest

import profiles.app as app_module


class _StubConfig:
    """Minimal config surface used by ProFileApp.run()."""

    scan_metrics = False
    verbose = "INFO"


@pytest.fixture(autouse=True)
def _restore_app_module():
    """Reload profiles.app normally after each test so other suites are unaffected."""
    yield
    importlib.reload(app_module)


def _reload_with_tkinter_blocked(monkeypatch: pytest.MonkeyPatch) -> object:
    """Put a None sentinel for tkinter, then reload profiles.app.

    ``sys.modules["tkinter"] = None`` makes ``import tkinter`` raise ImportError,
    simulating the Briefcase Windows embeddable distribution.
    """
    monkeypatch.setitem(sys.modules, "tkinter", None)
    monkeypatch.setitem(sys.modules, "profiles.gui.main_window", None)
    return importlib.reload(app_module)


def _stub_app_collaborators(monkeypatch: pytest.MonkeyPatch, app: object) -> None:
    """Replace logging and config loading so run() reaches the backend branch."""
    monkeypatch.setattr(
        type(app), "_setup_logging", lambda self, level=logging.INFO: logging.getLogger("test")
    )
    monkeypatch.setattr(type(app), "_load_configuration", lambda self, logger: _StubConfig())


def test_web_backend_runs_without_tkinter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Import + web run path succeed while tkinter is blocked."""
    mod = _reload_with_tkinter_blocked(monkeypatch)
    called: list[str] = []
    monkeypatch.setattr(mod.ProFileApp, "_run_web_gui", lambda self, **kw: called.append("web"))

    app = mod.ProFileApp(gui_backend="web")
    _stub_app_collaborators(monkeypatch, app)
    app.run()  # must not raise ImportError

    assert called == ["web"]


def test_headless_runs_without_tkinter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Headless mode needs no tkinter either."""
    mod = _reload_with_tkinter_blocked(monkeypatch)
    app = mod.ProFileApp(gui_backend="web", headless=True)
    _stub_app_collaborators(monkeypatch, app)
    monkeypatch.setattr(mod.ProFileApp, "run_headless", lambda self, file_path=None: 0)

    with pytest.raises(SystemExit) as excinfo:
        app.run()

    assert excinfo.value.code == 0


def test_tkinter_banner_printed_when_requested(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With tkinter available, --tkinter routes through main() and prints the banner before GUI launch."""
    calls: list[str] = []
    monkeypatch.setattr(sys, "argv", ["profiles", "--tkinter"])
    monkeypatch.setattr(app_module.ProFileApp, "_run_gui", lambda self: calls.append("tk"))

    app = app_module.ProFileApp(gui_backend="tk")
    _stub_app_collaborators(monkeypatch, app)
    app_module.main()  # banner comes from main(), before ProFileApp is used

    assert calls == ["tk"]
    out = capsys.readouterr().out
    assert "deprecated" in out.lower()
    assert "will be removed" in out.lower()


def test_tkinter_clean_error_when_unavailable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without tkinter, --tkinter prints banner + actionable error and exits 1 (no traceback).

    main() is exercised so stdout contains the deprecation banner exactly as a
    real ``profiles --tkinter`` invocation would.
    """
    mod = _reload_with_tkinter_blocked(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["profiles", "--tkinter"])

    app = mod.ProFileApp(gui_backend="tk")
    _stub_app_collaborators(monkeypatch, app)

    with pytest.raises(SystemExit) as excinfo:
        mod.main()

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "deprecated" in captured.out.lower()
    assert "full Python installation" in captured.err
    assert "Traceback" not in captured.err


def test_theme_fallback_without_sv_ttk(monkeypatch: pytest.MonkeyPatch) -> None:
    """apply_theme survives sv_ttk absence (clam fallback path in gui/theme.py)."""
    pytest.importorskip("tkinter")
    import tkinter as tk

    from profiles.gui import theme as theme_module

    monkeypatch.setitem(sys.modules, "sv_ttk", None)  # import sv_ttk -> ImportError
    root = tk.Tk()
    root.withdraw()
    try:
        theme_module.apply_theme(root, theme_module.DARK_THEME)
    finally:
        root.destroy()
