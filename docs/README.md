# ProFiles Documentation

> 🏠 **Documentation Home** | 
> 📦 **[Installation](./installation-guide.en.md)** | 
> ⚙️ **[Configuration](./configuration-profile.en.md)** | 
> 🔧 **[Hooks](./hooks-guide.en.md)** | 
> 📊 **[Dynamic Columns](./dynamic-columns-guide.md)** | 
> ⚡ **[Performance Metrics](./performance-metrics-guide.md)** | 
> 🚀 **[Advanced Guide](./advanced/advanced-guide.en.md)**

---

Welcome to the ProFiles documentation. This documentation is available in **English** and **French**.

## 📚 Documentation Index

### Configuration

- **English**: [.profiles Configuration](./configuration-pylaunch.en.md)
- **Français**: [Configuration .profiles](./configuration-pylaunch.fr.md)

Detailed reference for the `.profiles` configuration file (also applies to `.profile` legacy naming):
- Global `[LAUNCHER]` settings
- Per-machine `[CONFIGURATION_N]` sections
- Search operators and syntax
- Row coloring rules
- CLI command lines
- Launch hooks (`[HOOKS]` section)

> **Note**: The configuration file is named `.profiles`. Older documentation may reference `configuration-profile.*.md` files — these are superseded by `configuration-pylaunch.*.md` but the content is equivalent.

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

- **Technical Guide** (English): [Dynamic Column Configuration](./dynamic-columns-guide.md)
  - Architecture and data flow
  - Column construction logic
  - Runtime extraction process
  - GUI integration details

- **Usage Guide** (French): [Guide d'utilisation des colonnes dynamiques](./dynamic-columns-usage.md)
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

---
## 🚀 Quick Start

### First Launch

```bash
# Run the installer
python install.py

# Or install manually
pip install -e .

# Launch the GUI
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
3. **Usage** — Launch ProFiles in GUI or headless mode

### For Developers

1. **Installation** — Use development mode: `pip install -e ".[dev]"`
2. **Code Quality** — Run `ruff format .` and `ruff check .`
3. **Testing** — Execute `pytest` for unit tests
4. **Architecture** — See `AGENTS.md` for layered architecture details
5. **Advanced Guide** — See [advanced-guide.en.md](./advanced/advanced-guide.en.md) for CLI automation and custom front-ends

---
## 🔧 Available Commands

| Command                              | Description                     |
| ------------------------------------ | ------------------------------- |
| `python -m profiles`                 | Launch GUI                      |
| `python -m profiles --headless`      | Run in CLI mode                 |
| `python -m profiles --headless FILE` | Launch specific file (no GUI)   |
| `python -m profiles --init`          | Generate configuration file     |
| `python -m profiles --config PATH`   | Use specific configuration file |
| `ProFiles`                           | Console script (same as above)  |
| `python install.py`                  | Run installation wizard         |

---
## 📁 Project Structure

```
PyLaunch/
├── src/profiles/
│   ├── core/
│   │   ├── config/         # Configuration subsystem (models, service, loader, reader, io)
│   │   ├── environment/    # OS environment & process spawn (system, execution/hooks)
│   │   ├── processing/     # File scanning, classification, column extraction
│   │   ├── telemetry/      # Logging & diagnostics
│   │   └── actions.py      # Domain actions (launch, config open, log open)
│   ├── gui/                # Tkinter presentation layer
│   ├── utils/              # Stateless utility functions
│   ├── app.py              # Application lifecycle (GUI & headless)
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
| Configuration | [configuration-pylaunch.en.md](./configuration-pylaunch.en.md) | [configuration-pylaunch.fr.md](./configuration-pylaunch.fr.md) |
| Installation  | [installation-guide.en.md](./installation-guide.en.md)         | [installation-guide.fr.md](./installation-guide.fr.md)         |
| Advanced      | [advanced-guide.en.md](./advanced/advanced-guide.en.md)        | [guide-avance.fr.md](./advanced/guide-avance.fr.md)            |
| Hooks         | [hooks-guide.en.md](./hooks-guide.en.md)                      | —                                                              |

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
- **GUI**: Tkinter + [Sun Valley ttk theme](https://github.com/rdbende/Sun-Valley-ttk-theme) (`sv-ttk`) + `darkdetect` (system theme)
- **License**: See `LICENCE` file

---

*Last updated: 2026-08-02*
