"""pvf_app_runner — the standard, executable application runner for pvf-based applications.

Startup orchestration:
  1. load pvf_app_startup.yaml (bindings, feature switches, share vocabularies)
  2. ingest the configured env file (usually .env) with python-dotenv
  3. inject startup-owned values into pvf_settings (read-only thereafter)
  4. establish the database connection FIRST; on failure, clear diagnostics to stderr
     and exit with an error code
  5. register pvf model metadata (feature-gated)
  6. build the four FastAPI applications (noauth / session / share / external) and the
     root app; register pvf-owned routers
  7. invoke the application shell entry point with a PvfInvocation; it registers hooks
     and routers and returns None (success), an error message, or raises
  8. complete setup: include application routers, merge OpenAPI tag metadata, run the
     dependency-injection integrity check, install handlers, mount apps and static files

Run with:  fastapi dev src/pvf/pvf_app_runner.py   (or fastapi run ... for production)
The module-level `app` is the composed ASGI root application.
"""
import importlib
import json
import os
import re
import sys
from pathlib import Path
from traceback import format_exc

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .bindings.pvf_startup_config import (
    PvfStartupConfig,
    PvfStartupConfigError,
    apply_startup_config,
    apply_watcher_config,
    load_startup_config,
    load_watcher_config,
)

_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]  # pvf -> src -> workspace root
_STATIC_DIR = str(_WORKSPACE_ROOT / "static")
_STATIC_CLIENT_DIR = str(_WORKSPACE_ROOT / "static_client")


class _CachedStaticFiles(StaticFiles):
    """StaticFiles with Cache-Control appropriate to file type.

    - HTML entry points (index.html, 404.html, any *.html) → no-store, no-cache.
      This is the user-visible fix for `client 0.7.88 → server 0.7.89` banners that
      survive Reload: a cached index.html baked with the old appVersion keeps
      being served from browser disk cache unless the server forces revalidation.
    - Hashed Nuxt assets under _nuxt/ → immutable, long-lived (1y). These filenames
      contain content hashes, so a new deploy produces new URLs; long caching is safe
      and improves performance. Plain reload still re-fetches HTML (no-cache above)
      which then references the new hashed URLs.
    - Other static assets (favicon, etc.) → short public cache.
    """

    def file_response(self, full_path, stat_result, scope, status_code: int = 200):  # type: ignore[override]
        from starlette.datastructures import Headers
        from starlette.responses import FileResponse as _FileResponse

        from starlette.staticfiles import NotModifiedResponse as _NotMod

        request_headers = Headers(scope=scope)
        # Build response exactly as base class does, so etag/last-modified handling stays correct.
        response = _FileResponse(full_path, status_code=status_code, stat_result=stat_result)
        if self.is_not_modified(response.headers, request_headers):
            not_mod = _NotMod(response.headers)
            path_str = str(full_path)
            if path_str.endswith(".html"):
                not_mod.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                not_mod.headers["Pragma"] = "no-cache"
                not_mod.headers["Expires"] = "0"
            elif "_nuxt" in path_str:
                not_mod.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return not_mod
        # 200 response — inject cache policy by file type.
        path_str = str(full_path)
        if path_str.endswith(".html"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif "_nuxt" in path_str:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            # Generic static (images, fonts, etc.) — short cache; html fallback is handled above.
            # Use a modest max-age so repeat visits are fast but still refresh reasonably.
            if "Cache-Control" not in response.headers:
                response.headers["Cache-Control"] = "public, max-age=3600"
        return response

# Mount prefixes for the four FastAPI applications
MOUNT_PREFIXES = {"noauth": "/auth-ws", "session": "/ws", "share": "/ext-ws", "external": "/api"}

# Non-app paths (reserved prefixes) always return JSON 404s rather than the SPA page
RESERVED_PREFIXES = ["/ws", "/ext-ws", "/api", "/auth", "/hook-stripe-events", "/api/webhooks"]

EXIT_BAD_STARTUP_CONFIG = 2
EXIT_DATABASE_FAILED = 3
EXIT_APP_STARTUP_FAILED = 4

# The composed applications, populated by build_app(); consumed by tooling
# (OpenAPI snapshot extraction, diagnostics).
composed_apps: dict[str, FastAPI] = {}

_PVF_TAGS = {
    "noauth": [
        {"name": "auth", "description": "Services to support authentication"},
        {"name": "self-reg", "description": "Self Registration Services for Initial Signup"},
    ],
    "session": [
        {"name": "admin", "description": "Services to customer/user administration and customer/user information"},
        {"name": "context", "description": "Services to access the user/customer context and related user information"},
        {"name": "devops", "description": "Services to access and post log events for diagnostic purposes"},
    ],
    "share": [],
    "external": [
        {"name": "access_check", "description": "Signed API connectivity checks"},
    ],
}


def _fatal(message: str, exit_code: int) -> None:
    print(f"FATAL: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def _load_env_file(startup_config: PvfStartupConfig) -> None:
    """Ingest the configured env file (usually .env). Process environment wins in production.

    In non-production (SERVER_ENV != "production"), the file is reloaded with
    override=True so edits to .env override stale process env (e.g., VS Code
    Python's python.envFile / EnvironmentVariableCollection cache that injects
    old .env values into the debugger terminal). This is the user-observed
    EMAIL_LOCAL_ALLOW_DOMAINS staleness: .env had 5 entries but the process
    kept the old 4-entry export because override=False masked the file.
    """
    from dotenv import load_dotenv

    env_path = Path(startup_config.env_file)
    if not env_path.is_absolute():
        env_path = _WORKSPACE_ROOT / env_path
    if env_path.is_file():
        load_dotenv(env_path, override=False)
        # Second pass for non-prod: allow .env to win over stale terminal exports.
        # Check SERVER_ENV after the first pass (process env wins there). Default
        # to "local" if unset. Only "production" keeps process-wins semantics.
        server_env = os.environ.get("SERVER_ENV", os.environ.get("ENV", "local")).lower()
        if server_env != "production":
            load_dotenv(env_path, override=True)


def _probe_database_or_exit(db, dsn: str) -> None:
    try:
        with db.get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as ex:
        masked_dsn = re.sub(r"://([^:@/]+):([^@/]+)@", r"://\1:****@", dsn)
        _fatal(
            "could not establish a connection to the database.\n"
            f"  DSN: {masked_dsn}\n"
            f"  error: {type(ex).__name__}: {ex}",
            EXIT_DATABASE_FAILED,
        )


def _merge_openapi_specs(title: str, specs: list[tuple[str, FastAPI]]) -> dict:
    """Merge (mount_prefix, app) OpenAPI specs into one schema; paths are prefixed.

    Component name collisions are tolerated only when the schemas are identical
    (shared pvf models); conflicting definitions are a build error.
    """
    merged: dict | None = None
    for prefix, sub_app in specs:
        spec = sub_app.openapi()
        if merged is None:
            merged = {"openapi": spec["openapi"], "info": {"title": title, "version": spec["info"].get("version", "")},
                      "paths": {}, "components": {"schemas": {}}, "tags": []}
        for path, item in spec.get("paths", {}).items():
            merged["paths"][prefix + path] = item
        for name, schema in spec.get("components", {}).get("schemas", {}).items():
            existing = merged["components"]["schemas"].get(name)
            if existing is not None and existing != schema:
                raise RuntimeError(f"Conflicting OpenAPI schema definitions for '{name}' across composed apps")
            merged["components"]["schemas"][name] = schema
        seen_tags = {t["name"] for t in merged["tags"]}
        for tag in spec.get("tags", []):
            if tag["name"] not in seen_tags:
                merged["tags"].append(tag)
                seen_tags.add(tag["name"])
    return merged or {}


_sessions_openapi_cache: dict = {}


def build_sessions_openapi() -> dict:
    """The aggregate session-facing contract: root + noauth + session + share apps."""
    if not _sessions_openapi_cache:
        specs = [("", composed_apps["root"])]
        for target in ("noauth", "session", "share"):
            specs.append((MOUNT_PREFIXES[target], composed_apps[target]))
        _sessions_openapi_cache.update(_merge_openapi_specs("Session UI API", specs))
    return _sessions_openapi_cache


def build_external_openapi() -> dict:
    return composed_apps["external"].openapi()


def build_app(config_path: str | None = None) -> FastAPI:
    global composed_apps

    # 1. startup YAML
    try:
        startup_config = load_startup_config(config_path)
    except PvfStartupConfigError as ex:
        _fatal(str(ex), EXIT_BAD_STARTUP_CONFIG)

    # 2. env file (python-dotenv; process environment overrides file values)
    _load_env_file(startup_config)

    # 3. settings + read-only startup value injection
    from .config.pvf_config_settings import pvf_settings

    apply_startup_config(startup_config, pvf_settings)
    # 3b. watcher YAML (critical bindings only; optional — defaults if absent)
    try:
        watcher_config = load_watcher_config()
        apply_watcher_config(watcher_config, pvf_settings)
    except PvfStartupConfigError as ex:
        _fatal(str(ex), EXIT_BAD_STARTUP_CONFIG)
    pvf_settings.process_name = os.path.basename(__file__)

    if not pvf_settings.UNIQUE_CONFIGURATION_CHECK:
        _fatal(
            "This system appears to be running on an example or missing configuration file; "
            "check the .env contents (UNIQUE_CONFIGURATION_CHECK must be 1).",
            EXIT_BAD_STARTUP_CONFIG,
        )

    # 4. database connection first
    from .db.connect import PvfDatabaseConnection

    db = PvfDatabaseConnection()
    _probe_database_or_exit(db, pvf_settings.DB_PATH_OR_CONNECTION_STRING)

    # 4b. application schema extensions must be declared before any model import:
    # import the shell module (declarations only; no models at module level by
    # contract) and let it register added columns on pvf tables
    try:
        shell_module = importlib.import_module(startup_config.application.shell_module)
    except Exception as ex:
        _fatal(
            f"could not import application shell module '{startup_config.application.shell_module}': {ex}",
            EXIT_APP_STARTUP_FAILED,
        )
    from .db.model_factory import get_schema_extension_registry

    register_schema_extensions = getattr(shell_module, "register_schema_extensions", None)
    if callable(register_schema_extensions):
        register_schema_extensions(get_schema_extension_registry())

    # 5. pvf model metadata (feature-gated)
    from .db.models import pvf_bootstrap

    pvf_bootstrap.import_core_models()
    pvf_bootstrap.import_feature_models(
        activate_stripe_integration=pvf_settings.ACTIVATE_STRIPE_INTEGRATION,
        activate_branding_image_store=pvf_settings.ACTIVATE_BRANDING_IMAGE_STORE,
        activate_share_links=pvf_settings.ACTIVATE_SHARE_LINKS,
        activate_external_api=pvf_settings.ACTIVATE_EXTERNAL_API,
        activate_customer_communication=pvf_settings.ACTIVATE_CUSTOMER_COMMUNICATION,
    )

    # 6. build the FastAPI applications
    from .bindings.pvf_invocation import PvfAppTarget, PvfInvocation, set_current_invocation
    from .utils.fastapi_app_handlers import (
        handle_500_internal_error,
        handle_422_unprocessable_entity,
        make_spa_fallback_404_handler,
    )

    # per-app 404 defaults to JSON; the root app gets the SPA fallback below
    sub_app_exceptions: dict = {}
    if pvf_settings.PYTEST_ACTIVE is False:
        # don't handle 500 errors while testing, so complete error message is visible in pytest results
        sub_app_exceptions[500] = handle_500_internal_error

    def _make_sub_app(title: str, target: str) -> FastAPI:
        sub = FastAPI(title=title, openapi_tags=list(_PVF_TAGS[target]), exception_handlers=dict(sub_app_exceptions))

        @sub.exception_handler(RequestValidationError)
        async def _handle_422(request, exc):
            return await handle_422_unprocessable_entity(request, exc)

        return sub

    app_noauth = _make_sub_app(f"{pvf_settings.APPLICATION_NAME} Entry API", "noauth")
    app_session = _make_sub_app(f"{pvf_settings.APPLICATION_NAME} Session UI API", "session")
    app_share = _make_sub_app(f"{pvf_settings.APPLICATION_NAME} Share Link API", "share")
    app_external = _make_sub_app(f"{pvf_settings.APPLICATION_NAME} PvfCustomer API", "external")

    for browser_app in (app_noauth, app_session, app_share):
        browser_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", pvf_settings.APPLICATION_BASE_URL],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["content-disposition"],
        )

    # public liveness probe on the external app (exempt from the signed-header check)
    from fastapi import APIRouter

    external_minimal_router = APIRouter()

    @external_minimal_router.get("/status")
    async def external_status():
        return {"service": f"{pvf_settings.APPLICATION_NAME} Service PvfCustomer Facing API",
                "version": pvf_settings.PVF_VERSION,
                "status": "API Available"}

    app_external.include_router(external_minimal_router)

    # pvf-owned routers
    from .api.auth import router as auth_router
    from .api.log_events_request import router as log_events_request_router
    from .api.user_requests import noauth_router as self_reg_router, router as user_requests_router

    app_noauth.include_router(auth_router)
    app_noauth.include_router(self_reg_router)
    app_session.include_router(user_requests_router)
    app_session.include_router(log_events_request_router)

    root_exceptions = dict(sub_app_exceptions)
    root_exceptions[404] = make_spa_fallback_404_handler(_STATIC_CLIENT_DIR, RESERVED_PREFIXES)
    root_app = FastAPI(title=f"{pvf_settings.APPLICATION_NAME} Service", docs_url="/root-docs", redoc_url=None,
                       openapi_tags=[{"name": "stripe-event-hook", "description": "Capture, log, and process updates from stripe via webhook"}],
                       exception_handlers=root_exceptions)

    @root_app.exception_handler(RequestValidationError)
    async def _root_handle_422(request, exc):
        return await handle_422_unprocessable_entity(request, exc)

    # SPA host routes (/alive, /)
    from .api.hello_web import router as web_files_router

    root_app.include_router(web_files_router)

    # 7. application entry point (shell module imported above, before model registration)
    # watcher critical bindings (YAML authoritative)
    from .watcher.registry import build_registry_from_config
    watcher_registry = build_registry_from_config(watcher_config) if 'watcher_config' in locals() else build_registry_from_config(None)
    invocation = PvfInvocation(
        pvf_settings=pvf_settings,
        startup_config=startup_config,
        watcher_config=watcher_config if 'watcher_config' in locals() else None,
        watcher_registry=watcher_registry,
        watcher_types=dict(watcher_registry.watcher_types) if watcher_registry else {},
        db=db,
        app_noauth=app_noauth,
        app_session=app_session,
        app_share=app_share,
        app_external=app_external,
    )
    set_current_invocation(invocation)
    # allow app to shadow builtin handlers
    if hasattr(shell_module, "register_watcher_handlers"):
        try:
            shell_module.register_watcher_handlers(watcher_registry)  # type: ignore[attr-defined]
            invocation.watcher_registry = watcher_registry
            invocation.watcher_types = dict(watcher_registry.watcher_types)
        except Exception as ex:
            _fatal(f"register_watcher_handlers raised {type(ex).__name__}: {ex}", EXIT_APP_STARTUP_FAILED)

    entry_point = getattr(shell_module, startup_config.application.entry_point, None)
    if not callable(entry_point):
        _fatal(
            f"application shell '{startup_config.application.shell_module}' has no callable "
            f"'{startup_config.application.entry_point}'",
            EXIT_APP_STARTUP_FAILED,
        )

    try:
        startup_result = entry_point(invocation)
    except SystemExit:
        raise
    except Exception as ex:
        _fatal(
            f"application startup raised {type(ex).__name__}: {ex}\n{format_exc()}",
            EXIT_APP_STARTUP_FAILED,
        )
    if startup_result is not None:
        _fatal(f"application startup failed: {startup_result}", EXIT_APP_STARTUP_FAILED)

    from .api.app_context_views import (
        bind_client_session_context_settings,
        noauth_router as context_noauth_router,
        router as context_router,
    )
    from .api.app_post_subscriber_transactions import router as subscriber_tx_router

    if invocation.client_session_context_settings_type is not None:
        bind_client_session_context_settings(invocation.client_session_context_settings_type)
    app_noauth.include_router(context_noauth_router)
    app_session.include_router(context_router)
    app_session.include_router(subscriber_tx_router)

    if pvf_settings.ACTIVATE_STRIPE_INTEGRATION:
        from .api.hook_stripe_events import router as hook_stripe_events_router
        root_app.include_router(hook_stripe_events_router)

    if pvf_settings.ACTIVATE_BRANDING_IMAGE_STORE:
        from .api.app_branding import router as branding_router, share_router as branding_share_router
        app_session.include_router(branding_router)
        app_share.include_router(branding_share_router)

    if pvf_settings.ACTIVATE_SHARE_LINKS:
        from .api.share_link_manage import router as share_link_manage_router
        app_session.include_router(share_link_manage_router)

    if pvf_settings.ACTIVATE_EXTERNAL_API:
        from .api.api_access_management import router as api_access_management_router
        from .api.api_probe import router as api_probe_router
        app_session.include_router(api_access_management_router)
        app_external.include_router(api_probe_router)

    if pvf_settings.ACTIVATE_CUSTOMER_COMMUNICATION:
        from .api.app_user_communication import router as user_communication_router
        app_session.include_router(user_communication_router)
        
    # include application routers and merge tag metadata
    for target in PvfAppTarget:
        target_app = invocation.target_app(target)
        for registration in invocation.routers[target]:
            target_app.include_router(registration.router)
        target_app.openapi_tags.extend(invocation.openapi_tags[target])

    # 8. dependency-injection integrity (strict, regardless of endpoint parameters)
    from .utils.dependency_integrity import verify_app_dependency_integrity

    verify_app_dependency_integrity(app_noauth, "noauth")
    verify_app_dependency_integrity(app_session, "session")
    verify_app_dependency_integrity(app_share, "share")
    verify_app_dependency_integrity(app_external, "external")

    # root status (reports the application's identity/version when supplied by the shell)
    @root_app.get("/status")
    async def root_status():
        return {"service": f"{invocation.application_name or pvf_settings.APPLICATION_NAME} Service UI API",
                "version": invocation.application_version or pvf_settings.PVF_VERSION,
                "status": "API Available"}

    # aggregate session-surface contract (root + noauth + session + share)
    @root_app.get("/session/docs.json", include_in_schema=False)
    async def sessions_openapi():
        return JSONResponse(build_sessions_openapi())

    @root_app.get("/session/docs", include_in_schema=False)
    async def sessions_docs():
        return get_swagger_ui_html(openapi_url="/session/docs.json", title="Session UI API - Docs")

    # mounts: API prefixes first, static last
    root_app.mount(MOUNT_PREFIXES["external"], app_external, name="external_api")
    root_app.mount(MOUNT_PREFIXES["noauth"], app_noauth, name="noauth_api")
    root_app.mount(MOUNT_PREFIXES["session"], app_session, name="session_api")
    root_app.mount(MOUNT_PREFIXES["share"], app_share, name="share_api")

    root_app.mount("/static", _CachedStaticFiles(directory=_STATIC_DIR), name="static")
    root_app.mount("/", _CachedStaticFiles(directory=_STATIC_CLIENT_DIR), name="static_client_files")

    composed_apps = {
        "root": root_app,
        "noauth": app_noauth,
        "session": app_session,
        "share": app_share,
        "external": app_external,
    }

    from .utils.utils_show import show_vars_semi

    show_vars_semi("pvf_app_runner is running", app_name=pvf_settings.APPLICATION_NAME, pvf_vers=pvf_settings.PVF_VERSION, pid=os.getpid())
    return root_app


app = build_app()
