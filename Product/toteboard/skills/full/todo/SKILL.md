---
name: todo
description: Process Agentic TODO Board worklist entries (expand, plan, build, codeGuide, or userGuide). Prefer MCP tools; fallback to worklist files. Lists up to 10 queued tasks for user pick.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "true"
  audience: agents
  workflow: agentic-todo
---

# Agentic TODO skill

Interactive runner: **list → user picks → one entry → list again**. Never claim or execute until the user selects a concrete task.

> **Not for Expand Now automation.** Headless single-entry runs use **`todo-run`**.

## Prefer MCP (when tools are available)

If MCP tools `todo_list_queued`, `todo_claim`, `todo_get_task`, and `todo_complete` are available, use them and **skip** file claim choreography.

### Board browsing (read-only)

For project/board organization — **not** the ready-to-process queue — use `todo_list_categories` (all category columns with counts) and `todo_list_tasks_by_category` (tasks in one category). These are board views; only `todo_list_queued` drives work selection.

### Adding items (MCP)

`todo_add_item` creates a board item from a title and optional description (`{ title, description?, categoryId? }`). Omit `categoryId` to use the configured default MCP category; only MCP-exposed categories accept items. Use `todo_list_categories` to discover exposed categories (`mcpEnabled` / `mcpDescription`).

## Direct provider guard

The extension-owned worklist includes a `dispatch` object. Check it before presenting or claiming work.

- If `dispatch.mode` is `direct`, report the returned queue `message` (or the equivalent statement that the selected Agent Provider owns the queue; mention when automatic execution is paused). Stop without claiming.
- Only continue with the interactive flow when `dispatch.mode` is `skill`.

### MCP session flow

1. **List** — `todo_list_queued` with optional `action` filter (`expand`|`plan`|`build`|`codeGuide`|`userGuide`) and `limit` 10. Check the returned `dispatch` before showing cards.
2. **Pick** — present titles to the user (plus **Exit and save for later**). Do not claim yet.
3. **Claim** — `todo_claim` with `{ entryId, mode: "direct", agent: "opencode" }` (or `copilot`).
4. **Load task** — `todo_get_task` with `{ entryId, sections: ["full"] }` (or staged sections).
5. **Execute** — follow instructions. expand/plan/codeGuide/userGuide: no repo edits. build: implement in repo.
6. **Complete** — `todo_complete` with structured payload:
   - expand: `{ status, summary, sections: { expandedDescription } }`
   - plan: `{ status, summary, sections: { plan, questions? } }`
   - build: `{ status, summary, sections: { buildSummary, keyChoices?, filesTouched?, verification?, followUps? } }`
   - codeGuide: `{ status, summary, sections: { codeReviewGuide } }`
   - userGuide: `{ status, summary, sections: { uiReviewGuide } }`
7. Re-list; stop when empty or user exits.

Exactly **one** claim at a time. Never auto-drain.

## Arguments

| Invocation | Queue filter |
|---|---|
| bare `/todo`, `todo`, or no action | **all** actions (`expand`, then `plan`, then `build`, then `codeGuide`, then `userGuide`) |
| `todo expand` / `/todo expand` | `expand` only |
| `todo plan` / `/todo plan` | `plan` only |
| `todo build` / `/todo build` | `build` only |
| `todo codeGuide` / `/todo codeGuide` | `codeGuide` only |
| `todo userGuide` / `/todo userGuide` | `userGuide` only |

Use a **write-capable/build** agent (not a restricted plan-only agent).

## File fallback (no MCP)

When MCP tools are missing, read **`protocol.md`** (once per session) and use:

| Role | Path |
|---|---|
| Machine worklist | `todo/todo_results/worklist.json` (metadata only; prompts at `promptPath`) |
| Agent inbox | `todo/todo_results/inbox/<nodeId>/` |

1. Read the worklist `dispatch` object. If `dispatch.mode` is `direct`, report that the Agent Provider owns the queue automatically and stop. Do not claim.
2. List `status === "queued"` (max 10, expand→plan→build→codeGuide→userGuide).
3. User picks.
4. Load full prompt from `todo/<entry.promptPath>` (not embedded in worklist.json).
5. Exclusive-create claim + four inbox outputs per `protocol.md`.
6. Prefer structured `sections` inside `*.result.json` when possible.

**Do not** edit `worklist.json`, `worklist.md`, or `todo/todo_items/**` (except real code on **build**).

## Hard rules

1. Exactly one active claim/entry at a time.
2. Never claim without an explicit user **selection** (or Exit).
3. Never edit the worklist files.
4. Show at most **10** choices; order **expand → plan → build → codeGuide → userGuide**.
5. Interactive picks use **`mode: "direct"`**.
