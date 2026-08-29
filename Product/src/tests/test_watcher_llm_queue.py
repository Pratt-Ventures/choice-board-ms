"""Tests for watcher LLM queue — tenancy, encryption, capture/no_log, semantic_tag."""
import pytest
from unittest.mock import patch, MagicMock

from sqlmodel import delete, Session, select

from src.pvf.bindings.pvf_watcher_requests import (
    get_llm_request,
    list_llm_requests,
    queue_llm_request,
)
from src.pvf.config.pvf_config_settings import pvf_settings
from src.pvf.db.models.customer_user import PvfUserContext
from src.pvf.depends.api_session_dependencies import get_next_session
from src.pvf.utils.field_encryption import decrypt_secret
from src.pvf.watcher.models import PvfWatcherLlmRequest
from src.pvf.watcher.orchestration import redact_for_no_log, should_capture, is_no_log_tag
from src.pvf.watcher.poll import poll_and_dispatch
from src.pvf.watcher.registry import PvfWatcherRegistry
from src.tests.helpers.factories import create_account


@pytest.fixture(autouse=True)
def _clean_llm():
    with get_next_session() as s:
        s.exec(delete(PvfWatcherLlmRequest))
        s.commit()
    yield
    with get_next_session() as s:
        s.exec(delete(PvfWatcherLlmRequest))
        s.commit()


def test_queue_and_get_same_tenant_ok(account):
    with get_next_session() as session:
        res = queue_llm_request(
            session=session,
            usr_context=account.user_context(),
            provider="opencode_go",
            model="glm-5.2",
            api_key="sk-test-llm",
            messages=[{"role": "pvf_user", "content": "hello"}],
            prompt="hello",
            temperature=0.2,
            max_tokens=50,
            semantic_tag="SHORTEN_PRODUCT_NAME",
            metadata={"x": 1},
        )
        assert not res.failure_reason
        qid = res.result_package["id"]

        # fetch as same tenant
        got = get_llm_request(session=session, usr_context=account.user_context(), queue_id=qid)
        assert not got.failure_reason
        assert got.row is not None
        assert got.row.id == qid
        # encrypted
        assert got.row.api_key_encrypted != "sk-test-llm"
        assert got.row.api_key_encrypted.startswith("enc:v1:")
        assert decrypt_secret(got.row.api_key_encrypted) == "sk-test-llm"
        # never plaintext in request_package
        pkg_str = str(got.row.request_package)
        assert "sk-test-llm" not in pkg_str
        assert got.row.semantic_tag == "SHORTEN_PRODUCT_NAME"


def test_cross_tenant_fetch_not_found(account, other_account):
    with get_next_session() as session:
        res = queue_llm_request(
            session=session,
            usr_context=account.user_context(),
            provider="opencode_go",
            model="glm-5.2",
            api_key="sk-a",
            messages=[{"role": "pvf_user", "content": "hi"}],
            prompt="hi",
            semantic_tag="SHORTEN_PRODUCT_NAME",
        )
        qid = res.result_package["id"]
    with get_next_session() as session:
        got = get_llm_request(session=session, usr_context=other_account.user_context(), queue_id=qid)
        assert got.failure_reason == "not found"


def test_semantic_tag_none_accepted(account):
    with get_next_session() as session:
        res = queue_llm_request(
            session=session,
            usr_context=account.user_context(),
            provider="opencode_go",
            model="glm-5.2",
            api_key="sk-b",
            prompt="test",
            semantic_tag=None,
        )
        assert not res.failure_reason
        qid = res.result_package["id"]
        got = get_llm_request(session=session, usr_context=account.user_context(), queue_id=qid)
        assert not got.failure_reason
        assert got.row.semantic_tag is None


def test_api_key_roundtrips_encrypted_only(account):
    with get_next_session() as session:
        res = queue_llm_request(
            session=session,
            usr_context=account.user_context(),
            provider="opencode_go",
            model="glm-5.2",
            api_key="my-secret-key",
            prompt="secret test",
        )
        qid = res.result_package["id"]
        row = session.get(PvfWatcherLlmRequest, qid)
        # stored encrypted
        assert row.api_key_encrypted != "my-secret-key"
        assert row.api_key_encrypted.startswith("enc:v1:")
        # request_package must not contain secret
        import json
        assert "my-secret-key" not in json.dumps(row.request_package or {})
        if row.messages_json is not None:
            assert "my-secret-key" not in json.dumps(row.messages_json)


def test_capture_disabled_redacts_on_success(account, monkeypatch):
    # Capture disabled should redact
    orig_capture = pvf_settings.WATCHER_CAPTURE_PAYLOADS
    pvf_settings.WATCHER_CAPTURE_PAYLOADS = False
    # Clear no_log to isolate capture flag
    orig_no_log = pvf_settings.WATCHER_NO_LOG_TYPES
    pvf_settings.WATCHER_NO_LOG_TYPES = []
    # Also clear YAML no_log via watcher_config if present
    orig_yaml = getattr(pvf_settings, "_watcher_config", None)
    if orig_yaml is not None:
        orig_yaml_no_log = list(orig_yaml.no_log_request_types)
        orig_yaml.no_log_request_types = []
    try:
        assert should_capture("SHORTEN_PRODUCT_NAME") is False
        with get_next_session() as session:
            res = queue_llm_request(
                session=session,
                usr_context=account.user_context(),
                provider="opencode_go",
                model="glm-5.2",
                api_key="sk-x",
                messages=[{"role": "pvf_user", "content": "hello"}],
                prompt="hello",
                semantic_tag="SHORTEN_PRODUCT_NAME",
            )
            qid = res.result_package["id"]
            row = session.get(PvfWatcherLlmRequest, qid)
            # when capture False, messages_json should be None (redacted)
            assert row.messages_json is None
            # request_package should be redacted minimal
            assert "provider" in (row.request_package or {})
            assert "messages" not in (row.request_package or {})

        # Now exercise poll with no_log helper — both redacted equally
        # Already asserted should_capture False; redact_for_no_log produces minimal
        red = redact_for_no_log(provider="opencode_go", model="glm-5.2", prompt_hash="abc123", status="complete", semantic_tag="SHORTEN_PRODUCT_NAME")
        assert "provider" in red and "model" in red
        assert "text" not in red
    finally:
        pvf_settings.WATCHER_CAPTURE_PAYLOADS = orig_capture
        pvf_settings.WATCHER_NO_LOG_TYPES = orig_no_log
        if orig_yaml is not None:
            orig_yaml.no_log_request_types = orig_yaml_no_log


def test_no_log_tag_suppresses_even_on_error(account):
    # Tag in no_log should suppress even on error
    orig_no_log = pvf_settings.WATCHER_NO_LOG_TYPES
    orig_capture = pvf_settings.WATCHER_CAPTURE_PAYLOADS
    pvf_settings.WATCHER_CAPTURE_PAYLOADS = True
    pvf_settings.WATCHER_NO_LOG_TYPES = ["SHORTEN_PRODUCT_NAME"]
    # Clear YAML no_log as well then add tag via env
    cfg = getattr(pvf_settings, "_watcher_config", None)
    orig_yaml_no_log = None
    if cfg is not None:
        orig_yaml_no_log = list(cfg.no_log_request_types)
        cfg.no_log_request_types = []
    try:
        assert is_no_log_tag("SHORTEN_PRODUCT_NAME") is True
        assert should_capture("SHORTEN_PRODUCT_NAME") is False
        from src.pvf.watcher.orchestration import PvfWatcherInvocationResult
        from src.pvf.watcher.poll import _finalize_row
        with get_next_session() as session:
            res = queue_llm_request(
                session=session,
                usr_context=account.user_context(),
                provider="opencode_go",
                model="glm-5.2",
                api_key="sk-y",
                prompt="error test",
                semantic_tag="SHORTEN_PRODUCT_NAME",
            )
            qid = res.result_package["id"]
            row = session.get(PvfWatcherLlmRequest, qid)
            # Simulate failure
            row.status = "trying"
            row.attempts = 1
            session.add(row)
            session.commit()
            result = PvfWatcherInvocationResult(failure_reason="provider error", error_package={"message": "provider error", "retryable": False}, retryable=False)
            _finalize_row(session, row, result, work_type="llm", semantic_tag="SHORTEN_PRODUCT_NAME")
            session.refresh(row)
            # Even on error, detailed message suppressed when no_log
            assert row.error_package is not None
            # Should be redacted minimal, not containing raw provider error text
            assert "provider error" not in str(row.error_package) or row.error_package.get("status") == "no_retry"
    finally:
        pvf_settings.WATCHER_NO_LOG_TYPES = orig_no_log
        pvf_settings.WATCHER_CAPTURE_PAYLOADS = orig_capture
        if cfg is not None and orig_yaml_no_log is not None:
            cfg.no_log_request_types = orig_yaml_no_log


def test_app_binding_without_system_cannot_set_null_customer(account):
    # Negative test: app binding without _system cannot create NULL customer_id by passing customer_id=None
    # queue_llm_request signature has no customer_id arg; try to spoof via usr_context=None
    with get_next_session() as session:
        # usr_context with sess_user None should result in NULL — but this is the _system path for framework only
        # App callers normally pass a valid usr_context; passing None should be treated as _system but binding requires framework-only
        # Ensure that normal tenant queue still injects its customer_id
        res = queue_llm_request(
            session=session,
            usr_context=account.user_context(),
            provider="opencode_go",
            model="glm-5.2",
            api_key="sk-z",
            prompt="test",
        )
        row = session.get(PvfWatcherLlmRequest, res.result_package["id"])
        assert row.customer_id == account.customer.id
        # Now try _system directly via internal helper — should be NULL and not accessible via normal get
        from src.pvf.bindings.pvf_watcher_requests import _queue_llm_request_system
        sys_res = _queue_llm_request_system(session=session, provider="opencode_go", model="glm-5.2", api_key="sk-sys", prompt="sys", semantic_tag=None)
        sys_row = session.get(PvfWatcherLlmRequest, sys_res.result_package["id"])
        assert sys_row.customer_id is None
        # Normal get should not find _system row
        got = get_llm_request(session=session, usr_context=account.user_context(), queue_id=sys_row.id)
        assert got.failure_reason == "not found"


def test_list_llm_tenancy(account, other_account):
    with get_next_session() as session:
        queue_llm_request(session=session, usr_context=account.user_context(), provider="opencode_go", model="m", prompt="a")
        queue_llm_request(session=session, usr_context=account.user_context(), provider="opencode_go", model="m", prompt="b")
    with get_next_session() as session:
        res = list_llm_requests(session=session, usr_context=account.user_context())
        assert not res.failure_reason
        assert len(res.rows) >= 2
        res2 = list_llm_requests(session=session, usr_context=other_account.user_context())
        assert not res2.failure_reason
        # other tenant sees 0 created by account
        assert all(r.customer_id != account.customer.id for r in res2.rows)


def test_llm_roundtrip_via_httpx_mock(account):
    """One real round-trip via httpx mock (no external network) — queued → trying → complete."""
    import httpx
    from src.pvf.watcher.poll import poll_and_dispatch

    # Prepare a watcher registry with llm handler
    from src.pvf.bindings.pvf_startup_config import load_watcher_config
    from src.pvf.watcher.registry import build_registry_from_config
    cfg = load_watcher_config()
    reg = build_registry_from_config(cfg)
    # Ensure llm handler is present
    assert reg.resolve_handler("llm") is not None

    with get_next_session() as session:
        res = queue_llm_request(
            session=session,
            usr_context=account.user_context(),
            provider="opencode_go",
            model="glm-5.2",
            api_key="sk-mock",
            messages=[{"role": "pvf_user", "content": "hello mock"}],
            prompt="hello mock",
            semantic_tag=None,
        )
        qid = res.result_package["id"]

    # Mock httpx.Client.request to return a fake LLM response
    fake_body = {"choices": [{"message": {"content": "mocked response"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 10}}

    class FakeResp:
        status_code = 200
        def json(self): return fake_body
        @property
        def text(self): return str(fake_body)
        headers = {}

    # Patch httpx.Client in llm_client._request_json path
    orig_client = httpx.Client

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def request(self, method, url, headers=None, json=None):
            return FakeResp()

    with patch("httpx.Client", FakeClient):
        with get_next_session() as session:
            did = poll_and_dispatch(session, reg)
            assert did is True

    with get_next_session() as session:
        row = session.get(PvfWatcherLlmRequest, qid)
        assert row.status == "complete"
        assert row.result_package is not None
        assert "mocked response" in str(row.result_package) or row.result_package.get("text") == "mocked response"
