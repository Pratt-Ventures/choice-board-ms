"""Tests for sort-group compare session, group packages, and reports."""
from datetime import datetime, timedelta

from src.db.models.customer_projects import CustomerProject
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.auth_client import as_user, clear_auth
from src.tests.helpers.factories import create_alternative, create_factor, create_project, create_account, uid
from src.utils.project_end_time import COLLECTION_CLOSED_MSG


def _seed_vote_project(account):
    project = create_project(account, tag=uid("vote"))
    a1 = create_alternative(account, project_id=project.id, title="Alpha")
    a2 = create_alternative(account, project_id=project.id, title="Beta")
    a3 = create_alternative(account, project_id=project.id, title="Gamma")
    factor = create_factor(account, project_id=project.id, title="Value")
    return project, a1, a2, a3, factor


def _complete_issued_group(client, project_id, group: dict):
    """Build a trivial total order package for the issued group and post it."""
    ids = list(group.get("item_ids") or [i["id"] for i in group.get("items") or []])
    assert len(ids) >= 2
    # descending id order as rank (stable)
    rank = sorted(ids)
    pairings = []
    # minimal synthetic pairings covering adjacent
    for i in range(len(rank) - 1):
        pairings.append({
            "winner_id": rank[i],
            "loser_id": rank[i + 1],
            "response": "winner",
            "decision_seconds": 0.5,
            "presented_left_id": rank[i],
            "presented_right_id": rank[i + 1],
            "effective_rule": "choice",
        })
    pkg = {
        "client_group_id": group["client_group_id"],
        "pass_index": group.get("pass_index") or 1,
        "group_type": group.get("group_type") or "alternative",
        "criterion_id": group.get("criterion_id"),
        "sort_algorithm": group.get("sort_algorithm") or "ford_johnson",
        "item_ids_initial": ids,
        "rank_order": rank,
        "pairings": pairings,
        "algorithm_version": "1.0-sort",
    }
    res = client.post(
        "/ws/project-votes/complete-group",
        json={"project_id": project_id, "prior_group": pkg},
    )
    return res


def test_session_sort_group_and_report(client, account):
    as_user(client, account.admin.id)
    project, a1, a2, a3, factor = _seed_vote_project(account)
    project_id = project.id

    mine = client.get("/ws/project-votes/my-vote", params={"project_id": project_id, "request_next": True})
    assert mine.status_code == 200
    mine_body = mine.json()
    assert not mine_body.get("failure_reason")
    assert mine_body["participant_info"]["project_id"] == project_id
    g = mine_body.get("next_group")
    assert g and g.get("client_group_id")
    assert g.get("group_token")
    assert len(g["group_token"]) == 10
    assert g.get("question_budget") or g.get("estimated_comparisons")
    assert g.get("sort_algorithm") in ("ford_johnson", "merge_sort")
    assert len(g.get("items") or []) >= 2
    groups = mine_body.get("groups") or []
    assert any(
        (row.get("group_token") or row.get("client_group_id")) == g["group_token"]
        and row.get("status") == "in_progress"
        for row in groups
    )

    submit = _complete_issued_group(client, project_id, g)
    assert submit.status_code == 200
    body = submit.json()
    assert not body.get("failure_reason"), body
    assert body.get("group_info")
    assert body["group_info"]["client_group_id"] == g["client_group_id"]

    # idempotent replay
    replay = _complete_issued_group(client, project_id, g)
    assert replay.status_code == 200
    assert replay.json()["group_info"]["id"] == body["group_info"]["id"]

    report = client.post(
        "/ws/project-votes/project-report",
        json={"project_id": project_id, "include_participants": True},
    )
    assert report.status_code == 200
    rb = report.json()
    assert not rb.get("failure_reason"), rb
    assert rb["report"]["unique_participants"] >= 1
    assert rb["report"]["group_count"] >= 1
    assert rb["report"].get("option_ranking") is not None
    assert "pivot" in rb["report"]

    detail = client.post(
        "/ws/project-votes/report-pivot-detail",
        json={"project_id": project_id, "primary_axis": "alternatives", "row_id": a1.id},
    )
    assert detail.status_code == 200
    assert not detail.json().get("failure_reason")

    parts = client.get("/ws/project-votes/participants", params={"project_id": project_id})
    assert parts.status_code == 200
    assert len(parts.json().get("participant_info_list") or []) >= 1


def test_save_group_partial_and_resume(client, account):
    as_user(client, account.admin.id)
    project, a1, a2, a3, _factor = _seed_vote_project(account)
    mine = client.get("/ws/project-votes/my-vote", params={"project_id": project.id, "request_next": True})
    g = mine.json()["next_group"]
    ids = list(g.get("item_ids") or [i["id"] for i in g.get("items") or []])
    pairing = {
        "winner_id": ids[0],
        "loser_id": ids[1],
        "response": "winner",
        "decision_seconds": 0.4,
        "presented_left_id": ids[0],
        "presented_right_id": ids[1],
    }
    saved = client.post(
        "/ws/project-votes/save-group",
        json={
            "project_id": project.id,
            "prior_group": {
                "client_group_id": g["client_group_id"],
                "group_token": g.get("group_token"),
                "item_ids_initial": ids,
                "pairings": [pairing],
            },
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert not body.get("failure_reason"), body
    assert body["group_info"]["status"] == "in_progress"
    assert body["group_info"]["received_pairing_count"] == 1
    ev = (body.get("progress") or {}).get("ranking_evidence")
    assert isinstance(ev, list)
    assert any(len(row.get("pairings") or []) == 1 for row in ev)

    again = client.get("/ws/project-votes/my-vote", params={"project_id": project.id, "request_next": True})
    nxt = again.json()["next_group"]
    assert nxt["group_token"] == g["group_token"]
    assert len(nxt.get("pairings") or []) == 1


def test_next_group_endpoint(client, account):
    as_user(client, account.admin.id)
    project, *_ = _seed_vote_project(account)
    res = client.post("/ws/project-votes/next-group", json={"project_id": project.id})
    assert res.status_code == 200
    body = res.json()
    assert not body.get("failure_reason"), body
    assert body.get("next_group")
    assert body.get("progress")
    assert isinstance((body.get("progress") or {}).get("ranking_evidence"), list)


def test_ranking_evidence_scoped_to_participant(client, account):
    as_user(client, account.admin.id)
    project, a1, a2, a3, factor = _seed_vote_project(account)
    mine = client.get("/ws/project-votes/my-vote", params={"project_id": project.id, "request_next": True})
    assert mine.status_code == 200
    g = mine.json()["next_group"]
    submit = _complete_issued_group(client, project.id, g)
    assert submit.status_code == 200
    body = submit.json()
    assert not body.get("failure_reason"), body
    ev = (body.get("progress") or {}).get("ranking_evidence")
    assert isinstance(ev, list) and ev
    pairing_ids = {
        pid
        for row in ev
        for p in (row.get("pairings") or [])
        for pid in (p.get("winner_id"), p.get("loser_id"), p.get("item_a_id"), p.get("item_b_id"))
        if pid
    }
    allowed = {a1.id, a2.id, a3.id, factor.id}
    assert pairing_ids <= allowed

    as_user(client, account.member.id)
    other = client.get("/ws/project-votes/my-vote", params={"project_id": project.id, "request_next": True})
    assert other.status_code == 200
    other_body = other.json()
    assert not other_body.get("failure_reason"), other_body
    other_ev = (other_body.get("progress") or {}).get("ranking_evidence") or []
    other_pairs = sum(len(row.get("pairings") or []) for row in other_ev)
    admin_pairs = sum(len(row.get("pairings") or []) for row in ev)
    assert admin_pairs >= 1
    assert other_pairs == 0


def test_vote_endpoints_unauthenticated(client, account):
    clear_auth(client)
    project, *_ = _seed_vote_project(account)
    r = client.get("/ws/project-votes/my-vote", params={"project_id": project.id})
    assert r.status_code in (401, 403)
    r2 = client.post("/ws/project-votes/complete-group", json={"project_id": project.id})
    assert r2.status_code in (401, 403)


def test_vote_cross_tenant_denied(client, account, account_b=None):
    """Other customer cannot complete groups on this project."""
    from src.tests.helpers.factories import create_account

    as_user(client, account.admin.id)
    project, *_ = _seed_vote_project(account)
    other = create_account()
    try:
        as_user(client, other.admin.id)
        r = client.get("/ws/project-votes/my-vote", params={"project_id": project.id})
        # 404 or failure
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json().get("failure_reason") or r.status_code == 404
    finally:
        clear_auth(client)


def test_complete_group_validation(client, account):
    as_user(client, account.admin.id)
    project, a1, a2, a3, _ = _seed_vote_project(account)
    nxt = client.post("/ws/project-votes/next-group", json={"project_id": project.id}).json()
    g = nxt["next_group"]
    bad = client.post(
        "/ws/project-votes/complete-group",
        json={
            "project_id": project.id,
            "prior_group": {
                "client_group_id": g["client_group_id"],
                "item_ids_initial": g["item_ids"],
                "rank_order": g["item_ids"][:-1],  # not a permutation
                "pairings": [],
            },
        },
    )
    assert bad.status_code == 200
    assert bad.json().get("failure_reason")


def test_participant_detail_and_bundle(client, account):
    as_user(client, account.admin.id)
    project, *_ = _seed_vote_project(account)
    mine = client.get("/ws/project-votes/my-vote", params={"project_id": project.id}).json()
    g = mine["next_group"]
    _complete_issued_group(client, project.id, g)
    pid = mine["participant_info"]["id"]
    detail = client.get(
        "/ws/project-votes/participant-detail",
        params={"project_id": project.id, "participant_id": pid},
    )
    assert detail.status_code == 200
    assert len(detail.json().get("groups") or []) >= 1
    bundle = client.get("/ws/project-votes/project-bundle", params={"project_id": project.id})
    assert bundle.status_code == 200
    bb = bundle.json()
    assert bb.get("groups")
    assert bb.get("report")


def test_member_can_vote(client, account):
    as_user(client, account.member.id)
    project, *_ = _seed_vote_project(account)
    mine = client.get("/ws/project-votes/my-vote", params={"project_id": project.id})
    assert mine.status_code == 200
    assert mine.json().get("next_group")


def test_mark_complete(client, account):
    as_user(client, account.admin.id)
    project, *_ = _seed_vote_project(account)
    g = client.get("/ws/project-votes/my-vote", params={"project_id": project.id}).json()["next_group"]
    _complete_issued_group(client, project.id, g)
    done = client.post(
        "/ws/project-votes/mark-complete",
        json={"project_id": project.id, "is_complete": True},
    )
    assert done.status_code == 200
    body = done.json()
    assert body["participant_info"]["is_complete"] is True
    assert body.get("submitter_summary") is not None


def test_private_participation_hides_names_in_report(client, account):
    from src.db.models.customer_projects import CustomerProject
    from src.pvf.depends.api_session_dependencies import get_next_session
    from sqlmodel import select

    as_user(client, account.admin.id)
    project = create_project(account, tag=uid("priv"))
    session = get_next_session()
    row = session.exec(select(CustomerProject).where(CustomerProject.id == project.id)).one()
    row.private_participation = True
    session.add(row)
    session.commit()
    session.close()
    create_alternative(account, project_id=project.id, title="A")
    create_alternative(account, project_id=project.id, title="B")
    g = client.get("/ws/project-votes/my-vote", params={"project_id": project.id}).json().get("next_group")
    if g:
        _complete_issued_group(client, project.id, g)
    as_user(client, account.member.id)
    # rename member display via participant path is automatic from user name
    g2 = client.get("/ws/project-votes/my-vote", params={"project_id": project.id}).json().get("next_group")
    if g2:
        _complete_issued_group(client, project.id, g2)
    as_user(client, account.admin.id)
    report = client.post(
        "/ws/project-votes/project-report",
        json={"project_id": project.id, "include_participants": True},
    ).json()
    assert report["report"].get("private_participation") is True
    names = " ".join(
        str(p.get("display_name") or "") for p in (report["report"].get("participants") or [])
    )
    assert "unique participant" in names.lower() or account.member.name not in names


def test_project_pass_settings_on_create(client, account):
    as_user(client, account.admin.id)
    tag = uid("passes")
    res = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag,
            "project_title": "Passes",
            "project_description": "d",
            "min_expected_passes": 3,
            "max_recommended_passes": 5,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert not body.get("failure_reason"), body
    p = body["customer_project_info"]
    assert p["min_expected_passes"] == 3
    assert p["max_recommended_passes"] == 5
    assert abs(float(p.get("factor_weight_floor_alpha", 0.5)) - 0.5) < 1e-9
    if p.get("id"):
        account.tracked_project_ids.append(p["id"])
        account.tracked_app_ids.append(p["id"])


def test_project_pass_settings_clamp_and_defaults(client, account):
    as_user(client, account.admin.id)

    tag_omit = uid("pass-omit")
    omitted = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag_omit,
            "project_title": "Omit max",
            "project_description": "d",
            "min_expected_passes": 5,
        },
    )
    assert omitted.status_code == 200
    omit_body = omitted.json()
    assert not omit_body.get("failure_reason"), omit_body
    omit_p = omit_body["customer_project_info"]
    if omit_p.get("id"):
        account.tracked_project_ids.append(omit_p["id"])
        account.tracked_app_ids.append(omit_p["id"])
    assert omit_p["min_expected_passes"] == 5
    assert omit_p["max_recommended_passes"] == 5

    tag_def = uid("pass-def")
    defaulted = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag_def,
            "project_title": "Default passes",
            "project_description": "d",
        },
    )
    assert defaulted.status_code == 200
    def_body = defaulted.json()
    assert not def_body.get("failure_reason"), def_body
    def_p = def_body["customer_project_info"]
    if def_p.get("id"):
        account.tracked_project_ids.append(def_p["id"])
        account.tracked_app_ids.append(def_p["id"])
    assert def_p["min_expected_passes"] == 2
    assert def_p["max_recommended_passes"] == 2

    tag_eq = uid("pass-eq")
    equal = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag_eq,
            "project_title": "Equal passes",
            "project_description": "d",
            "min_expected_passes": 2,
            "max_recommended_passes": 2,
        },
    )
    assert equal.status_code == 200
    eq_body = equal.json()
    assert not eq_body.get("failure_reason"), eq_body
    eq_p = eq_body["customer_project_info"]
    if eq_p.get("id"):
        account.tracked_project_ids.append(eq_p["id"])
        account.tracked_app_ids.append(eq_p["id"])
    assert eq_p["min_expected_passes"] == 2
    assert eq_p["max_recommended_passes"] == 2

    tag_one = uid("pass-one")
    one = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag_one,
            "project_title": "One pass",
            "project_description": "d",
            "min_expected_passes": 1,
            "max_recommended_passes": 1,
        },
    )
    assert one.status_code == 200
    one_body = one.json()
    assert not one_body.get("failure_reason"), one_body
    one_p = one_body["customer_project_info"]
    if one_p.get("id"):
        account.tracked_project_ids.append(one_p["id"])
        account.tracked_app_ids.append(one_p["id"])
    assert one_p["min_expected_passes"] == 1
    assert one_p["max_recommended_passes"] == 1

    tag_lo = uid("pass-lo")
    low = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag_lo,
            "project_title": "Under min",
            "project_description": "d",
            "min_expected_passes": 5,
            "max_recommended_passes": 2,
        },
    )
    assert low.status_code == 200
    low_body = low.json()
    assert not low_body.get("failure_reason"), low_body
    low_p = low_body["customer_project_info"]
    if low_p.get("id"):
        account.tracked_project_ids.append(low_p["id"])
        account.tracked_app_ids.append(low_p["id"])
    assert low_p["min_expected_passes"] == 5
    assert low_p["max_recommended_passes"] == 5

    updated = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": tag_eq,
            "project_title": "Equal passes",
            "project_description": "d",
            "min_expected_passes": 5,
            "max_recommended_passes": 2,
        },
    )
    assert updated.status_code == 200
    assert not updated.json().get("failure_reason"), updated.json()
    got = client.get(
        f"/ws/custprojects/customer-project-get-by-tag?retrieve_by_tag={tag_eq}"
    )
    assert got.status_code == 200
    info = got.json()["customer_project_info"]
    assert info["min_expected_passes"] == 5
    assert info["max_recommended_passes"] == 5


def test_factor_weight_floor_alpha_create_update(client, account):
    as_user(client, account.admin.id)
    tag = uid("fwfa")
    created = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag,
            "project_title": "Floor alpha",
            "project_description": "d",
            "factor_weight_floor_alpha": 0.2,
            "participant_influence_min_comparisons": 12,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert not body.get("failure_reason"), body
    p = body["customer_project_info"]
    if p.get("id"):
        account.tracked_project_ids.append(p["id"])
        account.tracked_app_ids.append(p["id"])
    assert abs(float(p["factor_weight_floor_alpha"]) - 0.2) < 1e-9
    assert p["participant_influence_min_comparisons"] == 12

    updated = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": tag,
            "project_title": "Floor alpha",
            "project_description": "d",
            "factor_weight_floor_alpha": 0.05,  # clamp to 0.1
            "participant_influence_min_comparisons": 12,
        },
    )
    assert updated.status_code == 200
    assert not updated.json().get("failure_reason"), updated.json()
    got = client.get(
        f"/ws/custprojects/customer-project-get-by-tag?retrieve_by_tag={tag}"
    )
    assert got.status_code == 200
    info = got.json()["customer_project_info"]
    assert abs(float(info["factor_weight_floor_alpha"]) - 0.1) < 1e-9


def test_questions_per_group_create_update(client, account):
    as_user(client, account.admin.id)
    tag = uid("qpg")
    created = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag,
            "project_title": "Questions per group",
            "project_description": "d",
            "option_questions_per_group": 12,
            "factor_questions_per_group": 8,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert not body.get("failure_reason"), body
    p = body["customer_project_info"]
    if p.get("id"):
        account.tracked_project_ids.append(p["id"])
        account.tracked_app_ids.append(p["id"])
    assert p["option_questions_per_group"] == 12
    assert p["factor_questions_per_group"] == 8
    assert p["option_questions_per_group_explicit"] is True
    assert p["factor_questions_per_group_explicit"] is True

    updated = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": tag,
            "project_title": "Questions per group",
            "project_description": "d",
            "option_questions_per_group": 0,
            "factor_questions_per_group": 900,
        },
    )
    assert updated.status_code == 200
    assert not updated.json().get("failure_reason"), updated.json()
    got = client.get(f"/ws/custprojects/customer-project-get-by-tag?retrieve_by_tag={tag}")
    assert got.status_code == 200
    info = got.json()["customer_project_info"]
    assert info["option_questions_per_group"] == 1
    assert info["factor_questions_per_group"] == 500
    assert info["option_questions_per_group_explicit"] is True
    assert info["factor_questions_per_group_explicit"] is True


def test_questions_per_group_default_until_explicit(client, account):
    as_user(client, account.admin.id)
    tag = uid("qpgdef")
    created = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag,
            "project_title": "Default group size",
            "project_description": "d",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert not body.get("failure_reason"), body
    p = body["customer_project_info"]
    if p.get("id"):
        account.tracked_project_ids.append(p["id"])
        account.tracked_app_ids.append(p["id"])
    assert p["option_questions_per_group_explicit"] is False
    assert p["factor_questions_per_group_explicit"] is False
    assert p["option_questions_per_group"] == 20
    assert p["factor_questions_per_group"] == 20

    kept = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": tag,
            "project_title": "Default group size",
            "project_description": "d",
            "option_questions_per_group": 16,
            "factor_questions_per_group": 16,
            "option_questions_per_group_explicit": False,
            "factor_questions_per_group_explicit": False,
        },
    )
    assert kept.status_code == 200
    assert not kept.json().get("failure_reason"), kept.json()
    got = client.get(f"/ws/custprojects/customer-project-get-by-tag?retrieve_by_tag={tag}")
    info = got.json()["customer_project_info"]
    assert info["option_questions_per_group_explicit"] is False
    assert info["factor_questions_per_group_explicit"] is False


def _set_end_time(project_id: int, end_time):
    session = get_next_session()
    row = session.get(CustomerProject, project_id)
    row.end_time = end_time
    session.add(row)
    session.commit()
    session.close()


def test_session_accepts_comparisons_until_grace_then_rejects(client, account):
    as_user(client, account.admin.id)
    project, *_ = _seed_vote_project(account)
    _set_end_time(project.id, datetime.now() - timedelta(minutes=30))
    mine = client.get("/ws/project-votes/my-vote", params={"project_id": project.id, "request_next": True})
    assert mine.status_code == 200
    body = mine.json()
    assert not body.get("failure_reason"), body
    assert body.get("next_group")
    settings = body.get("project_settings") or {}
    assert settings.get("end_time")
    assert settings.get("collection_ending_soon") is True

    _set_end_time(project.id, datetime.now() - timedelta(hours=2))
    nxt = client.post("/ws/project-votes/next-group", json={"project_id": project.id})
    assert nxt.status_code == 200
    assert nxt.json().get("failure_reason") == COLLECTION_CLOSED_MSG
    done = client.post(
        "/ws/project-votes/complete-group",
        json={"project_id": project.id, "prior_group": None},
    )
    assert done.status_code == 200
    assert done.json().get("failure_reason") == COLLECTION_CLOSED_MSG


def test_session_null_end_time_never_blocks(client, account):
    as_user(client, account.admin.id)
    project, *_ = _seed_vote_project(account)
    mine = client.get("/ws/project-votes/my-vote", params={"project_id": project.id, "request_next": True})
    assert mine.status_code == 200
    assert not mine.json().get("failure_reason")
    assert mine.json().get("next_group")
    assert (mine.json().get("project_settings") or {}).get("end_time") in (None, "")


def test_session_disabled_still_independent_of_end_time(client, account):
    as_user(client, account.admin.id)
    project, *_ = _seed_vote_project(account)
    session = get_next_session()
    row = session.get(CustomerProject, project.id)
    row.disabled = True
    row.end_time = datetime.now() + timedelta(days=10)
    session.add(row)
    session.commit()
    session.close()
    nxt = client.post("/ws/project-votes/next-group", json={"project_id": project.id})
    assert nxt.status_code == 200
    assert "locked" in (nxt.json().get("failure_reason") or "").lower()
