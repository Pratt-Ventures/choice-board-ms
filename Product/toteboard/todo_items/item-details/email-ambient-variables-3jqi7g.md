# email ambient variables

## Short Description
### user
The outbound email services needs more ambient variables.

Add these below, either by obvious computation, extraction from the UsrContext (which has both User and Customer data record information), or, for branding and similar constants, add appropriate configuration settings in config_settings.py (in proximity to the general email settings).
[comment: created 2026-08-15T17:37:29.885Z | id email-ambient-variables-3jqi7g]

## Expanded Description
### agent
I'll inspect the email services, UsrContext, and config settings so the expansion matches the codebase.The brief says “add these below” but the list isn’t in the prompt — I’ll pull the todo item, email guidelines, and current ambient-variable code.Outbound email already injects session user/customer fields in `send_outbound_mail`, but templates still read branding and app-URL values that the queue never sets. Inject those missing ambient keys—by computing them, pulling them from `UserContext`/`User`/`Customer`, or adding nearby settings in `config_settings.py`—so SMTP-Jinja and SendGrid share one complete `email_params` dict.

- Scope: extend `send_outbound_mail` ambient injection (and tests/guidelines); do not invent per-call-site duplicates.
- Must-add theme keys not injected today: `brand_name`, `support_email`, `year`, `app_login_url`, `app_base_url`.
- Source map: `year` from UTC now; URLs from `APPLICATION_BASE_URL` (or a dedicated login path); brand/support as new settings next to the existing email block; extra user/customer fields only if present on those records.
- Do not overwrite caller-supplied keys; keep unauthenticated/self-reg and share-proxy sends tolerant of empty `user_*`/`customer_*`.
- Open: the brief says “add these below” but lists no extra names—confirm nothing beyond the theme set; also whether `app_login_url` is just the base URL or a distinct login path.
[comment: expand completed 2026-08-15T17:39:03.500Z | via executor-opencode | entryId e-20260815-0001 | artifacts: ./email-ambient-variables-3jqi7g/2026-08-15T17-37-29-917Z-expand-apfnuz.request.md, ./email-ambient-variables-3jqi7g/2026-08-15T17-37-29-917Z-expand-apfnuz.response.md, ./email-ambient-variables-3jqi7g/2026-08-15T17-37-29-917Z-expand-apfnuz.trace.log, ./email-ambient-variables-3jqi7g/2026-08-15T17-37-29-917Z-expand-apfnuz.result.json]


## Plan
### agent
I'll inspect email services, UsrContext, and config so the plan matches the codebase.Graphify would rebuild the whole corpus; I'll read the email queue, settings, and templates instead.Need User/Customer fields, email settings, login URL, and existing tests before locking the source map.## 1. Implementation steps

1. **Add settings** in `src/config/config_settings.py`
   - Next to the email block (`USE_EMAIL_SERVICE` / `DIRECT_EMAIL_*`, ~109–122): `EMAIL_BRAND_NAME` default `"Power Choice Pro"`; `EMAIL_SUPPORT_EMAIL` default `""` (empty so the theme footer mailto stays hidden).
   - Next to the existing app-path settings (`APP_RESET_PASSWORD_URL`, `CUSTOMER_ACTIVATION_URL`, ~83–84): `APP_LOGIN_PATH` default `"login"` (matches `client/pages` `/login`).
   - Document the three keys in `powerchoice.env.example` only (do not touch `powerchoice.env`).

2. **Inject ambient keys in one place** — `send_outbound_mail` in `src/utils/outbound_mail_queue.py`, after the existing user/customer/project injection and before backend dispatch, so SMTP-Jinja and SendGrid share one `email_params`.
   - `year` ← `datetime.now(timezone.utc).year` (int).
   - `app_base_url` ← `settings.APPLICATION_BASE_URL.rstrip("/")`.
   - `app_login_url` ← `f"{app_base_url}/{settings.APP_LOGIN_PATH.lstrip('/')}"`.
   - `brand_name` ← `settings.EMAIL_BRAND_NAME`.
   - `support_email` ← `settings.EMAIL_SUPPORT_EMAIL`.
   - Helper: `_set_if_absent(email_params, key, value)` (`if key not in email_params`). Apply it to the five theme keys **and** to existing `user_*` / `customer_*` writes so callers (e.g. password-reset `user_email`) are not overwritten.
   - Still always set queue-owned `remote_ip` and `email_type`.
   - No extra User/Customer columns (ids, admin flags, stripe, dates). Theme-relevant fields are already name/email/phone.
   - Unauthenticated / self-reg / share-proxy (`sess_user is None`): keep `user_*` / `customer_*` as `""` via set-if-absent; still inject branding/year/URLs.

3. **Do not change call sites.** `user_requests.py`, `auth.py`, `app_shared_link_manage.py` stay as-is. `new_user_welcome` CTA starts working because the queue now supplies `app_login_url`.

4. **Docs** — move the five keys from “recommended / not injected” to “always present” in `email_template_guidelines.md` and `email_templates/README.md`. Note sources and the no-overwrite rule.

5. **Tests** — new `src/tests/test_outbound_mail_ambient.py` calling `send_outbound_mail` with a `@mailinator.com` dest (allowlisted so `EmailActivityLog` is written; `PYTEST_ACTIVE` short-circuits SMTP/SendGrid). Cover:
   - Authenticated session: all five theme keys present; `year` equals current UTC year; URLs match settings; `user_*` / `customer_*` filled.
   - No `sess_user`: `user_*` / `customer_*` empty; theme keys still present.
   - Caller-supplied `brand_name` / `app_login_url` not overwritten.
   - Verify: `src/.venv/bin/pytest src/tests/test_outbound_mail_ambient.py src/tests/test_share_manage.py src/tests/test_auth.py` (no project lint/typecheck).

## 2. Clarifying questions

- Confirm scope is only the five theme keys (`brand_name`, `support_email`, `year`, `app_login_url`, `app_base_url`) — the original brief said “add these below” but listed nothing else.
- Should `app_login_url` be `{base}/login` (recommended) or equal to `APPLICATION_BASE_URL`?
- Preferred default for `EMAIL_SUPPORT_EMAIL`: empty (recommended) or `DIRECT_EMAIL_FROM_ADDRESS` (often a no-reply)?

## 3. Options and trade-offs

**Login URL**
- A. Distinct `{APPLICATION_BASE_URL}/login` via `APP_LOGIN_PATH` — matches the Nuxt `/login` page and the welcome CTA; same pattern as `CUSTOMER_ACTIVATION_URL`. Extra setting.
- B. Reuse `APPLICATION_BASE_URL` for both `app_base_url` and `app_login_url` — simpler; welcome “Sign in” lands on the app root, not the login page.
- **Recommend A.**

**Overwrite policy**
- A. set-if-absent for theme + user/customer keys (recommended). Preserves password-reset `user_email`; small behavior change vs today’s always-overwrite of session fields (same values in current callers).
- B. Always overwrite session fields as today; only set-if-absent for the five new keys. Safer for “session is source of truth,” but keeps the overwrite footgun.
- **Recommend A**, matching the expand note.

**Brand/support source**
- A. New email-adjacent settings (recommended). Deploy-wide, env-overridable, no per-call-site copies.
- B. Hardcode `"Power Choice Pro"` / omit support. Faster, not configurable.
- **Recommend A.** Empty support default keeps the footer clean until ops set a real address.
[comment: plan completed 2026-08-15T17:41:50.816Z | via executor-opencode | entryId e-20260815-0002 | artifacts: ./email-ambient-variables-3jqi7g/2026-08-15T17-39-03-526Z-plan-dbt933.request.md, ./email-ambient-variables-3jqi7g/2026-08-15T17-39-03-526Z-plan-dbt933.response.md, ./email-ambient-variables-3jqi7g/2026-08-15T17-39-03-526Z-plan-dbt933.trace.log, ./email-ambient-variables-3jqi7g/2026-08-15T17-39-03-526Z-plan-dbt933.result.json]


## Build Summary
### agent
I'll inspect the email queue, settings, and templates first so the ambient-variable injection matches the existing design.Next I’ll read the guidelines, tests, and env example so the new ambient keys land in the right places.I have the source map. Implementing settings, queue injection, docs, and tests next.Tests passed. Checking git state so I can commit only this work.Staging only this work’s files and committing.**Build complete** — `e29cda99618ea69babd6f42f10ffb0df97fe66e7`

Inject email ambient theme variables in send_outbound_mail

Queue now supplies brand_name, support_email, year, app_base_url, and app_login_url so SMTP-Jinja and SendGrid share one email_params dict. Caller-supplied keys are not overwritten. Adds EMAIL_BRAND_NAME, EMAIL_SUPPORT_EMAIL, and APP_LOGIN_PATH settings.

**Verified:** `29 passed` (`test_outbound_mail_ambient.py`, `test_share_manage.py`, `test_auth.py`)

**Touch points**
- `src/config/config_settings.py:52-53` VERSION `0.7.21`
- `src/config/config_settings.py:85` `APP_LOGIN_PATH`
- `src/config/config_settings.py:112-113` `EMAIL_BRAND_NAME` / `EMAIL_SUPPORT_EMAIL`
- `src/utils/outbound_mail_queue.py:23-25` `_set_if_absent`
- `src/utils/outbound_mail_queue.py:69-88` session user/customer set-if-absent
- `src/utils/outbound_mail_queue.py:103-108` theme keys (`year`, URLs, brand, support)
- `src/tests/test_outbound_mail_ambient.py:50-105` authenticated / unauth / no-overwrite
- `powerchoice.env.example:16,31-32` new keys
- `email_template_guidelines.md:118-139` always-present table
- `email_templates/README.md:43-52` context fields
[comment: build completed 2026-08-15T17:46:24.747Z | via executor-opencode | entryId e-20260815-0003 | artifacts: ./email-ambient-variables-3jqi7g/2026-08-15T17-41-50-905Z-build-odixe7.request.md, ./email-ambient-variables-3jqi7g/2026-08-15T17-41-50-905Z-build-odixe7.response.md, ./email-ambient-variables-3jqi7g/2026-08-15T17-41-50-905Z-build-odixe7.trace.log, ./email-ambient-variables-3jqi7g/2026-08-15T17-41-50-905Z-build-odixe7.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-15T17:46:24.751Z build completed (e-20260815-0003)
- 2026-08-15T17:41:50.816Z plan completed (e-20260815-0002)
- 2026-08-15T17:39:03.500Z expand completed (e-20260815-0001)
- 2026-08-15T17:37:29.885Z created (source: user)
