"""External (customer toolkit) API access configuration and webhook event tables.

Framework-generic. Webhook event types are application vocabularies: the application
registers payload builders / readiness predicates per type on the PvfInvocation hooks
(see pvf.pvf_invocation.PvfHookRegistry); internally the type is a plain string.
`application_tag` is an opaque, application-defined tag on each key.
"""
from __future__ import annotations
from typing import Union, List
from datetime import datetime
from enum import Enum
import secrets
import uuid

from sqlmodel import SQLModel, Field, Session, select
from sqlalchemy import func, DateTime, Column
from sqlalchemy.dialects.postgresql import JSONB

from ...config.pvf_config_settings import pvf_settings as settings
from ..model_factory import extend_model_class, get_schema_extension_registry
from ...utils.pvf_base_internal_resources import PvfWsResultPackage
from ...utils.log_event import log_event
from ...utils.utils_general import get_hex_hash_from_args
from .customer_user import PvfUser, PvfUserContext


class PvfWebHookStatus(str, Enum):
    not_applicable = "not_applicable"
    waiting = "waiting"    # waiting for application-side readiness (see readiness predicates)
    pending = "pending"    # pending delivery to webhook endpoint
    trying = "trying"      # webhook endpoint deliver attempt in process in one watcher instance
    delivered = "delivered" # webhook endpoint delivered successfully
    failed = "failed"    # webhook endpoint delivery failed and will not be retried


class PvfApiAccessConfigurationSpec(SQLModel):
    __tablename__ = "pvf_apiaccessconfiguration"
    id: int | None = Field(default=None, primary_key=True, description="The primary key for the api access configuration; assigned by database")
    authentication_key_id: str | None = Field(default=None, index=True, unique=True, description="The authentication value used to authenticate exchanged messages; generated on create; target of <system_secret>+<supplied_key> hash for inbound requests; used with <system_secret>+<supplied_key> to generate hash for outbound requests")
    description: str | None = Field(default=None, description="Optional short description of the usage intended for the API key")
    active_status: bool = Field(default=True, description="If true, the key is active and can be used to access the API")

    customer_id: int | None = Field(default=None, index=True, description="customer account associated with this api access configuration")
    user_id: int | None = Field(default=None, description="user id associated with the collection entry, either originator or sends the original link if applicable; may be a FOREIGN user if created by invite link activation")

    shared_secret: str | None = Field(default=None, description="The secret value used to authenticate exchanged messages; generated on create.")

    application_tag: str = Field(index=True, unique=False, description="Opaque application-defined tag bound to this key; its meaning is defined by the application")
    webhook_endpoint: str | None = Field(default=None, description="The webhook endpoint to receive events; if not provided, no webhook events will be sent")

    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))

    def create_api_configuration_entry(self, session: Session, usr_context: PvfUserContext, clear_lock: bool=True) -> PvfApiAccessConfigurationResult_One:
        if (self.customer_id != usr_context.sess_user.customer_id or self.user_id != usr_context.sess_user.id):
            session.close()
            failure_reason = f"Security mismatch; attempting to add an access control entry with inconsistent customer/user information {self.customer_id}/{self.user_id}"
            log_id = log_event(failure_reason, severity=3, usr_context=usr_context)
            return PvfApiAccessConfigurationResult_One(failure_reason=failure_reason + f' ({log_id})', log_id=log_id)

        result = PvfApiAccessConfigurationResult_One()
        result.api_configuration_request_authentication = f'rq-{get_hex_hash_from_args(secrets.token_urlsafe(32), uuid.uuid4().hex.upper(), hash_length=32)}'
        self.authentication_key_id = f'ky-{get_hex_hash_from_args(settings.CUSTOMER_API_INBOUND_HASH_KEY, result.api_configuration_request_authentication, hash_length=32)}'
        result.api_callback_authentication = f'cb-{get_hex_hash_from_args(settings.CUSTOMER_API_OUTBOUND_HASH_KEY, self.authentication_key_id, hash_length=32)}'
        result.api_reciprocal_callback_key = f'cb-ky:ky-{get_hex_hash_from_args(settings.CUSTOMER_API_INBOUND_HASH_KEY, result.api_callback_authentication, hash_length=32)}'
        """
        For testing, callbacks may be routed to /api/api-check endpoint.
        The cb-ky:... value is returned as api_reciprocal_callback_key by the the create api access call that indicates what a key would receive this request signed with
        the same shared secret, even though a 'cb-...' value is supplied rather than the normal 'ky-'.
        A phantom entry would be manually set up in the database to allow processing of the callback
        for testing, using the cb-ky: value (cb-ky: removed) and the same shared secret and other properties for testing end-to-end.
        """
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        result.api_configuration_info = self
        return result

    def update_access_entry(self, session: Session, usr_context: PvfUserContext,
                                                        clear_lock: bool=True) -> PvfApiAccessConfigurationResult_One:
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        return PvfApiAccessConfigurationResult_One(api_configuration_info=self)


    @classmethod
    def get_access_list(cls, session: Session, usr_context: PvfUserContext, clear_lock: bool=True) -> PvfApiAccessConfigurationResult_Many:
        query = select(cls).where(
            cls.customer_id == usr_context.sess_user.customer_id,
            )
        access_list = session.exec(query).all()
        if clear_lock: session.close()
        return PvfApiAccessConfigurationResult_Many(api_configuration_list=access_list)

    @classmethod
    def get_access_entry_by_authentication_key_id(cls, session: Session, usr_context: PvfUserContext,
                                                        authentication_key_id: str,
                                                        clear_lock: bool=True) -> PvfApiAccessConfigurationResult_One:
        if usr_context.sess_customer is None:
            access_entry = session.exec(select(cls).where(cls.authentication_key_id == authentication_key_id).limit(1)).one_or_none()
        else:
            access_entry = session.exec(select(cls).where(cls.authentication_key_id == authentication_key_id, cls.customer_id == usr_context.sess_customer.id).limit(1)).one_or_none()
        log_id = None
        failure_reason = ''
        if access_entry is None:
            session.close()
            log_id = log_event(log_message=f'Api Access Configuration {authentication_key_id} NOT FOUND', severity=2, usr_context=usr_context)
            failure_reason = f'Access Configuration {authentication_key_id} not found'
        elif usr_context.sess_user is not None and access_entry.customer_id != usr_context.sess_user.customer_id:  # shouldn't happen per query
            session.close()
            log_id = log_event(log_message=f'Api Access Configuration {authentication_key_id} NOT ASSOCIATED WITH CUSTOMER {usr_context.sess_user.customer_id}', severity=3, usr_context=usr_context, access_entry_customer_id=access_entry.customer_id)
            failure_reason = f'Access Configuration {authentication_key_id} not found or not associated with this customer'
        if clear_lock: session.close()
        return PvfApiAccessConfigurationResult_One(failure_reason=failure_reason, log_id=log_id, api_configuration_info=access_entry)

    @classmethod
    def remove_access_entry_by_key(cls, session: Session, usr_context: PvfUserContext, authentication_key_id: str, clear_lock: bool=True) -> PvfApiAccessConfigurationResult_One_Id:
        existing_row = cls.get_access_entry_by_authentication_key_id(session=session, usr_context=usr_context, authentication_key_id=authentication_key_id, clear_lock=False)
        if existing_row.api_configuration_info is None or existing_row.failure_reason not in (None, ''):
            session.close()
            log_id = log_event(f"Existing Api Access Entry {authentication_key_id} not found on remove/delete request", usr_context=usr_context, severity=3, authentication_key_id=authentication_key_id)
            return PvfApiAccessConfigurationResult_One_Id(failure_reason='existing api access entry not found', log_id=log_id)
        save_id = existing_row.api_configuration_info.id
        session.delete(existing_row.api_configuration_info)
        session.commit()
        if clear_lock: session.close()
        return PvfApiAccessConfigurationResult_One_Id(api_configuration_id=save_id)


# The actual table class, built through the model factory so the application can add
# columns (see pvf.db.model_factory). No added columns registered -> plain table subclass.
PvfApiAccessConfiguration = extend_model_class(
    PvfApiAccessConfigurationSpec,
    get_schema_extension_registry().for_table("pvf_apiaccessconfiguration"),
)


class PvfApiWebInvocationEvent(SQLModel, table=True):
    __tablename__ = "pvf_apiwebinvocationevent"
    id: int | None = Field(default=None, primary_key=True, description="The primary key for the api access configuration; assigned by database")

    customer_id: int | None = Field(default=None, index=True, description="customer account associated with api access configuration")
    api_configuration_id: int | None = Field(default=None, index=True, description="The api configuration id associated with the event")
    authentication_key_id: str | None = Field(default=None, index=True, description="The authentication value used to authenticate exchanged messages; as matched value (not at received)")

    unique_tracking_id: str | None = Field(default=None, index=True, unique=True, description="The unique tracking id for the event; generated on create and provided in synchronous request result package")
    requesting_transaction_tag: str | None = Field(default=None, description="The tracking context optionally supplied with the request and echoed on callbacks")

    web_hook_type: str | None = Field(default=None, max_length=80, description="The type of webhook event (application-registered); used to determine the payload structure")
    payload_params_json: List | dict | None = Field(default=None, sa_column=Column(JSONB, default=None, nullable=True), description="Application-supplied parameters carried to the registered payload builder for this event")

    web_hook_status: PvfWebHookStatus | None = Field(default=None, description="Webhook request / callback status")
    web_hook_delivery_attempts: int = Field(default=0, description="The number of webhook delivery attempts")
    web_hook_failure_reason: str | None = Field(default=None, description="The reason for the last webhook delivery failure, if any")
    last_delivery_attempt_time: datetime | None = Field(default=None, description="The last time a webhook delivery was attempted")

    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))

    def create_web_invocation_event(self, session: Session, usr_context: PvfUserContext, clear_lock: bool=True) -> PvfApiWebInvocationResult_One:
        if (usr_context.sess_user is not None and self.customer_id != usr_context.sess_user.customer_id ):
            session.close()
            failure_reason = f"Security mismatch; attempting to add an access control entry with inconsistent customer/user information {self.customer_id}"
            log_id = log_event(failure_reason, severity=3, usr_context=usr_context)
            return PvfApiWebInvocationResult_One(failure_reason=failure_reason + f' ({log_id})', log_id=log_id)

        result = PvfApiWebInvocationResult_One()
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        result.api_event_info = self
        return result

    @staticmethod
    def enqueue_callback_event(session: Session,
                               usr_context: PvfUserContext,
                               api_config: PvfApiAccessConfiguration,
                               web_hook_type: str,
                               payload_params: list | dict | None = None,
                               requesting_transaction_tag: str | None = None,
                               clear_lock: bool = True) -> PvfApiWebInvocationResult_One:
        """Queue a webhook callback event for delivery by the watcher process.

        The application supplies the registered web_hook_type and any payload_params its
        payload builder needs; the watcher signs and delivers the built payload to the
        configuration's webhook_endpoint.
        """
        event = PvfApiWebInvocationEvent(
            customer_id=api_config.customer_id,
            api_configuration_id=api_config.id,
            authentication_key_id=api_config.authentication_key_id,
            unique_tracking_id=f'cbq-{uuid.uuid4().hex}',
            requesting_transaction_tag=requesting_transaction_tag,
            web_hook_type=web_hook_type,
            payload_params_json=payload_params,
            web_hook_status=PvfWebHookStatus.pending,
            web_hook_delivery_attempts=0,
        )
        return event.create_web_invocation_event(session=session, usr_context=usr_context, clear_lock=clear_lock)

    @classmethod
    def get_web_invocation_event_by_unique_tracking_id(cls, session: Session, usr_context: PvfUserContext,
                                                        unique_tracking_id: str,
                                                        clear_lock: bool=True) -> PvfApiWebInvocationResult_One:
        if usr_context.sess_customer is None:
            access_entry = session.exec(select(cls).where(cls.unique_tracking_id == unique_tracking_id).limit(1)).one_or_none()
        else:
            access_entry = session.exec(select(cls).where(cls.unique_tracking_id == unique_tracking_id).where(cls.customer_id == usr_context.sess_customer.id).limit(1)).one_or_none()
        log_id = None
        failure_reason = ''
        if access_entry is None:
            session.close()
            log_id = log_event(log_message=f'Api Access Event {unique_tracking_id} NOT FOUND', severity=2, usr_context=usr_context)
            failure_reason = f'Access Entry {unique_tracking_id} not found'
        elif usr_context.sess_customer is not None and access_entry.customer_id != usr_context.sess_customer.id:  # shouldn't happen per query
            session.close()
            log_id = log_event(log_message=f'Api Access Event {unique_tracking_id} NOT ASSOCIATED WITH CUSTOMER {usr_context.sess_customer.id}', severity=3, usr_context=usr_context, access_entry_customer_id=access_entry.customer_id)
            failure_reason = f'Access Entry {unique_tracking_id} not found or not associated with this customer'
        if clear_lock: session.close()
        return PvfApiWebInvocationResult_One(failure_reason=failure_reason, log_id=log_id, api_event_info=access_entry)

    @classmethod
    def set_web_invocation_event_status_by_unique_tracking_id(cls, session: Session,
                                                              usr_context: PvfUserContext,
                                                        unique_tracking_id: str,
                                                        new_status: PvfWebHookStatus,
                                                        web_hook_failure_reason: str | None = None,
                                                        clear_lock: bool=True) -> None:
        if usr_context.sess_customer is None:
            access_entry = session.exec(select(cls).where(cls.unique_tracking_id == unique_tracking_id).limit(1)).one_or_none()
        else:
            access_entry = session.exec(select(cls).where(cls.unique_tracking_id == unique_tracking_id).where(cls.customer_id == usr_context.sess_customer.id).limit(1)).one_or_none()

        if access_entry is not None:
            access_entry.web_hook_status = new_status
            access_entry.web_hook_failure_reason = web_hook_failure_reason if web_hook_failure_reason is not None else ''
            session.add(access_entry)
            session.commit()
            session.refresh(access_entry)
        else:
            log_event(f'Api Access Event {unique_tracking_id} NOT FOUND for status update in set_web_invocation_event_status_by_unique_tracking_id', severity=3, usr_context=usr_context)
            session.close()
        if clear_lock: session.close()
        return None


class PvfApiAccessConfigurationResult_One_Id(PvfWsResultPackage):
    api_configuration_id: Union[int, None] = None

class PvfApiAccessConfigurationResult_One(PvfWsResultPackage):
    api_configuration_request_authentication: str | None = Field(default=None, description="The api configuration key provided on a request (generated on initial creation, not stored")
    api_callback_authentication: str | None = Field(default=None, description="The api configuration key provided on a webhook result delivered to the requesting client webhook url")
    api_reciprocal_callback_key: str | None = Field(default=None, description="The api configuration key that would be a reciprocal handler for cb- signed messages (testing purposes only)")
    api_configuration_info: Union[PvfApiAccessConfiguration, None] = None

class PvfApiAccessConfigurationResult_Many(PvfWsResultPackage):
    api_configuration_list: Union[list[PvfApiAccessConfiguration], None] = None

class PvfApiAccessEventResult_One(PvfWsResultPackage):
    api_event_info: Union[PvfApiWebInvocationEvent, None] = None

class PvfApiWebInvocationResult_One(PvfWsResultPackage):
    api_event_info: Union[PvfApiWebInvocationEvent, None] = None
