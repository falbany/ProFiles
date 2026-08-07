# Bibliothèque de Colonnes Dynamiques — Guide de Référence

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **[Installation](./installation-guide.fr.md)** |
> ⚙️ **[Configuration](./configuration-profile.fr.md)** |
> 🔧 **[Hooks](./hooks-guide.en.md)** |
> 📊 **Colonnes Dynamiques** |
> 🚀 **[Guide Avancé](./advanced/guide-avance.fr.md)**

---

## Introduction

Cette bibliothèque fournit des configurations de colonnes **prêtes à l'emploi** pour ProFiles. Copiez-collez les blocs qui vous conviennent sous la section `columns:` de votre fichier `.profiles`.

---

## 🧠 Macros de Motifs Intégrés

Au lieu d'écrire une regex personnalisée, utilisez un mot-clé intégré comme valeur de `match`. Les mots-clés sont comparés sans tenir compte de la casse.

| Mot-clé       | Extrait                          |
| ------------- | --------------------------------- |
| `version`     | Numéro de version après `_V` ou `-V` |
| `date`        | Date ISO ou YYYYMMDD              |
| `git_commit`  | Hash court de commit git        |
| `type`        | Dernier tag de type d'environnement |
| `filename`    | Nom de fichier sans chemin      |
| `extension`   | Extension (sans le point)       |

Exemple :

```yaml
columns:
  Version:
    name: Version
    width: 100
    stretch: false
    match: version           # mot-clé intégré
    transform: "{group:1}"
    priority: 10
```

---

## 📁 Colonnes de Base

### Nom de Fichier Complet (avec extension)
```yaml
columns:
  File:
    name: File
    width: 60
    stretch: false
    match: '.*'
    transform: '{group:0}'
    priority: 100
```

### Nom de Fichier (sans extension)
```yaml
  FileName:
    name: FileName
    width: 200
    stretch: false
    match: '([^/\\]+)\.[^.]+$'
    transform: '{group:1}'
    priority: 100
```

### Extension de Fichier
```yaml
  Extension:
    name: Extension
    width: 80
    stretch: false
    match: '\.([^.]+)$'
    transform: '{group:1}'
    priority: 50
```

### Chemin Complet (répertoire)
```yaml
  Path:
    name: Path
    width: 300
    stretch: false
    match: '(.+[\\/])'
    transform: '{group:1}'
    priority: 10
    default: "."
```

### Nom de Fichier Seulement (sans chemin)
```yaml
  FileNameOnly:
    name: FileNameOnly
    width: 250
    stretch: false
    match: '([^/\\]+)$'
    transform: '{group:1}'
    priority: 90
```

---

## 🔢 Versions et Révisions

### Version Simple (_Vxxx)
```yaml
  Version:
    name: Version
    width: 100
    stretch: false
    match: '_V([^\\/]+)'
    transform: '{group:1}'
    priority: 20
```

### Version Numérique (_V01, _V02, etc.)
```yaml
  VersionNum:
    name: VersionNum
    width: 60
    stretch: false
    match: '_V(\d+)'
    transform: '{group:1}'
    priority: 20
```

### Version avec Release (_V01-Rel6.2.1)
```yaml
  VersionFull:
    name: VersionFull
    width: 120
    stretch: false
    match: '_V([^-]+-Rel[^\\/]+)'
    transform: '{group:1}'
    priority: 20
```

### Date de Version (_V2026.7 ou _V20260715)
```yaml
  VersionDate:
    name: VersionDate
    width: 100
    stretch: false
    match: '_V(\d{4}\.?\d{2,4})'
    transform: '{group:1}'
    priority: 20
```

### Numéro de Build
```yaml
  Build:
    name: Build
    width: 70
    stretch: false
    match: 'build(\d+)'
    transform: '{group:1}'
    priority: 9
```

### Numéro de Révision (_Rev01, _Rev02)
```yaml
  Revision:
    name: Revision
    width: 70
    stretch: false
    match: '_Rev(\d+)'
    transform: '{group:1}'
    priority: 18
```

### Version Semantique (1.2.3)
```yaml
  SemVer:
    name: SemVer
    width: 90
    stretch: false
    match: '(\d+\.\d+\.\d+)'
    transform: '{group:1}'
    priority: 15
```

---

## 🏭 Environnements et Types

### Type d'Environnement (PRO, DEV, TEST, TMP)
```yaml
  Type:
    name: Type
    width: 70
    stretch: false
    match: '(PRO|ENG|DEV|TMP|DEBUG|TEST|PROD)'
    transform: '{group:1}'
    priority: 15
```

### Type avec Priorité depuis la Fin (Dernier Match)
```yaml
  TypeLast:
    name: TypeLast
    width: 70
    stretch: false
    match: '(PRO|ENG|DEV|TMP|DEBUG)(?!.*(PRO|ENG|DEV|TMP|DEBUG))'
    transform: '{group:1}'
    priority: 15
```

### Statut de Version (Release, Beta, Alpha, RC)
```yaml
  Status:
    name: Status
    width: 80
    stretch: false
    match: '(Release|Beta|Alpha|RC)'
    transform: '{group:1}'
    priority: 18
```

### Niveau de Qualité (QTY_PRO, QTY_ENG, etc.)
```yaml
  QualityLevel:
    name: QualityLevel
    width: 90
    stretch: false
    match: '(QTY_PRO|QTY_ENG|QTY_DEV|LOC_A|LOC_B|LOC_C)'
    transform: '{group:1}'
    priority: 12
```

### Environnement (Prod, Dev, Test, Stage)
```yaml
  Environment:
    name: Environment
    width: 90
    stretch: false
    match: '(Prod|Dev|Test|Stage|Preprod)'
    transform: '{group:1}'
    priority: 16
```

### Mode de Debug (Debug, Release, Optimized)
```yaml
  BuildMode:
    name: BuildMode
    width: 80
    stretch: false
    match: '(Debug|Release|Optimized|Profile)'
    transform: '{group:1}'
    priority: 17
```

---

## 🏢 Projets et Équipements

### Code Projet
```yaml
  Project:
    name: Project
    width: 100
    stretch: false
    match: '(PROJ|DEV|PRJ|EMBED|APP)'
    transform: '{group:1}'
    priority: 25
```

### Nom de Périphérique Complet
```yaml
  Device:
    name: Device
    width: 120
    stretch: false
    match: 'Device_([A-Za-z0-9_]+)'
    transform: '{group:1}'
    priority: 20
```

### Identifiant Périphérique (ABC123, XYZ789)
```yaml
  DeviceID:
    name: DeviceID
    width: 100
    stretch: false
    match: 'Device_([A-Z0-9]+)'
    transform: '{group:1}'
    priority: 20
```

### Modèle ou Référence (MOD001A, MOD002B)
```yaml
  Model:
    name: Model
    width: 110
    stretch: false
    match: '(MOD\d+[A-Z]|DEV\d+|TOOL\d+|SYS\d+)'
    transform: '{group:1}'
    priority: 18
```

### Famille de Produit
```yaml
  Family:
    name: Family
    width: 100
    stretch: false
    match: '(Family_[A-Z0-9]+|Fam_[A-Z]+)'
    transform: '{group:1}'
    priority: 22
```

### Code Client
```yaml
  Client:
    name: Client
    width: 90
    stretch: false
    match: '(Client_[A-Z0-9]+|C_[A-Z]{2,4})'
    transform: '{group:1}'
    priority: 24
```

---

## 📍 Localisation et Sites

### Site ou Localisation
```yaml
  Site:
    name: Site
    width: 100
    stretch: false
    match: '(SITE_A|SITE_B|SITE_C|SITE_NORTH|SITE_SOUTH)'
    transform: '{group:1}'
    priority: 14
```

### Région ou Zone
```yaml
  Region:
    name: Region
    width: 90
    stretch: false
    match: '(Region_[A-Z]+|Zone_[A-Z0-9]+)'
    transform: '{group:1}'
    priority: 13
```

### Pays ou Code Pays
```yaml
  Country:
    name: Country
    width: 70
    stretch: false
    match: '(FR|DE|EN|ES|IT|JP|CN|US)'
    transform: '{group:1}'
    priority: 11
```

### Bureau ou Département
```yaml
  Department:
    name: Department
    width: 110
    stretch: false
    match: '(DEPT_[A-Z0-9]+|Bureau_[A-Z]+)'
    transform: '{group:1}'
    priority: 12
```

---

## 🔧 Configurations Techniques

### Architecture (x32, x64, ARM)
```yaml
  Arch:
    name: Arch
    width: 60
    stretch: false
    match: '(AMD64|x64|x86|ARM|ARM64)'
    transform: '{group:1}'
    priority: 15
```

### Langue ou Locale
```yaml
  Language:
    name: Language
    width: 70
    stretch: false
    match: '(FR|EN|DE|ES|IT|JA|ZH|RU)'
    transform: '{group:1}'
    priority: 11
```

### Plateforme (Windows, Linux, Mac)
```yaml
  Platform:
    name: Platform
    width: 80
    stretch: false
    match: '(Win|Linux|Mac|Android|iOS)'
    transform: '{group:1}'
    priority: 16
```

### Version de Runtime
```yaml
  Runtime:
    name: Runtime
    width: 90
    stretch: false
    match: '(rt_\d+\.\d+|runtime-\d+\.\d+)'
    transform: '{group:1}'
    priority: 14
```

### Configuration Spécifique
```yaml
  Config:
    name: Config
    width: 100
    stretch: false
    match: '(cfg_[A-Z0-9]+|config-[a-z]+)'
    transform: '{group:1}'
    priority: 13
```

---

## 📅 Dates et Timestamps

### Date de Création (YYYY.MM.DD)
```yaml
  Date:
    name: Date
    width: 100
    stretch: false
    match: '(\d{4}\.\d{2}\.\d{2})'
    transform: '{group:1}'
    priority: 8
```

### Date ISO (YYYY-MM-DD)
```yaml
  DateISO:
    name: DateISO
    width: 100
    stretch: false
    match: '(\d{4}-\d{2}-\d{2})'
    transform: '{group:1}'
    priority: 8
```

### Timestamp Unix
```yaml
  Timestamp:
    name: Timestamp
    width: 110
    stretch: false
    match: '_t(\d{10,13})'
    transform: '{group:1}'
    priority: 5
```

### Semaine ISO (YYYY-Www)
```yaml
  Week:
    name: Week
    width: 80
    stretch: false
    match: '(\d{4}-W\d{2})'
    transform: '{group:1}'
    priority: 7
```

---

## 🎯 Métadonnées Spécifiques

### Auteur ou Créateur
```yaml
  Author:
    name: Author
    width: 120
    stretch: false
    match: 'by_([A-Za-z0-9_]+)'
    transform: '{group:1}'
    priority: 6
```

### Commit Hash (court - 7 caractères)
```yaml
  Commit:
    name: Commit
    width: 90
    stretch: false
    match: '_g([a-f0-9]{7})'
    transform: '{group:2}'
    priority: 7
```

### Nom de Branche
```yaml
  Branch:
    name: Branch
    width: 100
    stretch: false
    match: '_branch_([A-Za-z0-9-_]+)'
    transform: '{group:2}'
    priority: 7
```

### Tag ou Label
```yaml
  Tag:
    name: Tag
    width: 100
    stretch: false
    match: '\[([A-Z_]+)\]'
    transform: '{group:1}'
    priority: 20
```

### Numéro de Ticket/Issue
```yaml
  Ticket:
    name: Ticket
    width: 90
    stretch: false
    match: '(PROJ-\d+|ISSUE-\d+|#\d+)'
    transform: '{group:1}'
    priority: 19
```

### Catégorie
```yaml
  Category:
    name: Category
    width: 100
    stretch: false
    match: 'cat_([A-Za-z0-9_]+)'
    transform: '{group:1}'
    priority: 10
```

---

## 🔄 Configurations Avancées

### Extraction avec Séparateurs Multiples
```yaml
  Separator:
    name: Separator
    width: 100
    stretch: false
    match: '[._-]([A-Z0-9]+)[._-]'
    transform: '{group:1}'
    priority: 12
```

### Multiple Tags (Premier Match)
```yaml
  MultiTag:
    name: MultiTag
    width: 100
    stretch: false
    match: '([A-Z]{2,5})_(\d+)'
    transform: '{group:1}'
    priority: 15
```

### Extraction Conditionnelle avec Default
```yaml
  Optional:
    name: Optional
    width: 100
    stretch: false
    match: '_opt_([^_]+)_'
    transform: '{group:1}'
    priority: 5
    default: "Standard"
```

### Version avec Suffixe (_V01-beta, _V01-alpha)
```yaml
  VersionWithSuffix:
    name: VersionWithSuffix
    width: 120
    stretch: false
    match: '_V(\d+)-?(beta|alpha|rc)?'
    transform: '{group:1}'
    priority: 20
```

### Code Mixte (Lettres + Chiffres)
```yaml
  Alphanumeric:
    name: Alphanumeric
    width: 100
    stretch: false
    match: '([A-Z]{2,4}\d{3,6})'
    transform: '{group:1}'
    priority: 16
```

### Extraction depuis la Fin (Priorité Dernière Occurrence)
```yaml
  LastOccurrence:
    name: LastOccurrence
    width: 100
    stretch: false
    match: '.*?(TAG_[A-Z]+)'
    transform: '{group:1}'
    priority: 10
```

---

## 📊 Combinaisons Courantes

### Configuration Complète — Fichiers de Production
```yaml
defaults:
  title: Project Launcher
  theme: light
  recursive_search: true
  extensions: [mttl OR mttx -backup, mttl, mttx]
  filters: ["", QTY_PRO, QTY_ENG]

columns:
  File:
    name: File
    width: 60
    stretch: false
    match: '.*'
    transform: '{group:0}'
    priority: 100

  FileName:
    name: FileName
    width: 200
    stretch: false
    match: '([^/\\]+)\.[^.]+$'
    transform: '{group:1}'
    priority: 90

  Type:
    name: Type
    width: 70
    stretch: false
    match: '(PRO|ENG|DEV|TMP|DEBUG)(?!.*(PRO|ENG|DEV|TMP|DEBUG))'
    transform: '{group:1}'
    priority: 15

  QualityLevel:
    name: QualityLevel
    width: 90
    stretch: false
    match: '(_PRO|_ENG|_DEV)'
    transform: '{group:1}'
    priority: 12

  VersionFull:
    name: VersionFull
    width: 120
    stretch: false
    match: '_V([^-]+-Rel[^\\/]+)'
    transform: '{group:1}'
    priority: 20

  BuildMode:
    name: BuildMode
    width: 80
    stretch: false
    match: '(Debug|Release|Optimized)'
    transform: '{group:1}'
    priority: 17
```

### Configuration — Fichiers de Développement
```yaml
columns:
  File:
    name: File
    width: 60
    stretch: false
    match: '.*'
    transform: '{group:0}'
    priority: 100

  Project:
    name: Project
    width: 100
    stretch: false
    match: '(PROJ|DEV|PRJ)'
    transform: '{group:1}'
    priority: 25

  DeviceID:
    name: DeviceID
    width: 100
    stretch: false
    match: 'Device_([A-Z0-9]+)'
    transform: '{group:1}'
    priority: 20

  VersionNum:
    name: VersionNum
    width: 60
    stretch: false
    match: '_V(\d+)'
    transform: '{group:1}'
    priority: 20

  Environment:
    name: Environment
    width: 90
    stretch: false
    match: '(Prod|Dev|Test|Stage)'
    transform: '{group:1}'
    priority: 16

  Build:
    name: Build
    width: 70
    stretch: false
    match: 'build(\d+)'
    transform: '{group:1}'
    priority: 9

  Arch:
    name: Arch
    width: 60
    stretch: false
    match: '(AMD64|x86|ARM)'
    transform: '{group:1}'
    priority: 15

  Commit:
    name: Commit
    width: 90
    stretch: false
    match: '_g([a-f0-9]{7})'
    transform: '{group:2}'
    priority: 7
```

### Configuration — Fichiers Multi-Sites
```yaml
columns:
  File:
    name: File
    width: 60
    stretch: false
    match: '.*'
    transform: '{group:0}'
    priority: 100

  Site:
    name: Site
    width: 100
    stretch: false
    match: '(SITE_A|SITE_B|SITE_C)'
    transform: '{group:1}'
    priority: 14

  Type:
    name: Type
    width: 70
    stretch: false
    match: '(PRO|ENG|DEV|TMP)'
    transform: '{group:1}'
    priority: 15

  Version:
    name: Version
    width: 100
    stretch: false
    match: '_V([^\\/]+)'
    transform: '{group:1}'
    priority: 20

  QualityLevel:
    name: QualityLevel
    width: 90
    stretch: false
    match: '(QTY_PRO|QTY_ENG|QTY_DEV)'
    transform: '{group:1}'
    priority: 12
```

### Configuration Minimaliste
```yaml
columns:
  File:
    name: File
    width: 60
    stretch: false
    match: '.*'
    transform: '{group:0}'
    priority: 100

  Version:
    name: Version
    width: 100
    stretch: false
    match: '_V([^\\/]+)'
    transform: '{group:1}'
    priority: 20

  Type:
    name: Type
    width: 70
    stretch: false
    match: '(PRO|ENG|DEV|TMP)'
    transform: '{group:1}'
    priority: 15
```

### Configuration — Fichiers avec Métadonnées Git
```yaml
columns:
  File:
    name: File
    width: 60
    stretch: false
    match: '.*'
    transform: '{group:0}'
    priority: 100

  Project:
    name: Project
    width: 100
    stretch: false
    match: '(PROJ|DEV|PRJ)'
    transform: '{group:1}'
    priority: 25

  Version:
    name: Version
    width: 100
    stretch: false
    match: '_V([^\\/]+)'
    transform: '{group:1}'
    priority: 20

  Commit:
    name: Commit
    width: 90
    stretch: false
    match: '_g([a-f0-9]{7})'
    transform: '{group:2}'
    priority: 7

  Branch:
    name: Branch
    width: 100
    stretch: false
    match: '_branch_([A-Za-z0-9-_]+)'
    transform: '{group:2}'
    priority: 7

  Build:
    name: Build
    width: 70
    stretch: false
    match: 'build(\d+)'
    transform: '{group:1}'
    priority: 9
```

---

## 🛠️ Guide de Sélection

### Comment Choisir une Colonne

1. **Identifiez le motif** dans vos noms de fichiers
2. **Choisissez** la colonne correspondante dans cette bibliothèque
3. **Ajustez** `width` selon la longueur moyenne des valeurs
4. **Ajustez** `priority` si plusieurs colonnes peuvent matcher le même texte
5. **Testez** avec quelques fichiers avant déploiement

### Ordre de Priorité Recommandé

| Priorité | Type de Colonne | Exemple |
|----------|-----------------|---------|
| 100 | File (chemin/nom) | `[COLUMN_File]` |
| 90-80 | Identifiants uniques | `[COLUMN_FileName]` |
| 25-20 | Versions, Projets, Devices | `[COLUMN_Version]`, `[COLUMN_Project]` |
| 18-15 | Types, Environnements, Arch | `[COLUMN_Type]`, `[COLUMN_Arch]` |
| 14-10 | Sites, Qualité, Langue | `[COLUMN_Site]`, `[COLUMN_QualityLevel]` |
| 9-5 | Build, Date, Commit | `[COLUMN_Build]`, `[COLUMN_Commit]` |

### Astuces d'Optimisation

1. **Priorité inversée** : Utilisez `(?!.*PATTERN)` pour capturer la dernière occurrence
2. **Groupes de capture** : `group = 1` pour extraire seulement le contenu entre `()`
3. **Valeurs par défaut** : Ajoutez `default = ...` pour éviter les cellules vides
4. **Largeurs adaptées** : `width = 60-80` pour codes courts, `150-300` pour chemins

---

## 📝 Exemples de Fichiers Cibles

### Exemple 1 : Fichiers de Production
```
QTY_PRO_Device_ABC123_MOD001A_V01-Rel6.2.1_Prod_x64.mttl
QTY_ENG_Device_XYZ789_MOD001B_V02-Rel6.3.0_Dev_x64.mttl
```

**Colonnes recommandées :**
- `QualityLevel` → `QTY_PRO`, `QTY_ENG`
- `DeviceID` → `ABC123`, `XYZ789`
- `Model` → `MOD001A`, `MOD001B`
- `VersionFull` → `01-Rel6.2.1`, `02-Rel6.3.0`
- `Environment` → `Prod`, `Dev`
- `Arch` → `x64`

### Exemple 2 : Fichiers de Développement avec Git
```
PROJ_Device_TEST_V03_build1234_gabc1234_branch-feature.mttl
DEV_Simulator_XY123_V04_build1235_gdef5678_branch-develop.mttl
```

**Colonnes recommandées :**
- `Project` → `PROJ`, `DEV`
- `DeviceID` → `TEST`, `XY123`
- `VersionNum` → `03`, `04`
- `Build` → `1234`, `1235`
- `Commit` → `abc1234`, `def5678`
- `Branch` → `feature`, `develop`

### Exemple 3 : Fichiers Multi-Sites
```
SITE_A_Program_PRO_V01.mttl
SITE_B_Program_DEV_V02.mttl
SITE_C_Program_TMP_V03.mttl
```

**Colonnes recommandées :**
- `Site` → `SITE_A`, `SITE_B`, `SITE_C`
- `Type` → `PRO`, `DEV`, `TMP`
- `VersionNum` → `01`, `02`, `03`

---

## 🔗 Ressources Complémentaires

- [Guide d'Utilisation : Colonnes Dynamiques](./columns-guide.fr.md)
- [Guide Technique : Architecture des Colonnes](./columns-guide.en.md)
- [Guide Avancé : Expressions Régulières](./advanced/advanced-guide.en.md)

---

## 📄 Licence

Cette configuration est fournie avec ProFiles. Libre d'utilisation et de modification selon les termes de la licence du projet.
