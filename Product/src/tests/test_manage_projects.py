from datetime import datetime, timedelta, timezone

from sqlmodel import select

from src.tests.helpers.auth_client import as_user, clear_auth
from src.tests.helpers.factories import (
    create_alternative,
    create_factor,
    create_project,
    uid,
)
from src.db.models.ai_agent_jobs import AiAgentJob
from src.db.models.project_vote_events import ProjectVoteParticipant, VoteSource
from src.pvf.db.models.customer_user import PvfUserContext
from src.pvf.db.models.email_activity_log import PvfEmailActivityLog
from src.pvf.db.models.share_link_tracking import PvfShareLink, PvfShareLinkMagicKey
from src.pvf.depends.api_session_dependencies import get_next_session
from src.utils.sort_compare import clamp_max_recommended_passes, clamp_min_expected_passes
from src.utils.vote_sort_session import estimate_pass_comparisons
from src.utils.project_end_time import PAST_DATE_MSG



def _complete_one_group(client, project_id):
    mine = client.get("/ws/project-votes/my-vote", params={"project_id": project_id, "request_next": True})
    assert mine.status_code == 200, mine.text
    g = mine.json().get("next_group")
    assert g, mine.json()
    ids = list(g.get("item_ids") or [i["id"] for i in g.get("items") or []])
    rank = sorted(ids)
    pairings = []
    for i in range(len(rank) - 1):
        pairings.append({
            "winner_id": rank[i],
            "loser_id": rank[i + 1],
            "response": "winner",
            "decision_seconds": 0.1,
            "presented_left_id": rank[i],
            "presented_right_id": rank[i + 1],
        })
    res = client.post(
        "/ws/project-votes/complete-group",
        json={
            "project_id": project_id,
            "prior_group": {
                "client_group_id": g["client_group_id"],
                "pass_index": g.get("pass_index") or 1,
                "group_type": g.get("group_type") or "alternative",
                "criterion_id": g.get("criterion_id"),
                "sort_algorithm": g.get("sort_algorithm") or "ford_johnson",
                "item_ids_initial": ids,
                "rank_order": rank,
                "pairings": pairings,
            },
        },
    )
    assert res.status_code == 200, res.text
    assert not res.json().get("failure_reason"), res.json()
    return res


def test_project_create_as_admin(client, account):
    as_user(client, account.admin.id)
    tag = uid("proj")
    response = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag,
            "project_title": "Title",
            "project_description": "desc",
            "disabled": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    project = body.get("customer_project_info") or {}
    if project.get("id"):
        account.tracked_project_ids.append(project["id"])
        account.tracked_app_ids.append(project["id"])
        account.project_tag = tag
        assert project.get("project_created_by") == account.admin.id
        assert project.get("private_participation") is False


def test_project_private_participation_create_and_update(client, account):
    as_user(client, account.admin.id)
    tag = uid("priv")
    created = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag,
            "project_title": "Private",
            "project_description": "desc",
            "private_participation": True,
            "disabled": False,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert not body.get("failure_reason"), body
    project = body["customer_project_info"]
    account.tracked_project_ids.append(project["id"])
    account.tracked_app_ids.append(project["id"])
    assert project.get("private_participation") is True

    updated = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": tag,
            "project_title": "Private",
            "project_description": "desc",
            "private_participation": False,
            "disabled": False,
        },
    )
    assert updated.status_code == 200
    assert not updated.json().get("failure_reason"), updated.json()
    got = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project['id']}")
    assert got.json()["customer_project_info"]["private_participation"] is False


def _project_update_body(project, *, private_participation: bool):
    return {
        "project_tag": project.project_tag,
        "project_title": project.project_title,
        "project_description": project.project_description,
        "private_participation": private_participation,
        "disabled": False,
    }


def test_private_participation_reversible_with_only_creator_comparisons(client, account):
    """Creator-only comparisons do not lock private participation."""
    from src.tests.helpers.factories import create_alternative, create_factor, create_project

    project = create_project(account, tag=uid("priv-cre"))
    a1 = create_alternative(account, project_id=project.id, title="A")
    a2 = create_alternative(account, project_id=project.id, title="B")
    factor = create_factor(account, project_id=project.id, title="F")

    as_user(client, account.admin.id)
    enable = client.post(
        "/ws/custprojects/customer-project-update",
        json=_project_update_body(project, private_participation=True),
    )
    assert enable.status_code == 200
    assert not enable.json().get("failure_reason"), enable.json()

    _complete_one_group(client, project.id)

    got = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project.id}")
    assert got.status_code == 200
    assert got.json().get("private_participation_locked") is False

    disable = client.post(
        "/ws/custprojects/customer-project-update",
        json=_project_update_body(project, private_participation=False),
    )
    assert disable.status_code == 200
    assert not disable.json().get("failure_reason"), disable.json()
    refreshed = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project.id}")
    assert refreshed.json()["customer_project_info"]["private_participation"] is False


def test_private_participation_locked_after_non_creator_comparisons(client, account):
    """Non-creator comparisons lock turning private participation off for customer admins."""
    from src.tests.helpers.factories import create_alternative, create_factor, create_project

    project = create_project(account, tag=uid("priv-lock"))
    a1 = create_alternative(account, project_id=project.id, title="A")
    a2 = create_alternative(account, project_id=project.id, title="B")
    factor = create_factor(account, project_id=project.id, title="F")

    as_user(client, account.admin.id)
    enable = client.post(
        "/ws/custprojects/customer-project-update",
        json=_project_update_body(project, private_participation=True),
    )
    assert enable.status_code == 200
    assert not enable.json().get("failure_reason"), enable.json()

    as_user(client, account.member.id)
    _complete_one_group(client, project.id)

    as_user(client, account.admin.id)
    got = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project.id}")
    assert got.status_code == 200
    gb = got.json()
    assert gb["customer_project_info"]["private_participation"] is True
    assert gb.get("private_participation_locked") is True

    # Other fields may still update while private stays on
    keep = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            **_project_update_body(project, private_participation=True),
            "project_title": "Still private",
        },
    )
    assert keep.status_code == 200
    assert not keep.json().get("failure_reason"), keep.json()

    deny = client.post(
        "/ws/custprojects/customer-project-update",
        json=_project_update_body(project, private_participation=False),
    )
    assert deny.status_code == 200
    db = deny.json()
    assert db.get("failure_reason")
    assert "locked" in (db.get("failure_reason") or "").lower()

    still = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project.id}")
    assert still.json()["customer_project_info"]["private_participation"] is True


def test_private_participation_sysadmin_can_unlock(client, sysadmin_account):
    """System admin may reverse private participation after non-creator comparisons."""
    from src.tests.helpers.factories import create_alternative, create_factor, create_project

    project = create_project(sysadmin_account, tag=uid("priv-sys"))
    a1 = create_alternative(sysadmin_account, project_id=project.id, title="A")
    a2 = create_alternative(sysadmin_account, project_id=project.id, title="B")
    factor = create_factor(sysadmin_account, project_id=project.id, title="F")

    as_user(client, sysadmin_account.admin.id)
    enable = client.post(
        "/ws/custprojects/customer-project-update",
        json=_project_update_body(project, private_participation=True),
    )
    assert enable.status_code == 200
    assert not enable.json().get("failure_reason"), enable.json()

    as_user(client, sysadmin_account.member.id)
    _complete_one_group(client, project.id)

    as_user(client, sysadmin_account.admin.id)
    got = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project.id}")
    assert got.json().get("private_participation_locked") is True

    unlock = client.post(
        "/ws/custprojects/customer-project-update",
        json=_project_update_body(project, private_participation=False),
    )
    assert unlock.status_code == 200
    assert not unlock.json().get("failure_reason"), unlock.json()
    refreshed = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project.id}")
    rb = refreshed.json()
    assert rb["customer_project_info"]["private_participation"] is False
    assert rb.get("private_participation_locked") is False


def test_project_create_non_admin_forbidden(client, account):
    as_user(client, account.member.id)
    response = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": uid("proj"),
            "project_title": "Title",
            "project_description": "desc",
        },
    )
    assert response.status_code == 403


def test_project_get_by_id(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    response = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project.id}")
    assert response.status_code == 200
    body = response.json()
    assert body.get("customer_project_info", {}).get("id") == project.id


def test_project_get_by_id_cross_tenant_denied(client, account, other_account):
    foreign = create_project(other_account)
    as_user(client, account.admin.id)
    response = client.get(
        f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={foreign.id}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason") or body.get("customer_project_info") is None


def test_project_get_by_tag(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    response = client.get(
        f"/ws/custprojects/customer-project-get-by-tag?retrieve_by_tag={project.project_tag}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("customer_project_info", {}).get("project_tag") == project.project_tag


def test_project_get_all(client, account):
    create_project(account)
    as_user(client, account.admin.id)
    response = client.get("/ws/custprojects/customer-projects-get-all")
    assert response.status_code == 200
    body = response.json()
    assert body.get("customer_project_info_list") is not None or body.get("failure_reason", "") in ("", None)


def test_projects_list_summary_lean(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    response = client.get("/ws/custprojects/customer-projects-list-summary")
    assert response.status_code == 200
    body = response.json()
    assert not body.get("failure_reason"), body
    items = body.get("projects") or []
    assert any(i.get("project", {}).get("id") == project.id for i in items)
    row = next(i for i in items if i.get("project", {}).get("id") == project.id)
    assert "alternative_count" in row
    assert "factor_count" in row
    assert "observation_count" in row
    assert "participant_count" in row
    assert "metrics" in row
    assert "completion" in (row.get("metrics") or {})
    # Lean payload: no raw observations / report blobs
    assert "observations" not in row
    assert "report" not in row


def test_project_page_summary_lean(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    response = client.get(
        "/ws/custprojects/customer-project-page-summary",
        params={"project_id": project.id},
    )
    assert response.status_code == 200
    body = response.json()
    assert not body.get("failure_reason"), body
    assert body.get("project", {}).get("id") == project.id
    assert isinstance(body.get("alternatives"), list)
    assert isinstance(body.get("factors"), list)
    assert "my_observation_count" in body
    assert "participant_count" in body
    assert "target_comparisons_est" in body
    assert "max_comparisons_est" in body
    assert "active_participant_count" in body
    assert "my_metrics" in body
    assert "ai_agent_counts" in body
    assert "human_participants" in body
    assert "ai_participants" in body
    assert body["ai_agent_counts"]["requested"] == 0
    assert body["ai_participants"] == []
    assert "report" not in body
    assert "next_questions" not in body


def test_project_page_summary_estimates_and_active_participants(client, account):
    project = create_project(account)
    for title in ("Alpha", "Beta", "Gamma"):
        create_alternative(account, project_id=project.id, title=title)
    create_factor(account, project_id=project.id, title="Value")
    create_factor(account, project_id=project.id, title="Cost")

    as_user(client, account.admin.id)
    # one session participant with recorded comparisons
    _complete_one_group(client, project.id)

    # idle participant with zero comparisons
    session = get_next_session()
    session.add(ProjectVoteParticipant(
        customer_id=account.customer.id,
        project_id=project.id,
        participant_key="share:idle:0",
        display_name="Idle",
        source=VoteSource.share,
        comparison_count=0,
    ))
    session.commit()
    session.close()

    response = client.get(
        "/ws/custprojects/customer-project-page-summary",
        params={"project_id": project.id},
    )
    assert response.status_code == 200
    body = response.json()
    assert not body.get("failure_reason"), body
    proj = body["project"]
    # factory projects are non-explicit so they use the Ford–Johnson default per n
    from src.utils.sort_compare import default_questions_per_group_for_n
    per_pass = estimate_pass_comparisons(3, 2, default_questions_per_group_for_n(3), default_questions_per_group_for_n(2))
    min_passes = clamp_min_expected_passes(proj["min_expected_passes"])
    max_passes = clamp_max_recommended_passes(proj["max_recommended_passes"], min_passes)
    assert body["target_comparisons_est"] == per_pass * min_passes
    assert body["max_comparisons_est"] == per_pass * max_passes
    assert body["participant_count"] == 2
    assert body["active_participant_count"] == 1


def _create_overview_share(client, project_id: int, **overrides) -> dict:
    body = {
        "shared_type": "vote",
        "shared_entity_db_id": project_id,
        "access_mode": "open_access",
        "link_auto_send": False,
        "share_link_name": f"ov-{uid()}",
        "shared_with_email": f"{uid('rcpt')}@example.com",
        "shared_with_person_name": "Recipient",
    }
    body.update(overrides)
    response = client.post("/ws/create-share-link", json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert not result.get("failure_reason"), result
    return result["link_info"]


def _page_summary(client, project_id: int) -> dict:
    response = client.get(
        "/ws/custprojects/customer-project-page-summary",
        params={"project_id": project_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert not body.get("failure_reason"), body
    return body


def _backdate(session, row, field: str, days: int):
    setattr(row, field, datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days))
    session.add(row)
    session.commit()
    session.refresh(row)


def test_project_page_summary_cross_tenant_denied(client, account, other_account):
    foreign = create_project(other_account)
    as_user(client, account.admin.id)
    response = client.get(
        "/ws/custprojects/customer-project-page-summary",
        params={"project_id": foreign.id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason") or body.get("project") is None


def test_project_page_summary_human_buckets_and_report_excluded(client, account):
    project = create_project(account)
    create_alternative(account, project_id=project.id, title="Alpha")
    create_alternative(account, project_id=project.id, title="Beta")
    as_user(client, account.admin.id)
    _complete_one_group(client, project.id)

    locked = _create_overview_share(
        client,
        project.id,
        access_mode="email_matching",
        shared_with_person_name="Locked Invitee",
        shared_with_email=f"{uid('lock')}@example.com",
        share_link_name="Locked vote",
    )
    open_verified = _create_overview_share(
        client,
        project.id,
        access_mode="email_any_verified",
        shared_with_person_name=None,
        shared_with_email=None,
        share_link_name="Open verified",
    )
    anonymous = _create_overview_share(
        client,
        project.id,
        access_mode="open_access",
        share_link_name="Public vote",
    )
    report = _create_overview_share(
        client,
        project.id,
        shared_type="report",
        access_mode="email_matching",
        shared_with_person_name="Report Only",
        shared_with_email=f"{uid('rep')}@example.com",
        share_link_name="Report share",
    )

    session = get_next_session()
    locked_row = session.get(PvfShareLink, locked["id"])
    _backdate(session, locked_row, "create_date", 5)
    PvfEmailActivityLog(
        email_address=locked["shared_with_email"].lower(),
        email_type="share_project_vote",
        email_params_json={"magic_token": locked["magic_token"]},
        customer_id=account.customer.id,
        user_id=account.admin.id,
        result_message="ok",
    ).create_email_event(session=session, usr_context=account.user_context(), clear_lock=False)
    invite_row = session.exec(
        select(PvfEmailActivityLog)
        .where(PvfEmailActivityLog.email_address == locked["shared_with_email"].lower())
        .order_by(PvfEmailActivityLog.id.desc())
    ).first()
    assert invite_row is not None
    _backdate(session, invite_row, "create_date", 7)

    magic = PvfShareLinkMagicKey.create_shared_magic_key_record(
        session=session,
        usr_context=PvfUserContext(authenticated_session=False),
        share_link_id=open_verified["id"],
        shared_magic_token=open_verified["magic_token"],
        captured_email=f"{uid('ver')}@example.com",
        captured_display_name="Verified Guest",
        clear_lock=False,
    )
    _backdate(session, magic, "accessed_date", 2)

    session.add(ProjectVoteParticipant(
        customer_id=account.customer.id,
        project_id=project.id,
        share_id=anonymous["id"],
        participant_key=f"share:{anonymous['id']}:cookie:act1",
        display_name="Anon One",
        source=VoteSource.share,
        comparison_count=4,
    ))
    session.add(ProjectVoteParticipant(
        customer_id=account.customer.id,
        project_id=project.id,
        share_id=anonymous["id"],
        participant_key=f"share:{anonymous['id']}:cookie:idle",
        display_name="Anon Idle",
        source=VoteSource.share,
        comparison_count=0,
    ))
    session.add(ProjectVoteParticipant(
        customer_id=account.customer.id,
        project_id=project.id,
        participant_key="ai:glm-5.2",
        display_name="AI AGENT: glm-5.2",
        source=VoteSource.ai,
        is_ai=True,
        ai_model="glm-5.2",
        comparison_count=9,
        is_complete=True,
    ))
    session.add(ProjectVoteParticipant(
        customer_id=account.customer.id,
        project_id=project.id,
        share_id=report["id"],
        participant_key=f"share:{report['id']}:email:report@example.com",
        display_name="Report Only",
        email=f"{uid('rep2')}@example.com",
        source=VoteSource.share,
        comparison_count=0,
    ))
    session.commit()
    session.close()

    body = _page_summary(client, project.id)
    humans = body["human_participants"]
    active_labels = [row["label"] for row in humans["active"]]
    pending_labels = [row["label"] for row in humans["pending"]]
    anon_labels = [row["label"] for row in humans["anonymous_shares"]]
    assert "Locked Invitee" not in active_labels
    assert any(active_labels)
    assert "Locked Invitee" in pending_labels
    locked_pending = next(row for row in humans["pending"] if row["label"] == "Locked Invitee")
    assert locked_pending["days_pending"] >= 7
    assert "Verified Guest" in pending_labels
    verified_pending = next(row for row in humans["pending"] if row["label"] == "Verified Guest")
    assert verified_pending["days_pending"] >= 2
    assert "Public vote" in anon_labels
    public = next(row for row in humans["anonymous_shares"] if row["label"] == "Public vote")
    assert public["activated"] == 1
    assert "Report Only" not in pending_labels
    assert "Report share" not in anon_labels
    assert "AI AGENT: glm-5.2" not in active_labels
    assert "Anon One" not in active_labels


def test_project_page_summary_ai_agent_counts_and_rows(client, account):
    project = create_project(account)
    for title in ("Alpha", "Beta"):
        create_alternative(account, project_id=project.id, title=title)
    as_user(client, account.admin.id)
    body = _page_summary(client, project.id)
    target = int(body["target_comparisons_est"])

    session = get_next_session()
    session.add(AiAgentJob(
        customer_id=account.customer.id,
        project_id=project.id,
        job_type="ai_baseline",
        model_key="glm-5.2",
        status="complete",
        pair_count=target,
        details_json={"display_name": "AI AGENT: glm-5.2"},
    ))
    session.add(AiAgentJob(
        customer_id=account.customer.id,
        project_id=project.id,
        job_type="ai_baseline",
        model_key="grok-4.6",
        status="queued",
        pair_count=0,
        details_json={"display_name": "AI AGENT: grok-4.6"},
    ))
    session.add(AiAgentJob(
        customer_id=account.customer.id,
        project_id=project.id,
        job_type="ai_baseline",
        model_key="failed-model",
        status="failed",
        pair_count=4,
        details_json={"display_name": "AI AGENT: failed-model"},
    ))
    session.add(ProjectVoteParticipant(
        customer_id=account.customer.id,
        project_id=project.id,
        participant_key="ai:glm-5.2",
        display_name="AI AGENT: glm-5.2",
        source=VoteSource.ai,
        is_ai=True,
        ai_model="glm-5.2",
        comparison_count=target,
        is_complete=True,
    ))
    session.commit()
    session.close()

    body = _page_summary(client, project.id)
    counts = body["ai_agent_counts"]
    assert counts["requested"] == 3
    assert counts["in_flight"] == 1
    assert counts["completed"] == 1
    rows = {row["model_key"]: row for row in body["ai_participants"]}
    assert rows["glm-5.2"]["status"] == "complete"
    assert rows["glm-5.2"]["pairs_answered"] == target
    assert rows["glm-5.2"]["pairs_remaining"] == 0
    assert rows["grok-4.6"]["status"] == "queued"
    assert rows["grok-4.6"]["pairs_remaining"] == target
    assert rows["failed-model"]["status"] == "failed"
    assert rows["failed-model"]["pairs_answered"] == 4
    assert rows["failed-model"]["pairs_remaining"] == max(0, target - 4)
    assert all("AI AGENT" not in (row.get("label") or "") for row in body["human_participants"]["active"])


def test_project_page_summary_ai_all_complete_chip(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    session = get_next_session()
    for key in ("glm-5.2", "grok-4.6"):
        session.add(AiAgentJob(
            customer_id=account.customer.id,
            project_id=project.id,
            job_type="ai_baseline",
            model_key=key,
            status="complete",
            pair_count=8,
            details_json={"display_name": f"AI AGENT: {key}"},
        ))
        session.add(ProjectVoteParticipant(
            customer_id=account.customer.id,
            project_id=project.id,
            participant_key=f"ai:{key}",
            display_name=f"AI AGENT: {key}",
            source=VoteSource.ai,
            is_ai=True,
            ai_model=key,
            comparison_count=8,
            is_complete=True,
        ))
    session.commit()
    session.close()
    body = _page_summary(client, project.id)
    counts = body["ai_agent_counts"]
    assert counts["requested"] == 2
    assert counts["in_flight"] == 0
    assert counts["completed"] == 2


def test_project_update_as_admin(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": project.project_tag,
            "project_title": "updated title",
            "project_description": "updated desc",
            "disabled": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)


def test_project_update_non_admin_or_wrong_customer(client, account, other_account):
    project = create_project(account)
    as_user(client, account.member.id)
    response = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": project.project_tag,
            "project_title": "nope",
            "project_description": "nope",
        },
    )
    assert response.status_code in (200, 403)

    as_user(client, other_account.admin.id)
    response = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": project.project_tag,
            "project_title": "cross",
            "project_description": "cross",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason") or body.get("customer_project_id") in (-1, None)


def test_project_delete_as_admin(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    response = client.request(
        "DELETE",
        "/ws/custprojects/customer-project-delete",
        json={"project_id": project.id, "project_tag": project.project_tag},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None) or body.get("success") is True


def test_project_delete_cross_tenant_fails(client, account, other_account):
    project = create_project(account)
    as_user(client, other_account.admin.id)
    response = client.request(
        "DELETE",
        "/ws/custprojects/customer-project-delete",
        json={"project_id": project.id, "project_tag": project.project_tag},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason") or body.get("success") is False


def test_project_unauthenticated(client):
    clear_auth(client)
    response = client.get("/ws/custprojects/customer-projects-get-all")
    assert response.status_code in (401, 403)


def test_project_end_time_create_update_clear_and_normalize(client, account):
    as_user(client, account.admin.id)
    tag = uid("end")
    future = (datetime.now(timezone.utc) + timedelta(days=10)).replace(
        hour=10, minute=15, second=0, microsecond=0, tzinfo=None
    )
    created = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag,
            "project_title": "End time",
            "project_description": "desc",
            "disabled": False,
            "end_time": future.isoformat(),
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert not body.get("failure_reason"), body
    project = body["customer_project_info"]
    account.tracked_project_ids.append(project["id"])
    account.tracked_app_ids.append(project["id"])
    stored = datetime.fromisoformat(project["end_time"])
    assert stored.hour == 23 and stored.minute == 59
    assert stored.date() == future.date()

    later = future + timedelta(days=5)
    updated = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": tag,
            "project_title": "End time",
            "project_description": "desc",
            "disabled": False,
            "end_time": later.isoformat(),
        },
    )
    assert updated.status_code == 200
    assert not updated.json().get("failure_reason"), updated.json()
    got = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project['id']}")
    stored = datetime.fromisoformat(got.json()["customer_project_info"]["end_time"])
    assert stored.date() == later.date()
    assert stored.hour == 23 and stored.minute == 59

    omitted = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": tag,
            "project_title": "End time",
            "project_description": "desc",
            "disabled": False,
        },
    )
    assert omitted.status_code == 200
    assert not omitted.json().get("failure_reason"), omitted.json()
    still = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project['id']}")
    assert still.json()["customer_project_info"]["end_time"]

    cleared = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": tag,
            "project_title": "End time",
            "project_description": "desc",
            "disabled": False,
            "end_time": None,
        },
    )
    assert cleared.status_code == 200
    assert not cleared.json().get("failure_reason"), cleared.json()
    empty = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project['id']}")
    assert empty.json()["customer_project_info"]["end_time"] in (None, "")


def test_project_end_time_rejects_past_date(client, account):
    as_user(client, account.admin.id)
    tag = uid("past")
    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3)
    created = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": tag,
            "project_title": "Past",
            "project_description": "desc",
            "end_time": past.isoformat(),
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body.get("failure_reason") == PAST_DATE_MSG
    assert not body.get("customer_project_info")


def test_project_end_time_non_admin_cannot_set(client, account):
    project = create_project(account)
    as_user(client, account.member.id)
    future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=8)
    response = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": project.project_tag,
            "project_title": project.project_title,
            "project_description": project.project_description,
            "end_time": future.isoformat(),
        },
    )
    assert response.status_code in (200, 403)
    if response.status_code == 200:
        assert response.json().get("failure_reason")
    as_user(client, account.admin.id)
    got = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project.id}")
    assert got.json()["customer_project_info"]["end_time"] in (None, "")
