# Adjust share security flow type

## Short Description
### user
Share options today include a mode that relies on the original target email specified with the share (whether emailed or not).  
This is actived by :
ENABLE_SHARE_PASSWORD_WITH_RECIPIENT_EMAIL_VERIFIED
And has a similar description in the code.  

This requires the receipient to reenter their email, and it must match, before sending a key via email to the recipient on file (which would match). 
Since another option is behaviorally almost identical, ENABLE_SHARE_PASSWORD_WITH_EMAIL_MATCHING_VERIFIED, we want to make adjustments to the RECIPIENT_EMAIL_VERIFIED version.

When this mode is used, the email prompt in the client should not be shown. Instead, a clera note that it is using the email it was sent to. The present behavior woud still be used for ENABLE_SHARE_PASSWORD_WITH_EMAIL_MATCHING_VERIFIED.

This may require an update on the server to hint the mode, but I believe all the information is there already. The client should be changed accordingly. Advise of server changes, which must occur, if needed, only in the PVF area, so as not to tangle our framework code with application.
We'd like
[comment: created 2026-08-18T11:23:50.225Z | id adjust-share-security-flow-type-176dys]

## Expanded Description
### agent
I'll inspect the share-security flags and client/server flow so the expansion matches the existing code.Differentiate `ENABLE_SHARE_PASSWORD_WITH_RECIPIENT_EMAIL_VERIFIED` from the nearly identical `ENABLE_SHARE_PASSWORD_WITH_EMAIL_MATCHING_VERIFIED` flow: recipient-email-verified should stop asking the visitor to re-enter an email that must match the share-on-file address before the one-time key is sent. In that mode the client hides the email prompt and shows a clear note that the key will use the email the share was sent to / on file; email-matching-verified keeps today’s prompt-and-match behavior. Any server hint belongs only in PVF so framework code stays application-agnostic.

- Scope: client share-access UI for password + recipient-email-verified; do not change email-matching-verified; server changes only if the live payload cannot already distinguish modes.
- Existing signals: `config_client` already exposes both flags; PVF comments already say “Enter Name Only” vs “Enter Name & Email”; `SHARE_SECURITY_NOTE_PASSWORD_WITH_RECIPIENT_EMAIL_VERIFIED` already describes sending the key to the email on file.
- If a mode hint is still missing on the share-access response, add it in PVF (e.g. `share_link_manage` notes / client config), not framework.
- Copy: “email it was sent to” vs “email on file” — shares can exist without an outbound send.
- Open: apply the same UX to non-password `ENABLE_SHARE_RECIPIENT_EMAIL_VERIFIED`? Still collect name only? Reveal or mask the on-file address?
[comment: expand completed 2026-08-18T11:24:48.552Z | via executor-opencode | entryId e-20260818-0001 | artifacts: ./adjust-share-security-flow-type-176dys/2026-08-18T11-23-50-254Z-expand-8gwwvb.request.md, ./adjust-share-security-flow-type-176dys/2026-08-18T11-23-50-254Z-expand-8gwwvb.response.md, ./adjust-share-security-flow-type-176dys/2026-08-18T11-23-50-254Z-expand-8gwwvb.trace.log, ./adjust-share-security-flow-type-176dys/2026-08-18T11-23-50-254Z-expand-8gwwvb.result.json]


## Plan
### agent
I'll inspect the share-security flags and client/server flow so the plan matches the existing code.Checking the graph and tracing both share-security modes in client and PVF.Verifying gate flags, copy, and whether the email field is already hidden.# Plan: Adjust share security flow type

**Finding:** The visitor gate already hides email for `password_with_recipient_email_verified` and `recipient_email_verified`. Denial flags already distinguish those modes from `*_email_matching_verified`. No new server hint is required. Remaining work is lock-in, copy, and first-load polish.

Live contract (`ShareAccessDenied_Base` in `src/pvf/api/share_link_manage.py`):

| Mode | `verification_email_needed` | `verification_original_email_needed` | `verification_email_send_link_mode` |
|---|---|---|---|
| `password_with_recipient_email_verified` / `recipient_email_verified` | false | false | true |
| `password_with_email_matching_verified` / `email_matching_verified` | true | true | true |

`ShareAccessGate.vue` already uses those flags: email field only if `needsEmail`; otherwise hint is “We will send a one-time access code to the email on file.” Server already accepts blank email in recipient modes and always sends the key to `link_info.shared_with_email`. Matching-verified still requires a typed match.

`ENABLE_SHARE_*` / `config_client` are create-picker visibility only. Visitors never receive them. Do not drive the gate from those flags.

**Server:** no new field. PVF *is* the framework (`src/pvf/`). Do not add app-layer mode wrapping in `app_shared_link_ext_access.py`. Any optional string polish stays in `share_link_manage.py`.

## Implementation steps

1. **Do not add a mode-hint field.** Client already has `access_mode` plus the flag combo above. Covered by `test_ext_every_access_mode_gate_flags`.

2. **Keep `ShareAccessGate` flag-driven.** Leave `needsEmail` as-is so matching-verified still prompts. Do not use `access_mode.includes('email')` (that would wrongly show email for recipient modes). Optionally AND-out email when `access_mode` is exactly `recipient_email_verified` or `password_with_recipient_email_verified`.

3. **Keep submitting blank `verification_email`** when the field is hidden (`ShareAccessGate` already does). Do not post a stale typed address — recipient modes reject a non-matching leftover (`The supplied email does not match the share request`).

4. **Visitor copy.** Keep a clear on-file note (already present). Do not reveal the address. Prefer “email on file” / “email this share was created for” over “email it was sent to” (shares can exist with no outbound invite).

5. **First-load alert (main remaining UX bug).** Probe without `authorize_verification_email` returns `Explicit authorization required to send a verification email`, shown as an error. Treat that reason as info/empty in `ShareVoteSession.vue` and `pages/share/report/[token]/index.vue` so the hint + “Send Code to Email” are the instruction. Do not change matching-verified’s “An email address must be supplied” path.

6. **Optional PVF-only string fix** in `share_link_manage.py` 902–904: “set” → “sent”. No framework/app split beyond that file.

7. **Align creator/docs comments** (not visitor behavior): `shares.vue` 480/486 and enum comments in `share_link_tracking.py` 59/65 still say “Enter Name & optional Email”. Change to “Enter Name Only; key goes to the email on file” to match `pvf_config_settings.py` / `config_client.py`.

8. **Tests.** E2E: Email locator count 0 for both recipient modes; 1 for both matching-verified modes (`e2e/tests/share-access-modes.spec.ts` + `e2e/helpers/gate.ts`). Unit: recipient modes accept blank email + `authorize_verification_email: true` and still send to on-file; matching-verified still requires a match.

9. **Out of scope.** Do not change matching-verified, any-email-verified, or picker `ENABLE_SHARE_*` defaults.

## Clarifying questions

1. Copy: keep “email on file”, or use “email this share was created for”? (“Sent to” is wrong when the invite was never emailed.)
2. First-load authorize message: hide it, or show as info under the existing hint?
3. Non-password `recipient_email_verified` already matches this UX — leave it?
4. Still collect name only (current)? Reveal/mask the on-file address? (Recommend: name only, never show the address.)
5. Should recipient modes ignore a typed email entirely instead of matching-if-present?

## Options and recommendation

- **A. Lock-in only** — tests + creator comment alignment. Visitor UI already correct.
- **B. A + first-load alert polish + “set”→“sent”.** Smallest change that matches the requested feel.
- **C. New PVF hint field** (`verification_uses_on_file_email`). Redundant; extra contract.
- **D. Drive gate from `ENABLE_SHARE_*`.** Wrong signal (global picker, not this share’s mode).

**Recommend B.** No new server hint. Keep matching-verified prompt-and-match. Keep both recipient modes name + password (if any) + “Send Code”, with the on-file note and no email field.
[comment: plan completed 2026-08-18T11:30:47.527Z | via executor-opencode | entryId e-20260818-0002 | artifacts: ./adjust-share-security-flow-type-176dys/2026-08-18T11-24-48-637Z-plan-i2l1dg.request.md, ./adjust-share-security-flow-type-176dys/2026-08-18T11-24-48-637Z-plan-i2l1dg.response.md, ./adjust-share-security-flow-type-176dys/2026-08-18T11-24-48-637Z-plan-i2l1dg.trace.log, ./adjust-share-security-flow-type-176dys/2026-08-18T11-24-48-637Z-plan-i2l1dg.result.json]


## Build Summary
### agent
I'll inspect the share-security flags and client/server flow, then implement option B from the plan.Checking the graph and reading the share-security files from the plan.The gate already hides email for recipient modes. I'll read first-load alert handling, tests, and the remaining copy/comment sites.Implementing option B: first-load polish, copy/comment alignment, and tests. No new server hint field.Applying the code changes now.Non-prod skips the mail log. I'll assert the magic-key row and on-file destination instead.E2E passed. Checking git state and committing only the related files.## Build summary

Recipient-email-verified no longer prompts for email. Matching-verified is unchanged. No new server hint.

**Commit:** `a75e209` — Hide email prompt for recipient-email-verified share access

**Touch points**
- `client/components/ShareAccessGate.vue:127-136` — hide email for recipient modes; blank `verification_email` when hidden (`191-193`)
- `client/utils/shareGateCreds.ts:1-2,20-27` — first-load authorize reason treated as empty/info
- `client/components/ShareVoteSession.vue:377-381` / `client/pages/share/report/[token]/index.vue:190-194` — use that alert helper
- `src/pvf/api/share_link_manage.py:902-904` — “set” → “sent”
- `src/pvf/db/models/share_link_tracking.py:59,65` / `client/pages/projects/[id]/shares.vue:480,486` — “Enter Name Only; key goes to the email on file”
- `src/tests/test_share_ext_access.py` — blank-email send-to-on-file; matching-verified still requires match
- `e2e/tests/share-access-modes.spec.ts:158-191` — email field count 0 vs 1

**Verified:** 35 share ext-access unit tests; 4 new e2e gate tests. Static client rebuilt. Version `0.7.31`. No CHANGELOG.md.
[comment: build completed 2026-08-18T11:41:24.418Z | via executor-opencode | entryId e-20260818-0003 | artifacts: ./adjust-share-security-flow-type-176dys/2026-08-18T11-30-47-598Z-build-eiryf0.request.md, ./adjust-share-security-flow-type-176dys/2026-08-18T11-30-47-598Z-build-eiryf0.response.md, ./adjust-share-security-flow-type-176dys/2026-08-18T11-30-47-598Z-build-eiryf0.trace.log, ./adjust-share-security-flow-type-176dys/2026-08-18T11-30-47-598Z-build-eiryf0.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-18T11:41:24.418Z build completed (e-20260818-0003)
- 2026-08-18T11:30:47.527Z plan completed (e-20260818-0002)
- 2026-08-18T11:24:48.552Z expand completed (e-20260818-0001)
- 2026-08-18T11:23:50.225Z created (source: user)
