"""Backwards-compatible uvicorn target.

The application composition now lives in pvf_app_runner (configured by
pvf_app_startup.yaml and src/app_shell.py). This shim remains so existing launch
configurations and tooling keep working during the transition.
"""
from .pvf.pvf_app_runner import app  # noqa: F401
