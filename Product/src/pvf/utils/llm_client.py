from __future__ import annotations

import time
from typing import Any

import httpx

from ..config.pvf_config_settings import pvf_settings

NO_PROVIDERS_CONFIGURED = "no providers configured"
SUPPORTED_LLM_PROVIDERS = ("opencode_go", "opencode_zen", "openrouter")

_PLACEHOLDER_KEYS = {"", "specify in .env", "<specify>", "changeme"}

_PROVIDER_BASE_URLS = {
    "opencode_go": "https://opencode.ai/zen/go/v1",
    "opencode_zen": "https://opencode.ai/zen/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


class LlmError(Exception):
    def __init__(self, message: str = "AI service is unavailable", *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def normalize_llm_provider(raw: str | None) -> str:
    name = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if name in ("opencode_zen", "zen", "opencodezen"):
        return "opencode_zen"
    if name in ("openrouter", "open_router"):
        return "openrouter"
    if name in ("opencode_go", "go", "opencodego", "opencode", "opencode_zen_go", "zen_go"):
        return "opencode_go"
    if name:
        return name
    return "opencode_go"


def provider_is_supported(provider: str | None) -> bool:
    return normalize_llm_provider(provider) in SUPPORTED_LLM_PROVIDERS


def _timeout() -> float:
    try:
        return max(1.0, float(getattr(pvf_settings, "AI_HTTP_TIMEOUT_SECONDS", 30) or 30))
    except (TypeError, ValueError):
        return 30.0


def _retries() -> int:
    try:
        return max(0, min(8, int(getattr(pvf_settings, "AI_HTTP_RETRIES", 3) or 3)))
    except (TypeError, ValueError):
        return 3


def _system_key() -> str:
    return str(getattr(pvf_settings, "AI_API_KEY", "") or "").strip()


def _system_provider() -> str:
    return normalize_llm_provider(getattr(pvf_settings, "AI_SERVICE", "opencode_go"))


def _system_model() -> str:
    return str(getattr(pvf_settings, "AI_MODEL", "") or "").strip() or "glm-5.2"


def system_llm_configured() -> bool:
    key = _system_key().lower()
    return bool(key) and key not in _PLACEHOLDER_KEYS and provider_is_supported(_system_provider())


def llm_base_url(provider: str | None = None) -> str:
    override = str(getattr(pvf_settings, "AI_BASE_URL", "") or "").strip().rstrip("/")
    if override:
        return override
    name = normalize_llm_provider(provider or _system_provider())
    return _PROVIDER_BASE_URLS.get(name, _PROVIDER_BASE_URLS["opencode_go"])


def _headers(provider: str, api_key: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if normalize_llm_provider(provider) == "openrouter":
        app_name = str(getattr(pvf_settings, "APPLICATION_NAME", "") or "PowerChoice")
        headers["HTTP-Referer"] = "https://powerchoice.app"
        headers["X-Title"] = app_name
    return headers


def _extract_result(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        msg = first.get("message") if isinstance(first, dict) else None
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        parts.append(item["text"])
                    elif isinstance(item, str):
                        parts.append(item)
                return "".join(parts).strip()
        text = first.get("text") if isinstance(first, dict) else None
        if isinstance(text, str):
            return text.strip()
    output = body.get("output_text")
    if isinstance(output, str):
        return output.strip()
    return ""


def _status_retryable(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _request_json(
    *,
    method: str,
    url: str,
    provider: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
    retries: int | None = None,
) -> Any:
    attempts = _retries() if retries is None else max(0, retries)
    timeout = _timeout()
    last_retryable = False
    for attempt in range(attempts + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method,
                    url,
                    headers=_headers(provider, api_key),
                    json=payload if payload is not None else None,
                )
        except httpx.TimeoutException:
            last_retryable = True
            if attempt < attempts:
                time.sleep(min(8.0, 0.5 * (2 ** attempt)))
                continue
            raise LlmError(retryable=True) from None
        except httpx.HTTPError:
            last_retryable = True
            if attempt < attempts:
                time.sleep(min(8.0, 0.5 * (2 ** attempt)))
                continue
            raise LlmError(retryable=True) from None
        if response.status_code >= 400:
            last_retryable = _status_retryable(response.status_code)
            if last_retryable and attempt < attempts:
                time.sleep(min(8.0, 0.5 * (2 ** attempt)))
                continue
            if response.status_code in (401, 403):
                raise LlmError("Provider authorization failed")
            raise LlmError(retryable=last_retryable)
        try:
            return response.json()
        except Exception:
            raise LlmError() from None
    raise LlmError(retryable=last_retryable)


def _normalize_model_rows(body: Any) -> list[dict[str, str]]:
    rows: list[Any]
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, list):
            rows = data
        elif isinstance(body.get("models"), list):
            rows = body["models"]
        else:
            rows = []
    elif isinstance(body, list):
        rows = body
    else:
        rows = []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in rows:
        if isinstance(item, str):
            model_id = item.strip()
            name = model_id
        elif isinstance(item, dict):
            model_id = str(item.get("id") or item.get("model") or item.get("name") or "").strip()
            name = str(item.get("name") or item.get("display_name") or model_id).strip() or model_id
        else:
            continue
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        out.append({"id": model_id, "name": name})
    out.sort(key=lambda r: r["name"].lower())
    return out


def _resolve_call_settings(
    *,
    provider: str | None,
    model: str | None,
    api_key: str | None,
) -> tuple[str, str, str]:
    key = str(api_key or "").strip()
    prov = normalize_llm_provider(provider) if provider else ""
    mdl = str(model or "").strip()
    if key and prov:
        if not provider_is_supported(prov):
            raise LlmError("Unsupported LLM provider")
        return prov, mdl or _system_model(), key
    if system_llm_configured():
        return _system_provider(), mdl or _system_model(), _system_key()
    raise LlmError(NO_PROVIDERS_CONFIGURED)


def query_llm_model(
    prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    messages: list[dict[str, str]] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 800,
) -> tuple[Any, str]:
    """Send a prompt to the configured provider/model.

    Returns (session_contents, result). Callers own prompt assembly and parsing.
    """
    prov, mdl, key = _resolve_call_settings(provider=provider, model=model, api_key=api_key)
    if messages:
        chat_messages = messages
    else:
        chat_messages = [{"role": "pvf_user", "content": str(prompt or "")}]
    payload = {
        "model": mdl,
        "messages": chat_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    body = _request_json(
        method="POST",
        url=f"{llm_base_url(prov)}/chat/completions",
        provider=prov,
        api_key=key,
        payload=payload,
    )
    result = _extract_result(body)
    if not result:
        raise LlmError()
    session_contents = {
        "provider": prov,
        "model": mdl,
        "messages": chat_messages,
        "response": body,
    }
    return session_contents, result


def verify_llm_provider(
    provider: str,
    api_key: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Validate provider + key. When valid, return the provider's available models."""
    prov = normalize_llm_provider(provider)
    key = str(api_key or "").strip()
    if not key or key.lower() in _PLACEHOLDER_KEYS:
        return {"ok": False, "models": [], "error": NO_PROVIDERS_CONFIGURED}
    if not provider_is_supported(prov):
        return {"ok": False, "models": [], "error": "Unsupported LLM provider"}
    try:
        body = _request_json(
            method="GET",
            url=f"{llm_base_url(prov)}/models",
            provider=prov,
            api_key=key,
            retries=1,
        )
    except LlmError as exc:
        return {"ok": False, "models": [], "error": str(exc) or "Provider authorization failed"}
    models = _normalize_model_rows(body)
    requested = str(model or "").strip()
    if requested and not any(row["id"] == requested for row in models):
        models.insert(0, {"id": requested, "name": requested})
    return {"ok": True, "models": models, "error": None, "provider": prov}
