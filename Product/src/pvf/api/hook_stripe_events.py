from __future__ import annotations
import time
import json

from fastapi import APIRouter, status, HTTPException, Request

import stripe

from ..db.models.customer_user import PvfCustomer, PvfUser
from ..db.models.stripe_events import PvfStripeEvent
from ..db.models.subscriber_transactions import PvfSubscriberTransaction
from ..utils.pvf_base_internal_resources import PvfSubscriberTransactionType
from ..utils.log_event import log_event
from ..depends.api_session_dependencies import SessionDep

from ..config.pvf_config_settings import pvf_settings as settings

router = APIRouter()
stripe.api_key = settings.STRIPE_API_KEY_PRIMARY

not_found_last_timestamp = 0.0
not_found_skipped_log_events = 0

sandbox_warnings = {}

@router.post('/hook-stripe-events/{stripe_event_hook_str}',
             summary='Validate and accept web-hook calls from stripe and process for primary customers',
             tags=["stripe-event-hook"],)
async def hook_stripe_events(session: SessionDep, request: Request, stripe_event_hook_str: str):
    return await post_stripe_event(session=session, request=request, stripe_event_hook_str=stripe_event_hook_str, sandbox_mode=False)

@router.post('/hook-stripe-events-sandbox/{stripe_event_hook_str}',
             summary='Validate and accept web-hook calls from stripe IN SANDBOX MODE for primary customers; all transactions forced to LIVEMODE FALSE',
             tags=["stripe-event-hook"],)
async def hook_stripe_events_sandbox(session: SessionDep, request: Request, stripe_event_hook_str: str):
    return await post_stripe_event(session=session, request=request, stripe_event_hook_str=stripe_event_hook_str, sandbox_mode=False)


async def post_stripe_event(session: SessionDep, request: Request, stripe_event_hook_str: str, sandbox_mode: bool) -> bool:
    global not_found_skipped_log_events, not_found_last_timestamp, sandbox_warnings
    result_flag = True
    remote_ip = None

    try:
        remote_ip = request.client.host
        sig_header = request.headers.get('stripe-signature')
    except Exception:
        if not_found_last_timestamp < time.time() - 1.0:
            log_event("/stripe-events - No stripe header found in listener (skipped {not_found_skipped_log_events})", severity=3, remote_ip=remote_ip, url_path='/stripe-events')
            not_found_skipped_log_events = 0
            not_found_last_timestamp = time.time()
        else:
            not_found_skipped_log_events += 1
        return False

    if stripe_event_hook_str != settings.STRIPE_HOOK_STR_PRIMARY:
        log_event(f"Stripe event hook string {stripe_event_hook_str} is not the primary platform hook", severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event Hook with ID {stripe_event_hook_str} is not recognized"))

    STRIPE_ENDPOINT_SECRET_PRIMARY = settings.STRIPE_ENDPOINT_SECRET_PRIMARY

    payload = await request.body()
    try:
        root_event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                STRIPE_ENDPOINT_SECRET_PRIMARY)
    except stripe.error.SignatureVerificationError as e:
        log_event(f'Stripe Webhook signature verification failed for hook {stripe_event_hook_str}, primary platform scope.', severity=7, ex_info=e)
        return False

    root_event_object_type = root_event.get('object', "")
    assert root_event_object_type == 'event', f"Expected stripe root event type of 'event,' received {root_event_object_type}"
    root_event_id = root_event.get('id', None)
    root_event_type = root_event.get('type', None)

    cur_transaction = PvfStripeEvent(
        stripe_event_id = root_event_id,
        stripe_event_type = root_event_type,
        sandbox_hook = sandbox_mode,
        stripe_livemode = root_event.get('livemode', None),
        stripe_informational_capture_only = True,
        stripe_event_data=json.dumps(root_event)
    )

    if (cur_transaction.sandbox_hook is True and cur_transaction.stripe_livemode is True) or \
       (cur_transaction.sandbox_hook is False and cur_transaction.stripe_livemode is False):
        cur_transaction.sandbox_mismatch = True
        if -1 not in sandbox_warnings or sandbox_warnings[-1] < time.time() - 900.0:
            log_event(f"sandbox/livemode mismatch for stripe event for ROOT customer, event {cur_transaction.stripe_event_id}: stripe_livemode={cur_transaction.stripe_livemode}, sandbox_hook={cur_transaction.sandbox_hook}", severity=4)
            sandbox_warnings[-1] = time.time()

    stripe_billing_details = None
    transaction_description_list: list[str] = []
    stripe_nested_object = None
    exception_notes = []
    exception_severity = 0
    stripe_customer_id = None

    stripe_nested_data = root_event.get('data', None)
    if stripe_nested_data:
        stripe_nested_object = stripe_nested_data.get('object', None)
        stripe_nested_object_type = stripe_nested_object.get('object', None)
        if stripe_nested_object_type in ('pvf_customer',):
            cur_transaction.stripe_customer_id = stripe_nested_object.get('id', None)
            cur_transaction.stripe_customer_email = stripe_nested_object.get('email', None)
            cur_transaction.stripe_charge_name = stripe_nested_object.get('name', None)
            cur_transaction.stripe_charge_phone = stripe_nested_object.get('phone', None)
        elif stripe_nested_object_type in ('payment_method',):
            cur_transaction.stripe_customer_id = stripe_nested_object.get('pvf_customer', None)
            stripe_billing_details = stripe_nested_object.get('billing_details', None)
            if stripe_billing_details is not None:
                cur_transaction.stripe_customer_email = stripe_billing_details.get('email', None)
                cur_transaction.stripe_charge_name = stripe_billing_details.get('name', None)
                cur_transaction.stripe_charge_phone = stripe_billing_details.get('phone', None)
        elif stripe_nested_object_type in ('subscription',):
            cur_transaction.stripe_subscription_id = stripe_nested_object.get('id', None)
            cur_transaction.stripe_customer_id = stripe_nested_object.get('pvf_customer', None)
            sub_items_list_package = stripe_nested_object.get('items', None)
            if sub_items_list_package:
                for line_num, sub_item in enumerate(sub_items_list_package.get('data', [])):
                    price_info = sub_item.get('price', None)
                    if price_info and cur_transaction.stripe_product is None:
                        cur_transaction.stripe_product = price_info.get('product', None)
        elif stripe_nested_object_type in ('payment_intent',):
            cur_transaction.stripe_customer_id = stripe_nested_object.get('pvf_customer', None)
            cur_transaction.stripe_payment_intent_id = stripe_nested_object.get('id', None)
            cur_transaction.stripe_invoice_id = stripe_nested_object.get('invoice', None)
            canceled_at = stripe_nested_object.get('canceled_at', None)
            cancellation_reason = stripe_nested_object.get('cancellation_reason', None)
            if canceled_at is not None or cancellation_reason is not None:
                cur_transaction.stripe_cancellation_info = f'{canceled_at} - {cancellation_reason}'
        elif stripe_nested_object_type in ('charge',):
            cur_transaction.stripe_customer_id = stripe_nested_object.get('pvf_customer', None)
            cur_transaction.stripe_invoice_id = stripe_nested_object.get('invoice', None)
            cur_transaction.stripe_receipt_url = stripe_nested_object.get('receipt_url', None)
            stripe_billing_details = stripe_nested_object.get('billing_details', None)
            cur_transaction.stripe_payment_intent_id = stripe_nested_object.get('payment_intent', None)
            if stripe_billing_details is not None:
                cur_transaction.stripe_customer_email = stripe_billing_details.get('email', None)
                cur_transaction.stripe_charge_name = stripe_billing_details.get('name', None)
                cur_transaction.stripe_charge_phone = stripe_billing_details.get('phone', None)
        elif stripe_nested_object_type in ('checkout.session',):
            cur_transaction.stripe_customer_id = stripe_nested_object.get('pvf_customer', None)
            cur_transaction.stripe_checkout_session_id = stripe_nested_object.get('id', None)
            cur_transaction.stripe_payment_link = stripe_nested_object.get('payment_link', None)
            cur_transaction.stripe_subscription_id = stripe_nested_object.get('subscription', None)
            stripe_customer_details = stripe_nested_object.get('customer_details', None)
            cur_transaction.stripe_payment_intent_id = stripe_nested_object.get('payment_intent', None)
            cur_transaction.stripe_invoice_id = stripe_nested_object.get('invoice', None)
            if stripe_customer_details is not None:
                cur_transaction.stripe_customer_email = stripe_customer_details.get('email', None)
                cur_transaction.stripe_charge_name = stripe_customer_details.get('name', None)
                cur_transaction.stripe_charge_phone = stripe_customer_details.get('phone', None)
        elif stripe_nested_object_type in ('invoice',):
            cur_transaction.stripe_customer_id = stripe_nested_object.get('pvf_customer', None)
            cur_transaction.stripe_customer_email = stripe_nested_object.get('customer_email', None)
            cur_transaction.stripe_charge_name = stripe_nested_object.get('customer_name', None)
            cur_transaction.stripe_charge_phone = stripe_nested_object.get('customer_phone', None)
            cur_transaction.stripe_subscription_id = stripe_nested_object.get('subscription', None)
            cur_transaction.stripe_invoice_id = stripe_nested_object.get('id', None)
            cur_transaction.stripe_invoice_pdf_url = stripe_nested_object.get('invoice_pdf', None)

            invoice_lines_list_package = stripe_nested_object.get('lines', None)
            if invoice_lines_list_package and root_event_type == 'invoice.payment_succeeded':
                for line_num, invoice_line in enumerate(invoice_lines_list_package.get('data', [])):
                    price_info = invoice_line.get('price', None)
                    cur_transaction.stripe_currency = invoice_line.get('currency', 'usd')
                    cur_description = invoice_line.get('description', 'na')
                    transaction_description_list.append(cur_description)
                    cur_line_item_amount = invoice_line.get('amount', 0.0) / 100.0
                    cur_transaction.stripe_transaction_amount += cur_line_item_amount
                    discount_amounts = invoice_line.get('discount_amounts', [])
                    for discount_amount in discount_amounts:
                        cur_transaction.stripe_discount_amount += discount_amount.get('amount', 0.0) / 100.0

                    trial_period_days = 0
                    if price_info:
                        cur_transaction.stripe_informational_capture_only = False
                        lookup_key = price_info.get('lookup_key', None)
                        if cur_transaction.stripe_lookup_key is None: cur_transaction.stripe_lookup_key = lookup_key
                        product_key = price_info.get('product', None)
                        if cur_transaction.stripe_product is None: cur_transaction.stripe_product = product_key
                        if cur_transaction.stripe_subscription_id is None: cur_transaction.stripe_subscription_id = price_info.get('subscription', None)
                        type_recurring = price_info.get('type', None)
                        if type_recurring == 'one_time':
                            log_event(f'One-time purchase detected for invoice line {line_num} with amount {cur_line_item_amount}')
                        else:
                            recurring_info = price_info.get('recurring', None) if type_recurring == 'recurring' else None
                            interval_count = recurring_info.get('interval_count', 1) if recurring_info else 1
                            transaction_units = recurring_info.get('interval', 'month') if recurring_info else 'month'
                            if transaction_units in ('year', 'years'):
                                cur_transaction.transaction_add_months_count += interval_count * 12
                            elif transaction_units in ('day', 'days'):
                                cur_transaction.transaction_add_days_count += interval_count
                            else:
                                cur_transaction.transaction_add_months_count += interval_count

                            line_trial_period_days = recurring_info.get('trial_period_days', 0) if recurring_info else 0
                            trial_period_days += line_trial_period_days
                            cur_transaction.transaction_add_days_count += line_trial_period_days

                if cur_transaction.stripe_transaction_amount > 0 and cur_transaction.transaction_add_months_count == 0 and cur_transaction.transaction_add_days_count == 0:
                    exception_notes.append(f'Unmatched invoice line item {line_num} - subscription not affected')
                    exception_severity = max(exception_severity, 3)
                    result_flag = False
        else:
            stripe_customer_id = stripe_nested_object.get('pvf_customer', None)

    if stripe_customer_id is None:
        stripe_customer_id = cur_transaction.stripe_customer_id

    if cur_transaction.stripe_transaction_amount > 0 and cur_transaction.stripe_informational_capture_only is False:
        customer_info = PvfCustomer.get_customer_by_email_system(session=session, customer_email=cur_transaction.stripe_customer_email, clear_lock=False)
        if customer_info is None and stripe_customer_id not in (None, ""):
            customer_info = PvfCustomer.get_customer_by_account_system(session=session, customer_account=stripe_customer_id, clear_lock=False)
        if customer_info is None:
            user_info = PvfUser.get_user_by_email_system(session=session, email=cur_transaction.stripe_customer_email, clear_lock=False)
            if user_info is not None:
                customer_info = PvfCustomer.get_customer_by_id_system(session=session, id=user_info.customer_id, clear_lock=False)
        if customer_info and customer_info.customer_account in (None, ""):
            customer_info = PvfCustomer.get_customer_by_id_system(session=session, id=customer_info.id, clear_lock=False)
            customer_info.customer_account = stripe_customer_id
            customer_info.update_customer_system(session=session, clear_lock=False)

        if customer_info is None:
            cur_transaction.related_log_id = log_event(f"??? unknown primary customer for payment event transaction {root_event_id} email {cur_transaction.stripe_customer_email} amount {cur_transaction.stripe_transaction_amount}",
                                       severity=5, stripe_customer_email=cur_transaction.stripe_customer_email, stripe_event_id=root_event_id)
            exception_notes.append(f'PvfCustomer not found via id or email ({cur_transaction.related_log_id}); subscription cannot be processed')
            exception_severity = max(exception_severity, 3)
            result_flag = False
        elif customer_info.customer_account != stripe_customer_id:
            exception_notes.append(f"Warning: PvfCustomer account {customer_info.id}:{customer_info.customer_email} - {customer_info.customer_account} does not match stripe transaction {stripe_customer_id}; tokens ASSIGNED with email match")
            exception_severity = max(exception_severity, 1)

        if customer_info is not None:
            cur_transaction.primary_customer_id = customer_info.id

            new_subscription_trans = PvfSubscriberTransaction(customer_id=customer_info.id,
                                                    financial_event_row_id=cur_transaction.id,
                                                    livemode_flag=cur_transaction.stripe_livemode,
                                                    sandbox_mismatch=cur_transaction.sandbox_mismatch,
                                                    financial_event_source='stripe',
                                                    financial_event_type=cur_transaction.stripe_event_type,
                                                    financial_transaction_amount=cur_transaction.stripe_transaction_amount,
                                                    financial_transaction_currency=cur_transaction.stripe_currency,
                                                    financial_discount_amount=cur_transaction.stripe_discount_amount,
                                                    transaction_type=PvfSubscriberTransactionType.purchase,
                                                    transaction_units=cur_transaction.transaction_units,
                                                    transaction_month_count=cur_transaction.transaction_add_months_count,
                                                    transaction_day_count=cur_transaction.transaction_add_days_count,
                                                    transaction_description='; '.join(transaction_description_list)
                                                    )
            cur_transaction.latest_transaction_id = new_subscription_trans.create_subscriber_transaction_system(session=session, usr_context=None, clear_lock=False)

    cur_transaction.exception_message = '; '.join(exception_notes) if len(exception_notes) else None
    cur_transaction.exception_severity = exception_severity
    cur_transaction.create_stripe_event_system(session=session, clear_lock=False)

    return result_flag
