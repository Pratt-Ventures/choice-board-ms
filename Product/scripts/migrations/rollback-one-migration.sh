#!/bin/bash
cd src
PYTHONPATH=$(pwd)/.. ./.venv/bin/alembic downgrade -1