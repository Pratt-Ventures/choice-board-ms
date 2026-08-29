# Email Token for 2fa and share verification security

## Short Description
### user
Add a paramter token_security_digits_only to the pvf_settings.py configuration. It should default to False.  

If this is true, the tokens included in emails to verify users login or share access would be restricted to digits only, with the digits_only parameter passed to get_random_baseN_value. This value has the same semantics as the parameter, so it can be passed directly. 

For less secure environments and applications, it provides a user convenience tradeoff.
[comment: updated 2026-08-18T16:15:29.297Z | id email-token-for-2fa-and-share-verificati-3dwy3o]

## Expanded Description
### agent
I'll inspect the settings and token-generation paths so the expansion matches how email 2FA/share tokens actually work.I have the token call sites; next I’ll read settings and the login/share email paths so the expansion stays accurate.Add a `token_security_digits_only` setting (default `False`) so email-borne login 2FA and share-access verification codes can be restricted to digits when operators accept weaker entropy for easier typing. When true, pass it through as `digits_only` on `get_random_baseN_value` at those email-token call sites; the flag already has the same semantics. Leave password-reset tokens, cookie/magic non-email values, and the default alphanumeric path unchanged.

- Scope: new setting on `PvfGlobalSettings` in `src/pvf/config/pvf_config_settings.py` (there is no `pvf_settings.py`); wire `issue_login_2fa_code` and share-email `access_magic_key` generation only.
- Mirror the field into app settings / `.env` if startup merge expects env-backed booleans, defaulting false.
- Do not apply to `UserPasswordReset` or non-email `get_random_baseN_value` uses (e.g. share cookie placeholders).
- Tests that monkeypatch `get_random_baseN_value` must accept `digits_only`; add coverage that true yields digits-only codes and false keeps current behavior.
- Open: confirm share verification is only `access_magic_key` (length 6), not other share tokens; whether digits-only should be documented as a security tradeoff in env/example config.
[comment: expand completed 2026-08-18T16:16:52.091Z | via executor-opencode | entryId e-20260818-0002 | artifacts: ./email-token-for-2fa-and-share-verificati-3dwy3o/2026-08-18T16-15-50-304Z-expand-7vl9ec.request.md, ./email-token-for-2fa-and-share-verificati-3dwy3o/2026-08-18T16-15-50-304Z-expand-7vl9ec.response.md, ./email-token-for-2fa-and-share-verificati-3dwy3o/2026-08-18T16-15-50-304Z-expand-7vl9ec.trace.log, ./email-token-for-2fa-and-share-verificati-3dwy3o/2026-08-18T16-15-50-304Z-expand-7vl9ec.result.json]


## Plan

## Build Summary
### agent
I'll inspect settings and email token generation so the new `token_security_digits_only` flag wires only to login 2FA and share verification.Reading settings, token generators, and tests so the flag only hits email 2FA and share verification.Checking share-test helpers and existing 2FA/share coverage so new tests match the suite.Implementing the setting and wiring it only into login 2FA and share email tokens.Verifying the edits, then running the 2FA and share tests.Startup import failed before my changes ran. Checking whether that's pre-existing or a path issue.The worktree has other uncommitted work. I'll isolate this feature's diffs and see why app import fails.Tests passed. Staging only this feature's hunks, then committing.**Build summary**

Added `token_security_digits_only` (default `False` / `TOKEN_SECURITY_DIGITS_ONLY=0`) so email-borne login 2FA and share `access_magic_key` codes can be digits-only. Flag is passed through as `digits_only` on `get_random_baseN_value`. Password-reset tokens and non-email cookie values are unchanged. Version `0.7.35`.

**Touch points (committed)**
- `src/pvf/config/pvf_config_settings.py:190` — `token_security_digits_only` on `PvfGlobalSettings`
- `src/pvf/utils/pvf_base_classes_and_enums.py:66-70` — `digits_only` on `get_random_baseN_value`
- `src/pvf/db/models/share_link_tracking.py:230-232` — share email `access_magic_key`
- `src/config/config_settings.py:17` — `VERSION` 0.7.35
- `example.env:53-54` — security-tradeoff note
- `src/pvf/README.md:115-118` — operator note
- `src/tests/test_share_ext_access.py:777-851` — digits-only / flag-pass-through coverage

**Also wired (untracked 2FA work, not in this commit)**
- `src/pvf/utils/login_2fa.py:100` — `issue_login_2fa_code`
- `src/tests/test_login_2fa.py` — monkeypatches accept `digits_only`; 2FA digits-only tests added

**Verify:** 26 passed (`test_login_2fa.py` + new share token tests).

**Commit:** `1ec036a02a54a03aca0576b44c05d942aa5ab266`  
Add token_security_digits_only for email 2FA and share verification codes
[comment: build completed 2026-08-18T16:25:20.144Z | via executor-opencode | entryId e-20260818-0003 | artifacts: ./email-token-for-2fa-and-share-verificati-3dwy3o/2026-08-18T16-16-52-130Z-build-0l4ybt.request.md, ./email-token-for-2fa-and-share-verificati-3dwy3o/2026-08-18T16-16-52-130Z-build-0l4ybt.response.md, ./email-token-for-2fa-and-share-verificati-3dwy3o/2026-08-18T16-16-52-130Z-build-0l4ybt.trace.log, ./email-token-for-2fa-and-share-verificati-3dwy3o/2026-08-18T16-16-52-130Z-build-0l4ybt.result.json]


## Code Review Guide

## UI Review Guide

## History
- 2026-08-18T16:25:20.144Z build completed (e-20260818-0003)
- 2026-08-18T16:16:52.091Z expand completed (e-20260818-0002)
- 2026-08-18T16:15:20.873Z created (source: user)
