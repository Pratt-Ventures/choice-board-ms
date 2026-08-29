from typing import Union, Any
from pydantic import BaseModel
import time
import numpy as np
import random
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter,status, HTTPException, Request, Response

from .request_types.auth import CustomerSelfRegUserInfoForm, CustomerUserCreateResult, CustomerUserInfoForm, DeleteUserForm, DeleteUserResult, SetUse2FAForm, SetUse2FAResult, UserInfoForm

from ..depends.api_session_dependencies import SessionDep
from ..depends.check_user_session_jwt_dependencies import UserAccessDep
from ..utils.auth_tokens import create_access_token
from ..config.pvf_config_settings import pvf_settings as settings
from ..db.models.customer_user import PvfUser as UserModel, PvfUserContext
from ..db.models.customer_user import PvfUserResult_One, PvfUserResult_Many, PvfUserResult_One_Id
from ..db.models.customer_user import PvfCustomer, PvfAccountStatus, PvfCustomerResult_One_Id, PvfCustomerResult_One

from ..utils.pvf_base_internal_resources import PvfWsResultPackage
from ..utils.pvf_base_internal_resources import PvfAuthRelatedOutboundEmailType as OutboundEmailType
from ..utils.outbound_mail_queue import send_outbound_mail
from ..utils.log_event import log_event
from ..utils.utils_general import parse_activation_string, make_activation_string
from ..utils.outbound_mail_queue import send_outbound_mail

router = APIRouter()

# Self-registration endpoints carry no authorization expectation; the runner includes
# this router in the no-auth application (mounted at /auth-ws).
noauth_router = APIRouter()

@router.post("/user/user-create",
             summary="Create a new user; must be customer_admin; must be in same customer",
             tags=['admin'])
def user_create(session: SessionDep, usr_context: UserAccessDep, new_user: UserInfoForm, send_welcome_email: bool=False) -> PvfUserResult_One:
    if usr_context.sess_user.customer_admin is False:
        log_event("Unauthorized attempt to create user", usr_context=usr_context, severity=3, 
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Unauthorized attempt to create user {str(new_user.email)[:50]}"))
    if new_user.id is not None and new_user.id > 0:
        log_event("Attempt to create user with existing id", usr_context=usr_context, severity=3, 
                  raise_exception=HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Attempt to create user with existing id {str(new_user.email)[:50]}"))
    else:
        new_user.id = None
        
    log_id = log_event("create_user", usr_context=usr_context, new_user_email=new_user.email, new_user_name=new_user.name, new_user_phone=new_user.phone, new_user_customer_admin=new_user.customer_admin)
    # get my user info and customer id
    # etc...
    # needs check for duplica
    # te email... IntegrityError
    power_mode = new_user.power_user_mode if new_user.power_user_mode is not None else 0
    if power_mode not in (0, 1, 2):
        power_mode = 0
    new_user_row = UserModel(
        customer_id=usr_context.sess_user.customer_id,
        name=new_user.name,
        email=new_user.email,
        phone=new_user.phone,
        customer_admin=new_user.customer_admin,
        power_user_mode=power_mode,
    )
    return_result = new_user_row.create_user(session=session, usr_context=usr_context, password=new_user.password)
    if return_result.failure_reason in (None,"") and send_welcome_email:
        new_user_row = return_result.user_info
        email_result = send_outbound_mail(session=session, 
                                                usr_context=usr_context,
                           email_type=OutboundEmailType.new_user_welcome,
                           destination_email=new_user_row.email,
                           email_params=dict(new_user_name=new_user_row.name,
                                             new_user_phone=new_user_row.phone,
                                             added_by_name=usr_context.sess_user.name,
                                             added_by_email=usr_context.sess_user.email,
                                            ))
        # nothing to do with email result, as it isn't an error indication of creation, but indicates no email was sent.
    return return_result

@router.post("/user/customer-create", 
             summary="Create a new customer and user; ",
             tags=['admin'])
def customer_create_admin(request: Request, session: SessionDep, usr_context: UserAccessDep, new_customer_user: CustomerUserInfoForm) -> CustomerUserCreateResult:
    if usr_context.sess_user.customer_admin is False or usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to create customer & user", usr_context=usr_context, severity=3, 
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Unauthorized attempt to create customer/user {new_customer_user.customer_email}"))
    if new_customer_user.customer_email in (None, "", "string"):
        new_customer_user.customer_email = new_customer_user.admin_email
    if new_customer_user.customer_phone in (None,"", "string"):
        new_customer_user.customer_phone = new_customer_user.admin_phone
    if new_customer_user.admin_email in (None, "", "string"):
        new_customer_user.admin_email = new_customer_user.customer_email

    new_customer = PvfCustomer(customer_name=new_customer_user.customer_name, 
                            account_status=new_customer_user.account_status, 
                            customer_activated=new_customer_user.customer_activated, 
                            customer_email=new_customer_user.customer_email, 
                            customer_phone=new_customer_user.customer_phone,
                            customer_account=f'No_account_set_{random.randint(1000000,9999999)}' if new_customer_user.assign_temporary_account else None,
                            )
    check_customer = PvfCustomer.get_customer_by_email_system(session=session, customer_email=new_customer_user.customer_email, clear_lock=True)
    if check_customer is not None:
        log_id = log_event(f"PvfCustomer with email {new_customer_user.customer_email} already exists", usr_context=usr_context, severity=3)
        return CustomerUserCreateResult(failure_reason="Create failed. This customer email is already associated with an account.", log_id=log_id)

    check_user = UserModel.get_user_by_email_system(session=session, email=new_customer_user.admin_email, clear_lock=True)
    if check_user is not None:
        log_id = log_event(f"PvfCustomer Admin/PvfUser with email {new_customer_user.admin_email} already exists", usr_context=usr_context, severity=3)
        return CustomerUserCreateResult(failure_reason="Create failed. This customer admin email is already associated with an active user.", log_id=log_id)

    new_customer = new_customer.create_customer_system(session=session, admin_name=new_customer_user.admin_name, 
                                                    admin_email=new_customer_user.admin_email, 
                                                    admin_phone=new_customer_user.admin_phone, 
                                                    power_user_mode=new_customer_user.admin_power_user, 
                                                    admin_password=new_customer_user.admin_password,
                                                    clear_lock=False)


    ext_usr_context = PvfUserContext(limited_proxy=True, remote_ip=request.client.host, url_path=request.url.path[:150],
                                  sess_customer=new_customer)

    session.close()

    log_id = log_event("create_customer_user", usr_context=usr_context, new_customer_email=new_customer_user.customer_email, new_admin_email=new_customer_user.admin_email)

    if new_customer_user.send_welcome_email:
        if new_customer.customer_activated is False:
            verify_token, token_payload = make_activation_string(customer_name=new_customer_user.customer_name, 
                                                                admin_name=new_customer_user.admin_name, 
                                                                customer_email=new_customer_user.admin_email,
                                                                )

            send_outbound_mail(session=session, usr_context=usr_context, email_type=OutboundEmailType.customer_activation_admin, 
                            destination_email=new_customer_user.admin_email,
                            email_params=dict(url_with_activation_code=f'{settings.APPLICATION_BASE_URL}/{settings.CUSTOMER_ACTIVATION_URL}/{token_payload}',
                                            token_payload=token_payload,
                                            new_customer_name=new_customer.customer_name,
                                            new_admin_name=new_customer_user.admin_name,
                                            new_customer_email=new_customer_user.admin_email,
                                            new_admin_email=new_customer_user.admin_email,
                                            new_admin_pw=new_customer_user.admin_password,
                                            ))
        else:
            send_outbound_mail(session=session, usr_context=usr_context, email_type=OutboundEmailType.customer_activation_admin_activated, 
                            destination_email=new_customer_user.admin_email,
                            email_params=dict(url=f'{settings.APPLICATION_BASE_URL}',
                                            new_customer_name=new_customer.customer_name,
                                            new_admin_name=new_customer_user.admin_name,
                                            new_customer_email=new_customer_user.admin_email,
                                            new_admin_email=new_customer_user.admin_email,
                                            new_admin_pw=new_customer_user.admin_password,
                                            ))

    return CustomerUserCreateResult(customer_id=new_customer.id)

@noauth_router.post("/initial-signup",
             summary="Self registration - create a new customer and user account simultaneously; ",
             tags=['self-reg'])
def customer_create_wrapper(response: Response, request: Request, session: SessionDep, 
                          new_customer_user: CustomerSelfRegUserInfoForm) -> CustomerUserCreateResult:
    return customer_create_self(response=response, request=request, session=session, new_customer_user=new_customer_user)


def customer_create_self(response: Response, request: Request, session: SessionDep, 
                          new_customer_user: CustomerSelfRegUserInfoForm) -> CustomerUserCreateResult:
    ext_usr_context = PvfUserContext(limited_proxy=True, remote_ip=request.client.host, url_path=request.url.path[:150])
    # for testing, enable this to force a trial code not provided by the client.
    # new_customer_user.trial_activation_code = 'trial_account_30_days'

    existing_customer = PvfCustomer.get_customer_by_email_system(session=session, customer_email=new_customer_user.admin_email)
    if existing_customer is not None:
        log_id = log_event(f"PvfCustomer email {new_customer_user.admin_email} already exists on self signup request",
                            usr_context=ext_usr_context,
                           customer_email=new_customer_user.admin_email)
        return CustomerUserCreateResult(failure_reason="This email is already associated with an account. Please try signing in.", log_id=log_id)

    existing_user = UserModel.get_user_by_email_system(session=session, email=new_customer_user.admin_email)
    if existing_user is not None:
        log_id = log_event(f"USER email {new_customer_user.admin_email} already exists on self signup request",
                            usr_context=ext_usr_context,
                           customer_email=new_customer_user.admin_email)
        return CustomerUserCreateResult(failure_reason="This email is already associated with an account. Please try signing in.", log_id=log_id)

    referral_customer_id = None
    if new_customer_user.trial_activation_code not in (None, ""):
        new_customer_user.trial_activation_code = new_customer_user.trial_activation_code.strip().lower()
        if new_customer_user.trial_activation_code.lower() not in settings.TRIAL_ACCOUNT_CODES:
            log_id = log_event(f"Unrecognized trial activation code {new_customer_user.trial_activation_code} on customer create request", usr_context=ext_usr_context, severity=3)
            return CustomerUserCreateResult(failure_reason="Create failed. This trial activation code is not recognized in self registration.", log_id=log_id)
        trial_expiration_days = settings.TRIAL_ACCOUNT_CODES[new_customer_user.trial_activation_code]
        trial_expiration_date = datetime.now(timezone.utc) + timedelta(days=trial_expiration_days)
    else:
        new_customer_user.trial_activation_code = None
        trial_expiration_date = None
        trial_expiration_days = -1

    new_customer = PvfCustomer(customer_name=new_customer_user.customer_name, 
                            account_status=PvfAccountStatus.active, 
                            customer_email=new_customer_user.admin_email, 
                            customer_phone=new_customer_user.admin_phone,
                            invitation_from_customer_id=referral_customer_id,
                            trial_activation_code=new_customer_user.trial_activation_code,
                            trial_expiration_date=trial_expiration_date,
                            )
    
    new_customer = new_customer.create_customer_system(session=session, 
                                                       admin_name=new_customer_user.admin_name, 
                                                    admin_email=new_customer_user.admin_email, 
                                                    admin_phone=new_customer_user.admin_phone, 
                                                    power_user_mode=0, 
                                                    admin_password=new_customer_user.admin_password,
                                                    clear_lock=False)
    ext_usr_context.sess_customer = new_customer

    log_id = log_event("create_customer_user (self)", 
                            usr_context=ext_usr_context,
                       new_customer_email=new_customer_user.admin_email, 
                       trial_info=f'Granted {trial_expiration_days} day(s) promotional trial for trial activation code {new_customer_user.trial_activation_code}.' if trial_expiration_days not in (None, -1, 0) else None)

    verify_token, token_payload = make_activation_string(customer_name=new_customer_user.customer_name, 
                                                         admin_name=new_customer_user.admin_name, 
                                                         customer_email=new_customer_user.admin_email,
                                                         )

    send_outbound_mail(session=session, usr_context=ext_usr_context, email_type=OutboundEmailType.customer_activation_self, 
                       destination_email=new_customer_user.admin_email,
                    email_params=dict(url_with_activation_code=f'{settings.APPLICATION_BASE_URL}/{settings.CUSTOMER_ACTIVATION_URL}/{token_payload}',
                                    token_payload=token_payload,
                                    new_customer_name=new_customer.customer_name,
                                    new_admin_name=new_customer_user.admin_name,
                                    new_customer_email=new_customer_user.admin_email,
                                    new_admin_email=new_customer_user.admin_email,
                                    ))

    new_customer_id = new_customer.id
    
    session.close()
    return CustomerUserCreateResult(customer_id=new_customer_id)

@noauth_router.get("/signup-confirm/{activation_code}",
             summary="Self registration - phase 2 - customer activations email link with activation code",
             tags=['self-reg'])
def signup_confirm_activation_wrapper(response: Response, request: Request, session: SessionDep, activation_code) -> PvfCustomerResult_One_Id:
    return signup_confirm_activation(response=response, request=request, session=session, activation_code=activation_code)

def signup_confirm_activation(response: Response, request: Request, session: SessionDep, activation_code) -> PvfCustomerResult_One_Id:
    ext_usr_context = PvfUserContext(limited_proxy=True, remote_ip=request.client.host, url_path=request.url.path[:150])

    received_token, customer_name, admin_name, customer_email, expiration_time, make_strings_better = parse_activation_string(activation_code=activation_code)
    verify_token, token_payload = make_activation_string(customer_name=customer_name, admin_name=admin_name, customer_email=customer_email, expiration_time=expiration_time, make_strings_better=make_strings_better)
    if verify_token != received_token:
        log_id = log_event("Activation token does not match expected value in signup-confirm", severity=4, 
                            usr_context=ext_usr_context,
                           received_token=received_token, verify_token=verify_token, 
                           raise_exception=True)
        
    customer_info = PvfCustomer.get_customer_by_email_system(session=session, customer_email=customer_email, clear_lock=False)
    if customer_info is None:
        log_id = log_event("PvfCustomer information not found in signup-confirm", severity=4, 
                            usr_context=ext_usr_context,
                           customer_email=customer_email, admin_email=customer_email,
                           raise_exception=True)

    if customer_info.account_status not in (PvfAccountStatus.active,):
        log_id = log_event("PvfCustomer entity is not marked active in signup-confirm", severity=4, 
                            usr_context=ext_usr_context,
                           customer_id=customer_info.id,
                           customer_email=customer_email, admin_email=customer_email,
                           raise_exception=True)

    if customer_info.customer_activated:
        log_id = log_event(f"PvfCustomer with email {customer_email} was previously activated", severity=3, 
                            usr_context=ext_usr_context,
                           customer_id=customer_info.id,
                           customer_email=customer_email, 
                           )
        return PvfCustomerResult_One_Id(failure_reason="It looks like you've already activated your account. Please sign in instead.", log_id=log_id)

    if expiration_time in (None, 0, 0.0, "") or expiration_time < time.time():
        log_id = log_event("Received activation token has expired in signup-confirm - requesting new activation email", severity=3, 
                            usr_context=ext_usr_context,
                           past_due_seconds = time.time() - expiration_time,
                           customer_id=customer_info.id,
                           customer_email=customer_email, 
                           )

        verify_token, token_payload = make_activation_string(customer_name=customer_name, admin_name=admin_name, customer_email=customer_email)

        send_outbound_mail(session=session, usr_context=ext_usr_context, email_type=OutboundEmailType.customer_activation, 
                        destination_email=customer_email,
                        email_params=dict(url_with_activation_code=f'{settings.APPLICATION_BASE_URL}/{settings.CUSTOMER_ACTIVATION_URL}/{token_payload}',
                                        token_payload=token_payload,
                                        customer_id=customer_info.id,
                                        new_customer_name=customer_name,
                                        new_admin_name=admin_name,
                                        new_customer_email=customer_email,
                                        new_admin_email=customer_email,
                                        ))

        return PvfCustomerResult_One_Id(failure_reason="Your activation email has expired. We've sent a new activation email, please check your inbox.", log_id=log_id)

    customer_info.customer_activated = True
    customer_info.update_customer_system(session=session)

    log_event("PvfCustomer activated", severity=1, 
                usr_context=ext_usr_context,
                customer_id=customer_info.id,
              customer_email=customer_email, admin_email=customer_email)

    user_info = UserModel.get_user_by_email_system(session=session, email=customer_email)
    if user_info is None:
        log_id = log_event(f"Activated customer has unknown initial administrator {customer_email}", severity=4, 
                            usr_context=ext_usr_context,
                            customer_id=customer_info.id,
                            customer_email=customer_email, 
                            admin_email=customer_email,
                            raise_exception=True)

    response.set_cookie("access_token", create_access_token(user_info.id), httponly=True, 
                    max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    path="/", samesite="strict", secure=True)

    return PvfCustomerResult_One_Id(customer_id=customer_info.id)


@router.get('/user/user-get-by-id', 
            summary='Return user information by internal user id (for admin purposes)',
            tags=['admin'])
def get_user_info_by_id(session: SessionDep, usr_context: UserAccessDep, retrieve_by_id:int) -> PvfUserResult_One:
    return UserModel.get_user_by_id(session=session, usr_context=usr_context, id=retrieve_by_id)

@router.get('/user/user-get-by-email', 
            summary='Return user information by internal user email (for admin purposes)',
            tags=['admin'])
def get_user_info_by_email(session: SessionDep, usr_context: UserAccessDep, retrieve_by_email:str) -> PvfUserResult_One:
    return UserModel.get_user_by_email(session=session, usr_context=usr_context, email=retrieve_by_email)

@router.get('/user-all-account-users', 
            summary='Return user information for all users in the current account (for my-team and admin purposes)',
            tags=['context'])
def get_all_account_users(session: SessionDep, usr_context: UserAccessDep) -> PvfUserResult_Many:
    return UserModel.get_account_users(session=session, usr_context=usr_context)

@router.get('/user-all-account-admins', 
            summary='Return user information for all admin users in the current account (for my-team and admin purposes)',
            tags=['context'])
def get_account_admin_users(session: SessionDep, usr_context: UserAccessDep) -> PvfUserResult_Many:
    return UserModel.get_account_admins(session=session, usr_context=usr_context)

@router.post("/user-update", 
             summary="Modify a user; must be self or customer_admin in same customer",
             tags=['admin'])
def update_user_info(session: SessionDep, usr_context: UserAccessDep, update_user: UserInfoForm) -> PvfUserResult_One_Id:
    if update_user.id is not None:
        check_result = UserModel.get_user_by_id(session=session, id=update_user.id, usr_context=usr_context)  
    else:
        check_result = UserModel.get_user_by_email(session=session, email=update_user.email, usr_context=usr_context)  

    if check_result.failure_reason or check_result.user_info is None:
        return PvfUserResult_One_Id(failure_reason=check_result.failure_reason, log_id=check_result.log_id, user_id=-1)
    if update_user.id is None:
        update_user.id = check_result.user_info.id

    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.id != update_user.id:
        log_event("Unauthorized attempt to update user", usr_context=usr_context, severity=3, 
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Unauthorized attempt to create user {update_user.email}"))
    if usr_context.sess_user.customer_admin is False and update_user.customer_admin:
        log_event("Unauthorized attempt to convert user to admin", usr_context=usr_context, severity=3, 
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Unauthorized attempt to convert user to admin {update_user.email}"))
    if update_user.power_user_mode is not None and usr_context.sess_user.customer_admin is False:
        log_event("Unauthorized attempt to change power user mode", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized attempt to change power user mode"))
    update_dict = update_user.model_dump(mode='dict')
    update_dict['customer_id'] = usr_context.sess_user.customer_id
    # PvfCustomer admins may set power_user_mode only; system_user_mode is never client-writable here.
    update_dict.pop('system_user_mode', None)
    update_dict.pop('use_2fa', None)
    if usr_context.sess_user.customer_admin is False:
        update_dict.pop('power_user_mode', None)
        update_dict.pop('customer_admin', None)
    if 'password' in update_dict:
        new_password = update_dict.pop('password')
        new_password = None if new_password in (None, '') else new_password
    else:
        new_password = None
        
    update_user_row = check_result.user_info

    for key, value in update_dict.items():
        if value is not None:
            setattr(update_user_row, key, value)
        
    update_user_result = update_user_row.update_user(session=session, usr_context=usr_context, new_password=new_password)
    return PvfUserResult_One_Id(failure_reason=update_user_result.failure_reason, log_id=update_user_result.log_id, user_id=update_user_result.user_info.id if update_user_result.user_info else None)

@router.post(
    "/user/set-use-2fa",
    summary="Enable or disable email 2FA for the current user",
    tags=["auth"],
)
def set_user_use_2fa(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: SetUse2FAForm,
) -> SetUse2FAResult:
    from ..utils.login_2fa import login_2fa_optional

    customer = usr_context.sess_customer
    if customer is None:
        customer = PvfCustomer.get_customer_by_id_system(
            session=session, id=usr_context.sess_user.customer_id, clear_lock=False
        )
    if customer is None:
        return SetUse2FAResult(failure_reason="PvfCustomer not found")
    if not login_2fa_optional(usr_context.sess_user, customer):
        log_id = log_event(
            "PvfUser 2FA change denied",
            usr_context=usr_context,
            severity=3,
        )
        return SetUse2FAResult(failure_reason="Two-factor authentication is not optional for this account", log_id=log_id)
    user_row = UserModel.get_user_by_id_system(session=session, id=usr_context.sess_user.id, clear_lock=False)
    prior = bool(user_row.use_2fa)
    new_state = bool(form.enabled)
    if prior != new_state:
        user_row.use_2fa = new_state
        session.add(user_row)
        session.commit()
        session.refresh(user_row)
    return SetUse2FAResult(prior=prior, new=bool(user_row.use_2fa), use_2fa=bool(user_row.use_2fa))

@router.post(
    "/customer/set-use-2fa",
    summary="Enable or disable email 2FA for all users of the current customer",
    tags=["auth"],
)
def set_customer_use_2fa(
    session: SessionDep,
    usr_context: UserAccessDep,
    form: SetUse2FAForm,
) -> SetUse2FAResult:
    from ..utils.login_2fa import login_2fa_customer_controllable

    if not login_2fa_customer_controllable(usr_context.sess_user):
        log_id = log_event(
            "PvfCustomer 2FA change denied",
            usr_context=usr_context,
            severity=3,
        )
        return SetUse2FAResult(failure_reason="PvfCustomer admin access required to change workspace 2FA", log_id=log_id)
    customer = usr_context.sess_customer
    if customer is None:
        customer = PvfCustomer.get_customer_by_id_system(
            session=session, id=usr_context.sess_user.customer_id, clear_lock=False
        )
    if customer is None:
        return SetUse2FAResult(failure_reason="PvfCustomer not found")
    prior = bool(customer.use_2fa)
    new_state = bool(form.enabled)
    if prior != new_state:
        customer.use_2fa = new_state
        customer.update_customer_system(session=session, clear_lock=False)
        log_event(
            "PvfCustomer 2FA setting changed",
            severity=1,
            usr_context=usr_context,
            details_json={"prior": prior, "new": new_state, "customer_id": customer.id},
        )
    return SetUse2FAResult(prior=prior, new=bool(customer.use_2fa), use_2fa=bool(customer.use_2fa))

@router.delete("/user/delete-user", 
             summary="Delete a user; must be self or customer_admin in same customer",
             tags=['admin'])
def delete_user(session: SessionDep, usr_context: UserAccessDep, delete_user_form: DeleteUserForm) -> PvfUserResult_One_Id:
    if delete_user_form.user_id is not None:
        check_result = UserModel.get_user_by_id(session=session, id=delete_user_form.user_id, usr_context=usr_context)  
    else:
        check_result = UserModel.get_user_by_email(session=session, email=delete_user_form.email, usr_context=usr_context)  

    if check_result.failure_reason or check_result.user_info is None:
        return PvfUserResult_One_Id(failure_reason=check_result.failure_reason, log_id=check_result.log_id, user_id=-1)
    if delete_user_form.user_id is None:
        delete_user_form.user_id = check_result.user_info.id

    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.id != delete_user_form.user_id:
        log_event("Unauthorized attempt to update user", usr_context=usr_context, severity=3, 
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Unauthorized attempt to create user {delete_user_form.email}"))
    if usr_context.sess_user.customer_admin is False and delete_user_form.customer_admin:
        log_event("Unauthorized attempt to convert user to admin", usr_context=usr_context, severity=3, 
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Unauthorized attempt to convert user to admin {delete_user_form.email}"))
        
    delete_user_row = check_result.user_info
    delete_user_result = delete_user_row.delete_user_system(session=session, usr_context=usr_context)
    return DeleteUserResult(failure_reason=delete_user_result.failure_reason, log_id=delete_user_result.log_id, user_id=delete_user_result.user_id if delete_user_result.user_id else None)

@router.get('/user/user-my-info', 
            summary='Return user information for currently authenticated user session',
            tags=['dev'])
def get_me(usr_context: UserAccessDep) -> PvfUserResult_One:
    return PvfUserResult_One(failure_reason="", user_info=usr_context.sess_user)
