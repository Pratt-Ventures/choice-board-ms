# log_event json details_json

## Short Description
### user
We want to standardize the approach in the code.

Change manual JSON load/save in details_json, in ApplicationLogEvent to use the JSONB approach used in the project_vote_events.py for relevant tables there.
[comment: updated 2026-08-15T19:36:38.574Z | id log-event-json-details-json-1r94ya]

## Expanded Description
### agent
I'll inspect `ApplicationLogEvent` and the JSONB pattern in `project_vote_events.py` so the expansion matches the codebase.I'll read the log-event model and the vote-events JSONB pattern next.Standardize `ApplicationLogEvent.details_json` so it is stored as PostgreSQL JSONB and assigned as native Python dict/list objects, matching `ProjectVoteGroupResult` JSONB columns in `project_vote_events.py` instead of `json.dumps` into a string. Today the column is `str | None` (AutoString from the initial migration), and both `log_event.py` and `log_events_request.py` serialize payloads by hand—including pydantic `model_dump` fallbacks and a string error placeholder. After the change, writers should pass objects through and SQLAlchemy/JSONB should persist them; readers and the recent-events API will return structured JSON rather than a string.

- Scope: model field type, Alembic alter of `applicationlogevent.details_json`, and drop/adjust manual serialize in `log_event.py`, `log_events_request.py`, and any other writers (e.g. bootstrap already passes a dict).
- Follow the vote-events / `email_params_json` pattern: `sa_column=Column(JSONB, …)` plus a `postgresql_using` CAST that treats NULL/blank as NULL (or `{}`) and coerces existing string JSON.
- Keep accepting both list and dict (current API and the conversion-failure placeholder are list-shaped); decide whether to coerce pydantic models to dict at the helper boundary or require callers to pass JSON-serializable objects.
- Response/contract: `/ws/log/recent-events` returns the model as-is, so clients will see an object instead of a JSON string; confirm no UI/tests parse `details_json` as text.
- Open: what to do with rows that are not valid JSON; whether NULL vs `{}` is the empty default; and whether `log_event` should still catch non-serializable values or let insert fail.
[comment: expand completed 2026-08-15T19:37:41.218Z | via executor-opencode | entryId e-20260815-0001 | artifacts: ./log-event-json-details-json-1r94ya/2026-08-15T19-36-38-602Z-expand-j1m8gt.request.md, ./log-event-json-details-json-1r94ya/2026-08-15T19-36-38-602Z-expand-j1m8gt.response.md, ./log-event-json-details-json-1r94ya/2026-08-15T19-36-38-602Z-expand-j1m8gt.trace.log, ./log-event-json-details-json-1r94ya/2026-08-15T19-36-38-602Z-expand-j1m8gt.result.json]


## Plan
### agent
I'll inspect the log-event model and the vote-events JSONB pattern so the plan matches the codebase.Graphify is available; I'll query it and inspect the log-event and vote-events JSONB code in parallel.Next I’ll read the model, writers, and existing JSONB migrations so the plan can follow the project’s pattern.I have the model and writers; next I’ll check callers, tests, UI, and the latest Alembic head.## Plan: store `ApplicationLogEvent.details_json` as JSONB

Mirror `ProjectVoteGroupResult` / `EmailActivityLog.email_params_json`: assign dict/list objects; drop `json.dumps`. Keep the column nullable and dual-shaped (`dict | list | None`) — unlike `email_params_json` (`{}` NOT NULL), this field is optional and already list-shaped in the API and the conversion-failure placeholder.

### 1. Implementation steps

1. **Model** — In `src/db/models/application_event_log.py`, import `JSONB` and change the field to:
   `details_json: dict[str, Any] | list[Any] | None = Field(default=None, sa_column=Column(JSONB, default=None, nullable=True))`
   Pattern matches `client_settings` / template JSONB columns, not the NOT NULL `email_params_json` default.

2. **Alembic** — Add `n5o6p7q8r9s0` (`down_revision="m4n5o6p7q8r9"`) altering `applicationlogevent.details_json` VARCHAR → `postgresql.JSONB`.
   - Upgrade `postgresql_using`: `CASE WHEN details_json IS NULL OR btrim(details_json) = '' THEN NULL ELSE details_json::jsonb END`
   - Keep `nullable=True`. Downgrade: `details_json::text`.
   - Existing writers only store `json.dumps` output, the list-shaped error placeholder, or NULL — CAST should succeed on current data.

3. **`log_event` helper** (`src/utils/log_event.py`) — Change the param type to `dict | list | Any | None`. Coerce at the helper boundary, then assign the object (no `json.dumps`):
   - `None` → `None`
   - `dict` / `list` → pass through
   - pydantic (`model_dump`) → dict
   - `str` → `json.loads` if it is a JSON object/array (so leftover string writers still work); otherwise keep as a JSON string value
   - On coerce failure, store a **list/dict placeholder object** (same message as today), not a string. Logging must not fail the caller.

4. **API writer** (`src/api/log_events_request.py`) — Pass `log_ui_event.details_json` through. Drop `json.dumps` and unused `import json`. `PostLogEvent.details_json: Union[list, dict, None]` stays.

5. **Other writers** — `bootstrap_system_templates.py` already passes a dict; no change.

6. **Contract / OpenAPI** — `/ws/log/recent-events` returns the table model as-is, so `details_json` becomes object/array/null instead of a JSON string. No Vue/TS client reads this field. Regenerate `openapi_sessions.json` via `./scripts/extract_openapi/update_openapi_json.sh sessions`.

7. **Tests** — Extend `src/tests/test_devops_logs.py`: POST `details_json` as both a dict and a list; GET `/ws/log/recent-events` and assert the value is a parsed object/list, not a string. Optionally assert `log_event(..., details_json=SomeModel())` persists a dict. Run `src/.venv/bin/pytest src/tests/test_devops_logs.py` (and apply the migration first).

### 2. Clarifying questions

- Invalid existing VARCHAR rows (not valid JSON): fail the migration, or pre-sanitize (wrap as a JSON string) then CAST?
- Confirm NULL (absent) vs `{}` as the empty default — plan uses NULL.
- Confirm `log_event` should still swallow non-serializable values (placeholder object) rather than let insert fail.

### 3. Options and trade-offs

| Choice | Options | Recommendation |
|---|---|---|
| Empty default | NULL (current + `client_settings`) vs `{}` NOT NULL (`email_params_json`) | **NULL.** Field is optional and may be a list; `{}` would lie about shape and collapse “absent” vs “empty object”. |
| Accepted types | dict-only vs `dict \| list` | **`dict \| list \| None`.** `PostLogEvent` and the failure placeholder are already list-shaped. |
| Pydantic / junk values | Require JSON-serializable objects; or coerce in `log_event` | **Coerce in `log_event`.** Only current object caller is bootstrap (dict); helper already has `model_dump` + fallback. Logging must not raise. |
| Bad legacy rows | Bare `::jsonb` (email_params) vs wrap non-JSON as `to_jsonb(text)` | **Bare CAST**, matching `m4n5o6p7q8r9`. Current writers only emit valid JSON or NULL. Add a pre-UPDATE only if a prod scan finds junk. |
| Response contract | Keep returning a string (re-dump) vs native JSON | **Native JSON.** No UI/tests parse it as text; OpenAPI `ApplicationLogEvent.details_json` updates with the snapshot regen. |
[comment: plan completed 2026-08-15T19:40:28.276Z | via executor-opencode | entryId e-20260815-0002 | artifacts: ./log-event-json-details-json-1r94ya/2026-08-15T19-37-41-260Z-plan-kc5s0o.request.md, ./log-event-json-details-json-1r94ya/2026-08-15T19-37-41-260Z-plan-kc5s0o.response.md, ./log-event-json-details-json-1r94ya/2026-08-15T19-37-41-260Z-plan-kc5s0o.trace.log, ./log-event-json-details-json-1r94ya/2026-08-15T19-37-41-260Z-plan-kc5s0o.result.json]


## Build Summary
### agent
I'll implement JSONB for `ApplicationLogEvent.details_json` per the plan. First I'll inspect the model, writers, and existing JSONB pattern.Graphify is available; I'll query it while reading the model, writers, and existing JSONB migrations.I have the model and writers. Next I’ll check callers, tests, UI, and the Alembic head.`config_settings.py` is already dirty — I'll check VERSION and other JSONB writers before editing.Implementing the model, migration, writers, tests, and version bump.Leftover plain strings would fail `dict | list | None` validation — I'll coerce those so logging cannot raise.Migration applied. Running the devops logs tests next.Staging only this work, then I'll restore the unrelated `APPLICATION_BASE_URL` change after the commit.**Build summary**

`ApplicationLogEvent.details_json` is now JSONB. Writers pass dict/list objects; `log_event` coerces pydantic/`json.dumps` leftovers and stores a list placeholder on failure. Empty stays NULL. `src/.venv/bin/pytest src/tests/test_devops_logs.py` — 8 passed. Regenerated untracked `openapi_sessions.json` (not committed).

**Touch points**
- `src/db/models/application_event_log.py:43-45` — `details_json: dict | list | None` + `Column(JSONB)`
- `src/alembic/versions/n5o6p7q8r9s0_details_json_to_jsonb.py:20-31` — VARCHAR → JSONB (`NULL`/blank → NULL)
- `src/utils/log_event.py:11-45,83` — coerce helper; assign object, no `json.dumps`
- `src/api/log_events_request.py:58-68` — pass `details_json` through
- `src/tests/test_devops_logs.py:77-124` — object/list API + pydantic helper
- `src/config/config_settings.py:79-80` — `0.7.26`

**Commit** `fa538d7` — Store ApplicationLogEvent.details_json as native JSONB
[comment: build completed 2026-08-15T19:46:48.205Z | via executor-opencode | entryId e-20260815-0003 | artifacts: ./log-event-json-details-json-1r94ya/2026-08-15T19-40-28-324Z-build-qhru05.request.md, ./log-event-json-details-json-1r94ya/2026-08-15T19-40-28-324Z-build-qhru05.response.md, ./log-event-json-details-json-1r94ya/2026-08-15T19-40-28-324Z-build-qhru05.trace.log, ./log-event-json-details-json-1r94ya/2026-08-15T19-40-28-324Z-build-qhru05.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-15T19:46:48.206Z build completed (e-20260815-0003)
- 2026-08-15T19:40:28.276Z plan completed (e-20260815-0002)
- 2026-08-15T19:37:41.218Z expand completed (e-20260815-0001)
- 2026-08-15T18:43:21.523Z created (source: user)
