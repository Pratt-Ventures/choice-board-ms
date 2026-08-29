# Factor 'What Matters Most' dual violin — importance (weight) + rank per entry with differentiation/leverage below

## Short Description
### user
Added WeightRangeBar (client/utils/weightRangeBar.ts + client/components/WeightRangeBar.vue, 0–100% axis, mean±2SD from weight/weight_ci95, deep-purple gradient) mirroring RankRangeBar. Each factor row now: wide deep-purple bar (importance mean scoreBarPercent), then Importance violin (WeightRangeBar density comfortable, fallback Importance X% (CI)), then Rank violin (RankRangeBar :item-count=factorCount density comfortable, fallback rankCi/expected), then Differentiation x% / Decision Leverage y% line. Applied to project results (client/pages/projects/[id]/results.vue:185 sortedFactorRankings), share personal (client/components/ShareVoteSession.vue:117 personalFactors) and share report (client/pages/share/report/[token]/index.vue:106 factorWeights). Added factor-violin-row/violin-label styles, weightRangeBar.test.ts (8 tests), VERSION 0.7.77, rebuilt static_client.
[comment: created 2026-08-21T22:17:19.474Z | id factor-what-matters-most-dual-violin-imp-sbvo9j]

## Expanded Description

## Plan

## Build Summary

## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T22:17:19.474Z created (source: user)
