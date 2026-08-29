# Share options in user interface

## Short Description
### user
Adjust the user interface on the share page so that only configured options are intiially visible in the pulldown (as is now the case). 

Make the selection drop down narrower and add a small text link '*show all options'  that will show all available options. When all options are shown, the list behaves as if all options were enabled, showing the preview summary beneath the box when something is selected. Add a 'show common options' text button to the right in that case, which reduces the list back to the configured options, clearing the selection if needed. For those in the full list that are not enabled in the initial choices, add an * after the display name to distinguish them. The * is somewhat explained by the * in the all options link.
[comment: updated 2026-08-18T17:55:57.721Z | id share-options-in-user-interface-9iqzz1]

## Expanded Description
### agent
The share page dropdown should keep showing only configured options at first, but become narrower and gain a small `*show all options` text link. Expanding reveals every available option, treats them as selectable (including the preview summary under the box), marks non-configured names with a trailing `*`, and shows a `show common options` text control on the right. Collapsing returns to the configured list and clears the selection when the current pick is not among those common options.

- Scope: share-page option pulldown only — width, configured-vs-all toggle, `*` markers, preview, and selection clearing.
- Default view stays the current configured-only list; full list is opt-in via `*show all options`.
- In the full list, unconfigured options behave like enabled ones for selection and preview, distinguished only by a trailing `*`.
- `show common options` restores the configured list and must clear the selection if it is not in that set.
- Layout: narrower select; expand link near the control; collapse control to the right when expanded.
- Open: whether “common” always equals configured, whether expand/collapse persists across navigation, and exact placement/styling of the two text links.
[comment: expand completed 2026-08-18T17:56:45.414Z | via executor-opencode | entryId e-20260818-0001 | artifacts: ./share-options-in-user-interface-9iqzz1/2026-08-18T17-55-57-776Z-expand-ue5x4a.request.md, ./share-options-in-user-interface-9iqzz1/2026-08-18T17-55-57-776Z-expand-ue5x4a.response.md, ./share-options-in-user-interface-9iqzz1/2026-08-18T17-55-57-776Z-expand-ue5x4a.trace.log, ./share-options-in-user-interface-9iqzz1/2026-08-18T17-55-57-776Z-expand-ue5x4a.result.json]


## Plan

## Build Summary
### agent
I'll start by locating the share-page option pulldown and how configured vs available options are currently rendered.Skipping queue/claim tools per the brief. Next I’ll find the share-page option dropdown and how configured vs all options are filtered.The access-mode select on the share create dialog matches the brief. I’ll check existing tests, changelog, and nearby UI patterns before changing it.The access-mode dropdown is the target. I’ll narrow it, add the configured/all toggle, and keep preview plus selection-clearing as specified.Next I’ll confirm the form still typechecks, then rebuild the published UI and check version references.npm isn’t on PATH, and `config_settings.py` has extra diffs. I’ll isolate this change’s files and locate a usable Node toolchain.Static client built. I’ll confirm the new copy is in the generated UI, then commit only the share-page and version files.**Build summary**

Share create dialog keeps the configured-only access-mode list by default. The select is narrower, `*show all options` reveals every mode (unconfigured names get a trailing `*`, preview still shows), and `show common options` restores the configured list and clears a non-common pick. Static client regenerated. VERSION `0.7.37`.

**Commit:** `2761cdf`  
Narrow share access-mode dropdown and add show-all toggle

**Touch points**
- `client/pages/projects/[id]/shares.vue:173-200` — narrower select, `*show all options` / `show common options`
- `client/pages/projects/[id]/shares.vue:399-422` — select width and text-link styles
- `client/pages/projects/[id]/shares.vue:538-571` — configured vs all list, `*` markers, collapse + clear
- `client/pages/projects/[id]/shares.vue:277` / `:714` / `:728-730` / `:774-777` — empty selection after collapse
- `src/config/config_settings.py:17` — VERSION `0.7.37`
[comment: build completed 2026-08-18T18:03:26.067Z | via executor-opencode | entryId e-20260818-0002 | artifacts: ./share-options-in-user-interface-9iqzz1/2026-08-18T17-56-45-455Z-build-3ycy2c.request.md, ./share-options-in-user-interface-9iqzz1/2026-08-18T17-56-45-455Z-build-3ycy2c.response.md, ./share-options-in-user-interface-9iqzz1/2026-08-18T17-56-45-455Z-build-3ycy2c.trace.log, ./share-options-in-user-interface-9iqzz1/2026-08-18T17-56-45-455Z-build-3ycy2c.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-18T18:03:26.067Z build completed (e-20260818-0002)
- 2026-08-18T17:56:45.414Z expand completed (e-20260818-0001)
- 2026-08-18T17:55:55.315Z created (source: user)
