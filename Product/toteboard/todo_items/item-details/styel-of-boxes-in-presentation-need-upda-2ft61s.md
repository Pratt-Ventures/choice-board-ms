# Styel of boxes in presentation need update

## Short Description
### user
Many larger boxes, like 'Overall Ranking' on the results pages and many others, use heavily rounded corners that clip content or come close. Change these to less rounded and consistent throughout the site.
[comment: created 2026-08-19T10:56:56.987Z | id styel-of-boxes-in-presentation-need-upda-2ft61s]

## Expanded Description
### agent
Many larger presentation cards—especially Overall Ranking on results pages—use very large border radii that clip inner content or leave it cramped against the curve. Reduce those radii so boxes stay rounded but no longer cut off titles, badges, or list items, and apply the same treatment to similar large containers site-wide. Smaller chips and buttons can keep tighter rounding; this is about card-scale surfaces.

- Scope: large result/ranking cards and other oversized boxes that currently use heavy `rounded-*` values
- Align on one or two card radii (e.g. `rounded-lg` / `rounded-xl`) instead of per-page one-offs
- Watch overflow, padding, and inner badges so content no longer sits in the clipped corners
- Audit results pages first, then matching card patterns elsewhere for consistency
- Open: keep a slightly larger radius on hero/featured cards, or one radius for all large boxes?
[comment: expand completed 2026-08-19T10:57:30.169Z | via executor-opencode | entryId e-20260819-0001 | artifacts: ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T10-56-57-096Z-expand-q492jl.request.md, ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T10-56-57-096Z-expand-q492jl.response.md, ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T10-56-57-096Z-expand-q492jl.trace.log, ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T10-56-57-096Z-expand-q492jl.result.json]


## Plan
### agent
I'll audit card radii and large-box patterns first so the plan is grounded in the actual UI.Graph exists; I'll query it and scan the UI for heavy `rounded-*` card styles.Confirming tokens and the Overall Ranking markup so the plan matches the real cascade.## Plan: reduce large-card corner radii

**Cause:** Large boxes are Vuetify `v-card`s (`glass-card` + `rounded="xl"`), not Tailwind. `$border-radius-root: 16px` makes `xl` = **96px**. That fights `--pc-radius: 16px` on `.glass-card`. Overall Ranking is inline in `results.vue` and the share report, not a shared component.

**Target:** one card radius of **12px** (same as `.pc-dialog-card` / `.share-gate`). Leave chips, pills, buttons, and progress bars alone.

### Implementation steps
1. Set `--pc-radius` to `12px` in `client/assets/styles/main.scss`.
2. Pin large surfaces with higher specificity (share-gate pattern): `.glass-card.v-card`, `.soft-card.v-card`, `.pc-card.v-card`, `.metric-card.v-card` → `border-radius: var(--pc-radius) !important`.
3. Align leftover large one-offs to the same token: `.result-hero` (18px), `.welcome-banner` (24px), `.login-card` (20px), `.probe-stage` (20px).
4. Set `$card-border-radius: 12px` in `client/assets/styles/settings.scss`. Do **not** change `$border-radius-root` (it would shrink buttons/inputs).
5. Drop `rounded="xl"` on results/report cards first (`results.vue`, `share/report/[token]/index.vue`), then the other `glass-card` pages/components so `xl` cannot win the cascade.
6. Check overflow/padding on Overall Ranking, result hero badges (`.status`, `.factor-tag`), and list rows; keep overflow visible on in-page cards.
7. Spot-check results, share report, project workspace, vote stage, login. Do not change `VChip` pills, `$button-border-radius`, or `v-progress-linear rounded`.

### Clarifying questions
1. One 12px radius for every large box, or keep a slightly larger hero (e.g. 16px) on `.result-hero` / login / welcome?
2. Include vote stage + login + welcome banner this pass, or results + `glass-card` only?
3. Prefer 12px (match dialogs) or tighter (8–10px)?

### Options
- **A. Token + CSS override (recommended):** one 12px card radius site-wide; leave Vuetify’s `lg`/`xl` scale and chips/buttons untouched. Low risk, matches prior share-gate fix.
- **B. Two radii:** 12px cards, 16px heroes. Slightly more “featured,” but less consistent and heroes still clip corner chips.
- **C. Reset `$border-radius-root` to 4px:** fixes `xl`=96px at the source, but also shrinks every `rounded="lg"` control.

**Recommend A**, unless you want heroes slightly rounder (B).
[comment: plan completed 2026-08-19T11:03:29.919Z | via executor-opencode | entryId e-20260819-0002 | artifacts: ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T10-57-30-210Z-plan-f9blbs.request.md, ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T10-57-30-210Z-plan-f9blbs.response.md, ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T10-57-30-210Z-plan-f9blbs.trace.log, ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T10-57-30-210Z-plan-f9blbs.result.json]


## Build Summary
### agent
I'll implement the 12px card-radius plan: audit current styles and markup, then apply the token and card overrides.Next I’ll read the style tokens and the large-card markup so the radius change matches the existing cascade.The token and Vuetify `xl` cascade are clear. I’ll read the remaining card surfaces, then apply the 12px pin.Applying the 12px card token, CSS pins, and stripping `rounded="xl"` from large cards.Styles look right. Rebuilding the published UI next, then I'll commit only these files.Build succeeded. Staging only the radius-related files and committing.**bf51e72** — Reduce large presentation card radii to 12px

One 12px card radius site-wide (`--pc-radius`). `rounded="xl"` (96px) dropped from glass/metric cards. Chips, buttons, progress bars unchanged. Static UI rebuilt.

**Touch points**
- `client/assets/styles/main.scss:19` — `--pc-radius: 12px`
- `client/assets/styles/main.scss:272-285` — `.glass-card.v-card` / `.soft-card.v-card` / `.pc-card.v-card` / `.metric-card.v-card` pin + overflow visible
- `client/assets/styles/main.scss:458` / `:659` / `:664` / `:1063` — welcome-banner, result-hero, probe-stage, login-card
- `client/assets/styles/settings.scss:5` — `$card-border-radius: 12px` (`$border-radius-root` left at 16px)
- `client/pages/projects/[id]/results.vue:30,76` — Overall Ranking / result hero
- `client/pages/share/report/[token]/index.vue:59` — share report ranking
- `src/config/config_settings.py:17` — version `0.7.45`
[comment: build completed 2026-08-19T11:08:33.432Z | via executor-opencode | entryId e-20260819-0003 | artifacts: ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T11-03-29-972Z-build-vwphd6.request.md, ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T11-03-29-972Z-build-vwphd6.response.md, ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T11-03-29-972Z-build-vwphd6.trace.log, ./styel-of-boxes-in-presentation-need-upda-2ft61s/2026-08-19T11-03-29-972Z-build-vwphd6.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-19T11:08:33.432Z build completed (e-20260819-0003)
- 2026-08-19T11:03:29.920Z plan completed (e-20260819-0002)
- 2026-08-19T10:57:30.169Z expand completed (e-20260819-0001)
- 2026-08-19T10:56:56.987Z created (source: user)
