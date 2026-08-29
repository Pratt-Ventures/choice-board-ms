from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from sqlmodel import Session

from ...db.models.ai_agent_jobs import AiAgentJob
from ...pvf.utils import utils_show as ut
from ...db.models.customer_project_alternatives_criteria import (
    CustomerProjectAlternatives,
    CustomerProjectFactors,
)
from ...db.models.customer_projects import CustomerProject
from ...db.models.project_vote_events import (
    GroupType,
    ProjectVoteGroupResult,
    ProjectVoteParticipant,
    SortAlgorithm,
)
from ...utils.pair_scheduler import (
    PairAnswer,
    SchedulerState,
    answer_to_pairing,
    choose_orientation,
    pairings_to_answers,
    rank_order_from_answers,
    ranking_target_from_group,
    select_next_pair,
)
from ...utils.vote_sort_session import (
    ALGORITHM_VERSION,
    package_group_id,
    pick_next_sort_group,
    project_pass_settings,
)
from .config import (
    DEFAULT_MODEL_KEY,
    ai_features_enabled,
    ai_max_concurrent_projects,
    ai_max_pairs_per_project,
    ai_pairs_per_tick,
    ai_skip_rate_abort,
    no_providers_message,
    resolve_llm_credentials,
)
from .prompts import ai_vote_threshold, combined_abstentions, pairwise_messages, parse_pairwise_choice
from .provider import AiProviderError, chat_text_sync


def _item_map(rows: list) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for row in rows or []:
        d = row.model_dump() if hasattr(row, "model_dump") else dict(row)
        if d.get("disabled") or d.get("deleted_date"):
            continue
        rid = d.get("id")
        if rid is None:
            continue
        title = d.get("alternative_title") or d.get("factor_title") or d.get("title") or ""
        description = d.get("alternative_description") or d.get("factor_description") or d.get("description") or ""
        # Prefer concise compare_prompt when present
        cp = (d.get("compare_prompt") or "").strip() if isinstance(d.get("compare_prompt"), str) else ""
        if cp:
            # For options, cp is concise label replacing title; for factors, keep title but use cp as question later
            # Detect option vs factor by presence of alternative_title
            if d.get("alternative_title") is not None or "alternative_title" in d:
                title = cp
            else:
                # factor: keep title, expose compare_prompt as comparison_question override
                pass
        out[int(rid)] = {
            "id": int(rid),
            "title": title,
            "description": description,
            "comparison_question": d.get("comparison_question"),
            "compare_prompt": d.get("compare_prompt"),
        }
    return out


def _parse_group_type(raw: str) -> GroupType:
    v = (raw or "alternative").strip().lower()
    if v in ("criteria", "factor", "factors"):
        return GroupType.criteria
    return GroupType.alternative


def _parse_algo(raw: str) -> SortAlgorithm:
    v = (raw or "ford_johnson").strip().lower()
    if v in ("merge_sort", "mergesort", "merge"):
        return SortAlgorithm.merge_sort
    return SortAlgorithm.ford_johnson


def _mark_job(session: Session, job: AiAgentJob, *, status: str, error: str | None = None) -> None:
    job.status = status
    job.error_summary = error
    job.modify_date = datetime.now()
    if status in ("complete", "failed"):
        job.completed_date = datetime.now()
    session.add(job)
    session.commit()
    session.refresh(job)
    ut.show_vars_semi(
        f"powerchoice_watcher - AI job {job.id} {status}",
        project_id=job.project_id,
        model_key=job.model_key,
        pairs=job.pair_count,
        skips=job.skip_count,
        error=error,
    )


def process_next_ai_job(session: Session) -> bool:
    if not ai_features_enabled():
        return False
    job = AiAgentJob.claim_next(
        session=session,
        max_concurrent=ai_max_concurrent_projects(),
        clear_lock=False,
    )
    if job is None:
        return False
    try:
        return _run_job(session, job)
    except Exception as ex:
        ut.show_vars_semi(
            f"powerchoice_watcher - AI job {job.id} failed",
            project_id=job.project_id,
            error=str(ex) or type(ex).__name__,
        )
        _mark_job(session, job, status="failed", error="AI baseline could not be completed")
        return True


def _run_job(session: Session, job: AiAgentJob) -> bool:
    project = session.get(CustomerProject, job.project_id)
    if project is None or project.deleted_date is not None or int(project.customer_id) != int(job.customer_id):
        _mark_job(session, job, status="failed", error="Project not found")
        return True
    alt_rows = CustomerProjectAlternatives.get_all_by_project_id_system(
        session=session, project_id=project.id, customer_id=project.customer_id, clear_lock=False
    ) or []
    factor_rows = CustomerProjectFactors.get_all_by_project_id_system(
        session=session, project_id=project.id, customer_id=project.customer_id, clear_lock=False
    ) or []
    alts = [a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in alt_rows]
    factors = [f.model_dump() if hasattr(f, "model_dump") else dict(f) for f in factor_rows]
    active_alts = [a for a in alts if not a.get("disabled")]
    if len(active_alts) < 2:
        _mark_job(session, job, status="failed", error="Project needs at least two options")
        return True

    from ...pvf.bindings.pvf_services import PvfCustomer

    customer = PvfCustomer.get_customer_by_id_system(
        session=session, id=int(project.customer_id), clear_lock=False
    )
    model_key = str(getattr(job, "model_key", None) or DEFAULT_MODEL_KEY)
    creds = resolve_llm_credentials(customer, model_key=model_key)
    if creds is None:
        _mark_job(session, job, status="failed", error=no_providers_message())
        return True
    part_result = ProjectVoteParticipant.get_or_create_ai_participant(
        session=session,
        customer_id=int(project.customer_id),
        project_id=int(project.id),
        model_key=creds.model_key,
        display_name=creds.display_name,
        clear_lock=False,
    )
    participant = part_result.participant_info
    if participant is None:
        _mark_job(session, job, status="failed", error="AI baseline could not be started")
        return True
    job.participant_id = participant.id
    session.add(job)
    session.commit()
    session.refresh(job)
    session.refresh(project)

    if participant.is_complete:
        _mark_job(session, job, status="complete")
        return True

    groups = ProjectVoteGroupResult.list_for_participant_system(
        session=session, participant_id=int(participant.id), clear_lock=False
    )
    ps = project_pass_settings(project)
    issued = pick_next_sort_group(
        project=project,
        alternatives=alts,
        factors=factors,
        groups=groups,
        max_pass_index=ps["min_expected_passes"],
        seed=int(participant.id),
    )
    group = issued.get("group")
    if not group or issued.get("session_complete"):
        skip_rate = (job.skip_count / job.pair_count) if job.pair_count else 0.0
        if job.pair_count and skip_rate >= ai_skip_rate_abort():
            _mark_job(session, job, status="failed", error="AI baseline is incomplete")
            return True
        participant.mark_activity(session, is_complete=True, clear_lock=False)
        job.group_count = int(participant.group_count or 0)
        _mark_job(session, job, status="complete")
        return True

    issued_row = ProjectVoteGroupResult.issue_group_result(
        session=session,
        participant=participant,
        group_type=_parse_group_type(str(group.get("group_type") or "alternative")),
        criterion_id=group.get("criterion_id"),
        sort_algorithm=_parse_algo(str(group.get("sort_algorithm") or "ford_johnson")),
        pass_index=int(group.get("pass_index") or 1),
        item_ids_initial=[int(x) for x in (group.get("item_ids") or [])],
        client_group_id=str(group.get("client_group_id") or group.get("group_token") or ""),
        group_token=str(group.get("group_token") or group.get("client_group_id") or ""),
        requested_pairing_count=int(group.get("question_budget") or group.get("estimated_comparisons") or 0),
        historical_pairing_count=len(group.get("prior_pairings") or []),
        ranking_target=str(group.get("ranking_target") or "full"),
        top_n=group.get("top_n"),
        batch_index=int(group.get("batch_index") or 0),
        algorithm_version=str(group.get("algorithm_version") or ALGORITHM_VERSION),
        clear_lock=False,
    )
    row = issued_row.group_info
    if row is None:
        _mark_job(session, job, status="failed", error="AI baseline could not be started")
        return True

    alt_map = _item_map(alts)
    fac_map = _item_map(factors)
    group_type = str(group.get("group_type") or "alternative")
    item_lookup = fac_map if group_type == "criteria" else alt_map
    criterion = group.get("criterion") if isinstance(group.get("criterion"), dict) else None
    if criterion is None and group.get("criterion_id") is not None:
        criterion = fac_map.get(int(group["criterion_id"]))

    answers = pairings_to_answers(row.pairings or [])
    prior = pairings_to_answers(group.get("prior_pairings") or [])
    items = [int(x) for x in (row.item_ids_initial or group.get("item_ids") or [])]
    budget = int(row.requested_pairing_count or group.get("question_budget") or 0)
    last_pair = None
    if answers:
        last = answers[-1]
        last_pair = (last.item_a, last.item_b)
    state = SchedulerState(
        items=items,
        target=ranking_target_from_group(group),
        pass_index=int(row.pass_index or 1),
        question_budget=budget,
        answers=list(answers),
        prior_answers=prior,
        last_pair=last_pair,
    )

    tick_limit = ai_pairs_per_tick()
    pair_cap = ai_max_pairs_per_project()
    processed = 0
    while processed < tick_limit:
        if job.pair_count >= pair_cap:
            _mark_job(session, job, status="failed", error="AI baseline is incomplete")
            return True
        nxt = select_next_pair(state)
        if nxt is None:
            break
        history = [*state.prior_answers, *state.answers]
        left, right = choose_orientation(
            nxt[0],
            nxt[1],
            history,
            [int(row.pass_index or 1), budget, *items],
        )
        left_item = item_lookup.get(left) or {"title": str(left), "description": ""}
        right_item = item_lookup.get(right) or {"title": str(right), "description": ""}
        # Quota per spec: 20% of group size (len(items)) with minimum 1, combined TIE+SKIP per group
        group_size_for_quota = int(len(items) or 0)
        threshold = ai_vote_threshold(group_size_for_quota)
        combined = combined_abstentions(state.answers)
        allow_skip_tie = (combined < threshold) if threshold > 0 else False
            # When threshold is 0 (degenerate group) we never allow abstention
        if str(group_type) == "criteria":
            # left/right are factors; surface each factor's question + description as Factor 1 / Factor 2
            def _factor_q(item: dict | None) -> str | None:
                if not isinstance(item, dict):
                    return None
                cp = (item.get("compare_prompt") or "").strip()
                return cp if cp else None
            messages = pairwise_messages(
                problem_title=str(getattr(project, "project_title", None) or getattr(project, "project_tag", None) or ""),
                problem_description=str(getattr(project, "project_description", None) or ""),
                left_title=str(left_item.get("title") or left),
                left_description=left_item.get("description"),
                right_title=str(right_item.get("title") or right),
                right_description=right_item.get("description"),
                factor_title=None,
                factor_description=None,
                group_type=group_type,
                comparison_question=None,
                allow_skip_tie=allow_skip_tie,
                left_factor_question=_factor_q(left_item),
                right_factor_question=_factor_q(right_item),
                left_factor_description=left_item.get("description"),
                right_factor_description=right_item.get("description"),
            )
        else:
            crit_q = None
            if criterion:
                cp = (criterion.get("compare_prompt") or "").strip()
                crit_q = cp if cp else None
            messages = pairwise_messages(
                problem_title=str(getattr(project, "project_title", None) or getattr(project, "project_tag", None) or ""),
                problem_description=str(getattr(project, "project_description", None) or ""),
                left_title=str(left_item.get("title") or left),
                left_description=left_item.get("description"),
                right_title=str(right_item.get("title") or right),
                right_description=right_item.get("description"),
                factor_title=(criterion or {}).get("title") if criterion else None,
                factor_description=(criterion or {}).get("description") if criterion else None,
                comparison_question=crit_q,
                group_type=group_type,
                allow_skip_tie=allow_skip_tie,
            )
        response_kind = "skipped"
        winner_id = left
        try:
            # In PYTEST mode, bypass watcher queue to allow test mocks on chat_text_sync to work
            _use_queue = True
            try:
                from ...config.config_settings import settings as _app_settings
                from ...pvf.config.pvf_config_settings import pvf_settings as _pvf_settings
                if getattr(_app_settings, "PYTEST_ACTIVE", False) or getattr(_pvf_settings, "PYTEST_ACTIVE", False):
                    _use_queue = False
            except Exception:
                _use_queue = True
            if _use_queue:
                try:
                    from ...pvf.bindings.pvf_watcher_requests import queue_llm_and_wait
                    from ...pvf.db.models.customer_user import PvfUserContext as _UC
                    usr_ctx = _UC(remote_ip="ai_worker", url_path="ai_worker")
                    try:
                        usr_ctx.sess_customer = customer  # type: ignore
                        class _D:
                            pass
                        _d = _D()
                        _d.customer_id = int(getattr(customer, "id", 0) or getattr(project, "customer_id", 0))
                        _d.id = int(getattr(job, "requested_by_user_id", 0) or 0)
                        usr_ctx.sess_user = _d  # type: ignore
                    except Exception:
                        pass
                    text, _result_pkg, _err = queue_llm_and_wait(session=session, usr_context=usr_ctx, messages=messages, temperature=0.1, max_tokens=16, provider=creds.provider, model=creds.model, api_key=creds.api_key, semantic_tag="ai_pairwise", timeout=15.0)
                    if _err:
                        if str(_err).startswith("queued:"):
                            raise AiProviderError("AI service is unavailable", retryable=True)
                        raise AiProviderError(str(_err) or "AI service is unavailable", retryable="retryable" in str(_err).lower() or "unavailable" in str(_err).lower())
                    raw = text or ""
                except AiProviderError:
                    raise
                except Exception as _qex:
                    raw = chat_text_sync(messages=messages, temperature=0.1, max_tokens=16, provider=creds.provider, model=creds.model, api_key=creds.api_key)
            else:
                raw = chat_text_sync(messages=messages, temperature=0.1, max_tokens=16, provider=creds.provider, model=creds.model, api_key=creds.api_key)
            choice = parse_pairwise_choice(raw)
            if choice == "left":
                response_kind = "winner"
                winner_id = left
            elif choice == "right":
                response_kind = "winner"
                winner_id = right
            elif choice == "tie":
                response_kind = "tie"
                winner_id = left
            elif choice == "skipped":
                response_kind = "skipped"
                winner_id = left
            else:
                response_kind = "skipped"
                winner_id = left
        except AiProviderError as ex:
            if ex.retryable:
                ut.show_vars_semi(
                    f"powerchoice_watcher - AI job {job.id} retrying",
                    project_id=job.project_id,
                    error=str(ex) or type(ex).__name__,
                )
                return True
            response_kind = "skipped"
            winner_id = left

        loser_id = right if winner_id == left else left
        ans = PairAnswer(
            item_a=nxt[0],
            item_b=nxt[1],
            winner_id=winner_id if response_kind == "winner" else None,
            response=response_kind,
            presented_left_id=left,
            presented_right_id=right,
            decision_seconds=0.0,
        )
        state.answers.append(ans)
        state.last_pair = nxt
        job.pair_count = int(job.pair_count or 0) + 1
        if response_kind == "skipped":
            job.skip_count = int(job.skip_count or 0) + 1
        pairings = [answer_to_pairing(a) for a in state.answers]
        ProjectVoteGroupResult.save_group_pairings(
            session=session,
            participant=participant,
            client_group_id=package_group_id({"group_token": row.group_token, "client_group_id": row.client_group_id}),
            pairings=pairings,
            rank_order=rank_order_from_answers(items, state.answers),
            clear_lock=False,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        processed += 1

    if select_next_pair(state) is not None:
        return True

    skip_rate = (job.skip_count / job.pair_count) if job.pair_count else 0.0
    if job.pair_count and skip_rate >= ai_skip_rate_abort() and not any(a.response != "skipped" for a in state.answers):
        _mark_job(session, job, status="failed", error="AI baseline is incomplete")
        return True

    order = rank_order_from_answers(items, state.answers)
    ProjectVoteGroupResult.create_group_result(
        session=session,
        participant=participant,
        group_type=_parse_group_type(group_type),
        criterion_id=row.criterion_id,
        sort_algorithm=_parse_algo(str(row.sort_algorithm or "ford_johnson")),
        pass_index=int(row.pass_index or 1),
        item_ids_initial=items,
        rank_order=order,
        pairings=[answer_to_pairing(a) for a in state.answers],
        client_group_id=str(row.client_group_id or row.group_token or ""),
        algorithm_version=ALGORITHM_VERSION,
        clear_lock=False,
    )
    participant = ProjectVoteParticipant.get_by_id_system(
        session=session, participant_id=int(participant.id), clear_lock=False
    )
    job.group_count = int(getattr(participant, "group_count", 0) or 0)
    session.add(job)
    session.commit()
    return True


def suggest_factors_sync(*, title: str, description: str, customer=None) -> list[dict[str, str]]:
    from .prompts import factor_suggest_messages, parse_factor_suggestions

    creds = resolve_llm_credentials(customer)
    if creds is None:
        raise AiProviderError(no_providers_message())
    # In PYTEST, directly use chat_json_sync so test mocks on that function work
    try:
        from ...config.config_settings import settings as _app_settings
        from ...pvf.config.pvf_config_settings import pvf_settings as _pvf_settings
        _is_pytest = bool(getattr(_app_settings, "PYTEST_ACTIVE", False) or getattr(_pvf_settings, "PYTEST_ACTIVE", False))
    except Exception:
        _is_pytest = False
    if _is_pytest:
        from .provider import chat_json_sync
        payload = chat_json_sync(
            messages=factor_suggest_messages(title=title, description=description),
            temperature=0.3,
            max_tokens=1200,
            provider=creds.provider,
            model=creds.model,
            api_key=creds.api_key,
        )
        return parse_factor_suggestions(payload)
    # Use watcher queue
    try:
        from ...pvf.bindings.pvf_watcher_requests import queue_llm_and_wait
        from ...pvf.db.models.customer_user import PvfUserContext as _UC
        from ...pvf.depends.api_session_dependencies import get_next_session as _get_next
        usr_ctx = _UC(remote_ip="suggest_sync", url_path="suggest_sync")
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
            text, result_pkg, err = queue_llm_and_wait(session=sess, usr_context=usr_ctx, messages=factor_suggest_messages(title=title, description=description), temperature=0.3, max_tokens=1200, provider=creds.provider, model=creds.model, api_key=creds.api_key, semantic_tag="factor_suggest", timeout=15.0)
            if err:
                if str(err).startswith("queued:"):
                    raise AiProviderError("AI service is unavailable", retryable=True)
                raise AiProviderError(str(err) or "Could not suggest factors")
            # Parse JSON from text
            import json as _json
            raw = (text or "").strip()
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
                        raise AiProviderError("Could not suggest factors")
                else:
                    raise AiProviderError("Could not suggest factors")
            return parse_factor_suggestions(payload)
    except AiProviderError:
        raise
    except Exception:
        # Fallback to direct sync
        from .provider import chat_json_sync
        payload = chat_json_sync(
            messages=factor_suggest_messages(title=title, description=description),
            temperature=0.3,
            max_tokens=1200,
            provider=creds.provider,
            model=creds.model,
            api_key=creds.api_key,
        )
        return parse_factor_suggestions(payload)


async def suggest_factors(*, title: str, description: str, customer=None) -> list[dict[str, str]]:
    # Async wrapper now delegates to sync watcher version (no true async)
    return suggest_factors_sync(title=title, description=description, customer=customer)
