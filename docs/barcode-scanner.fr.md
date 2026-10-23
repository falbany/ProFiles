# Mode Lecteur de Codes-barres

> 🏠 **[Documentation principale](./README.md)** |
> ⚙️ **[Configuration](./configuration-profile.fr.md)** |
> 🚀 **[Guide Avancé](./advanced/guide-avance.fr.md)** |
> 🇬🇧 **[English Version](./barcode-scanner.en.md)**

---

## Aperçu

ProFiles prend en charge la **saisie par code-barres** via des lecteurs USB HID (Human Interface Device) de type *wedge*. Lorsqu'il est activé, un lecteur de code-barres connecté agit comme un clavier : il tape le contenu du code-barres caractère par caractère, puis appuie sur `Entrée` à la fin. ProFiles intercepte cette saisie et l'analyse en paires `key=value`, en appliquant automatiquement les valeurs aux contrôles de scan et en déclenchant un scan immédiat.

Cette fonctionnalité est idéale pour les déploiements en kiosque, la gestion d'inventaire et les flux de travail de lancement de fichiers rapide.

---

## Activation du Mode Lecteur de Codes-barres

### Via l'interface

1. Cliquez sur le bouton **Code-barres** dans la **Barre de Recherche** (groupe de droite, à côté du chronomètre).
2. L'icône (`QrCode`) commence à **pulser** pour indiquer que le mode code-barres est actif.
3. L'étiquette `aria-label` du bouton change en "Désactiver le mode code-barres" lorsqu'il est actif.

### Via le raccourci clavier

- Appuyez sur **`Ctrl+B`** pour activer ou désactiver le mode code-barres.

### Écouteur d'événements clavier global

Lorsque le mode code-barres est actif, ProFiles installe un **écouteur `keydown` au niveau du document** qui capture chaque frappe. Un mécanisme de débogage (délai par défaut : 50 ms) regroupe les caractères en une seule chaîne. Lorsque la touche `Entrée` terminale est détectée, la saisie accumulée est envoyée à l'analyseur de code-barres.

---

## Format de la Donnée du Code-barres

### Format Structuré (`key=value;key=value`)

Le contenu du code-barres est analysé en paires `key=value` séparées par des points-virgules :

```
filter=.py;ext=toml;recursive=0;dir=/Users/me/docs;scan=1
```

| Clé | Alias(es) | Description |
|-----|-----------|-------------|
| `filter` | `query`, `search`, `filter_text` | Texte de filtre appliqué à la liste des fichiers |
| `ext` | `extension`, `filetype` | Filtre d'extension de fichier (ex. : `.py`, `.toml`) |
| `recursive` | `recurse`, `recursive_search` | `1`/`true`/`on` → récursif ; `0`/`false`/`off` → non-récursif |
| `dir` | `directory`, `path`, `folder` | Chemin du répertoire à scanner. `~` se développe en le répertoire personnel du système d'exploitation |
| `scan` | — | `1`/`true` → déclencher automatiquement un scan après application des valeurs ; `0`/`false` → appliquer uniquement |

### Retour à l'usage simple

Si le contenu du code-barres ne contient **aucun délimiteur `=`**, la chaîne complète est traitée comme une valeur de filtre simple :

```
rapport-urgent-final
```

Cela définit le champ de filtre sur `rapport-urgent-final` et ne déclenche **pas** automatiquement un scan (sauf si `scan=1` est spécifié séparément).

---

## Application et Scan Automatique

Lorsqu'un code-barres est scanné :

1. **Les valeurs analysées sont appliquées** aux contrôles (répertoire dans la barre d'en-tête ; filtre, extension, bouton de récursion dans la barre de recherche).
2. Si la clé `scan=1` est présente (ou si le payload est un jeu structuré `key=value`), ProFiles **déclenche automatiquement un scan** avec les nouveaux critères.
3. Une **notification toast** confirme le lancement du scan.

---

## Indicateurs d'interface

### Bouton de la Barre de Recherche

| État | Icône | Comportement |
|------|------|----------|
| **Inactif** | `QrCode` (statique) | Cliquez pour activer le mode code-barres |
| **Actif** | `QrCode` + `animate-pulse` | Cliquez pour désactiver ; les frappes sont capturées |

Le bouton utilise le style cohérent de l'application :
- `border border-line bg-elevated`
- `hover:border-indigo-500 hover:text-ink`
- `focus-visible:ring-2 focus-visible:ring-indigo-500`
- `transition-colors`

### Notifications toast

| Scénario | Message toast |
|----------|---------------|
| Code-barres analysé et scan déclenché | `Code-barres scanné : N champ(s) appliqué(s) et scan déclenché.` |
| Code-barres analysé (sans drapeau scan) | `Code-barres scanné : N champ(s) appliqué(s).` |
| Mode code-barres désactivé | `Mode code-barres désactivé.` |
| Mode code-barres activé | `Mode code-barres activé. Scannez un code-barres pour remplir automatiquement les contrôles et déclencher un scan.` |

---

## Architecture Technique

```
┌─────────────────────────────────────────────────┐
│  Lecteur de Code-barres (USB HID)               │
│  — Agit comme un clavier —                     │
│  Tapez : filter=pdf;ext=pdf;dir=~/docs;scan=1  │
│  Appuie sur : Entrée                           │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  App.tsx — Écouteur keydown global              │
│  — Capture les frappes                         │
│  — Débogage en chaîne brute                    │
│  — Envoi à parseBarcodeInput()                 │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  barcodeScanner.ts — parseBarcodeInput(raw)     │
│  — Division sur le délimiteur ";"              │
│  — Division de chaque segment sur "="          │
│  — Normalisation des clés via normalizeKey()  │
│  — Retourne { values, isPlainFilter }          │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  App.tsx — handleBarcodeSubmit()                 │
│  — Applique les valeurs aux contrôles         │
│  — Déclenche le scan si scan=1               │
│  — Affiche une notification toast              │
└──────────────────────────────────────────────────┘
```

### Fonctions Clés

| Fonction | Fichier | Description |
|----------|------|-------------|
| `parseBarcodeInput(raw)` | `utils/barcodeScanner.ts` | Analyse la chaîne brute en `{ values, isPlainFilter }` |
| `normalizeKey(key)` | `utils/barcodeScanner.ts` | Mappe les alias (ex. : `directory` → `dir`, `recurse` → `recursive`) |
| `handleBarcodeToggle()` | `App.tsx` | Active/désactive le mode code-barres et gère l'écouteur keydown global |
| `handleBarcodeSubmit(raw)` | `App.tsx` | Applique les valeurs analysées et déclenche éventuellement un scan |

---

## Cas d'usage

### Poste de travail en kiosque / Gestion d'inventaire

1. Activez le mode code-barres (`Ctrl+B` ou cliquez sur le bouton `QrCode`).
2. Scannez un code-barres collé sur un dossier ou un produit.
3. Le code-barres contient `dir=/path/to/assets;ext=png;scan=1`.
4. ProFiles scanne immédiatement le répertoire et affiche tous les fichiers PNG.

### Attribution de filtre rapide

1. Scannez un code-barres contenant `filter=urgent;scan=1`.
2. ProFiles définit le filtre sur "urgent" et scanne le répertoire courant.

### Navigation vers le répertoire personnel

1. Scannez un code-barres contenant `dir=~;scan=1`.
2. ProFiles définit le répertoire sur le dossier personnel de votre système d'exploitation et lance un scan.

---

## Génération de Code QR

### Partage de l'emplacement de fichiers

ProFiles peut **générer des codes QR** encodant l'emplacement d'un fichier sous forme de payload de code-barres, afin que les destinataires puissent le scanner directement dans leur propre instance ProFiles :

1. Cliquez avec le bouton droit sur n'importe quel fichier dans la liste des résultats.
2. Sélectionnez **Générer un code QR** dans le menu contextuel.
3. Une fenêtre modale s'affiche montrant le code QR et le payload encodé (par ex. `dir=/chemin/vers/le/dossier;filter=nom_fichier.ext;ext=.ext;scan=1`).
4. Imprimez ou partagez le code QR — le destinataire active le mode code-barres (`Ctrl+B`) et scanne le QR. ProFiles remplit automatiquement le répertoire, le filtre et l'extension, puis déclenche un scan.

### Fonctionnement technique

| Composant | Description |
|-----------|-------------|
| `POST /api/actions/barcode` | Point de terminaison backend qui construit le payload et génère un QR en PNG |
| `generateBarcode()` | Fonction client frontend qui récupère l'image QR + le payload |
| `ContextMenu.tsx` | Ajoute l'élément de menu "Générer un code QR" (icône `QrCode`) |
| `App.tsx` | Affiche la modale QR et gère l'ouverture/fermeture |

Le format du payload est identique à celui consommé par le lecteur de codes-barres, garantissant une compatibilité aller-retour complète.

---

## Accessibilité

- Le bouton code-barres possède une `aria-label` qui se met à jour selon l'état du bouton.
- Le bouton inclut un inférieur `title` : "Activer le mode lecteur de codes-barres (HID USB)."
- Lorsqu'il est actif, l'animation de pulsation respecte `motion-reduce: animate-none`.
- Les notifications toast sont annoncées par les lecteurs d'écran.

---

## Dépannage

| Problème | Solution |
|---------|----------|
| L'entrée code-barres n'est pas détectée | Vérifiez que le mode code-barres est actif (le bouton pulse). Vérifiez qu'aucun autre champ n'est sélectionné. |
| Les touches apparaissent dans le champ de filtre | Le mode code-barres peut avoir été désactivé pendant le scan. Réactivez et réessayez. |
| `~` ne se développe pas en répertoire personnel | Vérifiez que `Path.expanduser()` du backend est disponible (systèmes POSIX). |
| Trop peu de caractères capturés | Augmentez l'intervalle de débogage dans `App.tsx` si vous scannez très lentement. |
| Code-barres scanné mais aucun scan déclenché | Vérifiez que le payload inclut `scan=1`. |
