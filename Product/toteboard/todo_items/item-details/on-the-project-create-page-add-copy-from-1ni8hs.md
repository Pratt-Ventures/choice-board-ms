# On the project create page add 'Copy from project'

## Short Description
### user
This would be added to the left of 'Start with Template' - when selected, the user chooses from a list of existing projects. The project is read and its initial settings (but not voting state, shares, or other details) are copied into the new project. This should be similar to the 'Duplicate Project' option available separately. The option should be greyed out if any options or alternatives have already been specified.
[comment: created 2026-08-21T14:23:40.518Z | id on-the-project-create-page-add-copy-from-1ni8hs]

## Expanded Description
### agent
Add a "Copy from project" action to the project create page (the overview tab of the create/edit screen), positioned to the left of "Start with Template". When clicked, it opens a dialog listing existing projects; choosing one loads that project's initial settings into the new-project draft exactly as the existing "Duplicate Project" flow does (reusing the `duplicateFromId`/`applyProjectSettings(..., { asDuplicate: true })` path), while excluding voting state, shares, end times, and other run details. The button is greyed out once any options or factors have already been specified in the draft, with a tooltip explaining why.

- Scope: create page only (`edit.vue` in new mode); new picker dialog reusing the project list API; copy settings via the existing duplicate-draft loading logic so title/tag get "- Copy"/slugified treatment.
- Exclusions: no votes/comparison state, shares/participant data, branding image, end time, or template linkage copied — settings only.
- Disabled rule: disable when any named option or factor exists in the form; tooltip mirrors the "Save as Template" pattern ("Clear entered options before copying").
- Considerations: decide whether copy also brings factor/multi-factor config and AI-agent settings (they're part of `applyProjectSettings` today); confirm which projects appear in the list (all visible to user vs. admin-owned only).
- Open questions: should the dialog offer search/filtering like other project pickers, and should selecting a source overwrite a typed title/description or leave user-entered values intact?
[comment: expand completed 2026-08-21T14:29:03.051Z | via executor-opencode | entryId e-20260821-0002 | artifacts: ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-27-33-954Z-expand-obcdd6.request.md, ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-27-33-954Z-expand-obcdd6.response.md, ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-27-33-954Z-expand-obcdd6.trace.log, ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-27-33-954Z-expand-obcdd6.result.json]


## Plan
### agent
## Execution Plan: "Copy from project" on the project create page

### Grounding (verified in code)
- Create/edit page: `client/pages/projects/[id]/edit.vue`. New mode = `projectId === 0`; overview tab action row currently holds **Start with Template** (edit.vue:38) and **Save as Template** (edit.vue:41–48, the `:disabled` + `:title` tooltip pattern to mirror).
- Existing duplicate path: `/projects/0/edit?from=<id>` → `duplicateFromId` (edit.vue:785) → `loadDuplicateDraft()` (edit.vue:1307) → `api.getProject(from)` → `applyProjectSettings(info, { asDuplicate: true })` + `loadContentRows(id, false)` + `isDuplicateDraft = true`. This already excludes votes/shares/end time/disabled/branding and applies "- Copy"/slugified-tag title handling.
- Draft content detection for the disabled rule: `namedOptions` / `namedCriteria` computeds (edit.vue:962–963) ignore the blank starter rows.
- Project list API: `useProjectsApi().listProjectsSummary()` (`/ws/custprojects/customer-projects-list-summary`) returns all non-deleted projects in the user's account with counts — same scope as the Projects page where Duplicate lives.

### 1. Numbered implementation steps
1. **Button**: In the overview-tab action row, insert `Copy from project` (small, tonal, clone icon) immediately **left of Start with Template**; render only when `isNew`. Bind `:disabled="!canCopyFromProject"` and `:title="copyFromDisabledHint"` following the Save-as-Template pattern.
2. **Disabled rule**: Add computed `canCopyFromProject = namedOptions.length === 0 && namedCriteria.length === 0`; hint text: `"Clear entered options before copying"` (mirrors existing tooltip tone). Blank starter rows don't trigger it; anything named — typed or imported from a template — does.
3. **Picker dialog**: Add a `v-dialog` modeled on the template-import picker (edit.vue:516–553): search `v-text-field` (client-side filter on title/tag), scrollable radio list showing project title, tag, and option/factor counts, empty-state message when the account has no other projects, Cancel/**Copy** confirm disabled until a selection is made. Exclude nothing by status — settings copy is valid for closed/voted projects too.
4. **Open handler**: `openCopyFromDialog()` awaits `api.listProjectsSummary()`, populates candidates + resets selection/search, opens dialog (reuse `loadingDraft` bar for fetch feedback).
5. **Confirm handler**: Extract the body of `loadDuplicateDraft()` into a shared `applyDuplicateSource(projectResult)` helper; `confirmCopyFromProject()` closes the dialog, then calls it with the chosen id so behavior is byte-for-byte identical to Duplicate Project (settings + options/factors, `- Copy` title/slug, `isDuplicateDraft = true`, success snackbar naming the source project). `onMounted` `?from=` deep-link keeps working through the same helper.
6. **Verification**: No backend/OpenAPI changes, so no pytest snapshot work. Run `cd client && npm run dev` and manually exercise: fresh draft enabled → copy → confirm title/tag/options/factors/settings copied, end time/voting/shares/branding/template linkage absent; typed-options draft shows greyed button + tooltip; regression-check existing Duplicate entry points and Start with Template. Then run `./scripts/nuxt/update_static_client.sh` (required after any `client/` change).

### 2. Clarifying questions
1. **Overwrite semantics**: Selecting a source will replace a hand-typed title/description with "<Source> - Copy" (exact Duplicate parity). Confirm overwrite is desired, vs. preserving user-entered values?
2. **AI agents & advanced settings**: `applyProjectSettings` carries `include_ai_agents`/`ai_voter_models`, factor-weight spread, passes, questions-per-group. Keep full parity (recommended), or strip AI-agent settings for copy?
3. **List scope**: Account-wide projects via `listProjectsSummary` (same visibility as Projects page/Duplicate) — confirm rather than restricting to admin-created projects?
4. Is the "New project (copy)" header/subtitle treatment acceptable after copying (it signals provenance), or should the page stay labeled "New project"?

### 3. Options and trade-offs
- **A. In-page dialog reusing the duplicate-draft loader (recommended)** — smallest diff, exact behavioral parity, no backend work; costs a small refactor of `loadDuplicateDraft()` into a shared helper.
- **B. Navigate to `/projects/0/edit?from=<id>`** — zero new logic, but changing only the query on the current route won't remount without an added watcher, causes a reload flash, and bypasses the requested dialog UX. Not recommended.
- **C. New server-side "copy settings" endpoint** — needless duplication of client logic already proven by Duplicate; adds API/test/snapshot burden for zero user-visible gain. Rejected.
- **Disabled-rule granularity**: strict (any named option *or* factor blocks copy, per brief) vs. lenient (only options block). Recommend strict — it matches the stated rule and avoids silently discarding entered factors.
- **Dialog search**: add lightweight client-side filter now vs. plain list. Recommend including it — trivial cost, consistent with shares/projects list patterns, matters once accounts hold many projects.
[comment: plan completed 2026-08-21T14:34:53.400Z | via executor-opencode | entryId e-20260821-0004 | artifacts: ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-29-03-134Z-plan-ee8xfe.request.md, ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-29-03-134Z-plan-ee8xfe.response.md, ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-29-03-134Z-plan-ee8xfe.trace.log, ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-29-03-134Z-plan-ee8xfe.result.json]


## Build Summary
### agent
Now let me check the projects API for `listProjectsSummary` and the summary type:Let me check the projects index page (where Duplicate lives) and its dialog patterns:Let me check the shares page project picker for its search pattern:I have full context now. Let me check CHANGELOG.md and the version file before implementing:Worktree has unrelated dirty files — I'll stage only mine. No CHANGELOG.md exists, so no changelog note applies. Now implementing in `edit.vue`.

**Edit 1 — Button left of "Start with Template":****Edit 2 — Picker dialog after the import picker:****Edit 3 — Type import:****Edit 4 — Refactor `loadDuplicateDraft` into a shared helper:****Edit 5 — Copy-from state, computeds, open/confirm handlers:****Edit 6 — Scoped style for the scrollable list:**Now let me verify the edited regions and bump the version:All edits in place. Now bump VERSION and run the required UI build/publish:Build succeeded and `static_client/` republished. Let me review the final diff before committing:Diff is clean. Committing only the two related files:## Build Summary

**"Copy from project" on the project create page — implemented, verified, committed.**

### What was built
- **Button**: `Copy from project` (small/tonal) rendered only in new mode, immediately left of `Start with Template`; disabled with tooltip once any option or factor is named in the draft.
- **Picker dialog**: searchable radio list of account projects (`listProjectsSummary`) showing title, tag, and option/factor counts; empty states for no projects / no search matches; Cancel/**Copy** gated on selection.
- **Copy behavior**: exact Duplicate Project parity via the shared duplicate loader — settings + options/factors copied; votes, shares, end time, disabled flag, branding, and template linkage excluded; title/tag get `- Copy`/slug treatment; header switches to "New project (copy)".
- **Refactor**: `loadDuplicateDraft()` body extracted into shared `applyDuplicateSource(sourceProjectId)` so the `?from=` deep-link and the dialog use byte-identical logic.

### Verification
- `./scripts/nuxt/update_static_client.sh` completed successfully (production generate + publish to `static_client/`); no SFC/build errors. No backend/OpenAPI changes → no pytest or snapshot work per plan.
- One deliberate deviation from plan wording: used `fa-copy` icon instead of a second `fa-clone`, since `Start with Template` directly beside it already uses `fa-clone` (identical adjacent icons would read as duplicates).

### Commit
- **Hash/message**: `5e9f451` — "Add \"Copy from project\" to the project create page"
- Staged only `client/pages/projects/[id]/edit.vue` + `src/config/config_settings.py` (version bump 0.7.69 per build policy; note this file also carried a prior uncommitted 0.7.67→0.7.68 bump now subsumed). Unrelated dirty files left untouched. No CHANGELOG.md exists in-repo, so no changelog note.

### Major touch points (`client/pages/projects/[id]/edit.vue`)
| Anchor | Location |
|---|---|
| Button (disabled rule + tooltip binding) | edit.vue:38–47 |
| Picker dialog (search, list, counts, empty states) | edit.vue:565–610 |
| `ProjectListSummaryItem` type import | edit.vue:655 |
| Shared `applyDuplicateSource()` helper | edit.vue:1363–1376 |
| `loadDuplicateDraft()` now delegates to helper | edit.vue:1378–1381 |
| State + `canCopyFromProject` / hint / filter computeds | edit.vue:1384–1397 |
| `openCopyFromDialog()` | edit.vue:1399–1415 |
| `confirmCopyFromProject()` | edit.vue:1418–1429 |
| `.copy-from-list` scroll style | edit.vue:1662–1665 |
| Version bump | src/config/config_settings.py:13 |
[comment: build completed 2026-08-21T14:49:04.441Z | via executor-opencode | entryId e-20260821-0005 | artifacts: ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-38-23-256Z-build-hcm62o.request.md, ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-38-23-256Z-build-hcm62o.response.md, ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-38-23-256Z-build-hcm62o.trace.log, ./on-the-project-create-page-add-copy-from-1ni8hs/2026-08-21T14-38-23-256Z-build-hcm62o.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T14:49:04.441Z build completed (e-20260821-0005)
- 2026-08-21T14:34:53.400Z plan completed (e-20260821-0004)
- 2026-08-21T14:29:03.051Z expand completed (e-20260821-0002)
- 2026-08-21T14:23:40.518Z created (source: user)
