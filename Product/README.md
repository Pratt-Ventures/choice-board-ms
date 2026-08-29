# Power Choice Pro

Structured decision support: teams define a **Project**, add **Options** and **Factors**, **Compare** them pairwise, and review **Results**. Share links collect participant input (Compare Only / Compare and See Only Your Results / See Full Results). User-facing language lives in [`docs_examples/terminology_dictionary.md`](docs_examples/terminology_dictionary.md).

Python 3.13 + FastAPI + SQLModel + Alembic (Postgres). Nuxt 3 SPA in `client/` generates into `static_client/` (gitignored) and is served by FastAPI.

## Pratt Ventures Framework (pvf) — keep isolated

The app runs on **pvf** (`src/pvf/`). pvf is a reusable multi-tenant kernel (session JWT, customer/user admin, email, share links, signed external APIs, Stripe, branding, logging). It may be managed or replaced as a separate tree. **Keep it isolated.**

Current isolation patterns (do not erode these):

- **pvf never imports this application.** The runner loads the shell named in `src/pvf_app_startup.yaml` (`src.app_shell` / `app_startup`). Application code reaches pvf only through published entry points — see [`src/pvf/README.md`](src/pvf/README.md).
- **Do not put Power Choice logic inside `src/pvf/`.** Product routes, models, ranking, and UI bindings belong in `src/api/`, `src/db/`, `src/utils/`, `src/app_shell.py`, and `client/`.
- **Do not reach past published pvf surfaces** (`pvf_app_runner`, `pvf_get_alembic_config`, `pvf.utils.pvf_services`, `pvf.pvf_invocation`, `pvf.config.pvf_config_settings`, `pvf.depends.*`, `pvf.db.models.*`).
- **Extend, don’t fork.** Extra columns on pvf tables go through `register_schema_extensions` in the shell. Feature switches and share vocabularies stay in `src/pvf_app_startup.yaml` (deployment-fixed, read-only at runtime).
- Framework tables live in `src/pvf/db/models/`; application tables live in `src/db/models/` and are registered from `src/db/models/bootstrap.py`.

## Directory structure

| Path | Purpose |
|------|---------|
| `src/` | Backend. Poetry project (`package-mode = false`); in-project venv is `src/.venv`. |
| `src/pvf/` | **Framework only.** Runner, four FastAPI apps, auth/share/external/Stripe/email, framework models. Treat as a separate product. |
| `src/pvf_app_startup.yaml` | Deployment-fixed pvf config: shell module, env file name, feature switches, share types. |
| `src/app_shell.py` | Application bridge: settings merge, hooks, routers, schema extensions. Shared with the watcher. |
| `src/api/` | Power Choice session/share/external routes (projects, options/factors, compare, results). |
| `src/db/models/` | Application tables (projects, options/factors, vote events). Wired in `bootstrap.py`. |
| `src/utils/` | Application services (ranking, compare session, templates, user context). |
| `src/config/` | Application `GlobalSettings` (extends pvf settings) and client-facing settings. |
| `src/alembic/` | Migrations. `env.py` is a thin shim over `pvf_get_alembic_config`. |
| `src/powerchoice_watcher.py` | Separate process: signed webhook callback delivery. Not started by `./start-server.sh`. |
| `src/powerchoice_server.py` | Compatibility shim that re-exports the pvf runner `app`. |
| `src/tests/` | API tests against the configured DB (not hermetic). Helpers in `src/tests/helpers/`. |
| `client/` | Nuxt 3 SPA (`ssr: false`) + Vue 3 + Vuetify. Dev on `:3000`, proxies API to `:8100`. |
| `static_client/` | Generated SPA FastAPI serves. Gitignored. Rebuild with `./scripts/nuxt/update_static_client.sh`. |
| `static/` | Non-SPA static files (`/static`). |
| `scripts/` | Migrations, OpenAPI extract, Nuxt publish, Stripe CLI helpers. |
| `e2e/` | Playwright. Starts/reuses API `:8100` + Nuxt `:3000`. |
| `email_templates/` | SMTP-Jinja templates (html/txt/subject). |
| `docs_examples/` | Product language, share-mode notes, prototypes — not runtime. |
| `build/` | Docker image, supervisord, sample compose. |
| `.devcontainer/` | Dev container + Postgres 16 sidecar. |
| `openapi_sessions.json` / `openapi_api.json` | Contract snapshots for the session UI surface and customer toolkit API. |
| `example.env` | Runtime env template. Copy to `.env` at the repo root (`*.env` is gitignored). |
| `project_templates.yml` | Seed project / option / factor templates. |
| `AGENTS.md` | Engineering conventions for this repo (commands, testing, OpenAPI). |

## HTTP surfaces

Composed by `src/pvf/pvf_app_runner.py`, then handed to `src/app_shell.py`:

| App | Mount | Auth | Role |
|-----|-------|------|------|
| root | `/` | — | Static + SPA fallback + Stripe hooks; `/status`, `/alive` |
| noauth | `/auth-ws` | none | Login, password reset, self-registration |
| session | `/ws` | JWT cookie | Session UI API |
| share | `/ext-ws` | share cookie / magic key | Share-link compare and results |
| external | `/api` | signed headers | Customer toolkit API |

Session OpenAPI: `/session/docs`. Toolkit OpenAPI: `/api/docs`.

## Local development

Dev container (recommended): reopen in the container, then:

```bash
mkdir -p /workspaces/powerchoice/postgres-data-${USER}   # before first compose start
cp example.env .env                                       # set UNIQUE_CONFIGURATION_CHECK=1 and secrets
cd src && poetry install
cd ..
./scripts/migrations/run-migrations.sh
./start-server.sh                                         # fastapi dev → 0.0.0.0:8100
```

UI in another terminal:

```bash
cd client && npm install && npm run dev                   # :3000, proxies to :8100
```

Ship the SPA with the API: `./scripts/nuxt/update_static_client.sh` (required after any `client/` change).

Default DSN (compose sidecar): `postgresql+psycopg://powerchoice:powerchoice_dev_password@postgres:5432/powerchoice`.

```bash
# Tests (hit the real configured DB)
src/.venv/bin/pytest src/tests/

# Browser e2e
cd e2e && npm install && npx playwright install chromium && npm test
```

More commands: migrations, OpenAPI refresh, version bump — see [`AGENTS.md`](AGENTS.md).

## Git remote

This repo’s `origin` is its own remote (e.g. `git@gh-powerchoice:Pratt-Ventures/power-choice.git`). There is no local bare sibling. If `git ls-remote origin` fails with “dubious ownership”, add `git config --global --add safe.directory /workspaces/powerchoice`.
