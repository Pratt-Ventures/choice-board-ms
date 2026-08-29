from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import func, DateTime, Column

class PvfUserPasswords(SQLModel, table=True):
    __tablename__ = "pvf_userpasswords"
    id: int = Field(primary_key=True)
    user_id: int = Field(foreign_key="pvf_user.id")
    hash: str
    last_2fa_hash: str | None = Field(default=None)
    last_2fa_issued_at: datetime | None = Field(default=None, sa_column=Column(DateTime, default=None, nullable=True))
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    # from https://github.com/fastapi/sqlmodel/discussions/990 regarding onupdate support simulation in sqlmodel
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))
