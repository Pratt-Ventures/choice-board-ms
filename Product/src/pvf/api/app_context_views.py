from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field, model_serializer
import json
import copy

from sqlmodel import Session

from fastapi import APIRouter, Request, Response

from ..utils.pvf_base_internal_resources import PvfClientAuthSettings, PvfWsResultPackage
from ..api.auth import PvfLogin, PvfLogin2FAChallenge, auth_request
from ..utils.login_2fa import apply_2fa_client_settings
from ..depends.api_session_dependencies import SessionDep
from ..depends.check_user_session_jwt_dependencies import UserAccessDep
from ..bindings.pvf_invocation import invocation_context, runtime_settings

from ..db.models.customer_user import PvfCustomer, PvfUser, PvfUserContext
from ..utils.log_event import log_event
from ..utils.field_encryption import decrypt_secret, is_stored_secret
from ..utils.llm_client import (
    NO_PROVIDERS_CONFIGURED,
    SUPPORTED_LLM_PROVIDERS,
    normalize_llm_provider,
    provider_is_supported,
    system_llm_configured,
    verify_llm_provider,
)

router = APIRouter()

# No-authorization routes (mounted at /auth-ws): composes the pvf auth_request
# primitive with this application's context view. The endpoint itself is defined
# below, after UserCustomerContextView.
noauth_router = APIRouter()


class ClientSessionContextSettings(PvfClientAuthSettings):
    """Placeholder replaced by bind_client_session_context_settings() before OpenAPI."""


def _parse_settings_blob(raw) -> dict:
    if raw in (None, "", "null"):
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _client_settings_defaults():
    inv = invocation_context
    if inv is not None and inv.app_client_settings is not None:
        return copy.deepcopy(inv.app_client_settings)
    settings_type = inv.client_session_context_settings_type if inv is not None else None
    if settings_type is not None:
        return settings_type()
    return PvfClientAuthSettings()


def _user_communication_available() -> bool:
    return bool(getattr(runtime_settings(), "ACTIVATE_CUSTOMER_COMMUNICATION", False))


def _ai_yaml_activated() -> bool:
    return bool(getattr(runtime_settings(), "ACTIVATE_AI_AGENTS", False))


def _ai_features_available() -> bool:
    return _ai_yaml_activated()


def _customer_llm_configured(customer) -> bool:
    if customer is None:
        return False
    try:
        return bool(customer.customer_llm_configured())
    except Exception:
        provider = str(getattr(customer, "ai_provider", "") or "").strip()
        key = decrypt_secret(getattr(customer, "ai_api_key", None) or "").strip()
        return bool(provider) and provider_is_supported(provider) and bool(key)


def _ai_providers_configured(customer=None) -> bool:
    if not _ai_yaml_activated():
        return False
    return system_llm_configured() or _customer_llm_configured(customer)


def _active_version() -> str | None:
    try:
        inv = invocation_context
        if inv is not None and getattr(inv, "application_version", None):
            return str(inv.application_version)
    except Exception:
        pass
    try:
        rs = runtime_settings()
        v = getattr(rs, "VERSION", None)
        if v:
            return str(v)
    except Exception:
        pass
    try:
        from ..config.pvf_config_settings import pvf_settings as _pvs
        v2 = getattr(_pvs, "PVF_VERSION", None)
        if v2:
            return str(v2)
    except Exception:
        pass
    return None


def _merged_client_settings(*blobs):
    merged = _client_settings_defaults()
    for raw in blobs:
        data = _parse_settings_blob(raw)
        for k, v in data.items():
            if hasattr(merged, k):
                setattr(merged, k, v)
    if hasattr(merged, "enable_user_communication"):
        merged.enable_user_communication = _user_communication_available()
    if hasattr(merged, "ai_features_enabled"):
        merged.ai_features_enabled = _ai_features_available()
    if hasattr(merged, "ai_providers_configured"):
        merged.ai_providers_configured = False
    return merged


class RequestUserCustomerContext(BaseModel):
    include_account_status: bool = Field(default=False, description="TBD Include account status information for admins")


class UpdateCustomerVoteSettingsForm(BaseModel):
    coherence_method: str | None = Field(
        default=None,
        description="Participant agreement algorithm on results: spearman | kendall",
    )

class CustomerVoteSettingsResult(PvfWsResultPackage):
    settings: ClientSessionContextSettings | None = None

class CustomerAdminInfo(BaseModel):
    customer_user_count: int = 0

class TeamMember(BaseModel):
    id: int
    name: str
    email: str
    customer_admin: bool
    created_date: datetime

class CustomerAccountStatus(BaseModel):
    credits: int = -1

class CompanyInformation(BaseModel):
    profiled_company_id: int
    profiled_company_name: str

class UserCustomerContextView(PvfWsResultPackage):
    context_timestamp: datetime = Field(description="Time the context was generated; should be reloaded after a modest period")
    user_id: int = Field(description="system assigned user identifier")
    name: str  = Field(description="PvfUser's full name as provided")
    email: str = Field(default=None, description="Email address (and login key) in the user profile")
    is_customer_admin: bool = Field(default=False, description="indicates if the current user session is a customer_admin")
    customer_id: int = Field(default=-1, description="system assigned id when customer was created")
    customer_name: str | None = Field(default=None, description="customer's business name")
    customer_email: str | None = Field(default=None, description="provided email for the customer level")
    stripe_customer_id: str | None = Field(default=None, description="Indicates customer number associated with stripe/account setup")
    trial_expiration_days: int | None = Field(default=None, description="If the customer is on a trial account, indicates the number of days remaining in the trial period")
    stripe_callback_prefix: str | None = Field(default=None, description="Prefix for stripe callback URLs associated with the customer")
    stripe_callback_prefix_sandbox: str | None = Field(default=None, description="Prefix for stripe callback URLs associated with the customer in sandbox mode (forces livemode False)")
    user_record: PvfUser = Field(default=None, description="current user's user profile record")
    customer_record: PvfCustomer = Field(default=None, description="current user's customer profile record")
    team_info: list[TeamMember] | None = Field(default=None, description="A list of team members in the current company")
    settings: ClientSessionContextSettings | None = Field(default=None, description="A dict of key-value pairs for client settings; from global config_client, with potential customer or user overrides")
    server_version: str | None = Field(default=None, description="Active server application version")
    client_version: str | None = Field(default=None, description="Expected client build version (matches server active version)")

    @model_serializer(mode="wrap")
    def _serialize_masked_context(self, serializer):
        data = serializer(self)
        masked_fields = list(runtime_settings().CONTEXT_MASKED_FIELDS or [])
        for extra in ("ai_api_key",):
            if extra not in masked_fields:
                masked_fields.append(extra)
        if not masked_fields:
            return data
        for record_key in ("user_record", "customer_record"):
            record = data.get(record_key)
            if not isinstance(record, dict):
                continue
            for field_name in masked_fields:
                record.pop(field_name, None)
        return data

@noauth_router.post("/login-and-get-context",
             summary="Create access and refresh tokens for user session and return session settings/context",
             tags=['auth', 'context'])
def auth_with_context(response: Response, request: Request, session: SessionDep, login: PvfLogin) -> UserCustomerContextView | PvfLogin2FAChallenge:
    user_result = auth_request(response=response, request=request, session=session, login=login, return_user_info=True)
    if isinstance(user_result, PvfLogin2FAChallenge):
        return user_result
    return get_user_customer_context(session=session, usr_context=PvfUserContext(authenticated_login=True, sess_user=user_result, remote_ip=request.client.host, url_path=request.url.path), context_request=RequestUserCustomerContext(include_account_status=True))

@router.post('/core/get-user-customer-context',
              summary='Return overall user/customer context information and settings',
              description="Return information regarding the user, customer, and general team information to support client user experience",
              tags=["context"])
def req_get_user_customer_context(session: SessionDep, usr_context: UserAccessDep, context_request: RequestUserCustomerContext) -> UserCustomerContextView:
    return get_user_customer_context(session=session, usr_context=usr_context, context_request=context_request)

def get_user_customer_context(session: Session, usr_context: PvfUser, context_request: RequestUserCustomerContext) -> UserCustomerContextView:

    if usr_context.sess_customer is None:
        cur_customer = PvfCustomer.get_customer_by_id_system(session=session, id=usr_context.sess_user.customer_id)
        if cur_customer is None:
            log_event(f'PvfCustomer id {usr_context.sess_user.customer_id} not found for current user {usr_context.sess_user.id}', severity=3,
                    usr_context=usr_context, raise_exception=True)
            # note raise - this is a serious problem, user exists without customer
        usr_context.sess_customer = cur_customer
    else:
        cur_customer = usr_context.sess_customer

    trial_expiration_days = None
    if cur_customer.customer_account in (None, "") and cur_customer.trial_expiration_date is not None:
        check_expiration_date = cur_customer.trial_expiration_date
        check_expiration_date = check_expiration_date.astimezone(timezone.utc)

        check_trial_expiration_days = (check_expiration_date - datetime.now(timezone.utc)).days
        if check_trial_expiration_days >= 0:
            trial_expiration_days = check_trial_expiration_days

    _active = _active_version()
    context_view = UserCustomerContextView(context_timestamp=datetime.now(timezone.utc),
                                             user_id=usr_context.sess_user.id,
                                             name=usr_context.sess_user.name,
                                             email=usr_context.sess_user.email,
                                             customer_id=usr_context.sess_user.customer_id,
                                             # Enable this instead to allow legacy client to go direct to dashboard during trial...
                                             # stripe_customer_id=usr_context.sess_customer.customer_account if trial_expiration_days is None else f'Trial active {trial_expiration_days} days',
                                             stripe_customer_id=usr_context.sess_customer.customer_account,
                                             stripe_callback_prefix=runtime_settings().STRIPE_CALLBACK_PREFIX,
                                             stripe_callback_prefix_sandbox=runtime_settings().STRIPE_CALLBACK_PREFIX_SANDBOX,
                                             trial_expiration_days=trial_expiration_days,
                                             is_customer_admin=usr_context.sess_user.customer_admin,
                                             user_record=usr_context.sess_user,
                                             customer_record=cur_customer,
                                             server_version=_active,
                                             client_version=_active,
                                             )
    context_view.customer_name = cur_customer.customer_name
    context_view.customer_email = cur_customer.customer_email
    context_view.settings = _merged_client_settings(
        cur_customer.client_settings,
        usr_context.sess_user.client_settings,
    )
    if hasattr(context_view.settings, "ai_providers_configured"):
        context_view.settings.ai_providers_configured = _ai_providers_configured(cur_customer)
    apply_2fa_client_settings(context_view.settings, usr_context.sess_user, cur_customer)

    account_users_check = PvfUser.get_account_users(session=session, usr_context=usr_context)
    if account_users_check.failure_reason != '':
        context_view.failure_reason = account_users_check.failure_reason
        context_view.log_id = account_users_check.log_id
        return context_view

    context_view.team_info = []
    for account_user_row in account_users_check.user_info_list:
        context_view.team_info.append(TeamMember(id=account_user_row.id,
                                                 name=account_user_row.name,
                                                 email=account_user_row.email,
                                                 customer_admin=account_user_row.customer_admin,
                                                 created_date=account_user_row.create_date))
    return context_view


@router.post(
    "/core/update-customer-vote-settings",
    summary="Admin: update customer-level compare/results settings",
    tags=["context"],
)
def update_customer_vote_settings(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: UpdateCustomerVoteSettingsForm,
) -> CustomerVoteSettingsResult:
    if not usr_context.sess_user.customer_admin:
        log_id = log_event(
            "Non-admin attempted to update customer vote settings",
            usr_context=usr_context,
            severity=3,
        )
        return CustomerVoteSettingsResult(failure_reason="PvfCustomer admin access required", log_id=log_id)

    customer = usr_context.sess_customer
    if customer is None:
        customer = PvfCustomer.get_customer_by_id_system(
            session=session, id=usr_context.sess_user.customer_id, clear_lock=False
        )
    if customer is None:
        return CustomerVoteSettingsResult(failure_reason="PvfCustomer not found")

    data = _parse_settings_blob(customer.client_settings)
    # Strip retired SoftMax / triple-frame knobs
    if form.coherence_method is not None:
        m = str(form.coherence_method).strip().lower()
        data["coherence_method"] = m if m in ("spearman", "kendall") else "spearman"
    customer.client_settings = json.dumps(data) if data else None
    customer.update_customer_system(session=session, clear_lock=False)
    merged = _merged_client_settings(customer.client_settings, usr_context.sess_user.client_settings)
    apply_2fa_client_settings(merged, usr_context.sess_user, customer)
    return CustomerVoteSettingsResult(settings=merged)


class CustomerAiSettingsForm(BaseModel):
    ai_provider: str | None = Field(default=None, description="opencode_go, opencode_zen, or openrouter")
    ai_model: str | None = Field(default=None, description="Default model identifier for this customer")
    ai_api_key: str | None = Field(default=None, description="Authorization key; send stored encoded value to leave unchanged, blank to clear")


class CustomerAiSettingsResult(PvfWsResultPackage):
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_api_key: str | None = None
    key_configured: bool = False
    system_provider_configured: bool = False
    providers: list[str] = Field(default_factory=lambda: list(SUPPORTED_LLM_PROVIDERS))


class TestCustomerAiConnectionForm(BaseModel):
    ai_provider: str
    ai_api_key: str | None = None
    ai_model: str | None = None


class TestCustomerAiConnectionResult(PvfWsResultPackage):
    ok: bool = False
    models: list[dict] = Field(default_factory=list)
    provider: str | None = None


class LlmAvailableModelsResult(PvfWsResultPackage):
    source: str | None = None
    provider: str | None = None
    default_model: str | None = None
    default_is_system: bool = False
    models: list[dict] = Field(default_factory=list)


def _require_customer_admin(usr_context) -> str | None:
    if not usr_context.sess_user.customer_admin:
        log_event(
            "Non-admin attempted to update customer AI settings",
            usr_context=usr_context,
            severity=3,
        )
        return "PvfCustomer admin access required"
    return None


def _load_session_customer(session: Session, usr_context) -> PvfCustomer | None:
    customer = usr_context.sess_customer
    if customer is None:
        customer = PvfCustomer.get_customer_by_id_system(
            session=session, id=usr_context.sess_user.customer_id, clear_lock=False
        )
    return customer


def _ai_settings_view(customer: PvfCustomer) -> CustomerAiSettingsResult:
    stored_key = customer.ai_api_key or ""
    return CustomerAiSettingsResult(
        ai_provider=customer.ai_provider or None,
        ai_model=customer.ai_model or None,
        ai_api_key=stored_key,
        key_configured=bool(customer.decrypted_ai_api_key().strip()),
        system_provider_configured=system_llm_configured(),
        providers=list(SUPPORTED_LLM_PROVIDERS),
    )


def _resolve_submitted_key(customer: PvfCustomer, submitted: str | None) -> str:
    value = "" if submitted is None else str(submitted)
    stored = customer.ai_api_key or ""
    if value == stored or is_stored_secret(value):
        return customer.decrypted_ai_api_key()
    return value


@router.get(
    "/core/customer-ai-settings",
    summary="Admin: read customer LLM provider, model, and encoded key",
    tags=["context"],
)
def get_customer_ai_settings(
    session: SessionDep,
    usr_context: UserAccessDep,
) -> CustomerAiSettingsResult:
    if not _ai_yaml_activated():
        return CustomerAiSettingsResult(failure_reason="AI features are not enabled")
    denied = _require_customer_admin(usr_context)
    if denied:
        return CustomerAiSettingsResult(failure_reason=denied)
    customer = _load_session_customer(session, usr_context)
    if customer is None:
        return CustomerAiSettingsResult(failure_reason="PvfCustomer not found")
    return _ai_settings_view(customer)


@router.post(
    "/core/customer-ai-settings",
    summary="Admin: update customer LLM provider, model, and authorization key",
    tags=["context"],
)
def update_customer_ai_settings(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: CustomerAiSettingsForm,
) -> CustomerAiSettingsResult:
    if not _ai_yaml_activated():
        return CustomerAiSettingsResult(failure_reason="AI features are not enabled")
    denied = _require_customer_admin(usr_context)
    if denied:
        return CustomerAiSettingsResult(failure_reason=denied)
    customer = _load_session_customer(session, usr_context)
    if customer is None:
        return CustomerAiSettingsResult(failure_reason="PvfCustomer not found")
    provider = str(form.ai_provider or "").strip()
    if provider:
        provider = normalize_llm_provider(provider)
        if not provider_is_supported(provider):
            return CustomerAiSettingsResult(failure_reason="Unsupported LLM provider")
        customer.ai_provider = provider
    else:
        customer.ai_provider = None
    customer.ai_model = (str(form.ai_model or "").strip() or None)
    customer.apply_ai_api_key_update(form.ai_api_key)
    customer.update_customer_system(session=session, clear_lock=False)
    return _ai_settings_view(customer)


@router.post(
    "/core/test-customer-ai-connection",
    summary="Admin: test LLM provider credentials and list available models",
    tags=["context"],
)
def test_customer_ai_connection(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: TestCustomerAiConnectionForm,
) -> TestCustomerAiConnectionResult:
    if not _ai_yaml_activated():
        return TestCustomerAiConnectionResult(failure_reason="AI features are not enabled")
    denied = _require_customer_admin(usr_context)
    if denied:
        return TestCustomerAiConnectionResult(failure_reason=denied)
    customer = _load_session_customer(session, usr_context)
    if customer is None:
        return TestCustomerAiConnectionResult(failure_reason="PvfCustomer not found")
    provider = normalize_llm_provider(form.ai_provider)
    if not provider_is_supported(provider):
        return TestCustomerAiConnectionResult(failure_reason="Unsupported LLM provider")
    key = _resolve_submitted_key(customer, form.ai_api_key)
    if not key:
        return TestCustomerAiConnectionResult(failure_reason=NO_PROVIDERS_CONFIGURED)
    verified = verify_llm_provider(provider, key, form.ai_model)
    return TestCustomerAiConnectionResult(
        ok=bool(verified.get("ok")),
        models=list(verified.get("models") or []),
        provider=verified.get("provider") or provider,
        failure_reason="" if verified.get("ok") else (verified.get("error") or "Provider authorization failed"),
    )


@router.get(
    "/core/llm-available-models",
    summary="Admin: list models from the resolved customer or system LLM provider",
    tags=["context"],
)
def llm_available_models(
    session: SessionDep,
    usr_context: UserAccessDep,
) -> LlmAvailableModelsResult:
    if not _ai_yaml_activated():
        return LlmAvailableModelsResult(failure_reason="AI features are not enabled")
    denied = _require_customer_admin(usr_context)
    if denied:
        return LlmAvailableModelsResult(failure_reason=denied)
    customer = _load_session_customer(session, usr_context)
    if customer is None:
        return LlmAvailableModelsResult(failure_reason="PvfCustomer not found")
    if _customer_llm_configured(customer):
        provider = normalize_llm_provider(customer.ai_provider)
        key = customer.decrypted_ai_api_key()
        default_model = str(customer.ai_model or "").strip() or None
        source = "pvf_customer"
        default_is_system = False
    elif system_llm_configured():
        s = runtime_settings()
        provider = normalize_llm_provider(getattr(s, "AI_SERVICE", "opencode_go"))
        key = str(getattr(s, "AI_API_KEY", "") or "").strip()
        default_model = str(getattr(s, "AI_MODEL", "") or "").strip() or None
        source = "system"
        default_is_system = True
    else:
        return LlmAvailableModelsResult(failure_reason=NO_PROVIDERS_CONFIGURED)
    verified = verify_llm_provider(provider, key, default_model)
    if not verified.get("ok"):
        return LlmAvailableModelsResult(
            source=source,
            provider=provider,
            default_model=default_model,
            default_is_system=default_is_system,
            failure_reason=verified.get("error") or "Provider authorization failed",
        )
    return LlmAvailableModelsResult(
        source=source,
        provider=provider,
        default_model=default_model,
        default_is_system=default_is_system,
        models=list(verified.get("models") or []),
    )


def bind_client_session_context_settings(settings_type: type) -> None:
    """Point context/vote-settings fields at the application type and rebuild schemas."""
    if settings_type is None:
        return
    annotation = settings_type | None
    for model in (UserCustomerContextView, CustomerVoteSettingsResult):
        model.model_fields["settings"].annotation = annotation
        model.__annotations__["settings"] = annotation
        model.model_rebuild(force=True)

