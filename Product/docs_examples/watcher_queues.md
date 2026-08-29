# Watcher Queues — Consumer Guide (≤80 lines)

**Framework-owned watcher:** `src/pvf/watcher/` + `src/pvf_app_watcher.yaml` (critical bindings, YAML authoritative). App uses `src/pvf/bindings/pvf_watcher_requests.py` (re-exported via `pvf.utils.pvf_services`) — no direct `pvf.watcher.*` imports. See `src/pvf/README.md` entry points and `PVF Architecture §12`; prompt §2 details capture/no-log.

```yaml
# src/pvf_app_watcher.yaml (sibling to pvf_app_startup.yaml) — template: src/pvf/example_pvf_app_watcher.yaml
version: 1
capture_payloads: true          # mirrors WATCHER_CAPTURE_PAYLOADS (env bool, default 1)
no_log_request_types: []        # union with WATCHER_NO_LOG_TYPES (env csv); [] in prod, cleared in dev/test; no-log wins even on error
types:
  llm: {kind: pvf, module: src.pvf.watcher.handlers.llm, entry: handle_llm}
  outbound_email: {kind: pvf, module: src.pvf.watcher.handlers.email, entry: handle_email}
  outbound_api_call: {kind: pvf, module: src.pvf.watcher.handlers.api, entry: handle_api}
  SHORTEN_PRODUCT_NAME: {kind: app, module: src.app.watcher_handlers, entry: shorten_product_name}
```

**Enqueue (tenancy injected, encryption handled):**
```python
from src.pvf.utils.pvf_services import queue_llm_request, queue_generic_request  # or pvf.bindings.pvf_watcher_requests
queue_llm_request(session=session, usr_context=usr_context, provider="opencode_go", model="glm-5.2", api_key="…", messages=[…], prompt="…", semantic_tag="SHORTEN_PRODUCT_NAME", metadata={})
queue_generic_request(session=session, usr_context=usr_context, work_type="SHORTEN_PRODUCT_NAME", request_package={"product_name": "Acme …"}, semantic_tag="SHORTEN_PRODUCT_NAME")
# also queue_email_request(to_email, template_type, params, semantic_tag) and queue_api_request(target_url, http_method="POST", connection_protocol="pvf", auth_protocol="pvf", auth_params, payload, headers, semantic_tag)
# get_*/list_* verify row.customer_id == usr_context.sess_user.customer_id; caller ids ignored; _system NULL path is framework-only
```

**App handler registration** (`src/app_shell.py`):
```python
def register_watcher_handlers(registry):  # PvfWatcherRegistry
    registry.register("SHORTEN_PRODUCT_NAME", WatcherTypeSpec(kind="app", module="src.app.watcher_handlers", entry="shorten_product_name"))
```

**Handler contract:**
```python
def my_handler(inv: PvfWatcherInvocation) -> WatcherInvocationResult: ...
# inv = {row: dict, customer_id, user_id, work_type, semantic_tag, request_package, attempt, max_attempts, orchestration: {status, retries_remaining, next_attempt_at, is_no_log}, session_factory}
# return WatcherInvocationResult(failure_reason="", result_package={}, error_package={}, retryable=None, next_delay_s=None)
# framework maps retryable False→no_retry, True+attempts<max→will_retry(queued, next_attempt_at=now+delay), True+exceeded→max_retries_exceeded, ""→complete
```

**Status:** `queued→trying→{complete|will_retry|no_retry|max_retries_exceeded}` (`failed` alias). Capture: `should_capture(tag)` and `redact_for_no_log` / `is_no_log_tag`. App wrapper `src/utils/ai/pvf_llm.py` shows BYOK resolution before queueing; `poll.poll_and_dispatch` + `service.run_watcher_forever` + `runner.main` run it.

Run: `python -m src.pvf.watcher.runner` (or shim `python -m src.powerchoice_watcher`). See `scripts/migrate_watcher_env_to_yaml.py`.
