"""PowerChoice app watcher handlers — examples for generic queue.

Registered via app_shell.register_watcher_handlers. These run inside the watcher
process off the request thread, receiving PvfWatcherInvocation and returning
PvfWatcherInvocationResult.

The framework never imports this module directly; the watcher_registry loads it
by spec.module + entry from pvf_app_watcher.yaml / register_watcher_handlers.
"""
from __future__ import annotations

import re

from src.pvf.watcher.orchestration import PvfWatcherInvocationResult


def shorten_product_name(inv) -> PvfWatcherInvocationResult:
    """Example app handler for semantic_tag SHORTEN_PRODUCT_NAME.

    Generic work_type handler that shortens a product name. Used to prove
    dedicated+generic path both have a live caller without needing AI.

    Expects inv.request_package = {"product_name": str, "max_len": int|None}
    """
    try:
        pkg = inv.request_package or {}
        name = str(pkg.get("product_name") or pkg.get("title") or pkg.get("name") or "").strip()
        if not name:
            # Also check raw row's request_package JSON
            row = inv.row or {}
            rp = row.get("request_package") or {}
            name = str(rp.get("product_name") or rp.get("title") or "").strip()
        if not name:
            return PvfWatcherInvocationResult(failure_reason="product_name required", error_package={"message": "product_name required", "retryable": False}, retryable=False)
        max_len = pkg.get("max_len")
        try:
            max_len = int(max_len) if max_len is not None else 20
        except Exception:
            max_len = 20
        # Simple shorten: take first max_len chars, avoid breaking words harshly
        short = name.strip()
        if len(short) > max_len:
            # Prefer cutting at word boundary
            cut = short[: max_len].rstrip()
            # If next char is not space and cut contains space, backtrack to last space
            if len(short) > max_len and short[max_len] != " " and " " in cut:
                cut = cut.rsplit(" ", 1)[0]
            short = cut.strip()
        # Remove trailing punctuation
        short = re.sub(r"[.,;:!]+$", "", short)
        return PvfWatcherInvocationResult(
            failure_reason="",
            result_package={"short_name": short, "original": name, "semantic_tag": inv.semantic_tag or "SHORTEN_PRODUCT_NAME"},
        )
    except Exception as ex:
        return PvfWatcherInvocationResult(failure_reason=f"{type(ex).__name__}: {ex}", error_package={"message": str(ex), "retryable": False}, retryable=False)


# Future app handlers can be added here and registered in src/app_shell.register_watcher_handlers
# Example:
# def my_batch_handler(inv) -> PvfWatcherInvocationResult: ...
