"""Watcher service — run_watcher_forever with signal handling preserved from powerchoice_watcher.py:107.

Consumed by both the slimmed app shim (src/powerchoice_watcher.py) and the sample runner.
"""
from __future__ import annotations

import atexit
import signal
import os
import time
import logging

from ..config.pvf_config_settings import pvf_settings as settings
from ..utils import utils_show as ut

logger = logging.getLogger(__name__)

default_signal_handlers: dict = dict(atexit='atexit')
shutdown_processed: bool = False


def shutdown_processing(signal=None, frame=None):
    global shutdown_processed, default_signal_handlers
    if not shutdown_processed:
        ut.show_vars_semi(f'watcher - shutdown signal {signal}; Instance {settings.environment_name}; pid {os.getpid()}')
        shutdown_processed = True
    orig_handler = default_signal_handlers.get(signal)
    if orig_handler in ('atexit',):
        pass
    elif callable(orig_handler):
        orig_handler(signal, frame)
    else:  # SIG_DFL
        try:
            ut.show_vars_semi(f'watcher - shutdown_processing_deregister_and_kill {signal}; pid {os.getpid()}')
            signal_signal = signal  # type: ignore
            import signal as _sig
            _sig.signal(signal_signal, orig_handler)  # type: ignore
            os.kill(os.getpid(), signal_signal)  # type: ignore
        except Exception:
            pass
    return


def _install_signal_handlers():
    global default_signal_handlers
    atexit.register(shutdown_processing, signal='atexit', frame=None)
    default_signal_handlers[signal.SIGTERM] = signal.signal(signal.SIGTERM, shutdown_processing)
    default_signal_handlers[signal.SIGINT] = signal.signal(signal.SIGINT, shutdown_processing)
    default_signal_handlers[signal.SIGABRT] = signal.signal(signal.SIGABRT, shutdown_processing)
    if settings.PLATFORM_LINUX in (1, True, '1', "true", "True", "TRUE", 't', 'T'):
        try:
            signal.signal(signal.SIGQUIT, shutdown_processing)
            signal.signal(signal.SIGHUP, shutdown_processing)
        except Exception:
            pass
    else:
        try:
            default_signal_handlers[signal.SIGBREAK] = signal.signal(signal.SIGBREAK, shutdown_processing)  # type: ignore[attr-defined]
        except Exception:
            pass


def run_watcher_forever(invocation, *, poll_interval_busy: float | None = None, poll_interval_idle: float | None = None) -> None:
    """Main watcher loop — blocks forever (or until signal).

    `invocation` must have `watcher_registry` and be set as current invocation.
    Uses invocation.db (PvfDatabaseConnection) and the registry to poll_and_dispatch.
    """
    from ..depends.api_session_dependencies import get_next_session
    from .poll import poll_and_dispatch

    _install_signal_handlers()

    busy = poll_interval_busy if poll_interval_busy is not None else float(getattr(settings, "WATCHER_SHORTER_BUSY_POLL_SLEEP", 1.0) or 1.0)
    idle_base = poll_interval_idle if poll_interval_idle is not None else float(getattr(settings, "WATCHER_LONGER_IDLE_INCREASING_POLL_SLEEP", 5.0) or 5.0)
    exp = float(getattr(settings, "WATCHER_POLL_EXPONENTIAL_FACTOR", 1.2) or 1.2)
    max_sleep = float(getattr(settings, "WATCHER_POLL_MAXIMUM_SLEEP_TIME", 30.0) or 30.0)

    registry = getattr(invocation, "watcher_registry", None)
    # Build display list
    type_names = list(registry.all_types()) if registry and hasattr(registry, "all_types") else []
    ut.show_vars_semi('watcher started', monitor=', '.join(type_names) or 'no types registered', poll_wait_busy=busy, poll_wait_idle=f'>={idle_base}')

    idle_count = 0
    while True:
        # exponential backoff when idle
        if idle_count < max(1, len(type_names) if type_names else 1):
            wait = busy
        else:
            wait = idle_base * (exp ** max(0, idle_count - max(1, len(type_names) if type_names else 1)))
        time.sleep(min(max_sleep, wait))

        did_work = False
        try:
            with get_next_session() as session:
                did_work = poll_and_dispatch(session, registry)
        except Exception as ex:
            logger.exception("watcher poll_and_dispatch raised")
            ut.show_vars_semi(f'watcher - poll error {type(ex).__name__}: {ex}')
            # Backoff on error
            idle_count = min(idle_count + 1, 100)
            continue

        if did_work:
            idle_count = 0
        else:
            idle_count = min(idle_count + 1, 100)
