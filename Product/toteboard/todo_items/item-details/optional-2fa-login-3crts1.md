# Optional 2FA login

## Short Description
### user
PERFORMED IN CONSOLE TO ALLOW QUESTIONS AND CLARIFICATIONS

We are adding optional 2FA to the PVF capability, the nuxt application here. This will be configured to apply at the system, customer, and user levels.
A new configuration setting (in the PVF level) would be LOGIN_2FA_MODE and its values would be 'disabled','sysadmins', 'admins', 'admins+optin', where disabled means no 2FA, sysadmins means system admins only, admins means 2FA for system and customer admins, admins+optin  means all customer and syss admins and users with use_2fa set in either the customer or particular user record. Only a customer or system admin (or backoffice) can change the customer level 2fa setting. A new column is added to both the user and customer record definitions for this purpose. When either is set to true, and the option is admins+optin or 'all', 2FA is turned on for the user, in addition to if sysadmin or admin applies. 

A new email mode and template will be added to send login 2FA codes. It should say this is your supplemental login code for security. Valid for <configured minutes> and standard practices for such emails.

The availability of 2fa needs to be signalled to the client. Add a setting in the client settings area for 'TWO_FACTOR_AUTH_ENABLED' that is set to true if the system mode, user type (admin or sys admin) or 2FA opt-in with admin+optin mode. This is false when no 2FA applies to the user currently. 

Add a 'TWO_FACTOR_AUTH_OPTIONAL' setting in the settings area for the client. This is set to true in client settings when the user can effectively change the setting. This requires mode admin+optins with the customer record set to false. Otherwise, the user cannot change the 2FA setting. If either 2FA setting field is enabled, If this is enabled, the user will get a new box on their settings page, either providing information or allowing them to change it. If it is locked on, due to customer setting or user setting, it states your account is 2FA enabled, linked to your email. If it is optional, the 2fa info box provides the option to set or clear 2FA needed. If the user is a customer admin, the box indicates whether all customer users are required to have 2FA and a switch to enable or disable (if optional). 
Changes to customer or user 2FA settings, although redundnat with other broader update modes, will be done using new endpoints to enable or disable 2FA for a user or customer.  The service allows both user mode and a customer mode changes, changing the customer record or user record as appropriate. After security checks, requiring customer admin and admin+optiiit will adjust the record if different. Changes to the customer record will create an informational log entry. The return value indicates the new state and prior state.

A new response to the auth setting will be required indicating a 2FA submission is required.  The password hash table will have new columns for last 2FA issued (stored as a hash) and last 2fa timestamp. The 2FA will be valid until the system configured timestamp is reached. A new config parameter for login 2fa validity in minutes will be needed as well. That should be in the emails, similar to share links.

Thoroughly plan all required changes in preparation for a build step. Ask any clarification quiestions that may be required.
[comment: updated 2026-08-18T15:10:50.316Z | id optional-2fa-login-3crts1]

## Expanded Description
### agent
Optional email-based 2FA will be added to the PVF Nuxt app, gated by system `LOGIN_2FA_MODE` (`disabled` / `sysadmins` / `admins` / `admins+optin`) plus new `use_2fa` columns on customer and user records. Client settings will expose `TWO_FACTOR_AUTH_ENABLED` and `TWO_FACTOR_AUTH_OPTIONAL` so the settings page can show a locked “2FA on, linked to email” state, a user opt-in toggle, and (for customer admins) a customer-wide require-2FA switch. Login must return a 2FA-required challenge; codes are stored hashed with a timestamp on the password-hash table, expire after a new validity-minutes config (also used in the email, like share links), and are sent via a new 2FA email mode/template. Dedicated enable/disable endpoints will update user or customer flags after security checks, log customer-level changes, and return prior and new state.

- Scope: PVF config + validity minutes; user/customer schema; auth 2FA challenge + hashed code/timestamp; 2FA email; client settings + settings-page box; user/customer 2FA endpoints and customer-change audit log.
- Enforcement: 2FA applies when mode matches role (sysadmin/admin) or, in `admins+optin` (and any `'all'` mode), when customer or user `use_2fa` is true; only customer/system admin or backoffice may change the customer-level flag.
- Client: `TWO_FACTOR_AUTH_ENABLED` when 2FA currently applies to the user; `TWO_FACTOR_AUTH_OPTIONAL` only in `admins+optin` with customer `use_2fa` false so the user can set/clear their own flag.
- Key considerations: hash codes (not plaintext); reuse share-link validity/email patterns; customer toggle needs admin+optin and customer-admin; do not rely only on existing broad update APIs; return prior/new state.
- Open: Is `'all'` a fifth `LOGIN_2FA_MODE` or just another name for `admins+optin`? How is the code submitted (new field on existing auth vs new endpoint)? Default validity minutes, resend/rate limits, and whether a user-level lock-on can be cleared by the user or only by admins?
[comment: expanded description edited 2026-08-18T15:10:50.316Z]


## Plan

## Build Summary

## Code Review Guide

## UI Review Guide

## History
- 2026-08-18T13:34:58.948Z expand completed (e-20260818-0001)
- 2026-08-18T12:43:46.375Z created (source: user)
