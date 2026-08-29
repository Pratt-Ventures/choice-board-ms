# outbound_mail_smtp_jinja - provides support for sending mail using SMTP with html/txt/subject
# templates with Jinja2 -- requires poetry add emails[jinja] or equivalent

from __future__ import annotations
from typing import Any
from enum import Enum
from pathlib import Path
import emails
from emails.template import JinjaTemplate
from jinja2 import Environment, FileSystemLoader
from sqlmodel import Session

from .log_event import log_event
from ..db.models.customer_user import PvfUserContext

from ..config.pvf_config_settings import pvf_settings as settings

# note: local smtp/jinja needs poetry add emails[jinja]

# helper logic for direct outbound emails from company SMTP server - SMTP-JINJA mode
# Templates use {% extends %}; Jinja needs a FileSystemLoader (from_string alone is not enough).
_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]  # utils -> pvf -> src -> workspace root
_SHARED_TEMPLATE_BASES = frozenset({"email_visual_theme"})
_SUBJECT_SUFFIX = "_subject_line.txt"
_jinja_env: Environment | None = None
_jinja_cache_dir: Path | None = None
_jinja_template_cache: dict[str, dict[str, JinjaTemplate]] = {}


def _normalize_email_type(email_type: str | Enum) -> str:
    if isinstance(email_type, Enum):
        return str(email_type.value)
    return str(email_type)


def _email_templates_dir() -> Path:
    configured = Path(settings.DIRECT_TEMPLATE_DIRECTORY)
    if configured.is_absolute():
        return configured.resolve()
    cwd_candidate = (Path.cwd() / configured).resolve()
    if cwd_candidate.is_dir():
        return cwd_candidate
    peer = (_WORKSPACE_ROOT / "email_templates").resolve()
    if peer.is_dir():
        return peer
    return cwd_candidate


def _discover_sendable_template_names(templates_dir: Path) -> list[str]:
    if not templates_dir.is_dir():
        return []
    html_names = {path.stem for path in templates_dir.glob("*.html")}
    subject_names = {
        path.name[:-len(_SUBJECT_SUFFIX)]
        for path in templates_dir.glob(f"*{_SUBJECT_SUFFIX}")
    }
    return sorted((html_names & subject_names) - _SHARED_TEMPLATE_BASES)


def _load_jinja_template(templates_dir: Path, filename: str, environment: Environment) -> JinjaTemplate:
    return JinjaTemplate(
        (templates_dir / filename).read_text(encoding="utf-8"),
        environment=environment,
    )


def _ensure_jinja_templates_loaded() -> dict[str, dict[str, JinjaTemplate]]:
    global _jinja_env, _jinja_cache_dir, _jinja_template_cache
    templates_dir = _email_templates_dir()
    if _jinja_env is not None and _jinja_cache_dir == templates_dir:
        return _jinja_template_cache

    templates_dir_str = str(templates_dir)
    _jinja_env = Environment(loader=FileSystemLoader(templates_dir_str))
    _jinja_cache_dir = templates_dir
    loaded: dict[str, dict[str, JinjaTemplate]] = {}
    for name in _discover_sendable_template_names(templates_dir):
        entry: dict[str, JinjaTemplate] = {
            "html": _load_jinja_template(templates_dir, f"{name}.html", _jinja_env),
            "subject": _load_jinja_template(templates_dir, f"{name}{_SUBJECT_SUFFIX}", _jinja_env),
        }
        text_path = templates_dir / f"{name}.txt"
        if text_path.exists():
            entry["text"] = _load_jinja_template(templates_dir, f"{name}.txt", _jinja_env)
        loaded[name] = entry
    _jinja_template_cache = loaded
    return _jinja_template_cache


def _get_jinja_env() -> Environment:
    _ensure_jinja_templates_loaded()
    assert _jinja_env is not None
    return _jinja_env


def get_valid_jinja_template_names() -> list[str]:
    return sorted(_ensure_jinja_templates_loaded().keys())


def load_template(filename: str) -> JinjaTemplate:
    template_path = _email_templates_dir() / filename
    return JinjaTemplate(
        template_path.read_text(encoding="utf-8"),
        environment=_get_jinja_env(),
    )


def send_template_email(
    *,
    usr_context: PvfUserContext,
    to: str,
    template_name: str,
    parameters: dict[str, Any],
) -> None:
    cache = _ensure_jinja_templates_loaded()
    bundled = cache.get(template_name)
    if bundled is None:
        log_event(f"Unsupported template requested {template_name} for outbound email to {to} - requested aborted",
                  severity=4, usr_context=usr_context)
        return

    message = emails.html(
        subject=bundled["subject"],
        html=bundled["html"],
        text=bundled.get("text"),
        mail_from=(settings.DIRECT_EMAIL_FROM_NAME, settings.DIRECT_EMAIL_FROM_ADDRESS),
    )

    # emails SMTPBackend: ssl and tls are mutually exclusive.
    # 465 = implicit SSL (SMTP_SSL); 587 = plain + STARTTLS (tls=True).
    use_ssl = bool(settings.DIRECT_EMAIL_SMTP_SSL)
    use_tls = bool(settings.DIRECT_EMAIL_SMTP_TLS)
    if use_ssl and use_tls:
        if int(settings.DIRECT_EMAIL_SMTP_PORT) == 465:
            use_tls = False
        else:
            use_ssl = False
    elif not use_ssl and not use_tls:
        use_ssl = int(settings.DIRECT_EMAIL_SMTP_PORT) == 465
        use_tls = int(settings.DIRECT_EMAIL_SMTP_PORT) == 587

    response = message.send(
        to=to,
        render=parameters,
        smtp={
            "host": settings.DIRECT_EMAIL_SMTP_HOST,
            "port": settings.DIRECT_EMAIL_SMTP_PORT,
            "ssl": use_ssl,
            "tls": use_tls,
            "user": settings.DIRECT_EMAIL_SMTP_USER,
            "password": settings.DIRECT_EMAIL_SMTP_PASSWORD,
            "timeout": settings.DIRECT_EMAIL_SMTP_TIMEOUT,
        },
    )

    if not response.success:
        log_event(f"Email failed: status={response.status_code}, message={response.status_text}, error={response.error}", severity=5,
                  usr_context=usr_context, email_send_parameters=parameters,
                raise_exception=RuntimeError(f"Email failed: status={response.status_code}",
                                             f"message={response.status_text}, error={response.error}"))
    return


async def request_smtp_jinja_delivery(session: Session,
                                     usr_context: PvfUserContext,
                                     destination_email: str,
                                     email_type: str | Enum,
                                     email_params: dict[str, Any],
                                     ) -> str:
    email_type_name = _normalize_email_type(email_type)
    if email_type_name not in _ensure_jinja_templates_loaded():
        log_id = log_event(f"Unsupported template requested {email_type_name} for outbound email to {destination_email} - requested aborted",
                  severity=4, usr_context=usr_context)
        return f"Unsupported template requested {email_type_name} {destination_email} ({log_id})"

    if settings.PYTEST_ACTIVE:
        log_event("request_smtp_jinja_delivery: temporarily disabled for testing", severity=0,
                  usr_context=usr_context,
                email_params=email_params)
        return ""

    result = send_template_email(usr_context=usr_context,
                                 to=destination_email,
                                 template_name=email_type_name,
                                 parameters=email_params)
    return result
