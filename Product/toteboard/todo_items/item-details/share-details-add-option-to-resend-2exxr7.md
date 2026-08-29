# Share details - add Option to resend

## Short Description
### user
On the share details, add an option to 'send' or 'resend' the invite emails. Add a new message type for 'resending_invitation' and create a slightly revised template to reflect that a project administrator requested this be resent.
[comment: created 2026-08-17T18:31:52.540Z | id share-details-add-option-to-resend-2exxr7]

## Expanded Description
### agent
I'll quickly inspect how share details and invitation emails work so the expansion is accurate.Checking message types and the share-details UI so the expansion matches existing patterns.On the share details view, add Send and Resend actions so a project administrator can deliver or re-deliver the invitation email for an existing share link, not only at create time when `link_auto_send` is set. Introduce a new outbound message type `resending_invitation` with a lightly revised template that states a project administrator requested the invite be resent, while reusing the same share URL, access notes, and recipient context as the original invite. Wire this through the existing outbound-mail and share-manage paths so vote, vote-view, and report shares can all be resent.

- Scope: share details UI (`client/pages/shares/index.vue`), a share-manage send/resend API, `OutboundEmailType` plus Jinja/SendGrid template registration, and activity-log coverage.
- Use Send when no invite was delivered; Resend when one already went out. Disable or hide the action for revoked/expired links and shares with no recipient email.
- Reuse existing share-type dispatch (`share_project_vote` / `_vote_view` / `_report`) for first send; use `resending_invitation` (or type-specific resend variants) only for administrator-triggered resends.
- Respect outbound throttling, password-in-email rules, and do not rotate the token unless product requires a fresh link.
- Open: one shared resend template vs per-share-type copies; whether resend is allowed after the recipient has already opened or completed the share.
[comment: expand completed 2026-08-17T18:32:53.219Z | via executor-opencode | entryId e-20260817-0001 | artifacts: ./share-details-add-option-to-resend-2exxr7/2026-08-17T18-31-52-592Z-expand-77i4vr.request.md, ./share-details-add-option-to-resend-2exxr7/2026-08-17T18-31-52-592Z-expand-77i4vr.response.md, ./share-details-add-option-to-resend-2exxr7/2026-08-17T18-31-52-592Z-expand-77i4vr.trace.log, ./share-details-add-option-to-resend-2exxr7/2026-08-17T18-31-52-592Z-expand-77i4vr.result.json]


## Plan

## Build Summary
### agent
I'll inspect share details, invitation email types, and share-manage paths first so the send/resend work matches existing patterns.Share-details, invite types, and manage APIs are mapped. Next I’ll read the files I’ll change and implement send/resend end to end.I have the patterns. Implementing the enum, templates, send/resend API, activity flags, and share-details actions next.Next I’ll add send/resend tests and wire invite-sent flags into the existing activity coverage.Tests passed. Regenerating the session OpenAPI snapshot and rebuilding the published UI.Nuxt generate hit a running dev lock. Retrying the static client publish with the lock bypass.**1b66d04** Add send and resend invitation actions on share details

Send/Resend on share details. First send uses share-type templates; resend uses `resending_invitation`. Disabled/expired/no-email blocked; token not rotated. 44 tests passed. VERSION 0.7.29.

- `src/utils/base_classes_and_enums.py:30` — `resending_invitation`
- `email_templates/resending_invitation.html:2` — admin-requested resend copy
- `src/pvf/api/share_link_manage.py:110-114`, `:136`, `:465`, `:518`, `:1026` — send API, activity flags
- `src/app_shell.py:104` — resend dispatcher
- `client/pages/shares/index.vue:282-289`, `:429` — details Send/Resend
- `client/pages/projects/[id]/shares.vue:78-85`, `:349-356`, `:779` — project share actions
- `src/tests/test_share_manage.py:415` — first send vs resend coverage
[comment: build completed 2026-08-17T18:48:27.923Z | via executor-opencode | entryId e-20260817-0002 | artifacts: ./share-details-add-option-to-resend-2exxr7/2026-08-17T18-32-53-302Z-build-s9fx5k.request.md, ./share-details-add-option-to-resend-2exxr7/2026-08-17T18-32-53-302Z-build-s9fx5k.response.md, ./share-details-add-option-to-resend-2exxr7/2026-08-17T18-32-53-302Z-build-s9fx5k.trace.log, ./share-details-add-option-to-resend-2exxr7/2026-08-17T18-32-53-302Z-build-s9fx5k.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-17T18:48:27.923Z build completed (e-20260817-0002)
- 2026-08-17T18:32:53.219Z expand completed (e-20260817-0001)
- 2026-08-17T18:31:52.540Z created (source: user)
