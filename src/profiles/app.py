"""ProFiles application entry point.

Supports both GUI mode (interactive) and headless CLI mode (automated).
In headless mode, files can be launched via command-line arguments.
"""

from __future__ import annotations

import argparse
import logging
import sys
import tkinter as tk
from pathlib import Path

from profiles.core import AppConfig, actions, load_config
from profiles.core.config.io.yaml_io import PRIMARY_CONFIG_NAME
from profiles.core.processing.scanner import scan_and_process
from profiles.core.telemetry import events
from profiles.core.telemetry.diagnostics import configure_logger
from profiles.gui.main_window import MainWindow
from profiles.utils.network import get_hostname, get_username


class ProFileApp:
    """ProFiles application orchestrator.

    Supports two modes:
    - GUI mode: Interactive file browser with launch capabilities
    - Headless mode: CLI-only for automated file launching

    Usage::
        # GUI mode
        app = ProFileApp()
        app.run()

        # Headless mode
        app = ProFileApp(headless=True)
        app.run_headless(file_path="path/to/file.mttl")
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
        log_path: str | Path = "profiles.log",
        headless: bool = False,
    ) -> None:
        """Initialize the application.

        Args:
            config_path: Path to the .profiles configuration file.
                If None, the config loader searches the folder tree.
            log_path: Path to the log file.
            headless: Run without GUI (CLI mode).
        """
        self._config_path = Path(config_path) if config_path is not None else None
        self._log_path = Path(log_path)
        self._headless = headless
        self._config: AppConfig | None = None
        self._window: MainWindow | None = None
        self._logger: logging.Logger | None = None

    @staticmethod
    def _parse_log_level(verbose: str) -> int:
        """Convert verbose string to logging level.

        Args:
            verbose: Verbose level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).

        Returns:
            Corresponding logging level constant.
        """
        try:
            return getattr(logging, verbose.upper(), logging.INFO)
        except (AttributeError, ValueError):
            return logging.INFO

    def _setup_logging(self, level: int | str = logging.INFO) -> logging.Logger:
        """Configure the logging subsystem.

        Configures a rotating file logger with the hostname as the
        source identifier.

        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

        Returns:
            Configured logger instance.
        """
        return configure_logger(
            log_path=self._log_path,
            source=get_hostname(),
            level=level,
        )

    def _load_configuration(self, logger: logging.Logger) -> AppConfig:
        """Load the application configuration.

        Searches the folder tree for a .profiles file. If none is found,
        returns an AppConfig with default values.

        Args:
            logger: Logger instance to use for logging.

        Returns:
            The loaded AppConfig (may contain defaults).

        Exits:
            SystemExit(1) if configuration is invalid.
        """
        try:
            config = load_config(self._config_path)
            events.config_loaded(
                logger,
                path=str(self._config_path) if self._config_path else "auto",
                mode="folder tree search" if not self._config_path else "explicit",
                release=config.release,
            )
            return config
        except (OSError, ValueError) as exc:
            events.config_invalid(logger, error=str(exc))
            print(f"ERROR: Invalid configuration: {exc}", file=sys.stderr)
            sys.exit(1)

    def run(self, file: str | Path | None = None) -> None:
        """Run the ProFiles application.

        The full lifecycle:
        1. Load configuration (to get verbose level)
        2. Configure logging with the specified verbosity
        3. Create and display the main window (or run headless)
        4. Start the Tkinter event loop

        Args:
            file: File to launch (headless mode only).
        """
        # Step 1: Load configuration with temporary logger
        temp_logger = self._setup_logging()
        self._config = self._load_configuration(temp_logger)

        # Step 2: Determine logging level
        # If scan_metrics is enabled, force DEBUG level to capture metrics
        if self._config.scan_metrics:
            log_level = logging.DEBUG
        else:
            log_level = self._parse_log_level(self._config.verbose)

        # Step 3: Reconfigure logging with the determined level
        self._logger = self._setup_logging(log_level)

        # Step 4: Branch to headless mode if requested
        if self._headless:
            try:
                sys.exit(self.run_headless(file_path=file))
            finally:
                # Ensure all log handlers are flushed before exit
                for handler in self._logger.handlers[:]:
                    handler.flush()
                    handler.close()
                    self._logger.removeHandler(handler)

        # Step 5: Create and run the GUI
        self._run_gui()

    def _run_gui(self) -> None:
        """Create and run the GUI.

        Handles GUI creation and error cases (e.g., no display available).

        Exits:
            SystemExit(1) if GUI initialization fails.
        """
        try:
            self._window = MainWindow(config=self._config)
        except (RuntimeError, tk.TclError) as exc:
            error_msg = str(exc).lower()
            if "screen" in error_msg or "display" in error_msg:
                events.app_gui_failed(
                    self._logger,
                    error="running in headless environment. Use --headless for CLI mode.",
                )
                print(
                    "ERROR: No display available. Use 'profiles --headless' for CLI mode.",
                    file=sys.stderr,
                )
            else:
                events.app_gui_failed(self._logger, error=str(exc))
                print(f"ERROR: Failed to create GUI: {exc}", file=sys.stderr)
            sys.exit(1)

        self._window.run()

    def run_headless(self, file_path: str | Path | None = None) -> int:
        """Run in headless/CLI mode for automated file launching.

        Args:
            file_path: Path to file to launch. If None, scans directories
                from config and launches files matching criteria.

        Returns:
            Exit code (0 for success, 1 for error).
        """
        # Narrow types for type checker (set in run() before calling this)
        _logger = self._logger
        _config = self._config
        assert _logger is not None
        assert _config is not None

        if file_path:
            _logger.info("Running in headless mode. File: %s", file_path)
        else:
            _logger.info("Running in headless mode: scanning all configured directories")

        # If file_path is not provided, scan all configured directories
        if not file_path:
            for cfg in _config.configurations:
                if cfg.directory:
                    ext = _config.extensions[0] if _config.extensions else "All"
                    # Use scan_and_process to enable metrics logging
                    scanned_files = scan_and_process(
                        cfg.directory,
                        extension=ext,
                        exclude_dirs=_config.search_exclude_dirs,
                        exclude_files=cfg.search_exclude_files,
                        config=_config,  # Pass config for scan_metrics
                    )
                    for scanned in scanned_files:
                        result = actions.launch_selected_file(
                            directory=str(scanned.path.parent),
                            filename=scanned.path.name,
                            release=_config.release,
                            username=get_username(),
                            logger=_logger,
                            config=_config,
                        )
                        if result.status is not actions.ActionStatus.SUCCESS:
                            _logger.warning(
                                "Launch did not succeed for %s: %s",
                                scanned.path,
                                result.message,
                            )
            return 0

        # Launch the specified file
        file_path = Path(file_path)
        if not file_path.exists():
            events.file_not_found(logger=_logger, path=str(file_path))
            print(f"ERROR: File not found: {file_path}", file=sys.stderr)
            return 1

        result = actions.launch_selected_file(
            directory=str(file_path.parent),
            filename=file_path.name,
            release=_config.release,
            username=get_username(),
            logger=_logger,
            config=_config,
        )
        if result.status is actions.ActionStatus.SUCCESS:
            return 0

        print(f"ERROR: {result.message}", file=sys.stderr)
        return 1


def init_default_config(dest: Path | None = None) -> Path:
    """Generate a default ``.profiles`` file in the given directory.

    Writes the canonical YAML starter template from
    :mod:`profiles.core.config.template` to *dest* (or the current
    working directory by default). If the file already exists, prints
    a warning and exits.

    Args:
        dest: Destination directory (default: current working directory).

    Returns:
        Path to the generated file.

    Raises:
        SystemExit: If the file already exists or cannot be written.
    """
    if dest is None:
        dest = Path.cwd()
    target = Path(dest) / PRIMARY_CONFIG_NAME

    if target.exists():
        print(
            f"Warning: {target} already exists. Delete it first or use a different directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    from profiles.core.config.template import STARTER_CONFIG_TEMPLATE

    body = STARTER_CONFIG_TEMPLATE.format(cwd=str(Path.cwd()))
    try:
        target.write_text(body, encoding="utf-8")
    except OSError as exc:
        print(f"Error: Could not write configuration file: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Default configuration created: {target}")
    return target


def main() -> None:
    """Entry point for the ProFiles application.

    This function is registered as console_scripts entry point
    in pyproject.toml.

    Usage:
        profiles                          Launch GUI
        profiles --config path/.profiles  Launch with explicit config
        profiles --headless               Headless: scan & launch all
        profiles --headless file.mttl     Launch specific file
        profiles --init                   Generate default .profiles in CWD
    """
    parser = argparse.ArgumentParser(
        description="ProFiles - Python MuTool Project Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  profiles                                  Launch GUI (auto-search config)
  profiles --config /path/to/.profiles      Use explicit config file
  profiles --headless                       Headless: scan & launch all
  profiles --headless file.mttl             Headless: launch specific file
  profiles --init                           Generate default .profiles in CWD
        """,
    )
    parser.add_argument(
        "--config",
        default=None,
        type=str,
        help="Path to .profiles configuration file (default: auto-search folder tree)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Generate a default .profiles configuration file in the current directory",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (no GUI)",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="File to launch (optional, headless mode only)",
    )

    args = parser.parse_args()

    if args.init:
        init_default_config()
        return

    app = ProFileApp(config_path=args.config, headless=args.headless)
    app.run(file=args.file)


if __name__ == "__main__":
    main()
