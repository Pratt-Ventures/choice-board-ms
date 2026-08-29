#!/bin/bash
# Build the Nuxt SPA under client/ and replace static_client/ so FastAPI can
# serve the precompiled UI on the same address/port as the web services.
# The client/ tree is left intact for nuxt dev (latest UI on :3000).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLIENT_DIR="$REPO_ROOT/client"
STATIC_CLIENT_DIR="$REPO_ROOT/static_client"
OUTPUT_PUBLIC="$CLIENT_DIR/.output/public"

cd "$CLIENT_DIR"

if [ ! -d node_modules ]; then
  echo "Installing client dependencies..."
  npm install
fi

# Empty apiBase → relative same-origin requests when UI is served by FastAPI
# Derive client version from package.json so the baked appVersion matches the
# release (prevents stale `client 0.7.83 → server 0.7.84` mismatches where the
# banner never clears because static_client was built with an old fallback).
CLIENT_VERSION="$(node -p "require('./package.json').version" 2>/dev/null || jq -r .version package.json 2>/dev/null || echo "")"
if [ -z "$CLIENT_VERSION" ]; then
  echo "warning: could not derive client version from package.json; using nuxt.config fallback" >&2
fi

# --- version sync guard: client package.json must match server settings.VERSION ---
# This prevents hard-to-clear `client X → server Y` banners that survive reload
# because static_client was (re)generated with a stale client version while the
# server was bumped independently (e.g. 0.7.88→0.7.89 without rebuilding).
SERVER_VERSION="$(sed -nE 's/^[[:space:]]*VERSION[^=]*=[[:space:]]*"([^"]+)".*/\1/p' "$REPO_ROOT/src/config/config_settings.py" | head -n1)"
FALLBACK_VERSION="$(sed -nE "s/^[[:space:]]*let _pkgVersion.*'([^']+)'.*/\1/p" "$CLIENT_DIR/nuxt.config.ts" | head -n1)"
if [ -n "$SERVER_VERSION" ] && [ -n "$CLIENT_VERSION" ] && [ "$CLIENT_VERSION" != "$SERVER_VERSION" ]; then
  echo "error: version drift — client/package.json $CLIENT_VERSION != server src/config/config_settings.py $SERVER_VERSION" >&2
  echo "  Fix: bump the lagging side so both are $SERVER_VERSION (or $CLIENT_VERSION) and re-run this script." >&2
  echo "  Hint: both src/config/config_settings.py VERSION and client/package.json version must be bumped together." >&2
  exit 1
fi
if [ -n "$FALLBACK_VERSION" ] && [ -n "$CLIENT_VERSION" ] && [ "$FALLBACK_VERSION" != "$CLIENT_VERSION" ]; then
  echo "warning: nuxt.config.ts fallback _pkgVersion $FALLBACK_VERSION != client/package.json $CLIENT_VERSION — updating fallback is recommended" >&2
  # Non-fatal: generate still uses NUXT_PUBLIC_APP_VERSION, but stale fallback would bite if that env var is omitted.
fi
echo "Generating static client (NUXT_PUBLIC_API_BASE=, NUXT_PUBLIC_APP_VERSION=${CLIENT_VERSION:-<fallback>}, server $SERVER_VERSION)..."
NUXT_PUBLIC_API_BASE= NUXT_PUBLIC_APP_VERSION="$CLIENT_VERSION" npm run generate

if [ ! -f "$OUTPUT_PUBLIC/index.html" ]; then
  echo "error: generate did not produce $OUTPUT_PUBLIC/index.html" >&2
  exit 1
fi

# Guard: production SPA HTML must link entry CSS (missing = unstyled UI)
if ! grep -q 'rel="stylesheet".*entry\..*\.css\|entry\..*\.css.*rel="stylesheet"\|/_nuxt/entry\.' "$OUTPUT_PUBLIC/index.html"; then
  if ! grep -q 'entry\.[^"]*\.css' "$OUTPUT_PUBLIC/index.html"; then
    echo "error: generated index.html has no entry CSS link; check nuxt SPA build config" >&2
    echo "  (the vite:configResolved entry→server hack must not run during generate)" >&2
    exit 1
  fi
fi

echo "Replacing $STATIC_CLIENT_DIR ..."
rm -rf "$STATIC_CLIENT_DIR"
mkdir -p "$STATIC_CLIENT_DIR"
cp -a "$OUTPUT_PUBLIC"/. "$STATIC_CLIENT_DIR"/

# Post-build verification: baked appVersion must match server version
BAKED_VERSION="$(grep -o 'appVersion:"[^"]*"' "$STATIC_CLIENT_DIR/index.html" | head -n1 | sed -E 's/appVersion:"([^"]+)"/\1/' || echo "")"
if [ -z "$BAKED_VERSION" ]; then
  BAKED_VERSION="$(grep -o 'appVersion:[^,}]*' "$OUTPUT_PUBLIC/index.html" | head -n1 | sed -E 's/appVersion:"?([^",}]+)"?/\1/' || echo "")"
fi
if [ -n "$SERVER_VERSION" ] && [ -n "$BAKED_VERSION" ] && [ "$BAKED_VERSION" != "$SERVER_VERSION" ]; then
  echo "error: baked static_client appVersion $BAKED_VERSION != server $SERVER_VERSION — build produced stale artifact" >&2
  exit 1
fi
if [ -n "$BAKED_VERSION" ]; then
  echo "Verified baked appVersion $BAKED_VERSION matches server $SERVER_VERSION"
fi

echo "Done. Precompiled UI is in static_client/ (served with the web services)."
echo "Dev UI remains available via: cd client && npm run dev"
