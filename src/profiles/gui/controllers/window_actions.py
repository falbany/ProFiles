"""Top-level window actions: open config, open log, restart.

These actions use :mod:`profiles.core.actions` for the business logic and
:messsagebox for user-facing dialogs. Kept separate from MainWindow to
keep the class focused on widget orchestration.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox

from profiles.core import actions
from profiles.core.config.models import AppConfig
from profiles.core.telemetry import events

__all__ = ["WindowActions"]


class WindowActions:
    """Top-level window actions for config, log, and restart."""

    def __init__(
        self,
        config: AppConfig,
        logger: logging.Logger,
        root_destroy: object,
    ) -> None:
        self._config = config
        self._logger = logger
        self._root_destroy = root_destroy  # () -> None

    def open_config(self) -> None:
        """Open the configuration file with the default text editor.

        When the ``.profiles`` file does not exist, offer to generate a
        documented starter file in the current working directory.
        """
        config_path = self._config.config_path

        if not config_path.exists():
            cwd_label = str(Path.cwd())
            prompt = (
                f"No configuration file was found at:\n{config_path}\n\n"
                "Would you like to generate a starter .profiles file in the\n"
                f"current working directory ({cwd_label})?\n\n"
                "The starter is fully commented and ready to edit."
            )
            if not messagebox.askyesno(
                "Configuration File Missing",
                prompt,
            ):
                return

            write_result = actions.write_starter_config(
                config_path,
                logger=self._logger,
            )
            if write_result.status != actions.ActionStatus.SUCCESS:
                messagebox.showerror(
                    write_result.message,
                    write_result.message,
                )
                return

            messagebox.showinfo(
                "Starter Configuration Created",
                write_result.message,
            )

        result = actions.open_config_file(
            config_path,
            logger=self._logger,
        )
        if result.status != actions.ActionStatus.SUCCESS:
            messagebox.showerror(result.message, result.message)

    def open_log(self, log_path: Path) -> None:
        """Open the log file with the default text editor."""
        result = actions.open_log_file(log_path, logger=self._logger)
        if result.status != actions.ActionStatus.SUCCESS:
            messagebox.showerror(result.message, result.message)

    def restart(self) -> None:
        """Destroy the current window and launch a fresh instance."""
        events.app_restarting(self._logger)
        self._root_destroy()

        python_executable = sys.executable
        try:
            subprocess.Popen([str(python_executable), "-m", "profiles"])
            events.app_launched(
                self._logger, command=f"{python_executable} -m profiles"
            )
        except OSError as exc:
            events.app_gui_failed(self._logger, error=f"restart failed: {exc}")
            messagebox.showerror(
                "Restart Failed",
                f"Could not automatically restart the application.\n\n"
                f"Error: {exc}\n\n"
                "Please restart manually by running ProFiles again.",
            )
