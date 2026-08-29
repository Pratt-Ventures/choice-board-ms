from typing import Union
from pydantic import BaseModel

from sqlmodel import Field
from fastapi import APIRouter, Request

from ..depends.api_session_dependencies import SessionDep
from ..depends.check_user_session_jwt_dependencies import UserAccessDep
from ..db.models.application_event_log import PvfApplicationLogEvent as LogModel
from ..db.models.application_event_log import PvfLogEventResult_One_Id, PvfLogEventResult_Many, PvfLogEventResult_One, PvfApplicationLogEvent
from ..utils.pvf_base_internal_resources import PvfLogSeverity
from ..utils.log_event import log_event

from ..config.pvf_config_settings import pvf_settings as settings

router = APIRouter()

class LogViewRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=250, description="Specifies maximum nubmer of log rows to return (latest first)")
    only_user: bool = Field(default=False, description="If True, restrict results to current user only")
    only_customer: bool = Field(default=True, description="If True, restrict results to current customer account only")

class PostLogEvent(BaseModel):
    severity: PvfLogSeverity
    computer_name: str | None = None
    log_message: str
    added_details: str | None = None
    kw_details: dict[str, Union[str, int, float]] = None
    details_json: Union[list, dict, None] = None

@router.post('/log/recent-events', summary='Return recent log events (for diagnostic purposes)',
             tags=["devops"])
def get_recent_log_events(session: SessionDep, usr_context: UserAccessDep, log_request: LogViewRequest) -> PvfLogEventResult_Many:
    # we don't error, but constrain the request to what we would authorize
    # logged in users can indirectly access recent log entries for the user.
    # customer admins can see recent logs for customer
    # power_user 2 can see recent logs for all
    if usr_context.sess_user.customer_admin is False:
        log_request.only_user = True
    if usr_context.sess_user.system_user_mode < 2:
        log_request.only_customer = True
    select_user_id = usr_context.sess_user.id if log_request.only_user else None
    select_customer_id = usr_context.sess_user.customer_id if log_request.only_customer else None
    result_set = LogModel.get_log_events_system(session=session, customer_id=select_customer_id, user_id=select_user_id, limit=log_request.limit)
    return PvfLogEventResult_Many(log_event_info_list=result_set)

@router.post('/log/post-log-event', summary='Post a log event to the server for review/analysis (for diagnostic purposes)',
             tags=["devops"])
def post_log_event(request: Request, session: SessionDep, usr_context: UserAccessDep, log_ui_event: PostLogEvent) -> PvfLogEventResult_One_Id:
    # we don't error, but constrain the request to what we would authorize
    # logged in users can indirectly access recent log entries for the user.
    # customer admins can see recent logs for customer
    # power_user 2 can see recent logs for all
    if log_ui_event.kw_details is not None:
        kw_details_info = '; '.join([f'{str(kw)}={str(val)}' for kw, val in log_ui_event.kw_details.items()])
    else:
        kw_details_info = None

    log_entry = PvfApplicationLogEvent(severity=log_ui_event.severity.value,
                                    computer_name=log_ui_event.computer_name,
                                    user_id=usr_context.sess_user.id,
                                    customer_id=usr_context.sess_user.customer_id,
                                    customer_admin=usr_context.sess_user.customer_admin,
                                    log_message=log_ui_event.log_message,
                                    remote_ip=usr_context.remote_ip,
                                    url_path=usr_context.url_path,
                                    kw_details=kw_details_info,
                                     details_str=log_ui_event.added_details,
                                     details_json=log_ui_event.details_json,
                                    process_name=f'{settings.process_name}:remote',  # hosting servier
                                    process_id=settings.process_id,  # hosting server
                                    exception_msg=None,
                                    exception_trace=None,
                                    )

    log_id = log_entry.create_log_event(session=session)    
    return PvfLogEventResult_One_Id(log_event_id=log_id)
