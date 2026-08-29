"""Tests for performance metrics functionality.

These tests verify that the metrics feature works correctly without
relying on log capture which can cause issues in some environments.
"""

from pathlib import Path

from profiles.core.config.models import AppConfig
from profiles.core.processing.scanner import scan_and_process
from profiles.core.telemetry.metrics import ScanMetrics, ScanTimer


class TestScanTimer:
    """Tests for the ScanTimer context manager."""

    def test_timer_basic_functionality(self, tmp_path: Path) -> None:
        """Test basic timer start/stop and metrics collection."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Use timer as context manager
        with ScanTimer(str(tmp_path), recursive=False) as timer:
            # Simulate work
            files = list(tmp_path.iterdir())
            timer.record_files(len(files))

        # Verify metrics
        metrics = timer.get_metrics()
        assert metrics is not None
        assert metrics.directory == str(tmp_path)
        assert metrics.file_count == 1
        assert metrics.duration_ms >= 0
        assert metrics.recursive is False
        assert metrics.error_count == 0

    def test_timer_empty_directory(self, tmp_path: Path) -> None:
        """Test timer with no files."""
        with ScanTimer(str(tmp_path), recursive=False) as timer:
            timer.record_files(0)

        metrics = timer.get_metrics()
        assert metrics is not None
        assert metrics.file_count == 0
        assert metrics.files_per_second == 0.0

    def test_timer_error_counting(self, tmp_path: Path) -> None:
        """Test that errors are tracked."""
        with ScanTimer(str(tmp_path), recursive=False) as timer:
            timer.error_count = 3
            timer.record_files(10)

        metrics = timer.get_metrics()
        assert metrics is not None
        assert metrics.error_count == 3

    def test_timer_recursive_flag(self, tmp_path: Path) -> None:
        """Test that recursive flag is recorded."""
        with ScanTimer(str(tmp_path), recursive=True) as timer:
            timer.record_files(5)

        metrics = timer.get_metrics()
        assert metrics is not None
        assert metrics.recursive is True

    def test_timer_finish_logs_metrics(self, tmp_path: Path, caplog) -> None:  # noqa: ANN001
        """Test that finish() records count, stops timer, and logs."""
        import logging

        with caplog.at_level(logging.DEBUG, logger="profiles"):
            with ScanTimer(str(tmp_path), recursive=False) as timer:
                pass

            metrics = timer.finish(7)

        # Returns computed metrics
        assert metrics is not None
        assert metrics.file_count == 7
        assert metrics.duration_ms >= 0
        # And emits the structured event lines
        assert any("SCAN_COMPLETE" in r.message for r in caplog.records)
        assert any("SCAN_METRICS" in r.message for r in caplog.records)

    def test_metrics_to_dict(self) -> None:
        """Test metrics serialization to dictionary."""
        metrics = ScanMetrics(
            directory="/test/path",
            file_count=100,
            duration_ms=500.0,
            files_per_second=200.0,
            recursive=True,
            error_count=0,
        )

        result = metrics.to_dict()
        assert isinstance(result, dict)
        assert result["directory"] == "/test/path"
        assert result["file_count"] == 100
        assert result["duration_ms"] == 500.0
        assert result["files_per_second"] == 200.0
        assert result["recursive"] is True
        assert result["error_count"] == 0


class TestScanMetricsIntegration:
    """Integration tests for metrics with scanner."""

    def test_scan_with_metrics_enabled(self, tmp_path: Path) -> None:
        """Test that scan works with metrics enabled."""
        for i in range(5):
            (tmp_path / f"test_{i}.txt").write_text(f"content {i}")

        config = AppConfig(scan_metrics=True)
        results = scan_and_process(str(tmp_path), extension=".txt", config=config)

        assert len(results) == 5

    def test_scan_with_metrics_disabled(self, tmp_path: Path) -> None:
        """Test that scan works with metrics disabled (default)."""
        for i in range(3):
            (tmp_path / f"test_{i}.txt").write_text(f"content {i}")

        config = AppConfig(scan_metrics=False)
        results = scan_and_process(str(tmp_path), extension=".txt", config=config)

        assert len(results) == 3

    def test_scan_without_config(self, tmp_path: Path) -> None:
        """Test that scan works without config (no metrics)."""
        for i in range(2):
            (tmp_path / f"test_{i}.txt").write_text(f"content {i}")

        results = scan_and_process(str(tmp_path), extension=".txt")

        assert len(results) == 2

    def test_scan_recursive_with_metrics(self, tmp_path: Path) -> None:
        """Test recursive scan with metrics."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.txt").write_text("root")
        (subdir / "nested.txt").write_text("nested")

        config = AppConfig(scan_metrics=True)
        results = scan_and_process(
            str(tmp_path),
            extension=".txt",
            recursive=True,
            config=config,
        )

        assert len(results) == 2

    def test_explicit_log_metrics_override(self, tmp_path: Path) -> None:
        """Test that explicit log_metrics=True overrides config."""
        for i in range(2):
            (tmp_path / f"test_{i}.txt").write_text(f"content {i}")

        # Config says False, but explicit param says True
        config = AppConfig(scan_metrics=False)
        results = scan_and_process(
            str(tmp_path),
            extension=".txt",
            config=config,
            log_metrics=True,
        )

        assert len(results) == 2


class TestConfigScanMetrics:
    """Tests for scan_metrics configuration."""

    def test_config_default_value(self) -> None:
        """Test that scan_metrics defaults to False."""
        config = AppConfig()
        assert config.scan_metrics is False

    def test_config_explicit_true(self) -> None:
        """Test explicit scan_metrics=True."""
        config = AppConfig(scan_metrics=True)
        assert config.scan_metrics is True

    def test_config_explicit_false(self) -> None:
        """Test explicit scan_metrics=False."""
        config = AppConfig(scan_metrics=False)
        assert config.scan_metrics is False

    def test_config_parsing_vrai(self, tmp_path: Path) -> None:
        """Test ConfigReader parses 'True' as True."""
        from profiles.core.config.reader import ConfigReader

        profiles_file = tmp_path / ".profiles"
        profiles_file.write_text("defaults:\n  scan_metrics: true\n")

        reader = ConfigReader(profiles_file)
        config = reader.load()

        assert config.scan_metrics is True

    def test_config_parsing_faux(self, tmp_path: Path) -> None:
        """Test ConfigReader parses 'False' as False."""
        from profiles.core.config.reader import ConfigReader

        profiles_file = tmp_path / ".profiles"
        profiles_file.write_text("defaults:\n  scan_metrics: false\n")

        reader = ConfigReader(profiles_file)
        config = reader.load()

        assert config.scan_metrics is False

    def test_config_parsing_true(self, tmp_path: Path) -> None:
        """Test ConfigReader parses 'True' as True."""
        from profiles.core.config.reader import ConfigReader

        profiles_file = tmp_path / ".profiles"
        profiles_file.write_text("defaults:\n  scan_metrics: true\n")

        reader = ConfigReader(profiles_file)
        config = reader.load()

        assert config.scan_metrics is True

    def test_config_parsing_false(self, tmp_path: Path) -> None:
        """Test ConfigReader parses 'False' as False."""
        from profiles.core.config.reader import ConfigReader

        profiles_file = tmp_path / ".profiles"
        profiles_file.write_text("[LAUNCHER]\nscan_metrics = False\n")

        reader = ConfigReader(profiles_file)
        config = reader.load()

        assert config.scan_metrics is False
