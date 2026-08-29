# PVF Prefix Rename — Migration Helper

This document tracks the clean-break rename of all PVF-managed tables and widely-used support classes to `Pvf` / `pvf_` prefixes. There are **no backward-compatibility aliases** — update all external consumers.

**Revision:** `eace549c78a8_pvf_prefix_rename` (revises `fb7d7d4374bd`) — single migration.

## Table renames (22 tables)

All PVF tables now use snake-prefixed `pvf_` / `pvf_watcher_` table names. Fresh installs (`alembic upgrade head` on empty DB or `BOOTSTRAP_SAMPLE_DATA` + `create_all`) create new names directly; existing DBs are migrated via `op.rename_table`.

| Old table | New table | Old class | New class |
|---|---|---|---|
| `customer` | `pvf_customer` | `Customer` / `CustomerSpec` | `PvfCustomer` / `PvfCustomerSpec` |
| `user` | `pvf_user` | `User` / `UserSpec` | `PvfUser` / `PvfUserSpec` |
| `sharelink` | `pvf_sharelink` | `ShareLink` / `ShareLinkSpec` | `PvfShareLink` / `PvfShareLinkSpec` |
| `sharelinkmagickey` | `pvf_sharelinkmagickey` | `ShareLinkMagicKey` | `PvfShareLinkMagicKey` |
| `sharelinkaccessed` | `pvf_sharelinkaccessed` | `ShareLinkAccessed` | `PvfShareLinkAccessed` |
| `apiaccessconfiguration` | `pvf_apiaccessconfiguration` | `ApiAccessConfiguration` / `ApiAccessConfigurationSpec` | `PvfApiAccessConfiguration` / `PvfApiAccessConfigurationSpec` |
| `apiwebinvocationevent` | `pvf_apiwebinvocationevent` | `ApiWebInvocationEvent` | `PvfApiWebInvocationEvent` |
| `customerbrandingimage` | `pvf_customerbrandingimage` | `CustomerBrandingImage` | `PvfCustomerBrandingImage` |
| `projectbrandingimage` | `pvf_projectbrandingimage` | `ProjectBrandingImage` | `PvfProjectBrandingImage` |
| `applicationlogevent` | `pvf_applicationlogevent` | `ApplicationLogEvent` | `PvfApplicationLogEvent` |
| `usersessionlog` | `pvf_usersessionlog` | `UserSessionLog` | `PvfUserSessionLog` |
| `emailactivitylog` | `pvf_emailactivitylog` | `EmailActivityLog` | `PvfEmailActivityLog` |
| `stripeevent` | `pvf_stripeevent` | `StripeEvent` | `PvfStripeEvent` |
| `subscribertransaction` | `pvf_subscribertransaction` | `SubscriberTransaction` / `SubscriberTransactionBase` | `PvfSubscriberTransaction` / `PvfSubscriberTransactionBase` |
| `userpasswords` | `pvf_userpasswords` | `UserPasswords` | `PvfUserPasswords` |
| `userpasswordreset` | `pvf_userpasswordreset` | `UserPasswordReset` | `PvfUserPasswordReset` |
| `bugreport` | `pvf_bugreport` | `BugReport` | `PvfBugReport` |
| `suggestion` | `pvf_suggestion` | `Suggestion` | `PvfSuggestion` |
| `watcher_llm_requests` | `pvf_watcher_llm_requests` | `WatcherLlmRequest` | `PvfWatcherLlmRequest` |
| `watcher_email_requests` | `pvf_watcher_email_requests` | `WatcherEmailRequest` | `PvfWatcherEmailRequest` |
| `watcher_api_requests` | `pvf_watcher_api_requests` | `WatcherApiRequest` | `PvfWatcherApiRequest` |
| `watcher_generic_jobs` | `pvf_watcher_generic_jobs` | `WatcherGenericJob` | `PvfWatcherGenericJob` |

**Explicit `__tablename__`** now set on every table (specs `PvfCustomerSpec`, `PvfUserSpec`, `PvfShareLinkSpec`, `PvfApiAccessConfigurationSpec` carry `__tablename__` so `extend_model_class` preserves it; direct tables define `__tablename__` explicitly). Watches keep snake (`pvf_watcher_*`), others are `pvf_` + original lowercased name (no extra underscores).

**Indexes / constraints / sequences** renamed:

- `ix_customer_customer_email` → `ix_pvf_customer_customer_email`, `ix_user_email` → `ix_pvf_user_email`, `ix_sharelink_*` → `ix_pvf_sharelink_*`, `ix_apiaccessconfiguration_*` → `ix_pvf_apiaccessconfiguration_*`, `ix_…_llm_requests_claim` → `ix_pvf_watcher_llm_requests_claim`, `uq_customerbrandingimage_customer_id` → `uq_pvf_customerbrandingimage_customer_id`, `ix_bugreport_*` → `ix_pvf_bugreport_*`, etc. (full list in `eace549c78a8_pvf_prefix_rename.py:INDEX_RENAMES`). Sequences `*_id_seq` renamed similarly (`customer_id_seq` → `pvf_customer_id_seq`).
- Foreign key `userpasswords.user_id → user.id` now `pvf_userpasswords.user_id → pvf_user.id` (`Field(foreign_key="pvf_user.id")` in `src/pvf/db/models/user_passwords.py:8`). Postgres OID-based FKs are updated automatically on `ALTER TABLE RENAME`; constraint name `userpasswords_user_id_fkey` renamed to `pvf_userpasswords_user_id_fkey` where present.
- `EXTENSIBLE_TABLES` in `src/pvf/db/model_factory.py:38` now `{"pvf_customer","pvf_user","pvf_sharelink","pvf_apiaccessconfiguration"}` and `for_table("pvf_…")` calls updated (`customer_user.py:258,399`, `share_link_tracking.py:204`, `api_access_configuration.py:134-136`).

## Support class / enum renames (widely-used)

All widely-used PVF support types now carry `Pvf` prefix. Update imports from `src.pvf.*` and `src.pvf.bindings.pvf_services`.

| Old | New |
|---|---|
| `UserContext` | `PvfUserContext` |
| `AccountStatus` | `PvfAccountStatus` |
| `ShareAccessCheckMode` | `PvfShareAccessCheckMode` |
| `WebHookStatus` | `PvfWebHookStatus` |
| `WsResultPackage` | `PvfWsResultPackage` |
| `LogSeverity` | `PvfLogSeverity` |
| `AuthRelatedOutboundEmailType` | `PvfAuthRelatedOutboundEmailType` |
| `SubscriberTransactionType` | `PvfSubscriberTransactionType` |
| `SubscriberTransactionUnits` | `PvfSubscriberTransactionUnits` |
| `TokenPayload` | `PvfTokenPayload` |
| `TokenSchema` | `PvfTokenSchema` |
| `WatcherStatus` | `PvfWatcherStatus` |
| `WatcherEventOrchestration` | `PvfWatcherEventOrchestration` |
| `WatcherInvocationResult` | `PvfWatcherInvocationResult` |
| `WatcherRegistryEntry` | `PvfWatcherRegistryEntry` |
| `DatabaseConnection` | `PvfDatabaseConnection` |
| `Login` | `PvfLogin` |
| `Login2FAChallenge` | `PvfLogin2FAChallenge` |
| `ShareAccessRequest_Base` | `PvfShareAccessRequest_Base` |
| `ShareAccessRequest` | `PvfShareAccessRequest` |
| `ShareAccessDenied_Base` | `PvfShareAccessDenied_Base` |
| `ShareAccessConfirmed_Base` | `PvfShareAccessConfirmed_Base` |
| Result wrappers `UserResult_One`, `CustomerResult_Many`, `ShareLinkResult_One`, `ApiAccessConfigurationResult_One`, `LogEventResult_Many`, `SubscriberTransactionResult_One`, `BrandingImageResult`, `UserCommunicationRow`, `UserCommunicationSubmitResult`, etc. | `PvfUserResult_One`, `PvfCustomerResult_Many`, `PvfShareLinkResult_One`, `PvfApiAccessConfigurationResult_One`, `PvfLogEventResult_Many`, `PvfSubscriberTransactionResult_One`, `PvfBrandingImageResult`, `PvfUserCommunicationRow`, `PvfUserCommunicationSubmitResult`, etc. (all `*Result*`, `*Row`, `DeleteResult` → `Pvf*`) |

`src/pvf/bindings/pvf_services.py` now exports `Pvf*` names via `_LAZY_ATTRS` and `__all__`; `from ..pvf.bindings.pvf_services import Customer` → `PvfCustomer`, `User` → `PvfUser`, `UserContext` → `PvfUserContext`, `WsResultPackage` → `PvfWsResultPackage`, etc. Also `src/pvf/db/model_factory.py` comment example updated.

## How to migrate other environments

**Single migration, no aliases.**

1. Deploy code + migration together (atomic). The migration renames tables in-place; old names disappear.
2. Run migrations:
   ```bash
   cd src && PYTHONPATH=.. ./.venv/bin/alembic upgrade head
   # or
   ./scripts/migrations/run-migrations.sh
   ```
   On Postgres, indexes/sequences/constraints are renamed (`IF EXISTS` guards). On SQLite, table renames are applied; index names are best-effort (drop old if exists). Fresh DBs created via `alembic upgrade head` from empty will run `214c4d6a4a26_initial` (creating old names) then this rename — ending at new names. `BOOTSTRAP_SAMPLE_DATA` fresh `create_all` writes new names directly (no migration needed).

3. Verify:
   ```bash
   src/.venv/bin/pytest src/tests/test_pvf_alembic_config.py -k test_alembic_runtime_exports_full_schema
   src/.venv/bin/pytest src/tests/test_pvf_schema_extensions.py -k test_real_pvf_models_intact
   ```
   Check `SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'pvf_%';` shows 22 tables.

4. Rollback (if needed):
   ```bash
   cd src && PYTHONPATH=.. ./.venv/bin/alembic downgrade -1
   # or
   ./scripts/migrations/rollback-one-migration.sh
   ```
   Downgrade renames `pvf_*` → old names and restores indexes/sequences.

**Code changes required in external consumers:**
- Replace `from src.pvf.db.models.customer_user import Customer, User, UserContext, AccountStatus` → `PvfCustomer, PvfUser, PvfUserContext, PvfAccountStatus`
- Replace `from src.pvf.db.models.share_link_tracking import ShareLink, ShareLinkMagicKey, ShareAccessCheckMode` → `PvfShareLink, PvfShareLinkMagicKey, PvfShareAccessCheckMode`
- Replace `from src.pvf.bindings.pvf_services import Customer, User, ShareLink, UserContext, WsResultPackage` → `PvfCustomer, PvfUser, PvfShareLink, PvfUserContext, PvfWsResultPackage`
- Replace `from src.pvf.watcher.models import WatcherLlmRequest` → `PvfWatcherLlmRequest` (same for email/api/generic)
- Replace `Field(foreign_key="user.id")` → `Field(foreign_key="pvf_user.id")` if you have custom FKs (only PVF internal had this).
- Update any `__tablename__` checks in tests: `assert ShareLink.__tablename__ == "sharelink"` → `PvfShareLink.__tablename__ == "pvf_sharelink"`.

No JSON / API field renames — `customer_id`, `user_id`, `shared_type` etc column/field names are unchanged (per `terminology_dictionary.md`).

## Fresh installs

Alembic initial migration still creates the original names, then the rename migration converts them. If you use SQLite `local.db` with `BOOTSTRAP_SAMPLE_DATA=1` and `SERVER_ENV != production`, the DB is created via `SQLModel.metadata.create_all` which now emits `pvf_*` tables directly (no rename needed). For Postgres production, always use `alembic upgrade head`.

## References

- `src/pvf/db/models/pvf_bootstrap.py` — `import_all_models()` now registers `Pvf*` tables.
- `src/pvf/pvf_get_alembic_config.py` — `get_alembic_runtime()` still forces `BOOTSTRAP_SAMPLE_DATA=False`, calls `register_schema_extensions` before `import_all_models`, then `get_target_metadata()` (now `pvf_*`).
- `src/pvf/README.md` — PVF is off-limits unless explicitly allowed; this rename was explicitly allowed.
- `src/config/config_settings.py:VERSION` bumped `0.7.94` → `0.7.95`.
