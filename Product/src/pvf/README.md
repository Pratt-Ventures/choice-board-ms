# pvf — Pratt Ventures Framework

A standard framework for multi-tenant FastAPI + SQLModel applications: session-JWT
authentication, customer/user administration, outbound email, share links, external
(signed-header) APIs with webhook callback delivery, Stripe hooks, branding image
storage, structured logging, and schema extension points for application-specific
columns.

The framework is composed and launched by a single executable runner configured by a
YAML file in the application's src root. Application-specific behavior is bound
through a shell module and hooks — pvf never imports application modules.

**Stand-up and architecture:** [`PVF Architecture, Configuration and Usage.MD`](PVF%20Architecture%2C%20Configuration%20and%20Usage.MD)
— startup sequence, YAML vs env, application handoff, hooks, feature switches,
services, share/external/watcher, and a minimal all-features-on shell. Use that
document to adopt pvf in a new application; this file is the short contract.

## Startup configuration: `pvf_app_startup.yaml`; example in framework src/pvf/example_pvf_app_startup.yaml

Located at the application src root (override with the `PVF_STARTUP_CONFIG` env var):

```yaml
application:
  shell_module: src.app_shell        # module loaded as the application bridge
  entry_point: app_startup           # callable receiving the PvfInvocation
  models_module: src.db.models.bootstrap  # imports all app table specs (alembic probe)
env_file: .env                       # ingested with python-dotenv; process env wins
features:
  activate_stripe_integration: false
  activate_branding_image_store: false
  activate_share_links: true
  activate_external_api: true
  activate_customer_communication: true
share:
  object_actions: [not_set, ...]     # share types the application offers
  access_operations: [not_set, ...]  # operations journalable per share
```

Feature switches and share vocabularies are deployment-fixed: they are injected into
`pvf_settings` by the startup logic and are **read-only** thereafter — `.env` and
process environment cannot supply them (see `PvfGlobalSettings` startup-owned
ClassVars). Everything else (secrets, URLs, tuning) lives in the env file (usually
`.env`; ship `example.env` in images).

## Entry points for applications

| Entry point | Use |
|---|---|
| `pvf.pvf_app_runner` | The executable server. `fastapi dev src/pvf/pvf_app_runner.py` (dev) / `fastapi run ...` (prod). Builds the DB connection first (fail → stderr + exit code), composes four FastAPI apps, invokes the application shell, verifies dependency injection, mounts static/SPA. |
| `pvf.pvf_get_alembic_config` | Invoked by `src/alembic/env.py`. Reads the YAML and exports the current SQLAlchemy/SQLModel metadata + DB URL, loading only schema-relevant paths from pvf and the application. |
| `pvf.utils.pvf_services` | **The single non-REST entry point.** All standard services an application needs outside of REST endpoints: settings merge, mail, logging, tokens, share gate, callback enqueue, **watcher queue (llm/email/api/generic)** via `queue_*_request` / `get_*_request` / `list_*_requests`, schema extension helpers, dependency types. |
| `pvf.bindings.pvf_watcher_requests` | Watcher queue bindings — `queue_llm_request`, `queue_email_request`, `queue_api_request`, `queue_generic_request` (and `get_*` / `list_*`). Re-exported via `pvf.utils.pvf_services`; either import path satisfies the “complete bindings” rule. |
| `pvf.bindings.pvf_startup_config` | YAML loaders — `load_startup_config` / `PvfStartupConfig` for `pvf_app_startup.yaml`, plus `load_watcher_config` / `PvfWatcherConfig` / `WatcherTypeSpec` for `pvf_app_watcher.yaml` (critical bindings only). |
| `pvf.pvf_invocation` | `PvfInvocation` (the runner → application contract), `PvfAppTarget`, `PvfHookRegistry`, `PvfResolvedEntity`, `watcher_registry` / `watcher_types` / `watcher_config`. |
| `pvf.config.pvf_config_settings` | `PvfGlobalSettings` (base class for the application's settings) and the active `pvf_settings` (includes `WATCHER_CAPTURE_PAYLOADS`, `WATCHER_NO_LOG_TYPES`, poll backoff). |
| `pvf.depends.*` | `SessionDep`, `UserAccessDep` (+ admin variants), `WebServiceDep` for endpoint signatures. |
| `pvf.db.models.*` | Framework table classes (Customer, User, ShareLink, ApiAccessConfiguration, **watcher queues** `WatcherLlmRequest` / `WatcherEmailRequest` / `WatcherApiRequest` / `WatcherGenericJob`) for queries and id references. |
| `pvf.watcher.*` | Framework-owned watcher service — `poll.poll_and_dispatch`, `service.run_watcher_forever`, `runner.main`, `handlers/llm|email|api`, `registry.PvfWatcherRegistry`, `orchestration.PvfWatcherInvocation` / `WatcherInvocationResult`. Apps interact only via bindings + `register_watcher_handlers`; never import `pvf.watcher.*` directly. |

Other imports or calls into pvf are discouraged — use the entry points above.

## The application shell contract

The shell module named in the YAML exposes:

- `app_startup(invocation: PvfInvocation) -> str | None` — the entry point. Expected to:
  1. build the application settings (typically `GlobalSettings(PvfGlobalSettings)`) and call `merge_pvf_settings_into(app_settings)`
  2. import the application models module (registers table metadata)
  3. perform application startup tasks (template seeding, sample data)
  4. register hooks on `invocation.hooks` (usually via a `register_app_hooks` function, which the watcher process also calls)
  5. add routers via `invocation.add_router(PvfAppTarget.<target>, router)`
  6. optionally extend `invocation.openapi_tags` and set `application_name`/`application_version`
  7. return `None` on success, an error message on failure, or raise
- `register_schema_extensions(registry)` *(optional)* — declares added columns on pvf
  tables. Called by the runner and by the alembic config **before any model import**.
  The shell module must not import models at module level.
- `register_app_hooks(hooks)` *(convention)* — shared by the server and watcher processes.
- `register_watcher_handlers(registry: PvfWatcherRegistry)` *(optional, watcher)* — registers app-specific watcher handlers (e.g. `SHORTEN_PRODUCT_NAME -> src.app.watcher_handlers.shorten_product_name`). Called after YAML builtins are registered; may shadow a builtin type (logged, not double-registered). See `src/pvf/docs/PVF Architecture, Configuration and Usage.MD §12` and `docs_examples/watcher_queues.md`.

## The four FastAPI applications

| App | Mount | Authorization |
|---|---|---|
| noauth | `/auth-ws` | none (login, password reset, self registration) |
| session | `/ws` | session JWT cookie (`UserAccessDep`) |
| share | `/ext-ws` | share cookie / magic-key gate (no session JWT) |
| external | `/api` | signed headers (`WebServiceDep`) |

Stripe webhooks are mounted on the root app at their configured paths (their
authorization is the in-body signature). Dependency injection is strictly enforced at
composition time by the runner's integrity check, regardless of whether the
dependency data is an input parameter for a given endpoint; startup fails with a
descriptive error listing violations.

The aggregate session-surface OpenAPI is served at `/session/docs.json` (+ Swagger UI
at `/session/docs`); the external surface at `/api/openapi.json` (+ `/api/docs`).

## Hooks (PvfHookRegistry)

- `entity_resolver(session, usr_context, entity_id) -> PvfResolvedEntity | None` — validation, tenancy, display naming for shares and branding
- `share_type_email_dispatcher(share_type) -> email type | None` — invitation email per share type
- `share_resend_email_dispatcher(share_type) -> email type | None` — administrator resend template (falls back to the first-send type)
- `share_action_matrix: {share_type: [operations]}` — valid operations per share type
- `share_mutating_operations: [operations]` — operations requiring an established cookie
- `share_activity_enricher(session, usr_context, shares) -> {share_id: {field: value}}` — application stats on activity rows
- `share_email_params_enricher(share_link, params) -> params` — application template params
- `webhook_payload_builders: {web_hook_type: (session, event) -> dict}` — callback payloads
- `webhook_readiness_predicates: {web_hook_type: (session, event) -> bool}` — delivery gating

## Login email 2FA

Optional email 2FA is a framework capability, gated by `LOGIN_2FA_MODE`
(`disabled` / `sysadmins` / `admins` / `admins+optin` / `all`) plus `use_2fa` on
`user` and `customer`. Validity is `LOGIN_2FA_VALIDITY_MINUTES` (email copy
`LOGIN_2FA_VALIDITY_MESSAGE`). Codes are hashed on `userpasswords`.

`POST /auth-ws/login` and the application's `/auth-ws/login-and-get-context`
accept optional `two_factor_code`. Password success without a code returns HTTP
200 `Login2FAChallenge` (`two_factor_required=true`) and no session cookie.

Session writes (self / customer only; do not use `/user-update`):

- `POST /ws/user/set-use-2fa` `{ enabled }` — self, only when `admins+optin` and customer `use_2fa` is false
- `POST /ws/customer/set-use-2fa` `{ enabled }` — customer or system admin, only in `admins+optin`

Helpers on `pvf.utils.pvf_services`: `normalize_login_2fa_mode`,
`login_2fa_required`, `login_2fa_optional`, `login_2fa_customer_controllable`,
`apply_2fa_client_settings`, `PvfClientAuthSettings`. Applications should inherit
the mixin on their client settings class and call `apply_2fa_client_settings`
after merging stored blobs so `TWO_FACTOR_AUTH_ENABLED` /
`TWO_FACTOR_AUTH_OPTIONAL` / `TWO_FACTOR_AUTH_CUSTOMER_CONTROLLABLE` are computed
per request.

## Share links

Share types (object actions) and access operations are application vocabularies from
the YAML, normalized to plain string lists internally; applications may define enums
at their own boundary. Each share carries `share_actions` (actions possible,
defaulted from the action matrix); each access record journals `access_operation`
(actions actually used). The gate engine (`share_link_validate_and_log`), cookie
helpers, throttling, and management endpoints are framework-provided; payloads are
application endpoints on the share app calling the gate.

Email `access_magic_key` values and login 2FA codes can be restricted to digits
via `token_security_digits_only` / `TOKEN_SECURITY_DIGITS_ONLY` (default false;
weaker entropy, easier to type). Password-reset tokens and non-email cookie
values are unchanged.

## Schema extensions

Applications may add columns to pvf tables (`customer`, `user`, `sharelink`,
`apiaccessconfiguration`) via `register_schema_extensions`, positioned after a named
predecessor field (never before the standard `id`). Extensible pvf models are defined
as non-table spec classes and built by `pvf.db.model_factory.extend_model_class`;
both the runner and the alembic probe replay the registry so runtime and migrations
see identical metadata. Populate added fields with `apply_extra_fields` /
`extra_fields` dictionaries on internal calls; pvf otherwise only moves and stores them.

## The watcher process

Framework-owned `src/pvf/watcher/` service with four queues (three dedicated + one generic), bound via `src/pvf_app_watcher.yaml` (critical bindings) and `register_watcher_handlers`.

- **Dedicated queues:** `watcher_llm_requests` (LLM), `watcher_email_requests` (email), `watcher_api_requests` (outbound API callbacks) — each has its own table, claim index, and builtin handler (`src/pvf/watcher/handlers/{llm,email,api}.py`).
- **Generic queue:** `watcher_generic_jobs` for arbitrary `work_type` (e.g. `SHORTEN_PRODUCT_NAME`) — any unlisted type is served here; app handlers are registered via `register_watcher_handlers`.
- **YAML:** `src/pvf_app_watcher.yaml` (sibling to `src/pvf_app_startup.yaml`, deployment-fixed, validated by `PvfWatcherConfig` in `pvf.bindings.pvf_startup_config`). Declares only critical bindings; operating tunables (`WATCHER_CAPTURE_PAYLOADS`, `WATCHER_NO_LOG_TYPES`, poll backoff) stay in `PvfGlobalSettings` (.env). No env override for `types` — YAML is authoritative. Template: `src/pvf/example_pvf_app_watcher.yaml`.
- **Runner:** canonical `src/pvf/watcher/runner.py` (`main()`), thin forwarder `src/powerchoice_watcher.py` (~60 lines). Lifecycle: load both YAMLs → env → `DatabaseConnection` → `import_all_models()` → `PvfInvocation(watcher_registry, watcher_types)` → `register_app_hooks` + `register_watcher_handlers` → `set_current_invocation` → `service.run_watcher_forever` (poll + dispatch with `SELECT … FOR UPDATE SKIP LOCKED`).
- **Tenancy & capture:** every `queue_*_request` injects `customer_id`/`created_by_user_id` from `UserContext` (NULL when None); `get_*/list_*` enforce `row.customer_id == usr_context.sess_user.customer_id`; caller-supplied ids ignored. Internal `_system=True` bypass exists but is framework-only. `WATCHER_CAPTURE_PAYLOADS` + union `WATCHER_NO_LOG_TYPES ∪ PvfWatcherConfig.no_log_request_types` gate detailed logs (redacted to `{provider, model, prompt_hash, token_counts, latency_ms, status, semantic_tag}` when disabled or tag in no-log, even on error). App wrapper `src/utils/ai/pvf_llm.py` shows BYOK resolution before queuing; raw `pvf.utils.llm_client.query_llm_model` stays internal to the handler.
- **Legacy:** `src/pvf/example.application_watcher.py` is deprecated (now a shim warning to use `src.pvf.watcher.runner`); `WATCHER_PROCESS_MODULE_LIST` is deprecated — use `pvf_app_watcher.yaml` `types`.
See `docs_examples/watcher_queues.md` for the ≤80-line consumer guide and `PVF Architecture §12` for full design.
