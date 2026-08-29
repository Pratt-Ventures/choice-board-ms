# Recommended application and PVF improvements — per Muse 2026-08-23 (updated 2026-08-24)

> **Scope.** Architecture, maintainability, and performance assessment of PowerChoice (`src/`, `client/`) and the Pratt Ventures Framework (`src/pvf/`). Includes PVF interface compliance audit (prescribed `src/pvf/bindings/*` surfaces) and an updated design direction for the watcher as a proper integrated PVF service, with Redis-optional throttling and async email.

> **Conventions.**
> - All file references use absolute-repo paths with `path:line` (e.g. `src/pvf/pvf_app_runner.py:44`) to ease navigation. Text outside code uses product terms from `docs_examples/terminology_dictionary.md` (Project · Option · Factor · Compare · Results · Sharing).
> - Severity: **P0** block deploy / data-loss / tenancy, **P1** high — fix next sprint, **P2** normal backlog.
> - This doc is advisory; it does **not** itself change migrations, YAML, or runtime defaults. Phase 1 below is the watcher/email/Redis/LLM redesign explicitly requested 2026-08-24; remaining items are ordered backlog.
> - PVF is read-only infrastructure per `AGENTS.md:16` and `src/pvf/README.md:51`. App work stays in `src/app_shell.py`, `src/api/*`, `src/db/models/*`, `src/utils/*`, `client/*`. Interact with PVF only via `src/pvf/bindings/*` unless this doc explicitly proposes a new `pvf_services` re-export (section 6).

---

## 0. How to read this doc

- **Section 1** — principles and proposed opt-in Redis posture.
- **Section 2** — the requested redesign: watcher as integrated PVF service with (a) generic LLM calling, (b) optional system-managed email delivery, (c) general-purpose module management table registered from YAML. Read this first with `src/powerchoice_watcher.py:1` open.
- **Section 3** — email delivery mode (sync vs async-via-watcher) and the `send_outbound_mail(..., delivery=…, timeout)` contract, including the 10 s poll-to-sync behavior requested for backwards-compatible callers.
- **Section 4** — other PVF improvements (security, DB, config) decoupled from the watcher redesign.
- **Section 5** — PowerChoice application improvements (routers, models, ranking, frontend).
- **Section 6** — PVF interface compliance audit (what today reaches around `src/pvf/bindings` and how Phase 1 + backlog closes it).
- **Section 7** — sequenced implementation & testing plan so `docs`, `migrations`, `openapi_sessions.json` stay green.
- **Section 8** — revisit checklist for after the watcher refactoring lands.

---

## 1. Principles

1. **PVF never imports application code.** Runner loads the shell named in `src/pvf_app_startup.yaml:6` (`shell_module` / `entry_point`) and passes a `PvfInvocation`; application reaches PVF via `src/pvf/bindings/pvf_services.py:1`, `src/pvf/bindings/pvf_invocation.py:1`, `src/pvf/bindings/pvf_startup_config.py:1`, `src/pvf/config/pvf_config_settings.py:1`, `src/pvf/depends/*`, `src/pvf/db/models/*`. Preserve this after watcher/Redis changes.
2. **Opt-in infrastructure, graceful degradation.** Redis, async email, and generic LLM queuing are *optional* capabilities with in-process fallbacks. If `REDIS_URL` (new, see §1.1) is unset/empty, throttling and caches degrade to current in-process implementations — no deploy breaks, no test harness Redis requirement.
3. **Tenancy is non-negotiable.** Every queue table row carries `customer_id`; queue consumers validate `PvfResolvedEntity.customer_id` via the registered `entity_resolver` before touching application entities (current pattern `src/app_shell.py:58`).
4. **Low-risk migrations.** Add columns/tables; do not rename DB/JSON fields without a parallel migration + API compat window (`terminology_dictionary.md:216`).

### 1.1 Redis posture (requested: default on, connection string when present)

Introduce a single optional env (see `example.env:10` for style):

```ini
# src/pvf/config/pvf_config_settings.py — new
# Full connection info when present; None/empty disables Redis and uses in-process fallback.
# Default ON in prod when set; default OFF (stub) in tests.
REDIS_URL=""  # e.g. redis://:password@redis:6379/0  or  rediss://...?ssl_cert_reqs=required
REDIS_THROTTLE_ENABLED=1  # 0 disables even if REDIS_URL is set (escape hatch)
```

- Logic **checks the parameter** (`if settings.REDIS_URL and settings.REDIS_THROTTLE_ENABLED`) and acts accordingly. No import-time `redis` requirement.
- Code imports `redis` lazily (`import redis` inside the helper) and exposes a `get_redis_client() -> Redis | None` accessor analogous to `DatabaseConnection.get_engine()` (`src/pvf/db/connect.py:22`). The helper builds a single pooled `Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=…)` and caches it on a `ClassVar`.
- **In testing, Redis is locally stubbed** — `conftest` provides an in-memory fake (`fakeredis` or a small `dict`+`time` stub implementing `incr/expire/get/set`) when `REDIS_URL` is empty, matching the "may not exist in dev" requirement. No test file imports `redis` at module scope.
- Applies to: share-gate throttling (`src/pvf/utils/share_gate_throttle.py:9`), email throttling (`src/pvf/utils/outbound_mail_queue.py:40`), callback debounce, and the lightweight ranking/LLM caches discussed in §§2.5, 4, 5.

---

## 2. Watcher as a proper integrated PVF service (Phase 1)

Current state (`src/powerchoice_watcher.py:1`, `AGENTS.md:128`, `src/pvf/README.md:155`): a thin application script imports `src/pvf/config/pvf_config_settings.py:29`, `src/pvf/db/connect.py:34`, `src/pvf/utils/callback_delivery.py:38` directly and polls `ApiWebInvocationEvent`. It is not covered by `pvf_services`, not described by YAML, and not extensible to LLM or email without application-owned forks.

### 2.1 Target shape

**Framework-owned service, application-extensible:**

```
src/pvf/services/pvf_watcher_service.py  (new, framework)
  ├─ PvfWatcherRegistry  (module-type registry, lifetime of PvfInvocation)
  ├─ PvfWatcherModule    (protocol: claim(session) -> jobs, execute(session, job) -> result, backoff)
  ├─ PvfWatcherJobTable  (generic table, see §2.2)
  └─ redis-backed throttling helper (optional)

src/pvf_app_startup.yaml  (existing, extended — see §2.3)
  └─ watcher: { modules: [callback, email, ai_agents, reword, <app-defined>], redis: … }

src/app_shell.py:register_app_hooks / new register_watcher_modules  (app)
  └─ registers concrete PvfWatcherModule implementations for app-specific jobs
      (AI baseline, compare-prompt reword — today src/utils/ai/worker.py:116,
       src/utils/ai/reword_worker.py:12) against module keys

src/pvf/pvf_app_runner.py:216 (unchanged entry) + new pvf watcher entry point
  └─ `pvf_watcher_service.run_forever(invocation)` replaces ad-hoc powerchoice_watcher.py loop
```

- `PvfWatcherRegistry` lives on `PvfInvocation` (`src/pvf/bindings/pvf_invocation.py:81`) alongside `hooks`/`routers`, e.g. `invocation.watcher_modules: PvfWatcherRegistry`. The runner constructs it; the app shell populates it — same handoff as routers.
- Execution stays generic: per-module `claim` does `SELECT … FOR UPDATE SKIP LOCKED` on whichever rows that module owns (callback / email / llm / app-custom). `execute` is module-specific. The poll loop (`src/powerchoice_watcher.py:61` today) moves to `src/pvf/services/pvf_watcher_service.py` and cycles over `registry.ordered_modules` with per-module backoff (`shorter_busy_wait`, `increasing_idle_wait`, `poll_exponential_factor`, `poll_maximum_sleep_time` — existing `src/pvf/config/pvf_config_settings.py:259`).
- `src/powerchoice_watcher.py:1` becomes a **40-line shim** that loads `src/pvf_app_startup.yaml`, merges settings (`merge_pvf_settings_into`), calls `pvf_watcher_service.run_forever()` — no direct `pvf.utils`/`pvf.db` imports remain. This closes the compliance gaps in §6.

### 2.2 General management table for arbitrary module types

**Request:** "a general management table for arbitrary module types, implementation from the application, that can be registered from a new YAML file."

Add one framework table; applications provide the behavior:

```python
# src/pvf/db/models/watcher_jobs.py (new, framework-owned, migrated via Alembic)
class PvfWatcherJob(SQLModel, table=True):
    __tablename__ = "pvf_watcher_job"
    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True)                       # tenancy scope; 0 for system jobs
    module_type: str = Field(index=True)                       # e.g. "callback", "email", "llm", "ai_agent", "reword", "app:my_module"
    status: str = Field(default="queued", index=True)          # queued | trying | complete | failed | waiting
    priority: int = Field(default=0, index=True)               # higher dequeued first
    payload_json: dict | None = Field(default=None, sa_column=Column(JSONB))  # job-specific args (validated by module)
    result_json: dict | None = Field(default=None, sa_column=Column(JSONB))
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=5)
    next_attempt_at: datetime | None = Field(default=None, index=True)
    locked_by: str | None = Field(default=None, index=True)   # watcher instance id
    locked_at: datetime | None = Field(default=None)
    created_by_user_id: int | None = Field(index=True)
    create_date: datetime = Field(default_factory=datetime.now, index=True)
    modify_date: datetime = Field(default_factory=datetime.now, sa_column_kwargs={"onupdate": func.now()})
    completed_date: datetime | None = None
    error_summary: str | None = None

    __table_args__ = (
        Index("ix_pvf_watcher_job_claim", "module_type", "status", "next_attempt_at", "priority", "id"),
        Index("ix_pvf_watcher_job_customer", "customer_id", "module_type", "status"),
    )
```

- Existing `ApiWebInvocationEvent` (`src/pvf/db/models/api_access_configuration.py:140`) and `AiAgentJob` (`src/db/models/ai_agent_jobs.py:17`) / `ComparePromptJob` (`src/db/models/compare_prompt_jobs.py:17`) remain as-is initially; over time they become **views or adapters** over `pvf_watcher_job` rows with typed payloads, so product code need not rewrite queries in one release. The registry lets an app register either a legacy table-backed module or a new generic-table module under a new key.
- `poll_maximum_sleep_time` etc. remain global; per-module `max_attempts`/`retry_delays` come from YAML (`watcher.modules.<name>.retry_delays`).
- Application implementation registers via `invocation.watcher_modules.register("app:reweight", AppReweightModule())`. The protocol is `class PvfWatcherModule(Protocol): def claim(self, session) -> list[PvfWatcherJob] | None; def execute(self, session, job) -> str | None; def on_failed(self, session, job, err): …`. Framework executes `claim → execute` inside one `session.begin()` transaction with `FOR UPDATE SKIP LOCKED`.

### 2.3 YAML registration: `src/pvf_app_startup.yaml` + new `src/watcher_modules.yaml` (proposed)

Keep `src/pvf_app_startup.yaml:12` for deployment-fixed PVF switches (runner already treats it read-only via `src/pvf/config/pvf_config_settings.py:95`). Add a **second, also deployment-fixed** file for watcher module wiring:

```yaml
# src/pvf_app_startup.yaml (existing) — add stanza
watcher:
  # framework-owned, but overridable
  redis_url_env: REDIS_URL            # name of env var holding the Redis URL; empty disables Redis
  email_delivery: sync                # default delivery mode when caller omits param (§3)
  modules_enabled: [callback, email, llm, ai_agents, reword]  # ordering matters

# src/watcher_modules.yaml (new, deployment-fixed, read-only at startup)
# Each key is a module_type that will appear in pvf_watcher_job.module_type.
# `impl` names a shell-provided module implementation; framework provides
# callback/email/llm — everything else must be registered by the shell.
modules:
  callback:
    impl: pvf:callback                 # framework built-in (ApiWebInvocationEvent adapter)
    max_attempts: 5
    retry_delays: [1, 4, 10, 60, 120]
    concurrency: 1
  email:
    impl: pvf:email                    # framework built-in (EmailActivityLog queue adapter)
    max_attempts: 5
    retry_delays: [1, 4, 10, 60, 120]
    concurrency: 1
  llm:
    impl: pvf:llm                      # generic LLM caller (see §2.4)
    max_attempts: 3
    retry_delays: [1, 4, 10]
    concurrency: 2
  ai_agents:
    impl: app:ai_agents                # application-provided (src/utils/ai/worker.py:116)
    max_attempts: 3
    retry_delays: [1, 4, 10]
  reword:
    impl: app:reword                   # application-provided (src/utils/ai/reword_worker.py)
    max_attempts: 3
    retry_delays: [1, 4, 10]
  # future example
  # app:my_batch:
  #   impl: app:my_batch
```

- Loader lives in `src/pvf/bindings/pvf_startup_config.py:15` alongside `load_startup_config`; it validates `watcher_modules.yaml` against a Pydantic model (`PvfWatcherModulesConfig`, `ClassVar` read-only pattern matching `src/pvf/config/pvf_config_settings.py:124`). Environment cannot override it.
- `src/pvf/pvf_app_runner.py:216` and `src/pvf/pvf_get_alembic_config.py` both load this file; tests import it once in `src/tests/conftest.py:45` as with the existing startup YAML. Single write path `apply_startup_config` is retained.
- Alternative considered and rejected: folding this into `src/pvf_app_startup.yaml` is acceptable if you prefer one file; the two-file split keeps the watcher module catalog versioned independently and avoids inflating `PvfStartupConfig`.

### 2.4 Generic LLM calling as a watcher module

Today AI participants call `src/pvf/utils/llm_client.py:228` (`query_llm_model`) synchronously in the request (`src/api/app_customer_project_management.py:892`) or semi-synchronously in the watcher tick (`src/utils/ai/worker.py:330` `chat_text_sync`). The requested change is to expose **generic LLM execution** as a watcher capability:

- Framework provides `pvf:llm` module:
  - `claim` dequeues `pvf_watcher_job` rows with `module_type == "llm"` and `status == "queued"` (bounded: `LIMIT 25`, `FOR UPDATE SKIP LOCKED`, ordered by `priority desc, id asc`).
  - `execute` resolves credentials (`src/utils/ai/config.py:183` `resolve_llm_credentials` — BYOK or system key from `src/pvf/config/pvf_config_settings.py:294`), calls `src/pvf/utils/llm_client.py:228` (`query_llm_model` now `httpx.AsyncClient`-backed; see §4), writes `result_json` (`{result, session_contents}`) or `error_summary` (`LlmError(retryable=…)` `llm_client.py:22`), and transitions `queued → trying → complete | failed | queued(retry)`.
  - Retry semantics respect `LlmError.retryable` exactly as `src/utils/ai/worker.py:354` does today.
- Application usage stays narrow:
  - Compare-prompt reword (`src/api/app_customer_project_content_management.py:408,497`, `src/api/app_customer_project_management.py:798`) stops calling `generate_*_prompt_sync` inline. It enqueues:
    ```python
    PvfWatcherJob.enqueue_llm(
        session, customer_id=…, module_type="llm",
        payload={"kind": "reword_option", "option_id": …},
        priority=10,
    )
    ```
    and returns `202` with `{queued_count}`. The watcher fills `compare_prompt` on completion via a small completion hook registered as `app:reword` (or inline in the `llm` payload).
  - AI baseline ticks (`src/utils/ai/worker.py:260`) enqueue per-pair or per-group LLM jobs to `pvf:llm` instead of blocking `while processed < AI_PAIRS_PER_TICK:260`. The existing `src/utils/pair_scheduler.py:261` / `src/utils/vote_sort_session.py:715` scheduling remains unchanged; only the I/O is deferred.
- Credentials: system key from `AI_API_KEY` (`src/pvf/config/pvf_config_settings.py:295`) or per-customer encrypted `ai_api_key` (decrypted via `src/pvf/utils/field_encryption.py:12`). The framework never logs keys; `conftest` stubs `query_llm_model` as it stubs SendGrid today (`src/tests/conftest.py:91`).

### 2.5 Email as an optional watcher-queued module

Spec in §3. For the watcher side:

- When `watcher.modules.email.enabled` and the job is `module_type == "email"`, the email module delivers via `request_sendgrid_delivery` / `request_smtp_jinja_delivery` (`src/pvf/utils/outbound_mail_sendgrid.py`, `src/pvf/utils/outbound_mail_smtp_jinja.py`) **off the request thread**.
- Throttling checks (`MAX_EMAILS_PER_DEST_PER_HOUR` etc. `src/pvf/config/pvf_config_settings.py:276`) run **twice**: once at enqueue time (fast-fail with `failure_reason`, same as today `src/pvf/utils/outbound_mail_queue.py:48`), and once at delivery time (race-safe; failed delivery requeues with `next_attempt_at` from retry delays). This preserves current limits while making the async path audited in `EmailActivityLog` (`src/pvf/db/models/email_activity_log.py:13`).
- Redis throttling (§1.1) wraps the same checks via `INCR key; EXPIRE key window` when Redis is available; falls back to the existing `EmailActivityLog.get_recent_log_events_system` queries when not.

---

## 3. Email delivery — sync default, async-via-watcher with friendly poll

### 3.1 Requested behavior

> Email will be adapted to have a system setting for default synchronous (as it is now) or async (via PVF watcher queueing). The call chain to `send_outbound_mail` will request either `sync`, or `async with a timeout`. The caller will have a friendly polling wait to see if the requested email clears the outbound queue within that time. For emails queued within a default of 10 seconds, the async behavior would have the same flow as the current sync calls.

### 3.2 Settings

```python
# src/pvf/config/pvf_config_settings.py — new, framework-owned, non-startup
EMAIL_DELIVERY_MODE: str = environ.get("EMAIL_DELIVERY_MODE", "sync")  # sync | async
# Per-module max attempts/delays come from watcher_modules.yaml; global sync timeout:
EMAIL_ASYNC_POLL_SECONDS: float = float(environ.get("EMAIL_ASYNC_POLL_SECONDS", 10))
EMAIL_ASYNC_POLL_INTERVAL: float = float(environ.get("EMAIL_ASYNC_POLL_INTERVAL", 0.25))
```

- `EMAIL_DELIVERY_MODE` is env-overridable (not YAML read-only) because it is an operational knob, not a deployment-fixed contract. `sync` preserves current behavior; `async` enqueues to watcher.
- Keep `USE_EMAIL_SERVICE` (`SENDGRID` / `SMTP-JINJA` / `None`) `src/pvf/config/pvf_config_settings.py:271` orthogonal.

### 3.3 Call contract

```python
# src/pvf/utils/outbound_mail_queue.py — extended
async def send_outbound_mail(
    *,
    session: Session,
    usr_context: UserContext,
    email_type: str | Enum,
    destination_email: str,
    email_params: dict,
    delivery: Literal["default", "sync", "async"] = "default",
    async_timeout: float | None = None,   # seconds to poll when async; None → settings.EMAIL_ASYNC_POLL_SECONDS
) -> bool | str:
    """
    Returns same as today on success ("" or result_msg string) or an error string
    containing the log id on throttling/unknown service. Callers inspect truthiness
    of the returned string exactly as today (e.g. src/api/share_link_manage.py sync flow).
    When async, this function blocks up to async_timeout polling the EmailActivityLog /
    pvf_watcher_job row for completion; if it clears within the window the caller
    observes sync-like success. This satisfies "same flow as current sync calls" for
    the 10 s default.
    """
```

- `delivery="default"` → `settings.EMAIL_DELIVERY_MODE` (`sync` today).
- `delivery="sync"` → today's direct path `request_sendgrid_delivery` / `request_smtp_jinja_delivery` (`outbound_mail_queue.py:113-122`).
- `delivery="async"` → run throttling checks, insert a `pvf_watcher_job` (or legacy `EmailActivityLog` pending row) + `EmailActivityLog` entry with `result_message="queued"`, `commit`, then **poll** (`while elapsed < async_timeout: sleep(EMAIL_ASYNC_POLL_INTERVAL); refresh row; if result_message not in ("queued","retrying"): break`).
- Poll uses `session.refresh(job)` or a fresh `select(EmailActivityLog).where(id == …)` on the same session — caller already holds `SessionDep` (`src/pvf/depends/api_session_dependencies.py:16`).
- Important: `email_params` mutation (`outbound_mail_queue.py:74` `email_params['remote_ip'] = …`) must be copy-on-write — snapshot the dict before adding request-local keys so callers that reuse the dict do not alias.

### 3.4 Queue representation (choose one; recommend A)

- **(A) New `pvf_watcher_job` row** with `module_type="email"`, `payload_json={"email_type":…, "destination_email":…, "email_params":…}`. Delivery module renders the Jinja/SendGrid template off-thread. `EmailActivityLog.create_email_event` records the final result in the same transaction as `job.status = complete`.
- **(B) Reuse `EmailActivityLog` as queue** by adding `delivery_status` + `next_attempt_at` columns. Less preferred — pollutes the audit log with queue state.
- **(A) recommended** — keeps audit (`EmailActivityLog`) immutable and queue (`pvf_watcher_job`) mutable, matches the callback path.

### 3.5 Tests & stubbing

- When `settings.REDIS_URL == ""` (dev/CI) and SMTP/SendGrid is unset, `send_outbound_mail` short-circuits as today (`outbound_mail_queue.py:135` `non production; email NOT sent`) but the async poll still returns success so `api/share_link_manage.py` callers keep their current flow. No real network required in `src/tests/test_outbound_mail_ambient.py` / `test_outbound_mail_isolation.py`.
- Add `fakeredis`-style stub for `EmailActivityLog` throttling counts when Redis is enabled in tests; or keep the existing DB query path — DB path remains the source of truth, Redis is a windowed fast-path cache (writer writes both, reader checks Redis first then DB).

---

## 4. PVF — other improvements (decoupled from §2-3)

### 4.1 Database & storage

| Priority | Area | Current | Fix | Migration |
|----------|------|---------|-----|-----------|
| P1 | `ApiWebInvocationEvent.web_hook_status` hot path `src/pvf/utils/callback_delivery.py:43` | No index → `SELECT … WHERE web_hook_status=='pending'` full scan every `WATCHER_SHORTER_BUSY_POLL_SLEEP=1.0` `src/pvf/config/pvf_config_settings.py:259` | Add composite `Index(ApiWebInvocationEvent.web_hook_status, ApiWebInvocationEvent.next_attempt_at)` via `pvf_watcher_job` or directly; change `check_for_callbacks_ready:42` to `SELECT … WHERE status=='pending' ORDER BY next_attempt_at LIMIT 25 FOR UPDATE SKIP LOCKED` | Alembic `op.create_index` |
| P1 | Missing FKs / tenancy | `user.customer_id`, `sharelink.customer_id` are plain `int` without FK; orphan rows possible | Add `ForeignKey("customer.id")` with `ondelete=RESTRICT` in next schema pass; enforce `customer_id == usr_context.sess_user.customer_id` in `pvf/services` helpers, not raw model methods | FK add (check existing orphans first) |
| P1 | `user.customer_id` missing index, `userpasswords.user_id` missing index, `emailactivitylog` single-col indexes insufficient for `WHERE email_address==… AND email_type==… AND create_date > …` `src/pvf/utils/outbound_mail_queue.py:40` | Seq scans | Add `index=True` on `user.customer_id`, `userpasswords.user_id`; add composite `(email_address, email_type, create_date)` on `emailactivitylog` | Index adds |
| P2 | `branding_images.image_data LargeBinary` in-row `src/pvf/db/models/branding_images.py:49` | Every metadata select loads TOAST | `defer(image_data)` on list queries (already done for `admin_list` — extend to all `get_by_customer_id_system`) | No DDL |
| P2 | `subscriber_transactions` expiry recompute `src/pvf/db/models/subscriber_transactions.py:99` loads all rows into Python `relativedelta` loop | O(n) per tx | SQL `SUM(duration)` via `generate_series` / Python capped at `MAX_ROWS=200` + DB-side aggregation | No DDL |
| P2 | Soft-delete `deleted_date` without partial index | Every query `WHERE deleted_date IS NULL` | `CREATE INDEX … WHERE deleted_date IS NULL` | Index adds |

### 4.2 Security hardening (P0-P1)

Carry these from the assessment; none depend on watcher work:

- `src/pvf/api/hook_stripe_events.py:36` sandbox route passes `sandbox_mode=False` — fix to `True`; return `400` (not `200 false`) on `construct_event` failure; guard duplicate `stripe_event_id` with unique-index retry idempotency (`src/pvf/db/models/stripe_events.py`).
- `src/pvf/api/share_link_manage.py:186` `numpy.random.randint` → `secrets.token_hex`; `share_password` truncated SHA224 → `bcrypt`/`argon2` with per-row salt; hash `access_magic_key` rather than storing plaintext `share_link_tracking.py:207`; enforce `share_password` validation beyond `re.search(r'[\w.]+\@[\w.]+')` `share_link_manage.py:823`.
- `src/pvf/api/auth.py:52` throttle is process-global `anti_flooding_time`; replace with Redis/IP-bucketed throttle (§1.1). Fix `usr_contextx` typo `auth.py:236,240` that drops audit `customer_id/user_id`. Make cookie `secure` conditional on `is_prod()` (like `app_branding.py`).
- `src/pvf/utils/callback_delivery.py:137` `requests.post` without timeout → `httpx.AsyncClient` with `timeout=settings.AI_HTTP_TIMEOUT_SECONDS` `src/pvf/config/pvf_config_settings.py:298` and retry budget from `pvf_watcher_job.retry_delays`.
- `src/pvf/utils/field_encryption.py` fallback to `JWT_SECRET_KEY` with static HKDF salt — require `PVF_FIELD_ENCRYPTION_KEY` `src/pvf/config/pvf_config_settings.py:300` or fail-closed.

### 4.3 Config hygiene

- `src/pvf/config/pvf_config_settings.py:7` `TODO process_name getting unset` — make `process_name` a `ClassVar` or computed `@property` so `PvfGlobalSettings()` re-instantiation in `pvf_get_alembic_config.py` / tests does not revert it.
- `pvf_config_settings.py:10` `pvf_env_dir = path.abspath(getcwd())` is CWD-sensitive — switch to `Path(__file__).resolve().parents[2]` (workspace root) as `_WORKSPACE_ROOT` in `pvf_app_runner.py:44`.
- `pvf_config_settings.py:79` `extra="ignore"` silently swallows `.env` typos — warn in non-prod (`log_event` severity 2).
- `pvf_config_settings.py:86,253,258` `bool(int(environ.get…))` fragile (`"false"` → `ValueError`) and `WATCHER_PROCESS_MODULE_LIST` `253` `['']` when empty — switch to `Field(…)` with pydantic coercion or `strtobool`.

---

## 5. Application — PowerChoice improvements

### 5.1 Architecture

| Priority | Issue | Location | Change |
|----------|-------|----------|--------|
| P1 | **Synchronous LLM in request** blocks the FastAPI event loop N× seconds | `src/api/app_customer_project_management.py:892` loop `generate_*_prompt_sync` per alt/fac, `src/api/app_customer_project_content_management.py:445,535` per-item `generate_*_prompt_sync` | Enqueue to `pvf:llm` watcher module (§2.4); endpoint returns `202 {queued_count}` already surfaced by `compare-prompts-status:1070`. Remove inline `session.commit()` per item. |
| P1 | Duplicate vote flows 80% (session vs share) | `src/api/app_project_vote_events.py:354-546` vs `src/api/app_shared_link_ext_access.py:471-722` (`_issue_next`, `validate_group_package`) | Extract `src/utils/vote_session_service.py` shared by both routers; inject `scope`/`share_context` — one place to patch sort/ranking changes. |
| P2 | No DB uniqueness on `(customer_id, project_tag)` | `src/db/models/customer_projects.py:34` single-col indexes only; concurrent `POST /customer-project-create:289` can dupe | Add `UniqueConstraint(customer_id, project_tag, deleted_date)` (partial where `deleted_date IS NULL`) + `IntegrityError` → `422` in `create_customer_project:124`. |
| P2 | `next_group_cache` `src/utils/next_group_cache.py:8` volatile dict, TTL 300 s, no size bound, not cross-process | Replace with `PvfWatcherJob`-backed or Redis `SETEX project:participant:group` when `REDIS_URL` set; fallback dict already Redis-gated. |
| P2 | `project_group_size.sync_project_group_sizes` `src/utils/project_group_size.py:41` extra write per alt/factor mutate | Compute `resolve_questions_per_group` `src/utils/sort_compare.py:301` and only `session.commit()` on delta; add SQL `WHERE disabled=false` instead of Python `sum(1 …):25`. |

### 5.2 Performance

| Priority | Area | Loc | Fix |
|----------|------|-----|-----|
| P1 | **Unbounded project loads** | `src/api/app_dashboard_views.py:174` `SELECT … WHERE customer_id=…` `.all()` then `[:max(limit,5)]:263`; `src/api/api_probe_customer_status.py:38` ignores `page_index/page_size:24` (`page_size default 1_000_000`) | Enforce `limit/offset` + cursor (`ORDER BY id DESC`), return `total_count`; apply pagination to `alternatives/factors` `GET …/alternatives-get-by-project-id:188` etc. |
| P1 | **BT Laplace per-request CPU** | `src/utils/bt_inference/laplace.py:52` `O(D²)` Hessian + `minimize 400 iters:92`, draws 80-2000 | `asyncio.to_thread` / `ThreadPoolExecutor`; raise LRU 64→512 `bt_inference/cache.py:10`; pre-warm on `complete-group`. |
| P2 | N+1-ish `count_active_*` scans | `src/utils/project_group_size.py:18` | Push `WHERE disabled=false AND deleted_date IS NULL` to SQL; reuse `sync_project_group_sizes` result across batch creates. |
| P2 | `private_participation.has_non_creator_comparisons:20` loads all participants twice | — | Single query `WHERE participant_key != creator_key AND source != 'ai' LIMIT 1`. |
| P2 | Email-style fan-out on hub page | `src/utils/project_overview_participation.py:133` loads all share invite emails then Python filter by `magic_token:144` | `WHERE email_params_json->>'magic_token' IN (…)` with GIN index or secondary `(magic_token)` index. |
| P2 | Large bundle payloads | `src/api/app_project_vote_events.py:733` `project-bundle` returns all groups + pivot | `?include=report|groups|participants&limit=` pagination. |
| P2 | AI watcher per-pair `commit` churn | `src/utils/ai/worker.py:388` `session.add(job); commit; refresh` per pair | Flush once per `AI_PAIRS_PER_TICK` tick (already 20 — batch results). |

### 5.3 Maintainability & frontend

- Split large routers (`app_customer_project_management.py:1084`, `app_shared_link_ext_access.py:965`) by tag (`project-crud`, `compare-prompts`, `project-votes`).
- Normalize error contract — `WsResultPackage.failure_reason` sentinel vs `HTTPException`; typed `AppError` codes (keeps `src/pvf/utils/pvf_base_internal_resources.py:21` but adds enum).
- `client/utils/ranking.ts` mirrors `src/utils/vote_ranking.py` — keep parity via shared contract test `ranking.test.ts` ↔ `test_bt_inference.py` (intentional duplication; document ownership).
- Version drift `client/package.json:3` `0.7.90` vs `src/config/config_settings.py:13` `0.7.91` — bump together per `AGENTS.md:139`.
- Remove `from src...` / relative mix (`AGENTS.md:57` `PYTHONPATH` note) after watcher lands — prefer absolute `src.` imports for Alembic parity.
- Hard-coded test signup URL `src/api/test_helpers.py:108` `localhost:8000` vs proxy `8100` — read `settings.APPLICATION_BASE_URL:89`.

---

## 6. PVF interface compliance — today and after Phase 1

### 6.1 Prescribed surfaces (`src/pvf/README.md:45`)

`pvf.pvf_app_runner` · `pvf.pvf_get_alembic_config` · `pvf.utils.pvf_services` · `pvf.pvf_invocation` · `pvf.config.pvf_config_settings` · `pvf.depends.*` · `pvf.db.models.*`

### 6.2 Current bypasses — production code (tests excluded)

Reproduced via `grep -r "from.*pvf\." src --include="*.py" | grep -v "__pycache__" | grep -v "pvf/bindings" | grep -v "tests/" | grep -v "^src/pvf/"` :

| File | Import | Prescribed import | Notes |
|------|--------|-------------------|-------|
| `src/powerchoice_watcher.py:14` | `from .pvf.utils import utils_show` | `from .pvf.bindings.pvf_services import log_event` (`pvf_services.py:65`) | Debug helper; replace with `log_event` facade or re-export `debug_log` |
| `src/powerchoice_watcher.py:29,34,36` | `pvf.config.pvf_config_settings.pvf_settings`, `pvf.db.connect.DatabaseConnection`, `pvf.db.models.pvf_bootstrap`, `pvf.depends.api_session_dependencies.get_next_session`, `pvf.utils.callback_delivery` | Partially `pvf_services` (settings, `DatabaseConnection`, `import_all_models`, `get_next_session` are re-exported at `pvf_services.py:92`), but `callback_delivery` is not | **Intended watcher exception** — Phase 1 moves `callback_delivery` to `pvf_watcher_service` and re-exports `check_for_callbacks_ready` or removes the need for direct import |
| `src/utils/ai/worker.py:10` | `from ...pvf.utils import utils_show as ut` | `pvf_services.log_event` | Replace `ut.show_vars_semi` with `log_event` (already used `src/app_shell.py:132`) |
| `src/utils/ai/reword_worker.py:12,13` | `pvf.utils.utils_show`, `pvf.utils.log_event` | `pvf_services.log_event` | Same |
| `src/utils/ai/prompts.py:142,277,337` | `pvf.utils.utils_show` (4 sites) | Remove debug logging from pure prompt formatting or inject via `runtime_settings` `ai/prompts.py:37` | Prompts are not a watcher concern |
| `src/utils/ai/config.py:37` | `from ...pvf.config.pvf_config_settings import pvf_settings` (fallback after `runtime_settings` `config.py:18`) | Keep only `from ...pvf.bindings.pvf_invocation import runtime_settings` (which is actually a prescribed `pvf.pvf_invocation` entry) | Remove fallback import |
| `src/utils/project_overview_participation.py:12` | `from ..pvf.db.models.email_activity_log import EmailActivityLog` | Not in `pvf_services` today — see §6.3 | Read helper needed |
| `src/utils/analytic_tracking.py:112,130` | `from ..pvf.utils.log_event import log_event` | `pvf_services.log_event` | One-line fix |

All `src/api/*` and `src/db/models/*` are **clean** — every `from …pvf` is `..pvf.bindings.pvf_services` (e.g. `src/api/app_customer_project_management.py:13`).

### 6.3 Closing the gaps in Phase 1 + §4

To make "no `from pvf.` outside bindings" enforceable in CI, extend `src/pvf/bindings/pvf_services.py:114`:

```python
# Add to __all__ / _LAZY_ATTRS — no new pvf internals exposed, just published facades:
from ..utils.branding_image import process_branding_upload, MAX_BRANDING_UPLOAD_BYTES  # today src/pvf/api/app_branding.py:20 bypasses
from ..db.models.email_activity_log import EmailActivityLog  # read-only helper for throttling fan-out
from ..services.pvf_watcher_service import PvfWatcherRegistry, PvfWatcherModule, get_watcher_registry
# optional debug shim:
from ..utils.log_event import log_event  # already exported — keep; add debug_log = log_event wrapper
```

Then:

```bash
# CI gate (add to scripts/check_pvf_isolation.sh)
! grep -r "from.*pvf\." src --include="*.py" \
    | grep -v "__pycache__" \
    | grep -v "pvf/bindings" \
    | grep -v "tests/" \
    | grep -v "^src/pvf/" \
    | grep -v "watcher_modules.yaml" \
    && echo "pvf isolation OK"
```

`src/tests/*` is allowed to import internals directly (needed for `helpers/factories.py:1` `ApiAccessConfiguration`, `helpers/cleanup.py`, `test_callback_delivery.py:1`; ` AGENTS.md:146` calls these tag-clustered helpers intentional).

---

## 7. Sequenced implementation & testing plan

### Phase 1 — Watcher / Redis / Email / LLM (requested)

1. **Settings + YAML** — add `REDIS_URL`, `REDIS_THROTTLE_ENABLED`, `EMAIL_DELIVERY_MODE`, `EMAIL_ASYNC_POLL_*` to `src/pvf/config/pvf_config_settings.py:1`; add `src/watcher_modules.yaml` loader to `src/pvf/bindings/pvf_startup_config.py:1` (mirrors `load_startup_config:95`); extend `apply_startup_config` read-only guard (`pvf_config_settings.py:124`) to cover `REDIS_URL` if you want it deployment-fixed (recommended) or keep it env-overridable (as in §1.1 — either is defensible, document the choice).
2. **Watcher service + table** — add `src/pvf/db/models/watcher_jobs.py` + `src/pvf/services/pvf_watcher_service.py`; extend `PvfInvocation` with `watcher_modules` (`src/pvf/bindings/pvf_invocation.py:81`); extend `pvf_services` facade (§6.3). Generate Alembic migration: `pvf_watcher_job` + indexes (§2.2).
3. **Email async** — extend `src/pvf/utils/outbound_mail_queue.py:32` with `delivery`/`async_timeout` and polling (§3.3); implement `pvf:email` module; add `EmailActivityLog.get_queued_email_status` helper.
4. **LLM generic module** — implement `pvf:llm` module (§2.4); migrate compare-prompt endpoints (`app_customer_project_content_management.py:408`, `app_customer_project_management.py:798`) to enqueue path; keep `LlmError.retryable` semantics.
5. **Redis adapter** — `src/pvf/services/redis_service.py` (`get_redis_client`, `throttle_incr(key, window, limit) -> bool` stub). Wire into `share_gate_throttle.py:9`, `outbound_mail_queue.py:40`. Default off when `REDIS_URL` empty.
6. **PowerChoice shim** — slim `src/powerchoice_watcher.py` to the 40-line shim; move `process_next_ai_job` (`src/utils/ai/worker.py:116`) into an `app:ai_agents` watcher module implementation registered from `src/app_shell.py:47` (`register_watcher_modules`).
7. **Tests** — extend `src/tests/conftest.py` to set `REDIS_URL=""`, stub `get_redis_client` → in-memory fake, stub `query_llm_model` (like SendGrid autouse mock `conftest.py:91`). Add `test_pvf_watcher_service.py`, `test_email_async_poll.py` (sync-like 10 s poll vs timeout), `test_redis_throttle_fallback.py`. Keep DB tests shared-DB-aware (`helpers/cleanup.py`).
8. **OpenAPI & docs** — no endpoint path changes in Phase 1 (only behavior), but regenerate `openapi_sessions.json` if the enqueue status shape (`queued_count`) changes (`./scripts/extract_openapi/update_openapi_json.sh sessions`).

### Phase 2 — Backlog (P0/P1 security & hot-path perf)

Apply §4.1-4.3 in small shippable sets: one migration per index batch, one PR per throttle/cookie hardening slice. Verify each with `src/.venv/bin/pytest src/tests/test_callback_delivery.py src/tests/test_outbound_mail_* src/tests/test_share* -x` and a local watcher run (`python -m src.powerchoice_watcher`).

### Phase 3 — Application hardening (P1/P2)

Apply §5 incremental: pagination (behind `?limit=` with backward-compat default), ranking offload, vote-service extraction. Each router split must be accompanied by its tag-cluster test (`AGENTS.md:151`).

**Definition of done per phase:** `PYTHONPATH=. src/.venv/bin/pytest src/tests/` green against a clean Postgres (`./scripts/migrations/run-migrations.sh` without `BOOTSTRAP_SAMPLE_DATA`), `./scripts/extract_openapi/update_openapi_json.sh sessions` diff clean, and `grep -r "from.*pvf\." src … | grep -v bindings` empty (or only the documented watcher shim).

---

## 8. Revisit checklist — after the watcher refactoring lands

- [ ] Verify `src/powerchoice_watcher.py` is the thin shim; `grep -r "from.*pvf\." src --include="*.py" | grep -v bindings | grep -v tests | grep -v ^src/pvf/` → no application-owned `pvf.utils`/`pvf.db` lines remain (except `src/watcher_modules.yaml` loader).
- [ ] Measure async email: p50 poll completions within `EMAIL_ASYNC_POLL_SECONDS=10` on staging with `USE_EMAIL_SERVICE=SMTP-JINJA` and with `SENDGRID`; confirm callers observe sync-like flow (share invite, password reset) within timeout >95% of the time at 10 RPS.
- [ ] Redis path: deploy with `REDIS_URL` set and unset; confirm fallback throttling keeps limits and that `conftest` stub covers `fakeredis` missing in CI (conditional skip).
- [ ] LLM generic path: `compare-prompt-status` shows `queued → complete` without request-thread `generate_*_prompt_sync`; watcher `pvf:llm` metrics (`attempts`, `retryable`) visible in `pvf_watcher_job.result_json`.
- [ ] File issues for remaining P0-P1 security items if not covered by Phase 1 (share password hashing, sandbox flag, `usr_contextx` typo).
- [ ] Update this doc's title date and remove this section, or replace with `docs_examples/watcher_service.md` + `docs_examples/redis_throttling.md` split docs.

---

## Appendix A — Files to touch first

| File | Why |
|------|-----|
| `src/pvf/config/pvf_config_settings.py:1` | `REDIS_URL`, `EMAIL_DELIVERY_MODE`, watcher tunables |
| `src/pvf/bindings/pvf_startup_config.py:1` | `load_watcher_modules_config`, `apply_startup_config` read-only |
| `src/pvf/bindings/pvf_invocation.py:81` | `watcher_modules: PvfWatcherRegistry` |
| `src/pvf/bindings/pvf_services.py:1` | Re-export `EmailActivityLog`, `process_branding_upload`, watcher registry (closes §6) |
| `src/pvf/services/pvf_watcher_service.py` | New — registry, poll loop, claim/execute |
| `src/pvf/services/redis_service.py` | New — optional Redis accessor + stub |
| `src/pvf/db/models/watcher_jobs.py` | New — `pvf_watcher_job` table |
| `src/pvf/utils/outbound_mail_queue.py:32` | `delivery`/`async_timeout` + poll |
| `src/pvf/utils/llm_client.py:129` | `httpx.AsyncClient` pool, keep `LlmError.retryable` |
| `src/pvf/utils/callback_delivery.py:35` | Limit + `FOR UPDATE SKIP LOCKED` |
| `src/powerchoice_watcher.py:1` | Slim to shim |
| `src/app_shell.py:47` | Register `app:ai_agents` / `app:reword` watcher modules |
| `src/watcher_modules.yaml` | New — module catalog |
| `example.env:1` | Template entries for `REDIS_URL`, `EMAIL_*` |
| `src/tests/conftest.py:1` | Redis stub, watcher registry fixture |

## Appendix B — Non-goals for Phase 1

- No rename of DB/JSON fields (`alternative_*`, `criteria` observation type) — keep internal vocabulary, user-facing terms are `terminology_dictionary.md`.
- No new REST surface beyond `delivery`/`async_timeout` params; callback and share APIs keep wired behavior (`/ws`, `/ext-ws`, `/api` mounts `src/pvf/pvf_app_runner.py:451`).
- No switch of `USE_EMAIL_SERVICE` semantics; watched queue reuses existing SendGrid/SMTP-Jinja backends.
