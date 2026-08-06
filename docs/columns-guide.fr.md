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
| `width`      | Entier | `150` (ou `600` pour File) | Largeur de la colonne en pixels.                                                  |
| `expression` | Chaîne | **Obligatoire**            | Expression régulière contenant un groupe de capture pour extraire la valeur.      |
| `group`      | Entier | `1`                        | Index du groupe de capture regex (`0` = correspondance complète, `1+` = groupes). |
| `priority`   | Entier | `0`                        | Ordre d'évaluation (les valeurs les plus élevées sont traitées en premier).       |
| `default`    | Chaîne | `""`                       | Valeur de repli affichée si le motif ne correspond pas.                           |

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
    width: 120
    expression: "Device_([A-Z0-9]+)"
    group: 1
    priority: 10
    default: "Inconnu"
```

### 2. Extraction des Versions

Pour extraire la version après `_V` :

```yaml
columns:
  Version:
    width: 150
    expression: '_V([^\\/]+)'
    group: 1
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
    width: 400
    expression: ".*"
    group: 0
    priority: 100

  Device:
    width: 120
    expression: "Device_([A-Z0-9]+)"
    group: 1
    priority: 15
    default: "N/A"

  Version:
    width: 130
    expression: "_V([^-]+)"
    group: 1
    priority: 20
    default: "Dernière"

configs:
  configuration_1:
    pc_hostname: All
    directory: .
    extensions: [.mttl]
```

---

## Dépannage et Conseils

- **Format YAML uniquement** : La configuration s'effectue exclusivement en YAML (`.profiles`). Veillez à respecter l'indentation.
- **Regex sur le chemin complet** : Les expressions régulières s'appliquent au _chemin complet_ du fichier, ce qui permet d'extraire des informations sur les dossiers parents si nécessaire.
- **Rafraîchissement** : Après avoir modifié `.profiles`, cliquez sur le bouton **🔄 Refresh** ou utilisez `Ctrl+R` pour recharger la configuration en direct.
- **Colonne vide** : Vérifiez que vos parenthèses de capture `()` ciblent correctement le texte attendu, sinon la valeur `default` sera affichée.
