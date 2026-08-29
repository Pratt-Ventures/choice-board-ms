# Project Overview Status Display Improvements

## Short Description
### user
In the project overview page, in the 'project summary' box, add an element like the 'active participants' element with the number of AI agents requested, queued or in progress, and successfully completed, e.g., 5/2/3 - ideally, it ends at 5/0/5

Above the factor ratings, add an 'Active Participants' box. This will list all human participants with more at least 1 response with their response to date. These would only be verified emails or other team members in the project.

In the active participants box, below the list of actives (1 or more comparisons), list inactive or pending specific named invited participants. This would include invites to a known fixed emails or verified invites with flexible emails. The list include those participants with 0 responses and how many days since the invite was sent or an email was verified for an open share (they can accept but not start comparing). This should include explicit shares with a locked email or open shares where an email was verified. 

Then, list all shares that are open but are potentially anonymous (no email or name known in advance). For these, show number activated (should also be shown above).

This completes the first participant information box.

If any AI participants have been requested, add another box for the AI participants. List each model with its current status, queued, in progress, failed, complete. Show the number of pairs answered and estimated number remaining (if any).
[comment: created 2026-08-21T11:10:05.001Z | id project-overview-status-display-improvem-28d8ru]

## Expanded Description
### agent
The project overview page should surface clearer participation status in the summary and in dedicated boxes above factor ratings. Add an AI-agent counter in the project summary box in the same style as active participants (requested / queued-or-in-progress / completed, e.g. 5/2/3, ideally ending at 5/0/5). Above factor ratings, add an Active Participants box listing verified humans or team members with ≥1 comparison and their response counts, then named invited/pending people with 0 responses and days since invite or email verification, then open potentially anonymous shares with an activated count. If any AI participants were requested, add a second box listing each model with status (queued, in progress, failed, complete), pairs answered, and estimated remaining.

- Scope is the project overview page only: summary chip plus human participants box, and an AI box only when AI work was requested.
- Active humans are verified emails or project team members with at least one comparison; show response-to-date counts.
- Inactive/pending covers locked-email invites and verified open shares with 0 responses, including days since invite sent or email verified.
- Anonymous/open shares (no name or email known in advance) should show activated count, consistent with the summary.
- AI box is per model: status, pairs answered, and remaining estimate when applicable.
- Open questions: data sources for invite/verify timestamps and remaining-pair estimates, and whether failed AI runs stay listed until retry or dismissal.
[comment: expand completed 2026-08-21T11:10:45.340Z | via executor-opencode | entryId e-20260821-0001 | artifacts: ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-10-05-145Z-expand-e8ihny.request.md, ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-10-05-145Z-expand-e8ihny.response.md, ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-10-05-145Z-expand-e8ihny.trace.log, ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-10-05-145Z-expand-e8ihny.result.json]


## Plan
### agent
I'll inspect the project overview page and related participant/AI status data so the plan matches the current UI and APIs.I'll search the overview UI, participant APIs, and AI-run status next so the plan can name concrete files and data sources.The overview page has the summary chips but no factor-ratings block yet; I'll check results and prototypes for that layout.# Project Overview Status Display Improvements

Scope: `client/pages/projects/[id]/index.vue` plus lean summary API. Insert new boxes between the summary hero and the Options/Factors row (overview has no factor-ratings block today).

## 1. Implementation steps

1. **Extend `ProjectPageSummaryResult`** in `src/api/app_customer_project_management.py` (mirror in `client/types/api.ts`):
   - `ai_agent_counts: {requested, in_flight, completed}` for the summary chip (`5/2/3` → `5/0/5`).
   - `human_participants`: `{active: [...], pending: [...], anonymous_shares: [...]}`.
   - `ai_participants`: list of per-model rows, omitted/empty when no AI work was requested.
   Keep the existing lean contract; do not attach report/next-probe blobs.

2. **Classify humans server-side** (exclude `VoteSource.ai`):
   - **Active:** `source=session` team members **or** verified-email share identities, with `comparison_count >= 1`. Label = `display_name` else email; show `comparison_count`.
   - **Pending/inactive:** named, 0 comparisons:
     - Locked-email vote/vote_view shares (`email_matching*`, `recipient_email_verified*`, password variants) even with no participant row.
     - Open verified modes (`email_any_verified*`) after magic-key redemption (`ShareLinkMagicKey.accessed_date`) with 0 comparisons.
     - Session participants with 0 comparisons.
     - Days = floor((now − timestamp) / 1d) from invite send (`_latest_invite_send_by_token` / `EmailActivityLog`) else verify time else share `create_date`.
   - **Anonymous/open shares:** modes with no name/email in advance (`open_access`, `email_any_unverified`, `password_only`, `password_with_email_any_unverified`). One row per share: label + **activated** = participants with `comparison_count >= 1` (same rule as the existing Active-participants chip). Ignore report-only shares.

3. **AI chip + box**
   - Show chip when `requested > 0`. Counts: distinct models with jobs and/or complete AI participants; `in_flight` = `queued`+`in_progress`; `completed` = job `complete` or `participant.is_complete`. Failed is neither in-flight nor completed (`5/0/4` if one failed).
   - Show AI box only when any AI was requested. One row per model (latest job): status queued / in progress / failed / complete, `pairs_answered` = `AiAgentJob.pair_count` (fallback `comparison_count`), `pairs_remaining` = `max(0, target_comparisons_est − pairs_answered)` when not complete (AI stops at `min_expected_passes`, same as that estimate). Remaining `0` when complete; still show remaining on failed.
   - Reuse `AiAgentJob.list_for_project` / `_job_view` status mapping. Keep failed rows until a later successful run for that model (latest job wins).

4. **Overview UI** (`index.vue`):
   - New metric pill beside Active participants: `<strong>5/2/3</strong><span>AI agents</span>` with tooltip “requested / queued or in progress / completed”. Hide if `requested === 0`.
   - **Active Participants** glass-card: Active list (name + responses), then Pending (name/email + “N days”), then Anonymous (share label + activated count). Empty sections omitted; empty card if no humans/shares.
   - **AI participants** card under it when requested > 0: model display name, status chip, pairs answered, remaining if > 0.
   - Match existing `metric-pill` / `rank-row` / `glass-card` styling. Light-poll summary (or AI fields only) while `in_flight > 0`.

5. **Tests** in `src/tests/test_manage_projects.py` (and AI fixtures from `test_ai_agents.py` as needed):
   - Chip `requested/in_flight/completed` including the all-complete `N/0/N` case and a failed-job case.
   - Active vs pending vs anonymous buckets, invite/verify day counts, locked-email with zero access.
   - AI rows: status, pair counts, remaining vs `target_comparisons_est`.
   - Report-only shares excluded; AI excluded from human lists.
   - Cross-tenant still denied.

6. **Verify:** existing page-summary lean assertions still pass; `npm`/client types compile for the new fields.

## 2. Clarifying questions

1. Overview has Options/Factors, not factor ratings. Confirm boxes go on this hub page between summary and Options/Factors — not on Results (“What matters most”).
2. Should anonymous people with ≥1 comparison appear **by name** in Active, or only as the anonymous activated count (brief says verified/team only)?
3. Private participation: show real names on this owner hub, or anonymize like Results?
4. Failed AI: keep listing the latest failed job until retry (recommended), or hide after dismiss (no dismiss API today)?
5. “Activated” for anonymous = participants with ≥1 comparison (aligned with the summary chip), or any access/cookie even at 0 comparisons?

## 3. Options and trade-offs

**A. Extend `customer-project-page-summary` (recommended)**  
One load, matches current `getProjectPageSummary`. Slightly heavier hub payload, but no extra round-trips and classification stays server-owned.

**B. New participation endpoint**  
Keeps summary lean; extra client fetch and duplication of project/share joins.

**C. Compose from `participants` + share activity + `ai-baseline-status`**  
Avoids API change, but client cannot get invite/verify days, locked-email pending with no participant, or remaining-pair estimates without new fields anyway.

**AI remaining:** use existing `target_comparisons_est` (min passes) rather than inventing a second estimator — same number the AI worker already targets.

**Failed in the chip:** exclude from the middle number (spec: queued/in-progress only). Show failed only in the AI box.

**Recommendation:** Option A; anonymous actives counted not named; owner hub shows identities even if `private_participation`; failed stays until a newer job for that model.
[comment: plan completed 2026-08-21T11:14:10.849Z | via executor-opencode | entryId e-20260821-0002 | artifacts: ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-10-45-433Z-plan-8xtli3.request.md, ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-10-45-433Z-plan-8xtli3.response.md, ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-10-45-433Z-plan-8xtli3.trace.log, ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-10-45-433Z-plan-8xtli3.result.json]


## Build Summary
### agent
I'll inspect the overview page, summary API, and participant/AI status sources first so the implementation matches the current UI and contracts.I have the data sources and layout. Next I’ll extend the summary API, then wire the overview chips and participant boxes.**a87f95deef0bae8e54701c64b8ee195a14ae3c2f** — Show project overview participation status for humans and AI agents

Lean `customer-project-page-summary` now returns AI chip counts plus classified human/AI rows. Overview hub shows the `5/2/3` pill, Active Participants (active / pending / open shares), and an AI box when any agents were requested. Tests, OpenAPI sessions snapshot, and static client rebuild are done.

Touch points:
- `src/utils/project_overview_participation.py:45` `AiAgentCounts`; `:71` `HumanParticipantsSummary`; `:162` `build_human_participants`; `:349` `build_ai_participation`
- `src/api/app_customer_project_management.py:202` `ProjectPageSummaryResult`; `:220–228` new fields; `:590–631` assemble payload
- `client/pages/projects/[id]/index.vue:82` AI chip; `:108` Active Participants; `:141` AI participants
- `client/types/api.ts:182` / `:208` / `:222`
- `src/tests/test_manage_projects.py:444` human buckets; `:577` AI rows; `:644` `N/0/N` chip
[comment: build completed 2026-08-21T11:28:09.749Z | via executor-opencode | entryId e-20260821-0003 | artifacts: ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-14-10-953Z-build-4xhyor.request.md, ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-14-10-953Z-build-4xhyor.response.md, ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-14-10-953Z-build-4xhyor.trace.log, ./project-overview-status-display-improvem-28d8ru/2026-08-21T11-14-10-953Z-build-4xhyor.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T11:28:09.749Z build completed (e-20260821-0003)
- 2026-08-21T11:14:10.849Z plan completed (e-20260821-0002)
- 2026-08-21T11:10:45.341Z expand completed (e-20260821-0001)
- 2026-08-21T11:10:05.001Z created (source: user)
