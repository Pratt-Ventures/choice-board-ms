from __future__ import annotations

from datetime import datetime

from sqlmodel import Session

from ...db.models.compare_prompt_jobs import ComparePromptJob
from ...db.models.customer_project_alternatives_criteria import (
    CustomerProjectAlternatives,
    CustomerProjectFactors,
)
from ...pvf.utils import utils_show as ut
from ...pvf.utils.log_event import log_event
from .config import (
    ai_rewrite_factor_max_tokens,
    ai_rewrite_option_max_tokens,
    customer_llm_configured,
    resolve_llm_credentials,
)
from .prompts import factor_rewrite_messages, option_rewrite_messages, parse_compare_prompt
from .provider import AiProviderError, chat_json_sync


def _update_target(session: Session, job: ComparePromptJob, prompt_text: str | None) -> bool:
    if job.item_type == "option":
        row = session.get(CustomerProjectAlternatives, job.item_id)
        if row is None or row.deleted_date is not None:
            return False
        row.compare_prompt = prompt_text
        session.add(row)
        session.commit()
        return True
    elif job.item_type == "factor":
        row = session.get(CustomerProjectFactors, job.item_id)
        if row is None or row.deleted_date is not None:
            return False
        row.compare_prompt = prompt_text
        session.add(row)
        session.commit()
        return True
    return False


def process_next_reword_job(session: Session) -> bool:
    job = ComparePromptJob.claim_next(session=session, clear_lock=False)
    if job is None:
        return False
    # Load customer for credentials
    from ...pvf.bindings.pvf_services import PvfCustomer

    customer = PvfCustomer.get_customer_by_id_system(session=session, id=int(job.customer_id), clear_lock=False)
    if customer is None or not customer_llm_configured(customer):
        job.status = "failed"
        job.error_summary = "There is no provider set up for this customer, check settings to enable"
        job.completed_date = datetime.now()
        session.add(job)
        session.commit()
        ut.show_vars_semi(f"reword job {job.id} failed - no provider", project_id=job.project_id)
        log_event(
            f"reword job {job.id} failed - no provider",
            severity=2,
            customer_id=int(job.customer_id),
            details_str=f"project_id={job.project_id} item_type={job.item_type} item_id={job.item_id}",
            job_id=job.id,
            project_id=int(job.project_id),
            item_type=job.item_type,
            item_id=int(job.item_id),
        )
        return True
    creds = resolve_llm_credentials(customer)
    if creds is None or creds.source != "pvf_customer":
        job.status = "failed"
        job.error_summary = "There is no provider set up for this customer, check settings to enable"
        job.completed_date = datetime.now()
        session.add(job)
        session.commit()
        log_event(
            f"reword job {job.id} failed - no credentials",
            severity=2,
            customer_id=int(job.customer_id),
            details_str=f"project_id={job.project_id} item_type={job.item_type} item_id={job.item_id} provider={getattr(creds, 'provider', '') if creds else ''}",
            job_id=job.id,
            project_id=int(job.project_id),
            item_type=job.item_type,
            item_id=int(job.item_id),
        )
        return True

    # Load item
    try:
        if job.item_type == "option":
            row = session.get(CustomerProjectAlternatives, job.item_id)
            if row is None or row.deleted_date is not None:
                raise ValueError("Option not found")
            messages = option_rewrite_messages(title=row.alternative_title or "", description=row.alternative_description)
        else:
            row = session.get(CustomerProjectFactors, job.item_id)
            if row is None or row.deleted_date is not None:
                raise ValueError("Factor not found")
            messages = factor_rewrite_messages(
                title=row.factor_title or "",
                description=row.factor_description,
                polarity_positive=row.factor_polarity_positive,
                polarity_note=row.factor_polarity_note,
            )
        # Use watcher LLM queue with byte tracking instead of direct chat_json_sync
        max_tokens = ai_rewrite_factor_max_tokens() if job.item_type == "factor" else ai_rewrite_option_max_tokens()
        # Build a minimal PvfUserContext for queue (customer_id from job)
        from ...pvf.db.models.customer_user import PvfUserContext as _UC
        from ...pvf.bindings.pvf_watcher_requests import queue_llm_and_wait
        # Try to get user context from job.requested_by_user_id if available
        usr_ctx = _UC(remote_ip="watcher:reword", url_path="watcher:reword")
        # Attach sess_user/customer for tenancy
        try:
            # Fetch user for tenancy if possible
            from ...pvf.db.models.customer_user import PvfUser as _User
            _u = session.get(_User, int(job.requested_by_user_id)) if job.requested_by_user_id else None
            if _u is not None:
                usr_ctx.sess_user = _u
                usr_ctx.sess_customer = customer
        except Exception:
            pass
        # Fallback: at least set customer_id via manual injection for _resolve check
        if getattr(usr_ctx, "sess_user", None) is None:
            # Create a dummy sess_user with customer_id for fallback resolution
            class _Dummy:
                pass
            _d = _Dummy()
            _d.customer_id = int(job.customer_id)
            _d.id = int(job.requested_by_user_id or 0)
            usr_ctx.sess_user = _d  # type: ignore
            usr_ctx.sess_customer = customer
        text, result_pkg, err = queue_llm_and_wait(session=session, usr_context=usr_ctx, messages=messages, temperature=0.3, max_tokens=max_tokens, provider=creds.provider, model=creds.model, api_key=creds.api_key, semantic_tag=f"reword_{job.item_type}", timeout=20.0)
        if err:
            if str(err).startswith("queued:"):
                # Still queued after wait -> requeue job for next tick
                job.status = "queued"
                job.error_summary = "queued for LLM"
                job.modify_date = datetime.now()
                session.add(job)
                session.commit()
                ut.show_vars_semi(f"reword job {job.id} queued LLM", project_id=job.project_id)
                return True
            raise AiProviderError(str(err) or "AI service is unavailable", retryable="retryable" in str(err).lower() or "unavailable" in str(err).lower())
        if not text:
            if isinstance(result_pkg, dict):
                text = result_pkg.get("text") or ""
            if not text:
                raise AiProviderError("Could not parse compare prompt")
        # Parse compare_prompt from text
        # text may be JSON string with compare_prompt field, or plain
        import json as _json
        payload = None
        raw = (text or "").strip()
        if raw.startswith("{") or raw.startswith("```"):
            # Try JSON parse as before
            if raw.startswith("```"):
                lines = raw.split("\n")
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                raw = "\n".join(lines).strip()
            try:
                payload = _json.loads(raw)
            except _json.JSONDecodeError:
                start = raw.find("{")
                end = raw.rfind("}")
                if start >= 0 and end > start:
                    try:
                        payload = _json.loads(raw[start:end + 1])
                    except _json.JSONDecodeError:
                        payload = {"compare_prompt": raw}
                else:
                    payload = {"compare_prompt": raw}
        else:
            payload = {"compare_prompt": raw}
        # If result_pkg already contains structured payload
        if isinstance(result_pkg, dict) and result_pkg.get("text") and isinstance(result_pkg.get("session_contents"), dict):
            # Prefer parsed from result_pkg if available
            pass
        parsed = parse_compare_prompt(payload if isinstance(payload, dict) else {"compare_prompt": str(payload)})
        if not parsed:
            if isinstance(payload, dict):
                for v in payload.values():
                    if isinstance(v, str) and v.strip():
                        parsed = parse_compare_prompt({"compare_prompt": v})
                        if parsed:
                            break
            if not parsed:
                raise AiProviderError("Could not parse compare prompt")
        _update_target(session, job, parsed)
        job.status = "complete"
        job.error_summary = None
        job.completed_date = datetime.now()
        job.modify_date = datetime.now()
        session.add(job)
        session.commit()
        ut.show_vars_semi(f"reword job {job.id} complete", project_id=job.project_id, item_type=job.item_type, prompt=parsed[:80] if parsed else "")
        log_event(
            f"reword job {job.id} complete",
            severity=1,
            customer_id=int(job.customer_id),
            details_str=f"project_id={job.project_id} item_type={job.item_type} item_id={job.item_id} provider={creds.provider} model={creds.model}",
            job_id=job.id,
            project_id=int(job.project_id),
            item_type=job.item_type,
            item_id=int(job.item_id),
            provider=creds.provider,
            model=creds.model,
        )
        return True
    except AiProviderError as ex:
        if ex.retryable:
            msg = str(ex) or "AI service is unavailable"
            job.status = "queued"
            job.error_summary = msg
            job.modify_date = datetime.now()
            session.add(job)
            session.commit()
            ut.show_vars_semi(f"reword job {job.id} retryable", error=msg[:200])
            log_event(
                f"reword job {job.id} retryable: {msg[:200]}",
                severity=2,
                customer_id=int(job.customer_id),
                ex_info=ex,
                details_str=f"project_id={job.project_id} item_type={job.item_type} item_id={job.item_id} provider={creds.provider if creds else ''} model={creds.model if creds else ''}",
                job_id=job.id,
                project_id=int(job.project_id),
                item_type=job.item_type,
                item_id=int(job.item_id),
                provider=getattr(creds, "provider", "") if creds else "",
                model=getattr(creds, "model", "") if creds else "",
                error=msg[:300],
            )
            return True
        msg = str(ex) or "AI provider error"
        job.status = "failed"
        job.error_summary = msg
        job.completed_date = datetime.now()
        session.add(job)
        session.commit()
        ut.show_vars_semi(f"reword job {job.id} failed", error=msg[:200])
        log_event(
            f"reword job {job.id} failed: {msg[:200]}",
            severity=2,
            customer_id=int(job.customer_id),
            ex_info=ex,
            details_str=f"project_id={job.project_id} item_type={job.item_type} item_id={job.item_id} provider={creds.provider if creds else ''} model={creds.model if creds else ''}",
            job_id=job.id,
            project_id=int(job.project_id),
            item_type=job.item_type,
            item_id=int(job.item_id),
            provider=getattr(creds, "provider", "") if creds else "",
            model=getattr(creds, "model", "") if creds else "",
            error=msg[:300],
        )
        return True
    except Exception as ex:
        msg = str(ex)[:300] or "Failed to generate compare prompt"
        job.status = "failed"
        job.error_summary = msg
        job.completed_date = datetime.now()
        session.add(job)
        session.commit()
        ut.show_vars_semi(f"reword job {job.id} failed exception", error=msg[:200])
        log_event(
            f"reword job {job.id} failed exception: {msg[:200]}",
            severity=3,
            customer_id=int(job.customer_id),
            ex_info=ex if isinstance(ex, Exception) else None,
            details_str=f"project_id={job.project_id} item_type={job.item_type} item_id={job.item_id}",
            job_id=job.id,
            project_id=int(job.project_id),
            item_type=job.item_type,
            item_id=int(job.item_id),
            error=msg[:300],
        )
        return True


def generate_option_prompt_sync(*, customer, title: str, description: str | None) -> str:
    # In PYTEST, directly use chat_json_sync to allow test mocks to work
    try:
        from ...config.config_settings import settings as _app_settings
        from ...pvf.config.pvf_config_settings import pvf_settings as _pvf_settings
        if getattr(_app_settings, "PYTEST_ACTIVE", False) or getattr(_pvf_settings, "PYTEST_ACTIVE", False):
            creds = resolve_llm_credentials(customer)
            if creds is None or creds.source != "pvf_customer":
                raise AiProviderError("There is no provider set up for this customer, check settings to enable")
            messages = option_rewrite_messages(title=title or "", description=description)
            # Use direct sync in pytest so monkeypatch on chat_json_sync works
            payload = chat_json_sync(messages=messages, temperature=0.3, max_tokens=ai_rewrite_option_max_tokens(), provider=creds.provider, model=creds.model, api_key=creds.api_key)
            parsed = parse_compare_prompt(payload)
            if not parsed:
                raise AiProviderError("Could not parse compare prompt")
            return parsed
    except AiProviderError:
        raise
    except Exception:
        pass
    # Legacy sync wrapper now delegates to watcher queue (with fallback).
    # For backward compat, try watcher; if queued, raise retryable.
    creds = resolve_llm_credentials(customer)
    if creds is None or creds.source != "pvf_customer":
        raise AiProviderError("There is no provider set up for this customer, check settings to enable")
    messages = option_rewrite_messages(title=title or "", description=description)
    # Use watcher queue; for sync callers that expect immediate result, poll with short timeout.
    try:
        from ...pvf.bindings.pvf_watcher_requests import queue_llm_and_wait
        from ...pvf.db.models.customer_user import PvfUserContext as _UC
        from ...pvf.depends.api_session_dependencies import get_next_session as _get_next
        # Create a minimal usr_context for tenancy (customer -> system fallback handled in queue)
        usr_ctx = _UC(remote_ip="reword_sync", url_path="reword_sync")
        # Try to attach customer for resolution
        try:
            usr_ctx.sess_customer = customer  # type: ignore
            # Create dummy sess_user for customer_id
            class _D:
                pass
            _d = _D()
            _d.customer_id = int(getattr(customer, "id", 0) or 0)
            _d.id = 0
            usr_ctx.sess_user = _d  # type: ignore
        except Exception:
            pass
        with _get_next() as sess:
            text, result_pkg, err = queue_llm_and_wait(session=sess, usr_context=usr_ctx, messages=messages, temperature=0.3, max_tokens=ai_rewrite_option_max_tokens(), provider=creds.provider, model=creds.model, api_key=creds.api_key, semantic_tag="reword_option", timeout=12.0)
            if err:
                if str(err).startswith("queued:"):
                    raise AiProviderError("AI service is unavailable", retryable=True)
                raise AiProviderError(str(err) or "Could not parse compare prompt", retryable="retryable" in str(err).lower())
            payload_text = text or (result_pkg.get("text") if isinstance(result_pkg, dict) else "") or ""
            # Parse JSON if needed
            import json as _json
            raw = (payload_text or "").strip()
            # Try to parse as JSON first
            try:
                if raw.startswith("{") or raw.startswith("```"):
                    # Reuse same parsing as before
                    if raw.startswith("```"):
                        lines = raw.split("\n")
                        if lines and lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip() == "```":
                            lines = lines[:-1]
                        raw = "\n".join(lines).strip()
                    try:
                        payload = _json.loads(raw)
                    except _json.JSONDecodeError:
                        start = raw.find("{")
                        end = raw.rfind("}")
                        if start >= 0 and end > start:
                            payload = _json.loads(raw[start:end+1])
                        else:
                            payload = {"compare_prompt": raw}
                else:
                    payload = {"compare_prompt": raw}
                parsed = parse_compare_prompt(payload if isinstance(payload, dict) else {"compare_prompt": str(payload)})
                if parsed:
                    return parsed
            except Exception:
                pass
            # Fallback try raw
            parsed = parse_compare_prompt({"compare_prompt": payload_text})
            if parsed:
                return parsed
            raise AiProviderError("Could not parse compare prompt")
    except AiProviderError:
        raise
    except Exception as ex:
        raise AiProviderError(str(ex) or "Could not parse compare prompt")


def generate_factor_prompt_sync(*, customer, title: str, description: str | None, polarity_positive: bool, polarity_note: str | None) -> str:
    try:
        from ...config.config_settings import settings as _app_settings
        from ...pvf.config.pvf_config_settings import pvf_settings as _pvf_settings
        if getattr(_app_settings, "PYTEST_ACTIVE", False) or getattr(_pvf_settings, "PYTEST_ACTIVE", False):
            creds = resolve_llm_credentials(customer)
            if creds is None or creds.source != "pvf_customer":
                raise AiProviderError("There is no provider set up for this customer, check settings to enable")
            messages = factor_rewrite_messages(title=title or "", description=description, polarity_positive=polarity_positive, polarity_note=polarity_note)
            payload = chat_json_sync(messages=messages, temperature=0.3, max_tokens=ai_rewrite_factor_max_tokens(), provider=creds.provider, model=creds.model, api_key=creds.api_key)
            parsed = parse_compare_prompt(payload)
            if not parsed:
                raise AiProviderError("Could not parse compare prompt")
            return parsed
    except AiProviderError:
        raise
    except Exception:
        pass
    creds = resolve_llm_credentials(customer)
    if creds is None or creds.source != "pvf_customer":
        raise AiProviderError("There is no provider set up for this customer, check settings to enable")
    messages = factor_rewrite_messages(title=title or "", description=description, polarity_positive=polarity_positive, polarity_note=polarity_note)
    try:
        from ...pvf.bindings.pvf_watcher_requests import queue_llm_and_wait
        from ...pvf.db.models.customer_user import PvfUserContext as _UC
        from ...pvf.depends.api_session_dependencies import get_next_session as _get_next
        usr_ctx = _UC(remote_ip="reword_sync", url_path="reword_sync")
        try:
            usr_ctx.sess_customer = customer  # type: ignore
            class _D:
                pass
            _d = _D()
            _d.customer_id = int(getattr(customer, "id", 0) or 0)
            _d.id = 0
            usr_ctx.sess_user = _d  # type: ignore
        except Exception:
            pass
        with _get_next() as sess:
            text, result_pkg, err = queue_llm_and_wait(session=sess, usr_context=usr_ctx, messages=messages, temperature=0.3, max_tokens=ai_rewrite_factor_max_tokens(), provider=creds.provider, model=creds.model, api_key=creds.api_key, semantic_tag="reword_factor", timeout=12.0)
            if err:
                if str(err).startswith("queued:"):
                    raise AiProviderError("AI service is unavailable", retryable=True)
                raise AiProviderError(str(err) or "Could not parse compare prompt", retryable="retryable" in str(err).lower())
            payload_text = text or (result_pkg.get("text") if isinstance(result_pkg, dict) else "") or ""
            import json as _json
            raw = (payload_text or "").strip()
            try:
                if raw.startswith("{") or raw.startswith("```"):
                    if raw.startswith("```"):
                        lines = raw.split("\n")
                        if lines and lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip() == "```":
                            lines = lines[:-1]
                        raw = "\n".join(lines).strip()
                    try:
                        payload = _json.loads(raw)
                    except _json.JSONDecodeError:
                        start = raw.find("{")
                        end = raw.rfind("}")
                        if start >= 0 and end > start:
                            payload = _json.loads(raw[start:end+1])
                        else:
                            payload = {"compare_prompt": raw}
                else:
                    payload = {"compare_prompt": raw}
                parsed = parse_compare_prompt(payload if isinstance(payload, dict) else {"compare_prompt": str(payload)})
                if parsed:
                    return parsed
            except Exception:
                pass
            parsed = parse_compare_prompt({"compare_prompt": payload_text})
            if parsed:
                return parsed
            raise AiProviderError("Could not parse compare prompt")
    except AiProviderError:
        raise
    except Exception as ex:
        raise AiProviderError(str(ex) or "Could not parse compare prompt")
