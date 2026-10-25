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

Coverage target: **85%** enforced by `--cov-fail-under` (aim for 90%+ per module); the deprecated `profiles/gui/` package is omitted (see `.coveragerc`).

## Test File Structure
Test files mirror the `src/profiles/` tree 1:1 — each source module has a matching `test_<module>.py` at the mirrored path, and supplementary files for the same module are named `test_<module>_<topic>.py`. Every test directory is a package (`__init__.py`), mirroring `src/profiles`.

The authoritative layout — full tree, supplements, documented cross-cutting exceptions (`tests/characterization/`, `tests/packaging/`, `tests/server/test_barcode_integration.py`, `test_public_api.py`), known coverage gaps, and the deprecated-Tkinter skip — is maintained in **[AGENTS.md](AGENTS.md) → Test File Organization**.

Highlights:

| File | Source Module | Focus Areas |
|---|---|---|
| tests/test_app.py | profiles.app | ProFileApp, main(), init_default_config |
| tests/test_app_*.py | profiles.app | supplements: backend selection, launch resolution, log path, no-tkinter run, deprecated tk lifecycle |
| tests/test_config.py | profiles.config | shim re-exports (ColumnConfiguration, …) |
| tests/core/… | profiles.core.* | actions, config (models/reader/schema/service/loader/matcher/validator/template/inheritance/yaml_io), environment (system/execution/matcher/render/interactions/message_dialog/workflow), processing (scanner/file_classifier/file_metadata/column_extractor), telemetry (diagnostics/events/metrics) |
| tests/desktop/test_lifecycle.py | profiles.desktop.lifecycle | port discovery, background server lifecycle |
| tests/gui/** | profiles.gui.* | **skipped** — deprecated Tkinter frontend (see `tests/gui/conftest.py`) |
| tests/launch/test_{context,creation,resolution}.py | profiles.launch.* | launch context detection, shortcut creation, resolution |
| tests/packaging/ | (cross-cutting) | entry-point stub, packaging dependency rules, ProFiles.pyw stub |
| tests/server/test_app.py | profiles.server.app | FastAPI factory, client connection telemetry |
| tests/server/routes/test_*.py | profiles.server.routes.* | actions/config/fs/logs/scan/system/workflow endpoints |
| tests/utils/test_*.py | profiles.utils.* | file_utils, network, search_parser, shortcut |
| tests/web/test_build{,_hook}.py | profiles.web.* | web build CLI and Briefcase build hook |
| conftest.py | shared infrastructure | os.startfile polyfill |

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
tests/conftest.py provides shared infrastructure auto-inherited by all subdirs: it polyfills `os.startfile` on non-Windows so launch tests can mock it, and provides the `sample_config_path` / `empty_config_path` fixtures. `tests/gui/conftest.py` applies the Tkinter-deprecation skip to everything under `tests/gui/`. Use the built-in `tmp_path` fixture for temporary file setups.

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
