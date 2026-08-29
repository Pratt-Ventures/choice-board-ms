# Small changes to sharing UI

## Short Description
### user
Small changes to sharing UI
[comment: created 2026-08-18T12:08:09.368Z | id small-changes-to-sharing-ui-1ac55i | work-package]

## Expanded Description
### agent
Small sharing-UI tweaks: surface Resend Invite on listed shares (when show-shares is on), and default the create-share dialog to email-link when the recipient option is email-verified.

- Scope: share page list actions (Resend Invite under Copy link if applicable) plus create-share-link dialog defaulting.
- Resend Invite only when that share can be resent; same behavior as manage, no extra manage hop.
- If user picks an email-verified recipient option, default to emailing the link rather than copy/generic share.
- Confirm “email verified option” means verified recipient email vs. a verified-email share type, and whether unverified stays on copy-link.
- Confirm visibility rules (pending vs accepted shares) and any rate limits or toasts to reuse from manage.
[comment: expand completed 2026-08-18T15:17:05.125Z | via executor-opencode | entryId e-20260818-0001 | artifacts: ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-16-23-425Z-expand-v3oe1n.request.md, ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-16-23-425Z-expand-v3oe1n.response.md, ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-16-23-425Z-expand-v3oe1n.trace.log, ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-16-23-425Z-expand-v3oe1n.result.json]


## Plan
### agent
I'll inspect the sharing UI and related invite/create-share flows so the plan matches current behavior.# Small changes to sharing UI

Two frontend-only tweaks. No API, backend, or type changes.

## 1. Implementation steps

1. **Workspace list — Resend Invite** (`client/pages/shares/index.vue`)
   - In the expanded “Show shares” table action cell (after Copy link, ~123–134), add a third text button:
     - `v-if="canSendInvite(entry)"`
     - Label: `entry.invite_email_sent ? 'Resend invite' : 'Send invite'` (same as History dialog / project manage)
     - `@click="sendOrResendInvite(entry)"`
   - Reuse existing `canSendInvite` (email + enabled + not expired) and `sendOrResendInvite` (toasts: `Invitation sent` / `Invitation resent` / API `failure_reason` / `Could not send invitation` / admin gate).
   - Promote `sendingInvite` boolean to per-row `sendingInviteId === entry.share_id` so two list rows do not share one spinner (manage already does this).
   - Stack the cell (`d-flex flex-column align-end`) so the new action sits below Copy link without crowding the dense table.

2. **Create-share dialog default** (`client/pages/projects/[id]/shares.vue`)
   - Watch `createForm.access_mode`. When the user picks an email-verified mode, set `link_auto_send = true` (the “Email link to recipient” switch). When they switch to an unverified mode, set it back to `false`.
   - Keep the switch user-overridable after the default. Do not change `resetCreateForm` beyond resetting `link_auto_send` to `false` as today.
   - Existing create path already emails when `link_auto_send` is true and skips auto-copy when `link_email_sent` is true.

3. **Verify (manual; no client unit tests exist)**
   - `/shares` → Show shares → pending email share: Send/Resend under Copy link; History still works; non-applicable rows (no email / disabled / expired) hide the button.
   - Same share: list action and manage/History produce the same toasts and activity flags.
   - Create dialog: pick a verified access mode → switch on; pick unverified → switch off; user can still flip it; create still emails vs copies as today.

## 2. Clarifying questions

1. **“Email verified option”** — default auto-email for which modes?
   - **A (narrow):** `recipient_email_verified` and `password_with_recipient_email_verified` only (key goes to on-file email).
   - **B (all `*verified*`):** also `email_any_verified`, `email_matching_verified`, and password variants. Note: `email_any_verified` does **not** require recipient email unless auto-send is on — flipping the switch would suddenly require an email.
   - **C:** any mode that already requires recipient email (`matching` or `recipient`), including unverified matching.
2. **After defaulting, if the user then changes access mode again**, should we always overwrite `link_auto_send`, or only auto-set on first verified pick and then leave their override alone?
3. Visibility is currently **not** pending-vs-accepted (no such status). Resend stays available after the recipient opens the share, as on manage. Change that, or keep parity?
4. Workspace `requireAdmin()` already blocks non-admins with a toast. Server also allows the share **creator**. Should the list button follow the client admin check (current History behavior) or also show for creators?

## 3. Options and trade-offs

| Topic | Options | Recommendation |
|---|---|---|
| Verified-mode scope | A narrow / B all `*verified*` / C matching+recipient | **A**, unless product meant B. Recipient-verified modes already require email and are the ones where “email the link” is the natural delivery. B surprises users on `email_any_verified`. C over-applies to unverified matching. |
| Watch vs one-shot default | Always sync switch to mode vs set-once | **Always sync** when mode changes, then allow manual override until the next mode change. Predictable; matches “if user selects … default to”. |
| List layout | Extra wrapping inline button vs stacked under Copy link | **Stack** — matches the brief and avoids a cramped third inline control. |
| Loading state | Shared boolean vs per-`share_id` | **Per-id** — manage already does this; needed once the action is on every row. |
| Pending/accepted hide | Hide after first open vs always if applicable | **Keep current manage rules** (email + enabled + not expired). No pending/accepted field; changing it here would fork behavior. |
| Tests | New client tests vs manual + existing backend tests | **Manual QA only** for this slice. Backend send/resend is already covered in `src/tests/test_share_manage.py`. No client test harness for these pages. |

**Out of scope:** new endpoints, rate-limit UI, token rotation, password-in-email on resend, e2e visitor-gate specs.
[comment: plan completed 2026-08-18T15:46:14.080Z | via executor-opencode | entryId e-20260818-0002 | artifacts: ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-42-08-728Z-plan-5n775j.request.md, ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-42-08-728Z-plan-5n775j.response.md, ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-42-08-728Z-plan-5n775j.trace.log, ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-42-08-728Z-plan-5n775j.result.json]


## Build Summary
### agent
I'll inspect the share list and create-share dialog, then apply the two UI tweaks from the plan.Plan is clear: Resend on the share list, and default email-link for recipient-verified modes. Checking version, changelog, and existing watcher patterns.Implementing both UI tweaks and checking the worktree so the commit stays scoped.Rebuilding the published client, then committing only these share-UI files.Static client built. Staging only the share-UI files and committing.Version should bump once from HEAD (`0.7.33` → `0.7.34`); the extra increment belonged to other dirty work.**Build summary**

Resend/Send invite is now on the workspace Sharing table (Show shares) under Copy link when `canSendInvite` applies; create-share defaults “Email link to recipient” on for recipient-email-verified modes only.

**Touch points**
- `client/pages/shares/index.vue:123-145` stacked list actions; `:136-144` Send/Resend; `:297` / `:331` / `:451` per-row `sendingInviteId`
- `client/pages/projects/[id]/shares.vue:670-676` watch `access_mode` → `link_auto_send` for `recipient_email_verified` / `password_with_recipient_email_verified`
- `src/config/config_settings.py:17` version `0.7.34`

**Commit** `073d6a95128285097f268427ba365f6a9f3a9e98`  
Add resend invite on share list and default email-link for recipient-verified modes
[comment: build completed 2026-08-18T15:58:16.343Z | via executor-opencode | entryId e-20260818-0004 | artifacts: ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-54-52-702Z-build-7tgkhm.request.md, ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-54-52-702Z-build-7tgkhm.response.md, ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-54-52-702Z-build-7tgkhm.trace.log, ./small-changes-to-sharing-ui-1ac55i/2026-08-18T15-54-52-702Z-build-7tgkhm.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-18T15:58:16.343Z build completed (e-20260818-0004)
- 2026-08-18T15:46:14.080Z plan completed (e-20260818-0002)
- 2026-08-18T15:17:05.125Z expand completed (e-20260818-0001)
- 2026-08-18T12:08:09.368Z created (source: user)
