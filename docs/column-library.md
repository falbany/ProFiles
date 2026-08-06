# Bibliothèque de Colonnes Dynamiques — Guide de Référence

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **[Installation](./installation-guide.fr.md)** |
> ⚙️ **[Configuration](./configuration-profile.fr.md)** |
> 🔧 **[Hooks](./hooks-guide.en.md)** |
> 📊 **Colonnes Dynamiques** |
> 🚀 **[Guide Avancé](./advanced/guide-avance.fr.md)**

---

## Introduction

Cette bibliothèque fournit des configurations de colonnes **prêtes à l'emploi** pour ProFiles. Copiez-collez les sections `[COLUMN_*]` qui vous conviennent dans votre fichier `.profiles`.

---

## 📁 Colonnes de Base

### Nom de Fichier Complet (avec extension)
```ini
[COLUMN_File]
width = 60
expression = .*
group = 0
priority = 100
```

### Nom de Fichier (sans extension)
```ini
[COLUMN_FileName]
width = 200
expression = ([^/\\]+)\.[^.]+$
group = 1
priority = 100
```

### Extension de Fichier
```ini
[COLUMN_Extension]
width = 80
expression = \.([^.]+)$
group = 1
priority = 50
```

### Chemin Complet (répertoire)
```ini
[COLUMN_Path]
width = 300
expression = (.+[\\/])
group = 1
priority = 10
default = .
```

### Nom de Fichier Seulement (sans chemin)
```ini
[COLUMN_FileNameOnly]
width = 250
expression = ([^/\\]+)$
group = 1
priority = 90
```

---

## 🔢 Versions et Révisions

### Version Simple (_Vxxx)
```ini
[COLUMN_Version]
width = 100
expression = _V([^\\/]+)
group = 1
priority = 20
```

### Version Numérique (_V01, _V02, etc.)
```ini
[COLUMN_VersionNum]
width = 60
expression = _V(\d+)
group = 1
priority = 20
```

### Version avec Release (_V01-Rel6.2.1)
```ini
[COLUMN_VersionFull]
width = 120
expression = _V([^-]+-Rel[^\\/]+)
group = 1
priority = 20
```

### Date de Version (_V2026.7 ou _V20260715)
```ini
[COLUMN_VersionDate]
width = 100
expression = _V(\d{4}\.?\d{2,4})
group = 1
priority = 20
```

### Numéro de Build
```ini
[COLUMN_Build]
width = 70
expression = build(\d+)
group = 1
priority = 9
```

### Numéro de Révision (_Rev01, _Rev02)
```ini
[COLUMN_Revision]
width = 70
expression = _Rev(\d+)
group = 1
priority = 18
```

### Version Semantique (1.2.3)
```ini
[COLUMN_SemVer]
width = 90
expression = (\d+\.\d+\.\d+)
group = 1
priority = 15
```

---

## 🏭 Environnements et Types

### Type d'Environnement (PRO, DEV, TEST, TMP)
```ini
[COLUMN_Type]
width = 70
expression = (PRO|ENG|DEV|TMP|DEBUG|TEST|PROD)
group = 1
priority = 15
```

### Type avec Priorité depuis la Fin (Dernier Match)
```ini
[COLUMN_TypeLast]
width = 70
expression = (PRO|ENG|DEV|TMP|DEBUG)(?!.*(PRO|ENG|DEV|TMP|DEBUG))
group = 1
priority = 15
```

### Statut de Version (Release, Beta, Alpha, RC)
```ini
[COLUMN_Status]
width = 80
expression = (Release|Beta|Alpha|RC)
group = 1
priority = 18
```

### Niveau de Qualité (QTY_PRO, QTY_ENG, etc.)
```ini
[COLUMN_QualityLevel]
width = 90
expression = (QTY_PRO|QTY_ENG|QTY_DEV|LOC_A|LOC_B|LOC_C)
group = 1
priority = 12
```

### Environnement (Prod, Dev, Test, Stage)
```ini
[COLUMN_Environment]
width = 90
expression = (Prod|Dev|Test|Stage|Preprod)
group = 1
priority = 16
```

### Mode de Debug (Debug, Release, Optimized)
```ini
[COLUMN_BuildMode]
width = 80
expression = (Debug|Release|Optimized|Profile)
group = 1
priority = 17
```

---

## 🏢 Projets et Équipements

### Code Projet
```ini
[COLUMN_Project]
width = 100
expression = (PROJ|DEV|PRJ|EMBED|APP)
group = 1
priority = 25
```

### Nom de Périphérique Complet
```ini
[COLUMN_Device]
width = 120
expression = Device_([A-Za-z0-9_]+)
group = 1
priority = 20
```

### Identifiant Périphérique (ABC123, XYZ789)
```ini
[COLUMN_DeviceID]
width = 100
expression = Device_([A-Z0-9]+)
group = 1
priority = 20
```

### Modèle ou Référence (MOD001A, MOD002B)
```ini
[COLUMN_Model]
width = 110
expression = (MOD\d+[A-Z]|DEV\d+|TOOL\d+|SYS\d+)
group = 1
priority = 18
```

### Famille de Produit
```ini
[COLUMN_Family]
width = 100
expression = (Family_[A-Z0-9]+|Fam_[A-Z]+)
group = 1
priority = 22
```

### Code Client
```ini
[COLUMN_Client]
width = 90
expression = (Client_[A-Z0-9]+|C_[A-Z]{2,4})
group = 1
priority = 24
```

---

## 📍 Localisation et Sites

### Site ou Localisation
```ini
[COLUMN_Site]
width = 100
expression = (SITE_A|SITE_B|SITE_C|SITE_NORTH|SITE_SOUTH)
group = 1
priority = 14
```

### Région ou Zone
```ini
[COLUMN_Region]
width = 90
expression = (Region_[A-Z]+|Zone_[A-Z0-9]+)
group = 1
priority = 13
```

### Pays ou Code Pays
```ini
[COLUMN_Country]
width = 70
expression = (FR|DE|EN|ES|IT|JP|CN|US)
group = 1
priority = 11
```

### Bureau ou Département
```ini
[COLUMN_Department]
width = 110
expression = (DEPT_[A-Z0-9]+|Bureau_[A-Z]+)
group = 1
priority = 12
```

---

## 🔧 Configurations Techniques

### Architecture (x32, x64, ARM)
```ini
[COLUMN_Arch]
width = 60
expression = (AMD64|x64|x86|ARM|ARM64)
group = 1
priority = 15
```

### Langue ou Locale
```ini
[COLUMN_Language]
width = 70
expression = (FR|EN|DE|ES|IT|JA|ZH|RU)
group = 1
priority = 11
```

### Plateforme (Windows, Linux, Mac)
```ini
[COLUMN_Platform]
width = 80
expression = (Win|Linux|Mac|Android|iOS)
group = 1
priority = 16
```

### Version de Runtime
```ini
[COLUMN_Runtime]
width = 90
expression = (rt_\d+\.\d+|runtime-\d+\.\d+)
group = 1
priority = 14
```

### Configuration Spécifique
```ini
[COLUMN_Config]
width = 100
expression = (cfg_[A-Z0-9]+|config-[a-z]+)
group = 1
priority = 13
```

---

## 📅 Dates et Timestamps

### Date de Création (YYYY.MM.DD)
```ini
[COLUMN_Date]
width = 100
expression = (\d{4}\.\d{2}\.\d{2})
group = 1
priority = 8
```

### Date ISO (YYYY-MM-DD)
```ini
[COLUMN_DateISO]
width = 100
expression = (\d{4}-\d{2}-\d{2})
group = 1
priority = 8
```

### Timestamp Unix
```ini
[COLUMN_Timestamp]
width = 110
expression = _t(\d{10,13})
group = 1
priority = 5
```

### Semaine ISO (YYYY-Www)
```ini
[COLUMN_Week]
width = 80
expression = (\d{4}-W\d{2})
group = 1
priority = 7
```

---

## 🎯 Métadonnées Spécifiques

### Auteur ou Créateur
```ini
[COLUMN_Author]
width = 120
expression = by_([A-Za-z0-9_]+)
group = 1
priority = 6
```

### Commit Hash (court - 7 caractères)
```ini
[COLUMN_Commit]
width = 90
expression = _g([a-f0-9]{7})
group = 2
priority = 7
```

### Nom de Branche
```ini
[COLUMN_Branch]
width = 100
expression = _branch_([A-Za-z0-9-_]+)
group = 2
priority = 7
```

### Tag ou Label
```ini
[COLUMN_Tag]
width = 100
expression = \[([A-Z_]+)\]
group = 1
priority = 20
```

### Numéro de Ticket/Issue
```ini
[COLUMN_Ticket]
width = 90
expression = (PROJ-\d+|ISSUE-\d+|#\d+)
group = 1
priority = 19
```

### Catégorie
```ini
[COLUMN_Category]
width = 100
expression = cat_([A-Za-z0-9_]+)
group = 1
priority = 10
```

---

## 🔄 Configurations Avancées

### Extraction avec Séparateurs Multiples
```ini
[COLUMN_Separator]
width = 100
expression = [._-]([A-Z0-9]+)[._-]
group = 1
priority = 12
```

### Multiple Tags (Premier Match)
```ini
[COLUMN_MultiTag]
width = 100
expression = ([A-Z]{2,5})_(\d+)
group = 1
priority = 15
```

### Extraction Conditionnelle avec Default
```ini
[COLUMN_Optional]
width = 100
expression = _opt_([^_]+)_
group = 1
priority = 5
default = Standard
```

### Version avec Suffixe (_V01-beta, _V01-alpha)
```ini
[COLUMN_VersionWithSuffix]
width = 120
expression = _V(\d+)-?(beta|alpha|rc)?
group = 1
priority = 20
```

### Code Mixte (Lettres + Chiffres)
```ini
[COLUMN_Alphanumeric]
width = 100
expression = ([A-Z]{2,4}\d{3,6})
group = 1
priority = 16
```

### Extraction depuis la Fin (Priorité Dernière Occurrence)
```ini
[COLUMN_LastOccurrence]
width = 100
expression = .*?(TAG_[A-Z]+)
group = 1
priority = 10
```

---

## 📊 Combinaisons Courantes

### Configuration Complète — Fichiers de Production
```ini
[LAUNCHER]
title = Project Launcher
theme = light
recursive_search = Vrai
extensions = mttl OR mttx -backup, mttl, mttx
filters = , QTY_PRO, QTY_ENG

[COLUMN_File]
width = 60
expression = .*
group = 0
priority = 100

[COLUMN_FileName]
width = 200
expression = ([^/\\]+)\.[^.]+$
group = 1
priority = 90

[COLUMN_Type]
width = 70
expression = (PRO|ENG|DEV|TMP|DEBUG)(?!.*(PRO|ENG|DEV|TMP|DEBUG))
group = 1
priority = 15

[COLUMN_QualityLevel]
width = 90
expression = (_PRO|_ENG|_DEV)
group = 1
priority = 12

[COLUMN_VersionFull]
width = 120
expression = _V([^-]+-Rel[^\\/]+)
group = 1
priority = 20

[COLUMN_BuildMode]
width = 80
expression = (Debug|Release|Optimized)
group = 1
priority = 17
```

### Configuration — Fichiers de Développement
```ini
[COLUMN_File]
width = 60
expression = .*
group = 0
priority = 100

[COLUMN_Project]
width = 100
expression = (PROJ|DEV|PRJ)
group = 1
priority = 25

[COLUMN_DeviceID]
width = 100
expression = Device_([A-Z0-9]+)
group = 1
priority = 20

[COLUMN_VersionNum]
width = 60
expression = _V(\d+)
group = 1
priority = 20

[COLUMN_Environment]
width = 90
expression = (Prod|Dev|Test|Stage)
group = 1
priority = 16

[COLUMN_Build]
width = 70
expression = build(\d+)
group = 1
priority = 9

[COLUMN_Arch]
width = 60
expression = (AMD64|x86|ARM)
group = 1
priority = 15

[COLUMN_Commit]
width = 90
expression = _g([a-f0-9]{7})
group = 2
priority = 7
```

### Configuration — Fichiers Multi-Sites
```ini
[COLUMN_File]
width = 60
expression = .*
group = 0
priority = 100

[COLUMN_Site]
width = 100
expression = (SITE_A|SITE_B|SITE_C)
group = 1
priority = 14

[COLUMN_Type]
width = 70
expression = (PRO|ENG|DEV|TMP)
group = 1
priority = 15

[COLUMN_Version]
width = 100
expression = _V([^\\/]+)
group = 1
priority = 20

[COLUMN_QualityLevel]
width = 90
expression = (QTY_PRO|QTY_ENG|QTY_DEV)
group = 1
priority = 12
```

### Configuration Minimaliste
```ini
[COLUMN_File]
width = 60
expression = .*
group = 0
priority = 100

[COLUMN_Version]
width = 100
expression = _V([^\\/]+)
group = 1
priority = 20

[COLUMN_Type]
width = 70
expression = (PRO|ENG|DEV|TMP)
group = 1
priority = 15
```

### Configuration — Fichiers avec Métadonnées Git
```ini
[COLUMN_File]
width = 60
expression = .*
group = 0
priority = 100

[COLUMN_Project]
width = 100
expression = (PROJ|DEV|PRJ)
group = 1
priority = 25

[COLUMN_Version]
width = 100
expression = _V([^\\/]+)
group = 1
priority = 20

[COLUMN_Commit]
width = 90
expression = _g([a-f0-9]{7})
group = 2
priority = 7

[COLUMN_Branch]
width = 100
expression = _branch_([A-Za-z0-9-_]+)
group = 2
priority = 7

[COLUMN_Build]
width = 70
expression = build(\d+)
group = 1
priority = 9
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

- [Guide d'Utilisation : Colonnes Dynamiques](./dynamic-columns-usage.md)
- [Guide Technique : Architecture des Colonnes](./dynamic-columns-guide.md)
- [Guide Avancé : Expressions Régulières](./advanced/advanced-guide.en.md)

---

## 📄 Licence

Cette configuration est fournie avec ProFiles. Libre d'utilisation et de modification selon les termes de la licence du projet.
