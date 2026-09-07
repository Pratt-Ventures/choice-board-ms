#!/bin/sh
# Validate local publication state before sending URLs. This never publishes a page.
set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/indexnow.py" "$@"
