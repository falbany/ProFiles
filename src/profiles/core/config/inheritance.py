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

    def pick_str_list(field: str) -> list[str]:
        """Merge a ``list[str]`` field: local (first, deduped) then inherited."""
        local = getattr(cfg, field)
        inherited = getattr(base, field) if base is not None else None
        if local is not None and field in cfg.model_fields_set:
            return _merge_str(list(inherited or []), local)
        return list(inherited or [])

    def pick_row_colors() -> list[RowColor]:
        """Merge ``row_colors``: local rules first, then inherited (deduped)."""
        local = cfg.row_colors
        inherited = base.row_colors if base is not None else None
        if local is not None and "row_colors" in cfg.model_fields_set:
            return _merge_row(list(inherited or []), local)
        return list(inherited or [])

    def pick_match() -> MatchCriteriaSchema:
        """Return the local ``match`` block, falling back to the inherited one."""
        if "match" in cfg.model_fields_set:
            return cfg.match
        return base.match if base is not None else MatchCriteriaSchema()

    def pick_scan() -> list[str]:
        """Return the local ``scan`` list, falling back to the inherited one."""
        if "scan" in cfg.model_fields_set:
            return cfg.scan
        return base.scan if base is not None else []

    max_depth = (
        cfg.max_search_depth
        if "max_search_depth" in cfg.model_fields_set
        else base.max_search_depth
        if base is not None
        else None
    )
    recursive = (
        cfg.recursive_search
        if "recursive_search" in cfg.model_fields_set
        else base.recursive_search
        if base is not None
        else None
    )

    return MachineConfig(
        name=cfg.name,
        extends=cfg.extends,
        match=pick_match(),
        scan=pick_scan(),
        extensions=_merge_str(defaults.extensions, pick_str_list("extensions")),
        filters=_merge_str(defaults.filters, pick_str_list("filters")),
        row_colors=_merge_row(defaults.row_colors, pick_row_colors()),
        search_exclude_files=_merge_str(
            defaults.search_exclude_files, pick_str_list("search_exclude_files")
        ),
        max_search_depth=max_depth if max_depth is not None else defaults.max_search_depth,
        recursive_search=recursive if recursive is not None else defaults.recursive_search,
        search_exclude_dirs=_merge_str(
            defaults.search_exclude_dirs, pick_str_list("search_exclude_dirs")
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
