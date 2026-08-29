"""Re-export watcher LLM table and ensure metadata registration via pvf_bootstrap."""
from ...watcher.models import PvfWatcherLlmRequest  # noqa: F401

__all__ = ["PvfWatcherLlmRequest"]
