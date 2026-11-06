"""Semantic validation of the raw ProFiles configuration tree.

Single Responsibility: check the raw YAML dict for problems that Pydantic
type validation cannot catch — unknown top-level keys, ``extends``
references to missing configs, and inheritance cycles. Raises
:class:`ConfigError` with a precise dotted path.
"""

from __future__ import annotations

from profiles.core.config.schema import ConfigError

_KNOWN_TOP_LEVEL = {"version", "defaults", "columns", "hooks", "configs"}


def collect_issues(raw: dict) -> list[ConfigError]:
    """Collect ALL semantic problems in the raw YAML mapping, in order.

    Same checks as :func:`validate` — unknown top-level keys, unknown
    ``extends`` references, inheritance cycles — but every occurrence is
    reported instead of failing fast at the first one. Built for editor
    diagnostics (issue: the validator surfaced only the first error);
    :func:`validate` keeps its fail-fast contract on top of this.

    Args:
        raw: The parsed YAML dict (from :func:`yaml_io.read_yaml`).

    Returns:
        Every semantic problem found, in document order (unknown keys,
        then unknown ``extends`` references, then inheritance cycles).
        ``[]`` when the mapping is clean.
    """
    errors: list[ConfigError] = []

    if not isinstance(raw, dict):
        return [ConfigError("", "configuration root must be a mapping")]

    for key in raw:
        if not isinstance(key, str) or key not in _KNOWN_TOP_LEVEL:
            errors.append(ConfigError(str(key), f"unknown top-level key '{key}'"))

    configs = raw.get("configs") or {}
    if not isinstance(configs, dict):
        return errors

    for name, cfg in configs.items():
        if not isinstance(cfg, dict):
            continue
        extends = cfg.get("extends")
        if extends is None:
            continue
        if not isinstance(extends, str) or extends not in configs:
            errors.append(
                ConfigError(
                    f"configs.{name}.extends",
                    f"unknown config '{extends}'",
                )
            )

    # Cycle detection via DFS; each cycle met along the way is reported.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str, stack: tuple[str, ...]) -> None:
        if name in visiting:
            cycle = " -> ".join((*stack, name))
            closed = stack[-1]
            errors.append(
                ConfigError(
                    f"configs.{closed}.extends",
                    f"inheritance cycle: {cycle}",
                )
            )
            return
        if name in visited:
            return
        if not isinstance(configs.get(name), dict):
            visited.add(name)
            return
        visiting.add(name)
        extends = configs[name].get("extends")
        if isinstance(extends, str):
            visit(extends, (*stack, name))
        visiting.discard(name)
        visited.add(name)

    for name in configs:
        if isinstance(name, str):
            visit(name, (name,))

    return errors


def validate(raw: dict) -> None:
    """Validate the raw YAML mapping semantically.

    Fail-fast twin of :func:`collect_issues`: raises the FIRST problem
    found, preserving the historical load-path contract.

    Args:
        raw: The parsed YAML dict (from :func:`yaml_io.read_yaml`).

    Raises:
        ConfigError: On unknown top-level keys, unknown ``extends``
            references, or inheritance cycles.
    """
    issues = collect_issues(raw)
    if issues:
        raise issues[0]


__all__ = ["collect_issues", "validate"]
