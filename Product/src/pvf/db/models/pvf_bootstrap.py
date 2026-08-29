"""Explicit registration of pvf model tables on SQLModel.metadata.

Import-time side effects are deliberately avoided: the pvf startup logic (runner,
alembic config) calls these functions so that only the models needed are loaded.

  import_core_models()      - always required framework tables
  import_feature_models()   - feature-gated tables (stripe, branding, share, external api, customer communication)
  import_all_models()       - everything; used for alembic schema probing so the
                              migrated schema stays complete regardless of which
                              features are activated at runtime

Class definition is what registers a table on SQLModel.metadata; no instantiation
of row objects is needed (or done) here.
"""
from sqlmodel import SQLModel

_core_loaded = False
_feature_loaded: set[str] = set()


def import_core_models() -> None:
    global _core_loaded
    if _core_loaded:
        return
    from . import (  # noqa: F401
        application_event_log,
        application_session_log,
        customer_user,
        email_activity_log,
        share_link_tracking,
        user_password_reset_tokens,
        user_passwords,
    )
    # watcher queue tables — always registered (framework-owned)
    from . import (  # noqa: F401
        watcher_llm_requests,
        watcher_email_requests,
        watcher_api_requests,
        watcher_generic_jobs,
    )
    _core_loaded = True
    return


def import_feature_models(*, activate_stripe_integration: bool = False, 
                          activate_branding_image_store: bool = False, 
                          activate_share_links: bool = False,
                          activate_external_api: bool = False,
                          activate_customer_communication: bool = False) -> None:
    if activate_stripe_integration and "stripe" not in _feature_loaded:
        from . import stripe_events, subscriber_transactions  # noqa: F401
        _feature_loaded.add("stripe")
    if activate_branding_image_store and "branding" not in _feature_loaded:
        from . import branding_images  # noqa: F401
        _feature_loaded.add("branding")
    if activate_share_links and "share_links" not in _feature_loaded:
        from . import share_link_tracking  # noqa: F401
        _feature_loaded.add("share_links")
    if activate_external_api and "external_api" not in _feature_loaded:
        from . import api_access_configuration  # noqa: F401
        _feature_loaded.add("external_api")
    if activate_customer_communication and "customer_communication" not in _feature_loaded:
        from . import user_communication  # noqa: F401
        _feature_loaded.add("customer_communication")

def import_watcher_models() -> None:
    """Ensure watcher queue tables are registered (idempotent)."""
    from . import (  # noqa: F401
        watcher_llm_requests,
        watcher_email_requests,
        watcher_api_requests,
        watcher_generic_jobs,
    )
    return


def import_all_models() -> None:
    import_core_models()
    import_watcher_models()
    import_feature_models(activate_stripe_integration=True, 
                          activate_branding_image_store=True,
                          activate_share_links=True,
                          activate_external_api=True,
                          activate_customer_communication=True)
    return

# note - caller is expected to define get_target_metadata for Alembic migrations
def pvf_get_target_metadata():
    """Return the SQLModel metadata for Alembic to use; usually hooked from the project ingesting this framework """
    return SQLModel.metadata
