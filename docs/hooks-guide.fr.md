# Workflows de Lancement — Référence

> 🏠 **[Accueil Documentation](./README.md)** |
> 📦 **[Installation](./installation-guide.fr.md)** |
> ⚙️ **[Configuration](./configuration-profile.fr.md)** |
> 🔧 **Workflows** |
> 📊 **[Colonnes Dynamiques](./dynamic-columns-guide.md)** |
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
        content: "# Lancement de {filename}\\nPréparation de l'environnement..."
      - action: run
        content: "prepare_env.exe --file {path}"
        ask: "Exécuter le script de préparation ?"
      - action: replace
        content: "special_launcher.exe {path}"
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
| `{path}`     | Chemin absolu du fichier          |
| `{dir}`      | Dossier parent du fichier         |
| `{filename}` | Nom du fichier avec extension     |
| `{stem}`     | Nom du fichier sans extension     |
| `{ext}`      | Extension (incluant le point)     |

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
        content: "echo {path}"
      - action: replace
        content: "special_run {path}"
