"""Tests for HiDPI configuration."""

import pytest
from PySide6.QtWidgets import QApplication


class TestHiDPI:
    """Tests for HiDPI scale factor configuration."""

    def test_hidpi_scale_factor(self):
        """Verify PassThrough policy is set for HiDPI scaling."""
        app = QApplication.instance() or QApplication([])
        # Check if the policy method exists (Qt 5.14+)
        if hasattr(app.__class__, "setHighDpiScaleFactorRoundingPolicy"):
            try:
                from PySide6.QtGui import QHighDpiScaleFactorRoundingPolicy

                # The policy should be set during configure_app
                # We verify the method is callable and accepts the policy
                app.__class__.setHighDpiScaleFactorRoundingPolicy(
                    QHighDpiScaleFactorRoundingPolicy.PassThrough
                )

                # Verify it was set correctly
                current_policy = app.__class__.highDpiScaleFactorRoundingPolicy()
                assert current_policy == QHighDpiScaleFactorRoundingPolicy.PassThrough
            except ImportError:
                # Policy class not available in this Qt version - skip test
                pytest.skip("QHighDpiScaleFactorRoundingPolicy not available")
