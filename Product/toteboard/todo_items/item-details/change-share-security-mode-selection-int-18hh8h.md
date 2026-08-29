# Change share security mode selection interaction

## Short Description
### user
On share invite, the '*show all options' should be changed to 'show all*'
The ''show common options' should be 'show basic' and should float near the pull down, like the existing show all does.
[comment: created 2026-08-19T00:42:14.832Z | id change-share-security-mode-selection-int-18hh8h]

## Expanded Description
### agent
I'll locate the share-invite security-mode UI so the expansion matches the current labels and layout.On the create-share invite dialog, retitle the access-mode toggle so collapsed state reads `show all*` (was `*show all options`) and expanded state reads `show basic` (was `show common options`). Keep both controls as the existing text-button next to the Access mode select; `show basic` must sit beside the pulldown like `show all*` does today, not get pushed to the far end of the row. Scope is the invite UI in `client/pages/projects/[id]/shares.vue` (labels plus the `justify-space-between` layout when all modes are shown).

- Scope: label copy on both toggles; keep `show basic` adjacent to the select (drop or stop applying `justify-space-between` on `.access-mode-row` when expanded).
- Do not change access-mode lists, defaults, or backend share security behavior.
- Preserve the leading/trailing asterisk treatment as specified (`show all*` / `show basic`).
- Check e2e/unit selectors that match the old strings (`*show all options`, `show common options`).
- Confirm whether edit-share or other dialogs reuse the same pattern; if not, leave them alone.
- Open: should `show basic` also use an asterisk, or stay unadorned as written?
[comment: expand completed 2026-08-19T00:43:33.827Z | via executor-opencode | entryId e-20260819-0001 | artifacts: ./change-share-security-mode-selection-int-18hh8h/2026-08-19T00-42-14-972Z-expand-f2dwr8.request.md, ./change-share-security-mode-selection-int-18hh8h/2026-08-19T00-42-14-972Z-expand-f2dwr8.response.md, ./change-share-security-mode-selection-int-18hh8h/2026-08-19T00-42-14-972Z-expand-f2dwr8.trace.log, ./change-share-security-mode-selection-int-18hh8h/2026-08-19T00-42-14-972Z-expand-f2dwr8.result.json]


## Plan

## Build Summary
### agent
I'll locate the share-invite access-mode toggle and any selectors using the old labels.The labels live in `shares.vue`. Next I’ll read that block and search tests for the old copy.No e2e matches. I’ll inspect styles, the edit dialog, changelog, and version next.Labels and layout only live in the create dialog. I’ll update those, bump the version, and check commit style.Rebuilding the published UI so FastAPI serves the new labels.Build succeeded. Verifying the Vue change, then committing only the related source files.Staging only the invite-UI and version files, then committing.Create-share access-mode toggle now reads `show all*` / `show basic`, both beside the select. Static client rebuilt. No e2e/unit selectors used the old strings; edit-share does not reuse this pattern.

**Touch points**
- `client/pages/projects/[id]/shares.vue:174` — dropped `justify-space-between` on `.access-mode-row`
- `client/pages/projects/[id]/shares.vue:189` — collapsed label `show all*`
- `client/pages/projects/[id]/shares.vue:195` — expanded label `show basic`
- `src/config/config_settings.py:17` — VERSION `0.7.39`

**Commit** `5a72e09f7e3e0841704cf3d417ea5d0e951e0544`
Retitle share invite access-mode toggles to show all* / show basic
[comment: build completed 2026-08-19T00:47:42.451Z | via executor-opencode | entryId e-20260819-0002 | artifacts: ./change-share-security-mode-selection-int-18hh8h/2026-08-19T00-43-33-912Z-build-zh14wo.request.md, ./change-share-security-mode-selection-int-18hh8h/2026-08-19T00-43-33-912Z-build-zh14wo.response.md, ./change-share-security-mode-selection-int-18hh8h/2026-08-19T00-43-33-912Z-build-zh14wo.trace.log, ./change-share-security-mode-selection-int-18hh8h/2026-08-19T00-43-33-912Z-build-zh14wo.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-19T00:47:42.451Z build completed (e-20260819-0002)
- 2026-08-19T00:43:33.827Z expand completed (e-20260819-0001)
- 2026-08-19T00:42:14.832Z created (source: user)
