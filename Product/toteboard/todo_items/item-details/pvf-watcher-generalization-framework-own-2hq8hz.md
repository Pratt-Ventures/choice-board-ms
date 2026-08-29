# PVF watcher generalization — framework-owned watcher service (2026-08-24)

## Short Description
### user
Overview:
Collapses ad-hoc powerchoice_watcher.py + utils/ai polling into framework-owned src/pvf/watcher/. Dedicated queue tables for known PVF types + one generic queue; bound via deployment-fixed src/pvf_app_watcher.yaml (critical bindings only, YAML authoritative) and PvfInvocation.watcher_registry populated at app_startup (app_shell.register_watcher_handlers). Only YAMLs + .env remain outside src/pvf/ — shells/models/bindings/handlers all live in src/pvf/.

Punchlist:
• Settings/YAML: WATCHER_CAPTURE_PAYLOADS (default True) + WATCHER_NO_LOG_TYPES (csv) in PvfGlobalSettings; PvfWatcherConfig/WatcherTypeSpec + load_watcher_config/apply_watcher_config in pvf_startup_config.py; wired into pvf_app_runner.py + pvf_get_alembic_config.py; example YAMLs + deprecation header on example.application_watcher.py + scripts/migrate_watcher_env_to_yaml.py
• Tables: 4 SQLModels (watcher_llm/email/api/generic) with claim indexes, re-exports in db/models/watcher_*.py, registered in pvf_bootstrap, Alembic 20ba6b8d0df6 applied
• Orchestration/registry: WatcherStatus, PvfWatcherInvocation, WatcherInvocationResult, WatcherEventOrchestration, redact/is_no_log/should_capture helpers; PvfWatcherRegistry on PvfInvocation (pvf_invocation.py)
• Binding pvf_watcher_requests.py: queue/get/list per type with tenancy (customer_id/created_by_user_id from UserContext, caller ids ignored, cross-tenant → not found), encryption via field_encryption + PVF_FIELD_ENCRYPTION_KEY, semantic_tag (default None, no_log-aware), internal _system NULL path; app wrapper src/utils/ai/pvf_llm.py
• Poll/service: poll_and_dispatch (SELECT FOR UPDATE SKIP LOCKED, queued→trying→{complete|will_retry|no_retry|max_retries_exceeded}), handlers llm (query_llm_model + LlmError.retryable), email (deliver_email_package off thread), api (generalized callback_delivery, target_url/auth_params_encrypted, V1 pvf), service.run_watcher_forever + runner.main; slim powerchoice_watcher.py (~14 lines); app glue SHORTEN_PRODUCT_NAME in src/app/watcher_handlers.py
• Docs: README entry-points, PVF Architecture §3/4/12, docs_examples/watcher_queues.md (42 lines), pvf_services re-exports
• Tests: test_watcher_{llm,email,api,generic}_queue (tenancy, encryption, capture/no_log, SHORTEN_PRODUCT_NAME round-trip, httpx mock), extended test_callback_delivery registry roundtrip; fixed test_manage_project_content deprecation + version sync (0.7.91→0.7.92) + static_client rebuild; full pytest 469 passed
• Checklist: watcher/ populated, bindings reachable, capture/no_log union honored (incl. error), semantic_tag + SHORTEN_PRODUCT_NAME OK, cross-customer not found, _system NULL, pvf protocols default, httpx mock complete, thin forwarder + example YAMLs
[comment: created 2026-08-24T02:40:59.995Z | id pvf-watcher-generalization-framework-own-2hq8hz]

## Expanded Description

## Plan

## Build Summary

## Code Review Guide

## UI Review Guide

## History
- 2026-08-24T02:40:59.995Z created (source: user)
