"""pvf.watcher — framework-owned watcher service package.

Exposes orchestration types, registry, and poll/service entry points.
Application code should never import from pvf internals; instead use
src.pvf.bindings.pvf_watcher_requests and register handlers via
PvfInvocation.watcher_registry / register_watcher_handlers.

Only src/pvf/ may import from this package directly; applications use bindings.
"""
from .orchestration import (  # noqa: F401
    PvfWatcherInvocation,
    PvfWatcherEventOrchestration,
    PvfWatcherInvocationResult,
    PvfWatcherStatus,
    is_no_log_tag,
    redact_for_no_log,
    should_capture,
)
from .registry import PvfWatcherRegistry, WatcherTypeSpec  # noqa: F401

__all__ = [
    "PvfWatcherInvocation",
    "PvfWatcherEventOrchestration",
    "PvfWatcherInvocationResult",
    "PvfWatcherStatus",
    "PvfWatcherRegistry",
    "WatcherTypeSpec",
    "is_no_log_tag",
    "redact_for_no_log",
    "should_capture",
]
