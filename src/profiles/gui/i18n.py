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
        "menu.properties": "Properties",
        "menu.delete": "Delete file",
        "menu.refresh_list": "Refresh list",
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
        "menu.properties": "Propriétés",
        "menu.delete": "Supprimer le fichier",
        "menu.refresh_list": "Actualiser la liste",
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