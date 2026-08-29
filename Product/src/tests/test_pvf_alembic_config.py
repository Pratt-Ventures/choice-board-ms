"""Tests for pvf_get_alembic_config: metadata export and the thin alembic env.py."""
import os
import subprocess
from pathlib import Path

from src.pvf.config.pvf_config_settings import pvf_settings
from src.pvf.pvf_get_alembic_config import get_alembic_runtime

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {
    # pvf core
    "pvf_customer", "pvf_user", "pvf_userpasswords", "pvf_userpasswordreset",
    "pvf_applicationlogevent", "pvf_usersessionlog", "pvf_emailactivitylog",
    # pvf feature tables (always migrated, even when the feature is off at runtime)
    "pvf_stripeevent", "pvf_subscribertransaction", "pvf_customerbrandingimage", "pvf_projectbrandingimage",
    # application
    "customerproject", "customerprojectalternatives", "customerprojectfactors",
    "customerfactortemplates", "pvf_sharelink", "pvf_sharelinkmagickey", "pvf_sharelinkaccessed",
    "pvf_apiaccessconfiguration", "pvf_apiwebinvocationevent",
    "projectvoteparticipant", "projectvotegroupresult",
}


def test_alembic_runtime_exports_full_schema():
    original_bootstrap = pvf_settings.BOOTSTRAP_SAMPLE_DATA
    try:
        runtime = get_alembic_runtime()
        tables = set(runtime.target_metadata.tables)
        missing = EXPECTED_TABLES - tables
        assert not missing, f"missing tables in exported metadata: {sorted(missing)}"
        assert runtime.db_url == pvf_settings.DB_PATH_OR_CONNECTION_STRING
        assert pvf_settings.BOOTSTRAP_SAMPLE_DATA is False  # alembic owns the schema
    finally:
        pvf_settings.BOOTSTRAP_SAMPLE_DATA = original_bootstrap


def test_alembic_env_py_heads_and_current():
    """End-to-end: the thin env.py works through the standard migration scripts."""
    result = subprocess.run(
        ["./.venv/bin/alembic", "heads"],
        capture_output=True, text=True, cwd=REPO_ROOT / "src", timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "(head)" in result.stdout

    result = subprocess.run(
        ["./.venv/bin/alembic", "current"],
        capture_output=True, text=True, cwd=REPO_ROOT / "src", timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "(head)" in result.stdout
