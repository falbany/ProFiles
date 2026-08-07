"""Tests for the refactored ColumnConfiguration schema."""

from profiles.core.config.models import ColumnConfiguration


def test_column_configuration_new_schema():
    """Verify ColumnConfiguration has match/transform/stretch/name fields."""
    config = ColumnConfiguration(
        name="Version Number",
        width=120,
        stretch=False,
        match="version",
        transform="Ver. \\1",
        priority=20,
        default="",
    )

    assert config.name == "Version Number"
    assert config.width == 120
    assert config.stretch is False
    assert config.match == "version"
    assert config.transform == "Ver. \\1"
    assert config.priority == 20
    assert config.default == ""


def test_column_configuration_default_values():
    """Verify ColumnConfiguration defaults."""
    config = ColumnConfiguration()

    assert config.name == ""
    assert config.width == 150
    assert config.stretch is False
    assert config.match == ".*"
    assert config.transform is None
    assert config.priority == 0
    assert config.default == ""


def test_column_configuration_has_no_legacy_fields():
    """Old expression/group fields are gone from the dataclass."""
    config = ColumnConfiguration()
    assert not hasattr(config, "expression")
    assert not hasattr(config, "group")
