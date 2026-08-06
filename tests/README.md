# ProFiles Test Suite
Comprehensive pytest-based test suite for the ProFiles application.

## Prerequisites

- Python 3.11+
- [pytest](https://docs.pytest.org/) >= 7.0
- [pytest-cov](https://pytest-cov.readthedocs.io/) (for coverage reports)
- [pytest-mock](https://pytest-mock.readthedocs.io/) (for mocking platform-specific calls)

Install test dependencies:

```bash
pip install pytest pytest-cov pytest-mock
```

## Running Tests
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file (mirrored paths)
pytest tests/core/config/test_loader.py -v
pytest tests/gui/test_main_window.py -v
pytest tests/utils/test_search_parser.py -v

# Run a specific test class
pytest tests/core/config/test_loader.py::TestLoadConfig -v

# Run all tests for a source sub-package
pytest tests/core/config/ -v
pytest tests/gui/ -v
pytest tests/utils/ -v
```

## Coverage

```bash
# Run all tests with coverage report
pytest --cov=profiles --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=profiles --cov-report=html

# Run with coverage for a specific module
pytest --cov=profiles.config -v
```

Coverage target: **90%+** statement coverage across all modules.
## Test File Structure
Test files mirror the `src/profiles/` tree 1:1 — each source module has a matching `test_<module>.py` at the mirrored path.

| File | Source Module | Focus Areas |
|---|---|---|
| tests/test_app.py | profiles.app | ProFileApp, main(), init_default_config, ShortcutsDialog |
| tests/core/test_actions.py | profiles.core.actions | launch_selected_file, open_config_file, write_starter_config, clear_file, ActionResult |
| tests/core/config/test_models.py | profiles.core.config.models | AppConfig, MachineConfiguration, HookSpec dataclasses |
| tests/core/config/test_service.py | profiles.core.config.service | find_configuration_by_hostname, auto_select_directory, merge_config_overrides |
| tests/core/config/test_loader.py | profiles.core.config.loader | load_config, propose_config_creation, default column behavior |
| tests/core/config/test_reader.py | profiles.core.config.reader | ConfigReader.load, ConfigReader properties, hook reading |
| tests/core/config/io/test_ini_primitives.py | profiles.core.config.io.ini_primitives | parse_bool, find_config_file |
| tests/core/config/io/test_writer.py | profiles.core.config.io.writer | save_config_bool, save_config_str |
| tests/core/environment/test_system.py | profiles.core.environment.system | SystemInfo, collect_system_info, apply_source_to_logger |
| tests/core/environment/test_execution.py | profiles.core.environment.execution | parse_hook_entries, run_hooks_for_file, _substitute_tokens |
| tests/core/processing/test_scanner.py | profiles.core.processing.scanner | scan_and_process, ScannedFile, ScannedFileDynamic, is_simple_extension |
| tests/core/processing/test_file_classifier.py | profiles.core.processing.file_classifier | get_file_info, extract_version, directory_exists, ensure_trailing_separator |
| tests/core/processing/test_column_extractor.py | profiles.core.processing.column_extractor | ColumnRule, ColumnExtractor |
| tests/core/telemetry/test_diagnostics.py | profiles.core.telemetry.diagnostics | LoggerFactory, SourceFilter, configure_logger, get_logger |
| tests/gui/test_main_window.py | profiles.gui.main_window | MainWindow, _hex_luminance, _restart_application, context menu, key bindings |
| tests/gui/test_ui.py | profiles.gui.ui | MainWindowUI, build, progress bar |
| tests/gui/test_styles.py | profiles.gui.styles | configure_styles, ToolTip, current_theme |
| tests/gui/test_theme.py | profiles.gui.theme | Md3Theme, DARK_THEME, LIGHT_THEME, apply_theme, contrast ratio |
| tests/gui/test_search_bar.py | profiles.gui.search_bar | SearchBar, widget construction, bindings |
| tests/gui/test_status_bar.py | profiles.gui.status_bar | StatusBar, callbacks, theme label |
| tests/utils/test_file_utils.py | profiles.utils.file_utils | scan_directory, _matches_extension, launch_file, open_file_explorer, hash_file |
| tests/utils/test_network.py | profiles.utils.network | get_hostname, get_username, get_local_ip |
| tests/utils/test_search_parser.py | profiles.utils.search_parser | tokenize, split_or_groups, match_filter |
| conftest.py | shared infrastructure | os.startfile polyfill, requires_tkinter marker |

## Writing Tests
### Conventions
All test files follow these conventions:

```python
"""Test module docstring."""

from __future__ import annotations

import pytest

from profiles.module import function_under_test


class TestFeature:
    """Group tests by feature."""

    def test_scenario_description(self) -> None:
        """Docstring describing the scenario."""
        assert function_under_test(args) == expected_result
```

- `from __future__ import annotations` at the top of every test file
- Class-based organization grouping tests by function/feature
- Type hints and docstrings on every test function
- Descriptive test names following `test_<feature>_<scenario>` pattern
- Fixtures from `conftest.py` for shared setup (`tmp_path`, `sample_files`, etc.)

### Mocking Platform-Specific Calls
ProFiles uses `os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux.
Mock the platform-appropriate call in tests:

```python
def test_launch(mocker):
    mock_startfile = mocker.patch("os.startfile")
    result = launch_file(path)
    assert result is True
    mock_startfile.assert_called_once()

# Or for macOS / Linux coverage:
def test_launch_macos(mocker):
    mocker.patch("os.startfile", create=True)
    mock_run = mocker.patch("subprocess.run")
    mocker.patch("sys.platform", "darwin")
    launch_file(path)
    mock_run.assert_called_once()
```

### Fixtures Reference
tests/conftest.py provides shared infrastructure auto-inherited by all subdirs: it polyfills `os.startfile` on non-Windows so launch tests can mock it, and registers the `requires_tkinter` pytest marker. Note: the named fixture functions `sample_profile_conf`, `sample_files`, `config_with_profile` are currently unused — slated for cleanup. Use the built-in `tmp_path` fixture for temporary file setups.

### CI/CD Integration
```yaml
# GitLab CI example
test:
  script:
    - pip install pytest pytest-cov pytest-mock
    - pytest --cov=profiles --cov-report=term-missing --junitxml=report.xml
  artifacts:
    reports:
      junit: report.xml
```
