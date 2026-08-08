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
| `match`      | Chaîne | **Obligatoire**            | Mot-clé intégré (`version`, `date`, `git_commit`, `type`, `filename`, `extension`) ou expression regex brute. |
| `transform`  | Chaîne | `None`                     | Modèle de remplacement avec références arrière. Supporte `{group:N}` (ex: `v{group:1}`) ou la syntaxe standard `\g<N>` / `\N`. |
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
