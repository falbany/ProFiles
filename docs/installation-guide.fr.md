# Procédure d'Installation ProFiles

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **Installation** |
> ⚙️ **[Configuration](./configuration-profile.fr.md)** |
> 🔧 **[Hooks](./hooks-guide.en.md)** |
> 📊 **[Colonnes Dynamiques](./columns-guide.fr.md)** |
> 🚀 **[Guide Avancé](./advanced/guide-avance.fr.md)** |
> 🇬🇧 **[English Version](./installation-guide.en.md)**

---

## Prérequis

- **Python** : Version 3.11 ou supérieure
- **Système d'exploitation** : Windows, Linux, ou macOS
- **Permissions** : Droits d'écriture dans le répertoire de projet

## Méthode 1 : Installation avec l'Assistant (Recommandé)

ProFiles inclut un assistant d'installation interactif qui guide l'utilisateur à travers le processus.

### Étapes

1. **Lancer l'assistant**

   ```bash
   python install.py
   ```

2. **Choisir la cible d'installation**

   L'assistant propose deux options :

   - **[1] New Virtual Environment (.venv)** — Environnement isolé (recommandé)
   - **[2] System Python** — Installation système globale (nécessite des permissions)

   ```
   Select your preference: 1
   ```

3. **Choisir le mode de travail**

   - **[1] Standard** — Installation prête à l'emploi
   - **[2] Development** — Install modifiable + suite complète de développement

   ```
   Select your workflow: 1
   ```

4. **Confirmer l'installation**

   ```
   Ready to proceed? (y/n): y
   ```

5. **Créer un raccourci bureau (Windows)**

   ```
   Create a desktop shortcut for quick access? (y/n): y
   ```

### Résultat

L'assistant affiche les commandes de démarrage rapide :

```
✨ ProFiles successfully installed!

Quick Start:
1. Activate venv:    .venv\Scripts\activate
2. Launch GUI:       profiles
3. Headless mode:    profiles --headless
4. Run as module:    python -m profiles
```

---

## Méthode 2 : Installation Manuelle

### 1. Créer un environnement virtuel (recommandé)

```bash
python -m venv .venv
```

### 2. Activer l'environnement virtuel

**Windows :**

```bash
.venv\Scripts\activate
```

**Linux/macOS :**

```bash
source .venv/bin/activate
```

### 3. Installer les dépendances

**Mode Standard :**

```bash
pip install -e .
```

**Mode Développement :**

```bash
pip install -e ".[dev]"
```

### 4. Vérifier l'installation

```bash
python -m profiles --help
```

---

## Dépendances

### Dépendances principales

- `sv-ttk` — Thème Sun Valley ttk (inspiration Material Design 3)
- `darkdetect` — Détection automatique du thème système (clair/sombre)

Ces dépendances sont déclarées dans `pyproject.toml` et installées automatiquement avec `pip install .`.

### Dépendances de développement (optionnel)

Les dépendances de développement sont installées avec `pip install -e ".[dev]"` :

- `ruff` — Formater et linter Python
- `pylint` — Analyse statique du code
- `pytest` — Framework de test
- `pytest-cov` — Couverture de code
- `pre-commit` — Hooks pre-commit

---

## Commandes de Développement

### Formatage du code

```bash
ruff format .
```

### Vérification linting

```bash
ruff check .
ruff check --fix .
```

### Analyse Pylint

```bash
pylint src/profiles
```

### Exécution des tests

```bash
pytest
pytest --cov=src/profiles --cov-report=term-missing
```

### Hooks pre-commit

```bash
# Installer les hooks
pre-commit install

# Exécuter manuellement
pre-commit run --all-files
```

---

## Configuration Post-Installation

### 1. Générer le fichier de configuration

```bash
python -m profiles --init
```

Cela crée un fichier `.profiles` dans le répertoire courant avec les paramètres par défaut.

### 2. Personnaliser la configuration

Éditez le fichier `.profiles` pour adapter :

- Répertoire de recherche
- Extensions de fichiers
- Filtres de recherche
- Couleurs de lignes
- Paramètres par machine

Voir [Configuration .profiles](./configuration-pylaunch.fr.md) pour les détails.

---

## Modes d'Utilisation

### Mode Graphique (GUI)

```bash
python -m profiles
```

ou

```bash
profiles
```

### Mode Sans Interface (CLI)

```bash
python -m profiles --headless
```

### Spécifier un fichier de configuration

```bash
python -m profiles --config /chemin/vers/.profiles
```

### Régénérer le fichier de configuration

```bash
python -m profiles --init
```

---

## Meilleures Pratiques

### Flux de Travail de Développement

1. **Toujours utiliser un environnement virtuel** pour l'isolation
2. **Installer en mode modifiable** pour le développement : `pip install -e ".[dev]"`
3. **Exécuter les hooks pre-commit** avant chaque commit : `pre-commit run --all-files`
4. **Maintenir la qualité du code** : Garder le score Pylint au-dessus de 8.0
5. **Écrire des tests** pour les nouvelles fonctionnalités : Viser >85% de couverture

### Déploiement en Production

1. **Utiliser l'installation standard** : `pip install -e .`
2. **Tester en environnement isolé** avant déploiement
3. **Documenter la configuration** dans le fichier `.profiles`
4. **Créer un raccourci bureau** pour un accès facile
5. **Vérifier le mode headless** fonctionne pour les scripts automatisés

### Checklist de Qualité du Code

Avant de commettre des modifications :

- [ ] Exécuter `ruff format .` pour formater le code
- [ ] Exécuter `ruff check --fix .` pour corriger les problèmes de linting
- [ ] Exécuter `pylint src/profiles` et vérifier le score > 8.0
- [ ] Exécuter `pytest` pour s'assurer que tous les tests passent
- [ ] Vérifier la couverture de test : `pytest --cov=src/profiles`
- [ ] Supprimer tous les commentaires `TODO` ou les documenter
- [ ] Ajouter des indices de type pour les nouvelles fonctions publiques
- [ ] Ajouter des docstrings pour les APIs publiques

---

## Utilisation Avancée

### Mode Headless pour l'Automatisation

ProFiles peut s'exécuter sans interface graphique pour les flux de travail automatisés :

```bash
# Mode headless de base
python -m profiles --headless

# Avec configuration spécifique
python -m profiles --headless --config /chemin/vers/.profiles

# Utilisation programmatique
from profiles.core.scanner import scan_and_process
from profiles.core.actions import launch_selected_file

# Scanner un répertoire
results = scan_and_process(
    directory="/chemin/vers/rep",
    extension=".lnk",
    recursive=True,
    filter_text=""
)

# Lancer le premier résultat
if results:
    result = launch_selected_file(
        directory="/chemin/vers/rep",
        filename=results[0].filename,
        release="v1.0",
        username="automatisation"
    )
    print(f"Statut de lancement : {result.status}")
```

### Interfaces Personnalisées

La couche principale de ProFiles est indépendante de l'interface graphique. Vous pouvez créer des interfaces personnalisées :

```python
# Exemple CLI
from profiles.core import config_service, scanner, actions

# Sélection automatique de configuration
config_dir = config_service.auto_select_directory(None, "mon-ordinateur")

# Scanner les fichiers
results = scanner.scan_and_process(
    directory=config_dir, extension=".lnk", recursive=True, filter_text=""
)

# Afficher les résultats
for file in results:
    print(f"{file.filename} - {file.version}")
```

Voir [AGENTS.md](../AGENTS.md) pour les détails de l'architecture.

---

## Guide de Dépannage Détaillé

### Problème : L'assistant échoue à installer les dépendances

**Symptômes** : L'installation s'arrête avec une erreur concernant `sv-ttk` ou `darkdetect`.

**Diagnostic** :
- Problèmes de connectivité réseau
- Corruption du cache pip
- Problèmes de permissions

**Solution** :
```bash
# Vider le cache pip
pip cache purge

# Installer les dépendances directement
pip install sv-ttk darkdetect

# Exécuter l'installateur à nouveau
python install.py

# Ou installer avec sortie détaillée
pip install -v sv-ttk darkdetect
```

### Problème : Commande `profiles` non trouvée

**Symptômes** : La commande n'est pas reconnue après l'installation.

**Diagnostic** :
- Environnement virtuel non activé
- Script non dans le PATH
- Installation échouée silencieusement

**Solution** :
```bash
# Vérifier l'installation
pip show profiles

# Vérifier l'emplacement du script
# Windows :
.venv\Scripts\profiles.exe --help

# Linux/macOS :
.venv/bin/profiles --help

# Ajouter au PATH (Linux/macOS)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Problème : Permission refusée sur installation système

**Symptômes** : Erreurs de permission lors de l'installation sans environnement virtuel.

**Diagnostic** :
- Écriture dans Python système nécessite des privilèges admin
- L'utilisateur n'a pas les permissions d'écriture

**Solution** :

**Option 1 : Utiliser un environnement virtuel (recommandé)**
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
pip install -e .
```

**Option 2 : Utiliser l'installation utilisateur**
```bash
pip install --user -e .
```

**Option 3 : Utiliser les privilèges administrateur**
```bash
# Windows (Exécuter en tant qu'Administrateur)
pip install -e .

# Linux/macOS
sudo pip install -e .
```

### Problème : Interface graphique ne s'affiche pas

**Symptômes** : L'application démarre mais aucune fenêtre n'apparaît, ou erreur Tkinter.

**Diagnostic** :
- Tkinter non installé (courant sur les installations Linux minimales)
- Environnement d'affichage non défini (sessions distantes Linux)
- Transfert X11 non activé

**Solution** :

**Windows** : Tkinter est inclus par défaut. Réinstallez Python si nécessaire.

**Linux** :
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# RHEL/CentOS
sudo dnf install python3-tkinter

# Arch Linux
sudo pacman -S python-tkinter
```

**SSH à distance** :
```bash
# Activer le transfert X11 dans SSH
ssh -X user@host

# Ou utiliser VNC/X forwarding
```

### Problème : Fichier de configuration non trouvé

**Symptômes** : ProFiles utilise les valeurs par défaut au lieu de la configuration personnalisée.

**Diagnostic** :
- Fichier `.profiles` au mauvais emplacement
- Nom de fichier incorrect (sensible à la casse sur Unix)
- Problème de permissions de fichier

**Solution** :
```bash
# Vérifier le répertoire courant
pwd  # Linux/macOS
cd   # Windows

# Vérifier si le fichier existe
ls -la .profiles  # Linux/macOS
dir .profiles     # Windows

# Utiliser le chemin explicite
python -m profiles --config /chemin/complet/vers/.profiles
```

### Problème : Scan lent sur les grands répertoires

**Symptômes** : L'interface se fige ou prend plusieurs minutes pour scanner.

**Diagnostic** :
- Scan récursif sur une très grande arborescence de répertoires
- Aucun motif d'exclusion configuré
- Latence du lecteur réseau

**Solution** :
```ini
# Dans le fichier .profiles
[LAUNCHER]
# Exclure les répertoires courants volumineux
search_exclude_dirs = .git, node_modules, __pycache__, bin, obj, Debug, Release

# Limiter les extensions
extensions = .lnk, .pdf

# Ou désactiver le récursif initialement
recursive_search = Faux
```

---

## Optimisation des Performances

### Pour les Grands Projets (>10 000 fichiers)

1. **Utiliser le scan non-récursif** :
   ```ini
   recursive_search = Faux
   ```

2. **Exclure les répertoires inutiles** :
   ```ini
   search_exclude_dirs = .git, __pycache__, node_modules, build, dist
   ```

3. **Limiter les extensions de fichiers** :
   ```ini
   extensions = .lnk  # Scanner uniquement les types spécifiques
   ```

4. **Utiliser un répertoire de recherche spécifique** :
   ```ini
   search_dir = /chemin/vers/production/dossier_specifique  # Portée plus étroite
   ```

### Utilisation Mémoire

ProFiles utilise l'insertion par morceaux pour les grandes listes de fichiers. Si vous rencontrez des problèmes de mémoire :

- Réduire la profondeur récursive
- Augmenter la taille des morceaux dans le code (avancé)
- Utiliser des motifs de filtre pour limiter les résultats

---

## Désinstallation Complète

### Suppression Complète

**1. Désinstaller le package** :
```bash
pip uninstall profiles
```

**2. Supprimer l'environnement virtuel** :
```bash
# Windows
rmdir /s .venv

# Linux/macOS
rm -rf .venv
```

**3. Supprimer le fichier de configuration** :
```bash
# Windows
del .profiles

# Linux/macOS
rm .profiles
```

**4. Supprimer le raccourci bureau** (Windows) :
- Clic droit sur le raccourci sur le bureau
- Sélectionner "Supprimer"

**5. Supprimer les fichiers installés** (installation système) :
```bash
pip uninstall profiles
# Supprimer manuellement si nécessaire
rm -rf ~/.local/lib/python3.11/site-packages/profiles*
```

---

## Vérification et Tests

### Vérification Post-Installation

Après l'installation, vérifiez que tout fonctionne :

```bash
# 1. Vérifier l'installation du package
pip show profiles

# 2. Vérifier le lancement GUI
python -m profiles --help

# 3. Tester le mode headless
python -m profiles --headless

# 4. Exécuter les tests unitaires
pytest

# 5. Vérifier la qualité du code
pylint src/profiles
ruff check .
```

### Sortie Attendue

**`pip show profiles`** :
```
Name: profiles
Version: 1.0.0
Summary: Python MuTool Project Launcher
Location: c:\Git\GitLab-ST\profiles\src
Editable: true
```

**`python -m profiles --help`** :
```
usage: profiles [-h] [--config CONFIG] [--headless] [--init]

ProFiles - Production File Launcher

options:
  -h, --help       show this help message and exit
  --config CONFIG  Path to configuration file
  --headless       Run without GUI
  --init           Generate starter configuration file
```

---

## Support et Ressources

### Documentation

- **Configuration** : [configuration-pylaunch.fr.md](./configuration-pylaunch.fr.md)
- **Architecture** : [AGENTS.md](../AGENTS.md)
- **README** : [README.md](../README.md)

### Ressources de Développement

- **Code Source** : `src/profiles/`
- **Tests** : `tests/`
- **Exemples** : Voir les fichiers de test pour des exemples d'utilisation

### Obtenir de l'Aide

1. **Consulter la documentation** dans le dossier `docs/`
2. **Examiner les journaux d'erreur** dans les journaux de l'application
3. **Exécuter les tests** pour vérifier l'installation : `pytest -v`
4. **Vérifier les informations système** : `python -m profiles --headless`

---

## Informations de Version

- **Python** : 3.11+
- **Tkinter** : Requis pour l'interface graphique
- **Rich** : Requis pour l'assistant CLI
- **Licence** : Voir le fichier `LICENCE`

---

## Désinstallation

### Avec pip

```bash
pip uninstall profiles
```

### Supprimer l'environnement virtuel

```bash
rmdir /s .venv        # Windows
rm -rf .venv          # Linux/macOS
```

### Supprimer le fichier de configuration

```bash
rm .profiles          # Linux/macOS
del .profiles         # Windows
```

---

## Structure du Projet

```
profiles/
├── src/
│   └── profiles/
│       ├── core/           # Logique métier partagée
│       ├── gui/            # Interface Tkinter
│       ├── utils/          # Fonctions utilitaires
│       ├── app.py          # Cycle de vie application
│       └── config.py       # Configuration
├── tests/                  # Tests unitaires
├── docs/                   # Documentation
├── install.py              # Assistant d'installation
├── pyproject.toml          # Configuration package
└── .profiles               # Configuration utilisateur
```

---

## Méthode 4 : Installeur Natif (Briefcase)

Des installeurs pré-construits sont produits par la pipeline CI
Briefcase et joints à chaque release GitHub.

### Télécharger l'artefact

Depuis l'onglet [Actions](../../actions) ou la page
[Releases](../../releases), téléchargez l'artefact correspondant à
votre plateforme :

- `ProFiles-windows` → `ProFiles-2026.8.0.msi`
- `ProFiles-macos` → `ProFiles-2026.8.0.dmg`
- `ProFiles-ubuntu` → `profiles_2026.8.0_amd64.deb` et
  `ProFiles-2026.8.0.AppImage`

### Installation

- **macOS** : ouvrez le `.dmg`, glissez `ProFiles.app` dans
  `/Applications`. Premier lancement : clic droit → **Ouvrir**
  (contournement Gatekeeper ; les builds ne sont pas signés).
- **Windows** : exécutez le `.msi`. Si SmartScreen affiche un
  avertissement, cliquez sur **Informations complémentaires** →
  **Exécuter quand même**.
- **Linux (`.deb`)** : `sudo dpkg -i profiles_2026.8.0_amd64.deb`
  puis `sudo apt-get install -f` en cas de dépendances manquantes.
- **Linux (`.AppImage`)** : `chmod +x ProFiles-2026.8.0.AppImage`
  puis double-clic. Aucune installation requise.

### Lancement

Depuis le menu Démarrer (Windows), `/Applications` (macOS), ou le
lanceur d'applications de votre environnement de bureau (Linux).

---

## Support

Pour toute question ou problème, consultez :

- Documentation complète dans le dossier `docs/`
- Fichier `README.md` à la racine du projet
- Code source dans `src/profiles/`
