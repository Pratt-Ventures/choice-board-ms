"""Watcher type registry — attached to PvfInvocation as watcher_registry.

Flow:
  1. Runner loads src/pvf_app_watcher.yaml → PvfWatcherConfig.types (kind: pvf auto-registered)
  2. Runner builds PvfInvocation.watcher_registry from those builtins
  3. Runner calls app_shell.register_watcher_handlers(registry)
  4. App may shadow a builtin type (duplicate → app handler shadows builtin, logged, not double-registered)

The registry maps work_type → (module, entry, kind, description). Builtins + generic fallback
all participate; poll_and_dispatch iterates over registered types plus implicit generic work_types
seen in watcher_generic_jobs.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from pydantic import BaseModel, Field

from ..bindings.pvf_startup_config import PvfWatcherConfig, WatcherTypeSpec

logger = logging.getLogger(__name__)


class PvfWatcherRegistryEntry(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    work_type: str
    kind: str  # pvf | app
    module: str
    entry: str
    description: str | None = None
    # resolved callable (populated at registration time for validation)
    handler: Callable | None = None


class PvfWatcherRegistry(BaseModel):
    """Registry of watcher handler bindings."""

    model_config = {"arbitrary_types_allowed": True}
    entries: dict[str, PvfWatcherRegistryEntry] = Field(default_factory=dict)
    watcher_types: dict[str, WatcherTypeSpec] = Field(default_factory=dict)

    def register(self, work_type: str, spec: WatcherTypeSpec | dict[str, Any], *, allow_shadow: bool = True) -> bool:
        """Register one type. Returns True if registered, False if shadowed built-in and not allowed.

        If `work_type` already exists and `allow_shadow` is True, the new spec shadows the old
        (app shadows builtin). Logged at startup per prompt §3.
        """
        if isinstance(spec, dict):
            spec = WatcherTypeSpec.model_validate(spec)
        existing = self.entries.get(work_type)
        if existing is not None:
            if existing.module == spec.module and existing.entry == spec.entry:
                return True
            if not allow_shadow:
                logger.warning("duplicate watcher type %r already registered by %s; skipping %s", work_type, existing.module, spec.module)
                return False
            logger.warning("overrode builtin handler for type %r: %s -> %s", work_type, existing.module, spec.module)
        # Validate importability at registration time (fail-fast)
        handler = None
        try:
            mod = importlib.import_module(spec.module)
            handler = getattr(mod, spec.entry, None)
            if not callable(handler):
                logger.warning("watcher type %r handler %s.%s not callable", work_type, spec.module, spec.entry)
                handler = None
        except Exception as ex:
            logger.warning("watcher type %r failed to import %s.%s: %s", work_type, spec.module, spec.entry, ex)
            handler = None
        entry = PvfWatcherRegistryEntry(
            work_type=work_type,
            kind=spec.kind,
            module=spec.module,
            entry=spec.entry,
            description=spec.description,
            handler=handler,
        )
        self.entries[work_type] = entry
        self.watcher_types[work_type] = spec
        return True

    def register_many(self, types: dict[str, WatcherTypeSpec]) -> None:
        for wt, spec in (types or {}).items():
            self.register(wt, spec, allow_shadow=False)

    def get(self, work_type: str) -> PvfWatcherRegistryEntry | None:
        return self.entries.get(work_type)

    def all_types(self) -> list[str]:
        return list(self.entries.keys())

    def resolve_handler(self, work_type: str) -> Callable | None:
        """Resolve work_type to a callable, importing on demand if needed."""
        entry = self.entries.get(work_type)
        if entry is None:
            return None
        if entry.handler is not None and callable(entry.handler):
            return entry.handler
        try:
            mod = importlib.import_module(entry.module)
            h = getattr(mod, entry.entry, None)
            if callable(h):
                entry.handler = h
                return h
        except Exception as ex:
            logger.warning("watcher resolve failed for %r: %s", work_type, ex)
        return None


def build_registry_from_config(cfg: PvfWatcherConfig | None) -> PvfWatcherRegistry:
    """Build a registry seeded from PvfWatcherConfig (builtins)."""
    reg = PvfWatcherRegistry()
    if cfg and cfg.types:
        reg.register_many(cfg.types)
    return reg
