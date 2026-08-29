# UI and Share Access Flows

## Short Description
### user
Ensure the UI the functions with all available share security modes. Some are turned off to simply the interface, but should function in the app.

Also, on the page where a key is required on an invite - there is confusion when a user clicks the link and goes to a page with the 'enter code' hint, even though it says 'if received already'.  The link should go to the page with the behavior having a clear 'Send Code to Email' button and a small 'already have code' option. When linking from an email with a code, the enter code box should appear populated.
[comment: updated 2026-08-17T04:04:02.375Z | id ui-and-share-access-flows-fa29t9]

## Expanded Description
### agent
I'll inspect share-access UI and security modes so the expansion matches the actual flows.Gathering share-mode and invite-page details to keep the expansion accurate.Checking which modes the UI hides and how the invite-code page is structured.Make every `ShareAccessCheckMode` work end-to-end even when some modes are hidden from the share-create UI via `enable_share_*` flags, and fix the verified-invite gate so a share link is not mistaken for a “paste the code” page. Recipients who open the share URL should see a primary **Send Code to Email** action and a small **already have code** path; links from a code email should open the enter-code view with the key prefilled. Existing e2e coverage in `share-access-modes.spec.ts` already catalogs all 12 modes and the verified unlock flow.

- **Scope:** Share-create/manage UI (hidden vs available modes), recipient gate for all 12 modes (open, email match/any, password combos, verified variants), and the send-code vs enter-code invite page.
- **Keep:** Backend/frontend flows and feature flags; do not force every mode into the simplified create UI.
- **UX:** Default share-link landing = send code; “already have code” is secondary; email-with-code URLs populate the key field.
- **Verify:** All modes still unlock via existing e2e; verified modes send then accept the magic key; password + verified combos still require both.
- **Open:** Which modes stay hidden by default? Same send/enter-code treatment on vote vs other share actions? Prefill from query/hash only, or also deep-link token?
[comment: expand completed 2026-08-18T10:49:23.119Z | via executor-opencode | entryId e-20260818-0001 | artifacts: ./ui-and-share-access-flows-fa29t9/2026-08-18T10-48-30-655Z-expand-c4101h.request.md, ./ui-and-share-access-flows-fa29t9/2026-08-18T10-48-30-655Z-expand-c4101h.response.md, ./ui-and-share-access-flows-fa29t9/2026-08-18T10-48-30-655Z-expand-c4101h.trace.log, ./ui-and-share-access-flows-fa29t9/2026-08-18T10-48-30-655Z-expand-c4101h.result.json]


## Plan
### agent
I'll inspect share-access UI, security modes, and the invite-code page so the plan matches the actual flows.Graph exists — I'll query it and read the share-create UI, invite gate, and e2e coverage next.Graphify CLI isn’t available; I’ll read the invite gate, flags, and e2e coverage directly.The gate currently shows the code field by default on verified modes — I'll trace how pages use it and how email links prefill the key.## Plan: UI and Share Access Flows

### Current state
- All 12 `ShareAccessCheckMode`s already work on the API (`test_share_ext_access.py`, `share-access-modes.spec.ts`). `ENABLE_SHARE_*` only filters the create picker.
- **Hidden by default:** `open_access`, `email_matching_verified`, `password_only`, `password_with_email_any_verified`, `password_with_email_matching`, `password_with_email_matching_verified`, `password_with_recipient_email_verified`.
- **Shown by default:** `email_any_unverified`, `email_any_verified`, `email_matching`, `recipient_email_verified`, `password_with_email_any_unverified`.
- Verified-mode bug: `ShareAccessGate` shows the key field whenever `verification_email_send_link_mode` is set, plus an unchecked “Send me a one-time access link” checkbox. Share-link landing looks like a paste-the-code page.
- `?key=` is submitted on probe (`shareMagicKeyFromRoute`) but **not bound into the visible field**. Email-with-code users who still need name/password see an empty box.
- Same gate is used for vote, vote_view, and report. Report does not persist creds the way `ShareVoteSession` does.
- Magic-key emails already use `?key=`; `/{token}/{key}` rewrites to query. No hash key today.

### Implementation steps
1. **Keep the create-UI split.** Do not add hidden modes to the picker. Confirm manage/history (`modeLabel`, resend, preview, copy) already labels all 12 from the full catalog, not `availableAccessModes`. Fix create default so it never sticks on hidden `open_access` before settings load (already watched; make the initial value first-enabled, not `open_access`).
2. **Drive gate fields from denial flags, not string-matching.** Show name/email/password only from `verification_*_needed` / `_not_supplied` / `_incorrect`. Stop using `includes('email'|'verified')` so hidden modes cannot mis-render.
3. **Split verified landing into two views in `ShareAccessGate` (used by vote, vote_view, report):**
   - **Request code (default, no key in URL):** name/email/password as required; primary **Send Code to Email** (`authorize_verification_email=true`); small **Already have a code** control.
   - **Enter code:** after send, after “already have code”, or when a key is in the URL. Key field visible and focused; remaining password/email fields still shown for combo modes; Continue unlocks. Optional small resend.
4. **Prefill the key field** from `route.query.key` then `route.params.key` (legacy path already rewritten). Pass that into the gate on mount so the box is populated, not only attached on submit. After send, stay on enter-code with success copy (“key sent”).
5. **Persist gate creds on report** the same way `ShareVoteSession` does, so password + verified still requires both after send/redeem.
6. **Create-form robustness (no new modes):** require recipient email for matching/recipient modes; require password for `password_*`. Hidden-mode shares created via API remain fully manageable.
7. **Tests:** update `e2e/helpers/gate.ts` (`completeVerifiedUnlock` currently checks the checkbox + Continue). Add: share URL shows Send Code, not a key field; “already have code” reveals the box; `?key=` and `/{token}/{key}` open enter-code with the value filled; password + verified still needs both. Re-run `share-access-modes.spec.ts` (all 12) and the API flag matrix. No backend flag or validator changes unless a real gate bug appears.

### Clarifying questions
1. Keep the current default hidden/shown set, or change which modes the create picker offers?
2. After “Send Code”, auto-switch to enter-code (recommended) or stay on the send view with only a banner?
3. Should a `?key=` / path-key landing auto-submit when name/password/email are not required, or always show the prefilled box for confirmation?
4. Any need to read a key from the URL hash, or is query + legacy path enough?

### Options and recommendation
| Option | Trade-off |
|---|---|
| **A. Minimal** — hide key field until sent / `?key=` present; turn the checkbox into a Send button | Fastest; still one crowded form; “already have code” is easy to miss |
| **B. Two-view gate** — Send Code primary; already-have-code secondary; email links open enter-code prefilled | Matches the request; one shared component; e2e helper rewrite |
| **C. Per-mode custom pages** | Clearest copy per mode; more UI to keep in sync across 12 modes × 3 share kinds |

**Recommend B.** Same treatment on vote, vote_view, and report. Prefill from `query.key` then `params.key` only (no hash). Do not surface hidden modes in create. Auto-switch to enter-code after send; auto-unlock on key-only landings (recipient verified with `?key=`) when the probe succeeds, otherwise show the prefilled enter-code view plus remaining fields.
[comment: plan completed 2026-08-18T10:57:51.086Z | via executor-opencode | entryId e-20260818-0001 | artifacts: ./ui-and-share-access-flows-fa29t9/2026-08-18T10-54-58-495Z-plan-75addo.request.md, ./ui-and-share-access-flows-fa29t9/2026-08-18T10-54-58-495Z-plan-75addo.response.md, ./ui-and-share-access-flows-fa29t9/2026-08-18T10-54-58-495Z-plan-75addo.trace.log, ./ui-and-share-access-flows-fa29t9/2026-08-18T10-54-58-495Z-plan-75addo.result.json]


## Build Summary
### agent
I'll inspect the share-access UI, invite gate, and e2e coverage so the implementation matches the existing flows.The plan is already detailed. I'll read the gate, create form, e2e helpers, and related pages next.Implementing the two-view gate, flag-driven fields, create-form defaults, and report credential persistence.The key field should show as soon as a URL key is present, not only after the denial flags arrive.API tests passed. Locating npm so I can rebuild the static client.The path-key rewrite never ran. I'll inspect the route page and fix the redirect.The `[token].vue` parent is swallowing the nested `[key]` rewrite. I'll split those into `index` routes so the path-key redirect can run.Both remaining e2e tests passed. Rebuilding the static client, then committing.**cc970a79edcb10f8edef560a44c315513b6f061c**
Split verified share access into send-code and enter-code views

Share URLs land on Send Code to Email with a small already-have-code path. Email links with `?key=` or `/{token}/{key}` open enter-code prefilled and auto-unlock when the key is enough. Create picker still hides unused modes; report now persists gate credentials like vote.

Verified: `test_share_ext_access.py` 31 passed; `share-access-modes.spec.ts` 18 passed (all 12 modes + send-code / prefill / auto-unlock). Version 0.7.30. static_client rebuilt.

Touch points:
- `client/components/ShareAccessGate.vue:50` request view Send Code; `:67` already have a code; `:121` flag-only fields; `:133` verified mode; `:159` prefill `initialKey`; `:185` send then enter
- `client/utils/shareGateCreds.ts:1` persist creds; skip key while sending
- `client/components/ShareVoteSession.vue:12` pass `initial-key`; `:364` merge creds
- `client/pages/share/report/[token]/index.vue:181` same persist (vote/vote_view/report)
- `client/pages/projects/[id]/shares.vue:490` hide picker until flags; `:499` first-enabled default; `:506` require recipient email; `:692` create validation
- `client/pages/share/vote/[token]/index.vue` (and vote_view/report) so `/{token}/{key}` rewrite actually runs
- `e2e/helpers/gate.ts:44` send-code vs enter-code; `:89` `completeVerifiedUnlock`
- `e2e/tests/share-access-modes.spec.ts:212` new landing/prefill/auto-unlock cases
[comment: build completed 2026-08-18T11:19:10.683Z | via executor-opencode | entryId e-20260818-0001 | artifacts: ./ui-and-share-access-flows-fa29t9/2026-08-18T11-00-45-024Z-build-si53nx.request.md, ./ui-and-share-access-flows-fa29t9/2026-08-18T11-00-45-024Z-build-si53nx.response.md, ./ui-and-share-access-flows-fa29t9/2026-08-18T11-00-45-024Z-build-si53nx.trace.log, ./ui-and-share-access-flows-fa29t9/2026-08-18T11-00-45-024Z-build-si53nx.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-18T11:19:10.683Z build completed (e-20260818-0001)
- 2026-08-18T10:57:51.086Z plan completed (e-20260818-0001)
- 2026-08-18T10:49:23.119Z expand completed (e-20260818-0001)
- 2026-08-17T04:03:39.410Z created (source: user)
