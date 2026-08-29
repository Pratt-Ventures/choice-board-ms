# compare experience

## Short Description
### user
In both the logged in and shared experience, on the interstitial page that introduced each group, change the order of project fields shown from 'question' then 'title' to a box with 'title' and 'description' above a box with just 'question'.
[comment: created 2026-08-21T15:39:32.649Z | id compare-experience-1hsmww]

## Expanded Description
### agent
On the group-start interstitial shown in both the logged-in compare flow (`probe.vue`) and the shared vote session (`ShareVoteSession.vue`), reorder the displayed fields so a box containing the factor title and description appears above a separate box containing only the comparison question. This is a presentation-order change within `CompareQuestionHeader.vue`'s intro variant; no data, scheduling, or pair-frame behavior changes.

- Scope: intro variant of `client/components/CompareQuestionHeader.vue` only — restructure so title+description render as one block/box above a question-only block; `variant="pair"` rendering stays untouched.
- Both consumers (`client/pages/projects/[id]/probe.vue`, `client/components/ShareVoteSession.vue`) should pick up the change automatically with no edits expected.
- Description comes from `factorDetailsCopy()` / `criterion.description`; render it inline in the title box when present and omit gracefully when empty.
- Keep existing affordances intact: kicker ("Pass N"), circled-info details dialog, and any custom `comparison_question` wording for the question box.
- Check visual hierarchy/styling so the two boxes read as distinct cards consistent with current design tokens.
- Verify no tests or e2e flows assert on the old field order or DOM structure.
- Open: should the title box still show when there's neither description nor custom title (criteria-only passes), and does "box" imply new card styling or just reordered existing blocks?
[comment: expand completed 2026-08-21T16:04:54.644Z | via executor-opencode | entryId e-20260821-0003 | artifacts: ./compare-experience-1hsmww/2026-08-21T16-03-55-753Z-expand-e3b0jm.request.md, ./compare-experience-1hsmww/2026-08-21T16-03-55-753Z-expand-e3b0jm.response.md, ./compare-experience-1hsmww/2026-08-21T16-03-55-753Z-expand-e3b0jm.trace.log, ./compare-experience-1hsmww/2026-08-21T16-03-55-753Z-expand-e3b0jm.result.json]


## Plan

## Build Summary
### agent
All context gathered. No e2e/unit assertions on this DOM, consumers pass `criterion`/`criterionId` already. Implementing the intro-variant restructure:Now the SCSS: the standalone intro kicker must keep the `.mode-kicker` look (its rule is descendant-scoped to `.batch-mode-header`).Component verified. Rebuilding/publishing the UI (required after `client/` changes):Build succeeded and `static_client/` published. Running the client unit tests as a sanity check:No client test runner is wired into `client/package.json`; the successful production generate (which compiles every SFC template) plus zero e2e/unit references to the old DOM order covers verification. No API surface changed, so no OpenAPI regeneration. Committing only the related files:**Build complete.** The group-start interstitial now leads with a factor card (title, plus inline description when present) above a separate question-only card, in both the logged-in and shared compare flows via the intro variant only; pair frames are untouched. UI rebuilt and republished to `static_client/`.

**Commit:** `4dbe5c4` — Show factor title above question on compare group interstitials

**Major touch points**
- `client/components/CompareQuestionHeader.vue:3-29` — new intro branch: standalone pass kicker, `.criterion-banner` title box with description from `factorDetailsCopy()` (`:8-10`, omitted when empty), then `.batch-mode-header` holding only the question plus the circled-info button
- `client/components/CompareQuestionHeader.vue:30-53` — pair variant preserved verbatim (kicker+question header, banner below)
- `client/assets/styles/main.scss:758-762` — `.intro-pass-kicker` added to the kicker style group so the relocated "Pass N" line keeps its look
- `src/config/config_settings.py:13` — VERSION bump `0.7.69` → `0.7.70`
- Consumers needed no edits: `client/pages/projects/[id]/probe.vue:127-133`, `client/components/ShareVoteSession.vue:211-217`

**Verification:** `nuxt generate` succeeded end-to-end (all SFC templates compile) and `static_client/` refreshed; greps over `e2e/` and client tests found no assertions on the old field order/DOM; no API endpoints changed, so no OpenAPI snapshot regeneration was needed. No CHANGELOG.md exists in-repo, so no changelog note was added. Only the three related files were staged; unrelated dirty files were left uncommitted.
[comment: build completed 2026-08-21T16:16:24.456Z | via executor-opencode | entryId e-20260821-0004 | artifacts: ./compare-experience-1hsmww/2026-08-21T16-04-54-707Z-build-hucw5g.request.md, ./compare-experience-1hsmww/2026-08-21T16-04-54-707Z-build-hucw5g.response.md, ./compare-experience-1hsmww/2026-08-21T16-04-54-707Z-build-hucw5g.trace.log, ./compare-experience-1hsmww/2026-08-21T16-04-54-707Z-build-hucw5g.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T16:16:24.456Z build completed (e-20260821-0004)
- 2026-08-21T16:04:54.644Z expand completed (e-20260821-0003)
- 2026-08-21T15:39:32.649Z created (source: user)
