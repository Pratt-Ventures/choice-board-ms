---
name: todo-run
description: Lightweight Agentic TODO direct-runner (mini). Full /TODO skill processing is disabled; verify the TODO environment and delegate to the extension's built-in automation.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "false"
  audience: agents
  workflow: agentic-todo-direct
---

# Agentic TODO direct runner (mini)

Full `/TODO` skill processing is disabled. Do **not** claim or execute the requested `entryId`.

1. Verify the TODO environment: the Agentic TODO Board extension is installed and the reduced MCP tools (`todo_list_categories`, `todo_add_item`) are reachable.
2. If the environment is missing, report the exact missing piece and stop.
3. Otherwise, report that the selected Agent Provider owns the queue and delegate to the extension's built-in automation.

Re-enable full `/TODO` processing from **Agentic TODO → Settings → Agent Provider** (turn off "Disable full `/TODO` skill processing") and re-run **Install/Update Skills** if needed.
