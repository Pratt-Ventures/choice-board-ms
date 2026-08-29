from typing import Union, Any
from pydantic import BaseModel, Field
import time
import numpy as np
import random
from datetime import datetime, timezone, timedelta
import secrets

from fastapi import APIRouter,status, HTTPException, Request, Response
from sqlmodel import select
from sqlalchemy import func

from ..pvf.bindings.pvf_services import SessionDep, UserAccessDep, log_event, PvfWsResultPackage, PvfUserContext, PvfCustomer

from ..config.config_settings import settings

from ..db.models.customer_projects import CustomerProject, CustomerProjectResult_One_Id, CustomerProjectResult_One, CustomerProjectResult_Many, CustomerProjectDeleteResult
from ..db.models.customer_project_alternatives_criteria import (
    CustomerProjectAlternatives,
    CustomerProjectFactors,
)
from ..db.models.project_vote_events import ProjectVoteParticipant, ProjectVoteGroupResult, VoteSource
from ..utils.vote_ranking import (
    project_metrics,
    ranking_settings_from_customer,
    ranking_settings_with_project_influence,
    normalize_participant_influence_mode,
    clamp_influence_min_comparisons,
    clamp_factor_weight_floor_alpha,
)
from ..utils.sort_compare import (
    clamp_min_expected_passes,
    clamp_max_recommended_passes,
    clamp_questions_per_group_stored,
    default_questions_per_group,
    resolve_questions_per_group,
)
from ..utils.project_group_size import count_active_factors, count_active_options
from ..utils.vote_sort_session import (
    exclusive_from_ranking_mode,
    normalize_ranking_mode,
)
from ..utils.vote_sort_session import estimate_pass_comparisons, project_pass_settings

from ..utils.private_participation import (
    PRIVATE_PARTICIPATION_LOCK_MSG,
    private_participation_is_locked,
)
from ..utils.project_end_time import normalize_project_end_time
from ..utils.ai.config import unique_voter_models
from ..utils.project_overview_participation import (
    AiAgentCounts,
    AiParticipantStatusItem,
    HumanParticipantsSummary,
    build_ai_participation,
    build_human_participants,
)

class CustomerProjectForm(BaseModel):
    project_tag: str = Field(description="the short name that uniquely identifies the project within a customer")
    project_title: str | None = Field(description="the title of the project")
    project_description: str | None = Field(description="short description of the project as an information/context")
    project_exclusive_mode: bool = Field(default=False, description="Pick one (true): single winner. Rank all (false): full option ranking.")
    ranking_mode: str = Field(
        default="rank_all",
        description="Compare target: find_best, find_top_3, find_top_half, or rank_all",
    )
    private_participation: bool = Field(
        default=False,
        description=(
            "When true, individual participant names are hidden in reports and views. "
            "Locked once comparisons are collected by anyone other than the project creator; "
            "only a system admin can reverse it after lock."
        ),
    )
    participant_influence_mode: str = Field(
        default="comparisons",
        description=(
            "Group Results influence balance: comparisons, balanced, or participants_normalized"
        ),
    )
    participant_influence_min_comparisons: int = Field(
        default=10,
        description="Soft floor on calculable comparisons before participant influence is amplified (minimum 3)",
    )
    factor_weight_floor_alpha: float = Field(
        default=0.5,
        description=(
            "Factor importance weight floor scale alpha×(n−1). "
            "Lower spreads factor weights more; higher keeps them more equal (0.1–0.9, default 0.5)"
        ),
    )
    min_expected_passes: int = Field(
        default=2,
        description="Target minimum sort passes per participant (1–5)",
    )
    max_recommended_passes: int = Field(
        default=2,
        description="Recommended maximum sort passes per participant (≥ min expected, ≤ 10); hard limit is max + 1",
    )
    option_questions_per_group: int = Field(
        default=20,
        description=(
            "Pairwise comparisons per option group. Follows the Ford–Johnson default "
            "for the current option count unless option_questions_per_group_explicit is true"
        ),
    )
    factor_questions_per_group: int = Field(
        default=20,
        description=(
            "Pairwise comparisons per factor-importance group. Follows the Ford–Johnson "
            "default for the current factor count unless factor_questions_per_group_explicit is true"
        ),
    )
    option_questions_per_group_explicit: bool = Field(
        default=False,
        description="True when option comparisons per group were set by the user instead of the Ford–Johnson default",
    )
    factor_questions_per_group_explicit: bool = Field(
        default=False,
        description="True when factor comparisons per group were set by the user instead of the Ford–Johnson default",
    )
    project_criteria_template: int = Field(default=0, description="Last applied factor template id, if any")
    disabled: bool = Field(default=False, description="When true, input is closed; new comparisons are not accepted")
    end_time: datetime | None = Field(
        default=None,
        description="Optional date when comparison collection closes (stored as 11:59 PM). None means no deadline.",
    )
    include_ai_agents: bool = Field(
        default=False,
        description=(
            "When true, the project's saved AI agents can be queued from Results and other surfaces. "
            "When false, the saved selection is kept but ignored at queue time."
        ),
    )
    ai_voter_models: list[str] = Field(
        default_factory=list,
        description="Unique LLM model keys that vote as AI agents; __default__ uses the resolved default model. No model may participate twice.",
    )

class CustomerProjectDeleteForm(BaseModel):
    project_id: int = Field(default=0, description="The unique identifier of the project data entity")
    project_tag: str = Field(default="", description="the short name that uniquely identifies the project within a customer")


def _form_group_size_explicit(form: CustomerProjectForm, explicit_attr: str, number_attr: str) -> bool:
    fields = form.model_fields_set
    if explicit_attr in fields:
        return bool(getattr(form, explicit_attr))
    if number_attr in fields:
        return clamp_questions_per_group_stored(getattr(form, number_attr)) != default_questions_per_group()
    return False


def _apply_group_size_update(
    update_project: CustomerProjectForm,
    update_dict: dict,
    *,
    number_attr: str,
    explicit_attr: str,
    current_value: int,
    item_n: int,
) -> None:
    fields = update_project.model_fields_set
    if number_attr not in fields and explicit_attr not in fields:
        update_dict.pop(number_attr, None)
        update_dict.pop(explicit_attr, None)
        return
    explicit = (
        bool(getattr(update_project, explicit_attr))
        if explicit_attr in fields
        else True
    )
    if number_attr in fields:
        stored = clamp_questions_per_group_stored(getattr(update_project, number_attr))
    else:
        stored = current_value
    update_dict[explicit_attr] = explicit
    update_dict[number_attr] = resolve_questions_per_group(stored, item_n, explicit)


class ProjectListSummaryItem(BaseModel):
    project: CustomerProject
    alternative_count: int = 0
    factor_count: int = 0
    observation_count: int = 0
    participant_count: int = 0
    metrics: dict = Field(default_factory=dict)


class ProjectListSummaryResult(PvfWsResultPackage):
    projects: list[ProjectListSummaryItem] = Field(default_factory=list)


class ProjectPageContentItem(BaseModel):
    id: int
    title: str | None = None
    description: str | None = None
    disabled: bool = False


class ProjectPageSummaryResult(PvfWsResultPackage):
    project: CustomerProject | None = None
    alternatives: list[ProjectPageContentItem] = Field(default_factory=list)
    factors: list[ProjectPageContentItem] = Field(default_factory=list)
    my_observation_count: int = 0
    participant_count: int = 0
    target_comparisons_est: int = Field(
        default=0,
        description="Estimated comparisons for one participant completing the minimum target groups across all factors plus the factor group",
    )
    max_comparisons_est: int = Field(
        default=0,
        description="Estimated comparisons for one participant at the recommended maximum number of passes",
    )
    active_participant_count: int = Field(
        default=0,
        description="Participants who have recorded at least one comparison",
    )
    ai_agent_counts: AiAgentCounts = Field(
        default_factory=AiAgentCounts,
        description="AI agents requested / queued or in progress / completed",
    )
    human_participants: HumanParticipantsSummary = Field(
        default_factory=HumanParticipantsSummary,
        description="Named active and pending people, plus open anonymous shares",
    )
    ai_participants: list[AiParticipantStatusItem] = Field(
        default_factory=list,
        description="Per-model AI agent status when any AI work was requested",
    )
    my_metrics: dict = Field(default_factory=dict)


router = APIRouter()


def _count_map(session, model, customer_id: int, *, active_only: bool = False, exclude_ai: bool = False) -> dict[int, int]:
    """GROUP BY project_id counts for a tenant-scoped soft-delete table."""
    clauses = [
        model.customer_id == customer_id,
        model.deleted_date == None,  # noqa: E711
    ]
    if active_only and hasattr(model, "disabled"):
        clauses.append(model.disabled == False)  # noqa: E712
    if exclude_ai and hasattr(model, "source"):
        clauses.append(model.source != VoteSource.ai)
    rows = session.exec(
        select(model.project_id, func.count())
        .where(*clauses)
        .group_by(model.project_id)
    ).all()
    return {int(pid): int(cnt) for pid, cnt in rows if pid is not None}


def _ranking_settings_for_customer(session, customer_id: int) -> dict:
    customer = PvfCustomer.get_customer_by_id_system(session=session, id=customer_id, clear_lock=False)
    return ranking_settings_from_customer(customer.client_settings if customer else None)


def _metrics_for_project(
    *,
    groups: list,
    alternatives: list,
    factors: list,
    exclusive_mode: bool,
    settings: dict,
    participants: list | None = None,
) -> dict:
    alt_dicts = [a if isinstance(a, dict) else a.model_dump() for a in alternatives]
    factor_dicts = [f if isinstance(f, dict) else f.model_dump() for f in factors]
    m = project_metrics(
        groups,
        alternatives=alt_dicts,
        factors=factor_dicts,
        exclusive_mode=bool(exclusive_mode),
        participants=participants,
        settings=settings or {},
    )
    return {
        "stability": m.get("stability", 0),
        "confidence": m.get("confidence", 0),
        "agreement": m.get("agreement", 0),
        "completion": m.get("completion", 0),
        "coverage": m.get("coverage", 0),
        "accuracy": 0,
    }

@router.post("/custprojects/customer-project-create",
             summary="Register a new project within the customer; must be customer_admin; must be in same customer",
             tags=['manage-projects'])
def customer_project_create(session: SessionDep, usr_context: UserAccessDep, new_customer_project: CustomerProjectForm) -> CustomerProjectResult_One:
    if usr_context.sess_user.customer_admin is False:
        log_event("Unauthorized attempt to create an project", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Unauthorized attempt to create project {str(new_customer_project.project_tag)[:50]}"))

    existing_project = CustomerProject.get_customer_project_by_tag_system(session=session, customer_id=usr_context.sess_user.customer_id, tag=new_customer_project.project_tag, clear_lock=True)
    if existing_project is not None:
        log_event(f"Project with tag {new_customer_project.project_tag} already exists", usr_context=usr_context, severity=2)
        return CustomerProjectResult_One(failure_reason=f"Project with tag {new_customer_project.project_tag} already exists")

    normalized_end, end_err = normalize_project_end_time(new_customer_project.end_time)
    if end_err:
        return CustomerProjectResult_One(failure_reason=end_err)

    log_id = log_event("create_customer_project", usr_context=usr_context, new_customer_project_tag=new_customer_project.project_tag)

    new_customer_project_row = CustomerProject(
        customer_id=usr_context.sess_user.customer_id,
        project_tag=new_customer_project.project_tag,
        project_title=new_customer_project.project_title,
        project_description=new_customer_project.project_description,
        ranking_mode=normalize_ranking_mode(
            new_customer_project.ranking_mode,
            exclusive_mode=new_customer_project.project_exclusive_mode,
        ),
        project_exclusive_mode=exclusive_from_ranking_mode(
            normalize_ranking_mode(
                new_customer_project.ranking_mode,
                exclusive_mode=new_customer_project.project_exclusive_mode,
            )
        ),
        private_participation=new_customer_project.private_participation,
        participant_influence_mode=normalize_participant_influence_mode(
            new_customer_project.participant_influence_mode
        ),
        participant_influence_min_comparisons=clamp_influence_min_comparisons(
            new_customer_project.participant_influence_min_comparisons
        ),
        factor_weight_floor_alpha=clamp_factor_weight_floor_alpha(
            new_customer_project.factor_weight_floor_alpha
        ),
        min_expected_passes=clamp_min_expected_passes(new_customer_project.min_expected_passes),
        max_recommended_passes=clamp_max_recommended_passes(
            new_customer_project.max_recommended_passes,
            new_customer_project.min_expected_passes,
        ),
        option_questions_per_group=(
            clamp_questions_per_group_stored(new_customer_project.option_questions_per_group)
            if _form_group_size_explicit(
                new_customer_project,
                "option_questions_per_group_explicit",
                "option_questions_per_group",
            )
            else default_questions_per_group()
        ),
        factor_questions_per_group=(
            clamp_questions_per_group_stored(new_customer_project.factor_questions_per_group)
            if _form_group_size_explicit(
                new_customer_project,
                "factor_questions_per_group_explicit",
                "factor_questions_per_group",
            )
            else default_questions_per_group()
        ),
        option_questions_per_group_explicit=_form_group_size_explicit(
            new_customer_project,
            "option_questions_per_group_explicit",
            "option_questions_per_group",
        ),
        factor_questions_per_group_explicit=_form_group_size_explicit(
            new_customer_project,
            "factor_questions_per_group_explicit",
            "factor_questions_per_group",
        ),
        project_criteria_template=new_customer_project.project_criteria_template,
        project_created_by=usr_context.sess_user.id,
        disabled=new_customer_project.disabled,
        end_time=normalized_end,
        include_ai_agents=bool(new_customer_project.include_ai_agents),
        ai_voter_models=unique_voter_models(new_customer_project.ai_voter_models),
    )
    return_result = new_customer_project_row.create_customer_project(session=session, usr_context=usr_context)
    return return_result


def _with_private_lock_flag(session: SessionDep, result: CustomerProjectResult_One) -> CustomerProjectResult_One:
    if result.failure_reason or result.customer_project_info is None:
        return result
    result.private_participation_locked = private_participation_is_locked(
        session, project=result.customer_project_info, clear_lock=False
    )
    return result


@router.get('/custprojects/customer-project-get-by-id',
            summary='Return customer project information by internal project id (for admin purposes)',
            tags=['manage-projects'])
def get_customer_project_info_by_id(session: SessionDep, usr_context: UserAccessDep, retrieve_by_id:int) -> CustomerProjectResult_One:
    result = CustomerProject.get_customer_project_by_id(
        session=session, usr_context=usr_context, id=retrieve_by_id, clear_lock=False
    )
    return _with_private_lock_flag(session, result)

@router.get('/custprojects/customer-project-get-by-tag',
            summary='Return customer project information by project tag (for admin purposes)',
            tags=['manage-projects'])
def get_customer_project_info_by_tag(session: SessionDep, usr_context: UserAccessDep, retrieve_by_tag:str) -> CustomerProjectResult_One:
    result = CustomerProject.get_customer_project_by_tag(
        session=session, usr_context=usr_context, tag=retrieve_by_tag, clear_lock=False
    )
    return _with_private_lock_flag(session, result)

@router.get('/custprojects/customer-projects-get-all',
            summary='Return customer project information for all projects in the current account (for my-team and admin purposes)',
            tags=['manage-projects'])
def get_all_account_projects(session: SessionDep, usr_context: UserAccessDep) -> CustomerProjectResult_Many:
    return CustomerProject.get_all_customer_projects(session=session, usr_context=usr_context)


@router.get(
    "/custprojects/customer-projects-list-summary",
    summary="Lean projects list: counts + light metrics (no full observations/report)",
    tags=["manage-projects"],
)
def customer_projects_list_summary(
    session: SessionDep,
    usr_context: UserAccessDep,
) -> ProjectListSummaryResult:
    customer_id = usr_context.sess_user.customer_id
    projects = list(session.exec(
        select(CustomerProject).where(
            CustomerProject.customer_id == customer_id,
            CustomerProject.deleted_date == None,  # noqa: E711
        )
    ).all())
    if not projects:
        return ProjectListSummaryResult(projects=[])

    alt_counts = _count_map(session, CustomerProjectAlternatives, customer_id, active_only=True)
    factor_counts = _count_map(session, CustomerProjectFactors, customer_id, active_only=True)
    group_counts = _count_map(session, ProjectVoteGroupResult, customer_id)
    part_counts = _count_map(session, ProjectVoteParticipant, customer_id, exclude_ai=True)
    ranking_settings = _ranking_settings_for_customer(session, customer_id)

    project_ids = [p.id for p in projects]
    all_alts = list(session.exec(
        select(CustomerProjectAlternatives).where(
            CustomerProjectAlternatives.customer_id == customer_id,
            CustomerProjectAlternatives.project_id.in_(project_ids),
            CustomerProjectAlternatives.deleted_date == None,  # noqa: E711
        )
    ).all())
    all_factors = list(session.exec(
        select(CustomerProjectFactors).where(
            CustomerProjectFactors.customer_id == customer_id,
            CustomerProjectFactors.project_id.in_(project_ids),
            CustomerProjectFactors.deleted_date == None,  # noqa: E711
        )
    ).all())
    projects_with_groups = [pid for pid in project_ids if group_counts.get(pid, 0) > 0]
    all_groups: list[ProjectVoteGroupResult] = []
    if projects_with_groups:
        all_groups = list(session.exec(
            select(ProjectVoteGroupResult).where(
                ProjectVoteGroupResult.customer_id == customer_id,
                ProjectVoteGroupResult.project_id.in_(projects_with_groups),
                ProjectVoteGroupResult.deleted_date == None,  # noqa: E711
            )
        ).all())

    alts_by_p: dict[int, list] = {}
    for a in all_alts:
        alts_by_p.setdefault(a.project_id, []).append(a)
    factors_by_p: dict[int, list] = {}
    for f in all_factors:
        factors_by_p.setdefault(f.project_id, []).append(f)
    groups_by_p: dict[int, list] = {}
    for g in all_groups:
        groups_by_p.setdefault(g.project_id, []).append(g)

    items: list[ProjectListSummaryItem] = []
    for p in projects:
        pid = p.id
        metrics = _metrics_for_project(
            groups=groups_by_p.get(pid, []),
            alternatives=alts_by_p.get(pid, []),
            factors=factors_by_p.get(pid, []),
            exclusive_mode=bool(p.project_exclusive_mode),
            settings=ranking_settings_with_project_influence(ranking_settings, p),
        ) if group_counts.get(pid, 0) or alt_counts.get(pid, 0) else {
            "stability": 0, "confidence": 0, "agreement": 0, "completion": 0, "coverage": 0, "accuracy": 0,
        }
        # observation_count field keeps API shape; value is comparison groups completed
        items.append(ProjectListSummaryItem(
            project=p,
            alternative_count=alt_counts.get(pid, 0),
            factor_count=factor_counts.get(pid, 0),
            observation_count=group_counts.get(pid, 0),
            participant_count=part_counts.get(pid, 0),
            metrics=metrics,
        ))
    return ProjectListSummaryResult(projects=items)


@router.get(
    "/custprojects/customer-project-page-summary",
    summary="Lean project hub payload: project + options/factors + counts (no report/next probes)",
    tags=["manage-projects"],
)
def customer_project_page_summary(
    session: SessionDep,
    usr_context: UserAccessDep,
    project_id: int,
) -> ProjectPageSummaryResult:
    result = CustomerProject.get_customer_project_by_id(
        session=session, id=project_id, usr_context=usr_context, clear_lock=False
    )
    if result.failure_reason or result.customer_project_info is None:
        return ProjectPageSummaryResult(failure_reason=result.failure_reason or "Project not found", log_id=result.log_id)
    project = result.customer_project_info
    customer_id = project.customer_id

    alts = list(session.exec(
        select(CustomerProjectAlternatives).where(
            CustomerProjectAlternatives.project_id == project.id,
            CustomerProjectAlternatives.customer_id == customer_id,
            CustomerProjectAlternatives.deleted_date == None,  # noqa: E711
        )
    ).all())
    factors = list(session.exec(
        select(CustomerProjectFactors).where(
            CustomerProjectFactors.project_id == project.id,
            CustomerProjectFactors.customer_id == customer_id,
            CustomerProjectFactors.deleted_date == None,  # noqa: E711
        )
    ).all())

    all_participants = ProjectVoteParticipant.list_for_project_system(
        session=session, customer_id=customer_id, project_id=project.id, clear_lock=False
    )
    humans = [p for p in all_participants if p.source != VoteSource.ai]
    participant_count = len(humans)
    active_participant_count = sum(1 for p in humans if int(p.comparison_count or 0) > 0)

    # Per-participant estimate: min/max passes × one pass of groups across all
    # active factors plus the factor group (factor-vs-factor comparisons).
    active_option_n = len([a for a in alts if not a.disabled])
    active_factor_n = len([f for f in factors if not f.disabled])
    per_pass_est = estimate_pass_comparisons(
        active_option_n,
        active_factor_n,
        resolve_questions_per_group(
            getattr(project, "option_questions_per_group", None),
            active_option_n,
            bool(getattr(project, "option_questions_per_group_explicit", False)),
        ),
        resolve_questions_per_group(
            getattr(project, "factor_questions_per_group", None),
            active_factor_n,
            bool(getattr(project, "factor_questions_per_group_explicit", False)),
        ),
    )
    pass_settings = project_pass_settings(project)
    target_comparisons_est = per_pass_est * pass_settings["min_expected_passes"]
    max_comparisons_est = per_pass_est * pass_settings["max_recommended_passes"]

    my_obs_count = 0
    my_groups: list[ProjectVoteGroupResult] = []
    user_id = usr_context.sess_user.id
    part = session.exec(
        select(ProjectVoteParticipant).where(
            ProjectVoteParticipant.customer_id == customer_id,
            ProjectVoteParticipant.project_id == project.id,
            ProjectVoteParticipant.user_id == user_id,
            ProjectVoteParticipant.deleted_date == None,  # noqa: E711
        ).limit(1)
    ).one_or_none()
    if part is not None:
        my_groups = list(session.exec(
            select(ProjectVoteGroupResult).where(
                ProjectVoteGroupResult.participant_id == part.id,
                ProjectVoteGroupResult.deleted_date == None,  # noqa: E711
            )
        ).all())
        my_obs_count = int(part.comparison_count or 0)

    ranking_settings = ranking_settings_with_project_influence(
        _ranking_settings_for_customer(session, customer_id), project
    )
    my_metrics = _metrics_for_project(
        groups=my_groups,
        alternatives=alts,
        factors=factors,
        exclusive_mode=bool(project.project_exclusive_mode),
        settings=ranking_settings,
        participants=[part] if part is not None else [],
    )

    human_participants = build_human_participants(
        session,
        customer_id=customer_id,
        project_id=int(project.id),
        humans=humans,
    )
    ai_agent_counts, ai_participants = build_ai_participation(
        session,
        customer_id=customer_id,
        project_id=int(project.id),
        participants=all_participants,
        target_comparisons_est=target_comparisons_est,
    )

    return ProjectPageSummaryResult(
        project=project,
        alternatives=[
            ProjectPageContentItem(
                id=a.id,
                title=a.alternative_title,
                description=a.alternative_description,
                disabled=bool(a.disabled),
            )
            for a in alts
        ],
        factors=[
            ProjectPageContentItem(
                id=f.id,
                title=f.factor_title,
                description=f.factor_description,
                disabled=bool(f.disabled),
            )
            for f in factors
        ],
        my_observation_count=my_obs_count,
        participant_count=int(participant_count or 0),
        target_comparisons_est=target_comparisons_est,
        max_comparisons_est=max_comparisons_est,
        active_participant_count=int(active_participant_count or 0),
        ai_agent_counts=ai_agent_counts,
        human_participants=human_participants,
        ai_participants=ai_participants if ai_agent_counts.requested else [],
        my_metrics=my_metrics,
    )


@router.post("/custprojects/customer-project-update",
             summary="Modify a project; must be customer_admin in same customer",
             tags=['manage-projects'])
def update_customer_project(session: SessionDep, usr_context: UserAccessDep, update_project: CustomerProjectForm) -> CustomerProjectResult_One_Id:
    check_result = CustomerProject.get_customer_project_by_tag(
        session=session, tag=update_project.project_tag, usr_context=usr_context, clear_lock=False
    )

    if check_result.failure_reason or check_result.customer_project_info is None:
        return CustomerProjectResult_One_Id(failure_reason=check_result.failure_reason, log_id=check_result.log_id, customer_project_id=-1)

    customer_project_info = check_result.customer_project_info

    was_private = bool(customer_project_info.private_participation)
    wants_private = bool(update_project.private_participation)
    if was_private and not wants_private:
        is_sysadmin = int(getattr(usr_context.sess_user, "system_user_mode", 0) or 0) >= 2
        if not is_sysadmin and private_participation_is_locked(
            session, project=customer_project_info, clear_lock=False
        ):
            log_id = log_event(
                "private_participation_locked",
                usr_context=usr_context,
                severity=2,
                details_str=f"project_tag={customer_project_info.project_tag}",
            )
            return CustomerProjectResult_One_Id(
                failure_reason=PRIVATE_PARTICIPATION_LOCK_MSG,
                log_id=log_id,
                customer_project_id=customer_project_info.id,
            )

    failure_reason, log_id, allowed = CustomerProject.check_user_access_to_customer_project(
        "update_customer_project",
        key=update_project.project_tag,
        usr_context=usr_context,
        check_customer_project=customer_project_info,
        update_mode=True,
    )
    if allowed is None or failure_reason:
        return CustomerProjectResult_One_Id(
            failure_reason=failure_reason or "Not allowed",
            log_id=log_id,
            customer_project_id=-1,
        )

    update_dict = update_project.model_dump(mode="dict")
    if "participant_influence_mode" in update_dict:
        update_dict["participant_influence_mode"] = normalize_participant_influence_mode(
            update_dict.get("participant_influence_mode")
        )
    if "participant_influence_min_comparisons" in update_dict:
        update_dict["participant_influence_min_comparisons"] = clamp_influence_min_comparisons(
            update_dict.get("participant_influence_min_comparisons")
        )
    if "factor_weight_floor_alpha" in update_dict:
        update_dict["factor_weight_floor_alpha"] = clamp_factor_weight_floor_alpha(
            update_dict.get("factor_weight_floor_alpha")
        )
    if "min_expected_passes" in update_dict:
        update_dict["min_expected_passes"] = clamp_min_expected_passes(
            update_dict.get("min_expected_passes")
        )
    if "max_recommended_passes" in update_dict or "min_expected_passes" in update_dict:
        mn = update_dict.get("min_expected_passes", customer_project_info.min_expected_passes)
        mx = update_dict.get("max_recommended_passes", customer_project_info.max_recommended_passes)
        update_dict["min_expected_passes"] = clamp_min_expected_passes(mn)
        update_dict["max_recommended_passes"] = clamp_max_recommended_passes(mx, mn)
    if "ranking_mode" in update_dict or "project_exclusive_mode" in update_dict:
        mode = normalize_ranking_mode(
            update_dict.get("ranking_mode", getattr(customer_project_info, "ranking_mode", None)),
            exclusive_mode=update_dict.get(
                "project_exclusive_mode",
                getattr(customer_project_info, "project_exclusive_mode", False),
            ),
        )
        update_dict["ranking_mode"] = mode
        update_dict["project_exclusive_mode"] = exclusive_from_ranking_mode(mode)
    _apply_group_size_update(
        update_project,
        update_dict,
        number_attr="option_questions_per_group",
        explicit_attr="option_questions_per_group_explicit",
        current_value=customer_project_info.option_questions_per_group,
        item_n=count_active_options(
            session,
            project_id=customer_project_info.id,
            customer_id=customer_project_info.customer_id,
        ),
    )
    _apply_group_size_update(
        update_project,
        update_dict,
        number_attr="factor_questions_per_group",
        explicit_attr="factor_questions_per_group_explicit",
        current_value=customer_project_info.factor_questions_per_group,
        item_n=count_active_factors(
            session,
            project_id=customer_project_info.id,
            customer_id=customer_project_info.customer_id,
        ),
    )
    if "include_ai_agents" in update_dict:
        update_dict["include_ai_agents"] = bool(update_dict.get("include_ai_agents"))
    if "ai_voter_models" in update_dict:
        update_dict["ai_voter_models"] = unique_voter_models(update_dict.get("ai_voter_models"))
    if "end_time" in update_project.model_fields_set:
        normalized_end, end_err = normalize_project_end_time(update_project.end_time)
        if end_err:
            return CustomerProjectResult_One_Id(
                failure_reason=end_err,
                customer_project_id=customer_project_info.id,
            )
        customer_project_info.end_time = normalized_end
    for key, value in update_dict.items():
        if key == "end_time":
            continue
        if value is not None:
            setattr(customer_project_info, key, value)

    session.add(customer_project_info)
    session.commit()
    session.refresh(customer_project_info)
    return CustomerProjectResult_One_Id(customer_project_id=customer_project_info.id)

@router.delete("/custprojects/customer-project-delete",
             summary="Delete a project; must be customer_admin and same customer",
             tags=['manage-projects'])
def delete_customer_project(session: SessionDep, usr_context: UserAccessDep, delete_project_form: CustomerProjectDeleteForm) -> CustomerProjectDeleteResult:
    if delete_project_form.project_id not in (0, -1, None):
        check_result = CustomerProject.get_customer_project_by_id(session=session, id=delete_project_form.project_id, usr_context=usr_context)
        used_project_id = delete_project_form.project_id
        used_project_tag = None
    else:
        check_result = CustomerProject.get_customer_project_by_tag(session=session, tag=delete_project_form.project_tag, usr_context=usr_context)
        used_project_id = None
        used_project_tag = delete_project_form.project_tag

    if check_result.failure_reason or check_result.customer_project_info is None:
        return CustomerProjectDeleteResult(failure_reason=check_result.failure_reason, log_id=check_result.log_id, customer_project_id=used_project_id, customer_project_tag=used_project_tag)

    used_project_id = check_result.customer_project_info.id
    used_project_tag = check_result.customer_project_info.project_tag

    delete_project_result = check_result.customer_project_info.delete_customer_project(session=session, usr_context=usr_context)
    return CustomerProjectDeleteResult(failure_reason=delete_project_result.failure_reason, log_id=delete_project_result.log_id, customer_project_id=used_project_id, customer_project_tag=used_project_tag)


class ComparePromptBulkForm(BaseModel):
    project_id: int


class ComparePromptBulkResult(PvfWsResultPackage):
    queued: int = 0
    skipped_existing: int = 0
    cleared: int = 0
    failed: int = 0


DISABLED_PROVIDER_MSG = "There is no provider set up for this customer, check settings to enable"


@router.post("/custprojects/customer-project-compare-prompts-generate",
             summary="Generate concise compare prompts for all options and factors with empty values; customer_admin required",
             tags=['manage-projects'])
def customer_project_compare_prompts_generate(session: SessionDep, usr_context: UserAccessDep, form: ComparePromptBulkForm) -> ComparePromptBulkResult:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to generate compare prompts", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    from ..utils.ai.config import customer_llm_configured, resolve_llm_credentials
    customer = usr_context.sess_customer
    if not customer_llm_configured(customer):
        log_event(
            "compare prompt bulk generate failed - no provider",
            usr_context=usr_context,
            severity=2,
            project_id=form.project_id,
            failure_reason=DISABLED_PROVIDER_MSG,
        )
        return ComparePromptBulkResult(failure_reason=DISABLED_PROVIDER_MSG)
    proj_res = CustomerProject.get_customer_project_by_id(session=session, id=form.project_id, usr_context=usr_context, clear_lock=False)
    if proj_res.failure_reason or proj_res.customer_project_info is None:
        log_event(
            f"compare prompt bulk generate failed - project {form.project_id} not found",
            usr_context=usr_context,
            severity=2,
            project_id=form.project_id,
            failure_reason=proj_res.failure_reason or "Project not found",
        )
        return ComparePromptBulkResult(failure_reason=proj_res.failure_reason or "Project not found")
    project = proj_res.customer_project_info
    creds = resolve_llm_credentials(customer)
    # Select blanks
    alts = CustomerProjectAlternatives.get_all_by_project_id_system(session=session, project_id=project.id, customer_id=project.customer_id, clear_lock=False) or []
    factors = CustomerProjectFactors.get_all_by_project_id_system(session=session, project_id=project.id, customer_id=project.customer_id, clear_lock=False) or []
    blank_alts = [a for a in alts if not (a.compare_prompt or "").strip()]
    blank_facs = [f for f in factors if not (f.compare_prompt or "").strip()]
    skipped = (len(alts) - len(blank_alts)) + (len(factors) - len(blank_facs))
    if not blank_alts and not blank_facs:
        log_event(
            "compare prompt bulk generate - no blanks",
            usr_context=usr_context,
            severity=1,
            project_id=project.id,
            skipped_existing=skipped,
        )
        return ComparePromptBulkResult(queued=0, skipped_existing=skipped, failed=0)
    log_event(
        "compare prompt bulk generate start",
        usr_context=usr_context,
        severity=1,
        project_id=project.id,
        blank_alts=len(blank_alts),
        blank_facs=len(blank_facs),
        skipped_existing=skipped,
        provider=getattr(creds, "provider", "") if creds else "",
        model=getattr(creds, "model", "") if creds else "",
    )
    queued = 0
    enqueue_failed = 0
    # Queue via watcher LLM (and legacy ComparePromptJob for status compatibility)
    from ..db.models.compare_prompt_jobs import ComparePromptJob
    from ..utils.ai.prompts import option_rewrite_messages, factor_rewrite_messages
    from ..pvf.bindings.pvf_watcher_requests import queue_llm_request
    for alt in blank_alts:
        try:
            # Legacy job for status UI
            ComparePromptJob.enqueue(session=session, customer_id=project.customer_id, project_id=project.id, item_type="option", item_id=alt.id, requested_by_user_id=usr_context.sess_user.id, clear_lock=False)
            # Watcher LLM queue with byte tracking
            messages = option_rewrite_messages(title=alt.alternative_title or "", description=alt.alternative_description)
            queue_llm_request(session=session, usr_context=usr_context, messages=messages, temperature=0.3, max_tokens=1200, semantic_tag="reword_option", metadata={"project_id": project.id, "item_type": "option", "item_id": alt.id})
            queued += 1
        except Exception as ex:
            enqueue_failed += 1
            log_event(f"compare prompt enqueue option {alt.id} failed: {ex}", usr_context=usr_context, severity=2, ex_info=ex if isinstance(ex, Exception) else None, project_id=project.id, alternative_id=alt.id, error=str(ex)[:500])
    for fac in blank_facs:
        try:
            ComparePromptJob.enqueue(session=session, customer_id=project.customer_id, project_id=project.id, item_type="factor", item_id=fac.id, requested_by_user_id=usr_context.sess_user.id, clear_lock=False)
            messages = factor_rewrite_messages(title=fac.factor_title or "", description=fac.factor_description, polarity_positive=fac.factor_polarity_positive, polarity_note=fac.factor_polarity_note)
            queue_llm_request(session=session, usr_context=usr_context, messages=messages, temperature=0.3, max_tokens=1200, semantic_tag="reword_factor", metadata={"project_id": project.id, "item_type": "factor", "item_id": fac.id})
            queued += 1
        except Exception as ex:
            enqueue_failed += 1
            log_event(f"compare prompt enqueue factor {fac.id} failed: {ex}", usr_context=usr_context, severity=2, ex_info=ex if isinstance(ex, Exception) else None, project_id=project.id, factor_id=fac.id, error=str(ex)[:500])
    # Watcher will deliver; no inline generation (fully async)
    failed = enqueue_failed
    if failed > 0:
        log_event(f"compare prompt bulk generate done with failures: queued={queued} failed={failed} skipped={skipped}", usr_context=usr_context, severity=2, project_id=project.id, queued=queued, failed=failed, skipped_existing=skipped, provider=getattr(creds, "provider", "") if creds else "")
    else:
        msg = "Auto generate queued for watcher." if queued else "No prompts needed"
        log_event(f"compare prompt bulk generate done: {msg} queued={queued} skipped={skipped}", usr_context=usr_context, severity=1, project_id=project.id, queued=queued, failed=failed, skipped_existing=skipped)
    return ComparePromptBulkResult(queued=queued, skipped_existing=skipped, failed=failed)


@router.post("/custprojects/customer-project-compare-prompts-clear",
             summary="Clear all generated compare prompts for a project; customer_admin required",
             tags=['manage-projects'])
def customer_project_compare_prompts_clear(session: SessionDep, usr_context: UserAccessDep, form: ComparePromptBulkForm) -> ComparePromptBulkResult:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to clear compare prompts", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    proj_res = CustomerProject.get_customer_project_by_id(session=session, id=form.project_id, usr_context=usr_context, clear_lock=False)
    if proj_res.failure_reason or proj_res.customer_project_info is None:
        return ComparePromptBulkResult(failure_reason=proj_res.failure_reason or "Project not found")
    project = proj_res.customer_project_info
    alts = CustomerProjectAlternatives.get_all_by_project_id_system(session=session, project_id=project.id, customer_id=project.customer_id, clear_lock=False) or []
    factors = CustomerProjectFactors.get_all_by_project_id_system(session=session, project_id=project.id, customer_id=project.customer_id, clear_lock=False) or []
    cleared = 0
    for alt in alts:
        if (alt.compare_prompt or "").strip():
            alt.compare_prompt = None
            session.add(alt)
            cleared += 1
    for fac in factors:
        if (fac.compare_prompt or "").strip():
            fac.compare_prompt = None
            session.add(fac)
            cleared += 1
    if cleared:
        session.commit()
    # also clear pending jobs
    from ..db.models.compare_prompt_jobs import ComparePromptJob
    from sqlmodel import select as _sel
    jobs = list(session.exec(_sel(ComparePromptJob).where(ComparePromptJob.project_id == project.id, ComparePromptJob.customer_id == project.customer_id, ComparePromptJob.status.in_(("queued", "in_progress")))).all())
    for j in jobs:
        j.status = "failed"
        j.error_summary = "cleared by user"
        from datetime import datetime as _dt
        j.completed_date = _dt.now()
        session.add(j)
    if jobs:
        session.commit()
    return ComparePromptBulkResult(cleared=cleared)


@router.get("/custprojects/customer-project-compare-prompts-status",
            summary="Return compare prompt generation status for a project",
            tags=['manage-projects'])
def customer_project_compare_prompts_status(session: SessionDep, usr_context: UserAccessDep, project_id: int) -> ComparePromptBulkResult:
    proj_res = CustomerProject.get_customer_project_by_id(session=session, id=project_id, usr_context=usr_context, clear_lock=False)
    if proj_res.failure_reason or proj_res.customer_project_info is None:
        return ComparePromptBulkResult(failure_reason=proj_res.failure_reason or "Project not found")
    project = proj_res.customer_project_info
    from ..db.models.compare_prompt_jobs import ComparePromptJob
    pending = ComparePromptJob.queued_count(session=session, project_id=project.id, customer_id=project.customer_id, clear_lock=False)
    alts = CustomerProjectAlternatives.get_all_by_project_id_system(session=session, project_id=project.id, customer_id=project.customer_id, clear_lock=False) or []
    factors = CustomerProjectFactors.get_all_by_project_id_system(session=session, project_id=project.id, customer_id=project.customer_id, clear_lock=False) or []
    total = len(alts) + len(factors)
    with_prompt = sum(1 for a in alts if (a.compare_prompt or "").strip()) + sum(1 for f in factors if (f.compare_prompt or "").strip())
    return ComparePromptBulkResult(queued=pending, skipped_existing=with_prompt, cleared=total - with_prompt)
