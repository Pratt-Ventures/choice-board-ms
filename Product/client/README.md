# PowerChoice client (Nuxt + Vue + Vuetify)

SPA for the PowerChoice session UI API. Lives under `client/` so it stays separate from the Python FastAPI server.

## Stack

- Nuxt 3 (SPA mode, `ssr: false`)
- Vue 3
- Vuetify 3 (`vuetify-nuxt-module`)
- Cookie session auth against the FastAPI `access_token` JWT

## Setup

```bash
cd client
npm install
```

## Development

Start the Python API (port 8100), then:

```bash
npm run dev
```

Opens on [http://localhost:3000](http://localhost:3000). In dev, Vite proxies `/auth-ws`, `/ws`, `/api`, and `/status` to `http://localhost:8100` so cookie auth works same-origin.

**Notes (SPA / Nuxt 3.21+):**
- Dev: `vite:configResolved` maps `{ entry }` → `{ entry, server }` only for `nuxt dev` (nuxt/nuxt#35466). Do not apply this during `generate` or entry CSS will not be linked.
- `experimental.appManifest` is disabled so Vite does not fail resolving `#app-manifest` in SPA mode.
- Deploy static assets with `../scripts/nuxt/update_static_client.sh` (copies `.output/public` → `../static_client/`).

Optional env:

```bash
# Absolute API origin when not using the Vite proxy (e.g. production build)
NUXT_PUBLIC_API_BASE=http://localhost:8100
```

CORS on the server already allows `http://localhost:3000` with credentials.

## Build

```bash
npm run build      # SSR/Nitro output under .output (SPA)
npm run generate   # static export under .output/public
```

Deploy the generated static assets in place of (or alongside) `static_client/` if you want the server to serve this UI.

## Routes

| Path | Purpose |
|------|---------|
| `/login` | Sign in |
| `/signup` | Self-registration |
| `/forgot-password` | Request reset |
| `/forgot-password/:token` | Set new password |
| `/activate-customer/:code` | Activation link |
| `/dashboard` | Overview metrics |
| `/applications` | List / create apps |
| `/applications/:id` | App detail |
| `/api-keys` | Toolkit API keys |
| `/users` | Team management |

## Design

PowerChoice visual system from the HTML prototype: navy/blue/indigo palette, soft panels, metric cards, and dual-pane auth screens.
