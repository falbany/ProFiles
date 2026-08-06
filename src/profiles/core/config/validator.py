"""Semantic validation of the raw ProFiles configuration tree.

Single Responsibility: check the raw YAML dict for problems that Pydantic
type validation cannot catch — unknown top-level keys, ``extends``
references to missing configs, and inheritance cycles. Raises
:class:`ConfigError` with a precise dotted path.
"""

from __future__ import annotations

from profiles.core.config.schema import ConfigError

_KNOWN_TOP_LEVEL = {"version", "defaults", "columns", "hooks", "configs"}


def validate(raw: dict) -> None:
    """Validate the raw YAML mapping semantically.

    Args:
        raw: The parsed YAML dict (from :func:`yaml_io.read_yaml`).

    Raises:
        ConfigError: On unknown top-level keys, unknown ``extends``
            references, or inheritance cycles.
    """
    for key in raw:
        if key not in _KNOWN_TOP_LEVEL:
            raise ConfigError(key, f"unknown top-level key '{key}'")

    configs = raw.get("configs") or {}
    if not isinstance(configs, dict):
        return

    for name, cfg in configs.items():
        if not isinstance(cfg, dict):
            continue
        extends = cfg.get("extends")
        if extends is None:
            continue
        if extends not in configs:
            raise ConfigError(
                f"configs.{name}.extends",
                f"unknown config '{extends}'",
            )

    # Cycle detection via DFS
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str, stack: tuple[str, ...]) -> None:
        if name in visiting:
            cycle = " -> ".join((*stack, name))
            closed = stack[-1]
            raise ConfigError(
                f"configs.{closed}.extends",
                f"inheritance cycle: {cycle}",
            )
        if name in visited:
            return
        visiting.add(name)
        extends = configs[name].get("extends")
        if extends is not None:
            visit(extends, (*stack, name))
        visiting.discard(name)
        visited.add(name)

    for name in configs:
        visit(name, (name,))


__all__ = ["validate"]
