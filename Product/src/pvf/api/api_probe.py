"""External API connectivity probe — the canonical signed-header check endpoint.

Also the designated loopback target for reciprocal callback testing (see
PvfApiAccessConfiguration.create_api_configuration_entry).
"""
from typing import Any, Annotated

from fastapi import APIRouter, Header

from ..depends.api_session_dependencies import SessionDep
from ..depends.check_api_key_dependencies import WebServiceDep
from ..utils.log_event import log_event

router = APIRouter()


@router.post('/api-check',
             summary="Returns boolean of True when received. Captured request",
             description="Endpoint expects api-request-authentication matching rq- value and api-request-signature matching computed with secret key encoded as v1=auth-key, t=epoch time value; example: v1=67ee...8d5b,t=1783908806",
             tags=['access_check'])
def web_service_access_check(session: SessionDep, usr_context: WebServiceDep,
                                                 request_package: dict[str, Any],
                                                api_request_authentication: Annotated[str | None, Header()] = None,
                                                api_request_signature: Annotated[str | None, Header()] = None,
                                                 ) -> bool:
    log_event(f"API: Access check received", request_package=request_package,
              usr_context=usr_context, severity=0)
    return True
