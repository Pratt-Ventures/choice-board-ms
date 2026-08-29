# The comparison process is visually clunky.

## Short Description
### user
Adjust the display, both for logged in and share users, so there is no visual box around the question. That box is distracting. The actual layout can remain the same.
[comment: created 2026-08-21T19:26:50.760Z | id the-comparison-process-is-visually-clunk-1snrqg]

## Expanded Description
### agent
The comparison flow's question is currently enclosed in a heavy bordered box that visually competes with the choices and makes the step feel clunky. Remove the box styling (border/background/shadow) around the question while preserving its existing position, size, and overall page layout. Apply the update consistently to both logged-in and share-link comparison views.

- Scope: Comparison question display for both authenticated and share/anonymous users — visual treatment only, no layout or interaction logic changes
- Scope: Strip container chrome from the question wrapper (border, fill, shadow/radius) and retain current typography and spacing
- Key consideration: Maintain clear visual hierarchy and readability without the box across breakpoints and light/dark/share themes
- Key consideration: Verify no regression to surrounding elements (answer cards, controls) and that spacing still separates question from options
- Open question: Is a minimal separator/extra whitespace needed for grouping, and should this de-boxing extend to other similar prompts?
[comment: expand completed 2026-08-21T19:51:53.783Z | via executor-opencode | entryId e-20260821-0002 | artifacts: ./the-comparison-process-is-visually-clunk-1snrqg/2026-08-21T19-51-16-157Z-expand-6hku6c.request.md, ./the-comparison-process-is-visually-clunk-1snrqg/2026-08-21T19-51-16-157Z-expand-6hku6c.response.md, ./the-comparison-process-is-visually-clunk-1snrqg/2026-08-21T19-51-16-157Z-expand-6hku6c.trace.log, ./the-comparison-process-is-visually-clunk-1snrqg/2026-08-21T19-51-16-157Z-expand-6hku6c.result.json]


## Plan

## Build Summary
### agent
Debloating the comparison question — stripping the boxed chrome while keeping layout.Found the boxed chrome around the comparison question — now excising its visual container.Visual fix verified — now tidying the commit.Build summary:

**Goal:** Remove heavy bordered box around comparison question while preserving layout/position for both logged-in and share-link views.

**Changes:**
- `client/assets/styles/main.scss:781-793` — Stripped container chrome from `.batch-mode-header` and `.batch-mode-header.criteria`: removed `border`, `background: linear-gradient(...)`, `border-radius:16px`; replaced with `border:0; background:transparent; box-shadow:none; border-radius:0; padding:2px 2px 0; margin-bottom:18px;` Retains typography (`mode-kicker`/`mode-title` at lines 758-779) and spacing separation from answer cards. Verified across `html[data-theme="light"]` / `dark` : transparent works for both; no regression to `probe-stage:668` or `choice-card:680` hierarchy. Rebuilt SPA via `./scripts/nuxt/update_static_client.sh` (precompiled `static_client/` updated, build passed 35005ms).
- `src/config/config_settings.py:13` — Bumped `VERSION` `0.7.73` → `0.7.74`.
- Anchor usages (unchanged, validated): `client/components/CompareQuestionHeader.vue:12` and `:31` (both `batch-mode-header` variants), `client/pages/projects/[id]/probe.vue:129`/`144` (logged-in compare), `client/components/ShareVoteSession.vue:210`/`225` (share compare).

Commit: `8eded6801c56b8a3f72b20673cf29452551ab081` — `feat(compare): remove boxed chrome from comparison question (1snrqg)`
[comment: build completed 2026-08-21T19:56:36.352Z | via executor-opencode | entryId e-20260821-0003 | artifacts: ./the-comparison-process-is-visually-clunk-1snrqg/2026-08-21T19-51-53-813Z-build-m2zq9n.request.md, ./the-comparison-process-is-visually-clunk-1snrqg/2026-08-21T19-51-53-813Z-build-m2zq9n.response.md, ./the-comparison-process-is-visually-clunk-1snrqg/2026-08-21T19-51-53-813Z-build-m2zq9n.trace.log, ./the-comparison-process-is-visually-clunk-1snrqg/2026-08-21T19-51-53-813Z-build-m2zq9n.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T19:56:36.352Z build completed (e-20260821-0003)
- 2026-08-21T19:51:53.783Z expand completed (e-20260821-0002)
- 2026-08-21T19:26:50.760Z created (source: user)
