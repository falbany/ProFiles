"""Qt styling and HiDPI configuration."""

from typing import Literal

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QStyleFactory

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
    """Generate light theme QSS."""
    return """
        QMainWindow {
            background-color: #f0f0f0;
        }
        QMenuBar {
            background-color: #f0f0f0;
            color: #000000;
        }
        QMenuBar::item:selected {
            background-color: #d0d0d0;
        }
        QStatusBar {
            background-color: #f0f0f0;
            color: #000000;
        }
    """


def _get_dark_qss() -> str:
    """Generate dark theme QSS."""
    return """
        QMainWindow {
            background-color: #2b2b2b;
        }
        QMenuBar {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QMenuBar::item:selected {
            background-color: #3b3b3b;
        }
        QStatusBar {
            background-color: #2b2b2b;
            color: #ffffff;
        }
    """
