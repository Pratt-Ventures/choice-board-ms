"""Email queue tenancy + _system bypass."""
from sqlmodel import delete
from src.pvf.bindings.pvf_watcher_requests import queue_email_request, get_email_request, list_email_requests
from src.pvf.depends.api_session_dependencies import get_next_session
from src.pvf.watcher.models import PvfWatcherEmailRequest
from src.tests.helpers.factories import create_account
import pytest

@pytest.fixture(autouse=True)
def _clean():
    with get_next_session() as s:
        s.exec(delete(PvfWatcherEmailRequest))
        s.commit()
    yield
    with get_next_session() as s:
        s.exec(delete(PvfWatcherEmailRequest))
        s.commit()

def test_email_queue_tenancy(account, other_account):
    with get_next_session() as session:
        res = queue_email_request(session=session, usr_context=account.user_context(), to_email="a@example.com", template_type="share_project_vote", params={"x":1}, semantic_tag=None)
        qid = res.result_package["id"]
        got = get_email_request(session=session, usr_context=account.user_context(), queue_id=qid)
        assert not got.failure_reason
        assert got.row.to_email == "a@example.com"
        # cross-tenant
        got2 = get_email_request(session=session, usr_context=other_account.user_context(), queue_id=qid)
        assert got2.failure_reason == "not found"

def test_email_list_tenancy(account):
    with get_next_session() as session:
        queue_email_request(session=session, usr_context=account.user_context(), to_email="b@example.com", template_type="t1", params={})
    with get_next_session() as session:
        lst = list_email_requests(session=session, usr_context=account.user_context())
        assert not lst.failure_reason
        assert len(lst.rows) >= 1

def test_email_system_bypass_framework_only(account):
    with get_next_session() as session:
        # normal injects customer_id
        res = queue_email_request(session=session, usr_context=account.user_context(), to_email="c@example.com", template_type="t1", params={})
        row = session.get(PvfWatcherEmailRequest, res.result_package["id"])
        assert row.customer_id == account.customer.id
        # internal _system
        from src.pvf.bindings.pvf_watcher_requests import _queue_email_request_system
        sys_res = _queue_email_request_system(session=session, to_email="sys@example.com", template_type="t1", params={})
        sys_row = session.get(PvfWatcherEmailRequest, sys_res.result_package["id"])
        assert sys_row.customer_id is None
        # app cannot get _system
        got = get_email_request(session=session, usr_context=account.user_context(), queue_id=sys_row.id)
        assert got.failure_reason == "not found"

def test_email_capture_and_semantic_tag(account):
    with get_next_session() as session:
        res = queue_email_request(session=session, usr_context=account.user_context(), to_email="d@example.com", template_type="t1", params={"a":1}, semantic_tag="SHORTEN_PRODUCT_NAME")
        assert not res.failure_reason
        row = session.get(PvfWatcherEmailRequest, res.result_package["id"])
        assert row.semantic_tag == "SHORTEN_PRODUCT_NAME"
