<div align="center">

![ProFiles banner](img/ProFiles_banner.png)

[![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat)](#-installation)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat)](https://github.com/astral-sh/ruff)
[![Pylint](https://img.shields.io/badge/linting-pylint-09A64D?style=flat&logo=pylint&logoColor=white)](https://github.com/pylint-dev/pylint)
[![License](https://img.shields.io/github/license/falbany/ProFiles?style=flat&color=brightgreen)](./LICENCE)
[![GitHub](https://img.shields.io/badge/GitHub-falbany%2FProFiles-181717?style=flat&logo=github)](https://github.com/falbany/ProFiles)

🇬🇧 **English** | 🇫🇷 [Français](./README.fr.md)
</div>

---

**ProFiles** adapts to any file-based workflow through flexible configuration without touching code. Browse directories, filter with Google-style operators, extract metadata from filenames, and launch files via OS associations or custom arguments. The default interface is a modern **web UI** (React PWA) bundled with an integrated FastAPI server — usable as a desktop window, in any browser on the network, or fully headless.

<details>
<summary><b>Table of Contents</b></summary>

- [✨ Key Features](#-key-features)
  - [🔍 Smart Search \& Browse](#-smart-search--browse)
  - [🚀 Execute \& Automate](#-execute--automate)
  - [⚙️ Auto-Configuration](#️-auto-configuration)
- [🚀 Installation](#-installation)
  - [Option 1: Native Installer (Recommended)](#option-1-native-installer-recommended)
  - [Option 2: One-Line Install (Developers)](#option-2-one-line-install-developers)
  - [Option 3: Wizard / Manual](#option-3-wizard--manual)
    - [Option 1: pip (system-wide)](#option-1-pip-system-wide)
    - [Option 2: pipx (recommended for system-wide)](#option-2-pipx-recommended-for-system-wide)
    - [Option 3: uv (development)](#option-3-uv-development)
    - [Option 4: Poetry (development)](#option-4-poetry-development)
  - [Web Frontend Build](#web-frontend-build)
  - [Desktop Shortcut](#desktop-shortcut)
- [💻 Usage](#-usage)
  - [Web Mode (default)](#web-mode-default)
  - [Browser / PWA Mode (shared servers)](#browser--pwa-mode-shared-servers)
  - [Legacy Tkinter Mode (deprecated)](#legacy-tkinter-mode-deprecated)
  - [CLI / Headless Mode (work in progress)](#cli--headless-mode-work-in-progress)
- [🛠 Configuration](#-configuration)
- [🏗 Architecture](#-architecture)
- [👨‍💻 Development](#-development)
- [📄 License \& Support](#-license--support)

</details>

## ✨ Key Features

### 🔍 Smart Search & Browse

- **Google-Style Operators**: Implicit AND, `OR`, NOT (`-`), exact phrase (`"..."`).
- **Dynamic Columns**: Extract metadata (version, device, revision) from filenames using regex rules.
- **Parallel Recursion**: High-performance background thread scanning keeps the UI responsive.
- **Glob Exclusion**: Skip noisy directories (e.g., `node_modules`, `.venv`) and filter out files matching glob patterns (e.g., `*backup*`, `~$*`).

### 🚀 Execute & Automate

- **Modern Web UI**: React + Vite PWA served by an integrated FastAPI backend — desktop shell (PyWebView), any browser on the LAN, or headless.
- **Structured Log Viewer**: Built-in modal with level filters, live tail, and external log opening.
- **Launch Workflows (Hooks)**: Intercept file launches with powerful step-based YAML workflows. Run background scripts, display Markdown notifications, or completely replace the OS default launcher.
- **One-Click Launch**: Native OS execution (Windows `os.startfile`, macOS `open`, Linux `xdg-open`).
- **Custom CLI Arguments**: Right-click to launch with custom arguments, remembered per row.
- **Headless Mode**: Trigger file launches via CLI for CI/CD or scripts.
- **File Operations**: Bulk launch, copy path, hash verification (SHA-256), and safe deletion.

### ⚙️ Auto-Configuration

- **Zero-Touch Deployment**: Detects hostname/IP/path to auto-select matching configurations for multi-station setups.
- **Visual Formatting**: Rules-based row coloring with automatic contrast adjustment.
- **No-Config Fallback**: Sensible defaults allow immediate use without a `.profiles` file.

## 🚀 Installation

### Option 1: Native Installer (Recommended)

Download the installer for your OS from
[Releases](../../releases) and double-click — no Python required:

- Windows: `ProFiles-<version>.msi`
- macOS: `ProFiles-<version>.dmg`
- Linux: `profiles_<version>_amd64.deb`

### Option 2: One-Line Install (Developers)

```bash
# From a GitHub release wheel (the package is not on PyPI yet):
uv tool install profiles-app --from <url-to-profiles_app-<version>-py3-none-any.whl>
```

_(requires Python 3.11+; `pipx install <wheel-url>` is equivalent. Plain `uv tool install profiles-app` will work once the package is published to PyPI)_

### Option 3: Wizard / Manual

```bash
python install.py
```

_Runs an interactive wizard that installs the package._

From a source clone:

#### Option 1: pip (system-wide)

```bash
git clone https://github.com/falbany/ProFiles.git
cd ProFiles
pip install .
```

#### Option 2: pipx (recommended for system-wide)

```bash
git clone https://github.com/falbany/ProFiles.git
cd ProFiles
pipx install .
```

#### Option 3: uv (development)

```bash
git clone https://github.com/falbany/ProFiles.git
cd ProFiles
uv sync          # creates .venv and installs dependencies
uv run ProFiles  # run the app
uv run pytest --cov  # run tests
```

#### Option 4: Poetry (development)

```bash
git clone https://github.com/falbany/ProFiles.git
cd ProFiles
poetry install   # creates .venv and installs dependencies
poetry run ProFiles  # run the app
```

### Web Frontend Build

ProFiles includes a React web frontend that is automatically built during installation:

**With npm installed:**
If Node.js and npm are installed, the web frontend will be built automatically:

```bash
pip install .
# Building web frontend...
# SUCCESS: Web build successful.
```

**Without npm:**
If npm is not installed, ProFiles will use pre-built web assets:

```bash
pip install .
# WARNING: npm not found. Using pre-built web assets.
```

**Manual rebuild:**
To rebuild the web frontend after modifications:

```bash
python -m profiles.web.build --force
```

Download Node.js from https://nodejs.org

### Desktop Shortcut

Run the built-in script to generate a native shortcut (Windows `.lnk`, macOS Alias, or Linux `.desktop`):

```bash
python create_shortcut.py
```

## 💻 Usage

The console entry point is **`ProFiles`** (capital P, F) — registered in `pyproject.toml` as `[project.scripts]`. `python -m profiles` is equivalent.

### Web Mode (default)

```bash
ProFiles
# or
python -m profiles
```

Launches the local FastAPI server and opens the React frontend in a native PyWebView desktop window.

- **Interface**: The web chrome is bilingual (English / French). Use the language switcher in the status bar to change on the fly, or set `language: en` / `language: fr` in the `defaults` section.
- **Search**: Use `+` for inclusion, `-` for exclusion, `OR` for alternatives, and `"..."` for exact phrases.
- **Keyboard shortcuts**: `Ctrl+F` (focus filter) · `Ctrl+D` (focus directory) · `Ctrl+E` (focus extension) · `F5` (rescan) · `Ctrl+R` (reload config + rescan) · `Ctrl+H` (home directory) · `Ctrl+Shift+L` (log viewer) · `Ctrl+,` (open config) · `Ctrl+Shift+T` (cycle theme) · `Ctrl+B` (barcode scanner mode) · `Ctrl+Shift+B` (camera barcode scanner) · `Ctrl+T` (auto-rescan timer) · `?` (shortcuts dialog).
- **PWA**: The frontend ships a service worker precache, so the page can be installed in the browser as an app.

### Browser / PWA Mode (shared servers)

```bash
ProFiles --server-only
```

Runs the FastAPI server **without** the desktop window. Point any browser on the network at `http://<host>:8088` (default port). See the [Network Server Guide](./docs/network-server-guide.en.md) for firewall, hostname and multi-client setup.

### Legacy Tkinter Mode (deprecated)

```bash
ProFiles --tkinter
```

The original Tkinter desktop interface is kept for compatibility only and is **deprecated** — new features land exclusively on the web frontend.

### CLI / Headless Mode (work in progress)

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
  filters: ["", PROD, DEV]
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#E65100"
  search_exclude_dirs: [.git, __pycache__, node_modules, .venv, tmp]
  search_exclude_files: ["*backup*", "~$*", "*.tmp"]
  verbose: INFO
  scan_metrics: false

# Dynamic columns extracted from filenames
columns:
  File:
    name: File
    width: 600
    stretch: true
    match: ".*"
    transform: "{group:0}"
    priority: 100
  Version:
    name: Version
    width: 100
    stretch: false
    match: "[-_]V(\\d+(?:\\.\\d+)*)"
    transform: "{group:1}"
    priority: 10

# Machine-specific configurations
configs:
  base:
    match:
      hostname: ["*"]
    scan: "C:/Users/YourName/Workspace"

  production:
    extends: base
    match:
      hostname: ["WORKSTATION-01"]
      ip: ["192.168.1.100"]
    scan:
      - "Z:/Projects/Engineering"
      - "Z:/Projects/Shared"
    extensions: [.pdf, .docx, .lnk, .xlsx]
    filters: [tmp, dev, prod]
    row_colors:
      - pattern: PROD
        color: "#1565C0"
      - pattern: DEV
        color: "#E65100"

# Launch workflows — intercept file launches with step-based automation
hooks:
  failmode: warn           # warn | abort | skip (behavior on step failure)
  timeout: 30              # Timeout in seconds for blocking steps
  entries:
    "*.mttl":
      - action: notify
        message: "# Launching {{filename}}\\n**Preparing environment...**"
      - action: run
        command: "prepare_env.exe --file {{path}}"
        message: "**Preparing** {{stem}}..."
        ask: "Run preparation script?"
        on_failure: stop
      - action: run_after
        command: "logger.exe --opened {{filename}}"
        wait: false

    "*.exe":
      - action: notify
        message: "**Warning** : Executable launch\\nVerify file origin."
      - action: run
        command: "antivirus.exe --scan {{path}}"
        ask: "Scan with antivirus?"
        on_failure: warn
      - action: replace
        command: "sandbox_launcher.exe {{path}}"
        ask: "Execute in sandbox?"
        on_failure: stop
```

_See [Configuration Reference](./docs/configuration-profile.en.md), [Dynamic Columns Guide](./docs/columns-guide.en.md), and **[Launch Workflows Guide](./docs/hooks-guide.en.md)** for complete workflow automation._

## 🏗 Architecture

Clean layered design separating domain logic from presentation.

```text
ProFiles/
├── src/profiles/
│   ├── core/              # Domain logic: config, environment/hooks, processing, telemetry
│   ├── server/            # FastAPI backend — REST API routes, workflow & scan sessions
│   ├── web/               # React + TypeScript + Vite PWA frontend (src/, dist/, build.py)
│   ├── desktop/           # PyWebView desktop shell & background server lifecycle
│   ├── gui/               # Legacy Tkinter presentation layer (deprecated)
│   ├── utils/             # Stateless helpers (file ops, network, search parser, shortcut)
│   ├── app.py             # Application lifecycle (web desktop, server-only, Tk, headless)
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

Web frontend (Node.js required):

```bash
cd src/profiles/web
npm install
npm run build        # tsc + vite build — outputs dist/ and refreshes the PWA precache
```

## 📄 License & Support

- **Author**: [Florent ALBANY](https://github.com/falbany)
- **License**: [MIT](./LICENCE)
