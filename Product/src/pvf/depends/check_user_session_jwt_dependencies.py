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
from ..config.pvf_config_settings import pvf_settings as settings
from ..utils.utils_general import get_hex_hash_from_args
from ..utils.webcalls_and_hooks import Webrequest, SignatureVerificationError, APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY, APPLICATION_API_HEADER_SIGNATURE

reuseable_oauth = OAuth2PasswordBearer(
    tokenUrl="/auth",
    scheme_name="JWT"
)

async def get_current_user_customer_admin(request: Request, response: Response) -> PvfUserContext:
    result = await get_current_user(request=request, response=response)
    if result.sess_user.customer_admin == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PvfUser is not a customer admin",
        )
    return result

async def get_current_user_system_admin(request: Request, response: Response) -> PvfUserContext:
    result = await get_current_user(request=request, response=response)
    if result.sess_user.system_user_mode < 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PvfUser is not a system admin",
        )
    return result

# async def get_current_user(request: Request, token: str = Depends(reuseable_oauth)) -> PvfUser:
async def get_current_user(request: Request, response: Response) -> PvfUserContext:
    usr_context = PvfUserContext(remote_ip=request.client.host, url_path=request.url.path)

    try:    
        token = request.cookies.get('access_token')
    except:
        token = None

    if token is None or token == settings.CLEARED_TOKEN_VALUE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token cookie not found - {token}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        token_data = PvfTokenPayload(**payload)

        if datetime.fromtimestamp(token_data.exp) < datetime.now():
            response.set_cookie("access_token", settings.CLEARED_TOKEN_VALUE, httponly=True, 
                            max_age=180,
                            path="/", samesite="strict", secure=False)
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except(jwt.JWTError, ValidationError):
        response.set_cookie("access_token", settings.CLEARED_TOKEN_VALUE, httponly=True, 
                            max_age=180,
                            path="/", samesite="strict", secure=False)
        log_id = log_event(f"JWT Token validation error for submitted token", usr_context=usr_context, severity=2)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session = get_next_session()
    user: Union[dict[str, Any], None] = PvfUser.get_user_by_id_system(session=session, id=int(token_data.sub))

    if user is None:
        response.set_cookie("access_token", settings.CLEARED_TOKEN_VALUE, httponly=True, 
                            max_age=180,
                            path="/", samesite="strict", secure=False)
        log_id = log_event(f"Could not find user {token_data.sub} for submitted token", user_id=token_data.sub, usr_context=usr_context, severity=2)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find user ({log_id})",
        )

    if user.access_disabled not in (None, 0, False):
        response.set_cookie("access_token", settings.CLEARED_TOKEN_VALUE, httponly=True, 
                            max_age=180,
                            path="/", samesite="strict", secure=False)
        log_id = log_event(f"PvfUser id {token_data.sub} is disabled for submitted token", usr_context=usr_context, user_id=token_data.sub, user_name=user.name, user_email=user.email, severity=2)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find user ({log_id})",
        )

    cust = PvfCustomer.get_customer_by_id_system(session=session, id=user.customer_id)
    if cust is None:
        response.set_cookie("access_token", settings.CLEARED_TOKEN_VALUE, httponly=True, 
                            max_age=180,
                            path="/", samesite="strict", secure=False)
        log_id = log_event(f"Could not find customer {user.customer_id} for user {user.id} based on submitted token",  usr_context=usr_context, user_id=token_data.sub, customer_id=user.customer_id, severity=3)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PvfCustomer not found for current user from token {log_id}",
        )

    if cust.account_status in (PvfAccountStatus.inactive, PvfAccountStatus.inactive.value) or not cust.customer_activated:
        response.set_cookie("access_token", settings.CLEARED_TOKEN_VALUE, httponly=True, 
                            max_age=180,
                            path="/", samesite="strict", secure=False)

        log_id = log_event(f"PvfCustomer is not active or activated {user.customer_id} for user {user.id} based on submitted token",  usr_context=usr_context, user_id=token_data.sub, customer_id=user.customer_id, severity=3)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PvfCustomer is not activated or currently active ({log_id})",
        )
    usr_context.sess_user=user
    usr_context.sess_customer = cust
    usr_context.authenticated_session = True
    return usr_context

UserAccessDep = Annotated[PvfUserContext, Depends(get_current_user)]
UserAccessDepCustomerAdmin = Annotated[PvfUserContext, Depends(get_current_user_customer_admin)]
UserAccessDepSystemAdmin = Annotated[PvfUserContext, Depends(get_current_user_system_admin)]


