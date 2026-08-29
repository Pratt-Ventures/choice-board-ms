"""Loader and model for pvf_app_startup.yaml — the deployment-fixed startup configuration.

The YAML file lives at the application's src root and declares:
  - the application shell module / entry point invoked by pvf_app_runner
  - the env file name (usually .env)
  - feature switches that require application logic to interface (stripe, branding,
    share links, external api) — these are injected into pvf settings read-only
  - share link vocabularies (object actions / access operations)
  - the models module used for alembic schema probing

Only the startup logic (pvf_app_runner, pvf_get_alembic_config) may apply these
values to settings; see PvfGlobalSettings._inject_startup_values.
"""
from enum import Enum
from os import environ
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

# env var override, honored first (used by tests and multi-app development)
STARTUP_CONFIG_ENV_VAR = "PVF_STARTUP_CONFIG"
STARTUP_CONFIG_FILENAME = "pvf_app_startup.yaml"
WATCHER_CONFIG_ENV_VAR = "PVF_WATCHER_CONFIG"
WATCHER_CONFIG_FILENAME = "pvf_app_watcher.yaml"


def normalize_str_list(value: Any) -> list[str]:
    """Normalize enums, comma-separated strings, or mixed iterables to a list of plain strings.

    Applications may define enums for clarity and pass either the enum members or raw
    strings; internally the framework works with lists of strings (same pattern as
    outbound email types).
    """
    if value is None:
        return []
    if isinstance(value, (str, Enum)):
        value = [value]
    result: list[str] = []
    for item in value:
        if isinstance(item, Enum):
            item = item.value
        for token in str(item).split(","):
            token = token.strip()
            if token:
                result.append(token)
    return result


class PvfStartupApplicationConfig(BaseModel):
    shell_module: str = "src.app_shell"          # module loaded as the application bridge
    entry_point: str = "app_startup"             # callable(shell_module) receiving PvfInvocation
    models_module: str = "src.db.models.bootstrap"  # imports all app table specs (alembic probe)


class PvfStartupFeaturesConfig(BaseModel):    # ALLOWED IN YAML
    activate_stripe_integration: bool = False
    activate_branding_image_store: bool = False
    activate_share_links: bool = True
    activate_external_api: bool = True
    activate_customer_communication: bool = True
    activate_ai_agents: bool = False


class PvfStartupShareConfig(BaseModel):   # ALLOWED IN YAML
    object_actions: list[str] = ["not_set"]      # share types the application supports
    access_operations: list[str] = ["not_set"]   # operations journalable per share

    @field_validator("object_actions", "access_operations", mode="before")
    @classmethod
    def _normalize(cls, value):
        return normalize_str_list(value)


class PvfStartupConfig(BaseModel):       # FULL YAML SPEC
    application: PvfStartupApplicationConfig = PvfStartupApplicationConfig()
    env_file: str = ".env"
    features: PvfStartupFeaturesConfig = PvfStartupFeaturesConfig()
    share: PvfStartupShareConfig = PvfStartupShareConfig()


# --- Watcher config (pvf_app_watcher.yaml — critical bindings only) --------------

class WatcherTypeSpec(BaseModel):
    """One entry under `types:` in pvf_app_watcher.yaml."""
    kind: str = Field(description="pvf = framework builtin, app = application handler")
    module: str = Field(description="Python module containing the handler")
    entry: str = Field(description="Callable name inside module")
    description: str | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def _normalize_kind(cls, v):
        k = str(v or "").strip().lower()
        if k not in ("pvf", "app"):
            raise ValueError(f"kind must be 'pvf' or 'app', got {v!r}")
        return k


class PvfWatcherConfig(BaseModel):
    """Deployment-fixed watcher critical bindings (YAML authoritative)."""
    version: int = 1
    capture_payloads: bool = Field(default=True, description="Mirrors PvfGlobalSettings.WATCHER_CAPTURE_PAYLOADS")
    no_log_request_types: list[str] = Field(default_factory=list, description="Semantic tags/work_types never detailed-logged, even on error")
    types: dict[str, WatcherTypeSpec] = Field(default_factory=dict, description="Bound watcher types (builtin pvf + app-declared)")

    @field_validator("no_log_request_types", mode="before")
    @classmethod
    def _normalize_no_log(cls, v):
        return normalize_str_list(v)


class PvfStartupConfigError(RuntimeError):
    """Raised when the startup YAML is missing or invalid; message is operator-facing."""


def find_startup_config_path() -> Path:
    """Locate pvf_app_startup.yaml: env var override first, else the src root
    (the parent of the pvf package)."""
    override = environ.get(STARTUP_CONFIG_ENV_VAR)
    if override:
        return Path(override).resolve()
    src_root = Path(__file__).resolve().parents[2]  # config -> pvf -> src
    return src_root / STARTUP_CONFIG_FILENAME


def find_watcher_config_path() -> Path:
    """Locate pvf_app_watcher.yaml: env var override first, else the src root."""
    override = environ.get(WATCHER_CONFIG_ENV_VAR)
    if override:
        return Path(override).resolve()
    src_root = Path(__file__).resolve().parents[2]
    return src_root / WATCHER_CONFIG_FILENAME


def load_startup_config(config_path: str | Path | None = None) -> PvfStartupConfig:
    path = Path(config_path).resolve() if config_path else find_startup_config_path()
    if not path.is_file():
        raise PvfStartupConfigError(
            f"Startup configuration file not found: {path}\n"
            f"Create {STARTUP_CONFIG_FILENAME} at the application src root, or set "
            f"{STARTUP_CONFIG_ENV_VAR} to its path."
        )
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as ex:
        raise PvfStartupConfigError(f"Startup configuration {path} is not valid YAML: {ex}") from ex
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise PvfStartupConfigError(f"Startup configuration {path} must be a YAML mapping at the top level.")
    try:
        return PvfStartupConfig.model_validate(raw)
    except ValueError as ex:
        raise PvfStartupConfigError(f"Startup configuration {path} is invalid: {ex}") from ex


def merge_pvf_settings_into(app_settings, pvf_settings_obj=None) -> None:
    """Merge the active pvf_settings startup-owned values into the application's settings.

    Applications typically build their GlobalSettings on PvfGlobalSettings and call this
    once at the top of their startup entry point, so the application settings instance
    carries the same read-only YAML-owned values the framework injected into pvf_settings.
    """
    if pvf_settings_obj is None:
        from ..config.pvf_config_settings import pvf_settings as pvf_settings_obj
    values = {
        name: getattr(pvf_settings_obj, name)
        for name in app_settings._STARTUP_VALUE_NAMES
    }
    app_settings._inject_startup_values(values)
    return


def apply_startup_config(config: PvfStartupConfig, settings_obj) -> None:
    """Inject startup-owned values into a PvfGlobalSettings instance (read-only thereafter).

    This is the single write path for the settings ClassVar dummies; .env and process
    environment cannot supply them.
    """
    settings_obj._inject_startup_values({
        "ACTIVATE_STRIPE_INTEGRATION": config.features.activate_stripe_integration,
        "ACTIVATE_BRANDING_IMAGE_STORE": config.features.activate_branding_image_store,
        "ACTIVATE_SHARE_LINKS": config.features.activate_share_links,
        "ACTIVATE_EXTERNAL_API": config.features.activate_external_api,
        "ACTIVATE_CUSTOMER_COMMUNICATION": config.features.activate_customer_communication,
        "ACTIVATE_AI_AGENTS": config.features.activate_ai_agents,
        "SHARE_OBJECT_ACTIONS": list(config.share.object_actions),
        "SHARE_ACCESS_OPERATIONS": list(config.share.access_operations),
    })


def load_watcher_config(config_path: str | Path | None = None) -> PvfWatcherConfig:
    """Load pvf_app_watcher.yaml (critical watcher bindings only).

    Returns an empty default config if the file does not exist — watcher still
    runs with built-in defaults so existing deployments without the file keep
    working. Callers that require the file can check `find_watcher_config_path().is_file()`.
    """
    path = Path(config_path).resolve() if config_path else find_watcher_config_path()
    if not path.is_file():
        return PvfWatcherConfig()
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as ex:
        raise PvfStartupConfigError(f"Watcher configuration {path} is not valid YAML: {ex}") from ex
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise PvfStartupConfigError(f"Watcher configuration {path} must be a YAML mapping at the top level.")
    try:
        return PvfWatcherConfig.model_validate(raw)
    except ValueError as ex:
        raise PvfStartupConfigError(f"Watcher configuration {path} is invalid: {ex}") from ex


def apply_watcher_config(config: PvfWatcherConfig, settings_obj) -> None:
    """Apply watcher YAML values that need runtime visibility.

    Currently no ClassVar injection is needed — capture_payloads and no_log
    are consulted via the loaded PvfWatcherConfig plus PvfGlobalSettings union.
    This hook exists so the runner/alembic can call a single place and to
    allow future startup-owned watcher values without changing call sites.
    """
    # Store the loaded config on the settings object for runtime access if desired
    object.__setattr__(settings_obj, "_watcher_config", config)
    return
