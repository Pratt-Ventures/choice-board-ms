# powerchoice_watcher.py — thin forwarder to canonical PVF watcher

"""PowerChoice watcher shim (~60 lines).

Loads startup + watcher YAML, builds invocation, delegates to pvf.watcher.service.
The canonical implementation lives in src/pvf/watcher/ (runner.py, service.py, poll.py, handlers/*).

For new applications, run:
  python -m src.pvf.watcher.runner
"""
from src.pvf.pvf_watcher_runner import main

if __name__ == "__main__":
    main()
