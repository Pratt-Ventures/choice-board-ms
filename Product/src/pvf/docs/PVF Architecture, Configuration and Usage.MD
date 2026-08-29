# PVF Architecture, Configuration and Usage

A stand-up guide for senior engineers adopting the Pratt Ventures Framework. Companion to the short overview in [`README.md`](README.md).

pvf is a multi-tenant FastAPI + SQLModel kernel: session JWT auth, customer/user admin, outbound email, share links, signed-header external APIs with webhook delivery, Stripe hooks, branding image storage, structured logging, and schema extension points. The runner never imports application modules by name; the application binds through a shell module named in YAML.

---

## Table of contents

1. [Design rules](#1-design-rules)
2. [Process map](#2-process-map)
3. [Configuration planes](#3-configuration-planes)
4. [Runner startup sequence](#4-runner-startup-sequence)
5. [Application handoff](#5-application-handoff)
6. [Four FastAPI apps and DI integrity](#6-four-fastapi-apps-and-di-integrity)
7. [Feature switches](#7-feature-switches)
8. [Hooks](#8-hooks)
9. [Schema extensions](#9-schema-extensions)
10. [Services (`pvf_services`)](#10-services-pvf_services)
11. [Share links](#11-share-links)
12. [External API and the watcher](#12-external-api-and-the-watcher)
13. [Email, Stripe, branding](#13-email-stripe-branding)
14. [Models, Alembic, database](#14-models-alembic-database)
15. [Stand-up checklist](#15-stand-up-checklist)
16. [Minimal application shell (all features on)](#16-minimal-application-shell-all-features-on)
17. [Import policy and pitfalls](#17-import-policy-and-pitfalls)

---

## 1. Design rules

- **pvf never imports the application.** The runner loads the shell module named in YAML (`importlib`). Application code reaches pvf through published entry points only.
- **Two config planes.** Deployment-fixed switches live in `pvf_app_startup.yaml` and are injected read-only. Secrets, URLs, and tuning live in `.env` / process environment.
- **Handoff is a single callable.** `app_startup(invocation: PvfInvocation) -> str | None`. Return `None` to continue; return a string or raise to abort (exit 4).
- **Hooks, not subclassing.** Application logic for shares, branding, and webhooks is registered on `invocation.hooks`. The watcher process binds the same hooks via `register_app_hooks`.
- **Auth is composition-enforced.** Every route on each of the four apps is checked at boot (`dependency_integrity`). Missing or illegal guards fail startup with a listed violation.

Published entry points (do not reach past these):

| Entry point | Role |
|---|---|
| `pvf.pvf_app_runner` | Executable ASGI server (`fastapi dev` / `fastapi run`) |
| `pvf.pvf_get_alembic_config` | Schema probe used by `src/alembic/env.py` |
| `pvf.utils.pvf_services` | **Only** non-REST import surface |
| `pvf.pvf_invocation` | `PvfInvocation`, `PvfAppTarget`, `PvfHookRegistry`, `PvfResolvedEntity` |
| `pvf.config.pvf_config_settings` | `PvfGlobalSettings`, `pvf_settings` |
| `pvf.depends.*` | `SessionDep`, `UserAccessDep` (+ admin), `WebServiceDep` |
| `pvf.db.models.*` | Framework tables for queries and FKs |

---

## 2. Process map

Three processes share YAML + env + hooks. Only the runner composes HTTP.

```
pvf_app_startup.yaml ──► pvf_app_runner          ASGI: four apps + SPA + Stripe
                    ├──► pvf_get_alembic_config  metadata + DSN for migrations
                    └──► <app>_watcher           poll + signed webhook delivery
                              ▲
                              └── shell.register_app_hooks (same bindings)
```

| Process | Loads shell | Calls `app_startup` | HTTP | Models |
|---|---|---|---|---|
| Runner | yes, then `entry_point` | yes | yes | core + **feature-gated** |
| Alembic | `register_schema_extensions` only | no | no | **all** pvf + `models_module` |
| Watcher | `register_app_hooks` only | no | no | all pvf + `models_module` |

Alembic always migrates the full pvf schema so flipping a feature switch at runtime does not require a new migration.

---

## 3. Configuration planes

### 3.1 Startup YAML — deployment-fixed

Path: application `src/` root (`src/pvf_app_startup.yaml`). Override with `PVF_STARTUP_CONFIG`. Template: `src/pvf/example_pvf_app_startup.yaml`.

```yaml
application:
  shell_module: src.app_shell              # imported; must not import models at module level
  entry_point: app_startup                 # callable(PvfInvocation) -> str | None
  models_module: src.db.models.bootstrap   # alembic + watcher table registration
env_file: .env                             # python-dotenv; process env wins
features:
  activate_stripe_integration: true
  activate_branding_image_store: true
  activate_share_links: true
  activate_external_api: true
  activate_customer_communication: true
share:
  object_actions: [not_set, review, comment]   # share types you offer
  access_operations: [not_set, view, comment]  # operations journaled per access
```

`apply_startup_config` writes these into `pvf_settings` via `_inject_startup_values`. They are **ClassVars** with a `__setattr__` guard — `.env` and ordinary assignment cannot set them.

| YAML | Settings ClassVar |
|---|---|
| `features.activate_stripe_integration` | `ACTIVATE_STRIPE_INTEGRATION` |
| `features.activate_branding_image_store` | `ACTIVATE_BRANDING_IMAGE_STORE` |
| `features.activate_share_links` | `ACTIVATE_SHARE_LINKS` |
| `features.activate_external_api` | `ACTIVATE_EXTERNAL_API` |
| `features.activate_customer_communication` | `ACTIVATE_CUSTOMER_COMMUNICATION` |
| `share.object_actions` | `SHARE_OBJECT_ACTIONS` |
| `share.access_operations` | `SHARE_ACCESS_OPERATIONS` |

Share vocabularies are normalized to `list[str]` (`normalize_str_list`). App-level enums are fine at your boundary; pvf stores strings.

### 3.1a Watcher YAML — deployment-fixed critical bindings

Path: application `src/` root (`src/pvf_app_watcher.yaml`). Override with `PVF_WATCHER_CONFIG`. Template: `src/pvf/example_pvf_app_watcher.yaml`. Validated by `PvfWatcherConfig` in `pvf.bindings.pvf_startup_config`.

```yaml
# critical bindings only — general tunables stay in PvfGlobalSettings (.env), not here
version: 1
capture_payloads: true            # mirrors PvfGlobalSettings.WATCHER_CAPTURE_PAYLOADS
no_log_request_types: []          # semantic tags never detailed-logged, even on error; union with WATCHER_NO_LOG_TYPES
types:
  llm:                           # builtin PVF handler (kind: pvf)
    kind: pvf
    module: src.pvf.watcher.handlers.llm
    entry: handle_llm
  outbound_email:
    kind: pvf
    module: src.pvf.watcher.handlers.email
    entry: handle_email
  outbound_api_call:
    kind: pvf
    module: src.pvf.watcher.handlers.api
    entry: handle_api
  SHORTEN_PRODUCT_NAME:          # app handler (kind: app)
    kind: app
    module: src.app.watcher_handlers
    entry: shorten_product_name
```

Loader: `load_watcher_config` + `apply_watcher_config` in `pvf.bindings.pvf_startup_config`. Runner and `pvf_get_alembic_config` both load this file (after `apply_startup_config`). **YAML is authoritative for `types`** — no env override. Unknown `work_type` values not listed are still served from `watcher_generic_jobs` (generic fallback). Deprecated `WATCHER_PROCESS_MODULE_LIST` — use `pvf_app_watcher.yaml` `types`; see `scripts/migrate_watcher_env_to_yaml.py`.

### 3.2 Env file — runtime

Ingested after YAML load, `override=False` (process environment wins). Template: repo-root `example.env`. Ship a real `.env`; the runner **exits 2** unless `UNIQUE_CONFIGURATION_CHECK=1`.

Application settings subclass `PvfGlobalSettings` and call `merge_pvf_settings_into(settings)` at the top of `app_startup` so the app instance carries the same YAML-owned values.

Material groups on `PvfGlobalSettings` (all overridable from env except startup-owned ClassVars):

| Group | Examples |
|---|---|
| Identity / env | `APPLICATION_NAME`, `APPLICATION_BASE_URL`, `SERVER_ENV` (`local` / `staging` / `production`; `is_prod()` is only `production`) |
| Database | `DB_PATH_OR_CONNECTION_STRING`, `DB_ECHO_SQL_TO_CONSOLE`, `BOOTSTRAP_SAMPLE_DATA` |
| JWT / cookies | `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `CLEARED_TOKEN_VALUE` |
| Share gate | `ACCESS_VIEW_COOKIE`, `SHARE_LINK_*`, `SHARE_GATE_*`, `ENABLE_SHARE_*` (UI option flags only; backend supports every access mode) |
| External API | `CUSTOMER_API_INBOUND_HASH_KEY`, `CUSTOMER_API_OUTBOUND_HASH_KEY`, `CUSTOMER_API_TIME_TOLERANCE` |
| Watcher (ops) | `WATCHER_CAPTURE_PAYLOADS` (bool default True), `WATCHER_NO_LOG_TYPES` (csv default "" — union with YAML `no_log_request_types`), poll backoff (`WATCHER_SHORTER_BUSY_POLL_SLEEP=1.0`, `WATCHER_LONGER_IDLE_INCREASING_POLL_SLEEP=5.0`, `WATCHER_POLL_EXPONENTIAL_FACTOR=1.2`, `WATCHER_POLL_MAXIMUM_SLEEP_TIME=30.0`), legacy `WATCHER_PROCESS_*` (deprecated) |
| Watcher (critical) | `pvf_app_watcher.yaml` `types`, `capture_payloads`, `no_log_request_types` (YAML authoritative) |
| Email | `USE_EMAIL_SERVICE` (`SMTP-JINJA` / `SENDGRID` / unset = off), SMTP / SendGrid, throttle caps, `EMAIL_LOCAL_ALLOW_DOMAINS` |
| Stripe | `STRIPE_API_KEY_PRIMARY`, `STRIPE_ENDPOINT_SECRET_PRIMARY`, `STRIPE_HOOK_STR_PRIMARY`, callback prefixes |
| Bootstrap users | `BOOTSTRAP_*_EMAIL` / `PASSWORD` (non-prod sample data) |

`CONTEXT_MASKED_FIELDS` (CSV) strips named fields from context/session payloads (default `stripe_settings`).

---

## 4. Runner startup sequence

`build_app()` in `pvf_app_runner.py`. Module-level `app = build_app()` is the ASGI root.
Alembic mirrors 1–3 + 4b + 5 so metadata matches runtime.

```
1  load startup YAML  (pvf_app_startup.yaml)   missing/invalid → exit 2
1b load watcher YAML  (pvf_app_watcher.yaml)   validated by PvfWatcherConfig (defaults if absent)
2  load_dotenv(env_file)                       process env wins
3  apply_startup_config + apply_watcher_config  inject ClassVars; UNIQUE_CONFIGURATION_CHECK
4  DatabaseConnection + SELECT 1               fail → stderr (DSN password masked) exit 3
4b import shell module
   register_schema_extensions(reg)             optional; BEFORE any model import
5  pvf_bootstrap.import_core_models            watcher queues always registered
   import_feature_models(stripe, branding)    runtime feature-gated
   import_watcher_models (idempotent)          ensures watcher tables in metadata
6  construct four FastAPI apps + root
   CORS on browser apps (localhost:3000 + APPLICATION_BASE_URL)
   include pvf routers (auth, users, logs, + feature routers)
6b build PvfWatcherRegistry from watcher YAML (builtins) → PvfInvocation.watcher_registry / watcher_types
7  entry_point(invocation)                     None → continue; str or exception → exit 4
   register_watcher_handlers(registry)         app may shadow builtin (logged, not double-registered)
   set_current_invocation            hooks reachable without importing the app
   include invocation routers + merge openapi_tags
8  verify_app_dependency_integrity   all four apps
   /status, /session/docs.json
   mount /api /auth-ws /ws /ext-ws, then /static, then SPA
```

Exit codes: `2` bad/missing config, `3` database, `4` application startup.

Static paths resolve from the **workspace root**, not cwd: `static/`, `static_client/`. Reserved prefixes always JSON-404 (no SPA fallback): `/ws`, `/ext-ws`, `/api`, `/auth`, `/hook-stripe-events`, `/api/webhooks`.

OpenAPI: aggregate session surface at `/session/docs.json` (+ `/session/docs`); external at `/api/openapi.json` (+ `/api/docs`). Root docs at `/root-docs`.

---

## 5. Application handoff

### 5.1 `PvfInvocation` (runner → shell)

```python
class PvfInvocation:
    pvf_settings          # already injected
    startup_config        # parsed YAML
    db                    # DatabaseConnection, probed
    app_noauth / app_session / app_share / app_external
    application_name      # you set; /status
    application_version   # you set; /status
    routers               # filled via add_router
    openapi_tags          # per PvfAppTarget
    hooks                 # PvfHookRegistry
    schema_extensions     # same registry as 4b

    def add_router(self, target: PvfAppTarget, router: APIRouter) -> None
    def target_app(self, target: PvfAppTarget) -> FastAPI
```

`set_current_invocation` is called **after** a successful `app_startup`. Internals (`get_hooks()`) read that singleton — never import the application.

### 5.2 Shell contract

The module named in `application.shell_module` exposes:

| Symbol | Required | When called | May import models? |
|---|---|---|---|
| `app_startup(invocation) -> str \| None` | yes | runner step 7 | yes (after merge) |
| `register_schema_extensions(registry)` | no | runner 4b **and** alembic, before any model import | **no** (module-level imports forbidden) |
| `register_app_hooks(hooks)` | convention | `app_startup` + watcher (both) | yes |
| `register_watcher_handlers(registry)` | optional | runner 7 (after hooks) + watcher (`pvf.watcher.runner:build_invocation`) | may import app handler modules; do not import pvf internals |

Watcher registry carries `watcher/{llm,email,api,generic}` handlers. YAML builtins are registered first; app handlers may shadow (logged).

**`app_startup` expected order:**

1. Build app settings (`GlobalSettings(PvfGlobalSettings)`), `merge_pvf_settings_into(settings)`.
2. Set `invocation.application_name` / `application_version` (root `GET /status`).
3. Import `models_module` (registers app tables on `SQLModel.metadata`).
4. App bootstrap (template seed, non-prod sample data). Failures here should log, not silently pass, unless you accept degraded start.
5. `register_app_hooks(invocation.hooks)`.
6. `invocation.add_router(PvfAppTarget.<target>, router)` for every app router.
7. Extend `invocation.openapi_tags[target]`.
8. Return `None`.

Do **not** `include_router` on `invocation.app_*` yourself. The runner includes registered routers after the entry point returns so DI verification sees the final graph.

### 5.3 Why the shell must not import models at module level

```
runner/alembic
  import shell_module          # declarations only
  register_schema_extensions   # populate registry
  import pvf models            # extend_model_class reads registry
  … later …
  app_startup → import app models
```

A module-level `from .db.models.foo import Bar` in the shell imports pvf models too early. Added columns never appear; runner and alembic metadata diverge.

### 5.4 What the watcher reuses

The watcher does **not** call `app_startup`. It loads both YAMLs (startup + watcher) plus env, applies both configs, imports all models, constructs a `PvfInvocation` with `watcher_registry` (built from `pvf_app_watcher.yaml` builtins) and `watcher_types`, calls `register_app_hooks` **and** `register_watcher_handlers` (which may shadow builtins), then `set_current_invocation` → `run_watcher_forever`. Put webhook payload builders and readiness predicates in `register_app_hooks`, and per-type queue consumers in `register_watcher_handlers` — not only in `app_startup`.

---

## 6. Four FastAPI apps and DI integrity

| Target | Mount | Guard | Typical contents |
|---|---|---|---|
| `noauth` | `/auth-ws` | **none** | login, logout, password reset, self-registration |
| `session` | `/ws` | `UserAccessDep` (JWT cookie `access_token`) | admin, context, app CRUD, share manage, API keys, branding |
| `share` | `/ext-ws` | share cookie / magic-key **gate** (not JWT) | application share payloads; optional branding-on-share |
| `external` | `/api` | `WebServiceDep` (signed headers) | customer toolkit |

Root app (unmounted): `/`, `/alive`, `/status`, Stripe hooks, SPA fallback 404, static mounts.

Admin variants: `UserAccessDepCustomerAdmin` (`customer_admin`), `UserAccessDepSystemAdmin` (`system_user_mode >= 2`). All three count as a session guard.

**Integrity rules** (`pvf.utils.dependency_integrity`):

- `session` — every route must depend on a session guard.
- `external` — every route must depend on `get_api_key_info`.
- `noauth` / `share` — no route may depend on session or signed-header guards.
- Exempt: tag `test-helpers`; path suffix `/status`.

Declare deps even if unused:

```python
@router.get("/items/{item_id}", tags=["items"])
def get_item(item_id: int, session: SessionDep, usr_context: UserAccessDep):
    ...
```

> **Sync endpoints (threadpool).** All session/share/noauth/external handlers are `def` (sync), not `async def`. The DB is sync (`SQLModel`/`SQLAlchemy` over `psycopg`/`sqlite`) and LLM/email work is now via the watcher queue, so blocking calls never block the event loop — Starlette runs `def` endpoints in `anyio.to_thread.run_sync` (default 40 threads). Only `src/pvf/api/hook_stripe_events.py:39` stays `async def` for `await request.body()`. Do not reintroduce `async def` for DB handlers unless you also switch the DB driver to async.

Share endpoints call `share_link_validate_and_log` themselves — they must **not** take `UserAccessDep` (the gate is `def` as of 2026-08-24, called without `await`).

CORS (credentials, all methods/headers, `content-disposition` exposed) is installed on noauth / session / share only.

---

## 7. Feature switches

Each YAML flag is both a **router/model gate** (runner) and a **hook requirement** (if you use the feature).

| Switch | Runner includes | Models at runtime | You must register |
|---|---|---|---|
| `activate_share_links` | session: share CRUD | share tables (core — always loaded) | `entity_resolver`, action matrix, email dispatchers as needed |
| `activate_external_api` | session: API-key admin; external: `/api-check` | `api_access_configuration` | payload builders / readiness if you enqueue callbacks |
| `activate_branding_image_store` | session + share branding routers | `branding_images` | `entity_resolver` (tenancy + display name) |
| `activate_stripe_integration` | root Stripe hook routes | `stripe_events`, `subscriber_transactions` | nothing (pvf handles signature + persist) |
| `activate_customer_communication` | session: bug-report / suggestion routers | `user_communication` | nothing. Context `settings.enable_user_communication` is this flag (not `.env`). |

Core models always loaded at runtime: customer/user, passwords + reset tokens, share tracking, email activity, application/session logs.

`GET /api/status` is public (no signed header). `GET /status` on the root reports `invocation.application_name` / `application_version`.

---

## 8. Hooks

All optional unless a feature that needs them is on. Signatures:

| Hook | Signature | Used by |
|---|---|---|
| `entity_resolver` | `(session, usr_context, entity_id) -> PvfResolvedEntity \| None` | share create, branding tenancy |
| `share_type_email_dispatcher` | `(share_type: str) -> str \| Enum \| None` | first invitation |
| `share_resend_email_dispatcher` | same; falls back to first-send type | admin resend |
| `share_action_matrix` | `{share_type: [operation, ...]}` | gate: allowed operations |
| `share_mutating_operations` | `[operation, ...]` | those ops require an established share cookie |
| `share_activity_enricher` | `(session, usr_context, shares) -> {share_id: {field: value}}` | activity list extra columns |
| `share_email_params_enricher` | `(share_link, params: dict) -> dict` | invitation template params |
| `webhook_payload_builders` | `{type: (session, event) -> dict}` | watcher body |
| `webhook_readiness_predicates` | `{type: (session, event) -> bool}` | watcher: skip until True; missing ⇒ always ready |

`PvfResolvedEntity`: `display_name`, `customer_id`. Return `None` to reject (unknown / wrong tenant).

```python
def register_app_hooks(hooks: PvfHookRegistry) -> None:
    hooks.entity_resolver = resolve_widget
    hooks.share_type_email_dispatcher = {"review": "share_review", "comment": "share_comment"}.get
    hooks.share_resend_email_dispatcher = lambda _t: "resending_invitation"
    hooks.share_action_matrix = {"review": ["view"], "comment": ["view", "comment"]}
    hooks.share_mutating_operations = ["comment"]
    hooks.share_activity_enricher = enrich_share_stats
    hooks.share_email_params_enricher = lambda link, params: {**params, "widget_title": link.share_link_name}
    hooks.webhook_payload_builders["widget.updated"] = build_widget_updated
    hooks.webhook_readiness_predicates["widget.updated"] = lambda session, event: True
```

---

## 9. Schema extensions

Add columns to pvf tables `customer`, `user`, `sharelink`, `apiaccessconfiguration` without forking those modules.

Rules: inject **after** a named predecessor field; never before `id`; types `str|int|bool|float`; populate via `apply_extra_fields(row, extra_fields)` on internal creates — pvf only stores and moves the values.

```python
# app_shell.py — no model imports at module level
def register_schema_extensions(registry) -> None:
    registry.add_column(table="customer", name="region_code", type="str",
                        default=None, after="customer_name", description="Billing region")
    registry.add_column(table="user", name="job_title", type="str",
                        default=None, after="phone")
```

Extensible pvf models are non-table `*Spec` classes; `extend_model_class` rebuilds the real table class from the registry. Runner and alembic both replay the registry so metadata matches.

---

## 10. Services (`pvf_services`)

Import from `src.pvf.utils.pvf_services` only.

| Export | Use |
|---|---|
| `SessionDep`, `get_session`, `get_next_session` | request-scoped / ad-hoc SQLModel sessions |
| `UserAccessDep`, `UserAccessDepCustomerAdmin`, `UserAccessDepSystemAdmin` | JWT cookie guards |
| `WebServiceDep` | signed-header guard |
| `PvfGlobalSettings`, `pvf_settings`, `merge_pvf_settings_into` | settings |
| `load_startup_config`, `PvfStartupConfig`, `normalize_str_list` | YAML (watcher / tools) |
| `PvfInvocation`, `PvfAppTarget`, `PvfHookRegistry`, `PvfResolvedEntity`, `get_hooks` | handoff + runtime hooks |
| `log_event` | structured `ApplicationLogEvent` (own session; severity 0 skipped in prod DB) |
| `send_outbound_mail` | throttled, fully async via watcher queue — `send_outbound_mail(session, usr_context, email_type, destination_email, email_params, timeout=10.0) -> ""` (sent) \| `"queued:<id>"` (queued) \| error string (failed); `timeout` polls watcher queue, never reports sent unless delivery confirmed; `WsResultPackage`-style `sent/queued/failed` |
| `queue_llm_request`, `queue_email_request`, `queue_api_request`, `queue_generic_request` + `get_*`/`list_*` + `queue_llm_and_wait`/`poll_llm_request` | watcher queues — `queue_llm_request` injects tenancy, resolves `provider/model/api_key` fallback `api` > `customer` (`customer.ai_provider/ai_model/ai_api_key` decrypted) > `system` (`AI_SERVICE/AI_API_KEY/AI_MODEL`), records `key_source` and `prompt_bytes`; handler records `response_bytes`; `queue_llm_and_wait` polls with timeout |
| `create_access_token`, `Login`, `auth_request` | JWT / login helpers |
| `share_link_validate_and_log`, `ShareAccessRequest`, `ShareAccessConfirmed_Base`, `ShareAccessDenied_Base`, `get_token_cookie`, `make_token_cookie`, `build_share_landing_url` | share gate (now `def`, not `async def` — share gate is sync; caller is sync) |
| `enqueue_callback` | legacy `ApiWebInvocationEvent` queue for the watcher (compat — new code uses `queue_api_request`) |
| `apply_extra_fields`, `PvfAddedColumn`, `PvfSchemaExtensionRegistry` | extra columns |
| `Webrequest`, `WebrequestSignature` | inbound/outbound signed HTTP |
| `WsResultPackage`, `TokenPayload`, `TokenSchema`, `LogSeverity`, `AuthRelatedOutboundEmailType` | shared types |
| `get_random_baseN_value`, `set_update_field` | utilities |
| `DatabaseConnection` | engine holder |

`log_event(..., raise_exception=HTTPException(...))` logs then raises. `usr_context` fills customer/user/IP/path when present.

---

## 11. Share links

**pvf owns:** CRUD on session (`/ws/create-share-link`, extend/disable, send invitation, activity), cookie + magic-key gate, throttle, access journaling.

**You own:** payload routes on the **share** app that call the gate, plus hooks (entity, emails, matrix).

Gate call:

```python
from src.pvf.utils.pvf_services import (
    SessionDep, ShareAccessRequest, share_link_validate_and_log,
)

@router.post("/share/widget-view")
def widget_view(session: SessionDep, request: Request, response: Response,
                      body: ShareAccessRequest):
    share_usr = UserContext(remote_ip=request.client.host, url_path=request.url.path)
    result, link, access = share_link_validate_and_log(
        session=session, share_usr_context=share_usr, request=request,
        response=response, share_request=body,
    )
    if getattr(result, "failure_reason", None):
        return result  # ShareAccessDenied_Base — UI drives the next prompt
    # link.shared_entity_db_id is your entity; serve the payload
```

`ShareAccessRequest` carries `requested_target_token`, `requested_target_share_type` (YAML object action), `requested_target_share_operation` (YAML access operation), plus name/email/password/magic-key fields. Mutating operations listed in `share_mutating_operations` require an already-established cookie.

Access modes (`ShareAccessCheckMode`) are framework-complete (open, email any/matching ± verify, recipient-email verify, password combinations). `ENABLE_SHARE_*` flags only hide options in the UI.

Throttle (env): unauth hits per IP, failures per IP, failures per token, window seconds. `0` disables a cap.

---

## 12. External API and the watcher

**Inbound.** Client sends `X-` authentication + signature headers (`Webrequest` / `WebServiceDep`). pvf hashes the presented key with `CUSTOMER_API_INBOUND_HASH_KEY`, loads `ApiAccessConfiguration`, verifies the signature and clock skew (`CUSTOMER_API_TIME_TOLERANCE`), binds `UserContext` to that customer/user/key.

**Key admin** (session, feature on): create / modify / remove / list under `/ws/api-keys/*`. Create returns the one-time request key and callback authentication material — store them; they are not recoverable.

**Outbound callbacks (legacy).**

```python
from src.pvf.utils.pvf_services import enqueue_callback  # legacy ApiWebInvocationEvent path

enqueue_callback(session=session, usr_context=usr_context, api_config=cfg,
                 web_hook_type="widget.updated",
                 payload_params={"widget_id": widget.id})
```

Same machinery is available via the new unified watcher API queue (`queue_api_request` in `pvf.bindings.pvf_watcher_requests`, columns `target_url`, `http_method`, `connection_protocol`, `auth_protocol`). V1 `connection_protocol`/`auth_protocol` are always `"pvf"` (validated, stored, not yet branched) so future `ssh`/`bearer` need no migration. The old `apiwebinvocationevent` table remains readable this release behind a compat view — do not drop it.

**Watcher as a PVF service — hybrid dedicated + generic queues.**

Framework-owned `src/pvf/watcher/` replaces ad-hoc `src/powerchoice_watcher.py:71` / `example.application_watcher:59` polling. Known PVF types get dedicated queue tables; arbitrary app types use one generic queue; all are bound via `src/pvf_app_watcher.yaml` (critical bindings) and `PvfInvocation.watcher_registry`.

| Queue | Table | Handler (`kind: pvf`) | Via |
|---|---|---|---|
| LLM | `watcher_llm_requests` | `src.pvf.watcher.handlers.llm:handle_llm` (wraps `pvf.utils.llm_client:query_llm_model` with `LlmError.retryable`, 3 retries, capture/no-log aware, **records `key_source` + `prompt_bytes`/`response_bytes` diagnostics, fallback `api` > `customer` > `system`** — `customer.ai_provider/ai_model/ai_api_key` decrypted, else `AI_SERVICE/AI_API_KEY/AI_MODEL`; `poll_llm_request`/`queue_llm_and_wait` poll with timeout) | `queue_llm_request` / `queue_llm_and_wait` / `poll_llm_request` |
| Email | `watcher_email_requests` | `src.pvf.watcher.handlers.email:handle_email` (`deliver_email_package` off thread, throttle caps honored; **fully async — `send_outbound_mail` queues + polls with `timeout`, returns `sent`/`queued`/`failed`, never reports sent unless delivery confirmed**) | `queue_email_request` via `send_outbound_mail(..., timeout=10.0)` |
| API callback | `watcher_api_requests` | `src.pvf.watcher.handlers.api:handle_api` (generalized `pvf.utils.callback_delivery`, signed `POST`/`GET`/`PUT`/`PATCH`/`DELETE` with `WebrequestSignature`, 429/5xx retryable, `connection_protocol`/`auth_protocol` V1 `"pvf"` future `ssh`/`bearer` no migration) | `queue_api_request` |
| Generic | `watcher_generic_jobs` | app-supplied via `register_watcher_handlers` (e.g. `SHORTEN_PRODUCT_NAME -> src.app.watcher_handlers:shorten_product_name`) | `queue_generic_request(work_type, request_package)` |

```python
# Enqueue from a session endpoint (tenancy + encryption + semantic_tag handled in binding):
# Endpoints are `def` (sync) — they block on the DB/watcher queue in the threadpool.
from src.pvf.bindings.pvf_watcher_requests import (
    queue_llm_request, queue_email_request, queue_api_request, queue_generic_request,
    queue_llm_and_wait, poll_llm_request,
)
# or re-exported via src.pvf.utils.pvf_services:
# from src.pvf.utils.pvf_services import queue_llm_request

# Explicit api key (key_source="api") or fallback customer>system when omitted:
queue_llm_request(session=session, usr_context=usr_context,
                  provider="opencode_go", model="glm-5.2", api_key="…",
                  messages=[…], temperature=0.2, max_tokens=800,
                  semantic_tag="SHORTEN_PRODUCT_NAME", metadata={…})
# Fallback example — customer then system key, records key_source + prompt_bytes:
queue_llm_request(session=session, usr_context=usr_context,
                  messages=[…], semantic_tag="reword_option")
# Polling variant (used by reword/factor-suggest; bytes tracked):
text, result_pkg, err = queue_llm_and_wait(session=session, usr_context=usr_context,
                  messages=[…], semantic_tag="reword_option", timeout=12.0)
# err is None (sent), "queued:<id>" (still queued), or failure string (failed)
queue_generic_request(session=session, usr_context=usr_context,
                      work_type="SHORTEN_PRODUCT_NAME",
                      request_package={"product_name": "Acme Super Widget Pro"}, semantic_tag="SHORTEN_PRODUCT_NAME")
# All watcher tables now store diagnostics: watcher_llm_requests.key_source,
# watcher_llm_requests.prompt_bytes (UTF-8 bytes sent), watcher_llm_requests.response_bytes
```

Each `queue_*` injects `customer_id`/`created_by_user_id` from `usr_context` (NULL when `sess_user` is None); each `get_*/list_*` verifies `row.customer_id == usr_context.sess_user.customer_id` (caller-supplied ids ignored). Internal `_system=True` path sets NULL and is framework-only. `semantic_tag` defaults `None` and participates in `no_log` filtering; `WATCHER_CAPTURE_PAYLOADS` (bool default True) + union `WATCHER_NO_LOG_TYPES ∪ PvfWatcherConfig.no_log_request_types` (both `[]` in prod, cleared in dev/test) decide redaction — no-log wins even on error, gated helper `should_capture` / `redact_for_no_log` / `is_no_log_tag` in `pvf.watcher.orchestration` (unit-tested).

**Poll & service:**

```python
from src.pvf.watcher.poll import poll_and_dispatch  # replaces itertools.cycle
from src.pvf.watcher.service import run_watcher_forever

# Claim is SELECT … FOR UPDATE SKIP LOCKED LIMIT 1 ordered by next_attempt_at, id per type
# queued → trying → {complete | will_retry (next_attempt_at=now+delay) | no_retry | max_retries_exceeded}
# Framework maps WatcherInvocationResult.retryable (None→ error_package, True/False override)
```

Invocation handed to each `module.entry`:

```python
class PvfWatcherInvocation:
    row: dict                          # detached copy (no SA session)
    customer_id: int | None
    user_id: int | None
    work_type: str                     # "llm" | "outbound_email" | "outbound_api_call" | work_type
    semantic_tag: str | None
    request_package: dict
    attempt: int; max_attempts: int
    orchestration: WatcherEventOrchestration  # {status, retries_remaining, next_attempt_at, is_no_log}
    session_factory: Callable          # short session if handler needs DB reads
class WatcherInvocationResult:
    failure_reason: str = ""           # "" == success
    result_package: dict | None
    error_package: dict | None         # {code, message, retryable}
    retryable: bool | None             # overrides framework decision
    next_delay_s: int | None           # honors retry_delays when None
```

Claim index per table: `ix_<table>_claim(status, next_attempt_at, id)`.

**Running the watcher:**

- Canonical runner: `src/pvf/watcher/runner.py:main()` — loads both YAMLs + env, builds `DatabaseConnection`, imports all models, builds `PvfInvocation(watcher_registry, watcher_types)` from YAML builtins, calls `register_app_hooks` + `register_watcher_handlers`, `set_current_invocation`, then `service.run_watcher_forever` (signal handling preserved from `powerchoice_watcher:107`: `atexit`/`SIGTERM`/`SIGINT`/`SIGABRT` + `SIGQUIT`/`SIGHUP` Linux vs `SIGBREAK` Windows, exponential backoff via `WATCHER_SHORTER_BUSY_POLL_SLEEP=1.0`/`WATCHER_LONGER_IDLE_INCREASING_POLL_SLEEP=5.0`/`WATCHER_POLL_EXPONENTIAL_FACTOR=1.2`/`WATCHER_POLL_MAXIMUM_SLEEP_TIME=30.0`).
- App shim: `src/powerchoice_watcher.py` is now `~60` lines (`from src.pvf.watcher.runner import main; main()`). Superseded by the framework runner.
- Sample: `src/pvf/example_pvf_app_watcher.yaml` (annotated, 1:1 with target shape) plus `src/pvf/example.application_watcher.py` deprecated (warns to use `src.pvf.watcher.runner`). Migration helper: `scripts/migrate_watcher_env_to_yaml.py`.
- `pvf_app_runner` also builds the same `watcher_registry` so session handlers can introspect available types; YAML `types` is authoritative (`No env-override`).

The watcher is still a **separate process** (supervisord in staging/prod). `fastapi dev` / `./start-server.sh` do not start it. `application_tag` on each key remains opaque.

See `docs_examples/watcher_queues.md` (≤80-line consumer guide) for the minimal human/LLM reference.

---

## 13. Email, Stripe, branding

### Email — fully async via watcher

`send_outbound_mail(session, usr_context, email_type, destination_email, email_params, timeout=10.0) -> str` — **sync `def`, not `async def`**.

- Queues `watcher_email_requests` via `queue_email_request` (tenancy + `semantic_tag` handled), then polls the watcher queue up to `timeout` seconds (`0.25s` interval) for `complete`/`failed`. Returns `""` (sent — delivery confirmed), `"queued:<id>"` (still queued after timeout — watcher will deliver), or error string (`"Outbound email limits exceeded..."`, `"No configuration..."`, throttling, missing share payload, etc.). **Never reports sent unless the watcher handler confirmed delivery**; callers must treat `queued:` as non-failure (share endpoints surface `link_email_sent=False` for queued, `True` only for `""`).
- Throttling is checked twice: at enqueue time (fast-fail) and at handler time (race-safe). Caps: per dest/hour (`MAX_EMAILS_PER_DEST_PER_HOUR`), per dest/24h, per remote IP (`MAX_EMAILS_PER_REMOTE_IP_PER_HOUR` / `VERIFIED` when `usr_context.authenticated_session`), same as before.
- `USE_EMAIL_SERVICE=SMTP-JINJA` — Jinja files under `DIRECT_TEMPLATE_DIRECTORY` / workspace `email_templates/`. Stem = type string: `{stem}.html`, `{stem}_subject_line.txt`, optional `{stem}.txt`. See `docs/email_template_guidelines.md`.
- `USE_EMAIL_SERVICE=SENDGRID` — same `email_params` posted as `dynamic_template_data` via `httpx.AsyncClient`; ids from `SENDGRID_TEMPLATE_IDS` (`code:d-xxx,...`).
- Unset — no send (error string).
- Non-prod: destination domain must be in `EMAIL_LOCAL_ALLOW_DOMAINS` for a send to be attempted (otherwise `log_event` and `""` in non-prod, still creates `EmailActivityLog` for test visibility). `PYTEST_ACTIVE` short-circuits the queue and does a direct `_send_direct_sync` (still creates `EmailActivityLog`) so `src/tests/test_outbound_mail_*` remain green without a running watcher; production always queues when `USE_EMAIL_SERVICE` is set.
- Handler `src/pvf/watcher/handlers/email.py:handle_email` runs off the request thread, calls `deliver_email_package` → `_send_direct_sync` → `request_sendgrid_delivery`/`request_smtp_jinja_delivery` (both `async` with `httpx.AsyncClient`), then creates `EmailActivityLog` with `result_message` from the provider.
- Queued audit: `send_outbound_mail` also creates an interim `EmailActivityLog` with `result_message="queued:<id>"` so tests that query `EmailActivityLog` immediately still see the ambient `email_params`.

Framework auth types (`AuthRelatedOutboundEmailType`): password reset, customer activation variants, new-user welcome, magic access key (`login_2fa` via `send_login_2fa_email`). Share invitation types are **yours**; return them from the email dispatcher hooks. Magic-key share gate (`src/pvf/api/share_link_manage.py:878,929`) also uses `send_outbound_mail` — queued is treated as `sent_magic_access_message=True` with `"queued for delivery"` message, not `Unable to send`.

### Stripe

Feature on → root routes:

- `POST /hook-stripe-events/{hook_str}`
- `POST /hook-stripe-events-sandbox/{hook_str}`

`hook_str` is `STRIPE_HOOK_STR_PRIMARY` or a per-customer hook id. Authorization is the Stripe signature (`STRIPE_ENDPOINT_SECRET_PRIMARY`), not session/API guards. pvf persists events and subscriber transactions.

### Branding

Feature on → session upload/get/delete for customer- and entity-scoped images; share-app read endpoints that resolve the entity via `entity_resolver` + the share cookie. Images stored in pvf tables, not the filesystem.

---

## 14. Models, Alembic, database

**pvf tables (core):** `customer`, `user`, `userpasswords`, `userpasswordresettokens`, `sharelink` + access/magic-key, `apiaccessconfiguration`, `apiwebinvocationevent`, `emailactivitylog`, `applicationlogevent`, `usersessionlog`.

**Watcher queues (framework-owned):** `watcher_llm_requests` (`provider`, `model`, `api_key_encrypted`, **`key_source`**, `prompt_hash`, **`prompt_bytes`**, **`response_bytes`**, `messages_json`, `request_package`, `result_package`, `raw_trace`, `error_package`, `semantic_tag`, `status`, `attempts`, `max_attempts`, `next_attempt_at` — claim index `ix_<table>_claim(status,next_attempt_at,id)`), `watcher_email_requests`, `watcher_api_requests`, `watcher_generic_jobs`. `key_source` is `api|customer|system`; `prompt_bytes`/`response_bytes` are UTF-8 sizes for diagnostics (populated at queue time and handler time, included in `result_package` even when redacted).

**Feature tables:** `stripeevent`, `subscribertransaction`; branding image tables.

**Your tables:** imported by `models_module`. That module should call `pvf_bootstrap.import_all_models()` then import app models, and expose `get_target_metadata()` → `SQLModel.metadata`.

```python
# src/db/models/bootstrap.py
from sqlmodel import SQLModel
from ...pvf.db.models import pvf_bootstrap

pvf_bootstrap.import_all_models()
from .widgets import Widget  # noqa: F401

def get_target_metadata():
    return SQLModel.metadata
```

`src/alembic/env.py` is a shim over `get_alembic_runtime()`: YAML → env → inject → `register_schema_extensions` → all pvf models → `models_module` → metadata + DSN. `BOOTSTRAP_SAMPLE_DATA` is forced `False` so alembic owns schema.

SQLite `create_all` runs only when **not** prod **and** `BOOTSTRAP_SAMPLE_DATA`. Real schema changes go through Alembic (Postgres in the normal dev sidecar).

`DatabaseConnection` is a process-global engine. `get_next_session()` is for startup/watcher/log_event; request handlers use `SessionDep`.

---

## 15. Stand-up checklist

1. Copy pvf into `src/pvf/` (or depend on it in-tree). Repo root on `PYTHONPATH`.
2. `src/pvf_app_startup.yaml` — shell, entry, models module, env file, **all features you want**, share vocabularies.
3. `.env` from `example.env` with `UNIQUE_CONFIGURATION_CHECK=1`, DSN, JWT secrets, mail, Stripe as needed.
4. `src/config/config_settings.py` — `class GlobalSettings(PvfGlobalSettings)` + app `VERSION` / `APPLICATION_NAME`.
5. `src/app_shell.py` — `register_schema_extensions` (optional, no model imports), `register_app_hooks`, `app_startup`.
6. `src/db/models/bootstrap.py` — `import_all_models()` + app tables + `get_target_metadata`.
7. App routers: correct `PvfAppTarget` and the matching Depends.
8. Share payload routes on the share app; webhook builders in `register_app_hooks`.
9. Jinja and/or SendGrid templates for every email type you dispatch.
10. `src/<app>_watcher.py` from `example.application_watcher.py` if you enqueue callbacks.
11. Alembic: `src/alembic/env.py` already delegates; generate/run migrations after model or extension changes.
12. Launch: `fastapi dev src/pvf/pvf_app_runner.py --host 0.0.0.0` (or the app’s start script). Confirm `/status`, `/session/docs`, `/api/docs`.

---

## 16. Minimal application shell (all features on)

YAML as in [§3.1](#31-startup-yaml--deployment-fixed) with every `activate_*` true.

```python
# src/config/config_settings.py
from ..pvf.config.pvf_config_settings import PvfGlobalSettings

class GlobalSettings(PvfGlobalSettings):
    VERSION: str = "0.1.0"
    APPLICATION_NAME: str = "Widget App"

settings = GlobalSettings()
```

```python
# src/app_shell.py — no model imports at module level
from fastapi import APIRouter, Request, Response
from .pvf.pvf_invocation import PvfAppTarget, PvfInvocation, PvfResolvedEntity

def register_schema_extensions(registry) -> None:
    registry.add_column(table="customer", name="region_code", type="str",
                        default=None, after="customer_name")

def register_app_hooks(hooks) -> None:
    def resolve_widget(session, usr_context, entity_id: int) -> PvfResolvedEntity | None:
        from .db.models.widgets import Widget
        cid = usr_context.sess_user.customer_id if usr_context and usr_context.sess_user else None
        if cid is None:
            return None
        row = session.get(Widget, entity_id)
        if row is None or row.customer_id != cid:
            return None
        return PvfResolvedEntity(display_name=row.title, customer_id=row.customer_id)

    hooks.entity_resolver = resolve_widget
    hooks.share_type_email_dispatcher = {"review": "share_review", "comment": "share_comment"}.get
    hooks.share_resend_email_dispatcher = lambda _t: "resending_invitation"
    hooks.share_action_matrix = {"review": ["view"], "comment": ["view", "comment"]}
    hooks.share_mutating_operations = ["comment"]
    hooks.webhook_payload_builders["widget.updated"] = (
        lambda session, event: {"type": "widget.updated", "params": event.payload_params_json}
    )

def app_startup(invocation: PvfInvocation) -> str | None:
    from .config.config_settings import settings
    from .pvf.config.pvf_startup_config import merge_pvf_settings_into
    merge_pvf_settings_into(settings)
    invocation.application_name = settings.APPLICATION_NAME
    invocation.application_version = settings.VERSION

    from .db.models import bootstrap  # noqa: F401

    register_app_hooks(invocation.hooks)

    from .api.widgets import session_router, share_router, external_router
    invocation.add_router(PvfAppTarget.session, session_router)
    invocation.add_router(PvfAppTarget.share, share_router)
    invocation.add_router(PvfAppTarget.external, external_router)
    invocation.openapi_tags[PvfAppTarget.session].append(
        {"name": "widgets", "description": "Widget CRUD"}
    )
    return None
```

```python
# src/api/widgets.py — DI matches the target app
# All endpoint handlers are `def` (sync) — they run in Starlette's threadpool.
# DB (SQLModel/SQLAlchemy) and watcher queue work is blocking, so sync avoids
# blocking the event loop. Only `src/pvf/api/hook_stripe_events.py` remains
# `async def` for `await request.body()`; everything else is `def`.
from fastapi import APIRouter
from src.pvf.utils.pvf_services import (
    SessionDep, UserAccessDep, WebServiceDep,
    ShareAccessRequest, share_link_validate_and_log, enqueue_callback,
)
from src.pvf.db.models.customer_user import UserContext

session_router = APIRouter()
share_router = APIRouter()
external_router = APIRouter()

@session_router.get("/widgets/{widget_id}", tags=["widgets"])
def get_widget(widget_id: int, session: SessionDep, usr_context: UserAccessDep):
    ...

@share_router.post("/share/widget-view", tags=["share_ext"])
def share_view(session: SessionDep, request: Request, response: Response,
                     body: ShareAccessRequest):
    ctx = UserContext(remote_ip=request.client.host, url_path=request.url.path)
    return (share_link_validate_and_log(
        session=session, share_usr_context=ctx, request=request,
        response=response, share_request=body))[0]

@external_router.post("/widgets/status", tags=["general"])
def ext_status(session: SessionDep, usr_context: WebServiceDep):
    ...
```

pvf already mounted: `/auth-ws/login`, password reset, `/auth-ws/initial-signup`, session user admin, logs, share manage, API-key admin, branding, `/api/api-check`, Stripe hooks.

---

## 17. Import policy and pitfalls

- Import services from `pvf.utils.pvf_services`. Other pvf imports are discouraged.
- After `merge_pvf_settings_into`, read startup flags from **your** `settings` (or `pvf_settings`) — they are the same values.
- Tests that override pvf-owned fields must set them on **both** `settings` and `pvf_settings` via `_inject_startup_values` (see app `conftest`). Ordinary assignment raises.
- `PYTEST_ACTIVE` skips the 500 handler so pytest shows tracebacks.
- Do not start with `UNIQUE_CONFIGURATION_CHECK=0` (that is `example.env`).
- Do not put session JWT deps on share/noauth routes, or omit them on session/external — boot will fail.
- Do not `include_router` inside `app_startup`; use `add_router`.
- Keep `register_app_hooks` sufficient for the watcher (payload builders live there).
- Alembic imports **all** pvf models; runtime imports feature models only. Do not delete feature tables from migrations when a switch is off.
- SPA generate/publish is an application concern (`static_client/`); pvf only mounts that directory.

Reference implementation of a full shell: `src/app_shell.py` in this repo. Watcher: `src/powerchoice_watcher.py` and `src/pvf/example.application_watcher.py`.
