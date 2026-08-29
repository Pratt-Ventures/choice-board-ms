# Email template guidelines

How outbound mail templates are built, rendered, and maintained in this repo. Companion to `email_templates/README.md` and `AGENTS.md`.

These **are Jinja2 templates**. SMTP delivery loads them through `emails.template.JinjaTemplate` backed by a shared `jinja2.Environment` with a `FileSystemLoader` on the templates directory (`src/utils/outbound_mail_smtp_jinja.py`). `{% extends %}`, `{% block %}`, `{% if %}`, and filters such as `|default(...)` are first-class. A string-only Jinja environment is not enough: inheritance requires the filesystem loader.

SendGrid mode (`USE_EMAIL_SERVICE=SENDGRID`) does **not** render these files. It posts the same `email_params` dict as SendGrid `dynamic_template_data` to a remote template id. Keep field names aligned across both backends when a type exists in both.

---

## Pipeline

```
caller (auth / user_requests / app_shared_link_manage)
    → send_outbound_mail()          # outbound_mail_queue.py
        injects ambient context
        throttles per dest + per source IP
    → request_smtp_jinja_delivery() # SMTP-JINJA
        or request_sendgrid_delivery()
        → send_template_email()
            loads {name}_subject_line.txt
            loads {name}.html
            loads {name}.txt  (optional fallback)
            renders all three with the same parameters dict
            sends via SMTP
```

The template stem is a string. App callers still pass `OutboundEmailType` for expressiveness; mail utilities normalize `str | Enum` (use `.value` when an enum is passed) and then operate only on that string. Jinja allowed names come from files on disk (`{name}.html` + `{name}_subject_line.txt`; `{name}.txt` optional; shared bases such as `email_visual_theme` excluded). SendGrid allowed names come from `SENDGRID_TEMPLATE_IDS`. Adding a mail type means an enum member in the **app** plus template files (Jinja) and/or a dict entry (SendGrid).

Directory resolution (`DIRECT_TEMPLATE_DIRECTORY`, default `../email_templates` relative to cwd):

1. Absolute configured path, if set.
2. `cwd / configured` if that directory exists.
3. Workspace-root `email_templates/` (resolved from the utils module, two parents up from `src/utils`).
4. Otherwise the cwd-relative candidate (even if missing — load will fail loudly).

Non-prod sends are suppressed unless the destination domain is listed in `EMAIL_LOCAL_ALLOW_DOMAINS`. Pytest short-circuits both SMTP and SendGrid before a network call. Successful (or attempted) sends are logged on `EmailActivityLog` with `email_params` JSON.

---

## File layout

Each sendable type is a triple. The shared chrome is not sent alone.

| File | Role |
|------|------|
| `{stem}.html` | HTML body. Must `{% extends "email_visual_theme.html" %}`. |
| `{stem}.txt` | Plain-text fallback. Must `{% extends "email_visual_theme.txt" %}`. Optional on disk; if missing, SMTP sends HTML-only. Always ship it. |
| `{stem}_subject_line.txt` | Single-line subject. Same Jinja context. No HTML. |
| `email_visual_theme.html` / `.txt` | Shared shell: header, blocks, sign-off, footer. |

Current sendable stems (Jinja files on disk; app enum members share these values):

| Stem | Product purpose |
|------|-----------------|
| `password_reset` | Account security — reset link + one-time code |
| `customer_activation_self` | Self-signup — confirm email / activate workspace |
| `customer_activation_admin` | Admin-created workspace — still needs activation |
| `customer_activation_admin_activated` | Admin-created workspace — already active, sign in |
| `new_user_welcome` | Teammate added to an existing workspace |
| `share_project_vote` | Share: Compare |
| `share_project_vote_view` | Share: Compare & see mine |
| `share_project_report` | Share: Full results |
| `magic_access_key` | One-time share access verification |
| `login_2fa` | Supplemental email login code |

`not_set` is a log default, not a template.

---

## How a child template is built

HTML children fill theme blocks. Override only what the message needs; empty blocks collapse cleanly.

```jinja
{#
  OutboundEmailType.<stem>
  Fields: <caller-supplied>
  Session: <ambient from send_outbound_mail>
#}
{% extends "email_visual_theme.html" %}

{% block page_title %}…{% endblock %}
{% block preheader %}Inbox preview line.{% endblock %}
{% block header_kicker %}Short eyebrow in the navy header{% endblock %}

{% block eyebrow %}…badge…{% endblock %}
{% block title %}Hero heading{% endblock %}
{% block body %}Prose paragraphs.{% endblock %}
{% block cta %}Primary button table.{% endblock %}
{% block details %}Secondary facts, raw URL, codes.{% endblock %}
{% block signoff %}{% endblock %}
{% block footer_note %}{% endblock %}
```

Theme blocks (HTML unless noted):

| Block | Purpose |
|-------|---------|
| `page_title` | `<title>` (few clients show it) |
| `preheader` | Hidden preview text after the subject |
| `header_kicker` | Uppercase line under the brand name |
| `eyebrow` | Colored pill above the hero |
| `title` | H1 |
| `body` | Main copy |
| `cta_row` / `cta` | Primary action row / button contents |
| `details_row` / `details` | Fact box, codes, paste-able URL |
| `signoff` | “Sent on behalf of …” (theme default uses ambient customer/user) |
| `footer_note` | Legal / “ignore if unexpected” |
| `divider` | Plain-text rule only |

Keep HTML and `.txt` copy in lockstep: same facts, same links, same codes. Recipients and spam filters both use the text part.

Document required fields in the HTML `{# … #}` header comment. That comment is the contract for callers and for SendGrid dynamic data.

---

## Ambient variables

`send_outbound_mail` always writes these onto `email_params` before render. Callers must not rely on omitting them. Theme keys and `user_*` / `customer_*` are set only if the caller did not already supply the key (`_set_if_absent`). Queue-owned `remote_ip` and `email_type` are always overwritten.

### Always present

| Variable | Source | Notes |
|----------|--------|--------|
| `remote_ip` | `usr_context.remote_ip` | Request origin. Shown on password-reset. Always overwritten. |
| `email_type` | normalized template name | Template stem string. Always overwritten. |
| `user_name` | Session user `name`, else `""` | Often the **sender / inviter**, not the recipient. |
| `user_email` | Session user `email`, else `""` | Same caveat. Password-reset callers also set this to the account being reset (not overwritten). |
| `user_phone` | Session user `phone`, else `""` | Rarely used in copy. |
| `customer_name` | Session user's customer, else `""` | Workspace / company of the session user. |
| `customer_email` | Customer record, else `""` | |
| `customer_phone` | Customer record, else `""` | |
| `brand_name` | `settings.EMAIL_BRAND_NAME` | Default `Power Choice Pro`. Header / footer brand. |
| `support_email` | `settings.EMAIL_SUPPORT_EMAIL` | Footer mailto. Empty default hides the link. |
| `year` | UTC now (int) | Copyright line. |
| `app_base_url` | `settings.APPLICATION_BASE_URL` (no trailing slash) | App origin. |
| `app_login_url` | `{app_base_url}/{APP_LOGIN_PATH}` | Sign-in URL. Default path `login`. |

If a session user is present but the customer row cannot be loaded, **the mail is not sent**.

Unauthenticated / proxy contexts (self-signup, some share-key flows) get empty strings for the six user/customer fields. Branding, year, and app URLs are still injected. Templates must tolerate blanks (`{% if user_name %}`, `|default('…')`).

### Conditionally injected by the queue

| Variable | When |
|----------|------|
| `project_name` | `project_id` is in `email_params` and `project_name` was not already set. Loaded from `CustomerProject` (`project_title` or `project_tag`). Share callers usually pass `project_name` themselves (the share link name). |
| `local_override` | Non-prod only, when the destination matches `EMAIL_LOCAL_ALLOW_DOMAINS`. Debug, not for copy. |

---

## Type-specific fields (caller-supplied)

These come from `email_params=` at the call site. The queue does not invent them. New product mail will add more fields here — that is expected.

### `password_reset` — `src/api/auth.py`

| Field | Meaning |
|-------|---------|
| `user_email` | Account being reset (caller-supplied; queue will not overwrite) |
| `pw_token` | Short one-time code |
| `pw_reset_url` | Full UI URL including the token |

### `new_user_welcome` — `src/api/user_requests.py`

| Field | Meaning |
|-------|---------|
| `new_user_name` | Recipient |
| `new_user_phone` | Recipient phone on file |
| `added_by_name` / `added_by_email` | Inviting admin (usually same as ambient `user_*`) |

### `customer_activation_self` — self-registration

| Field | Meaning |
|-------|---------|
| `url_with_activation_code` | Full activation URL |
| `token_payload` | Raw token (available; HTML currently uses the full URL) |
| `new_customer_name` | New workspace name |
| `new_admin_name` | Recipient |
| `new_customer_email` / `new_admin_email` | Sign-in email (often the same value) |

Self-reg has no session user, so ambient `user_*` / `customer_*` are empty. Copy must use the `new_*` fields.

### `customer_activation_admin`

Same as self, plus `new_admin_pw` (temporary password). Ambient `user_*` is the **creating** system/admin, used as “set up by …”.

### `customer_activation_admin_activated`

| Field | Meaning |
|-------|---------|
| `url` | App base URL (sign-in), not an activation token |
| `new_customer_name`, `new_admin_name`, `new_customer_email`, `new_admin_email`, `new_admin_pw` | Same as admin-create |

### Share types — `src/pvf/api/share_link_manage.py`

`share_project_vote`, `share_project_vote_view`, `share_project_report`, and administrator `resending_invitation` share one param set:

| Field | Meaning |
|-------|---------|
| `shared_with_company` | Recipient org label |
| `shared_with_name` | Recipient name |
| `valid_duration` | Human string (“14 days”, “no time limit”, …) |
| `project_id` | Triggers ambient `project_name` lookup if name omitted |
| `project_name` | Display title (callers pass the share link name) |
| `security_note` | Access-mode explanation |
| `share_password_note` | Password-in-email vs password-separate copy |
| `magic_token` | Share token (URL already includes it) |
| `url_prefix` / `url_suffix` | Path pieces around the token |
| `url` | Full share URL (primary CTA) |
| `share_id` | Share row id (matching / activity) |
| `shared_type` | `vote` / `vote_view` / `report` (resend copy/CTA) |

Ambient `user_*` / `customer_*` are the **sharing** account, not the recipient.

### `magic_access_key`

| Field | Meaning |
|-------|---------|
| `url_with_magic_key` | Full verify-and-continue URL (`/share/{type}/{token}?key={access_magic_key}`) |
| `url_prefix` / `url_suffix` | Path pieces |
| `valid_duration` | Human expiry copy |
| `project_name` | Present on some paths, omitted on recipient-locked paths |
| `share_magic_token` | Share token |
| `access_magic_key` | One-time key (shown in the details box) |

Share-key sends often run under a limited proxy context; do not assume ambient user/customer names are populated.

### `login_2fa`

| Field | Meaning |
|-------|---------|
| `login_2fa_code` | One-time supplemental login code (never in the subject) |
| `valid_duration` | Human expiry copy (`LOGIN_2FA_VALIDITY_MESSAGE`) |

Sends under a limited proxy context. Hash the code before storage; do not persist plaintext.

### Extensibility

Other fields will appear as new mail use cases land (billing, digest, export ready, seat limits, etc.). Rules:

1. Add `OutboundEmailType.<stem> = '<stem>'` in the app domain.
2. Add the three files named after the stem; extend the theme; document fields in the HTML header comment. Jinja discovers sendable names from those files.
3. Pass only what that type needs in `email_params`. Reuse ambient names instead of inventing a second `sender_name`.
4. Guard every new field in the template (`{% if %}` / `|default`) so older call paths and SendGrid tests do not explode.
5. If SendGrid is still in play, add `template_code:sendgrid_id` to `SENDGRID_TEMPLATE_IDS` in the env. Mail modules do not validate against the app enum.
6. Prefer product language from `docs_examples/terminology_dictionary.md` (Project, Option, Factor, Compare, Results, share types, Workspace). Do not rename DB/JSON keys to match the glossary.

Known mismatch: `signup_confirm_activation` currently requests `OutboundEmailType.customer_activation`, which is **not** an enum member. New types must exist on the enum before any caller uses them.

---

## Maintenance checklist

When editing or adding a type:

1. Change HTML, text, and subject together. Preview both bodies.
2. Keep the `{# Fields: … #}` comment accurate.
3. Use `|default` and `{% if %}` — Jinja `StrictUndefined` is not enabled, but missing names still render empty and look broken.
4. Do not put passwords, magic keys, or reset tokens in the **subject**. Subjects are logged, previewed, and forwarded more freely than the body.
5. Escape assumption: the production `Environment` does **not** enable `select_autoescape`. Treat every interpolated value as untrusted. Prefer text in `{{ }}` (Jinja still HTML-escapes only if autoescape is on — it is not). Until autoescape is turned on, avoid interpolating user-controlled strings into HTML attributes without explicit `|e`. Enabling autoescape on the shared env is the durable fix; do it in `outbound_mail_smtp_jinja.py` and re-preview every template.
6. Do not add comments in committed templates except the header contract and theme notes. No leftover lorem.
7. Copy review: terminology dictionary + existing tone (direct, calm, no MCDA jargon).
8. After behavior changes, cover the send path in the matching `src/tests/` module (throttling, unauth, tenancy, params present). Mail is not delivered under `PYTEST_ACTIVE`; assert on `EmailActivityLog` / queued params.

Local HTML preview (does not send):

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

---

## Visual system

`email_visual_theme.html` follows `docs_examples/power_choice_pro_style_guide.html`:

- Primary `#4059d8`, secondary `#6f7ff2`, navy header gradient, canvas `#f4f6fa`, ink `#152033`, muted `#667085`
- 600px table shell, 16px corner radius, Arial/Helvetica (web fonts are unreliable in mail)
- Table layout + inline styles; MSO conditional in the theme head
- One primary button: filled `#4059d8`, white 700-weight label, 11px radius

Do not introduce flex/grid, `<style>` in children, background images as the only CTA, or custom webfonts. Put new structural CSS in the theme, not in every child.

---

## Best practices for high-performing business email

These are transactional messages (activation, security, share invites), not a newsletter. Deliverability and trust matter more than flourish.

### Subject and preheader

- One job per subject: what happened and what to do. Keep under ~50 characters when possible; personalize with workspace or project name, not clickbait.
- Never start with `RE:`, `FW:`, “Free”, “Urgent!!!”, or all-caps. Avoid spam-trigger stacks ($$$ / excessive punctuation).
- Write the `preheader` as a second sentence, not a repeat of the subject. Clients show ~40–90 characters next to the subject.
- Do not put secrets in the subject.

### One action

- One primary CTA. The button label is a verb (“Activate account”, “Start comparing”), not “Click here”.
- Repeat the raw URL under the button. Many clients block images and some strip buttons; every recipient must be able to paste the link.
- Deep-link to the exact next step. Do not send people to a generic homepage unless that is the action (`customer_activation_admin_activated`).

### Structure and length

- Lead with the recipient’s name when known; identify the sender workspace immediately.
- First screen (above a typical mobile fold): who, why, button.
- Details (duration, access mode, codes) go below the CTA.
- Short paragraphs, one idea each. These templates already sit in that shape — keep them there.

### HTML that survives inboxes

- Tables + inline CSS only. Assume Gmail, Outlook (Word engine), Apple Mail, and mobile WebKit.
- Set `role="presentation"` on layout tables.
- Always include a `background-color` fallback next to gradients.
- 600px max width; the theme already collapses padding under 620px.
- No JavaScript, forms, `<video>`, or external CSS files.
- Images are optional decoration. The current theme uses a CSS “logo” tile, not a hosted PNG — keep a text brand name even if you add a real logo later. Host images on HTTPS; never embed tracking pixels that change the message meaning.
- Provide both `text/html` and `text/plain`. Divergent parts look like phishing.

### Accessibility and inclusion

- Meaningful link text. Contrast on the navy button is already passing; do not lighten it.
- Do not rely on color alone for “activation required” vs “account ready” (the eyebrow label carries the meaning).
- `lang="en"` is on the theme. Keep copy in the product language of the deployment.

### Trust and security copy

- Security mail (reset, magic key) must say: ignore if unexpected; do not forward; request origin when useful (`remote_ip`).
- Temporary passwords in the body are a last resort. If present, tell the user to change them immediately. Prefer activation-then-set-password when the product allows it.
- Share mail that may include a password must say not to forward the message.
- From-name and From-address come from `DIRECT_EMAIL_FROM_NAME` / `DIRECT_EMAIL_FROM_ADDRESS` (or SendGrid `SG_FROM_EMAIL`). Keep them stable. Sudden From changes tank placement.

### Deliverability (ops, not the Jinja file)

- SPF, DKIM, and DMARC on the sending domain. Align From domain with the authenticated domain.
- Warm new IPs; do not blast from a cold SMTP host.
- Honor the in-app throttles (`MAX_EMAILS_PER_DEST_PER_HOUR` / `_24_HOURS`, per-IP caps). Templates cannot fix a spam loop.
- These are 1:1 transactional messages. Do not add marketing footers or purchase-list unsubscribe headers unless the message is actually promotional.
- Bounce and complaint handling lives at the ESP; do not retry hard failures from the app.

### Measurement

- Prefer first-party “link clicked / account activated” product events over email open pixels. Opens are a poor metric and pixels hurt trust.
- If you A/B a subject, change one variable and keep the body contract stable.

### QA before shipping a template change

- Render HTML and text with empty, partial, and full context (especially no `user_name`, no `project_name`, no `app_login_url`).
- Click every URL in a real client or Litmus/Email on Acid if available; at minimum open the HTML file and the `.txt` in a browser/editor.
- Confirm subjects stay one line after interpolation (no stray newlines in `_subject_line.txt`).
- Confirm copy still matches `docs_examples/terminology_dictionary.md`.

---

## Related files

| Path | Role |
|------|------|
| `email_templates/` | Jinja sources |
| `email_templates/README.md` | Short layout + preview snippet |
| `src/utils/outbound_mail_queue.py` | Ambient injection, throttle, backend dispatch |
| `src/utils/outbound_mail_smtp_jinja.py` | Load, render, SMTP send |
| `src/utils/outbound_mail_sendgrid.py` | Same params → remote dynamic templates |
| `src/utils/base_classes_and_enums.py` | `OutboundEmailType` stems |
| `src/api/auth.py` | Password reset |
| `src/api/user_requests.py` | Welcome + activation |
| `src/api/app_shared_link_manage.py` | Share + magic key |
| `docs_examples/terminology_dictionary.md` | User-facing nouns |
| `docs_examples/power_choice_pro_style_guide.html` | Brand tokens |
