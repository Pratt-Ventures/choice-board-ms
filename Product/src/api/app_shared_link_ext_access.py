from __future__ import annotations
from typing import Union, Any
from datetime import datetime
from pydantic import BaseModel, Field

from fastapi import APIRouter, status, HTTPException, Request, Response

from ..pvf.bindings.pvf_services import (
    PvfWsResultPackage, PvfUserContext, PvfCustomer, SessionDep, PvfCustomerBrandingImage, PvfProjectBrandingImage,
    PvfShareAccessRequest_Base, PvfShareAccessRequest, PvfShareAccessDenied_Base,
    PvfShareAccessConfirmed_Base, share_link_validate_and_log, get_token_cookie,
)


from ..utils.base_classes_and_enums import ShareAccessOperation, ShareType
from ..db.models.project_vote_events import (
    ProjectVoteParticipant,
    ProjectVoteGroupResult,
    GroupType,
    SortAlgorithm,
)
from ..db.models.customer_projects import CustomerProject
from ..db.models.customer_project_alternatives_criteria import (
    CustomerProjectAlternatives,
    CustomerProjectFactors,
)
from ..utils.vote_ranking import (
    build_report,
    build_personal_submitter_summary,
    ranking_settings_from_customer,
    ranking_settings_with_project_influence,
)
from ..utils.vote_sort_session import (
    pick_next_sort_group,
    validate_group_package,
    normalize_pairing,
    parse_event_timestamp,
    package_group_id,
    project_ranking_mode,
    ranking_evidence_from_groups,
    ALGORITHM_VERSION,
)
from ..config.config_settings import settings
from ..utils.private_participation import redact_report_identities
from ..utils.next_group_cache import get_issued_group, set_issued_group, invalidate_participant
from ..utils.sort_compare import (
    clamp_min_expected_passes,
    clamp_max_recommended_passes,
    clamp_questions_per_group_stored,
    hard_max_passes,
)
from ..utils.project_end_time import (
    collection_ending_soon,
    collection_is_closed,
    project_end_time_payload,
    project_input_block_reason,
)

router = APIRouter()

_SHARE_CACHE_SCOPE = "share"


class RequestSharedProjectAccess(PvfShareAccessRequest_Base):
    request_next: bool = Field(default=True, description="When true, include the next sort group")
    # legacy alias
    request_next_count: int = Field(default=0, description="Deprecated; treated as request_next when >0")
    share_kind: str | None = Field(default=None, description="Share type: vote | vote_view")


class ShareAccessDenied(PvfShareAccessDenied_Base):
    pass


class SharedProjectSummary(BaseModel):
    project_id: int = Field(default=-1)
    project_tag: str | None = None
    project_title: str | None = None
    project_description: str | None = None
    project_exclusive_mode: bool = False
    private_participation: bool = False
    participant_influence_mode: str = "comparisons"
    participant_influence_min_comparisons: int = 10
    factor_weight_floor_alpha: float = 0.5
    min_expected_passes: int = 2
    max_recommended_passes: int = 2
    option_questions_per_group: int = 20
    factor_questions_per_group: int = 20
    option_questions_per_group_explicit: bool = False
    factor_questions_per_group_explicit: bool = False
    alternative_count: int = 0
    factor_count: int = 0
    disabled: bool = False
    end_time: datetime | None = None
    collection_ending_soon: bool = False
    collection_closed: bool = False
    customer_name: str | None = None
    has_customer_branding_image: bool = False
    has_project_branding_image: bool = False


class SharedProjectVotePayload(PvfWsResultPackage):
    share_result_status: PvfShareAccessConfirmed_Base | None = None
    project: SharedProjectSummary | None = None
    alternatives: list[dict] = Field(default_factory=list)
    factors: list[dict] = Field(default_factory=list)
    personal_vote: dict | None = None
    participant_id: int | None = None
    next_group: dict | None = None
    progress: dict = Field(default_factory=dict)
    session_complete: bool = False
    project_settings: dict = Field(default_factory=dict)
    next_questions: list[dict] = Field(default_factory=list)
    ranking_settings: dict = Field(default_factory=dict)
    viewer: dict | None = None


class SharedProjectVoteViewPayload(PvfWsResultPackage):
    share_result_status: PvfShareAccessConfirmed_Base | None = None
    project: SharedProjectSummary | None = None
    alternatives: list[dict] = Field(default_factory=list)
    factors: list[dict] = Field(default_factory=list)
    personal_vote: dict | None = None
    completion_status: dict = Field(default_factory=dict)
    participant_id: int | None = None
    next_group: dict | None = None
    progress: dict = Field(default_factory=dict)
    session_complete: bool = False
    project_settings: dict = Field(default_factory=dict)
    next_questions: list[dict] = Field(default_factory=list)
    ranking_settings: dict = Field(default_factory=dict)
    viewer: dict | None = None
    submitter_summary: dict | None = None
    votes_captured: int = 0


class SharedProjectReportPayload(PvfWsResultPackage):
    share_result_status: PvfShareAccessConfirmed_Base | None = None
    project: SharedProjectSummary | None = None
    alternatives: list[dict] = Field(default_factory=list)
    factors: list[dict] = Field(default_factory=list)
    report: dict = Field(default_factory=dict)


class PairingForm(BaseModel):
    winner_id: int
    loser_id: int
    response: str = "winner"
    decision_seconds: float = 0.0
    presented_left_id: int | None = None
    presented_right_id: int | None = None
    effective_rule: str = "id_asc"


class GroupPackageForm(BaseModel):
    client_group_id: str = ""
    group_token: str | None = None
    pass_index: int = 1
    group_type: str = "alternative"
    criterion_id: int | None = None
    sort_algorithm: str = "ford_johnson"
    item_ids_initial: list[int] = Field(default_factory=list)
    rank_order: list[int] = Field(default_factory=list)
    pairings: list[PairingForm] = Field(default_factory=list)
    algorithm_version: str = ALGORITHM_VERSION
    event_timestamp: str | None = None


class ExternalCompleteGroupForm(PvfShareAccessRequest_Base):
    prior_group: GroupPackageForm | None = None
    share_kind: str | None = None


class ExternalNextGroupForm(PvfShareAccessRequest_Base):
    share_kind: str | None = None


class ExternalGroupResult(PvfWsResultPackage):
    share_result_status: PvfShareAccessConfirmed_Base | None = None
    group_info: dict | None = None
    participant_id: int | None = None
    personal_vote: dict | None = None
    next_group: dict | None = None
    progress: dict = Field(default_factory=dict)
    session_complete: bool = False
    project_settings: dict = Field(default_factory=dict)
    viewer: dict | None = None


class ExternalCompleteForm(PvfShareAccessRequest_Base):
    is_complete: bool = True
    share_kind: str | None = None


def _resolve_vote_share_type(share_kind: str | None) -> ShareType:
    kind = (share_kind or "vote").strip().lower()
    if kind in ("vote_view", "vote-view"):
        return ShareType.vote_view
    return ShareType.vote


def _project_settings(project) -> dict:
    if project is None:
        return {}
    mn = clamp_min_expected_passes(getattr(project, "min_expected_passes", None))
    mx = clamp_max_recommended_passes(getattr(project, "max_recommended_passes", None), mn)
    payload = {
        "min_expected_passes": mn,
        "max_recommended_passes": mx,
        "hard_max_passes": hard_max_passes(mx, mn),
        "project_exclusive_mode": bool(project.project_exclusive_mode),
        "option_questions_per_group": clamp_questions_per_group_stored(
            getattr(project, "option_questions_per_group", None)
        ),
        "factor_questions_per_group": clamp_questions_per_group_stored(
            getattr(project, "factor_questions_per_group", None)
        ),
        "option_questions_per_group_explicit": bool(
            getattr(project, "option_questions_per_group_explicit", False)
        ),
        "factor_questions_per_group_explicit": bool(
            getattr(project, "factor_questions_per_group_explicit", False)
        ),
        "ranking_mode": project_ranking_mode(project),
        "partial_flush_count": int(getattr(settings, "COMPARE_PARTIAL_FLUSH_COUNT", 5) or 5),
        "partial_idle_seconds": int(getattr(settings, "COMPARE_PARTIAL_IDLE_SECONDS", 90) or 90),
    }
    payload.update(project_end_time_payload(project))
    return payload


def _load_project_summary(session, link_info):
    project = CustomerProject.get_customer_project_by_id_system(
        session=session,
        customer_id=link_info.customer_id,
        id=link_info.shared_entity_db_id,
        clear_lock=False,
    )
    if project is None:
        return None, [], [], "Shared project was not found or is no longer available", None

    alternatives = CustomerProjectAlternatives.get_all_by_project_id_system(
        session=session, project_id=project.id, customer_id=link_info.customer_id, clear_lock=False)
    factors = CustomerProjectFactors.get_all_by_project_id_system(
        session=session, project_id=project.id, customer_id=link_info.customer_id, clear_lock=False)

    alt_dicts = [a.model_dump() for a in (alternatives or [])]
    factor_dicts = [f.model_dump() for f in (factors or [])]
    mn = clamp_min_expected_passes(getattr(project, "min_expected_passes", None))
    mx = clamp_max_recommended_passes(getattr(project, "max_recommended_passes", None), mn)

    customer = PvfCustomer.get_customer_by_id_system(
        session=session, id=link_info.customer_id, clear_lock=False
    )
    cust_img = PvfCustomerBrandingImage.get_by_customer_id_system(
        session=session, customer_id=link_info.customer_id, clear_lock=False
    )
    proj_img = PvfProjectBrandingImage.get_by_project_id_system(
        session=session,
        customer_id=link_info.customer_id,
        project_id=project.id,
        clear_lock=False,
    )

    summary = SharedProjectSummary(
        project_id=project.id,
        project_tag=project.project_tag,
        project_title=project.project_title,
        project_description=project.project_description,
        project_exclusive_mode=project.project_exclusive_mode,
        private_participation=bool(getattr(project, "private_participation", False)),
        participant_influence_mode=getattr(project, "participant_influence_mode", None) or "comparisons",
        participant_influence_min_comparisons=int(
            getattr(project, "participant_influence_min_comparisons", None) or 10
        ),
        factor_weight_floor_alpha=float(
            getattr(project, "factor_weight_floor_alpha", None) or 0.5
        ),
        min_expected_passes=mn,
        max_recommended_passes=mx,
        option_questions_per_group=clamp_questions_per_group_stored(
            getattr(project, "option_questions_per_group", None)
        ),
        factor_questions_per_group=clamp_questions_per_group_stored(
            getattr(project, "factor_questions_per_group", None)
        ),
        option_questions_per_group_explicit=bool(
            getattr(project, "option_questions_per_group_explicit", False)
        ),
        factor_questions_per_group_explicit=bool(
            getattr(project, "factor_questions_per_group_explicit", False)
        ),
        alternative_count=len(alt_dicts),
        factor_count=len(factor_dicts),
        disabled=bool(project.disabled),
        end_time=project.end_time,
        collection_ending_soon=collection_ending_soon(project.end_time),
        collection_closed=collection_is_closed(project.end_time),
        customer_name=customer.customer_name if customer else None,
        has_customer_branding_image=cust_img is not None,
        has_project_branding_image=proj_img is not None,
    )
    return summary, alt_dicts, factor_dicts, None, project


def _personal_vote_bundle(session, participant) -> dict | None:
    if participant is None:
        return None
    groups = ProjectVoteGroupResult.list_for_participant_system(
        session=session, participant_id=participant.id, clear_lock=False
    )
    comps = int(participant.comparison_count or 0)
    return {
        "participant": participant.model_dump(),
        "groups": [g.model_dump() for g in groups],
        "group_count": len(groups),
        "comparison_count": comps,
        "observation_count": comps,
        "is_complete": participant.is_complete,
    }


def _viewer_info(share_result, participant=None) -> dict:
    name = getattr(share_result, "viewer_personal_name", None) or (participant.display_name if participant else None)
    email = getattr(share_result, "viewer_captured_email", None) or (participant.email if participant else None)
    org = getattr(share_result, "viewer_organization_name", None)
    return {
        "display_name": name or None,
        "organization": org or None,
        "email": email or None,
    }


def _issue_next(session, *, project, participant, alts=None, factors=None, groups=None) -> dict:
    if groups is None and participant is not None:
        groups = ProjectVoteGroupResult.list_for_participant_system(
            session=session, participant_id=int(participant.id), clear_lock=False
        )
    result = pick_next_sort_group(
        project=project,
        alternatives=alts,
        factors=factors,
        groups=groups or [],
        seed=int(participant.id) if participant is not None else None,
    )
    group = result.get("group")
    if group and participant is not None:
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
        if issued_row.group_info is not None:
            group["status"] = issued_row.group_info.status
            group["pairings"] = list(issued_row.group_info.pairings or group.get("pairings") or [])
            result["group"] = group
        set_issued_group(
            scope=_SHARE_CACHE_SCOPE,
            project_id=int(project.id),
            participant_id=int(participant.id),
            group=group,
        )
    return result


def _resolve_share_participant(session, request: Request, link_info, share_result, access_info):
    view_token, view_cookie_display_name, view_cookie_email, _ = get_token_cookie(request)
    display_name = share_result.viewer_personal_name or view_cookie_display_name
    email = share_result.viewer_captured_email or view_cookie_email
    cookie_token = view_token
    if access_info is not None and getattr(access_info, "cookie_token", None):
        cookie_token = access_info.cookie_token
    part = ProjectVoteParticipant.get_or_create_share_participant(
        session=session,
        customer_id=link_info.customer_id,
        project_id=link_info.shared_entity_db_id,
        share_id=link_info.id,
        share_access_id=access_info.id if access_info is not None else share_result.link_access_id,
        cookie_token=cookie_token,
        display_name=display_name,
        email=email,
        email_verified=bool(getattr(share_result, "is_email_verified", False)),
        clear_lock=False,
    )
    return part.participant_info if part.participant_info else None


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


def _want_next(access_request) -> bool:
    if getattr(access_request, "request_next", True):
        return True
    return int(getattr(access_request, "request_next_count", 0) or 0) > 0


@router.post('/share/{shared_magic_token}/vote',
             summary="External share: access a project for comparing options/factors",
             tags=['share_ext'])
def shared_project_vote_access(session: SessionDep,
                                     request: Request, response: Response,
                                     access_request: RequestSharedProjectAccess,
                                     shared_magic_token: str,
                                     ) -> Union[SharedProjectVotePayload, ShareAccessDenied]:
    share_usr_context = PvfUserContext(limited_proxy=True,
                                    remote_ip=request.client.host if request.client else None,
                                    url_path=request.url.path[:150])
    share_request = PvfShareAccessRequest(**access_request.model_dump(),
                                       requested_target_token=shared_magic_token,
                                       requested_target_share_type=ShareType.vote,
                                       requested_target_share_operation=ShareAccessOperation.view)
    share_result, link_info, access_info = share_link_validate_and_log(
        session=session, share_usr_context=share_usr_context,
        request=request, response=response, share_request=share_request)
    if share_result.failure_reason not in (None, ""):
        return share_result

    summary, alts, factors, err, project_row = _load_project_summary(session, link_info)
    if err:
        return SharedProjectVotePayload(failure_reason=err, share_result_status=share_result)

    participant = _resolve_share_participant(session, request, link_info, share_result, access_info)
    personal = _personal_vote_bundle(session, participant)
    next_group = None
    progress: dict = {}
    session_complete = False
    if _want_next(access_request) and project_row is not None and not project_input_block_reason(project_row):
        issued = _issue_next(session, project=project_row, participant=participant, alts=alts, factors=factors)
        next_group = issued.get("group")
        progress = issued.get("progress") or {}
        session_complete = bool(issued.get("session_complete"))
    return SharedProjectVotePayload(
        share_result_status=share_result,
        project=summary,
        alternatives=alts,
        factors=factors,
        personal_vote=personal,
        participant_id=participant.id if participant else None,
        next_group=next_group,
        progress=progress,
        session_complete=session_complete,
        project_settings=_project_settings(project_row),
        viewer=_viewer_info(share_result, participant),
    )


@router.post('/share/{shared_magic_token}/vote/next-group',
             summary="External share: issue next sort group",
             tags=['share_ext'])
def shared_project_vote_next_group(session: SessionDep,
                                         request: Request, response: Response,
                                         form: ExternalNextGroupForm,
                                         shared_magic_token: str,
                                         ) -> Union[ExternalGroupResult, ShareAccessDenied]:
    share_usr_context = PvfUserContext(limited_proxy=True,
                                    remote_ip=request.client.host if request.client else None,
                                    url_path=request.url.path[:150])
    share_type = _resolve_vote_share_type(form.share_kind)
    share_request = PvfShareAccessRequest(
        display_name=form.display_name,
        verification_email=form.verification_email,
        verification_password=form.verification_password,
        verification_magic_email_key=form.verification_magic_email_key,
        authorize_verification_email=form.authorize_verification_email,
        requested_target_token=shared_magic_token,
        requested_target_share_type=share_type,
        requested_target_share_operation=ShareAccessOperation.vote,
    )
    share_result, link_info, access_info = share_link_validate_and_log(
        session=session, share_usr_context=share_usr_context,
        request=request, response=response, share_request=share_request)
    if share_result.failure_reason not in (None, ""):
        return share_result
    project = CustomerProject.get_customer_project_by_id_system(
        session=session, customer_id=link_info.customer_id, id=link_info.shared_entity_db_id, clear_lock=False
    )
    if project is None:
        return ExternalGroupResult(failure_reason="Shared project was not found", share_result_status=share_result)
    blocked = project_input_block_reason(project)
    if blocked:
        return ExternalGroupResult(failure_reason=blocked, share_result_status=share_result)
    participant = _resolve_share_participant(session, request, link_info, share_result, access_info)
    if participant is None:
        return ExternalGroupResult(failure_reason="Unable to resolve voter identity", share_result_status=share_result)
    summary, alts, factors, err, _ = _load_project_summary(session, link_info)
    issued = _issue_next(session, project=project, participant=participant, alts=alts, factors=factors)
    return ExternalGroupResult(
        share_result_status=share_result,
        participant_id=participant.id,
        personal_vote=_personal_vote_bundle(session, participant),
        next_group=issued.get("group"),
        progress=issued.get("progress") or {},
        session_complete=bool(issued.get("session_complete")),
        project_settings=_project_settings(project),
        viewer=_viewer_info(share_result, participant),
    )


@router.post('/share/{shared_magic_token}/vote/complete-group',
             summary="External share: submit completed sort group and get next",
             tags=['share_ext'])
def shared_project_vote_complete_group(session: SessionDep,
                                             request: Request, response: Response,
                                             form: ExternalCompleteGroupForm,
                                             shared_magic_token: str,
                                             ) -> Union[ExternalGroupResult, ShareAccessDenied]:
    share_usr_context = PvfUserContext(limited_proxy=True,
                                    remote_ip=request.client.host if request.client else None,
                                    url_path=request.url.path[:150])
    share_type = _resolve_vote_share_type(form.share_kind)
    share_request = PvfShareAccessRequest(
        display_name=form.display_name,
        verification_email=form.verification_email,
        verification_password=form.verification_password,
        verification_magic_email_key=form.verification_magic_email_key,
        authorize_verification_email=form.authorize_verification_email,
        requested_target_token=shared_magic_token,
        requested_target_share_type=share_type,
        requested_target_share_operation=ShareAccessOperation.vote,
    )
    share_result, link_info, access_info = share_link_validate_and_log(
        session=session, share_usr_context=share_usr_context,
        request=request, response=response, share_request=share_request)
    if share_result.failure_reason not in (None, ""):
        return share_result
    project = CustomerProject.get_customer_project_by_id_system(
        session=session, customer_id=link_info.customer_id, id=link_info.shared_entity_db_id, clear_lock=False
    )
    if project is None:
        return ExternalGroupResult(failure_reason="Shared project was not found", share_result_status=share_result)
    blocked = project_input_block_reason(project)
    if blocked:
        return ExternalGroupResult(failure_reason=blocked, share_result_status=share_result)
    participant = _resolve_share_participant(session, request, link_info, share_result, access_info)
    if participant is None:
        return ExternalGroupResult(failure_reason="Unable to resolve voter identity", share_result_status=share_result)

    group_info = None
    if form.prior_group is not None:
        pkg = form.prior_group.model_dump()
        issued = get_issued_group(
            scope=_SHARE_CACHE_SCOPE,
            project_id=int(project.id),
            participant_id=int(participant.id),
        )
        token = package_group_id(pkg)
        if token:
            pkg["client_group_id"] = token
        known = (
            ProjectVoteGroupResult.get_by_client_group_id(
                session=session, participant_id=int(participant.id), client_group_id=token, clear_lock=False,
            ) if token else None
        )
        if known is None and token:
            known = ProjectVoteGroupResult.get_by_group_token(
                session=session, group_token=token, participant_id=int(participant.id), clear_lock=False,
            )
        if known is not None:
            # Retry/update of an already-issued group: the stored row is authoritative
            # even though the issuance cache may already hold a newer follow-up group.
            pkg["item_ids_initial"] = [int(x) for x in (known.item_ids_initial or [])]
            err = validate_group_package(None, pkg)
        else:
            err = validate_group_package(issued, pkg)
        if err:
            return ExternalGroupResult(failure_reason=err, share_result_status=share_result)
        if issued and package_group_id(issued) == token:
            pkg["item_ids_initial"] = list(issued.get("item_ids") or pkg.get("item_ids_initial") or [])
            pkg["pass_index"] = int(issued.get("pass_index") or pkg.get("pass_index") or 1)
            pkg["group_type"] = issued.get("group_type") or pkg.get("group_type")
            pkg["criterion_id"] = issued.get("criterion_id") if "criterion_id" in issued else pkg.get("criterion_id")
            pkg["sort_algorithm"] = issued.get("sort_algorithm") or pkg.get("sort_algorithm")
        pairings = [normalize_pairing(p) for p in (pkg.get("pairings") or [])]
        created = ProjectVoteGroupResult.create_group_result(
            session=session,
            participant=participant,
            group_type=_parse_group_type(str(pkg.get("group_type") or "alternative")),
            criterion_id=pkg.get("criterion_id"),
            sort_algorithm=_parse_algo(str(pkg.get("sort_algorithm") or "ford_johnson")),
            pass_index=int(pkg.get("pass_index") or 1),
            item_ids_initial=[int(x) for x in (pkg.get("item_ids_initial") or [])],
            rank_order=[int(x) for x in (pkg.get("rank_order") or [])],
            pairings=pairings,
            client_group_id=token or str(pkg.get("client_group_id") or ""),
            algorithm_version=str(pkg.get("algorithm_version") or ALGORITHM_VERSION),
            event_timestamp=parse_event_timestamp(pkg.get("event_timestamp")),
            clear_lock=False,
        )
        if created.failure_reason:
            return ExternalGroupResult(
                failure_reason=created.failure_reason,
                share_result_status=share_result,
                participant_id=participant.id,
            )
        group_info = created.group_info.model_dump() if created.group_info else None
        participant = ProjectVoteParticipant.get_by_id_system(
            session=session, participant_id=int(participant.id), clear_lock=False
        )

    summary, alts, factors, err, _ = _load_project_summary(session, link_info)
    issued = _issue_next(session, project=project, participant=participant, alts=alts, factors=factors)
    return ExternalGroupResult(
        share_result_status=share_result,
        group_info=group_info,
        participant_id=participant.id if participant else None,
        personal_vote=_personal_vote_bundle(session, participant),
        next_group=issued.get("group"),
        progress=issued.get("progress") or {},
        session_complete=bool(issued.get("session_complete")),
        project_settings=_project_settings(project),
        viewer=_viewer_info(share_result, participant),
    )


@router.post('/share/{shared_magic_token}/vote/save-group',
             summary="External share: save in-progress pairings for the current compare group",
             tags=['share_ext'])
def shared_project_vote_save_group(session: SessionDep,
                                         request: Request, response: Response,
                                         form: ExternalCompleteGroupForm,
                                         shared_magic_token: str,
                                         ) -> Union[ExternalGroupResult, ShareAccessDenied]:
    share_usr_context = PvfUserContext(limited_proxy=True,
                                    remote_ip=request.client.host if request.client else None,
                                    url_path=request.url.path[:150])
    share_type = _resolve_vote_share_type(form.share_kind)
    share_request = PvfShareAccessRequest(
        display_name=form.display_name,
        verification_email=form.verification_email,
        verification_password=form.verification_password,
        verification_magic_email_key=form.verification_magic_email_key,
        authorize_verification_email=form.authorize_verification_email,
        requested_target_token=shared_magic_token,
        requested_target_share_type=share_type,
        requested_target_share_operation=ShareAccessOperation.vote,
    )
    share_result, link_info, access_info = share_link_validate_and_log(
        session=session, share_usr_context=share_usr_context,
        request=request, response=response, share_request=share_request)
    if share_result.failure_reason not in (None, ""):
        return share_result
    project = CustomerProject.get_customer_project_by_id_system(
        session=session, customer_id=link_info.customer_id, id=link_info.shared_entity_db_id, clear_lock=False
    )
    if project is None:
        return ExternalGroupResult(failure_reason="Shared project was not found", share_result_status=share_result)
    blocked = project_input_block_reason(project)
    if blocked:
        return ExternalGroupResult(failure_reason=blocked, share_result_status=share_result)
    participant = _resolve_share_participant(session, request, link_info, share_result, access_info)
    if participant is None:
        return ExternalGroupResult(failure_reason="Unable to resolve voter identity", share_result_status=share_result)
    if form.prior_group is None:
        return ExternalGroupResult(failure_reason="Group package required", share_result_status=share_result)
    pkg = form.prior_group.model_dump()
    token = package_group_id(pkg)
    if token:
        pkg["client_group_id"] = token
    issued = get_issued_group(
        scope=_SHARE_CACHE_SCOPE,
        project_id=int(project.id),
        participant_id=int(participant.id),
    )
    err = validate_group_package(issued, pkg, require_rank_order=False)
    if err:
        return ExternalGroupResult(failure_reason=err, share_result_status=share_result)
    pairings = [normalize_pairing(p) for p in (pkg.get("pairings") or [])]
    saved = ProjectVoteGroupResult.save_group_pairings(
        session=session,
        participant=participant,
        client_group_id=token,
        pairings=pairings,
        rank_order=[int(x) for x in (pkg.get("rank_order") or [])] or None,
        event_timestamp=parse_event_timestamp(pkg.get("event_timestamp")),
        clear_lock=False,
    )
    if saved.failure_reason:
        return ExternalGroupResult(
            failure_reason=saved.failure_reason,
            share_result_status=share_result,
            participant_id=participant.id,
        )
    groups = ProjectVoteGroupResult.list_for_participant_system(
        session=session, participant_id=int(participant.id), clear_lock=False
    )
    return ExternalGroupResult(
        share_result_status=share_result,
        group_info=saved.group_info.model_dump() if saved.group_info else None,
        participant_id=participant.id,
        next_group=issued,
        progress={"ranking_evidence": ranking_evidence_from_groups(groups)},
        session_complete=False,
        project_settings=_project_settings(project),
        viewer=_viewer_info(share_result, participant),
    )


@router.post('/share/{shared_magic_token}/vote/complete',
             summary="External share: mark comparison session complete",
             tags=['share_ext'])
def shared_project_vote_complete(session: SessionDep,
                                       request: Request, response: Response,
                                       form: ExternalCompleteForm,
                                       shared_magic_token: str,
                                       ) -> Union[SharedProjectVoteViewPayload, ShareAccessDenied]:
    share_usr_context = PvfUserContext(limited_proxy=True,
                                    remote_ip=request.client.host if request.client else None,
                                    url_path=request.url.path[:150])
    share_type = _resolve_vote_share_type(form.share_kind)
    share_request = PvfShareAccessRequest(
        display_name=form.display_name,
        verification_email=form.verification_email,
        verification_password=form.verification_password,
        verification_magic_email_key=form.verification_magic_email_key,
        authorize_verification_email=form.authorize_verification_email,
        requested_target_token=shared_magic_token,
        requested_target_share_type=share_type,
        requested_target_share_operation=ShareAccessOperation.vote,
    )
    share_result, link_info, access_info = share_link_validate_and_log(
        session=session, share_usr_context=share_usr_context,
        request=request, response=response, share_request=share_request)
    if share_result.failure_reason not in (None, ""):
        return share_result
    participant = _resolve_share_participant(session, request, link_info, share_result, access_info)
    if participant is None:
        return SharedProjectVoteViewPayload(failure_reason="Unable to resolve voter identity", share_result_status=share_result)
    participant.mark_activity(session=session, is_complete=form.is_complete, clear_lock=False)
    summary, alts, factors, err, project_row = _load_project_summary(session, link_info)
    personal = _personal_vote_bundle(session, participant)
    votes_captured = personal["comparison_count"] if personal else 0
    email_tied = bool(participant.email) or bool(getattr(link_info, "shared_with_email", None))
    all_parts = ProjectVoteParticipant.list_for_project_system(
        session=session, customer_id=link_info.customer_id, project_id=link_info.shared_entity_db_id, clear_lock=False
    )
    completion = {
        "alternative_count": len(alts),
        "factor_count": len(factors),
        "votes_recorded": len(all_parts) if email_tied else 1,
        "my_observation_count": votes_captured,
        "my_comparison_count": votes_captured,
        "my_group_count": personal["group_count"] if personal else 0,
        "is_complete": participant.is_complete,
        "completion_ratio": min(1.0, (personal or {}).get("group_count", 0) / max(1, 2)),
        "email_tied": email_tied,
    }
    submitter_summary = None
    if share_type == ShareType.vote_view:
        groups = (personal or {}).get("groups") or []
        submitter_summary = build_personal_submitter_summary(
            alternatives=alts,
            factors=factors,
            groups=groups,
            exclusive_mode=bool(project_row.project_exclusive_mode) if project_row else False,
            settings=ranking_settings_with_project_influence(
                ranking_settings_from_customer(None), project_row,
            ),
        )
    invalidate_participant(scope=_SHARE_CACHE_SCOPE, project_id=participant.project_id, participant_id=participant.id)
    return SharedProjectVoteViewPayload(
        share_result_status=share_result,
        project=summary,
        alternatives=alts,
        factors=factors,
        personal_vote=personal,
        completion_status=completion,
        participant_id=participant.id,
        project_settings=_project_settings(project_row),
        viewer=_viewer_info(share_result, participant),
        submitter_summary=submitter_summary,
        votes_captured=votes_captured,
    )


@router.post('/share/{shared_magic_token}/vote-view',
             summary="External share: compare + personal results after complete",
             tags=['share_ext'])
def shared_project_vote_view_access(session: SessionDep,
                                          request: Request, response: Response,
                                          access_request: RequestSharedProjectAccess,
                                          shared_magic_token: str,
                                          ) -> Union[SharedProjectVoteViewPayload, ShareAccessDenied]:
    share_usr_context = PvfUserContext(limited_proxy=True,
                                    remote_ip=request.client.host if request.client else None,
                                    url_path=request.url.path[:150])
    share_request = PvfShareAccessRequest(**access_request.model_dump(),
                                       requested_target_token=shared_magic_token,
                                       requested_target_share_type=ShareType.vote_view,
                                       requested_target_share_operation=ShareAccessOperation.view)
    share_result, link_info, access_info = share_link_validate_and_log(
        session=session, share_usr_context=share_usr_context,
        request=request, response=response, share_request=share_request)
    if share_result.failure_reason not in (None, ""):
        return share_result

    summary, alts, factors, err, project_row = _load_project_summary(session, link_info)
    if err:
        return SharedProjectVoteViewPayload(failure_reason=err, share_result_status=share_result)

    participant = _resolve_share_participant(session, request, link_info, share_result, access_info)
    personal = _personal_vote_bundle(session, participant)
    is_complete = bool(personal and personal.get("is_complete"))
    my_count = personal["comparison_count"] if personal else 0
    email_tied = bool(participant and participant.email) or bool(getattr(link_info, "shared_with_email", None))
    all_parts = ProjectVoteParticipant.list_for_project_system(
        session=session, customer_id=link_info.customer_id, project_id=link_info.shared_entity_db_id, clear_lock=False
    )
    completion = {
        "alternative_count": len(alts),
        "factor_count": len(factors),
        "votes_recorded": len(all_parts) if email_tied else (1 if participant else 0),
        "my_observation_count": my_count,
        "my_comparison_count": my_count,
        "my_group_count": personal["group_count"] if personal else 0,
        "completion_ratio": min(1.0, (personal or {}).get("group_count", 0) / max(1, 2)),
        "is_complete": is_complete,
        "email_tied": email_tied,
    }
    next_group = None
    progress: dict = {}
    session_complete = False
    if not is_complete and project_row is not None and not project_input_block_reason(project_row) and _want_next(access_request):
        issued = _issue_next(session, project=project_row, participant=participant, alts=alts, factors=factors)
        next_group = issued.get("group")
        progress = issued.get("progress") or {}
        session_complete = bool(issued.get("session_complete"))
    submitter_summary = None
    if is_complete:
        groups = (personal or {}).get("groups") or []
        submitter_summary = build_personal_submitter_summary(
            alternatives=alts,
            factors=factors,
            groups=groups,
            exclusive_mode=bool(project_row.project_exclusive_mode) if project_row else False,
            settings=ranking_settings_with_project_influence(
                ranking_settings_from_customer(None), project_row,
            ),
        )
    return SharedProjectVoteViewPayload(
        share_result_status=share_result,
        project=summary,
        alternatives=alts,
        factors=factors,
        personal_vote=personal,
        completion_status=completion,
        participant_id=participant.id if participant else None,
        next_group=next_group,
        progress=progress,
        session_complete=session_complete,
        project_settings=_project_settings(project_row),
        viewer=_viewer_info(share_result, participant),
        submitter_summary=submitter_summary,
        votes_captured=my_count,
    )


@router.post('/share/{shared_magic_token}/report',
             summary="External share: full project results report",
             tags=['share_ext'])
def shared_project_report_access(session: SessionDep,
                                       request: Request, response: Response,
                                       access_request: RequestSharedProjectAccess,
                                       shared_magic_token: str,
                                       ) -> Union[SharedProjectReportPayload, ShareAccessDenied]:
    share_usr_context = PvfUserContext(limited_proxy=True,
                                    remote_ip=request.client.host if request.client else None,
                                    url_path=request.url.path[:150])
    share_request = PvfShareAccessRequest(**access_request.model_dump(),
                                       requested_target_token=shared_magic_token,
                                       requested_target_share_type=ShareType.report,
                                       requested_target_share_operation=ShareAccessOperation.report)
    share_result, link_info, _access_info = share_link_validate_and_log(
        session=session, share_usr_context=share_usr_context,
        request=request, response=response, share_request=share_request)
    if share_result.failure_reason not in (None, ""):
        return share_result

    summary, alts, factors, err, project_row = _load_project_summary(session, link_info)
    if err:
        return SharedProjectReportPayload(failure_reason=err, share_result_status=share_result)

    participants = ProjectVoteParticipant.list_for_project_system(
        session=session, customer_id=link_info.customer_id, project_id=link_info.shared_entity_db_id, clear_lock=False
    )
    groups = ProjectVoteGroupResult.list_for_project_system(
        session=session, customer_id=link_info.customer_id, project_id=link_info.shared_entity_db_id, clear_lock=True
    )
    from ..utils.ai.report import build_report_with_ai_baseline

    report = build_report_with_ai_baseline(
        alternatives=alts,
        factors=factors,
        exclusive_mode=bool(summary.project_exclusive_mode),
        all_groups=groups,
        participants=participants,
        settings=ranking_settings_with_project_influence(
            ranking_settings_from_customer(None), project_row,
        ),
    )
    if summary.private_participation:
        report = redact_report_identities(report)
    else:
        report["private_participation"] = False
    return SharedProjectReportPayload(
        share_result_status=share_result,
        project=summary,
        alternatives=alts,
        factors=factors,
        report=report,
    )


@router.get('/share/{shared_magic_token}/logout',
             summary="Clear the stored cookie associated with this shared_magic_token if any",
             tags=['share_ext'])
def share_logout(session: SessionDep,
                       request: Request, response: Response,
                       shared_magic_token: str,
                       ) -> None:
    share_usr_context = PvfUserContext(limited_proxy=True,
                                    remote_ip=request.client.host if request.client else None,
                                    url_path=request.url.path[:150])
    for share_type, op in (
        (ShareType.vote, ShareAccessOperation.view),
        (ShareType.vote_view, ShareAccessOperation.view),
        (ShareType.report, ShareAccessOperation.report),
    ):
        share_request = PvfShareAccessRequest(
            requested_target_token=shared_magic_token,
            requested_target_share_type=share_type,
            requested_target_share_operation=op,
            request_logout=True,
        )
        try:
            share_link_validate_and_log(
                session=session, share_usr_context=share_usr_context,
                request=request, response=response, share_request=share_request)
            return
        except HTTPException:
            continue
    return
