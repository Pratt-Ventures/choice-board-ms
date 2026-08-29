from __future__ import annotations
from typing import TYPE_CHECKING, Any, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
from passlib.context import CryptContext

from sqlmodel import SQLModel, Field, Session, select, desc
from sqlalchemy import func, DateTime, Column
from sqlalchemy.dialects.postgresql import JSONB

from .customer_user import PvfUserContext

class PvfEmailActivityLog(SQLModel, table=True):
    __tablename__ = "pvf_emailactivitylog"
    id: int | None = Field(default=None, primary_key=True)
    email_address: str = Field(default=None, index=True, description="The email address associated with the activity log")
    email_type: str = Field(default="not_set", description="The type of outbound email in terms of purpose or context; binds to a template name")
    email_service: str | None = Field(default=None, description="Name of mechanism or service; sendgrid or similar")
    email_params_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, default=dict), description="Additional email parameters")
    # the remainder are filled in from usr_context if available.
    user_id: int = Field(default=-1, description="The ID of the user associated with the email activity")
    customer_id: int = Field(default=-1, description="The ID of the customer associated with the email activity")
    remote_ip: str = Field(default='', index=True, description="The remote IP address from which the email activity originated")
    url_path: str = Field(default='', description="The URL path associated with the email activity")
    result_message: str = Field(default=None, description="The result message or status of the email activity")
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))

    def create_email_event(self, session: Session, usr_context: PvfUserContext, clear_lock: bool=True) -> PvfEmailActivityLog:
        if usr_context is not None:
            if usr_context.sess_user is not None:
                if self.user_id in (None, "", 0, -1): self.user_id = usr_context.sess_user.id 
                if self.customer_id in (None, "", 0, -1): self.customer_id = usr_context.sess_user.customer_id 
            if self.remote_ip in (None, ""): self.remote_ip = usr_context.remote_ip
            if self.url_path in (None, ""): self.url_path = usr_context.url_path
        self.email_address = self.email_address.lower()
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        
        return self.id
   
    @staticmethod    
    def get_recent_log_events_system(session: Session, email_address: str=None, remote_ip: str=None, email_type: str | Enum | None=None, cutoff_hours: int | None=None, limit: int=25, clear_lock: bool=True) -> PvfEmailActivityLog:
        filter_clauses = []
        if cutoff_hours is not None:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)
            filter_clauses.append(PvfEmailActivityLog.create_date > cutoff_time)
        if email_address is not None:
            email_address = email_address.lower()
            filter_clauses.append(PvfEmailActivityLog.email_address == email_address)
        if remote_ip is not None:
            filter_clauses.append(PvfEmailActivityLog.remote_ip == remote_ip)
        if email_type is not None:
            if isinstance(email_type, Enum):
                email_type = str(email_type.value)
            else:
                email_type = str(email_type)
            filter_clauses.append(PvfEmailActivityLog.email_type == email_type)
        if len(filter_clauses):
            app_log_rows = session.exec(select(PvfEmailActivityLog).where(*filter_clauses).order_by(desc(PvfEmailActivityLog.id)).limit(limit)).all()
        else:
            app_log_rows = session.exec(select(PvfEmailActivityLog).order_by(desc(PvfEmailActivityLog.id)).limit(limit)).all()
        if clear_lock: session.close()
        return app_log_rows