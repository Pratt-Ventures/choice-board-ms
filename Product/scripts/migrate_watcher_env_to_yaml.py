#!/usr/bin/env python3
"""Print a pvf_app_watcher.yaml skeleton derived from current env (.env).

No backward-compat shim for WATCHER_PROCESS_MODULE_LIST — this late-stage app may
reconfigure quickly. Run once after updating to pvf watcher:

  PYTHONPATH=. python scripts/migrate_watcher_env_to_yaml.py > src/pvf_app_watcher.yaml

Uses WATCHER_PROCESS_MODULE_LIST if present, otherwise suggests the standard four types.
"""
import os

mods = [x.strip() for x in os.environ.get("WATCHER_PROCESS_MODULE_LIST", "").split(",") if x.strip()]
if not mods:
    mods = ["llm", "outbound_email", "outbound_api_call", "SHORTEN_PRODUCT_NAME"]

print("# Generated from current env — review and commit as src/pvf_app_watcher.yaml")
print("version: 1")
print(f"capture_payloads: {str(bool(int(os.environ.get('WATCHER_CAPTURE_PAYLOADS','1')))).lower()}")
print("no_log_request_types: []")
print("types:")
for m in mods:
    kind = "app" if m not in ("llm", "outbound_email", "outbound_api_call") else "pvf"
    if m == "llm":
        print("  llm:\n    kind: pvf\n    module: src.pvf.watcher.handlers.llm\n    entry: handle_llm")
    elif m == "outbound_email":
        print("  outbound_email:\n    kind: pvf\n    module: src.pvf.watcher.handlers.email\n    entry: handle_email")
    elif m == "outbound_api_call":
        print("  outbound_api_call:\n    kind: pvf\n    module: src.pvf.watcher.handlers.api\n    entry: handle_api")
    else:
        print(f"  {m}:\n    kind: {kind}\n    module: src.app.watcher_handlers\n    entry: {m.lower()}")
