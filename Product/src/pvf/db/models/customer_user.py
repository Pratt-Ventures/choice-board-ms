from __future__ import annotations
from typing import TYPE_CHECKING, Union, Any, Dict
from datetime import datetime
from enum import Enum
from passlib.context import CryptContext
from pydantic import BaseModel

from sqlmodel import SQLModel, Field, Session, select, desc
from sqlalchemy import func, DateTime, Column
from sqlalchemy.dialects.postgresql import JSONB

# from .user import PvfUser, PvfUserContext
from .user_passwords import PvfUserPasswords

from ...utils.pvf_base_internal_resources import PvfWsResultPackage
from ...utils.log_event import log_event

from ...config.pvf_config_settings import pvf_settings as settings
from ..model_factory import extend_model_class, get_schema_extension_registry

# Handle circular imports: https://sqlmodel.tiangolo.com/tutorial/code-structure/#hero-model-file.  Commenting out for now because it throws an error?
# if TYPE_CHECKING:
#     from .user_passwords import PvfUserPasswords

class PvfUserResult_One_Id(PvfWsResultPackage):
    user_id: Union[int, None] = None

class PvfUserResult_One(PvfWsResultPackage):
    user_info: Union[PvfUser, None] = None

class PvfUserResult_Many(PvfWsResultPackage):
    user_info_list: Union[list[PvfUser], None] = None

class PvfDeleteResult(PvfWsResultPackage):
    success: bool = False
    user_id: int | None = None

class PvfUserContext(BaseModel):
    authenticated_session: bool = Field(default=False, description="Indication of whether the context indicates a fully authenticated user session")
    limited_proxy: bool = Field(default=False, description="If true, the context is a limited use context, mainly for logging purposes, on behalf of indicated user, but possibly via share, password chg, or other 'proxy' type usage")
    sess_user: PvfUser | None = Field(default=None, description="the user information associated with the session OR grantor of the non-user access link")
    sess_customer: PvfCustomer | None = Field(default=None, description="the customer information associated with the session")
    sess_api_access_config: None | Any = Field(default=None, description="the api access configuration information associated with the session")
    remote_ip: str | None = Field(default=None, description="remote ip from fastapi request if known")
    url_path: str | None = Field(default=None, description="request url path from fastapi if known")
    share_link_id: int | None = Field(default=None, description="When access is via share link, the PvfShareLink.id")
    share_link_ident: str | None = Field(default=None, description="When access is via share link, a display identity for the sharee")
    def model_post_init(self, ctx):
        if self.limited_proxy and self.sess_user is not None:
            self.sess_user.power_user_mode = 0
            self.sess_user.customer_admin = 0
            self.sess_user.system_user_mode = 0
            return
        
class PvfUserSpec(SQLModel):
    __tablename__ = "pvf_user"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    phone: str | None = Field(default=None, description="Optional phone number to contact user")
    customer_id: int
    customer_admin: bool = False
    # power_users: 0 = normal; 1=customer enhanced features / limited power user; 2=customer full features/power within customer
    power_user_mode: int = Field(default=0, ge=0, le=2, description="Added power user features; 0 = normal; 1=extra features/power in customer (can queue requests on upload); 2=more extra features/power in customer")
    # system_users: 0 = normal; 1=system access within customer, 2=system features all customers
    system_user_mode: int = Field(default=0, ge=0, le=2, description="Added system user features; 0 = normal; 1=system features within customer; 2=system features global")
    client_settings: Dict[str, Any] | None=Field(default=None, sa_column=Column(JSONB, default=None, nullable=True), description="Contains a JSON packaged dict where each named field is placed in the client_settings area iff the field is already defined there; applied after defaults and customer level settings; VERIFY IMPLEMENTATION BEFORE USE")
    # TODO: Add access_disabled option
    access_disabled: int = Field(default=0, description="Setting to temporarily or permanently disable access; if 1 user only; if 2 user and any shared links")
    use_2fa: bool = Field(default=False, description="When true and LOGIN_2FA_MODE is admins+optin, this user must complete email 2FA at login")
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    # from https://github.com/fastapi/sqlmodel/discussions/990 regarding onupdate support simulation in sqlmodel
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))
    deleted_date: datetime | None = Field(default=None, description="Date user was deleted; if not None, user is considered deleted and not active")

    def create_user(self, session: Session, usr_context: PvfUserContext, password: str, clear_lock: bool=True) -> PvfUserResult_One:
        failure_reason, log_id, create_user_row = PvfUser.check_user_access_to_user('create_user', 
                                                                                 key=self.email, usr_context=usr_context, 
                                                                                 check_user=self, 
                                                                                 update_mode=True
                                                                                 )
        if create_user_row is None:
            return PvfUserResult_One(failure_reason=failure_reason, log_id=log_id)
        return self.create_user_system(session, password, customer_id=usr_context.sess_user.customer_id, clear_lock=clear_lock)

    def create_user_system(self, session: Session, password: str, customer_id: int=None, clear_lock: bool=True) -> PvfUserResult_One:
        if self.id not in (-1, 0, None):
            existing_user = PvfUser.get_user_by_id_system(session, self.id)
            if existing_user:
                return PvfUserResult_One(failure_reason=f"user id {self.id} already exists")
        existing_user = PvfUser.get_user_by_email_system(session, email=self.email)
        if existing_user:
            info_msg = f" as id {existing_user.id}" if (customer_id is None or customer_id == existing_user.customer_id) else ''
            return PvfUserResult_One(failure_reason=f"{self.email} already belongs to another {settings.APPLICATION_NAME} account")
        session.add(self)
        session.commit()
        session.refresh(self)
        return_user = PvfUser(**self.model_dump())   # otherwise we return a hobbled post-transaction object

        pwd_context = CryptContext(schemes=["pbkdf2_sha512"], deprecated="auto")
        hashed_password = pwd_context.hash(password)
        session.add(PvfUserPasswords(user_id=self.id, hash=hashed_password))
        session.commit()
        if clear_lock: session.close()
        return PvfUserResult_One(user_info=return_user)

    def update_user(self, session: Session, usr_context: PvfUserContext, new_password: str=None, clear_lock: bool=True) -> PvfUserResult_One:
        if self.id not in (None, 0, -1):
            existing_user_result = PvfUser.get_user_by_id(session, id=self.id, usr_context=usr_context)
        else:
            existing_user_result = PvfUser.get_user_by_email(session, email=self.email, usr_context=usr_context)
        if existing_user_result.failure_reason:
            return existing_user_result
        existing_user = existing_user_result.user_info
        failure_reason, log_id, existing_user  = PvfUser.check_user_access_to_user('update_user', key=self.id, usr_context=usr_context, check_user=existing_user, update_mode=True)
        if existing_user is None or failure_reason != '':
            return PvfUserResult_One(failure_reason=failure_reason, log_id=log_id)
        if self.customer_admin is False and existing_user.customer_admin is True:
            admin_results = PvfUser.get_account_admins(session, usr_context=usr_context)
            admin_users_list = admin_results.user_info_list
            if failure_reason or len(admin_users_list) < 2:
                log_id = log_event(log_message=f'Cannot remove the only admin user {existing_user.email} ({existing_user.id})', severity=3, 
                                   usr_context=usr_context)
                return PvfUserResult_One(failure_reason='Cannot remove the only customer admin', log_id=log_id)
        self.id = existing_user.id
        if self.email in (None, ''):
            self.email = existing_user.email
        update_fields = self.model_dump(exclude_unset=True)
        existing_user.sqlmodel_update(update_fields)
        session.add(existing_user)
        return_user = PvfUser(**existing_user.model_dump())
        session.commit()
        session.refresh(existing_user)
        if new_password is not None:
            existing_pw_row = session.exec(select(PvfUserPasswords).where(PvfUserPasswords.user_id == self.id).order_by(desc(PvfUserPasswords.id)).limit(1)).one()
            pwd_context = CryptContext(schemes=["pbkdf2_sha512"], deprecated="auto")
            hashed_password = pwd_context.hash(new_password)
            existing_pw_row.hash = hashed_password
            existing_pw_row.last_2fa_hash = None
            existing_pw_row.last_2fa_issued_at = None
            session.add(existing_pw_row)  # performing an update
            session.commit()
        if clear_lock: session.close()
        return PvfUserResult_One(user_info=return_user)
    
    def delete_user_system(self, session: Session, usr_context: PvfUserContext) -> PvfDeleteResult:
        if self.id not in (None, 0, -1):
            existing_user_result = PvfUser.get_user_by_id(session, id=self.id, usr_context=usr_context)
        else:
            existing_user_result = PvfUser.get_user_by_email(session, email=self.email, usr_context=usr_context)
        if existing_user_result.failure_reason:
            return PvfDeleteResult(success=False, failure_reason=existing_user_result.failure_reason)

        existing_user = existing_user_result.user_info
        failure_reason, log_id, existing_user  = PvfUser.check_user_access_to_user('delete_user', key=self.id, usr_context=usr_context, check_user=existing_user, update_mode=True)
        if existing_user is None or failure_reason != '':
            return PvfDeleteResult(failure_reason=failure_reason, log_id=log_id)
        if self.customer_admin is False and existing_user.customer_admin is True:
            admin_results = PvfUser.get_account_admins(session, usr_context=usr_context)
            admin_users_list = admin_results.user_info_list
            if failure_reason or len(admin_users_list) < 2:
                log_id = log_event(log_message=f'Cannot remove the only admin user {existing_user.email} ({existing_user.id})', severity=3, 
                                   usr_context=usr_context)
                return PvfDeleteResult(failure_reason='Cannot remove the only customer admin', log_id=log_id)
        
        if usr_context.sess_user.id == existing_user.id:
            return PvfDeleteResult(failure_reason='You cannot delete yourself. Please have a different admin do it for you.', log_id=log_id)
        
        existing_user.deleted_date = datetime.now()
        session.add(existing_user)
        session.commit()
        return PvfDeleteResult(success=True, user_id=existing_user.id)


    def update_user_password_system(self, session: Session, new_password: str=None, clear_lock: bool=True) -> bool:
        existing_pw_row = session.exec(select(PvfUserPasswords).where(PvfUserPasswords.user_id == self.id).order_by(desc(PvfUserPasswords.id)).limit(1)).one()
        if existing_pw_row is None:
            if clear_lock: session.close()
            return False
        pwd_context = CryptContext(schemes=["pbkdf2_sha512"], deprecated="auto")
        hashed_password = pwd_context.hash(new_password)
        existing_pw_row.hash = hashed_password
        existing_pw_row.last_2fa_hash = None
        existing_pw_row.last_2fa_issued_at = None
        session.add(existing_pw_row)  # performing an update
        session.commit()
        if clear_lock: session.close()
        return True

    def verify_password(self, session: Session, password: str) -> bool:
        pwd_context = CryptContext(schemes=["pbkdf2_sha512"], deprecated="auto")
        password_record = session.exec(select(PvfUserPasswords).where(PvfUserPasswords.user_id == self.id).order_by(desc(PvfUserPasswords.id)).limit(1)).one()
        return pwd_context.verify(password, password_record.hash)
    
    @staticmethod
    def get_user_by_email(session: Session, *, email: str, usr_context: PvfUserContext, clear_lock: bool=True) -> PvfUserResult_One:
        user_info = session.exec(select(PvfUser).where(PvfUser.email == email, PvfUser.deleted_date == None).limit(1)).one_or_none()
        failure_reason, log_id, user_info = PvfUser.check_user_access_to_user('get_user_by_email', key=email, usr_context=usr_context, check_user=user_info, update_mode=False)
        if clear_lock: session.close()
        return PvfUserResult_One(failure_reason=failure_reason, log_id=log_id, user_info=user_info)

    @staticmethod
    def get_user_by_email_system(session: Session, *, email: str, clear_lock: bool=True) -> PvfUser:
        user_info = session.exec(select(PvfUser).where(PvfUser.email == email, PvfUser.deleted_date == None).limit(1)).one_or_none()
        if clear_lock: session.close()
        return user_info

    @staticmethod
    def get_user_by_id(session: Session, *, id: int, usr_context: PvfUserContext, clear_lock: bool=True) -> PvfUserResult_One:
        user_info = session.exec(select(PvfUser).where(PvfUser.id == id, PvfUser.deleted_date == None).limit(1)).one_or_none()
        failure_reason, log_id, user_info = PvfUser.check_user_access_to_user('get_user_by_id', key=id, usr_context=usr_context, check_user=user_info, update_mode=False)
        if clear_lock: session.close()
        return PvfUserResult_One(failure_reason=failure_reason, log_id=log_id, user_info=user_info)

    @staticmethod
    def get_user_by_id_system(session: Session, *, id: int, clear_lock: bool=True) -> PvfUser:
        user_info = session.exec(select(PvfUser).where(PvfUser.id == id, PvfUser.deleted_date == None).limit(1)).one_or_none()
        if clear_lock: session.close()
        return user_info

    @staticmethod
    def get_account_users(session: Session, *, usr_context: PvfUserContext, clear_lock: bool=True) -> PvfUserResult_Many:
        # note - any account user can see other users, just no updates are allowed...
        # supports a 'my team' type list...
        user_info_list = session.exec(select(PvfUser).where(PvfUser.customer_id == usr_context.sess_user.customer_id, PvfUser.deleted_date == None)).all()
        if clear_lock: session.close()
        return PvfUserResult_Many(user_info_list=user_info_list)

    @staticmethod
    def get_account_admins(session: Session, *, usr_context: PvfUserContext, clear_lock: bool=True) ->  PvfUserResult_Many:
        # note - any account user can see other users, just no updates are allowed...
        # supports a 'my team' type list...
        admin_info_list = session.exec(select(PvfUser).where(PvfUser.customer_id == usr_context.sess_user.customer_id, PvfUser.deleted_date == None).where(PvfUser.customer_admin == True)).all()
        if clear_lock: session.close()
        return PvfUserResult_Many(user_info_list=admin_info_list)

    @staticmethod
    def check_user_access_to_user(action: str, *, key: any, usr_context: PvfUserContext, check_user: PvfUser, update_mode: bool) -> tuple[str, int, PvfUser]:
        failure_reason = ''
        log_id = 0
        if check_user is None:
            log_id = log_event(log_message=f'{action} - PvfUser {key}: PvfUser {key} NOT FOUND', severity=2, 
                               usr_context=usr_context) 
            failure_reason = 'PvfUser not found'
        elif update_mode and usr_context.sess_user.customer_admin is False and check_user.id != usr_context.sess_user.id:
            log_id = log_event(log_message=f'{action} - PvfUser {key}: {check_user.email} ({check_user.id}) cust {check_user.customer_id}) NON-ADMIN USER MISMATCH', 
                        severity=3, usr_context=usr_context)
            check_user = None
            failure_reason = "Not allowed; non-admin"
        elif check_user.customer_id != usr_context.sess_user.customer_id:
            log_id = log_event(log_message=f'{action} - PvfUser {key}: {check_user.email} ({check_user.id}) cust {check_user.customer_id}) CUSTOMER MISMATCH', 
                        severity=3, usr_context=usr_context)
            check_user = None
            failure_reason = "Internal issue; customer mismatch"
        return failure_reason, log_id, check_user

# The actual table class, built through the model factory so the application can add
# columns (see pvf.db.model_factory).
PvfUser = extend_model_class(PvfUserSpec, get_schema_extension_registry().for_table("pvf_user"))


class PvfAccountStatus(Enum):
    inactive = "inactive"
    active = "active"

class PvfCustomerResult_Many(PvfWsResultPackage):
    customer_info_list: Union[list[PvfCustomer], None] = None

class PvfCustomerSpec(SQLModel):
    __tablename__ = "pvf_customer"
    id: int | None = Field(default=None, primary_key=True)
    customer_email: str = Field(index=True, unique=True)
    customer_account: str | None = Field(default=None, index=True, unique=True, description="PvfCustomer's associated billing account information once established")
    customer_name: str
    customer_phone: str | None = Field(default=None, description="Phone number to contact customer - recommneded, but optional")
    account_status: PvfAccountStatus  # PvfAccountStatus values from enum above
    customer_activated: bool = Field(default=False, description="Set to true when a self registration customer has been initially activated or on creation for administratively created accounts")
    stripe_settings: str | None=Field(default=None, description="Contains a JSON packaged dict that binds account and services to a stripe account; encrypted compressed in storage")
    ai_provider: str | None = Field(default=None, description="PvfCustomer LLM provider: opencode_go, opencode_zen, or openrouter")
    ai_model: str | None = Field(default=None, description="PvfCustomer default LLM model identifier")
    ai_api_key: str | None = Field(default=None, description="PvfCustomer LLM authorization key; encrypted and encoded in storage")
    client_settings: str | None=Field(default=None, description="Contains a JSON packaged dict where each named field is placed in the clientSettings area iff the field is already defined there; prior to applying user settings")
    trial_activation_code: str | None = Field(default=None, description="Contains the trial activation code for the customer if a trial activation code was used on registration")
    trial_expiration_date: datetime | None = Field(default=None, description="If a trial activation code was used, this contains the expiration date for the trial period")
    service_expiration_date: datetime | None = Field(sa_column=Column(DateTime, default=None), description="Contains the expiration date for the service period associated with the customer")
    sandbox_count: int | None = Field(default=0, description="The number of sandbox transactions detected for the customer")
    use_2fa: bool = Field(default=False, description="When true and LOGIN_2FA_MODE is admins+optin, all users of this customer must complete email 2FA at login")
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    # from https://github.com/fastapi/sqlmodel/discussions/990 regarding onupdate support simulation in sqlmodel
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))


    def create_customer_system(self, session: Session, admin_name: str, admin_email: str, admin_phone: str, admin_password: str, 
                               power_user_mode: int=0, system_user_mode: int=0, clear_lock: bool=True) -> PvfCustomer:
        # note - this allows for the same email and phone from the customer to be used for the auto created admin user
        session.add(self)
        session.commit()
        session.refresh(self)
        admin_user = PvfUser(customer_id=self.id, customer_admin=True, name=admin_name, email=admin_email if admin_email else self.customer_email, power_user_mode=power_user_mode, system_user_mode=system_user_mode, phone=admin_phone if admin_phone else self.customer_phone)
        admin_user_result = admin_user.create_user_system(session, password=admin_password)
        admin_user = admin_user_result.user_info
        session.commit()
        if clear_lock: session.close()
        return self
    
    def update_customer_system(self, session: Session, clear_lock: bool=True):
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        return

    def apply_ai_api_key_update(self, submitted: str | None) -> None:
        from ...utils.field_encryption import encrypt_secret

        value = "" if submitted is None else str(submitted)
        stored = self.ai_api_key or ""
        if value == stored:
            return
        if value.strip() == "":
            self.ai_api_key = ""
            return
        self.ai_api_key = encrypt_secret(value)

    def decrypted_ai_api_key(self) -> str:
        from ...utils.field_encryption import decrypt_secret

        return decrypt_secret(self.ai_api_key or "")

    def customer_llm_configured(self) -> bool:
        from ...utils.llm_client import provider_is_supported

        provider = str(self.ai_provider or "").strip()
        key = self.decrypted_ai_api_key().strip()
        return bool(provider) and provider_is_supported(provider) and bool(key)
    
    @staticmethod
    def get_customer_by_email(session: Session, usr_context: PvfUserContext, email: str, clear_lock: bool=True) -> Union[PvfCustomer, None]:
        # TODO: Possible poweruser or superuser adjustment needed here...
        customer_info = session.exec(select(PvfCustomer).where(PvfCustomer.customer_email == email).limit(1)).one_or_none()
        if customer_info is None:
            user_info = session.exec(select(PvfUser).where(PvfUser.email == email).limit(1)).one_or_none()
            if user_info is not None:
                customer_info = session.exec(select(PvfCustomer).where(PvfCustomer.id == user_info.customer_id).limit(1)).one_or_none()
        if customer_info.id != usr_context.sess_user.customer_id:
            log_event(f"Attempt to access customer record id by email {email} from outside account", severity=3, usr_context=usr_context)
            return None
        if clear_lock: session.close()
        return customer_info

    @staticmethod
    def get_customer_by_id(session: Session, *, usr_context: PvfUserContext, id: int, clear_lock: bool=True) -> PvfCustomer:
        customer_info = session.exec(select(PvfCustomer).where(PvfCustomer.id == id).limit(1)).one_or_none()
        if customer_info.id != usr_context.sess_user.customer_id:
            log_event(f"Attempt to access customer record id {id} from outside account", severity=3, usr_context=usr_context)
            return None
        if clear_lock: session.close()
        return customer_info

    @staticmethod
    def get_customer_by_id_system(session: Session, id: int, clear_lock: bool=True) -> PvfCustomer:
        customer_info = session.exec(select(PvfCustomer).where(PvfCustomer.id == id).limit(1)).one_or_none()
        if clear_lock: session.close()
        return customer_info

    @staticmethod
    def get_customer_by_email_system(session: Session, customer_email: str, clear_lock: bool=True) -> PvfCustomer:
        customer_info = session.exec(select(PvfCustomer).where(PvfCustomer.customer_email == customer_email).limit(1)).one_or_none()
        if clear_lock: session.close()
        return customer_info

    @staticmethod
    def get_customer_by_account_system(session: Session, customer_account: str, clear_lock: bool=True) -> PvfCustomer:
        customer_info = session.exec(select(PvfCustomer).where(PvfCustomer.customer_account == customer_account).limit(1)).one_or_none()
        if clear_lock: session.close()
        return customer_info

    @staticmethod
    def get_customer_by_stripe_key_system(session: Session, customer_STRIPE_HOOK_STR_PRIMARY: str, clear_lock: bool=True) -> PvfCustomer:
        customer_info = session.exec(select(PvfCustomer).where(PvfCustomer.customer_STRIPE_HOOK_STR_PRIMARY == customer_STRIPE_HOOK_STR_PRIMARY).limit(1)).one_or_none()
        if clear_lock: session.close()
        return customer_info

    @staticmethod
    def get_all_customers(session: Session, *, usr_context: PvfUserContext, page: int=0, page_size: int=100, clear_lock: bool=True) -> PvfCustomerResult_Many:
        # note - any account user can see other users, just no updates are allowed...
        # supports a 'my team' type list...
        if usr_context.sess_user is None or usr_context.sess_user.system_user_mode:
            offset = max((page - 1) * page_size, 0)
            query = select(PvfCustomer).offset(offset).limit(page_size)
            customer_list = session.exec(query).all()
        else:
            log_event("unexpected request for customer list", usr_context=usr_context, severity=3, 
                      raise_exception=True)
        if clear_lock: session.close()
        return PvfCustomerResult_Many(customer_info_list=customer_list)


# The actual table class, built through the model factory so the application can add
# columns (see pvf.db.model_factory).
PvfCustomer = extend_model_class(PvfCustomerSpec, get_schema_extension_registry().for_table("pvf_customer"))


class PvfCustomerResult_One_Id(PvfWsResultPackage):
    customer_id: Union[int, None] = None

class PvfCustomerResult_One(PvfWsResultPackage):
    customer_info: Union[PvfCustomer, None] = None

