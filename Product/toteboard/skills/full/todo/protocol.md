# Agentic TODO — file-protocol fallback (claim / execute / release)

Use only when **MCP tools are unavailable**. Prefer `todo_claim` / `todo_get_task` / `todo_complete` when present.

## Preconditions

- User already **selected** one queued worklist entry (`entryId`, `nodeId`, `action`).
- `todo/todo_results/worklist.json` has `dispatch.mode === "skill"`. If it is `direct`, the extension-owned Agent Provider manages the queue and this protocol must stop without claiming.

## 1. Claim (exclusive)

Create **only if it does not already exist**:

`todo/todo_results/inbox/<nodeId>/<entryId>.claim.json`

```json
{
  "entryId": "<entry.entryId>",
  "nodeId": "<entry.nodeId>",
  "action": "<entry.action>",
  "mode": "direct",
  "claimedAt": "<ISO-8601 UTC>",
  "agent": "opencode"
}
```

`mode: "direct"` is **required** for interactive picks.

## 2. Re-validate

Re-read `todo/todo_results/worklist.json`. Confirm the entry is still present and `queued` or `claimed` for you.

## 3. Load prompt

Read `todo/<entry.promptPath>` (staged prompt). If missing, fall back to any `entry.prompt` field.

## 4. Execute

Follow the prompt. expand/plan/codeGuide/userGuide: inbox writes only. build: repo changes allowed.

## 5. Write outputs

Paths from `entry.output` (prefixed with `todo/`):

| File | Content |
|---|---|
| `output.request` | Echo of the prompt |
| `output.response` | Deliverable body |
| `output.trace` | Brief step log |
| `output.result` | Result sidecar |

```json
{
  "entryId": "<entry.entryId>",
  "status": "completed",
  "finishedAt": "<ISO-8601 UTC>",
  "summary": "<one-line summary>",
  "sections": {
    "expandedDescription": "(expand)",
    "plan": "(plan)",
    "questions": ["(plan optional)"],
    "buildSummary": "(build)",
    "keyChoices": ["(build optional)"],
    "filesTouched": ["(build optional)"],
    "verification": "(build optional)",
    "followUps": ["(build optional)"],
    "codeReviewGuide": "(codeGuide)",
    "uiReviewGuide": "(userGuide)"
  }
}
```

On failure use `"status": "failed"`. Write the three text outputs first, then publish `result.json` by writing a temporary sibling and renaming it atomically so the extension never ingests a partial completion signal.

## 6. Release

Delete `<entryId>.claim.json` after the result sidecar is written.

## Hard rules

1. One claim at a time.
2. Never edit worklist files.
3. Never write outside inbox paths except build repo edits.
4. Always `mode: "direct"` on interactive picks.
