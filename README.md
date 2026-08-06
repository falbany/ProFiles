<div align="center">
  <h1>ProFiles</h1>

  <p><strong>The Highly Configurable, Multi-Purpose File Launcher</strong></p>

  ![ProFiles_banner](img/ProFiles_banner.png)

  [![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
  [![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
  [![Pylint](https://img.shields.io/badge/linting-pylint-09A64D.svg)](https://github.com/pylint-dev/pylint)
  [![License](https://img.shields.io/badge/license-MIT-brightgreen)](./LICENCE)
  [![GitHub](https://img.shields.io/badge/GitHub-falbany/ProFiles-181717?logo=github)](https://github.com/falbany/ProFiles)
</div>

---

**ProFiles** adapts to any file-based workflow through flexible configuration without touching code. Browse directories, filter with Google-style operators, extract metadata from filenames, and launch files via OS associations or custom arguments.

<details>
<summary><b>Table of Contents</b></summary>

- [✨ Key Features](#-key-features)
  - [🔍 Smart Search \& Browse](#-smart-search--browse)
  - [🚀 Execute \& Automate](#-execute--automate)
  - [⚙️ Auto-Configuration](#️-auto-configuration)
- [🚀 Installation](#-installation)
  - [Quick Install (Recommended)](#quick-install-recommended)
  - [Manual Install](#manual-install)
  - [Desktop Shortcut](#desktop-shortcut)
- [💻 Usage](#-usage)
  - [GUI Mode](#gui-mode)
  - [CLI / Headless Mode](#cli--headless-mode)
- [🛠 Configuration](#-configuration)
- [🏗 Architecture](#-architecture)
- [👨‍💻 Development](#-development)
- [📄 License \& Support](#-license--support)

</details>

## ✨ Key Features

### 🔍 Smart Search & Browse
* **Google-Style Operators**: Implicit AND, `OR`, NOT (`-`), exact phrase (`"..."`).
* **Dynamic Columns**: Extract metadata (version, device, revision) from filenames using regex rules.
* **Parallel Recursion**: High-performance background thread scanning keeps the UI responsive.
* **Glob Exclusion**: Skip noisy directories (e.g., `node_modules`, `.venv`) and filter out files matching glob patterns (e.g., `*backup*`, `~$*`).

### 🚀 Execute & Automate
* **One-Click Launch**: Native OS execution (Windows `os.startfile`, macOS `open`, Linux `xdg-open`).
* **Custom CLI Arguments**: Right-click to launch with custom arguments, remembered per row.
* **Headless Mode**: Trigger file launches via CLI for CI/CD or scripts.
* **File Operations**: Bulk launch, copy path, hash verification (SHA-256), and safe deletion.

### ⚙️ Auto-Configuration
* **Zero-Touch Deployment**: Detects hostname to auto-select matching configurations for multi-station setups.
* **Visual Formatting**: Rules-based row coloring with automatic contrast adjustment.
* **No-Config Fallback**: Sensible defaults allow immediate use without a `.profiles` file.

## 🚀 Installation

Requires **Python 3.11+**. Minimal dependencies: `sv-ttk` (Material Design 3 theme), `darkdetect` (system theme detection).

### Quick Install (Recommended)
```bash
python install.py
```
*Runs an interactive wizard that creates an isolated `.venv` and installs the package.*

### Manual Install
```bash
git clone https://github.com/falbany/ProFiles.git
cd ProFiles
pip install .
```

### Desktop Shortcut
Run the built-in script to generate a native shortcut (Windows `.lnk`, macOS Alias, or Linux `.desktop`):
```bash
python create_shortcut.py
```

## 💻 Usage

The console entry point is **`ProFiles`** (capital P, F) — registered in `pyproject.toml` as `[project.scripts]`. `python -m profiles` is equivalent.

### GUI Mode
```bash
ProFiles
# or
python -m profiles
```
* **Search**: Use `+` for inclusion, `-` for exclusion, `OR` for alternatives.
* **Shortcuts**: `Ctrl+F` (focus filter), `F5` (refresh), `Ctrl+Shift+L` (toggle theme).
* **Language**: The GUI chrome is bilingual (English / French). Use the language button in the status bar to switch on the fly, or set `language: en` / `language: fr` in the `defaults` section.

### CLI / Headless Mode
```bash
# Launch a specific file directly without GUI
ProFiles --headless "path/to/script.py"

# Generate a starter .profiles in the current directory
ProFiles --init

# Use a specific configuration
ProFiles --config "/path/to/.profiles"
```

## 🛠 Configuration

ProFiles is driven by a `.profiles` **YAML** file, walking up the filesystem tree to locate it.

```yaml
# ProFiles Configuration — YAML Format
version: 1

# Global defaults inherited by all configurations
defaults:
  title: "MyWorkspace"
  theme: light
  language: en
  search_dir: "C:/Users/YourName/Workspace"
  recursive_search: false
  extensions: [All, .lnk, .pdf]
  filters: ["", ST_PRO, ST_ENG]
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#E65100"
  search_exclude_dirs: [.git, __pycache__, node_modules, .venv, tmp]
  search_exclude_files: [*backup*, ~$*, *.tmp]
  verbose: INFO
  scan_metrics: false

# Dynamic columns extracted from filenames
columns:
  File:
    width: 600
    expression: ".*"
    group: 0
    priority: 100
  Version:
    width: 100
    expression: "[-_]V(\\d+(?:\\.\\d+)*)"
    group: 1
    priority: 10

# Machine-specific configurations
configs:
  base:
    pc_hostname: All
    pc_name: Generic
    directory: "C:/Users/YourName/Workspace"
    
  production:
    extends: base
    pc_hostname: WORKSTATION-01
    pc_name: Production Station
    directory: "Z:/Projects/Engineering"
    extensions: [.pdf, .docx, .lnk, .xlsx]
    filters: [tmp, dev, prod]
    row_colors:
      - pattern: PROD
        color: "#1565C0"
      - pattern: DEV
        color: "#E65100"
```
*See [Configuration Reference](./docs/configuration-profile.en.md) and [Dynamic Columns Guide](./docs/dynamic-columns-guide.md).*

## 🏗 Architecture

Clean layered design separating domain logic from presentation.

```text
PyLaunch/
├── src/profiles/
│   ├── core/
│   │   ├── config/        # Configuration subsystem (models, service, loader, reader, io)
│   │   ├── environment/   # OS environment & process spawn (system, execution/hooks)
│   │   ├── processing/    # File scanning, classification, column extraction
│   │   ├── telemetry/     # Logging & diagnostics
│   │   └── actions.py     # Domain actions (launch, config open, log open)
│   ├── gui/               # Tkinter presentation layer (main_window, theme, context_menu)
│   ├── utils/             # Stateless helpers (file ops, network, search parser, shortcut)
│   ├── app.py             # Application lifecycle (GUI & headless)
│   └── config.py          # Convenience re-exports for config API
├── docs/                  # User documentation (EN/FR)
└── tests/                 # Pytest suite
```

See [`AGENTS.md`](./AGENTS.md) for detailed architecture rules and conventions.

## 👨‍💻 Development

```bash
pip install -e .[dev]
pytest               # Run tests
ruff check .         # Linting
ruff format .        # Formatting
pylint src/profiles/ # Static analysis
```

## 📄 License & Support

* **Author**: [Florent ALBANY](https://github.com/falbany)
* **License**: [MIT](./LICENCE)
* **Version**: 2026.7.0
