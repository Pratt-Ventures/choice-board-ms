---
name: todo-run
description: Non-interactive single-entry Agentic TODO Board runner for direct queue execution / automation. Claims one exact worklist entryId and stops — no user confirms, no next-item offers, no queue scanning.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "false"
  audience: agents
  workflow: agentic-todo-direct
---

# Agentic TODO direct runner (`todo-run`)

Headless companion to the interactive `todo` skill.

**Use only when the caller already chose the exact worklist entry** (e.g. a direct queue run).  
For human `/todo` sessions, use the **`todo`** skill instead.

## Required inputs (from the user message)

| Field | Meaning |
|---|---|
| `entryId` | Exact worklist `entryId` |
| `nodeId` | Exact item id |
| `action` | `expand` \| `plan` \| `build` \| `codeGuide` \| `userGuide` |

If any is missing → stop.

## Prefer MCP

When tools exist:

1. Call `todo_list_queued` and inspect `dispatch`. If `dispatch.mode` is `direct`, report the returned queue `message` and stop. Do not claim.
2. `todo_claim` `{ entryId, mode: "direct", agent: "opencode-todo-run" }`
3. `todo_get_task` `{ entryId, sections: ["full"] }`
4. Execute (expand/plan/codeGuide/userGuide: no repo edits; build: implement)
5. `todo_complete` with structured `sections` for the action
6. **Stop** (no loop, no next item)

## File fallback

1. Read `todo/todo_results/worklist.json`. If `dispatch.mode` is `direct`, report that the Agent Provider owns the queue automatically and stop. Do not claim.
2. Find exact `entryId` + `nodeId` + `action` with `status === "queued"`.
3. Exclusive-create `todo/todo_results/inbox/<nodeId>/<entryId>.claim.json` with `mode: "direct"`, `agent: "opencode-todo-run"`.
4. Load prompt from `todo/<entry.promptPath>`.
5. Write request/response/trace first, then atomically publish the result sidecar; include structured `sections` in result.json when possible.
6. Delete claim. **Stop.**

## Hard rules

1. Process **only** that `entryId`.
2. **No** user confirmation. **No** loop.
3. One claim; never edit worklist files.
4. Write only under the entry inbox (except build repo edits).
