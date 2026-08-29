# Submission k of n message on bug/report submission

## Short Description
### user
Only show the message after 1/3 the limit.
Change the text of the brief message after submission to say, 'We limit submissions in a 24 hour period due to our capacity. You have submitted k of n as of now.'
[comment: created 2026-08-19T16:00:39.922Z | id submission-k-of-n-message-on-bug-report-3ab3n5]

## Expanded Description
### agent
I'll look up the current submission-limit copy so the expansion matches the real flow.Checking the current quota copy and when it appears.After a successful bug or idea submission, the snackbar currently always shows “Submission k of n (per day) has been submitted.” Change that brief so it appears only once the user has used more than one-third of the 24-hour cap, and replace the wording with “We limit submissions in a 24 hour period due to our capacity. You have submitted k of n as of now.” Keep the existing hard-limit discard and over-limit warning behavior unless those paths share the same copy helper.

- Scope: `quotaCopy` in `client/components/SubmissionForm.vue` (used by both bug and suggestion submits); gate display on `submitted_in_window` vs `max_per_day`.
- Show the k-of-n line only when `k > n/3` (or `k >= ceil(n/3)`—pick one and apply consistently).
- Below the threshold, keep a generic success message; do not surface quota on every early submit.
- Preserve the discard snackbar (`stored: false`) and the separate daily-limit warning; only change the brief quota line.
- Update any tests that assert the old always-on copy or expect quota on the first submit.
- Open: floor vs ceil for “1/3 the limit,” and whether a rejected over-limit submit should still show the new k-of-n sentence.
[comment: expand completed 2026-08-19T16:01:53.366Z | via executor-opencode | entryId e-20260819-0001 | artifacts: ./submission-k-of-n-message-on-bug-report-3ab3n5/2026-08-19T16-00-40-007Z-expand-m0suw2.request.md, ./submission-k-of-n-message-on-bug-report-3ab3n5/2026-08-19T16-00-40-007Z-expand-m0suw2.response.md, ./submission-k-of-n-message-on-bug-report-3ab3n5/2026-08-19T16-00-40-007Z-expand-m0suw2.trace.log, ./submission-k-of-n-message-on-bug-report-3ab3n5/2026-08-19T16-00-40-007Z-expand-m0suw2.result.json]


## Plan

## Build Summary
### agent
I'll inspect the current quota copy and submission-form flow first.The quota helper and tests already exist — I'll read them next.Quota helper already matches the spec. I'll check git status and whether the UI still needs a rebuild.Implementation looks done in the worktree. I'll verify the version bump, tests, and static-client publish next.Quota tests passed. Rebuilding the published UI next.Static generate succeeded. I'll confirm the new copy is in the bundle, then commit only the related files.**Build complete** — `6769663` Show submission quota snackbar only after one-third of the daily cap

- `client/utils/submissionQuota.ts:1-4` — `quotaCopy` hidden when `k <= n/3`; copy is “We limit submissions in a 24 hour period… k of n as of now.”
- `client/components/SubmissionForm.vue:224-234` — uses helper; generic “Submission received” below threshold; discard (`stored: false`) and over-limit warning unchanged.
- `client/utils/submissionQuota.test.ts:12-41` — threshold + new wording; `node --test` 4/4 pass.
- `src/config/config_settings.py:17` — version `0.7.51`. Static client rebuilt.
[comment: build completed 2026-08-19T16:14:23.698Z | via executor-opencode | entryId e-20260819-0002 | artifacts: ./submission-k-of-n-message-on-bug-report-3ab3n5/2026-08-19T16-08-54-884Z-build-kajte2.request.md, ./submission-k-of-n-message-on-bug-report-3ab3n5/2026-08-19T16-08-54-884Z-build-kajte2.response.md, ./submission-k-of-n-message-on-bug-report-3ab3n5/2026-08-19T16-08-54-884Z-build-kajte2.trace.log, ./submission-k-of-n-message-on-bug-report-3ab3n5/2026-08-19T16-08-54-884Z-build-kajte2.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-19T16:14:23.698Z build completed (e-20260819-0002)
- 2026-08-19T16:01:53.366Z expand completed (e-20260819-0001)
- 2026-08-19T16:00:39.922Z created (source: user)
