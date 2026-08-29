# Share link updates

## Short Description
### user
Refining the share link process
[comment: updated 2026-08-18T11:46:50.631Z | id share-link-updates-vmjpub]

## Expanded Description
### agent
This work package refines share-link and access-code login UX so actions are easier to find and less ambiguous. It adds a second New Share Link control at the bottom of the share list, skips auto-copy when a share is emailed, and splits the login page into a clear “email a code” first step versus the existing code-entry step. The three items are independent UI changes and can ship separately.

- Scope: share-list page (duplicate New Share Link), post-send copy behavior (email vs clipboard), login when a code is required but not known vs already present or requested.
- Treat an emailed-code link as “code known”: show the code field, not Email Access Code.
- After Email Access Code (or if a code is already on the URL), keep today’s code field and add “send/resend code to email”; hide the primary Email Access Code button.
- Do not auto-copy share text when an email is sent; keep copy for non-email share actions.
- Confirm placement/styling of the extra New Share Link button and the small “already have a code” / resend links against existing share and login components.
- Open: should “already have a code” deep-link into the code field without sending mail, and should resend reuse the same email/rate-limit path as today?
[comment: expand completed 2026-08-18T11:47:15.958Z | via executor-opencode | entryId e-20260818-0001 | artifacts: ./share-link-updates-vmjpub/2026-08-18T11-46-50-647Z-expand-apswfl.request.md, ./share-link-updates-vmjpub/2026-08-18T11-46-50-647Z-expand-apswfl.response.md, ./share-link-updates-vmjpub/2026-08-18T11-46-50-647Z-expand-apswfl.trace.log, ./share-link-updates-vmjpub/2026-08-18T11-46-50-647Z-expand-apswfl.result.json]


## Plan

## Build Summary
### agent
I'll start by locating the share-list, share-copy, and access-code login UI so the three items can be implemented against existing components.The three surfaces are mapped. Next I’ll read the share list, create-copy path, and access-code gate, then apply the UX changes.The first-load denial may already force the code field. I’ll check that path before changing the gate copy.The gate flow is already correct; I’ll add the bottom create button, skip clipboard copy after email, and update the access-code labels.Rebuilding the published UI next, then I’ll commit only the share-link files.Static client published. Staging only the share-link files and committing.**5491fbb** Refine share-link and access-code login UX

- Duplicate **New share link** at list bottom: `client/pages/projects/[id]/shares.vue:150`
- Skip autocopy when email sent: `client/pages/projects/[id]/shares.vue:737`
- Gate request view **Email Access Code** + **already have a code**: `client/components/ShareAccessGate.vue:50`
- Enter view keeps code field + **send/resend code to email**: `client/components/ShareAccessGate.vue:71`
- E2E helpers/labels: `e2e/helpers/gate.ts:15`, `e2e/helpers/gate.ts:44`, `e2e/helpers/gate.ts:58`
[comment: build completed 2026-08-18T11:54:14.803Z | via executor-opencode | entryId e-20260818-0001 | artifacts: ./share-link-updates-vmjpub/2026-08-18T11-47-27-012Z-build-gu3btd.request.md, ./share-link-updates-vmjpub/2026-08-18T11-47-27-012Z-build-gu3btd.response.md, ./share-link-updates-vmjpub/2026-08-18T11-47-27-012Z-build-gu3btd.trace.log, ./share-link-updates-vmjpub/2026-08-18T11-47-27-012Z-build-gu3btd.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-18T11:54:14.803Z build completed (e-20260818-0001)
- 2026-08-18T11:47:15.958Z expand completed (e-20260818-0001)
- 2026-08-17T18:22:49.128Z created (source: user)
