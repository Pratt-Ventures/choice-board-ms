# AI Participants — Configuration, Prompts, and Watcher Queuing

## Overview

AI participants are synthetic voters that can cast pairwise rankings on the same
sort-groups human participants see. They are **system-level** (not end-user
editable), gated by `ACTIVATE_AI_AGENTS`, and produce a separate **Agents**
baseline that is excluded from human counts in the project report but shown as
`ai_baseline` for comparison. AI work is queued and executed by the background
watcher process rather than the request thread.

```
Browser / API  ->  CustomerProject (include_ai_agents, ai_voter_models)
              ->  AiAgentJob  (queue per model_key)
              ->  powerchoice_watcher.py --poll--> process_next_ai_job()
              ->  ProjectVoteParticipant (source=ai, participant_key=ai:..., display_name="AI AGENT: ...")
              ->  ProjectVoteGroupResult / pairings / rank_order
              ->  build_report_with_ai_baseline() splits human vs ai for the UI
```

---

## Configuration — system level, not end-user editable

All knobs live in **`src/config/config_settings.py`** (`GlobalSettings`) and are
read via `pvf.bindings.pvf_invocation.runtime_settings()` (startup YAML
`ACTIVATE_AI_AGENTS` + `.env`). End users cannot edit prompts; admins configure
providers at the customer level (`/ws/core/customer-ai-settings`) which is
encrypted (`enc:v1:`) and never echoed to the browser context.

| Setting | Env | Default | Notes |
|---|---|---|---|
| `ACTIVATE_AI_AGENTS` | startup YAML (`src/pvf_app_startup.yaml`) | `False` | Gate; pvf ClassVar |
| `AI_SERVICE` | `AI_SERVICE` | `opencode_go` | `opencode_go | opencode_zen | openrouter` |
| `AI_API_KEY` | `AI_API_KEY` | `""` | System fallback; customer key preferred |
| `AI_MODEL` | `AI_MODEL` | `glm-5.2` | Default model key |
| `AI_MAX_CONCURRENT_PROJECTS` | `AI_MAX_CONCURRENT_PROJECTS` | `2` | Job claim concurrency |
| `AI_MAX_PAIRS_PER_PROJECT` | `AI_MAX_PAIRS_PER_PROJECT` | `500` | Per-project pair cap |
| `AI_PAIRS_PER_TICK` | `AI_PAIRS_PER_TICK` | `20` | Pairs processed per watcher tick |
| `AI_SKIP_RATE_ABORT` | `AI_SKIP_RATE_ABORT` | `0.25` | Abort group if skip-rate >= threshold |
| `AI_TIE_SKIP_QUOTA_RATIO` | `AI_TIE_SKIP_QUOTA_RATIO` | `0.2` | Combined TIE+SKIP quota = `ceil(group_size * ratio)` |
| `AI_TIE_SKIP_QUOTA_MIN` | `AI_TIE_SKIP_QUOTA_MIN` | `1` | Minimum quota, even for small groups |
| `AI_PROMPT_SINGLE_OPTION_TEMPLATE` | `AI_PROMPT_SINGLE_OPTION_TEMPLATE` | see below | System prompt for overall option comparison |
| `AI_PROMPT_FACTOR_OPTION_TEMPLATE` | `AI_PROMPT_FACTOR_OPTION_TEMPLATE` | see below | Prompt when a specific factor/criterion scopes the option comparison |
| `AI_PROMPT_FACTOR_RANKING_TEMPLATE` | `AI_PROMPT_FACTOR_RANKING_TEMPLATE` | see below | Prompt for factor-importance ranking (criteria group) |
| `AI_PROMPT_CHOICE_TIE_SKIP` | `AI_PROMPT_CHOICE_TIE_SKIP` | `Respond with 1, 2, TIE or SKIP. Use TIE and SKIP sparingly.` | Choice line while quota remains |
| `AI_PROMPT_CHOICE_STRICT` | `AI_PROMPT_CHOICE_STRICT` | `Respond with Option 1 or Option 2.` | Choice line once quota is reached |

Resolution order for every setting: explicit arg → `runtime_settings()` →
`src/config/config_settings.py` (`app_settings`) → `src/pvf/config/pvf_config_settings.py`
(`pvf_settings`). Helpers in **`src/utils/ai/config.py:16`** (`_runtime_settings`,
`_app_settings`, `_pvf_settings`, `_setting`) implement this.

Customer-level overrides (encrypted at rest) are resolved by
**`src/utils/ai/config.py:183`** `resolve_llm_credentials()` which prefers
`customer.ai_provider` + `decrypted_ai_api_key()` (`src/pvf/utils/field_encryption.py`)
over the system provider, and normalizes `model_key` (`__default__`).

Preference locations:
- Framework settings base: `src/pvf/config/pvf_config_settings.py:106` / `294`
- App settings + prompt templates: `src/config/config_settings.py:11`
- AI config helpers: `src/utils/ai/config.py:1`
- Identity / display names: `src/utils/ai/identity.py:7`

---

## Prompt templates — configurable, format-string based

Templates are Python `str.format` templates stored in `config_settings.py` and read
by **`src/utils/ai/prompts.py:72`** `_get_templates()`. They are **not** exposed
to project owners. Editing requires a redeploy (or env override); `format`
failures are caught and logged via `utils_show`, falling back to built-in
defaults (`_DEFAULT_SINGLE`, `_DEFAULT_FACTOR_OPTION`, `_DEFAULT_FACTOR_RANKING`).

### Ambient parameters (explicit)

*Single option comparison* (`AI_PROMPT_SINGLE_OPTION_TEMPLATE`):
`{project_title}` `{project_description}` `{option1_title}` `{option1_description}`
`{option2_title}` `{option2_description}` `{choice_1}` `{choice_2}`

*Factor-specific option comparison* (`AI_PROMPT_FACTOR_OPTION_TEMPLATE`):
`{project_title}` `{project_description}` `{factor_title}` `{factor_description}`
`{factor_question}` `{option1_title}` `{option1_description}` `{option2_title}`
`{option2_description}` `{choice_1}` `{choice_2}`

*Factor-importance ranking* (`AI_PROMPT_FACTOR_RANKING_TEMPLATE`):
`{project_title}` `{project_description}` `{factor1_title}` `{factor1_question}`
`{factor1_description}` `{factor2_title}` `{factor2_question}` `{factor2_description}`
`{choice_1}` `{choice_2}`

All templates receive `{choice_1}` and `{choice_2}` rendered as `1. {choice_1}` / `2. {choice_2}` on successive lines and swapped per quota state (see next
section). Legacy `{choice_line}` is still tolerated via fallback (deprecated, logs once via `utils_show`). `comparison_question` is normalized by
`src/utils/comparison_question.py:4`. Placeholders are documented in
`src/config/config_settings.py` comments and in
`src/utils/ai/prompts.py:124` `pairwise_messages` docstring.

### Default prompts

**Single factor / overall option (no factor):**
```
You are an agent being asked for a ranking opinion between the following two options. Choose the best overall answer based on information provided and your prior knowledge.

Project Context: {project_title}
{project_description}

Option 1: {option1_title}
{option1_description}

Option 2: {option2_title}
{option2_description}

1. {choice_1}
2. {choice_2}
```

**Multiple factors — probe of option with specific factor:**
```
You are an agent being asked for a ranking opinion between the following two options. This ranking is for a specific factor or perspective. Make a selection based on the factor and specific question, keeping the factor in context, based on your overall knowledge.

Project Context: {project_title}
{project_description}

Current Factor: {factor_title}
{factor_description}

{factor_question}

Option 1: {option1_title}
{option1_description}

Option 2: {option2_title}
{option2_description}

1. {choice_1}
2. {choice_2}
```

**Factor-importance ranking (criteria group):**
```
You are an agent being asked for a ranking the importance of two factors being used in a weighted selection ranking process. Choose the more important factor based on information provided and your prior knowledge.

Project Context: {project_title}
{project_description}

Factor 1: {factor1_title}
Factor 1 Question Format: {factor1_question}
Factor 1 description: {factor1_description}

Factor 2: {factor2_title}
Factor 2 Question Format: {factor2_question}
Factor 2 description: {factor2_description}

1. {choice_1}
2. {choice_2}
```

Choice lines (rendered as `1. {choice_1}` then `2. {choice_2}` on successive lines, single `\n`, no blank line):
- While quota remains: `1. Respond with 1, 2, TIE or SKIP. Use TIE and SKIP sparingly.` / `2. Respond with 1, 2, TIE or SKIP. Use TIE and SKIP sparingly.`
- Once quota reached: `1. Respond with Option 1 or Option 2.` / `2. Respond with Option 1 or Option 2.`
- Legacy custom templates still using `{choice_line}` continue to work (deprecated fallback) — migrate to `1. {choice_1}\n2. {choice_2}`.

System messages are intentionally minimal ("Reply with exactly one token … Never
explain.") so the templated user content carries the domain context. Error
handling in `_safe_format` (`src/utils/ai/prompts.py:93`) logs `ai prompt format
failed; using fallback` via `utils_show` and never crashes the watcher tick.

Parsing (`src/utils/ai/prompts.py:280` `parse_pairwise_choice`) accepts
`1` / `2` / `Option 1` / `Option 2` / `LEFT` / `RIGHT` / `TIE` / `SKIP` (and
synonyms `EQUAL/DRAW`, `UNSURE/PASS/ABSTAIN`, `A/B`) and maps `1→left (Option 1)`,
`2→right (Option 2)`. Legacy `LEFT/RIGHT` is kept for backward compatibility.

---

## Randomization vs. 1/2 labeling

Options (or factors in a criteria group) are randomized per pairing but always
presented as **Option 1 then Option 2**. The response token `1` means "the item
shown as Option 1" and `2` means "Option 2". Stability of results is preserved
by mapping the randomized presentation back to stable IDs.

- Scheduler picks canonical pair `nxt = (a,b)` via `src/utils/pair_scheduler.py:261`
  `select_next_pair`.
- `choose_orientation(a,b, history, seed_parts)` (`pair_scheduler.py:301`)
  randomizes orientation deterministically (left-presentation balance + seeded
  50/50) → `(left, right)` where `left` is shown as **Option 1**.
- `pairwise_messages` labels `left` as Option 1 and `right` as Option 2.
- `parse_pairwise_choice` maps `left(1) / right(2)` → `winner_id` =
  `left` or `right`; the stored `PairAnswer` (`pair_scheduler.py:14`) retains
  both canonical `(item_a,item_b)` and presentation `(presented_left_id,
  presented_right_id)`, so `answer_to_pairing` / `pairings_to_answers` round-trip
  without losing orientation. The worker uses this to build `pairings` with
  `winner_id/loser_id` + `presented_left_id/presented_right_id` for the
  BT/Copeland ranking.

---

## TIE / SKIP quota (combined, per group)

- Quota per **group** (one sort group in `ProjectVoteGroupResult`) over the
  answers accumulated so far in that group (`SchedulerState.answers`).
- Size = `len(item_ids_initial)` (number of items in the group).
- Quota = `max(AI_TIE_SKIP_QUOTA_MIN, ceil(group_size * AI_TIE_SKIP_QUOTA_RATIO))`.
  Default ratio `0.2` with min `1` → a 6-item group allows 2 TIE/SKIP, a 2-item
  group allows 1.
- Implementation: `src/utils/ai/prompts.py:9` `ai_vote_threshold(group_size)` /
  `tie_skip_quota` + `combined_abstentions` + `quota_reached`; the worker
  (`src/utils/ai/worker.py:260`) recomputes `combined = combined_abstentions(state.answers)`
  before each LLM call and sets `allow_skip_tie = combined < threshold`. When
  `threshold==0` (degenerate), abstention is never allowed.
- Prompt switch: `allow_skip_tie=True` → choice line with `TIE or SKIP`;
  `False` → strict `Respond with Option 1 or Option 2.` (both `prompts.py` and
  the system wrapper change). If the model still returns `TIE`/`SKIP` after the
  quota is exhausted, it is recorded as `tie`/`skipped` and increments the
  counter (logged via `utils_show`); the next iteration will remain strict, so
  additional abstentions are rate-limited but not silently coerced to a winner.
  Treat this as "quota is a prompt gate, not a hard reject" — SKIP is
  **not** valid once the prompt has switched, and callers should expect rate
  limiting rather than re-queueing.
- Global skip guard: `AI_SKIP_RATE_ABORT` (`src/utils/ai/config.py:122`) aborts
  a job if overall `skip_count/pair_count` ≥ `0.25` and all answers are skips
  (see `worker.py:191`, `worker.py:356`).

---

## Queuing and watcher flow

### Enqueue

- UI toggles `CustomerProject.include_ai_agents` + `ai_voter_models` (deduped via
  `unique_voter_models`, default key `__default__`) in
  `src/tests/test_ai_agents.py:258` / `src/api` customer-project create/update.
- User action `POST /ws/project-votes/ai-baseline-run` (gated by
  `ai_features_enabled` and `include_ai_agents`) enqueues one
  `AiAgentJob` per distinct `model_key` via `AiAgentJob.enqueue_baseline(...)`
  (`src/db/models/ai_agent_jobs.py`). Dedupe prevents double-queue.

### Storage

- `AiAgentJob` row: `customer_id`, `project_id`, `model_key`, `status`
  (`queued→in_progress→complete/failed`), `participant_id`, `pair_count`,
  `skip_count`, `group_count`, `error_summary`. Claim is via
  `AiAgentJob.claim_next(session, max_concurrent)` (ordered by `modify_date`
  for round-robin fairness; see `src/tests/test_ai_agents.py:602`).

### Watcher process

- Entrypoint: `src/powerchoice_watcher.py:1`. Separate OS process (supervisord
  in prod; **not** `start-server.sh`). It loads startup config
  (`src/pvf/bindings/pvf_startup_config.py`) and registers hooks via
  `src/app_shell.py:register_app_hooks`.
- Loop: `process_watch_loop` (`powerchoice_watcher.py:57`) cycles
  `WATCHER_PROCESS_MODULE_LIST` with exponential back-off
  (`WATCHER_SHORTER_BUSY_POLL_SLEEP`, `WATCHER_LONGER_IDLE_INCREASING_POLL_SLEEP`,
  `WATCHER_POLL_EXPONENTIAL_FACTOR`, `WATCHER_POLL_MAXIMUM_SLEEP_TIME`).
- On the AI tag (`settings.WATCHER_PROCESS_AI_AGENTS_TAG`), each iteration
  calls `process_next_ai_job(session)` (`src/utils/ai/worker.py:105`). If it
  returns `True`, idle counter resets and the loopBusy-waits; else it backs off.
- `process_next_ai_job` claims one job (`ai_max_concurrent_projects`) and runs
  `_run_job`. Retries on `AiProviderError(retryable=True)` by returning `True`
  without advancing counts (`worker.py:313`). Non-retryable errors become
  `skipped` responses.

### Per-job execution (`_run_job`)

1. Load `CustomerProject` + alternatives/factors (`CustomerProjectAlternatives`,
   `CustomerProjectFactors`) and resolve LLM credentials (`resolve_llm_credentials`).
2. Get-or-create AI participant (`ProjectVoteParticipant.get_or_create_ai_participant`,
   `source=ai`, `participant_key=ai:default` etc. via `src/utils/ai/identity.py`).
3. Pick next sort group via `pick_next_sort_group` (`src/utils/vote_sort_session.py`).
4. If no group / session complete → mark complete or fail on skip-rate.
5. Issue `ProjectVoteGroupResult.issue_group_result` and build `SchedulerState`
   from `prior_answers` + `answers`.
6. **Tick loop** (up to `ai_pairs_per_tick`, `ai_max_pairs_per_project` cap):
   `select_next_pair` → `choose_orientation` (randomize) → `pairwise_messages`
   (quota-aware) → `chat_text_sync` (provider: `src/utils/ai/provider.py`) →
   `parse_pairwise_choice` → `PairAnswer` (keep stable + presented IDs) →
   `save_group_pairings`. Repeat until `select_next_pair` is `None`.
7. Build final order `rank_order_from_answers` → `create_group_result` →
   mark `group_count` and return `True` to let the watcher re-claim the same job
   for its next group. When no groups remain, job goes `complete`.

Report partitioning: `src/utils/ai/identity.py:61` `partition_vote_data` and
`src/utils/ai/report.py:build_report_with_ai_baseline` keep AI participants
out of `unique_participants` and emit `ai_baseline` (`available`, `option_ranking`,
`factor_rankings`) for the UI. Providers are verified by
`src/pvf/utils/llm_client.py` (`verify_llm_provider`).

---

## Files

- `src/config/config_settings.py:11` — app settings + prompt templates + quota knobs
- `src/utils/ai/config.py:1` — `ai_features_enabled`, credential resolution
- `src/utils/ai/prompts.py:1` — templates, `ai_vote_threshold`, `combined_abstentions`, `pairwise_messages`, `parse_pairwise_choice`
- `src/utils/ai/worker.py:1` — `process_next_ai_job`, `_run_job`, scheduler integration, randomization + quota wiring
- `src/utils/ai/provider.py` — `chat_text_sync` / `chat_json_sync` (opencode_go / openrouter)
- `src/utils/ai/identity.py:7` — AI keys/display names + report partitioning
- `src/utils/pair_scheduler.py:14` — `PairAnswer`, `SchedulerState`, `select_next_pair`, `choose_orientation`, `rank_order_from_answers`
- `src/utils/comparison_question.py:4` — question normalization
- `src/db/models/ai_agent_jobs.py` — job queue model
- `src/powerchoice_watcher.py:57` — `process_watch_loop` + AI tag polling
- `src/pvf/utils/callback_delivery.py` — sibling watcher machinery (API callbacks)
