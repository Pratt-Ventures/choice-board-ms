#!/bin/bash
if [ "$#" -lt 3 ]; then
    echo "Merge message, and two head hashes are required as arguments to use this script. If you don't have the head hashes, run 'list-migration-heads.sh' first."
    exit 1
elif [ "$#" -gt 3 ]; then
    echo "This script is only built to handle two head hashes."
    exit 1
fi

MESSAGE="$1"
HEAD_1="$2"
HEAD_2="$3"

cd src
PYTHONPATH=$(pwd)/.. ./.venv/bin/alembic merge -m "$MESSAGE" "$HEAD_1" "$HEAD_2"