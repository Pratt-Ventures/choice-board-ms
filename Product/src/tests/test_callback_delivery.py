"""Tests for the generic webhook callback delivery machinery (watcher path)."""
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from src.pvf.config.pvf_config_settings import pvf_settings
from src.pvf.db.models.api_access_configuration import (
    PvfApiWebInvocationEvent,
    PvfWebHookStatus,
)
from src.pvf.depends.api_session_dependencies import get_next_session
from src.pvf.bindings.pvf_invocation import get_hooks
from src.pvf.utils import callback_delivery
from src.pvf.utils.callback_delivery import (
    check_for_callbacks_ready,
    get_callback_proxy_usr_context,
    perform_callback,
)
from src.tests.helpers.factories import create_api_key, uid

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _clean_callback_events():
    """The ready-check scans the whole event table; isolate each test."""
    from sqlmodel import delete
    with get_next_session() as session:
        session.exec(delete(PvfApiWebInvocationEvent))
        session.commit()
    yield
    with get_next_session() as session:
        session.exec(delete(PvfApiWebInvocationEvent))
        session.commit()


def _backdate(event_id, minutes=10):
    """Make an event immediately eligible under the first retry-delay gate."""
    from datetime import datetime, timedelta
    with get_next_session() as session:
        event = session.get(PvfApiWebInvocationEvent, event_id)
        event.modify_date = datetime.now() - timedelta(minutes=minutes)
        session.add(event)
        session.commit()


def _enqueue(account, web_hook_type="test_event", payload_params=None):
    """Create an API key + queued callback event for the account."""
    from sqlmodel import select
    from src.pvf.db.models.api_access_configuration import PvfApiAccessConfiguration

    key_id, _, _ = create_api_key(account)
    with get_next_session() as session:
        api_config = session.exec(
            select(PvfApiAccessConfiguration).where(PvfApiAccessConfiguration.authentication_key_id == key_id)
        ).one()
        api_config.webhook_endpoint = "https://hooks.example.test/callback"
        session.add(api_config)
        session.commit()
        config_id = api_config.id
        from src.pvf.db.models.customer_user import PvfUserContext
        result = PvfApiWebInvocationEvent.enqueue_callback_event(
            session=session,
            usr_context=PvfUserContext(limited_proxy=True),
            api_config=api_config,
            web_hook_type=web_hook_type,
            payload_params=payload_params,
            requesting_transaction_tag=uid("txn"),
            clear_lock=False,
        )
        assert not result.failure_reason, result.failure_reason
        event_id = result.api_event_info.id
        tracking_id = result.api_event_info.unique_tracking_id
    return config_id, event_id, tracking_id


def _get_event(event_id):
    with get_next_session() as session:
        return session.get(PvfApiWebInvocationEvent, event_id)


def test_enqueue_callback_event(account):
    _, event_id, tracking_id = _enqueue(account, payload_params={"project_id": 42})
    event = _get_event(event_id)
    assert event.web_hook_status == PvfWebHookStatus.pending
    assert event.web_hook_type == "test_event"
    assert event.payload_params_json == {"project_id": 42}
    assert event.unique_tracking_id == tracking_id
    assert event.web_hook_delivery_attempts == 0


def test_check_for_callbacks_ready_transitions_to_trying(account):
    _, event_id, _ = _enqueue(account)
    _backdate(event_id)
    with get_next_session() as session:
        ready = check_for_callbacks_ready(session=session)
    assert ready is not None and len(ready) == 1
    event = _get_event(event_id)
    assert event.web_hook_status == PvfWebHookStatus.trying
    assert event.web_hook_delivery_attempts == 1


def test_check_for_callbacks_ready_honors_readiness_predicate(account, monkeypatch):
    _, event_id, _ = _enqueue(account, web_hook_type="gated_event")
    _backdate(event_id)
    hooks = get_hooks()
    monkeypatch.setitem(hooks.webhook_readiness_predicates, "gated_event", lambda session, event: False)
    with get_next_session() as session:
        ready = check_for_callbacks_ready(session=session)
    assert ready is None
    assert _get_event(event_id).web_hook_status == PvfWebHookStatus.pending

    monkeypatch.setitem(hooks.webhook_readiness_predicates, "gated_event", lambda session, event: True)
    with get_next_session() as session:
        ready = check_for_callbacks_ready(session=session)
    assert ready is not None and len(ready) == 1


def test_check_for_callbacks_ready_marks_max_attempts_failed(account):
    _, event_id, _ = _enqueue(account)
    _backdate(event_id)
    with get_next_session() as session:
        event = session.get(PvfApiWebInvocationEvent, event_id)
        event.web_hook_delivery_attempts = pvf_settings.WATCHER_PROCESS_API_CALLBACKS_MAXIMUM_ATTEMPTS
        session.add(event)
        session.commit()
        ready = check_for_callbacks_ready(session=session)
    assert ready is None
    assert _get_event(event_id).web_hook_status == PvfWebHookStatus.failed


def test_perform_callback_delivers_signed_payload(account, monkeypatch):
    config_id, event_id, tracking_id = _enqueue(account, payload_params={"a": 1})
    monkeypatch.setitem(get_hooks().webhook_payload_builders, "test_event",
                        lambda session, event: {"tracking": event.unique_tracking_id, "params": event.payload_params_json})

    event = _get_event(event_id)
    with get_next_session() as session:
        proxy = get_callback_proxy_usr_context(session=session, api_event_info=event)
    assert proxy is not None
    assert proxy.sess_api_access_config.id == config_id

    class _Response:
        status_code = 200
        content = b'{"ok": true}'
        text = '{"ok": true}'
        reason = "OK"
        def json(self):
            return {"ok": True}

    with patch.object(callback_delivery.requests, "post", return_value=_Response()) as mock_post:
        with get_next_session() as session:
            result = perform_callback(session=session, proxy_usr_context=proxy, api_event=event)
    assert result is None
    assert _get_event(event_id).web_hook_status == PvfWebHookStatus.delivered

    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["content-type"] == "application/json"
    assert "t=" in kwargs["headers"]["X-api-request-signature"]
    assert kwargs["headers"]["X-api-request-authentication"].startswith("cb-")


def test_perform_callback_failure_returns_to_pending(account, monkeypatch):
    _, event_id, _ = _enqueue(account)
    monkeypatch.setitem(get_hooks().webhook_payload_builders, "test_event", lambda session, event: {"x": 1})

    event = _get_event(event_id)
    with get_next_session() as session:
        proxy = get_callback_proxy_usr_context(session=session, api_event_info=event)

    with patch.object(callback_delivery.requests, "post", side_effect=ConnectionError("refused")):
        with get_next_session() as session:
            result = perform_callback(session=session, proxy_usr_context=proxy, api_event=event)
    assert result is not None and "refused" in result
    event = _get_event(event_id)
    assert event.web_hook_status == PvfWebHookStatus.pending  # retryable
    assert "refused" in event.web_hook_failure_reason


def test_perform_callback_unknown_type_is_descriptive(account):
    _, event_id, _ = _enqueue(account, web_hook_type="unregistered_type")
    event = _get_event(event_id)
    with get_next_session() as session:
        proxy = get_callback_proxy_usr_context(session=session, api_event_info=event)
        result = perform_callback(session=session, proxy_usr_context=proxy, api_event=event)
    assert "no registered payload builder" in result


def test_watcher_module_imports_and_binds_hooks():
    """The watcher is a separate process; verify it boots its bindings standalone."""
    result = subprocess.run(
        [str(REPO_ROOT / "src" / ".venv" / "bin" / "python"), "-c",
         "from src.pvf.pvf_watcher_runner import build_invocation; inv=build_invocation(); "
         "from src.pvf.bindings.pvf_invocation import get_hooks; "
         "assert get_hooks().entity_resolver is not None; "
         "print('watcher bindings OK')"],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(REPO_ROOT), "HOME": str(Path.home())},
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "watcher bindings OK" in result.stdout


def test_watcher_service_registry_roundtrip():
    """Extend callback delivery: verify PVF watcher service imports and registry round-trip."""
    from src.pvf.watcher.service import run_watcher_forever  # noqa: F401
    from src.pvf.watcher.registry import PvfWatcherRegistry, build_registry_from_config
    from src.pvf.bindings.pvf_startup_config import load_watcher_config, WatcherTypeSpec
    from src.pvf.bindings.pvf_invocation import get_current_invocation, set_current_invocation

    # App runner already built a PvfInvocation with watcher_registry — save it
    orig_inv = get_current_invocation()
    assert orig_inv is not None
    assert hasattr(orig_inv, "watcher_registry")
    reg = orig_inv.watcher_registry
    assert isinstance(reg, PvfWatcherRegistry)
    assert "llm" in reg.watcher_types
    assert "outbound_email" in reg.watcher_types
    assert "outbound_api_call" in reg.watcher_types

    # Registry can shadow builtins and resolve handlers
    cfg = load_watcher_config()
    fresh = build_registry_from_config(cfg)
    assert fresh.resolve_handler("llm") is not None
    # generic handler dispatched via app_shell should be present on the live inv
    assert reg.resolve_handler("SHORTEN_PRODUCT_NAME") is not None
    # Also test that the canonical watcher runner builds same registry (restore afterwards)
    try:
        from src.pvf.pvf_watcher_runner import build_invocation
        inv2 = build_invocation()
        assert inv2.watcher_registry.resolve_handler("llm") is not None
    finally:
        set_current_invocation(orig_inv)
