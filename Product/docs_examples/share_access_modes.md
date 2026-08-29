# Share Link Access Modes

Reference: authentication flow in `share_link_validate_and_log` (`src/api/app_shared_link_manage.py`) and the `ShareAccessCheckMode` enum (`src/db/models/share_link_tracking.py`). These modes control what a visitor must complete before a view cookie is granted for a shared vote, vote-view, or report link.

## Access mode matrix

| Access mode | UI title | Password needed | Email needed | Email check | Magic key | Key sent to | Grant condition | `is_email_verified` | Viewer identity source | Invite security note |
|---|---|---|---|---|---|---|---|---|---|---|
| `open_access` | Open access | No | No | — | No | — | Immediate | No | Typed name/email | This link is open access; no additional verification is required. |
| `email_any_unverified` | Any email (unverified) | No | Yes | Regex: any valid-looking email | No | — | Email passes check → immediate | No | Typed | You will be asked to enter an email address to continue. |
| `email_any_verified` | Any email (verified magic link) | No | Yes | Regex: any valid-looking email | Yes | Typed email | Key redeemed | Yes | Typed | You will verify any email address via a one-time access key. |
| `email_matching` | Matching email only | No | Yes | Equality vs on-file email | No | — | Email matches → immediate | No | Typed | You must enter the email address this link was sent to. |
| `email_matching_verified` | Matching email + verified | No | Yes | Equality vs on-file email | Yes | Typed (matching) email | Key redeemed | Yes | Share record | You must verify the email address this link was sent to via a one-time access key. |
| `recipient_email_verified` | Recipient email verified | No | No (hidden; key to on-file) | Visitor is not asked for email | Yes | **On-file email** | Key redeemed | Yes | Share record | A one-time access key will be sent to the email on file for this link. |
| `password_only` | Password only | Yes | No | — | No | — | Password correct → immediate | No | Typed | A password is required to open this link. |
| `password_with_email_any_unverified` | Password + any email | Yes | Yes | Regex: any valid-looking email | No | — | Password + email → immediate | No | Typed | A password and an email address are required to open this link. |
| `password_with_email_any_verified` | Password + verified email | Yes | Yes | Regex: any valid-looking email | Yes | Typed email | Password + key | Yes | Typed | A password is required, then any email is verified via a one-time access key. |
| `password_with_email_matching` | Password + matching email | Yes | Yes | Equality vs on-file email | No | — | Password + email match → immediate | No | Share record | A password and the original recipient email are required. |
| `password_with_email_matching_verified` | Password + matching verified | Yes | Yes | Equality vs on-file email | Yes | Typed (matching) email | Password + key | Yes | Share record | A password is required, then the original recipient email is verified via a one-time access key. |
| `password_with_recipient_email_verified` | Password + recipient verified | Yes | No (hidden; key to on-file) | Visitor is not asked for email | Yes | **On-file email** | Password + key | Yes | Share record | A password is required, then a one-time access key is sent to the email on file. |

## Flow notes

- **Check order** (per request, in `share_link_validate_and_log`): cookie token validity → link enabled/not expired → magic key (if supplied) → password (if required) → email step → grant.
- **Magic key**: 6-digit key stored in `ShareLinkMagicKey`, sent by email as a `?key=` link + the key in the body; single-use (`accessed_date` set on redemption), expires after `ACCESS_MAGIC_KEY_EXPIRATION_MINUTES` (70); a redeemable/used/expired/incorrect key each produce a distinct denial flag. On success the key issues the view cookie (`make_token_cookie`), path-scoped to the share token. Legacy path-form URLs (`/{token}/{key}`) are rewritten by the SPA to `?key=`.
- **Gate throttle**: unauthenticated `/ext-ws/share/{token}/…` calls are volume-capped per IP; wrong password / bad-or-spent magic key / mismatched email increment a tighter per-IP and per-token failure cap (`SHARE_GATE_MAX_*`). Cookied sessions are not throttled. Over-limit requests return HTTP 429.
- **Cookie**: one valid cookie means `access_granted = True` for the session regardless of mode; follow-up mutating operations (e.g. `vote`) additionally require an existing cookie.
- **Verified modes** set `is_email_verified = True` on the confirmed result: `email_any_verified`, `email_matching_verified`, `recipient_email_verified` and their `password_with_*` variants.
- **Viewer identity**: verified/matching recipient modes resolve the viewer's name/org/email from the share record (`shared_with_*`); other modes use what the visitor typed. Notable asymmetry: `password_with_email_matching` uses the share record, while plain `email_matching` uses typed data.
- **`not_specified`** exists as an enum value but is rejected at link creation (`ShareLink.create_shared_link_record`).
