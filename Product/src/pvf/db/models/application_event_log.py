from __future__ import annotations
from typing import TYPE_CHECKING, Any, Union
from datetime import datetime

from sqlmodel import SQLModel, Field, Session, select, desc
from sqlalchemy import func, DateTime, Column
from sqlalchemy.dialects.postgresql import JSONB

from ...utils.pvf_base_internal_resources import PvfWsResultPackage

class PvfLogEventResult_One_Id(PvfWsResultPackage):
    log_event_id: Union[int, None] = None

class PvfLogEventResult_One(PvfWsResultPackage):
    log_event_info: Union[PvfApplicationLogEvent, None] = None

class PvfLogEventResult_Many(PvfWsResultPackage):
    log_event_info_list: Union[list[PvfApplicationLogEvent], None] = None

# Handle circular imports: https://sqlmodel.tiangolo.com/tutorial/code-structure/#hero-model-file.  Commenting out for now because it throws an error?
# if TYPE_CHECKING:
#     from .user_passwords import PvfUserPasswords

class PvfApplicationLogEvent(SQLModel, table=True):
    __tablename__ = "pvf_applicationlogevent"
    id: int | None = Field(default=None, primary_key=True)
    event_time: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    severity: int=1   # 0=debug, 1=info, 2=warning, 3=error, 4=critical, 5=crisis, 6=catastrophic, 7=apocalypse, 8=extinction-level-event
    computer_name: str
    process_name: str
    process_id: int
    authenticated_session: bool = False
    customer_id: int
    user_id: int
    api_config_key_id: str | None = ''
    customer_admin: bool = False
    remote_ip: str = ''
    url_path: str = ''
    exception_msg: str = ''
    exception_trace: str = ''
    log_message: str
    kw_details: str = ''
    details_str: str | None = None
    details_json: dict[str, Any] | list[Any] | None = Field(
        default=None, sa_column=Column(JSONB, default=None, nullable=True)
    )

    def create_log_event(self, session: Session) -> int:
        session.add(self)
        session.commit()
        session.refresh(self)
        session.commit()
        return self.id
    
    @staticmethod
    def get_log_event_by_id(session: Session, id: int, clear_lock: bool=True) -> PvfApplicationLogEvent:
        log_results = session.exec(select(PvfApplicationLogEvent).where(PvfApplicationLogEvent.id == id).limit(1)).one_or_none()
        if clear_lock: session.close()        
        return log_results

    @staticmethod    
    def get_log_events_system(session: Session, customer_id=None, user_id=None, limit: int=25, clear_lock: bool=True) -> PvfApplicationLogEvent:
        if user_id is not None:
            app_log_rows =  session.exec(select(PvfApplicationLogEvent).where(PvfApplicationLogEvent.user_id == user_id).order_by(desc(PvfApplicationLogEvent.id)).limit(limit)).all()
        elif customer_id is not None:
            app_log_rows = session.exec(select(PvfApplicationLogEvent).where(PvfApplicationLogEvent.customer_id == customer_id).order_by(desc(PvfApplicationLogEvent.id)).limit(limit)).all()
        else:
            app_log_rows = session.exec(select(PvfApplicationLogEvent).order_by(desc(PvfApplicationLogEvent.id)).limit(limit)).all()
        if clear_lock: session.close()
        return app_log_rows