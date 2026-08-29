# Style of Join this decision box is still rounded with clipping.

## Short Description
### user
Make sure styles match other dialogs, and especially don't clip text.
[comment: updated 2026-08-18T12:13:00.420Z | id style-of-join-this-decision-box-is-still-tb81f9]

## Expanded Description
### agent
I'll look up the Join this decision box and how other dialogs are styled so the expansion is accurate.No exact match yet. Searching for the join-decision dialog and overflow/clipping styles.Found the join box in `ShareVoteSession.vue`. Comparing it with the other dialogs next.The join box is `ShareAccessGate`. Checking its styles against other dialogs.The “Join this decision” gate is `ShareAccessGate` on the vote share landing (`ShareVoteSession`), still a `glass-card` with `rounded="xl"` (`--pc-radius` 16px) instead of the moderate `pc-dialog-card` treatment used by other dialogs (12px). That extra rounding plus card `overflow: hidden` clips titles, field labels, alerts, and focus rings. Align the gate with other dialogs and keep text fully visible without changing access-gate behavior.

- Scope: `ShareAccessGate.vue` markup/classes and `.share-gate` / surface rules in `client/assets/styles/main.scss`; same component also gates “Open full results”.
- Match `pc-dialog-card`: ~12px radius, drop `rounded="xl"`, do not copy dialog `overflow: hidden` onto this in-page card.
- Prevent clipping: `overflow: visible` (as on `.share-surface-card`) or scroll only the body; check Vuetify field labels, tonal alerts, and focus rings.
- Out of scope: gate logic, copy, and post-unlock comparison UI.
- Verify vote and report landings, long subtitle/message, and every field combination (name/email/password/code).
- Open: restyle report gate the same way, and whether a 12px card is enough or it should become a real `v-dialog`.
[comment: expand completed 2026-08-18T12:15:13.124Z | via executor-opencode | entryId e-20260818-0001 | artifacts: ./style-of-join-this-decision-box-is-still-tb81f9/2026-08-18T12-13-00-445Z-expand-ont39w.request.md, ./style-of-join-this-decision-box-is-still-tb81f9/2026-08-18T12-13-00-445Z-expand-ont39w.response.md, ./style-of-join-this-decision-box-is-still-tb81f9/2026-08-18T12-13-00-445Z-expand-ont39w.trace.log, ./style-of-join-this-decision-box-is-still-tb81f9/2026-08-18T12-13-00-445Z-expand-ont39w.result.json]


## Plan

## Build Summary
### agent
I'll inspect the join-decision gate and dialog styles first, then align the card so text no longer clips.The skill is for queue claiming only — I'll implement the gate restyle directly from the brief.Checking radius tokens, overflow on glass cards, and version/commit conventions.Aligning the gate with dialog radius and making overflow visible so labels and alerts no longer clip.Rebuilding the published UI after the client style change.npm isn't on PATH — locating it so the UI generate can run.Build succeeded. Verifying the CSS landed, then committing only the related source files.**60c5d66** — Stop clipping Join this decision gate text

Match the share access gate to dialog radius (12px), drop rounded=xl, and keep overflow visible so titles, labels, alerts, and focus rings are not clipped.

**Touch points**
- `client/components/ShareAccessGate.vue:2` — dropped `rounded="xl"`; still `glass-card share-gate` (vote + report gates)
- `client/assets/styles/main.scss:1004-1016` — 12px radius, `overflow: visible` on card and card-text (no dialog `overflow: hidden`)
- `src/config/config_settings.py:17` — version `0.7.33`
- `static_client/` regenerated (gitignored)
[comment: build completed 2026-08-18T12:20:30.688Z | via executor-opencode | entryId e-20260818-0002 | artifacts: ./style-of-join-this-decision-box-is-still-tb81f9/2026-08-18T12-15-13-209Z-build-sjgmgx.request.md, ./style-of-join-this-decision-box-is-still-tb81f9/2026-08-18T12-15-13-209Z-build-sjgmgx.response.md, ./style-of-join-this-decision-box-is-still-tb81f9/2026-08-18T12-15-13-209Z-build-sjgmgx.trace.log, ./style-of-join-this-decision-box-is-still-tb81f9/2026-08-18T12-15-13-209Z-build-sjgmgx.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-18T12:20:30.688Z build completed (e-20260818-0002)
- 2026-08-18T12:15:13.124Z expand completed (e-20260818-0001)
- 2026-08-18T12:12:21.709Z created (source: user)
