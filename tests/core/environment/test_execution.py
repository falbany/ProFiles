"""Tests for profiles.core.environment.execution — parse_hook_entries, run_hooks_for_file, _substitute_tokens."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from profiles.core.config.models import AppConfig, HookSpec
from profiles.core.environment.execution import (
    HookOutcome,
    _build_argv,
    _spawn_after_hook,
    _substitute_tokens,
    parse_hook_entries,
    run_blocking_hook,
    run_hooks_for_file,
    spawn_background_hook,
)


class TestParseHookEntries:
    """parse_hook_entries() splitting and coercion."""

    def test_empty_value_yields_empty_tuple(self) -> None:
        """An empty raw value parses to an empty tuple."""
        assert not parse_hook_entries("")

    def test_invalid_phase_defaults_to_before(self) -> None:
        """An unknown phase is coerced to 'before' inside HookSpec."""
        entries = parse_hook_entries("wrong|cmd.exe")
        assert entries == (HookSpec(when="before", template="cmd.exe"),)

    def test_comma_inside_quotes_preserved(self) -> None:
        """Commas inside double quotes do not split entries."""
        entries = parse_hook_entries('before|"C:/path, name/x.exe"')
        assert entries == (HookSpec(when="before", template='"C:/path, name/x.exe"'),)

    def test_multiple_comma_separated(self) -> None:
        """Multiple comma-separated entries each get their own phase."""
        entries = parse_hook_entries("before|a, after|b, abort|c")
        assert len(entries) == 3
        assert [hook.when for hook in entries] == ["before", "after", "abort"]

    def test_no_pipe_defaults_to_before(self) -> None:
        """An entry without a pipe defaults to the before phase."""
        assert parse_hook_entries("just-a-command") == (
            HookSpec(when="before", template="just-a-command"),
        )

    def test_empty_template_entries_dropped(self) -> None:
        """Entries with empty templates are dropped."""
        assert parse_hook_entries(",foo,,") == (HookSpec(when="before", template="foo"),)

    def test_first_pipe_wins(self) -> None:
        """Only the first pipe separates phase from template."""
        hook = parse_hook_entries("before|cmd|extra|pipes")[0]
        assert hook.when == "before"
        assert hook.template == "cmd|extra|pipes"


def _make_config(*hooks: HookSpec, failmode: str = "warn") -> AppConfig:
    """Build an AppConfig with hooks registered under the ``.mttx`` key."""
    return AppConfig(
        launch_hooks={".mttx": hooks},
        launch_hook_failmode=failmode,
    )


class TestRunHooksForFile:
    """Hook pipeline decisions for a file being launched."""

    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_no_matching_extension_returns_continue(
        self, mock_run: MagicMock, _mock_spawn: MagicMock
    ) -> None:
        """A file with no registered extension resolves to CONTINUE."""
        result = run_hooks_for_file(Path("/tmp/x.txt"), AppConfig())

        assert result is HookOutcome.CONTINUE
        mock_run.assert_not_called()

    @pytest.mark.parametrize("failmode", ["warn", "abort", "skip"])
    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_abort_nonzero_returns_abort_regardless_of_failmode(
        self, mock_run: MagicMock, _mock_spawn: MagicMock, failmode: str
    ) -> None:
        """A failing abort hook returns ABORT under every failmode."""
        mock_run.return_value = 1

        result = run_hooks_for_file(
            Path("/tmp/x.mttx"),
            _make_config(HookSpec(when="abort", template="x"), failmode=failmode),
        )

        assert result is HookOutcome.ABORT

    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_abort_zero_returns_continue(self, mock_run: MagicMock, _mock_spawn: MagicMock) -> None:
        """A succeeding abort hook lets the pipeline continue."""
        mock_run.return_value = 0

        result = run_hooks_for_file(
            Path("/tmp/x.mttx"),
            _make_config(HookSpec(when="abort", template="x")),
        )

        assert result is HookOutcome.CONTINUE

    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_before_nonzero_with_warn_returns_continue(
        self, mock_run: MagicMock, _mock_spawn: MagicMock
    ) -> None:
        """A failing before hook with warn failmode continues."""
        mock_run.return_value = 1

        result = run_hooks_for_file(
            Path("/tmp/x.mttx"),
            _make_config(HookSpec(when="before", template="x")),
        )

        assert result is HookOutcome.CONTINUE
    @patch("profiles.core.environment.execution.confirm_dialog")
    def test_confirmation_hook_success(self, mock_confirm: MagicMock) -> None:
        """User confirms -> returns CONTINUE."""
        mock_confirm.return_value = True
        config = _make_config(HookSpec(when="confirm", template="Run it?"))

        result = run_hooks_for_file(Path("/tmp/x.mttx"), config)

        assert result is HookOutcome.CONTINUE
        mock_confirm.assert_called_once_with("Run it?", title="Launch Confirmation")

    @patch("profiles.core.environment.execution.confirm_dialog")
    def test_confirmation_hook_cancel(self, mock_confirm: MagicMock) -> None:
        """User cancels -> returns ABORT."""
        mock_confirm.return_value = False
        config = _make_config(HookSpec(when="confirm", template="Run it?"))

        result = run_hooks_for_file(Path("/tmp/x.mttx"), config)

        assert result is HookOutcome.ABORT

    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_sequential_chain_aborts_on_middle_failure(self, mock_run: MagicMock) -> None:
        """Required hook failure stops the pipeline under failmode=abort."""
        mock_run.side_effect = [0, 1]  # Success then failure
        config = _make_config(
            HookSpec(template="cmd1", requires_success=True),
            HookSpec(template="cmd2", requires_success=True),
            failmode="abort",
        )

        result = run_hooks_for_file(Path("/tmp/x.mttx"), config)

        assert result is HookOutcome.ABORT
        assert mock_run.call_count == 2

    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_sequential_chain_continues_if_optional_fails(self, mock_run: MagicMock) -> None:
        """Optional hook failure (requires_success=False) allows pipeline to continue."""
        mock_run.side_effect = [1, 0]
        config = _make_config(
            HookSpec(template="optional", requires_success=False),
            HookSpec(template="required", requires_success=True),
            failmode="abort",
        )

        result = run_hooks_for_file(Path("/tmp/x.mttx"), config)

        assert result is HookOutcome.CONTINUE
        assert mock_run.call_count == 2
    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_before_nonzero_with_abort_returns_abort(
        self, mock_run: MagicMock, _mock_spawn: MagicMock
    ) -> None:
        """A failing before hook with abort failmode aborts."""
        mock_run.return_value = 1

        result = run_hooks_for_file(
            Path("/tmp/x.mttx"),
            _make_config(HookSpec(when="before", template="x"), failmode="abort"),
        )

        assert result is HookOutcome.ABORT

    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_before_nonzero_with_skip_returns_skip(
        self, mock_run: MagicMock, _mock_spawn: MagicMock
    ) -> None:
        """A failing before hook with skip failmode skips the OS launch."""
        mock_run.return_value = 1

        result = run_hooks_for_file(
            Path("/tmp/x.mttx"),
            _make_config(HookSpec(when="before", template="x"), failmode="skip"),
        )

        assert result is HookOutcome.SKIP

    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_instead_zero_returns_skip(self, mock_run: MagicMock, _mock_spawn: MagicMock) -> None:
        """A succeeding instead hook replaces the OS launch."""
        mock_run.return_value = 0

        result = run_hooks_for_file(
            Path("/tmp/x.mttx"),
            _make_config(HookSpec(when="instead", template="x")),
        )

        assert result is HookOutcome.SKIP

    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_instead_nonzero_with_warn_returns_continue(
        self, mock_run: MagicMock, _mock_spawn: MagicMock
    ) -> None:
        """A failing instead hook with warn failmode falls back to the OS."""
        mock_run.return_value = 1

        result = run_hooks_for_file(
            Path("/tmp/x.mttx"),
            _make_config(HookSpec(when="instead", template="x")),
        )

        assert result is HookOutcome.CONTINUE

    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_timeout_raises_then_failmode_abort_returns_abort(
        self, mock_run: MagicMock, _mock_spawn: MagicMock
    ) -> None:
        """A timeout with abort failmode aborts the launch."""
        mock_run.side_effect = TimeoutError("boom")

        result = run_hooks_for_file(
            Path("/tmp/x.mttx"),
            _make_config(HookSpec(when="before", template="x"), failmode="abort"),
        )

        assert result is HookOutcome.ABORT

    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_timeout_raises_then_failmode_warn_returns_continue(
        self, mock_run: MagicMock, _mock_spawn: MagicMock
    ) -> None:
        """A timeout with warn failmode continues the launch."""
        mock_run.side_effect = TimeoutError("boom")

        result = run_hooks_for_file(
            Path("/tmp/x.mttx"),
            _make_config(HookSpec(when="before", template="x")),
        )

        assert result is HookOutcome.CONTINUE

    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_after_hook_spawns_on_continue(
        self, _mock_run: MagicMock, mock_spawn: MagicMock
    ) -> None:
        """An after hook spawns in the background when the pipeline continues."""
        file_path = Path("/tmp/x.mttx")

        result = run_hooks_for_file(
            file_path,
            _make_config(HookSpec(when="after", template="x")),
        )

        assert result is HookOutcome.CONTINUE
        mock_spawn.assert_called_once_with("x", file_path)

    @patch("profiles.core.environment.execution.spawn_background_hook")
    @patch("profiles.core.environment.execution.run_blocking_hook")
    def test_after_hook_not_spawned_on_abort(
        self, mock_run: MagicMock, mock_spawn: MagicMock
    ) -> None:
        """After hooks do not spawn when an earlier hook aborts."""
        mock_run.return_value = 1

        result = run_hooks_for_file(
            Path("/tmp/x.mttx"),
            _make_config(
                HookSpec(when="before", template="x"),
                HookSpec(when="after", template="x"),
                failmode="abort",
            ),
        )

        assert result is HookOutcome.ABORT
        mock_spawn.assert_not_called()


class TestTokenSubstitution:
    """Token replacement in hook templates."""

    def test_path_token_resolves(self) -> None:
        """{path} resolves to the resolved file path."""
        result = _substitute_tokens("{path}", Path("/tmp/foo.mttx"))
        assert result.endswith("foo.mttx")

    def test_dir_token_resolves_to_parent(self) -> None:
        """{dir} resolves to the resolved parent directory."""
        result = _substitute_tokens("{dir}", Path("/tmp/foo.mttx"))
        assert result == str(Path("/tmp/foo.mttx").parent.resolve())

    def test_name_token(self) -> None:
        """{name} resolves to the file name."""
        assert _substitute_tokens("{name}", Path("/tmp/foo.mttx")) == "foo.mttx"

    def test_ext_token(self) -> None:
        """{ext} resolves to the file extension."""
        assert _substitute_tokens("{ext}", Path("/tmp/foo.mttx")) == ".mttx"

    def test_unknown_token_preserved(self) -> None:
        """Unknown tokens are left untouched."""
        result = _substitute_tokens("{unknown}", Path("/tmp/foo.mttx"))
        assert result == "{unknown}"

    def test_combined_template(self) -> None:
        """Multiple tokens in one template are all substituted."""
        result = _substitute_tokens("{name} in {dir}", Path("/tmp/foo.mttx"))
        assert "foo.mttx" in result
        assert str(Path("/tmp/foo.mttx").parent.resolve()) in result

    def test_cwd_and_date_and_hostname_tokens(self) -> None:
        """{cwd}, {date} and {hostname} are substituted with runtime values."""
        result = _substitute_tokens(
            "{cwd}|{date}|{hostname}", Path("/tmp/foo.mttx")
        )
        parts = result.split("|")
        assert parts[0] == str(Path.cwd().resolve())
        assert len(parts[1]) == 10  # ISO date yyyy-mm-dd
        assert parts[2]  # non-empty hostname


class TestBuildArgv:
    """_build_argv token-substitutes then shell-splits."""

    def test_simple_command(self) -> None:
        """A plain template becomes a single-element argv."""
        assert _build_argv("echo", Path("/tmp/foo.mttx")) == ["echo"]

    def test_substitutes_tokens_before_split(self) -> None:
        """Tokens are replaced before shell splitting."""
        args = _build_argv("cp {path} {dir}/backup", Path("/tmp/foo.mttx"))
        assert args[0] == "cp"
        assert args[1] == str(Path("/tmp/foo.mttx").resolve())
        assert args[2] == f"{Path('/tmp/foo.mttx').parent.resolve()}/backup"

    def test_unbalanced_quotes_raise_value_error(self) -> None:
        """An unterminated quote raises ValueError from shlex."""
        with pytest.raises(ValueError):
            _build_argv('echo "unclosed', Path("/tmp/foo.mttx"))


class TestRunBlockingHook:
    """run_blocking_hook executes synchronously and returns the returncode."""

    @patch("profiles.core.environment.execution.subprocess.run")
    def test_returns_returncode(self, mock_run: MagicMock) -> None:
        """The subprocess returncode is returned as-is."""
        mock_run.return_value = MagicMock(returncode=7)
        result = run_blocking_hook("some cmd", Path("/tmp/x.mttx"), timeout=5)
        assert result == 7
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 5
        assert kwargs["shell"] is False

    @patch("profiles.core.environment.execution.subprocess.run")
    def test_timeout_raises_timeout_error(self, mock_run: MagicMock) -> None:
        """A subprocess.TimeoutExpired is surfaced as TimeoutError."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="x", timeout=5)
        with pytest.raises(TimeoutError):
            run_blocking_hook("slow cmd", Path("/tmp/x.mttx"), timeout=5)


class TestSpawnBackgroundHook:
    """spawn_background_hook is fire-and-forget and never raises."""

    @patch("profiles.core.environment.execution.subprocess.Popen")
    def test_spawns_detached_process(self, mock_popen: MagicMock) -> None:
        """Popen is invoked with DEVNULL streams."""
        spawn_background_hook("notify {name}", Path("/tmp/x.mttx"))
        mock_popen.assert_called_once()
        _, kwargs = mock_popen.call_args
        assert kwargs["stdout"] is subprocess.DEVNULL
        assert kwargs["stderr"] is subprocess.DEVNULL

    @patch("profiles.core.environment.execution.subprocess.Popen")
    def test_file_not_found_swallowed(self, mock_popen: MagicMock) -> None:
        """A missing hook binary is swallowed, not raised."""
        mock_popen.side_effect = FileNotFoundError()
        # Must not raise
        spawn_background_hook("missing-bin", Path("/tmp/x.mttx"))

    @patch("profiles.core.environment.execution.subprocess.Popen")
    def test_oserror_swallowed(self, mock_popen: MagicMock) -> None:
        """Other OS-level spawn failures are swallowed."""
        mock_popen.side_effect = OSError("denied")
        # Must not raise
        spawn_background_hook("denied-bin", Path("/tmp/x.mttx"))

    @patch("profiles.core.environment.execution.subprocess.Popen")
    def test_unbalanced_quotes_propagate_value_error(
        self, mock_popen: MagicMock
    ) -> None:
        """A ValueError from shlex is not swallowed by Popen handling."""
        with pytest.raises(ValueError):
            spawn_background_hook('echo "oops', Path("/tmp/x.mttx"))


class TestSpawnAfterHook:
    """_spawn_after_hook wraps spawn_background_hook with logging."""

    @patch("profiles.core.environment.execution.spawn_background_hook")
    def test_logs_failure(self, mock_spawn: MagicMock, caplog) -> None:  # noqa: ANN001
        """Unexpected failures are logged as warnings."""
        mock_spawn.side_effect = OSError("boom")
        with caplog.at_level(logging.WARNING, logger="profiles"):
            _spawn_after_hook(
                HookSpec(when="after", template="x"),
                Path("/tmp/x.mttx"),
                logging.getLogger("profiles"),
            )
        assert any("after hook failed to spawn" in r.message for r in caplog.records)
