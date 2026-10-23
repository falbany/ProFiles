# ProFiles Documentation

> 🏠 **Documentation Home** | 
> 📦 **[Installation](./installation-guide.en.md)** | 
> ⚙️ **[Configuration](./configuration-profile.en.md)** | 
> 🔧 **[Hooks](./hooks-guide.en.md)** | 
> 📊 **[Dynamic Columns](./columns-guide.en.md)** | 
> ⚡ **[Performance Metrics](./performance-metrics-guide.md)** | 
> 🚀 **[Advanced Guide](./advanced/advanced-guide.en.md)**

---

Welcome to the ProFiles documentation. This documentation is available in **English** and **French**.

## 📚 Documentation Index

### Configuration

- **English**: [.profiles Configuration](./configuration-profile.en.md)
- **Français**: [Configuration .profiles](./configuration-profile.fr.md)

### Installation

- **English**: [Installation Guide](./installation-guide.en.md)
- **Français**: [Guide d'installation](./installation-guide.fr.md)

Complete installation procedures:
- Interactive wizard installation
- Manual installation steps
- Development environment setup
- Post-installation configuration
- Troubleshooting guide

### Advanced

- **English**: [Advanced Guide](./advanced/advanced-guide.en.md)
- **Français**: [Guide Avancé](./advanced/guide-avance.fr.md)

Covers headless automation, programmatic API usage, custom front-ends (CLI/Web), performance tuning, and integration patterns.

### Dynamic Columns

- **Column Library** (English): [Ready-to-use configurations](./column-library.md)
  - **50+ pre-configured columns** for common use cases
  - Production, Development, Multi-site combinations
  - Selection guide and examples

- **Technical Guide** (English): [Dynamic Column Configuration](./columns-guide.en.md)
  - Architecture and data flow
  - Column construction logic
  - Runtime extraction process
  - GUI integration details

- **Usage Guide** (French): [Guide d'utilisation des colonnes dynamiques](./columns-guide.fr.md)
  - Extract device names, project codes, versions, etc.
  - Configure extraction rules without coding
  - Customize column widths and default values
  - Regex patterns and examples
  - Troubleshooting guide

### Performance Monitoring

- **Metrics Guide** (English): [Performance Metrics Reference](./performance-metrics-guide.md)
  - Enable scan performance monitoring
  - Understand metrics output (duration, throughput)
  - Optimize scan configuration
  - Benchmark and troubleshoot performance

### Network Server

- **English**: [Network Server Guide](./network-server-guide.en.md)
- **Français**: [Guide du serveur réseau](./network-server-guide.fr.md)

  - Start ProFiles with the built-in FastAPI server (`--server-only`, port 8088)
  - Access the web UI from any browser on the network
  - Firewall, static IP and troubleshooting guidance

### Log Format

- **English**: [Log File Format](./operations/log-format.md)

  - Structure of `profiles.log` event lines (source, timestamps)
  - Telemetry events and the built-in log viewer modal

### Barcode Scanner

- **English**: [Barcode Scanner Mode](./barcode-scanner.en.md)
  - Enable/disable barcode mode (UI button or `Ctrl+B`)
  - Barcode payload format (`key=value;key=value` pairs)
  - Auto-apply values and trigger scan
  - UI indicators and toast notifications
  - Technical architecture and troubleshooting

---
## 🚀 Quick Start

### First Launch

```bash
# Run the installer
python install.py

# Or install manually
pip install -e .

# Launch the app (web backend by default: FastAPI server + PyWebView shell)
python -m profiles
```

### Generate Configuration

```bash
# Create starter configuration file
python -m profiles --init
```

---
## 📖 Documentation Overview

### For Users

1. **Installation** — Follow the installation guide for your language
2. **Configuration** — Learn how to customize `.profiles`
3. **Usage** — Launch ProFiles in web mode (default), browser mode, or headless mode

### For Developers

1. **Installation** — Use development mode: `pip install -e ".[dev]"`
2. **Code Quality** — Run `ruff format .` and `ruff check .`
3. **Testing** — Execute `pytest` for unit tests
4. **Architecture** — See `AGENTS.md` for layered architecture details
5. **Advanced Guide** — See [advanced-guide.en.md](./advanced/advanced-guide.en.md) for CLI automation and custom front-ends

---
## 🔧 Available Commands

| Command                                | Description                                    |
| -------------------------------------- | ---------------------------------------------- |
| `python -m profiles`                   | Launch the web UI in a PyWebView desktop shell (default) |
| `python -m profiles --web`             | Same as above (explicit)                       |
| `python -m profiles --server-only`     | Run the FastAPI server only (browser/PWA use)  |
| `python -m profiles --tkinter`         | Legacy Tkinter interface (deprecated)          |
| `python -m profiles --headless`        | Run in CLI mode                                |
| `python -m profiles --headless FILE`   | Launch specific file (no GUI)                  |
| `python -m profiles --init`            | Generate configuration file                    |
| `python -m profiles --config PATH`     | Use specific configuration file                |
| `ProFiles`                             | Console script (same as above)                 |
| `python install.py`                    | Run installation wizard                        |

---
## 📁 Project Structure

```
ProFiles/
├── src/profiles/
│   ├── core/               # Domain logic: config, environment/hooks, processing, telemetry
│   ├── server/             # FastAPI backend — REST API, workflow & scan sessions
│   ├── web/                # React + TypeScript + Vite PWA frontend (src/, dist/, build.py)
│   ├── desktop/            # PyWebView desktop shell & background server lifecycle
│   ├── gui/                # Legacy Tkinter presentation layer (deprecated)
│   ├── utils/              # Stateless utility functions
│   ├── app.py              # Application lifecycle (web desktop, server-only, Tk, headless)
│   └── config.py           # Convenience re-exports for config API
├── tests/                  # Unit tests
├── docs/                   # This documentation
├── img/                    # Logos and assets
├── install.py              # Installation wizard
├── create_shortcut.py      # Desktop shortcut generator
├── pyproject.toml          # Package configuration
└── .profiles               # User configuration (created on demand)
```

---
## 🌐 Language Selection

Choose your preferred language for documentation:

| Topic         | English                                                        | Français                                                       |
| ------------- | -------------------------------------------------------------- | -------------------------------------------------------------- |
| Configuration | [configuration-profile.en.md](./configuration-profile.en.md)    | [configuration-profile.fr.md](./configuration-profile.fr.md)   |
| Installation  | [installation-guide.en.md](./installation-guide.en.md)         | [installation-guide.fr.md](./installation-guide.fr.md)         |
| Advanced      | [advanced-guide.en.md](./advanced/advanced-guide.en.md)        | [guide-avance.fr.md](./advanced/guide-avance.fr.md)            |
| Hooks         | [hooks-guide.en.md](./hooks-guide.en.md)                       | [hooks-guide.fr.md](./hooks-guide.fr.md)                       |
| Network       | [network-server-guide.en.md](./network-server-guide.en.md)     | [network-server-guide.fr.md](./network-server-guide.fr.md)     |
| Barcode       | [barcode-scanner.en.md](./barcode-scanner.en.md)               | [barcode-scanner.fr.md](./barcode-scanner.fr.md)               |

---
## 📞 Support

For additional support:

- Review the [README.md](../README.md) at project root
- Check source code documentation in `src/profiles/`
- Run tests with `pytest` to verify installation
- Use `--help` flag: `python -m profiles --help`

---
## 🔄 Version Information

- **Python**: 3.11+
- **Interface**: Web UI (React + TypeScript + Vite PWA) served by FastAPI, desktop shell via PyWebView
- **Legacy GUI (deprecated)**: Tkinter + [Sun Valley ttk theme](https://github.com/rbdende/Sun-Valley-ttk-theme) (`sv-ttk`) + `darkdetect` — use `--tkinter`, kept for compatibility only
- **License**: See `LICENCE` file

---

*Last updated: 2026-10-23*
