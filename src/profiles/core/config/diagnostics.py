"""Editor diagnostics: collect ALL problems in configuration content.

Single Responsibility: turn the fail-fast parse → semantic → schema
pipeline (:class:`~profiles.core.config.reader.ConfigReader.from_content`
raises on the first problem) into a complete issue report for the YAML
editor's Problems panel. Pure and read-only — parses in memory, never
touches the disk, never raises.

Error-collection guarantees:
- YAML *syntax* errors are necessarily single-issue: the underlying
  parser (ruamel.yaml) stops at the first one.
- Semantic problems (unknown top-level keys, unknown ``extends``
  references, inheritance cycles) are collected exhaustively.
- Schema violations report every Pydantic error, with a dotted path.
"""

from __future__ import annotations

from pydantic import ValidationError

from profiles.core.config.io.yaml_io import read_yaml_text
from profiles.core.config.schema import AppConfigYaml
from profiles.core.config.validator import collect_issues


def collect_config_issues(text: str) -> list[dict[str, str]]:
    """Report every problem found in configuration *text*.

    Args:
        text: Raw YAML configuration content (a ``.profiles`` draft).

    Returns:
        A list of ``{"severity": "error", "message": ...}`` dicts — ``[]``
        when the content parses, passes semantic validation and the
        schema. The first YAML syntax error (if any) ends the report:
        no tree exists to validate until it is fixed.
    """
    try:
        raw = read_yaml_text(text)
    except Exception as exc:  # noqa: BLE001 — any parser failure is report data
        return [{"severity": "error", "message": f"YAML syntax error: {exc}"}]
    if not raw and not isinstance(raw, (int, float, bool)):
        return [{"severity": "error", "message": "configuration file is empty"}]
    if not isinstance(raw, dict):
        return [{"severity": "error", "message": "configuration root must be a mapping"}]

    try:
        issues = [{"severity": "error", "message": str(error)} for error in collect_issues(raw)]
    except Exception as exc:  # noqa: BLE001
        issues = [{"severity": "error", "message": f"semantic validation error: {exc}"}]

    try:
        AppConfigYaml.model_validate(raw)
    except ValidationError as exc:
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            message = error["msg"]
            issues.append(
                {"severity": "error", "message": f"{location}: {message}" if location else message}
            )
    except Exception as exc:  # noqa: BLE001
        issues.append({"severity": "error", "message": f"schema validation error: {exc}"})
    return issues


__all__ = ["collect_config_issues"]
