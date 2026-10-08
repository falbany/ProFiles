"""Qt styling and HiDPI configuration."""

from typing import Literal

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QStyleFactory

from profiles.gui.theme import DARK_THEME, LIGHT_THEME, to_qss_tokens

ThemeName = Literal["light", "dark", "auto"]


def configure_app(app: QApplication, theme_name: ThemeName = "auto") -> ThemeName:
    """Configure QApplication with HiDPI support and theme.

    Args:
        app: QApplication instance to configure.
        theme_name: Theme name ('light', 'dark', or 'auto').

    Returns:
        Resolved theme name after configuration.
    """
    # HiDPI setup for Qt >= 6.0
    if hasattr(QGuiApplication, "setHighDpiScaleFactorRoundingPolicy"):
        try:
            from PySide6.QtGui import QHighDpiScaleFactorRoundingPolicy

            QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
                QHighDpiScaleFactorRoundingPolicy.PassThrough
            )
        except ImportError:
            # Fallback for Qt versions where this is not available
            pass

    # Font scaling based on DPI
    screen = app.primaryScreen()
    if screen:
        # Qt 6.x uses logicalDotsPerInchX() instead of logicalDpiX()
        if hasattr(screen, "logicalDotsPerInchX"):
            dpi = screen.logicalDotsPerInchX()
        elif hasattr(screen, "logicalDpiX"):
            dpi = screen.logicalDpiX()
        else:
            dpi = 96  # Default DPI
        if dpi >= 144:  # Retina/high-DPI
            font = app.font()
            font.setPointSize(11)
            app.setFont(font)

    # Resolve theme
    if theme_name == "auto":
        # Detect system color scheme
        resolved_theme: ThemeName = "light"
    else:
        resolved_theme = theme_name

    # Apply QSS style
    style_name = "Fusion"
    app.setStyle(QStyleFactory.create(style_name))

    # Generate and apply QSS
    qss = _generate_qss(resolved_theme)
    if qss:
        app.setStyleSheet(qss)
    else:
        # Fallback to original style
        app.setStyle(QStyleFactory.create(style_name))

    return resolved_theme


def _generate_qss(theme: ThemeName) -> str:
    """Generate QSS stylesheet for the given theme.

    Args:
        theme: Theme name to generate stylesheet for.

    Returns:
        QSS stylesheet string, or empty string on error.
    """
    try:
        if theme == "dark":
            return _get_dark_qss()
        return _get_light_qss()
    except Exception:
        return ""


def _get_light_qss() -> str:
    """Generate light theme QSS using MD3 tokens."""
    tokens = to_qss_tokens(LIGHT_THEME)
    return f"""
        QMainWindow {{
            background-color: {tokens["surface"]};
            color: {tokens["on_surface"]};
        }}
        QMenuBar {{
            background-color: {tokens["surface"]};
            color: {tokens["on_surface"]};
            border: 1px solid {tokens["outline_variant"]};
        }}
        QMenuBar::item:selected {{
            background-color: {tokens["surface_container"]};
        }}
        QMenuBar::item:pressed {{
            background-color: {tokens["surface_container"]};
        }}
        QStatusBar {{
            background-color: {tokens["status_bg"]};
            color: {tokens["on_surface"]};
        }}
        QMenu {{
            background-color: {tokens["surface"]};
            color: {tokens["on_surface"]};
            border: 1px solid {tokens["outline"]};
        }}
        QMenu::item:selected {{
            background-color: {tokens["hover"]};
        }}
        QToolTip {{
            background-color: {tokens["tooltip_bg"]};
            color: {tokens["tooltip_fg"]};
            border: 1px solid {tokens["tooltip_border"]};
        }}
    """


def _get_dark_qss() -> str:
    """Generate dark theme QSS using MD3 tokens."""
    tokens = to_qss_tokens(DARK_THEME)
    return f"""
        QMainWindow {{
            background-color: {tokens["surface"]};
            color: {tokens["on_surface"]};
        }}
        QMenuBar {{
            background-color: {tokens["surface"]};
            color: {tokens["on_surface"]};
            border: 1px solid {tokens["outline_variant"]};
        }}
        QMenuBar::item:selected {{
            background-color: {tokens["surface_container"]};
        }}
        QMenuBar::item:pressed {{
            background-color: {tokens["surface_container"]};
        }}
        QStatusBar {{
            background-color: {tokens["status_bg"]};
            color: {tokens["on_surface"]};
        }}
        QMenu {{
            background-color: {tokens["surface"]};
            color: {tokens["on_surface"]};
            border: 1px solid {tokens["outline"]};
        }}
        QMenu::item:selected {{
            background-color: {tokens["hover"]};
        }}
        QToolTip {{
            background-color: {tokens["tooltip_bg"]};
            color: {tokens["tooltip_fg"]};
            border: 1px solid {tokens["tooltip_border"]};
        }}
    """
