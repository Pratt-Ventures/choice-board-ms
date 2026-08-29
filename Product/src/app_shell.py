"""PowerChoice application shell — the bridge between pvf_app_runner and the application.

Named in pvf_app_startup.yaml (application.shell_module / application.entry_point).
The entry point receives the PvfInvocation, wires application settings, models, hooks,
and routers into it, and returns None on success (or an error message on failure).
"""
from .pvf.bindings.pvf_invocation import PvfAppTarget, PvfInvocation

_OPENAPI_TAGS_SESSION = [
    {
        "name": "powerchoice_session_api",
        "description": "Session Based web service operations for **PowerChoice Service** - UI focused API for single page application and specialized applications.",
        "externalDocs": {
            "description": "See Also: Toolkit Request API Documentation Endpoint",
            "url": "{base_url}/api/docs",
        },
    },
    {"name": "manage-projects", "description": "Services to manage customer defined projects"},
    {"name": "manage-project-content", "description": "Services to manage project alternatives, factors/criteria, and factor templates"},
    {"name": "api-keys", "description": "Services to manage customer assigned API keys bound to applications"},
    {"name": "dashboard", "description": "Services to access the general dashboard purposes"},
    {"name": "share", "description": "Authenticated services to create and manage project share links"},
    {"name": "project-votes", "description": "Logged-in voting sessions, observations, and project report analytics"},
    {"name": "user-communication", "description": "PvfUser Communication — submit and review bug reports and suggestions"},
    {"name": "deprecated", "description": "Calls that are pending deprecation - see notes for alternatives"},
    {"name": "test-helpers", "description": "Testing only. Endpoints used by automated and e2e tests; not registered in production."},
]

_OPENAPI_TAGS_SHARE = [
    {"name": "share_ext", "description": "External (cookie/magic-key) access to shared project vote, status, and report views"},
]

_OPENAPI_TAGS_EXTERNAL = [
    {
        "name": "powerchoice_toolkit_api",
        "description": "Toolkit Request API access to PowerChoice Service",
        "externalDocs": {
            "description": "See Also: Session Based API Documentation Endpoint",
            "url": "{base_url}/session/docs",
        },
    },
    {"name": "general", "description": "Retrieve defined projects and other toolkit details"},
    {"name": "callback_examples", "description": "Examples of callback payload configurations"},
]


def register_app_hooks(hooks) -> None:
    """Register PowerChoice hooks on a PvfHookRegistry.

    Called by app_startup (server process) and by the watcher process, which runs
    separately and needs the same application bindings (webhook payload builders, etc.).
    """
    from .utils.base_classes_and_enums import OutboundEmailType
    from .db.models.customer_projects import CustomerProject
    from .db.models.project_vote_events import ProjectVoteParticipant
    from .pvf.bindings.pvf_invocation import PvfResolvedEntity

    def powerchoice_entity_resolver(session, usr_context, entity_id: int) -> PvfResolvedEntity | None:
        """Resolve a CustomerProject for pvf share/branding validation, tenancy, and naming."""
        customer_id = usr_context.sess_user.customer_id if usr_context and usr_context.sess_user else None
        if customer_id is None:
            return None
        project = CustomerProject.get_customer_project_by_id_system(session=session, customer_id=customer_id, id=entity_id, clear_lock=False)
        if project is None:
            return None
        return PvfResolvedEntity(display_name=project.project_title or project.project_tag, customer_id=project.customer_id)

    _SHARE_EMAIL_TYPES = {
        "vote": OutboundEmailType.share_project_vote,
        "vote_view": OutboundEmailType.share_project_vote_view,
        "report": OutboundEmailType.share_project_report,
    }

    def share_activity_enricher(session, usr_context, shares: list) -> dict[int, dict]:
        """Participant/observation counts per share for the activity endpoints."""
        from sqlmodel import select
        from sqlalchemy import func

        stats: dict[int, dict] = {}
        share_ids = [share.id for share in shares]
        if not share_ids:
            return stats
        for share_id in share_ids:
            stats[int(share_id)] = {"participant_count": 0, "observation_count": 0}
        vote_rows = session.exec(
            select(
                ProjectVoteParticipant.share_id,
                func.count(ProjectVoteParticipant.id),
                func.coalesce(func.sum(ProjectVoteParticipant.comparison_count), 0),
            )
            .where(
                ProjectVoteParticipant.customer_id == usr_context.sess_user.customer_id,
                ProjectVoteParticipant.share_id.in_(share_ids),
                ProjectVoteParticipant.deleted_date.is_(None),
            )
            .group_by(ProjectVoteParticipant.share_id)
        ).all()
        for share_id, part_count, obs_sum in vote_rows:
            if share_id is not None:
                stats[int(share_id)] = {"participant_count": int(part_count or 0), "observation_count": int(obs_sum or 0)}
        return stats

    hooks.entity_resolver = powerchoice_entity_resolver
    hooks.share_type_email_dispatcher = _SHARE_EMAIL_TYPES.get
    hooks.share_resend_email_dispatcher = lambda _share_type: OutboundEmailType.resending_invitation
    hooks.share_action_matrix = {
        share_type: ["vote", "view", "report"]
        for share_type in ("vote", "vote_view", "report")
    }
    hooks.share_mutating_operations = ["vote"]
    hooks.share_activity_enricher = share_activity_enricher


def register_watcher_handlers(registry) -> None:
    """Register PowerChoice watcher handlers — called after builtin YAML registration.

    Populates PvfWatcherRegistry with app-specific semantic tags. May shadow a
    builtin type (log at startup, do not double-register).
    """
    from .pvf.bindings.pvf_startup_config import WatcherTypeSpec

    # Example: concise label generation via generic queue (dedicated+generic both exercised)
    registry.register(
        "SHORTEN_PRODUCT_NAME",
        WatcherTypeSpec(kind="app", module="src.app.watcher_handlers", entry="shorten_product_name", description="Application semantic tag; participates in no_log filtering when listed"),
        allow_shadow=True,
    )
    # Additional app types can be registered here without YAML changes:
    # registry.register("MY_BATCH", WatcherTypeSpec(kind="app", module="src.app.watcher_handlers", entry="my_batch_handler"))


def app_startup(invocation: PvfInvocation) -> str | None:
    """PowerChoice startup entry point called by pvf_app_runner with the PvfInvocation."""
    # 1. application settings (subclass of PvfGlobalSettings) + startup value merge
    from .config.config_settings import settings
    from .config.config_client import ClientSettings, client_settings
    from .pvf.bindings.pvf_startup_config import merge_pvf_settings_into

    merge_pvf_settings_into(settings)
    invocation.app_settings = settings
    invocation.app_client_settings = client_settings
    invocation.client_session_context_settings_type = ClientSettings
    invocation.application_name = settings.APPLICATION_NAME
    invocation.application_version = settings.VERSION
    
    # 2. register application table metadata (also the alembic probe models_module)
    from .db.models import bootstrap  # noqa: F401

    # 3. application startup tasks: seed system shared templates; sample data outside prod
    from .pvf.bindings.pvf_services import get_next_session, log_event, populate_test_customer_and_user
    from .utils.bootstrap_system_templates import bootstrap_system_shared_templates

    try:
        with get_next_session() as session:
            bootstrap_system_shared_templates(session)
    except Exception as ex:
        log_event(
            f"app_startup: bootstrap_system_shared_templates failed: {ex}",
            severity=2,
            ex_info=ex,
        )

    if settings.is_prod() is False and settings.BOOTSTRAP_SAMPLE_DATA:
        populate_test_customer_and_user(get_next_session())

    # 4. application hooks binding pvf internals to PowerChoice logic
    register_app_hooks(invocation.hooks)

    # 5. application routers targeted at the appropriate FastAPI apps
    from .api.app_customer_project_management import router as app_customer_project_router
    from .api.app_customer_project_content_management import router as app_customer_project_content_router
    from .api.app_dashboard_views import router as app_entries_views_router
    from .api.app_shared_link_ext_access import router as app_shared_link_ext_access_router
    from .api.app_project_vote_events import router as app_project_vote_events_router
    from .api.api_probe_customer_status import router as api_probe_services_router
    from .api.analytic_tracking import external_router as analytic_tracking_external_router
    from .api.analytic_tracking import noauth_router as analytic_tracking_noauth_router

    invocation.add_router(PvfAppTarget.session, app_customer_project_router)
    invocation.add_router(PvfAppTarget.session, app_customer_project_content_router)
    invocation.add_router(PvfAppTarget.session, app_entries_views_router)
    invocation.add_router(PvfAppTarget.session, app_project_vote_events_router)
    invocation.add_router(PvfAppTarget.share, app_shared_link_ext_access_router)
    invocation.add_router(PvfAppTarget.external, api_probe_services_router)
    # Analytic tracking: unauthenticated, no session — served on /api and alias on /auth-ws
    # External mount handles GET /api/_public/analytic-tracking (primary, consistent with spec)
    # Noauth alias handles GET /auth-ws/_public/analytic-tracking
    invocation.add_router(PvfAppTarget.external, analytic_tracking_external_router)
    invocation.add_router(PvfAppTarget.noauth, analytic_tracking_noauth_router)

    # Testing only. Endpoints used by automated and e2e tests; not registered in production.
    if settings.is_prod() is False:
        from .api.test_helpers import router as test_helpers_router

        invocation.add_router(PvfAppTarget.session, test_helpers_router)

    # 6. application OpenAPI tag metadata (merged by the runner)
    def _with_base_url(tags: list[dict]) -> list[dict]:
        return [
            {**tag, "externalDocs": {**tag["externalDocs"], "url": tag["externalDocs"]["url"].format(base_url=settings.APPLICATION_BASE_URL)}}
            if "externalDocs" in tag else tag
            for tag in tags
        ]

    invocation.openapi_tags[PvfAppTarget.session].extend(_with_base_url(_OPENAPI_TAGS_SESSION))
    invocation.openapi_tags[PvfAppTarget.share].extend(_with_base_url(_OPENAPI_TAGS_SHARE))
    invocation.openapi_tags[PvfAppTarget.external].extend(_with_base_url(_OPENAPI_TAGS_EXTERNAL))

    return None
