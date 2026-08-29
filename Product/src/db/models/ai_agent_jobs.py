from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import SQLModel, Field, Session, select
from sqlalchemy import DateTime, Column, func
from sqlalchemy.dialects.postgresql import JSONB

from ...pvf.bindings.pvf_services import PvfWsResultPackage


class AiAgentJobResult_One(PvfWsResultPackage):
    job_info: AiAgentJob | None = None


class AiAgentJob(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True)
    project_id: int = Field(index=True)
    job_type: str = Field(default="ai_baseline", index=True)
    model_key: str = Field(default="__default__", index=True)
    status: str = Field(default="queued", index=True)
    requested_by_user_id: int | None = Field(default=None)
    participant_id: int | None = Field(default=None, index=True)
    pair_count: int = Field(default=0)
    skip_count: int = Field(default=0)
    group_count: int = Field(default=0)
    error_summary: str | None = Field(default=None)
    details_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, default=dict))
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))
    started_date: datetime | None = Field(default=None)
    completed_date: datetime | None = Field(default=None)
    deleted_date: datetime | None = Field(default=None)

    @staticmethod
    def get_active_for_project(
        session: Session,
        *,
        customer_id: int,
        project_id: int,
        model_key: str | None = None,
        clear_lock: bool = False,
    ) -> AiAgentJob | None:
        filters = [
            AiAgentJob.customer_id == customer_id,
            AiAgentJob.project_id == project_id,
            AiAgentJob.job_type == "ai_baseline",
            AiAgentJob.status.in_(("queued", "in_progress")),
            AiAgentJob.deleted_date == None,
        ]
        if model_key is not None:
            filters.append(AiAgentJob.model_key == model_key)
        row = session.exec(
            select(AiAgentJob).where(*filters).order_by(AiAgentJob.id.asc()).limit(1)
        ).one_or_none()
        if clear_lock:
            session.close()
        return row

    @staticmethod
    def latest_for_project(
        session: Session,
        *,
        customer_id: int,
        project_id: int,
        clear_lock: bool = False,
    ) -> AiAgentJob | None:
        row = session.exec(
            select(AiAgentJob).where(
                AiAgentJob.customer_id == customer_id,
                AiAgentJob.project_id == project_id,
                AiAgentJob.job_type == "ai_baseline",
                AiAgentJob.deleted_date == None,
            ).order_by(AiAgentJob.id.desc()).limit(1)
        ).one_or_none()
        if clear_lock:
            session.close()
        return row

    @staticmethod
    def count_in_progress(session: Session, *, clear_lock: bool = False) -> int:
        n = session.exec(
            select(func.count()).select_from(AiAgentJob).where(
                AiAgentJob.status == "in_progress",
                AiAgentJob.deleted_date == None,
            )
        ).one()
        if clear_lock:
            session.close()
        return int(n or 0)

    @staticmethod
    def _oldest_in_progress(session: Session) -> AiAgentJob | None:
        return session.exec(
            select(AiAgentJob).where(
                AiAgentJob.status == "in_progress",
                AiAgentJob.deleted_date == None,
            ).order_by(AiAgentJob.modify_date.asc(), AiAgentJob.id.asc()).limit(1)
        ).one_or_none()

    @staticmethod
    def claim_next(
        session: Session,
        *,
        max_concurrent: int,
        clear_lock: bool = False,
    ) -> AiAgentJob | None:
        in_progress = AiAgentJob.count_in_progress(session, clear_lock=False)
        row: AiAgentJob | None = None
        if in_progress < max_concurrent:
            row = session.exec(
                select(AiAgentJob).where(
                    AiAgentJob.status == "queued",
                    AiAgentJob.deleted_date == None,
                ).order_by(AiAgentJob.id.asc()).limit(1)
            ).one_or_none()
            if row is not None:
                row.status = "in_progress"
                row.started_date = datetime.now()
                row.modify_date = datetime.now()
                session.add(row)
                session.commit()
                session.refresh(row)
                if clear_lock:
                    session.close()
                return row
        row = AiAgentJob._oldest_in_progress(session)
        if row is not None:
            row.modify_date = datetime.now()
            session.add(row)
            session.commit()
            session.refresh(row)
        if clear_lock:
            session.close()
        return row

    @staticmethod
    def list_for_project(
        session: Session,
        *,
        customer_id: int,
        project_id: int,
        clear_lock: bool = False,
    ) -> list[AiAgentJob]:
        rows = session.exec(
            select(AiAgentJob).where(
                AiAgentJob.customer_id == customer_id,
                AiAgentJob.project_id == project_id,
                AiAgentJob.job_type == "ai_baseline",
                AiAgentJob.deleted_date == None,
            ).order_by(AiAgentJob.id.desc())
        ).all()
        if clear_lock:
            session.close()
        return list(rows or [])

    @staticmethod
    def enqueue_baseline(
        session: Session,
        *,
        customer_id: int,
        project_id: int,
        requested_by_user_id: int | None,
        model_key: str = "__default__",
        details: dict[str, Any] | None = None,
        clear_lock: bool = True,
    ) -> AiAgentJobResult_One:
        existing = AiAgentJob.get_active_for_project(
            session=session,
            customer_id=customer_id,
            project_id=project_id,
            model_key=model_key,
            clear_lock=False,
        )
        if existing is not None:
            payload = existing
            if clear_lock:
                session.close()
            return AiAgentJobResult_One(job_info=payload)
        row = AiAgentJob(
            customer_id=customer_id,
            project_id=project_id,
            job_type="ai_baseline",
            model_key=model_key or "__default__",
            status="queued",
            requested_by_user_id=requested_by_user_id,
            details_json=details or {},
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        if clear_lock:
            session.close()
        return AiAgentJobResult_One(job_info=row)
