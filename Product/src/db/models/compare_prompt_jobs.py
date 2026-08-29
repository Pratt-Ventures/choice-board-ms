from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import SQLModel, Field, Session, select
from sqlalchemy import DateTime, Column, func
from sqlalchemy.dialects.postgresql import JSONB

from ...pvf.bindings.pvf_services import PvfWsResultPackage


class ComparePromptJobResult_One(PvfWsResultPackage):
    job_info: ComparePromptJob | None = None


class ComparePromptJob(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True)
    project_id: int = Field(index=True)
    item_type: str = Field(index=True, description="option or factor")
    item_id: int = Field(index=True)
    status: str = Field(default="queued", index=True)
    requested_by_user_id: int | None = Field(default=None)
    error_summary: str | None = Field(default=None)
    details_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, default=dict))
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))
    started_date: datetime | None = Field(default=None)
    completed_date: datetime | None = Field(default=None)
    deleted_date: datetime | None = Field(default=None)

    @staticmethod
    def enqueue(
        session: Session,
        *,
        customer_id: int,
        project_id: int,
        item_type: str,
        item_id: int,
        requested_by_user_id: int | None,
        clear_lock: bool = False,
    ) -> ComparePromptJob:
        # dedup queued/in_progress for same item
        existing = session.exec(
            select(ComparePromptJob).where(
                ComparePromptJob.customer_id == customer_id,
                ComparePromptJob.project_id == project_id,
                ComparePromptJob.item_type == item_type,
                ComparePromptJob.item_id == item_id,
                ComparePromptJob.status.in_(("queued", "in_progress")),
                ComparePromptJob.deleted_date == None,
            ).limit(1)
        ).one_or_none()
        if existing is not None:
            if clear_lock:
                session.close()
            return existing
        row = ComparePromptJob(
            customer_id=customer_id,
            project_id=project_id,
            item_type=item_type,
            item_id=item_id,
            status="queued",
            requested_by_user_id=requested_by_user_id,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        if clear_lock:
            session.close()
        return row

    @staticmethod
    def queued_count(session: Session, *, project_id: int, customer_id: int, clear_lock: bool = False) -> int:
        n = session.exec(
            select(func.count()).select_from(ComparePromptJob).where(
                ComparePromptJob.project_id == project_id,
                ComparePromptJob.customer_id == customer_id,
                ComparePromptJob.status.in_(("queued", "in_progress")),
                ComparePromptJob.deleted_date == None,
            )
        ).one()
        if clear_lock:
            session.close()
        return int(n or 0)

    @staticmethod
    def claim_next(session: Session, clear_lock: bool = False) -> ComparePromptJob | None:
        row = session.exec(
            select(ComparePromptJob).where(
                ComparePromptJob.status == "queued",
                ComparePromptJob.deleted_date == None,
            ).order_by(ComparePromptJob.id.asc()).limit(1)
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

    @staticmethod
    def list_for_project(session: Session, *, project_id: int, customer_id: int, clear_lock: bool = False) -> list[ComparePromptJob]:
        rows = list(session.exec(
            select(ComparePromptJob).where(
                ComparePromptJob.project_id == project_id,
                ComparePromptJob.customer_id == customer_id,
                ComparePromptJob.deleted_date == None,
            ).order_by(ComparePromptJob.id.desc())
        ).all())
        if clear_lock:
            session.close()
        return rows
