from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field

from fastapi import APIRouter, status, HTTPException

from ..pvf.bindings.pvf_services import SessionDep, UserAccessDep, PvfWsResultPackage
from ..config.config_settings import settings

from ..db.models.customer_projects import CustomerProject
from ..db.models.customer_project_alternatives_criteria import (
    CustomerProjectAlternatives,
    CustomerProjectFactors,
)
from ..db.models.project_vote_events import (
    ProjectVoteParticipant,
    ProjectVoteGroupResult,
    ProjectVoteParticipantResult_One,
    ProjectVoteParticipantResult_Many,
    GroupType,
    SortAlgorithm,
    GroupStatus,
)
from ..utils.vote_ranking import (
    build_report,
    ranking_settings_with_project_influence,
    build_pivot_detail,
    build_personal_submitter_summary,
    ranking_settings_from_customer,
)
from ..utils.ai.report import build_report_with_ai_baseline
from ..utils.ai.identity import is_ai_participant, partition_vote_data
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
from ..utils.private_participation import (
    redact_participant_list,
    redact_report_identities,
    redact_pivot_detail_identities,
)
from ..utils.next_group_cache import get_issued_group, set_issued_group, invalidate_participant
from ..utils.sort_compare import (
    clamp_min_expected_passes,
    clamp_max_recommended_passes,
    clamp_questions_per_group_stored,
    hard_max_passes,
)
from ..utils.project_end_time import (
    project_end_time_payload,
    project_input_block_reason,
)

router = APIRouter()

_SESSION_CACHE_SCOPE = "session"


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


class CompleteGroupForm(BaseModel):
    project_id: int
    prior_group: GroupPackageForm | None = None


class NextGroupForm(BaseModel):
    project_id: int


class ParticipantCompleteForm(BaseModel):
    project_id: int
    is_complete: bool = True


class ProjectReportRequest(BaseModel):
    project_id: int
    include_participants: bool = True
    coherence_method: str | None = None


class ProjectPivotDetailRequest(BaseModel):
    project_id: int
    primary_axis: str = Field(default="participants", description="Pivot axis: alternatives (options) | factors | participants")
    row_id: int | None = None
    alternative_id: int | None = None
    factor_id: int | None = None
    participant_id: int | None = None


class ProjectReportResult(PvfWsResultPackage):
    project_id: int | None = None
    report: dict = Field(default_factory=dict)


class ProjectPivotDetailResult(PvfWsResultPackage):
    project_id: int | None = None
    detail: dict = Field(default_factory=dict)


class SortSessionResult(PvfWsResultPackage):
    participant_info: ProjectVoteParticipant | None = None
    groups: list[ProjectVoteGroupResult] = Field(default_factory=list)
    next_group: dict | None = None
    progress: dict = Field(default_factory=dict)
    session_complete: bool = False
    project_settings: dict = Field(default_factory=dict)


class CompleteGroupResult(PvfWsResultPackage):
    participant_info: ProjectVoteParticipant | None = None
    group_info: ProjectVoteGroupResult | None = None
    groups: list[ProjectVoteGroupResult] = Field(default_factory=list)
    next_group: dict | None = None
    progress: dict = Field(default_factory=dict)
    session_complete: bool = False
    project_settings: dict = Field(default_factory=dict)


class ParticipantBundleResult(PvfWsResultPackage):
    participant_info: ProjectVoteParticipant | None = None
    groups: list[ProjectVoteGroupResult] = Field(default_factory=list)
    # legacy aliases for transitional clients
    observations: list = Field(default_factory=list)
    next_group: dict | None = None
    progress: dict = Field(default_factory=dict)
    session_complete: bool = False
    project_settings: dict = Field(default_factory=dict)


class ParticipantCompleteResult(PvfWsResultPackage):
    participant_info: ProjectVoteParticipant | None = None
    votes_captured: int = 0
    groups_captured: int = 0
    submitter_summary: dict | None = None
    personal_vote: dict | None = None


class ProjectVoteBundleResult(PvfWsResultPackage):
    project_id: int | None = None
    participants: list[ProjectVoteParticipant] = Field(default_factory=list)
    groups: list[ProjectVoteGroupResult] = Field(default_factory=list)
    observations: list = Field(default_factory=list)
    report: dict = Field(default_factory=dict)


def _require_project(session, usr_context, project_id: int):
    result = CustomerProject.get_customer_project_by_id(
        session=session, id=project_id, usr_context=usr_context, clear_lock=False
    )
    if result.failure_reason or result.customer_project_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.failure_reason or "Project not found")
    return result.customer_project_info


def _project_settings_payload(project: CustomerProject) -> dict:
    mn = clamp_min_expected_passes(getattr(project, "min_expected_passes", None))
    mx = clamp_max_recommended_passes(getattr(project, "max_recommended_passes", None), mn)
    payload = {
        "min_expected_passes": mn,
        "max_recommended_passes": mx,
        "hard_max_passes": hard_max_passes(mx, mn),
        "project_exclusive_mode": bool(project.project_exclusive_mode),
        "participant_influence_mode": getattr(project, "participant_influence_mode", "comparisons"),
        "participant_influence_min_comparisons": int(
            getattr(project, "participant_influence_min_comparisons", 10) or 10
        ),
        "factor_weight_floor_alpha": float(
            getattr(project, "factor_weight_floor_alpha", 0.5) or 0.5
        ),
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


def _load_content(session, project: CustomerProject):
    alts = CustomerProjectAlternatives.get_all_by_project_id_system(
        session=session, project_id=project.id, customer_id=project.customer_id, clear_lock=False
    ) or []
    factors = CustomerProjectFactors.get_all_by_project_id_system(
        session=session, project_id=project.id, customer_id=project.customer_id, clear_lock=False
    ) or []
    return alts, factors


def _issue_next(
    session,
    *,
    scope: str,
    project: CustomerProject,
    participant: ProjectVoteParticipant,
    groups: list | None = None,
) -> dict:
    alts, factors = _load_content(session, project)
    if groups is None:
        groups = ProjectVoteGroupResult.list_for_participant_system(
            session=session, participant_id=int(participant.id), clear_lock=False
        )
    result = pick_next_sort_group(
        project=project,
        alternatives=alts,
        factors=factors,
        groups=groups,
        seed=int(participant.id),
    )
    group = result.get("group")
    if group:
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
        scope=scope,
        project_id=int(project.id),
        participant_id=int(participant.id),
        group=group,
    )
    return result


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


@router.post(
    "/project-votes/ensure-participant",
    summary="Ensure a compare participant row exists for the current logged-in user on a project",
    tags=["project-votes"],
)
def ensure_session_participant(
    session: SessionDep,
    usr_context: UserAccessDep,
    project_id: int,
) -> ProjectVoteParticipantResult_One:
    return ProjectVoteParticipant.get_or_create_session_participant(
        session=session, usr_context=usr_context, project_id=project_id
    )


@router.get(
    "/project-votes/my-vote",
    summary="Return the current user's participant record, completed groups, and next sort group",
    tags=["project-votes"],
)
def get_my_vote(
    session: SessionDep,
    usr_context: UserAccessDep,
    project_id: int,
    request_next: bool = True,
) -> ParticipantBundleResult:
    project = _require_project(session, usr_context, project_id)
    part = ProjectVoteParticipant.get_or_create_session_participant(
        session=session, usr_context=usr_context, project_id=project_id, clear_lock=False
    )
    if part.failure_reason or part.participant_info is None:
        return ParticipantBundleResult(failure_reason=part.failure_reason, log_id=part.log_id)
    groups = ProjectVoteGroupResult.list_for_participant_system(
        session=session, participant_id=part.participant_info.id, clear_lock=False
    )
    next_group = None
    progress: dict = {}
    session_complete = False
    if request_next and not project_input_block_reason(project):
        issued = _issue_next(
            session, scope=_SESSION_CACHE_SCOPE, project=project, participant=part.participant_info, groups=groups
        )
        next_group = issued.get("group")
        progress = issued.get("progress") or {}
        session_complete = bool(issued.get("session_complete"))
        groups = ProjectVoteGroupResult.list_for_participant_system(
            session=session, participant_id=part.participant_info.id, clear_lock=False
        )
    return ParticipantBundleResult(
        participant_info=part.participant_info,
        groups=groups,
        observations=[],
        next_group=next_group,
        progress=progress,
        session_complete=session_complete,
        project_settings=_project_settings_payload(project),
    )


@router.post(
    "/project-votes/next-group",
    summary="Issue the next sort group for the current user (no prior package)",
    tags=["project-votes"],
)
def next_group(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: NextGroupForm,
) -> SortSessionResult:
    project = _require_project(session, usr_context, form.project_id)
    blocked = project_input_block_reason(project)
    if blocked:
        return SortSessionResult(failure_reason=blocked)
    part = ProjectVoteParticipant.get_or_create_session_participant(
        session=session, usr_context=usr_context, project_id=form.project_id, clear_lock=False
    )
    if part.failure_reason or part.participant_info is None:
        return SortSessionResult(failure_reason=part.failure_reason, log_id=part.log_id)
    groups = ProjectVoteGroupResult.list_for_participant_system(
        session=session, participant_id=part.participant_info.id, clear_lock=False
    )
    issued = _issue_next(
        session, scope=_SESSION_CACHE_SCOPE, project=project, participant=part.participant_info, groups=groups
    )
    return SortSessionResult(
        participant_info=part.participant_info,
        groups=groups,
        next_group=issued.get("group"),
        progress=issued.get("progress") or {},
        session_complete=bool(issued.get("session_complete")),
        project_settings=_project_settings_payload(project),
    )


@router.post(
    "/project-votes/complete-group",
    summary="Record a completed sort group and return the next group",
    tags=["project-votes"],
)
def complete_group(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: CompleteGroupForm,
) -> CompleteGroupResult:
    project = _require_project(session, usr_context, form.project_id)
    blocked = project_input_block_reason(project)
    if blocked:
        return CompleteGroupResult(failure_reason=blocked)
    part = ProjectVoteParticipant.get_or_create_session_participant(
        session=session, usr_context=usr_context, project_id=form.project_id, clear_lock=False
    )
    if part.failure_reason or part.participant_info is None:
        return CompleteGroupResult(failure_reason=part.failure_reason, log_id=part.log_id)

    group_info = None
    if form.prior_group is not None:
        pkg = form.prior_group.model_dump()
        issued = get_issued_group(
            scope=_SESSION_CACHE_SCOPE,
            project_id=int(project.id),
            participant_id=int(part.participant_info.id),
        )
        token = package_group_id(pkg)
        if token:
            pkg["client_group_id"] = token
        known = (
            ProjectVoteGroupResult.get_by_client_group_id(
                session=session, participant_id=int(part.participant_info.id), client_group_id=token, clear_lock=False,
            ) if token else None
        )
        if known is None and token:
            known = ProjectVoteGroupResult.get_by_group_token(
                session=session, group_token=token, participant_id=int(part.participant_info.id), clear_lock=False,
            )
        if known is not None:
            # Retry/update of an already-issued group: the stored row is authoritative
            # even though the issuance cache may already hold a newer follow-up group.
            pkg["item_ids_initial"] = [int(x) for x in (known.item_ids_initial or [])]
            err = validate_group_package(None, pkg)
        else:
            err = validate_group_package(issued, pkg)
        if err:
            return CompleteGroupResult(failure_reason=err)
        if issued and package_group_id(issued) == token:
            # prefer issued metadata
            pkg["item_ids_initial"] = list(issued.get("item_ids") or pkg.get("item_ids_initial") or [])
            pkg["pass_index"] = int(issued.get("pass_index") or pkg.get("pass_index") or 1)
            pkg["group_type"] = issued.get("group_type") or pkg.get("group_type")
            pkg["criterion_id"] = issued.get("criterion_id") if "criterion_id" in issued else pkg.get("criterion_id")
            pkg["sort_algorithm"] = issued.get("sort_algorithm") or pkg.get("sort_algorithm")

        pairings = [normalize_pairing(p) for p in (pkg.get("pairings") or [])]
        created = ProjectVoteGroupResult.create_group_result(
            session=session,
            participant=part.participant_info,
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
            return CompleteGroupResult(failure_reason=created.failure_reason, log_id=created.log_id)
        group_info = created.group_info
        # refresh participant
        part.participant_info = ProjectVoteParticipant.get_by_id_system(
            session=session, participant_id=int(part.participant_info.id), clear_lock=False
        )

    groups = ProjectVoteGroupResult.list_for_participant_system(
        session=session, participant_id=int(part.participant_info.id), clear_lock=False
    )
    issued = _issue_next(
        session, scope=_SESSION_CACHE_SCOPE, project=project, participant=part.participant_info, groups=groups
    )
    return CompleteGroupResult(
        participant_info=part.participant_info,
        group_info=group_info,
        groups=groups,
        next_group=issued.get("group"),
        progress=issued.get("progress") or {},
        session_complete=bool(issued.get("session_complete")),
        project_settings=_project_settings_payload(project),
    )


@router.post(
    "/project-votes/save-group",
    summary="Save in-progress pairings for the current compare group",
    tags=["project-votes"],
)
def save_group(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: CompleteGroupForm,
) -> CompleteGroupResult:
    project = _require_project(session, usr_context, form.project_id)
    blocked = project_input_block_reason(project)
    if blocked:
        return CompleteGroupResult(failure_reason=blocked)
    part = ProjectVoteParticipant.get_or_create_session_participant(
        session=session, usr_context=usr_context, project_id=form.project_id, clear_lock=False
    )
    if part.failure_reason or part.participant_info is None:
        return CompleteGroupResult(failure_reason=part.failure_reason, log_id=part.log_id)
    if form.prior_group is None:
        return CompleteGroupResult(failure_reason="Group package required")
    pkg = form.prior_group.model_dump()
    token = package_group_id(pkg)
    if token:
        pkg["client_group_id"] = token
    issued = get_issued_group(
        scope=_SESSION_CACHE_SCOPE,
        project_id=int(project.id),
        participant_id=int(part.participant_info.id),
    )
    err = validate_group_package(issued, pkg, require_rank_order=False)
    if err:
        return CompleteGroupResult(failure_reason=err)
    pairings = [normalize_pairing(p) for p in (pkg.get("pairings") or [])]
    saved = ProjectVoteGroupResult.save_group_pairings(
        session=session,
        participant=part.participant_info,
        client_group_id=token,
        pairings=pairings,
        rank_order=[int(x) for x in (pkg.get("rank_order") or [])] or None,
        event_timestamp=parse_event_timestamp(pkg.get("event_timestamp")),
        clear_lock=False,
    )
    if saved.failure_reason:
        return CompleteGroupResult(failure_reason=saved.failure_reason, log_id=saved.log_id)
    groups = ProjectVoteGroupResult.list_for_participant_system(
        session=session, participant_id=int(part.participant_info.id), clear_lock=False
    )
    return CompleteGroupResult(
        participant_info=part.participant_info,
        group_info=saved.group_info,
        groups=groups,
        next_group=issued,
        progress={"ranking_evidence": ranking_evidence_from_groups(groups)},
        session_complete=False,
        project_settings=_project_settings_payload(project),
    )


@router.post(
    "/project-votes/mark-complete",
    summary="Mark the current user's comparison session complete or reopen it",
    tags=["project-votes"],
)
def mark_participant_complete(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: ParticipantCompleteForm,
) -> ParticipantCompleteResult:
    project = _require_project(session, usr_context, form.project_id)
    part = ProjectVoteParticipant.get_or_create_session_participant(
        session=session, usr_context=usr_context, project_id=form.project_id, clear_lock=False
    )
    if part.failure_reason or part.participant_info is None:
        return ParticipantCompleteResult(failure_reason=part.failure_reason, log_id=part.log_id)
    updated = part.participant_info.mark_activity(session=session, is_complete=form.is_complete, clear_lock=False)
    groups = ProjectVoteGroupResult.list_for_participant_system(
        session=session, participant_id=updated.id, clear_lock=False
    )
    alts, factors = _load_content(session, project)
    summary = build_personal_submitter_summary(
        alternatives=[a.model_dump() for a in alts],
        factors=[f.model_dump() for f in factors],
        groups=groups,
        exclusive_mode=bool(project.project_exclusive_mode),
        settings=ranking_settings_with_project_influence(
            ranking_settings_from_customer(None), project,
        ),
    )
    participant_payload = ProjectVoteParticipant.model_validate(updated.model_dump())
    groups_n = len(groups)
    comps_n = int(updated.comparison_count or 0)
    is_complete = bool(updated.is_complete)
    invalidate_participant(scope=_SESSION_CACHE_SCOPE, project_id=form.project_id, participant_id=int(updated.id))
    session.close()
    return ParticipantCompleteResult(
        participant_info=participant_payload,
        votes_captured=comps_n,
        groups_captured=groups_n,
        submitter_summary=summary,
        personal_vote={
            "participant": participant_payload.model_dump(),
            "groups": [g.model_dump() for g in groups],
            "group_count": groups_n,
            "comparison_count": comps_n,
            "observation_count": comps_n,
            "is_complete": is_complete,
        },
    )


@router.get(
    "/project-votes/participants",
    summary="List unique compare participants for a project",
    tags=["project-votes"],
)
def list_participants(
    session: SessionDep,
    usr_context: UserAccessDep,
    project_id: int,
) -> ProjectVoteParticipantResult_Many:
    project = _require_project(session, usr_context, project_id)
    result = ProjectVoteParticipant.list_for_project(
        session=session, usr_context=usr_context, project_id=project_id
    )
    if result.failure_reason or not getattr(project, "private_participation", False):
        return result
    rows = result.participant_info_list or []
    result.participant_info_list = redact_participant_list(rows)
    return result


@router.get(
    "/project-votes/participant-detail",
    summary="Return one participant's groups (project owner/admin view)",
    tags=["project-votes"],
)
def participant_detail(
    session: SessionDep,
    usr_context: UserAccessDep,
    project_id: int,
    participant_id: int,
) -> ParticipantBundleResult:
    project = _require_project(session, usr_context, project_id)
    participant = ProjectVoteParticipant.get_by_id_system(
        session=session, participant_id=participant_id, clear_lock=False
    )
    if participant is None or participant.project_id != project.id or participant.customer_id != project.customer_id:
        return ParticipantBundleResult(failure_reason="Participant not found for this project")
    groups = ProjectVoteGroupResult.list_for_participant_system(
        session=session, participant_id=participant.id, clear_lock=True
    )
    if getattr(project, "private_participation", False):
        participant = redact_participant_list([participant])[0]
    return ParticipantBundleResult(participant_info=participant, groups=groups)


@router.post(
    "/project-votes/project-report",
    summary="Aggregate rankings, participant views, and stability metrics for a project",
    tags=["project-votes"],
)
def project_report(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: ProjectReportRequest,
) -> ProjectReportResult:
    project = _require_project(session, usr_context, form.project_id)
    alts, factors = _load_content(session, project)
    participants = ProjectVoteParticipant.list_for_project_system(
        session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=False
    )
    groups = ProjectVoteGroupResult.list_for_project_system(
        session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=True
    )
    settings = ranking_settings_with_project_influence(
        ranking_settings_from_customer(None), project,
    )
    if form.coherence_method is not None:
        settings["coherence_method"] = form.coherence_method

    report = build_report_with_ai_baseline(
        alternatives=[a.model_dump() for a in alts],
        factors=[f.model_dump() for f in factors],
        exclusive_mode=bool(project.project_exclusive_mode),
        all_groups=groups,
        participants=participants if form.include_participants else [],
        settings=settings,
    )
    if not form.include_participants:
        human_parts, _, _, _ = partition_vote_data(participants, [])
        report["unique_participants"] = len(human_parts)
        report["participants"] = []
    if getattr(project, "private_participation", False):
        report = redact_report_identities(report)
    else:
        report["private_participation"] = False
    return ProjectReportResult(project_id=project.id, report=report)


@router.post(
    "/project-votes/report-pivot-detail",
    summary="Drill-down rows for the multi-axis results pivot (option / factor / participant)",
    tags=["project-votes"],
)
def project_report_pivot_detail(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: ProjectPivotDetailRequest,
) -> ProjectPivotDetailResult:
    project = _require_project(session, usr_context, form.project_id)
    alts, factors = _load_content(session, project)
    participants = ProjectVoteParticipant.list_for_project_system(
        session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=False
    )
    groups = ProjectVoteGroupResult.list_for_project_system(
        session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=True
    )
    settings = ranking_settings_with_project_influence(
        ranking_settings_from_customer(None), project,
    )
    human_parts, human_groups, _, _ = partition_vote_data(participants, groups)
    detail = build_pivot_detail(
        alternatives=[a.model_dump() for a in alts],
        factors=[f.model_dump() for f in factors],
        exclusive_mode=bool(project.project_exclusive_mode),
        all_groups=human_groups,
        participants=human_parts,
        settings=settings,
        primary_axis=form.primary_axis,
        row_id=form.row_id,
        alternative_id=form.alternative_id,
        factor_id=form.factor_id,
        participant_id=form.participant_id,
    )
    if getattr(project, "private_participation", False):
        detail = redact_pivot_detail_identities(detail)
    else:
        detail["private_participation"] = False
    return ProjectPivotDetailResult(project_id=project.id, detail=detail)


@router.get(
    "/project-votes/project-bundle",
    summary="Participants + all groups + report for a project",
    tags=["project-votes"],
)
def project_vote_bundle(
    session: SessionDep,
    usr_context: UserAccessDep,
    project_id: int,
) -> ProjectVoteBundleResult:
    project = _require_project(session, usr_context, project_id)
    alts, factors = _load_content(session, project)
    participants = ProjectVoteParticipant.list_for_project_system(
        session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=False
    )
    groups = ProjectVoteGroupResult.list_for_project_system(
        session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=True
    )
    settings = ranking_settings_with_project_influence(
        ranking_settings_from_customer(None), project,
    )
    report = build_report_with_ai_baseline(
        alternatives=[a.model_dump() for a in alts],
        factors=[f.model_dump() for f in factors],
        exclusive_mode=bool(project.project_exclusive_mode),
        all_groups=groups,
        participants=participants,
        settings=settings,
    )
    human_parts, human_groups, _, _ = partition_vote_data(participants, groups)
    if getattr(project, "private_participation", False):
        report = redact_report_identities(report)
        human_parts = redact_participant_list(human_parts)
    else:
        report["private_participation"] = False
    return ProjectVoteBundleResult(
        project_id=project.id,
        participants=human_parts,
        groups=human_groups,
        observations=[],
        report=report,
    )


class AiBaselineRunForm(BaseModel):
    project_id: int
    models: list[str] | None = Field(
        default=None,
        description="Ignored; queue uses the project's saved AI agents when Include AI Agents is on",
    )


class AiBaselineJobView(BaseModel):
    id: int | None = None
    project_id: int | None = None
    model_key: str = ""
    status: str = ""
    pair_count: int = 0
    skip_count: int = 0
    group_count: int = 0
    error_summary: str | None = None
    participant_complete: bool = False
    display_name: str | None = None


class AiBaselineJobResult(PvfWsResultPackage):
    job: AiBaselineJobView | None = None
    jobs: list[AiBaselineJobView] = Field(default_factory=list)
    already_complete: bool = False


def _job_view(job, *, participant_complete: bool = False, display_name: str | None = None) -> AiBaselineJobView:
    if job is None:
        return AiBaselineJobView(participant_complete=participant_complete, display_name=display_name)
    return AiBaselineJobView(
        id=job.id,
        project_id=job.project_id,
        model_key=str(getattr(job, "model_key", "") or ""),
        status=str(job.status or ""),
        pair_count=int(job.pair_count or 0),
        skip_count=int(job.skip_count or 0),
        group_count=int(job.group_count or 0),
        error_summary=job.error_summary,
        participant_complete=participant_complete,
        display_name=display_name,
    )


def _require_ai_admin(usr_context) -> None:
    from ..utils.ai.config import ai_features_enabled, ai_unavailable_message
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    if not ai_features_enabled():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ai_unavailable_message())


def _ai_parts_by_key(parts: list) -> dict[str, Any]:
    from ..utils.ai.identity import build_ai_participant_key

    out: dict[str, Any] = {}
    for p in parts or []:
        if not is_ai_participant(p):
            continue
        key = str(getattr(p, "participant_key", "") or "")
        out[key] = p
        model = str(getattr(p, "ai_model", "") or "")
        if model:
            out[build_ai_participant_key(model)] = p
    return out


@router.post(
    "/project-votes/ai-baseline-run",
    summary="Enqueue unique AI agent participants for a project; customer_admin required",
    tags=["project-votes"],
)
def ai_baseline_run(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: AiBaselineRunForm,
) -> AiBaselineJobResult:
    from ..db.models.ai_agent_jobs import AiAgentJob
    from ..utils.ai.config import (
        no_providers_message,
        resolve_llm_credentials,
        unique_voter_models,
    )
    from ..utils.ai.identity import build_ai_participant_key

    _require_ai_admin(usr_context)
    project = _require_project(session, usr_context, form.project_id)
    if not bool(getattr(project, "include_ai_agents", False)):
        return AiBaselineJobResult(failure_reason="AI agents are not included for this project")
    customer = usr_context.sess_customer
    if resolve_llm_credentials(customer) is None:
        return AiBaselineJobResult(failure_reason=no_providers_message())
    alts, factors = _load_content(session, project)
    active_alts = [a for a in alts if not getattr(a, "disabled", False)]
    if len(active_alts) < 2:
        return AiBaselineJobResult(failure_reason="Save at least two options before running AI agents")
    requested = unique_voter_models(getattr(project, "ai_voter_models", None))
    if not requested:
        return AiBaselineJobResult(failure_reason="Select at least one AI agent in project settings")
    existing_parts = ProjectVoteParticipant.list_for_project_system(
        session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=False
    )
    parts_by_key = _ai_parts_by_key(existing_parts)
    views: list[AiBaselineJobView] = []
    latest = None
    all_complete = True
    for model_key in requested:
        creds = resolve_llm_credentials(customer, model_key=model_key)
        if creds is None:
            return AiBaselineJobResult(failure_reason=no_providers_message())
        part = parts_by_key.get(build_ai_participant_key(creds.model_key))
        if part is not None and part.is_complete:
            views.append(_job_view(None, participant_complete=True, display_name=creds.display_name))
            continue
        existing_job = AiAgentJob.get_active_for_project(
            session=session,
            customer_id=int(project.customer_id),
            project_id=int(project.id),
            model_key=creds.model_key,
            clear_lock=False,
        )
        if existing_job is not None:
            all_complete = False
            latest = existing_job
            views.append(_job_view(existing_job, participant_complete=False, display_name=creds.display_name))
            continue
        all_complete = False
        enqueued = AiAgentJob.enqueue_baseline(
            session=session,
            customer_id=int(project.customer_id),
            project_id=int(project.id),
            requested_by_user_id=int(usr_context.sess_user.id),
            model_key=creds.model_key,
            details={"provider": creds.provider, "source": creds.source, "display_name": creds.display_name},
            clear_lock=False,
        )
        latest = enqueued.job_info
        views.append(_job_view(enqueued.job_info, participant_complete=False, display_name=creds.display_name))
    return AiBaselineJobResult(
        job=_job_view(latest, participant_complete=all_complete) if latest else (views[0] if views else None),
        jobs=views,
        already_complete=all_complete,
    )


@router.get(
    "/project-votes/ai-baseline-status",
    summary="Return AI agent job status for a project; customer_admin required",
    tags=["project-votes"],
)
def ai_baseline_status(
    session: SessionDep,
    usr_context: UserAccessDep,
    project_id: int,
) -> AiBaselineJobResult:
    from ..db.models.ai_agent_jobs import AiAgentJob
    from ..utils.ai.identity import ai_display_name

    _require_ai_admin(usr_context)
    project = _require_project(session, usr_context, project_id)
    jobs = AiAgentJob.list_for_project(
        session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=False
    )
    parts = ProjectVoteParticipant.list_for_project_system(
        session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=True
    )
    parts_by_key = _ai_parts_by_key(parts)
    views = []
    complete_count = 0
    for job in jobs:
        part = parts_by_key.get(ProjectVoteParticipant.build_ai_key(job.model_key))
        done = bool(part and part.is_complete)
        if done:
            complete_count += 1
        views.append(
            _job_view(
                job,
                participant_complete=done,
                display_name=getattr(part, "display_name", None) or ai_display_name(job.model_key),
            )
        )
    ai_parts = [p for p in parts if is_ai_participant(p)]
    all_complete = bool(ai_parts) and all(p.is_complete for p in ai_parts) and not any(
        j.status in ("queued", "in_progress") for j in jobs
    )
    latest = jobs[0] if jobs else None
    return AiBaselineJobResult(
        job=_job_view(latest, participant_complete=all_complete) if latest else None,
        jobs=views,
        already_complete=all_complete,
    )
