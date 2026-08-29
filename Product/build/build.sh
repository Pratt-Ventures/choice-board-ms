#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Building static client (Nuxt generate -> static_client/) ==="
bash "$REPO_ROOT/scripts/nuxt/update_static_client.sh"

docker buildx build --platform linux/x86_64 -f "$SCRIPT_DIR/Dockerfile" -t powerchoice-service:preview "$REPO_ROOT"