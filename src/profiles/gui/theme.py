"""Material Design 3 theme definitions for ProFiles.

Provides light and dark colour themes following Google's Material Design 3
guidelines, with a dedicated ``Md3Theme`` dataclass and helper functions
for applying themes to the Tkinter application.
"""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

# ── Theme colour palette ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Md3Theme:
    """A complete Material Design 3 colour theme.

    All colour values are 7-character hex strings (e.g. ``#1565C0``).
    """

    # Primary / Secondary
    primary: str
    on_primary: str
    primary_container: str
    on_primary_container: str
    secondary: str
    on_secondary: str

    # Surface tones
    surface: str
    surface_container: str
    surface_dim: str

    # On-surface colours
    on_surface: str
    on_surface_variant: str

    # Outline
    outline: str
    outline_variant: str

    # Background
    background: str
    on_background: str

    # Error
    error: str
    on_error: str
    error_container: str

    # Status / message semantic colours (surface-level feedback)
    status_info: str
    status_info_fg: str
    status_warning: str
    status_warning_fg: str
    status_error: str
    status_error_fg: str
    status_success: str
    status_success_fg: str

    # Link styling
    link: str
    link_hover: str

    # Opacity / elevation steps (light: higher number = lighter)
    elevation_0: str
    elevation_1: str

    # Application-specific
    header_bg: str
    header_fg: str
    status_bg: str
    border: str
    prod: str
    dev: str
    green: str
    green_hover: str

    # Interactive states
    hover: str
    selected: str

    # Tooltip & focus
    tooltip_bg: str
    tooltip_fg: str
    tooltip_border: str
    focus_ring: str


# ── Theme instances ─────────────────────────────────────────────────────────

LIGHT_THEME = Md3Theme(
    # Primary
    primary="#005fb8",
    on_primary="#FFFFFF",
    primary_container="#D1E4FF",
    on_primary_container="#001D36",
    # Secondary
    secondary="#625B71",
    on_secondary="#FFFFFF",
    # Surface
    surface="#fafafa",
    surface_container="#f3f3f3",
    surface_dim="#eaeaea",
    # On-surface
    on_surface="#1c1c1c",
    on_surface_variant="#49454F",
    # Outline (≥3:1 on surface per WCAG 1.4.11)
    outline="#79747E",
    outline_variant="#D0D1DA",
    # Background
    background="#fafafa",
    on_background="#1c1c1c",
    # Error
    error="#B3261E",
    on_error="#FFFFFF",
    error_container="#F9DEDC",
    # Semantic status surfaces
    status_info="#FFF7ED",
    status_info_fg="#7C2D12",
    status_warning="#FFFBEB",
    status_warning_fg="#92400E",
    status_error="#FEF2F2",
    status_error_fg="#B91C1C",
    status_success="#DCFCE8",
    status_success_fg="#15803D",
    # Links
    link="#005fb8",
    link_hover="#004791",
    # Elevation steps
    elevation_0="#fafafa",
    elevation_1="#f3f3f3",
    # App-specific
    header_bg="#1F1F1F",
    header_fg="#FFFFFF",
    status_bg="#f3f3f3",
    border="#8A8A8A",  # ≥3:1 on #fafafa
    prod="#005fb8",
    dev="#757575",
    green="#16A34A",
    green_hover="#15803D",
    # Interactive
    hover="#eaeaea",
    selected="#2f60d8",
    # Tooltip & focus
    tooltip_bg="#212121",
    tooltip_fg="#fafafa",
    tooltip_border="#212121",
    focus_ring="#005fb8",
)

DARK_THEME = Md3Theme(
    # Primary - Brighter, more vibrant
    primary="#57c8ff",
    on_primary="#003258",
    primary_container="#1A497D",
    on_primary_container="#D1E4FF",
    # Secondary - Lighter for better contrast
    secondary="#D0C8E0",
    on_secondary="#382E45",
    # Surface tones (elevated steps)
    surface="#121212",
    surface_container="#2A2A2A",
    surface_dim="#0A0A0A",
    # On-surface - Better readability
    on_surface="#E8E6EA",
    on_surface_variant="#C4BFC9",
    # Outline — Subtle, minimal borders (≥3:1 on surface)
    outline="#8A8591",
    outline_variant="#5B5866",
    # Background - Warmer tone
    background="#0F0F10",
    on_background="#E8E6EA",
    # Error
    error="#F2B8B5",
    on_error="#601416",
    error_container="#8C1D18",
    # Semantic status surfaces
    status_info="#0F1C2E",
    status_info_fg="#B3D4F5",
    status_warning="#1A150E",
    status_warning_fg="#FCD34D",
    status_error="#2B0A08",
    status_error_fg="#FCA5A5",
    status_success="#0A1F12",
    status_success_fg="#86EFAC",
    # Links
    link="#57c8ff",
    link_hover="#8ED5FF",
    # Elevation steps (dark: higher number = darker)
    elevation_0="#101014",
    elevation_1="#1c1c1c",
    # App-specific - Modern flat colors
    header_bg="#1F1E24",
    header_fg="#E8E3E7",
    status_bg="#2d2d2d",
    border="#7A7680",  # ≥3:1 on #0F0F10
    prod="#57c8ff",
    dev="#C4BFC9",
    green="#22C55E",
    green_hover="#16A34A",
    # Interactive - Slightly more visible hover
    hover="#2d2d2d",
    selected="#2f60d8",
    # Tooltip & focus
    tooltip_bg="#fafafa",
    tooltip_fg="#1c1c1c",
    tooltip_border="#fafafa",
    focus_ring="#57c8ff",
)

# ── Lookup maps ─────────────────────────────────────────────────────────────

THEMES: dict[str, Md3Theme] = {
    "light": LIGHT_THEME,
    "dark": DARK_THEME,
}

THEME_LABELS: dict[str, str] = {
    "light": "\u2600 Light",
    "dark": "\u263e Dark",
    "auto": "\u25d0 Auto",
}

# ── Font configuration (shared across themes) ───────────────────────────────

FONT_FAMILY = "Segoe UI"
FONT_SIZE_SMALL = 9
FONT_SIZE_NORMAL = 11
FONT_SIZE_LARGE = 13


def resolve_theme_name(config_theme: str) -> str:
    """Resolve theme name, handling 'auto' detection using darkdetect if requested."""
    if config_theme == "auto":
        try:
            import darkdetect

            detect_val = darkdetect.theme()
            if detect_val and detect_val.lower() == "dark":
                return "dark"
        except Exception:
            pass
        return "light"
    return config_theme


# ── WCAG contrast helpers ───────────────────────────────────────────────────


def _hex_luminance(hex_color: str) -> float:
    """Return WCAG relative luminance (0..1) of a #RRGGBB hex color.

    Tolerates a missing leading ``#``. Returns 0.5 on parse failure so
    callers can fall back to a neutral mid-grey comparison rather than
    crashing.
    """
    if not isinstance(hex_color, str):
        return 0.5
    raw = hex_color.lstrip("#")
    if len(raw) != 6:
        return 0.5
    try:
        channels = (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    except ValueError:
        return 0.5

    def linear(channel: int) -> float:
        srgb = channel / 255.0
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Return WCAG contrast ratio (1.0..21.0) between two #RRGGBB colors."""
    fg_lum = _hex_luminance(fg_hex)
    bg_lum = _hex_luminance(bg_hex)
    lighter, darker = max(fg_lum, bg_lum), min(fg_lum, bg_lum)
    return (lighter + 0.05) / (darker + 0.05)


def _assert_contrast(
    fg_hex: str,
    bg_hex: str,
    *,
    min_ratio: float = 4.5,
    label: str = "",
) -> bool:
    """Return True if contrast meets ``min_ratio`` (WCAG AA for normal text).

    Used by :func:`apply_theme` for audit logs only — never raises.
    """
    ratio = _contrast_ratio(fg_hex, bg_hex)
    return ratio >= min_ratio


def apply_theme(root: tk.Tk, theme: Md3Theme) -> ttk.Style:
    # pylint: disable=too-many-statements
    """Apply a Material Design 3 theme or sv-ttk theme to the application.

    Updates both the Tk root palette and all ttk styles to match the
    given theme colours.

    Args:
        root: The root Tk window.
        theme: An Md3Theme instance (light or dark).

    Returns:
        The configured ttk.Style instance.
    """
    # ── Base theme (sv-ttk preferred; clam always gives us full control) ──
    style = ttk.Style()
    try:
        import sv_ttk

        sv_ttk.set_theme("dark" if theme.surface == DARK_THEME.surface else "light")
    except Exception:
        style.theme_use("clam")

    # --- Tk palette (affects native tk widgets) ---
    root.tk_setPalette(
        background=theme.surface,
        foreground=theme.on_surface,
        selectColor=theme.primary,
        selectBackground=theme.primary,
    )

    def _font(size: int = FONT_SIZE_NORMAL, *, bold: bool = False) -> tuple:
        opts: tuple = (FONT_FAMILY, size)
        if bold:
            opts = opts + ("bold",)
        return opts

    def _btn(style_name: str, fg: str, bg: str, pad: tuple[int, int]) -> None:
        style.configure(
            style_name,
            font=_font(FONT_SIZE_NORMAL),
            padding=pad,
            borderwidth=0,
            focusthickness=0,
            background=bg,
            foreground=fg,
            relief="flat",
        )
        style.map(
            style_name,
            background=[("active", theme.hover), ("pressed", theme.surface_dim)],
            foreground=[("active", fg), ("pressed", fg)],
        )

    # ── Base widget styles (always apply — not only on sv-ttk failure) ──
    style.configure("TFrame", background=theme.surface)
    style.configure(
        "TLabel",
        background=theme.surface,
        foreground=theme.on_surface,
        font=_font(),
    )
    _btn("TButton", theme.on_surface, theme.surface_container, (14, 6))
    style.configure(
        "TCombobox",
        font=_font(),
        fieldbackground=theme.surface,
        background=theme.surface,
        foreground=theme.on_surface,
        arrowcolor=theme.on_surface,
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "TCombobox",
        fieldbackground=[("focus", theme.primary_container)],
        foreground=[("focus", theme.on_primary_container)],
    )
    style.configure(
        "TCombobox.Listbox",
        font=_font(),
        background=theme.surface,
        foreground=theme.on_surface,
        borderwidth=0,
        selectbackground=theme.primary,
        selectforeground=theme.on_primary,
    )
    style.configure(
        "TCheckbutton",
        font=_font(),
        background=theme.surface,
        foreground=theme.on_surface,
        padding=(6, 4),
    )
    style.map(
        "TCheckbutton",
        background=[("active", theme.surface)],
        indicatorbackground=[("active", theme.surface_container), ("selected", theme.primary)],
        indicatorforeground=[("selected", theme.on_primary)],
    )
    style.configure("TSeparator", background=theme.outline_variant, borderwidth=0)
    for orient in ("Vertical", "Horizontal"):
        style.configure(
            f"{orient}.TScrollbar",
            background=theme.surface_container,
            troughcolor=theme.surface,
            bordercolor=theme.surface_container,
            relief="flat",
            borderwidth=0,
            arrowsize=0,
            width=14,
        )
        style.map(
            f"{orient}.TScrollbar",
            background=[("active", theme.primary), ("pressed", theme.surface_dim)],
            troughcolor=[("active", theme.surface_container)],
        )
    style.configure("TMenu", background=theme.surface, foreground=theme.on_surface)
    style.configure("TEntry", fieldbackground=theme.surface, foreground=theme.on_surface)

    # ── Focus ring: highlight keyboard focus on all interactive widgets ──
    focus = theme.focus_ring
    for sname in ("TButton", "TCombobox", "TEntry", "TCheckbutton"):
        try:
            style.map(sname, focuscolor=[("focus", focus)])
        except tk.TclError:
            pass  # some themes ignore focuscolor — harmless

    # ── Custom Sub-Styles (always apply on top of base theme) ──────
    style.configure(
        "Status.TFrame",
        background=theme.status_bg,
    )
    style.configure(
        "Title.TLabel",
        font=_font(20, bold=True),
        foreground=theme.primary,
        background=theme.surface,
    )
    style.configure(
        "TitleAuthor.TLabel",
        font=_font(FONT_SIZE_SMALL),
        foreground=theme.outline,
        background=theme.surface,
    )

    # ── Treeview (Flat, no borders, modern look) ─────────────────────
    style.configure(
        "FileList.Treeview",
        font=_font(),
        rowheight=36,
        borderwidth=0,
        fieldbackground=theme.surface,
        background=theme.surface,
        foreground=theme.on_surface,
        focuscolor="",
        relief="flat",
        selectborderwidth=0,
    )
    style.configure(
        "FileList.Treeview.Heading",
        font=_font(bold=True),
        borderwidth=0,
        relief="flat",
        background=theme.surface_container,
        foreground=theme.on_surface,
        padding=(8, 6),
    )
    style.map(
        "FileList.Treeview.Heading",
        background=[("active", theme.hover)],
    )
    style.map(
        "FileList.Treeview",
        background=[("selected", theme.primary)],
        foreground=[("selected", theme.on_primary)],
        fieldbackground=[("selected", theme.primary)],
    )

    # ── Execute button: prominent accent button ──────────────────────
    style.configure(
        "Execute.Accent.TButton",
        font=_font(FONT_SIZE_LARGE, bold=True),
        padding=(24, 8),
        borderwidth=0,
        focusthickness=0,
        background=theme.green,
        foreground=theme.on_primary,
        relief="flat",
    )
    style.map(
        "Execute.Accent.TButton",
        background=[("active", theme.green_hover), ("pressed", theme.surface_dim)],
        foreground=[("active", theme.on_primary), ("pressed", theme.on_primary)],
    )

    # ── Small status-bar button (Value.TButton) ──────────────────────
    style.configure(
        "Value.TButton",
        font=_font(FONT_SIZE_SMALL, bold=True),
        padding=(8, 3),
        borderwidth=0,
        focusthickness=0,
        background=theme.status_bg,
        foreground=theme.on_surface,
        relief="flat",
    )
    style.map(
        "Value.TButton",
        background=[("active", theme.surface_container), ("pressed", theme.surface_dim)],
        foreground=[("active", theme.primary), ("pressed", theme.primary)],
    )

    # ── Theme toggle button (smaller, status-bar style) ──────────────
    style.configure(
        "Theme.TButton",
        font=_font(FONT_SIZE_SMALL, bold=True),
        padding=(10, 3),
        borderwidth=0,
        focusthickness=0,
        background=theme.status_bg,
        foreground=theme.on_surface,
        relief="flat",
    )
    style.map(
        "Theme.TButton",
        background=[("active", theme.surface_container), ("pressed", theme.surface_dim)],
        foreground=[("active", theme.primary), ("pressed", theme.primary)],
    )

    # ── Search-bar buttons (height matches combobox fields) ──────────
    style.configure(
        "SearchBar.TButton",
        font=_font(),
        padding=(14, 5),
        borderwidth=0,
        focusthickness=0,
        background=theme.surface_container,
        foreground=theme.on_surface,
        relief="flat",
    )
    style.map(
        "SearchBar.TButton",
        background=[("active", theme.hover), ("pressed", theme.surface_dim)],
        foreground=[("active", theme.primary), ("pressed", theme.primary)],
    )

    # ── Link button (status bar / dialogs) ───────────────────────────
    style.configure(
        "Link.TButton",
        font=_font(),
        padding=0,
        borderwidth=0,
        focusthickness=0,
        background=theme.surface,
        foreground=theme.link,
        relief="flat",
        underline=True,
    )
    style.map(
        "Link.TButton",
        foreground=[("active", theme.link_hover), ("pressed", theme.link_hover)],
        background=[("active", theme.surface), ("pressed", theme.surface)],
    )

    # ── Status / message label variants ──────────────────────────────
    style.configure(
        "Header.TLabel",
        font=_font(FONT_SIZE_LARGE, bold=True),
        foreground=theme.header_fg,
        background=theme.header_bg,
        padding=(12, 8),
    )
    style.configure(
        "Status.TLabel",
        font=_font(FONT_SIZE_SMALL),
        background=theme.status_bg,
        foreground=theme.on_surface,
        padding=(4, 2),
    )
    style.configure(
        "Info.TLabel",
        font=_font(FONT_SIZE_SMALL),
        background=theme.status_bg,
        foreground=theme.on_surface,
        padding=(2, 0),
    )
    style.configure(
        "Value.TLabel",
        font=_font(FONT_SIZE_SMALL, bold=True),
        background=theme.status_bg,
        foreground=theme.on_surface,
        padding=(2, 0),
    )
    style.configure(
        "HighlightCount.TLabel",
        font=_font(FONT_SIZE_SMALL, bold=True),
        background=theme.primary_container,
        foreground=theme.primary,
        padding=(6, 2),
    )
    style.configure(
        "EmptyState.TLabel",
        font=_font(FONT_SIZE_LARGE),
        foreground=theme.outline,
        background=theme.surface,
        justify="center",
        anchor="center",
    )

    # ── Semantic status labels (info / warning / error / success) ───
    def _status_label(name: str, bg: str, fg: str) -> None:
        style.configure(
            name,
            font=_font(FONT_SIZE_SMALL, bold=True),
            background=bg,
            foreground=fg,
            padding=(4, 2),
            relief="flat",
        )

    _status_label("Status.Info.TLabel", theme.status_info, theme.status_info_fg)
    _status_label("Status.Warning.TLabel", theme.status_warning, theme.status_warning_fg)
    _status_label("Status.Error.TLabel", theme.status_error, theme.status_error_fg)
    _status_label("Status.Success.TLabel", theme.status_success, theme.status_success_fg)

    # ── Tooltip (themed; inverted on dark for legibility) ───────────
    style.configure(
        "Tooltip.TLabel",
        font=_font(FONT_SIZE_SMALL),
        background=theme.tooltip_bg,
        foreground=theme.tooltip_fg,
        bordercolor=theme.tooltip_border,
        borderwidth=1,
        relief="solid",
        padding=(6, 2),
    )

    # ── Combobox focus ring ──────────────────────────────────────────
    style.configure(
        "Focus.TCombobox",
        fieldbackground=theme.primary_container,
        foreground=theme.on_primary_container,
        bordercolor=theme.focus_ring,
        lightcolor=theme.focus_ring,
        darkcolor=theme.focus_ring,
    )

    # ── WCAG contrast audit (logs warnings, never raises) ───────────
    audit_pairs = (
        ("on_surface/surface", theme.on_surface, theme.surface),
        ("on_surface_variant/surface", theme.on_surface_variant, theme.surface),
        ("on_primary/primary", theme.on_primary, theme.primary),
        ("on_surface/status_bg", theme.on_surface, theme.status_bg),
        ("outline/surface", theme.outline, theme.surface),
        ("border/surface", theme.border, theme.surface),
        ("on_surface/outline_variant", theme.on_surface, theme.outline_variant),
    )
    audit_logger = logging.getLogger("profiles")
    for label, fg, bg in audit_pairs:
        ratio = _contrast_ratio(fg, bg)
        if ratio < 4.5:
            audit_logger.warning(
                "WCAG contrast below AA threshold: %s ratio=%.2f (fg=%s bg=%s)",
                label,
                ratio,
                fg,
                bg,
            )

    return style
