<div align="center">

![Bannière ProFiles](img/ProFiles_banner.png)

[![Plateformes](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat)](#-installation)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat)](https://github.com/astral-sh/ruff)
[![Pylint](https://img.shields.io/badge/linting-pylint-09A64D?style=flat&logo=pylint&logoColor=white)](https://github.com/pylint-dev/pylint)
[![License](https://img.shields.io/github/license/falbany/ProFiles?style=flat&color=brightgreen)](./LICENCE)
[![GitHub](https://img.shields.io/badge/GitHub-falbany%2FProFiles-181717?style=flat&logo=github)](https://github.com/falbany/ProFiles)

🇬🇧 [English](./README.md) | 🇫🇷 **Français**

</div>

---

**ProFiles** s'adapte à tout workflow basé sur des fichiers grâce à une configuration flexible, sans toucher au code. Parcourez des répertoires, filtrez avec des opérateurs de style Google, extrayez des métadonnées depuis les noms de fichiers, et lancez vos fichiers via les associations du système d'exploitation ou des arguments personnalisés. L'interface par défaut est une **web UI** moderne (PWA React) embarquée avec un serveur FastAPI intégré — utilisable comme fenêtre de bureau, dans n'importe quel navigateur du réseau, ou entièrement en mode headless.

<details>
<summary><b>Sommaire</b></summary>

- [✨ Fonctionnalités clés](#-fonctionnalités-clés)
  - [🔍 Recherche et navigation intelligentes](#-recherche-et-navigation-intelligentes)
  - [🚀 Exécuter et automatiser](#-exécuter-et-automatiser)
  - [⚙️ Auto-configuration](#️-auto-configuration)
- [🚀 Installation](#-installation)
  - [Option 1 : Installeur natif (recommandé)](#option-1--installeur-natif-recommandé)
  - [Option 2 : Installation en une ligne (développeurs)](#option-2--installation-en-une-ligne-développeurs)
  - [Option 3 : Assistant / Manuel](#option-3--assistant--manuel)
    - [Option 1 : pip (system-wide)](#option-1--pip-system-wide)
    - [Option 2 : pipx (recommandé pour une installation system-wide)](#option-2--pipx-recommandé-pour-une-installation-system-wide)
    - [Option 3 : uv (développement)](#option-3--uv-développement)
    - [Option 4 : Poetry (développement)](#option-4--poetry-développement)
  - [Build du frontend web](#build-du-frontend-web)
  - [Raccourci bureau](#raccourci-bureau)
- [💻 Utilisation](#-utilisation)
  - [Mode Web (par défaut)](#mode-web-par-défaut)
  - [Mode Navigateur / PWA (serveurs partagés)](#mode-navigateur--pwa-serveurs-partagés)
  - [Mode Tkinter historique (déprécié)](#mode-tkinter-historique-déprécié)
  - [Mode CLI / Headless (en cours de développement)](#mode-cli--headless-en-cours-de-développement)
- [🛠 Configuration](#-configuration)
- [🏗 Architecture](#-architecture)
- [👨‍💻 Développement](#-développement)
- [📄 Licence \& support](#-licence--support)

</details>

## ✨ Fonctionnalités clés

### 🔍 Recherche et navigation intelligentes

- **Opérateurs de style Google** : AND implicite, `OR`, NOT (`-`), expression exacte (`"..."`).
- **Colonnes dynamiques** : extraction de métadonnées (version, device, révision) depuis les noms de fichiers via des règles regex.
- **Récursion parallèle** : scanning en thread d'arrière-plan haute performance qui garde l'interface réactive.
- **Exclusion par glob** : ignorer les répertoires bruyants (ex. `node_modules`, `.venv`) et filtrer les fichiers correspondant à des motifs glob (ex. `*backup*`, `~$*`).

### 🚀 Exécuter et automatiser

- **Web UI moderne** : PWA React + Vite servie par un backend FastAPI intégré — fenêtre de bureau (PyWebView), n'importe quel navigateur du LAN, ou headless.
- **Visionneuse de logs structurée** : modale intégrée avec filtres par niveau, tail en direct et ouverture externe des logs.
- **Workflows de lancement (hooks)** : interceptez les lancements de fichiers avec des workflows YAML à étapes. Exécutez des scripts en arrière-plan, affichez des notifications Markdown, ou remplacez complètement le lanceur par défaut de l'OS.
- **Lancement en un clic** : exécution native (Windows `os.startfile`, macOS `open`, Linux `xdg-open`).
- **Arguments CLI personnalisés** : clic droit pour lancer avec des arguments personnalisés, mémorisés par ligne.
- **Mode headless** : déclenchez des lancements de fichiers via CLI pour la CI/CD ou vos scripts.
- **Opérations sur les fichiers** : lancement en masse, copie de chemin, vérification de hash (SHA-256) et suppression sécurisée.

### ⚙️ Auto-configuration

- **Déploiement zero-touch** : détection du hostname/IP/chemin pour sélectionner automatiquement les configurations adaptées aux postes multi-stations.
- **Formatage visuel** : coloration des lignes par règles avec ajustement automatique du contraste.
- **Repli sans configuration** : des valeurs par défaut sensées permettent une utilisation immédiate sans fichier `.profiles`.

## 🚀 Installation

### Option 1 : Installeur natif (recommandé)

Téléchargez l'installeur pour votre OS depuis les
[Releases](../../releases) et double-cliquez — Python n'est pas requis :

- Windows : `ProFiles-<version>.msi`
- macOS : `ProFiles-<version>.dmg`
- Linux : `.deb` ou `.AppImage`

### Option 2 : Installation en une ligne (développeurs)

```bash
uv tool install profiles-app      # ou : pipx install profiles-app
```

_(requiert Python 3.11+ ; depuis un wheel de release GitHub : ajoutez `--from <wheel-url>`)_

### Option 3 : Assistant / Manuel

```bash
python install.py
```

_Lance un assistant interactif qui installe le paquet._

Depuis un clone des sources :

#### Option 1 : pip (system-wide)

```bash
git clone https://github.com/falbany/ProFiles.git
cd ProFiles
pip install .
```

#### Option 2 : pipx (recommandé pour une installation system-wide)

```bash
git clone https://github.com/falbany/ProFiles.git
cd ProFiles
pipx install .
```

#### Option 3 : uv (développement)

```bash
git clone https://github.com/falbany/ProFiles.git
cd ProFiles
uv sync          # crée .venv et installe les dépendances
uv run ProFiles  # lance l'application
uv run pytest --cov  # lance les tests
```

#### Option 4 : Poetry (développement)

```bash
git clone https://github.com/falbany/ProFiles.git
cd ProFiles
poetry install   # crée .venv et installe les dépendances
poetry run ProFiles  # lance l'application
```

### Build du frontend web

ProFiles inclut un frontend React qui est construit automatiquement lors de l'installation :

**Avec npm installé :**
Si Node.js et npm sont installés, le frontend web sera construit automatiquement :

```bash
pip install .
# Building web frontend...
# SUCCESS: Web build successful.
```

**Sans npm :**
Si npm n'est pas installé, ProFiles utilisera les assets web pré-construits :

```bash
pip install .
# WARNING: npm not found. Using pre-built web assets.
```

**Rebuild manuel :**
Pour reconstruire le frontend web après des modifications :

```bash
python -m profiles.web.build --force
```

Téléchargez Node.js depuis https://nodejs.org

### Raccourci bureau

Exécutez le script intégré pour générer un raccourci natif (`.lnk` Windows, Alias macOS ou `.desktop` Linux) :

```bash
python create_shortcut.py
```

## 💻 Utilisation

Le point d'entrée console est **`ProFiles`** (P et F majuscules) — enregistré dans `pyproject.toml` comme `[project.scripts]`. `python -m profiles` est équivalent.

### Mode Web (par défaut)

```bash
ProFiles
# ou
python -m profiles
```

Lance le serveur FastAPI local et ouvre le frontend React dans une fenêtre de bureau native PyWebView.

- **Interface** : le chrome web est bilingue (anglais / français). Utilisez le sélecteur de langue dans la barre de statut pour changer à la volée, ou définissez `language: en` / `language: fr` dans la section `defaults`.
- **Recherche** : utilisez `+` pour l'inclusion, `-` pour l'exclusion, `OR` pour les alternatives et `"..."` pour les expressions exactes.
- **Raccourcis clavier** : `Ctrl+F` (champ filtre) · `Ctrl+D` (champ répertoire) · `Ctrl+E` (champ extension) · `F5` (rescan) · `Ctrl+R` (recharger la config + rescan) · `Ctrl+H` (répertoire home) · `Ctrl+Shift+L` (visionneuse de logs) · `Ctrl+,` (ouvrir la config) · `Ctrl+Shift+T` (cycler le thème) · `Ctrl+B` (mode scanner de code-barres) · `Ctrl+Shift+B` (scanner de code-barres caméra) · `Ctrl+T` (timer de rescan auto) · `?` (dialogue des raccourcis).
- **PWA** : le frontend embarque un precache de service worker, la page peut donc être installée dans le navigateur comme une application.

### Mode Navigateur / PWA (serveurs partagés)

```bash
ProFiles --server-only
```

Lance le serveur FastAPI **sans** la fenêtre de bureau. Pointez n'importe quel navigateur du réseau vers `http://<hôte>:8088` (port par défaut). Voir le [Guide Serveur Réseau](./docs/network-server-guide.fr.md) pour la configuration firewall, hostname et multi-clients.

### Mode Tkinter historique (déprécié)

```bash
ProFiles --tkinter
```

L'interface de bureau Tkinter d'origine est conservée pour compatibilité uniquement et est **dépréciée** — les nouvelles fonctionnalités arrivent exclusivement sur le frontend web.

### Mode CLI / Headless (en cours de développement)

```bash
# Lancer un fichier spécifique directement, sans GUI
ProFiles --headless "path/to/script.py"

# Générer un .profiles de départ dans le répertoire courant
ProFiles --init

# Utiliser une configuration spécifique
ProFiles --config "/path/to/.profiles"
```

## 🛠 Configuration

ProFiles est piloté par un fichier **YAML** `.profiles`, recherché en remontant l'arborescence du système de fichiers.

```yaml
# ProFiles Configuration — Format YAML
version: 1

# Valeurs globales héritées par toutes les configurations
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
  search_exclude_files: [*backup*, ~$*, *.tmp]
  verbose: INFO
  scan_metrics: false

# Colonnes dynamiques extraites des noms de fichiers
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

# Configurations spécifiques par machine
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

# Workflows de lancement — interceptez les lancements avec une automatisation par étapes
hooks:
  failmode: warn           # warn | abort | skip (comportement en cas d'échec d'étape)
  timeout: 30              # Timeout en secondes pour les étapes bloquantes
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

_Voir la [Référence de Configuration](./docs/configuration-profile.fr.md), le [Guide des Colonnes Dynamiques](./docs/columns-guide.fr.md) et le **[Guide des Workflows de Lancement](./docs/hooks-guide.fr.md)** pour l'automatisation complète des workflows._

## 🏗 Architecture

Conception en couches propre, séparant la logique métier de la présentation.

```text
ProFiles/
├── src/profiles/
│   ├── core/              # Logique métier : config, environment/hooks, processing, telemetry
│   ├── server/            # Backend FastAPI — routes API REST, sessions workflow & scan
│   ├── web/               # Frontend PWA React + TypeScript + Vite (src/, dist/, build.py)
│   ├── desktop/           # Shell de bureau PyWebView & cycle de vie du serveur en fond
│   ├── gui/               # Couche de présentation Tkinter historique (dépréciée)
│   ├── utils/             # Helpers stateless (file ops, network, search parser, shortcut)
│   ├── app.py             # Cycle de vie applicatif (web desktop, server-only, Tk, headless)
│   └── config.py          # Ré-exports pratiques pour l'API de configuration
├── docs/                  # Documentation utilisateur (EN/FR)
└── tests/                 # Suite Pytest
```

Voir [`AGENTS.md`](./AGENTS.md) pour les règles d'architecture et les conventions détaillées.

## 👨‍💻 Développement

```bash
pip install -e .[dev]
pytest               # Lancer les tests
ruff check .         # Linting
ruff format .        # Formatage
pylint src/profiles/ # Analyse statique
```

Frontend web (Node.js requis) :

```bash
cd src/profiles/web
npm install
npm run build        # tsc + vite build — génère dist/ et rafraîchit le precache PWA
```

## 📄 Licence & support

- **Auteur** : [Florent ALBANY](https://github.com/falbany)
- **Licence** : [MIT](./LICENCE)
