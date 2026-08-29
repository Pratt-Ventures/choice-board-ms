from __future__ import annotations
from typing import Any
from enum import Enum
import json
import httpx
from sqlmodel import Session

from .utils_show import print_hierarchy
from .log_event import log_event
from ..db.models.customer_user import PvfUserContext
from ..config.pvf_config_settings import pvf_settings as settings


def _normalize_email_type(email_type: str | Enum) -> str:
    if isinstance(email_type, Enum):
        return str(email_type.value)
    return str(email_type)


def _sendgrid_template_map() -> dict[str, str]:
    return settings.SENDGRID_TEMPLATE_IDS or {}


def get_valid_sendgrid_template_names() -> list[str]:
    return sorted(name for name, sg_id in _sendgrid_template_map().items() if name and sg_id)


def _lookup_sendgrid_template_id(email_type_name: str) -> str | None:
    sg_template_id = _sendgrid_template_map().get(email_type_name)
    if not sg_template_id:
        return None
    return sg_template_id


async def request_sendgrid_delivery(session: Session,
                              usr_context: PvfUserContext,
                              destination_email: str,
                              email_type: str | Enum,
                              email_params: dict[str, Any],
                              ) -> str:
    email_type_name = _normalize_email_type(email_type)
    sg_template_id = _lookup_sendgrid_template_id(email_type_name)
    if sg_template_id is None:
        log_id = log_event(f'Unsupported template requested {email_type_name} for outbound email to {destination_email} - requested aborted',
                  severity=4, usr_context=usr_context)
        return f"Unsupported template requested {email_type_name} {destination_email} ({log_id})"

    if settings.PYTEST_ACTIVE:
        log_event("request_sendgrid_delivery: temporarily disabled for testing", severity=0,
                  usr_context=usr_context,
                email_params=email_params)
        return ""

    headers = {'Content-Type': 'application/json',
                'Authorization': f'Bearer {settings.SG_KEY}'}

    request_payload = {}
    request_payload['from'] = {'email': settings.SG_FROM_EMAIL}
    request_payload['personalizations'] = [{}]
    request_payload['personalizations'][0]['to'] = [{"email": destination_email}]
    request_payload['personalizations'][0]['dynamic_template_data'] = email_params
    request_payload['template_id'] = sg_template_id

    data_req = json.dumps(request_payload)

    if settings.SENDGRID_CONSOLE_JSON_REQUEST:
        print_hierarchy(dict(sending_email_type_via_sendgrid=email_type_name, request_and_personalization_payload=request_payload))
        print('\n\nrequest_sendgrid_delivery: json request trace:\n', data_req, '\n\n')

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(settings.SG_API_ENDPOINT,
                                         data=data_req, headers=headers)
    except Exception as ex_info:
        response = None
        log_id = log_event(f'request_sendgrid_delivery failed - {email_type_name} - {destination_email} to {settings.SG_API_ENDPOINT} failed {ex_info}',
                  severity = 3,
                  ex_info=ex_info,
                  usr_context=usr_context,
                  )
        failure_reason = f'email delivery attempt failued {ex_info} ({log_id})'
        return failure_reason

    message = None
    status_code = None

    if response.status_code not in (200, 202):
        try:
            message = response.json().get('message', response.text)
            status_code = response.status_code
            failure_reason = f'Email service delivery attempt {email_type_name} - {destination_email} to {settings.SG_API_ENDPOINT} failed: {status_code}. Message: {message}.'
        except ValueError as predictions_response:
            failure_reason = f'Email service delivery attempt {email_type_name} - {destination_email} to {settings.SG_API_ENDPOINT} failed - response != 200 - ValueError: {predictions_response.reason} - possible incorrect target host'
        except Exception as ex_info:
            failure_reason = f'Email service delivery attempt {email_type_name} - {destination_email} to {settings.SG_API_ENDPOINT} failed - response != 200 - {ex_info}'

        log_id = log_event(f'{failure_reason}', severity = 3, usr_context=usr_context)
        return failure_reason

    if len(response.content) > 0:
        response_dict = json.loads(response.content)
    else:
        response_dict = dict()

    if settings.SENDGRID_CONSOLE_JSON_RESULT:
        print('\n\nrequest_sendgrid_delivery: json result trace:\n', response.content, '\n\n')

    return ""
