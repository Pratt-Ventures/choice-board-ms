# Share Link Capability — Deep Dive

**Audience:** senior engineers and product managers evaluating the share-link subsystem for extraction into the `pvf` framework as an optionally activated module.
**Sources:** `src/db/models/share_link_tracking.py`, `src/api/app_shared_link_manage.py`, `src/api/app_shared_link_ext_access.py`, `src/pvf/api/app_branding.py` (share routes), `client/pages/share/**`, `client/components/Share*.vue`, `client/pages/projects/[id]/shares.vue`, `src/config/config_settings.py`, `src/config/config_client.py`, `email_templates/`, `src/tests/test_share_*.py`, `e2e/tests/share-access-modes.spec.ts`.

---

## 1. What the capability is

The share-link subsystem lets an authenticated workspace user (the **originator**) issue a URL that grants a **non-registered recipient** a scoped, revocable experience inside the application — today: comparing options on a project (`vote`), comparing plus seeing one's own results (`vote_view`), or viewing full project results (`report`). The recipient never logs in; instead they pass a per-link **access gate** (ranging from "nothing" to "password + verified recipient email") and receive a path-scoped, HMAC-style **share cookie** that authenticates all subsequent API calls for that share only.

Product-level properties:

- **Distribution is two-channel:** the originator can have the server send a templated invitation email (`link_auto_send`), or copy the link / a pre-formatted invitation text into any out-of-band channel (Slack, SMS, their own mail client).
- **Security is a per-link dial**, not a global one: 12 access modes covering open access, email capture (unverified / verified / must-match-recipient), password, and all meaningful combinations.
- **Everything is tracked:** each issued link, each one-time email key, and each access session (cookie) is a DB row, surfaced back to the originator as an activity dashboard (sessions, opens, participants, comparisons, keys issued/used).
- **Kill switches everywhere:** per-link disable, per-link expiration, and originator-account deactivation (`User.access_disabled >= 2`) all invalidate links without deleting history.

---

## 2. Architecture at a glance

```
Originator (logged-in SPA)                     Recipient (anonymous browser)
        │                                                │
        ▼                                                ▼
┌─────────────────────────────┐           ┌──────────────────────────────┐
│ /ws/create-share-link       │           │ /share/{type}/{token}  (SPA) │
│ /ws/extend-or-disable-…     │           │   ShareAccessGate component  │
│ /ws/get-share-activity-…    │           │        │ POST probe          │
│ app_shared_link_manage.py   │           │        ▼                     │
│ deps: SessionDep+UserAccess │           │ /ext-ws/share/{token}/vote   │
└────────────┬────────────────┘           │ /ext-ws/share/{token}/vote-… │
             │                            │ /ext-ws/share/{token}/report │
             ▼                            │ app_shared_link_ext_access   │
   ShareLink / ShareLinkMagicKey /        │ deps: SessionDep ONLY        │
   ShareLinkAccessed  (DB)                └────────────┬─────────────────┘
             │                                         │
             └────────► share_link_validate_and_log ◄──┘   (single choke point)
                                   │
                    sets/reads cookie `pc_share_view`
                    path = /ext-ws/share/{token}/
                                   │
                    pseudo UserContext (limited_proxy=True)
                    → logging, outbound mail, activity rows
```

| Layer | Files | Role |
|---|---|---|
| Data model | `src/db/models/share_link_tracking.py` | `ShareLink`, `ShareLinkMagicKey`, `ShareLinkAccessed` tables + all record-level logic |
| Management API (auth) | `src/api/app_shared_link_manage.py` | Create/extend/disable/activity; also hosts `share_link_validate_and_log`, the gate engine used by the external API |
| External API (anon) | `src/api/app_shared_link_ext_access.py` | `/ext-ws/share/{token}/…` endpoints: gate probe, vote operations, report |
| Share branding | `src/pvf/api/app_branding.py` (`share_router`) | Branding meta by token; images only after cookie |
| Pseudo-context | `src/pvf/db/models/customer_user.py` (`UserContext`) | `limited_proxy`, `share_link_id`, `share_link_ident` |
| Client landings | `client/pages/share/{vote,vote_view,report}/[token].vue`, `client/layouts/share.vue`, `client/components/ShareAccessGate.vue`, `ShareVoteSession.vue` | Anonymous-facing SPA |
| Client management | `client/pages/projects/[id]/shares.vue`, `client/composables/useSharesApi.ts` | Originator UI |
| Email | `email_templates/share_project_{vote,vote_view,report}.*`, `magic_access_key.*` | Jinja/SendGrid templates |
| Config | `src/config/config_settings.py`, `src/config/config_client.py`, `src/pvf/config/pvf_config_settings.py` | Secrets, expirations, URL shapes, per-mode enable flags |

Router wiring (`src/powerchoice_server.py`): the manage router is mounted on the session UI app with `SessionDep + UserAccessDep` (JWT cookie); the ext-access router is mounted with **`SessionDep` only** — it is anonymous by design and performs its own authorization. `/ext-ws` is a reserved prefix (JSON 404, no SPA fallback).

---

## 3. Core concepts and vocabulary

| Concept | Type | Meaning |
|---|---|---|
| `ShareType` | StrEnum, built dynamically from `settings.SHARE_OBJECT_ACTIONS` (`['not_set','vote','vote_view','report']`) | **What** is being shared — the intent/experience. Also determines the landing URL path segment and the invitation email template. |
| `ShareAccessOperation` | StrEnum from `settings.SHARE_ACCESS_OPERATIONS` (`['not_set','vote','view','report']`) | **What the recipient is doing right now** — `view`/`report` may establish a session; `vote` is a follow-up mutation that requires an existing cookie. |
| `ShareAccessCheckMode` | static `str, Enum`, 12 modes + `not_specified` | **How the recipient proves themselves** at the gate (§6). |
| `magic_token` | 22-char urlsafe-base64 UUID4, unique, indexed | The public identifier of the share; the only secret in the URL. |
| `access_magic_key` | 6-char `secrets.token_urlsafe` | One-time email-verification key, stored paired as `{magic_token}:{key}` (unique). |
| share cookie | `pc_share_view` (env `ACCESS_VIEW_COOKIE`) | Path-scoped, httponly cookie carrying a keyed hash + display name + email (§5.4). |
| participant | `ProjectVoteParticipant` row | The durable "who compared what" identity, keyed by `participant_key` derived from the cookie or email (§7). |

Note the deliberate split: **`ShareType` is data-driven from settings** (an extensibility seam — new share intents can be added via config), while **`ShareAccessCheckMode` is a hardcoded enum** (the gate logic is a hand-written switch over modes).

---

## 4. Data model

### 4.1 `ShareLink` (table `sharelink`) — the issued link

Request-facing base (`ShareLink_Base`) plus server-assigned fields.

| Field | Notes |
|---|---|
| `shared_type` | `ShareType`; must be a known value or creation 422s |
| `shared_entity_db_id` | FK-by-convention to the shared entity. **Hard-bound to `CustomerProject`** via `ReferenceEntityModel = CustomerProject` — the single most important coupling to break for generalization |
| `shared_with_company_name` / `shared_with_person_name` / `shared_with_email` | Recipient descriptors. `shared_with_email` is the security anchor for `email_matching*` and `recipient_email_verified*` modes |
| `share_link_name` | Display name; defaults to the project title/tag at creation |
| `share_link_expiration` | Days from `create_date`; `-1` = no limit. Checked on every retrieval |
| `access_mode` | `ShareAccessCheckMode`; `not_specified` is rejected at creation |
| `share_password` | Stored **only as a keyed hash**: `sha224(SHARE_LINK_REST_PW_HASH_KEY, magic_token, password, SHARE_LINK_REST_PW_HASH_KEY)[:20]`. Plaintext exists transiently (and in the invitation email if `share_password_in_email`) |
| `share_password_in_email` | Whether the invitation email may include the plaintext password |
| `link_auto_send` | Send the invitation email on creation |
| `cookie_duration` | Days the view cookie should live after grant. `0` uses `SHARE_LINK_COOKIE_EXPIRATION_DAYS`; `-1` is long-lived (~10 years). Honored when the cookie is set. |
| `magic_token` | Server-generated at creation (client cannot choose it) |
| `customer_id` / `user_id` | Owning tenant + originator; forced from the session, and re-validated on create/update (cross-tenant attempts → 403 + severity-3 log) |
| `share_link_enabled` | Boolean kill switch; disabled links fail retrieval unless explicitly requested with `allow_disabled_link_retrieval` (management path only) |

Validity rule (in `get_shared_link_by_id_or_magic_token_system`): row exists ∧ (`share_link_enabled` unless management override) ∧ not expired (`create_date + expiration_days ≥ now`, skipped when `< 0`).

### 4.2 `ShareLinkMagicKey` (table `sharelinkmagickey`) — one-time email keys

One row per issued verification email. Key fields: `share_id`, `share_magic_token`, `access_magic_key` (6 chars), `share_token_and_access_magic_key` (`"{token}:{key}"`, unique index — the lookup key), `captured_email`, `captured_display_name`, `original_link_recipient_email`, `accessed_date` (NULL = unused).

Lifecycle: created when the gate sends a verification email → redeemed by submitting the key → `accessed_date` set (one-time use) → also expires `ACCESS_MAGIC_KEY_EXPIRATION_MINUTES` (default **70**) after creation. Expired and already-used keys produce distinct denial flags (`verification_magic_link_expired` / `verification_magic_link_used`), which the client gate turns into distinct messages.

### 4.3 `ShareLinkAccessed` (table `sharelinkaccessed`) — access sessions

One row per (share, cookie) pair — i.e., per recipient browser session. Fields: `share_id`, `cookie_token` (the hash, indexed), `remote_ip`, `url_path`, `access_operation` (JSONB list), `captured_email` / `captured_display_name`, `access_count` (incremented on each validated call with the same cookie), plus denormalized `customer_id` / `user_id` / `shared_entity_db_id` for tenant-scoped reporting. When no cookie exists yet, rows are created with a `not_used_{random}` placeholder token.

### 4.4 `ProjectVoteParticipant` — the durable recipient identity

External voters are bound into the vote domain via `get_or_create_share_participant` with:

```
participant_key = share:{share_id}:cookie:{sha224(VIEW_TOKEN_KEY, share_id, cookie_token)[:24]}
                | share:{share_id}:email:{lowercased email}
                | share:{share_id}:anon
```

unique per `(customer_id, project_id, participant_key)`. Carries `share_id`, `share_access_id` (the `ShareLinkAccessed` row that established identity), `display_name`, `email`, `source=share`, `comparison_count`, `is_complete`. **This is the hand-off point**: everything downstream of the gate (groups, rankings, reports) talks to `participant`, not to the share tables.

---

## 5. Message flows

### 5.1 Flow A — Create a share link (authenticated)

```
SPA (projects/:id/shares)  POST /ws/create-share-link   [JWT cookie]
  body: ShareLink_Base
server:
  1. Force user_id/customer_id from session context
  2. Map shared_type → (URL prefix, email template):
       vote      → /share/vote/      + share_project_vote
       vote_view → /share/vote_view/ + share_project_vote_view   (client route uses underscore)
       report    → /share/report/    + share_project_report
  3. Build password note + per-mode security note (settings strings)
  4. ShareLink.create_shared_link_record:
       - reject if session user ≠ (user_id, customer_id)         → 403
       - load referenced project; must belong to session tenant  → 422
       - default share_link_name from project
       - mint magic_token; hash share_password if present
  5. link_url = {APPLICATION_BASE_URL}/share/{type}/{magic_token}{suffix}
  6. if link_auto_send → send_outbound_mail(email_type per type, params §9)
response: CreateShareLinkResponse { link_info, link_url, link_email_sent }
```

Failure to send the email does **not** roll back the link; it returns `failure_reason = "Link request succeeded, but we could not send an email notification…"`. In non-prod, the issued URL is logged to the server console instead.

### 5.2 Flow B — Manage and monitor (authenticated)

- `POST /ws/extend-or-disable-share-link` — flip `share_link_enabled` and/or `share_link_expiration` by `share_id` or `magic_token`. Ownership re-validated.
- `GET /ws/get-share-activity-single-project?project_id=` / `POST /ws/get-share-activity-multiple-projects` — tenant-scoped join of `ShareLink` + `ShareLinkMagicKey` + `ShareLinkAccessed` + vote-participant aggregates, returning per-share: `session_count`, `total_hits`, `magic_keys_issued/used`, `participant_count`, `observation_count`, `password_set` (boolean), the full URL, and the raw key/access rows for the history drill-down. **`share_password` is redacted** via a detached copy (`_redact_share_link_for_response`) — the hash never leaves the server.

### 5.3 Flow C — Recipient lands and passes the gate

```
GET /share/vote/{token}              → SPA fallback serves index.html (not a reserved prefix)
                                       auth.global.ts whitelists /share/* (no login redirect)
                                       layouts/share.vue fetches GET /ext-ws/share/{token}/branding
onMounted: POST /ext-ws/share/{token}/vote   (empty body = "probe")
server: share_link_validate_and_log(...)
  ├─ valid cookie present & hash matches  → access_granted (returning visitor)
  ├─ open_access                          → access_granted immediately
  └─ otherwise                            → ShareAccessDenied shell with mode flags
client: denial flags drive which inputs ShareAccessGate shows (name/email/password/key/checkbox)
loop: submit → POST again with fields → denied-with-flags or granted
on grant: server sets cookie + upserts ShareLinkAccessed + returns payload
```

The denial shell (`ShareAccessDenied_Base`) is the **gate-rendering contract** — a declarative description of what the gate must collect:

| Flag | Client effect |
|---|---|
| `access_mode` | Mode echo; client also string-matches it (`startsWith('password')`, `includes('email')`, `includes('verified')`, `includes('recipient')`) |
| `verification_password_needed` / `_not_supplied` / `_incorrect` | show password field + error |
| `verification_email_needed` / `_not_supplied` / `verification_original_email_needed` | show email field ("must match the email this was sent to") |
| `verification_email_send_link_mode` | show "Send me a one-time access link" checkbox (`authorize_verification_email`) |
| `verification_magic_link_incorrect` / `_expired` / `_used`, `sent_magic_access_message` | show access-key field + status |
| `failure_reason` | human message banner |

### 5.4 The share cookie

Set on grant:

```
name:     settings.ACCESS_VIEW_COOKIE          (default "pc_share_view")
value:    base64( "{H}|{display_name}|{email}|{rand}" )
          H = sha224(VIEW_TOKEN_KEY, cookie-name, magic_token, display_name, email, rand, VIEW_TOKEN_KEY)[:20]
flags:    httponly, samesite=strict, secure (prod only),
          max_age = share cookie_duration days (fallback SHARE_LINK_COOKIE_EXPIRATION_DAYS),
          path  = /ext-ws/share/{magic_token}/
```

Properties worth noting:

- **Path scoping** means the cookie is only ever sent to that one share's API subtree (including the branding-image endpoints). It is never sent to other shares, to `/ws/*`, or to page loads. This is a strong isolation property to preserve in the framework.
- The cookie is **self-authenticating**: the server recomputes `H` from the cookie's own cleartext fields; any tampering with name/email/rand invalidates it (401 + cookie cleared). `display_name`/`email` ride in cleartext (base64 ≠ encryption) — acceptable for display identity, but a framework version should consider an opaque token.
- Logout (`GET /ext-ws/share/{token}/logout`, or `request_logout=true` on any access call) clears the cookie by re-setting it with `max_age=0` on the same path. The logout endpoint tries all three share types so it works regardless of link type.

### 5.5 Flow D — Verified-email loop (modes with `*_verified`)

```
1. recipient submits name (+email) with authorize_verification_email=true
2. server: validate email (regex, or equality with shared_with_email for *_matching*)
   → create ShareLinkMagicKey(captured_email, captured_display_name, original_link_recipient_email)
   → send magic_access_key email containing:
       url_with_magic_key = {base}/share/{type}/{token}/{key}{suffix}
       access_magic_key   = the 6-char key (also shown as text)
   → respond denied + sent_magic_access_message=true   (NOT granted)
3. recipient either pastes the key into the gate, or follows the emailed URL
4. server: lookup "{token}:{key}" → must be unused and < 70 min old
   → mark used, mint cookie bound to the key's captured name/email → granted
```

For `recipient_email_verified*` modes the key email goes to the **on-file** `shared_with_email`, not to anything the visitor types — the visitor proves inbox possession, not knowledge of the address.

> **Magic-key URL:** invitation verify links use `?key=` (`/share/{type}/{token}?key={access_magic_key}`). The SPA also registers `/share/{type}/[token]/[key]` and rewrites those legacy path-form URLs to the query form so already-sent emails still redeem.

### 5.6 Flow E — Post-gate operations (every call re-validates)

All external endpoints run the **same** `share_link_validate_and_log` choke point before touching domain data:

| Endpoint | Operation | Notes |
|---|---|---|
| `POST /ext-ws/share/{t}/vote` | `view` | Initial probe/access; returns project summary, alternatives, factors, personal vote bundle, next sort group, progress, viewer identity |
| `POST /ext-ws/share/{t}/vote/next-group` | `vote` | Follow-up; **requires existing cookie** (`follow_up_use_existing_cookie_only`) |
| `POST /ext-ws/share/{t}/vote/complete-group` | `vote` | Submits a sort-group package; validated against a server-side issued-group cache (anti-tamper), then persisted via `ProjectVoteGroupResult` |
| `POST /ext-ws/share/{t}/vote/complete` | `vote` | Marks participant complete; returns completion status (+ personal summary for `vote_view`) |
| `POST /ext-ws/share/{t}/vote-view` | `view` | Same as vote + completion status + personal results after completion |
| `POST /ext-ws/share/{t}/report` | `report` | Full aggregated report; redacts identities when `private_participation` |
| `GET  /ext-ws/share/{t}/branding` | — | Open with a valid token (meta only, no image bytes) |
| `GET  /ext-ws/share/{t}/customer-image` / `project-image` | — | **Requires the share cookie** |
| `GET  /ext-ws/share/{t}/logout` | — | Clears cookie |

Per-call validation enforces, in order: cookie-hash integrity → logout short-circuit → link exists/enabled/unexpired → **requested `ShareType` matches the link's type** (a `vote` link cannot be used on `/vote-view` or `/report`) → originator user still active (`access_disabled < 2`) → optional `verify_link_id` binding → mode-specific credential checks. Follow-up (`vote`) operations with no cookie are hard-401'd and the cookie is cleared.

### 5.7 The pseudo user context

External handlers construct `UserContext(limited_proxy=True, remote_ip, url_path)`; on grant, the validator attaches the **originator's** `User` row as `sess_user` with `customer_admin=False`, `power_user_mode=0`, `system_user_mode=0` (also enforced by `UserContext.model_post_init`), plus `share_link_id` and `share_link_ident` (a display string built from the shared-with fields). This context is used for **logging and outbound mail ambient identity only** — the ext handlers load domain data through `*_system` methods keyed off `link_info.customer_id`, not through user-authorized accessors. That is the correct pattern to keep: the share context must never flow into permission-checked paths as if it were a session.

---

## 6. Access-mode matrix

Modes compose three orthogonal factors: **password?** × **email requirement** (none / any / must-match-recipient / recipient-on-file) × **email verified by one-time key?**. `ENABLE_SHARE_*` env flags (defaults below) control which modes the **UI offers**; the backend implements all 12 unconditionally and does not re-check the flags — a deployment that disables a mode only hides it from the picker (gap G5).

| Mode | Name | Email | Password | Magic key | Identity bound to | Default enabled |
|---|---|---|---|---|---|---|
| `open_access` | optional | — | — | — | cookie only (anonymous) | **No** |
| `email_any_unverified` | ✓ | any (regex-checked) | — | — | cookie + captured email | Yes |
| `email_any_verified` | ✓ | any | — | ✓ | key-captured email | Yes |
| `email_matching` | ✓ | must equal `shared_with_email` | — | — | cookie + recipient email | Yes |
| `email_matching_verified` | ✓ | must match | — | ✓ | recipient email, verified | No |
| `recipient_email_verified` | ✓ | optional; key mailed to on-file address | — | ✓ | on-file recipient | Yes |
| `password_only` | ✓ | — | ✓ | — | cookie only | No |
| `password_with_email_any_unverified` | ✓ | any | ✓ | — | cookie + captured email | Yes |
| `password_with_email_any_verified` | ✓ | any | ✓ | ✓ | key-captured email | No |
| `password_with_email_matching` | ✓ | must match | ✓ | — | cookie + recipient email | No |
| `password_with_email_matching_verified` | ✓ | must match | ✓ | ✓ | recipient email, verified | No |
| `password_with_recipient_email_verified` | ✓ | optional | ✓ | ✓ (to on-file) | on-file recipient | No |

Behavioral consequences encoded in the confirmed payload (`ShareAccessConfirmed_Base`):

- **Viewer identity attribution:** for `email_matching_verified`, `password_with_email_matching*`, and `recipient_email_verified*` modes, `viewer_*` fields are populated from the **link's** shared-with fields (the share speaks for a known person). For other modes they come from the cookie/captured input (self-asserted).
- **`is_email_verified=True`** only for the six `*_verified` modes.
- Cookie content differs accordingly: magic-key redemption mints the cookie from the **key's captured** name/email, not from whatever is typed at redemption time.

---

## 7. What the shared user is bound to (post-authentication)

After the gate, the "session" is the conjunction of four bindings — this is the surface a client application consumes, and all deeper logic keys off it:

1. **The cookie** (`pc_share_view`, path `/ext-ws/share/{token}/`): proves the browser passed the gate; carries display name/email; hash-verified on every call; expires per the link's `cookie_duration` (default `SHARE_LINK_COOKIE_EXPIRATION_DAYS`); dies with link disable/expiration because the *link* is re-validated on every call, not just the cookie.
2. **A `ShareLinkAccessed` row** per cookie: the audit anchor (IP, path, count, captured identity). `link_access_id` / `link_access_count` are returned to the client.
3. **A `ProjectVoteParticipant` row** per stable identity (`participant_key` from cookie digest or email): the domain identity all vote data hangs off. Cookie loss → new participant (comparisons start over) unless the email-based key path re-unifies them.
4. **The link itself**: type, expiration, enabled flag, and originator liveness are re-checked on **every** external call, so revocation is immediate.

The client additionally re-sends its gate credentials (`gateCreds`) on every call, but the server prefers the cookie; credentials only matter on the first (cookie-less) call. There is no CSRF token — mitigation is `samesite=strict` + path scoping + POST-only mutations; acceptable here, but a framework extraction should note it explicitly.

---

## 8. Landing pages and their key fields

All three landings use `layouts/share.vue` (top bar: customer branding or product badge, project title, share-kind chip) and are whitelisted from auth middleware. Branding meta loads pre-gate; **images load only post-gate** (cookie-gated endpoints), triggered by a shared `useShareSession().markUnlocked()` flag.

| Page | Component | Gate | Post-gate content (from API payload) |
|---|---|---|---|
| `/share/vote/[token]` | `ShareVoteSession share-kind="vote"` | `ShareAccessGate` ("Join this decision") | project title/image/end-time, pair-comparison runner (group intro → left/right choice cards → tie/unsure/skip), per-group + overall progress, pause/undo, min/max-pass handling, "Mark complete" → thank-you + count |
| `/share/vote_view/[token]` | `ShareVoteSession share-kind="vote_view"` | same | same, plus after completion: personal ranking (`submitter_summary.alternative_leaderboard`) |
| `/share/report/[token]` | own page | `ShareAccessGate` ("Open full results") | project header, private-participation notice, stat cards, full rankings/agreement report |

Gate fields (all optional in the payload, shown per denial flags): `display_name`, `verification_email`, `verification_password`, `verification_magic_email_key`, `authorize_verification_email` (checkbox). On mount the component auto-probes with `?key=` if present.

Management landing (`/projects/[id]/shares`, authenticated): summary cards (totals), per-share cards (type/active/mode chips, recipient, URL, copy-link / copy-invite-text / preview / disable / extend+30d), metrics (sessions, opens, comparisons, participants, magic keys used/issued, password set-masked), access-log and magic-key history tables, and the create dialog (share type toggle, access-mode select filtered by `enable_share_*` flags from the merged client settings, recipient name/org/email, link name, expiration, password, auto-send, include-password).

---

## 9. Email bindings

Pipeline: caller → `send_outbound_mail()` (ambient context injection, per-destination and per-IP throttling, `EmailActivityLog` row) → SMTP-Jinja (`email_templates/`) or SendGrid (`SENDGRID_TEMPLATE_IDS`). Non-prod sends are suppressed unless the domain is in `EMAIL_LOCAL_ALLOW_DOMAINS`; pytest short-circuits delivery.

| Template stem | Trigger | Caller-supplied params |
|---|---|---|
| `share_project_vote` / `share_project_vote_view` / `share_project_report` | create with `link_auto_send` | `shared_with_company`, `shared_with_name`, `valid_duration` ("N days" / "no time limit"), `project_id`, `project_name` (share link name), `security_note` (per-mode settings string), `share_password_note` (includes plaintext password only when `share_password_in_email`), `magic_token`, `url_prefix`, `url_suffix`, `url` (full CTA) |
| `magic_access_key` | gate, verified modes, `authorize_verification_email=true` | `url_with_magic_key`, `url_prefix`/`url_suffix`, `valid_duration` ("one hour"), `project_name` (some paths), `share_magic_token`, `access_magic_key` |

Ambient variables injected by the queue (sender-side): `user_*`/`customer_*` of the **originator** (empty under the limited-proxy share-key context — templates must tolerate blanks), `brand_name`, `support_email`, `app_base_url`, `app_login_url`, `remote_ip`, `year`. The server-side `_security_note_for_mode()` map and the two password-note strings in `config_settings.py` are the copy contract between access mode and email text.

---

## 10. Configuration surface

| Setting | Default | Role |
|---|---|---|
| `VIEW_TOKEN_KEY` | dev default, **must override** | Key for cookie hash + participant digest |
| `ACCESS_VIEW_COOKIE` | `pc_share_view` | Cookie name |
| `SHARE_LINK_REST_PW_HASH_KEY` | dev default, **must override** | Key for share-password hash |
| `SHARE_LINK_EXPIRATION_DAYS` | 30 | Default link lifetime (`-1` per link = unlimited) |
| `SHARE_LINK_COOKIE_EXPIRATION_DAYS` | 14 | Default cookie max-age when `cookie_duration` is 0/unset |
| `SHARE_GATE_MAX_UNAUTH_PER_IP_PER_HOUR` | 60 | Cap on cookieless share-gate hits per IP (0 disables) |
| `SHARE_GATE_MAX_FAILURES_PER_IP_PER_HOUR` | 20 | Cap on credential failures (wrong password/key/email) per IP |
| `SHARE_GATE_MAX_FAILURES_PER_TOKEN_PER_HOUR` | 10 | Cap on credential failures per IP+token |
| `ACCESS_MAGIC_KEY_EXPIRATION_MINUTES` | 70 (pvf settings) | Magic-key lifetime |
| `SHARE_PROJECT_APP_VIEW_BASE_URL` / `_SUFFIX_URL` | `/share/` / `""` | Client landing URL shape — **must match Nuxt routes** |
| `SHARE_WS_BASE_URL` | `/ext-ws/share/` | API prefix; also the cookie path base |
| `APPLICATION_BASE_URL` | — (pvf settings) | Origin used to build absolute URLs in emails/responses |
| `SHARE_OBJECT_ACTIONS` / `SHARE_ACCESS_OPERATIONS` | vote/vote_view/report; vote/view/report | Drive the dynamic `ShareType`/`ShareAccessOperation` enums |
| `ENABLE_SHARE_*` (12 flags) | mixed (§6) | UI-only mode filtering, merged global → customer → user via `/ws/context` settings |
| `SHARE_SECURITY_NOTE_*` (14 strings) | English copy | Per-mode recipient guidance in invitation emails |

Note the split that already exists: `APPLICATION_BASE_URL` and `ACCESS_MAGIC_KEY_EXPIRATION_*` live in `src/pvf/config/pvf_config_settings.py`; everything else share-related lives in the app-level `config_settings.py`. The migration has, in effect, already started at the config layer.

---

## 11. Testing surface

- `src/tests/test_share_manage.py` — creation per type, URL shape, auto-send logging (`EmailActivityLog`), tenancy/ownership failures, extend/disable, activity redaction.
- `src/tests/test_share_ext_access.py` — every gate mode, cookie issuance/reuse/tamper, magic-key issue/redeem/expiry/reuse, type-mismatch rejection, follow-up-without-cookie 401, logout, report redaction.
- `src/tests/test_branding.py` — branding meta open, images 401 pre-cookie / 200 post-cookie.
- `e2e/tests/share-access-modes.spec.ts` — all 12 modes end-to-end through the real gate UI (serial), using the non-prod test helper `POST /test-helpers/get-latest-share-magic-key` to redeem keys without email delivery.
- OpenAPI tags: `share` (management, in `openapi_sessions.json`) and `share_ext` (external).

---

## 12. Generalization guide — making this a `pvf` module

The design is already close to framework-shaped: a single validation choke point, declarative denial→UI contract, config-driven share types, and a clean participant hand-off. The work is decoupling, not redesign.

### 12.1 Decouple the shared entity (highest value)

`ReferenceEntityModel = CustomerProject` and the vote-specific payload builders are the only app couplings in the core flow. Introduce a **share-target registry**:

```python
register_share_target(
    share_type="vote",                     # feeds the dynamic ShareType enum
    entity_model=CustomerProject,          # must provide: get-by-id-for-tenant, display name
    url_segment="vote",                    # landing path segment
    email_template="share_project_vote",   # invitation template stem
    payload_builder=...,                   # ext-endpoint handler / payload assembler
    activity_aggregator=...,               # optional extra metrics (participants, comparisons)
)
```

`share_link_validate_and_log` and the three tables are already entity-agnostic (only `shared_entity_db_id: int` + tenant ids). Creation's project lookup becomes `entity_model.get_for_tenant(...)`; activity aggregation becomes optional registered hooks.

### 12.2 Generalize the gate

- Replace the 12-mode hand-written switch with a **composition of three orthogonal checks** (password / email-capture-policy / email-verification) — the matrix in §6 shows they already factor this way. Keep the 12 named modes as presets for UX continuity.
- Make the denial shell the stable contract (it already is); new auth paths (SSO-lite, SMS code, magic-link-only, allowlist domain) then slot in as new check plugins emitting the same shell.
- Add **attempt throttling** on the gate (password and key guessing are currently unthrottled; only outbound mail is throttled) — a framework module should ship this by default.

### 12.3 Token/cookie service

Extract `get_token_cookie` / `make_token_cookie` / clear/set helpers into a named `ShareSessionService` parameterized by cookie name, key, path base, and TTL. Improvements to fold in: honor per-link `cookie_duration`; replace the numpy RNG with `secrets`; consider an opaque server-side token instead of cleartext name/email in the cookie value; standardize the magic-key URL on `?key=` (G1).

### 12.4 Logging and audit potential

The three tables already form a decent audit trail (issuance, key lifecycle, per-session access with IP/path/count). For the framework: emit structured **share lifecycle events** (created, email-sent, gate-failed reason-coded, granted, key-issued/redeemed, disabled, expired) through `log_event` with `share_link_id` — most hooks exist but gate failures are only partially logged today. This is cheap and high-value for downstream analytics ("invite → open → verify → participate" funnels).

### 12.5 Email templates

The template contract (§9) is already registry-friendly: stem per share type + one shared `magic_access_key`. Framework version: require templates by convention (`share_{type}`), keep ambient injection, and keep SendGrid/Jinja parity rules from `src/pvf/docs/email_template_guidelines.md`.

### 12.6 Known gaps to fix during (or before) extraction

- **G1 — magic-key URL shape:** remediated. Emails use `?key=`; legacy `/{token}/{key}` landings redirect.
- **G2 — `ShareType.vote_view` vs URL segment:** server route is `/ext-ws/share/{t}/vote-view` (hyphen) while the client page and email URL use `/share/vote_view/` (underscore). It works, but the mapping is hand-maintained in three places (`create_new_shared_link`, `useSharesApi.extAccess`, Nuxt pages) — a registry would collapse it.
- **G3 — dynamic enum duplication:** `ShareTypeValues` extends itself with `list(ShareType)` to tolerate enum-vs-str comparisons; creation re-checks `in (ShareType.vote, "vote")`. Clean up with a single canonical comparison.
- **G4 — `cookie_duration`:** remediated. Cookie `Max-Age` uses the per-link value.
- **G5 — `ENABLE_SHARE_*` flags are UI-only;** the API accepts any mode so configuration can pick the product subset without losing backend coverage. Keep this split.
- **G6 — gate attempt throttling:** remediated. Unauthenticated volume + credential-failure caps; cookied sessions exempt; HTTP 429 when exceeded.
- **G7 — `open_access` grants with zero identity** and mints a cookie with empty name/email; fine for low-stakes views, but document that downstream identity is `share:{id}:cookie:…` and is lost with the cookie.
- **G8 — dev-default secrets** (`VIEW_TOKEN_KEY`, `SHARE_LINK_REST_PW_HASH_KEY`) must fail-fast in prod in a framework module.

### 12.7 What should NOT change

- The single `share_link_validate_and_log` choke point and the every-call revalidation (revocation immediacy).
- Path-scoped, httponly, samesite=strict cookie bound to the share's API subtree.
- The denial-shell → gate-UI contract (client renders from flags, no mode-specific client logic beyond display).
- The pseudo `UserContext` (`limited_proxy=True`, zeroed privileges) used for logging/mail only.
- The participant hand-off: share auth establishes *who*, the domain module owns *what they did*.

---

## Appendix A — File index

| Area | Path |
|---|---|
| Tables + record logic | `src/db/models/share_link_tracking.py` |
| Management API + gate engine | `src/api/app_shared_link_manage.py` |
| External (anonymous) API | `src/api/app_shared_link_ext_access.py` |
| Share branding routes | `src/pvf/api/app_branding.py` (`share_router`) |
| Pseudo context | `src/pvf/db/models/customer_user.py` (`UserContext`) |
| Participant binding | `src/db/models/project_vote_events.py` (`ProjectVoteParticipant`) |
| Router wiring | `src/powerchoice_server.py` |
| Server config | `src/config/config_settings.py`, `src/pvf/config/pvf_config_settings.py` |
| Client config exposure | `src/config/config_client.py`, `src/api/app_context_views.py` |
| SPA landings | `client/pages/share/{vote,vote_view,report}/[token].vue`, `client/layouts/share.vue` |
| Gate + session components | `client/components/ShareAccessGate.vue`, `ShareVoteSession.vue` |
| Originator UI | `client/pages/projects/[id]/shares.vue`, `client/composables/useSharesApi.ts` |
| Email templates | `email_templates/share_project_*`, `email_templates/magic_access_key.*` |
| Email guidelines | `src/pvf/docs/email_template_guidelines.md` |
| Tests | `src/tests/test_share_manage.py`, `test_share_ext_access.py`, `test_branding.py`, `e2e/tests/share-access-modes.spec.ts` |
| Migration (tables/enums) | `src/alembic/versions/1fa893e89191_add_share_link_tables_and_enums.py` |
