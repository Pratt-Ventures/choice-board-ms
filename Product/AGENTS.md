# AGENTS.md

Python 3.13 + FastAPI + SQLModel + Alembic (Postgres). Nuxt 3 SPA in `client/` builds into `static_client/` (gitignored, published locally) served by FastAPI.

The application runs on **pvf** (`src/pvf/`, the Pratt Ventures Framework): a standard
runner (`src/pvf/pvf_app_runner.py`) reads `src/pvf_app_startup.yaml`, establishes the
DB connection, composes four FastAPI apps (noauth `/auth-ws`, session `/ws`, share
`/ext-ws`, external `/api`), and invokes the application shell (`src/app_shell.py`,
name/entry point configured in the YAML). Framework entry points are documented in
`src/pvf/README.md`; non-REST services come from `src/pvf/utils/pvf_services.py`.

**User-facing product language:** `docs_examples/terminology_dictionary.md` (Project · Option · Factor · Compare · Results · share types). Prefer those terms in UI copy and API `description=` strings; do not rename DB/JSON fields unless explicitly requested.

Root `README.md` is the product and layout overview (including pvf isolation). Prefer this file for engineering commands, testing, and OpenAPI.

## pvf is off-limits (unless explicitly allowed)

**Hard rule.** pvf (`src/pvf/`) is an infrastructure provider. PowerChoice is the application we are working on. Do **not** change pvf infrastructure or its dedicated settings — including `src/pvf_app_startup.yaml` and `src/pvf/config/pvf_config_settings.py` — unless the user **explicitly** allows it.

Application work belongs in the PowerChoice application area. Interact with pvf only through `src/app_shell.py` (via `PvfInvocation`) and the modules in `src/pvf/bindings`. Do not reach into pvf internals.

Unless specifically asked otherwise, treat pvf as read-only infrastructure.

## Engineering standards

Every change is production work by and for senior engineers. Build reliable, defensive, resilient systems. Users will not tolerate flakiness, and we cannot reach most of their environments — robustness and self-healing are required in every plane.

Understand the existing design before changing it. Prefer the simplest clean architecture that fully solves the problem. Preserve strong abstractions. Do not add technical debt, duplication, shortcuts, unnecessary complexity, or speculative work.

Handle edge cases, errors, compatibility, usability, and visual polish. Match existing conventions. Keep complexity local and factoring effective. Make confident changes with minimal unintended impact.

Verify. Run relevant tests; add tests for new or corrected behavior. Inspect failures — never bypass them. Exercise important user flows end-to-end.

Do not stop at “it works.” Ship code that is clear, maintainable, robust, secure, performant, and product-ready.

## Priority: request intake (before build actions)

**High priority.** Before implementing or changing code, evaluate every request for:

- **Scope** — what is in vs out; avoid expanding beyond what was asked
- **Duplication** — existing APIs, UI, settings, models, or flows that already cover the need
- **Risk** — tenancy/auth, data loss, breaking API/UI contracts, migrations, published `static_client/`, shared DB tests

If anything is ambiguous, incomplete, or high-risk, **stop and ask for clarification or guidance** before build actions (edits, migrations, generate, deploys). Prefer a short check-in over speculative implementation.

## Project records (after significant interactive work)

When significant changes are made in the interactive window, report a summary title and brief description so they can be added to the project records. No further action is implied; this keeps records complete as expected. Do **not** submit tickets if processing a toteboard (agentic-todo) request.

## Environment & toolchain

- **Poetry** lives in `src/` (`package-mode = false`, in-project venv → **`src/.venv`**). `cd src && poetry install`. Devcontainer puts `src/.venv/bin` on `PATH`.
- Deployment-fixed startup config is **`src/pvf_app_startup.yaml`** (shell module/entry point, env file name, feature switches, share vocabularies). Feature switches are injected into `pvf_settings` read-only at startup; only the startup logic can set them.
- Runtime config file is **`.env`** at the repo root (ingested via python-dotenv by the runner/alembic config + pydantic-settings; process env overrides the file). Template: `example.env`. Gitignore: `*.env` with `!example.env`.
- Key vars: `SERVER_ENV` (`local` | `staging` | `production` → `settings.server_env`; `is_prod()` only for `production`), `DB_PATH_OR_CONNECTION_STRING`, `BOOTSTRAP_SAMPLE_DATA`, `STRIPE_ENDPOINT_SECRET_PRIMARY`, `STRIPE_HOOK_STR_PRIMARY`, `PLATFORM_LINUX`.
- No project lint/typecheck tooling. Verify with pytest + running the server.
- Imports mix `from src...` and package-relative forms → **repo root must be on `PYTHONPATH`**. VS Code Alembic launch sets it; backend launch uses `cwd: src` and may need `PYTHONPATH=${workspaceFolder}` if `from src...` fails.

## Commands

```bash
cd src && poetry install

# API from repo root (activates venv, fastapi dev 0.0.0.0:8100 via pvf_app_runner)
./start-server.sh
# manual: source src/.venv/bin/activate && fastapi dev src/pvf/pvf_app_runner.py --host 0.0.0.0

# Migrations (scripts cd into src/, use ./.venv/bin/alembic; env.py is a thin shim over
# src/pvf/pvf_get_alembic_config.py, which forces BOOTSTRAP_SAMPLE_DATA=False)
./scripts/migrations/run-migrations.sh
./scripts/migrations/generate-migration.sh "<message>"
./scripts/migrations/rollback-one-migration.sh   # sets PYTHONPATH to repo root
./scripts/migrations/list-migration-heads.sh
./scripts/migrations/merge-migration-heads.sh

# Tests from repo root — hit the real configured DB (not isolated)
src/.venv/bin/pytest src/tests/
src/.venv/bin/pytest src/tests/test_auth.py -k <name>

# Browser e2e (Playwright) — starts/reuses API :8100 + Nuxt :3000
cd e2e && npm install && npx playwright install chromium
# First time / missing shared libs on Linux: npx playwright install-deps chromium
cd e2e && npm test
# Share access-mode suite only:
cd e2e && npm run test:share
# Modules map to OpenAPI tags: auth, admin, manage-projects, manage-project-content,
# api-keys, dashboard, self-reg, context, project-votes, stripe hooks, external API, etc.
```

Fresh local: `poetry install` → `./scripts/migrations/run-migrations.sh` → `./start-server.sh`.

## Frontend (`client/`)

- Nuxt 3 SPA (`ssr: false`) + Vue 3 + Vuetify. Session JWT cookie `access_token` (httponly) against the UI API.
- Dev: API on :8100, then `cd client && npm install && npm run dev` (:3000). Vite proxies `/auth-ws`, `/ws`, `/ext-ws`, `/api`, `/status` → `:8100`. CORS allows `localhost:3000` with credentials. In Nuxt dev, browser calls are same-origin so the proxy owns cookies.
- Ship UI with API: `./scripts/nuxt/update_static_client.sh` → `nuxt generate` with empty `NUXT_PUBLIC_API_BASE`, copies `.output/public` → **`static_client/`** (gitignored; published locally, not committed).
- SPA generate gotcha: `client/nuxt.config.ts` maps Vite `{ entry }` → `{ entry, server }` **only when `nuxt.options.dev`**. Do not apply during `generate` or entry CSS is dropped (script guards this).
- **After any change under `client/`**, rebuild and publish the UI: run `./scripts/nuxt/update_static_client.sh` (generates + copies into `static_client/`, the artifact FastAPI actually serves). The build must complete successfully before considering the work done; fix build/SFC errors and do not leave a broken generate or a stale `static_client/`.

## Postgres dev sidecar

`.devcontainer/docker-compose.yml` Postgres 16:

- Host bind-mount **must exist** before compose starts: `mkdir -p /workspaces/powerchoice/postgres-data-${USER}` (compose interpolates `USER` per tenant so co-tenants on the same VM get separate DB volumes).
- In-container DSN: `postgresql+psycopg://powerchoice:powerchoice_dev_password@postgres:5432/powerchoice`.
- SQLite (`sqlite:///local.db`) only auto-`create_all` when not prod **and** `BOOTSTRAP_SAMPLE_DATA`. Real schema changes go through Alembic. `*.db` is gitignored.

## Architecture

**`src/pvf/pvf_app_runner.py`** composes the root app plus four FastAPI sub-apps, and
invokes **`src/app_shell.py`** (the application bridge configured in the YAML) with a
`PvfInvocation`:

| App | Mount | Auth | Role |
|-----|-------|------|------|
| `app` (root) | `/` | — | Mounts others + static + SPA fallback + Stripe hooks; `/status`, `/alive` |
| `app_noauth` | `/auth-ws` | none | Login, password reset, self-registration |
| `app_session` | `/ws` | `SessionDep` + `UserAccessDep` (JWT cookie) | Session UI API |
| `app_share` | `/ext-ws` | `SessionDep` + share cookie/magic-key gate | Share link access |
| `app_external` | `/api` | `SessionDep` + `WebServiceDep` (signed headers) | Customer toolkit API |

- Routes are relative to each app's mount prefix (external URLs unchanged: `/auth-ws/...`, `/ws/...`, `/ext-ws/...`, `/api/...`). Stripe hooks keep full paths on the root app.
- DI is strictly enforced at composition time by the runner's boot integrity check (`src/pvf/utils/dependency_integrity.py`), independent of endpoint signatures. `test-helpers` routes (tagged, non-prod only) are exempt.
- Reserved prefixes return JSON 404 (no SPA fallback): `/ws`, `/ext-ws`, `/api`, `/auth`, `/hook-stripe-events`, `/api/webhooks`. Other 404s serve `static_client/index.html`.
- Aggregate session-surface OpenAPI at `/session/docs.json` (root + noauth + session + share); external at `/api/openapi.json`.
- Static: `/static` → `static/`; UI assets → `static_client/`. Paths resolved from workspace root (not cwd).
- Application hooks (entity resolver, share email dispatch/matrix/enrichers, webhook payload builders/readiness) are registered in `src/app_shell.py::register_app_hooks`, shared with the watcher process.
- **`src/powerchoice_watcher.py`**: separate process polling DB for API callback delivery (generic machinery in `src/pvf/utils/callback_delivery.py`). Prod/staging via supervisord (`build/supervisor.conf`); **not** started by `./start-server.sh`. Launch config: module `src.powerchoice_watcher`. Supervisor runs `./start-job-runner.sh`, which is **not in-repo** — check deploy packaging before relying on it.
- Models: framework tables in `src/pvf/db/models/`; application tables in `src/db/models/`; `bootstrap.py` imports app models and calls `pvf_bootstrap.import_all_models()` so Alembic/metadata see all tables. New app models must be wired there.
- Schema extensions: applications can add columns to pvf tables (`customer`, `user`, `sharelink`, `apiaccessconfiguration`) via `register_schema_extensions` in the shell — see `src/pvf/README.md`.

## Stripe webhooks

- Real routes: `POST /hook-stripe-events/{hook_str}` and sandbox variant. `hook_str` is `STRIPE_HOOK_STR_PRIMARY` or a per-customer hook id.
- `./scripts/stripe/stripe-forward.sh` forwards to a **stale path** (`/stripe-events-...`). Point the CLI at `/hook-stripe-events/<hook_str>` instead.

## Build & deploy

- **App version:** On each build (any shippable change set), always increment the last segment of `settings.VERSION` in `src/config/config_settings.py` (`a.b.LAST` → `a.b.LAST+1`). Exposed via `GET /status` (`version`) and the UI About box.
- `build/build.sh` (repo root): image `powerchoice-service:vX.Y.Z`, patch bump from `build/.last-build` (Docker tag only; still bump `settings.VERSION` as above).
- Runtime: supervisord runs `fastapi run src/pvf/pvf_app_runner.py` + watcher. `build/run.sh` sources `~/.bashrc` then supervisord.
- `build/compose.yml`: staging-style sample (`powerchoice:v0.5.5`, host `9001`→`8100`); bind paths are placeholders.

## Testing gotchas

- Layout: `src/tests/conftest.py` + tag-cluster modules + `src/tests/helpers/` (`as_user`/`login`/`signed_api_headers`, factories, best-effort cleanup).
- `conftest` sets `settings.PYTEST_ACTIVE = True` and clears SendGrid **before** importing `app`. `PYTEST_ACTIVE` skips the 500 handler so pytest shows full tracebacks. Autouse mock patches SendGrid delivery.
- Settings overrides in tests: pvf-owned fields must be set on **both** `settings` (app instance) and `pvf_settings` (what pvf internals read); conftest's helper loop shows the pattern.
- The app is composed by `src.pvf.pvf_app_runner` (conftest imports `app` from there); the shell runs during that import, so YAML, env, DB, and hooks are live for tests.
- Fixtures create random customers/users/apps/API keys and soft-delete/deactivate on teardown. Residual log/event rows are expected. **Not hermetic** against a shared dev DB.
- Assert security failure modes explicitly (unauth, non-admin, non-sysadmin, cross-tenant, bad API signatures).
- **Material new functionality must ship with tests** (happy path + security/tenancy failure modes) in the matching tag-cluster module under `src/tests/` (or a new one). Prefer API-level tests via `TestClient` and existing helpers over one-off DB scripts.
- Before and after large updates, run the affected suite (or full `src/.venv/bin/pytest src/tests/`) against the configured DB and fix regressions before considering the change done. Share/vote coverage lives in `test_share_manage.py`, `test_share_ext_access.py`, `test_project_votes.py`.
- **After tests**, if any endpoint in that surface changed, regenerate the matching OpenAPI snapshot at the repo root (see **OpenAPI snapshots** below).

## OpenAPI snapshots

Repo-root contract files used to define endpoints for the client and other services:

| File | Surface | Live schema |
|------|---------|-------------|
| `openapi_sessions.json` | Session UI API (root + noauth + session + share) | `/session/docs.json` |
| `openapi_api.json` | Customer toolkit API (external app under `/api`) | `/api/openapi.json` |

The extraction script builds the app in-process via `src.pvf.pvf_app_runner` and
prefix-stitches the sub-app schemas (the sessions file covers all browser-facing
surfaces). Operation IDs are regenerated from mount-relative route paths.

Regenerate **only the file whose endpoints changed** (path, method, params, request/response models, or tags), after the related tests pass:

```bash
./scripts/extract_openapi/update_openapi_json.sh           # both
./scripts/extract_openapi/update_openapi_json.sh sessions  # openapi_sessions.json
./scripts/extract_openapi/update_openapi_json.sh api       # openapi_api.json
```

Non-prod snapshots include `test_helpers` routes (those routers are not registered when `is_prod()`).

## Git remote policy (important)

This repo uses its own `origin` for storage — there is **no** local bare sibling repo. Verify with `git remote -v` (should be like `git@gh-powerchoice:Pratt-Ventures/power-choice.git`, never a `d:\...` local path) and `git ls-remote origin`.

Host bind mounts often show `root:root` while the container user is `ubuntu` → Git “dubious ownership”. The Dockerfile sets `safe.directory` for `/workspaces/powerchoice`. If `git ls-remote origin` still fails, add that path with `git config --global --add safe.directory /workspaces/powerchoice`.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
