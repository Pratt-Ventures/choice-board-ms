"""PvfInvocation — the binding contract between pvf_app_runner and the application shell.

The runner builds this object and passes it to the application entry point named in
pvf_app_startup.yaml. The application is expected to:
  1. create its own settings object (typically subclassing PvfGlobalSettings) and call
     pvf.config.pvf_startup_config.merge_pvf_settings_into() to receive startup-owned values
  2. import its model modules (registering table metadata)
  3. register any hooks connecting framework internals to application logic
  4. add its routers via add_router() targeted at the appropriate FastAPI app
  5. optionally extend openapi_tags and set application_version
The entry point returns None on success, or an error message string on failure; it may
also raise descriptive exceptions to signal startup failure.
"""
from enum import StrEnum
from typing import Any, Callable

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, ConfigDict, Field

from ..config.pvf_config_settings import PvfGlobalSettings, pvf_settings
from ..utils.pvf_base_internal_resources import PvfClientAuthSettings

class PvfAppTarget(StrEnum):
    """The four FastAPI applications composed by pvf_app_runner."""
    noauth = "noauth"        # no authorization expected: login, password reset, self registration
    session = "session"      # logged-in session (JWT cookie) endpoints
    share = "share"          # share link access (cookie / magic-key gate, no session JWT)
    external = "external"    # external API (signed headers)


class RouterRegistration(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    router: APIRouter
    target: PvfAppTarget


class PvfResolvedEntity(BaseModel):
    """Result of the application's entity_resolver hook."""
    display_name: str | None = None
    customer_id: int | None = None


class PvfHookRegistry(BaseModel):
    """Hooks connecting pvf internals to application-specific logic.

    Applications fill these in during startup. All hooks are optional unless a feature
    that needs them is activated in pvf_app_startup.yaml.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Entities: resolve an application entity (the thing a share or branding image
    # references) for validation, tenancy checks, and display naming.
    # Signature: (session, usr_context, entity_id) -> PvfResolvedEntity | None
    entity_resolver: Callable | None = None
    # Share links: map a share type (object action) to the outbound email type used for
    # invitations, or None to skip. Signature: (share_type: str) -> str | Enum | None
    share_type_email_dispatcher: Callable | None = None
    # Share links: map a share type to the outbound email type used when a project
    # administrator resends an existing invitation. Signature matches the dispatcher.
    share_resend_email_dispatcher: Callable | None = None
    # Share links: valid access operations per share type. {share_type: [operation, ...]}
    share_action_matrix: dict[str, list[str]] = Field(default_factory=dict)
    # Share links: operations that mutate state (require an established cookie session).
    share_mutating_operations: list[str] = Field(default_factory=list)
    # Share links: enrich activity rows with application stats.
    # Signature: (session, shares: list) -> dict[int, dict] mapping share id -> extra fields
    share_activity_enricher: Callable | None = None
    # Share links: add application fields to share email template params.
    # Signature: (share_link, base_params: dict) -> dict
    share_email_params_enricher: Callable | None = None
    # External API: per webhook type, build the callback payload and decide readiness.
    # payload_builder signature: (session, event) -> dict
    # readiness_predicate signature: (session, event) -> bool
    webhook_payload_builders: dict[str, Callable] = Field(default_factory=dict)
    webhook_readiness_predicates: dict[str, Callable] = Field(default_factory=dict)


from ..db.model_factory import PvfSchemaExtensionRegistry, get_schema_extension_registry


# Forward reference to watcher registry to avoid circular import at module load;
# the runner populates this after constructing PvfInvocation.
def _default_watcher_registry():
    try:
        from ..watcher.registry import PvfWatcherRegistry
        return PvfWatcherRegistry()
    except Exception:
        return None


class PvfInvocation(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    pvf_settings: PvfGlobalSettings = None          # PvfGlobalSettings (active, startup values applied)
    startup_config: Any = None        # PvfStartupConfig as loaded from pvf_app_startup.yaml
    db: Any = None                    # PvfDatabaseConnection (engine already verified)
    app_noauth: FastAPI | None = None
    app_session: FastAPI | None = None
    app_share: FastAPI | None = None
    app_external: FastAPI | None = None
    app_settings: BaseModel | None = None        # live app settings; recommended to have pvf settings merged in
    app_client_settings: BaseModel | None = None  # live default client-session settings instance
    # Informational; surfaced by the root /status endpoint.
    application_name: str | None = None
    application_version: str | None = None
    client_session_context_settings_type: type | None = None

    routers: dict[PvfAppTarget, list[RouterRegistration]] = Field(
        default_factory=lambda: {target: [] for target in PvfAppTarget}
    )
    openapi_tags: dict[PvfAppTarget, list[dict]] = Field(
        default_factory=lambda: {target: [] for target in PvfAppTarget}
    )
    hooks: PvfHookRegistry = Field(default_factory=PvfHookRegistry)
    schema_extensions: PvfSchemaExtensionRegistry = Field(default_factory=get_schema_extension_registry)
    # Watcher queue registry — populated from pvf_app_watcher.yaml + app_shell.register_watcher_handlers
    watcher_registry: Any = Field(default_factory=_default_watcher_registry, description="PvfWatcherRegistry instance")
    watcher_types: dict = Field(default_factory=dict, description="WatcherTypeSpec dict mirroring registry.watcher_types")
    watcher_config: Any = Field(default=None, description="PvfWatcherConfig as loaded from pvf_app_watcher.yaml")

    def add_router(self, target: PvfAppTarget, router: APIRouter) -> None:
        """Register an application router for inclusion in the given FastAPI app.

        Dependency injection is strictly enforced at composition time by the runner's
        integrity check, regardless of whether the dependency data is an input parameter
        for a given endpoint; see pvf.utils.dependency_integrity.
        """
        self.routers[PvfAppTarget(target)].append(RouterRegistration(router=router, target=PvfAppTarget(target)))

    def target_app(self, target: PvfAppTarget) -> FastAPI:
        return {
            PvfAppTarget.noauth: self.app_noauth,
            PvfAppTarget.session: self.app_session,
            PvfAppTarget.share: self.app_share,
            PvfAppTarget.external: self.app_external,
        }[PvfAppTarget(target)]


# The runner records the active invocation here so pvf internals (share gate, webhook
# delivery, ...) can reach registered hooks at request time without importing the app.
invocation_context: PvfInvocation = None

def set_current_invocation(invocation: PvfInvocation | None) -> None:
    global invocation_context
    invocation_context = invocation


def get_current_invocation() -> PvfInvocation | None:
    return invocation_context


def get_hooks() -> PvfHookRegistry:
    invocation = invocation_context
    return invocation.hooks if invocation is not None else PvfHookRegistry()


def runtime_settings() -> BaseModel:
    """Active settings for pvf request paths: the app instance when bound, else pvf_settings."""
    invocation = invocation_context
    if invocation is not None and invocation.app_settings is not None:
        return invocation.app_settings
    return pvf_settings

