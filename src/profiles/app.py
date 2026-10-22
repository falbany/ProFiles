"""ProFiles application entry point.

Supports both GUI mode (interactive) and headless CLI mode (automated).
In headless mode, files can be launched via command-line arguments.
"""

from __future__ import annotations

import argparse
import logging
import platform
import sys
import tkinter as tk
from pathlib import Path

from profiles.core import AppConfig, actions, load_config
from profiles.core.config.io.yaml_io import PRIMARY_CONFIG_NAME
from profiles.core.environment.system import format_user_host
from profiles.core.processing.scanner import scan_and_process
from profiles.core.telemetry import events
from profiles.core.telemetry.diagnostics import configure_logger, install_crash_hook
from profiles.gui.main_window import MainWindow
from profiles.launch import (
    detect_launch_context,
    resolve_config_path,
    with_explicit_config,
)
from profiles.utils.network import get_hostname, get_username

_DEFAULT_PORT = 8088


def _stop_port_owner_command(port: int) -> str:
    """Build the OS-appropriate command to free a busy local *port*.

    Embedded in startup errors so the fix is copy-pasteable instead of
    something the user has to go and look up.

    Args:
        port: TCP port number to release.

    Returns:
        A single-line shell command killing whatever listens on *port*.
    """
    if sys.platform == "win32":
        return (
            f'for /f "tokens=5" %a in '
            f"('netstat -ano ^| findstr :{port} ^| findstr LISTENING') "
            "do taskkill /PID %a /F"
        )
    return f"kill $(lsof -ti:{port} -sTCP:LISTEN)"


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
        server_only: bool = False,
        no_config_propose: bool = False,
        gui_backend: str = "web",
    ) -> None:
        """Initialize the application.

        Args:
            config_path: Path to the .profiles configuration file.
                If None, the config loader searches the folder tree.
            log_path: Path to the log file.
            headless: Run without GUI (CLI mode).
            server_only: Run only the web server without opening desktop window.
            no_config_propose: Do not offer to create a .profiles at startup.
            gui_backend: GUI backend to use ('tk' or 'web'). Defaults to 'web'.
        """
        self._config_path = Path(config_path) if config_path is not None else None
        self._log_path = Path(log_path)
        self._headless = headless
        self._server_only = server_only
        self._no_config_propose = no_config_propose
        self._gui_backend = gui_backend.lower()
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

        Configures a rotating file logger with the ``user@host`` source
        identifier and routes uncaught exceptions into the log.

        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

        Returns:
            Configured logger instance.
        """
        logger = configure_logger(
            log_path=self._log_path,
            source=format_user_host(get_username(), get_hostname()),
            level=level,
        )
        install_crash_hook(logger)
        return logger

    def _resolve_startup_config(
        self,
        explicit: Path | None,
    ) -> tuple[Path | None, bool]:
        """Return (config_path, config_is_missing).

        Uses the launch resolution logic to determine which config file
        should be used for this launch.

        Args:
            explicit: Value of --config flag, if any.

        Returns:
            Tuple of (resolved config path or None, whether it's missing).
        """
        ctx = detect_launch_context()
        ctx = with_explicit_config(ctx, explicit)
        resolved = resolve_config_path(ctx)
        is_missing = resolved is not None and not resolved.exists()
        return resolved, is_missing

    def _load_configuration(self, logger: logging.Logger) -> AppConfig:
        """Load the application configuration.

        Uses launch-time resolution to determine which config file to use.
        If no config is found and not in server-only mode, offers to create
        a starter configuration.

        Args:
            logger: Logger instance to use for logging.

        Returns:
            The loaded AppConfig (may contain defaults).

        Exits:
            SystemExit(1) if configuration is invalid.
        """
        # Use launch resolution instead of bare self._config_path
        resolved, is_missing = self._resolve_startup_config(self._config_path)

        if is_missing:
            events.config_invalid(logger, error=f"Config file not found: {resolved}")
            print(f"ERROR: Configuration file not found: {resolved}", file=sys.stderr)
            sys.exit(1)

        try:
            config = load_config(resolved)
            events.config_loaded(
                logger,
                path=str(resolved) if resolved else "auto",
                mode="launch resolution" if resolved else "auto",
                release=config.release,
            )
            self._config_path = resolved  # Update for later use
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

        if getattr(self, "_server_only", False):
            self._run_server_only()
            return

        # Step 4: Create and run the GUI
        # (missing-config proposal lives in gui/window_actions.py for the
        # Tkinter GUI and in the web frontend's config modal + the
        # /api/config/create endpoint for the web backend.)
        self._logger.info(f"Selected GUI backend: {self._gui_backend}")
        if self._gui_backend == "web":
            self._run_web_gui()
        else:
            self._run_gui()

    def _run_server_only(self, port: int = _DEFAULT_PORT, host: str = "0.0.0.0") -> None:
        """Run only the FastAPI background server without opening PyWebView."""
        import time

        from profiles.desktop.lifecycle import BackgroundServer, ServerStartError
        from profiles.utils.network import get_local_ip

        assert self._config is not None
        server = BackgroundServer(config=self._config, host=host, port=port)
        try:
            server.start()
        except ServerStartError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        # Display both local and network URLs
        local_ip = get_local_ip()
        print("ProFiles server running at:")
        print(f"  Local:  http://127.0.0.1:{server.port}")
        print(f"  Network: http://{local_ip}:{server.port}")
        print("  Access from other PCs on your network (press Ctrl+C to stop)")
        try:
            while server.is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nShutting down ProFiles server...")
        finally:
            server.stop()

    def _run_web_gui(self, port: int = _DEFAULT_PORT, host: str = "127.0.0.1") -> None:
        """Launch web backend via PyWebView desktop shell."""
        from profiles.desktop.launcher import launch_desktop_window
        from profiles.desktop.lifecycle import ServerStartError

        assert self._config is not None
        try:
            launch_desktop_window(self._config, port=port, host=host)
        except ServerStartError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            print(
                "Another process is already using this port. Stop it with:\n"
                f"    {_stop_port_owner_command(port)}",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc

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
            events.app_started(
                _logger,
                version=_config.release,
                headless=True,
                python_version=platform.python_version(),
                os_name=f"{platform.system()} {platform.release()}",
            )
        else:
            events.scan_complete(
                _logger,
                directory="<headless-all>",
                extension="*",
                filter_text="",
                files=0,
                recursive=True,
                duration_ms=0.0,
            )

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
                            events.file_launch_failed(
                                _logger,
                                path=str(scanned.path),
                                error=result.message,
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
        profiles                          Launch GUI with web backend (default)
        profiles --web                    Launch GUI with web backend
        profiles --tkinter                Launch GUI with Tkinter backend
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
  profiles                                  Launch GUI with web backend (default)
  profiles --web                            Launch GUI with web backend
  profiles --tkinter                        Launch GUI with Tkinter backend
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
        "--server-only",
        action="store_true",
        help="Run local FastAPI server only (no desktop window, for browser/PWA use)",
    )
    parser.add_argument(
        "--no-config-propose",
        action="store_true",
        help="Do not offer to create a .profiles file at startup",
    )
    parser.add_argument(
        "--tkinter",
        action="store_true",
        help="Use Tkinter GUI backend (default is web)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Use web GUI backend (default)",
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

    # Determine GUI backend from arguments
    if args.tkinter:
        gui_backend = "tk"
    elif args.web:
        gui_backend = "web"
    else:
        gui_backend = "web"  # Default to web

    app = ProFileApp(
        config_path=args.config,
        headless=args.headless,
        server_only=args.server_only,
        no_config_propose=args.no_config_propose,
        gui_backend=gui_backend,
    )
    app.run(file=args.file)


if __name__ == "__main__":
    main()
