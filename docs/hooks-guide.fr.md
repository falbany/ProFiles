# Hooks de Lancement — Référence

> 🏠 **[Accueil Documentation](./README.md)** |
> 📦 **[Installation](./installation-guide.fr.md)** |
> ⚙️ **[Configuration](./configuration-profile.fr.md)** |
> 🔧 **Hooks** |
> 📊 **[Colonnes Dynamiques](./dynamic-columns-guide.md)** |
> 🚀 **[Guide Avancé](./advanced/guide-avance.fr.md)**

---

Les hooks de lancement vous permettent d'exécuter des commandes arbitraires autour de chaque lancement de fichier. Le pipeline se trouve dans `src/profiles/core/environment/execution.py` et est invoqué par `launch_selected_file` dans `actions.py`. Les hooks sont configurés par extension dans la section `[HOOKS]` du fichier `.profiles`.

## Aperçu

- **Quand** – avant que l'association OS ne soit exécutée, après son retour, ou à sa place.
- **Phases** – `before`, `confirm`, `after`, `instead`, `abort`.
- **Résultat** – le pipeline retourne un `HookOutcome` (`CONTINUE`, `SKIP`, `ABORT`).
- **Portée** – les hooks s'appliquent à la clé d'extension normalisée (`.png`, `.pdf`, …).

La chaîne de caractères du hook peut omettre une phase ; la phase par défaut est `before`. Plusieurs hooks sont séparés par des virgules ; les virgules à l'intérieur de guillemets doubles sont ignorées.

## Démarrage Rapide

```ini
[HOOKS]
.mttl = before|echo "Lancement de {path}" , after|logger "Lancé : {path}"
```

- `before` affiche un message, s'interrompt en cas de code de sortie non nul selon `launch_hook_failmode`.
- `after` s'exécute de manière asynchrone après le lancement OS.

## Phases de Hook

| Phase    | Quand s'exécute-t-il                        | Gestion du code de retour                        |
| -------- | ------------------------------------------- | ------------------------------------------------ |
| before   | Immédiatement avant le lancement OS.        | `0` → continuer. non‑nul → mappé par _failmode_. |
| confirm  | Immédiatement avant les hooks `before`.     | Oui/Non utilisateur → `CONTINUE` ou `ABORT`.     |
| after    | Après un lancement OS réussi (ou `SKIP`).   | Lancé via `subprocess.Popen` ; ne bloque jamais. |
| instead  | Remplace le lancement OS.                   | `0` → `SKIP`. non‑nul → mappé par _failmode_.    |
| abort    | Force l'interruption du pipeline quoi qu'il arrive. | `0` → `CONTINUE`. non‑nul → toujours `ABORT`.    |

**Exemples**

```ini
[HOOKS]
.pdf = before|/usr/bin/evince {path} , instead|myviewer --file {path}
.exe = confirm|Exécuter ce fichier ? , before|check_safety.sh {path}
.mttl = abort|test -f {path} && echo "OK"
```

## Enchaînement de Hooks Séquentiels

Les hooks peuvent être enchaînés de sorte que chaque hook dépende du succès du précédent. Lorsqu'un hook échoue, le comportement du pipeline dépend de `launch_hook_failmode` et du niveau d'exigence du hook.

### Syntaxe

```ini
[HOOKS]
.exe = step1|validate.sh {path}, step2|backup.sh {path}, step3|launch.sh {path}
```

Chaque entrée est exécutée dans l'ordre. Par défaut, chaque hook est considéré comme "requis". Si un hook échoue (code de sortie non nul) et que `launch_hook_failmode` est réglé sur `abort`, le pipeline s'arrête immédiatement et le lancement est annulé.

### Politique d'Exécution

1. **Hook Requis** (par défaut) : S'il échoue, le pipeline obéit à `launch_hook_failmode`. Si failmode est `abort`, tout le lancement est annulé.
2. **Dépendance Séquentielle** : Si un hook échoue et entraîne un résultat `ABORT`, les hooks suivants dans la liste sont ignorés.

## Hooks de Confirmation

Les hooks de confirmation mettent le pipeline en pause et attendent l'approbation de l'utilisateur avant de continuer. Ils fonctionnent à la fois en mode GUI et en mode console (headless).

### Syntaxe

```ini
[HOOKS]
.exe = confirm|⚠️ Exécuter {name} ? , before|run.sh {path}
```

### Comportement

- **Mode GUI** : Affiche une boîte de dialogue Oui/Non.
- **Mode Console** : Invite l'utilisateur dans le terminal (ex: `Confirmation: ⚠️ Exécuter file.txt ? [y/N]: `).
- **Oui** : Le pipeline continue vers le hook suivant.
- **No / Annuler** : Le pipeline se résout en `ABORT`, et le lancement est annulé.

Les hooks de confirmation sont toujours synchrones et s'exécutent généralement avant toute autre logique pour s'assurer que l'utilisateur est conscient de l'action imminente.

## Substitution de Jetons (Tokens)

Le moteur de template remplace les jetons suivants avant que la commande ne soit découpée :

| Jeton        | Valeur                            |
| ------------ | --------------------------------- |
| `{path}`     | Chemin absolu du fichier          |
| `{dir}`      | Dossier parent du fichier         |
| `{name}`     | Nom du fichier avec extension     |
| `{cwd}`      | Dossier de travail actuel         |
| `{ext}`      | Extension (incluant le point)     |
| `{date}`     | Date ISO‑8601 (ex: `2026-07-31`)  |
| `{hostname}` | Nom d'hôte de la machine locale   |

Les jetons inconnus restent inchangés.

## Sémantique du Mode d'Échec (Failmode)

`launch_hook_failmode` régit les sorties non nulles (y compris les délais d'attente) pour les phases *bloquantes*.

| Failmode | Phase   | Code retour `0` | Code retour != `0` | `HookOutcome` résultant     |
| -------- | ------- | --------------- | ------------------ | --------------------------- |
| warn     | before  | continuer       | avertissement + continuer | `CONTINUE`                  |
| warn     | instead | ignorer         | avertissement + continuer | `CONTINUE` (le lancement OS s'exécute) |
| abort    | before  | continuer       | interruption + échec | `ABORT`                     |
| abort    | instead | ignorer         | interruption + échec | `ABORT`                     |
| skip     | before  | continuer       | ignorer + succès    | `SKIP`                      |
| skip     | instead | ignorer         | ignorer + échec      | `SKIP`                      |

*La phase `abort` produit toujours `ABORT` quel que soit le mode d'échec.*

## Comportement en cas de Délai d'Attente (Timeout)

`launch_hook_timeout` (par défaut 30 s) s'applique aux hooks `before`, `instead` et `abort`. Un `subprocess.TimeoutExpired` est converti en `TimeoutError` puis traité comme une sortie non nulle – le mode d'échec configuré décide du résultat.

## Hooks `after` Asynchrones

Les hooks `after` sont lancés via `subprocess.Popen`. Les flux de sortie sont redirigés vers `DEVNULL`. Les erreurs telles que `FileNotFoundError` sont supprimées – un hook mal configuré ne fait jamais planter l'appelant.
