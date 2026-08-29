"""API queue tenancy + connection_protocol/auth_protocol defaults."""
from sqlmodel import delete
from src.pvf.bindings.pvf_watcher_requests import queue_api_request, get_api_request, list_api_requests
from src.pvf.depends.api_session_dependencies import get_next_session
from src.pvf.watcher.models import PvfWatcherApiRequest
from src.pvf.utils.field_encryption import decrypt_secret
import json
import pytest

@pytest.fixture(autouse=True)
def _clean():
    with get_next_session() as s:
        s.exec(delete(PvfWatcherApiRequest))
        s.commit()
    yield
    with get_next_session() as s:
        s.exec(delete(PvfWatcherApiRequest))
        s.commit()

def test_api_queue_defaults_and_tenancy(account, other_account):
    with get_next_session() as session:
        res = queue_api_request(session=session, usr_context=account.user_context(), target_url="https://example.com/hook", http_method="POST", auth_params={"k": "v"}, payload={"event": "x"}, headers={"x": "y"}, semantic_tag=None)
        assert not res.failure_reason
        qid = res.result_package["id"]
        row = session.get(PvfWatcherApiRequest, qid)
        assert row.connection_protocol == "pvf"
        assert row.auth_protocol == "pvf"
        assert row.target_url == "https://example.com/hook"
        assert row.http_method == "POST"
        # encrypted
        assert row.auth_params_encrypted.startswith("enc:v1:")
        assert json.loads(decrypt_secret(row.auth_params_encrypted)) == {"k": "v"}
        # tenancy
        got = get_api_request(session=session, usr_context=account.user_context(), queue_id=qid)
        assert not got.failure_reason
        assert got.row.id == qid
        got2 = get_api_request(session=session, usr_context=other_account.user_context(), queue_id=qid)
        assert got2.failure_reason == "not found"

def test_api_v1_protocols_always_pvf(account):
    with get_next_session() as session:
        res = queue_api_request(session=session, usr_context=account.user_context(), target_url="https://example.com/hook2", connection_protocol="pvf", auth_protocol="pvf", payload={})
        row = session.get(PvfWatcherApiRequest, res.result_package["id"])
        assert row.connection_protocol == "pvf"
        assert row.auth_protocol == "pvf"

def test_api_list_and_system(account):
    with get_next_session() as session:
        queue_api_request(session=session, usr_context=account.user_context(), target_url="https://example.com/a", payload={})
        lst = list_api_requests(session=session, usr_context=account.user_context())
        assert not lst.failure_reason
        assert len(lst.rows) >= 1
        # _system
        from src.pvf.bindings.pvf_watcher_requests import _queue_api_request_system
        sys_res = _queue_api_request_system(session=session, target_url="https://example.com/sys", payload={})
        sys_row = session.get(PvfWatcherApiRequest, sys_res.result_package["id"])
        assert sys_row.customer_id is None
        got = get_api_request(session=session, usr_context=account.user_context(), queue_id=sys_row.id)
        assert got.failure_reason == "not found"
