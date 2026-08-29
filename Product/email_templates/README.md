# Outbound email templates (SMTP + Jinja)

HTML templates for `USE_EMAIL_SERVICE=SMTP-JINJA`. Directory path: `DIRECT_TEMPLATE_DIRECTORY` (default `../email_templates` from the process working directory).

## Layout

| File | Template name |
|------|----------------|
| `email_visual_theme.html` / `.txt` | Shared shell (not sent alone) |
| `password_reset.html` / `.txt` | `password_reset` |
| `customer_activation_self.html` / `.txt` | `customer_activation_self` |
| `customer_activation_admin.html` / `.txt` | `customer_activation_admin` |
| `customer_activation_admin_activated.html` / `.txt` | `customer_activation_admin_activated` |
| `new_user_welcome.html` / `.txt` | `new_user_welcome` |
| `share_project_vote.html` / `.txt` | `share_project_vote` |
| `share_project_vote_view.html` / `.txt` | `share_project_vote_view` |
| `share_project_report.html` / `.txt` | `share_project_report` |
| `resending_invitation.html` / `.txt` | `resending_invitation` |
| `magic_access_key.html` / `.txt` | `magic_access_key` |
| `login_2fa.html` / `.txt` | `login_2fa` |

Template file name = sendable stem + `.html` (HTML part) or `.txt` (plain-text fallback).
Subject line: stem + `_subject_line.txt` (single-line Jinja; same context).
A sendable Jinja name is any stem that has both `{name}.html` and `{name}_subject_line.txt` (text part optional). Shared bases such as `email_visual_theme` are excluded. SendGrid names come from `SENDGRID_TEMPLATE_IDS` in the env, not from the app enum.
HTML/text body formats use the same Jinja context and extend their respective theme shell.

## Theme

`email_visual_theme.html` matches the Power Choice Pro style guide:

- Primary `#4059d8`, secondary `#6f7ff2`, navy header gradient
- Canvas `#f4f6fa`, surface white, ink `#152033`, muted `#667085`
- Table-based layout for email clients; Arial/Helvetica stack (web fonts unreliable in mail)

Child templates:

```jinja
{% extends "email_visual_theme.html" %}
{% block title %}…{% endblock %}
{% block body %}…{% endblock %}
{% block cta %}…{% endblock %}
```

## Context fields

`send_outbound_mail` always injects when known (does not overwrite caller-supplied keys except `remote_ip` / `email_type`):

- `remote_ip`, `email_type`
- `user_name`, `user_email`, `user_phone` (session user — often the **sender**; empty if unauthenticated)
- `customer_name`, `customer_email`, `customer_phone`
- `project_name` (when `project_id` is present)
- `brand_name` — `EMAIL_BRAND_NAME` (default `Power Choice Pro`)
- `support_email` — `EMAIL_SUPPORT_EMAIL` (empty default)
- `year` — current UTC year
- `app_base_url` — `APPLICATION_BASE_URL` without trailing slash
- `app_login_url` — `{app_base_url}/{APP_LOGIN_PATH}` (default path `login`)

Type-specific fields are documented in each template header comment.

## Terminology

Copy follows `docs_examples/terminology_dictionary.md` (Project, Option, Factor, Compare, Results, share types).

## Preview

```python
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("email_templates"),
    autoescape=select_autoescape(["html", "xml"]),
)
html = env.get_template("password_reset.html").render(
    user_name="Alex Rivera",
    user_email="alex@example.com",
    pw_token="AB12CD",
    pw_reset_url="https://app.example.com/forgot-password/AB12CD",
    brand_name="Power Choice Pro",
    year=2026,
)
Path("/tmp/preview_password_reset.html").write_text(html, encoding="utf-8")
```
