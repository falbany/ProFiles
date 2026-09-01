# Guide Avancé ProFiles

> 🏠 **[Documentation Home](../README.md)** |
> 📦 **[Installation](../installation-guide.fr.md)** |
> ⚙️ **[Configuration](../configuration-profile.fr.md)** |
> 🔧 **[Hooks](../hooks-guide.en.md)** |
> 📊 **[Colonnes Dynamiques](../columns-guide.fr.md)** |
> 🚀 **Guide Avancé** |
> 🇬🇧 **[English Version](./advanced-guide.en.md)**

---

Ce guide couvre les modèles d'utilisation avancés, l'automatisation et le développement d'interfaces personnalisées pour ProFiles.

## Table des Matières

- [Mode Headless pour l'Automatisation](#mode-headless-pour-lautomatisation)
- [Interfaces Personnalisées](#interfaces-personnalisées)
- [Utilisation de l'API Programmatique](#utilisation-de-lapi-programmatique)
- [Optimisation des Performances](#optimisation-des-performances)
- [Modèles d'Intégration](#modèles-dintégration)

---

## Mode Headless pour l'Automatisation

ProFiles peut s'exécuter sans interface graphique pour les flux de travail automatisés et le scripting.

### Utilisation de Base

```bash
# Exécuter en mode headless
python -m profiles --headless

# Avec fichier de configuration spécifique
python -m profiles --headless --config /chemin/vers/.profiles
```

### Cas d'Usage

- **Pipelines CI/CD** : Automatiser le lancement de fichiers dans les processus de construction
- **Tâches planifiées** : Exécuter des scans ou lancements périodiques
- **Traitement par lots** : Traiter plusieurs fichiers programmatiquement
- **Exécution distante** : Exécuter sur des serveurs sans capacités d'affichage

---

## Interfaces Personnalisées

L'architecture de ProFiles sépare la logique principale de la couche de présentation, permettant des interfaces personnalisées.

### Aperçu de l'Architecture

```
┌─────────────────────────────────────────┐
│         Couche Interface                │
│  (GUI / CLI / TUI / Web / Personnalisé) │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Couche Principale               │
│  (profiles.core.*)                      │
│  ├── config/       # models, service,   │
│  │                 # loader, reader, io  │
│  ├── environment/  # system, execution  │
│  │                 # (launch hooks)     │
│  ├── processing/   # scanner,           │
│  │                 # column_extractor   │
│  ├── telemetry/    # diagnostics        │
│  └── actions.py                         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Couche Utilitaires              │
│  (profiles.utils.*)                   │
│  - file_utils.py                        │
│  - network.py                           │
│  - search_parser.py                     │
│  - shortcut.py                          │
└─────────────────────────────────────────┘
```

### Créer une Interface CLI

```python
#!/usr/bin/env python3
"""Interface CLI simple pour ProFiles."""

import argparse
import sys
from profiles.core import load_config, scan_and_process, launch_selected_file, ActionStatus
from profiles.core.config import auto_select_directory


def main():
    parser = argparse.ArgumentParser(description="ProFiles CLI")
    parser.add_argument("--directory", type=str, help="Répertoire à scanner")
    parser.add_argument("--extension", type=str, default=".lnk", help="Extension de fichier")
    parser.add_argument("--filter", type=str, default="", help="Texte de filtre")
    parser.add_argument("--recursive", action="store_true", help="Scan récursif")
    parser.add_argument("--launch", type=str, help="Lancer un fichier spécifique par nom")
    parser.add_argument("--config", type=str, help="Chemin du fichier de configuration")

    args = parser.parse_args()

    # Charger la configuration (recherche automatiquement dans l'arborescence si le chemin est None)
    config = load_config(args.config)

    # Déterminer le répertoire
    directory = args.directory or auto_select_directory(config, None)

    if args.launch:
        # Lancer un fichier spécifique
        result = launch_selected_file(
            directory=directory, filename=args.launch, release=config.release, username="cli"
        )
        print(f"Résultat du lancement : {result.status}")
        return 0 if result.status == ActionStatus.SUCCESS else 1
    else:
        # Scanner et afficher les résultats
        results = scan_and_process(
            directory=directory,
            extension=args.extension,
            recursive=args.recursive,
            filter_text=args.filter,
        )

        print(f"Trouvé {len(results)} fichiers :")
        for file in results:
            print(f"  {file.filename} - {file.version}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Créer une Interface Web

```python
from flask import Flask, jsonify, request
from profiles.core import scan_and_process, launch_selected_file, ActionStatus

app = Flask(__name__)


@app.route("/scan", methods=["GET"])
def scan():
    """Scanner un répertoire et retourner les résultats."""
    directory = request.args.get("directory", "/chemin/vers/rep")
    extension = request.args.get("extension", ".lnk")
    recursive = request.args.get("recursive", "false").lower() == "true"

    results = scan_and_process(
        directory=directory, extension=extension, recursive=recursive, filter_text=""
    )

    return jsonify(
        [{"filename": f.filename, "version": f.version, "path": f.path} for f in results]
    )


@app.route("/launch", methods=["POST"])
def launch():
    """Lancer un fichier."""
    data = request.json
    result = launch_selected_file(
        directory=data["directory"],
        filename=data["filename"],
        release=data.get("release", "v1.0"),
        username=data.get("username", "web"),
    )

    return jsonify({"status": result.status.value, "message": result.message, "path": result.path})


if __name__ == "__main__":
    app.run(debug=True)
```

---

## Utilisation de l'API Programmatique

### Imports des Modules Principaux

```python
# Import de haut niveau (recommandé pour la plupart des cas d'usage)
from profiles.core import (
    # Scanner
    scan_and_process,
    ScannedFile,
    is_simple_extension,
    # Config
    auto_select_directory,
    find_active_config,
    merge_config_overrides,
    get_unique_directories,
    # Actions
    launch_selected_file,
    open_config_file,
    open_log_file,
    ActionResult,
    ActionStatus,
    # Infos système
    SystemInfo,
    collect_system_info,
)

# Imports directs de sous-paquets (pour un contrôle fin)
from profiles.core.processing.scanner import scan_and_process, ScannedFile
from profiles.core.config.service import auto_select_directory, find_active_config
from profiles.core.config.models import AppConfig, MachineConfiguration
from profiles.core.config.loader import load_config
from profiles.core.actions import launch_selected_file, ActionStatus, ActionResult
from profiles.core.environment.system import collect_system_info, SystemInfo
from profiles.core.telemetry.diagnostics import get_logger, configure_logger
```

### Exemple : Traitement par Lots de Fichiers

```python
from profiles.core import scan_and_process, launch_selected_file, ActionStatus


def traiter_tous_les_fichiers(directory, extension=".lnk"):
    """Scanner et lancer tous les fichiers correspondants."""
    results = scan_and_process(
        directory=directory, extension=extension, recursive=True, filter_text=""
    )

    success_count = 0
    for file in results:
        result = launch_selected_file(
            directory=directory, filename=file.filename, release="v1.0", username="lot"
        )

        if result.status == ActionStatus.SUCCESS:
            success_count += 1
            print(f"✓ Lancé : {file.filename}")
        else:
            print(f"✗ Échoué : {file.filename} - {result.message}")

    print(f"\nTerminé : {success_count}/{len(results)} réussites")
    return success_count == len(results)
```

### Exemple : Pipeline de Filtre Personnalisé

```python
from profiles.core import scan_and_process


def scan_avance(directory, extension, version_min=None, motifs_exclusion=None):
    """Scanner avec logique de filtrage supplémentaire."""
    results = scan_and_process(
        directory=directory, extension=extension, recursive=True, filter_text=""
    )

    filtered = []
    for file in results:
        # Filtrer par version
        if version_min and file.version < version_min:
            continue

        # Filtrer par motifs d'exclusion
        if motifs_exclusion:
            if any(motif in file.filename for motif in motifs_exclusion):
                continue

        filtered.append(file)

    return filtered


# Utilisation
fichiers = scan_avance(
    directory="/chemin/vers/rep",
    extension=".lnk",
    version_min="v2.0",
    motifs_exclusion=["sauvegarde", "temporaire", "ancien"],
)
```

---

## Optimisation des Performances

### Optimiser les Grands Scans

Pour les répertoires avec >10 000 fichiers :

1. **Utiliser des extensions sélectives** :
   ```python
   results = scan_and_process(
       directory="/grand/repertoire",
       extension=".lnk",  # Extension spécifique
       recursive=True,
       filter_text="",
   )
   ```

2. **Exclure les répertoires courants volumineux** :
   ```ini
   [LAUNCHER]
   search_exclude_dirs = .git, node_modules, __pycache__, build, dist
   ```

3. **Utiliser le mode non-récursif initialement** :
   ```python
   # Première passe : non-récursif
   results = scan_and_process(directory="/chemin", extension=".lnk", recursive=False, filter_text="")

   # Deuxième passe : récursif seulement si nécessaire
   if len(results) < expected_min:
       results = scan_and_process(
           directory="/chemin", extension=".lnk", recursive=True, filter_text=""
       )
   ```

### Gestion Mémoire

ProFiles utilise l'insertion par morceaux pour les grandes listes de fichiers. Pour les interfaces personnalisées :

```python
from profiles.core import scan_and_process


def scan_avec_pagination(directory, extension, taille_page=100):
    """Scanner avec support de pagination."""
    all_results = scan_and_process(
        directory=directory, extension=extension, recursive=True, filter_text=""
    )

    # Retourner les résultats paginés
    total_pages = (len(all_results) + taille_page - 1) // taille_page

    def get_page(num_page):
        start = num_page * taille_page
        end = start + taille_page
        return all_results[start:end], total_pages

    return get_page
```

---

## Modèles d'Intégration

### Intégration CI/CD

```python
#!/usr/bin/env python3
"""Script d'intégration CI/CD."""

import sys
from profiles.core import scan_and_process


def ci_cd_valider(directory, extension, fichiers_requis):
    """Valider que les fichiers requis existent dans le répertoire."""
    results = scan_and_process(
        directory=directory, extension=extension, recursive=False, filter_text=""
    )

    filenames = {f.filename for f in results}
    missing = set(fichiers_requis) - filenames

    if missing:
        print(f"ERREUR : Fichiers requis manquants : {missing}")
        return False

    print(f"✓ Tous les {len(fichiers_requis)} fichiers requis présents")
    return True


if __name__ == "__main__":
    # Exemple : Valider les artefacts de construction
    requis = ["build.exe", "config.json", "README.md"]
    success = ci_cd_valider("/build/output", ".exe", requis)
    sys.exit(0 if success else 1)
```

### Intégration de Journalisation

```python
from profiles.core import collect_system_info
from profiles.core.telemetry.diagnostics import get_logger, configure_logger


def configurer_journalisation_audit():
    """Configurer la journalisation d'audit pour la conformité."""
    info = collect_system_info()
    logger = configure_logger(
        log_path="audit.log",
        source=f"automatisation-{info.hostname}",
        level="INFO",
    )
    
    return logger


def journaliser_evenement_lancement(nom_fichier, utilisateur, succes):
    """Journaliser l'événement de lancement de fichier."""
    logger = configurer_journalisation_audit()
    
    if succes:
        logger.info(f"Fichier lancé : {nom_fichier} par {utilisateur}")
    else:
        logger.warning(f"Lancement échoué : {nom_fichier} par {utilisateur}")
```

### Intégration de Surveillance

```python
from profiles.core import scan_and_process
import time


def surveiller_repertoire(directory, extension, intervalle=60):
    """Surveiller le répertoire pour les changements."""
    previous_files = set()

    while True:
        results = scan_and_process(
            directory=directory, extension=extension, recursive=False, filter_text=""
        )

        current_files = {f.filename for f in results}

        # Détecter les nouveaux fichiers
        new_files = current_files - previous_files
        if new_files:
            print(f"Nouveaux fichiers détectés : {new_files}")

        # Détecter les fichiers supprimés
        removed_files = previous_files - current_files
        if removed_files:
            print(f"Fichiers supprimés : {removed_files}")

        previous_files = current_files
        time.sleep(intervalle)
```

---

## Meilleures Pratiques

### Gestion des Erreurs

```python
from profiles.core import launch_selected_file, ActionStatus


def lancement_securise(directory, nom_fichier):
    """Lancer avec gestion d'erreur complète."""
    try:
        result = launch_selected_file(
            directory=directory, filename=nom_fichier, release="v1.0", username="system"
        )

        if result.status == ActionStatus.SUCCESS:
            return True, "Succès"
        elif result.status == ActionStatus.NOT_FOUND:
            return False, f"Fichier non trouvé : {nom_fichier}"
        elif result.status == ActionStatus.FAILED:
            return False, f"Lancement échoué : {result.message}"
        else:
            return False, f"Statut inconnu : {result.status}"

    except Exception as e:
        return False, f"Exception : {str(e)}"
```

### Validation de Configuration

```python
from profiles.core import auto_select_directory


def valider_configuration(nom_ordinateur, repertoire_attendu):
    """Valider la configuration avant utilisation."""
    selected = auto_select_directory(None, nom_ordinateur)
    
    if not selected:
        return False, "Aucune configuration trouvée pour le nom d'hôte"
    
    if selected != repertoire_attendu:
        return False, f"Discordance de répertoire : {selected} != {repertoire_attendu}"
    
    return True, "Configuration valide"
```

---

## Dépannage

### Problème : Mode headless ne trouve pas la configuration

**Solution** : Spécifier explicitement le chemin de configuration :

```bash
python -m profiles --headless --config /chemin/absolu/.profiles
```

### Problème : Erreurs d'import dans interface personnalisée

**Solution** : S'assurer que `src/` est dans le chemin Python :

```python
import sys
from pathlib import Path

# Ajouter le répertoire src au chemin
sys.path.insert(0, str(Path(__file__).parent / "src"))

from profiles.core import scan_and_process
```

### Problème : Dégradation des performances avec les grands répertoires

**Solution** : Implémenter la pagination ou le filtrage :

```python
# Utiliser un filtre pour réduire l'ensemble de résultats
results = scan_and_process(
    directory="/grand/rep",
    extension=".lnk",
    recursive=True,
    filter_text="production",  # Réduire les résultats
)
```

---

## Ressources

- **API Principale** : Voir `src/profiles/core/` pour la documentation des modules
- **Architecture** : Voir `AGENTS.md` pour les détails de l'architecture en couches
- **Tests** : Voir `tests/test_core_*` pour des exemples d'utilisation
- **Configuration** : Voir [configuration-pylaunch.fr.md](../configuration-pylaunch.fr.md)

---

*Dernière mise à jour : 2026-08-02*
