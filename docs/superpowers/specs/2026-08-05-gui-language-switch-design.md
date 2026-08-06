# GUI Language Switch — Design

**Date:** 2026-08-05
**Status:** Approved

## Goal

Let the user switch the ProFiles GUI between English and French. The active
language is a `[LAUNCHER]` key in the `.profiles` file, and it is switched live
(no restart) from a status-bar button next to the theme button — the same
interaction model as the existing theme toggle.

## Decisions (confirmed with user)

| Decision | Value |
|---|---|
| Scope of translated strings | **GUI chrome only** — buttons, menus, status labels, tooltips, dialog chrome. Logs, error dialogs, and internal exception messages stay English. |
| Default when `.profiles` has no `language` key | **English** (`"en"`) |
| Apply behavior | **Apply immediately + persist** — toggle relabels the whole GUI in place, writes `[LAUNCHER] language` to `.profiles` |
| Storage of translations | **Plain dicts** in a new `src/profiles/gui/i18n.py` module, loaded in-process. No JSON files, no `gettext`. |
| New config key name | **`language`** (lowercase, like `theme`) |
| Switch UX | **Cycle EN ↔ FR** button (`🌐 EN` / `🌐 FR`), placed immediately left of the theme button |
| Accepted language values | Only `en` and `fr`; anything else coerces to `en` (never an error) |
| Cycle order | `en → fr → en` |
| Brand strings | Window title and byline (`ProFiles`, `By Florent ALBANY - v…`) stay untranslated |
| Dynamic status label | Translate only fixed tokens (`Scanning…`, `Directory not found`); leave dynamic path text alone |

## Architecture

### Configuration model

- Add `language: str = "en"` to `AppConfig` in
  `src/profiles/core/config/models.py`, placed next to `theme: str = "light"`.
- `src/profiles/core/config/reader.py` `_load_launcher_section` parses
  `parser.get("LAUNCHER", "LANGUAGE", fallback=config.language)`, then coerces
  through `normalize_language()` → `{en, fr}`, anything else → `en`.
- Persist with the existing `save_config_str(path, "LAUNCHER", "language", value)`.
  No new writer helper.
- `src/profiles/core/config/template.py`: add a commented
  `; language = en` line under the `[LAUNCHER]` documentation block plus one
  doc line, mirroring the existing `theme` entry.

### Translation catalog — `src/profiles/gui/i18n.py` (new)

Public API:

- `STRINGS: dict[str, dict[str, str]]` — `en` and `fr` dictionaries.
- `SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "fr")`
- `LANGUAGE_LABELS: dict[str, str] = {"en": "\U0001f310 EN", "fr": "\U0001f310 FR"}`
- `current_language() -> str` — the active in-process language (default `"en"`).
- `normalize_language(value: str) -> str` — coerce to `{en, fr}`; unknown → `en`.
- `t(key: str, lang: str | None = None) -> str` — look up `STRINGS[lang][key]`;
  falls back to the English value, then to the raw key. Uses
  `current_language()` when `lang` is `None`.
- Live re-label registry:
  - `register(fn: Callable[[str], None])` — idempotent per callable (replacement).
  - `set_language(lang: str)` — sets `current_language()` and calls each registered
    callback in order with the new language.

Catalog keys and values (the complete set of translated strings):

| key | EN | FR |
|---|---|---|
| `title.tooltip` | `ProFiles — Production Test Program Launcher` | `ProFiles — Lanceur de programmes de test` |
| `search.dir_label` | `Directory:` | `Répertoire :` |
| `search.dir.tooltip` | `Select or type a directory path` | `Saisir ou choisir un répertoire` |
| `search.browse` | `📁 Browse` | `📁 Parcourir` |
| `search.browse.tooltip` | `Browse for a directory` | `Parcourir les répertoires` |
| `search.recursive` | `Recursive` | `Récursif` |
| `search.recursive.tooltip` | `Search files in subdirectories recursively` | `Rechercher dans les sous-répertoires` |
| `search.search_btn` | `🔍 Search` | `🔍 Rechercher` |
| `search.search_btn.tooltip` | `Scan the selected directory` | `Scanner le répertoire sélectionné` |
| `search.ext_label` | `Extension:` | `Extension :` |
| `search.ext.tooltip` | `Filter by extension with operators: AND (space), OR, NOT (-), exact ("...")` | `Filtrer par extension : AND (espace), OR, NOT (-), exact ("...")` |
| `search.filter_label` | `Filter:` | `Filtre :` |
| `search.filter.tooltip` | `Filter with operators: AND (space), OR, NOT (-), exact ("...")` | `Filtrer : AND (espace), OR, NOT (-), exact ("...")` |
| `status.config` | `⚙ Config` | `⚙ Config` |
| `status.config.tooltip` | `Open configuration file` | `Ouvrir le fichier de configuration` |
| `status.refresh` | `🔄 Refresh` | `🔄 Actualiser` |
| `status.refresh.tooltip` | `Reload configuration and refresh file list` | `Recharger la configuration et la liste` |
| `status.log` | `📄 Log` | `📄 Journal` |
| `status.log.tooltip` | `Open log file` | `Ouvrir le journal` |
| `status.shortcuts` | `⌨ Shortcuts` | `⌨ Raccourcis` |
| `status.shortcuts.tooltip` | `Show keyboard shortcuts (?)` | `Afficher les raccourcis clavier (?)` |
| `status.language.tooltip` | `Switch GUI language` | `Changer la langue de l'interface` |
| `status.theme.tooltip` | `Toggle between light and dark theme` | `Basculer entre thème clair et sombre` |
| `status.user` | `User:` | `Utilisateur :` |
| `status.user.tooltip` | `Current Windows username` | `Nom d'utilisateur Windows` |
| `status.host` | `Host:` | `Hôte :` |
| `status.host.tooltip` | `Current machine hostname` | `Nom de la machine` |
| `status.ip` | `IP:` | `IP :` |
| `status.ip.tooltip` | `Current machine IP address` | `Adresse IP de la machine` |
| `status.count` | `Files:` | `Fichiers :` |
| `status.count.tooltip` | `Number of files matching current filters` | `Nombre de fichiers correspondant aux filtres` |
| `status.dir_status.tooltip` | `Current directory and scan status` | `Répertoire courant et état du scan` |
| `action.close_after` | `Close after execution` | `Fermer après exécution` |
| `action.close_after.tooltip` | `Close ProFiles after launching a file` | `Fermer ProFiles après le lancement` |
| `action.execute` | `▶ Execute` | `▶ Exécuter` |
| `action.execute.empty` | `▶ Execute (select a file first)` | `▶ Exécuter (sélectionnez un fichier)` |
| `action.execute.no_match` | `▶ Execute (no matching file)` | `▶ Exécuter (aucun fichier)` |
| `shortcuts.title` | `Keyboard Shortcuts` | `Raccourcis clavier` |
| `shortcuts.close` | `Close` | `Fermer` |
| `menu.refresh` | `Refresh` | `Actualiser` |
| `menu.config` | `Open .profiles` | `Ouvrir .profiles` |
| `menu.log` | `Open log file` | `Ouvrir le journal` |
| `menu.shortcuts` | `Keyboard shortcuts` | `Raccourcis clavier` |
| `menu.exit` | `Exit` | `Quitter` |
| `menu.launch` | `Launch` | `Lancer` |
| `menu.launch_args` | `Launch with arguments…` | `Lancer avec des arguments…` |
| `menu.reveal` | `Reveal in file explorer` | `Ouvrir dans l'explorateur` |
| `menu.open_folder` | `Open containing folder` | `Ouvrir le dossier contenant` |
| `menu.terminal` | `Open terminal here` | `Ouvrir le terminal ici` |
| `menu.filter_folder` | `Filter list to this folder` | `Filtrer la liste sur ce dossier` |
| `menu.filter_extension` | `Filter list by this extension` | `Filtrer la liste par cette extension` |
| `menu.copy` | `Copy` | `Copier` |
| `menu.copy.full` | `Full file path` | `Chemin complet du fichier` |
| `menu.copy.forward` | `File path (forward slashes)` | `Chemin (slash)` |
| `menu.copy.name_w_ext` | `File name with extension` | `Nom avec extension` |
| `menu.copy.name_wo_ext` | `File name without extension` | `Nom sans extension` |
| `menu.copy.directory` | `Directory path` | `Chemin du répertoire` |
| `menu.copy.uri` | `Copy as URI` | `Copier comme URI` |
| `menu.hash` | `Hash` | `Empreinte` |
| `menu.hash.md5` | `MD5` | `MD5` |
| `menu.hash.sha256` | `SHA-256` | `SHA-256` |
| `menu.hash.copy_md5` | `Copy MD5` | `Copier le MD5` |
| `menu.hash.copy_sha256` | `Copy SHA-256` | `Copier le SHA-256` |
| `menu.hash.verify_md5` | `Verify MD5 against clipboard` | `Vérifier le MD5 dans le presse-papiers` |
| `menu.hash.verify_sha256` | `Verify SHA-256 against clipboard` | `Vérifier le SHA-256 dans le presse-papiers` |
| `count_patterns.scanning` | `Scanning...` | `Scan en cours...` |
| `count_patterns.dir_not_found` | `Directory not found` | `Répertoire introuvable` |
| `count_patterns.scan_failed` | `Scan failed` | `Échec du scan` |

> The final `menu.*` and `count_patterns.*` keys are refinements to the initial
> proposal that surfaced when the real `context_menu.py` and `main_window.py`
> strings were read. They are part of the approved "GUI chrome only" scope.

### GUI wiring

**`StatusBar`** (`src/profiles/gui/status_bar.py`):
- New constructor param `on_language_toggle: Callable[[], None]`.
- Build `_lang_btn` immediately before `_theme_btn` (left of it), label from
  `LANGUAGE_LABELS`, command `on_language_toggle`, tooltip `status.language.tooltip`.
- New `update_language_label(text: str)` and `update_theme_label` already exists.
- Translate the `User:`, `Host:`, `IP:` prefix labels and all status tooltips via a
  `_apply_text(lang)` registered once (see `MainWindow`).

**`MainWindowUI._build_status_bar`** (`src/profiles/gui/ui.py`):
- Pass `on_language_toggle=self.window._on_toggle_language`.
- Assign `self.window._lang_btn = self.window._status_bar.lang_btn`.

**`MainWindow`** (`src/profiles/gui/main_window.py`):
- `__init__`: `self._language = normalize_language(config.language)`.
- `_on_toggle_language()`: two-state cycle — `"fr" if self._language == "en" else "en"`.
- `_apply_language(lang)`:
  1. `self._language = lang`
  2. `self._status_bar.update_language_label(LANGUAGE_LABELS[lang])`
  3. `save_config_str(self._config.config_path, "LAUNCHER", "language", lang)`
  4. `i18n.set_language(lang)` — walks registered re-label callbacks.
- Registers re-label callbacks once in `__init__` after `_ui.build()`:
  - `_relabel_status_bar()`, `_relabel_search_bar()`, `_relabel_action_bar()`.
  - Each is called immediately at registration (initial labels) and re-invoked by
    `set_language` on every switch.
  - `_relabel_action_bar` on `MainWindow` (not `ui.py`) so the Execute button can
    pick the 3-state label based on current file list state.
  - `_relabel_status_bar` on `MainWindow` re-applies `_count_label` using the live
    tree count (`Files: N` vs `Fichiers : N`) and translates fixed `_dir_status_label`
    tokens.

**`SearchBar`** (`src/profiles/gui/search_bar.py`):
- Attach inline labels to attributes that currently have no refs: `_dir_label`,
  `_ext_label`, `_filter_label`.
- `_apply_text(lang)` updates all button texts and tooltips. Tooltips need a
  `ToolTip.set_text()` (below) so refs to `ToolTip` objects are kept.
- Keep: title `ProFiles — {config.title}` and byline `By Florent ALBANY - v{version}`
  untranslated.

**`ToolTip`** (`src/profiles/gui/styles.py`):
- Add `set_text(text: str)` that updates the tooltip label text.

**`FileContextMenu`** (`src/profiles/gui/context_menu.py`):
- Every `menu.add_command(label=...)` / `add_cascade(label=...)` routes through
  `t("menu.X")`. The context menu is rebuilt on every right-click, so it reads
  `current_language()` at call time; no live re-label needed.

**Shortcuts dialog** (`main_window.py._on_show_shortcuts`):
- Dialog title → `t("shortcuts.title")`, Close button → `t("shortcuts.close")`.

### Data flow

1. `MainWindow.__init__` reads `config.language`, normalizes, builds UI.
2. Widgets register re-label callbacks; each callback is run once at registration.
3. User clicks `🌐 EN` → `_on_toggle_language` → `_apply_language("fr")`.
4. `_apply_language` updates in-process state, persists to `.profiles`, and calls
   `set_language("fr")` which re-runs every registered callback.
5. Layout is untouched — only widget `text` and `ToolTip` text change.

### Error handling / failure modes

- Unknown `language` value in `.profiles` → silent `en`, never an error.
- `save_config_str` failure (read-only file, disk full) → language switches in
  memory but is not persisted. Same accepted risk as the existing theme toggle.
- Missing catalog key → `t()` falls back to English value, then to the raw key.

## Testing

New `tests/gui/test_i18n.py`:
- `normalize_language` known / unknown / empty.
- `t` lookup for `en` and `fr`.
- `t` missing key → English fallback → raw key.
- `set_language` walks registry in order; `register` is idempotent.

Additions to existing test files (fakes `Tk` with `Mock()` like current GUI tests):
- `tests/gui/test_status_bar.py`: language button built; `update_language_label`
  refreshes text.
- `tests/gui/test_main_window.py`: toggle persists `[LAUNCHER]language = fr`;
  toggle re-labels widgets (`_search_btn` text, `_count_label` prefix);
  shortcuts dialog re-translates on re-open.
- `tests/core/config/test_reader.py`: parses `language = FR` → `fr`;
  `language = de` → `en`.

No new test framework, no new fixtures.

## Documentation

- `docs/configuration-profile.en.md` + `.fr.md`: append a `### Language`
  subsection under `[LAUNCHER]` with a table row matching the `theme` row.
- `README.md`: one-line note in Configuration/Features about the `language` key and
  the status-bar 🌐 button.
- `MILESTONES.md`: one bullet under recent/in-progress additions.

## Changed files

| File | Change |
|---|---|
| `src/profiles/gui/i18n.py` | **new** — catalog + registry |
| `src/profiles/core/config/models.py` | +`language` field |
| `src/profiles/core/config/reader.py` | parse + coerce `LANGUAGE` |
| `src/profiles/core/config/template.py` | commented `; language = en` + doc line |
| `src/profiles/gui/status_bar.py` | +lang button + `update_language_label` + `_apply_text` |
| `src/profiles/gui/ui.py` | lang callback wiring |
| `src/profiles/gui/search_bar.py` | inline-label refs + `_apply_text` |
| `src/profiles/gui/main_window.py` | init, `_on_toggle_language`, `_apply_language`, `_relabel_*` |
| `src/profiles/gui/context_menu.py` | `label=` → `t("menu.X")` |
| `src/profiles/gui/styles.py` | `ToolTip.set_text()` |
| `tests/gui/test_i18n.py` | **new** |
| `tests/gui/test_status_bar.py` | +2 |
| `tests/gui/test_main_window.py` | +3 |
| `tests/core/config/test_reader.py` | +2 |
| `docs/configuration-profile.en.md` | +subsection |
| `docs/configuration-profile.fr.md` | +subsection |
| `README.md` | +note |

## Out of scope

- Logs, error dialogs, internal exception messages (stay English).
- Tree column headers (user-owned, from `.profiles` `[COLUMN_*]`).
- `gettext` / `.po` catalogs, JSON catalogs.
- Three-language mode or `auto` OS detection.
- Window title and byline translation (brand).