"""Tests for profiles.gui.theme — Md3Theme, theming constants, apply_theme.

Note: Tests that require a Tk root widget use ``pytest.mark.skipif``
when Tkinter is unavailable (headless CI, missing Tcl/Tk).
"""

from __future__ import annotations

import tkinter as tk

import pytest

from profiles.gui.theme import (
    DARK_THEME,
    FONT_FAMILY,
    FONT_SIZE_LARGE,
    FONT_SIZE_NORMAL,
    FONT_SIZE_SMALL,
    LIGHT_THEME,
    THEME_LABELS,
    THEMES,
    Md3Theme,
    _assert_contrast,
    _contrast_ratio,
    _hex_luminance,
    apply_theme,
    resolve_theme_name,
)

# ── Tkinter availability guard ──────────────────────────────────────────────

_tk_available = True
try:
    _root_test = tk.Tk()
    _root_test.destroy()
except (tk.TclError, RuntimeError):
    _tk_available = False

needs_tk = pytest.mark.skipif(
    not _tk_available,
    reason="Tkinter not available (headless CI or missing Tcl/Tk)",
)


# ── Md3Theme dataclass ─────────────────────────────────────────────────────


class TestMd3Theme:
    """Md3Theme frozen dataclass."""

    def test_is_frozen(self) -> None:
        theme = Md3Theme(
            primary="#000000",
            on_primary="#FFFFFF",
            primary_container="#E0E0E0",
            on_primary_container="#000000",
            secondary="#666666",
            on_secondary="#FFFFFF",
            surface="#FFFFFF",
            surface_container="#F5F5F5",
            surface_dim="#DDDDDD",
            on_surface="#000000",
            on_surface_variant="#444444",
            outline="#888888",
            outline_variant="#AAAAAA",
            background="#FFFFFF",
            on_background="#000000",
            error="#B3261E",
            on_error="#FFFFFF",
            error_container="#F9DEDC",
            status_info="#E8F4FD",
            status_info_fg="#003049",
            status_warning="#FEF9C3",
            status_warning_fg="#713000",
            status_error="#FEF2F2",
            status_error_fg="#991B1B",
            status_success="#DCFCE8",
            status_success_fg="#15803D",
            link="#005fb8",
            link_hover="#004791",
            elevation_0="#ffffff",
            elevation_1="#F5F5F5",
            header_bg="#1F1F1F",
            header_fg="#FFFFFF",
            status_bg="#F0F0F4",
            border="#C4C6D0",
            prod="#1565C0",
            dev="#757575",
            green="#2E7D32",
            green_hover="#1B5E20",
            hover="#E3F2FD",
            selected="#1565C0",
            tooltip_bg="#212121",
            tooltip_fg="#fafafa",
            tooltip_border="#212121",
            focus_ring="#005fb8",
        )
        with pytest.raises(AttributeError):
            theme.primary = "#FF0000"  # type: ignore[misc]

    def test_has_tooltip_and_focus_tokens(self) -> None:
        for field in ("tooltip_bg", "tooltip_fg", "tooltip_border", "focus_ring"):
            assert field in Md3Theme.__dataclass_fields__
            assert isinstance(getattr(LIGHT_THEME, field), str)
            assert isinstance(getattr(DARK_THEME, field), str)

    def test_light_dark_tokens_differ(self) -> None:
        assert LIGHT_THEME.tooltip_bg != DARK_THEME.tooltip_bg
        assert LIGHT_THEME.focus_ring != DARK_THEME.focus_ring

    def test_required_fields_present(self) -> None:
        """Smoke check that a fully populated Md3Theme can be created."""
        theme = LIGHT_THEME
        assert isinstance(theme.primary, str)
        assert theme.primary.startswith("#")
        assert theme.on_primary.startswith("#")


# ── Theme instances ─────────────────────────────────────────────────────────


class TestThemeInstances:
    """LIGHT_THEME and DARK_THEME validity."""

    def _is_valid_hex_color(self, color: str) -> bool:
        return isinstance(color, str) and len(color) == 7 and color.startswith("#")

    def test_light_theme_all_colors_valid_hex(self) -> None:
        for field_name in Md3Theme.__dataclass_fields__:
            value = getattr(LIGHT_THEME, field_name)
            assert self._is_valid_hex_color(value), f"LIGHT_THEME.{field_name} invalid: {value!r}"

    def test_dark_theme_all_colors_valid_hex(self) -> None:
        for field_name in Md3Theme.__dataclass_fields__:
            value = getattr(DARK_THEME, field_name)
            assert self._is_valid_hex_color(value), f"DARK_THEME.{field_name} invalid: {value!r}"

    def test_themes_are_different(self) -> None:
        assert LIGHT_THEME is not DARK_THEME
        assert LIGHT_THEME.surface != DARK_THEME.surface
        assert LIGHT_THEME.on_surface != DARK_THEME.on_surface

    def test_light_surface_lighter_than_dark(self) -> None:
        """Light theme surface should be a light colour (high RGB),
        dark theme surface should be dark (low RGB)."""
        # Parse hex to int for comparison
        light_rgb = int(LIGHT_THEME.surface[1:], 16)
        dark_rgb = int(DARK_THEME.surface[1:], 16)
        assert light_rgb > dark_rgb, "Light theme surface should be lighter than dark theme surface"


# ── THEMES / THEME_LABELS dicts ─────────────────────────────────────────────


class TestThemeDicts:
    """THEMES and THEME_LABELS lookup dictionaries."""

    def test_themes_has_both(self) -> None:
        assert "light" in THEMES
        assert "dark" in THEMES

    def test_themes_values_are_md3_theme(self) -> None:
        for theme in THEMES.values():
            assert isinstance(theme, Md3Theme)

    def test_theme_labels_has_both(self) -> None:
        assert "light" in THEME_LABELS
        assert "dark" in THEME_LABELS

    def test_theme_labels_non_empty(self) -> None:
        for label in THEME_LABELS.values():
            assert len(label) > 0


# ── Font constants ──────────────────────────────────────────────────────────


class TestFontConstants:
    """Font configuration values are sensible."""

    def test_font_family_is_string(self) -> None:
        assert isinstance(FONT_FAMILY, str)
        assert len(FONT_FAMILY) > 0

    def test_font_sizes_positive(self) -> None:
        assert FONT_SIZE_SMALL > 0
        assert FONT_SIZE_NORMAL > 0
        assert FONT_SIZE_LARGE > 0

    def test_font_size_ordering(self) -> None:
        assert FONT_SIZE_SMALL < FONT_SIZE_NORMAL < FONT_SIZE_LARGE


# ── apply_theme (requires Tk root, no mainloop) ─────────────────────────────


@needs_tk
class TestApplyTheme:
    """apply_theme function — verifies it runs without error."""

    @pytest.fixture
    def root(self) -> tk.Tk:
        """Create a temporary Tk root for style configuration."""
        r = tk.Tk()
        yield r
        r.destroy()

    def test_apply_light_theme(self, root: tk.Tk) -> None:
        style = apply_theme(root, LIGHT_THEME)
        assert style is not None
        # Verify ttk styles were configured
        assert style.lookup("FileList.Treeview", "fieldbackground") == LIGHT_THEME.surface

    def test_apply_dark_theme(self, root: tk.Tk) -> None:
        style = apply_theme(root, DARK_THEME)
        assert style is not None
        # Verify ttk styles were configured with dark colours
        assert style.lookup("FileList.Treeview", "fieldbackground") == DARK_THEME.surface

    def test_theme_switch(self, root: tk.Tk) -> None:
        """Apply light then dark — styles should change."""
        apply_theme(root, LIGHT_THEME)
        style = apply_theme(root, DARK_THEME)
        assert style.lookup("FileList.Treeview", "fieldbackground") == DARK_THEME.surface

    def test_reapply_same_theme(self, root: tk.Tk) -> None:
        """Re-applying the same theme should not raise and keep styles intact."""
        apply_theme(root, LIGHT_THEME)
        style = apply_theme(root, LIGHT_THEME)
        assert style.lookup("FileList.Treeview", "fieldbackground") == LIGHT_THEME.surface

    def test_reapply_toggles_back_to_light(self, root: tk.Tk) -> None:
        """Light → dark → light must restore the light surface colour."""
        apply_theme(root, LIGHT_THEME)
        apply_theme(root, DARK_THEME)
        style = apply_theme(root, LIGHT_THEME)
        assert style.lookup("FileList.Treeview", "fieldbackground") == LIGHT_THEME.surface
        assert style.lookup("FileList.Treeview", "fieldbackground") != DARK_THEME.surface

    def test_apply_theme_twice_is_idempotent(self, root: tk.Tk) -> None:
        """Calling apply_theme twice (same theme) must not raise."""
        style = apply_theme(root, LIGHT_THEME)
        style2 = apply_theme(root, LIGHT_THEME)
        assert style is not None
        assert style2 is not None
        assert style.lookup("FileList.Treeview", "fieldbackground") == LIGHT_THEME.surface
        assert style2.lookup("FileList.Treeview", "fieldbackground") == LIGHT_THEME.surface

    def test_apply_theme_with_tk_stub(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """apply_theme is callable twice with a minimal Tk stub (no real root)."""

        class _FakeToplevel:  # noqa: D401 - minimal stand-in
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

        class _FakeStyle:
            def __init__(self) -> None:
                self._configs: dict[str, dict[str, object]] = {}

            def theme_use(self, name: str) -> None:
                self._theme = name

            def configure(self, style: str, **kwargs: object) -> None:
                self._configs.setdefault(style, {}).update(kwargs)

            def lookup(self, style: str, opt: str) -> str:
                return str(self._configs.get(style, {}).get(opt, ""))

            def map(self, style: str, **kwargs: object) -> None:
                self._configs.setdefault(style, {}).update(kwargs)

        class _FakeTk:
            def __init__(self) -> None:
                self.palette: dict[str, str] = {}

            def update(self) -> None:
                pass

        def _tk_set_palette(self: _FakeTk, **kwargs: str) -> None:
            self.palette.update(kwargs)

        _FakeTk.tk_setPalette = _tk_set_palette

        import tkinter.ttk as ttk

        monkeypatch.setattr(ttk, "Style", _FakeStyle)
        monkeypatch.setattr(tk, "Toplevel", _FakeToplevel)
        fake = _FakeTk()
        s1 = apply_theme(fake, LIGHT_THEME)
        s2 = apply_theme(fake, DARK_THEME)
        assert isinstance(s1, _FakeStyle)
        assert isinstance(s2, _FakeStyle)
        assert fake.palette["background"] == DARK_THEME.surface


class TestResolveThemeName:
    """Tests for resolve_theme_name helper."""

    def test_resolve_explicit(self) -> None:
        assert resolve_theme_name("light") == "light"
        assert resolve_theme_name("dark") == "dark"

    def test_resolve_auto_dark(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import darkdetect

        monkeypatch.setattr(darkdetect, "theme", lambda: "Dark")
        assert resolve_theme_name("auto") == "dark"

    def test_resolve_auto_light(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import darkdetect

        monkeypatch.setattr(darkdetect, "theme", lambda: "Light")
        assert resolve_theme_name("auto") == "light"

    def test_resolve_auto_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import darkdetect

        monkeypatch.setattr(darkdetect, "theme", lambda: None)
        assert resolve_theme_name("auto") == "light"


# ── _hex_luminance binding to Md3Theme colours ──────────────────────────────


class TestThemeLuminance:
    """Luminance helper must yield values in [0, 1] for the theme palette.

    These tests exercise the ``_hex_luminance`` module-level helper from
    ``profiles.gui.main_window`` against the canonical ``surface`` and
    ``outline`` colours of both built-in themes. The helper is a pure
    function so importing it does not instantiate Tk.
    """

    def test_light_surface_luminance_in_range(self) -> None:
        from profiles.gui.main_window import _hex_luminance

        value = _hex_luminance(LIGHT_THEME.surface)
        assert 0.0 <= value <= 1.0

    def test_dark_surface_luminance_in_range(self) -> None:
        from profiles.gui.main_window import _hex_luminance

        value = _hex_luminance(DARK_THEME.surface)
        assert 0.0 <= value <= 1.0

    def test_light_outline_luminance_in_range(self) -> None:
        from profiles.gui.main_window import _hex_luminance

        value = _hex_luminance(LIGHT_THEME.outline)
        assert 0.0 <= value <= 1.0

    def test_dark_outline_luminance_in_range(self) -> None:
        from profiles.gui.main_window import _hex_luminance

        value = _hex_luminance(DARK_THEME.outline)
        assert 0.0 <= value <= 1.0

    def test_light_surface_lighter_than_dark_surface(self) -> None:
        """The luminance helper agrees with the qualitative expectation:
        light theme surface > dark theme surface."""
        from profiles.gui.main_window import _hex_luminance

        assert _hex_luminance(LIGHT_THEME.surface) > _hex_luminance(DARK_THEME.surface)


# ── WCAG contrast helpers ───────────────────────────────────────────────────


class TestContrast:
    """Unit tests for ``_hex_luminance``, ``_contrast_ratio``, ``_assert_contrast``."""

    def test_luminance_black_is_zero(self) -> None:
        assert _hex_luminance("#000000") == 0.0

    def test_luminance_white_is_one(self) -> None:
        assert _hex_luminance("#FFFFFF") == pytest.approx(1.0, abs=1e-6)

    def test_luminance_missing_hash_tolerated(self) -> None:
        assert _hex_luminance("FFFFFF") == pytest.approx(1.0, abs=1e-6)
        # Garbage returns the safe neutral 0.5
        assert _hex_luminance("not-a-color") == 0.5
        assert _hex_luminance("#abc") == 0.5  # wrong length

    def test_contrast_ratio_black_on_white_is_21(self) -> None:
        assert _contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=1e-3)

    def test_contrast_ratio_white_on_white_is_1(self) -> None:
        assert _contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0, abs=1e-6)

    def test_assert_contrast_passes_for_known_good_pair(self) -> None:
        # Black on white is 21:1 — well above the AA threshold of 4.5.
        assert _assert_contrast("#000000", "#FFFFFF") is True

    def test_assert_contrast_fails_for_known_bad_pair(self) -> None:
        # Light grey on white has a ratio of about 1.3:1.
        assert _assert_contrast("#CCCCCC", "#FFFFFF") is False


# ── apply_theme WCAG audit logging ───────────────────────────────────────────


@needs_tk
class TestApplyThemeContrastAudit:
    """apply_theme logs a WARNING for each contrast pair below 4.5:1."""

    @pytest.fixture
    def root(self) -> tk.Tk:
        r = tk.Tk()
        yield r
        r.destroy()

    def test_apply_theme_audit_warns_on_bad_contrast(
        self,
        root: tk.Tk,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Build a theme where on_surface is intentionally very close to surface.
        bad_theme = Md3Theme(
            primary="#005fb8",
            on_primary="#FFFFFF",
            primary_container="#D1E4FF",
            on_primary_container="#001D36",
            secondary="#625B71",
            on_secondary="#FFFFFF",
            surface="#FFFFFF",
            surface_container="#F5F5F5",
            surface_dim="#DDDDDD",
            on_surface="#FEFEFE",  # almost white on white → fails AA
            on_surface_variant="#49454F",
            outline="#C4C6D0",
            outline_variant="#E0E0E4",
            background="#FFFFFF",
            on_background="#1c1c1c",
            error="#B3261E",
            on_error="#FFFFFF",
            error_container="#F9DEDC",
            status_info="#FFFFFF",
            status_info_fg="#000000",
            status_warning="#FFFFFF",
            status_warning_fg="#000000",
            status_error="#FFFFFF",
            status_error_fg="#000000",
            status_success="#FFFFFF",
            status_success_fg="#000000",
            link="#000000",
            link_hover="#111111",
            elevation_0="#FFFFFF",
            elevation_1="#F5F5F5",
            header_bg="#1F1F1F",
            header_fg="#FFFFFF",
            status_bg="#FFFFFF",
            border="#E0E0E4",
            prod="#005fb8",
            dev="#757575",
            green="#16A34A",
            green_hover="#15803D",
            hover="#eaeaea",
            selected="#2f60d8",
            tooltip_bg="#212121",
            tooltip_fg="#fafafa",
            tooltip_border="#212121",
            focus_ring="#005fb8",
        )

        caplog.set_level("WARNING", logger="profiles")
        apply_theme(root, bad_theme)

        warnings = [rec for rec in caplog.records if rec.levelname == "WARNING"]
        labels = {str(rec.getMessage()).split(" ratio=")[0] for rec in warnings}
        # on_surface/surface should definitely trigger; audit must not raise.
        assert any("on_surface/surface" in msg for msg in labels)
        # Valid pairs stay silent.
        assert all("on_primary/primary" not in msg for msg in labels)
