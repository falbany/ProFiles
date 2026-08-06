# Configuration .profiles

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **[Installation](./installation-guide.fr.md)** |
> ⚙️ **Configuration** |
> 🔧 **[Hooks](./hooks-guide.en.md)** |
> 📊 **[Colonnes Dynamiques](./dynamic-columns-usage.md)** |
> 🚀 **[Guide Avancé](./advanced/guide-avance.fr.md)** |
> 🇬🇧 **[English Version](./configuration-profile.en.md)**

---

## Vue d'ensemble

Le fichier `.profiles` est un fichier de configuration INI qui personnalise le comportement de ProFiles. Ce fichier est recherché en commençant depuis le répertoire courant (CWD) et en descendant dans les sous-répertoires jusqu'à **5 niveaux de profondeur**. Le premier fichier trouvé est utilisé.

**Important** : La recherche est limitée à 5 niveaux de sous-répertoires pour maintenir de bonnes performances sur les arborescences de fichiers volumineuses.

Si aucun fichier `.profiles` n'est trouvé :
- En mode GUI : ProFiles propose de créer un fichier de configuration par défaut
- En mode headless : ProFiles utilise des valeurs par défaut identiques à celles présentées dans ce document

## Création du fichier de configuration

### Méthode 1 : Proposition automatique (mode GUI)

Au premier lancement en mode GUI, si aucun fichier `.profiles` n'est trouvé, ProFiles propose de créer un fichier de configuration par défaut dans le répertoire courant.

### Méthode 2 : Commande ligne de commande

```bash
python -m profiles --init
```

Cette commande crée un fichier `.profiles` avec des valeurs par défaut dans le répertoire courant.

### Méthode 3 : Création manuelle

Créez un fichier nommé `.profiles` dans votre répertoire de travail et copiez-y le contenu du modèle ci-dessous.

## Structure du fichier

Le fichier utilise le format INI standard avec des sections et des clés. Toutes les clés de section sont **insensibles à la casse**.

### Sections disponibles

- `[LAUNCHER]` — Configuration globale
- `[CONFIGURATION_N]` — Configurations par machine (N = 1, 2, 3, ...)

---

## Section `[LAUNCHER]` — Configuration globale

Cette section définit les paramètres par défaut applicables à toutes les machines.

### Paramètres

| Clé                   | Type               | Valeur par défaut    | Description                                                                 |
| --------------------- | ------------------ | -------------------- | --------------------------------------------------------------------------- |
| `title`               | string             | `""`                 | Titre personnalisé ajouté à la fenêtre principale                           |
| `gui_auto_launch`     | bool               | `Vrai`               | Afficher l'interface graphique lors de `python -m profiles`               |
| `close_after_execute` | bool               | `Faux`               | Fermer la fenêtre après un lancement réussi                                 |
| `theme`               | enum               | `"light"`            | Thème d'interface : `"light"` ou `"dark"` (Material Design 3)               |
| `language`            | enum               | `"en"`               | Langue de l'interface : `"en"` (anglais) ou `"fr"` (français) ; basculable via le bouton langue de la barre de statut (cycle en → fr → en) |
| `search_dir`          | absolute path      | `""`                 | Répertoire de recherche par défaut pour le champ Directory                  |
| `recursive_search`    | bool               | `Faux`               | État initial de la case à cocher Recursive                                  |
| `columns`             | csv string         | `"File, Version"`    | En-têtes des colonnes Treeview (la première est réservée au nom de fichier) |
| `column_widths`       | csv int            | `"600, 150"`         | Largeurs en pixels, DOIT correspondre au nombre de `columns`                |
| `extensions`          | csv string         | `"All, .lnk"`        | Présélections du combobox Extension (remplies par `[CONFIGURATION_N]`)      |
| `filters`             | csv string         | `", ST_PRO, ST_ENG"` | Présélections du combobox Filter ("" = tous les fichiers)                   |
| `row_colors`          | csv "PATTERN:#HEX" | `""`                 | Règles de coloration génériques appliquées à TOUS les configurations        |
| `search_exclude_dirs` | csv glob-pattern  | `".git"`             | Noms de répertoires (motifs glob insensibles à la casse) ignorés lors du scan récursif. Prend en charge les jokers `*`, `?`, `[seq]` (`*tmp`, `node_modules`, `Debug*`, etc.) |
| `search_exclude_files` | csv glob-pattern | `""`                 | Noms de fichiers (motifs glob insensibles à la casse) ignorés lors du scan. S'applique aux scans récursifs ET non récursifs. Même syntaxe de jokers que `search_exclude_dirs` (`*backup*`, `~$*`, `*.tmp`). Les motifs `[CONFIGURATION_N].search_exclude_files` sont AJOUTÉS. |

### Valeurs booléennes acceptées

- Français : `Vrai` / `Faux`
- Anglais : `true` / `false` / `yes` / `no` / `1` / `0` / `on` / `off`

### Exemple de configuration `[LAUNCHER]`

```ini
[LAUNCHER]
title = Mon Projet
gui_auto_launch = Vrai
close_after_execute = Faux
theme = dark
search_dir = /chemin/vers/repertoire/production
recursive_search = Vrai
columns = File, Version, Classification
column_widths = 600, 150, 100
extensions = All, .lnk, .pdf, .docx
filters = , ST_PRO, ST_ENG, DEV
row_colors = PROD:#1565C0, DEV:#757575, TMP:#BAC015
search_exclude_dirs = .git, tmp, Obsolete, Debug
search_exclude_files = *backup*, ~$*, *.tmp
```

### Exclusion par Glob (`search_exclude_dirs` / `search_exclude_files`)

Les deux clés acceptent des motifs glob insensibles à la casse avec les jokers `*`, `?`, `[seq]` (via `fnmatch` de Python).

| Clé | Portée | Défaut | Exemple |
| --- | --- | --- | --- |
| `search_exclude_dirs` | Noms de répertoires ignorés lors du scan **récursif** | `.git` | `node_modules`, `Debug*`, `*tmp` |
| `search_exclude_files` | Noms de fichiers Ignés lors du scan (**récursif et non récursif**) | `""` | `*backup*`, `~$*`, `*.tmp` |

**Ajout par configuration** : `search_exclude_files` dans une section `[CONFIGURATION_N]` est AJOUTÉ à la liste de base `[LAUNCHER]` — les deux jeux de motifs s'appliquent pour cette configuration. L'exclusion de répertoires (`search_exclude_dirs`) est globale uniquement.

---

## Sections `[CONFIGURATION_N]` — Configurations par machine

Ces sections définissent des paramètres spécifiques à chaque machine. Les sections sont numérotées séquentiellement (CONFIGURATION_1, CONFIGURATION_2, ...).

ProFiles sélectionne la section dont le `pc_hostname` correspond au nom d'hôte local (correspondance exacte, insensible à la casse).

Une section avec `pc_hostname = All` agit comme un piège universel — placez-la **DERNIÈRE** pour qu'elle ne masque pas les noms d'hôte spécifiques.

### Paramètres

| Clé           | Type               | Obligatoire | Description                                                            |
| ------------- | ------------------ | ----------- | ---------------------------------------------------------------------- |
| `pc_ip`       | string             | Non         | Label IP affiché (NON utilisé pour la correspondance)                  |
| `pc_hostname` | string             | Oui*        | Nom d'hôte local ciblé par cette section (*sauf si `All`)              |
| `pc_name`     | string             | Non         | Label convivial (journaux, statut)                                     |
| `directory`   | absolute path      | Non         | Répertoire de production scanné pour cette machine                     |
| `extensions`  | csv string         | Non         | Présélections Extension par station (remplace `[LAUNCHER].extensions`) |
| `filters`     | csv string         | Non         | Présélections Filter par station (remplace `[LAUNCHER].filters`)       |
| `row_colors`  | csv "PATTERN:#HEX" | Non         | Règles de coloration spécifiques à la configuration                    |
| `search_exclude_files` | csv glob-pattern | Non         | Motifs d'exclusion de fichiers par station. AJOUTÉS à `[LAUNCHER].search_exclude_files`. Même syntaxe de jokers. |

### Exemple de configuration par machine

```ini
[CONFIGURATION_1]
pc_hostname = POSTE-TRAVAIL-01
pc_name = Station Production
pc_ip = 192.168.1.100
directory = /chemin/vers/production/station1
extensions = .pdf, .docx, .lnk, .xlsx
filters = , tmp, dev, prod
row_colors = PROD:#1565C0, DEV:#757575
search_exclude_files = *brouillon*, *.bak

[CONFIGURATION_2]
pc_hostname = All
pc_name = Generic
directory = /chemin/vers/production
extensions = .lnk
filters = , ST_PRO
row_colors =
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

1. Les règles `[LAUNCHER]` sont appliquées en premier (base)
2. Les règles `[CONFIGURATION_N]` sont **ajoutées** après
3. Les règles par configuration ont la priorité (vérifiées en premier)

### Exemple

```ini
[LAUNCHER]
row_colors = PROD:#1565C0, DEV:#757575

[CONFIGURATION_1]
row_colors = SPECIFIC:#FF0000, PROD:#00FF00
```

Dans cet exemple :
- Les fichiers contenant "SPECIFIC" seront rouges (#FF0000) — priorité
- Les fichiers contenant "PROD" seront verts (#00FF00) — priorité
- Les fichiers contenant "DEV" seront gris (#757575) — base

---

## Lignes de commande CLI

```bash
# Interface graphique (lit .profiles)
python -m profiles

# Fichier de configuration explicite
python -m profiles --config PATH/.profiles

# Mode sans interface graphique
python -m profiles --headless

# Régénérer le fichier de configuration starter
python -m profiles --init
```

---

## Exemples de Configuration Avancée

### Configuration Multi-Machine Complète

```ini
[LAUNCHER]
title = Système de Lancement Production
gui_auto_launch = Vrai
close_after_execute = Faux
theme = dark
search_dir = /chemin/vers/racine/production
recursive_search = Vrai
columns = File, Version, Classification, Date
column_widths = 500, 120, 150, 100
extensions = All, .lnk, .pdf, .docx, .xlsx
filters = , ST_PRO, ST_ENG, DEV, TMP
row_colors = PROD:#1565C0, DEV:#757575, TMP:#BAC015, TEST:#FF6F00
search_exclude_dirs = .git, tmp, Obsolete, Debug, Backup

[CONFIGURATION_1]
pc_hostname = POSTE-TRAVAIL-PROD-01
pc_name = Station Production 1
pc_ip = 192.168.1.101
directory = /chemin/vers/production/station1
extensions = .lnk, .pdf
filters = , prod, specific
row_colors = CRITICAL:#B71C1C, PROD:#0D47A1

[CONFIGURATION_2]
pc_hostname = POSTE-TRAVAIL-ING-05
pc_name = Poste Ingénierie
pc_ip = 192.168.1.105
directory = /chemin/vers/ingenierie/tests
extensions = .lnk, .txt, .log
filters = , dev, test, debug
row_colors = DEV:#4A148C, TEST:#E65100, DEBUG:#006064

[CONFIGURATION_3]
pc_hostname = All
pc_name = Configuration par défaut
directory = /chemin/vers/production
extensions = .lnk
filters = , ST_PRO
row_colors =
```

### Configuration Production Minimale

```ini
[LAUNCHER]
theme = dark
row_colors = PROD:#1565C0

[CONFIGURATION_1]
pc_hostname = All
directory = /chemin/vers/production
extensions = .lnk
```

### Environnement Développement avec Codage Couleur

```ini
[LAUNCHER]
theme = light
row_colors = DEV:#757575, TEST:#FF6F00, TMP:#BAC015

[CONFIGURATION_1]
pc_hostname = All
directory = /chemin/vers/projet/development
extensions = .lnk, .py, .sh
filters = , dev, test, tmp
row_colors = FEATURE:#2E7D32, BUG:#C62828, REFACTOR:#6A1B9A
```

---

## Approfondissement des Opérateurs de Recherche

### Expressions de Recherche Complexes

```ini
# Trouver fichiers production, exclure sauvegardes, inclure version spécifique
extensions = .lnk
filters = Prod -backup +V2026.7

# Alternatives multiples avec phrases exactes
filters = "Programme Production" OR "Suite Test" -obsolète

# Combiner logique AND et OR
filters = (Prod OR Dev) -tmp "V2026.*"
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

```ini
[LAUNCHER]
row_colors = PROD:#1565C0, DEV:#757575

[CONFIGURATION_1]
row_colors = PROD:#0D47A1, SPECIFIC:#FF0000
```

**Ordre de résolution pour le fichier `PROD_test.lnk` :**
1. Vérifier d'abord les règles `[CONFIGURATION_1]` → `PROD:#0D47A1` (bleu plus foncé) ✅
2. Si aucune correspondance, vérifier les règles `[LAUNCHER]` → `PROD:#1565C0` (bleu standard)
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
```ini
# ✅ Format CORRECT
row_colors = PROD:#1565C0, DEV:#757575

# ❌ Formats INCORRECTS (seront ignorés)
row_colors = PROD:#1565C, DEV:#75757  # Trop court
row_colors = PROD:1565C0, DEV:757575  # # manquant
row_colors = PROD = #1565C0           # Mauvais séparateur
```

### Problème : Extensions non correspondantes

**Symptômes** : Les fichiers avec les extensions attendues n'apparaissent pas dans les résultats.

**Diagnostic** :
1. Le champ Extension correspond au **suffixe complet** (pas de point initial requis)
2. La comparaison est insensible à la casse
3. L'option "All" affiche tous les types de fichiers

**Solution** :
```ini
# Correspondre les fichiers .lnk (both .lnk et .LNK)
extensions = All, .lnk, .LNK  # Tous équivalents

# Correspondre plusieurs extensions
extensions = All, .lnk, .pdf, .docx, .xlsx

# Pour correspondre TOUS les fichiers quelle que soit l'extension
extensions = All
```

### Problème : Scan récursif trop lent

**Symptômes** : Le scan prend beaucoup de temps sur les arborescences de répertoires volumineux.

**Solution** :
```ini
[LAUNCHER]
# Exclure les répertoires courants volumineux
search_exclude_dirs = .git, node_modules, __pycache__, bin, obj, Debug, Release, tmp

# Ou désactiver le scan récursif pour le scan initial
recursive_search = Faux
```

---

## Conseils de Performance

### Optimiser la Vitesse de Scan

1. **Exclure les répertoires inutiles** :
   ```ini
   search_exclude_dirs = .git, node_modules, __pycache__, bin, obj
   ```

2. **Limiter les extensions de fichiers** :
   ```ini
   extensions = .lnk, .pdf  # Scanner uniquement ces types
   ```

3. **Utiliser un répertoire de recherche spécifique** :
   ```ini
   search_dir = /chemin/vers/production/dossier_specifique  # Portée plus étroite
   ```

### Optimisation Mémoire

Pour les très grands répertoires (>10 000 fichiers) :
- Désactiver le scan récursif initialement
- Utiliser des motifs de filtre pour réduire les résultats
- Envisager de diviser en plusieurs sections de configuration

---

## Guide de Migration

### Depuis l'Ancien Format de Configuration

Si vous avez un ancien format de configuration, migrez comme suit :

```ini
; ANCIEN FORMAT (obsolète)
[MAIN]
path = /chemin/vers/production
ext = .lnk, .pdf

; NOUVEAU FORMAT
[LAUNCHER]
search_dir = /chemin/vers/production
extensions = All, .lnk, .pdf

[CONFIGURATION_1]
pc_hostname = All
directory = /chemin/vers/production
extensions = .lnk, .pdf
```

---

## FAQ (Foire Aux Questions)

**Q : Puis-je avoir plusieurs fichiers `.profiles` ?**  
R : Oui, mais seul le premier trouvé (depuis le CWD vers le haut) est utilisé. Utilisez `--config` pour une sélection explicite.

**Q : Comment tester une configuration sans lancer ?**  
R : Utilisez le mode `--headless` : `python -m profiles --headless --config chemin/.profiles`

**Q : Puis-je utiliser des variables d'environnement ?**  
R : Pas actuellement pris en charge. Utilisez des chemins absolus ou configurez des sections par machine.

**Q : Que se passe-t-il si deux sections correspondent au nom d'hôte ?**  
R : La première section correspondante (par numéro) est utilisée. `All` doit être en dernier.

**Q : Comment réinitialiser aux valeurs par défaut ?**  
R : Supprimez `.profiles` ou exécutez `python -m profiles --init` pour régénérer.

---

## Journal des Modifications

### Version 1.0 (Actuelle)
- Prise en charge complète de la configuration au format INI
- Sections `[CONFIGURATION_N]` par machine
- Coloration des lignes avec correspondance de motifs
- Opérateurs de recherche avancés (-, +, OR, guillemets)
- Flags CLI pour configuration explicite

### Fonctionnalités Planifiées
- Substitution de variables d'environnement
- Outil de validation de configuration
- Éditeur de configuration GUI
- Import/export de configuration
