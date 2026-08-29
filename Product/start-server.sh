#!/bin/bash
source ./src/.venv/bin/activate && fastapi dev src/pvf/pvf_app_runner.py --host 0.0.0.0
