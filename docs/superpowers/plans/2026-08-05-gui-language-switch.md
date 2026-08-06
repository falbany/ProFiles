# GUI Language Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user switch the ProFiles GUI between English and French. The active language is stored under `[LAUNCHER] language` in `.profiles` and toggled live from a status-bar button next to the theme button — same interaction model as the existing theme toggle.

**Architecture:** New `profiles.gui.i18n` module owns the catalog and a small re-label callback registry. `AppConfig` gains a `language` field. The reader parses `[LAUNCHER].LANGUAGE` and coerces to `{en, fr}`. `StatusBar` gets a `🌐 EN` / `🌐 FR` cycle button left of the theme button. `MainWindow._apply_language()` updates state, persists, and walks the registry. `SearchBar`, `StatusBar`, the action bar, the shortcuts dialog, and the context menu read translations through `t()`. Layout never changes — only widget text and `ToolTip` text.

**Tech Stack:** Python 3.11+, Tkinter/ttk (existing), pytest (existing), `configparser` (existing), `unittest.mock` (existing).

## Global Constraints

- Test framework: **pytest** (existing); no new fixtures beyond `tmp_path` and existing `tests/conftest.py`.
- Default language when `.profiles` has no `language` key: **`en`** (English).
- Only **two** supported values: `en` and `fr`. Anything else coerces to `en` (never raises).
- Cycle order: **`en → fr → en`** (2-state).
- Persisted via the existing `save_config_str(path, "LAUNCHER", "language", value)` helper — no new writer.
- The new `[LAUNCHER]` config key name is **`language`** (lowercase, like `theme`).
- Brand strings (window title `ProFiles`, byline `By Florent ALBANY - v…`) **stay untranslated**.
- Dynamic values inside `_dir_status_label` (e.g. `Directory: <path>`, `No matching files found`) stay in their existing English form; only the three fixed tokens (`Scanning...`, `Directory not found`, `Scan failed`) get translated.
- Tree column headers come from `[COLUMN_*]` in `.profiles` — user-owned, **not** in the catalog.
- Every translation lookup **must** route through `profiles.gui.i18n.t(...)`. Hard-coded user-visible English strings in `gui/*.py` (except brand, status dynamic values, and column headers) are forbidden after this plan finishes.
- Existing test conventions: `Mock()` for callbacks; `tmp_path` for file-based tests; `textwrap.dedent` for INI fixtures. The existing `tests/gui/test_status_bar.py` retry pattern (Tk init up to 3 times) is reused, not rewritten.

---

## File structure (locked)

New file:
- `src/profiles/gui/i18n.py` — catalog, lookup, registry.
- `tests/gui/test_i18n.py` — pure unit tests for `i18n` (no Tk).

Modified files (single-responsibility split, no architectural rewiring):
- `src/profiles/core/config/models.py` — +`language` field.
- `src/profiles/core/config/reader.py` — parse + coerce `LANGUAGE`.
- `src/profiles/core/config/template.py` — commented `; language = en` + doc line.
- `src/profiles/gui/styles.py` — `ToolTip.set_text()`.
- `src/profiles/gui/status_bar.py` — language button + `update_language_label()` + `_apply_text()`.
- `src/profiles/gui/search_bar.py` — inline-label refs + `_apply_text()`.
- `src/profiles/gui/ui.py` — language callback wiring + action-bar relabel registration.
- `src/profiles/gui/main_window.py` — init `self._language`, `_on_toggle_language`, `_apply_language`, three `_relabel_*` methods registered in `__init__`, plus shortcuts dialog translations and dynamic status label translations.
- `src/profiles/gui/context_menu.py` — every `label=` route through `t()`.
- `tests/gui/test_status_bar.py` — +2 tests (button built, label updates).
- `tests/gui/test_main_window.py` — +3 tests (toggle persists, re-labels, shortcuts dialog re-translates).
- `tests/core/config/test_reader.py` — +2 tests (parses, defaults to `en`).
- `docs/configuration-profile.en.md` — +subsection.
- `docs/configuration-profile.fr.md` — +subsection.
- `README.md` — +one-line note.

No file in `src/profiles/core/**` is allowed to import from `src/profiles/gui/**`. The i18n module lives under `gui/` and is imported only by `gui/*` and by tests.

---

### Task 1: i18n catalog + lookup + registry (pure module, no Tk)

**Files:**
- Create: `src/profiles/gui/i18n.py`
- Test: `tests/gui/test_i18n.py`

**Interfaces (consumed by later tasks):**
- `STRINGS: dict[str, dict[str, str]]` — keys are language codes, values are `key → text`. Two top-level keys: `"en"`, `"fr"`.
- `SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "fr")`
- `LANGUAGE_LABELS: dict[str, str] = {"en": "\U0001f310 EN", "fr": "\U0001f310 FR"}`
- `current_language() -> str`
- `set_current_language(lang: str) -> None`
- `normalize_language(value: str) -> str`
- `t(key: str, lang: str | None = None) -> str`
- `register(fn: Callable[[str], None]) -> None`
- `set_language(lang: str) -> None`

**Catalog keys** (the complete set — copy verbatim from `docs/superpowers/specs/2026-08-05-gui-language-switch-design.md` § "Catalog keys and values"):

`title.tooltip`, `search.dir_label`, `search.dir.tooltip`, `search.browse`, `search.browse.tooltip`, `search.recursive`, `search.recursive.tooltip`, `search.search_btn`, `search.search_btn.tooltip`, `search.ext_label`, `search.ext.tooltip`, `search.filter_label`, `search.filter.tooltip`, `status.config`, `status.config.tooltip`, `status.refresh`, `status.refresh.tooltip`, `status.log`, `status.log.tooltip`, `status.shortcuts`, `status.shortcuts.tooltip`, `status.language.tooltip`, `status.theme.tooltip`, `status.user`, `status.user.tooltip`, `status.host`, `status.host.tooltip`, `status.ip`, `status.ip.tooltip`, `status.count`, `status.count.tooltip`, `status.dir_status.tooltip`, `action.close_after`, `action.close_after.tooltip`, `action.execute`, `action.execute.empty`, `action.execute.no_match`, `shortcuts.title`, `shortcuts.close`, `menu.refresh`, `menu.config`, `menu.log`, `menu.shortcuts`, `menu.exit`, `menu.launch`, `menu.launch_args`, `menu.reveal`, `menu.open_folder`, `menu.terminal`, `menu.filter_folder`, `menu.filter_extension`, `menu.copy`, `menu.copy.full`, `menu.copy.forward`, `menu.copy.name_w_ext`, `menu.copy.name_wo_ext`, `menu.copy.directory`, `menu.copy.uri`, `menu.hash`, `menu.hash.md5`, `menu.hash.sha256`, `menu.hash.copy_md5`, `menu.hash.copy_sha256`, `menu.hash.verify_md5`, `menu.hash.verify_sha256`, `count_patterns.scanning`, `count_patterns.dir_not_found`, `count_patterns.scan_failed`.

- [ ] **Step 1: Write failing tests**

Create `tests/gui/test_i18n.py`:

```python
"""Unit tests for the GUI i18n module (no Tk)."""

from __future__ import annotations

import pytest

from profiles.gui import i18n


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    """Each test starts with an empty registry and English language."""
    i18n._reset_for_tests()
    i18n.set_current_language("en")
    yield
    i18n._reset_for_tests()
    i18n.set_current_language("en")


def test_normalize_known_languages_case_insensitive() -> None:
    assert i18n.normalize_language("en") == "en"
    assert i18n.normalize_language("EN") == "en"
    assert i18n.normalize_language("fr") == "fr"
    assert i18n.normalize_language("FR") == "fr"
    assert i18n.normalize_language("Fr") == "fr"


def test_normalize_unknown_falls_back_to_en() -> None:
    assert i18n.normalize_language("es") == "en"
    assert i18n.normalize_language("") == "en"
    assert i18n.normalize_language("   ") == "en"


def test_t_returns_localized_string_for_explicit_lang() -> None:
    assert i18n.t("status.config", "en") == "\u2699 Config"
    assert i18n.t("status.refresh", "fr") == "\U0001f504 Actualiser"


def test_t_uses_current_language_when_lang_is_none() -> None:
    i18n.set_current_language("fr")
    assert i18n.t("status.refresh") == "\U0001f504 Actualiser"


def test_t_missing_key_returns_raw_key() -> None:
    assert i18n.t("does.not.exist", "en") == "does.not.exist"
    assert i18n.t("does.not.exist", "fr") == "does.not.exist"


def test_t_unsupported_lang_falls_back_to_english() -> None:
    assert i18n.t("status.refresh", "es") == "\U0001f504 Refresh"


def test_catalog_has_every_required_key_in_both_languages() -> None:
    required = {
        "title.tooltip", "search.dir_label", "search.dir.tooltip",
        "search.browse", "search.browse.tooltip", "search.recursive",
        "search.recursive.tooltip", "search.search_btn", "search.search_btn.tooltip",
        "search.ext_label", "search.ext.tooltip", "search.filter_label",
        "search.filter.tooltip", "status.config", "status.config.tooltip",
        "status.refresh", "status.refresh.tooltip", "status.log",
        "status.log.tooltip", "status.shortcuts", "status.shortcuts.tooltip",
        "status.language.tooltip", "status.theme.tooltip", "status.user",
        "status.user.tooltip", "status.host", "status.host.tooltip",
        "status.ip", "status.ip.tooltip", "status.count",
        "status.count.tooltip", "status.dir_status.tooltip",
        "action.close_after", "action.close_after.tooltip", "action.execute",
        "action.execute.empty", "action.execute.no_match", "shortcuts.title",
        "shortcuts.close", "menu.refresh", "menu.config", "menu.log",
        "menu.shortcuts", "menu.exit", "menu.launch", "menu.launch_args",
        "menu.reveal", "menu.open_folder", "menu.terminal",
        "menu.filter_folder", "menu.filter_extension", "menu.copy",
        "menu.copy.full", "menu.copy.forward", "menu.copy.name_w_ext",
        "menu.copy.name_wo_ext", "menu.copy.directory", "menu.copy.uri",
        "menu.hash", "menu.hash.md5", "menu.hash.sha256",
        "menu.hash.copy_md5", "menu.hash.copy_sha256",
        "menu.hash.verify_md5", "menu.hash.verify_sha256",
        "count_patterns.scanning", "count_patterns.dir_not_found",
        "count_patterns.scan_failed",
    }
    for key in required:
        assert key in i18n.STRINGS["en"], f"missing EN key: {key}"
        assert key in i18n.STRINGS["fr"], f"missing FR key: {key}"


def test_register_is_idempotent_per_callable() -> None:
    calls: list[str] = []
    fn = lambda lang: calls.append(lang)  # noqa: E731
    i18n.register(fn)
    i18n.register(fn)
    i18n.set_language("fr")
    assert calls == ["fr"]


def test_set_language_walks_registry_in_registration_order() -> None:
    order: list[int] = []
    i18n.register(lambda lang: order.append(1))
    i18n.register(lambda lang: order.append(2))
    i18n.register(lambda lang: order.append(3))
    i18n.set_language("fr")
    assert order == [1, 2, 3]


def test_set_language_persists_current_language() -> None:
    i18n.set_language("fr")
    assert i18n.current_language() == "fr"
    i18n.set_language("en")
    assert i18n.current_language() == "en"


def test_supported_languages_is_exactly_two() -> None:
    assert i18n.SUPPORTED_LANGUAGES == ("en", "fr")


def test_language_labels_have_both_keys() -> None:
    assert set(i18n.LANGUAGE_LABELS) == {"en", "fr"}
```

- [ ] **Step 2: Run tests, confirm RED**

Run: `pytest tests/gui/test_i18n.py -v`
Expected: collection errors or import errors (module does not exist yet).

- [ ] **Step 3: Implement `src/profiles/gui/i18n.py`**

```python
"""GUI i18n catalog and live re-label registry.

Single Responsibility: own the English/French translation strings and
expose a small callback registry that GUI widgets register with so a
language switch re-labels the whole window without rebuilding it.

Scope of translations (per design doc): GUI chrome only — buttons,
menus, status labels, tooltips, dialog chrome. Logs, error dialogs, and
internal exception messages stay English.
"""

from __future__ import annotations

from typing import Callable

SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "fr")

LANGUAGE_LABELS: dict[str, str] = {
    "en": "\U0001f310 EN",
    "fr": "\U0001f310 FR",
}

# The full catalog. Every key that appears here must also exist in EN
# (so a missing key always has a fallback). Any new translatable string
# must be added in BOTH languages in the same commit.
STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "title.tooltip": "ProFiles — Production Test Program Launcher",
        "search.dir_label": "Directory:",
        "search.dir.tooltip": "Select or type a directory path",
        "search.browse": "\U0001f4c1 Browse",
        "search.browse.tooltip": "Browse for a directory",
        "search.recursive": "Recursive",
        "search.recursive.tooltip": "Search files in subdirectories recursively",
        "search.search_btn": "\U0001f50d Search",
        "search.search_btn.tooltip": "Scan the selected directory",
        "search.ext_label": "Extension:",
        "search.ext.tooltip": 'Filter by extension with operators: AND (space), OR, NOT (-), exact ("...")',
        "search.filter_label": "Filter:",
        "search.filter.tooltip": 'Filter with operators: AND (space), OR, NOT (-), exact ("...")',
        "status.config": "\u2699 Config",
        "status.config.tooltip": "Open configuration file",
        "status.refresh": "\U0001f504 Refresh",
        "status.refresh.tooltip": "Reload configuration and refresh file list",
        "status.log": "\U0001f4c4 Log",
        "status.log.tooltip": "Open log file",
        "status.shortcuts": "\u2328 Shortcuts",
        "status.shortcuts.tooltip": "Show keyboard shortcuts (?)",
        "status.language.tooltip": "Switch GUI language",
        "status.theme.tooltip": "Toggle between light and dark theme",
        "status.user": "User:",
        "status.user.tooltip": "Current Windows username",
        "status.host": "Host:",
        "status.host.tooltip": "Current machine hostname",
        "status.ip": "IP:",
        "status.ip.tooltip": "Current machine IP address",
        "status.count": "Files:",
        "status.count.tooltip": "Number of files matching current filters",
        "status.dir_status.tooltip": "Current directory and scan status",
        "action.close_after": "Close after execution",
        "action.close_after.tooltip": "Close ProFiles after launching a file",
        "action.execute": "\u25b6 Execute",
        "action.execute.empty": "\u25b6 Execute (select a file first)",
        "action.execute.no_match": "\u25b6 Execute (no matching file)",
        "shortcuts.title": "Keyboard Shortcuts",
        "shortcuts.close": "Close",
        "menu.refresh": "Refresh",
        "menu.config": "Open .profiles",
        "menu.log": "Open log file",
        "menu.shortcuts": "Keyboard shortcuts",
        "menu.exit": "Exit",
        "menu.launch": "Launch",
        "menu.launch_args": "Launch with arguments…",
        "menu.reveal": "Reveal in file explorer",
        "menu.open_folder": "Open containing folder",
        "menu.terminal": "Open terminal here",
        "menu.filter_folder": "Filter list to this folder",
        "menu.filter_extension": "Filter list by this extension",
        "menu.copy": "Copy",
        "menu.copy.full": "Full file path",
        "menu.copy.forward": "File path (forward slashes)",
        "menu.copy.name_w_ext": "File name with extension",
        "menu.copy.name_wo_ext": "File name without extension",
        "menu.copy.directory": "Directory path",
        "menu.copy.uri": "Copy as URI",
        "menu.hash": "Hash",
        "menu.hash.md5": "MD5",
        "menu.hash.sha256": "SHA-256",
        "menu.hash.copy_md5": "Copy MD5",
        "menu.hash.copy_sha256": "Copy SHA-256",
        "menu.hash.verify_md5": "Verify MD5 against clipboard",
        "menu.hash.verify_sha256": "Verify SHA-256 against clipboard",
        "count_patterns.scanning": "Scanning...",
        "count_patterns.dir_not_found": "Directory not found",
        "count_patterns.scan_failed": "Scan failed",
    },
    "fr": {
        "title.tooltip": "ProFiles — Lanceur de programmes de test",
        "search.dir_label": "Répertoire :",
        "search.dir.tooltip": "Saisir ou choisir un répertoire",
        "search.browse": "\U0001f4c1 Parcourir",
        "search.browse.tooltip": "Parcourir les répertoires",
        "search.recursive": "Récursif",
        "search.recursive.tooltip": "Rechercher dans les sous-répertoires",
        "search.search_btn": "\U0001f50d Rechercher",
        "search.search_btn.tooltip": "Scanner le répertoire sélectionné",
        "search.ext_label": "Extension :",
        "search.ext.tooltip": "Filtrer par extension : AND (espace), OR, NOT (-), exact (\"...\")",
        "search.filter_label": "Filtre :",
        "search.filter.tooltip": "Filtrer : AND (espace), OR, NOT (-), exact (\"...\")",
        "status.config": "\u2699 Config",
        "status.config.tooltip": "Ouvrir le fichier de configuration",
        "status.refresh": "\U0001f504 Actualiser",
        "status.refresh.tooltip": "Recharger la configuration et la liste",
        "status.log": "\U0001f4c4 Journal",
        "status.log.tooltip": "Ouvrir le journal",
        "status.shortcuts": "\u2328 Raccourcis",
        "status.shortcuts.tooltip": "Afficher les raccourcis clavier (?)",
        "status.language.tooltip": "Changer la langue de l'interface",
        "status.theme.tooltip": "Basculer entre thème clair et sombre",
        "status.user": "Utilisateur :",
        "status.user.tooltip": "Nom d'utilisateur Windows",
        "status.host": "Hôte :",
        "status.host.tooltip": "Nom de la machine",
        "status.ip": "IP :",
        "status.ip.tooltip": "Adresse IP de la machine",
        "status.count": "Fichiers :",
        "status.count.tooltip": "Nombre de fichiers correspondant aux filtres",
        "status.dir_status.tooltip": "Répertoire courant et état du scan",
        "action.close_after": "Fermer après exécution",
        "action.close_after.tooltip": "Fermer ProFiles après le lancement",
        "action.execute": "\u25b6 Exécuter",
        "action.execute.empty": "\u25b6 Exécuter (sélectionnez un fichier)",
        "action.execute.no_match": "\u25b6 Exécuter (aucun fichier)",
        "shortcuts.title": "Raccourcis clavier",
        "shortcuts.close": "Fermer",
        "menu.refresh": "Actualiser",
        "menu.config": "Ouvrir .profiles",
        "menu.log": "Ouvrir le journal",
        "menu.shortcuts": "Raccourcis clavier",
        "menu.exit": "Quitter",
        "menu.launch": "Lancer",
        "menu.launch_args": "Lancer avec des arguments…",
        "menu.reveal": "Ouvrir dans l'explorateur",
        "menu.open_folder": "Ouvrir le dossier contenant",
        "menu.terminal": "Ouvrir le terminal ici",
        "menu.filter_folder": "Filtrer la liste sur ce dossier",
        "menu.filter_extension": "Filtrer la liste par cette extension",
        "menu.copy": "Copier",
        "menu.copy.full": "Chemin complet du fichier",
        "menu.copy.forward": "Chemin (slash)",
        "menu.copy.name_w_ext": "Nom avec extension",
        "menu.copy.name_wo_ext": "Nom sans extension",
        "menu.copy.directory": "Chemin du répertoire",
        "menu.copy.uri": "Copier comme URI",
        "menu.hash": "Empreinte",
        "menu.hash.md5": "MD5",
        "menu.hash.sha256": "SHA-256",
        "menu.hash.copy_md5": "Copier le MD5",
        "menu.hash.copy_sha256": "Copier le SHA-256",
        "menu.hash.verify_md5": "Vérifier le MD5 dans le presse-papiers",
        "menu.hash.verify_sha256": "Vérifier le SHA-256 dans le presse-papiers",
        "count_patterns.scanning": "Scan en cours...",
        "count_patterns.dir_not_found": "Répertoire introuvable",
        "count_patterns.scan_failed": "Échec du scan",
    },
}

# --- Module-private state ------------------------------------------------

_current_language: str = "en"
_relabel_registry: list[Callable[[str], None]] = []


def current_language() -> str:
    """Return the active in-process language code (default ``"en"``)."""
    return _current_language


def set_current_language(lang: str) -> None:
    """Set the active language without notifying the registry.

    Use :func:`set_language` for the normal "switch and re-label" flow.
    """
    global _current_language
    _current_language = normalize_language(lang)


def normalize_language(value: str) -> str:
    """Coerce *value* to a supported language code.

    Empty strings and unsupported codes fall back to ``"en"``.
    Case-insensitive.
    """
    if not value:
        return "en"
    candidate = value.strip().lower()
    if candidate in SUPPORTED_LANGUAGES:
        return candidate
    return "en"


def t(key: str, lang: str | None = None) -> str:
    """Look up *key* for *lang* (defaults to :func:`current_language`).

    Fallback order: requested language → English → raw key.
    """
    effective = normalize_language(lang) if lang is not None else _current_language
    table = STRINGS.get(effective, STRINGS["en"])
    if key in table:
        return table[key]
    en_table = STRINGS["en"]
    if key in en_table:
        return en_table[key]
    return key


def register(fn: Callable[[str], None]) -> None:
    """Register a re-label callback. Idempotent per callable.

    Re-registering the same ``fn`` replaces (does not duplicate) the
    existing entry. Order of first registration is preserved.
    """
    if fn in _relabel_registry:
        return
    _relabel_registry.append(fn)


def set_language(lang: str) -> None:
    """Set the active language and notify every registered callback.

    The active language is updated first; then each registered callback
    is invoked in registration order with the new language.
    """
    new_lang = normalize_language(lang)
    global _current_language
    _current_language = new_lang
    for fn in _relabel_registry:
        fn(new_lang)


def _reset_for_tests() -> None:
    """Clear the registry. Test-only — not part of the public API."""
    _relabel_registry.clear()


__all__ = [
    "LANGUAGE_LABELS",
    "STRINGS",
    "SUPPORTED_LANGUAGES",
    "current_language",
    "normalize_language",
    "register",
    "set_current_language",
    "set_language",
    "t",
]
```

- [ ] **Step 4: Run tests, confirm GREEN**

Run: `pytest tests/gui/test_i18n.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/profiles/gui/i18n.py tests/gui/test_i18n.py
git commit -m "feat(i18n): add GUI language catalog and live re-label registry"
```

---

### Task 2: `AppConfig.language` field + reader parse + template doc

**Files:**
- Modify: `src/profiles/core/config/models.py` (add `language` field)
- Modify: `src/profiles/core/config/reader.py` (parse + coerce)
- Modify: `src/profiles/core/config/template.py` (comment + doc line)
- Test: `tests/core/config/test_reader.py`

**Interfaces consumed:**
- `i18n.normalize_language(value)` — imported by `reader.py`.

**Interfaces produced:**
- `AppConfig.language: str = "en"` — default English.
- `ConfigReader.load()` parses `LAUNCHER.LANGUAGE` (any case) and stores the
  coerced value (`"en"` or `"fr"`) on `AppConfig.language`.

- [ ] **Step 1: Write failing tests in `tests/core/config/test_reader.py`**

Append inside `class TestLoad`:

```python
    def test_language_parses_french(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text("[LAUNCHER]\nlanguage=FR\n", encoding="utf-8")
        config = ConfigReader(conf).load()
        assert config.language == "fr"

    def test_language_unknown_falls_back_to_en(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text("[LAUNCHER]\nlanguage=de\n", encoding="utf-8")
        config = ConfigReader(conf).load()
        assert config.language == "en"

    def test_language_missing_defaults_to_en(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text("[LAUNCHER]\ntheme=dark\n", encoding="utf-8")
        config = ConfigReader(conf).load()
        assert config.language == "en"
```

Also append a section testing that the default language is English on a brand-new `AppConfig`:

```python
    def test_default_language_is_english(self, tmp_path: Path) -> None:
        reader = ConfigReader(tmp_path / "missing.profiles")
        config = reader.load()
        assert config.language == "en"
```

- [ ] **Step 2: Run tests, confirm RED**

Run: `pytest tests/core/config/test_reader.py -k language -v`
Expected: `AttributeError: type object 'AppConfig' has no attribute 'language'`.

- [ ] **Step 3: Add `language` field to `AppConfig`**

In `src/profiles/core/config/models.py`, inside `AppConfig`, immediately after the existing `theme: str = "light"` line, add:

```python
        language: str = "en"
```

- [ ] **Step 4: Parse + coerce `LANGUAGE` in `reader.py`**

In `src/profiles/core/config/reader.py` at the top, add an import:

```python
from profiles.gui import i18n
```

(Cycle check: `profiles.core.config.reader` already imports nothing from `gui` today. The gui dependency is acceptable here because the reader historically does no GUI work — but if you'd rather avoid the cross-layer import, declare a local helper `_normalize_lang` in `reader.py` that mirrors `i18n.normalize_language`. **Use the local helper.** This keeps the core layer GUI-free per the architecture guide. Both helpers must remain functionally identical; the unit test for `normalize_language` in `tests/gui/test_i18n.py` already pins the behaviour.)

Add at module top of `reader.py`:

```python
def _normalize_lang(value: str) -> str:
    """Mirror of profiles.gui.i18n.normalize_language; kept local to avoid
    a core→gui import. Behaviour pinned by tests/gui/test_i18n.py.
    """
    if not value:
        return "en"
    candidate = value.strip().lower()
    return candidate if candidate in {"en", "fr"} else "en"
```

In `_load_launcher_section`, immediately after the existing
`config.theme = parser.get("LAUNCHER", "theme", fallback=config.theme)` line, add:

```python
        raw_lang = parser.get("LAUNCHER", "LANGUAGE", fallback=config.language)
        config.language = _normalize_lang(raw_lang)
```

- [ ] **Step 5: Document `language` in starter template**

In `src/profiles/core/config/template.py`, find the `[LAUNCHER]` doc paragraph
for `theme` and add a parallel paragraph immediately above or below it for
`language`. The exact format mirrors the `theme` line:

Find the line that documents `theme` (it begins `;   theme               enum          default "light"`). Insert directly after that line:

```
;   language            enum          default "en"      "en" (English) or "fr" (French)
;                                                   Toggle the GUI language from the status-bar
;                                                   🌐 button or by editing this key.
```

Then locate the actual `[LAUNCHER]` section body in the template (the part
that writes real config values, after the doc comment block). It currently
contains lines like `gui_auto_launch = Vrai`, `close_after_execute = Faux`,
`theme = light`, etc. **Do not** add an active `language = en` line there —
leave it commented-out in the doc block only, so the starter still ships
with English by default and we don't risk conflicting with the user's
existing `[LAUNCHER]` section. The commented doc line is sufficient.

- [ ] **Step 6: Run reader tests, confirm GREEN**

Run: `pytest tests/core/config/test_reader.py -v`
Expected: all tests pass, including the new 4 language tests.

- [ ] **Step 7: Commit**

```bash
git add src/profiles/core/config/models.py src/profiles/core/config/reader.py src/profiles/core/config/template.py tests/core/config/test_reader.py
git commit -m "feat(config): add LANGUAGE key with en/fr coercion"
```

---

### Task 3: `ToolTip.set_text()`

**Files:**
- Modify: `src/profiles/gui/styles.py`
- Test: existing tests in `tests/gui/test_styles.py` (add 1 test).

**Interfaces produced:**
- `ToolTip.set_text(text: str) -> None` — replaces the tooltip text; if the
  tooltip is currently visible, hides it (next hover will show the new text).

- [ ] **Step 1: Write failing test**

In `tests/gui/test_styles.py`, find the `TestToolTip` class (or create one if absent). Append:

```python
    def test_set_text_changes_shown_text(self) -> None:
        """ToolTip.set_text() updates the stored text for next show."""
        import tkinter as tk
        from tkinter import ttk
        from profiles.gui.styles import ToolTip

        root = tk.Tk(); root.withdraw()
        try:
            btn = ttk.Button(root, text="x")
            tt = ToolTip(btn, "old text")
            tt.set_text("nouveau texte")
            assert tt._text == "nouveau texte"
        finally:
            root.destroy()
```

- [ ] **Step 2: Run test, confirm RED**

Run: `pytest tests/gui/test_styles.py -v`
Expected: `AttributeError: 'ToolTip' object has no attribute 'set_text'`.

- [ ] **Step 3: Implement `ToolTip.set_text()`**

In `src/profiles/gui/styles.py`, inside `class ToolTip`, append after `__init__`:

```python
    def set_text(self, text: str) -> None:
        """Replace the tooltip text.

        If the tooltip is currently visible, hide it; the next hover
        will display the new text. Bound widgets are not touched.
        """
        self._text = text
        self._hide()
```

- [ ] **Step 4: Run test, confirm GREEN**

Run: `pytest tests/gui/test_styles.py -v`
Expected: passes.

- [ ] **Step 5: Commit**

```bash
git add src/profiles/gui/styles.py tests/gui/test_styles.py
git commit -m "feat(gui): ToolTip.set_text() for live re-label"
```

---

### Task 4: `SearchBar._apply_text()` and inline label refs

**Files:**
- Modify: `src/profiles/gui/search_bar.py`

**Interfaces produced:**
- `SearchBar._apply_text(lang: str) -> None` — updates every button label,
  every inline Label `text=`, and every ToolTip in this component.
- `SearchBar` attributes: `_dir_label`, `_ext_label`, `_filter_label`
  (created in `_build()`), `_browse_btn_tt`, `_recursive_tt`, `_search_btn_tt`,
  `_ext_tt`, `_filter_tt`, `_dir_tt`, `_title_tt`.

- [ ] **Step 1: Hold ToolTip and inline-label refs**

In `src/profiles/gui/search_bar.py`, in `_build()`:

1. Replace the bare `ttk.Label(self._dir_frame, text="Directory:", ...)` with a stored reference:
   ```python
   self._dir_label = ttk.Label(
       self._dir_frame,
       text="Directory:",
       width=9,
       anchor=tk.W,
   )
   self._dir_label.pack(side=tk.LEFT, padx=(0, 4))
   ```
2. Replace the bare `ttk.Label(self._filter_frame, text="Extension:", ...)` with:
   ```python
   self._ext_label = ttk.Label(
       self._filter_frame,
       text="Extension:",
       width=9,
       anchor=tk.W,
   )
   self._ext_label.pack(side=tk.LEFT, padx=(0, 4))
   ```
3. Replace the bare `ttk.Label(self._filter_frame, text="Filter:")` with:
   ```python
   self._filter_label = ttk.Label(self._filter_frame, text="Filter:")
   self._filter_label.pack(side=tk.LEFT, padx=(0, 4))
   ```
4. After every `ToolTip(self._xxx, "...")` call, store the returned ToolTip on
   `self` so it can be mutated. Pattern:
   ```python
   self._title_tt = ToolTip(self._title_frame, "ProFiles — Production Test Program Launcher")
   # ...
   self._dir_tt = ToolTip(self._dir_combo, "Select or type a directory path")
   # ...
   self._browse_btn_tt = ToolTip(self._browse_btn, "Browse for a directory")
   # ...
   self._recursive_tt = ToolTip(self._recursive_check, "Search files in subdirectories recursively")
   # ...
   self._search_btn_tt = ToolTip(self._search_btn, "Scan the selected directory")
   # ...
   self._ext_tt = ToolTip(
       self._ext_combo,
       'Filter by extension with operators: AND (space), OR, NOT (-), exact ("...")',
   )
   # ...
   self._filter_tt = ToolTip(
       self._filter_combo,
       'Filter with operators: AND (space), OR, NOT (-), exact ("...")',
   )
   ```

   (Note: the existing code stores no `ToolTip` references at all today. The
   rewire is a strict addition — the `ToolTip(widget, "...")` calls keep their
   side effect of binding hover events to the widget; we're only capturing
   the return value for later `set_text()` calls.)

- [ ] **Step 2: Add `_apply_text()`**

Append at the end of `class SearchBar`:

```python
    def _apply_text(self, lang: str) -> None:
        """Re-apply every translatable string in this component."""
        from profiles.gui import i18n

        # Inline prefix labels
        self._dir_label.configure(text=i18n.t("search.dir_label", lang))
        self._ext_label.configure(text=i18n.t("search.ext_label", lang))
        self._filter_label.configure(text=i18n.t("search.filter_label", lang))

        # Browse button text
        self._browse_btn.configure(text=i18n.t("search.browse", lang))

        # Recursive + Search buttons
        self._recursive_check.configure(text=i18n.t("search.recursive", lang))
        self._search_btn.configure(text=i18n.t("search.search_btn", lang))

        # Tooltips
        self._title_tt.set_text(i18n.t("title.tooltip", lang))
        self._dir_tt.set_text(i18n.t("search.dir.tooltip", lang))
        self._browse_btn_tt.set_text(i18n.t("search.browse.tooltip", lang))
        self._recursive_tt.set_text(i18n.t("search.recursive.tooltip", lang))
        self._search_btn_tt.set_text(i18n.t("search.search_btn.tooltip", lang))
        self._ext_tt.set_text(i18n.t("search.ext.tooltip", lang))
        self._filter_tt.set_text(i18n.t("search.filter.tooltip", lang))
```

- [ ] **Step 3: Verify nothing else changed**

Run: `pytest tests/gui/test_search_bar.py -v`
Expected: all existing tests still pass (the only behavioural change is
new attribute names; no widget visibility or layout moved).

- [ ] **Step 4: Commit**

```bash
git add src/profiles/gui/search_bar.py
git commit -m "refactor(gui): SearchBar keeps ToolTip + label refs for live re-label"
```

---

### Task 5: `StatusBar` — language button + `_apply_text()` + `update_language_label()`

**Files:**
- Modify: `src/profiles/gui/status_bar.py`
- Test: `tests/gui/test_status_bar.py`

**Interfaces produced:**
- `StatusBar.__init__(parent, on_config_click, on_refresh_click, on_log_click,
  on_theme_toggle, theme_label, on_shortcuts_click=None, on_language_toggle=None,
  language_label="🌐 EN")` — adds two new keyword args.
- `StatusBar.lang_btn` — the `ttk.Button` widget for the language cycle.
- `StatusBar.lang_btn_tt` — its ToolTip.
- `StatusBar.update_language_label(text: str) -> None`
- `StatusBar._apply_text(lang: str) -> None` — updates every status-bar label and tooltip.

- [ ] **Step 1: Write failing tests in `tests/gui/test_status_bar.py`**

Add to the `mock_callbacks` fixture (in the same dict):

```python
        "on_language_toggle": MagicMock(),
```

Then add a `TestStatusBarLanguageButton` class at the bottom:

```python
class TestStatusBarLanguageButton:
    """Tests for the new language switch button on the status bar."""

    def test_language_button_is_built(self, status_bar):
        assert status_bar.lang_btn is not None

    def test_language_button_label(self, status_bar):
        assert status_bar.lang_btn.cget("text") == "🌐 EN"

    def test_language_button_click_invokes_callback(self, status_bar, mock_callbacks):
        status_bar.lang_btn.invoke()
        mock_callbacks["on_language_toggle"].assert_called_once()

    def test_update_language_label_changes_text(self, status_bar):
        status_bar.update_language_label("🌐 FR")
        assert status_bar.lang_btn.cget("text") == "🌐 FR"
```

To make `status_bar` use the new callback, modify the existing fixture so it
constructs the bar with `on_language_toggle=mock_callbacks["on_language_toggle"]`
and `language_label="🌐 EN"`. The existing `theme_label` arg stays as-is.

- [ ] **Step 2: Run tests, confirm RED**

Run: `pytest tests/gui/test_status_bar.py -v`
Expected: 4 failures (`AttributeError: 'StatusBar' object has no attribute 'lang_btn'` etc.) plus the `mock_callbacks["on_language_toggle"]` `KeyError` from the fixture.

- [ ] **Step 3: Wire up the language button**

In `src/profiles/gui/status_bar.py`:

1. Extend `__init__` signature with two new keyword params:
   ```python
   def __init__(
       self,
       parent: ttk.Frame,
       on_config_click: tk.Callable[[], None],
       on_refresh_click: tk.Callable[[], None],
       on_log_click: tk.Callable[[], None],
       on_theme_toggle: tk.Callable[[], None],
       theme_label: str = "☀ Light",
       on_shortcuts_click: tk.Callable[[], None] | None = None,
       on_language_toggle: tk.Callable[[], None] | None = None,
       language_label: str = "🌐 EN",
   ) -> None:
   ```
2. Store `self._on_language_toggle = on_language_toggle` and
   `self._language_label = language_label`.
3. In `_build()`, immediately **before** the existing theme button block:
   ```python
   # Language toggle button (only when callback provided)
   self._lang_btn: ttk.Button | None = None
   self._lang_btn_tt: ToolTip | None = None
   if self._on_language_toggle is not None:
       self._lang_btn = ttk.Button(
           self._status_inner,
           text=self._language_label,
           style="Theme.TButton",
           command=self._on_language_toggle,
       )
       self._lang_btn.pack(side=tk.LEFT, padx=(0, 4))
       self._lang_btn_tt = ToolTip(self._lang_btn, "Switch GUI language")
   ```
4. Add public properties:
   ```python
   @property
   def lang_btn(self) -> ttk.Button | None:
       return self._lang_btn

   @property
   def lang_btn_tt(self) -> ToolTip | None:
       return self._lang_btn_tt
   ```
5. Add public method (mirroring `update_theme_label`):
   ```python
   def update_language_label(self, text: str) -> None:
       """Update the language toggle button label."""
       if self._lang_btn is not None:
           self._lang_btn.configure(text=text)
   ```
6. Add `_apply_text(lang)`:
   ```python
   def _apply_text(self, lang: str) -> None:
       """Re-apply every translatable string in the status bar."""
       from profiles.gui import i18n

       self._config_link.configure(text=i18n.t("status.config", lang))
       self._refresh_btn.configure(text=i18n.t("status.refresh", lang))
       self._log_link.configure(text=i18n.t("status.log", lang))
       if self._shortcuts_btn is not None:
           self._shortcuts_btn.configure(text=i18n.t("status.shortcuts", lang))

       # Inline prefix labels are stored as _user_label_prefix, etc.
       # (Added below.)
       self._user_label_prefix.configure(text=i18n.t("status.user", lang))
       self._host_label_prefix.configure(text=i18n.t("status.host", lang))
       self._ip_label_prefix.configure(text=i18n.t("status.ip", lang))
       self._count_label.configure(text=i18n.t("status.count", lang))

       # Tooltips
       self._config_link_tt.set_text(i18n.t("status.config.tooltip", lang))
       self._refresh_btn_tt.set_text(i18n.t("status.refresh.tooltip", lang))
       self._log_link_tt.set_text(i18n.t("status.log.tooltip", lang))
       if self._shortcuts_btn_tt is not None:
           self._shortcuts_btn_tt.set_text(i18n.t("status.shortcuts.tooltip", lang))
       if self._lang_btn_tt is not None:
           self._lang_btn_tt.set_text(i18n.t("status.language.tooltip", lang))
       self._theme_btn_tt.set_text(i18n.t("status.theme.tooltip", lang))
       self._user_label_tt.set_text(i18n.t("status.user.tooltip", lang))
       self._host_label_tt.set_text(i18n.t("status.host.tooltip", lang))
       self._ip_label_tt.set_text(i18n.t("status.ip.tooltip", lang))
       self._count_label_tt.set_text(i18n.t("status.count.tooltip", lang))
       self._dir_status_label_tt.set_text(i18n.t("status.dir_status.tooltip", lang))
   ```
7. To make `_apply_text` work, store every inline `ttk.Label("User:")` and
   the ToolTip references created in `_build()`:

   Replace each existing bare `ttk.Label(self._status_inner, text="User:",
   style="Info.TLabel").pack(...)` line with:
   ```python
   self._user_label_prefix = ttk.Label(self._status_inner, text="User:", style="Info.TLabel")
   self._user_label_prefix.pack(side=tk.LEFT, padx=(4, 2))
   ```
   Do the same for `Host:`, `IP:`, and the bare Config/Refresh/Log/Shortcuts
   ToolTip calls. Pattern:
   ```python
   self._config_link_tt = ToolTip(self._config_link, "Open configuration file")
   self._refresh_btn_tt = ToolTip(self._refresh_btn, "Reload configuration and refresh file list")
   self._log_link_tt = ToolTip(self._log_link, "Open log file")
   self._theme_btn_tt = ToolTip(self._theme_btn, "Toggle between light and dark theme")
   self._user_label_tt = ToolTip(self._user_label, "Current Windows username")
   self._host_label_tt = ToolTip(self._host_label, "Current machine hostname")
   self._ip_label_tt = ToolTip(self._ip_label, "Current machine IP address")
   self._count_label_tt = ToolTip(self._count_label, "Number of files matching current filters")
   self._dir_status_label_tt = ToolTip(self._dir_status_label, "Current directory and scan status")
   ```
   For the `self._shortcuts_btn_tt`, store it only when the shortcuts button
   is created.

- [ ] **Step 4: Run tests, confirm GREEN**

Run: `pytest tests/gui/test_status_bar.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/profiles/gui/status_bar.py tests/gui/test_status_bar.py
git commit -m "feat(gui): StatusBar language button + live re-label"
```

---

### Task 6: Context menu — route every label through `t()`

**Files:**
- Modify: `src/profiles/gui/context_menu.py`

**Interfaces consumed:**
- `i18n.t(key)` (reads current language at call time; the menu is rebuilt on
  every right-click so no live re-label is needed).

- [ ] **Step 1: Add import and replace labels**

In `src/profiles/gui/context_menu.py`, add at top:

```python
from profiles.gui import i18n
```

Then replace every `label="…"` and `label=f"… {file_path.name}"` argument in
every `menu.add_command` / `menu.add_cascade` call with the appropriate
`t("menu.*")` call. The replacement table (read the file end-to-end):

| Existing literal | Replacement |
|---|---|
| `f"▶  Launch {file_path.name}"` | `f"\u25b6  {i18n.t('menu.launch')} {file_path.name}"` |
| `"🚀  Launch with arguments…"` | `f"\U0001f680  {i18n.t('menu.launch_args')}"` |
| `"📂  Reveal in file explorer"` | `f"\U0001f4c2  {i18n.t('menu.reveal')}"` |
| `"📁  Open containing folder"` | `f"\U0001f4c1  {i18n.t('menu.open_folder')}"` |
| `"🖥  Open terminal here"` | `f"\U0001f5a5  {i18n.t('menu.terminal')}"` |
| `"🔎  Filter list to this folder"` | `f"\U0001f50e  {i18n.t('menu.filter_folder')}"` |
| `"🔎  Filter list by this extension"` | `f"\U0001f50e  {i18n.t('menu.filter_extension')}"` |
| `"Full file path"` | `i18n.t("menu.copy.full")` |
| `"File path (forward slashes)"` | `i18n.t("menu.copy.forward")` |
| `"File name with extension"` | `i18n.t("menu.copy.name_w_ext")` |
| `"File name without extension"` | `i18n.t("menu.copy.name_wo_ext")` |
| `"Directory path"` | `i18n.t("menu.copy.directory")` |
| `"🔗  Copy as URI"` | `f"\U0001f517  {i18n.t('menu.copy.uri')}"` |
| `"📋  Copy"` | `f"\U0001f4cb  {i18n.t('menu.copy')}"` |
| `"MD5"` | `i18n.t("menu.hash.md5")` |
| `"SHA-256"` | `i18n.t("menu.hash.sha256")` |
| `"Copy MD5"` | `i18n.t("menu.hash.copy_md5")` |
| `"Copy SHA-256"` | `i18n.t("menu.hash.copy_sha256")` |
| `"✅  Verify MD5 against clipboard"` | `f"\u2705  {i18n.t('menu.hash.verify_md5')}"` |
| `"✅  Verify SHA-256 against clipboard"` | `f"\u2705  {i18n.t('menu.hash.verify_sha256')}"` |
| `"#  Hash"` | `f"#  {i18n.t('menu.hash')}"` |

- [ ] **Step 2: Run existing context menu tests**

Run: `pytest tests/gui/test_context_menu.py -v` (if present) and
`pytest tests/gui/test_main_window.py -v`.
Expected: pass. No test references string literals from the menu, so the
replacements are invisible to tests.

- [ ] **Step 3: Commit**

```bash
git add src/profiles/gui/context_menu.py
git commit -m "feat(gui): context menu routes labels through i18n.t"
```

---

### Task 7: `MainWindow` — language state, toggle, apply, registrations

**Files:**
- Modify: `src/profiles/gui/main_window.py`
- Test: `tests/gui/test_main_window.py`

**Interfaces produced:**
- `MainWindow._language: str` — current in-process language.
- `MainWindow._on_toggle_language()` — 2-state cycle (`en → fr → en`).
- `MainWindow._apply_language(lang: str)` — update state, persist, run registry.
- `MainWindow._relabel_status_bar(lang: str)` — re-applies status bar +
  count / dir_status labels.
- `MainWindow._relabel_search_bar(lang: str)` — delegates to
  `self._search_bar._apply_text(lang)`.
- `MainWindow._relabel_action_bar(lang: str)` — close-after + execute button.

- [ ] **Step 1: Write failing tests in `tests/gui/test_main_window.py`**

Read the existing file to find the test class for status bar / theme toggling.
Append three new tests:

```python
    def test_toggle_language_persists_french(self, tmp_path: Path) -> None:
        config_path = tmp_path / ".profiles"
        ConfigReader(config_path).load()  # ensure file exists
        # Build a window — uses existing test fixture pattern.
        win = MainWindow(AppConfig(config_path=config_path))
        win._on_toggle_language()  # en -> fr
        assert win._language == "fr"
        content = config_path.read_text(encoding="utf-8")
        assert re.search(r"^\s*language\s*=\s*fr\s*$", content, re.MULTILINE | re.IGNORECASE)
        win._root.destroy()

    def test_toggle_language_relabels_search_button(self, tmp_path: Path) -> None:
        config_path = tmp_path / ".profiles"
        ConfigReader(config_path).load()
        win = MainWindow(AppConfig(config_path=config_path))
        assert "Search" in win._search_btn.cget("text")
        win._on_toggle_language()
        assert "Rechercher" in win._search_btn.cget("text")
        win._root.destroy()

    def test_apply_language_updates_count_label(self, tmp_path: Path) -> None:
        config_path = tmp_path / ".profiles"
        ConfigReader(config_path).load()
        win = MainWindow(AppConfig(config_path=config_path))
        # Seed the count with an English label, then apply FR.
        win._count_label.configure(text="Files: 5")
        win._apply_language("fr")
        assert "Fichiers" in win._count_label.cget("text")
        win._root.destroy()
```

If the existing tests construct a full `MainWindow`, follow that pattern
exactly. If they use a smaller fixture that skips Tk, use it; the tests above
are written against the real `MainWindow` (matching the theme-toggle tests'
style — confirm by reading the file before pasting).

- [ ] **Step 2: Run tests, confirm RED**

Run: `pytest tests/gui/test_main_window.py -v`
Expected: 3 failures (`AttributeError: 'MainWindow' object has no attribute '_language'` etc.).

- [ ] **Step 3: Add language state to `__init__`**

In `src/profiles/gui/main_window.py`:

1. Add import:
   ```python
   from profiles.gui import i18n
   ```
2. Add a type annotation in the `MainWindow` class declaration block:
   ```python
       _language: str
   ```
3. In `__init__`, immediately after the existing
   `self._theme_name: str = self._config.theme` block, add:
   ```python
           self._language: str = i18n.normalize_language(self._config.language)
           i18n.set_current_language(self._language)
   ```

- [ ] **Step 4: Add `_on_toggle_language` and `_apply_language`**

Immediately after `_apply_theme`, add:

```python
    def _on_toggle_language(self) -> None:
        """Toggle between English and French."""
        new_lang = "fr" if self._language == "en" else "en"
        self._apply_language(new_lang)

    def _apply_language(self, lang: str) -> None:
        """Apply *lang* to the whole GUI and persist to .profiles."""
        new_lang = i18n.normalize_language(lang)
        if new_lang == self._language:
            return
        self._language = new_lang
        i18n.set_current_language(new_lang)

        # 1. Update status-bar language button label.
        if self._status_bar is not None:
            self._status_bar.update_language_label(
                i18n.LANGUAGE_LABELS.get(new_lang, i18n.LANGUAGE_LABELS["en"])
            )

        # 2. Persist (best-effort; mirrors theme toggle behaviour).
        save_config_str(
            self._config.config_path,
            "LAUNCHER",
            "language",
            new_lang,
        )

        # 3. Walk registry.
        i18n.set_language(new_lang)

        self._logger.info("Language switched to: %s", new_lang)
```

- [ ] **Step 5: Register re-label callbacks**

In `__init__`, immediately **after** the existing
`self._ui.build()` line (so every widget exists), add:

```python
        # Register live re-label callbacks (also called once at registration)
        i18n.register(lambda lang: self._search_bar._apply_text(lang))
        i18n.register(lambda lang: self._status_bar._apply_text(lang))
        i18n.register(lambda lang: self._relabel_action_bar(lang))
        i18n.register(lambda lang: self._relabel_status_bar_dynamic(lang))
```

And the two relabel methods, immediately after `_apply_language`:

```python
    def _relabel_action_bar(self, lang: str) -> None:
        """Re-apply the close-after + execute button labels."""
        from profiles.gui import i18n

        self._close_check.configure(text=i18n.t("action.close_after", lang))
        if self._close_check_tt is not None:
            self._close_check_tt.set_text(i18n.t("action.close_after.tooltip", lang))

        # Execute button: pick the right variant based on current state.
        if not self._tree.get_children():
            self._execute_btn.configure(text=i18n.t("action.execute.no_match", lang))
        elif not self._tree.selection():
            self._execute_btn.configure(text=i18n.t("action.execute.empty", lang))
        else:
            self._execute_btn.configure(text=i18n.t("action.execute", lang))

    def _relabel_status_bar_dynamic(self, lang: str) -> None:
        """Re-apply count label and the fixed tokens in dir_status.

        The count label's *number* (current file count) is preserved;
        only the translated prefix changes. The dir_status label is
        translated only when its current text matches a known fixed
        English token; dynamic values like 'Directory: <path>' are left
        untouched.
        """
        from profiles.gui import i18n

        current = self._count_label.cget("text")
        # Extract trailing number from "Files: N"
        match = re.match(r"^(\D*?)\s*(\d+)\s*$", current)
        if match is not None:
            prefix_en = i18n.t("status.count", "en")
            if match.group(1).strip() == prefix_en.rstrip(":"):
                # Currently English — translate prefix.
                new_prefix = i18n.t("status.count", lang).rstrip(":")
                self._count_label.configure(text=f"{new_prefix} {match.group(2)}")
            # else: already translated — leave alone.
        else:
            # No number; just set translated prefix with 0.
            new_prefix = i18n.t("status.count", lang).rstrip(":")
            self._count_label.configure(text=f"{new_prefix} 0")

        dir_text = self._dir_status_label.cget("text")
        for en_token in (
            i18n.t("count_patterns.scanning", "en"),
            i18n.t("count_patterns.dir_not_found", "en"),
            i18n.t("count_patterns.scan_failed", "en"),
        ):
            if dir_text == en_token:
                idx = (
                    i18n.t("count_patterns.scanning", "en"),
                    i18n.t("count_patterns.dir_not_found", "en"),
                    i18n.t("count_patterns.scan_failed", "en"),
                ).index(en_token)
                fr_keys = ("count_patterns.scanning", "count_patterns.dir_not_found", "count_patterns.scan_failed")
                self._dir_status_label.configure(text=i18n.t(fr_keys[idx], lang))
                break
```

(The `_close_check_tt` reference must be created in `ui.py`; do that as part
of this same step — see below.)

- [ ] **Step 6: Add `_close_check_tt` ref in `ui.py`**

In `src/profiles/gui/ui.py`, in `_build_action_bar`, after the existing
`ToolTip(self.window._close_check, "Close ProFiles after launching a file")`
call, capture the return value:

```python
        self.window._close_check_tt = ToolTip(
            self.window._close_check,
            "Close ProFiles after launching a file",
        )
```

Add a type annotation in `MainWindow`'s declaration block:

```python
       _close_check_tt: ToolTip
```

(Import `ToolTip` from `profiles.gui.styles` — the existing import in `ui.py`
already covers this.)

- [ ] **Step 7: Wire the language callback into the status bar build**

In `src/profiles/gui/ui.py`, in `_build_status_bar`, extend the `StatusBar(...)`
construction to pass the new callback:

```python
        self.window._status_bar = StatusBar(
            parent=self.window._root,
            on_config_click=self.window._on_open_config,
            on_refresh_click=self.window._on_refresh,
            on_log_click=self.window._on_open_log,
            on_theme_toggle=self.window._on_toggle_theme,
            on_shortcuts_click=self.window._on_show_shortcuts,
            on_language_toggle=self.window._on_toggle_language,
            theme_label=THEME_LABELS.get(self.window._theme_name, "\u2600 Light"),
            language_label=i18n.LANGUAGE_LABELS.get(self.window._language, i18n.LANGUAGE_LABELS["en"]),
        )
```

And capture the new widget reference:

```python
        self.window._lang_btn = self.window._status_bar.lang_btn
        self.window._lang_btn_tt = self.window._status_bar.lang_btn_tt
```

Add `from profiles.gui import i18n` at the top of `ui.py`.

Add type annotations for `_lang_btn` and `_lang_btn_tt` in `MainWindow`.

- [ ] **Step 8: Translate the shortcuts dialog**

In `_on_show_shortcuts` (already exists in `main_window.py`), replace:

- `dlg.title("Keyboard Shortcuts")` → `dlg.title(i18n.t("shortcuts.title", self._language))`
- `header = ttk.Label(dlg, text="Keyboard Shortcuts", style="Title.TLabel")` → `header = ttk.Label(dlg, text=i18n.t("shortcuts.title", self._language), style="Title.TLabel")`
- `close_btn = ttk.Button(dlg, text="Close", command=dlg.destroy)` → `close_btn = ttk.Button(dlg, text=i18n.t("shortcuts.close", self._language), command=dlg.destroy)`

- [ ] **Step 9: Run all relevant tests**

Run: `pytest tests/gui/test_main_window.py tests/gui/test_status_bar.py tests/gui/test_search_bar.py -v`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add src/profiles/gui/main_window.py src/profiles/gui/ui.py tests/gui/test_main_window.py
git commit -m "feat(gui): MainWindow language toggle + relabel registrations"
```

---

### Task 8: Documentation updates

**Files:**
- Modify: `docs/configuration-profile.en.md`
- Modify: `docs/configuration-profile.fr.md`
- Modify: `README.md`

- [ ] **Step 1: Add the EN doc subsection**

In `docs/configuration-profile.en.md`, find the existing `theme` row in the
`[LAUNCHER]` settings table. Immediately after it, add:

```markdown
| `language` | `en` \| `fr` | `en` | GUI language. Toggle from the 🌐 button in the status bar, or set this key and restart ProFiles. |
```

- [ ] **Step 2: Add the FR doc subsection**

Same edit in `docs/configuration-profile.fr.md`:

```markdown
| `language` | `en` \| `fr` | `en` | Langue de l'interface. Basculer avec le bouton 🌐 de la barre d'état, ou définir cette clé et relancer ProFiles. |
```

- [ ] **Step 3: Add the README note**

Find the "Configuration" or "Features" section in `README.md`. Add a single
line (matching the existing line style — most likely a bullet under Features):

```markdown
- Switch the GUI between English and French from the 🌐 button in the status bar (or via `language = fr` in `.profiles`).
```

If the existing list already has a closely-related bullet (e.g. theme toggle),
add the new bullet **immediately after** it for thematic grouping.

- [ ] **Step 4: Commit**

```bash
git add docs/configuration-profile.en.md docs/configuration-profile.fr.md README.md
git commit -m "docs: document GUI language switch"
```

---

## Self-review (after writing the plan)

1. **Spec coverage:** every spec section maps to at least one task.
   - Config model + reader + template → Task 2.
   - i18n module + catalog + registry → Task 1.
   - StatusBar button + `_apply_text` → Task 5.
   - SearchBar `_apply_text` → Task 4.
   - Context menu labels → Task 6.
   - MainWindow toggle + apply + registrations → Task 7.
   - Shortcuts dialog translation → Task 7 step 8.
   - ToolTip live update → Task 3.
   - Tests (i18n, status bar, main window, reader) → Tasks 1, 2, 5, 7.
   - Docs → Task 8.
   - No spec requirement without a task.

2. **Placeholder scan:** no "TBD", "TODO", "fill in", "similar to Task N" in the plan. ✅

3. **Type / signature consistency:**
   - `i18n.normalize_language(value)` used in Task 2 as the spec for
     `_normalize_lang` (Task 2 step 4).
   - `i18n.set_language(lang)` is the canonical entry point; MainWindow calls
     it once (Task 7 step 4); widget components register their `_apply_text`
     callbacks (Tasks 4, 5, 7).
   - `SearchBar._apply_text(lang)` is called from `MainWindow._relabel_search_bar`
     via the registered lambda (Task 7 step 5).
   - `StatusBar._apply_text(lang)` is called from the registered lambda
     (Task 7 step 5).
   - `MainWindow._relabel_status_bar_dynamic(lang)` is the method whose name
     matches the registration lambda body — consistent.
   - `ToolTip.set_text(text)` is the public method added in Task 3 and used
     in Tasks 4 and 5. Consistent.
   - `StatusBar.lang_btn` / `lang_btn_tt` are the public properties added in
     Task 5 and consumed in Task 7 step 7. Consistent.
   - `_close_check_tt` is added in Task 7 step 6 and consumed in Task 7
     step 5. Consistent.

4. **Scope check:** one cohesive feature, one PR's worth of diff, single
   implementation plan. ✅