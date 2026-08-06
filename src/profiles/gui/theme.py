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
    # Outline
    outline="#C4C6D0",
    outline_variant="#E0E0E4",
    # Background
    background="#fafafa",
    on_background="#1c1c1c",
    # Error
    error="#B3261E",
    on_error="#FFFFFF",
    error_container="#F9DEDC",
    # App-specific
    header_bg="#1F1F1F",
    header_fg="#FFFFFF",
    status_bg="#f3f3f3",
    border="#E0E0E4",
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
    # Surface - Lighter tones for modern flat look
    surface="#1c1c1c",
    surface_container="#2d2d2d",
    surface_dim="#202020",
    # On-surface - Better readability
    on_surface="#fafafa",
    on_surface_variant="#C4BFC9",
    # Outline - Subtle, minimal borders
    outline="#7A7680",
    outline_variant="#524E58",
    # Background - Warmer tone
    background="#1c1c1c",
    on_background="#fafafa",
    # Error
    error="#F2B8B5",
    on_error="#601410",
    error_container="#8C1D18",
    # App-specific - Modern flat colors
    header_bg="#1F1E24",
    header_fg="#E8E3E7",
    status_bg="#2d2d2d",
    border="#3E3A44",  # Very subtle borders
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
    # ── Try to load sv-ttk first ─────────────────────────────────────
    sv_ttk_loaded = False
    try:
        import sv_ttk

        theme_name = "dark" if theme.surface == DARK_THEME.surface else "light"
        sv_ttk.set_theme(theme_name)
        sv_ttk_loaded = True
    except Exception:
        pass

    # --- Tk palette (affects native tk widgets) ---
    root.tk_setPalette(
        background=theme.surface,
        foreground=theme.on_surface,
        selectColor=theme.primary,
        selectBackground=theme.primary,
    )

    # --- ttk styles ---
    style = ttk.Style()
    if not sv_ttk_loaded:
        style.theme_use("clam")  # clam supports most styling options

    # ── Custom Sub-Styles (always apply on top of active theme) ──────
    style.configure(
        "Status.TFrame",
        background=theme.status_bg,
    )
    style.configure(
        "Title.TLabel",
        font=(FONT_FAMILY, 20, "italic bold"),
        foreground=theme.primary,
        background=theme.surface,
    )
    style.configure(
        "TitleAuthor.TLabel",
        font=(FONT_FAMILY, FONT_SIZE_SMALL),
        foreground=theme.outline,
        background=theme.surface,
    )

    # ── Treeview (Flat, no borders, modern look) ─────────────────────
    style.configure(
        "FileList.Treeview",
        font=(FONT_FAMILY, FONT_SIZE_NORMAL),
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
        font=(FONT_FAMILY, FONT_SIZE_NORMAL, "bold"),
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
    if sv_ttk_loaded:
        style.configure(
            "Execute.Accent.TButton",
            font=(FONT_FAMILY, FONT_SIZE_LARGE, "bold"),
            padding=(24, 8),
        )
    else:
        style.configure(
            "Execute.Accent.TButton",
            font=(FONT_FAMILY, FONT_SIZE_LARGE, "bold"),
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
        font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
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
        font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
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
        font=(FONT_FAMILY, FONT_SIZE_NORMAL),
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

    # ── Label variants ───────────────────────────────────────────────
    style.configure(
        "Header.TLabel",
        font=(FONT_FAMILY, FONT_SIZE_LARGE, "bold"),
        foreground=theme.header_fg,
        background=theme.header_bg,
        padding=(12, 8),
    )
    style.configure(
        "Status.TLabel",
        font=(FONT_FAMILY, FONT_SIZE_SMALL),
        background=theme.status_bg,
        foreground=theme.on_surface,
        padding=(4, 2),
    )
    style.configure(
        "Info.TLabel",
        font=(FONT_FAMILY, FONT_SIZE_SMALL),
        background=theme.status_bg,
        foreground=theme.on_surface,
        padding=(2, 0),
    )
    style.configure(
        "Value.TLabel",
        font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
        background=theme.status_bg,
        foreground=theme.on_surface,
        padding=(2, 0),
    )
    style.configure(
        "HighlightCount.TLabel",
        font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
        background=theme.primary_container,
        foreground=theme.primary,
        padding=(6, 2),
    )
    style.configure(
        "EmptyState.TLabel",
        font=(FONT_FAMILY, FONT_SIZE_LARGE),
        foreground=theme.outline,
        background=theme.surface,
        justify="center",
        anchor="center",
    )

    # ── Tooltip (themed; inverted on dark for legibility) ───────────
    style.configure(
        "Tooltip.TLabel",
        font=(FONT_FAMILY, FONT_SIZE_SMALL),
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

    # ── Base clam Styles (only applied if sv-ttk fallback happens) ──
    if not sv_ttk_loaded:
        style.configure(
            "TFrame",
            background=theme.surface,
        )
        style.configure(
            "TLabel",
            background=theme.surface,
            foreground=theme.on_surface,
            font=(FONT_FAMILY, FONT_SIZE_NORMAL),
        )
        # Buttons
        style.configure(
            "TButton",
            font=(FONT_FAMILY, FONT_SIZE_NORMAL),
            padding=(14, 6),
            borderwidth=0,
            focusthickness=0,
            background=theme.surface_container,
            foreground=theme.on_surface,
            relief="flat",
        )
        style.map(
            "TButton",
            background=[("active", theme.hover), ("pressed", theme.surface_dim)],
            foreground=[("active", theme.primary), ("pressed", theme.primary)],
        )
        # Combobox
        style.configure(
            "TCombobox",
            font=(FONT_FAMILY, FONT_SIZE_NORMAL),
            padding=(6, 3),
            borderwidth=0,
            focusthickness=0,
            background=theme.surface,
            foreground=theme.on_surface,
            fieldbackground=theme.surface,
            arrowcolor=theme.on_surface,
            relief="flat",
        )
        style.map(
            "TCombobox",
            fieldbackground=[("focus", theme.surface)],
            background=[("focus", theme.surface)],
            foreground=[("focus", theme.on_surface)],
        )
        style.configure(
            "TCombobox.Listbox",
            font=(FONT_FAMILY, FONT_SIZE_NORMAL),
            background=theme.surface,
            foreground=theme.on_surface,
            borderwidth=0,
            selectbackground=theme.primary,
            selectforeground=theme.on_primary,
        )
        # Checkbutton
        style.configure(
            "TCheckbutton",
            font=(FONT_FAMILY, FONT_SIZE_NORMAL),
            background=theme.surface,
            foreground=theme.on_surface,
            padding=(6, 4),
            borderwidth=0,
            focusthickness=0,
            relief="flat",
            indicatorbackground=theme.surface_container,
            indicatorforeground=theme.primary,
        )
        style.map(
            "TCheckbutton",
            background=[("active", theme.surface)],
            indicatorbackground=[("active", theme.surface_container), ("selected", theme.primary)],
            indicatorforeground=[("selected", theme.on_primary)],
        )
        # Scrollbars
        style.configure(
            "Vertical.TScrollbar",
            borderwidth=0,
            gripcount=0,
            width=14,
            background=theme.surface_container,
            darkcolor=theme.secondary,
            lightcolor=theme.secondary,
            troughcolor=theme.surface,
            bordercolor=theme.surface_container,
            relief="flat",
            arrowsize=0,
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", theme.primary), ("pressed", theme.surface_dim)],
            troughcolor=[("active", theme.surface_container)],
        )
        style.configure(
            "Horizontal.TScrollbar",
            borderwidth=0,
            gripcount=0,
            width=14,
            background=theme.surface_container,
            darkcolor=theme.secondary,
            lightcolor=theme.secondary,
            troughcolor=theme.surface,
            relief="flat",
            arrowsize=0,
        )
        style.map(
            "Horizontal.TScrollbar",
            background=[("active", theme.primary), ("pressed", theme.surface_dim)],
            troughcolor=[("active", theme.surface_container)],
        )
        # Separator
        style.configure(
            "TSeparator",
            background=theme.outline_variant,
            relief="flat",
            borderwidth=0,
        )

    # ── WCAG contrast audit (logs warnings, never raises) ───────────
    audit_pairs = (
        ("on_surface/surface", theme.on_surface, theme.surface),
        ("on_surface_variant/surface", theme.on_surface_variant, theme.surface),
        ("on_primary/primary", theme.on_primary, theme.primary),
        ("on_surface/status_bg", theme.on_surface, theme.status_bg),
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
