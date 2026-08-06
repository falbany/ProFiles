# Design — ProFiles HOOKS → Workflow Engine

> **Date** : 2026-08-06
> **Statut** : Validé (brainstorming)
> **Portée** : Refonte du système de launch hooks en un moteur de workflow flexible, activé par double-clic sur un fichier.

---

## 1. Objectif

Transformer le système de HOOKS actuel (basé sur des phases figées `before`/`confirm`/`abort`/`instead`/`after` et un matching par extension seule) en un **moteur de workflow** :

- **Hybride** : le workflow peut soit lancer le fichier, soit le remplacer complètement par d'autres actions.
- **Config YAML intuitive** : modèle "étapes" avec vocabulaire métier.
- **Matching par patterns glob** (`*.mttl`, `toto.mttl`, `my_*.pdf`), pas seulement par extension.
- **`confirm` enrichi** : bouton **Skip** + rendu des escape sequences.
- **Nouvelle action `notify`** : boîte de message avec rendu Markdown (sous-ensemble).
- **Pas de rétrocompatibilité** : la configuration existante est migrée vers le nouveau format.

---

## 2. Décisions clés (issues du brainstorming)

| Sujet | Décision |
| ----- | -------- |
| Portée du workflow | **Hybride** — lance le fichier OU le remplace |
| Interface de config | **YAML** (format actuel), enrichi |
| Patterns de fichiers | **Glob simples** (`*`, `?`) |
| Priorité des patterns | **Le plus spécifique gagne** |
| Modèle d'exécution | **Par étapes ordonnées** (pas de phases figées) |
| Bouton Skip | **Step-over** : saute l'action protégée ; si dernière → saute le lancement OS |
| `ask` | **Garde de confirmation** attaché à n'importe quelle action (pas une action séparée) |
| Rendu Markdown | **Sous-ensemble de base** (extensible vers complet) |
| Rétrocompatibilité | **Non** — migration vers le nouveau format |

---

## 3. Architecture

On conserve l'architecture en couches existante (core pur, GUI délègue). Le moteur reste dans `src/profiles/core/environment/`.

```
src/profiles/core/environment/
├── workflow.py        # Moteur "étapes" (orchestration pure, aucun Tkinter)
├── matcher.py         # Sélection du pattern glob le plus spécifique
├── render.py          # Escape sequences + Markdown → RenderTree (pur)
├── interactions.py    # Dialog 3-way (Yes/Skip/No) — GUI + headless
└── message_dialog.py  # Boîte notify (blocking / non-blocking)
```

### Règles d'architecture

- **Core** : zéro dépendance Tkinter. Les dialogues sont **injectés** (mockables).
- **GUI** : traduit la `RenderTree` en widgets `ttk`/`Text` avec tags de style.
- **Utils** : fonctions pures (matcher, renderer).

---

## 4. Matching par patterns glob

Les clés de `hooks.entries` deviennent des **patterns glob** (rétro-compatibles avec les extensions : `.pdf` reste valide).

**Priorité : le plus spécifique gagne** (tri décroissant de spécificité) :

1. Pattern exact (aucun wildcard) — `toto.mttl`
2. Pattern avec `?` uniquement
3. Pattern avec `*`
4. Extension seule (`.pdf`) — cas le plus générique

Un fichier matche **un seul** pattern (le plus spécifique). Pas de fusion.

**Exemple** : `toto.mttl` matche `toto.mttl` (exact) plutôt que `*.mttl`.

---

## 5. Modèle "étapes" — configuration YAML

Chaque entrée = une **étape** avec un vocabulaire métier. Fini les phases techniques exposées à l'utilisateur.

```yaml
hooks:
  entries:
    "*.mttl":
      - action: notify          # afficher une info (message)
        content: |
          # Lancement de {name}
          **Fichier** : `{path}`
        wait: false             # non-bloquant
      - action: run             # exécuter une commande
        ask: "⚠️ Lancer le logger ?"
        content: 'logger "{date} launch {path}"'
      - action: replace         # remplacer le lancement OS
        ask: "Ouvrir avec le viewer custom ?"
        content: "myviewer --file {path}"
    "toto.mttl":                # plus spécifique → prioritaire sur *.mttl
      - action: run
        content: "special_handler.sh {path}"
    "my_*.pdf":
      - action: check           # vérifier avant de continuer
        content: "check_safety.sh {path}"
```

### Champs génériques

| Champ | Rôle | Valeurs |
| ----- | ---- | ------- |
| `action` | Ce que fait l'étape | `notify`, `run`, `run_after`, `replace`, `check` |
| `content` | Commande **ou** texte (selon `action`) | n'importe quel texte |
| `ask` | Garde de confirmation (optionnel) | texte du message |
| `wait` | Bloque-t-on le flux ? | `true`/`false` (défaut `true`) |
| `on_failure` | Que faire si l'étape échoue | `stop` \| `warn` \| `continue` (défaut `stop`) |

### Vocabulaire des `action`

| `action` | Sens pour l'utilisateur | Bloque ? |
| -------- | ----------------------- | -------- |
| `notify` | Affiche un message (Markdown) | `wait` |
| `run` | Exécute une commande avant lancement | oui |
| `run_after` | Exécute une commande après lancement | non |
| `replace` | Remplace le lancement OS par cette commande | oui |
| `check` | Vérifie ; échec ⇒ arrêt | oui |

### `on_failure`

- `stop` → arrête le workflow (défaut)
- `warn` → log un avertissement et continue
- `continue` → passe à l'étape suivante sans rien signaler

---

## 6. Garde de confirmation `ask`

`ask` est un champ optionnel sur **toute action**. S'il est présent, l'utilisateur doit confirmer **avant** que l'action s'exécute.

Dialog **Yes / Skip / No** :

| Bouton | Verdict | Effet |
| ------ | ------- | ----- |
| **Yes** | `CONTINUE` | L'action s'exécute normalement. |
| **Skip** | `SKIP_STEP` | **L'action elle-même est sautée**, on passe à l'étape suivante. |
| **No** | `ABORT` | Workflow arrêté, erreur affichée. |

**Cas particulier** : si le garde `ask` est sur la **dernière** action et que l'utilisateur choisit **Skip** → l'action est sautée **et** le lancement OS est sauté (succès silencieux).

- **GUI** : `Toplevel` Tkinter avec 3 boutons (car `askyesno` ne supporte que 2 boutons).
- **Headless** : prompt `[y/s/N]`.
- **Escape sequences** : `\n`, `\t`, `\\`, `\"` rendus avant affichage.

---

## 7. Flux d'exécution

**Sélection du pattern** (au double-clic) :
1. Prendre le nom de fichier → matcher contre les clés glob (`fnmatch`).
2. **Plus spécifique gagne** : exact > `?` > `*` > extension.
3. Les étapes du pattern retenu forment le **workflow** de ce fichier.

**Pipeline "étapes"** — les étapes s'exécutent **dans l'ordre de déclaration YAML**. Chaque étape retourne un verdict :

| Verdict | Signification | Effet |
| ------- | ------------- | ----- |
| `CONTINUE` | L'étape a réussi | Passer à l'étape suivante |
| `SKIP_LAUNCH` | Ne pas lancer le fichier | Arrêt du workflow, succès silencieux |
| `ABORT` | Échec / refus | Arrêt du workflow, erreur affichée |
| `SKIP_STEP` | **Skip** (garde `ask`) | Sauter l'action protégée, puis continuer |

**Fin de workflow** : quand toutes les étapes sont passées, le **lancement OS** a lieu — sauf si une étape a produit `SKIP_LAUNCH` (ex. `replace` a réussi, ou Skip sur le dernier `ask`).

### Verdicts par action

| `action` | Verdict succès | Verdict échec | Bloque ? |
| -------- | -------------- | ------------- | -------- |
| `notify` | `CONTINUE` | `CONTINUE` (jamais d'échec) | `wait` |
| `run` | `CONTINUE` | `on_failure` | oui |
| `run_after` | `CONTINUE` | ignoré (non-bloquant) | non |
| `replace` | `SKIP_LAUNCH` | `on_failure` | oui |
| `check` | `CONTINUE` | `ABORT` (toujours) | oui |

`notify` avec `wait: false` est lancé en arrière-plan (fenêtre non-bloquante) et ne retarde jamais le flux.

---

## 8. Rendu — escape sequences & Markdown

### Escape sequences (dans `content` et `ask`)

| Séquence | Rendu |
| -------- | ----- |
| `\n` | Saut de ligne |
| `\t` | Tabulation |
| `\\` | Backslash littéral |
| `\"` | Guillemet double littéral |
| `\'` | Guillemet simple littéral |

### Rendu Markdown (sous-ensemble de base, extensible)

| Syntaxe | Rendu Tkinter |
| ------- | ------------- |
| `#`, `##`, `###` | Titres (taille de police décroissante) |
| `**gras**` | Texte en gras |
| `*italique*` | Texte en italique |
| `- item` / `* item` | Puces (avec indentation) |
| `` `code` `` | Police monospace |
| ` ``` ... ``` ` | Bloc de code monospace |
| `[texte](url)` | Lien cliquable (ouvre le navigateur) |
| Lignes vides | Séparation de paragraphes |

### Architecture du rendu

- `render.py` (core pur) transforme le texte en **liste d'éléments structurés** (segments avec style) — pas de Tkinter dans le core.
- La **GUI** traduit ces éléments en widgets `ttk`/`Text` avec tags de style.
- **Headless** : rend une version texte brut (markdown strippé, escape sequences résolues).

Le renderer est **indépendant du backend** — le core produit une structure (type `RenderTree`), et chaque front-end la dessine. Permet d'étendre vers le Markdown complet plus tard sans toucher au moteur.

---

## 9. Gestion des erreurs

| Situation | Comportement |
| --------- | ----------- |
| Commande introuvable (`run`/`replace`) | `on_failure` décide (`stop`/`warn`/`continue`) |
| Timeout (`run`/`check`) | Traité comme un échec → `on_failure` |
| `check` échoue | Toujours `ABORT` (indépendant de `on_failure`) |
| `notify` / `ask` erreur de rendu | Log + `ABORT` |
| `run_after` échoue | Ignoré (non-bloquant), log |
| Aucun pattern ne matche | Lancement OS direct (comportement actuel) |

**Résultats finaux exposés au front-end** :
- `CONTINUE` → lancement OS
- `SKIP_LAUNCH` → succès silencieux (pas de lancement)
- `ABORT` → erreur affichée (messagebox GUI / logique headless)

---

## 10. Stratégie de test

Couverture cible > 85%. Le moteur de workflow est **pur** (aucun Tkinter) — les dialogues sont injectés (mockables).

| Fichier de test | Couvre |
|-----------------| ------ |
| `test_matcher.py` | Priorité de spécificité, glob `*`/`?`, extension rétro |
| `test_render.py` | Escape sequences, syntaxes Markdown, `RenderTree` |
| `test_workflow.py` | Ordre des étapes, verdicts, Skip step-over, `on_failure` |
| `test_interactions.py` | Dialog 3-way (mocké + headless) |
| `test_launch_hooks.py` (migré) | Intégration complète, actions, lancement |

---

## 11. Hors périmètre (futur)

- Rendu Markdown complet (tableaux, citations, images).
- Expansion de variables d'environnement (`${VAR}`) dans les templates.
- Hooks conditionnels basés sur des prédicats (ex. hostname).
- Éditeur graphique de workflows.

---

_Fin du document de design._