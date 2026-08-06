# Workflows de Lancement — Référence

> 🏠 **[Accueil Documentation](./README.md)** |
> 📦 **[Installation](./installation-guide.fr.md)** |
> ⚙️ **[Configuration](./configuration-profile.fr.md)** |
> 🔧 **Workflows** |
> 📊 **[Colonnes Dynamiques](./columns-guide.en.md)** |
> 🚀 **[Guide Avancé](./advanced/guide-avance.fr.md)**

---

Les workflows de lancement vous permettent d'exécuter une séquence d'actions autour de chaque lancement de fichier. Le moteur se trouve dans
`src/profiles/core/environment/workflow.py` et est invoqué par `launch_selected_file` dans
`actions.py`. Les workflows sont configurés dans la section `hooks` de votre configuration `.profiles`.

## Syntaxe YAML

Les workflows utilisent une structure YAML par étapes. Chaque entrée dans `hooks.entries` est un motif glob
supportant les jokers (`*`, `?`) et les raccourcis d'extension.

```yaml
hooks:
  failmode: warn           # warn | abort | skip
  timeout: 30              # secondes
  entries:
    "*.mttl":
      - action: notify
        content: "# Lancement de {{filename}}\\nPréparation de l'environnement..."
      - action: run
        content: "prepare_env.exe --file {{path}}"
        ask: "Exécuter le script de préparation ?"
      - action: replace
        content: "special_launcher.exe {{path}}"
        ask: "Utiliser le lanceur spécial au lieu du défaut OS ?"
    
    "special.mttl":
      - action: notify
        content: "**Traitement spécial** pour ce fichier."
```

## Spécificité des Motifs (Patterns)

Lorsque plusieurs motifs correspondent à un nom de fichier, ProFiles sélectionne le **plus spécifique** :
1. **Correspondance exacte** (ex: `manual.pdf`) gagne sur les jokers.
2. **Motifs avec point d'interrogation** (ex: `test?.txt`) gagnent sur les motifs avec étoile.
3. **Motifs avec étoile** (ex: `report_*.pdf`) gagnent sur les raccourcis d'extension.
4. **Raccourcis d'extension** (ex: `.pdf`) sont les moins spécifiques.

## Actions de Workflow

| Action      | Description                               | Bloquant | Gestion des Échecs           |
| ----------- | ----------------------------------------- | -------- | ---------------------------- |
| `notify`    | Affiche un message Markdown à l'utilisateur. | Optionnel | N'échoue jamais.             |
| `run`       | Exécute une commande shell.                | Oui      | Soumis à `on_failure`.       |
| `run_after` | Lance une commande en arrière-plan.      | Non      | Ne bloque/n'arrête jamais.   |
| `replace`   | Exécute une commande à la place de l'OS.  | Oui      | Ignore le lancement OS standard. |
| `check`     | Exécute une commande et vérifie son code. | Oui      | Soumis à `on_failure`.       |

## Gardes de Confirmation (ask)

Chaque étape peut être protégée par une invite `ask`. Cela affiche un dialogue **Oui/Passer/Non** :
- **Oui** : Exécute l'étape actuelle et continue.
- **Passer** (Skip) : Ignore l'étape actuelle et passe à la **suivante**.
- **Non** : Interrompt tout le workflow (et le lancement du fichier).

## Notifications Riches (Markdown)

L'action `notify` supporte un sous-ensemble de Markdown pour une communication claire :
- `# Titre`
- `**Texte en gras**`
- `*Texte en italique*`
- `` `Extraits de code` ``
- `\\n` pour les nouvelles lignes

## Substitution de Jetons (Tokens)

Les variables suivantes sont substituées au moment de l'exécution :

| Jeton        | Valeur                            |
| ------------ | --------------------------------- |
| `{{path}}`     | Chemin absolu du fichier          |
| `{{dir}}`      | Dossier parent du fichier         |
| `{{filename}}` | Nom du fichier avec extension     |
| `{{stem}}`     | Nom du fichier sans extension     |
| `{{ext}}`      | Extension (incluant le point)     |
| `{{content}}`  | La chaîne `content` de l'étape courante (utile pour `ask`) |

---

## Migration depuis les Hooks INI/Hérités

Le nouveau moteur de workflow remplace l'ancienne section INI `[HOOKS]`. Les chaînes de hooks existantes
doivent être converties vers la structure YAML par étapes.

**Ancien INI :**
```ini
[HOOKS]
.mttl = before|echo "{path}" , instead|special_run {path}
```

**Nouveau YAML :**
```yaml
hooks:
  entries:
    ".mttl":
      - action: run
        content: "echo {{path}}"
      - action: replace
        content: "special_run {{path}}"
```

## Sémantique du Failmode

`launch_hook_failmode` régit les sorties non nulles pour les étapes de workflow.

- **warn**: Avertit l'utilisateur pendant l'exécution, mais passe à l'étape suivante.
- **abort**: Annule l'exécution du workflow et arrête les opérations de fichier ultérieures.
- **continue**: Supprime les erreurs et avance avec les étapes du workflow.

## Comportement du Délai d'Attente (Timeout)

`launch_hook_timeout` (par défaut 30 s) s'applique aux étapes bloquantes. Un délai d'attente de commande compte comme une sortie non nulle et déclenche le mode d'échec configuré (`on_failure` / `failmode`).

## Dépannage

1. **Le Hook ne s'exécute jamais** – spécificité glob ou incohérence. Le moteur attribue automatiquement un score plus élevé aux motifs comme `special.mttl` qu'à `*.mttl`.
2. **L'espace réservé de la variable reste littéral** – vérifiez l'orthographe. Les variables sont développées à l'exécution (ex: `{{filename}}`, `{{path}}`).
3. **Le dialogue de notification ne s'affiche pas** – en mode sans tête ou si Tkinter est manquant, le moteur imprime automatiquement le texte de la notification sur la sortie standard à la place.

---

_Document généré le 06-08-2026._

---

_Fin de référence._
