# Automatic LLM Wording of Option and Factor information

## Short Description
### user
Factors are sometimes clunky when the better direction (less is better vs more is better) or temporally going forward vs historical vs projected-all-time. Using the LLM model configured in a recent update, we'd like an option on the option and criteria editing screen to rewrite all items with a prompt, one configured for each task, one option or factor at a time. The rewrites (with a default prompt generated in this task), will generate crisp concise option prompts for comparisons (added along with titles and descriptions in database), then similar for the factors. The new 'compare-prompt' for each would be concise and clear.  The options would be altered to produce clear, consistent and concise values when comparing. The factors would be worded concisely as a question, like 'Which requires less engineering resources?" This might be generated from 'Engineering resources needed, ramaining" - It adds a 'compare-prompt' value to the option information.

The compare prompt values will be used during option / factor compare process when available. The existing title/description will be used otherwise. Both values will be visible in the appropriate project settings areas and can be edited once generated. Project settings will have a 'Generate concise options and factors.' It will only generate for options or factors in the project that do not have the value set. The user will have a 'clear' buttion to delete the values if they don't like them or somethings changed. Apply the necessary work to do this, without changing the PVF areas at this time.  Indicate in earlier reviews if questions need answering and these will be answered inline before proceeding.

Each customer has an optional model provider, stored BYOK value, and model selection. That should be used for this purpose and the feature is otherwise disabled. When disabled, a hover should say, 'There is no provider set up for this customer, check settings to enable'

This process should queue the request, as a new type of processing, to be handled by the watcher process for all options in the current group. The database will be adjusted as each option is converted. Some indicate to the user that this 'Auto generate or refine questions' has been done.
[comment: updated 2026-08-21T13:39:44.271Z | id automatic-llm-wording-of-option-and-fact-2qt9i4]

## Expanded Description
### agent
I'll inspect the existing option/factor compare flow and customer LLM/BYOK setup so the expansion matches the codebase.Skipping graphify writes. I'll only read existing option/factor compare and customer LLM settings.Add a stored `compare-prompt` on each project option and factor so pairwise compares can use crisp, LLM-rewritten wording instead of clunky titles (factors as a question such as “Which requires less engineering resources?”; options as short consistent labels). Generation uses the customer’s configured provider, BYOK key, and model, one item at a time with default prompts produced in this work; project settings get “Generate concise options and factors” (only fills blanks) plus a clear action, and both the generated prompt and original title/description stay visible and editable. When `compare-prompt` is set it is used in the option/factor compare flow; otherwise title/description remain the fallback. The control is disabled without a customer provider, with hover text “There is no provider set up for this customer, check settings to enable”; do not change PVF.

- **Scope:** Alembic + models/APIs for `compare_prompt` on alternatives and factors; default option vs factor rewrite prompts; generate/clear on project settings and option/factor edit screens; consume the field in compare UI (and existing AI compare prompts) when present. Skip PVF, templates, and unrelated AI-agent job plumbing.
- **Behavior:** Bulk generate only for items with an empty `compare-prompt`; sequential per-item LLM calls; factor prompts should take polarity (less vs more is better) and temporal framing; titles/descriptions are not overwritten.
- **Gate:** Feature requires a customer-level provider + BYOK + model; today AI is env-level (`AI_SERVICE` / `AI_API_KEY` / `AI_MODEL`), so this either depends on that recent per-customer settings work or must add it.
- **Open:** Confirm per-customer BYOK is the intended source (vs env AI). Is “Clear” per-item, all blanks, or all generated values? Are rewrite prompts system defaults only, or customer-editable? Should human vote cards, AI voter prompts, or both use `compare-prompt`? Generate from option/factor pages as well as project settings, or settings-only?
[comment: expanded description edited 2026-08-21T13:39:44.271Z]


## Plan
### agent
Your wording upgrade is queued — drafting the LLM compare-prompt plan for options and factors.# Plan — Automatic LLM Wording of Option and Factor information (2qt9i4)

**Context validation (read-only):** No `compare_prompt` field exists (`grep compare_prompt` 0 hits). Options=`CustomerProjectAlternatives` and Factors=`CustomerProjectFactors` in `src/db/models/customer_project_alternatives_criteria.py:348,499` have `alternative_title/_description` and `factor_title/_description + comparison_question + polarity` but no concise compare wording. `CustomerProject` in `src/db/models/customer_projects.py:32` unchanged. LLM gating today is dual: env-level (`AI_SERVICE`/`AI_API_KEY`/`AI_MODEL` via `src/utils/ai/config.py:76-86`, `src/utils/ai/provider.py:21`) and per-customer BYOK (`customer_llm_configured` in `src/utils/ai/config.py:165`, `resolve_llm_credentials` prefers customer then system). Compare flow uses `normalize_comparison_question` (`src/utils/comparison_question.py:1`) and `pairwise_messages` (`src/utils/ai/prompts.py:204`) + worker quota logic (`src/utils/ai/worker.py:268`). Watcher is `src/powerchoice_watcher.py:92` polling `WATCHER_PROCESS_AI_AGENTS_TAG`; recent migrations `t1u2v3w4x5y6_customer_ai_and_multi_agents.py`, `s0t1u2v3w4x5y6_ai_agent_jobs_and_votesource_ai.py`, `v3w4x5y6z7a8_add_factor_comparison_question.py` show pattern.

## 1. Numbered Implementation Steps

1.  **Schema + migration:** Add `compare_prompt TEXT NULL` (or `VARCHAR(300)`) to `CustomerProjectAlternatives` and `CustomerProjectFactors` via `PvfAddedColumn` + Alembic `src/alembic/versions/*_add_compare_prompt.py` (mirrors `v3w4x5y6z7a8`). No PVF core table edits; application-only. Add normalization `normalize_compare_prompt` parallel to `normalize_comparison_question` (trim, 200-280 char cap, null-on-empty).
2.  **Model/API DTOs:** Expose `compare_prompt` in `Alternative/Factor` create/update response models, `model_dump(exclude_unset)` allowlists in `update_alternative:388` / `update_factor:549`, and `get_all_by_project_id*` SELECT serialization. No overwrite of `title/description`. Keep `comparison_question` on factors distinct (legacy question) vs new `compare_prompt` (LLM crisp question).
3.  **Default rewrite prompts (system defaults, no PVF change):** Add to `src/config/config_settings.py` (or `src/utils/ai/prompts.py:_DEFAULT_*`): `AI_REWRITE_OPTION_PROMPT` and `AI_REWRITE_FACTOR_PROMPT`. Draft defaults this ticket produces: Option: "Rewrite title+description as 2-5 word consistent label for pairwise comparison; no punctuation; preserve meaning; return JSON {\"compare_prompt\":string}" ; Factor: "Rewrite as concise question 'Which ...?' ≤120 chars; respect polarity (factor_polarity_positive / factor_polarity_note) and temporal cue (less-is-better vs more-is-better, historical vs forward vs projected-all-time); return JSON {\"compare_prompt\":string}". Provide tests for truncation/escaping.
4.  **LLM rewrite helpers:** In `src/utils/ai/prompts.py` add `option_rewrite_messages(title,desc)` and `factor_rewrite_messages(title,desc,polarity,polarity_note)` returning `messages` + `chat_json_sync` wrappers in `src/utils/ai/provider.py` pattern (use `resolve_llm_credentials(customer)` strictly — no env fallback per spec). Add parsers `parse_compare_prompt(payload)` with length guard.
5.  **Gate check utility:** `can_use_compare_prompt_llm(customer) = customer_llm_configured(customer)` (`src/utils/ai/config.py:165`). Feature disabled if false. API for generate must return `failure_reason="There is no provider set up for this customer, check settings to enable"` (hover text spec) and HTTP 409; front-end disables button + `title` hover.
6.  **Queue / watcher new job type:** Do not claim `AI_AGENTS` job plumbing. Add new application watcher module tag `WATCHER_PROCESS_REWORD_TAG` (settings + `src/pvf/config/pvf_app_startup.yaml` `WATCHER_PROCESS_MODULE_LIST`) or reuse `AiAgentJob` with `job_type='reword'` discriminator. Recommended minimal: new table `CustomerProjectRewordJob {id, customer_id, project_id, item_type ('option'|'factor'), item_id, status queued/processing/complete/failed, compare_prompt, error, create/modify}` + `claim_next` ordered FIFO. Enqueue is sequential per-item (one LLM call at a time per spec) for all `compare_prompt IS NULL` in project group. DB is adjusted as each option/factor converts (update row, commit). Show progress via polling API `GET /projects/{id}/reword-status`.
7.  **Bulk API: Generate + Clear (project settings):** `POST /projects/{id}/compare-prompts/generate` — auth `UserAccessDepCustomerAdmin`, loads project, checks gate, selects rows where `compare_prompt IS NULL` (only blanks), creates queued jobs sequentially, returns `{queued, skipped_existing, disabled_reason}`. `POST /projects/{id}/compare-prompts/clear` — deletes (sets NULL) `compare_prompt` values (scope TBD via question #2). Both invalidate `sync_project_group_sizes` not needed. Emit `log_event`.
8.  **Per-item API:** `PATCH /alternatives/{id}` and `/factors/{id}` already support update; add `POST /alternatives/{id}/compare-prompt/generate` and `/factors/{id}/generate` (single-item) plus allow direct `PATCH compare_prompt` edit from option/factor edit screens. Generate-one reuses same LLM helper and gate.
9.  **Consume in compare flow:** Human compare UI (`src/utils/vote_sort_session.py`, `src/utils/pair_scheduler.py` callers, client `client/pages/compare.vue` / `useVote` ) : when rendering pair, prefer `compare_prompt` if non-null else fallback `title/description` : Options: concise label; Factors: question string (`Which...?`). AI voter prompts (`src/utils/ai/worker.py:276,294` `pairwise_messages`): if `item_lookup[id].compare_prompt` present, use it as title override for options and as injected `factor_question` for factors; else existing title/description. No PVF template changes; templates remain copy-on-import.
10. **Project settings & edit screens UI:** Add section "Concise wording" showing both `title/description` (read-only) and editable `Compare prompt` input; button "Generate concise options and factors" (bulk) disabled + hover when gate false; per-row "Generate" + "Clear" on option/factor lists. Toast "Auto generate or refine questions has been done." on completion poll.
11. **Watcher integration:** `src/powerchoice_watcher.py:92` add branch for reword tag calling `src/utils/ai/reword_worker.py:process_next_reword_job(session)` (fetches credentials via `resolve_llm_credentials(customer)` per job's customer, calls provider `chat_json_sync`, updates target row, marks job complete/failed). Sequential per-item; on retryable `AiProviderError` requeue with backoff.
12. **Tests/migration verification:** Unit tests for normalization, `parse_compare_prompt`, gate, and worker mock (no live LLM). Alembic downgrade removes column. Manual QA: create project 3 options + 2 factors with clunky wording, gate off → hover, gate on → bulk generate → verify only blanks filled, edit persists, compare cards show new wording.

## 2. Clarifying Questions (need answers before build)

1.  **Per-customer BYOK source of truth:** Spec says customer BYOK (`ai_provider` + encrypted key + `ai_model`). Current prod still supports env `AI_SERVICE` fallback. Should reword feature strictly require `customer_llm_configured` (no fallback), or allow system fallback when customer empty? (Expanded Gate notes dependency.)
2.  **Clear scope:** Is "clear" per-item button only, or also project-level "Clear all generated prompts" vs "Clear blanks only"? Brief says "clear button to delete the values if they don't like them" — plural unclear.
3.  **Rewrite prompt editability:** Are default rewrite prompts system-only defaults (produced in this task) or customer-editable per-customer settings? Affects `config_settings` vs `Customer` column.
4.  **Where `compare_prompt` surfaces:** Human vote cards only, AI voter prompts only, or both? Spec: "during option / factor compare process when available" — implies humans; AI worker also benefits.
5.  **Entry points:** Generate from project settings only, or also from option-edit and factor-edit screens ("option on the option and criteria editing screen") as brief states? Expanded says both.
6.  **Queue granularity:** "for all options in the current group" vs all options/factors in project? Which grouping (active sort group vs whole project)?
7.  **Overwrite policy:** Bulk generate "only fills blanks" — does per-item Generate overwrite existing, or require Clear first?
8.  **PVF boundary:** Skill says skip PVF/templates/job plumbing — confirm new `compare_prompt` should not be copied to `CustomerFactorTemplates`/`OptionTemplateEntry` import?

## 3. Options & Trade-offs + Recommendation

**A. Storage type for `compare_prompt`:**
- *Option A1: `TEXT NULL` nullable* — simple, matches `comparison_question`. Pros: explicit blank vs set, easy query `IS NULL`. Cons: longer strings possible.
- *Option A2: `JSONB details.compare_prompt`* — avoids migration. Cons: harder indexing, breaks existing pattern where `comparison_question` is column.
- **Recommendation: A1 (`VARCHAR(280)/TEXT`, indexed where needed).** Consistent with `src/db/models/customer_project_alternatives_criteria.py:505` and migration history; clean `IS NULL` bulk logic.

**B. Async execution:**
- *B1: New watcher job table + module* — Pros: matches "queue the request ... watcher for all options" spec, durable, retryable, sequential. Cons: new settings/tag, watcher deployment update.
- *B2: Inline request (API calls LLM synchronously, loops items)* — Pros: no watcher change. Cons: HTTP timeout on 10-20 sequential LLM calls, blocks user.
- *B3: Reuse existing `AiAgentJob` with `job_type` column* — Pros: no new table. Cons: mixes concerns, quota logic entanglement.
- **Recommendation: B1.** Add `CustomerProjectRewordJob` and `WATCHER_PROCESS_REWORD_TAG`. Sequential per-item, one LLM call at a time per spec; progress feedback natural. Fallback: if watcher deploy is gated, ship B2 behind feature flag then migrate.

**C. LLM gating:**
- *Strict BYOK-only* vs *BYOK with system fallback* (`src/utils/ai/config.py:212`). Strict enforces customer setup and hover message; fallback hides missing config.
- **Recommendation: Strict BYOK-only** per spec hover text, while `resolve_llm_credentials` currently falls back — gate reword paths with `customer_llm_configured()` check before `resolve_llm_credentials` and never use `source=="system"` for this feature.

**D. Consume location:**
- *Human UI only* vs *Human + AI prompts* . Adding to `src/utils/ai/prompts.py:pairwise_messages` is 2-line change in `src/utils/ai/worker.py:276-306` and improves AI baseline consistency.
- **Recommendation: Both**, behind `if compare_prompt` fallback to title/description/ `comparison_question`; minimal risk.

**E. Default prompt location:**
- *Code constants in `src/utils/ai/prompts.py`* vs *DB-stored per customer* . Code constants are deployable and versioned; DB adds settings UI scope creep.
- **Recommendation: Code constants + `config_settings` overrides** (like `AI_PROMPT_SINGLE_OPTION_TEMPLATE`). System defaults produced now; customer-editable later if needed.
[comment: plan completed 2026-08-21T19:22:26.061Z | via executor-opencode | entryId e-20260821-0001 | artifacts: ./automatic-llm-wording-of-option-and-fact-2qt9i4/2026-08-21T19-21-33-200Z-plan-n2qnaj.request.md, ./automatic-llm-wording-of-option-and-fact-2qt9i4/2026-08-21T19-21-33-200Z-plan-n2qnaj.response.md, ./automatic-llm-wording-of-option-and-fact-2qt9i4/2026-08-21T19-21-33-200Z-plan-n2qnaj.trace.log, ./automatic-llm-wording-of-option-and-fact-2qt9i4/2026-08-21T19-21-33-200Z-plan-n2qnaj.result.json]


## Build Summary
### agent
Wiring crisp LLM compare-prompts for options and factors — scaffolding the schema and queued rewrite flow.Core research complete — now implementing the queued generation pipeline and UI edits.Backend queue and API layer ready — now building the frontend generation controls.Project settings UI updated — finalizing compare display and validating the build.Concise wording editors complete — final checks on version bumps and migrations.Version bump hit a config snag — patching and re-testing the build.Migrations applied and tests green — generating final OpenAPI snapshots.Full build succeeded — staging changes and committing.Build summary — commit 81d1a7f `feat(compare-prompts): automatic LLM wording of option and factor info (2qt9i4)`

Major touch points (file:line):

- Schema: `src/db/models/customer_project_alternatives_criteria.py:348-358` (Alternative `compare_prompt`), `499-527` (Factor `compare_prompt` + validators), `src/utils/compare_prompt.py:1` (`normalize_compare_prompt`, max 280), `src/alembic/versions/w4x5y6z7a8b9_add_compare_prompt.py:1`, `src/alembic/versions/x5y6z7a8b9c0_compare_prompt_jobs.py:1`, `src/db/models/compare_prompt_jobs.py:1` (ComparePromptJob queued/in_progress), `src/db/models/bootstrap.py:22` (register job)
- Config/default prompts: `src/config/config_settings.py:56-63` (`AI_REWRITE_OPTION_PROMPT / FACTOR_PROMPT`, VERSION 0.7.73), `src/utils/ai/prompts.py:8` (import normalize), `386-445` (`option_rewrite_messages`, `factor_rewrite_messages`, `parse_compare_prompt`)
- Queue/watcher: `src/utils/ai/reword_worker.py:1` (`process_next_reword_job`, `generate_*_prompt_sync`), `src/powerchoice_watcher.py:55` (WATCHER_PROCESS_REWORD_TAG) & `92-98` (reword branch)
- APIs: `src/api/app_customer_project_content_management.py:6` (imports), `144-154`/`238-248` (forms with `compare_prompt`), `194-205`/`310-323` (update allowlist), `382-470` (per-item generate, gating msg `There is no provider…`), `src/api/app_customer_project_management.py:761-930` (bulk generate/clear/status, only blanks, sequential LLM, toast message `Auto generate or refine questions has been done.`)
- Compare consumption: `src/utils/vote_sort_session.py:77-95` (`serialize_item/criterion` expose `compare_prompt`, option title prefers cp), `src/utils/ai/worker.py:52-68` (`_item_map` prefers cp for options), `285-315` (factor question prefers `compare_prompt`)
- Frontend: `client/utils/comparePrompt.ts:1` (`COMPARE_PROMPT_MAX_LEN`, `trimmedComparePrompt`, `optionCompareQuestion` prefers cp, `optionDisplayTitle`), `client/types/api.ts:253/263` (`compare_prompt` fields), `client/composables/useProjectsApi.ts:124-230` (generate/clear/status), `client/pages/projects/[id]/edit.vue:216-260` (Concise wording bulk card with disabled hover), `369-410` (option row compare_prompt + Generate/Clear), `482-517` (factor row), `754-820` (provider gating, `loadProviderStatus`, `generateConcisePrompts/clear`, per-row), `1375-1405` (`loadContentRows` map `compare_prompt`), `1506-1599` (`sync*` persist cp), `1789` (onMounted loadProviderStatus), `client/components/CompareQuestionHeader.vue:69-94` (uses updated `optionCompareQuestion`)

Verification: alembic migrations applied, `pytest src/tests/test_ai_agents.py src/tests/test_manage_project_content.py` 36 passed, `GET /session/docs.json` lists 5 new paths, `npm run build` + `update_static_client.sh` succeeded (22 routes prerendered), openapi_sessions.json regenerated.
[comment: build completed 2026-08-21T19:51:16.116Z | via executor-opencode | entryId e-20260821-0001 | artifacts: ./automatic-llm-wording-of-option-and-fact-2qt9i4/2026-08-21T19-23-24-968Z-build-zttx3c.request.md, ./automatic-llm-wording-of-option-and-fact-2qt9i4/2026-08-21T19-23-24-968Z-build-zttx3c.response.md, ./automatic-llm-wording-of-option-and-fact-2qt9i4/2026-08-21T19-23-24-968Z-build-zttx3c.trace.log, ./automatic-llm-wording-of-option-and-fact-2qt9i4/2026-08-21T19-23-24-968Z-build-zttx3c.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T19:51:16.117Z build completed (e-20260821-0001)
- 2026-08-21T19:22:26.061Z plan completed (e-20260821-0001)
- 2026-08-21T02:09:39.274Z expand completed (e-20260821-0001)
- 2026-08-20T19:37:17.700Z created (source: user)
