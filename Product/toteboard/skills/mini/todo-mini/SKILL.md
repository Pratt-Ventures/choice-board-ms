---
name: todo
description: Lightweight Agentic TODO skill. Full /TODO skill processing is disabled; verify the TODO environment and delegate to the extension's built-in automation.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "true"
  audience: agents
  workflow: agentic-todo
---

# Agentic TODO skill (mini)

Full `/TODO` skill processing is disabled for this workspace. Do **not** list, claim, execute, or complete queue entries with this skill.

## Environment check

1. Confirm the Agentic TODO Board extension is installed in VS Code and its storage is initialized (a `todo/` folder is present in the workspace).
2. Confirm the TODO MCP server is reachable: the reduced surface tools `todo_list_categories` and `todo_add_item` should be available via the extension's installed MCP config (`.vscode/mcp.json` or `opencode.json`). Queue tools are hidden while full processing is disabled.

If either is missing, report the exact missing piece and stop. Do not fabricate tool calls or fall back to manual file claims.

## Delegate to the extension

The selected Agent Provider owns the queue. Use the extension's built-in automation (the play / Expand Now / Plan Now / Build Now actions and direct queue execution) instead of this skill.

To re-enable full `/TODO` skill processing, open **Agentic TODO → Settings → Agent Provider**, turn off **"Disable full `/TODO` skill processing"**, then re-run **Install/Update Skills**.
