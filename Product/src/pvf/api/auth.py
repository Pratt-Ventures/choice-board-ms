import os
from datetime import datetime, timedelta, timezone
from typing import Union, Any
from pydantic import BaseModel
import time

from sqlmodel import Field
from fastapi import APIRouter,status, HTTPException, Request, Response, Depends
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from ..utils.pvf_base_internal_resources import PvfTokenPayload, PvfTokenSchema, PvfAuthRelatedOutboundEmailType, PvfWsResultPackage
from ..depends.api_session_dependencies import SessionDep
from ..utils.utils_show import show_vars, show_vars_semi
from ..config.pvf_config_settings import pvf_settings as settings
from ..utils.auth_tokens import create_access_token
from ..utils.log_event import log_event
from ..utils.outbound_mail_queue import send_outbound_mail

from ..db.models.application_session_log import PvfUserSessionLog
from ..db.models.user_password_reset_tokens import PvfUserPasswordReset
#from ..db.models.bootstrap import UserModel
from ..db.models.customer_user import PvfUser as UserModel
from ..db.models.customer_user import PvfUserContext, PvfAccountStatus
from ..db.models.customer_user import PvfCustomer as CustomerModel

router = APIRouter()

class PvfLogin(BaseModel):
    email: str
    password: str
    two_factor_code: str | None = Field(default=None, description="Supplemental email login code when 2FA is required")

class PvfLogin2FAChallenge(PvfWsResultPackage):
    two_factor_required: bool = True
    message: str = "A supplemental login code has been sent to your email"
    validity_minutes: int = 10

# def auth(request: Request, session: SessionDep, login: PvfLogin):

anti_flooding_time: float = 0.0

@router.post("/login", 
             summary="Create access and refresh tokens for user session",
             tags=['auth'])
def auth_plain(response: Response, request: Request, session: SessionDep, login: PvfLogin):
    return auth_request(response=response, request=request, session=session, login=login, return_user_info=False)

# note: /login-and-get-context is composed by the application (it layers the pvf
# auth_request primitive under the application's context view); see app_context_views.

def _reject_login(response: Response, request: Request, login: PvfLogin, abort_code: str, user) -> None:
    global anti_flooding_time
    response.set_cookie("access_token", settings.CLEARED_TOKEN_VALUE, httponly=True,
                        max_age=180,
                        path="/", samesite="strict", secure=True)
    if time.time() - anti_flooding_time > 0.4:
        anti_flooding_time = time.time()
        log_event_id = log_event(f"Authorization attempt failed {login.email[:25]} : abort code {abort_code}",
                  severity=2,
                  user_id=user.id if user is not None else None,
                  customer_id=user.customer_id if user is not None else None,
                  remote_ip=request.client.host)
    else:
        log_event_id = -1
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        headers={"set-cookie": response.headers["set-cookie"]},
        detail=f"PvfLogin failed - {abort_code} - [{log_event_id}]")

def _complete_login(response: Response, request: Request, session: SessionDep, user, return_user_info: bool):
    user_session = PvfUserSessionLog(computer_name=settings.computer_name,
                                  process_name=settings.process_name,
                                  process_id=settings.process_id,
                                  customer_id=user.customer_id,
                                  user_id=user.id,
                                  remote_ip=request.client.host)
    user_session.create_user_session_entry(session=session)
    response.set_cookie("access_token", create_access_token(user.id), httponly=True,
                        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                        path="/", samesite="strict", secure=True)
    if return_user_info:
        return user
    return {"message": "PvfLogin successful",
            "expiration_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "user_id": user.id,
            "user_name": user.name}

def auth_request(response: Response, request: Request, session: SessionDep, login: PvfLogin, return_user_info: bool=False) -> Union[UserModel, dict, PvfLogin2FAChallenge]:
    from ..utils.login_2fa import (
        LOGIN_2FA_ALREADY_SENT_MESSAGE,
        LOGIN_2FA_CHALLENGE_MESSAGE,
        clear_login_2fa_code,
        issue_login_2fa_code,
        login_2fa_code_is_fresh,
        login_2fa_required,
        send_login_2fa_email,
        verify_login_2fa_code,
    )

    user = UserModel.get_user_by_email_system(session=session, email=login.email)
    abort_code = None
    cust = None

    generic_failure_status = "email/pw"
    if (user is None):
        if not settings.is_prod():  # outside prod, we give this specific info
            abort_code = "email"
        else:
            abort_code = generic_failure_status

    if abort_code is None and not user.verify_password(session=session, password=login.password):
        if not settings.is_prod():  # outside prod, we give this specific info
            abort_code = "pw"
        else:
            abort_code = generic_failure_status

    if abort_code is None and user.access_disabled not in (None, 0, False):
        abort_code = "disabled"

    if abort_code is None:
        cust = CustomerModel.get_customer_by_id_system(session=session, id=user.customer_id)
        if cust is None:
            abort_code = "customer not found"

    if abort_code is None and cust.account_status not in (PvfAccountStatus.active,):
        abort_code = "customer not active"

    if abort_code is None and cust.customer_activated is False:
        abort_code = "customer not activated"

    if abort_code is None and cust.trial_expiration_date is not None and cust.trial_expiration_date + timedelta(days=settings.APPLICATION_ACCOUNT_TRIAL_GRACE_PERIOD_DAYS) < datetime.now():
        abort_code = "customer trial expired"

    if abort_code is None and cust.service_expiration_date is not None and cust.service_expiration_date + timedelta(days=settings.APPLICATION_ACCOUNT_GRACE_PERIOD_DAYS) < datetime.now():
        abort_code = "customer service expired"

    if abort_code is None and login_2fa_required(user, cust):
        submitted_code = (login.two_factor_code or "").strip()
        if submitted_code:
            if verify_login_2fa_code(session, user, submitted_code):
                return _complete_login(response, request, session, user, return_user_info)
            abort_code = "2fa" if not settings.is_prod() else generic_failure_status
        else:
            response.set_cookie("access_token", settings.CLEARED_TOKEN_VALUE, httponly=True,
                                max_age=180,
                                path="/", samesite="strict", secure=True)
            challenge = PvfLogin2FAChallenge(
                message=LOGIN_2FA_CHALLENGE_MESSAGE,
                validity_minutes=settings.LOGIN_2FA_VALIDITY_MINUTES,
            )
            if login_2fa_code_is_fresh(session, user):
                challenge.message = LOGIN_2FA_ALREADY_SENT_MESSAGE
                return challenge
            code = issue_login_2fa_code(session, user)
            email_result = send_login_2fa_email(
                session,
                user=user,
                remote_ip=request.client.host,
                url_path=request.url.path,
                code=code,
            )
            # send_outbound_mail returns "" (sent), "queued:<id>" (queued), or error string (failed)
            if email_result and not (isinstance(email_result, str) and email_result.startswith("queued:")):
                clear_login_2fa_code(session, user)
                challenge.failure_reason = email_result
            return challenge

    if abort_code is None:
        return _complete_login(response, request, session, user, return_user_info)

    _reject_login(response, request, login, abort_code, user)

class ResetPasswordRequest(BaseModel):
    email: str

# def auth(request: Request, session: SessionDep, login: PvfLogin):

anti_pw_reset_flooding_times: dict[str,list[float, str]] = dict()

@router.post("/password-reset-request", 
             summary="A request to change password for an email; if present, send a change pw token to the email with 1 per N minute max",
             tags=['auth'])
def password_reset_request_wrapper(response: Response, request: Request, session: SessionDep, reset_pw: ResetPasswordRequest) -> str:
    return password_reset_request(response=response, request=request, session=session, reset_pw=reset_pw)

def password_reset_request(response: Response, request: Request, session: SessionDep, reset_pw: ResetPasswordRequest) -> str:
    global anti_pw_reset_flooding_times
    chg_user = UserModel.get_user_by_email_system(session=session, email=reset_pw.email)
    email_result = ""
    if chg_user is not None and chg_user.email in anti_pw_reset_flooding_times and anti_pw_reset_flooding_times[chg_user.email][0] > time.time() - settings.PW_RESET_FLOODING_LIMIT_SECONDS:
        if anti_pw_reset_flooding_times[chg_user.email][1] <= 1:
            log_event(f'pw change redundant password reset(s) ignored for {chg_user.email} - within {settings.PW_RESET_FLOODING_LIMIT_SECONDS//60} minutes', severity=2, 
                      usr_context=PvfUserContext(sess_user=chg_user, remote_ip=request.client.host, url_path=request.url.path))
        anti_pw_reset_flooding_times[chg_user.email][1] += 1
        chg_user = None
    if chg_user is not None:
        user_pw_reset = PvfUserPasswordReset.create_user_password_reset_system(session=session, email=chg_user.email)
        anti_pw_reset_flooding_times[chg_user.email] = [time.time(), 1]
        log_event(f'pw change token reset id ({user_pw_reset.id}) - {user_pw_reset.email} - request token generated', severity=1, 
                  usr_context=PvfUserContext(sess_user=chg_user, remote_ip=request.client.host, url_path=request.url.path))
        show_vars_semi(password_reset_request_email=chg_user.email, token=user_pw_reset.token)
        chg_usr_context = PvfUserContext(limited_proxy=True,
                                      remote_ip=request.client.host, url_path=request.url.path[:150], 
                                      sess_user=chg_user)
        chg_usr_context.sess_user.customer_admin = False   # reduce inadvertent escalation risks
        chg_usr_context.sess_user.power_user_mode = 0
        chg_usr_context.sess_user.system_user_mode = 0

        email_result = send_outbound_mail(session=session, usr_context=chg_usr_context, 
                                    destination_email=chg_user.email, 
                                    email_type=PvfAuthRelatedOutboundEmailType.password_reset,
                                    email_params=dict(user_email=chg_user.email, pw_token=user_pw_reset.token, 
                                                      pw_reset_url=f'{settings.APPLICATION_BASE_URL}/{settings.APP_RESET_PASSWORD_URL}/{user_pw_reset.token}'))
        # queued is not failure; map to "" for backward compat
        if isinstance(email_result, str) and email_result.startswith("queued:"):
            email_result = ""
        
    return email_result  # if we were trying to queue sending an email, we will report the issue here; since email matched and there is an issue

class ChangePasswordViaToken(BaseModel):
    email: str | None = Field(default=None, description="PvfUser Id (email) of user to change - optional, if supplied must match")
    token: str = Field(description="Token provided in forgot password request, emailed or texted to user; subject to repeat request limits, expiration, and no reuse constraints")
    new_password: str = Field(description="A new password requested for the user; should pass medium/strong tests, but not verified at server for strength")

@router.post("/change-password-via-token",
             summary="Attempt to change a user's password using a token supplied by the reset request",
             tags=['auth'])
def change_password_via_token_wrapper(response: Response, request: Request, session: SessionDep, change_pw: ChangePasswordViaToken) -> bool:
    return change_password_via_token(response=response, request=request, session=session, change_pw=change_pw)

def change_password_via_token(response: Response, request: Request, session: SessionDep, change_pw: ChangePasswordViaToken) -> bool:
    request_usr_context = PvfUserContext(remote_ip=request.client.host, url_path=request.url.path)
    user_pw_reset = PvfUserPasswordReset.get_user_password_reset_by_token_system(session=session, token=change_pw.token)
    result_flag = False
    if user_pw_reset is not None:
        pw_reset_age = (datetime.now(timezone.utc) - user_pw_reset.create_date.astimezone()).total_seconds()
        if user_pw_reset.token_used_date is not None:
            log_event(f'pw change token reset id ({user_pw_reset.id}) - {user_pw_reset.email} - previously used {user_pw_reset.token_used_date.strftime("%Y/%m/%d, %H:%M:%S")}', severity=2, 
                      usr_contextx=request_usr_context, cur_user_email=user_pw_reset.email)
            user_pw_reset = None
        elif pw_reset_age > settings.PW_RESET_TOKEN_VALID_SECONDS:
            log_event(f'pw change token reset id ({user_pw_reset.id}) - {user_pw_reset.email} - expired token', severity=2, 
                      usr_contextx=request_usr_context, cur_user_email=user_pw_reset.email)
            user_pw_reset = None
        elif change_pw.email not in (None, "") and change_pw.email != user_pw_reset.email:
            log_event(f'pw change token reset id ({user_pw_reset.id}) - {user_pw_reset.email} - supplied email mismatch {change_pw.email} is incorrect', severity=2, 
                      usr_contextx=request_usr_context, cur_user_email=user_pw_reset.email)
            user_pw_reset = None
        else:
            chg_user = UserModel.get_user_by_email_system(session=session, email=user_pw_reset.email)
            result_flag = chg_user.update_user_password_system(session=session, new_password=change_pw.new_password)
            user_pw_reset.set_token_used(session=session)
            if chg_user.customer_admin:
                customer = CustomerModel.get_customer_by_id_system(session=session, id=chg_user.customer_id, clear_lock=False)
                if customer.customer_activated is False:
                    customer.customer_activated = True
                    customer.update_customer_system(session=session)
                    log_event(f'PvfCustomer {customer.id} - "{customer.customer_name}" activated by admin password change {user_pw_reset.id} - {user_pw_reset.email}', severity=2, 
                              usr_context=request_usr_context, cur_user_email=user_pw_reset.email)
                else:
                    session.close()
                    log_event(f'pw change token reset id ({user_pw_reset.id}) - {user_pw_reset.email} - user password changed', severity=1, 
                              usr_context=request_usr_context, cur_user_email=user_pw_reset.email)
    return result_flag

@router.get("/logout", 
            summary="Logout the user and clear the access token",
            tags=['auth'])
def logout_wrapper(response: Response):
    return logout(response=response)

def logout(response: Response):
    response.set_cookie("access_token", settings.CLEARED_TOKEN_VALUE, httponly=True, 
                        expires='Thu, 01 Jan 1970 00:00:00 GMT',
                        path="/", samesite="strict", secure=True)
    return {"message": "Logout successful"}
