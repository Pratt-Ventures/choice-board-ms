"""Generic queue tenancy + SHORTEN_PRODUCT_NAME example."""
from sqlmodel import delete, select
from src.pvf.bindings.pvf_watcher_requests import queue_generic_request, get_generic_request, list_generic_requests
from src.pvf.depends.api_session_dependencies import get_next_session
from src.pvf.watcher.models import PvfWatcherGenericJob
from src.pvf.watcher.registry import build_registry_from_config
from src.pvf.bindings.pvf_startup_config import load_watcher_config
from src.pvf.watcher.poll import poll_and_dispatch
import pytest

@pytest.fixture(autouse=True)
def _clean():
    with get_next_session() as s:
        s.exec(delete(PvfWatcherGenericJob))
        s.commit()
    yield
    with get_next_session() as s:
        s.exec(delete(PvfWatcherGenericJob))
        s.commit()

def test_generic_queue_and_shorten_handler(account):
    with get_next_session() as session:
        res = queue_generic_request(session=session, usr_context=account.user_context(), work_type="SHORTEN_PRODUCT_NAME", request_package={"product_name": "Acme Super Widget Pro Ultra Edition"}, semantic_tag="SHORTEN_PRODUCT_NAME")
        assert not res.failure_reason
        qid = res.result_package["id"]
        got = get_generic_request(session=session, usr_context=account.user_context(), queue_id=qid)
        assert not got.failure_reason
        assert got.row.work_type == "SHORTEN_PRODUCT_NAME"
        assert got.row.semantic_tag == "SHORTEN_PRODUCT_NAME"

    # Poll should invoke shorten handler
    cfg = load_watcher_config()
    reg = build_registry_from_config(cfg)
    # Ensure handler present (app_shell registered)
    from src.pvf.bindings.pvf_invocation import get_current_invocation
    # Fallback: the live registry from app is already built; use it if cfg registry missing handler
    try:
        from src.app.watcher_handlers import shorten_product_name
        reg.register("SHORTEN_PRODUCT_NAME", __import__("src.pvf.bindings.pvf_startup_config", fromlist=["WatcherTypeSpec"]).WatcherTypeSpec(kind="app", module="src.app.watcher_handlers", entry="shorten_product_name"))
    except Exception:
        pass
    with get_next_session() as session:
        did = poll_and_dispatch(session, reg)
        assert did is True
    with get_next_session() as session:
        row = session.get(PvfWatcherGenericJob, qid)
        assert row.status == "complete"
        assert row.result_package is not None
        assert "short_name" in row.result_package
        # short_name should be shorter than original
        assert len(row.result_package["short_name"]) <= len("Acme Super Widget Pro Ultra Edition")

def test_generic_cross_tenant_not_found(account, other_account):
    with get_next_session() as session:
        res = queue_generic_request(session=session, usr_context=account.user_context(), work_type="MY_TYPE", request_package={"a":1})
        qid = res.result_package["id"]
    with get_next_session() as session:
        got = get_generic_request(session=session, usr_context=other_account.user_context(), queue_id=qid)
        assert got.failure_reason == "not found"

def test_generic_list_tenancy(account):
    with get_next_session() as session:
        queue_generic_request(session=session, usr_context=account.user_context(), work_type="WT1", request_package={})
        queue_generic_request(session=session, usr_context=account.user_context(), work_type="WT2", request_package={})
        lst = list_generic_requests(session=session, usr_context=account.user_context())
        assert not lst.failure_reason
        assert len(lst.rows) >= 2
        lst2 = list_generic_requests(session=session, usr_context=account.user_context(), work_type="WT1")
        assert all(r.work_type == "WT1" for r in lst2.rows)

def test_generic_system_bypass(account):
    with get_next_session() as session:
        res = queue_generic_request(session=session, usr_context=account.user_context(), work_type="T1", request_package={})
        row = session.get(PvfWatcherGenericJob, res.result_package["id"])
        assert row.customer_id == account.customer.id
        from src.pvf.bindings.pvf_watcher_requests import _queue_generic_request_system
        sys_res = _queue_generic_request_system(session=session, work_type="T_SYS", request_package={})
        sys_row = session.get(PvfWatcherGenericJob, sys_res.result_package["id"])
        assert sys_row.customer_id is None
        got = get_generic_request(session=session, usr_context=account.user_context(), queue_id=sys_row.id)
        assert got.failure_reason == "not found"

def test_generic_work_type_required(account):
    with get_next_session() as session:
        res = queue_generic_request(session=session, usr_context=account.user_context(), work_type="", request_package={})
        assert res.failure_reason == "work_type required"
