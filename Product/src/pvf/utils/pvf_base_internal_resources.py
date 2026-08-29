
from pydantic import BaseModel, Field
from typing import Union, Any
from enum import Enum, IntEnum
import numpy as np
import secrets

def set_update_field(data_row: any, field_name: str, value: any):
    data_row.sqlmodel_update({field_name: value})
    return None

# used for jwt token processing
class PvfTokenPayload(BaseModel):
    sub: str = None
    exp: int = None

class PvfTokenSchema(BaseModel):
    access_token: str
    refresh_token: str

class PvfWsResultPackage(BaseModel):
    failure_reason: str = ""
    log_id: Union[int, None] = 0
    # specific fields added via subclass

class PvfLogSeverity(Enum):
    debug=0
    info=1
    warning=2
    error=3
    critical=4
    crisis=5
    catastrophic=6
    apocalypse=7
    extinction_level_event=8

class PvfAuthRelatedOutboundEmailType(Enum):
    password_reset = 'password_reset'
    customer_activation_self = 'customer_activation_self'
    customer_activation_admin = 'customer_activation_admin'
    customer_activation_admin_activated = 'customer_activation_admin_activated'
    new_user_welcome = 'new_user_welcome'
    magic_access_key = 'magic_access_key' # for shared link handling
    login_2fa = 'login_2fa'
    not_set = 'not_set'

class PvfSubscriberTransactionType(Enum):
    """ Note: 
    as a precaution, any transaction type containing + can only add time (pos count),
    any containing a - can only subtract time (neg count),
    and others must have zero toke effect
    """
    purchase="purchase+"
    promotion="promotion+"
    credit="credit+"
    usage="usage-"
    cancelled="cancelled-"
    note="note"
    balance_forward="balance_forward"

class PvfSubscriberTransactionUnits(Enum):
    days = 'days'
    months = 'months'
    years = 'years'

class PvfClientAuthSettings(BaseModel):
    TWO_FACTOR_AUTH_ENABLED: bool = False
    TWO_FACTOR_AUTH_OPTIONAL: bool = False
    TWO_FACTOR_AUTH_CUSTOMER_CONTROLLABLE: bool = False
    enable_user_communication: bool = False
    ai_features_enabled: bool = False
    ai_providers_configured: bool = False

base_32_chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"

def get_random_baseN_value(length=6, map_chars=base_32_chars, *, digits_only=False):
    if digits_only:
        secret_string = ''.join(secrets.choice('0123456789') for _ in range(length))
    elif map_chars:
        secret_string = ''.join(secrets.choice(map_chars) for _ in range(length))
    else:
        secret_string = secrets.token_urlsafe(length)[:length]
    return secret_string

