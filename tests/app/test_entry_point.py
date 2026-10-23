"""The Briefcase stub resolves ``profiles.main`` lazily (spec §5.3)."""

from __future__ import annotations


def test_package_exposes_lazy_main() -> None:
    import profiles
    from profiles.app import main as real_main

    assert profiles.main is real_main


def test_unknown_attribute_still_raises() -> None:
    import pytest

    import profiles

    with pytest.raises(AttributeError):
        profiles.no_such_thing  # noqa: B018
