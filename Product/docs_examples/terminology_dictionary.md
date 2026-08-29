# Power Choice Pro — terminology dictionary

Canonical **user-facing** language for the product. Use this for UI copy, empty states, emails, and OpenAPI/field *descriptions*.

**Scope**

- Apply consistently in the SPA and human-readable API docs.
- Do **not** rename database columns, JSON field names, path segments, or enums unless a change is local and very low risk.
- Internal code may keep `alternative`, `criteria`, `observation`, `probe`, `vote` as implementation vocabulary.

**Related product nouns (out of this glossary)**

- **Application** / API keys — toolkit integrations, not decision projects.
- **Workspace** — company/account context (signup), not a project.

---

## Principles

1. One primary noun per concept in user-facing copy.
2. Everyday English first; avoid MCDA jargon in the main UI.
3. Verbs for actions, nouns for things: *compare options using factors*.
4. Brand-safe: “choice” is product flavor (Power Choice), not the name of an option or mode.
5. Top-level work unit: **Project**. Primary action: **Compare** / **comparison**.

---

## Canonical terms

### 1. Container & framing

| Role | Canonical | Notes |
|------|-----------|--------|
| Owned work unit | **Project** | Nav, lists, CRUD, routes |
| What it’s about | **decision** | Framing only (“Structure the decision”) — not a second entity |
| Account context | **Workspace** | Company/signup only |

### 2. Project mode

| Role | Canonical | Internal |
|------|-----------|----------|
| Single winner | **Pick one** | `project_exclusive_mode = true` |
| Full ordering | **Rank all** | `project_exclusive_mode = false` |
| Edit labels | **Choose one winner** / **Rank all options** | OK long form on edit |

Avoid in UI: Choice, Prioritization, exclusive, selection-mode.

### 3. Things being compared

| Role | Canonical | Internal (keep) |
|------|-----------|-----------------|
| Entity | **Option** | `alternative_*`, `CustomerProjectAlternatives` |
| Count / empty states | **options** | — |

Avoid in UI: alternative, choice (as the item), item.

### 4. Evaluation dimensions

| Role | Canonical | Internal (keep) |
|------|-----------|-----------------|
| Entity | **Factor** | `factor_*` |
| Section | **Factors** | — |
| No separate factors | **Overall only** | Synthetic factor title: **Overall** |
| Multi | **Multiple factors** | — |
| Templates | **Template** | Project / options / factors scopes; internal: `CustomerFactorTemplates`, `project_templates.yml` |

Avoid in UI: criteria, criterion, rubric (except rare help metaphor).

Observation type `criteria` means factor-vs-factor comparisons — never say “criteria” to users.

### 5. Comparing (giving input)

| Role | Canonical | Internal (keep) |
|------|-----------|-----------------|
| Verb / CTA | **Compare** / **Start comparing** | vote APIs, probe routes |
| One unit | **comparison** | `observation`, probe |
| Progress | **comparisons** | — |
| Finish | **Mark complete** | — |
| Locked | **Input closed** / **Comparisons locked** | `disabled` |
| Status collecting | **Collecting input** | — |
| Live compare meter | **Current ranking confidence** | This participant’s option + factor ranking quality so far (None → Low → Moderate → Fair → Good → Strong). Display-only; not Results **Confidence**, **Agreement**, **Repeatability**, or **Stability** |

Answer controls (keep): **About equal**, **Not sure**, **Skip** / **Show another**, **Undo**, **Pause**.

**Prompt patterns**

- Option under a factor: “Which option is better for **{factor}**?”
- Factor importance: “Which factor matters more?”
- Overall: “Which option is better overall?”

Avoid in UI as primary terms: vote/voting, probe, observation, question (advanced settings may say “question group”).

### 6. People

| Role | Canonical |
|------|-----------|
| Someone who compared | **Participant** |
| Share recipient on gate | **you** / guest copy |

Avoid as default: voter (optional secondary).

### 7. Outcomes

| Role | Canonical | Notes |
|------|-----------|--------|
| Owner in-app page | **Results** | Live rankings & insight |
| Shared full access | **Full results** or **Report** | Share type; pick one label in UI and stick — prefer **Full results** for share picker, **Report** OK for page title of shared artifact |
| Pick-one headline | **Recommended option** | not “Recommended choice” |
| Rank-all headline | **Top option** / **Leading option** | “Top priority” secondary OK |
| Ordered list | **Ranking** / **Overall ranking** | — |
| Strength | **Score** | — |
| Margin | **Lead** | — |
| Readiness metrics | **Agreement**, **Repeatability** | keep separate; do not collapse to one Confidence number. **Stability** removed from primary chips to avoid showing the same posterior number twice (for **Rank all** both derive from `same_winner`). Legacy Confidence is advanced/footnote only |
| Group alignment | **Agreement** | prefer over coherence/dispersion for novices; advanced may keep Dispersion |
| Factor columns | **Importance**, **Differentiation**, **Decision leverage** | not “ratio-scale importance” |
| Weighting views | **All factors equally** / **Weighted by what matters most** | keep |
| Factor insight | **What matters most** | — |
| Per-factor | **Best option by factor** | — |
| State | **Preliminary results** / **Final results** | — |

Rule: *Results* = place you look; *Report* / *Full results* = shareable full-access artifact.

### 8. Sharing

| Role | Canonical | Internal `ShareType` |
|------|-----------|----------------------|
| Feature | **Sharing** / **Share link** | — |
| CTA | **Invite people** | — |
| Input only | **Compare Only** | `vote` |
| Input + personal outcome | **Compare and See Only Your Results** | `vote_view` |
| Group outcome | **See Full Results** | `report` |
| Activity | **Sessions**, **Opens**, **Access log** | Hits → Opens |

Avoid in UI: magic token (support/advanced OK), Vote & view, Hits.

### 9. Status chips (projects)

| Canonical | Meaning |
|-----------|---------|
| **Ready** | Enough structure to collect input (≥2 options) |
| **Collecting input** | Comparisons open |
| **Input closed** | Locked; no new comparisons |
| **Needs attention** | Setup incomplete |
| **Results available** | Strong completion / ready to review |

---

## Phrase bank

```
Projects
New project · Edit project · Project name
Pick one · Rank all
Options · Add option · Option title
Factors · Add factor · Factor title
Overall only · Multiple factors · Factor template
Start comparing · Continue comparing · Comparisons locked
One clear comparison at a time
Which option is better for {factor}?
Which factor matters more?
About equal · Not sure · Undo · Mark complete
Participants · N comparisons
Results · Preliminary results · Final results
Recommended option · Overall ranking · What matters most
Agreement · Repeatability
Importance · Differentiation · Decision leverage
Invite people · Share link
Compare Only · Compare and See Only Your Results · See Full Results
```

---

## Deprecations (user-facing)

| Stop saying | Say instead |
|-------------|-------------|
| alternative | option |
| choice (item or mode badge) | option / Pick one |
| prioritization (mode badge) | Rank all |
| criteria / criterion | factor |
| rubric (default copy) | factors |
| vote / voting (primary UX) | compare / comparison |
| Begin voting | Start comparing |
| Overall Assessment (labels) | Overall / Overall only |
| Decision factors (default tab) | Factors |
| Recommended choice | Recommended option |
| Hits | Opens |
| Vote & view | Compare and See Only Your Results |
| probe / observation (main UX) | comparison |
| Collecting responses | Collecting input |
| Voting closed | Input closed |

---

## Internal → UI mapping

| Internal / API | User-facing |
|----------------|-------------|
| `project` | Project |
| `alternative` | Option |
| `factor` + observation type `criteria` | Factor |
| `observation` / probe | comparison |
| `project_exclusive_mode` true/false | Pick one / Rank all |
| `report` (engine payload) | powers Results + See Full Results share |
| `ShareType.vote` | Compare Only |
| `ShareType.vote_view` | Compare and See Only Your Results |
| `ShareType.report` | See Full Results |
| `disabled` (project) | Input closed / Comparisons locked |
| participant | Participant |

---

## API documentation policy

- Update OpenAPI / Pydantic `description=` strings to use this dictionary (e.g. “option (API field: alternative_*)”).
- Keep JSON property names and path segments stable.
- New endpoints may introduce friendlier names only when they do not break existing clients.

---

## Adoption checklist

- [x] This dictionary file
- [x] UI string pass (projects, probe, results, shares, login/signup, settings)
- [x] Share type labels (enums unchanged; UI maps vote → Compare Only, vote_view → Compare and See Only Your Results, report → See Full Results)
- [x] API field descriptions (not renames)
- [ ] Optional later: DB/API identifier migration (separate, high risk)
