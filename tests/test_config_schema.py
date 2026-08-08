
from profiles.core.config.models import MachineConfiguration, MatchCriteria
from profiles.core.config.schema import MachineConfig


def test_match_criteria_schema_coercion():
    data = {
        "match": {
            "hostname": "WORKSTATION-1",
            "ip": ["192.168.1.1", "10.0.0.1"],
            "path": "/data/tests",
        },
        "scan": "/data/tests",
    }
    cfg = MachineConfig.model_validate(data)
    assert cfg.match.hostname == ["WORKSTATION-1"]
    assert cfg.match.ip == ["192.168.1.1", "10.0.0.1"]
    assert cfg.match.path == ["/data/tests"]
    assert cfg.scan == ["/data/tests"]


def test_match_criteria_schema_coercion_single_to_list():
    data = {
        "match": {
            "hostname": "WORKSTATION-1",
            "ip": "192.168.1.1",
            "path": "/data/tests",
        },
        "scan": "/data/tests",
    }
    cfg = MachineConfig.model_validate(data)
    assert cfg.match.hostname == ["WORKSTATION-1"]
    assert cfg.match.ip == ["192.168.1.1"]
    assert cfg.match.path == ["/data/tests"]
    assert cfg.scan == ["/data/tests"]


def test_match_criteria_schema_defaults():
    cfg = MachineConfig.model_validate({})
    assert cfg.match.hostname == []
    assert cfg.match.ip == []
    assert cfg.match.path == []
    assert cfg.scan == []


def test_machine_configuration_model_init():
    match = MatchCriteria(
        hostname=("WORKSTATION-1",),
        ip=("192.168.1.1", "10.0.0.1"),
        path=("/data/tests",),
    )
    mc = MachineConfiguration(
        extensions=(".txt",),
        filters=("ST_PRO",),
        row_colors=(("pattern", "color"),),
        search_exclude_files=("*.tmp",),
        match=match,
        scan=("/data/tests",),
    )
    assert mc.match.hostname == ("WORKSTATION-1",)
    assert mc.match.ip == ("192.168.1.1", "10.0.0.1")
    assert mc.match.path == ("/data/tests",)
    assert mc.scan == ("/data/tests",)
