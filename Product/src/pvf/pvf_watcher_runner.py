"""Canonical watcher runner — framework-owned, app shim delegates here.

Usage:
  python -m src.pvf.watcher.runner
  # or via shim:
  python -m src.powerchoice_watcher

Loads startup + watcher YAML, merges settings, establishes DB, registers watcher registry,
calls app_shell.register_app_hooks + register_watcher_handlers, sets current invocation,
then blocks in pvf.watcher.service.run_watcher_forever.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

from .bindings.pvf_startup_config import apply_startup_config, apply_watcher_config, load_startup_config, load_watcher_config
from .utils import utils_show as ut

_startup_config = load_startup_config()

from dotenv import load_dotenv  # noqa: E402  # after startup_config

_env_path = Path(_startup_config.env_file)
if not _env_path.is_absolute():
    _env_path = Path(__file__).resolve().parents[3] / _env_path
if _env_path.is_file():
    load_dotenv(_env_path, override=False)
    if os.environ.get("SERVER_ENV", os.environ.get("ENV", "local")).lower() != "production":
        load_dotenv(_env_path, override=True)

from .config.pvf_config_settings import pvf_settings as settings  # noqa: E402

apply_startup_config(_startup_config, settings)
_watcher_config = load_watcher_config()
apply_watcher_config(_watcher_config, settings)
settings.process_name = os.path.basename(__file__)

from .db.connect import PvfDatabaseConnection  # noqa: E402
from .db.models import pvf_bootstrap  # noqa: E402
from .bindings.pvf_invocation import PvfInvocation, set_current_invocation  # noqa: E402
from .watcher.registry import build_registry_from_config  # noqa: E402
from .watcher.service import run_watcher_forever  # noqa: E402


def build_invocation() -> PvfInvocation:
    """Build invocation with DB and watcher registry; idempotent for tests."""
    db = PvfDatabaseConnection()
    pvf_bootstrap.import_all_models()
    importlib.import_module(_startup_config.application.models_module)
    shell_module = importlib.import_module(_startup_config.application.shell_module)

    # Build registry from YAML, then let app intercept/shadow
    registry = build_registry_from_config(_watcher_config)

    invocation = PvfInvocation(
        pvf_settings=settings,
        startup_config=_startup_config,
        watcher_config=_watcher_config,
        db=db,
        watcher_registry=registry,
        watcher_types=dict(registry.watcher_types),
    )
    # Legacy hooks (callback payload builders, etc.)
    if hasattr(shell_module, "register_app_hooks"):
        shell_module.register_app_hooks(invocation.hooks)
    # New watcher handlers
    if hasattr(shell_module, "register_watcher_handlers"):
        try:
            shell_module.register_watcher_handlers(registry)
            # Sync back to invocation fields
            invocation.watcher_registry = registry
            invocation.watcher_types = dict(registry.watcher_types)
        except Exception as ex:
            ut.show_vars_semi(f'watcher runner — register_watcher_handlers raised {type(ex).__name__}: {ex}')

    set_current_invocation(invocation)
    return invocation


def main() -> None:
    invocation = build_invocation()
    # Expose watcher_config on invocation for poll/service
    run_watcher_forever(invocation)


if __name__ == "__main__":
    main()
