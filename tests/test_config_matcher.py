from profiles.core.config.matcher import (
    match_pattern,
    matches_machine_config,
    select_active_configuration,
)
from profiles.core.config.models import AppConfig, MachineConfiguration, MatchCriteria


def test_match_pattern_glob_and_regex():
    assert match_pattern("WORKSTATION-*", "workstation-1")
    assert match_pattern("re:^192\\.168\\.\\d+\\.\\d+$", "192.168.1.50")
    assert not match_pattern("WORKSTATION-*", "SERVER-1")


def test_matches_machine_config_or_logic():
    cfg = MachineConfiguration(
        match=MatchCriteria(hostname=("HOST-1",), ip=("10.0.0.*",), path=("/projects/*",))
    )
    assert matches_machine_config(cfg, "HOST-1", "192.168.0.1", "/tmp")
    assert matches_machine_config(cfg, "OTHER-HOST", "10.0.0.5", "/tmp")
    assert matches_machine_config(cfg, "OTHER-HOST", "192.168.0.1", "/projects/app")
    assert not matches_machine_config(cfg, "OTHER-HOST", "192.168.0.1", "/tmp")


def test_select_active_configuration():
    cfg1 = MachineConfiguration(match=MatchCriteria(hostname=("HOST-1",)))
    cfg2 = MachineConfiguration(match=MatchCriteria(path=("/data/*",)))
    app_cfg = AppConfig(configurations=[cfg1, cfg2])

    selected1 = select_active_configuration(app_cfg, "HOST-1", "1.1.1.1", "/tmp")
    assert selected1 == cfg1

    selected2 = select_active_configuration(app_cfg, "HOST-2", "1.1.1.1", "/data/app")
    assert selected2 == cfg2

    fallback = select_active_configuration(app_cfg, "HOST-3", "1.1.1.1", "/tmp")
    assert fallback == cfg1
