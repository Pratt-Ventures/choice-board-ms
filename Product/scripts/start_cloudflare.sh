#!/bin/bash
# Cloudflare Tunnel launcher for local development.
# Exposes the local PowerChoice dev server externally via
#   https://powerchoice-dev.prattventures.net
#
# Quick start:
#   ./scripts/start_cloudflare.sh
#     → proxies http://localhost:8100 (FastAPI + static_client SPA)
#     → requires a running API: ./start-server.sh (port 8100)
#
# Named tunnel (persistent hostname powerchoice-dev.prattventures.net):
#   1. Create a tunnel in Cloudflare Zero Trust dashboard:
#        Networks → Tunnels → Create tunnel → Cloudflared
#        Public Hostname: powerchoice-dev.prattventures.net → Service http://localhost:8100
#      Copy the tunnel TOKEN.
#   2. Add to your .env (repo root):
#        CLOUDFLARE_TUNNEL_TOKEN=<token>
#   3. Re-run: ./scripts/start_cloudflare.sh
#      The script auto-detects the token and runs:
#        cloudflared tunnel run --token $CLOUDFLARE_TUNNEL_TOKEN
#
# Quick (ephemeral) tunnel — no token needed:
#   If no token/config is present the script falls back to:
#        cloudflared tunnel --url http://localhost:8100
#   This prints a random *.trycloudflare.com URL. That URL works immediately
#   but is NOT powerchoice-dev.prattventures.net. To get the stable hostname,
#   configure the named tunnel above.
#
# Options:
#   --port 8100        Local port to expose (default 8100, use 3000 for Nuxt dev)
#   --url  URL         Full local URL (overrides --port, e.g. http://localhost:3000)
#   --token TOKEN      Tunnel token (overrides env/.env)
#   --background       Run detached (nohup + log file) — otherwise foreground with logs
#   --help             Show this help
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

HOSTNAME="powerchoice-dev.prattventures.net"
DEFAULT_PORT="8100"
DEFAULT_URL="http://localhost:${DEFAULT_PORT}"
LOCAL_URL="$DEFAULT_URL"
TOKEN_OVERRIDE=""
BACKGROUND=0

usage() {
  sed -n '2,35p' "$0" | sed 's/^# \?//'
  cat <<EOF

Usage: $0 [--port PORT] [--url URL] [--token TOKEN] [--background]

Environment:
  CLOUDFLARE_TUNNEL_TOKEN   Named-tunnel token (from .env or shell env)
  PORT / URL overrides via flags take precedence.
EOF
}

log()  { echo "[cloudflare] $*"; }
warn() { echo "[cloudflare] WARN: $*" >&2; }
err()  { echo "[cloudflare] ERROR: $*" >&2; }

# ---- arg parsing ----
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      if [[ $# -lt 2 ]]; then err "--port requires a value"; exit 1; fi
      LOCAL_URL="http://localhost:$2"
      shift 2
      ;;
    --url)
      if [[ $# -lt 2 ]]; then err "--url requires a value"; exit 1; fi
      LOCAL_URL="$2"
      shift 2
      ;;
    --token)
      if [[ $# -lt 2 ]]; then err "--token requires a value"; exit 1; fi
      TOKEN_OVERRIDE="$2"
      shift 2
      ;;
    --background)
      BACKGROUND=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      err "unknown option: $1"
      usage
      exit 1
      ;;
    *)
      err "unexpected argument: $1"
      usage
      exit 1
      ;;
  esac
done

# Load .env so CLOUDFLARE_TUNNEL_TOKEN is available without exporting.
# We do this without failing if the file is absent, and without
# overwriting already-exported env vars.
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env" 2>/dev/null || true
  set +a
fi

# Resolve token: CLI flag > env > .env via direct grep (in case source was skipped)
resolve_token() {
  if [[ -n "$TOKEN_OVERRIDE" ]]; then
    echo "$TOKEN_OVERRIDE"
    return
  fi
  if [[ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]]; then
    echo "$CLOUDFLARE_TUNNEL_TOKEN"
    return
  fi
  # Fallback grep (handles quoted values)
  if [[ -f "$REPO_ROOT/.env" ]]; then
    local raw
    raw="$(grep -E '^\s*CLOUDFLARE_TUNNEL_TOKEN\s*=' "$REPO_ROOT/.env" 2>/dev/null | tail -n1 | cut -d= -f2- || true)"
    # strip leading/trailing whitespace and quotes
    raw="$(echo "$raw" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'\'']//' -e 's/["'\'']$//')"
    if [[ -n "$raw" ]]; then
      echo "$raw"
      return
    fi
  fi
  echo ""
}

TOKEN="$(resolve_token)"

ensure_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    return 0
  fi
  warn "cloudflared not found on PATH."
  log "Attempting to install cloudflared..."

  # Prefer apt repo if available (Dockerfile adds it), otherwise fall back to .deb
  if [[ -f /etc/apt/sources.list.d/cloudflared.list ]]; then
    if sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cloudflared; then
      log "cloudflared installed via apt."
      command -v cloudflared >/dev/null 2>&1 && return 0
    fi
  fi

  # Try adding the repo + installing (for containers built before Dockerfile change)
  if command -v curl >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    log "Adding Cloudflare apt repo and installing cloudflared..."
    if sudo mkdir -p /usr/share/keyrings \
       && curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null \
       && echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared jammy main' | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null \
       && sudo apt-get update -qq \
       && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cloudflared; then
      log "cloudflared installed via apt repo."
      command -v cloudflared >/dev/null 2>&1 && return 0
    fi
    warn "apt install failed, trying direct .deb download..."
    # Fallback: direct .deb from GitHub releases
    local deb="/tmp/cloudflared-linux-amd64.deb"
    if curl -fsSL -o "$deb" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb" \
       && sudo dpkg -i "$deb" 2>/dev/null; then
      rm -f "$deb"
      log "cloudflared installed via .deb."
      command -v cloudflared >/dev/null 2>&1 && return 0
    fi
    rm -f "$deb" 2>/dev/null || true
  else
    warn "curl/sudo not available for auto-install."
  fi

  err "cloudflared is required but could not be installed automatically."
  err "Install manually inside the dev container:"
  err "  curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null"
  err "  echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared jammy main' | sudo tee /etc/apt/sources.list.d/cloudflared.list"
  err "  sudo apt-get update && sudo apt-get install -y cloudflared"
  err "Or download the .deb:"
  err "  curl -fsSL -o /tmp/cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && sudo dpkg -i /tmp/cloudflared.deb"
  err "Then re-run: $0"
  exit 1
}

check_local() {
  local url="$1"
  # Extract host:port for a quick TCP/connectivity check, then HTTP probe
  local check_url="${url}/status"
  # Prefer /alive and /status — both exist on the PVF root app
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS --connect-timeout 2 --max-time 3 "$check_url" >/dev/null 2>&1; then
      log "Local service reachable at $url (checked $check_url)"
      return 0
    fi
    if curl -fsS --connect-timeout 2 --max-time 3 "${url}/alive" >/dev/null 2>&1; then
      log "Local service reachable at $url (checked ${url}/alive)"
      return 0
    fi
    # If the root path returns anything (SPA fallback), consider it reachable
    if curl -fsS --connect-timeout 2 --max-time 3 "$url/" >/dev/null 2>&1; then
      log "Local service appears reachable at $url"
      return 0
    fi
    warn "No response from $url — is the dev server running?"
    warn "Start it first:  ./start-server.sh   (API on :8100)"
    warn "For Nuxt dev, use:  $0 --port 3000   (after 'cd client && npm run dev')"
    # Non-fatal: tunnel can still start and will 502 until the server is up
    return 0
  fi
}

check_already_running() {
  if pgrep -fa "cloudflared.*tunnel" >/dev/null 2>&1; then
    warn "An existing cloudflared tunnel process was found:"
    pgrep -fa "cloudflared.*tunnel" 2>/dev/null | sed 's/^/  /' >&2 || true
    warn "If you want a second tunnel, stop the existing one first (Ctrl-C or 'pkill cloudflared')."
    echo ""
  fi
}

ensure_cloudflared

PORT="$(echo "$LOCAL_URL" | sed -E 's|.*:([0-9]+).*|\1|')"
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
  PORT="$DEFAULT_PORT"
fi

log "Hostname:  $HOSTNAME"
log "Local URL: $LOCAL_URL"
if [[ -n "$TOKEN" ]]; then
  log "Mode:      named tunnel (token present, ${#TOKEN} chars) → $HOSTNAME"
else
  log "Mode:      quick tunnel (no token) → random *.trycloudflare.com URL"
  log "           To expose $HOSTNAME, set CLOUDFLARE_TUNNEL_TOKEN in .env"
fi

check_local "$LOCAL_URL"
check_already_running

# Show cloudflared version for diagnostics
if command -v cloudflared >/dev/null 2>&1; then
  log "cloudflared: $(cloudflared --version 2>&1 | head -n1)"
fi

# ---- choose execution mode ----
if [[ -n "$TOKEN" ]]; then
  # Named tunnel — Cloudflare dashboard controls the hostname→service mapping
  # (Public Hostname $HOSTNAME → Service $LOCAL_URL). The token already encodes
  # the tunnel ID; we just run it.
  log "Starting named tunnel for $HOSTNAME ..."
  log "Press Ctrl-C to stop."
  echo ""

  # Prefer the modern `cloudflared tunnel run --token` form
  CMD=(cloudflared tunnel --no-autoupdate run --token "$TOKEN")
  # Some cloudflared versions also accept `cloudflared tunnel run --token`

  if [[ $BACKGROUND -eq 1 ]]; then
    LOGFILE="${REPO_ROOT}/cloudflared-${HOSTNAME}.log"
    log "Running in background, logs → $LOGFILE"
    log "Stop with: pkill -f 'cloudflared.*tunnel.*run'"
    nohup "${CMD[@]}" >"$LOGFILE" 2>&1 &
    echo $! > "${REPO_ROOT}/cloudflared.pid"
    log "PID $(cat "${REPO_ROOT}/cloudflared.pid") — tail logs: tail -f $LOGFILE"
    # Give it a moment and show initial log lines
    sleep 2
    if [[ -f "$LOGFILE" ]]; then
      head -n 30 "$LOGFILE" || true
    fi
    exit 0
  else
    exec "${CMD[@]}"
  fi

else
  # Check for local config file based tunnel (credentials-file + tunnel ID)
  if [[ -f "$HOME/.cloudflared/config.yml" ]] || [[ -f "$HOME/.cloudflared/config.yaml" ]] || [[ -f "$REPO_ROOT/.cloudflared/config.yml" ]]; then
    warn "Found a cloudflared config file but no CLOUDFLARE_TUNNEL_TOKEN."
    log "Attempting 'cloudflared tunnel run' (uses config.yml)..."
    # Try config-based run; if it fails, fall through to quick tunnel
    if cloudflared tunnel run 2>&1 | head -n 50; then
      exit 0
    fi
    warn "'cloudflared tunnel run' failed — falling back to quick tunnel."
  fi

  # Quick (ephemeral) tunnel — fastest path for ad-hoc external testing
  log "Starting QUICK tunnel: $LOCAL_URL → https://<random>.trycloudflare.com"
  log "For stable $HOSTNAME, configure a named tunnel token and re-run."
  log "Press Ctrl-C to stop."
  echo ""

  CMD=(cloudflared tunnel --url "$LOCAL_URL")

  if [[ $BACKGROUND -eq 1 ]]; then
    LOGFILE="${REPO_ROOT}/cloudflared-quick.log"
    log "Running in background, logs → $LOGFILE"
    log "Stop with: pkill -f 'cloudflared.*tunnel.*--url'"
    nohup "${CMD[@]}" >"$LOGFILE" 2>&1 &
    echo $! > "${REPO_ROOT}/cloudflared-quick.pid"
    log "PID $(cat "${REPO_ROOT}/cloudflared-quick.pid") — tail logs: tail -f $LOGFILE"
    sleep 2
    if [[ -f "$LOGFILE" ]]; then
      # Quick tunnel prints the URL to stdout/stderr — surface it
      cat "$LOGFILE" || true
    fi
    exit 0
  else
    exec "${CMD[@]}"
  fi
fi
