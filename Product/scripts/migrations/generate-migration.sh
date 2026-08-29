#!/bin/bash
if [ -z "$1" ]; then
    echo "You need to provide a migration message."
    exit 1
fi
cd src
./.venv/bin/alembic revision --autogenerate -m "$1"