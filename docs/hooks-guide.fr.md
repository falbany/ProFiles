# Workflows de Lancement — Référence Complète

> 🏠 **[Accueil Documentation](./README.md)** |
> 📦 **[Installation](./installation-guide.fr.md)** |
> ⚙️ **[Configuration](./configuration-profile.fr.md)** |
> 🔧 **Workflows** |
> 📊 **[Colonnes Dynamiques](./columns-guide.en.md)** |
> 🚀 **[Guide Avancé](./advanced/guide-avance.fr.md)**

---

Les workflows de lancement constituent un moteur puissant permettant d'exécuter une séquence d'actions autour de chaque lancement de fichier. Ce système offre une flexibilité accrue grâce à une syntaxe YAML structurée et des fonctionnalités avancées.

**Moteur principal** : `src/profiles/core/environment/workflow.py`  
**Orchestration** : `src/profiles/core/actions.py` (`launch_selected_file`)  
**Configuration** : Section `hooks` dans votre fichier `.profiles`

## Table des Matières

1. [Syntaxe YAML et Structure](#syntaxe-yaml-et-structure)
2. [Actions Disponibles](#actions-disponibles)
3. [Confirmation Guards (ask)](#confirmation-guards-ask)
4. [Substitution de Jetons](#substitution-de-jetons)
5. [Notifications Riches (Markdown)](#notifications-riches-markdown)
6. [Gestion des Erreurs et Failmode](#gestion-des-erreurs-et-failmode)
7. [Comportement des Timeout](#comportement-des-timeout)
8. [Spécificité des Motifs (Pattern Matching)](#spécificité-des-motifs-pattern-matching)
9. [Exemples Complets](#exemples-complets)
10. [Migration depuis l'Ancien Format INI](#migration-depuis-lancien-format-ini)
11. [API de Programmation](#api-de-programmation)
12. [Dépannage](#dépannage)

---

## Syntaxe YAML et Structure

Les workflows utilisent une structure YAML par étapes. Chaque entrée dans `hooks.entries` est un **motif glob** qui correspond à des noms de fichiers.

### Structure de Base

```yaml
hooks:
  failmode: warn           # Mode d'échec global : "warn" | "abort" | "skip"
  timeout: 30              # Timeout par défaut en secondes pour les étapes bloquantes
  entries:
    "*.mttl":              # Motif glob (tous les fichiers .mttl)
      - action: notify
        content: "# Lancement de {{filename}}\\nPréparation de l'environnement..."
      - action: run
        content: "prepare_env.exe --file {{path}}"
        ask: "Exécuter le script de préparation ?"
        wait: true
        on_failure: stop
      - action: replace
        content: "special_launcher.exe {{path}}"
        ask: "Utiliser le lanceur spécial ?"
        wait: true
        on_failure: warn
    
    "special.mttl":        # Motif plus spécifique (fichier exact)
      - action: notify
        content: "**Traitement spécial** pour ce fichier."
      - action: run_after
        content: "logger.exe --special {{filename}}"
        wait: false
```

### Syntaxe des Motifs Glob

| Motif          | Description                  | Exemple                    |
| -------------- | ---------------------------- | -------------------------- |
| `*`            | Zéro ou plusieurs caractères | `*.pdf`, `report_*.txt`    |
| `?`            | Un seul caractère            | `test?.txt`, `data?.csv`   |
| `.ext`         | Raccourci pour `*.ext`       | `.mttl`, `.pdf`            |
| `filename.ext` | Correspondance exacte        | `manual.pdf`, `readme.txt` |

**Règle de priorité** : Lorsqu'un fichier correspond à plusieurs motifs, le moteur sélectionne le **plus spécifique** :
1. Correspondance exacte (`manual.pdf`) > `?` > `*` > `.ext`
2. Les motifs plus spécifiques **écrasent** les motifs génériques

---

## Actions Disponibles

Le moteur supporte **cinq types d'actions**, chacune avec un comportement spécifique :

### 1. `notify` — Notification Utilisateur

Affiche un message à l'utilisateur avec support partiel du Markdown.

```yaml
- action: notify
  content: "# Titre\\n**Message important**\\n*Note: Ceci est une italique*"
  wait: true  # Bloque jusqu'à ce que l'utilisateur ferme le dialogue
```

**Comportement** :
- **GUI mode** : Affiche une fenêtre Tkinter avec texte formaté
- **Headless mode** : Imprime le message formaté sur la sortie standard
- **Toujours réussi** : Ne peut pas échouer, donc `on_failure` est ignoré
- **Support Markdown** : `# Heading`, `**bold**`, `*italic*`, `` `code` ``, `\\n`

### 2. `run` — Exécution Synchronisée

Exécute une commande shell et attend la fin de l'exécution.

```yaml
- action: run
  content: "prepare_env.exe --file {{path}} --verbose"
  wait: true           # Attend la fin (défaut)
  on_failure: stop     # stop | warn | continue
  timeout: 15          # Optionnel : surcharge du timeout global (secondes)
  if: "env:DEBUG"      # Optionnel : n'exécute que si DEBUG est défini
```

**Comportement** :
- **Bloquant** : Le workflow attend la fin de la commande
- **Capture la sortie** : stdout/stderr capturés (non affichés par défaut)
- **Code de retour** : 0 = succès, non-0 = échec
- **Gestion d'échec** : Respecte `on_failure` (voir section [Gestion des Erreurs](#gestion-des-erreurs-et-failmode))

### 3. `run_after` — Exécution Asynchrone

Lance une commande en arrière-plan et continue immédiatement.

```yaml
- action: run_after
  content: "logger.exe --opened {{filename}} --async"
  wait: false  # Toujours false pour run_after
```

**Comportement** :
- **Non-bloquant** : Le workflow continue immédiatement
- **Processus détaché** : Le processus enfant est indépendant
- **Toujours réussi** : Ne peut pas échouer (échecs silencieux)
- **Usage typique** : Logging, notifications, nettoyage asynchrone

### 4. `replace` — Remplacement du Lancement OS

Exécute une commande **à la place** du lancement OS par défaut.

```yaml
- action: replace
  content: "special_launcher.exe {{path}} --custom-args"
  ask: "Utiliser le lanceur spécial ?"
  wait: true
```

**Comportement** :
- **Remplace le lancement OS** : La commande est exécutée INSTEAD de l'association OS
- **Workflow terminé** : Après `replace`, le workflow se termine (pas de lancement OS)
- **Blocage** : Attend la fin de la commande (si `wait: true`)
- **Usage typique** : Lanceurs personnalisés, émulateurs, environnements spéciaux

### 5. `check` — Vérification de Condition

Exécute une commande et vérifie son code de retour.

```yaml
- action: check
  content: "env_check.exe --verify {{dir}}"
  wait: true
  on_failure: warn
```

**Comportement** :
- **Bloquant** : Attend la fin de la commande
- **Vérification explicite** : Utilisé pour valider des préconditions
- **Gestion d'échec** : Respecte `on_failure`
- **Usage typique** : Vérification d'environnement, pré-requis, validations

---

## Confirmation Guards (ask)

Chaque étape peut être protégée par une invite de confirmation **Oui/Passer/Non**.

```yaml
- action: run
  content: "dangerous_operation.exe {{path}}"
  ask: "Êtes-vous sûr de vouloir exécuter cette opération dangereuse ?"
```

### Comportement des Choix

| Choix             | Action                   | Résultat                                                 |
| ----------------- | ------------------------ | -------------------------------------------------------- |
| **Oui**           | Exécute l'étape actuelle | Continue au prochain étape                               |
| **Passer** (Skip) | Ignore l'étape actuelle  | Passe au **prochain** étape                              |
| **Non**           | Aborte immédiatement     | **Arrête tout le workflow** (et le lancement du fichier) |

### Comportement sur Dernier Étape

Si l'utilisateur choisit **Passer** sur le **dernier** étape :
- Le workflow se termine
- Le lancement OS est **sauté** (SKIP_LAUNCH)

### Exemple avec Multiple Guards

```yaml
entries:
  "*.mttl":
    - action: run
      content: "prepare.exe {{path}}"
      ask: "Préparer le fichier ?"  # Oui/Passer/Non
      
    - action: notify
      content: "Environnement préparé."
      
    - action: run
      content: "validate.exe {{path}}"
      ask: "Valider avant lancement ?"  # Oui/Passer/Non
      
    - action: replace
      content: "special_launcher.exe {{path}}"
      ask: "Utiliser lanceur spécial ?"  # Oui/Passer/Non
```

**Scénarios** :
- **Oui → Oui → Oui** : Tous les étapes exécutés, lanceur spécial utilisé
- **Oui → Passer → Oui** : Étape 2 sautée, lanceur spécial utilisé
- **Passer** (premier) : Étape 1 sautée, continue aux étapes suivants
- **Non** (n'importe où) : Workflow aborté, fichier **non lancé**

---

## Substitution de Jetons

Le moteur substitue automatiquement des **placeholders** au moment de l'exécution.

### Jetons Disponibles

| Jeton          | Valeur                        | Exemple                      |
| -------------- | ----------------------------- | ---------------------------- |
| `{{path}}`     | Chemin absolu du fichier      | `C:\\Projects\\test.mttl`    |
| `{{dir}}`      | Dossier parent du fichier     | `C:\\Projects\\`             |
| `{{filename}}` | Nom du fichier avec extension | `test.mttl`                  |
| `{{stem}}`     | Nom du fichier sans extension | `test`                       |
| `{{ext}}`      | Extension (avec point)        | `.mttl`                      |
| `{{content}}`  | Contenu de l'étape actuel     | Utile dans les invites `ask` |
| `{{username}}` | Nom d'utilisateur             | `alice`                      |
| `{{hostname}}` | Nom de machine                | `workstation-01`             |
| `{{date}}`     | Date du jour (ISO 8601)       | `2026-08-29`                 |

### Exemples d'Utilisation

```yaml
entries:
  "*.pdf":
    - action: notify
      content: "# Ouverture de {{filename}}\\nChemin : {{path}}"
      
    - action: run
      content: "tracker.exe --log {{filename}} --dir {{dir}}"
      
    - action: run_after
      content: "backup.exe {{path}} --timestamp {{date}}"
```

### Jeton `{{content}}` — Cas d'Usage Spécifique

Le jeton `{{content}}` est substitué avec la chaîne `content` de l'étape actuel. Utile pour les invites de confirmation :

```yaml
- action: run
  content: "special_tool.exe {{path}} --mode=advanced"
  ask: "Exécuter : {{content}}"
```

**Résultat** : L'invite affichera "Exécuter : special_tool.exe test.mttl --mode=advanced"

---

## Notifications Riches (Markdown)

L'action `notify` supporte un **sous-ensemble de Markdown** pour une communication claire.

### Syntaxe Supportée

| Syntaxe         | Rendu                | Exemple                                |
| --------------- | -------------------- | -------------------------------------- |
| `# Titre`       | Heading niveau 1     | `# Lancement en cours`                 |
| `## Sous-titre` | Heading niveau 2     | `## Préparation...`                    |
| `**gras**`      | Texte en gras        | `**Important** : Vérifiez les données` |
| `*italique*`    | Texte en italique    | `*Note* : Ceci est optionnel`          |
| `` `code` ``    | Texte en police fixe | `` `commande.exe --arg` ``             |
| `\\n`           | Nouvelle ligne       | `Ligne 1\\nLigne 2`                    |

### Exemple Complet de Notification

```yaml
- action: notify
  content: |
    # Lancement de {{filename}}
    
    **Statut** : Préparation de l'environnement...
    
    *Note* : Cette opération peut prendre quelques secondes.
    
    Commande : `prepare_env.exe --file {{path}}`
```

**Rendu GUI** :
- Titre en grand et gras
- Texte en gras pour "Important"
- Texte en italique pour les notes
- Code en police fixe
- Mise en page aérée

**Rendu Headless** :
- Texte plat avec escape sequences
- Markdown stripé (voir `render_text()` dans `src/profiles/core/environment/render.py`)

---

## Gestion des Erreurs et Failmode

### Paramètres Globaux

```yaml
hooks:
  failmode: warn    # Comportement par défaut pour les échecs
  timeout: 30       # Timeout en secondes pour les étapes bloquantes
```

### Modes d'Échec (`failmode`)

| Mode    | Comportement                                      | Usage                                |
| ------- | ------------------------------------------------- | ------------------------------------ |
| `warn`  | Avertit l'utilisateur, continue au prochain étape | **Défaut** — tolérant aux erreurs    |
| `abort` | Annule immédiatement le workflow                  | Strict — échec = arrêt total         |
| `skip`  | Sauté le reste du workflow, retourne SKIP_LAUNCH  | Arrêter proprement sans lancement OS |

### Paramètre `on_failure` par Étape

Chaque étape peut surcharger le `failmode` global :

```yaml
- action: run
  content: "critical_setup.exe {{path}}"
  on_failure: abort  # Surcharge le failmode global
```

**Valeurs possibles** :
- `stop` : Arrête le workflow (équivalent à `abort`)
- `warn` : Avertit mais continue (équivalent à `warn`)
- `continue` : Supprime l'erreur et continue (similaire à `warn` mais sans avertissement)

### Hiérarchie de Priorité

1. **`on_failure` par étape** > `failmode` global
2. **`abort`** (motif) > `failmode` global
3. **`requires_success: false`** (legacy) > `requires_success: true`

### Comportement sur Timeout

Un timeout compte comme un **échec** (code de retour non-0) :

```yaml
hooks:
  timeout: 10  # Timeout court
  
entries:
  "*.mttl":
    - action: run
      content: "slow_command.exe {{path}}"
      # Si > 10s : timeout → échec → failmode appliqué
```

---

## Comportement des Timeout

### Timeout Global

Défini dans `hooks.timeout` (défaut : 30 secondes).

```yaml
hooks:
  timeout: 60  # 60 secondes pour tous les étapes bloquants
```

### Timeout par Étape (override)

Chaque étape peut surcharger le timeout global avec son propre champ `timeout` :

```yaml
hooks:
  timeout: 30  # Timeout global par défaut

entries:
  "*.mttl":
    - action: run
      content: "quick_check.exe {{path}}"
      timeout: 5    # Surcharge — 5 secondes pour cette étape seulement
    - action: run
      content: "slow_build.exe {{path}}"
      # Utilise le timeout global de 30s
```

Lorsqu'un `timeout` par étape est défini, il prend le pas sur `hooks.timeout`.
Un timeout entraîne un résultat d'échec (code de retour non-0) et déclenche la résolution `on_failure` de l'étape.

**S'applique à** : les actions `run`, `check`, et `replace`.

### Commandes Asynchrones (`run_after`)

Les étapes `run_after` **ne sont pas sujettes au timeout** :
- Elles sont lancées en arrière-plan
- Le workflow continue immédiatement
- Les échecs de spawn sont silencieux

---

## Exécution Conditionnelle (`if`)

Chaque étape peut inclure une condition `if` qui contrôle si l'étape s'exécute.

### Vérifications de Variables d'Environnement

Le champ `if` supporte les vérifications de variables d'environnement :

```yaml
entries:
  "*.mttl":
    - action: run
      content: "deploy.exe --production {{path}}"
      if: "env:DEPLOY_ENV"      # S'exécute seulement si DEPLOY_ENV est défini
    - action: run
      content: "staging_deploy.exe {{path}}"
      if: "env:DEPLOY_ENV=prod"  # S'exécute seulement si DEPLOY_ENV = "prod"
```

| Syntaxe            | Comportement                                  |
| ------------------ | --------------------------------------------- |
| `env:VAR_NAME`     | L'étape s'exécute si `VAR_NAME` est **défini** (n'importe quelle valeur) |
| `env:VAR=value`    | L'étape s'exécute si `VAR_NAME` **vaut** `value`  |

Si la condition **n'est pas remplie**, l'étape est silencieusement ignorée — le workflow continue à l'étape suivante.

---

Le moteur utilise un **algorithme de scoring** pour déterminer le motif le plus spécifique.

### Algorithme de Spécificité

1. **Correspondance exacte** (`manual.pdf`) → Score le plus élevé
2. **Motif `?`** (`test?.txt`) → Score élevé
3. **Motif `*`** (`report_*.pdf`) → Score moyen
4. **Raccourci extension** (`.pdf`) → Score le plus bas

### Exemple de Priorité

```yaml
hooks:
  entries:
    "*.mttl":           # Score bas — tous les .mttl
      - action: notify
        content: "Traitement générique .mttl"
    
    "special.mttl":     # Score élevé — fichier exact
      - action: notify
        content: "Traitement SPECIAL pour special.mttl"
    
    "test?.mttl":       # Score moyen — test1.mttl, test2.mttl
      - action: notify
        content: "Traitement pour test?.mttl"
```

**Résultats** :
- `special.mttl` → Utilise le motif `special.mttl` (exact)
- `test1.mttl` → Utilise le motif `test?.mttl` (`?` > `*`)
- `other.mttl` → Utilise le motif `*.mttl` (générique)

### Implémentation

Voir `src/profiles/core/environment/matcher.py` pour l'algorithme de scoring.

---

## Exemples Complets

### Exemple 1 : Workflow de Préparation Standard

```yaml
hooks:
  failmode: warn
  timeout: 30
  entries:
    "*.mttl":
      - action: notify
        content: "# Lancement de {{filename}}\\nPréparation de l'environnement..."
      
      - action: run
        content: "prepare_env.exe --file {{path}} --verbose"
        ask: "Exécuter la préparation ?"
        wait: true
        on_failure: stop
      
      - action: run
        content: "validate_env.exe --check {{dir}}"
        wait: true
        on_failure: warn
      
      - action: notify
        content: "**Environnement prêt**\\nLancement en cours..."
```

### Exemple 2 : Lanceur Personnalisé avec Confirmation

```yaml
hooks:
  failmode: abort
  timeout: 15
  entries:
    "*.exe":
      - action: notify
        content: "# Exécution d'un exécutable\\n**Attention** : Vérifiez l'origine du fichier."
        wait: true
      
      - action: run
        content: "antivirus.exe --scan {{path}}"
        ask: "Scanner avec antivirus ?"
        wait: true
        on_failure: warn
      
      - action: replace
        content: "sandbox_launcher.exe {{path}}"
        ask: "Exécuter en sandbox ?"
        wait: true
        on_failure: stop
```

### Exemple 3 : Logging et Audit

```yaml
hooks:
  failmode: warn
  timeout: 10
  entries:
    "*.pdf":
      - action: run_after
        content: "audit_logger.exe --opened {{filename}} --user {{username}} --time {{date}}"
        wait: false
      
      - action: run_after
        content: "backup.exe {{path}} --destination \\\\server\\backup"
        wait: false
```

### Exemple 4 : Workflow Conditionnel avec Multiple Guards

```yaml
hooks:
  failmode: warn
  timeout: 30
  entries:
    "*.mttl":
      - action: run
        content: "check_dependencies.exe {{dir}}"
        ask: "Vérifier les dépendances ?"
        wait: true
        on_failure: abort
      
      - action: notify
        content: "**Dépendances vérifiées**\\nContinuer le lancement ?"
      
      - action: run
        content: "prepare_data.exe {{path}}"
        ask: "Préparer les données ?"
        wait: true
        on_failure: warn
      
      - action: run
        content: "special_tool.exe {{path}} --mode=advanced"
        ask: "Exécuter : {{content}}"
        wait: true
        on_failure: stop
```

---

## API de Programmation

Pour les utilisateurs avancés souhaitant intégrer le moteur dans leur propre code.

### Module Principal

```python
from profiles.core.environment.workflow import (
    run_workflow,
    WorkflowOutcome,
)
from profiles.core.config.models import WorkflowStep
```

### Exemple d'Utilisation Programmée

```python
from pathlib import Path
from profiles.core.environment.workflow import run_workflow, WorkflowOutcome
from profiles.core.config.models import WorkflowStep

# Définir les étapes
steps = [
    WorkflowStep(
        action="notify",
        content="# Lancement personnalisé\\nFichier : {{filename}}",
    ),
    WorkflowStep(
        action="run",
        content="prepare.exe {{path}}",
        wait=True,
        on_failure="stop",
    ),
    WorkflowStep(
        action="replace",
        content="custom_launcher.exe {{path}}",
        wait=True,
    ),
]

# Exécuter le workflow
file_path = Path("C:\\test.mttl")
outcome = run_workflow(
    steps=steps,
    file_path=file_path,
    headless=False,
    # ask_callback=custom_ask_handler,  # Optionnel
    # notify_callback=custom_notify_handler,  # Optionnel
)

# Traiter le résultat
if outcome == WorkflowOutcome.CONTINUE:
    # Lancer avec l'association OS par défaut
    launch_file(file_path)
elif outcome == WorkflowOutcome.SKIP_LAUNCH:
    # Workflow terminé, pas de lancement OS
    print("Workflow terminé, pas de lancement OS")
elif outcome == WorkflowOutcome.ABORT:
    # Workflow aborté (par utilisateur ou erreur)
    print("Workflow aborté")
```

### Callbacks Personnalisés

```python
def custom_ask_handler(message: str) -> Literal["yes", "skip", "no"]:
    """Invite de confirmation personnalisée."""
    print(f"Question : {message}")
    response = input("[y/s/N]: ").strip().lower()
    if response in ("y", "yes"):
        return "yes"
    if response in ("s", "skip"):
        return "skip"
    return "no"

def custom_notify_handler(message: str, blocking: bool) -> None:
    """Notification personnalisée."""
    print(f"[NOTICE] {message}")

# Utiliser les callbacks
outcome = run_workflow(
    steps=steps,
    file_path=file_path,
    ask_callback=custom_ask_handler,
    notify_callback=custom_notify_handler,
)
```

---

## Dépannage

### Problème : Le Hook ne s'exécute jamais

**Cause** : Spécificité du motif ou incohérence de correspondance.

**Solutions** :
1. Vérifier que le motif correspond au fichier (ex: `.mttl` vs `*.mttl`)
2. Utiliser un motif plus spécifique (ex: `special.mttl` au lieu de `*.mttl`)
3. Vérifier l'extension du fichier (case-sensitive ?)

**Debug** : Activer le logging `verbose: DEBUG` dans `.profiles`

### Problème : Les Variables Restent Littérales

**Cause** : Orthographe incorrecte des jetons.

**Solutions** :
1. Vérifier la syntaxe : `{{path}}`, `{{filename}}`, `{{dir}}`, `{{ext}}`, `{{stem}}`
2. S'assurer d'utiliser **deux accolades** de chaque côté
3. Vérifier que le fichier existe (les jetons nécessitent un `file_path` valide)

### Problème : Le Dialogue de Notification ne s'Affiche Pas

**Cause** : Mode headless ou Tkinter manquant.

**Comportement attendu** :
- En mode headless : Le message est imprimé sur la sortie standard
- Si Tkinter manquant : Fallback automatique vers headless

**Solutions** :
1. Vérifier que Tkinter est installé (`python -m tkinter`)
2. En mode headless, vérifier la console pour les messages

### Problème : Timeout Fréquent

**Cause** : Commandes trop lentes pour le timeout configuré.

**Solutions** :
1. Augmenter `hooks.timeout` dans `.profiles`
2. Définir un `timeout` par étape pour surcharger la valeur globale pour les commandes lentes
3. Utiliser `action: run_after` pour les commandes longues en arrière-plan
4. Optimiser la commande pour qu'elle soit plus rapide

### Problème : Étape `if` ne s'exécute Pas

**Cause** : Vérification de variable d'environnement non remplie.

**Solutions** :
1. Vérifier que la variable est définie dans l'environnement avant le lancement
2. Utiliser `env:VAR` pour les vérifications d'existence ou `env:VAR=value` pour l'égalité
3. Se rappeler : les étapes ignorées sont **silencieuses** — aucun avertissement n'est journalisé

### Problème : Workflow ne S'arrête Pas sur Échec

**Cause** : `failmode` ou `on_failure` mal configuré.

**Solutions** :
1. Vérifier `failmode: abort` pour un comportement strict
2. Ajouter `on_failure: stop` aux étapes critiques
3. Utiliser `action: check` pour les validations explicites

---

## Références Techniques

### Fichiers Source

- **Moteur de workflow** : `src/profiles/core/environment/workflow.py`
- **Gestion des hooks legacy** : `src/profiles/core/environment/execution.py`
- **Modèles de données** : `src/profiles/core/config/models.py`
- **Dialogue de confirmation** : `src/profiles/core/environment/interactions.py`
- **Dialogue de notification** : `src/profiles/core/environment/message_dialog.py`
- **Rendu Markdown** : `src/profiles/core/environment/render.py`
- **Matching de motifs** : `src/profiles/core/environment/matcher.py`

### Classes et Fonctions Clés

- `WorkflowStep` : Modèle de données pour une étape
- `run_workflow()` : Fonction principale d'exécution
- `WorkflowOutcome` : Énumération des résultats (CONTINUE, SKIP_LAUNCH, ABORT)
- `confirm_dialog_3way()` : Dialogue Oui/Passer/Non
- `show_notify_dialog()` : Dialogue de notification
- `render_text()` : Rendu Markdown vers GUI/Headless

---

_Document généré le 2026-08-07._

---

_Fin de référence._
