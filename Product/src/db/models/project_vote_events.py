from __future__ import annotations
from typing import Union, Any
from datetime import datetime
from enum import Enum

from sqlmodel import SQLModel, Field, Session, select
from sqlalchemy import func, DateTime, Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from ...pvf.bindings.pvf_services import PvfWsResultPackage, PvfUserContext, get_hex_hash_from_args

from .customer_projects import CustomerProject
from ...utils.project_end_time import project_input_block_reason
from ...config.config_settings import settings


class VoteSource(str, Enum):
    session = "session"
    share = "share"
    ai = "ai"


class GroupType(str, Enum):
    alternative = "alternative"
    criteria = "criteria"


class SortAlgorithm(str, Enum):
    ford_johnson = "ford_johnson"
    merge_sort = "merge_sort"


class PairResponse(str, Enum):
    winner = "winner"
    tie = "tie"
    unsure = "unsure"
    skipped = "skipped"


class GroupStatus(str, Enum):
    in_progress = "in_progress"
    complete = "complete"


class RankingTarget(str, Enum):
    winner = "winner"
    top_n = "top_n"
    full = "full"


class ProjectVoteParticipantResult_One(PvfWsResultPackage):
    participant_info: Union[ProjectVoteParticipant, None] = None


class ProjectVoteParticipantResult_Many(PvfWsResultPackage):
    participant_info_list: Union[list[ProjectVoteParticipant], None] = None


class ProjectVoteGroupResultResult_One(PvfWsResultPackage):
    group_info: Union[ProjectVoteGroupResult, None] = None


class ProjectVoteGroupResultResult_Many(PvfWsResultPackage):
    group_info_list: Union[list[ProjectVoteGroupResult], None] = None


class ProjectVoteParticipant(SQLModel, table=True):
    """A unique voter (logged-in user or external share recipient) on a project."""
    __table_args__ = (
        UniqueConstraint("customer_id", "project_id", "participant_key", name="uq_vote_participant_key"),
    )

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True)
    project_id: int = Field(index=True)
    user_id: int | None = Field(default=None, index=True, description="Logged-in user id when source=session")
    share_id: int | None = Field(default=None, index=True, description="Share link id when source=share")
    share_access_id: int | None = Field(default=None, description="PvfShareLinkAccessed row used to establish identity")
    participant_key: str = Field(index=True, description="Stable identity key within project (user:id / share-cookie / email)")
    display_name: str | None = Field(default=None)
    email: str | None = Field(default=None, index=True)
    source: VoteSource = Field(default=VoteSource.session)
    is_ai: bool = Field(default=False, description="True when this participant is an AI agent")
    ai_model: str | None = Field(default=None, description="LLM model identifier when is_ai")
    group_count: int = Field(default=0, description="Completed sort groups")
    comparison_count: int = Field(default=0, description="Total pair comparisons across groups")
    is_complete: bool = Field(default=False, description="Participant marked their comparison session complete")
    last_activity_date: datetime | None = Field(default=None)
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))
    deleted_date: datetime | None = Field(default=None)

    @property
    def observation_count(self) -> int:
        """Back-compat alias: total pair comparisons."""
        return int(self.comparison_count or 0)

    @staticmethod
    def build_session_key(user_id: int) -> str:
        return f"user:{user_id}"

    @staticmethod
    def build_share_key(*, share_id: int, cookie_token: str | None, email: str | None,
                        email_verified: bool = False) -> str:
        # Verified (magic-key or recipient-on-file) emails are the single stable identity
        # for a share: a re-verified email always joins the same participant, even across
        # cookies/devices. Unverified emails are informational only and fall back to the
        # cookie key (a fresh cookie means a fresh participant).
        if email_verified and email:
            return f"share:{share_id}:email:{(email or '').strip().lower()}"
        if cookie_token:
            digest = get_hex_hash_from_args(settings.VIEW_TOKEN_KEY, str(share_id), cookie_token)[:24]
            return f"share:{share_id}:cookie:{digest}"
        if email:
            return f"share:{share_id}:email:{(email or '').strip().lower()}"
        return f"share:{share_id}:anon"

    @staticmethod
    def _find_existing_share_participant_by_email(*, session: Session, customer_id: int,
                                                 project_id: int, share_id: int, email: str | None):
        normalized = (email or '').strip().lower()
        if not normalized:
            return None
        return session.exec(
            select(ProjectVoteParticipant).where(
                ProjectVoteParticipant.customer_id == customer_id,
                ProjectVoteParticipant.project_id == project_id,
                ProjectVoteParticipant.share_id == share_id,
                ProjectVoteParticipant.email != None,
                ProjectVoteParticipant.deleted_date == None,
                func.lower(ProjectVoteParticipant.email) == normalized,
            ).order_by(
                ProjectVoteParticipant.comparison_count.desc(),
                ProjectVoteParticipant.id.asc(),
            ).limit(1)
        ).one_or_none()

    @staticmethod
    def get_or_create_session_participant(
        session: Session,
        *,
        usr_context: PvfUserContext,
        project_id: int,
        clear_lock: bool = True,
    ) -> ProjectVoteParticipantResult_One:
        project_result = CustomerProject.get_customer_project_by_id(
            session=session, id=project_id, usr_context=usr_context, clear_lock=False
        )
        if project_result.failure_reason or project_result.customer_project_info is None:
            if clear_lock:
                session.close()
            return ProjectVoteParticipantResult_One(
                failure_reason=project_result.failure_reason or "Project not found",
                log_id=project_result.log_id,
            )
        project = project_result.customer_project_info
        blocked = project_input_block_reason(project)
        if blocked:
            if clear_lock:
                session.close()
            return ProjectVoteParticipantResult_One(failure_reason=blocked)

        key = ProjectVoteParticipant.build_session_key(usr_context.sess_user.id)
        row = session.exec(
            select(ProjectVoteParticipant).where(
                ProjectVoteParticipant.customer_id == project.customer_id,
                ProjectVoteParticipant.project_id == project.id,
                ProjectVoteParticipant.participant_key == key,
                ProjectVoteParticipant.deleted_date == None,
            ).limit(1)
        ).one_or_none()
        if row is None:
            row = ProjectVoteParticipant(
                customer_id=project.customer_id,
                project_id=project.id,
                user_id=usr_context.sess_user.id,
                participant_key=key,
                display_name=usr_context.sess_user.name,
                email=usr_context.sess_user.email,
                source=VoteSource.session,
                last_activity_date=datetime.now(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        if clear_lock:
            session.close()
        return ProjectVoteParticipantResult_One(participant_info=row)

    @staticmethod
    def get_or_create_share_participant(
        session: Session,
        *,
        customer_id: int,
        project_id: int,
        share_id: int,
        share_access_id: int | None,
        cookie_token: str | None,
        display_name: str | None,
        email: str | None,
        email_verified: bool = False,
        clear_lock: bool = True,
    ) -> ProjectVoteParticipantResult_One:
        key = ProjectVoteParticipant.build_share_key(share_id=share_id, cookie_token=cookie_token,
                                                     email=email, email_verified=email_verified)
        row = session.exec(
            select(ProjectVoteParticipant).where(
                ProjectVoteParticipant.customer_id == customer_id,
                ProjectVoteParticipant.project_id == project_id,
                ProjectVoteParticipant.participant_key == key,
                ProjectVoteParticipant.deleted_date == None,
            ).limit(1)
        ).one_or_none()
        if row is None and email_verified and email:
            # Verified emails bind one participant per (share, email). If identity was
            # previously established under a cookie key (e.g. before verified-keyed
            # identity, or a data state from earlier releases), re-key that row so the
            # participant's vote history carries over instead of duplicating.
            row = ProjectVoteParticipant._find_existing_share_participant_by_email(
                session=session,
                customer_id=customer_id,
                project_id=project_id,
                share_id=share_id,
                email=email,
            )
            if row is not None:
                row.participant_key = key
        if row is None:
            row = ProjectVoteParticipant(
                customer_id=customer_id,
                project_id=project_id,
                share_id=share_id,
                share_access_id=share_access_id,
                participant_key=key,
                display_name=display_name,
                email=email,
                source=VoteSource.share,
                last_activity_date=datetime.now(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        else:
            changed = False
            if row.participant_key != key:
                row.participant_key = key
                changed = True
            if display_name and row.display_name != display_name:
                row.display_name = display_name
                changed = True
            if email and row.email != email:
                row.email = email
                changed = True
            if share_access_id and row.share_access_id != share_access_id:
                row.share_access_id = share_access_id
                changed = True
            if changed:
                row.last_activity_date = datetime.now()
                session.add(row)
                session.commit()
                session.refresh(row)
        if clear_lock:
            session.close()
        return ProjectVoteParticipantResult_One(participant_info=row)

    @staticmethod
    def build_ai_key(model_key: str | None = None) -> str:
        from ...utils.ai.identity import build_ai_participant_key
        return build_ai_participant_key(model_key)

    @staticmethod
    def get_or_create_ai_participant(
        session: Session,
        *,
        customer_id: int,
        project_id: int,
        model_key: str | None = None,
        display_name: str | None = None,
        clear_lock: bool = True,
    ) -> ProjectVoteParticipantResult_One:
        from ...utils.ai.config import DEFAULT_MODEL_KEY, is_default_model_key, normalize_model_key
        from ...utils.ai.identity import (
            AI_DISPLAY_NAME,
            LEGACY_AI_PARTICIPANT_KEY,
            ai_display_name,
            build_ai_participant_key,
        )

        key = build_ai_participant_key(model_key)
        name = display_name or ai_display_name(model_key)
        stored_model = None if is_default_model_key(model_key) else normalize_model_key(model_key)
        keys = [key]
        if is_default_model_key(model_key):
            keys.append(LEGACY_AI_PARTICIPANT_KEY)
        row = session.exec(
            select(ProjectVoteParticipant).where(
                ProjectVoteParticipant.customer_id == customer_id,
                ProjectVoteParticipant.project_id == project_id,
                ProjectVoteParticipant.participant_key.in_(keys),
                ProjectVoteParticipant.deleted_date == None,
            ).order_by(ProjectVoteParticipant.id.asc()).limit(1)
        ).one_or_none()
        if row is None:
            row = ProjectVoteParticipant(
                customer_id=customer_id,
                project_id=project_id,
                participant_key=key,
                display_name=name,
                source=VoteSource.ai,
                is_ai=True,
                ai_model=stored_model or DEFAULT_MODEL_KEY,
                last_activity_date=datetime.now(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        else:
            changed = False
            if row.participant_key != key:
                row.participant_key = key
                changed = True
            if row.source != VoteSource.ai:
                row.source = VoteSource.ai
                changed = True
            if not row.is_ai:
                row.is_ai = True
                changed = True
            if (row.ai_model or None) != (stored_model or DEFAULT_MODEL_KEY):
                row.ai_model = stored_model or DEFAULT_MODEL_KEY
                changed = True
            if row.display_name != name:
                row.display_name = name
                changed = True
            if changed:
                row.last_activity_date = datetime.now()
                session.add(row)
                session.commit()
                session.refresh(row)
        if clear_lock:
            session.close()
        return ProjectVoteParticipantResult_One(participant_info=row)

    @staticmethod
    def get_by_id_system(session: Session, *, participant_id: int, clear_lock: bool = True) -> ProjectVoteParticipant | None:
        row = session.exec(
            select(ProjectVoteParticipant).where(
                ProjectVoteParticipant.id == participant_id,
                ProjectVoteParticipant.deleted_date == None,
            ).limit(1)
        ).one_or_none()
        if clear_lock:
            session.close()
        return row

    @staticmethod
    def list_for_project(
        session: Session,
        *,
        usr_context: PvfUserContext,
        project_id: int,
        clear_lock: bool = True,
    ) -> ProjectVoteParticipantResult_Many:
        project_result = CustomerProject.get_customer_project_by_id(
            session=session, id=project_id, usr_context=usr_context, clear_lock=False
        )
        if project_result.failure_reason or project_result.customer_project_info is None:
            if clear_lock:
                session.close()
            return ProjectVoteParticipantResult_Many(
                failure_reason=project_result.failure_reason or "Project not found",
                log_id=project_result.log_id,
            )
        project = project_result.customer_project_info
        rows = list(session.exec(
            select(ProjectVoteParticipant).where(
                ProjectVoteParticipant.customer_id == project.customer_id,
                ProjectVoteParticipant.project_id == project.id,
                ProjectVoteParticipant.deleted_date == None,
            ).order_by(ProjectVoteParticipant.create_date.desc())
        ).all())
        if clear_lock:
            session.close()
        return ProjectVoteParticipantResult_Many(participant_info_list=rows)

    @staticmethod
    def list_for_project_system(
        session: Session,
        *,
        customer_id: int,
        project_id: int,
        clear_lock: bool = True,
    ) -> list[ProjectVoteParticipant]:
        rows = list(session.exec(
            select(ProjectVoteParticipant).where(
                ProjectVoteParticipant.customer_id == customer_id,
                ProjectVoteParticipant.project_id == project_id,
                ProjectVoteParticipant.deleted_date == None,
            )
        ).all())
        if clear_lock:
            session.close()
        return rows

    def mark_activity(self, session: Session, *, is_complete: bool | None = None, clear_lock: bool = True):
        self.last_activity_date = datetime.now()
        if is_complete is not None:
            self.is_complete = is_complete
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock:
            session.close()
        return self

    def bump_group_counts(
        self,
        session: Session,
        *,
        groups: int = 1,
        comparisons: int = 0,
        clear_lock: bool = False,
    ):
        self.group_count = (self.group_count or 0) + max(0, int(groups))
        self.comparison_count = (self.comparison_count or 0) + max(0, int(comparisons))
        self.last_activity_date = datetime.now()
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock:
            session.close()
        return self


class ProjectVoteGroupResult(SQLModel, table=True):
    """One compare group (options under a factor, overall options, or factors)."""
    __table_args__ = (
        UniqueConstraint("participant_id", "client_group_id", name="uq_vote_group_client_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True)
    project_id: int = Field(index=True)
    participant_id: int = Field(index=True)
    user_id: int | None = Field(default=None, index=True)
    share_id: int | None = Field(default=None, index=True)
    group_type: GroupType = Field(default=GroupType.alternative)
    criterion_id: int | None = Field(
        default=None,
        description="Factor id for option sorts; null for overall (0 stored as null) or factor-ranking groups",
    )
    sort_algorithm: SortAlgorithm = Field(default=SortAlgorithm.ford_johnson)
    pass_index: int = Field(default=1, description="1-based pass this group belongs to")
    item_ids_initial: list[int] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False, default=list))
    rank_order: list[int] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, default=list),
        description="Item ids best→worst (rank 0 = first); provisional until authoritative stats",
    )
    pairings: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, default=list),
        description="Pair logs: winner_id, loser_id, response, decision_seconds, presented sides",
    )
    comparison_count: int = Field(default=0)
    client_group_id: str = Field(index=True, description="Client/server idempotency key")
    group_token: str | None = Field(default=None, index=True, description="Unpredictable 10-char group token")
    status: str = Field(default=GroupStatus.complete.value, description="in_progress or complete")
    requested_pairing_count: int = Field(default=0, description="Question budget issued with the group")
    received_pairing_count: int = Field(default=0, description="Pairings stored for this group")
    historical_pairing_count: int = Field(
        default=0, description="Prior-channel pairings provided to the client for scheduling"
    )
    ranking_target: str = Field(default=RankingTarget.full.value)
    top_n: int | None = Field(default=None)
    batch_index: int = Field(default=0)
    algorithm_version: str = Field(default="1.0-sort")
    event_timestamp: datetime | None = Field(default=None, description="Client event time when group completed")
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))
    deleted_date: datetime | None = Field(default=None)

    @staticmethod
    def list_for_participant_system(
        session: Session,
        *,
        participant_id: int,
        clear_lock: bool = True,
    ) -> list[ProjectVoteGroupResult]:
        rows = list(session.exec(
            select(ProjectVoteGroupResult).where(
                ProjectVoteGroupResult.participant_id == participant_id,
                ProjectVoteGroupResult.deleted_date == None,
            ).order_by(ProjectVoteGroupResult.create_date.asc())
        ).all())
        if clear_lock:
            session.close()
        return rows

    @staticmethod
    def list_for_project_system(
        session: Session,
        *,
        customer_id: int,
        project_id: int,
        clear_lock: bool = True,
    ) -> list[ProjectVoteGroupResult]:
        rows = list(session.exec(
            select(ProjectVoteGroupResult).where(
                ProjectVoteGroupResult.customer_id == customer_id,
                ProjectVoteGroupResult.project_id == project_id,
                ProjectVoteGroupResult.deleted_date == None,
            ).order_by(ProjectVoteGroupResult.create_date.asc())
        ).all())
        if clear_lock:
            session.close()
        return rows

    @staticmethod
    def get_by_client_group_id(
        session: Session,
        *,
        participant_id: int,
        client_group_id: str,
        clear_lock: bool = False,
    ) -> ProjectVoteGroupResult | None:
        row = session.exec(
            select(ProjectVoteGroupResult).where(
                ProjectVoteGroupResult.participant_id == participant_id,
                ProjectVoteGroupResult.client_group_id == client_group_id,
                ProjectVoteGroupResult.deleted_date == None,
            ).limit(1)
        ).one_or_none()
        if clear_lock:
            session.close()
        return row

    @staticmethod
    def get_by_group_token(
        session: Session,
        *,
        group_token: str,
        participant_id: int | None = None,
        clear_lock: bool = False,
    ) -> ProjectVoteGroupResult | None:
        token = (group_token or "").strip()
        if not token:
            if clear_lock:
                session.close()
            return None
        q = select(ProjectVoteGroupResult).where(
            ProjectVoteGroupResult.group_token == token,
            ProjectVoteGroupResult.deleted_date == None,
        )
        if participant_id is not None:
            q = q.where(ProjectVoteGroupResult.participant_id == participant_id)
        row = session.exec(q.limit(1)).one_or_none()
        if clear_lock:
            session.close()
        return row

    @staticmethod
    def get_in_progress_for_participant(
        session: Session,
        *,
        participant_id: int,
        clear_lock: bool = False,
    ) -> ProjectVoteGroupResult | None:
        row = session.exec(
            select(ProjectVoteGroupResult).where(
                ProjectVoteGroupResult.participant_id == participant_id,
                ProjectVoteGroupResult.status == GroupStatus.in_progress.value,
                ProjectVoteGroupResult.deleted_date == None,
            ).order_by(ProjectVoteGroupResult.create_date.asc()).limit(1)
        ).one_or_none()
        if clear_lock:
            session.close()
        return row

    @staticmethod
    def issue_group_result(
        session: Session,
        *,
        participant: ProjectVoteParticipant,
        group_type: GroupType,
        criterion_id: int | None,
        sort_algorithm: SortAlgorithm,
        pass_index: int,
        item_ids_initial: list[int],
        client_group_id: str,
        group_token: str,
        requested_pairing_count: int,
        historical_pairing_count: int = 0,
        ranking_target: str = "full",
        top_n: int | None = None,
        batch_index: int = 0,
        algorithm_version: str = "1.1-adaptive",
        clear_lock: bool = True,
    ) -> ProjectVoteGroupResultResult_One:
        cid = (client_group_id or group_token or "").strip()
        token = (group_token or cid).strip()
        if not cid or not token:
            if clear_lock:
                session.close()
            return ProjectVoteGroupResultResult_One(failure_reason="group_token is required")
        existing = ProjectVoteGroupResult.get_by_client_group_id(
            session=session, participant_id=int(participant.id), client_group_id=cid, clear_lock=False
        )
        if existing is None:
            existing = ProjectVoteGroupResult.get_by_group_token(
                session=session, group_token=token, participant_id=int(participant.id), clear_lock=False
            )
        if existing is not None:
            if clear_lock:
                session.close()
            return ProjectVoteGroupResultResult_One(group_info=existing)
        initial = [int(x) for x in (item_ids_initial or [])]
        row = ProjectVoteGroupResult(
            customer_id=participant.customer_id,
            project_id=participant.project_id,
            participant_id=participant.id,
            user_id=participant.user_id,
            share_id=participant.share_id,
            group_type=group_type,
            criterion_id=criterion_id,
            sort_algorithm=sort_algorithm,
            pass_index=max(1, int(pass_index or 1)),
            item_ids_initial=initial,
            rank_order=[],
            pairings=[],
            comparison_count=0,
            client_group_id=cid,
            group_token=token,
            status=GroupStatus.in_progress.value,
            requested_pairing_count=max(0, int(requested_pairing_count or 0)),
            received_pairing_count=0,
            historical_pairing_count=max(0, int(historical_pairing_count or 0)),
            ranking_target=str(ranking_target or RankingTarget.full.value),
            top_n=top_n,
            batch_index=max(0, int(batch_index or 0)),
            algorithm_version=algorithm_version or "1.1-adaptive",
        )
        session.add(row)
        participant.last_activity_date = datetime.now()
        session.add(participant)
        session.commit()
        session.refresh(row)
        session.refresh(participant)
        payload = ProjectVoteGroupResult.model_validate(row.model_dump())
        if clear_lock:
            session.close()
        return ProjectVoteGroupResultResult_One(group_info=payload)

    @staticmethod
    def save_group_pairings(
        session: Session,
        *,
        participant: ProjectVoteParticipant,
        client_group_id: str,
        pairings: list[dict[str, Any]],
        rank_order: list[int] | None = None,
        event_timestamp: datetime | None = None,
        clear_lock: bool = True,
    ) -> ProjectVoteGroupResultResult_One:
        cid = (client_group_id or "").strip()
        row = ProjectVoteGroupResult.get_by_client_group_id(
            session=session, participant_id=int(participant.id), client_group_id=cid, clear_lock=False
        )
        if row is None:
            row = ProjectVoteGroupResult.get_by_group_token(
                session=session, group_token=cid, participant_id=int(participant.id), clear_lock=False
            )
        if row is None:
            if clear_lock:
                session.close()
            return ProjectVoteGroupResultResult_One(failure_reason="Group not found")
        if str(row.status) == GroupStatus.complete.value:
            if clear_lock:
                session.close()
            return ProjectVoteGroupResultResult_One(group_info=row)
        pairs = list(pairings or [])
        row.pairings = pairs
        row.received_pairing_count = len(pairs)
        row.comparison_count = len(pairs)
        if rank_order:
            row.rank_order = [int(x) for x in rank_order]
        if event_timestamp is not None:
            row.event_timestamp = event_timestamp
        session.add(row)
        participant.last_activity_date = datetime.now()
        session.add(participant)
        session.commit()
        session.refresh(row)
        session.refresh(participant)
        payload = ProjectVoteGroupResult.model_validate(row.model_dump())
        if clear_lock:
            session.close()
        return ProjectVoteGroupResultResult_One(group_info=payload)

    @staticmethod
    def create_group_result(
        session: Session,
        *,
        participant: ProjectVoteParticipant,
        group_type: GroupType,
        criterion_id: int | None,
        sort_algorithm: SortAlgorithm,
        pass_index: int,
        item_ids_initial: list[int],
        rank_order: list[int],
        pairings: list[dict[str, Any]],
        client_group_id: str,
        algorithm_version: str = "1.0-sort",
        event_timestamp: datetime | None = None,
        clear_lock: bool = True,
    ) -> ProjectVoteGroupResultResult_One:
        cid = (client_group_id or "").strip()
        if not cid:
            if clear_lock:
                session.close()
            return ProjectVoteGroupResultResult_One(failure_reason="client_group_id is required")
        existing = ProjectVoteGroupResult.get_by_client_group_id(
            session=session, participant_id=int(participant.id), client_group_id=cid, clear_lock=False
        )
        if existing is None:
            existing = ProjectVoteGroupResult.get_by_group_token(
                session=session, group_token=cid, participant_id=int(participant.id), clear_lock=False
            )
        if existing is not None and str(existing.status) == GroupStatus.complete.value:
            if clear_lock:
                session.close()
            return ProjectVoteGroupResultResult_One(group_info=existing)

        if not rank_order or len(rank_order) < 1:
            if clear_lock:
                session.close()
            return ProjectVoteGroupResultResult_One(failure_reason="rank_order is required")
        initial = [int(x) for x in (item_ids_initial or (existing.item_ids_initial if existing else []) or [])]
        order = [int(x) for x in rank_order]
        if sorted(order) != sorted(initial):
            if clear_lock:
                session.close()
            return ProjectVoteGroupResultResult_One(
                failure_reason="rank_order must be a permutation of item_ids_initial"
            )
        pairs = list(pairings or [])
        if existing is not None:
            existing.rank_order = order
            existing.pairings = pairs
            existing.comparison_count = len(pairs)
            existing.received_pairing_count = len(pairs)
            if existing.requested_pairing_count <= 0:
                existing.requested_pairing_count = len(pairs)
            existing.status = GroupStatus.complete.value
            existing.event_timestamp = event_timestamp or datetime.now()
            if algorithm_version:
                existing.algorithm_version = algorithm_version
            session.add(existing)
            participant.group_count = (participant.group_count or 0) + 1
            participant.comparison_count = (participant.comparison_count or 0) + len(pairs)
            participant.last_activity_date = datetime.now()
            session.add(participant)
            session.commit()
            session.refresh(existing)
            session.refresh(participant)
            payload = ProjectVoteGroupResult.model_validate(existing.model_dump())
            if clear_lock:
                session.close()
            return ProjectVoteGroupResultResult_One(group_info=payload)
        row = ProjectVoteGroupResult(
            customer_id=participant.customer_id,
            project_id=participant.project_id,
            participant_id=participant.id,
            user_id=participant.user_id,
            share_id=participant.share_id,
            group_type=group_type,
            criterion_id=criterion_id,
            sort_algorithm=sort_algorithm,
            pass_index=max(1, int(pass_index or 1)),
            item_ids_initial=initial,
            rank_order=order,
            pairings=pairs,
            comparison_count=len(pairs),
            client_group_id=cid,
            group_token=cid,
            status=GroupStatus.complete.value,
            requested_pairing_count=len(pairs),
            received_pairing_count=len(pairs),
            algorithm_version=algorithm_version or "1.0-sort",
            event_timestamp=event_timestamp or datetime.now(),
        )
        session.add(row)
        participant.group_count = (participant.group_count or 0) + 1
        participant.comparison_count = (participant.comparison_count or 0) + len(pairs)
        participant.last_activity_date = datetime.now()
        session.add(participant)
        session.commit()
        session.refresh(row)
        session.refresh(participant)
        payload = ProjectVoteGroupResult.model_validate(row.model_dump())
        if clear_lock:
            session.close()
        return ProjectVoteGroupResultResult_One(group_info=payload)
