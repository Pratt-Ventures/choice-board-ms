# powerchoice_watcher.py — thin forwarder to canonical PVF watcher

"""Example watcher shim (~60 lines).

Loads startup + watcher YAML from current cwd, builds invocation, delegates to pvf.watcher.service.
The canonical implementation lives in src/pvf/pvf_watcher_runner.py, supported by pvf/watcher: service.py, poll.py, handlers/*).

applications can also be started (from root/src cwd) with:
  python pvf/pvf_watcher_runner.py
"""
from src.pvf.pvf_watcher_runner import main

if __name__ == "__main__":
    main()
