"""pvf_services — the single non-REST entry point for applications built on pvf.

All standard services an application needs from the framework outside of REST
endpoint handling are re-exported here. Applications should import from this module
rather than reaching into pvf internals (see pvf/README.md).
"""

from ..config.pvf_config_settings import PvfGlobalSettings, pvf_settings

from ..db.connect import PvfDatabaseConnection
from ..db.model_factory import (
    PvfAddedColumn,
    PvfSchemaExtensionError,
    PvfSchemaExtensionRegistry,
    apply_extra_fields,
)
from ..db.models.pvf_bootstrap import import_all_models, pvf_get_target_metadata
from ..depends.api_session_dependencies import SessionDep, get_next_session, get_session
from ..depends.check_user_session_jwt_dependencies import (
    UserAccessDep,
    UserAccessDepCustomerAdmin,
    UserAccessDepSystemAdmin,
)
from ..depends.check_api_key_dependencies import WebServiceDep
from .pvf_startup_config import (
    PvfStartupConfig,
    PvfWatcherConfig,
    WatcherTypeSpec,
    find_watcher_config_path,
    load_startup_config,
    load_watcher_config,
    merge_pvf_settings_into,
    normalize_str_list,
)

__version__ = pvf_settings.PVF_VERSION

from ..api.auth import PvfLogin, PvfLogin2FAChallenge, auth_request
from ..api.request_types.auth import CustomerSelfRegUserInfoForm, CustomerUserCreateResult
from ..utils.login_2fa import (
    apply_2fa_client_settings,
    login_2fa_customer_controllable,
    login_2fa_optional,
    login_2fa_required,
    normalize_login_2fa_mode,
)
from ..api.share_link_manage import (
    PvfShareAccessConfirmed_Base,
    PvfShareAccessDenied_Base,
    PvfShareAccessRequest,
    PvfShareAccessRequest_Base,
    build_share_landing_url,
    get_token_cookie,
    make_token_cookie,
    share_link_validate_and_log,
)
from ..db.models.api_access_configuration import PvfApiWebInvocationEvent
from .pvf_invocation import (
    PvfAppTarget,
    PvfClientAuthSettings,
    PvfHookRegistry,
    PvfInvocation,
    PvfResolvedEntity,
    get_current_invocation,
    get_hooks,
    runtime_settings,
)
from ..utils.auth_tokens import create_access_token
from ..utils.log_event import log_event
from ..utils.outbound_mail_queue import send_outbound_mail
from ..utils.populate_test_customer_and_user import populate_test_customer_and_user
from ..utils.pvf_base_internal_resources import (
    PvfAuthRelatedOutboundEmailType,
    PvfLogSeverity,
    PvfTokenPayload,
    PvfTokenSchema,
    PvfWsResultPackage,
    get_random_baseN_value,
    set_update_field,
)
from ..utils.utils_general import get_hex_hash_from_args, make_activation_string
from ..utils.webcalls_and_hooks import Webrequest, WebrequestSignature
from ..utils.field_encryption import decrypt_secret, encrypt_secret, is_stored_secret
from ..utils.llm_client import (
    LlmError,
    NO_PROVIDERS_CONFIGURED,
    SUPPORTED_LLM_PROVIDERS,
    normalize_llm_provider,
    query_llm_model,
    system_llm_configured,
    verify_llm_provider,
)
from ..watcher.orchestration import (
    PvfWatcherInvocation,
    PvfWatcherEventOrchestration,
    PvfWatcherInvocationResult,
    PvfWatcherStatus,
    is_no_log_tag,
    prompt_hash_for_messages,
    redact_for_no_log,
    should_capture,
)
from ..watcher.registry import PvfWatcherRegistry

enqueue_callback = PvfApiWebInvocationEvent.enqueue_callback_event

# Watcher queue bindings — the public app surface for all queue types.
# Importing here registers them as the single entry point (see pvf/README.md).
from ..bindings.pvf_watcher_requests import (  # noqa: F401,E402
    get_api_request,
    get_email_request,
    get_generic_request,
    get_llm_request,
    list_api_requests,
    list_email_requests,
    list_generic_requests,
    list_llm_requests,
    queue_api_request,
    queue_email_request,
    queue_generic_request,
    queue_llm_request,
)

_LAZY_ATTRS = {
    "PvfApiAccessConfiguration": ("..db.models.api_access_configuration", "PvfApiAccessConfiguration"),
    "PvfCustomer": ("..db.models.customer_user", "PvfCustomer"),
    "PvfCustomerBrandingImage": ("..db.models.branding_images", "PvfCustomerBrandingImage"),
    "PvfProjectBrandingImage": ("..db.models.branding_images", "PvfProjectBrandingImage"),
    "PvfShareLink": ("..db.models.share_link_tracking", "PvfShareLink"),
    "PvfShareLinkMagicKey": ("..db.models.share_link_tracking", "PvfShareLinkMagicKey"),
    "PvfUser": ("..db.models.customer_user", "PvfUser"),
    "PvfUserContext": ("..db.models.customer_user", "PvfUserContext"),
    "PvfUserPasswordReset": ("..db.models.user_password_reset_tokens", "PvfUserPasswordReset"),
}


def __getattr__(name: str):
    spec = _LAZY_ATTRS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = spec
    from importlib import import_module
    return getattr(import_module(module_name, __package__), attr_name)


__all__ = [
    "PvfApiAccessConfiguration",
    "PvfAuthRelatedOutboundEmailType",
    "PvfCustomer",
    "PvfCustomerBrandingImage",
    "CustomerSelfRegUserInfoForm",
    "CustomerUserCreateResult",
    "PvfDatabaseConnection",
    "PvfLogin",
    "PvfLogin2FAChallenge",
    "PvfLogSeverity",
    "PvfProjectBrandingImage",
    "PvfAddedColumn",
    "PvfAppTarget",
    "PvfClientAuthSettings",
    "PvfGlobalSettings",
    "PvfHookRegistry",
    "PvfInvocation",
    "PvfResolvedEntity",
    "PvfSchemaExtensionError",
    "PvfSchemaExtensionRegistry",
    "PvfStartupConfig",
    "PvfWatcherConfig",
    "PvfWatcherRegistry",
    "PvfWatcherInvocation",
    "PvfWatcherEventOrchestration",
    "PvfWatcherInvocationResult",
    "PvfWatcherStatus",
    "SessionDep",
    "PvfShareAccessConfirmed_Base",
    "PvfShareAccessDenied_Base",
    "PvfShareAccessRequest",
    "PvfShareAccessRequest_Base",
    "PvfShareLink",
    "PvfShareLinkMagicKey",
    "PvfTokenPayload",
    "PvfTokenSchema",
    "PvfUser",
    "UserAccessDep",
    "UserAccessDepCustomerAdmin",
    "UserAccessDepSystemAdmin",
    "PvfUserContext",
    "PvfUserPasswordReset",
    "WebServiceDep",
    "Webrequest",
    "WebrequestSignature",
    "PvfWsResultPackage",
    "apply_2fa_client_settings",
    "apply_extra_fields",
    "auth_request",
    "build_share_landing_url",
    "create_access_token",
    "decrypt_secret",
    "encrypt_secret",
    "enqueue_callback",
    "is_stored_secret",
    "LlmError",
    "NO_PROVIDERS_CONFIGURED",
    "normalize_llm_provider",
    "query_llm_model",
    "SUPPORTED_LLM_PROVIDERS",
    "system_llm_configured",
    "verify_llm_provider",
    "get_current_invocation",
    "get_hex_hash_from_args",
    "get_hooks",
    "get_next_session",
    "get_random_baseN_value",
    "get_session",
    "get_token_cookie",
    "import_all_models",
    "load_startup_config",
    "log_event",
    "login_2fa_customer_controllable",
    "login_2fa_optional",
    "login_2fa_required",
    "make_activation_string",
    "make_token_cookie",
    "merge_pvf_settings_into",
    "normalize_login_2fa_mode",
    "normalize_str_list",
    "populate_test_customer_and_user",
    "pvf_get_target_metadata",
    "pvf_settings",
    "runtime_settings",
    "send_outbound_mail",
    "set_update_field",
    "share_link_validate_and_log",
    "queue_llm_request",
    "get_llm_request",
    "list_llm_requests",
    "queue_email_request",
    "get_email_request",
    "list_email_requests",
    "queue_api_request",
    "get_api_request",
    "list_api_requests",
    "queue_generic_request",
    "get_generic_request",
    "list_generic_requests",
    "is_no_log_tag",
    "should_capture",
    "redact_for_no_log",
    "prompt_hash_for_messages",
]
