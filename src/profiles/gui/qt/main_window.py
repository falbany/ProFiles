"""Qt main window shell for PySide6 backend."""

from PySide6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):
    """Main window shell for Qt backend."""

    def __init__(self) -> None:
        super().__init__()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the main window UI."""
        self.setWindowTitle("ProFiles")
        self.resize(1024, 768)

    def run(self) -> int:
        """Run the application.

        Returns:
            Application exit code.
        """
        self.show()
        from PySide6.QtWidgets import QApplication

        return QApplication.instance().exec() if QApplication.instance() else 0
