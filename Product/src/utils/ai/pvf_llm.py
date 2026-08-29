"""PVF LLM wrapper — application-side pre-processing before queue_llm_request.

Raw query_llm_model (src/pvf/utils/llm_client.py) stays internal to the watcher handler
and is NOT the public API. Application code should call this module, which resolves
credentials via src/utils/ai/config.py and prompts.py before enqueuing.

Usage:
  from src.utils.ai.pvf_llm import queue_llm_via_pvf
  result = queue_llm_via_pvf(session, usr_context, prompt="...", semantic_tag="SHORTEN_PRODUCT_NAME")
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session

from ...pvf.bindings.pvf_watcher_requests import queue_llm_request
from ...pvf.utils.pvf_base_internal_resources import PvfWsResultPackage
from .config import resolve_llm_credentials
from .prompts import pairwise_messages  # example; caller may pass pre-built messages


def queue_llm_via_pvf(
    *,
    session: Session,
    usr_context,
    prompt: str | None = None,
    messages: list[dict] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 800,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    semantic_tag: str | None = None,
    metadata: dict | None = None,
) -> PvfWsResultPackage:
    """Resolve credentials (BYOK or system) and queue via PVF binding.

    Mirrors the pre-processing that worker.py did inline before calling llm_client.
    """
    # Try to resolve credentials if not supplied explicitly
    # For app wrapper, we attempt to infer customer from usr_context if available
    cust = None
    try:
        if usr_context is not None:
            cust = getattr(usr_context, "sess_customer", None)
            if cust is None and hasattr(usr_context, "sess_user") and usr_context.sess_user is not None:
                from ...pvf.bindings.pvf_services import PvfCustomer
                # Will be fetched via session if needed; for now keep None and let fallback handle
                pass
    except Exception:
        cust = None

    # If no explicit provider/model/key, try resolve via customer/system
    if not (provider and api_key):
        try:
            # If we have a customer object, resolve against it
            if cust is not None:
                creds = resolve_llm_credentials(cust)
            else:
                creds = resolve_llm_credentials(None)
            if creds is not None:
                provider = provider or creds.provider
                model = model or creds.model
                api_key = api_key or creds.api_key
        except Exception:
            pass

    # Delegate to PVF binding (tenancy + encryption handled there)
    return queue_llm_request(
        session=session,
        usr_context=usr_context,
        provider=provider,
        model=model,
        api_key=api_key,
        messages=messages,
        prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        semantic_tag=semantic_tag,
        metadata=metadata,
    )


# Back-compat alias used in tests
queue_llm = queue_llm_via_pvf
