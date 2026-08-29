"""Alembic environment — thin shim over pvf_get_alembic_config.

All database configuration orchestration (startup YAML, env file, model imports,
metadata merge) lives in src/pvf/pvf_get_alembic_config.py.
"""
from logging.config import fileConfig
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from alembic import context

# Enables autogenerate detection of PostgreSQL ENUM create/alter/drop
import alembic_postgresql_enum  # noqa: F401

from src.pvf.pvf_get_alembic_config import get_alembic_runtime, run_migrations_offline, run_migrations_online

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

runtime = get_alembic_runtime()

if context.is_offline_mode():
    run_migrations_offline(context, runtime)
else:
    run_migrations_online(context, runtime)
