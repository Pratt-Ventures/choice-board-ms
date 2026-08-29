import json
from typing import Union, Any
import uuid
from pydantic import BaseModel
import numpy as np
import httpx

from sqlmodel import Field, select, desc
from fastapi import APIRouter,status, HTTPException, Request, Response, Depends

from ..pvf.bindings.pvf_services import (
    PvfCustomer,
    CustomerSelfRegUserInfoForm,
    CustomerUserCreateResult,
    SessionDep,
    PvfShareLink,
    PvfShareLinkMagicKey,
    PvfUserPasswordReset,
    make_activation_string,
)
from ..config.config_settings import settings

router = APIRouter()

class UserActivationTokenRequest(BaseModel):
    user_email: str

class UserActivationToken(BaseModel):
    activation_token: str

TEST_HELPER_PREFIX = '/test-helper'
TEST_ONLY = "Testing only. This endpoint is not registered in production."

@router.post(f'{TEST_HELPER_PREFIX}/get-user-activation-token', 
             summary="[Testing only — not in production] Retrieve a new user's activation token directly.",
             description=f"{TEST_ONLY} Returns an activation token for the given user email so tests can complete signup without email delivery.",
             tags=['test-helpers'])
def get_user_activation_token(session: SessionDep, user_activation_token_request: UserActivationTokenRequest) -> UserActivationToken:
    customer = session.exec(select(PvfCustomer).where(PvfCustomer.customer_email == user_activation_token_request.user_email)).one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="PvfUser not found")
    verify_token, token_payload = make_activation_string(customer_name=customer.customer_name, admin_name=customer.customer_name, customer_email=customer.customer_email)
    return UserActivationToken(activation_token=token_payload)

class ForgotPasswordTokenRequest(BaseModel):
    user_email: str

class ForgotPasswordToken(BaseModel):
    forgot_password_token: str

@router.post(f'{TEST_HELPER_PREFIX}/get-forgot-password-token',
             summary="[Testing only — not in production] Retrieve a user's forgot-password token directly.",
             description=f"{TEST_ONLY} Returns the latest forgot-password token for the given user email so tests can complete reset without email delivery.",
             tags=['test-helpers'])
def get_forgot_password_token(session: SessionDep, forgot_password_token_request: ForgotPasswordTokenRequest) -> ForgotPasswordToken:
    forgot_password_token = session.exec(select(PvfUserPasswordReset).where(PvfUserPasswordReset.email == forgot_password_token_request.user_email).order_by(desc(PvfUserPasswordReset.id))).one_or_none()
    if forgot_password_token is None:
        raise HTTPException(status_code=404, detail="PvfUser not found")
    return ForgotPasswordToken(forgot_password_token=forgot_password_token.token)


class ShareMagicKeyRequest(BaseModel):
    magic_token: str


class ShareMagicKeyResponse(BaseModel):
    access_magic_key: str
    share_id: int | None = None


@router.post(
    f'{TEST_HELPER_PREFIX}/get-latest-share-magic-key',
    summary="[Testing only — not in production] Retrieve the latest one-time share access key for a share magic token.",
    description=f"{TEST_ONLY} Returns the latest one-time share access key for a share magic token so e2e tests can complete share access without email delivery.",
    tags=['test-helpers'],
)
def get_latest_share_magic_key(
    session: SessionDep,
    request_body: ShareMagicKeyRequest,
) -> ShareMagicKeyResponse:
    link = session.exec(
        select(PvfShareLink).where(PvfShareLink.magic_token == request_body.magic_token)
    ).one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Share link not found")
    key_row = session.exec(
        select(PvfShareLinkMagicKey)
        .where(PvfShareLinkMagicKey.share_id == link.id)
        .order_by(desc(PvfShareLinkMagicKey.id))
    ).first()
    if key_row is None or not key_row.access_magic_key:
        raise HTTPException(status_code=404, detail="No magic key found for share")
    return ShareMagicKeyResponse(
        access_magic_key=key_row.access_magic_key,
        share_id=link.id,
    )


@router.post(f'{TEST_HELPER_PREFIX}/create-activated-user',
             summary="[Testing only — not in production] Create a new activated user with a given email and password.",
             description=f"{TEST_ONLY} Creates a user via signup and marks the customer activated so tests can log in without email delivery.",
             tags=['test-helpers'])
def create_activated_user(request: Request, response: Response,
                                session: SessionDep,
                                create_user_request: CustomerSelfRegUserInfoForm) -> CustomerUserCreateResult:
    with httpx.Client() as client:
        create_request_dump = create_user_request.model_dump()
        response = client.post("http://localhost:8000/auth-ws/initial-signup", json=create_request_dump)
        
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Failed to create user"))
    
    customer_info = PvfCustomer.get_customer_by_email_system(session=session, customer_email=create_user_request.admin_email, clear_lock=False)
    
    if customer_info is None:
        raise HTTPException(status_code=404, detail="PvfCustomer not found after creation")
    
    customer_info.customer_activated = True

    customer_info.update_customer_system(session=session)

    return CustomerUserCreateResult(
        failure_reason="",
        log_id=0,
        customer_id=customer_info.id if customer_info else None
    )
    
