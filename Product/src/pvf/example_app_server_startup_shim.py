"""optional application started run from root.

The application composition lives in pvf_app_runner (configured by
pvf_app_startup.yaml and src/app_shell.py). 

This shim can be used so existing launch
configurations and tooling are launched from the workspace root.

If cwd is the workspace root, preferred alternative: python pvf/pvf_app_runner.py --no-reload --port 8100
"""
from .pvf.pvf_app_runner import app  # noqa: F401
