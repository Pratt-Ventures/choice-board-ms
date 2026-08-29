from pydantic import BaseModel
from sqlmodel import Field

from ...db.models.customer_user import PvfAccountStatus
from ...utils.pvf_base_internal_resources import PvfWsResultPackage

class UserInfoForm(BaseModel):
    id: int = None           # optional on update, used instead of email in that case to find existing user
    email: str | None = None               # to change email, id must be supplied as key.
    name: str | None = None
    phone: str | None = None
    customer_admin: bool | None = None   # only admins can change this, last admin removal prohibited
    power_user_mode: int | None = Field(default=None, ge=0, le=2, description="0=off, 1=power, 2=power+; customer admins only")
    password: str | None = None          # password will be updated if supplied

class CustomerUserInfoForm(BaseModel):
    customer_name: str
    account_status: PvfAccountStatus = Field(default=PvfAccountStatus.active, description="Indicates if customer account is normally active; can be later set to inactive - distinct from innitial activation")
    customer_activated: bool = Field(default=False, description="Indicates if customer is pre-activated.  If not, the welcome email will include activation link/instructions; if activated, welcome email has link to site for login")
    customer_email: str | None = Field(default=None, description="PvfCustomer specific email, not necessarily a user email; taken from initial admin user email if not specified")
    customer_phone: str | None = Field(default=None, description="PvfCustomer specific phone, not necessarily a user phone; taken from initial admin user phone if not specified")
    admin_email: str               # to change email, id must be supplied as key.
    admin_name: str = ''
    admin_phone: str | None = Field(default='', description="Admin phone number")
    admin_password: str=None          # password will be updated if supplied
    admin_power_user: int = 0
    assign_temporary_account: bool = Field(default=False, description="Specifies whether a temporary account id is assigned to the customer; if true, the customer account is set to a random number and customer will not be forced to create a plan initially")
    send_welcome_email: bool = Field(default=True, description="Specifies whether a welcome/activation message is automatically generated if successful")

class CustomerSelfRegUserInfoForm(BaseModel):
    customer_name: str
    admin_name: str = ''
    admin_email: str = Field(description="Admin email, assigned as initial customer account email; may diverge later")
    admin_phone: str | None = Field(default=None, description="Admin phone, assigned as initial customer phone; may diverge later")
    admin_password: str=None          # password will be updated if supplied
    trial_activation_code: str | None = Field(default=None, description="If specified, this code identifies a trial account code to be assigned to the customer upon creation; defers payment setup processing based on the plan code settings")
    invitation_code: str | None = Field(default=None, description="Optional invitation code; if not specified, defaults to None; otherwise a share token identifying the context and invitation origin")

class CustomerUserCreateResult(BaseModel):
    failure_reason: str = ""
    log_id: int = 0
    customer_id: int | None = None

class DeleteUserForm(BaseModel):
    user_id: int | None = None
    email: str | None = None

class DeleteUserResult(BaseModel):
    failure_reason: str = ""
    log_id: int = 0
    user_id: int | None = None

class SetUse2FAForm(BaseModel):
    enabled: bool = Field(description="Whether email 2FA should be required")

class SetUse2FAResult(PvfWsResultPackage):
    prior: bool | None = None
    new: bool | None = None
    use_2fa: bool | None = None