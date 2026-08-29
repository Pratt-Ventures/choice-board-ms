from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...pvf.bindings.pvf_services import (
    NO_PROVIDERS_CONFIGURED,
    normalize_llm_provider,
    system_llm_configured,
)

_PLACEHOLDER_KEYS = {"", "specify in .env", "<specify>", "changeme"}
DEFAULT_MODEL_KEY = "__default__"


def _runtime_settings() -> Any:
    try:
        from ...pvf.bindings.pvf_invocation import runtime_settings

        settings = runtime_settings()
        if settings is not None:
            return settings
    except Exception:
        pass
    from ...config.config_settings import settings

    return settings


def _app_settings() -> Any:
    from ...config.config_settings import settings

    return settings


def _pvf_settings() -> Any:
    from ...pvf.config.pvf_config_settings import pvf_settings

    return pvf_settings


def _setting(name: str, default: Any = None, settings_obj: Any | None = None) -> Any:
    sources = [settings_obj, _runtime_settings(), _app_settings(), _pvf_settings()]
    for src in sources:
        if src is None:
            continue
        if hasattr(src, name):
            value = getattr(src, name)
            if value not in (None, ""):
                return value
    return default


def yaml_ai_activated(settings_obj: Any | None = None) -> bool:
    if settings_obj is not None and bool(getattr(settings_obj, "ACTIVATE_AI_AGENTS", False)):
        return True
    return bool(
        getattr(_runtime_settings(), "ACTIVATE_AI_AGENTS", False)
        or getattr(_app_settings(), "ACTIVATE_AI_AGENTS", False)
        or getattr(_pvf_settings(), "ACTIVATE_AI_AGENTS", False)
    )


def ai_features_enabled(settings_obj: Any | None = None) -> bool:
    return yaml_ai_activated(settings_obj)


def ai_unavailable_message() -> str:
    return "AI features are not enabled"


def no_providers_message() -> str:
    return NO_PROVIDERS_CONFIGURED


def ai_service_name(settings_obj: Any | None = None) -> str:
    return normalize_llm_provider(_setting("AI_SERVICE", "opencode_go", settings_obj))


def ai_model_name(settings_obj: Any | None = None) -> str:
    return str(_setting("AI_MODEL", "glm-5.2", settings_obj) or "glm-5.2").strip() or "glm-5.2"


def ai_api_key(settings_obj: Any | None = None) -> str:
    return str(_setting("AI_API_KEY", "", settings_obj) or "").strip()


def ai_http_timeout_seconds(settings_obj: Any | None = None) -> float:
    try:
        return max(1.0, float(_setting("AI_HTTP_TIMEOUT_SECONDS", 30, settings_obj) or 30))
    except (TypeError, ValueError):
        return 30.0


def ai_http_retries(settings_obj: Any | None = None) -> int:
    try:
        return max(0, min(8, int(_setting("AI_HTTP_RETRIES", 3, settings_obj) or 3)))
    except (TypeError, ValueError):
        return 3


def ai_max_concurrent_projects(settings_obj: Any | None = None) -> int:
    try:
        return max(1, min(20, int(_setting("AI_MAX_CONCURRENT_PROJECTS", 2, settings_obj) or 2)))
    except (TypeError, ValueError):
        return 2


def ai_max_pairs_per_project(settings_obj: Any | None = None) -> int:
    try:
        return max(1, min(5000, int(_setting("AI_MAX_PAIRS_PER_PROJECT", 500, settings_obj) or 500)))
    except (TypeError, ValueError):
        return 500


def ai_pairs_per_tick(settings_obj: Any | None = None) -> int:
    try:
        return max(1, min(200, int(_setting("AI_PAIRS_PER_TICK", 20, settings_obj) or 20)))
    except (TypeError, ValueError):
        return 20


def ai_skip_rate_abort(settings_obj: Any | None = None) -> float:
    try:
        v = float(_setting("AI_SKIP_RATE_ABORT", 0.25, settings_obj) or 0.25)
    except (TypeError, ValueError):
        v = 0.25
    return max(0.05, min(0.9, v))


def ai_rewrite_option_max_tokens(settings_obj: Any | None = None) -> int:
    try:
        return max(100, min(4000, int(_setting("AI_REWRITE_OPTION_MAX_TOKENS", 1200, settings_obj) or 1200)))
    except (TypeError, ValueError):
        return 1200


def ai_rewrite_factor_max_tokens(settings_obj: Any | None = None) -> int:
    try:
        return max(100, min(4000, int(_setting("AI_REWRITE_FACTOR_MAX_TOKENS", 1200, settings_obj) or 1200)))
    except (TypeError, ValueError):
        return 1200


def is_default_model_key(model_key: str | None) -> bool:
    raw = str(model_key or "").strip().lower()
    return raw in ("", DEFAULT_MODEL_KEY, "default", "ai:default", "ai:system", "system")


def normalize_model_key(model_key: str | None) -> str:
    if is_default_model_key(model_key):
        return DEFAULT_MODEL_KEY
    return str(model_key or "").strip()


def unique_voter_models(raw: Any) -> list[str]:
    items = raw if isinstance(raw, list) else []
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = normalize_model_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


@dataclass(frozen=True)
class LlmCredentials:
    provider: str
    model: str
    api_key: str
    source: str
    model_key: str
    display_name: str


def customer_llm_configured(customer: Any | None) -> bool:
    if customer is None:
        return False
    if hasattr(customer, "customer_llm_configured"):
        try:
            return bool(customer.customer_llm_configured())
        except Exception:
            pass
    provider = str(getattr(customer, "ai_provider", "") or "").strip()
    key = ""
    if hasattr(customer, "decrypted_ai_api_key"):
        try:
            key = str(customer.decrypted_ai_api_key() or "").strip()
        except Exception:
            key = ""
    return bool(provider) and bool(key)


def resolve_llm_credentials(
    customer: Any | None = None,
    *,
    model_key: str | None = None,
) -> LlmCredentials | None:
    requested = normalize_model_key(model_key)
    use_default = is_default_model_key(requested)
    if customer_llm_configured(customer):
        provider = normalize_llm_provider(getattr(customer, "ai_provider", None))
        key = str(customer.decrypted_ai_api_key() or "").strip()
        customer_model = str(getattr(customer, "ai_model", "") or "").strip()
        model = customer_model if use_default else requested
        if not model:
            model = ai_model_name()
        display = (
            "AI AGENT: Default Model"
            if use_default and not customer_model
            else f"AI AGENT: {model}"
        )
        if use_default and customer_model:
            display = f"AI AGENT: {customer_model}"
        return LlmCredentials(
            provider=provider,
            model=model,
            api_key=key,
            source="pvf_customer",
            model_key=DEFAULT_MODEL_KEY if use_default else requested,
            display_name=display,
        )
    if system_llm_configured() or (ai_api_key() and ai_api_key().lower() not in _PLACEHOLDER_KEYS):
        model = ai_model_name() if use_default else requested
        display = "AI AGENT: Default Model" if use_default else f"AI AGENT: {model}"
        return LlmCredentials(
            provider=ai_service_name(),
            model=model,
            api_key=ai_api_key(),
            source="system",
            model_key=DEFAULT_MODEL_KEY if use_default else requested,
            display_name=display,
        )
    return None
