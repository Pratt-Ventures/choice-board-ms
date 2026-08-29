from __future__ import annotations
from typing import Union
from datetime import datetime
from dateutil.relativedelta import relativedelta

from sqlmodel import SQLModel, Field, Session, select
from sqlalchemy import func, DateTime, Column

from .customer_user import PvfUserContext, PvfCustomer
from ...utils.log_event import log_event
from ...utils.pvf_base_internal_resources import PvfSubscriberTransactionType, PvfSubscriberTransactionUnits, PvfWsResultPackage


class PvfSubscriberTransactionResult_Id(PvfWsResultPackage):
    subscriber_transaction_id: int | None = None

class PvfSubscriberTransactionResult_One(PvfWsResultPackage):
    subscriber_transaction_info: Union[PvfSubscriberTransaction, None] = None

class PvfSubscriberTransactionResult_Many(PvfWsResultPackage):
    subscriber_transaction_info_list: Union[list[PvfSubscriberTransaction], None] = None


class PvfSubscriberTransactionBase(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    financial_event_row_id: int | None = Field(default=None, description="if the transaction is associated with a stripe event or similar table, this is the row id in the respective table")
    financial_event_source: str | None = Field(default=None, description="Source of the financial event, e.g., 'stripe', 'admin-api'")
    financial_event_type: str | None = Field(default=None, description="Type of the financial event as reported by the transaction source")
    user_id: int | None = Field(default=None, description="user id associated with the transaction, if applicable")
    financial_transaction_amount: float = Field(default=0.0, description="Amount of the financial transaction value, e.g., 9.99")
    financial_transaction_currency: str | None = Field(default=None, description="Currency of the financial transaction, e.g., 'usd'")
    financial_discount_amount: float = Field(default=0.0, description="Amount of any financial discount applied to the transaction, e.g., 2.00")
    csr_user_id: int | None = Field(default=None, description="if the transaction is associated with a customer service representative outside the client, this is the user id; if applicable")
    csr_user_name: str | None = Field(default=None, description="if the transaction is associated with a customer service representative outside the client, this identifies the responsible csr")
    csr_notes: str | None = Field(default=None, description="if initiated by a csr, this may provide notes regarding the circumstance")
    sandbox_mismatch: bool | None = Field(default=False, description="Indicates if the event was received from a sandbox hook but marked as livemode or vice versa")
    livemode_flag: bool = Field(default=True, description="Indicates if the transaction occurred in live mode (True) or test mode (False)")
    transaction_type: PvfSubscriberTransactionType = Field(default=PvfSubscriberTransactionType.note, description="indicates effective type of transaction, convention trailing + means additive, trailing - means subtractive")
    transaction_units: PvfSubscriberTransactionUnits = Field(default=PvfSubscriberTransactionUnits.months, description="Indicates the units of the transaction (e.g., days or months)")
    transaction_month_count: int = Field(default=0, description="Number of months added (if positive) or consumed/removed (if negative)")
    transaction_day_count: int = Field(default=0, description="Number of days added (if positive) or consumed/removed (if negative)")
    transaction_trial_days_count: int = Field(default=0, description="Number of trial days added (if positive) or consumed/removed (if negative) - also reflected in add days")
    transaction_description:str | None = Field(default=None, description="Description of the products referenced in thetransaction")


class PvfSubscriberTransaction(PvfSubscriberTransactionBase, table=True):
    __tablename__ = "pvf_subscribertransaction"
    customer_id: int | None = Field(default=None, index=True, description="customer account for which token balance applies")
    transaction_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))

    def update_customer_expiration_in_transaction(self, session: Session, usr_context: PvfUserContext):
        customer_data = session.exec(select(PvfCustomer).where(PvfCustomer.id == self.customer_id)).first()
        if customer_data is None:
            session.close()
            log_event(f"Subscription transaction {self.id} referenced customer id {self.customer_id} not found", severity=3, usr_context=usr_context, raise_exception=True)

        subscriber_subscription_end_date, _, _, sandbox_count = PvfSubscriberTransaction.get_subscriber_remaining_duration_by_customer(session=session,
                                                                                                               usr_context=usr_context, 
                                                                                                               customer_id=self.customer_id,
                                                                                                               clear_lock=False)
        customer_data.service_expiration_date = subscriber_subscription_end_date
        customer_data.sandbox_count = sandbox_count
        session.add(customer_data)
        return

    def create_subscriber_transaction_system(self, session: Session, usr_context: PvfUserContext, clear_lock:bool=True) -> int:
        session.add(self)
        self.update_customer_expiration_in_transaction(session=session, usr_context=usr_context)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        return self.id

    def update_subscriber_transaction_system(self, session: Session, usr_context: PvfUserContext, clear_lock:bool=True) -> int:
        session.add(self)
        self.update_customer_expiration_in_transaction(session=session, usr_context=usr_context)
        session.commit()
        session.refresh(self)
        if clear_lock: session.close()
        return self.id
   

    @classmethod
    def get_subscriber_transaction_history_by_customer_system(cls, session: Session, usr_context: PvfUserContext, customer_id: int|None=None, application_tag: str|None=None, high_water_mark_id: int|None=None, clear_lock: bool=True) -> list[PvfSubscriberTransaction]:
        if customer_id is None: customer_id = usr_context.sess_user.customer_id
        if high_water_mark_id not in (0, -1, None):
            if application_tag in (None, ""):
                transaction_result = session.exec(select(cls).where(cls.customer_id == customer_id, cls.id > high_water_mark_id)).all()
            else:
                transaction_result = session.exec(select(cls).where(cls.customer_id == customer_id, cls.application_tag == application_tag, cls.id > high_water_mark_id)).all()
        else:
            if application_tag in (None, ""):
                transaction_result = session.exec(select(cls).where(cls.customer_id == customer_id)).all()
            else:
                transaction_result = session.exec(select(cls).where(cls.customer_id == customer_id, cls.application_tag == application_tag)).all()
        if clear_lock: session.close()
        return transaction_result

    @classmethod
    def get_subscriber_remaining_duration_by_customer(cls, session: Session, usr_context: PvfUserContext, customer_id: int|None=None, clear_lock: bool=True) -> tuple[datetime|None, int, int]:
        if customer_id is None: customer_id = usr_context.sess_user.customer_id
        transaction_results = cls.get_subscriber_transaction_history_by_customer_system(session=session, usr_context=usr_context, customer_id=customer_id, clear_lock=clear_lock)
        sandbox_count = 0
        valid_end_date = None
        for te in transaction_results:
            if valid_end_date is None or te.transaction_date > valid_end_date:
                valid_end_date = te.transaction_date
            if te.transaction_month_count > 0:
                valid_end_date = valid_end_date + relativedelta(months=te.transaction_month_count)
            if te.transaction_month_count < 0:
                valid_end_date = valid_end_date - relativedelta(months=abs(te.transaction_month_count))
            if te.transaction_day_count > 0:
                valid_end_date = valid_end_date + relativedelta(days=te.transaction_day_count)
            if te.transaction_day_count < 0:
                valid_end_date = valid_end_date - relativedelta(days=abs(te.transaction_day_count))
            if te.livemode_flag is False or te.sandbox_mismatch is True:
                sandbox_count += 1
        if clear_lock: session.close()
        test_date = datetime.now()
        if valid_end_date is not None and valid_end_date > test_date:
            remaining_duration = valid_end_date - test_date
            days_total = remaining_duration.days
            months_approximate_total = days_total // 30
        else:
            days_total = 0
            months_approximate_total = 0
        
        return (valid_end_date, months_approximate_total, days_total, sandbox_count)
