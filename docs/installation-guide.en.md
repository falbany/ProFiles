# ProFiles Installation Guide

> 🏠 **[Documentation Home](./README.md)** | 
> 📦 **Installation** | 
> ⚙️ **[Configuration](./configuration-profile.en.md)** | 
> 🔧 **[Hooks](./hooks-guide.en.md)** | 
> 📊 **[Dynamic Columns](./columns-guide.en.md)** | 
> 🚀 **[Advanced Guide](./advanced/advanced-guide.en.md)** | 
> 🇫🇷 **[Version Française](./installation-guide.fr.md)**

---

## Prerequisites

- **Python**: Version 3.11 or higher
- **Operating System**: Windows, Linux, or macOS
- **Permissions**: Write permissions in project directory

## Method 1: Installation with Wizard (Recommended)

ProFiles includes an interactive installation wizard that guides users through the process.

### Steps

1. **Launch the wizard**

   ```bash
   python install.py
   ```

2. **Choose installation target**

   The wizard offers two options:

   - **[1] New Virtual Environment (.venv)** — Isolated environment (recommended)
   - **[2] System Python** — Global system installation (requires permissions)

   ```
   Select your preference: 1
   ```

3. **Choose workflow mode**

   - **[1] Standard** — Ready-to-use installation
   - **[2] Development** — Editable install + full development suite

   ```
   Select your workflow: 1
   ```

4. **Confirm installation**

   ```
   Ready to proceed? (y/n): y
   ```

5. **Create desktop shortcut (Windows)**

   ```
   Create a desktop shortcut for quick access? (y/n): y
   ```

### Result

The wizard displays quick start commands:

```
✨ ProFiles successfully installed!

Quick Start:
1. Activate venv:    .venv\Scripts\activate
2. Launch GUI:       profiles
3. Headless mode:    profiles --headless
4. Run as module:    python -m profiles
```

---

## Method 2: Manual Installation

### 1. Create a virtual environment (recommended)

```bash
python -m venv .venv
```

### 2. Activate the virtual environment

**Windows:**

```bash
.venv\Scripts\activate
```

**Linux/macOS:**

```bash
source .venv/bin/activate
```

### 3. Install dependencies

**Standard Mode:**

```bash
pip install -e .
```

**Development Mode:**

```bash
pip install -e ".[dev]"
```

### 4. Verify installation

```bash
python -m profiles --help
```

---

## Dependencies

### Main Dependencies

- `sv-ttk` — Sun Valley ttk theme (Material Design 3 inspired)
- `darkdetect` — Automatic system theme detection (light/dark)

These are declared in `pyproject.toml` and installed automatically with `pip install .`.

### Development Dependencies (optional)

Development dependencies are installed with `pip install -e ".[dev]"`:

- `ruff` — Python formatter and linter
- `pylint` — Static code analysis
- `pytest` — Testing framework
- `pytest-cov` — Code coverage
- `pre-commit` — Pre-commit hooks

---

## Development Commands

### Code Formatting

```bash
ruff format .
```

### Linting Check

```bash
ruff check .
ruff check --fix .
```

### Pylint Analysis

```bash
pylint src/profiles
```

### Running Tests

```bash
pytest
pytest --cov=src/profiles --cov-report=term-missing
```

### Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

---

## Post-Installation Configuration

### 1. Generate configuration file

```bash
python -m profiles --init
```

This creates a `.profiles` file in the current directory with default settings.

### 2. Customize configuration

Edit the `.profiles` file to adapt:

- Search directory
- File extensions
- Search filters
- Row colors
- Per-machine settings

See [Configuration .profiles](./configuration-pylaunch.en.md) for details.

---

## Usage Modes

### GUI Mode

```bash
python -m profiles
```

or

```bash
profiles
```

### Headless Mode (CLI)

```bash
python -m profiles --headless
```

### Specify Configuration File

```bash
python -m profiles --config /path/to/.profiles
```

### Regenerate Configuration File

```bash
python -m profiles --init
```

---

## Best Practices

### Development Workflow

1. **Always use a virtual environment** for isolation
2. **Install in editable mode** for development: `pip install -e ".[dev]"`
3. **Run pre-commit hooks** before each commit: `pre-commit run --all-files`
4. **Maintain code quality**: Keep Pylint score above 8.0
5. **Write tests** for new functionality: Aim for >85% coverage

### Production Deployment

1. **Use standard installation**: `pip install -e .`
2. **Test in isolated environment** before deployment
3. **Document configuration** in `.profiles` file
4. **Create desktop shortcut** for easy access
5. **Verify headless mode** works for automated scripts

### Code Quality Checklist

Before committing changes:

- [ ] Run `ruff format .` to format code
- [ ] Run `ruff check --fix .` to fix linting issues
- [ ] Run `pylint src/profiles` and verify score > 8.0
- [ ] Run `pytest` to ensure all tests pass
- [ ] Check test coverage: `pytest --cov=src/profiles`
- [ ] Remove any `TODO` comments or document them
- [ ] Add type hints for new public functions
- [ ] Add docstrings for public APIs

---

## Advanced Usage

### Headless Mode for Automation

ProFiles can run without GUI for automated workflows:

```bash
# Basic headless mode
python -m profiles --headless

# With specific configuration
python -m profiles --headless --config /path/to/.profiles

# Programmatic usage
from profiles.core.scanner import scan_and_process
from profiles.core.actions import launch_selected_file

# Scan directory
results = scan_and_process(
    directory="/path/to/dir",
    extension=".lnk",
    recursive=True,
    filter_text=""
)

# Launch first result
if results:
    result = launch_selected_file(
        directory="/path/to/dir",
        filename=results[0].filename,
        release="v1.0",
        username="automation"
    )
    print(f"Launch status: {result.status}")
```

### Custom Front-Ends

ProFiles's core layer is GUI-independent. You can create custom front-ends:

```python
# CLI example
from profiles.core import config_service, scanner, actions

# Auto-select configuration
config_dir = config_service.auto_select_directory(None, "my-hostname")

# Scan files
results = scanner.scan_and_process(
    directory=config_dir,
    extension=".lnk",
    recursive=True,
    filter_text=""
)

# Display results
for file in results:
    print(f"{file.filename} - {file.version}")
```

See [AGENTS.md](../AGENTS.md) for architecture details.

---

## Troubleshooting

### Issue: Wizard fails to install dependencies

**Symptoms**: Installation stops with an error about `sv-ttk` or `darkdetect`.

**Diagnosis**:
- Network connectivity issues
- pip cache corruption
- Permission problems

**Solution**:
```bash
# Clear pip cache
pip cache purge

# Install dependencies directly
pip install sv-ttk darkdetect

# Run installer again
python install.py

# Or install with verbose output
pip install -v sv-ttk darkdetect
```

### Issue: `profiles` command not found

**Symptoms**: Command not recognized after installation.

**Diagnosis**:
- Virtual environment not activated
- Script not in PATH
- Installation failed silently

**Solution**:
```bash
# Verify installation
pip show profiles

# Check script location
# Windows:
.venv\Scripts\profiles.exe --help

# Linux/macOS:
.venv/bin/profiles --help

# Add to PATH (Linux/macOS)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Issue: Permission denied on system installation

**Symptoms**: Permission errors when installing without virtual environment.

**Diagnosis**:
- Writing to system Python requires admin privileges
- User doesn't have write permissions

**Solution**:

**Option 1: Use virtual environment (recommended)**
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
pip install -e .
```

**Option 2: Use user installation**
```bash
pip install --user -e .
```

**Option 3: Use administrator privileges**
```bash
# Windows (Run as Administrator)
pip install -e .

# Linux/macOS
sudo pip install -e .
```

### Issue: GUI not displaying

**Symptoms**: Application starts but no window appears, or Tkinter error.

**Diagnosis**:
- Tkinter not installed (common on minimal Linux installs)
- Display environment not set (Linux remote sessions)
- X11 forwarding not enabled

**Solution**:

**Windows**: Tkinter is included by default. Reinstall Python if needed.

**Linux**:
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# RHEL/CentOS
sudo dnf install python3-tkinter

# Arch Linux
sudo pacman -S python-tkinter
```

**Remote SSH**:
```bash
# Enable X11 forwarding in SSH
ssh -X user@host

# Or use VNC/X forwarding
```

### Issue: Configuration file not found

**Symptoms**: ProFiles uses defaults instead of custom configuration.

**Diagnosis**:
- `.profiles` file in wrong location
- File name incorrect (case-sensitive on Unix)
- File permissions issue

**Solution**:
```bash
# Check current directory
pwd  # Linux/macOS
cd   # Windows

# Verify file exists
ls -la .profiles  # Linux/macOS
dir .profiles     # Windows

# Use explicit path
python -m profiles --config /full/path/to/.profiles
```

### Issue: Slow scanning on large directories

**Symptoms**: GUI freezes or takes minutes to scan.

**Diagnosis**:
- Recursive scan on very large directory tree
- No exclusion patterns configured
- Network drive latency

**Solution**:
```ini
# In .profiles file
[LAUNCHER]
# Exclude common large directories
search_exclude_dirs = .git, node_modules, __pycache__, bin, obj, Debug, Release

# Limit extensions
extensions = .lnk, .pdf

# Or disable recursive initially
recursive_search = false
```

---

## Performance Optimization

### For Large Projects (>10,000 files)

1. **Use non-recursive scanning**:
   ```ini
   recursive_search = false
   ```

2. **Exclude unnecessary directories**:
   ```ini
   search_exclude_dirs = .git, __pycache__, node_modules, build, dist
   ```

3. **Limit file extensions**:
   ```ini
   extensions = .lnk  # Only scan specific types
   ```

4. **Use specific search directory**:
   ```ini
   search_dir = /path/to/production/specific_folder  # Narrower scope
   ```

### Memory Usage

ProFiles uses chunked insertion for large file lists. If you experience memory issues:

- Reduce recursive depth
- Increase chunk size in code (advanced)
- Use filter patterns to limit results

---

## Uninstallation

### Complete Removal

**1. Uninstall package**:
```bash
pip uninstall profiles
```

**2. Remove virtual environment**:
```bash
# Windows
rmdir /s .venv

# Linux/macOS
rm -rf .venv
```

**3. Remove configuration file**:
```bash
# Windows
del .profiles

# Linux/macOS
rm .profiles
```

**4. Remove desktop shortcut** (Windows):
- Right-click shortcut on desktop
- Select "Delete"

**5. Remove installed files** (system installation):
```bash
pip uninstall profiles
# Manually remove if needed
rm -rf ~/.local/lib/python3.11/site-packages/profiles*
```

---

## Verification & Testing

### Post-Installation Verification

After installation, verify everything works:

```bash
# 1. Check package installation
pip show profiles

# 2. Verify GUI launch
python -m profiles --help

# 3. Test headless mode
python -m profiles --headless

# 4. Run unit tests
pytest

# 5. Check code quality
pylint src/profiles
ruff check .
```

### Expected Output

**`pip show profiles`**:
```
Name: profiles
Version: 2026.7.0
Summary: ProFiles - A modern GUI launcher for production test programs
Location: c:\Git\GitLab-ST\profiles\src
Editable: true
```

**`python -m profiles --help`**:
```
usage: profiles [-h] [--config CONFIG] [--headless] [--init] [file]

ProFiles - Python MuTool Project Launcher

positional arguments:
  file             File to launch (optional, headless mode only)

options:
  -h, --help       show this help message and exit
  --config CONFIG  Path to .profiles configuration file (default: auto-search folder tree)
  --headless       Run in headless mode (no GUI)
  --init           Generate a default .profiles configuration file in the current directory

Examples:
  profiles                              Launch GUI (auto-search config)
  profiles --config /path/to/.profiles  Use explicit config file
  profiles --headless                   Headless: scan & launch all
  profiles --headless file.mttl         Headless: launch specific file
  profiles --init                       Generate default .profiles in CWD
```

---

## Support & Resources

### Documentation

- **Configuration**: [configuration-pylaunch.en.md](./configuration-pylaunch.en.md)
- **Architecture**: [AGENTS.md](../AGENTS.md)
- **README**: [README.md](../README.md)

### Development Resources

- **Source Code**: `src/profiles/`
- **Tests**: `tests/`
- **Examples**: See test files for usage examples

### Getting Help

1. **Check documentation** in `docs/` folder
2. **Review error logs** in application logs
3. **Run tests** to verify installation: `pytest -v`
4. **Check system info**: `python -m profiles --headless`

---

## Version Information

- **Python**: 3.11+
- **Tkinter**: Required for GUI
- **sv-ttk**: Sun Valley ttk theme (auto-installed)
- **darkdetect**: System theme detection (auto-installed)
- **License**: See `LICENCE` file

---

## Uninstallation

### With pip

```bash
pip uninstall profiles
```

### Remove virtual environment

```bash
rmdir /s .venv        # Windows
rm -rf .venv          # Linux/macOS
```

### Remove configuration file

```bash
rm .profiles          # Linux/macOS
del .profiles         # Windows
```

---

## Project Structure

```
profiles/
├── src/
│   └── profiles/
│       ├── core/           # Shared business logic
│       ├── gui/            # Tkinter interface
│       ├── utils/          # Utility functions
│       ├── app.py          # Application lifecycle
│       └── config.py       # Configuration
├── tests/                  # Unit tests
├── docs/                   # Documentation
├── install.py              # Installation wizard
├── pyproject.toml          # Package configuration
└── .profiles               # User configuration
```

---

## Support

For questions or issues, consult:

- Complete documentation in `docs/` folder
- `README.md` file at project root
- Source code in `src/profiles/`
