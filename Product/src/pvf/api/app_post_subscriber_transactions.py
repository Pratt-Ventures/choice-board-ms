from __future__ import annotations
from pydantic import BaseModel
from datetime import datetime, timedelta

from sqlmodel import Field
from fastapi import APIRouter

from ..depends.api_session_dependencies import SessionDep
from ..depends.check_user_session_jwt_dependencies import UserAccessDep
from ..utils.pvf_base_internal_resources import PvfWsResultPackage
from ..utils.pvf_base_internal_resources import PvfSubscriberTransactionType, PvfSubscriberTransactionUnits
from ..utils.log_event import log_event
from ..db.models.subscriber_transactions import PvfSubscriberTransaction

from ..config.pvf_config_settings import pvf_settings as settings

router = APIRouter()

class SubscriberTransactionRequest(BaseModel):
    customer_id: int = Field(default=None, description="customer account for which token balance applies")
    csr_user_id: int | None = Field(default=None, description="if the transaction is associated with a customer service representative outside the client, this is the user id; if applicable")
    csr_user_name: str | None = Field(default=None, description="if the transaction is associated with a customer service representative outside the client, this identifies the responsible csr")
    csr_notes: str | None = Field(default=None, description="if initiated by a csr, this may provide notes regarding the circumstance")
    financial_transaction_amount: float = Field(default=0.0, description="Amount of the financial transaction value, e.g., 9.99")
    financial_transaction_currency: str | None = Field(default=None, description="Currency of the financial transaction, e.g., 'usd'")
    financial_discount_amount: float = Field(default=0.0, description="Amount of any financial discount applied to the transaction, e.g., 2.00")
    transaction_type: PvfSubscriberTransactionType = Field(description="indicates the type of transaction")
    transaction_units: PvfSubscriberTransactionUnits = Field(description="Indicates the primary units of the transaction (e.g., days or months); mixtures are allowed if same sign")
    transaction_day_count: int = Field(default=0, description="Number of days added (if positive) or consumed/removed (if negative)")
    transaction_month_count: int = Field(default=0, description="Number of months added (if positive) or consumed/removed (if negative)")

class SubscriberTransactionResult(PvfWsResultPackage):
    subscriber_transaction_id: int | None = Field(default=None, description="The transaction id assigned to the subscriber transaction")
    subscriber_subscription_end_date: datetime | None = Field(default=None, description="The date at which the subscriber's subscription ends")
    subscriber_grace_period_cutoff_date: datetime | None = Field(default=None, description="The date at which the subscriber's grace period ends")
    subscriber_months_remaining: int = Field(default=0, description="The number of subscriber months remaining for the customer")
    subscriber_days_remaining: int = Field(default=0, description="The number of subscriber days remaining for the customer")
    sandbox_count: int = Field(default=0, description="The number of sandbox transactions detected for the customer")

@router.post("/admin/post-subscriber-transaction",
             summary="Post a Subscriber Transaction entry for a particular customer-id (internal-requires system_user_mode>=2; setup by DBA)",
             tags=['admin'])
def post_subscription_transaction(session: SessionDep, usr_context: UserAccessDep, subscription_request: SubscriberTransactionRequest) -> SubscriberTransactionResult:
    result = SubscriberTransactionResult()
    if usr_context.sess_user.system_user_mode < 2 or not usr_context.sess_user.customer_admin:
        result.failure_reason= f"post_subscriber_transaction: Unauthorized user attempting to directly post subscriber transaction"
        result.log_id = log_event(result.failure_reason, severity=3, usr_context=usr_context)
        return result

    if subscription_request.customer_id in (None, 0):
        subscription_request.customer_id = usr_context.sess_user.customer_id

    if usr_context.sess_user.customer_id != subscription_request.customer_id and usr_context.sess_user.system_user_mode < 2:
        result.failure_reason= f"post_subscriber_transaction: Attempting to directly post subscriber transaction to other customer account"
        result.log_id = log_event(result.failure_reason, severity=3, usr_context=usr_context)
        return result

    tr_type = subscription_request.transaction_type.value
    if ( (subscription_request.transaction_month_count > 0 and '+' not in tr_type) or (subscription_request.transaction_day_count > 0 and '+' not in tr_type) or
         (subscription_request.transaction_month_count < 0 and '-' not in tr_type) or (subscription_request.transaction_day_count < 0 and '-' not in tr_type) or
         (subscription_request.transaction_month_count == 0 and subscription_request.transaction_day_count == 0 and ('+' in tr_type or '-' in tr_type)) ):
        result.failure_reason= f"post_subscriber_transaction: transaction_month_count {subscription_request.transaction_month_count} or transaction_day_count {subscription_request.transaction_day_count} is not consistent with transaction type {tr_type}"
        result.log_id = log_event(result.failure_reason, severity=3, usr_context=usr_context)
        return result

    post_transaction = PvfSubscriberTransaction(customer_id=subscription_request.customer_id,
                                             user_id=usr_context.sess_user.id,
                                             financial_event_source='admin-api',
                                             financial_event_type='post-subscriber-transaction',
                                             livemode_flag=False if settings.is_local() else True,
                                             csr_user_id=usr_context.sess_user.id,
                                        csr_user_name=usr_context.sess_user.name,
                                        financial_transaction_amount=subscription_request.financial_transaction_amount,
                                        financial_transaction_currency=subscription_request.financial_transaction_currency,
                                        financial_discount_amount=subscription_request.financial_discount_amount,
                                        transaction_type=subscription_request.transaction_type,
                                        transaction_units=subscription_request.transaction_units,
                                        transaction_month_count=subscription_request.transaction_month_count,
                                        transaction_day_count=subscription_request.transaction_day_count,
                                        )
    result.subscriber_transaction_id = post_transaction.create_subscriber_transaction_system(session=session, usr_context=usr_context)
    result.subscriber_subscription_end_date, result.subscriber_months_remaining, result.subscriber_days_remaining, sandbox_count = PvfSubscriberTransaction.get_subscriber_remaining_duration_by_customer(session=session,
                                                                                                               usr_context=usr_context,
                                                                                                               customer_id=subscription_request.customer_id)
    result.subscriber_grace_period_cutoff_date = result.subscriber_subscription_end_date + timedelta(days=settings.APPLICATION_ACCOUNT_GRACE_PERIOD_DAYS) if result.subscriber_subscription_end_date is not None else None
    result.sandbox_count = sandbox_count
    return result
