# Comare experience

## Short Description
### user
Add an 'Undo/Back' action to the left of 'about equal' 'not sure' and 'skip'.  This will ahve the same effect as the other undo, left on the page, and reverses the last entry in the group (only). It grays out on the first item of the group.
[comment: created 2026-08-19T18:04:51.214Z | id comare-experience-2s11vk]

## Expanded Description
### agent
Add an Undo/Back control immediately left of the About equal / Not sure / Skip actions on the compare experience. It should reuse the existing page-left undo behavior: reverse only the last entry in the current group, then return to that pair. Disable (gray out) the control on the first item of a group so users cannot step out of the group or undo earlier groups.

- Scope: UI placement and wiring only; same undo semantics as the existing left-side undo, group-local.
- Disabled state: first item of the group (no prior entry in this group).
- Reuse existing undo handler rather than a second undo stack.
- Confirm labels: “Undo” vs “Back”, and whether keyboard shortcut matches the other undo.
- Open: does undo also restore skipped / not-sure / about-equal the same as ranked picks?
[comment: expand completed 2026-08-19T18:05:54.808Z | via executor-opencode | entryId e-20260819-0001 | artifacts: ./comare-experience-2s11vk/2026-08-19T18-04-51-284Z-expand-lfv0gz.request.md, ./comare-experience-2s11vk/2026-08-19T18-04-51-284Z-expand-lfv0gz.response.md, ./comare-experience-2s11vk/2026-08-19T18-04-51-284Z-expand-lfv0gz.trace.log, ./comare-experience-2s11vk/2026-08-19T18-04-51-284Z-expand-lfv0gz.result.json]


## Plan
### agent
I'll inspect the compare UI and existing undo wiring so the plan matches current group-local behavior.Verifying the two action rows and `canUndo` so the plan cites the right files.## Plan: Compare Undo/Back (action-row)

Scope: UI placement + wire the existing `runner.undo()` / `runner.canUndo`. No new undo stack, API, or scheduler change. Same group-local pop as the header Undo.

Existing behavior to reuse (`useSortGroupRunner.ts`):
- `undo()` pops the last `PairAnswer` in the current group only (`winner` / `tie` / `unsure` / `skipped`), persists localStorage, re-runs `selectNextPair` so that pair returns.
- `canUndo` is `answers.length > 0 && !complete` — already the “first item of this group” (and completed-group) gate.
- Header Undo already calls this: `probe.vue` `onUndo` (~L409), share calls `runner.undo()` (~L42). `U` on probe already hits the same handler.

---

### 1. Implementation steps

1. **In-app action row** — `client/pages/projects/[id]/probe.vue` (~L170–174). Insert a button as the first child of the About equal / Not sure / Skip row.
   - Click: same as header — `onUndo()` → `runner.undo()`.
   - Disabled: `!runner.canUndo.value || submitting` (parity with header; pair row is not shown on intro/complete).
   - Style: `variant="text"` to sit left of tonal “About equal”; optional `fa-rotate-left` to match header.

2. **Share action row** — `client/components/ShareVoteSession.vue` (~L167–171). Same button, first in that row.
   - Click: `runner.undo()`.
   - Disabled: `!runner.canUndo.value` (share header does not use `submitting`).

3. **Do not change** `useSortGroupRunner.undo` / `canUndo`, pair scheduler, or vote APIs. One stack, group-local, cannot walk into `priorAnswers` or a finished group (action row unmounts when `complete`).

4. **Keyboard** — leave `U` on probe as-is (already same handler). Do not add a second shortcut. Share still has no keys unless product asks for parity.

5. **Verify manually** (no compare-undo tests exist):
   - Fresh group: new control grayed; header Undo grayed.
   - After a winner / About equal / Not sure / Skip: both Undos enabled; click either restores that pair; `inGroupDone` decrements by 1.
   - Mid-group resume with saved pairings: enabled; undo back to zero then gray out; cannot leave the group.
   - After group complete: action row gone; cannot undo into previous groups.
   - Repeat on `/projects/:id/probe` and `/share/vote/:token`.

6. **Out of scope (do not fix here):** undo-to-zero does not flush empty pairings (`flushPartial` returns when `inGroupDone === 0`); extract a shared compare-stage component; add missing scheduler undo unit tests.

---

### 2. Clarifying questions

1. **Label:** “Undo” (matches header + terminology dict) or “Back”?
2. **Keep the header Undo** as well, or replace it with this row control?
3. **Icon:** rotate-left like the header, chevron-left for “Back”, or text only?
4. **Share keyboard:** add probe’s `1/2/E/N/U` to share, or leave share mouse-only?
5. Confirm skip / not-sure / about-equal undo the same as ranked picks (current runner already does this).

---

### 3. Options and trade-offs

| Option | Pros | Cons |
|---|---|---|
| **A. Duplicate button in both action rows, reuse `runner.undo`** | Matches brief; tiny diff; identical semantics | Two UIs stay copied; two Undo buttons if header stays |
| **B. Extract a shared `CompareActionRow` used by probe + share** | Stops drift | Extra refactor beyond “UI placement and wiring only” |
| **C. New group-local stack / different undo** | — | Violates “reuse existing handler”; risk of crossing groups |

**Recommendation:** **A** with label **“Undo”**, header Undo left in place, no new shortcut. Disabled via existing `canUndo`. Skip / not-sure / about-equal already reverse the same as ranked picks — no special case. Revisit B only if the two rows keep diverging.
[comment: plan completed 2026-08-19T18:11:02.813Z | via executor-opencode | entryId e-20260819-0002 | artifacts: ./comare-experience-2s11vk/2026-08-19T18-05-54-915Z-plan-96fofu.request.md, ./comare-experience-2s11vk/2026-08-19T18-05-54-915Z-plan-96fofu.response.md, ./comare-experience-2s11vk/2026-08-19T18-05-54-915Z-plan-96fofu.trace.log, ./comare-experience-2s11vk/2026-08-19T18-05-54-915Z-plan-96fofu.result.json]


## Build Summary
### agent
I'll inspect the compare action rows and existing undo wiring, then add the shared Undo control.Action rows and `canUndo` match the plan. Adding the Undo control in both UIs, then bumping version and committing.Rebuilding the published UI, then committing only these files.Staging only the compare Undo files and committing.**Build complete** — compare action-row Undo

**Commit:** `0973250`  
Add Undo on the compare action row next to About equal

**Touch points**
- `client/pages/projects/[id]/probe.vue:170-177` — Undo first in About equal / Not sure / Skip row; `onUndo()` + `!canUndo || submitting`
- `client/components/ShareVoteSession.vue:167-174` — same placement; `runner.undo()` + `!canUndo`
- Header Undo left in place (`probe.vue:31`, `ShareVoteSession.vue:42`); `U` still hits `onUndo`
- `src/config/config_settings.py:17` — VERSION `0.7.56`
- `static_client/` rebuilt (gitignored)

No runner/API change. Skip / not-sure / about-equal already undo like ranked picks.
[comment: build completed 2026-08-19T18:14:28.676Z | via executor-opencode | entryId e-20260819-0003 | artifacts: ./comare-experience-2s11vk/2026-08-19T18-11-02-910Z-build-bw5bfc.request.md, ./comare-experience-2s11vk/2026-08-19T18-11-02-910Z-build-bw5bfc.response.md, ./comare-experience-2s11vk/2026-08-19T18-11-02-910Z-build-bw5bfc.trace.log, ./comare-experience-2s11vk/2026-08-19T18-11-02-910Z-build-bw5bfc.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-19T18:14:28.676Z build completed (e-20260819-0003)
- 2026-08-19T18:11:02.813Z plan completed (e-20260819-0002)
- 2026-08-19T18:05:54.808Z expand completed (e-20260819-0001)
- 2026-08-19T18:04:51.214Z created (source: user)
