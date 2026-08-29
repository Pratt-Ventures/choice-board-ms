# Email Module Isolation

## Short Description
### user
We are in the processing of isolating framework logic from core application logic. We will keep the use of an Enum in the general application areas to distinguish email types. However, in the email logic itself, we will use the 'values', which must match a defined template name. 

The config.settings that has been used to map mail events to sendgrid codes should be changed to parse a dictionary, as I believe is done with other parameters. The value, available only in the .env, would map template codes (from the application's enum values) to sendgrid template ids.  

Similarly, on first entry, the jinja variant should load all templates in email_templates directory. These should be cached for quick access on demand and also generate the set of unique template names allowed. This will replace the implicit test with enums. 

Ensure the logic is properly logging the error if an undefined template is requested, in either outbound implementation. If the calling logic needs to be aware of the template set, provide helper functions from each implemention to return the list of valid email template names.

The email related data structures should store the string format of the type value. The call into the outbound email logic should be changed to accept either a string or enum. If it gets an enum, take its value as a string. This isolates the effect to the email handling logic and keeps the expressiveness for the main application domain.

The existing email log table must be changed to store a string. The alembic migrate should convert prior values to strings in the new approach. A rollback would do the opposite, mapping to the not_specified or similar value in the previously defined enum if there is no match.

Along with other apprpropriate code, evaluate the email utilities, and data structures, in utils/outbound_mail_queue.py, utils/outbound_mail_sendgrid.py, utils/outbound_mail_smtp_jinja.py, and database definitions in models/email_activity_log.py.
[comment: created 2026-08-15T17:46:55.900Z | id email-module-isolation-hqu8z2]

## Expanded Description
### agent
I'll inspect the email utilities and related models so the expansion matches the current code.Reviewing the email types, settings parsing, and activity-log schema next.Checking how other settings parse dictionaries and how the email-log column is stored.Isolate outbound email handling so application code can keep `OutboundEmailType` for expressiveness while mail utilities, activity logs, and templates operate only on string template names. Replace the per-event SendGrid settings and enum if/elif chain with a single `.env` dictionary mapping template codes to SendGrid IDs, and have the Jinja path cache `email_templates` on first use to derive the allowed name set. Accept `str | Enum` at the outbound entrypoint (use `.value` when an enum is passed), persist `email_type` as a string, and add an Alembic migration that converts existing enum values to strings (rollback maps unknowns to `not_set`).
- Scope: `outbound_mail_queue.py`, `outbound_mail_sendgrid.py`, `outbound_mail_smtp_jinja.py`, `email_activity_log.py`, `config_settings.py`, Alembic, plus call-site/query updates that compare or store `email_type`.
- SendGrid valid names come from the parsed dict; Jinja valid names come from cached templates (exclude shared bases like `email_visual_theme`). Both implementations must log undefined templates and expose a helper listing allowed names.
- Keep `OutboundEmailType` in the app domain; do not make mail modules depend on the enum for validation.
- Migration must convert the Postgres `outboundemailtype` column/type to `varchar`, including historical labels from earlier revisions; rollback remaps unknown strings to `not_set`.
- Open: env dict syntax (match `TRIAL_ACCOUNT_CODES` vs JSON); whether `new_user_welcome` / `customer_activation` need SendGrid entries; whether Jinja should require html+subject or treat missing files as undefined.
[comment: expand completed 2026-08-15T17:47:57.949Z | via executor-opencode | entryId e-20260815-0001 | artifacts: ./email-module-isolation-hqu8z2/2026-08-15T17-46-55-965Z-expand-iwpp4o.request.md, ./email-module-isolation-hqu8z2/2026-08-15T17-46-55-965Z-expand-iwpp4o.response.md, ./email-module-isolation-hqu8z2/2026-08-15T17-46-55-965Z-expand-iwpp4o.trace.log, ./email-module-isolation-hqu8z2/2026-08-15T17-46-55-965Z-expand-iwpp4o.result.json]


## Plan
### agent
I'll inspect the email utilities, settings, and activity-log schema so the plan matches the current code.Graph exists — I'll query it and read the email modules in parallel.Next I’ll map the enum, settings dict parsing, call sites, and the email-log migration.## Email Module Isolation — Plan

Isolate outbound mail so app code keeps `OutboundEmailType`, while queue/backends/logs/templates use string template names only.

### 1. Implementation steps

1. **Normalize type at the mail boundary**
   - Add a small helper (in `outbound_mail_queue.py`, not the enum module): `str | Enum` → `str` via `.value` when an `Enum` is passed.
   - Change `send_outbound_mail`, `request_sendgrid_delivery`, and `request_smtp_jinja_delivery` to accept `str | Enum`, normalize immediately, then use only the string.
   - Drop `OutboundEmailType` imports from the three mail modules. Leave call sites (`auth.py`, `user_requests.py`, `app_shared_link_manage.py`) passing the enum.
   - Persist `email_params['email_type']` and `EmailActivityLog.email_type` as that string. Rewrite `email_type.value` log/show paths to the normalized string.

2. **SendGrid mapping → one `.env` dict**
   - Replace the eight `SENDGRID_TEMPLATE_*` settings and the if/elif chain with `SENDGRID_TEMPLATE_IDS: dict[str, str] | None = None` plus a `field_validator` (same pattern as `TRIAL_ACCOUNT_CODES`).
   - Parser: comma-separated `template_code:sendgrid_id` pairs, `split(':', 1)`, skip blanks. Default `{}` so SMTP-only installs need no mapping.
   - Valid SendGrid names = dict keys. Lookup by string; missing/blank id → `log_event` (severity ≥ 4) and abort, same as today’s unsupported-template path. Fix the existing non-f-string return on that path.
   - Add `get_valid_sendgrid_template_names() -> list[str]`.
   - Document the new var in `powerchoice.env.example`; remove the old per-event keys (including the `SENDGID_*` typos).

3. **Jinja: scan + cache on first use**
   - On first entry (`request_smtp_jinja_delivery` / helper / `send_template_email`), scan `email_templates` (same directory resolution as now).
   - A sendable name requires `{name}.html` **and** `{name}_subject_line.txt`. `{name}.txt` remains optional. Exclude shared bases (`email_visual_theme`).
   - Cache loaded `JinjaTemplate` objects (html / subject / optional text) keyed by name. Invalidate if the resolved directory changes (same idea as today’s `_jinja_env` check).
   - If the requested name is not in the cached set, log undefined template and return; do not raise `FileNotFoundError`.
   - Add `get_valid_jinja_template_names() -> list[str]`.

4. **Activity log stores a string**
   - `EmailActivityLog.email_type: str = Field(default="not_set", ...)`.
   - Remove the `OutboundEmailType` import from the model.
   - `get_recent_log_events_system(..., email_type: str | Enum | None=...)` normalizes with `enum.Enum` (not the app enum) before comparing.

5. **Alembic** (head `j1k2l3m4n5o6`)
   - Upgrade: `emailactivitylog.email_type` `outboundemailtype` → `varchar` with `USING email_type::text`; drop type `outboundemailtype`.
   - Downgrade: recreate enum with the **current** members (`password_reset`, `customer_activation_self`, `customer_activation_admin`, `customer_activation_admin_activated`, `new_user_welcome`, `share_project_vote`, `share_project_vote_view`, `share_project_report`, `magic_access_key`, `not_set`); `UPDATE` any string not in that set to `not_set`; cast column back; include historical labels from `214c4d6a4a26` / `1fa893e89191` in the unknown bucket.

6. **Call-site / test / docs updates (no behavior change at callers)**
   - `test_share_manage.py`: compare `email_type` to `"share_project_vote"` (or `.value`), not the enum member.
   - Keep `test_outbound_mail_ambient.py` passing the enum (proves dual accept).
   - Add focused tests: dict parse; Jinja name discovery excludes `email_visual_theme`; undefined name logs and does not send (both backends); helpers return the expected sets; log row stores a string.
   - Update `email_template_guidelines.md` / `email_templates/README.md`: stems come from files / SendGrid dict, not enum validation. Adding a type = enum member in the **app** + template files (Jinja) and/or a dict entry (SendGrid).

7. **Verify**
   - Run the outbound-mail and share-manage tests plus lint/typecheck for the touched files.

**Out of scope (pre-existing):** `user_requests.py` still calls `OutboundEmailType.customer_activation`, which is not an enum member and has no template. Isolation does not invent that type.

---

### 2. Clarifying questions

1. Env dict syntax: colon-comma (`TRIAL_ACCOUNT_CODES`) or JSON?
2. Should `new_user_welcome` (Jinja-only today) or the broken `customer_activation` call require SendGrid dict entries / an enum+template fix in this change?
3. Jinja allowed set: require html+subject, or treat any non-theme stem as valid and fail later if a file is missing?
4. Should the queue expose a single `get_valid_email_template_names()` that delegates by `USE_EMAIL_SERVICE`, or only the per-backend helpers?

---

### 3. Options and recommendation

| Topic | Options | Recommendation |
|---|---|---|
| Env syntax | **A.** `password_reset:d-abc,share_project_vote:d-def` + validator. **B.** JSON object (native pydantic-settings). | **A.** Matches the only existing dict setting, is `.env`-friendly, and `split(':', 1)` is safe for `d-…` ids. |
| SendGrid coverage | **A.** Dict is the sole source of truth; omit keys = cannot send. **B.** Seed defaults for every current enum value. | **A.** Isolation goal. `new_user_welcome` already has no SendGrid setting. Operators add keys when they have template ids. Do not fix `customer_activation` here. |
| Jinja validity | **A.** html + subject required; text optional; exclude theme. **B.** Any stem except theme. | **A.** Matches `send_template_email` today; missing required files are “undefined”, not a crash. |
| Helper surface | **A.** One helper per backend (as specified). **B.** Also a queue facade. | **A** only, unless a caller appears that must not know `USE_EMAIL_SERVICE`. |
| Query compares | **A.** Model accepts `str \| Enum` and normalizes. **B.** Force all queries to strings. | **A.** Keeps app-domain enum expressiveness; mail/DB stay strings. |

Proceed with the recommendations above unless you want a different call on 1–4.
[comment: plan completed 2026-08-15T17:52:12.824Z | via executor-opencode | entryId e-20260815-0002 | artifacts: ./email-module-isolation-hqu8z2/2026-08-15T17-47-57-980Z-plan-l813te.request.md, ./email-module-isolation-hqu8z2/2026-08-15T17-47-57-980Z-plan-l813te.response.md, ./email-module-isolation-hqu8z2/2026-08-15T17-47-57-980Z-plan-l813te.trace.log, ./email-module-isolation-hqu8z2/2026-08-15T17-47-57-980Z-plan-l813te.result.json]


## Build Summary
### agent
I'll inspect the email utilities, settings, and activity-log schema first so the implementation matches the current code.Reading the email modules, settings, models, and related tests next.Checking test env, log helpers, and remaining call sites so validation and the migration stay consistent.I have the current structure. Implementing isolation across settings, mail modules, the activity log, and a migration.Updating the core mail modules, settings, and the activity-log model.Moving the SendGrid dict next to the other mail settings so the config stays readable.Migration applied. Running outbound-mail and share-manage tests next.All 29 passed. Running the other suites that send mail.Staging only the email-isolation files and committing.## Email Module Isolation — build complete

Mail utilities, activity logs, and templates now operate on string template names. App callers still pass `OutboundEmailType`. Version `0.7.22`. Tests: 29 mail/share + 38 auth/self-reg/share-ext passed. Migration `k2l3m4n5o6p7` applied.

**Commit:** `bd1a2b9e5f0ea43e782b74e33f7d181d261c7288`  
Isolate outbound email handling onto string template names

### Touch points
- `src/utils/outbound_mail_queue.py:22-25` `normalize_email_type`; `:33-38` `str | Enum` entry
- `src/utils/outbound_mail_sendgrid.py:24-32` name helper + dict lookup; `:41-46` undefined log (f-string fixed)
- `src/utils/outbound_mail_smtp_jinja.py:49-57` discover html+subject; `:67-87` cache; `:96-97` helper; `:171-174` undefined log
- `src/db/models/email_activity_log.py:15` `email_type: str`; `:42-57` query normalizes `str | Enum`
- `src/config/config_settings.py:51-66` parser; `:122-131` `SENDGRID_TEMPLATE_IDS`; `:69-70` version
- `src/alembic/versions/k2l3m4n5o6p7_email_type_to_varchar.py:32-50` varchar + rollback → `not_set`
- `src/tests/test_outbound_mail_isolation.py` parse, discovery, undefined, string persist
- `powerchoice.env.example` `SENDGRID_TEMPLATE_IDS`; docs in `email_template_guidelines.md` / `email_templates/README.md`
[comment: build completed 2026-08-15T18:01:38.747Z | via executor-opencode | entryId e-20260815-0003 | artifacts: ./email-module-isolation-hqu8z2/2026-08-15T17-52-12-862Z-build-cwqohr.request.md, ./email-module-isolation-hqu8z2/2026-08-15T17-52-12-862Z-build-cwqohr.response.md, ./email-module-isolation-hqu8z2/2026-08-15T17-52-12-862Z-build-cwqohr.trace.log, ./email-module-isolation-hqu8z2/2026-08-15T17-52-12-862Z-build-cwqohr.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-15T18:01:38.747Z build completed (e-20260815-0003)
- 2026-08-15T17:52:12.824Z plan completed (e-20260815-0002)
- 2026-08-15T17:47:57.949Z expand completed (e-20260815-0001)
- 2026-08-15T17:46:55.900Z created (source: user)
