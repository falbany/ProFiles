# Configuration .profiles

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **[Installation](./installation-guide.fr.md)** |
> ⚙️ **Configuration** |
> 🔧 **[Hooks](./hooks-guide.en.md)** |
> 📊 **[Colonnes Dynamiques](./columns-guide.fr.md)** |
> 🚀 **[Guide Avancé](./advanced/guide-avance.fr.md)** |
> 🇬🇧 **[English Version](./configuration-profile.en.md)**

---

## Vue d'ensemble

Le fichier `.profiles` est un fichier de configuration au format **YAML** qui personnalise le comportement de ProFiles. Ce fichier est recherché en commençant depuis le répertoire courant (CWD) et en descendant dans les sous-répertoires. Le premier fichier trouvé est utilisé. La recherche dans l'arborescence du CWD est ignorée lorsque le CWD ne porte aucune information de lancement — un démarrage via le menu Démarrer/ lanceur hérite de `System32`, du dossier personnel ou du répertoire d'installation de l'interpréteur/application — et le défaut par utilisateur `~/.profiles/.profiles` est chargé s'il existe.

Si aucun fichier `.profiles` n'est trouvé :
- En mode interactif (interface web, bureau ou navigateur) : ProFiles propose de créer un fichier de configuration par défaut — dans le dossier du projet pour un lancement en terminal, dans `~/.profiles` pour un lancement par lanceur
- En mode headless : ProFiles utilise des valeurs par défaut identiques à celles présentées dans ce document

## Création du fichier de configuration

### Méthode 1 : Proposition automatique (mode interactif)

Au premier lancement en mode interactif (interface web dans la fenêtre PyWebView ou dans le navigateur), si aucun fichier `.profiles` n'est trouvé, ProFiles propose de créer un fichier de configuration par défaut dans le répertoire courant. Lorsque ce répertoire ne porte aucune information de lancement (raccourci du menu Démarrer, lanceur avec un champ « Démarrer dans » vide, lancement depuis le Finder/dock), la proposition cible `~/.profiles/.profiles` — le même dossier que `profiles.log` — afin de ne jamais écrire dans un répertoire système ; chaque lancement suivant charge automatiquement ce défaut par utilisateur.

### Méthode 2 : Commande ligne de commande

```bash
python -m profiles --init
```

Cette commande crée un fichier `.profiles` avec des valeurs par défaut dans le répertoire courant. Le même contenu starter est également disponible dans l'interface web via le bouton **New** de l'éditeur de configuration (voir [Éditeur de Configuration](#éditeur-de-configuration-interface-web)).

### Méthode 3 : Création manuelle

Créez un fichier nommé `.profiles` dans votre répertoire de travail et copiez-y le contenu du modèle ci-dessous.

## Structure du fichier

Le fichier utilise le format **YAML** avec des clés hiérarchiques. Toutes les clés sont **insensibles à la casse**.

### Clés de niveau supérieur

- `version` — Version du schéma de configuration (actuellement `1`)
- `defaults` — Configuration globale héritée par toutes les configurations spécifiques aux machines
- `columns` — Définitions des colonnes dynamiques pour l'extraction de métadonnées des noms de fichiers
- `hooks` — Hooks d'exécution pour les lancements de fichiers (before/after/confirm/abort/instead)
- `configs` — Configurations spécifiques aux machines (dictionnaire nommé)

---

## Section `defaults` — Configuration globale

Cette section définit les paramètres par défaut applicables à toutes les machines.

### Paramètres

| Clé                   | Type               | Valeur par défaut    | Description                                                                 |
| --------------------- | ------------------ | -------------------- | --------------------------------------------------------------------------- |
| `title`               | string             | `""`                 | Titre personnalisé ajouté à la fenêtre principale                           |
| `gui_auto_launch`     | bool               | `true`               | Afficher la fenêtre de l'interface web lors de `python -m profiles`       |
| `close_after_execute` | bool               | `false`              | Fermer la fenêtre après un lancement réussi                                 |
| `theme`               | enum               | `"auto"`             | Thème d'interface : `"light"`, `"dark"` ou `"auto"` (Material Design 3)     |
| `language`            | enum               | `"en"`               | Langue de l'interface : `"en"` (anglais) ou `"fr"` (français) ; basculable via le bouton langue de la barre de statut (cycle en → fr → en) |
| `search_dir`          | string             | `""`                 | Répertoire de recherche par défaut pour le champ Directory                  |
| `recursive_search`    | bool               | `false`              | **Déprécié.** Anciennement l'état initial de la case à cocher Recursive ; remplacé par `max_search_depth`, qui pilote désormais le menu déroulant Depth de l'interface. Toujours analysé (le scanner l'honore en l'absence de surcharge explicite) ; l'interface web l'ignore ; un avertissement de dépréciation est journalisé au chargement. |
| `extensions`          | array of strings   | `[All, .lnk]`        | Présélections du combobox Extension (remplies par `configs`)      |
| `filters`             | array of strings   | `["", PROD, DEV]` | Présélections du combobox Filter ("" = tous les fichiers)                   |
| `row_colors`          | array of objects   | `[]`                 | Règles de coloration génériques appliquées à TOUS les configurations. Chaque objet a `pattern` (string) et `color` (#RRGGBB)        |
| `search_exclude_dirs` | array of strings   | `[.git, __pycache__]` | Noms de répertoires (motifs glob insensibles à la casse) ignorés lors du scan récursif. Prend en charge les jokers `*`, `?`, `[seq]` (`*tmp`, `node_modules`, `Debug*`, etc.) |
| `search_exclude_files` | array of strings | `[]`                 | Noms de fichiers (motifs glob insensibles à la casse) ignorés lors du scan. S'applique aux scans récursifs ET non récursifs. Même syntaxe de jokers que `search_exclude_dirs` (`*backup*`, `~$*`, `*.tmp`). Les motifs par configuration sont AJOUTÉS. |
| `max_search_depth`    | integer            | `10`                 | Profondeur de scan maximale (1 = répertoire sélectionné uniquement ; N = N niveaux sous la racine ; ∞ = illimité). Pilote le menu déroulant Depth de l'interface (options 1 à max(configurée, 25), plus ∞) |
| `verbose`             | enum               | `"INFO"`             | Verbosité du logging : `"DEBUG"` | `"INFO"` | `"WARNING"` | `"ERROR"` | `"CRITICAL"` |
| `scan_metrics`        | bool               | `false`              | Journaliser les métriques de performance après chaque scan                   |

### Valeurs booléennes acceptées

YAML standard : `true` / `false` / `yes` / `no` / `1` / `0` / `on` / `off`

### Exemple de configuration `defaults`

```yaml
defaults:
  title: "Mon Projet"
  gui_auto_launch: true
  close_after_execute: false
  theme: dark
  language: en
  search_dir: "C:/Users/YourName/Workspace"
  # recursive_search : déprécié — utilisez max_search_depth
  extensions: [All, .lnk, .pdf, .docx]
  filters: ["", PROD, DEV, ENG]
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#757575"
    - pattern: TMP
      color: "#BAC015"
  search_exclude_dirs: [.git, tmp, Obsolete, Debug, __pycache__, node_modules]
  search_exclude_files: ["*backup*", "~$*", "*.tmp"]
  verbose: INFO
  scan_metrics: false
```

### Exclusion par Glob (`search_exclude_dirs` / `search_exclude_files`)

Les deux clés acceptent des motifs glob insensibles à la casse avec les jokers `*`, `?`, `[seq]` (via `fnmatch` de Python).

| Clé | Portée | Défaut | Exemple |
| --- | --- | --- | --- |
| `search_exclude_dirs` | Noms de répertoires ignorés lors du scan **récursif** | `.git` | `node_modules`, `Debug*`, `*tmp` |
| `search_exclude_files` | Noms de fichiers Ignés lors du scan (**récursif et non récursif**) | `""` | `*backup*`, `~$*`, `*.tmp` |

> **⚠️ Quotez toujours les globs en YAML** : un élément de liste non quoté commençant par `*` (p. ex. `[*backup*, *.tmp]`) est interprété comme un **alias** YAML, pas comme une chaîne — le fichier ne charge pas avec `found undefined alias 'backup*'`. Écrivez plutôt `["*backup*", "*.tmp"]`. La même règle vaut pour toute valeur commençant par `*`.

**Ajout par configuration** : `search_exclude_files` dans une section `configs` est AJOUTÉ à la liste de base `defaults.search_exclude_files` — les deux jeux de motifs s'appliquent pour cette configuration. L'exclusion de répertoires (`search_exclude_dirs`) est globale uniquement.

---

## Section `configs` — Configurations par machine

Cette section est un dictionnaire où chaque clé est une configuration nommée. ProFiles sélectionne automatiquement la configuration dont les critères `match` correspondent à l'environnement d'exécution local (nom d'hôte, adresse IP ou chemin de système de fichiers).

La correspondance utilise une logique **OU** : si un motif quelconque dans un champ `match` correspond, la configuration est sélectionnée. Les motifs prennent en charge les jokers glob (`*`, `?`, `[seq]`) et les expressions régulières (préfixe `re:`). La correspondance est insensible à la casse.

Une configuration avec `match.hostname: ["*"]` (ou un bloc `match` vide) agit comme un piège universel — placez-la **DERNIÈRE** pour qu'elle ne masque pas les correspondances spécifiques.

Les configurations peuvent `extend` une autre configuration pour hériter des paramètres. Les listes sont fusionnées : éléments locaux d'abord, puis éléments hérités non déjà présents.

### Paramètres

| Clé           | Type               | Obligatoire | Description                                                            |
| ------------- | ------------------ | ----------- | ---------------------------------------------------------------------- |
| `extends`     | string             | Non         | Nom d'une autre configuration à hériter                                |
| `match`       | object             | Non         | Critères de sélection automatique (voir ci-dessous)                   |
| `scan`        | string ou array    | Non         | Chemin(s) de répertoire à scanner pour cette machine. Une chaîne est automatiquement convertie en liste. |
| `extensions`  | array of strings   | Non         | Présélections Extension par station (remplace `defaults.extensions`)   |
| `filters`     | array of strings   | Non         | Présélections Filter par station (remplace `defaults.filters`)         |
| `row_colors`  | array of objects   | Non         | Règles de coloration spécifiques à la configuration. AJOUTÉES à `defaults.row_colors` et vérifiées en premier |
| `search_exclude_files` | array of strings | Non | Motifs d'exclusion de fichiers par station. AJOUTÉS à `defaults.search_exclude_files`. Même syntaxe de jokers. |
| `search_exclude_dirs` | array of strings | Non | Motifs d'exclusion de répertoires par station (remplace `defaults.search_exclude_dirs`). |
| `max_search_depth`    | integer            | Non         | Profondeur de scan maximale par station (1 = répertoire sélectionné uniquement ; ∞ = illimité). Pilote le menu déroulant Depth de l'interface. |
| `recursive_search`    | bool               | Non         | **Déprécié.** Anciennement la surcharge de récursivité par station ; remplacé par `max_search_depth`, qui pilote désormais le menu déroulant Depth de l'interface. Toujours analysé (le scanner l'honore en l'absence de surcharge explicite) ; l'interface web l'ignore ; un avertissement de dépréciation est journalisé au chargement. |

### Champ `match`

Le champ `match` est un objet avec trois propriétés de liste optionnelles. Une correspondance unique dans n'importe quel champ suffit (logique OU) :

| Sous-clé   | Type           | Description                                                                 |
| --------- | -------------- | --------------------------------------------------------------------------- |
| `hostname` | list of strings | Motifs glob/regex correspondant au nom d'hôte de la machine (insensible à la casse) |
| `ip`       | list of strings | Motifs glob/regex correspondant à l'adresse IP de la machine (insensible à la casse) |
| `path`     | list of strings | Motifs glob/regex correspondant au chemin du répertoire de travail courant (normalisation multi-plateforme) |

**Syntaxe des motifs :**
- **Glob** : `WORKSTATION-*`, `10.0.0.*`, `/projects/*` — utilise `fnmatch` avec correspondance insensible à la casse
- **Regex** : préfixe `re:` — ex. `re:^192\.168\.\d+\.\d+$`, `re:^/projects/.*$`
- **Normalisation des chemins** : les chemins sont normalisés via `os.path.normpath` + `os.path.expanduser`, avec conversion des antislashs en slashs pour une correspondance multi-plateforme

### Exemple de configuration par machine

```yaml
configs:
  base:
    match:
      hostname: ["*"]
    scan: "C:/Users/YourName/Workspace"
    extensions: [All, .lnk]
    filters: ["", PROD]
    row_colors:
      - pattern: SPECIFIC
        color: "#FF0000"

  production:
    extends: base
    match:
      hostname: ["POSTE-TRAVAIL-01", "re:^POSTE-TRAVAIL-\\d+$"]
      ip: ["192.168.1.100", "10.0.0.*"]
      path: ["/projects/engineering", "re:^/data/.*$"]
    scan:
      - "Z:/Projects/Engineering/station1"
      - "Z:/Projects/Shared"
    extensions: [.pdf, .docx, .lnk, .xlsx]
    filters: [tmp, dev, prod]
    row_colors:
      - pattern: PROD
        color: "#1565C0"
      - pattern: DEV
        color: "#757575"
    search_exclude_files: ["*brouillon*", "*.bak"]
```

---

## Opérateurs de recherche

Les champs **Extension** et **Filter** sont éditables et acceptent des expressions Google-style :

### Syntaxe

| Opérateur    | Symbole | Exemple              | Description                             |
| ------------ | ------- | -------------------- | --------------------------------------- |
| NOT          | `-`     | `Prod -backup`       | Rejette les fichiers contenant "backup" |
| include      | `+`     | `+Prod`              | Inclusion explicite (= plain)           |
| OR           | `OR`    | `Prod OR Dev`        | Accepte l'un ou l'autre terme           |
| exact phrase | `"..."` | `"V2026.7"`          | Chaîne littérale entre guillemets       |
| implicit AND | espace  | `Production Program` | Les deux termes doivent correspondre    |

### Précedence (du plus haut au plus bas)

1. Phrases entre guillemets → un terme littéral
2. Préfixe `-` ou `+` → lie au terme immédiatement suivant
3. Espace (AND) → tous les termes d'un groupe doivent correspondre
4. OR → sépare les groupes d'alternatives

### Exemples d'utilisation

```
# Fichiers contenant "Prod" mais pas "backup"
Prod -backup

# Fichiers contenant "Prod" ou "Dev"
Prod OR Dev

# Fichiers contenant exactement "V2026.7"
"V2026.7"

# Fichiers contenant "Production" ET "Program"
Production Program
```

### Opérateurs d'attributs (`size`, `modified`, `created`)

Dans le champ **Filter** (et la barre de filtre de l'interface web), un token de
forme `key:valeur` avec une clé connue et une valeur analysable est évalué sur
l'instantané `stat` du fichier. Les clés sont `size`, `size_bytes` (alias — mêmes
octets), `modified` et `created` ; clés et unités sont **insensibles à la casse**.
Il n'existe délibérément aucune clé `path` : un terme simple filtre déjà sur le
chemin affiché. Le champ **Extension** filtre les suffixes et ne dispose d'aucune
donnée d'attribut : un terme en forme d'opérateur d'attribut y est traité comme une
sous-chaîne littérale. Les phrases quotées (`"size:>10mb"`) sont toujours
littérales, jamais des opérateurs.

| Expression               | Signification                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------ |
| `size:>10mb`             | Taille strictement supérieure à 10 MB (unités binaires, 1 KB = 1024 B)               |
| `size:<500kb`            | Taille strictement inférieure à 500 KB                                               |
| `size:1048576`           | Taille égale à l'opérande (valeur seule = égalité)                                   |
| `size:1kb..1mb`          | Plage de tailles — inclusive aux deux bornes                                         |
| `modified:>2026-11-01`   | Modifié à partir de minuit local ce jour-là (les fichiers du 1er novembre correspondent) |
| `modified:<2026-11-01`   | Modifié strictement avant minuit local ce jour-là (toute la journée est exclue)      |
| `modified:2026-11-01`    | Modifié durant cette journée locale (date seule)                                     |
| `modified:today`         | Modifié durant la journée locale de l'évaluation                                     |
| `modified:<7d`           | Modifié **dans les 7 derniers jours** (fichiers récents)                             |
| `modified:>7d`           | Modifié **il y a plus de 7 jours** (fichiers anciens)                                |
| `modified:1d..7d`        | Âge du fichier entre 1 et 7 jours — inclus                                           |
| `created:…`              | Même grammaire que `modified`, appliquée à la date de création (sur Linux : changement d'inode) |
| `-size:>10mb`            | Négation — inverse le résultat de l'opérateur                                        |

> **⚠️ Lecture des durées (à la GNU-find)** — une durée borne l'**âge** du fichier,
> pas son horodatage :
>
> - `modified:<7d` = âge **inférieur** à 7 jours = modifié **dans les 7 derniers jours** (fichiers récents)
> - `modified:>7d` = âge **supérieur** à 7 jours = modifié **il y a plus de 7 jours** (fichiers anciens)

**Opérandes** — les tailles utilisent les unités binaires `b` `kb` `mb` `gb` `tb`
(un nombre seul est en octets ; décimales arrondies à l'octet inférieur), les
durées utilisent les unités `s` `m` `h` `d` `w` (décimales tronquées, ex.
`<0.5d` = 12 heures), les dates sont `YYYY-MM-DD` en heure locale (une date désigne
son minuit local ; `today` s'ancre au minuit local du moment de l'évaluation). Les
plages `a..b` (sans espaces) sont incluses à la granularité nommée ; chaque borne
se résout indépendamment selon son genre.

**Repli et composition** — les opérateurs malformés (`size:abc`, `modified:>10mb`,
une durée seule `modified:7d`, une plage cassée `1..2..3`) ne sont pas des erreurs :
ils retombent sur la recherche de sous-chaîne littérale. La composition suit la
grammaire Google-style ci-dessus (espace = AND, `OR`, `-terme`, `+terme`), et les
comparaisons de dates/durées lisent l'horloge **au moment de l'évaluation**, donc
`today` et `<7d` restent exacts dans une session longue. La barre de filtre de
l'interface web implémente la même grammaire.

> **Performance** — un filtre portant au moins un opérateur d'attribut fait
> effectuer à chaque scan un `stat` par fichier candidat (exécuté dans le pool de
> workers parallèle). Un scan est totalement sans `stat` uniquement quand le filtre
> n'a aucun opérateur d'attribut **et** que le bloc `columns:` n'a aucun mot-clé
> d'attribut — voir [Colonnes Dynamiques](./columns-guide.fr.md).

---

## Coloration des lignes (`row_colors`)

La coloration des lignes permet de mettre en évidence des fichiers selon leur nom.

### Syntaxe

```
row_colors = PATTERN1:#HEX1, PATTERN2:#HEX2, ...
```

- `PATTERN` : Sous-chaîne à rechercher dans le nom de fichier (insensible à la casse)
- `#HEX` : Code couleur hexadécimal au format RRGGBB

### Règles de priorité

1. Les règles `defaults` sont appliquées en premier (base)
2. Les règles `configs` sont **ajoutées** après
3. Les règles par configuration ont la priorité (vérifiées en premier)

### Exemple

```yaml
defaults:
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#757575"

configs:
  configuration_1:
    row_colors:
      - pattern: SPECIFIC
        color: "#FF0000"
      - pattern: PROD
        color: "#00FF00"
```

Dans cet exemple :
- Les fichiers contenant "SPECIFIC" seront rouges (#FF0000) — priorité
- Les fichiers contenant "PROD" seront verts (#00FF00) — priorité
- Les fichiers contenant "DEV" seront gris (#757575) — base

---

## Lignes de commande CLI

```bash
# Mode interactif (lit .profiles)
python -m profiles

# Fichier de configuration explicite
python -m profiles --config PATH/.profiles

# Mode sans interface graphique
python -m profiles --headless

# Régénérer le fichier de configuration starter
python -m profiles --init
```

Le contenu starter écrit par `--init` est également disponible depuis l'interface web : ouvrez l'éditeur de configuration (bouton **Config** de la barre d'état) et cliquez sur **New** — voir [Éditeur de Configuration](#éditeur-de-configuration-interface-web).

---

## Éditeur de Configuration (Interface Web)

L'interface web intègre un **éditeur YAML de configuration** — plus besoin d'éditeur externe.

### Ouvrir l'éditeur

Cliquez sur le bouton **Config** de la barre d'état (en bas de la fenêtre). L'éditeur s'ouvre en plein écran avec le contenu du fichier de configuration actif.

> L'en-tête de l'éditeur comporte également un bouton **Open in OS** qui ouvre le fichier avec l'éditeur par défaut du système, si vous préférez votre propre outil.

### Barre d'outils

| Bouton      | Action                                                                                                                                      |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **New**     | Charge le modèle de configuration starter (le même contenu que `--init` écrit sur disque) dans l'éditeur. Les modifications non enregistrées sont confirmées au préalable. |
| **Test**    | Valide le contenu de l'éditeur en mémoire ; les problèmes éventuels sont listés sans toucher à la session ni au disque.                       |
| **Revert**  | Abandonne les modifications et recharge le fichier depuis le disque (confirmation préalable si l'éditeur contient des modifications).          |
| **Save**    | Écrit le contenu de l'éditeur dans le fichier de configuration actif sur disque. Masqué tant que la session utilise une config d'essai sans fichier associé. |
| **Save As** | Écrit le contenu dans un **nouveau** fichier (voir ci-dessous) — cela ancre également la session sur ce fichier.                               |
| **Apply**   | Teste le contenu de l'éditeur comme **configuration de session** — en mémoire uniquement, rien n'est écrit sur disque.                          |

Raccourci clavier : `Ctrl/Cmd+S` enregistre quand le fichier est ancré sur disque ; sinon il revient à **Apply**.

### Le modèle en deux étapes : Apply vs Save

- **Apply** est un *essai de session* : le texte est analysé et devient immédiatement la configuration active (répertoire, extensions, filtres et thème recalculés), mais rien n'est écrit sur disque. L'essai disparaît au redémarrage, et un **Reload** ramène au fichier présent sur disque.
- **Save** (et **Save As**) *ancre* le texte à un fichier : le fichier est écrit et la session bascule dessus. Ce que vous voyez dans l'éditeur est ce que le prochain lancement lira.

### Garde-fou de conformité (Save & Save As)

L'enregistrement déclenche d'abord une validation. Si des problèmes sont détectés, un dialogue les liste et bloque l'écriture jusqu'à ce que vous choisissiez :

- **Go back and fix** — retour à l'éditeur avec la liste des problèmes affichée au-dessus ;
- **Force save anyway** — écrit le fichier malgré les problèmes (il se chargera avec les valeurs par défaut jusqu'à leur correction).

### Save As

- Extensions autorisées : **`.profiles`** et **`.profiles.yaml`** (insensibles à la casse).
- Si un fichier du même nom existe déjà dans le répertoire choisi, une confirmation **Replace** est exigée avant de l'écraser.

---

## Exemples de Configuration Avancée

### Configuration Multi-Machine Complète

```yaml
defaults:
  title: Système de Lancement Production
  gui_auto_launch: true
  close_after_execute: false
  theme: dark
  search_dir: /chemin/vers/racine/production
  # recursive_search : déprécié — utilisez max_search_depth
  extensions: [All, .lnk, .pdf, .docx, .xlsx]
  filters: ["", PROD, DEV, DEV, TMP]
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#757575"
    - pattern: TMP
      color: "#BAC015"
    - pattern: TEST
      color: "#FF6F00"
  search_exclude_dirs: [.git, tmp, Obsolete, Debug, Backup]

# Colonnes dynamiques — un mappage `columns:` au NIVEAU SUPÉRIEUR, PAS une
# clé de `defaults:` (le bloc defaults ignore les clés inconnues : y placer
# `columns:`/`column_widths:` n'aurait donc AUCUN effet, sans erreur).
columns:
  File:
    name: File
    width: 500
    stretch: true
    match: ".*"
  Version:
    match: "[-_]V(\\d+(?:\\.\\d+)*)"
    width: 120
  Classification:
    match: type
    width: 150
  Date:
    match: date
    width: 100

configs:
  configuration_1:
    match:
      hostname: ["POSTE-TRAVAIL-PROD-01"]
    scan: /chemin/vers/production/station1
    extensions: [.lnk, .pdf]
    filters: ["", prod, specific]
    row_colors:
      - pattern: CRITICAL
        color: "#B71C1C"
      - pattern: PROD
        color: "#0D47A1"

  configuration_2:
    match:
      hostname: ["POSTE-TRAVAIL-ING-05"]
    scan: /chemin/vers/ingenierie/tests
    extensions: [.lnk, .txt, .log]
    filters: ["", dev, test, debug]
    row_colors:
      - pattern: DEV
        color: "#4A148C"
      - pattern: TEST
        color: "#E65100"
      - pattern: DEBUG
        color: "#006064"

  configuration_3:
    match:
      hostname: ["*"]
    scan: /chemin/vers/production
    extensions: [.lnk]
    filters: ["", PROD]
    row_colors: []
```

### Configuration Production Minimale

```yaml
defaults:
  theme: dark
  row_colors:
    - pattern: PROD
      color: "#1565C0"

configs:
  configuration_1:
    match:
      hostname: ["*"]
    scan: /chemin/vers/production
    extensions: [.lnk]
```

### Environnement Développement avec Codage Couleur

```yaml
defaults:
  theme: light
  row_colors:
    - pattern: DEV
      color: "#757575"
    - pattern: TEST
      color: "#FF6F00"
    - pattern: TMP
      color: "#BAC015"

configs:
  configuration_1:
    match:
      hostname: ["*"]
    scan: /chemin/vers/projet/development
    extensions: [.lnk, .py, .sh]
    filters: ["", dev, test, tmp]
    row_colors:
      - pattern: FEATURE
        color: "#2E7D32"
      - pattern: BUG
        color: "#C62828"
      - pattern: REFACTOR
        color: "#6A1B9A"
```

---

## Approfondissement des Opérateurs de Recherche

### Expressions de Recherche Complexes

```yaml
# Trouver fichiers production, exclure sauvegardes, inclure version spécifique
  extensions: [.lnk]
  filters: ["Prod -backup +V2026.7"]

# Alternatives multiples avec phrases exactes
  filters: ['"Programme Production" OR "Suite Test" -obsolète']

# Combiner logique AND et OR
  filters: ['(Prod OR Dev) -tmp "V2026.*"']
```

### Exemples de Précedence des Opérateurs

| Expression | Signification | Correspondances |
|------------|---------------|-----------------|
| `Prod -backup` | Prod ET PAS backup | `prod_file.lnk` ✅, `prod_backup.lnk` ❌ |
| `Prod OR Dev` | Prod OU Dev | `prod_file.lnk` ✅, `dev_file.lnk` ✅, `test_file.lnk` ❌ |
| `"V2026.7"` | Phrase exacte | `file_V2026.7.lnk` ✅, `V2026.7_test.lnk` ✅ |
| `Prod Program` | Prod ET Program | `prod_program.lnk` ✅, `prod_file.lnk` ❌ |

---

## Meilleures Pratiques pour la Coloration des Lignes

### Palette de Couleurs Recommandée

| Catégorie | Code Hex | Cas d'usage | Exemple de Motif |
|-----------|----------|-------------|------------------|
| **Production** | `#1565C0` (Bleu) | Fichiers production | `PROD`, `PROD_` |
| **Développement** | `#757575` (Gris) | Fichiers développement | `DEV`, `DEV_` |
| **Test** | `#FF6F00` (Ambre) | Fichiers de test | `TEST`, `TEST_` |
| **Temporaire** | `#BAC015` (Olive) | Fichiers temporaires | `TMP`, `TEMP` |
| **Critique** | `#B71C1C` (Rouge) | Production critique | `CRITICAL`, `URGENT` |
| **Fonctionnalité** | `#2E7D32` (Vert) | Branches features | `FEATURE`, `FEAT` |
| **Correction Bug** | `#C62828` (Rouge) | Corrections de bugs | `BUG`, `FIX` |

### Exemple de Résolution de Priorité

```yaml
defaults:
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#757575"

configs:
  configuration_1:
    row_colors:
      - pattern: PROD
        color: "#0D47A1"
      - pattern: SPECIFIC
        color: "#FF0000"
```

**Ordre de résolution pour le fichier `PROD_test.lnk` :**
1. Vérifier d'abord les règles `configs` → `PROD:#0D47A1` (bleu plus foncé) ✅
2. Si aucune correspondance, vérifier les règles `defaults` → `PROD:#1565C0` (bleu standard)
3. Finalement : `SPECIFIC:#FF0000` (rouge) pour les fichiers contenant "SPECIFIC"

---

## Guide de Dépannage Détaillé

### Problème : Configuration non appliquée

**Symptômes** : L'interface affiche les valeurs par défaut au lieu des valeurs configurées.

**Diagnostic** :
1. Vérifier l'emplacement du fichier : `.profiles` doit être dans le CWD ou les répertoires parents
2. Vérifier le nom du fichier : Doit être exactement `.profiles` (fichier caché sur Unix)
3. Utiliser le chemin explicite : `python -m profiles --config /chemin/vers/.profiles`

**Solution** :
```bash
# Vérifier si le fichier existe
ls -la .profiles          # Linux/macOS
dir .profiles            # Windows

# Utiliser la configuration explicite
python -m profiles --config C:\chemin\vers\.profiles
```

### Problème : Couleurs non appliquées correctement

**Symptômes** : Les fichiers apparaissent avec les couleurs par défaut au lieu des couleurs configurées.

**Diagnostic** :
1. Vérifier le format hex : Doit être `#RRGGBB` (7 caractères incluant #)
2. Vérifier la correspondance des motifs : Le motif est une correspondance de sous-chaîne insensible à la casse
3. Vérifier la priorité : Les règles par configuration remplacent les règles globales

**Solution** :
```yaml
# ✅ Format CORRECT
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#757575"

# ❌ Formats INCORRECTS (seront ignorés)
  row_colors:
    - pattern: PROD
      color: "#1565C"
    - pattern: DEV
      color: "#75757  # Trop court"
  row_colors:
    - pattern: PROD
      color: "1565C0"
    - pattern: DEV
      color: "757575  # # manquant"
  row_colors:
```

### Problème : Extensions non correspondantes

**Symptômes** : Les fichiers avec les extensions attendues n'apparaissent pas dans les résultats.

**Diagnostic** :
1. Le champ Extension correspond au **suffixe complet** (pas de point initial requis)
2. La comparaison est insensible à la casse
3. L'option "All" affiche tous les types de fichiers

**Solution** :
```yaml
# Correspondre les fichiers .lnk ('.lnk' et '.LNK' — tous équivalents)
  extensions: [All, .lnk, .LNK]

# Correspondre plusieurs extensions
  extensions: [All, .lnk, .pdf, .docx, .xlsx]

# Pour correspondre TOUS les fichiers quelle que soit l'extension
  extensions: [All]
```

### Problème : Scan récursif trop lent

**Symptômes** : Le scan prend beaucoup de temps sur les arborescences de répertoires volumineux.

**Solution** :
```yaml
defaults:
# Exclure les répertoires courants volumineux
  search_exclude_dirs: [.git, node_modules, __pycache__, bin, obj, Debug, Release, tmp]

# Ou scanner uniquement le répertoire sélectionné pour le scan initial (Depth 1)
  max_search_depth: 1
```

---

## Conseils de Performance

### Optimiser la Vitesse de Scan

1. **Exclure les répertoires inutiles** :
   ```yaml
  search_exclude_dirs: [.git, node_modules, __pycache__, bin, obj]
```

2. **Limiter les extensions de fichiers** :
```yaml
  extensions: [.lnk, .pdf]  # Scanner uniquement ces types
```

3. **Utiliser un répertoire de recherche spécifique** :
```yaml
  search_dir: /chemin/vers/production/dossier_specifique  # Portée plus étroite
```

### Optimisation Mémoire

Pour les très grands répertoires (>10 000 fichiers) :
- Commencer avec une profondeur faible (Depth 1 — répertoire sélectionné uniquement)
- Utiliser des motifs de filtre pour réduire les résultats
- Envisager de diviser en plusieurs sections de configuration

---

## FAQ (Foire Aux Questions)

**Q : Puis-je avoir plusieurs fichiers `.profiles` ?**  
R : Oui, mais seul le premier trouvé (depuis le CWD vers le haut) est utilisé. Utilisez `--config` pour une sélection explicite.

**Q : Comment tester une configuration sans lancer ?**  
R : Utilisez le mode `--headless` : `python -m profiles --headless --config chemin/.profiles`

**Q : Puis-je utiliser des variables d'environnement ?**  
R : Pas actuellement pris en charge. Utilisez des chemins absolus ou configurez des sections par machine.

**Q : Que se passe-t-il si deux sections correspondent ?**  
R : La première section correspondante (par ordre dans le dictionnaire `configs`) est utilisée. Le piège universel (`match.hostname: ["*"]`) doit être en dernier.

**Q : Comment réinitialiser aux valeurs par défaut ?**  
R : Supprimez `.profiles` ou exécutez `python -m profiles --init` pour régénérer. Le même modèle starter peut aussi être chargé dans l'éditeur de l'interface web avec **New**.

---

## Journal des Modifications

### Version 1.0 (Actuelle)
- Prise en charge complète de la configuration au format YAML
- Sections `configs` par machine
- Coloration des lignes avec correspondance de motifs
- Opérateurs de recherche avancés (-, +, OR, guillemets)
- Flags CLI pour configuration explicite

### Fonctionnalités Planifiées
- Substitution de variables d'environnement
- Outil de validation de configuration
- Import/export de configuration
