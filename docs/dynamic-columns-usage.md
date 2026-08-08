# Guide d'Utilisation : Colonnes Dynamiques

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **[Installation](./installation-guide.fr.md)** |
> ⚙️ **[Configuration](./configuration-profile.fr.md)** |
> 🔧 **[Hooks](./hooks-guide.en.md)** |
> 📊 **Colonnes Dynamiques** |
> 🚀 **[Guide Avancé](./advanced/guide-avance.fr.md)**

---

## Qu'est-ce que les Colonnes Dynamiques ?

Les colonnes dynamiques permettent d'**extraire automatiquement des informations** depuis les noms de fichiers et de les afficher dans des colonnes personnalisées dans l'interface de ProFiles.

### Exemple Concret

Si vos fichiers sont nommés ainsi :
```
Device_ABC123_V01-Rel6.2.1.mttl
Device_XYZ789_V02-Rel6.3.0.mttl
Device_TEST_V03-Rel6.4.1.mttl
```

Vous pouvez configurer ProFiles pour afficher :

| File | Device | Version |
|------|--------|---------|
| Device_ABC123_V01-Rel6.2.1.mttl | ABC123 | 01-Rel6.2.1 |
| Device_XYZ789_V02-Rel6.3.0.mttl | XYZ789 | 02-Rel6.3.0 |
| Device_TEST_V03-Rel6.4.1.mttl | TEST | 03-Rel6.4.1 |

**Sans écrire une seule ligne de code** - juste en modifiant le fichier `.profiles`.

---

## Configuration de Base

### Étape 1 : Ouvrir ou Créer le Fichier `.profiles`

Le fichier `.profiles` se trouve dans le répertoire de lancement. S'il n'existe pas :

```bash
python -m profiles --init
```

Cela crée un fichier de démarrage avec des exemples commentés.

### Étape 2 : Ajouter des Sections `[COLUMN_*]`

Pour chaque colonne personnalisée, ajoutez une section dans `.profiles` :

```ini
[COLUMN_Device]
width = 120
expression = Device_([A-Z0-9]+)
group = 1
priority = 5
default = Inconnu

[COLUMN_Version]
width = 150
expression = _V(.+)
group = 1
priority = 10
```

### Étape 3 : Redémarrer ou Rafraîchir

Cliquez sur le bouton **🔄 Refresh** dans l'interface GUI pour appliquer les changements.

---

## Paramètres Disponibles

Chaque section `[COLUMN_<Nom>]` accepte ces paramètres :

| Paramètre | Description | Exemple | Obligatoire |
|-----------|-------------|---------|-------------|
| `width` | Largeur de la colonne en pixels | `width = 150` | Non (défaut: 150) |
| `expression` | Pattern regex pour extraire la valeur | `expression = Device_([A-Z0-9]+)` | **Oui** |
| `group` | Groupe de capture à extraire (0=total, 1+=groupe) | `group = 1` | Non (défaut: 1) |
| `priority` | Priorité d'extraction (plus élevé = traité en premier) | `priority = 10` | Non (défaut: 0) |
| `default` | Valeur par défaut si le pattern ne matche pas | `default = Inconnu` | Non |

---

## Exemples Pratiques

### Exemple 1 : Extraire le Nom du Périphérique

**Fichiers :**
```
ST_PRO_Device_ABC123_V01.mttl
ST_PRO_Device_XYZ789_V02.mttl
```

**Configuration :**
```ini
[COLUMN_Device]
width = 120
expression = Device_([A-Z0-9]+)
group = 1
priority = 5
```

**Résultat :**
- File: `ST_PRO_Device_ABC123_V01.mttl`
- Device: `ABC123`

---

### Exemple 2 : Extraire un Code Projet

**Fichiers :**
```
PROJ_Mutest_IM611B_V02.mttl
DEV_Simulator_XY123_V03.mttl
```

**Configuration :**
```ini
[COLUMN_Project]
width = 100
expression = (PROJ|DEV|ST_PRO)
group = 1
priority = 8
```

**Résultat :**
- File: `PROJ_Mutest_IM611B_V02.mttl`
- Project: `PROJ`

---

### Exemple 3 : Extraire l'Environnement

**Fichiers :**
```
Device_ABC123_Prod_V01.mttl
Device_XYZ789_Dev_V02.mttl
Device_TEST_Test_V03.mttl
```

**Configuration :**
```ini
[COLUMN_Environment]
width = 100
expression = (Prod|Dev|Test)
group = 1
priority = 6
```

**Résultat :**
- File: `Device_ABC123_Prod_V01.mttl`
- Environment: `Prod`

---

### Exemple 4 : Extraire le Nom de Fichier et le Chemin

Pour séparer le chemin complet du nom de fichier :

```ini
[COLUMN_Path]
width = 200
expression = (.+[\\/])
group = 1
priority = 5
default = .

[COLUMN_FileName]
width = 150
expression = ([^/\\]+)$
group = 1
priority = 5
```

**Pour un fichier :** `C:/Git/Project/src/file.mttl`

**Résultat :**
- Path: `C:/Git/Project/src/`
- FileName: `file.mttl`

---

### Exemple 5 : Personnaliser la Colonne File

Par défaut, la colonne "File" affiche le chemin complet. Vous pouvez la personnaliser :

**Afficher seulement le nom de fichier (sans le chemin) :**
```ini
[COLUMN_File]
width = 300
expression = ([^/\\]+)$
group = 1
priority = 100
```

**Afficher le nom sans l'extension :**
```ini
[COLUMN_File]
width = 300
expression = ([^/\\]+)\.[^.]+$
group = 1
priority = 100
```

---

## Comprendre les Expressions Régulières

### Patterns Courants

| Pattern | Description | Exemple de Match |
|---------|-------------|------------------|
| `Device_([A-Z0-9]+)` | Code après "Device_" | `Device_ABC123` → `ABC123` |
| `_V(.+)` | Tout après "_V" | `_V01-Rel6.2.1` → `01-Rel6.2.1` |
| `(PROJ\|DEV\|PROD)` | Un des mots-clés | `PROJ` → `PROJ` |
| `(\d{4})` | Année à 4 chiffres | `2024` → `2024` |
| `([^/\\]+)$` | Nom de fichier (dernier composant) | `path/to/file.txt` → `file.txt` |
| `(.+[\\/])` | Chemin complet (sans le nom) | `path/to/file.txt` → `path/to/` |

### Conseils pour les Patterns

1. **Utilisez des groupes de capture** `()` pour extraire des parties spécifiques
2. **Group 0** = correspondance complète
3. **Group 1+** = premier, deuxième, etc. groupe capturé
4. **Testez vos patterns** avant de les déployer

### Tester un Pattern

```python
import re

pattern = r"Device_([A-Z0-9]+)"
filename = "Device_ABC123_V01.mttl"

match = re.search(pattern, filename, re.IGNORECASE)
if match:
    print(match.group(1))  # Affiche: ABC123
```

---

## Système de Priorité

Le paramètre `priority` contrôle l'ordre d'extraction :

- **Priorité plus élevée** = traité en premier
- **Colonne "File"** : priorité implicite 100
- **Colonne "Version"** : priorité implicite 10
- **Colonnes personnalisées** : recommandez 0-99

### Exemple de Priorités

```ini
[COLUMN_File]
priority = 100      # Toujours en premier

[COLUMN_Project]
priority = 15       # Projets avant périphériques

[COLUMN_Device]
priority = 10       # Périphériques avant environnement

[COLUMN_Environment]
priority = 5        # Environnement en dernier
```

---

## Cas d'Usage Avancés

### Extraire Plusieurs Informations d'un Seul Fichier

**Fichier :** `PROJ_Device_ABC123_Prod_V01_2024.mttl`

**Configuration :**
```ini
[COLUMN_Project]
width = 100
expression = (PROJ\|DEV\|ST_PRO)
group = 1
priority = 15

[COLUMN_Device]
width = 120
expression = Device_([A-Z0-9]+)
group = 1
priority = 10

[COLUMN_Environment]
width = 100
expression = (Prod\|Dev\|Test)
group = 1
priority = 8

[COLUMN_Version]
width = 100
expression = _V(\d+)
group = 1
priority = 6

[COLUMN_Year]
width = 80
expression = (\d{4})
group = 1
priority = 4
```

**Résultat :**
| Project | Device | Environment | Version | Year |
|---------|--------|-------------|---------|------|
| PROJ | ABC123 | Prod | 01 | 2024 |

---

### Utiliser des Valeurs par Défaut

Pour éviter les cellules vides :

```ini
[COLUMN_Device]
width = 120
expression = Device_([A-Z0-9]+)
group = 1
priority = 5
default = Non spécifié
```

Si le pattern ne matche pas, la cellule affiche "Non spécifié".

---

### Expressions Complexes avec Alternation

Pour matcher plusieurs formats :

```ini
[COLUMN_Environment]
width = 100
expression = (Prod\|Dev\|Test\|ST_PRO\|DEV)
group = 1
priority = 6
```

Matche : `Prod`, `Dev`, `Test`, `ST_PRO`, ou `DEV`.

---

## Dépannage

### Problème : La Colonne Est Vide

**Causes possibles :**
1. Le pattern regex ne matche pas vos fichiers
2. Le numéro de groupe est incorrect
3. L'expression est mal formée

**Solution :**
1. Testez le pattern avec Python (voir section "Tester un Pattern")
2. Vérifiez que `group` correspond au bon groupe de capture
3. Simplifiez le pattern et testez progressivement

---

### Problème : La Colonne "File" Disparaît

**Cause :** Vous avez défini `[COLUMN_File]` mais l'expression ne matche pas.

**Solution :**
```ini
[COLUMN_File]
width = 600
expression = .*
group = 0
priority = 100
```

Ou supprimez la section `[COLUMN_File]` pour revenir au comportement par défaut (chemin complet).

---

### Problème : Valeurs Incorrectes

**Cause :** Le pattern capture trop ou pas assez.

**Solution :**
- Ajustez le pattern pour être plus spécifique
- Changez le numéro de `group` si nécessaire
- Utilisez `group = 0` pour la correspondance complète

---

### Problème : Colonnes dans le Mauvais Ordre

**Cause :** L'ordre est déterminé par la configuration, pas par l'ordre des sections.

**Solution :**
La colonne "File" est toujours en premier. Les autres colonnes suivent dans l'ordre où elles apparaissent dans le fichier `.profiles`.

---

## Bonnes Pratiques

### 1. Nommez Clair et Précis

```ini
# ✅ BON
[COLUMN_DeviceCode]
[COLUMN_ProjectName]
[COLUMN_BuildVersion]

# ❌ ÉVITEZ
[COLUMN_Col1]
[COLUMN_X]
```

### 2. Documentez Vos Patterns

Ajoutez des commentaires dans votre `.profiles` :

```ini
# Extraire le code appareil après "Device_"
[COLUMN_Device]
width = 120
expression = Device_([A-Z0-9]+)
group = 1
```

### 3. Testez Avant Déploiement

Créez des fichiers de test :
```bash
touch "Device_ABC123_V01.mttl"
touch "Device_XYZ789_V02.mttl"
```

Lancez ProFiles et vérifiez l'extraction.

### 4. Versionnez Votre Configuration

Gardez votre `.profiles` sous contrôle de version :
```bash
git add .profiles
git commit -m "Add dynamic column configuration"
```

### 5. Utilisez des Largeurs Appropriées

```ini
[COLUMN_File]
width = 400          # Chemins longs

[COLUMN_Device]
width = 120          # Codes courts

[COLUMN_Project]
width = 80           # Abréviations
```

---

## Workflow de Modification

### Modifier les Colonnes

1. **Ouvrez** `.profiles` dans un éditeur de texte
2. **Modifiez** ou **ajoutez** des sections `[COLUMN_*]`
3. **Sauvegardez** le fichier
4. **Cliquez** sur **🔄 Refresh** dans ProFiles
5. **Vérifiez** que les nouvelles colonnes apparaissent

### Ajouter une Nouvelle Colonne

```ini
# Ajoutez cette section à la fin du fichier
[COLUMN_NewColumn]
width = 150
expression = YOUR_PATTERN_HERE
group = 1
priority = 5
```

### Supprimer une Colonne

**Supprimez** simplement la section `[COLUMN_Nom]` correspondante.

---

## Limitations Connues

- **La colonne "File"** est toujours affichée en premier (ne peut pas être déplacée)
- **Le tri est réinitialisé** lors du rafraîchissement de la configuration
- **Les items du Treeview** sont supprimés pendant la reconfiguration (comportement attendu)
- **Les expressions regex** sont appliquées au **chemin complet**, pas seulement au nom de fichier

---

## 📚 Bibliothèque de Colonnes Prêtes à l'Usage

Pour gagner du temps, consultez le **[Column Library Guide](./column-library.md)** qui contient une collection complète de configurations de colonnes prêtes à l'emploi :

- ✅ Colonnes de base (File, FileName, Extension, Path)
- ✅ Versions et révisions (Version, Build, Revision, SemVer)
- ✅ Environnements et types (PRO, DEV, TEST, TMP)
- ✅ Projets et équipements (Project, Device, Model)
- ✅ Localisation et sites (Site, Region, Country)
- ✅ Configurations techniques (Arch, Language, Platform)
- ✅ Dates et timestamps (Date, Timestamp, Week)
- ✅ Métadonnées spécifiques (Author, Commit, Branch, Tag)
- ✅ Combinaisons courantes pour différents cas d'usage

**Exemple rapide :**
```ini
# Copiez-collez depuis column-library.md
[COLUMN_Version]
width = 100
expression = _V([^\\/]+)
group = 1
priority = 20
```

---

## Exemple Complet

Voici un fichier `.profiles` complet avec plusieurs colonnes dynamiques :

```ini
[LAUNCHER]
title = ProFiles - Projet X
gui_auto_launch = False
search_dir = .
extensions = .mttl, .exe, .dll
filters = Prod, Dev, Test

[COLUMN_Path]
width = 200
expression = (.+[\\/])
group = 1
priority = 5
default = .

[COLUMN_FileName]
width = 250
expression = ([^/\\]+)$
group = 1
priority = 5

[COLUMN_Project]
width = 100
expression = (PROJ\|DEV\|ST_PRO)
group = 1
priority = 15

[COLUMN_Device]
width = 120
expression = Device_([A-Z0-9]+)
group = 1
priority = 10

[COLUMN_Environment]
width = 100
expression = (Prod\|Dev\|Test)
group = 1
priority = 8

[COLUMN_Version]
width = 120
expression = _V(\d+\.\d+\.\d+)
group = 1
priority = 6

[COLUMN_Year]
width = 80
expression = (\d{4})
group = 1
priority = 4

[CONFIGURATION_1]
match.hostname = ["*"]
scan = .
extensions = .mttl, .exe, .dll
filters = Prod, Dev, Test
row_colors =
```

---

## Ressources Supplémentaires

- **Fichier de configuration** : `.profiles` dans le répertoire de lancement
- **Commande de démarrage** : `python -m profiles --init`
- **Bouton Refresh** : **🔄 Refresh** dans l'interface GUI
- **Raccourci clavier** : `Ctrl+R` pour rafraîchir

---

## Questions Fréquentes

### Puis-je utiliser des expressions régulières complexes ?

Oui, tous les patterns Python `re` sont supportés.

### Les expressions sont-elles sensibles à la casse ?

Non, toutes les expressions sont **insensibles à la casse** par défaut.

### Puis-je avoir plusieurs colonnes avec le même pattern ?

Oui, mais cela n'a généralement pas de sens.

### Comment savoir quel `group` utiliser ?

- `group = 0` : correspondance complète
- `group = 1` : premier groupe `()`
- `group = 2` : deuxième groupe `()`, etc.

### Puis-je modifier les colonnes à la volée ?

Oui, modifiez `.profiles` et cliquez sur **🔄 Refresh**.

---

**Fin du guide d'utilisation.**
