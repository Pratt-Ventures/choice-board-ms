# Add 'Comaprison in Question Format'

## Short Description
### user
The formatting of the factors with optoins during comparison is awkward. Let's add a field to the configured factor 'Comparison Question' that is the factor worded for the comparison process. So the factor can say 'Engineering Cost' and the Factor Question can say, 'Which option has lower Engineering Cost?'

This will help reduce the cognitive load during processing.

We should show both during the interstitial when factors are changing or a new group is starting. During individual qeustion frames, only the question is shown if present, otherwise a generate 'Choose the Best Based on <Factor Title> is used, like today. A circled I should be available to see the accompanying title/description of the factor in any case.
[comment: updated 2026-08-21T03:17:39.945Z | id add-comaprison-in-question-format-35pcxr]

## Expanded Description
### agent
Add an optional Comparison Question on each configured factor so pairwise comparison can use natural wording (e.g. “Which option has lower Engineering Cost?”) instead of making users interpret the factor title against options. Interstitials that start a new factor or group should show both the factor title and the comparison question; individual question frames should show only the question when one is set, otherwise keep today’s generated “Choose the Best Based on &lt;Factor Title&gt;”. A circled info control should always expose the factor’s title and description without cluttering the comparison UI.

- Scope: factor config schema/UI for Comparison Question; interstitial vs per-question display; info affordance for title/description
- Fallback: empty Comparison Question keeps the current generated prompt
- Interstitials show title + question; question frames show question only when present
- Circled I available on all comparison frames, including fallback copy
- Treat title/description as source of truth; question is comparison-specific wording only
- Open: required vs optional; length limits; use in results/exports/history; a11y of the info control; group vs factor interstitial distinction
[comment: expand completed 2026-08-21T03:18:08.305Z | via executor-opencode | entryId e-20260821-0001 | artifacts: ./add-comaprison-in-question-format-35pcxr/2026-08-21T03-17-25-502Z-expand-r1ncv9.request.md, ./add-comaprison-in-question-format-35pcxr/2026-08-21T03-17-25-502Z-expand-r1ncv9.response.md, ./add-comaprison-in-question-format-35pcxr/2026-08-21T03-17-25-502Z-expand-r1ncv9.trace.log, ./add-comaprison-in-question-format-35pcxr/2026-08-21T03-17-25-502Z-expand-r1ncv9.result.json]


## Plan
### agent
I'll inspect how factors and comparison prompts are defined so the plan matches the current UI.Graphify is present; I’ll query it and inspect factor/comparison code in parallel.I’ll verify the factor editor, comparison frames, and API models so the plan matches the code.# Add Comparison Question — execution plan

Current production copy is **not** “Choose the Best Based on \<Factor Title\>”. Option frames use **“Which option is better?”** plus a **Consider + factor title** banner (`probe.vue`, `ShareVoteSession.vue`). Interstitials already show title + description for every new group when ≥2 factors are enabled. There is no info control. Fallback should map onto that live UI, not resurrect unused toteboard wording.

## 1. Implementation steps

1. **Schema** — Add optional nullable `comparison_question` on `CustomerProjectFactors` (`src/db/models/customer_project_alternatives_criteria.py`). Alembic after head `s0t1u2v3w4x5` (same pattern as `l3m4n5o6p7q8_add_project_end_time.py`). Also add to `FactorTemplateEntry` JSONB (no table change). Empty/whitespace → `null`.

2. **API** — Thread the field through `FactorForm` / `FactorUpdateForm` and create/update in `src/api/app_customer_project_content_management.py`. Client: `CustomerProjectFactor`, `FactorTemplateEntry`, `useProjectsApi` create/update bodies.

3. **Session payload** — Do **not** put the field on every `serialize_item` (those are option/factor cards). Add it only on criterion in `_slot_items_and_criterion` / a small `serialize_criterion`. Extend `SortGroupPayload.criterion` with `comparison_question?: string | null`.

4. **Editor** — In `edit.vue` factors tab, add “Comparison question” under title/description (placeholder e.g. `Which option has lower Engineering Cost?`). Wire `addFactor`, `loadContentRows`, `syncFactors`, `applyFactorsFromTemplate`. Same field on `templates/index.vue`. Hint: optional; used only during pairwise option comparisons.

5. **Prompt helper** (shared, used by probe + share):
   - Trimmed `comparison_question` present → that string is the question.
   - Else keep today’s generated prompt: mode-title **“Which option is better?”** + Consider banner with title (Overall if no factor).
   - Criteria groups unchanged: **“Which factor matters more?”** (no per-factor question).

6. **Interstitial** (option groups) — Show **title + comparison question** (or fallback question). Move description off the banner; it lives behind info. Keep current gate: intro on **every** new group in multi-factor mode (including same-factor batches and criteria groups). Criteria intro stays “Factor priorities” / “Which factor matters more?”.

7. **Question frames** — If a comparison question is set, show **only that question** (no duplicate Consider + title). If unset, keep today’s generated prompt + title banner. Apply in both `probe.vue` and `ShareVoteSession.vue`.

8. **Circled I** — On all option-comparison frames (intro + pairs, custom and fallback). `fa-circle-info` button, `aria-label="Factor details"`, opens a short dialog/menu with **title + description** (and omit empty description). Keyboard: focusable, Enter/Space, Escape to close. Skip on criteria-priority frames (items are the factors).

9. **Out of results/exports** — Rankings, reports, overview keep title/description as identity. Do not surface comparison question there unless a follow-up asks.

10. **Tests** — CRUD roundtrip + template JSONB in `test_manage_project_content.py`. Criterion serialization includes/omits the field in `test_sort_compare.py`. Optional: small client helper test for prompt fallback. No e2e required unless already running comparison UI.

11. **AI pairwise (small, same ticket)** — If `comparison_question` is set, pass it in `pairwise_messages` as the comparison wording; title/description stay the factor identity. Do not auto-generate questions (separate LLM-wording work).

## 2. Clarifying questions

1. Fallback copy: keep live **“Which option is better?” + Consider \<title\>**, or switch empty questions to **“Choose the Best Based on \<title\>”**?
2. Interstitials: keep one intro **per group**, or only when the **factor changes** (skip same-factor batches)?
3. On interstitials, should description stay visible **and** the question, or description **only** behind the info control (as specified)?
4. Templates: include Comparison Question now, or project editor only?
5. AI voters: use the comparison question as the lens this ticket, or humans-only?
6. Max length (suggest 200) vs unconstrained like `factor_title`?

## 3. Options and trade-offs

| Topic | Options | Recommendation |
|---|---|---|
| Fallback copy | A) Live “Which option is better?” + Consider title. B) Tote “Choose the Best Based on \<title\>”. | **A** — matches shipped UI; B would change the empty-field path. |
| Required vs optional | Required on save vs optional with fallback. | **Optional.** Existing projects and overall-only mode keep working. |
| Interstitial frequency | Every group (today) vs only on factor/mode change. | **Keep every group.** Spec says new group or factor change; narrowing can be a follow-up. |
| Info vs inline description | Inline title+description+question vs question/title on canvas, details behind I. | **Details behind I** on both intro and pairs, so the canvas stays a question. |
| Shared UI | Duplicate probe/share edits vs extract a header component. | **Extract a small compare-header** (question + optional banner + info) so the two surfaces cannot drift. |
| Criterion payload | Add field to all `serialize_item` vs criterion-only. | **Criterion-only.** Option cards must not grow factor-only fields. |
| Results/history | Show question in rankings vs title-only. | **Title-only.** Question is comparison UX, not the factor’s name. |
| Length | Hard cap vs unconstrained. | **Trim to null; cap ~200** with counter in the editor. |

**Default if unanswered:** optional field, live fallback copy, intro every group, description only in the info popover, templates included, AI uses the question when present, 200-char cap.
[comment: plan completed 2026-08-21T03:26:13.561Z | via executor-opencode | entryId e-20260821-0002 | artifacts: ./add-comaprison-in-question-format-35pcxr/2026-08-21T03-18-08-342Z-plan-nnonym.request.md, ./add-comaprison-in-question-format-35pcxr/2026-08-21T03-18-08-342Z-plan-nnonym.response.md, ./add-comaprison-in-question-format-35pcxr/2026-08-21T03-18-08-342Z-plan-nnonym.trace.log, ./add-comaprison-in-question-format-35pcxr/2026-08-21T03-18-08-342Z-plan-nnonym.result.json]


## Build Summary
### agent
I'll inspect factor/comparison models and UI first so the implementation matches the live schema and frames.Graphify is present; I'll query it and read the factor/comparison code in parallel.I have the live prompt and payload shape. Next I’ll add the field through schema, API, session payload, and both compare surfaces.**Build complete.** Optional `comparison_question` on factors; interstitials show title + question; pair frames use the custom question or keep “Which option is better?”; title/description behind circled-info. v0.7.65.

**Commit:** `ab54cad` — Add optional comparison question for pairwise factor comparisons

**Touch points**
- Schema: `src/db/models/customer_project_alternatives_criteria.py:19`, `:505`; Alembic `src/alembic/versions/v3w4x5y6z7a8_add_factor_comparison_question.py:20`
- API: `src/api/app_customer_project_content_management.py:230`, `:281`, `:315`
- Criterion payload: `src/utils/vote_sort_session.py:81`, `:632`
- Editor: `client/pages/projects/[id]/edit.vue:443`; templates `client/pages/templates/index.vue:125`
- Compare UI: `client/components/CompareQuestionHeader.vue:9`, `:21`; `client/pages/projects/[id]/probe.vue:127`, `:142`; `client/components/ShareVoteSession.vue:200`, `:215`
- Prompt helper: `client/utils/comparePrompt.ts:20`; AI: `src/utils/ai/prompts.py:40`
[comment: build completed 2026-08-21T11:52:12.525Z | via executor-opencode | entryId e-20260821-0001 | artifacts: ./add-comaprison-in-question-format-35pcxr/2026-08-21T11-35-40-650Z-build-m332nm.request.md, ./add-comaprison-in-question-format-35pcxr/2026-08-21T11-35-40-650Z-build-m332nm.response.md, ./add-comaprison-in-question-format-35pcxr/2026-08-21T11-35-40-650Z-build-m332nm.trace.log, ./add-comaprison-in-question-format-35pcxr/2026-08-21T11-35-40-650Z-build-m332nm.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T11:52:12.527Z build completed (e-20260821-0001)
- 2026-08-21T03:26:13.561Z plan completed (e-20260821-0002)
- 2026-08-21T03:18:08.305Z expand completed (e-20260821-0001)
- 2026-08-21T03:17:25.458Z created (source: user)
