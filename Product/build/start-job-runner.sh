#!/bin/bash
set -e
echo "starting powerchoice watcher — $(date)" >&2
exec src/.venv/bin/python -u -m src.powerchoice_watcher
