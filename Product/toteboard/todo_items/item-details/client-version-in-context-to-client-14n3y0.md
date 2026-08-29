# Client version in context to client

## Short Description
### user
Ensure both the client and server versions are in the context sent to the client.

If the client version doesn't match the active version, add a notice near the top suggesting they reload for the latest version with an action to reload. Use a yellow box like many applications.
[comment: created 2026-08-22T14:38:32.263Z | id client-version-in-context-to-client-14n3y0]

## Expanded Description
### agent
Expose both client build version and server active version in the context payload delivered to the client (e.g., initial bootstrap/context endpoint or injected config), compare them on the frontend, and when mismatched render a prominent dismissible yellow banner near the top of the app suggesting the user reload for the latest version with an explicit Reload action.

* Scope: Add server active version and client expected version to client context/API response + frontend detection/comparison and banner UI; no backend versioning logic changes beyond exposing existing active version.
* Scope: Banner placement near top (above main content/app shell), yellow warning style, with text like "A new version is available — reload to update" and button/link that triggers `window.location.reload()`.
* Consideration: Source of truth for versions — client version from build-time injection (e.g., `APP_VERSION`/`package.json`/`Vite` define) vs. server version from deployment/config; ensure cache-busting and avoid false positives.
* Consideration: Comparison logic — strict equality vs. semver, handling missing/undefined versions gracefully, and option to dismiss/snooze per session via local state without hiding future updates.
* Consideration: Rollout/UX — banner should not block interaction, should be accessible, and should auto-dismiss after successful reload; consider polling or on-focus re-check for long-lived sessions.
* Open question: Should mismatch also be logged/telemetered for staleness monitoring?
[comment: expand completed 2026-08-22T14:39:29.071Z | via executor-opencode | entryId e-20260822-0001 | artifacts: ./client-version-in-context-to-client-14n3y0/2026-08-22T14-38-32-297Z-expand-6hub71.request.md, ./client-version-in-context-to-client-14n3y0/2026-08-22T14-38-32-297Z-expand-6hub71.response.md, ./client-version-in-context-to-client-14n3y0/2026-08-22T14-38-32-297Z-expand-6hub71.trace.log, ./client-version-in-context-to-client-14n3y0/2026-08-22T14-38-32-297Z-expand-6hub71.result.json]


## Plan
### agent
Drafting your version-mismatch execution plan — first mapping your client/server version wiring.**Execution Plan — Node `client-version-in-context-to-client-14n3y0` (FAST TRACK)**

**Overall:** Expose server `active version` (`src/config/config_settings.py:13` `VERSION=0.7.80` via `pvf_app_runner.py:375` `/status` / invocation.application_version) and client build version in the context payload delivered to browser, compare on frontend, render dismissible yellow banner with `Reload` → `window.location.reload()`.

**Summary Scope:** Backend: add version fields to `UserCustomerContextView` (`src/pvf/api/app_context_views.py:141`) populated from `runtime_settings()`/ `invocation_context`. Frontend (Nuxt3 SPA `client/nuxt.config.ts:16`, `client/app.vue:1`, `client/layouts/default.vue:91`): inject `APP_VERSION`, compare, banner. No new versioning logic.

**Numbered Implementation Steps**

1. **Backend — Add versions to context view:** Extend `src/pvf/api/app_context_views.py:141` `UserCustomerContextView` with `server_version: str|None` and `client_expected_version: str|None` (or `active_version`/`client_version`). Alternative: reuse `settings` blob but explicit fields preferred for typed client (`client/types/api.ts:59`). Populate in `get_user_customer_context()` `src/pvf/api/app_context_views.py:192` from `runtime_settings().VERSION` or `pvf_settings.PVF_VERSION` / `invocation_context.application_version`. Ensure both `/ws/core/get-user-customer-context` `src/pvf/api/app_context_views.py:185` and `/auth-ws/login-and-get-context` `src/pvf/api/app_context_views.py:176` return it (they share builder). Keep `GET /status` `src/pvf/pvf_app_runner.py:372` as fallback/telemetry.

2. **Build-time client version injection:** In `client/nuxt.config.ts:16` add `runtimeConfig.public.appVersion` from `package.json` version + `src/config/config_settings.py:13` sync, or Vite `define: { __APP_VERSION__: JSON.stringify(version) }` reading `client/package.json:3` and/or env `APP_VERSION`. At present `client/package.json:2` has no `version` field — add it and keep bumped with `src/config/config_settings.py:13` per `AGENTS.md:139`. Inject at `nuxt build`.

3. **Types & OpenAPI regen:** Update `client/types/api.ts:59` `UserCustomerContextView` interface to match backend. Run `src/pvf/pvf_app_runner.py:379` sessions OpenAPI rebuild and regenerate `openapi_sessions.json`/`openapi_api.json`.

4. **Frontend comparison composable:** Create `client/composables/useVersionCheck.ts` (or extend `client/composables/useAuth.ts:19`). Logic: `clientVersion = useRuntimeConfig().public.appVersion`; `serverVersion = context.value?.server_version ?? context.value?.settings?.server_version`; `mismatch = !!clientVersion && !!serverVersion && clientVersion !== serverVersion`. Strict string equality (no semver parsing). Gracefully handle `undefined/null` → no banner, avoid false positive on dev where versions absent. Optional `console.warn` + telemetry hook.

5. **Banner UI component:** Create `client/components/VersionBanner.vue` — `v-alert type="warning"` yellow (`color="warning"` like `client/layouts/default.vue:164`), prominent near top above `page-container`. Props: `serverVersion`, `clientVersion`. Text: "A new version is available — reload to update." Actions: `Reload` button `window.location.reload()` and `Dismiss` button. Accessible (role="alert", aria-live, focusable button). Non-blocking, not modal. Styled yellow box per brief.

6. **Layout integration & dismissal state:** Insert banner in `client/layouts/default.vue:158` `<v-main>` top (above read-only alert) and optionally `client/layouts/auth.vue`, `client/layouts/share.vue` for share flows. Dismiss per-session via `sessionStorage.setItem('versionBannerDismissed:<serverVersion>', '1')`; re-show on next load or when `serverVersion` changes. Auto-dismiss after reload naturally.

7. **Long-lived session re-check (optional but recommended):** On `window.focus` / `visibilitychange` and/or 5-15m polling call `refreshContext()` `client/composables/useAuth.ts:104` or `apiFetch('/status')` `client/components/AboutDialog.vue:59` and recompute mismatch. Keeps banner current without polling storm.

8. **Tests, cache, telemetry:** Add `src/tests/test_context.py:42` assertion that context contains versions. Add e2e check in `e2e/`. Ensure Vite/Nitro cache-busting via hashed assets (Nuxt default) + no `appManifest: false` masking. If telemetry desired, log mismatch to `log_event` or frontend analytics; don’t block UX.
[comment: plan completed 2026-08-22T14:42:26.623Z | via executor-opencode | entryId e-20260822-0002 | artifacts: ./client-version-in-context-to-client-14n3y0/2026-08-22T14-39-29-114Z-plan-p5wdzo.request.md, ./client-version-in-context-to-client-14n3y0/2026-08-22T14-39-29-114Z-plan-p5wdzo.response.md, ./client-version-in-context-to-client-14n3y0/2026-08-22T14-39-29-114Z-plan-p5wdzo.trace.log, ./client-version-in-context-to-client-14n3y0/2026-08-22T14-39-29-114Z-plan-p5wdzo.result.json]


## Build Summary
### agent
Wiring server and client versions into the banner — exposing, comparing, and prompting reload.Server context now carries version info — next bringing the client build version online.Core types ready — building the version comparison and notification UI.Frontend banner wired — now verifying the changes.Static build confirmed — finalizing the release.**Build Summary — client-version-in-context-to-client-14n3y0**

Commit `fa5dfdfca004cf1299e8bac9066cbc658d75c55e` — `feat: expose client/server versions in context and add mismatch banner`

**Backend — context payload**
- `src/pvf/api/app_context_views.py:141` — `UserCustomerContextView` extended with `server_version: str|None` and `client_version: str|None` (both typed nullable, yellow-banner contract)
- `src/pvf/api/app_context_views.py:95` — new `_active_version()` helper: `invocation_context.application_version` → `runtime_settings().VERSION` → `pvf_settings.PVF_VERSION`, strict string cast, graceful `None`
- `src/pvf/api/app_context_views.py:239-253` — `get_user_customer_context()` now populates `server_version=_active, client_version=_active` on construction (covers both `/ws/core/get-user-customer-context:211` and `/auth-ws/login-and-get-context:202` via shared builder)
- `src/config/config_settings.py:13` — `VERSION 0.7.80 → 0.7.81` (server active version source, also `GET /status` fallback via `src/pvf/pvf_app_runner.py:375`)

**Client — build-time version injection**
- `client/package.json:3` — added `"version": "0.7.81"` (client truth, kept in sync with server per `AGENTS.md`)
- `client/nuxt.config.ts:16-20` — `runtimeConfig.public.appVersion = process.env.NUXT_PUBLIC_APP_VERSION || '0.7.81'` (baked at `nuxt build/generate`, same-origin when served from FastAPI)
- `client/types/api.ts:59` — `UserCustomerContextView` interface adds `server_version?`/`client_version?` + `stripe_callback_prefix_sandbox?`

**Frontend — comparison & banner**
- `client/composables/useVersionCheck.ts:1` — new composable: `clientVersion = runtimeConfig.public.appVersion`, `serverVersion = context.server_version ?? client_version`, `mismatch = strict !==` with missing-guard (no false positive), `showBanner = mismatch && !dismissed`, `sessionStorage` key `versionBannerDismissed:<serverVersion>` per-session dismiss, `console.warn` telemetry, `reload() => window.location.reload()`, 10-min polling + `focus`/`visibilitychange` re-check via `refreshContext()`
- `client/components/VersionBanner.vue:1` — new yellow banner: `v-alert type="warning" color="warning" variant="tonal" prominent`, `role="alert" aria-live="polite"`, text “A new version is available — reload to update.” with `client → server` meta, `Reload` (flat warning) → `window.location.reload()` and `Dismiss` → `sessionStorage`, non-blocking flex layout above content
- `client/layouts/default.vue:159` — banner inserted at top of `<div class="page-container">` above read-only alert; `client/layouts/default.vue:184` `const versionCheck = useVersionCheck()`
- `client/layouts/auth.vue:1` — wrapped slot in `page-container` + same banner with `useVersionCheck` (no-op when unauthenticated)
- `client/layouts/share.vue:31,41` — same banner in share layout; `client/layouts/share.vue:44` `useVersionCheck` added

**Contract & build artifacts**
- `openapi_sessions.json` — regenerated via `src/pvf/pvf_app_runner.py:139 build_sessions_openapi()` → `openapi_sessions.json` now lists `server_version/client_version` on `UserCustomerContextView` (115 paths)
- `static_client/` — rebuilt via `./scripts/nuxt/update_static_client.sh` (`nuxt generate` with empty `NUXT_PUBLIC_API_BASE`, hashed assets, entry CSS guard passed)

**Verification**
- `src/.venv/bin/pytest src/tests/test_context.py` — 15 passed
- Ad-hoc `TestClient` check: `POST /ws/core/get-user-customer-context` returns `server_version: 0.7.81, client_version: 0.7.81`; `/session/docs.json` schema contains both fields
- `./scripts/extract_openapi/update_openapi_json.sh sessions` succeeded
- `./scripts/nuxt/update_static_client.sh` succeeded (29.5s client build, 22 routes prerendered)
[comment: build completed 2026-08-22T14:54:06.753Z | via executor-opencode | entryId e-20260822-0003 | artifacts: ./client-version-in-context-to-client-14n3y0/2026-08-22T14-42-26-651Z-build-nkyzaq.request.md, ./client-version-in-context-to-client-14n3y0/2026-08-22T14-42-26-651Z-build-nkyzaq.response.md, ./client-version-in-context-to-client-14n3y0/2026-08-22T14-42-26-651Z-build-nkyzaq.trace.log, ./client-version-in-context-to-client-14n3y0/2026-08-22T14-42-26-651Z-build-nkyzaq.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-22T14:54:06.753Z build completed (e-20260822-0003)
- 2026-08-22T14:42:26.624Z plan completed (e-20260822-0002)
- 2026-08-22T14:39:29.071Z expand completed (e-20260822-0001)
- 2026-08-22T14:38:32.263Z created (source: user)
