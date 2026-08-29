#!/bin/bash
echo "Sourcing ~/.bashrc..."
source ~/.bashrc
# Ensure static log dir exists (supervisord fails if logs/ missing; named volume is empty on first run)
SHARED_TMP="${SHARED_STORAGE_PATH:-/home/ubuntu/tmp}"
mkdir -p "$SHARED_TMP/logs" ./tmp/logs ../tmp/logs 2>/dev/null || true
echo "Log dir: $SHARED_TMP/logs (and ./tmp/logs)"
ls -ld "$SHARED_TMP/logs" 2>&1 || true
echo "Running supervisor command..."
supervisord -n -c ./supervisor.conf