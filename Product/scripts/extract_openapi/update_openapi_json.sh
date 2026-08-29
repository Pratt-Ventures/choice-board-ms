#!/bin/bash
# Write repo-root OpenAPI snapshots from the live FastAPI apps.
#   ./scripts/extract_openapi/update_openapi_json.sh           # both
#   ./scripts/extract_openapi/update_openapi_json.sh sessions  # openapi_sessions.json
#   ./scripts/extract_openapi/update_openapi_json.sh api       # openapi_api.json
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON="$REPO_ROOT/src/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "error: $PYTHON not found; run: cd src && poetry install" >&2
  exit 1
fi

TARGET="${1:-both}"
case "$TARGET" in
  both|sessions|session|api) ;;
  *)
    echo "usage: $0 [both|sessions|api]" >&2
    exit 1
    ;;
esac

cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT"

"$PYTHON" - "$TARGET" <<'PY'
import json
import sys
from pathlib import Path

target = sys.argv[1]
root = Path(".")

from src.pvf.pvf_app_runner import build_external_openapi, build_sessions_openapi

writes = []
if target in ("both", "sessions", "session"):
    writes.append(("openapi_sessions.json", build_sessions_openapi()))
if target in ("both", "api"):
    writes.append(("openapi_api.json", build_external_openapi()))

for name, spec in writes:
    path = root / name
    path.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {path} ({len(spec.get('paths', {}))} paths)")
PY
