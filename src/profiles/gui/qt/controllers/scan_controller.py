"""Background scan worker for Qt backend — pure, no widgets, runs off GUI thread.

Owns the thread-side logic for a single scan: invoke
``scanner.scan_and_process_dynamic`` and emit signals with the result (or error).
The main thread connects to these signals to update the UI.

Splitting this out lets us unit-test the worker without instantiating
Qt. The MainWindow still owns the controller and signal connections.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from profiles.core.config import service as config_service
from profiles.core.config.models import AppConfig
from profiles.core.processing.scanner import scan_and_process_dynamic

# pylint: disable=too-many-arguments


class ScanWorker(QObject):
    """Worker object that performs scans off the GUI thread.

    Signals:
        finished: Emitted with the list of ScannedFileDynamic on successful completion.
        failed: Emitted with an error message when the scan fails.
    """

    finished = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        directories: list[str],
        extension: str,
        filter_text: str,
        recursive: bool,
        config: AppConfig,
        directory_label: str,
        logger: logging.Logger,
    ) -> None:
        """Initialize the scan worker.

        Args:
            directories: List of directories to scan.
            extension: Extension filter expression.
            filter_text: Keyword filter expression.
            recursive: Whether to recurse into subdirectories.
            config: Application configuration (for exclude lists).
            directory_label: Label of the selected directory (for config lookup).
            logger: Logger for diagnostics.
        """
        super().__init__()
        self._directories = directories
        self._extension = extension
        self._filter_text = filter_text
        self._recursive = recursive
        self._config = config
        self._directory_label = directory_label
        self._logger = logger

    @Slot()
    def run(self) -> None:
        """Execute the scan off the GUI thread and emit signals.

        This method is called in the worker thread context. It performs
        the actual scan and emits either finished() with results or
        failed() with an error message.
        """
        try:
            active = config_service.find_active_config(self._config, self._directory_label)
            exclude_files = (
                active.search_exclude_files
                if active is not None
                else self._config.search_exclude_files
            )
            items = scan_and_process_dynamic(
                self._directories,
                extension=self._extension,
                filter_text=self._filter_text,
                recursive=self._recursive,
                exclude_dirs=self._config.search_exclude_dirs,
                exclude_files=exclude_files,
                column_names=self._config.column_names,
                columns=self._config.columns,
                config=self._config,
            )
            self.finished.emit(items)
        except Exception as exc:  # pylint: disable=broad-except
            from profiles.core.telemetry import events

            events.scan_failed(self._logger, directory="background", error=str(exc))
            self.failed.emit(str(exc))


# pylint: enable=too-many-arguments


class ScanController:
    """Controller managing the scan worker lifecycle.

    This class owns the ScanWorker instance and manages thread operations.
    It connects worker signals to GUI slots and provides start/stop methods.
    """

    def __init__(self, config: AppConfig, logger: logging.Logger) -> None:
        """Initialize the scan controller.

        Args:
            config: Application configuration.
            logger: Logger for diagnostics.
        """
        self._config = config
        self._logger = logger
        self._worker: ScanWorker | None = None
        self._thread: Any | None = None

    def start_scan(
        self,
        directories: list[str],
        extension: str,
        filter_text: str,
        recursive: bool,
        directory_label: str,
        on_finished: object,
        on_failed: object,
    ) -> None:
        """Start an asynchronous scan.

        Args:
            directories: List of directories to scan.
            extension: Extension filter expression.
            filter_text: Keyword filter expression.
            recursive: Whether to recurse into subdirectories.
            directory_label: Label of the selected directory.
            on_finished: Slot to connect to worker.finished signal.
            on_failed: Slot to connect to worker.failed signal.
        """
        # Stop any existing scan
        self.stop_scan()

        # Create worker
        self._worker = ScanWorker(
            directories=directories,
            extension=extension,
            filter_text=filter_text,
            recursive=recursive,
            config=self._config,
            directory_label=directory_label,
            logger=self._logger,
        )

        # Connect signals
        self._worker.finished.connect(on_finished)
        self._worker.failed.connect(on_failed)

        # Move to thread and start
        from PySide6.QtCore import QThread

        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def stop_scan(self) -> None:
        """Stop the current scan safely with timeout.

        This method attempts to gracefully stop the worker thread.
        If the thread doesn't quit within 5 seconds, it's terminated.
        """
        # Guard against accessing deleted C++ objects
        if self._thread is None:
            return
        try:
            if not self._thread.isRunning():
                return
            # Request quit with timeout - force terminate if timeout exceeded
            if not self._thread.wait(5000):
                # Force termination if timeout exceeded
                self._thread.terminate()
                self._thread.wait(1000)
        except RuntimeError:
            # Thread object already deleted - ignore
            pass

        # Clean up worker
        if self._worker is not None:
            try:
                self._worker.deleteLater()
            except RuntimeError:
                # Worker object already deleted - ignore
                pass
            self._worker = None

        self._thread = None
