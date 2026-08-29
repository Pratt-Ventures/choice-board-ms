# Change wording on share view

## Short Description
### user
The caption near the top of the ranking on the self-view after comparisons says 'Decision factors contribute according to importance ranked factors; Rank percentage is first vs last likelihood.'

This is slightly redundant, change to: Decision factors contribute according to their ranked importance; Rank percentage is first vs last likelihood.'

Make the same change on the full report page when 'Weighted by what matters most' is selected.
[comment: created 2026-08-20T18:52:11.130Z | id change-wording-on-share-view-3pvokj]

## Expanded Description
### agent
This change is a small copy edit that replaces the slightly redundant caption text "Decision factors contribute according to importance ranked factors; Rank percentage is first vs last likelihood." with "Decision factors contribute according to their ranked importance; Rank percentage is first vs last likelihood." across two surfaces: the self-view ranking shown after comparisons are complete, and the full report page when the "Weighted by what matters most" option is selected. The edit affects only the displayed caption string, not any underlying logic, data, or ranking calculations, and is intended to reduce phrasing redundancy while keeping the meaning identical. Because both surfaces presumably share or duplicate the caption string, the implementation should locate the exact string and update every occurrence, verifying the surrounding punctuation and sentence case stay intact.

- Scope: Locate the caption string in both the post-comparison self-view and the full report page; replace the text verbatim; no functional or styling changes.
- Key consideration: Confirm whether the caption is a shared/translated string constant or duplicated in each view so both spots are covered and none is missed.
- Key consideration: Check that this exact wording is not also used elsewhere (e.g., other views or exports) where an unintended change would occur.
- Key consideration: Preserve the trailing period and the two-clause semicolon structure in the new string.
- Open question: Should the caption differ when the report page uses a weighting mode other than "Weighted by what matters most," or is the string unconditional there?
- Open question: Is the caption covered by any existing tests or snapshot assertions that need updating to match the new text?
- Verification: After editing, render both surfaces to confirm the new wording appears correctly and no wrapping/layout issues result.
[comment: expand completed 2026-08-20T18:52:40.523Z | via executor-opencode | entryId e-20260820-0001 | artifacts: ./change-wording-on-share-view-3pvokj/2026-08-20T18-52-11-176Z-expand-5ufi8i.request.md, ./change-wording-on-share-view-3pvokj/2026-08-20T18-52-11-176Z-expand-5ufi8i.response.md, ./change-wording-on-share-view-3pvokj/2026-08-20T18-52-11-176Z-expand-5ufi8i.trace.log, ./change-wording-on-share-view-3pvokj/2026-08-20T18-52-11-176Z-expand-5ufi8i.result.json]


## Plan

## Build Summary
### agent
The two real surfaces are in `client/components/ShareVoteSession.vue:71` and `client/pages/projects/[id]/results.vue` around line 623-625. Let me examine both.

Now I understand the two surfaces.

1. `ShareVoteSession.vue:71` - the self-view caption with the exact redundant text.
2. `results.vue:622-627` - the report page. The "Weighted by what matters most" corresponds to `resultWeighting.value === 'adjusted'` (line 625). Note this line has a slightly different wording: "Decision factors contribute according to importance from ranked factor groups." 

Wait, the brief says the report page when 'Weighted by what matters most' is selected has the redundant text "Decision factors contribute according to importance ranked factors; Rank percentage is first vs last likelihood." But line 625 reads "Decision factors contribute according to importance from ranked factor groups." which is not the same text. Let me check what "Weighted by what matters most" maps to.

Let me look for the weighting options.

So line 582 maps "Weighted by what matters most" → `value: 'adjusted'`. The report page caption for "Weighted by what matters most" is line 625: "Decision factors contribute according to importance from ranked factor groups."

The brief says to change the report page caption to "Decision factors contribute according to their ranked importance; Rank percentage is first vs last likelihood." 

So the current line 625 text "Decision factors contribute according to importance from ranked factor groups." should be replaced with "Decision factors contribute according to their ranked importance." followed by the rankPct.

Let me apply both changes.

For ShareVoteSession.vue:71, replace the exact string.

For results.vue:625, replace the caption part.

Let me make the edits.

Now let me check whether this exact string appears anywhere else that could be affected (e.g., exports, PDF generation). From the earlier grep, the only actual source occurrences were those two. Let me double check the docs_examples/html_prototype is a mock-up (not real) and the results.vue line 1137 in the prototype uses different text — those are prototypes, not served code.

Let me verify the `static_client/` needs rebuilding per AGENTS.md (any change under `client/` requires rebuild). Let me rebuild the static client.

The build succeeded. Now let me check CHANGELOG.md to see if a changelog note is warranted.

There's no CHANGELOG.md in the repo (glob found none at root; let me confirm). Let me check for CHANGELOG elsewhere.

No CHANGELOG file exists, so no changelog note. The build succeeded but I notice `static_client/` is gitignored (per AGENTS.md), so no changes to stage there. 

Now I'll stage only the files related to this work: the two Vue source files. I'll exclude the graphify-out, todo/ storage files, and other unrelated dirty files per the instructions (do not commit unrelated dirty files).

The relevant changes are:
- `client/components/ShareVoteSession.vue`
- `client/pages/projects/[id]/results.vue`

Let me check whether `static_client/` shows as modified (it should be gitignored).

static_client is gitignored as expected. Now let me verify the two diffs and stage only those two files.

The diffs are clean and exactly as intended. Let me commit only these two files.

Committed successfully. Let me confirm the worktree is clean of the staged files (the unrelated dirty files remain untouched, which is correct per instructions).

Build complete.

## Build Summary

Changed the decision-factor caption wording from "Decision factors contribute according to importance ranked factors; Rank percentage is first vs last likelihood." to "Decision factors contribute according to their ranked importance; Rank percentage is first vs last likelihood." across both surfaces.

**Touch points:**
- `client/components/ShareVoteSession.vue:71` — self-view "Your ranking" caption after comparisons (exact redundant string replaced verbatim).
- `client/pages/projects/[id]/results.vue:625` — full report page caption for the "Weighted by what matters most" (`adjusted`) weighting mode; the pre-computed `rankPct` second clause (`Rank percentage is first vs last likelihood.`) is unchanged, so the new two-clause semicolon structure is preserved.

**Verification:**
- Confirmed the two strings are not shared constants — the self-view text was a literal, and the report page uses a `resultViewExplanation` computed with the `rankPct` fragment. No other served surface uses the exact wording (the `docs_examples/html_prototype` match is a non-served mock-up; the `todo/` matches are storage, not code).
- Rebuilt the UI via `./scripts/nuxt/update_static_client.sh` — generate succeeded (22 routes prerendered) and copied into gitignored `static_client/`.
- No CHANGELOG.md exists in the repo, so no changelog note was added.

**Commit:** `bd51761` — "Update decision-factor caption wording on share view and report page"
Only the two Vue source files were staged; unrelated dirty files (todo/ storage, graphify-out) were left untouched.
[comment: build completed 2026-08-20T18:56:13.977Z | via executor-opencode | entryId e-20260820-0002 | artifacts: ./change-wording-on-share-view-3pvokj/2026-08-20T18-52-40-714Z-build-pkcpno.request.md, ./change-wording-on-share-view-3pvokj/2026-08-20T18-52-40-714Z-build-pkcpno.response.md, ./change-wording-on-share-view-3pvokj/2026-08-20T18-52-40-714Z-build-pkcpno.trace.log, ./change-wording-on-share-view-3pvokj/2026-08-20T18-52-40-714Z-build-pkcpno.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-20T18:56:13.977Z build completed (e-20260820-0002)
- 2026-08-20T18:52:40.523Z expand completed (e-20260820-0001)
- 2026-08-20T18:52:11.130Z created (source: user)
