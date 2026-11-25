# Guide des Colonnes Dynamiques

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **[Installation](./installation-guide.fr.md)** |
> ⚙️ **[Configuration](./configuration-profile.fr.md)** |
> 🔧 **[Hooks](./hooks-guide.fr.md)** |
> 📊 **Colonnes Dynamiques** |
> 🚀 **[Guide Avancé](./advanced/guide-avance.fr.md)**

---

## Vue d'ensemble

ProFiles prend en charge l'**extraction dynamique de colonnes** via la section `columns:` de votre fichier de configuration YAML (`.profiles`). Cela vous permet d'extraire automatiquement des métadonnées personnalisées à partir des noms de fichiers et de les afficher dans l'interface graphique.

---

## Référence de Configuration

Chaque colonne est définie sous la clé `columns:` avec les paramètres suivants :

| Paramètre    | Type   | Défaut                     | Description                                                                       |
| ------------ | ------ | -------------------------- | --------------------------------------------------------------------------------- |
| `name`       | Chaîne | *(revient à la clé)*       | Libellé convivial affiché dans l'en-tête de la colonne de l'interface.            |
| `width`      | Entier | `150` (ou `600` pour File) | Largeur de la colonne en pixels (utilisée quand `stretch` est `false`).           |
| `stretch`    | Booléen| `false`                    | La colonne s'étire-t-elle pour remplir l'espace disponible dans le Treeview.      |
| `match`      | Chaîne | **Obligatoire**            | Mot-clé intégré (`version`, `date`, `git_commit`, `type`, `filename`, `extension`, `path`, `size`, `size_bytes`, `modified`, `created`) ou expression regex brute. |
| `transform`  | Chaîne | `None`                     | Modèle de remplacement avec références arrière. Supporte `{group:N}` (ex: `v{group:1}`) ou la syntaxe standard `\g<N>` / `\N`. Pour `modified`/`created`, `transform` est un motif strftime (défaut `%Y-%m-%d %H:%M:%S`, heure locale) ; il est ignoré pour `path`. |
| `priority`   | Entier | `0`                        | Ordre d'évaluation (les valeurs les plus élevées sont traitées en premier).       |
| `default`    | Chaîne | `""`                       | Valeur de repli affichée si le motif ne correspond pas.                           |

### Syntaxe des Références Arrière dans transform

Le champ `transform` supporte deux syntaxes équivalentes :

| Syntaxe      | Exemple              | Description                          |
| ------------ | -------------------- | ------------------------------------ |
| `{group:N}`  | `v{group:1}`         | Syntaxe conviviale (recommandée).    |
| `\g<N>`      | `v\g<1>`             | Syntaxe regex Python standard.       |
| `\N`         | `v\1`                | Forme abrégée de `\g<N>`.            |

La syntaxe `{group:N}` est traduite en `\g<N>` en interne avant l'appel à
`re.Pattern.expand()`, donc les trois formes sont équivalentes.

---

## Macros de Motifs Intégrés

Au lieu d'écrire une regex personnalisée, vous pouvez utiliser un **mot-clé
intégré** comme valeur de `match`. Les mots-clés sont comparés sans tenir
compte de la casse. Si la valeur de `match` ne correspond à aucun mot-clé,
elle est traitée comme une expression regex brute.

| Mot-clé       | Expression Régulière                                   | Extrait                          |
| ------------- | ------------------------------------------------------- | --------------------------------- |
| `version`     | `[-_]V(\d+(?:\.\d+)*)(?=[^\\/]*\.[a-zA-Z0-9]+$)`       | Numéro de version après `_V` ou `-V` |
| `date`        | `(\d{4}[-_]\d{2}[-_]\d{2}\|\d{8})`                      | Date ISO ou YYYYMMDD              |
| `git_commit`  | `_g([a-f0-9]{7})`                                       | Hash court de commit git        |
| `type`        | `(PRO\|ENG\|DEV\|TMP\|DEBUG)(?!.*(?:PRO\|ENG\|DEV\|TMP\|DEBUG))` | Dernier tag de type d'environnement |
| `filename`    | `([^/\\]+)$`                                            | Nom de fichier sans chemin      |
| `extension`   | `\.([^./\\]+)$`                                         | Extension (sans le point)       |

### Mots-clés d'Attributs et de Chemin

Cinq mots-clés ne sont pas des regex : quatre se résolvent depuis un instantané
`stat` par fichier et un depuis le chemin affiché lui-même. Comme les macros
ci-dessus, ils sont comparés sans tenir compte de la casse dans le champ `match`.

| Mot-clé       | Extrait                                                                                             | Exemple               |
| ------------- | ---------------------------------------------------------------------------------------------------- | --------------------- |
| `size`        | Taille lisible, base binaire (1 KB = 1024 B) ; octets exacts sous 1 KB                              | `12.4 MB`, `512 B`    |
| `size_bytes`  | Nombre d'octets brut (entier)                                                                       | `13002394`            |
| `modified`    | Date de dernière modification ; `transform` est un motif strftime (défaut `%Y-%m-%d %H:%M:%S`, heure locale) | `2026-11-25 14:03:07` |
| `created`     | Date de création (sur Linux : repli sur la date de changement d'inode)                              | `2026-11-25 09:41:22` |
| `path`        | Répertoire contenant le fichier du chemin affiché (`transform` est ignoré)                          | `subdir` (`.` à la racine du scan) |

> **Note de performance** — les quatre mots-clés d'attributs coûtent un `stat` par
> fichier, exécuté dans le pool de workers parallèle, et uniquement quand une telle
> colonne est configurée (ou que le filtre porte des opérateurs d'attributs).
> `path` est dérivé par simple manipulation de chaîne et ne déclenche jamais de
> stat. Une configuration sans colonne d'attribut ni opérateur d'attribut dans le
> filtre n'effectue aucun stat.

```yaml
columns:
  Size:
    name: Size
    width: 110
    stretch: false
    match: size              # mot-clé d'attribut — taille lisible
    priority: 20

  Modified:
    name: Modified
    width: 150
    stretch: false
    match: modified          # transform = motif strftime (heure locale)
    transform: "%Y-%m-%d %H:%M"
    priority: 10
```

### Utilisation des Macros Intégrées

```yaml
columns:
  Version:
    name: Version
    width: 100
    stretch: false
    match: version           # mot-clé intégré
    transform: "{group:1}"
    priority: 10

  Date:
    name: Date
    width: 120
    stretch: false
    match: date              # mot-clé intégré
    transform: "{group:1}"
    priority: 15

  Commit:
    name: Commit
    width: 100
    stretch: false
    match: git_commit        # mot-clé intégré
    transform: "{group:1}"
    priority: 20
```

---

## Filtrage avec les Opérateurs d'Attributs

Le champ **Filter** (et la barre de filtre de l'interface web) accepte des
opérateurs d'attributs construits sur les mêmes clés que le tableau de mots-clés
ci-dessus : `size`, `size_bytes` (alias — mêmes octets), `modified` et `created`.
Clés et unités sont **insensibles à la casse** (`SIZE:>10MB`). Un token de forme
`key:valeur` avec une valeur analysable est évalué sur les attributs du fichier ;
tout le reste — phrases quotées et opérateurs malformés compris — retombe sur la
grammaire de sous-chaîne documentée dans la
[référence de configuration](./configuration-profile.fr.md#opérateurs-de-recherche).
Il n'existe délibérément aucune clé `path` : un terme simple filtre déjà sur le
chemin affiché.

### Formes de comparaison

| Expression               | Signification                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------ |
| `size:>10mb`             | Taille strictement supérieure à 10 MB (unités binaires)                              |
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
| `created:…`              | Même grammaire que `modified`, appliquée à la date de création                       |
| `-size:>10mb`            | Négation — inverse le résultat de l'opérateur                                        |
| `"size:>10mb"`           | Quoté — sous-chaîne littérale, jamais un opérateur                                   |

> **⚠️ Lecture des durées (à la GNU-find)** — une durée borne l'**âge** du fichier,
> pas son horodatage. Le sens de la comparaison est inversé par rapport à une
> lecture naïve de l'horodatage :
>
> - `modified:<7d` = âge **inférieur** à 7 jours = modifié **dans les 7 derniers jours** (fichiers récents)
> - `modified:>7d` = âge **supérieur** à 7 jours = modifié **il y a plus de 7 jours** (fichiers anciens)

### Opérandes

| Genre   | Syntaxe               | Notes                                                                                                                                             |
| ------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Taille  | `10`, `10mb`, `1.5kb` | Unités binaires `b` `kb` `mb` `gb` `tb` (1 KB = 1024 B) ; un nombre seul est en octets ; décimales acceptées, arrondies à l'octet inférieur        |
| Durée   | `7d`, `12h`, `0.5w`   | Unités `s` `m` `h` `d` `w` (secondes, minutes, heures, jours, semaines) ; décimales tronquées (`<0.5d` = 12 heures)                                |
| Date    | `2026-11-01`, `today` | `YYYY-MM-DD` en heure locale ; une date désigne son minuit local ; `today` s'ancre au minuit local du moment de l'évaluation                       |
| Plage   | `a..b` (sans espaces) | Inclusive à la granularité nommée : octets pour les tailles, journées entières pour les dates, âges pour les durées ; chaque borne se résout indépendamment selon son genre (une date et une durée peuvent être mélangées), mais mélanger taille et date/durée est invalide |

### Repli et composition

- **Repli** : les opérateurs malformés ne sont pas des erreurs — `size:abc`, un
  opérande de taille sur une clé temporelle (`modified:>10mb`), une durée seule
  (`modified:7d`) ou une plage cassée (`1..2..3`) sont recherchés comme sous-chaînes
  littérales, exactement comme un terme simple.
- **Composition** : celle de la grammaire Google-style — l'espace est un AND
  implicite, `OR` sépare les alternatives, `-terme` exclut et `+terme` force
  l'inclusion.
- **Horloge** : les comparaisons de dates et de durées lisent l'horloge **au moment
  de l'évaluation**, donc `today` et `<7d` restent exacts dans une session longue.
- **Coût** : un filtre portant au moins un opérateur d'attribut fait effectuer au
  scan un `stat` par fichier candidat (dans le pool de workers parallèle) ; un
  filtre sans opérateur d'attribut n'effectue aucun stat.
- **Parité** : la barre de filtre de l'interface web implémente la même grammaire
  (les deux analyseurs sont testés contre les mêmes fixtures partagées).

---

## Exemples Pratiques

### 1. Extraction d'un Code Appareil

Pour des fichiers nommés ainsi :

```text
Device_ABC123_V01.mttl
Device_XYZ789_V02.mttl
```

Ajoutez ceci dans votre fichier `.profiles` au format YAML :

```yaml
columns:
  Device:
    name: Device
    width: 120
    stretch: false
    match: "Device_([A-Z0-9]+)"
    transform: "{group:1}"
    priority: 10
    default: "Inconnu"
```

### 2. Extraction des Versions

Pour extraire la version après `_V` :

```yaml
columns:
  Version:
    name: Version
    width: 150
    stretch: false
    match: '_V([^\\/]+)'
    transform: "{group:1}"
    priority: 20
```

---

## Exemple Complet de Configuration YAML

```yaml
defaults:
  title: ProFiles Launcher
  search_dir: .
  extensions: [.mttl, .exe]

columns:
  File:
    name: File
    width: 400
    stretch: true
    match: ".*"
    transform: "{group:0}"
    priority: 100

  Device:
    name: Device
    width: 120
    stretch: false
    match: "Device_([A-Z0-9]+)"
    transform: "{group:1}"
    priority: 15
    default: "N/A"

  Version:
    name: Version
    width: 130
    stretch: false
    match: "_V([^-]+)"
    transform: "{group:1}"
    priority: 20
    default: "Dernière"

configs:
  configuration_1:
    match:
      hostname: ["*"]
    scan: .
    extensions: [.mttl]
```

---

## Dépannage et Conseils

- **Format YAML uniquement** : La configuration s'effectue exclusivement en YAML (`.profiles`). Veillez à respecter l'indentation.
- **Regex sur le chemin complet** : Les expressions régulières s'appliquent au _chemin complet_ du fichier, ce qui permet d'extraire des informations sur les dossiers parents si nécessaire.
- **Rafraîchissement** : Après avoir modifié `.profiles`, cliquez sur le bouton **🔄 Refresh** ou utilisez `Ctrl+R` pour recharger la configuration en direct.
- **Colonne vide** : Vérifiez que vos parenthèses de capture `()` ciblent correctement le texte attendu, sinon la valeur `default` sera affichée.
