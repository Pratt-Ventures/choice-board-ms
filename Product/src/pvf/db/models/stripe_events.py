from __future__ import annotations
from typing import TYPE_CHECKING, Union
from datetime import datetime
from enum import Enum
from passlib.context import CryptContext

from sqlmodel import SQLModel, Field, Session, select, desc
from sqlalchemy import func, DateTime, Column

from .customer_user import PvfUser, PvfUserContext
from ...config.pvf_config_settings import pvf_settings as settings

# stripe hook test pages - as of 2/23/2025
# subscription purchase - https://buy.stripe.com/test_8wMdSZ0v70v0eXebIJ
# token add on package - https://buy.stripe.com/test_bIY9CJfq191w2asfYY

# Handle circular imports: https://sqlmodel.tiangolo.com/tutorial/code-structure/#hero-model-file.  Commenting out for now because it throws an error?
# if TYPE_CHECKING:
#     from .user_passwords import PvfUserPasswords

class PvfStripeEvent(SQLModel, table=True):
    __tablename__ = "pvf_stripeevent"
    id: int | None = Field(default=None, primary_key=True)
    stripe_event_id: Union[str, None] = Field(default=None, index=True, unique=True, description="Stripe reported transaction id")
    stripe_customer_id: str | None= Field(default=None, index=True, description="Stripe PvfCustomer Id")
    primary_customer_id: int | None= Field(default=None, index=True, description="The local customer account affected by the event")
    sandbox_hook: bool | None = Field(default=False, description="Indicates if the event was received from the configured sandbox stripe hook")
    sandbox_mismatch: bool | None = Field(default=False, description="Indicates if the event was received from a sandbox hook but marked as livemode or vice versa")
    application_tag: str | None = Field(default=None, description="PvfCustomer application tag associated with the event")
    stripe_event_type: str| None = Field(default="", description="Type of event as reported by Stripe")
    stripe_livemode: bool | None = Field(default=None, description="Indicates if the event was in live mode")
    stripe_nested_object_type: str | None = Field(default="", description="Type of nested object as reported by Stripe")
    stripe_informational_capture_only: bool = Field(default=False, description="Indicates if the event is informational in nature as implemented")
    stripe_invoice_id: str | None = Field(default=None, description="The Stripe invoice identification where applicable (charge or invoice related)")
    stripe_checkout_session_id: str | None = Field(default=None, description="Stripe Checkout Session Id")
    stripe_payment_intent_id: str | None = Field(default=None, description="Stripe Payment Intent Id")
    stripe_subscription_id: str | None = Field(default=None, description="Stripe Subscription Id")  

    stripe_lookup_key: str | None = Field(default=None, description="Stripe lookup key for the event")  
    stripe_product: str | None = Field(default=None, description="Stripe product id associated with the event")
    stripe_payment_link: str | None = Field(default=None, description="Stripe payment link associated with the event")
    stripe_customer_email: str | None=Field(default=None, description="Email associated with the stripe customer or transaction")
    stripe_charge_name: str | None = Field(default=None, description="Name assigned to account by stripe, expecting individual, not company name")
    stripe_charge_phone: str | None = Field(default=None, description="Phone number provided in stripe setup/checkout")
    stripe_invoice_pdf_url: str | None = Field(default=None, description="Stripe hosted pdf of related invoice")
    stripe_receipt_url: str | None = Field(default=None, description="Stripe hosted receipt for completed charges")
    stripe_cancellation_info:str | None = Field(default=None, description="Indication in stripe data of likely cancellation intent")

    stripe_transaction_amount: float = 0.0
    stripe_discount_amount: float = 0.0
    stripe_currency: str | None = Field(default=None, description='Currency for the transaction')
    
    transaction_units: str | None = Field(default=None, description="Units for the transaction, e.g., years, months or days")
    transaction_add_months_count: int = Field(default=0, description="Number of months to add")
    transaction_add_days_count: int = Field(default=0, description="Number of days to add")
    transaction_trial_days_count: int = Field(default=0, description="Number of trial days included for the transaction")

    latest_transaction_id: int = Field(default=0, description="The latest (usually only) subscriber transaction id created or 0 if none or not applicable")

    related_log_id: int = Field(default=0, description="Related system log message if non-zero")

    exception_message: str | None = Field(default=None, description="If present, specifies an exception or unexpected condition regarding this event")
    exception_severity: int = Field(default=0, description="Defines the importance or severity of the event to this system, 0=informational, 1=recognized event, 2 indicates error processing")

    stripe_event_data: str = Field(default="", description="str encoded JSON of the request message contents")
    event_time: datetime = Field(sa_column=Column(DateTime, default=func.now()))

    def create_stripe_event_system(self, session: Session, clear_lock:bool=True) -> int:
        session.add(self)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        return self.id
