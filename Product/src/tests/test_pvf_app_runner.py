"""Tests for pvf_app_runner: composition, DI integrity enforcement, and startup failure modes."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import APIRouter, Depends, FastAPI

from src.pvf.depends.check_user_session_jwt_dependencies import get_current_user
from src.pvf.bindings.pvf_invocation import PvfAppTarget
from src.pvf.utils.dependency_integrity import verify_app_dependency_integrity

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = REPO_ROOT / "src" / ".venv" / "bin" / "python"


# --- dependency integrity (synthetic apps) ------------------------------------

def _app_with_route(*, guard=None, tags=None, path="/thing"):
    app = FastAPI()
    router = APIRouter()
    if guard is None:
        @router.get(path, tags=tags or [])
        async def thing():
            return True
    else:
        @router.get(path, tags=tags or [])
        async def thing_guarded(ctx=Depends(guard)):
            return True
    app.include_router(router)
    return app


def test_session_app_requires_session_guard():
    with pytest.raises(RuntimeError, match="missing required session-JWT dependency"):
        verify_app_dependency_integrity(_app_with_route(), "session")


def test_session_app_accepts_session_guard():
    verify_app_dependency_integrity(_app_with_route(guard=get_current_user), "session")


def test_external_app_requires_signed_header_guard():
    with pytest.raises(RuntimeError, match="missing required signed-header dependency"):
        verify_app_dependency_integrity(_app_with_route(), "external")


def test_noauth_and_share_apps_forbid_guards():
    for target in ("noauth", "share"):
        with pytest.raises(RuntimeError, match="must not require"):
            verify_app_dependency_integrity(_app_with_route(guard=get_current_user), target)


def test_exemptions_skip_status_and_test_helpers():
    verify_app_dependency_integrity(_app_with_route(path="/status"), "session")
    verify_app_dependency_integrity(_app_with_route(tags=["test-helpers"]), "session")


# --- composed application (via the running test app) ---------------------------

def test_four_apps_composed_and_mounted():
    from src.pvf.pvf_app_runner import MOUNT_PREFIXES, composed_apps

    assert set(composed_apps) == {"root", "noauth", "session", "share", "external"}
    assert MOUNT_PREFIXES == {"noauth": "/auth-ws", "session": "/ws", "share": "/ext-ws", "external": "/api"}
    mounted_prefixes = {getattr(route, "path", None) for route in composed_apps["root"].routes}
    for prefix in MOUNT_PREFIXES.values():
        assert prefix in mounted_prefixes


def test_sessions_openapi_aggregate_covers_all_browser_surfaces(client):
    spec = client.get("/session/docs.json").json()
    paths = set(spec["paths"])
    assert any(p.startswith("/auth-ws/") for p in paths)
    assert any(p.startswith("/ws/") for p in paths)
    assert any(p.startswith("/ext-ws/") for p in paths)
    assert "/status" in paths  # root app surface


def test_reserved_prefix_404_is_json_but_spa_fallback_served(client):
    response = client.get("/ws/definitely-not-a-route")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")

    response = client.get("/some/client-side/route")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# --- startup failure modes (subprocess for isolation) ---------------------------

def _run_runner_subprocess(env_overrides: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env.update(env_overrides)
    return subprocess.run(
        [str(PYTHON), "-c", "from src.pvf.pvf_app_runner import app"],
        capture_output=True, text=True, env=env, cwd=REPO_ROOT, timeout=120,
    )


def test_missing_startup_yaml_exits_with_error_code(tmp_path):
    result = _run_runner_subprocess({"PVF_STARTUP_CONFIG": str(tmp_path / "missing.yaml")})
    assert result.returncode == 2
    assert "not found" in result.stderr


def test_bad_shell_module_exits_with_error_code(tmp_path):
    config = tmp_path / "bad_shell.yaml"
    config.write_text("application:\n  shell_module: src.no_such_shell_module\n")
    result = _run_runner_subprocess({"PVF_STARTUP_CONFIG": str(config)})
    assert result.returncode == 4
    assert "could not import application shell module" in result.stderr


def test_shell_error_return_exits_with_error_code(tmp_path):
    shell = tmp_path / "failing_shell.py"
    shell.write_text("def app_startup(invocation):\n    return 'deliberate failure for testing'\n")
    config = tmp_path / "failing.yaml"
    config.write_text(f"application:\n  shell_module: failing_shell\n")
    env = {"PVF_STARTUP_CONFIG": str(config), "PYTHONPATH": f"{REPO_ROOT}:{tmp_path}"}
    result = _run_runner_subprocess(env)
    assert result.returncode == 4
    assert "deliberate failure for testing" in result.stderr


def test_database_failure_exits_with_error_code():
    result = _run_runner_subprocess({
        "DB_PATH_OR_CONNECTION_STRING": "postgresql+psycopg://powerchoice:bad_password@localhost:59999/powerchoice",
        "SERVER_ENV": "production",  # prevent .env override of DB_PATH in non-prod helper
    })
    assert result.returncode == 3
    assert "could not establish a connection to the database" in result.stderr
    assert "bad_password" not in result.stderr  # DSN password is masked in diagnostics
