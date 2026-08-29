import traceback
from datetime import datetime
import json
from typing import Any

from ..db.models.application_event_log import PvfApplicationLogEvent
from ..config.pvf_config_settings import pvf_settings as settings
from .utils_show import show_vars_semi, print_hierarchy


def _coerce_details_json(details_json: dict | list | Any | None) -> dict | list | None:
    if details_json is None:
        return None
    if isinstance(details_json, (dict, list)):
        try:
            json.dumps(details_json)
            return details_json
        except Exception as json_ex_info:
            return [f"supplied dict/list failed json conversion - {json_ex_info}"]
    if isinstance(details_json, str):
        stripped = details_json.strip()
        if stripped[:1] in ("{", "["):
            try:
                loaded = json.loads(details_json)
                if isinstance(loaded, (dict, list)):
                    return loaded
            except Exception:
                pass
        return [details_json]
    json_ex_info = None
    try:
        dumped = details_json.model_dump(mode="json")
        if isinstance(dumped, (dict, list)):
            return dumped
    except Exception as ex_info:
        json_ex_info = ex_info
        dumped = None
    try:
        normalized = json.loads(json.dumps(details_json if dumped is None else dumped))
        if isinstance(normalized, (dict, list)):
            return normalized
        return [normalized]
    except Exception as ex_info:
        json_ex_info = ex_info
    return [f"supplied dict/list failed json conversion - {json_ex_info}"]

def log_event(log_message: str, *, 
              usr_context: any=None,
              # 0=debug, 1=info, 2=warning, 3=error, 4=critical, 5=crisis, 6=catostrophic, 7=apocalypse, 8=extinction-level-event, 9=universe-collapse
              severity: int=1,   
              ex_info: Exception=None,
              user_id: int=None,
              customer_id: int=None,
              api_config_key_id: str=None,
              remote_ip: str=None,
              url_path: str=None,
              customer_admin: bool=None,
              raise_exception: any=None,  # if not None, raise an exception, prefer passing on ex_info, then if raise_exception is an exception, then generic
              details_str: str | None=None,
              details_json: dict | list | Any | None=None,
              **kwds) -> int:
    
    from ..depends.api_session_dependencies import get_next_session

    if usr_context is not None:
        authenticated_session = usr_context.authenticated_session
        if usr_context.sess_user is not None:
            if user_id in (None, "", 0): user_id = usr_context.sess_user.id 
            if customer_id in (None, "", 0): customer_id = usr_context.sess_user.customer_id 
            if customer_admin in (None, ""): customer_admin = usr_context.sess_user.customer_admin
        if usr_context.sess_api_access_config is not None: api_config_key_id = usr_context.sess_api_access_config.authentication_key_id
        if remote_ip in (None, ""): remote_ip = usr_context.remote_ip
        if url_path in (None, ""): url_path = usr_context.url_path
    else:
        authenticated_session = False
    if ex_info is not None:
        exception_msg = f"{ex_info}"
        exception_trace = f"{traceback.format_tb(ex_info.__traceback__)}"
    else:
        exception_msg = ""
        exception_trace = ""

    details_json = _coerce_details_json(details_json)

    log_entry = PvfApplicationLogEvent(severity=severity,
                                    computer_name=f'{settings.environment_name}:{settings.computer_name}',
                                    process_name=settings.process_name,
                                    process_id=settings.process_id,
                                    authenticated_session=authenticated_session,
                                    customer_id=customer_id if customer_id is not None else -1,
                                    user_id=user_id if user_id is not None else -1,
                                    api_config_key_id=api_config_key_id if api_config_key_id is not None else '',
                                    customer_admin=customer_admin,
                                    remote_ip=remote_ip if remote_ip is not None else '',
                                    url_path=url_path if url_path is not None else '',
                                    exception_msg=exception_msg,
                                    exception_trace=exception_trace,
                                    log_message=log_message,
                                    details_str=details_str,
                                    details_json=details_json,
                                    kw_details='; '.join([f"{k}={v}" for k, v in kwds.items()])
                                    )
    log_id = -1
    if settings.is_prod() is False or severity not in (0,):
        # session = get_next_session()  # can't share parent sessions in case its a db problem or no session situation
        with get_next_session() as session:
            log_id = log_entry.create_log_event(session)

    # since 0 doesn't go to log in production, we do ensure output here so its not lost completely
    if not settings.is_prod() or severity not in (1,):
        if exception_msg != '':
            show_exception = f"Exception: {exception_msg}; "
        else:
            show_exception = ""
        cur_time = '{:%m-%d %H:%M}'.format(datetime.now())
        print(f"LOG EVENT ({log_id}) {cur_time}: Severity: {severity}; cust:{customer_id}; url_path:{url_path}; user:{user_id}; {show_exception}msg={log_message} ")

    if raise_exception not in (None, False):
        if isinstance(raise_exception, Exception):
            raise raise_exception
        elif ex_info is not None:
            raise ex_info
        else:
            raise Exception(f"Log entry {log_id} requested exception - {log_message}")
    return log_id

