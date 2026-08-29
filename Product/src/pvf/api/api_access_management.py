"""API key management (session UI API) — framework-generic CRUD for PvfApiAccessConfiguration."""
from pydantic import BaseModel
import secrets

from sqlmodel import Field
from fastapi import APIRouter

from ..depends.api_session_dependencies import SessionDep
from ..depends.check_user_session_jwt_dependencies import UserAccessDep
from ..utils.log_event import log_event
from ..db.models.api_access_configuration import (
    PvfApiAccessConfiguration,
    PvfApiAccessConfigurationResult_One_Id,
    PvfApiAccessConfigurationResult_One,
    PvfApiAccessConfigurationResult_Many,
)

router = APIRouter()

class CreateApiKeyConfigurationRequest(BaseModel):
    application_tag: str = Field(description="An application-defined tag bound to this key (meaning defined by the application)")
    description: str = Field(default="", description="Optional short description of the usage intended for the API key")
    active_status: bool = Field(default=True, description="Active status - entry is active if True, otherwise disabled for further inbound/outbound requests")
    webhook_endpoint: str | None = Field(default=None, description="The webhook endpoint to receive events")
    include_cb_test: bool = Field(default=False, description="If true, the reciprocal key is generated that for certain test endpoints - the 'ky-' value implied by the 'cb-' value used in callbacks; may requires manual admin update for use")

class ModifyApiKeyConfigurationRequest(BaseModel):
    authentication_key_id: str = Field(default=None, description="The api configuration key to modify")
    description: str | None = Field(default=None, description="Optional short description of the usage intended for the API key")
    active_status: bool | None = Field(default=None, description="Active status - entry is active if True, otherwise disabled for further inbound/outbound requests")
    webhook_endpoint: str | None = Field(default=None, description="The webhook endpoint to receive events")


class RemoveApiKeyConfigurationRequest(BaseModel):
    authentication_key_id: str = Field(description="The api configuration key to remove")


@router.post("/api-keys/create-api-access-configuration",
             summary="Creates a new api access configuration and key for this account",
             tags=['api-keys'])
def create_api_key_configuration(session: SessionDep, usr_context: UserAccessDep,
                              create_request: CreateApiKeyConfigurationRequest) -> PvfApiAccessConfigurationResult_One:
    if usr_context.sess_user.customer_admin is False:
        log_id = log_event("Only customer admin can create api access configurations", usr_context=usr_context, severity=3)
        return PvfApiAccessConfigurationResult_One_Id(log_id=log_id, failure_reason="Only customer admin can create api access configurations")

    new_access_configuration = PvfApiAccessConfiguration(
        description=create_request.description,
        active_status=True,
        customer_id=usr_context.sess_user.customer_id,
        application_tag=create_request.application_tag,
        user_id=usr_context.sess_user.id,
        shared_secret=f'ss-{secrets.token_urlsafe(32)}',
        webhook_endpoint=create_request.webhook_endpoint if create_request.webhook_endpoint is not None else '',
    )
    new_access_configuration_result = new_access_configuration.create_api_configuration_entry(session=session, usr_context=usr_context)
    if not create_request.include_cb_test:
        new_access_configuration_result.api_reciprocal_callback_key = None
    return new_access_configuration_result

@router.post("/api-keys/remove-api-access-configuration",
             summary="Remove an existing api access configuration association based on authentication_key_id",
             tags=['api-keys'])
def remove_api_key_configuration(session: SessionDep, usr_context: UserAccessDep, remove_request: RemoveApiKeyConfigurationRequest) -> PvfApiAccessConfigurationResult_One_Id:
    if usr_context.sess_user.customer_admin is False:
        log_id = log_event("Only customer admin can remove api access configurations", usr_context=usr_context, severity=3)
        return PvfApiAccessConfigurationResult_One_Id(log_id=log_id, failure_reason="Only customer admin can remove api access configurations")
    remove_membership_result = PvfApiAccessConfiguration.remove_access_entry_by_key(session=session,
                                                                                 usr_context=usr_context,
                                                                                 authentication_key_id=remove_request.authentication_key_id,
                                                                            )
    return remove_membership_result

@router.post("/api-keys/modify-api-access-configuration",
             summary="Modify an existing api access configuration association based on authentication_key_id",
             tags=['api-keys'])
def modify_api_key_configuration(session: SessionDep, usr_context: UserAccessDep, modify_request: ModifyApiKeyConfigurationRequest) -> PvfApiAccessConfigurationResult_One:
    if usr_context.sess_user.customer_admin is False:
        log_id = log_event("Only customer admin can modify api access configurations", usr_context=usr_context, severity=3)
        return PvfApiAccessConfigurationResult_One_Id(log_id=log_id, failure_reason="Only customer admin can modify api access configurations")

    modify_membership_result = PvfApiAccessConfiguration.get_access_entry_by_authentication_key_id(session=session,
                                                                                 usr_context=usr_context,
                                                                                 authentication_key_id=modify_request.authentication_key_id,
                                                                                 clear_lock=False,
                                                                            )
    if modify_membership_result.failure_reason not in ('', None):
        return modify_membership_result
    # copy any changed fields
    if modify_request.description is not None:
        modify_membership_result.api_configuration_info.description = modify_request.description
    if modify_request.active_status is not None:
        modify_membership_result.api_configuration_info.active_status = modify_request.active_status
    if modify_request.webhook_endpoint is not None:
        modify_membership_result.api_configuration_info.webhook_endpoint = modify_request.webhook_endpoint
    modify_membership_result.api_configuration_info.update_access_entry(session=session, usr_context=usr_context)
    return modify_membership_result

@router.post("/api-keys/get-api-access-configurations",
             summary="Retrieve all defined api access configurations for the current customer",
             tags=['api-keys'])
def get_api_access_configurations(session: SessionDep, usr_context: UserAccessDep) -> PvfApiAccessConfigurationResult_Many:
    return PvfApiAccessConfiguration.get_access_list(session=session, usr_context=usr_context)
