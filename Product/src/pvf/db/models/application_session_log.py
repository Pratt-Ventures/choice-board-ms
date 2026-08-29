from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime
from enum import Enum
from passlib.context import CryptContext

from sqlmodel import SQLModel, Field, Session, select, desc
from sqlalchemy import func, DateTime, Column


# Handle circular imports: https://sqlmodel.tiangolo.com/tutorial/code-structure/#hero-model-file.  Commenting out for now because it throws an error?
# if TYPE_CHECKING:
#     from .user_passwords import PvfUserPasswords

class PvfUserSessionLog(SQLModel, table=True):
    __tablename__ = "pvf_usersessionlog"
    id: int | None = Field(default=None, primary_key=True)
    event_time: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    computer_name: str
    process_name: str
    process_id: int
    customer_id: int
    user_id: int
    remote_ip: str
    customer_admin: bool = False

    def create_user_session_entry(self, session: Session) -> int:
        session.add(self)
        session.commit()
        session.refresh(self)
        session.close()
        return self.id
    
    @staticmethod
    def get_user_session_entry_by_id(session: Session, id: int, clear_lock:bool = True) -> PvfUserSessionLog:
        result_session = session.exec(select(PvfUserSessionLog).where(PvfUserSessionLog.id == id).limit(1)).one_or_none()
        if clear_lock: session.close()
        return result_session

    @staticmethod    
    def get_user_session_entries(session: Session, customer_id=None, user_id=None, limit: int=25, clear_lock: bool=True) -> PvfUserSessionLog:
        if user_id is not None:
            session_result = session.exec(select(PvfUserSessionLog).where(PvfUserSessionLog.user_id == user_id).order_by(desc(PvfUserSessionLog.id)).limit(limit))
        elif customer_id is not None:
            session_result = session.exec(select(PvfUserSessionLog).where(PvfUserSessionLog.customer_id == customer_id).order_by(desc(PvfUserSessionLog.id)).limit(limit))
        else:
            session_result = session.exec(select(PvfUserSessionLog).order_by(desc(PvfUserSessionLog.id)).limit(limit))
        if clear_lock: session.close()
        return session_result