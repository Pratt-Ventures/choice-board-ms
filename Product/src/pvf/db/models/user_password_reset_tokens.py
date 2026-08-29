from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime, timezone
from typing import Union
from passlib.context import CryptContext
import uuid

from sqlmodel import SQLModel, Field, Session, select
from sqlalchemy import func, DateTime, Column

from ...utils.log_event import log_event
from ...utils.pvf_base_internal_resources import get_random_baseN_value

# Handle circular imports: https://sqlmodel.tiangolo.com/tutorial/code-structure/#hero-model-file.  Commenting out for now because it throws an error?
# if TYPE_CHECKING:
#     from .user_passwords import PvfUserPasswords

class PvfUserPasswordReset(SQLModel, table=True):
    __tablename__ = "pvf_userpasswordreset"
    id: int | None = Field(default=None, primary_key=True)
    email: str
    token: str = Field(index=True, unique=True)
    token_used_date: datetime | None = None
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    # from https://github.com/fastapi/sqlmodel/discussions/990 regarding onupdate support simulation in sqlmodel
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))

    @staticmethod
    def create_user_password_reset_system(*, session: Session, email: str, clear_lock: bool=True) -> PvfUserPasswordReset:

        user_pw_reset = PvfUserPasswordReset(email=email, token=get_random_baseN_value(length=8))
        session.add(user_pw_reset)
        session.commit()
        session.refresh(user_pw_reset)
        if clear_lock: session.close()
        return user_pw_reset

    @staticmethod
    def get_user_password_reset_by_token_system(*, session: Session, token: str, clear_lock: bool=True) -> PvfUserPasswordReset | None:
        user_pw_reset = session.exec(select(PvfUserPasswordReset).where(PvfUserPasswordReset.token == token).limit(1)).one_or_none()
        if clear_lock: session.close()
        return user_pw_reset
    
    def set_token_used(self, *, session: Session, clear_lock: bool=True) -> bool:
        self.token_used_date = datetime.now(timezone.utc)
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        return True