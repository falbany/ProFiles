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
        "title.tooltip",
        "search.dir_label",
        "search.dir.tooltip",
        "search.browse",
        "search.browse.tooltip",
        "search.recursive",
        "search.recursive.tooltip",
        "search.search_btn",
        "search.search_btn.tooltip",
        "search.ext_label",
        "search.ext.tooltip",
        "search.filter_label",
        "search.filter.tooltip",
        "status.config",
        "status.config.tooltip",
        "status.refresh",
        "status.refresh.tooltip",
        "status.log",
        "status.log.tooltip",
        "status.shortcuts",
        "status.shortcuts.tooltip",
        "status.language.tooltip",
        "status.theme.tooltip",
        "status.user",
        "status.user.tooltip",
        "status.host",
        "status.host.tooltip",
        "status.ip",
        "status.ip.tooltip",
        "status.count",
        "status.count.tooltip",
        "status.dir_status.tooltip",
        "action.close_after",
        "action.close_after.tooltip",
        "action.execute",
        "action.execute.empty",
        "action.execute.no_match",
        "shortcuts.title",
        "shortcuts.close",
        "menu.refresh",
        "menu.config",
        "menu.log",
        "menu.shortcuts",
        "menu.exit",
        "menu.launch",
        "menu.launch_args",
        "menu.reveal",
        "menu.open_folder",
        "menu.terminal",
        "menu.filter_folder",
        "menu.filter_extension",
        "menu.copy",
        "menu.copy.full",
        "menu.copy.forward",
        "menu.copy.name_w_ext",
        "menu.copy.name_wo_ext",
        "menu.copy.directory",
        "menu.copy.uri",
        "menu.hash",
        "menu.hash.md5",
        "menu.hash.sha256",
        "menu.hash.copy_md5",
        "menu.hash.copy_sha256",
        "menu.hash.verify_md5",
        "menu.hash.verify_sha256",
        "count_patterns.scanning",
        "count_patterns.dir_not_found",
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
