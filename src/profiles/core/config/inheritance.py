"""Resolve ``defaults`` + ``extends`` inheritance for configurations.

Single Responsibility: pure functions that turn the raw schema
(:class:`AppConfigYaml`) into fully-resolved :class:`MachineConfig`
objects where every list is merged with defaults and no field is ``None``.
"""

from __future__ import annotations

from profiles.core.config.schema import (
    AppConfigYaml,
    ConfigError,
    Defaults,
    MachineConfig,
    MatchCriteriaSchema,
    RowColor,
)


def _merge_str(base: list[str], local: list[str] | None) -> list[str]:
    """Merge *local* (first) with *base*, deduped, order-preserving."""
    if local is None:
        return list(base)
    merged = list(local)
    for item in base:
        if item not in merged:
            merged.append(item)
    return merged


def _merge_row(base: list[RowColor], local: list[RowColor] | None) -> list[RowColor]:
    if local is None:
        return list(base)
    merged = list(local)
    for rc in base:
        if rc not in merged:
            merged.append(rc)
    return merged


def _resolve_machine(
    name: str,
    configs: dict[str, MachineConfig],
    defaults: Defaults,
    stack: tuple[str, ...],
) -> MachineConfig:
    cfg = configs[name]

    if cfg.extends is not None:
        if cfg.extends not in configs:
            raise ConfigError(f"configs.{name}.extends", f"unknown config '{cfg.extends}'")
        if cfg.extends in stack:
            cycle = " -> ".join((*stack, cfg.extends))
            raise ConfigError(f"configs.{name}.extends", f"inheritance cycle: {cycle}")
        base = _resolve_machine(cfg.extends, configs, defaults, (*stack, name))
    else:
        base = None

    def pick(field: str):
        local = getattr(cfg, field)
        inherited = getattr(base, field) if base is not None else None
        local_set = field in cfg.model_fields_set
        if field in ("extensions", "filters", "search_exclude_files"):
            if local is None or not local_set:
                return list(inherited or [])
            return _merge_str(inherited or [], local)
        if field == "row_colors":
            if local is None or not local_set:
                return list(inherited or [])
            return _merge_row(inherited or [], local)
        if local_set:
            return local
        return inherited

    return MachineConfig(
        name=cfg.name,
        extends=cfg.extends,
        match=pick("match") or MatchCriteriaSchema(),
        scan=list(pick("scan") or []),
        extensions=tuple(_merge_str(defaults.extensions, pick("extensions"))),
        filters=tuple(_merge_str(defaults.filters, pick("filters"))),
        row_colors=_merge_row(defaults.row_colors, pick("row_colors")),
        search_exclude_files=tuple(
            _merge_str(defaults.search_exclude_files, pick("search_exclude_files"))
        ),
    )


def resolve_configs(cfg: AppConfigYaml) -> dict[str, MachineConfig]:
    """Resolve every named config against defaults and the extends chain.

    Returns:
        A dict mapping config name to a fully-resolved :class:`MachineConfig`
        (all lists merged with defaults, no ``None`` fields).

    Raises:
        ConfigError: On unknown ``extends`` or inheritance cycles.
    """
    resolved: dict[str, MachineConfig] = {}
    for name in cfg.configs:
        resolved[name] = _resolve_machine(name, cfg.configs, cfg.defaults, (name,))
    return resolved


__all__ = ["resolve_configs"]
