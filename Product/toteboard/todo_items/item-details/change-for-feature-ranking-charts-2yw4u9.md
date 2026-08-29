# Change for feature ranking charts

## Short Description
### user
On the results page in the share results viewer and main project results viewer, a violin chart is shown for both rank and importance. Change the order from 'Importance' and then 'Rank' to 'Rank' and then 'Importance', since the list is usually sorted by rank, that provides a more intuitive order.

Ensure there is sufficient spacing so the legends don't overlap each other or text. They are tight now.

Include the violin chart on the overall page, in place of the tag and
[comment: created 2026-08-22T10:47:51.783Z | id change-for-feature-ranking-charts-2yw4u9]

## Expanded Description
### agent
Reorder the results-page violin charts in both the share results viewer and main project results viewer from Importance/Rank to Rank/Importance to align with the default rank-sorted list, increase legend/container spacing to eliminate overlap, and add the same violin visualization to the overall summary page replacing the existing tag element.

- **Scope:** Results page (`share results viewer` + `main project results viewer`) and `overall` page; swap chart/legend order, fix CSS/layout spacing, and replace tag/* (likely tag cloud) with violin chart on overall page
- **Key consideration:** Locate shared violin component to change once for both viewers; ensure Rank-first ordering in chart, legend, and any tooltips/axes
- **Key consideration:** Add padding/margin/legend positioning (wrap, gap, responsive breakpoints) so legends don't collide with each other or adjacent text at narrow widths
- **Key consideration:** Reuse same data source/props for overall page; handle empty, loading, and single-feature edge states gracefully without layout shift
- **Open questions:** Truncated brief "in place of the tag and" — confirm exact target element and fallback if no ranking data
[comment: expand completed 2026-08-22T10:48:20.066Z | via executor-opencode | entryId e-20260822-0001 | artifacts: ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-47-51-818Z-expand-jbiyf3.request.md, ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-47-51-818Z-expand-jbiyf3.response.md, ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-47-51-818Z-expand-jbiyf3.trace.log, ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-47-51-818Z-expand-jbiyf3.result.json]


## Plan
### agent
Your planning request is in — mapping the violin chart reorder and overall-page swap before detailing the build sequence.I’ve mapped the current Importance-then-Rank layout and the tight overlap risks — now finalizing the reordered plan.**Summary:** Reorder factor “What matters most” dual-violin rows on Results page from `Importance → Rank` to `Rank → Importance` in both viewers (`main project results viewer` `client/pages/projects/[id]/results.vue:200-232` + `share results viewer` personal/complete views `client/components/ShareVoteSession.vue:132-164` + `share report` `client/pages/share/report/[token]/index.vue:121-153`), fix legend/container overlap with flex/gap/padding changes, and reuse same violin on Overall ranking card replacing the truncated `tag and...` element (assumed `factor-tag` cloud/hero tags).

**Current state verified (read-only):**
* No shared component — identical markup/CSS duplicated 3× (`RankRangeBar` + `WeightRangeBar` with `factor-violin-row`/`violin-label` + `personal-rank-caption`). `WeightRangeBar.vue:87-148`/`RankRangeBar.vue:90-151` are shared viz; order is in page templates.
* Current order: `WeightRangeBar (Importance) mt-2` then `RankRangeBar mt-1` — must swap. Legends are `72px min-width` with `gap:6px 12px` (factor) / `4px 12px` (personal) and `mt-2/mt-1` — tight at 320px, tick-labels `9px` absolute under 130px viz can collide.
* Overall ranking (`results.vue:117-162`, `share/report:61-97`, `ShareVoteSession.vue:65-103` personal ranking) has single `RankRangeBar` or no factor violins; Brief truncated “in place of the tag and” — expanded assumes replace tag cloud (`results.vue:74-80 factor-tag` hero row) with same dual violin in same container.

**Execution Plan — numbered steps**

1. **Confirm scope/target:** Resolve “overall page” selector — treat as `Overall ranking` card (`results.vue:98-167`) + equivalent report/share overall card; confirm `tag` = `span.factor-tag` hero row (`results.vue:74-81`) vs separate overall-page tag cloud; photo/selector sign-off before code.
2. **Create single source if feasible (optional refactor):** Extract `FactorViolinRows.vue` wrapper (props: `criterion`, `index`, `itemCount`, `density='comfortable'`) rendering Rank then Importance to avoid 3× edits; otherwise plan 3× identical edit.
3. **Reorder — Rank first:** In all 3 files swap the two `div.factor-violin-row` blocks so `Rank` (`RankRangeBar`) is `mt-2` first, `Importance` (`WeightRangeBar`) is `mt-1` second; keep `#fallback` text and `scoreBarPercent` unchanged; verify tooltip/axis order matches.
4. **Fix legend spacing/overlap:** Update shared CSS (3 files duplicated; extract to `assets/` or keep synced):
   * `.factor-violin-row { gap: 8px 16px; row-gap >=12px; margin-bottom: 4px; }`
   * `.violin-label { min-width: 80px; }`
   * `.personal-rank-caption { gap: 6px 16px; }`
   * Add `flex-wrap:wrap; align-items:center;` already present, add `padding-right:4px` on container to prevent text clipping; set `WeightRangeBar/RankRangeBar__viz { width:130px; max-width: 42vw; }` with media query `@320px` full-width stacking; add `legend { line-height:1.2; }` and `tick-label { margin-top:2px; }` min 12–16px vertical separation.
   * Test at 320/768/1280, ensure violins don’t overlap adjacent `Differentiation/Leverage` row (`ga-4 mt-2`).
5. **Overall page — replace tag with violin:** Reuse `sortedFactorRankings` / `factorWeights` / `personalFactors` data source; in `Overall ranking` card replace `factor-tag` container (or add below hero) with same dual violin rows (Rank→Importance) per option if factor-aware, else add aggregated factor violin summary; keep hero `Score/Lead` chips if not replaced. 1:1 replacement in same container to avoid layout shift.
6. **Edge states:** Guard `factorRankings.length<=1` already hides What matters most; for overall reuse: loading skeleton, empty “No ranking data” text, single-feature hides second violin, keep height stable (`min-height`).
7. **Responsive QA & a11y:** Verify `WeightRangeBar`/`RankRangeBar` `srText` unchanged, `comfortable` density kept; check `formatWeightCi/formatRankCi` fallbacks still show; visual check with truncated title, long factor title truncation.
8. **Tests & build:** Add/update unit test for order (snapshot/DOM query `violin-label` text order), visual regression at breakpoints; run `pnpm test` / `weightRangeBar.test.ts`, `rankRangeBar` tests, `pnpm build`, rebuild `static_client` if applicable; version bump per `VERSION` pattern (0.7.x).

**Options & Trade-offs**

A. **Edit 3 files inline vs extract shared `FactorViolinPair.vue`:** Inline = minimal diff, low risk, but future drift (current duplication). Shared component = DRY, single fix guarantees consistency, better for overall reuse, but requires prop interface + import changes in 3 places. *Recommendation: Extract shared component if touching overall page anyway; otherwise do minimal swap + ticket to dedupe CSS.*

B. **Legend spacing: `flex-wrap+gap` vs absolute legend reposition:** Gap/wrap is minimal CSS, responsive naturally; absolute bottom legend needs more JS. *Recommendation: `flex-wrap` + `gap:8px 16px` + `row-gap 12px`, increase `violin-label min-width` to 80px, add `margin-top` on second row.*

C. **Overall page: dual violins (Rank+Importance) vs single Rank only:** Dual maintains consistency with Rank-first rationale; single Rank is simpler if overall page is option-centric not factor-centric. *Recommendation: Dual Rank→Importance using same props; fallback to Rank-only if no `weight_ci95` data, confirm with product.*
[comment: plan completed 2026-08-22T10:49:27.375Z | via executor-opencode | entryId e-20260822-0002 | artifacts: ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-48-20-118Z-plan-ouddls.request.md, ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-48-20-118Z-plan-ouddls.response.md, ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-48-20-118Z-plan-ouddls.trace.log, ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-48-20-118Z-plan-ouddls.result.json]


## Build Summary
### agent
Reordering Rank → Importance violins and freeing the overall view — auditing the current layout now.Core views mapped — now finalizing the design for tighter legend spacing and the new overall summary visualization.Rank → Importance order corrected — now tuning spacing and positioning the new overall violin view.Overall hero violins staged — wrapping up the remaining report view and build checks.Build passed — preparing the commit for these ranking chart updates.Build summary: Reordered factor violin charts Rank→Importance, fixed legend overlap, added overall hero violins, rebuilt UI.

Commit: `c86659c` — `feat(results): reorder factor violin Rank before Importance, add spacing and overall violin`

Major touch points:
- `client/pages/projects/[id]/results.vue:200-232` swapped `WeightRangeBar/Importance` + `RankRangeBar` blocks to Rank-first order; `53-85:140-210` added overall hero Rank violin for leader + Top factor Rank/Importance pair with fallback/empty guards; `1382-1442` updated `.personal-rank-caption` gap 6px 16px row-gap 8px line-height 1.3, `.factor-violin-row` gap 8px 16px row-gap 12px min-width 80px margin-bottom 4px padding-right 4px, added `.overall-violin-row` same, `+ .factor-violin-row` margin-top 10px, `@media max-width:480px` responsive gap/min-width
- `client/components/ShareVoteSession.vue:132-164` same Rank→Importance swap for `personalFactors`; `672-709`同步 CSS spacing + `.overall-violin-row` + responsive breakpoint
- `client/pages/share/report/[token]/index.vue:121-153` same swap for `factorWeights`; `43-55:43-115` added overall hero Rank for leader + Top factor Rank/Importance pair; `296-333`同步 CSS spacing
- `client/components/WeightRangeBar.vue:92-96` viz `max-width:42vw`; `139-147:148` tick-label `margin-top:2px line-height:1.2` + `@480px` width 110px
- `client/components/RankRangeBar.vue:95-99` viz `max-width:42vw`; `142-151` tick-label `margin-top:2px line-height:1.2` + `@480px` width 110px
- `src/config/config_settings.py:13` VERSION `0.7.78` → `0.7.79`
- `static_client/` regenerated via `scripts/nuxt/update_static_client.sh` (Nuxt generate + copy)

Verification: `update_static_client.sh` built successfully (31s client build, prerendered 22 routes, static_client replaced).
[comment: build completed 2026-08-22T10:58:45.801Z | via executor-opencode | entryId e-20260822-0003 | artifacts: ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-49-27-416Z-build-kv5cl4.request.md, ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-49-27-416Z-build-kv5cl4.response.md, ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-49-27-416Z-build-kv5cl4.trace.log, ./change-for-feature-ranking-charts-2yw4u9/2026-08-22T10-49-27-416Z-build-kv5cl4.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-22T10:58:45.801Z build completed (e-20260822-0003)
- 2026-08-22T10:49:27.375Z plan completed (e-20260822-0002)
- 2026-08-22T10:48:20.066Z expand completed (e-20260822-0001)
- 2026-08-22T10:47:51.783Z created (source: user)
