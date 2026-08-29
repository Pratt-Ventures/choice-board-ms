"""Share link tracking tables (framework-generic).

Share types (object actions) and access operations are application vocabularies,
supplied via pvf_app_startup.yaml and injected into pvf settings as plain string
lists. Applications may define enums for clarity at their own boundary; internally
the share link support works with lists of strings.

Application-specific entity validation/naming is provided by the entity_resolver
hook registered on the PvfInvocation (see pvf.pvf_invocation.PvfHookRegistry).
"""
from __future__ import annotations
from typing import Union, List
from datetime import datetime, timedelta, timezone
from enum import Enum
import uuid
import base64

from sqlmodel import SQLModel, Field, Session, select
from sqlalchemy import func, DateTime, Column
from sqlalchemy.dialects.postgresql import JSONB
from fastapi import status, HTTPException

from .customer_user import PvfUserContext
from ..model_factory import extend_model_class, get_schema_extension_registry
from ...config.pvf_config_settings import pvf_settings as settings
from ...utils.pvf_base_internal_resources import PvfWsResultPackage
from ...utils.log_event import log_event
from ...utils.utils_general import get_hex_hash_from_args
from ...utils.pvf_base_internal_resources import get_random_baseN_value
from ...bindings.pvf_invocation import get_hooks


class PvfShareLinkResult_One_Id(PvfWsResultPackage):
    link_id: Union[int, None] = None

class PvfShareLinkResult_One(PvfWsResultPackage):
    link_info: Union[PvfShareLink, None] = None

class PvfShareLinkResult_Many(PvfWsResultPackage):
    link_info_list: Union[list[PvfShareLink], None] = None


def get_share_object_actions() -> list[str]:
    """Share types the application supports (from pvf_app_startup.yaml)."""
    return list(settings.SHARE_OBJECT_ACTIONS or [])


def get_share_access_operations() -> list[str]:
    """Operations journalable against a share (from pvf_app_startup.yaml)."""
    return list(settings.SHARE_ACCESS_OPERATIONS or [])


class PvfShareAccessCheckMode(str, Enum):
    open_access = 'open_access'                     # Access Url; Access granted (no input required); Name optional.
    email_any_unverified = 'email_any_unverified'   # Access Url; Enter Name & Any Email (not verified); Access Granted.
    email_any_verified = 'email_any_verified'       # Access Url; Enter Name & Any Email; Token email sent; Follow link or enter key from token email; Access Granted.
    email_matching = 'email_matching'               # Access Url; Enter Name & Email; Email must match share; Access Granted.
    email_matching_verified = 'email_matching_verified'   # Access Url; Enter Name & Email; Email must match share; Token email sent; Use link or key to verify; Access Granted.
    recipient_email_verified = 'recipient_email_verified' # Access Url; Enter Name Only; key goes to the email on file; Use link or key to verify; Access Granted.
    password_only = 'password_only'                        # Access Url; Enter Name Only; Password required from share; Access Granted.
    password_with_email_any_unverified = 'password_with_email_any_unverified'   # Access Url; Enter Name & Any Email (not verified); Password required from share; Access Granted.
    password_with_email_any_verified = 'password_with_email_any_verified'       # Access Url; Enter Name & Any Email (verified); Password required from share; Token email sent; Use link or key to verify; Access Granted.
    password_with_email_matching = 'password_with_email_matching'          # Access Url; Enter Name & Email; Email must match share; Password required from share; Access Granted.
    password_with_email_matching_verified = 'password_with_email_matching_verified'   # Access Url; Enter Name & Email; Email must match share; Password required from share; Token email sent; Use link or key to verify; Access Granted.
    password_with_recipient_email_verified = 'password_with_recipient_email_verified' # Access Url; Enter Name Only; Password required from share; key goes to the email on file; Use link or key to verify; Access Granted.
    not_specified = 'not_specified'

class PvfShareLinkBase(SQLModel, title="PvfShareLink fields used in requests"):
    shared_type: str = Field(default="not_set", description="The share's access or intent within the referenced entity; one of the application's configured share object actions", max_length=50)

    shared_entity_db_id: int = Field(index=True, description="Identifies the referenced entity by its primary database id")

    link_auto_send: bool = Field(default=False, description="If True, the link is sent using a stored template and information on the requesting user, specified email, and target resource")
    shared_with_company_name: str | None = Field(default=None, description="Company name or organization the link was shared with")
    shared_with_person_name: str | None = Field(default=None, description="Person name the link was shared with")
    shared_with_email: str | None = Field(default=None, description="Email of Organization or Person(s) the link was shared with")
    share_link_name: str | None = Field(default=None, description="The name of the link/entity for recognition on the recipients side; defaults to target name if not specified")

    share_link_expiration: int = Field(default=settings.SHARE_LINK_EXPIRATION_DAYS, description="Indicates how many days the share link is valid from initial generation, regardless of user verification (if any); -1 for no limit")
    access_mode: PvfShareAccessCheckMode = Field(default=PvfShareAccessCheckMode.not_specified, description="Access checks for share recipient")
    share_password: str | None = Field(default=None, description="Specific password required to access the link, often provided separately; required in addition to email verification if specified")
    share_password_in_email: bool = Field(default=False, description="If true, and link_auto_send is enabled, the password will be included in settings for the outbound email")
    cookie_duration: int = Field(default=settings.SHARE_LINK_COOKIE_EXPIRATION_DAYS, description="Cookie valid duration in days from grant; -1 for long-lived, 0 uses the server default")
    share_actions: List[str] | None = Field(default=None,
                                            description="The actions possible on this share (from the application's configured access operations); defaults from the registered action matrix for the share type")


class PvfShareLinkSpec(PvfShareLinkBase):
    __tablename__ = "pvf_sharelink"
    id: int | None = Field(default=None, primary_key=True, description="Generated internal id for the share; automatically assigned at creation")
    magic_token: str | None = Field(default=None, index=True, unique=True, description="Generated magic token that uniquely identifies the share event and the shared resources and access mode")

    customer_id: int | None = Field(default=None, index=True, description="customer account that owns the shared entity")
    user_id: int | None = Field(default=None, description="user id of the originator who created the share link")

    share_actions: List[str] | None = Field(default=None, sa_column=Column(JSONB, default=None, nullable=True))

    share_link_enabled: bool = Field(default=True, description="Indicates if share link is active (assuming not expired), used to shut down link if needed")

    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))

    def create_shared_link_record(self, session: Session, usr_context: PvfUserContext, clear_lock: bool=True) -> PvfShareLinkResult_One:
        self.id = None
        self.magic_token = None
        if usr_context is not None and usr_context.sess_user is not None and (usr_context.sess_user.id != self.user_id or usr_context.sess_user.customer_id != self.customer_id):
            log_event("Unauthorized attempt to create shared link", usr_context=usr_context, severity=3,
                      raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized attempt to create shared link for another user/account"))

        if self.shared_type in get_share_object_actions():
            hooks = get_hooks()
            if hooks.entity_resolver is None:
                log_event("Share entity resolver hook is not registered by the application", usr_context=usr_context, severity=5,
                          raise_exception=HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Share link support is not fully configured"))
            resolved = hooks.entity_resolver(session=session, usr_context=usr_context, entity_id=self.shared_entity_db_id)
            if resolved is None or resolved.customer_id != usr_context.sess_user.customer_id:
                log_event("Associated entity not found or not current customer", usr_context=usr_context, severity=3,
                        raise_exception=HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot access entity specified attempting create a shared link"))
            if self.share_link_name in (None, ""):
                self.share_link_name = resolved.display_name
        else:
            log_event("Requesting unknown or unspecified share type", usr_context=usr_context, severity=4,
                      raise_exception=HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Requesting unknown share type {self.shared_type} - {self.shared_entity_db_id}"))

        if self.share_actions is None:
            self.share_actions = list(get_hooks().share_action_matrix.get(self.shared_type, [])) or None
        else:
            unknown_actions = [a for a in self.share_actions if a not in get_share_access_operations()]
            if unknown_actions:
                log_event(f"Requesting share with unknown actions {unknown_actions}", usr_context=usr_context, severity=4,
                          raise_exception=HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown share actions {unknown_actions} for share request {self.shared_type}"))

        if self.access_mode in (PvfShareAccessCheckMode.not_specified,):
            log_event("Requesting share without access_mode setting", usr_context=usr_context, severity=4,
                      raise_exception=HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Access Mode not set {self.access_mode} for share request {self.shared_type} - {self.shared_entity_db_id}"))
        self.magic_token = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode("ascii").strip("=")
        if self.share_password is not None and len(self.share_password):
            self.share_password = get_hex_hash_from_args(settings.SHARE_LINK_REST_PW_HASH_KEY, self.magic_token, self.share_password, settings.SHARE_LINK_REST_PW_HASH_KEY)
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        return PvfShareLinkResult_One(link_info=self)

    def update_shared_link_record(self, session: Session, usr_context: PvfUserContext, clear_lock: bool=True) -> PvfShareLinkResult_One:
        if usr_context.sess_user.id != self.user_id or usr_context.sess_user.customer_id != self.customer_id:
            log_event("Unauthorized attempt to update shared link for another user/customer", usr_context=usr_context, severity=3,
                      raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized attempt to update shared link for another user"))
        existing_row_result = PvfShareLink.get_shared_link_by_id_or_magic_token_system(session=session, usr_context=usr_context, shared_link_id=self.id, shared_magic_token=self.magic_token, clear_lock=False, allow_disabled_link_retrieval=True)
        if existing_row_result.failure_reason:
            session.close()
            return PvfShareLinkResult_One(failure_reason=existing_row_result.failure_reason, log_id=existing_row_result.log_id)
        if existing_row_result.link_info is None:
            session.close()
            return PvfShareLinkResult_One(failure_reason=f'existing share for id {self.magic_token}/{self.id} not found', log_id=existing_row_result.log_id)
        if usr_context.sess_user.customer_id != existing_row_result.link_info.customer_id:
            log_event("Unauthorized attempt to update shared link for another customer", usr_context=usr_context, severity=3,
                      raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized attempt to update shared link for another customer"))
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        return PvfShareLinkResult_One(link_info=self)

    @staticmethod
    def get_shared_link_by_id_or_magic_token_system(session: Session, usr_context: PvfUserContext | None=None, shared_link_id: int | None=None, shared_magic_token: str | None=None, clear_lock: bool=True, allow_disabled_link_retrieval: bool = False) -> PvfShareLinkResult_One:
        share_link_info: PvfShareLink | None = None
        if shared_link_id is not None:
            share_link_info = session.exec(select(PvfShareLink).where(PvfShareLink.id == shared_link_id).limit(1)).one_or_none()
            if share_link_info:
                shared_magic_token = share_link_info.magic_token
        elif shared_magic_token is not None:
            share_link_info = session.exec(select(PvfShareLink).where(PvfShareLink.magic_token == shared_magic_token).limit(1)).one_or_none()
            if share_link_info:
                shared_link_id = share_link_info.id
        else:
            log_event("Invalid request for shared link, no id or magic key was provided", severity=3,
                      usr_context=usr_context, raise_exception=True)
            raise HTTPException(status_code=500, detail="Invalid shared link request")
        if share_link_info is None:
            session.close()
            return PvfShareLinkResult_One(failure_reason=f'Shared link {shared_magic_token}/{shared_link_id} was not found')
        if share_link_info.share_link_enabled is False and allow_disabled_link_retrieval is False:
            session.close()
            return PvfShareLinkResult_One(failure_reason=f'Shared link {shared_magic_token}/{shared_link_id} is not enabled')
        if share_link_info.share_link_expiration >= 0 and share_link_info.create_date + timedelta(days=share_link_info.share_link_expiration) < datetime.now():
            session.close()
            return PvfShareLinkResult_One(failure_reason=f'Shared link {shared_magic_token}/{shared_link_id} has expired')
        if clear_lock: session.close()
        return PvfShareLinkResult_One(link_info=share_link_info)

    @staticmethod
    def get_shared_links_by_customer_id_and_project_ids(session: Session, usr_context: PvfUserContext, project_ids: list[int] | None=None, clear_lock: bool=True) -> PvfShareLinkResult_Many:
        customer_id = usr_context.sess_user.customer_id
        if project_ids is None:
            share_link_info_list = session.exec(select(PvfShareLink).where(PvfShareLink.customer_id == customer_id)).all()
        else:
            share_link_info_list = session.exec(select(PvfShareLink).where(PvfShareLink.customer_id == customer_id, PvfShareLink.shared_entity_db_id.in_(project_ids))).all()
        if clear_lock: session.close()
        return PvfShareLinkResult_Many(link_info_list=share_link_info_list)


# The actual table class, built through the model factory so the application can add
# columns (see pvf.db.model_factory).
PvfShareLink = extend_model_class(PvfShareLinkSpec, get_schema_extension_registry().for_table("pvf_sharelink"))


class PvfShareLinkMagicKey(SQLModel, table=True):
    __tablename__ = "pvf_sharelinkmagickey"
    id: int | None = Field(default=None, primary_key=True)
    share_id: int | None = Field(default=None, index=True, description="The associated share event id")
    share_magic_token: str | None = Field(default=None, description="The visible token value for the share")
    access_magic_key: str | None = Field(default=None, description="The assigned access magic key to grant one time access and set recurring cookie")
    share_token_and_access_magic_key: str | None = Field(default=None, unique=True, index=True, description="Holds the share magic key:login token values to validate issued tokens")
    captured_email: str | None = Field(default=None, description="The captured email associated with the link share")
    captured_display_name: str | None = Field(default=None, description="Display name associated with the link share")
    original_link_recipient_email: str | None = Field(default=None, description="The email on file associated with the link's origination")
    accessed_date: Union[datetime, None] = None
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))

    @staticmethod
    def create_shared_magic_key_record(session: Session, usr_context: PvfUserContext,
                                       share_link_id: int,
                                       shared_magic_token: str,
                                       captured_email: str|None=None,
                                       captured_display_name: str|None=None,
                                       original_link_recipient_email: str|None=None,
                                       clear_lock: bool=True) -> Union[PvfShareLinkMagicKey, None]:
        magic_record = PvfShareLinkMagicKey(share_id=share_link_id)
        magic_record.share_magic_token = shared_magic_token
        magic_record.access_magic_key = get_random_baseN_value(
            length=6, digits_only=settings.token_security_digits_only
        )
        magic_record.share_token_and_access_magic_key = f"{shared_magic_token}:{magic_record.access_magic_key}"
        magic_record.captured_email = captured_email
        magic_record.original_link_recipient_email = original_link_recipient_email
        magic_record.captured_display_name = captured_display_name
        session.add(magic_record)
        session.commit()
        session.refresh(magic_record)
        if clear_lock: session.close()
        return magic_record

    @staticmethod
    def get_shared_magic_key_record(session: Session, usr_context: PvfUserContext,
                                    shared_magic_token: str,
                                    access_magic_key: str,
                                    clear_lock: bool=True) -> Union[PvfShareLinkMagicKey, None]:
        share_token_and_access_magic_key = f"{shared_magic_token}:{access_magic_key}"
        share_magic_key_info: PvfShareLinkMagicKey = session.exec(select(PvfShareLinkMagicKey).where(PvfShareLinkMagicKey.share_token_and_access_magic_key == share_token_and_access_magic_key).limit(1)).one_or_none()
        if clear_lock or share_magic_key_info is None: session.close()
        return share_magic_key_info

    def set_shared_magic_key_record_used(self, session: Session, usr_context: PvfUserContext, clear_lock: bool=True):
        self.accessed_date = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        return

    @staticmethod
    def get_shared_magic_key_tracking_by_share_ids_system(session: Session, usr_context: PvfUserContext, share_ids: list[int]|None=None, clear_lock: bool=True) -> list[PvfShareLinkMagicKey]:
        share_magic_keys = session.exec(select(PvfShareLinkMagicKey).where(PvfShareLinkMagicKey.share_id.in_(share_ids))).all()
        if clear_lock: session.close()
        return share_magic_keys

class PvfShareLinkAccessed(SQLModel, table=True):
    __tablename__ = "pvf_sharelinkaccessed"
    id: int | None = Field(default=None, primary_key=True)
    share_id: int | None = Field(default=None, index=True, description="The associated share event id")
    share_magic_token: str | None = Field(default=None, description="The visible token value for the share")
    cookie_token: str = Field(default=None, index=True, description="Holds the assigned cookie; if exists, the count is updated rather than creating a new access entry")
    shared_entity_db_id: int | None = Field(default=None, index=True, description="Identifies the entity the share is associated with")
    customer_id: int | None = Field(default=None, index=True, description="customer account that owns the shared entity")
    user_id: int | None = Field(default=None, description="user id of the originator who created the share link")

    remote_ip: str | None = Field(default=None, description="The remote ip associated with the share link activation")
    url_path: str | None = Field(default=None, description="The url path used to access the resource when cookie was assigned")
    access_operation: List[str] | None = Field(default=None, sa_column=Column(JSONB, default=None, nullable=True), description="The action(s) actually used when the link was accessed")

    captured_customer_id: int | None = Field(default=None, description="The customer id associated with the share access event if relevant")
    captured_email: str | None = Field(default=None, description="The captured email associated with the access")
    captured_display_name: str | None = Field(default=None, description="Display name captured for the viewer")
    access_count: int = Field(default=1, description="The number of times this shared resource was accessed via this cookie token")
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))

    def record_operation_used(self, session: Session, operation: str | None, clear_lock: bool=True) -> None:
        """Journal an action actually used on this access record (idempotent append)."""
        if operation in (None, "", "not_set"):
            return
        operations = list(self.access_operation or [])
        if operation not in operations:
            operations.append(operation)
            self.access_operation = operations
            session.add(self)
            session.commit()
            session.refresh(self)
        if clear_lock: session.close()

    @staticmethod
    def create_shared_link_access_record(session: Session,
                                         usr_context: PvfUserContext,
                                         share_link_info: PvfShareLink,
                                         access_operation: List[str] | None = None,
                                         cookie_value: str|None=None,
                                         captured_customer_id: int|None=None,
                                       captured_email: str|None=None,
                                       captured_display_name: str|None=None,
                                       shared_entity_db_id: int|None=None,
                                       clear_lock: bool=True) -> Union[PvfShareLinkAccessed, None]:
        if cookie_value is None:
            cookie_value = f'not_used_{get_random_baseN_value(length=12)}'
        share_access_record = PvfShareLinkAccessed(share_id=share_link_info.id,
                                                 share_magic_token=share_link_info.magic_token,
                                                 cookie_token=cookie_value,
                                                 shared_entity_db_id=share_link_info.shared_entity_db_id if shared_entity_db_id is None else shared_entity_db_id,
                                                 customer_id=share_link_info.customer_id,
                                                 user_id=share_link_info.user_id,
                                                 remote_ip=usr_context.remote_ip,
                                                 url_path=usr_context.url_path,
                                                 access_operation=access_operation,
                                                 captured_customer_id=captured_customer_id,
                                                 captured_email=captured_email,
                                                 captured_display_name=captured_display_name
                                                 )
        session.add(share_access_record)
        session.commit()
        session.refresh(share_access_record)
        if clear_lock: session.close()
        return share_access_record

    @staticmethod
    def create_or_increment_shared_link_access_record(session: Session,
                                         usr_context: PvfUserContext,
                                         share_link_info: PvfShareLink,
                                         cookie_value: str|None=None,
                                       captured_email: str|None=None,
                                       captured_display_name: str|None=None,
                                       clear_lock: bool=True) -> Union[PvfShareLinkAccessed, None]:
        share_access_record = PvfShareLinkAccessed.get_shared_link_access_record_by_cookie_value_system(session=session,
                                                                                              usr_context=usr_context,
                                                                                              share_link_info=share_link_info,
                                                                                              cookie_value=cookie_value,
                                                                                              clear_lock=False)
        if share_access_record is None:
            share_access_record = PvfShareLinkAccessed(share_id=share_link_info.id,
                                                    share_magic_token=share_link_info.magic_token,
                                                    cookie_token=cookie_value,
                                                    shared_entity_db_id=share_link_info.shared_entity_db_id,
                                                    customer_id=share_link_info.customer_id,
                                                    user_id=share_link_info.user_id,
                                                    remote_ip=usr_context.remote_ip,
                                                    url_path=usr_context.url_path,
                                                    captured_email=captured_email,
                                                    captured_display_name=captured_display_name
                                                    )
            session.add(share_access_record)
            session.commit()
            session.refresh(share_access_record)
        else:
            share_access_record.access_count += 1
            session.add(share_access_record)
            session.commit()
            session.refresh(share_access_record)
        if clear_lock: session.close()
        return share_access_record

    @staticmethod
    def get_shared_link_access_record_by_cookie_value_system(session: Session,
                                         usr_context: PvfUserContext,
                                         share_link_info: PvfShareLink,
                                         cookie_value: str|None=None,
                                         clear_lock: bool=True):
        share_access_rows = session.exec(select(PvfShareLinkAccessed).where(PvfShareLinkAccessed.cookie_token == cookie_value, PvfShareLinkAccessed.share_id == share_link_info.id)).one_or_none()
        if clear_lock: session.close()
        return share_access_rows

    @staticmethod
    def get_shared_link_access_records_by_customer_id_and_project_ids_system(session: Session, usr_context: PvfUserContext, project_ids: list[int]|None=None, clear_lock: bool=True) -> list[PvfShareLinkAccessed]:
        customer_id = usr_context.sess_user.customer_id
        if project_ids is None:
            share_access_records = session.exec(select(PvfShareLinkAccessed).where(PvfShareLinkAccessed.customer_id == customer_id)).all()
        else:
            share_access_records = session.exec(select(PvfShareLinkAccessed).where(PvfShareLinkAccessed.customer_id == customer_id, PvfShareLinkAccessed.shared_entity_db_id.in_(project_ids))).all()
        if clear_lock: session.close()
        return share_access_records
