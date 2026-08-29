"""pvf_get_alembic_config — alembic database configuration orchestration.

When alembic needs the database configuration it invokes get_alembic_runtime(), which
reads pvf_app_startup.yaml and orchestrates the steps to export the current
SQLAlchemy/SQLModel database configuration:

  1. load the startup YAML (env file name, application models module)
  2. ingest the env file (alembic always runs as its own process)
  3. apply startup-owned values to pvf_settings and disable sample-data bootstrap
     (alembic owns the schema; create_all must not run)
  4. import ALL pvf model tables (the migrated schema stays complete regardless of
     which features are activated at runtime) plus the application's models_module
  5. return the merged metadata + database URL

Only the paths needed for a proper current schema are loaded — no routers, no FastAPI
applications, no mail/stripe runtime wiring.
"""
import importlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import MetaData

from .bindings.pvf_startup_config import (
    PvfStartupConfig,
    apply_startup_config,
    apply_watcher_config,
    load_startup_config,
    load_watcher_config,
)


@dataclass
class PvfAlembicRuntime:
    target_metadata: MetaData
    db_url: str


def get_alembic_runtime(config_path: str | None = None) -> PvfAlembicRuntime:
    startup_config: PvfStartupConfig = load_startup_config(config_path)

    # env file ingestion (fresh process for alembic invocations)
    from dotenv import load_dotenv

    env_path = Path(startup_config.env_file)
    if not env_path.is_absolute():
        env_path = Path(__file__).resolve().parents[2] / env_path  # pvf -> src -> workspace root
    if env_path.is_file():
        load_dotenv(env_path, override=False)
        if os.environ.get("SERVER_ENV", os.environ.get("ENV", "local")).lower() != "production":
            load_dotenv(env_path, override=True)

    from .config.pvf_config_settings import pvf_settings

    apply_startup_config(startup_config, pvf_settings)
    # watcher critical bindings (optional file — defaults if absent)
    watcher_config = load_watcher_config()
    apply_watcher_config(watcher_config, pvf_settings)
    # Force set this to false so that we don't auto-create a local db. We want Alembic to do that.
    pvf_settings.BOOTSTRAP_SAMPLE_DATA = False

    # Application schema extensions must be declared before any model import, exactly
    # as the runner does, so autogenerate sees the same metadata.
    from .db.model_factory import get_schema_extension_registry

    shell_module = importlib.import_module(startup_config.application.shell_module)
    register_schema_extensions = getattr(shell_module, "register_schema_extensions", None)
    if callable(register_schema_extensions):
        register_schema_extensions(get_schema_extension_registry())

    # All framework tables, so the migrated schema is complete even for features that
    # are deactivated at runtime.
    from .db.models import pvf_bootstrap

    pvf_bootstrap.import_all_models()

    # The application's table specifications, as named in the startup YAML.
    models_module = importlib.import_module(startup_config.application.models_module)

    get_target_metadata = getattr(models_module, "get_target_metadata", None)
    if callable(get_target_metadata):
        target_metadata = get_target_metadata()
    else:
        from sqlmodel import SQLModel

        target_metadata = SQLModel.metadata

    return PvfAlembicRuntime(target_metadata=target_metadata, db_url=pvf_settings.DB_PATH_OR_CONNECTION_STRING)


def run_migrations_offline(context, runtime: PvfAlembicRuntime) -> None:
    """Run migrations in 'offline' mode: emit SQL without a database connection."""
    context.configure(
        url=runtime.db_url,
        target_metadata=runtime.target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online(context, runtime: PvfAlembicRuntime) -> None:
    """Run migrations in 'online' mode against the configured engine.

    FastAPI is run from the root directory and looks for the sqlite db there by default.
    However, alembic is run from the src directory, and creates / migrates files there.  Check
    if the current working directory is 'src' and the database is SQLite.  If so, copy the db file
    from the parent directory to the current working directory, run migrations, and then move it back.
    """
    from .db.connect import PvfDatabaseConnection

    connectable = PvfDatabaseConnection.get_engine()

    cwd = os.getcwd()
    if os.path.basename(cwd) == 'src' and runtime.db_url.startswith('sqlite'):
        db_file = runtime.db_url.split('/')[-1]
        parent_dir = os.path.abspath(os.path.join(cwd, '..'))
        src_db_path = os.path.join(cwd, db_file)
        parent_db_path = os.path.join(parent_dir, db_file)

        # Copy the SQLite database file to the current working directory if it exists in the parent directory
        if os.path.exists(parent_db_path):
            shutil.copy(parent_db_path, src_db_path)

        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=runtime.target_metadata)
            with context.begin_transaction():
                context.run_migrations()

        # Copy the SQLite database file back to the parent directory
        if os.path.exists(src_db_path):
            shutil.move(src_db_path, parent_db_path)
    else:
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=runtime.target_metadata)
            with context.begin_transaction():
                context.run_migrations()
