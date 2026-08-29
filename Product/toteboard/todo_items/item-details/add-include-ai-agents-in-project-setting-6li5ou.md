# Add 'Include AI Agents' in project settings

## Short Description
### user
The project settings have the option to select one or more agents. 
A separate checkbox (or switch) to the left of the pull down should enable AI agents. If disabled, the pulldown is ignored, but can still be edited. 

Once one or more agents are selected and enable is on, and the settings are saved, the agents can be queud on the results page or other areas in the settings - with repeats ignored.

Implement the above and verify repeat votes by the same model won't happen. The user can later add more models and queue the new (non-duplicative) ones.
[comment: created 2026-08-21T04:21:31.866Z | id add-include-ai-agents-in-project-setting-6li5ou]

## Expanded Description
### agent
Add an “Include AI Agents” control in project settings: a checkbox/switch to the left of the existing multi-agent pulldown. When off, selected agents are ignored at queue time but the pulldown stays editable; when on and saved with one or more agents, those agents can be queued from the results page and other settings surfaces. Queueing must skip models already used so the same agent cannot vote twice, while later adding new models still queues only the non-duplicative ones.

- Scope: settings UI (enable switch + pulldown), persist enable + selected agents, queue from results/settings using saved selection only when enable is on.
- Dedup: ignore repeats of the same model/agent on queue; new selections queue only agents that have not already voted.
- Disabled path: pulldown remains editable; queue paths must not enqueue agents when include is off.
- Verify: enable+save+queue; disable ignores selection; re-queue same models is a no-op; add models later queues only new ones.
- Open: identity for “same model” (agent id vs model name); where prior votes are stored; UX when all selected agents are already queued.
[comment: expand completed 2026-08-21T04:22:49.091Z | via executor-opencode | entryId e-20260821-0001 | artifacts: ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-21-32-021Z-expand-wrr0ce.request.md, ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-21-32-021Z-expand-wrr0ce.response.md, ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-21-32-021Z-expand-wrr0ce.trace.log, ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-21-32-021Z-expand-wrr0ce.result.json]


## Plan
### agent
I'll inspect the codebase for project settings, agent selection, and queue/vote paths so the plan matches existing patterns.The existing agent pulldown and queue paths look like the core of this. I'll read those next.## Plan: Include AI Agents in project settings

Current state: project edit already has a multi-select for `ai_voter_models` (`client/pages/projects/[id]/edit.vue`). Queue is `POST /ws/project-votes/ai-baseline-run`, which uses saved models (or request `models`), then falls back to `__default__`. Dedup is partial: `unique_voter_models` + skip complete AI participants + reuse queued/in-progress jobs. There is **no** include switch; empty selection still queues the default model.

Identity for “same model” already exists: `normalize_model_key` → `participant_key` `ai:{model}` / `ai:default` (`src/utils/ai/identity.py`). Votes live on `ProjectVoteParticipant` (`source=ai`, `ai_model`); jobs on `AiAgentJob.model_key`.

### Implementation steps

1. **Persist `include_ai_agents` (bool, default false)**  
   Alembic after `t1u2v3w4x5y6` on `customerproject` (`nullable=False`, `server_default=false`, then drop server default — same pattern as `private_participation`). Add field on `CustomerProject`, `CustomerProjectForm`, create + update in `src/api/app_customer_project_management.py`. Wire TS types and `useProjectsApi` create/update.

2. **Settings UI**  
   In the AI agents row on project edit, put a `v-switch` (label “Include AI Agents”) **left** of the existing `v-select`. Switch does **not** disable the pulldown. Persist both on save. Stop auto-filling a default model when include is off (keep catalog load). Copy the flag on duplicate.

3. **Queue only when include is on + saved selection**  
   In `ai_baseline_run`: if `include_ai_agents` is false, return without enqueueing (do not fall back to default). If on, use **saved** `project.ai_voter_models` only (ignore request `models`). Empty list → no enqueue, clear error. Apply the same gate on every queue surface (results + project overview “Run AI agents”). Hide/disable those buttons when include is off or no models are saved.

4. **Dedup / no double vote**  
   For each requested model: skip if an AI participant already exists for that `participant_key` **and** is complete, or an active (`queued`/`in_progress`) job exists for that `model_key`. Enqueue only the rest. All skipped → `already_complete=true` (existing snackbar). Adding models later queues only keys that have not voted / are not in-flight. Keep `get_or_create_ai_participant` as the worker safety net.

5. **Verify** (extend `src/tests/test_ai_agents.py`)  
   - include off + models saved → 0 jobs  
   - include on + save + queue → one job/participant per unique model  
   - re-queue same models → no new jobs/participants  
   - add a new model, queue → only the new one  
   - `__default__` / `default` treated as the same voter  

### Clarifying questions

1. Existing projects with non-empty `ai_voter_models`: migrate `include_ai_agents=true`, or leave false (they must flip the switch)?  
2. Include on + empty pulldown: error, or keep today’s default-model fallback?  
3. All selected agents already queued: keep “already finished”, or a distinct “nothing new to queue” message?  
4. Should failed/incomplete agents be re-queued from the button, or only brand-new models?

### Options and trade-offs

| | Option | Trade-off |
|---|---|---|
| A | **Saved selection only when include on** (recommended) | Matches the brief; request `models` cannot bypass settings. Slightly less flexible for ad-hoc runs. |
| B | Keep request `models` override | Faster experiments; can queue models never saved; enable flag is weaker. |
| C | Infer “include” from non-empty `ai_voter_models` | No new column; cannot keep a selection while disabled. |

**Recommend A:** new `include_ai_agents` column, default false, queue from saved list only. Dedup key = normalized `model_key` / `ai:{model}` participant. Default false for existing rows (feature is new). Empty selection does not queue. Incomplete/failed runs may resume; completed votes never run twice.
[comment: plan completed 2026-08-21T04:26:10.317Z | via executor-opencode | entryId e-20260821-0002 | artifacts: ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-22-49-301Z-plan-arnan7.request.md, ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-22-49-301Z-plan-arnan7.response.md, ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-22-49-301Z-plan-arnan7.trace.log, ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-22-49-301Z-plan-arnan7.result.json]


## Build Summary
### agent
I'll inspect project settings, agent selection, and queue/vote paths so the implementation matches existing patterns.I'll read the model, API, queue path, and settings UI next so the new switch and persist fields match existing conventions.I have the queue, persist, and settings paths. Next I’ll add the include switch, gate enqueue on the saved flag, and tighten model dedup.Implementing persistence, settings UI, queue gating, and tests.**Include AI Agents** — switch left of the model pulldown; queue only when on + saved selection; repeats skipped.

**Verified:** `pytest src/tests/test_ai_agents.py src/tests/test_manage_projects.py` — 44 passed. Migration `u2v3w4x5y6z7` applied. OpenAPI sessions regenerated. Static client rebuilt. Version `0.7.62`.

**Nothing to commit** — implementation already in HEAD `6e680d4`; remaining dirty file is unrelated toteboard.

**Touch points**
- `src/alembic/versions/u2v3w4x5y6z7_include_ai_agents.py:19` — `include_ai_agents` bool, default false
- `src/db/models/customer_projects.py:73` — model field
- `src/api/app_customer_project_management.py:122`, `:351`, `:714` — form, create, update
- `src/api/app_project_vote_events.py:843` — include-off / empty / saved-only queue; `:867` complete + active-job skip
- `client/pages/projects/[id]/edit.vue:201` — switch left of pulldown (editable when off)
- `client/pages/projects/[id]/index.vue:49`, `:192` and `results.vue:28`, `:606` — Run AI agents hidden unless include on + models
- `src/tests/test_ai_agents.py:256` — persist, include-off, empty, ignore request models, dedup + new models
[comment: build completed 2026-08-21T04:39:06.804Z | via executor-opencode | entryId e-20260821-0003 | artifacts: ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-26-10-412Z-build-0sc64d.request.md, ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-26-10-412Z-build-0sc64d.response.md, ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-26-10-412Z-build-0sc64d.trace.log, ./add-include-ai-agents-in-project-setting-6li5ou/2026-08-21T04-26-10-412Z-build-0sc64d.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T04:39:06.804Z build completed (e-20260821-0003)
- 2026-08-21T04:26:10.317Z plan completed (e-20260821-0002)
- 2026-08-21T04:22:49.092Z expand completed (e-20260821-0001)
- 2026-08-21T04:21:31.866Z created (source: user)
