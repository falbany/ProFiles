"""Chunked file list worker for PySide6 backend.

Implements chunked insertion to match Tkinter behavior:
- Initial paint of 200 items
- Then 1000-item chunks to avoid UI freeze on large lists (10,000+ items)

Uses QThread worker that emits chunks via signals to main thread for model updates.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from profiles.core.processing.scanner import ScannedFileDynamic

# Chunk sizes matching Tkinter behavior
_INITIAL_PAINT_SIZE = 200
_CHUNK_SIZE = 1000


class ChunkedFileListWorker(QObject):
    """Worker that emits file list chunks for UI insertion.

    This worker takes a complete list of ScannedFileDynamic items and emits
    them in chunks to avoid blocking the UI thread on large lists.

    Signals:
        chunk_ready: Emitted with a list of items for each chunk (max 1000 items)
        finished: Emitted when all chunks have been sent
        progress: Emitted with (current_count, total_count) for progress indicator
    """

    chunk_ready = Signal(list)
    finished = Signal()
    progress = Signal(int, int)

    def __init__(
        self,
        items: list[ScannedFileDynamic],
        column_names: tuple[str, ...],
    ) -> None:
        """Initialize the chunked file list worker.

        Args:
            items: Complete list of scanned file items.
            column_names: Column names for building table rows.
        """
        super().__init__()
        self._items = items
        self._column_names = column_names
        self._cancelled = False

    @Slot()
    def run(self) -> None:
        """Emit chunks of items to the main thread.

        First emits initial paint of 200 items, then emits remaining
        items in chunks of 1000. Emits progress updates after each chunk.
        """
        total = len(self._items)
        offset = 0

        # Initial paint: first 200 items
        initial_end = min(_INITIAL_PAINT_SIZE, total)
        if initial_end > 0:
            chunk = self._items[:initial_end]
            self.chunk_ready.emit(chunk)
            self.progress.emit(initial_end, total)
            offset = initial_end

        # Remaining chunks of 1000 items
        while offset < total and not self._cancelled:
            chunk_end = min(offset + _CHUNK_SIZE, total)
            chunk = self._items[offset:chunk_end]
            self.chunk_ready.emit(chunk)
            self.progress.emit(chunk_end, total)
            offset = chunk_end

        self.finished.emit()

    @Slot()
    def cancel(self) -> None:
        """Request cancellation of chunk emission."""
        self._cancelled = True


class ChunkedFileListController:
    """Controller managing the chunked file list worker lifecycle.

    This class owns the ChunkedFileListWorker instance and manages thread
    operations for chunked file list insertion.
    """

    def __init__(self) -> None:
        """Initialize the controller."""
        self._worker: ChunkedFileListWorker | None = None
        self._thread: QThread | None = None

    def start_chunked_insert(
        self,
        items: list[ScannedFileDynamic],
        column_names: tuple[str, ...],
        on_chunk_ready: Any,
        on_finished: Any,
        on_progress: Any,
    ) -> None:
        """Start asynchronous chunked file list insertion.

        Args:
            items: Complete list of scanned file items.
            column_names: Column names for building table rows.
            on_chunk_ready: Slot to connect to worker.chunk_ready signal.
            on_finished: Slot to connect to worker.finished signal.
            on_progress: Slot to connect to worker.progress signal.
        """
        # Stop any existing insertion
        self.stop_chunked_insert()

        # Create worker
        self._worker = ChunkedFileListWorker(items, column_names)

        # Connect signals
        self._worker.chunk_ready.connect(on_chunk_ready)
        self._worker.finished.connect(on_finished)
        self._worker.progress.connect(on_progress)

        # Move to thread and start
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def stop_chunked_insert(self) -> None:
        """Stop the current chunked insertion safely with timeout."""
        if self._thread is None:
            return
        
        # Check if thread is running (handle deleted C++ objects)
        try:
            if not self._thread.isRunning():
                return
        except RuntimeError:
            # C++ object already deleted
            self._thread = None
            return

        # Request cancel
        if self._worker is not None:
            self._worker.cancel()

        # Wait with timeout
        if not self._thread.wait(5000):
            self._thread.terminate()
            self._thread.wait(1000)

        # Clean up worker
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

        self._thread = None
