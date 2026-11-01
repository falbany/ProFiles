# AGENTS.md — Guide d'Architecture et de Qualité

## 🎯 Vision

Ce document définit les standards d'architecture, les principes de conception et les pratiques de développement pour assurer un code **maintenable**, **testable**, **réutilisable** et de **haute qualité**.

---

## 🏗️ Principes Fondamentaux

### 📐 Principes SOLID

| Principe | Description                                    | Application                                                      |
| -------- | ---------------------------------------------- | ---------------------------------------------------------------- |
| **S**RP  | Une classe = une responsabilité                | Décomposer les fonctions complexes en modules spécialisés        |
| **O**CP  | Ouvert pour extension, fermé pour modification | Utiliser l'héritage et les interfaces pour étendre sans modifier |
| **L**SP  | Les sous-types doivent être substituables      | Respecter les contrats des classes parentes                      |
| **I**SP  | Préférer plusieurs interfaces spécifiques      | Diviser les interfaces lourdes en plus petites                   |
| **D**IP  | Dépendre des abstractions, pas des concrétions | Injecter les dépendances via interfaces                          |

### 🎓 Principes de Conception

1. **SRP (Single Responsibility Principle)** : Chaque méthode a une seule responsabilité
2. **DRY (Don't Repeat Yourself)** : Logique de parsing centralisée
3. **KISS (Keep It Simple, Stupid)** : Réduction de la complexité
4. **Separation of Concerns** : Séparation claire entre configuration, logging et UI

### 🔄 Principes d'Architecture

- **Layered Architecture** : Séparation stricte des couches (présentation, métier, données)
- **Dependency Inversion** : Les couches basses ne dépendent pas des couches hautes
- **Pure Functions** : Privilégier les fonctions pures pour la testabilité
- **Immutability** : Privilégier l'immutabilité quand c'est possible

---

## 📁 Structure de l'Application

> **⚠️ Keep in sync with the code** : cet arbre reflète `src/profiles/` au
> 31/10/2026. Toute création, suppression ou déplacement de module doit mettre
> à jour cette section dans le même commit — ainsi que `tests/AGENTS.md`,
> qui reflète l'arbre de tests 1:1. Avant d'utiliser un chemin d'import des
> extraits ci-dessous, vérifiez-le contre `src/profiles/core/__init__.py`
> (la surface publique du core) ou `docs/advanced/guide-avance.fr.md`.

```
src/profiles/
├── core/                     # Logique métier — indépendante de toute UI
│   ├── actions.py            # Actions domaine (lancement, ouverture, ActionResult)
│   ├── config/               # Sous-système configuration
│   │   ├── models.py         #   AppConfig, MachineConfiguration, ColumnConfiguration
│   │   ├── loader.py         #   load_config, propose_config_creation
│   │   ├── reader.py         #   ConfigReader (parsing .profiles)
│   │   ├── service.py        #   auto_select_directory, find_active_config
│   │   ├── matcher.py        #   Correspondance config ↔ hostname
│   │   ├── schema.py         #   Schéma de validation
│   │   ├── conditions.py     #   Grammaire des conditions if: des hook steps
│   │   ├── validator.py      #   Validation des valeurs
│   │   ├── inheritance.py    #   Héritage entre configurations
│   │   ├── template.py       #   STARTER_CONFIG_TEMPLATE (génération .profiles)
│   │   └── io/yaml_io.py     #   Lecture/écriture YAML
│   ├── processing/           # Pipeline de scan
│   │   ├── scanner.py        #   scan_and_process, ScannedFile
│   │   ├── file_classifier.py#   get_file_info, classification d'extensions
│   │   ├── file_metadata.py  #   Métadonnées fichiers
│   │   └── column_extractor.py#  Extraction des colonnes (version, …)
│   ├── environment/          # Environnement OS & exécution
│   │   ├── system.py         #   collect_system_info, SystemInfo, format_user_host
│   │   ├── execution.py      #   Spawn de processus, hooks de lancement
│   │   ├── workflow.py       #   Étapes de workflow
│   │   └── matcher.py, render.py, interactions.py, message_dialog.py
│   └── telemetry/            # Logging & diagnostics
│       ├── diagnostics.py    #   get_logger, configure_logger, crash hook
│       ├── events.py         #   Événements (COMMAND_OUTPUT, …)
│       └── metrics.py, log_viewer.py, diagnostics.py
│
├── launch/                   # Résolution launch-time (logique pure)
│   ├── context.py            #   LaunchContext, détection du signal OS
│   ├── resolution.py         #   Sélection du fichier de config à utiliser
│   └── creation.py           #   Proposition/écriture d'un .profiles de départ
│
├── server/                   # Serveur FastAPI local (backend du front-end web)
│   ├── app.py                #   create_app
│   ├── state.py              #   ServerState
│   ├── static.py             #   Service des assets web/dist
│   └── routes/               #   actions, config, fs, instance, logs, scan, system, workflow
│
├── web/                      # Front-end par défaut (React PWA + Vite + TypeScript)
│   ├── src/                  #   App.tsx, components/, api/, utils/
│   ├── dist/                 #   Build servi par server/static.py
│   └── build.py, build_hook.py  # Build intégré au packaging (hook hatch)
│
├── desktop/                  # Shell PyWebView (fenêtrage natif)
│   ├── launcher.py           #   Démarrage serveur + fenêtre
│   ├── lifecycle.py          #   Cycle de vie de l'application
│   └── instance.py, handoff.py  # Instances multiples, handoff de port
│
├── gui/                      # ⚠️ DÉPRÉCIÉ (Tkinter) — suppression prévue (phase 2)
│   │                         # Ne pas y ajouter de fonctionnalités ; le
│   │                         # front-end par défaut est web/. Tests skippés.
│   ├── main_window.py        # Orchestration des widgets
│   └── ui.py, styles.py, theme.py, i18n.py, controllers/, presentation/
│
├── utils/                    # Fonctions utilitaires pures & stateless
│   ├── file_utils.py         # scan_directory, launch_file, open_with_default_app
│   ├── network.py            # hostname, IP, username
│   ├── search_parser.py      # tokenize, match_filter
│   └── shortcut.py           # Raccourcis
│
├── app.py                    # Point d'entrée : backend web/desktop ou CLI headless
└── config.py                 # Shim de ré-export (AppConfig, load_config, …)
```

> `src/profiles/config.py` n'est qu'un module de commodité qui ré-exporte
> `profiles.core.config.*` sous un chemin court. Le code nouveau importe
> depuis `profiles.core` (surface publique) ou ses sous-paquets.

---

## 🎯 Règles d'Architecture par Couche

### Core Layer (`profiles.core`)

**Responsabilité** : Logique métier pure, indépendante de tout framework

**Règles** :
- ✅ Zéro dépendance vers les couches UI (React/web, desktop, Tkinter, CLI)
- ✅ Fonctions pures où c'est possible
- ✅ Retourner des structures de données typées (jamais `None` pour les collections)
- ✅ Documenter toutes les fonctions publiques avec des docstrings
- ✅ Utiliser des type hints pour toutes les signatures de fonctions
- ✅ Privilégier l'immutabilité des données

**Exemple** :
```python
# ✅ CORRECT : Fonction pure avec retour typé
def merge_configs(base: dict, override: dict) -> dict:
    """Merge override into base configuration.
    
    Args:
        base: Configuration de base
        override: Surcharges à appliquer
        
    Returns:
        Nouvelle configuration fusionnée
    """
    result = base.copy()
    result.update(override)
    return result


# ❌ WRONG : Effet de bord, pas de type hints
def merge(base, override):
    base.update(override)
    return base
```

### Couche Présentation

**Couche par défaut** : `profiles.web` (React PWA) + `profiles.server`
(FastAPI) + `profiles.desktop` (shell PyWebView). Le Tkinter
`profiles.gui` est **déprécié** (suppression prévue, phase 2) — ne pas y
ajouter de fonctionnalités ; les extraits ci-dessous ne valent que pour la
maintenance de la couche legacy.

**Responsabilité** : Gestion exclusive des objets d'interface et de l'expérience utilisateur

**Règles** :
- ✅ Tous les objets d'UI sont créés et gérés dans la couche présentation
- ✅ Déléguer la logique métier à `profiles.core.*`
- ✅ Gérer uniquement le code de liaison spécifique aux widgets/composants
- ✅ Utiliser les widgets `ttk` pour un theming cohérent (legacy Tkinter)
- ✅ Implémenter une gestion d'erreur robuste pour les actions utilisateur
- ✅ Ne jamais contenir de logique métier directe

**Exemple** :
```python
# ✅ CORRECT : GUI délègue au core
def on_scan_button_click(self) -> None:
    """Handle scan button click."""
    directory = self.directory_combo.get()
    extension = self.extension_entry.get()

    # Delegate to core layer
    results = scan_and_process(
        directory,
        extension=extension,
        recursive=self.recursive_var.get(),
    )

    self._update_treeview(results)


# ❌ WRONG : Logique métier dans la GUI
def on_scan_button_click(self) -> None:
    """Handle scan button click."""
    # Bad: business logic mixed with UI
    files = []
    for root, dirs, filenames in os.walk(self.directory_combo.get()):
        for f in filenames:
            if f.endswith(self.extension_entry.get()):
                files.append(f)
    self._update_treeview(files)
```

### Utils Layer (`profiles.utils`)

**Responsabilité** : Fonctions utilitaires stateless et agnostiques

**Règles** :
- ✅ Fonctions helpers stateless uniquement
- ✅ Aucune connaissance du domaine applicatif
- ✅ Aucun effet de bord (fonctions pures)
- ✅ Agnostiques au framework (pas de Tkinter, pas de CLI libs)
- ✅ Documenter les formats d'entrée/sortie attendus

**Exemple** :
```python
# ✅ CORRECT : Fonction utilitaire stateless
def normalize_path(path: str) -> str:
    """Normalize a filesystem path string.
    
    Args:
        path: Path string to normalize
        
    Returns:
        Normalized path string
    """
    return os.path.normpath(os.path.expanduser(path))
```

---

## 🛡️ Bonnes Pratiques de Code

### 1. Single Responsibility Principle (SRP)

**Chaque classe/fonction doit avoir une seule responsabilité.**

```python
# ✅ CORRECT : SRP respecté
class FileScanner:
    """Scan directories for files."""

    def scan(self, directory: str) -> list[str]:
        """Scan directory and return file paths."""
        ...


class FileFilter:
    """Filter files based on criteria."""

    def filter(self, files: list[str], pattern: str) -> list[str]:
        """Filter files by pattern."""
        ...


class FileLauncher:
    """Launch files via OS association."""

    def launch(self, file_path: str) -> bool:
        """Launch file with default application."""
        ...


# ❌ WRONG : SRP violé
class FileHandler:
    """Do everything with files."""

    def scan_and_filter_and_launch(self, directory: str, pattern: str) -> None:
        """Scan, filter, and launch files - too many responsibilities."""
        files = self.scan(directory)
        filtered = self.filter(files, pattern)
        for f in filtered:
            self.launch(f)
```

### 2. Don't Repeat Yourself (DRY)

**Centraliser la logique de parsing et de traitement.**

```python
# ✅ CORRECT : Logique centralisée
def parse_extension_pattern(pattern: str) -> list[str]:
    """Parse extension pattern into list of extensions.

    Handles: ".txt", ".py,.md", "OR(.txt,.py)"
    """
    # Centralized parsing logic
    ...


class ExtensionFilter:
    """Filter files by extension."""

    def __init__(self, pattern: str) -> None:
        self.extensions = parse_extension_pattern(pattern)

    def matches(self, filename: str) -> bool:
        """Check if file matches any extension."""
        return any(filename.endswith(ext) for ext in self.extensions)


# ❌ WRONG : Duplication de logique
def scan_files(directory: str, pattern: str) -> list[str]:
    # Parse pattern inline
    extensions = [p.strip() for p in pattern.split(",")]
    ...


def filter_files(files: list[str], pattern: str) -> list[str]:
    # Parse pattern again
    extensions = [p.strip() for p in pattern.split(",")]
    ...
```

### 3. Keep It Simple, Stupid (KISS)

**Réduire la complexité inutile.**

```python
# ✅ CORRECT : Simple et clair
def is_valid_extension(ext: str) -> bool:
    """Check if extension is valid."""
    return ext.startswith(".") and len(ext) > 2


# ❌ WRONG : Complexité inutile
def validate_extension_comprehensive(
    extension: str,
    check_dot: bool = True,
    check_length: bool = True,
    check_special_chars: bool = True,
    check_reserved_names: bool = False,
) -> tuple[bool, list[str]]:
    """Validate extension with comprehensive checks."""
    errors = []
    if check_dot and not extension.startswith("."):
        errors.append("Missing dot prefix")
    if check_length and len(extension) <= 2:
        errors.append("Too short")
    # ... 50 more lines
```

### 4. Separation of Concerns

**Séparer configuration, logging et UI.**

```python
# ✅ CORRECT : Séparation claire
# config.py - Configuration only
class AppConfig:
    """Application configuration."""

    def __init__(self, search_dir: str, extensions: tuple[str, ...]) -> None:
        self.search_dir = search_dir
        self.extensions = extensions


# logger.py - Logging only
class LoggerFactory:
    """Create configured loggers."""

    def create(self, name: str) -> Logger:
        """Create logger with standard configuration."""
        ...


# gui/main_window.py - UI only
class MainWindow:
    """Main application window."""

    def __init__(self, config: AppConfig, logger: Logger) -> None:
        self.config = config
        self.logger = logger
        self._init_ui()


# ❌ WRONG : Concerns mélangés
class MainWindow:
    """Main window with config and logging."""

    def __init__(self) -> None:
        # Bad: loading config in UI
        self.config = self._load_config()
        # Bad: creating logger in UI
        self.logger = self._create_logger()

    def _load_config(self) -> AppConfig:
        """Load configuration - not UI's responsibility."""
        ...
```

---

## 🧪 Stratégie de Test

### Principes de Test

1. **Testabilité** : Le code doit être conçu pour être testable
2. **Isolation** : Chaque test doit tester une seule chose
3. **Reproductibilité** : Les tests doivent être déterministes
4. **Lisibilité** : Un test doit être auto-documentant

### Structure des Tests

```python
# ✅ CORRECT : Test clair et isolé
def test_scan_directory_with_recursive_flag(tmp_path: Path) -> None:
    """Verify recursive directory scanning finds files in subdirectories.
    
    Given: A directory with nested subdirectories containing files
    When: scan_directory is called with recursive=True
    Then: All files including subdirectory files are returned
    """
    # Arrange
    test_file = tmp_path / "subdir" / "test.txt"
    test_file.parent.mkdir()
    test_file.write_text("test content")
    
    # Act
    result = scan_directory(str(tmp_path), recursive=True)
    
    # Assert
    assert len(result) == 1
    assert test_file.name in result[0]


# ❌ WRONG : Test trop complexe, multiple responsabilités
def test_scan(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    r = scan_directory(str(tmp_path), recursive=True)
    assert len(r) == 1
    # Too many things happening, unclear what's being tested
```

### Couverture de Test

| Type de test     | Objectif                               | Outil            |
| ---------------- | -------------------------------------- | ---------------- |
| **Unitaires**    | Tester les fonctions/classes isolément | pytest           |
| **Intégration**  | Tester les interactions entre modules  | pytest           |
| **Fonctionnels** | Tester les cas d'usage complets        | pytest           |
| **Front-end web**| Tester les composants React            | vitest (`src/profiles/web`) |

### Fixtures Réutilisables

> La vraie forme de `AppConfig` est définie dans
> `src/profiles/core/config/models.py` (dataclass à champs typés) ; voir aussi
> `tests/AGENTS.md` pour l'organisation des fixtures du projet.

```python
# ✅ CORRECT : Fixtures dans conftest.py
import pytest
from pathlib import Path

from profiles.core.config.models import AppConfig


@pytest.fixture
def temp_directory(tmp_path: Path) -> Path:
    """Create a temporary directory with test files."""
    test_dir = tmp_path / "test_files"
    test_dir.mkdir()
    (test_dir / "file1.txt").write_text("content1")
    (test_dir / "file2.py").write_text("print('hello')")
    return test_dir


@pytest.fixture
def sample_config(temp_directory: Path) -> AppConfig:
    """Create a sample application configuration."""
    return AppConfig(
        search_dir=str(temp_directory),
        extensions=(".txt", ".py"),
    )
```

---

## 📐 Standards de Qualité

### Outils de Qualité

| Outil      | Purpose                      | Commande                        |
| ---------- | ---------------------------- | ------------------------------- |
| **Ruff**   | Formatter & linter rapide    | `ruff format .`, `ruff check .` |
| **Pylint** | Analyse statique approfondie | `pylint src/profiles`         |
| **pytest** | Framework de test            | `pytest --cov=src/profiles`   |
| **pyright**| Vérification des types       | `pyright src/profiles`        |

### Métriques Cibles

| Métrique                    | Cible       | Outil                 |
| --------------------------- | ----------- | --------------------- |
| **Score Pylint**            | > 8.0       | Pylint                |
| **Couverture de test**      | > 85%       | pytest-cov            |
| **Complexité cyclomatique** | < 15        | pylint (R0915)        |
| **Longueur de fonction**    | < 50 lignes | Revue manuelle        |
| **Dette technique**         | < 1h        | SonarQube (optionnel) |

### Règles de Nommage

**Classes** :
- PascalCase : `FileScanner`, `ConfigService`
- Nom descriptif : éviter `SF`, `FC`

**Fonctions/Méthodes** :
- snake_case : `scan_directory`, `merge_configs`
- Verbe + objet : `get_file_info`, `validate_extension`

**Variables** :
- snake_case : `file_path`, `extension_pattern`
- Éviter les noms trop courts sauf boucles : `i`, `j`, `k`

**Constantes** :
- UPPER_SNAKE_CASE : `MAX_FILE_SIZE`, `DEFAULT_LOGGER`

---

## 🔒 Gestion des Erreurs

### Principes

1. **Fail Fast** : Échouer rapidement avec un message clair
2. **Graceful Degradation** : Dégradation élégante quand possible
3. **Informative Errors** : Messages d'erreur explicites
4. **No Silent Failures** : Jamais d'échec silencieux

### Patterns Recommandés

```python
# ✅ CORRECT : Gestion d'erreur explicite
from dataclasses import dataclass
from typing import Literal


@dataclass
class ActionResult:
    """Result of a domain action."""

    status: Literal["SUCCESS", "NOT_FOUND", "FAILED"]
    message: str
    path: str | None = None


def launch_selected_file(
    directory: str,
    filename: str,
    release: str,
    username: str,
) -> ActionResult:
    """Launch a file with OS association.

    Returns:
        ActionResult with status and message (never raises)
    """
    file_path = os.path.join(directory, filename)

    if not os.path.exists(file_path):
        return ActionResult(
            status="NOT_FOUND",
            message=f"File not found: {file_path}",
        )

    try:
        os.startfile(file_path)  # Windows
        return ActionResult(
            status="SUCCESS",
            message=f"Launched: {file_path}",
            path=file_path,
        )
    except OSError as e:
        return ActionResult(
            status="FAILED",
            message=f"Failed to launch file: {e}",
        )


# ❌ WRONG : Exceptions non gérées
def launch_file(directory: str, filename: str) -> None:
    """Launch a file."""
    path = os.path.join(directory, filename)
    os.startfile(path)  # May raise OSError silently
```

---

## 🔄 Réutilisabilité et Extensibilité

### Interfaces Abstraites

```python
from abc import ABC, abstractmethod
from typing import Protocol


# ✅ CORRECT : Interface pour scanner extensible
class FileScannerProtocol(Protocol):
    """Protocol for file scanners."""

    def scan(self, directory: str, recursive: bool = True) -> list[str]:
        """Scan directory for files."""
        ...


class DirectoryScanner:
    """Standard directory scanner."""

    def scan(self, directory: str, recursive: bool = True) -> list[str]:
        """Scan directory using os.walk."""
        ...


class GitAwareScanner:
    """Scanner that respects .gitignore."""

    def scan(self, directory: str, recursive: bool = True) -> list[str]:
        """Scan directory ignoring gitignored files."""
        ...


# Utilisation polymorphe
def process_files(scanner: FileScannerProtocol, directory: str) -> None:
    """Process files using any scanner implementation."""
    files = scanner.scan(directory)
    for f in files:
        print(f)
```

### Injection de Dépendances

```python
# ✅ CORRECT : DI pour testabilité
class FileProcessor:
    """Process files with injectable dependencies."""

    def __init__(
        self,
        scanner: FileScannerProtocol,
        logger: Logger,
        config: AppConfig,
    ) -> None:
        self.scanner = scanner
        self.logger = logger
        self.config = config

    def process(self, directory: str) -> int:
        """Process all files in directory."""
        files = self.scanner.scan(directory)
        self.logger.info(f"Found {len(files)} files")
        return len(files)


# Test avec mock
def test_file_processor():
    mock_scanner = Mock()
    mock_scanner.scan.return_value = ["file1.txt", "file2.py"]
    mock_logger = Mock()
    mock_config = AppConfig(search_dir="/tmp", extensions=(".mttl",))

    processor = FileProcessor(mock_scanner, mock_logger, mock_config)
    result = processor.process("/tmp")

    assert result == 2
    mock_scanner.scan.assert_called_once_with("/tmp")
```

---

## 📋 Checklist de Revue de Code

### Avant Commit

- [ ] **Ruff format** appliqué : `ruff format .`
- [ ] **Ruff lint** passe : `ruff check --fix .`
- [ ] **Pylint** score > 8.0 : `pylint src/profiles`
- [ ] **Tests** passent : `pytest`
- [ ] **Couverture** > 85% : `pytest --cov=src/profiles`
- [ ] **Aucun TODO** laissé (ou documenté dans le tracker d'issues)
- [ ] **Type hints** ajoutés pour les fonctions publiques
- [ ] **Docstrings** présents pour les APIs publiques
- [ ] **AGENTS.md à jour** si l'arborescence ou les imports publics ont changé (voir « Keep in sync »)

### Conformité Architecture

- [ ] **Core layer** n'a pas d'imports UI (Tkinter, FastAPI, React)
- [ ] **Couche présentation** (web/server/desktop, ou gui legacy) délègue la logique métier à `profiles.core.*`
- [ ] **Utils layer** est stateless et agnostique au framework
- [ ] **Imports** suivent les boundaries des couches
- [ ] **Aucune dépendance circulaire** entre modules
- [ ] **SRP** respecté pour chaque classe/fonction
- [ ] **DRY** : pas de duplication de logique
- [ ] **KISS** : complexité minimale

---

## 🚀 Workflow de Développement

### Installation

```bash
# Installation en mode développement
pip install -e ".[dev]"

# Installer les hooks pre-commit (recommandé)
pre-commit install
```

### Commandes Quotidiennes

```bash
# Formater le code
ruff format .

# Corriger les problèmes de lint
ruff check --fix .

# Vérifier la qualité complète
pylint src/profiles && pytest

# Vérifier avant push
pre-commit run --all-files

# Générer le rapport de couverture
pytest --cov=src/profiles --cov-report=html
open htmlcov/index.html
```

### CI/CD Recommandé

> Aligné sur les workflows réels du dépôt (`.github/workflows/`), qui
> utilisent `actions/checkout@v5` et `astral-sh/setup-uv@v6` avec uv.

```yaml
name: CI

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - name: Set up Python (uv)
        uses: astral-sh/setup-uv@v6
      - name: Install dependencies
        run: uv sync --locked
      - name: Format check
        run: uv run ruff format --check .
      - name: Lint check
        run: uv run ruff check .
      - name: Pylint check
        run: uv run pylint src/profiles --fail-under=8.0
      - name: Run tests with coverage
        run: uv run pytest --cov=src/profiles --cov-report=xml --cov-fail-under=85
```

---

## 📚 Guide pour Ajouter un Nouveau Front-end

> ProFiles embarque déjà un front-end web complet (React PWA +
> `profiles.server` FastAPI intégré + shell PyWebView `profiles.desktop`).
> L'exemple ci-dessous montre comment s'appuyer sur l'API Python du core pour
> créer un front-end alternatif (CLI, TUI, …). Les imports ci-dessous sont
> vérifiés contre la surface publique de `profiles.core` ; des exemples
> complets figurent dans `docs/advanced/guide-avance.fr.md`.

1. **Importer depuis le core layer** (surface publique recommandée) :
   ```python
   from profiles.core import (
       scan_and_process,
       launch_selected_file,
       ActionStatus,
       auto_select_directory,
       collect_system_info,
       load_config,
   )

   # Ou en import direct de sous-paquets, pour un contrôle fin :
   from profiles.core.processing.scanner import scan_and_process, ScannedFile
   from profiles.core.config.service import auto_select_directory, find_active_config
   from profiles.core.config.loader import load_config
   from profiles.core.actions import launch_selected_file, ActionStatus, ActionResult
   from profiles.core.environment.system import collect_system_info, SystemInfo
   ```

2. **Sélectionner le bon répertoire** :
   ```python
   config = load_config()  # cherche .profiles dans l'arborescence si chemin None
   hostname = collect_system_info().hostname
   directory = auto_select_directory(config, hostname)
   ```

3. **Scanner les fichiers** :
   ```python
   results = scan_and_process(
       directory,
       extension=".mttl",
       recursive=True,
   )
   ```

4. **Lancer un fichier** :
   ```python
   result = launch_selected_file(
       directory,
       results[0].filename,
       config.release,
       username,
   )
   if result.status is not ActionStatus.SUCCESS:
       ...
   ```

5. **Présenter les résultats** dans le format du front-end (table terminal, panel curses, etc.)

6. **Zéro import d'UI** nécessaire (pas de Tkinter, pas de React)

---

## 🎓 Ressources et Références

### Documentation

- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Clean Code](https://amzn.to/3G5BbJd)
- [Python Style Guide (PEP 8)](https://peps.python.org/pep-0008/)
- [Type Hints (PEP 484)](https://peps.python.org/pep-0484/)

### Outils

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Pylint Documentation](https://pylint.pycqa.org/)
- [pytest Documentation](https://docs.pytest.org/)

---

**Note** : Ce document est vivant et doit évoluer avec le projet. Les bonnes pratiques doivent être révisées régulièrement et adaptées aux besoins spécifiques du projet. En particulier, la **Structure de l'Application**, les **imports des extraits** et les **exemples de fixtures** doivent rester synchronisés avec le code — un chemin d'import obsolète ici génère du code cassé dans les suggestions des agents. En cas de doute, la source de vérité est `src/profiles/core/__init__.py` (surface publique) et `docs/advanced/guide-avance.fr.md` (exemples vérifiés).
