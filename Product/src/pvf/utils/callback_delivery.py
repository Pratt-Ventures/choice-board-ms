"""Generic webhook/callback delivery machinery for the watcher process.

Delivers PvfApiWebInvocationEvent rows to their configuration's webhook_endpoint, signed
with the configuration's shared secret. Application-specific behavior is bound through
hooks registered on the PvfInvocation (see pvf.pvf_invocation.PvfHookRegistry):

  - webhook_payload_builders[web_hook_type](session, event) -> dict
  - webhook_readiness_predicates[web_hook_type](session, event) -> bool
    (events whose type has no registered predicate are always considered ready)
"""
from datetime import datetime
from typing import Union

import requests
from sqlmodel import Session, select, and_

from ..config.pvf_config_settings import pvf_settings as settings
from ..db.models.api_access_configuration import (
    PvfApiAccessConfiguration,
    PvfApiWebInvocationEvent,
    PvfWebHookStatus,
)
from ..db.models.customer_user import PvfCustomer, PvfUser, PvfUserContext
from ..bindings.pvf_invocation import get_hooks
from .log_event import log_event
from .utils_general import get_hex_hash_from_args
from .utils_show import show_vars
from .webcalls_and_hooks import (
    APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY,
    APPLICATION_API_HEADER_SIGNATURE,
    WebrequestSignature,
)


def check_for_callbacks_ready(session: Session) -> Union[list[PvfApiWebInvocationEvent], None]:
    """Select the next callback event ready for delivery.

    Marks events that exhausted the maximum delivery attempts as failed, honors the
    configured retry delays, consults the registered readiness predicate for the
    event's webhook type, and transitions the selected event to 'trying'.
    """
    callback_candidates = session.exec(
        select(PvfApiWebInvocationEvent).where(and_(PvfApiWebInvocationEvent.web_hook_status == PvfWebHookStatus.pending.value))
    ).all()
    selected_candidate = None

    # mark candidates that exceeded the maximum delivery attempts as failed
    for cur_candidate in callback_candidates:
        if cur_candidate.web_hook_delivery_attempts >= settings.WATCHER_PROCESS_API_CALLBACKS_MAXIMUM_ATTEMPTS:
            cur_candidate.web_hook_status = PvfWebHookStatus.failed
            cur_candidate.web_hook_failure_reason = "Maximum delivery attempts exceeded in callback_delivery:check_for_callbacks_ready"
            session.add(cur_candidate)

    hooks = get_hooks()
    for cur_candidate in callback_candidates:
        if cur_candidate.web_hook_status != PvfWebHookStatus.pending.value:
            continue
        # delta time defaults to 1 minute if last_delivery_attempt_time is None
        eff_last_time = cur_candidate.last_delivery_attempt_time if cur_candidate.last_delivery_attempt_time is not None else cur_candidate.modify_date
        delta_time = (datetime.now() - eff_last_time).total_seconds() // 60
        retry_delays = settings.WATCHER_PROCESS_API_CALLBACKS_RETRY_DELAYS
        if delta_time < retry_delays[min(cur_candidate.web_hook_delivery_attempts, len(retry_delays) - 1)]:
            continue
        readiness = hooks.webhook_readiness_predicates.get(cur_candidate.web_hook_type)
        if readiness is not None and not readiness(session=session, event=cur_candidate):
            continue
        cur_candidate.web_hook_delivery_attempts += 1
        cur_candidate.web_hook_status = PvfWebHookStatus.trying.value
        cur_candidate.last_delivery_attempt_time = datetime.now()
        session.add(cur_candidate)
        selected_candidate = cur_candidate
        break
    session.commit()
    if selected_candidate is not None:
        session.refresh(selected_candidate)
        session.close()
        return [selected_candidate]
    return None


def get_callback_proxy_usr_context(session: Session, api_event_info: PvfApiWebInvocationEvent) -> Union[PvfUserContext, None]:
    """Build a limited-proxy usr_context for the event's API access configuration."""
    api_config = session.exec(select(PvfApiAccessConfiguration).where(PvfApiAccessConfiguration.id == api_event_info.api_configuration_id)).first()
    if api_config is None:
        session.close()
        log_event(f"callback_delivery:get_callback_proxy_usr_context: API Configuration not found for event {api_event_info.unique_tracking_id} - config id {api_event_info.api_configuration_id}", severity=3)
        return None

    proxy_usr_context = PvfUserContext(limited_proxy=True,
                                    sess_customer=session.exec(select(PvfCustomer).where(PvfCustomer.id == api_config.customer_id)).one_or_none(),
                                    sess_user=session.exec(select(PvfUser).where(PvfUser.id == api_config.user_id)).one_or_none(),
                                    sess_api_access_config=api_config, url_path=f'callback {api_event_info.unique_tracking_id} - {api_config.webhook_endpoint}')
    session.close()
    return proxy_usr_context


def perform_callback(session: Session, proxy_usr_context: PvfUserContext, api_event: PvfApiWebInvocationEvent) -> Union[str, None]:
    """Build, sign, and deliver one callback payload. Returns None on success, else an error message."""
    hooks = get_hooks()
    payload_builder = hooks.webhook_payload_builders.get(api_event.web_hook_type)
    if payload_builder is None:
        api_result = f"callback_delivery:perform_callback: API event {api_event.unique_tracking_id} has no registered payload builder for web hook type {api_event.web_hook_type}."
        log_event(api_result, severity=3)
        return api_result

    try:
        result_payload = payload_builder(session=session, event=api_event)
    except Exception as ex_info:
        api_result = f"callback_delivery:perform_callback: payload builder for {api_event.web_hook_type} raised {type(ex_info).__name__}: {ex_info}"
        log_event(api_result, usr_context=proxy_usr_context, severity=3, ex_info=ex_info)
        PvfApiWebInvocationEvent.set_web_invocation_event_status_by_unique_tracking_id(session=session, usr_context=proxy_usr_context,
                                                                                    new_status=PvfWebHookStatus.failed,
                                                                                    unique_tracking_id=api_event.unique_tracking_id,
                                                                                    web_hook_failure_reason=api_result)
        return api_result

    import json
    result_payload_json = json.dumps(result_payload)

    signed_header = WebrequestSignature.generate_signed_payload_header(result_payload_json,
                                                                       secret=proxy_usr_context.sess_api_access_config.shared_secret,
                                                                       )
    callback_auth_key = f'cb-{get_hex_hash_from_args(settings.CUSTOMER_API_OUTBOUND_HASH_KEY, proxy_usr_context.sess_api_access_config.authentication_key_id, hash_length=32)}'

    headers = {'content-type': 'application/json',
               APPLICATION_API_HEADER_RQ_AUTHENTICATION_KEY: callback_auth_key,
               APPLICATION_API_HEADER_SIGNATURE: signed_header, }

    if settings.WATCHER_PROCESS_SHOW_API_CALLBACKS:
        show_vars('API callback', unique_tracking_id=api_event.unique_tracking_id,
                  request_authentication_hdr=callback_auth_key,
                  request_signature_hdr=signed_header)

    failure_reason = None
    api_response = None
    try:
        api_response = requests.post(proxy_usr_context.sess_api_access_config.webhook_endpoint,
                                     data=result_payload_json,
                                     headers=headers)
    except Exception as ex_info:
        failure_reason = f'API: outbound request {api_event.unique_tracking_id} to {proxy_usr_context.sess_api_access_config.webhook_endpoint} failed {ex_info}'
        log_event(failure_reason,
                  severity=3,
                  remote_ip=proxy_usr_context.sess_api_access_config.webhook_endpoint,
                  ex_info=ex_info,
                  usr_context=proxy_usr_context,
                  module_type=settings.WATCHER_PROCESS_API_CALLBACKS_TAG,
                  request_id=api_event.unique_tracking_id)

    response_dict = None
    if api_response is not None and api_response.status_code != 200:
        status_code = api_response.status_code
        message = None
        reason = None
        try:
            message = api_response.json().get('message', api_response.text)
            reason = api_response.reason
            failure_reason = f'API: outbound request {api_event.unique_tracking_id} to {proxy_usr_context.sess_api_access_config.webhook_endpoint} failed {status_code} - {reason} - message {message}.'
        except ValueError:
            failure_reason = f'API: outbound request {api_event.unique_tracking_id} to {proxy_usr_context.sess_api_access_config.webhook_endpoint} failed {status_code} - ValueError - {reason} - message{message}.'
        except Exception as ex_info:
            failure_reason = f'API: outbound request {api_event.unique_tracking_id} to {proxy_usr_context.sess_api_access_config.webhook_endpoint} failed {status_code} - {ex_info}'

        log_id = log_event(failure_reason,
                           severity=3,
                           usr_context=proxy_usr_context, module_type=settings.WATCHER_PROCESS_API_CALLBACKS_TAG,
                           request_id=api_event.unique_tracking_id)
        failure_reason += f' ({log_id})'
    elif api_response is not None:
        try:
            response_dict = json.loads(api_response.content)
        except ValueError:
            response_dict = api_response.text
        if settings.WATCHER_PROCESS_SHOW_API_CALLBACKS:
            show_vars('API callback response', unique_tracking_id=api_event.unique_tracking_id,
                      status_code=api_response.status_code,
                      response_info=response_dict,
                      success=True)

    if failure_reason in ('', None):
        if isinstance(response_dict, dict):
            result_fields = [f'{k}={v}' for k, v in response_dict.items()]
            result_message = '; '.join(result_fields)
        else:
            result_message = str(response_dict)
        PvfApiWebInvocationEvent.set_web_invocation_event_status_by_unique_tracking_id(session=session,
                                                                                    usr_context=proxy_usr_context,
                                                                                    new_status=PvfWebHookStatus.delivered,
                                                                                    unique_tracking_id=api_event.unique_tracking_id,
                                                                                    web_hook_failure_reason=f'Results(200): {result_message}',)
        return None

    if api_event.web_hook_delivery_attempts < settings.WATCHER_PROCESS_API_CALLBACKS_MAXIMUM_ATTEMPTS:
        new_status = PvfWebHookStatus.pending
    else:
        new_status = PvfWebHookStatus.failed
    # if we have a failure reason, but we haven't exceeded the maximum delivery attempts, then we will retry
    PvfApiWebInvocationEvent.set_web_invocation_event_status_by_unique_tracking_id(session=session,
                                                                                usr_context=proxy_usr_context,
                                                                                new_status=new_status,
                                                                                unique_tracking_id=api_event.unique_tracking_id,
                                                                                web_hook_failure_reason=failure_reason)
    return failure_reason
