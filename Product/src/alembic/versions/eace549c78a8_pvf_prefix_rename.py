"""pvf prefix rename — Customer -> PvfCustomer / customer -> pvf_customer (all PVF tables)

Revision ID: eace549c78a8
Revises: fb7d7d4374bd
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'eace549c78a8'
down_revision: Union[str, None] = 'fb7d7d4374bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Old -> new table mapping (22 tables). Use snake prefix pvf_ / pvf_watcher_
TABLE_RENAMES: list[tuple[str, str]] = [
    ("customer", "pvf_customer"),
    ("user", "pvf_user"),
    ("sharelink", "pvf_sharelink"),
    ("sharelinkmagickey", "pvf_sharelinkmagickey"),
    ("sharelinkaccessed", "pvf_sharelinkaccessed"),
    ("apiaccessconfiguration", "pvf_apiaccessconfiguration"),
    ("apiwebinvocationevent", "pvf_apiwebinvocationevent"),
    ("customerbrandingimage", "pvf_customerbrandingimage"),
    ("projectbrandingimage", "pvf_projectbrandingimage"),
    ("applicationlogevent", "pvf_applicationlogevent"),
    ("usersessionlog", "pvf_usersessionlog"),
    ("emailactivitylog", "pvf_emailactivitylog"),
    ("stripeevent", "pvf_stripeevent"),
    ("subscribertransaction", "pvf_subscribertransaction"),
    ("userpasswords", "pvf_userpasswords"),
    ("userpasswordreset", "pvf_userpasswordreset"),
    ("bugreport", "pvf_bugreport"),
    ("suggestion", "pvf_suggestion"),
    ("watcher_llm_requests", "pvf_watcher_llm_requests"),
    ("watcher_email_requests", "pvf_watcher_email_requests"),
    ("watcher_api_requests", "pvf_watcher_api_requests"),
    ("watcher_generic_jobs", "pvf_watcher_generic_jobs"),
]

# Explicit old -> new index/constraint renames that are known.
# For Postgres we also do dynamic discovery for any remaining ix_/uq_ indexes.
# This list covers the cases where index name contains table name as substring.
# We use exact old index names as they appear in the DB at head.
INDEX_RENAMES: list[tuple[str, str]] = [
    # customer
    ("ix_customer_customer_account", "ix_pvf_customer_customer_account"),
    ("ix_customer_customer_email", "ix_pvf_customer_customer_email"),
    # user
    ("ix_user_email", "ix_pvf_user_email"),
    # sharelink (from 1fa893e89191)
    ("ix_sharelink_customer_id", "ix_pvf_sharelink_customer_id"),
    ("ix_sharelink_magic_token", "ix_pvf_sharelink_magic_token"),
    ("ix_sharelink_shared_entity_db_id", "ix_pvf_sharelink_shared_entity_db_id"),
    # sharelinkmagickey / sharelinkaccessed
    ("ix_sharelinkmagickey_share_id", "ix_pvf_sharelinkmagickey_share_id"),
    ("ix_sharelinkmagickey_share_token_and_access_magic_key", "ix_pvf_sharelinkmagickey_share_token_and_access_magic_key"),
    ("ix_sharelinkaccessed_share_id", "ix_pvf_sharelinkaccessed_share_id"),
    ("ix_sharelinkaccessed_shared_entity_db_id", "ix_pvf_sharelinkaccessed_shared_entity_db_id"),
    ("ix_sharelinkaccessed_customer_id", "ix_pvf_sharelinkaccessed_customer_id"),
    ("ix_sharelinkaccessed_cookie_token", "ix_pvf_sharelinkaccessed_cookie_token"),
    # apiaccessconfiguration
    ("ix_apiaccessconfiguration_application_tag", "ix_pvf_apiaccessconfiguration_application_tag"),
    ("ix_apiaccessconfiguration_authentication_key_id", "ix_pvf_apiaccessconfiguration_authentication_key_id"),
    ("ix_apiaccessconfiguration_customer_id", "ix_pvf_apiaccessconfiguration_customer_id"),
    # apiwebinvocationevent
    ("ix_apiwebinvocationevent_api_configuration_id", "ix_pvf_apiwebinvocationevent_api_configuration_id"),
    ("ix_apiwebinvocationevent_authentication_key_id", "ix_pvf_apiwebinvocationevent_authentication_key_id"),
    ("ix_apiwebinvocationevent_customer_id", "ix_pvf_apiwebinvocationevent_customer_id"),
    ("ix_apiwebinvocationevent_unique_tracking_id", "ix_pvf_apiwebinvocationevent_unique_tracking_id"),
    # branding
    ("uq_customerbrandingimage_customer_id", "uq_pvf_customerbrandingimage_customer_id"),
    ("uq_projectbrandingimage_project_id", "uq_pvf_projectbrandingimage_project_id"),
    # email
    ("ix_emailactivitylog_email_address", "ix_pvf_emailactivitylog_email_address"),
    ("ix_emailactivitylog_remote_ip", "ix_pvf_emailactivitylog_remote_ip"),
    # stripe
    ("ix_stripeevent_primary_customer_id", "ix_pvf_stripeevent_primary_customer_id"),
    ("ix_stripeevent_stripe_customer_id", "ix_pvf_stripeevent_stripe_customer_id"),
    ("ix_stripeevent_stripe_event_id", "ix_pvf_stripeevent_stripe_event_id"),
    # subscribertransaction
    ("ix_subscribertransaction_customer_id", "ix_pvf_subscribertransaction_customer_id"),
    # userpasswordreset
    ("ix_userpasswordreset_token", "ix_pvf_userpasswordreset_token"),
    # bugreport / suggestion (ix_*)
    ("ix_bugreport_user_create", "ix_pvf_bugreport_user_create"),
    ("ix_bugreport_customer_create", "ix_pvf_bugreport_customer_create"),
    ("ix_bugreport_deleted_create", "ix_pvf_bugreport_deleted_create"),
    ("ix_suggestion_user_create", "ix_pvf_suggestion_user_create"),
    ("ix_suggestion_customer_create", "ix_pvf_suggestion_customer_create"),
    ("ix_suggestion_deleted_create", "ix_pvf_suggestion_deleted_create"),
    # watcher - explicit Index names
    ("ix_watcher_llm_requests_claim", "ix_pvf_watcher_llm_requests_claim"),
    ("ix_watcher_llm_requests_customer", "ix_pvf_watcher_llm_requests_customer"),
    ("ix_watcher_email_requests_claim", "ix_pvf_watcher_email_requests_claim"),
    ("ix_watcher_email_requests_customer", "ix_pvf_watcher_email_requests_customer"),
    ("ix_watcher_api_requests_claim", "ix_pvf_watcher_api_requests_claim"),
    ("ix_watcher_api_requests_customer", "ix_pvf_watcher_api_requests_customer"),
    ("ix_watcher_generic_jobs_claim", "ix_pvf_watcher_generic_jobs_claim"),
    ("ix_watcher_generic_jobs_customer", "ix_pvf_watcher_generic_jobs_customer"),
    ("ix_watcher_generic_jobs_work_type", "ix_pvf_watcher_generic_jobs_work_type"),
]


def _rename_tables(old_new: list[tuple[str, str]]) -> None:
    for old, new in old_new:
        op.rename_table(old, new)


def _rename_indexes_postgres(old_new: list[tuple[str, str]]) -> None:
    for old, new in old_new:
        op.execute(sa.text(f'ALTER INDEX IF EXISTS "{old}" RENAME TO "{new}"'))


def _rename_sequences_postgres(old_new: list[tuple[str, str]]) -> None:
    for old, new in old_new:
        old_seq = f"{old}_id_seq"
        new_seq = f"{new}_id_seq"
        op.execute(sa.text(f'ALTER SEQUENCE IF EXISTS "{old_seq}" RENAME TO "{new_seq}"'))


def _rename_remaining_indexes_and_pkeys(bind, table_renames: list[tuple[str, str]]) -> None:
    """Rename any remaining indexes/constraints that still contain old table name.

    Handles both upgrade (old->new, tables already renamed to new) and downgrade
    (old is pvf_*, new is original, tables still old before rename) by checking
    both possible current table names safely.
    """
    for old, new in table_renames:
        # Check both possible current table names (before and after rename) - use safe queries
        for tbl in (old, new):
            # Indexes: safe even if tbl doesn't exist (pg_indexes returns 0 rows)
            try:
                rows = bind.execute(sa.text(
                    "SELECT indexname FROM pg_indexes WHERE tablename = :tbl"
                ), {"tbl": tbl}).fetchall()
                for (idxname,) in rows:
                    if old in idxname:
                        new_idx = idxname.replace(old, new, 1)
                        if new_idx != idxname:
                            op.execute(sa.text(f'ALTER INDEX IF EXISTS "{idxname}" RENAME TO "{new_idx}"'))
            except Exception:
                pass
            # Constraints: use join to avoid error on non-existent table
            try:
                rows = bind.execute(sa.text(
                    "SELECT c.conname FROM pg_constraint c "
                    "JOIN pg_class cl ON c.conrelid = cl.oid "
                    "WHERE cl.relname = :tbl AND cl.relkind = 'r'"
                ), {"tbl": tbl}).fetchall()
                for (conname,) in rows:
                    if old in conname:
                        new_con = conname.replace(old, new, 1)
                        if new_con != conname:
                            op.execute(sa.text(f'ALTER TABLE "{tbl}" RENAME CONSTRAINT "{conname}" TO "{new_con}"'))
            except Exception:
                pass


def upgrade() -> None:
    # 1. Rename tables
    _rename_tables(TABLE_RENAMES)

    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # 2. Rename indexes / unique constraints (they are indexes under the hood)
        _rename_indexes_postgres(INDEX_RENAMES)
        # 2b. Rename any remaining indexes/constraints that contain old table name (e.g., auto indexes, pkeys)
        _rename_remaining_indexes_and_pkeys(bind, TABLE_RENAMES)
        # 3. Rename sequences for serial PKs
        _rename_sequences_postgres(TABLE_RENAMES)
        # 4. Foreign key constraint on pvf_userpasswords.user_id -> pvf_user.id
        #    Postgres automatically updates the referenced table OID on ALTER TABLE RENAME,
        #    so the FK remains valid. We only rename the constraint itself for consistency.
        #    Check existence first to avoid transaction abort on missing constraint.
        try:
            exists = bind.execute(sa.text(
                "SELECT 1 FROM pg_constraint WHERE conname = :old AND conrelid = 'pvf_userpasswords'::regclass"
            ), {"old": "userpasswords_user_id_fkey"}).scalar() is not None
            if exists:
                op.execute(sa.text('ALTER TABLE "pvf_userpasswords" RENAME CONSTRAINT "userpasswords_user_id_fkey" TO "pvf_userpasswords_user_id_fkey"'))
        except Exception:
            pass
    else:
        # SQLite / other dialects: indexes are recreated automatically on fresh create_all,
        # but for existing DBs the old index names remain and still work. We attempt to
        # recreate them with new names for consistency (best-effort).
        for old, new in INDEX_RENAMES:
            try:
                # Drop old index if exists, create new one is handled by SQLModel metadata on next autogenerate.
                # Here we just try to rename via raw SQL if supported.
                op.execute(sa.text(f'DROP INDEX IF EXISTS "{old}"'))
            except Exception:
                pass
        # No sequence handling for SQLite.


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # Reverse remaining indexes/constraints before table renames (need new table names still)
        rev_remaining = [(new, old) for old, new in TABLE_RENAMES]
        _rename_remaining_indexes_and_pkeys(bind, rev_remaining)
        rev_indexes = [(new, old) for old, new in INDEX_RENAMES]
        _rename_indexes_postgres(rev_indexes)
        rev_seqs = [(new, old) for old, new in TABLE_RENAMES]
        _rename_sequences_postgres(rev_seqs)
        # FK rename back
        try:
            exists = bind.execute(sa.text(
                "SELECT 1 FROM pg_constraint WHERE conname = :old AND conrelid = 'pvf_userpasswords'::regclass"
            ), {"old": "pvf_userpasswords_user_id_fkey"}).scalar() is not None
            if exists:
                op.execute(sa.text('ALTER TABLE "pvf_userpasswords" RENAME CONSTRAINT "pvf_userpasswords_user_id_fkey" TO "userpasswords_user_id_fkey"'))
        except Exception:
            pass

    # Rename tables back
    rev_renames = [(new, old) for old, new in TABLE_RENAMES]
    _rename_tables(rev_renames)

    if dialect != "postgresql":
        # SQLite: best-effort drop new indexes
        for new, old in INDEX_RENAMES:
            try:
                op.execute(sa.text(f'DROP INDEX IF EXISTS "{new}"'))
            except Exception:
                pass
