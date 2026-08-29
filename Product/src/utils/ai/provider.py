from __future__ import annotations

import json
from typing import Any

from ...pvf.bindings.pvf_services import LlmError, query_llm_model


class AiProviderError(LlmError):
    pass


def _as_provider_error(exc: Exception) -> AiProviderError:
    if isinstance(exc, AiProviderError):
        return exc
    if isinstance(exc, LlmError):
        return AiProviderError(str(exc) or "AI service is unavailable", retryable=exc.retryable)
    return AiProviderError()


def chat_text_sync(
    *,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 800,
    settings_obj: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    _ = settings_obj
    try:
        _session, result = query_llm_model(
            "",
            provider=provider,
            model=model,
            api_key=api_key,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return result
    except LlmError as exc:
        raise _as_provider_error(exc) from exc


async def chat_text(
    *,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 800,
    settings_obj: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    return chat_text_sync(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        settings_obj=settings_obj,
        provider=provider,
        model=model,
        api_key=api_key,
    )


def _parse_json_object(text: str) -> Any:
    raw = (text or "").strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise AiProviderError() from None


def chat_json_sync(
    *,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 1200,
    settings_obj: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> Any:
    text = chat_text_sync(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        settings_obj=settings_obj,
        provider=provider,
        model=model,
        api_key=api_key,
    )
    return _parse_json_object(text)


async def chat_json(
    *,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 1200,
    settings_obj: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> Any:
    return chat_json_sync(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        settings_obj=settings_obj,
        provider=provider,
        model=model,
        api_key=api_key,
    )
