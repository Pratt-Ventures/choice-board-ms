from typing import Union, Any, Annotated
from datetime import datetime
from pydantic import ValidationError
from jose import jwt

from sqlmodel import SQLModel, Field, Session, select, desc

from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer

from ..utils.pvf_base_internal_resources import PvfTokenPayload
from ..utils.log_event import log_event
from ..db.models.customer_user import PvfUser, PvfUserContext
from ..db.models.customer_user import PvfCustomer, PvfAccountStatus
from .api_session_dependencies import get_next_session

from ..db.models.api_access_configuration import PvfApiAccessConfiguration

from ..config.pvf_config_settings import pvf_settings as settings

from ..utils.utils_general import get_hex_hash_from_args
from ..utils.webcalls_and_hooks import Webrequest, SignatureVerificationError, APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY, APPLICATION_API_HEADER_SIGNATURE

reuseable_oauth = OAuth2PasswordBearer(
    tokenUrl="/auth",
    scheme_name="JWT"
)

# UserAccessDep = Annotated[PvfUserContext, Depends(get_current_user_deprecated)]

# async def get_current_user(request: Request, token: str = Depends(reuseable_oauth)) -> PvfUser:
async def get_api_key_info(request: Request, response: Response) -> PvfUserContext:
    usr_context = PvfUserContext(remote_ip=request.client.host, url_path=request.url.path)
    session = get_next_session()

    api_configuration_request_authentication = request.headers.get(APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY, None)
    if api_configuration_request_authentication is None and APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY.lower().startswith("x-"):
        api_configuration_request_authentication = request.headers.get(APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY[2:], None)

    api_signature = request.headers.get(APPLICATION_API_HEADER_SIGNATURE, None)
    if api_signature is None and APPLICATION_API_HEADER_SIGNATURE.lower().startswith("x-"):
        api_signature = request.headers.get(APPLICATION_API_HEADER_SIGNATURE[2:], None)
    
    if api_configuration_request_authentication in (None, '', 0) or api_signature in (None, '', 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"API configuration or signature not found",
        )

    api_config_request_key_value = f'ky-{get_hex_hash_from_args(settings.CUSTOMER_API_INBOUND_HASH_KEY, api_configuration_request_authentication, hash_length=32)}'

    api_access_config = PvfApiAccessConfiguration.get_access_entry_by_authentication_key_id(session=session, usr_context=usr_context, authentication_key_id=api_config_request_key_value)

    if api_access_config is None or api_access_config.failure_reason not in (None, ''):
        result_message = f"API configuration for {api_configuration_request_authentication}/{api_config_request_key_value} not found"
        log_id = log_event(result_message, usr_context=usr_context, severity=3)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result_message + f" ({log_id})",
        )

    user: Union[dict[str, Any], None] = PvfUser.get_user_by_id_system(session=session, id=api_access_config.api_configuration_info.user_id)

    if user is None:
        result_message = f"API configuration - associated user {api_access_config.api_configuration_info.user_id} not found for config {api_config_request_key_value}"
        log_id = log_event(result_message, usr_context=usr_context, severity=3)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result_message + f" ({log_id})",
        )

    if user.access_disabled not in (None, 0, False):
        result_message = f"API configuration - associated user {api_access_config.api_configuration_info.user_id} disabled for config {api_config_request_key_value}"
        log_id = log_event(result_message, usr_context=usr_context, severity=3)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result_message + f" ({log_id})",
        )

    if api_access_config.api_configuration_info.customer_id != user.customer_id:
        result_message = f"API configuration - associated user {api_access_config.api_configuration_info.user_id} inconsistent customer {user.customer_id} <> {api_access_config.api_configuration_info.customer_id} for config {api_config_request_key_value}"
        log_id = log_event(result_message, usr_context=usr_context, severity=3)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result_message + f" ({log_id})",
        )

    if api_access_config.api_configuration_info.active_status is False:
        result_message = f"API configuration - inactive for config {api_config_request_key_value}"
        log_id = log_event(result_message, usr_context=usr_context, severity=3)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result_message + f" ({log_id})",
        )
    
    cust = PvfCustomer.get_customer_by_id_system(session=session, id=api_access_config.api_configuration_info.customer_id)
    if cust is None:
        result_message = f"API configuration - associated customer {api_access_config.api_configuration_info.customer_id} not found for config {api_config_request_key_value}"
        log_id = log_event(result_message, usr_context=usr_context, severity=3)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result_message + f" ({log_id})",
        )


    if cust.account_status in (PvfAccountStatus.inactive, PvfAccountStatus.inactive.value) or not cust.customer_activated:
        result_message = f"API configuration - associated customer {api_access_config.api_configuration_info.customer_id} not active and/or activated for config {api_config_request_key_value}"
        log_id = log_event(result_message, usr_context=usr_context, severity=3)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result_message + f" ({log_id})",
        )

    usr_context.sess_user=user
    usr_context.sess_customer = cust
    usr_context.sess_api_access_config = api_access_config.api_configuration_info

    payload = await request.body()
    try:
        root_event = Webrequest.construct_event(
                payload, 
                api_signature, 
                api_access_config.api_configuration_info.shared_secret, 
                tolerance=settings.CUSTOMER_API_TIME_TOLERANCE,
                return_payload=False,
                api_config_id=api_config_request_key_value,
                test_environment=not settings.is_prod())
    except SignatureVerificationError as e:
        result_message = f"Webrequest signature check/verification failed for config {api_config_request_key_value} - {e}"
        log_id = log_event(result_message, usr_context=usr_context, severity=7)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result_message + f" ({log_id})",
        )

    usr_context.authenticated_session = True
    return usr_context


WebServiceDep = Annotated[PvfUserContext, Depends(get_api_key_info)]
