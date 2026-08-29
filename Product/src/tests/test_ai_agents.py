from contextlib import contextmanager
from datetime import datetime

from src.config.config_settings import settings
from src.db.models.ai_agent_jobs import AiAgentJob
from src.db.models.project_vote_events import (
    ProjectVoteGroupResult,
    ProjectVoteParticipant,
    VoteSource,
)
from src.pvf.config.pvf_config_settings import pvf_settings
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.auth_client import as_user, clear_auth
from src.tests.helpers.factories import create_alternative, create_factor, create_project, uid
from src.utils.ai.config import DEFAULT_MODEL_KEY
from src.utils.ai.identity import AI_DISPLAY_NAME, AI_PARTICIPANT_KEY, partition_vote_data
from src.utils.ai.report import build_report_with_ai_baseline
from src.utils.ai.provider import AiProviderError
from src.utils.ai.worker import _run_job, process_next_ai_job


@contextmanager
def _ai_enabled(monkeypatch, *, key="test-ai-key"):
    settings._inject_startup_values({"ACTIVATE_AI_AGENTS": True})
    pvf_settings._inject_startup_values({"ACTIVATE_AI_AGENTS": True})
    monkeypatch.setattr(settings, "AI_API_KEY", key)
    monkeypatch.setattr(settings, "AI_SERVICE", "opencode_go")
    monkeypatch.setattr(settings, "AI_MODEL", "glm-5.2")
    monkeypatch.setattr(pvf_settings, "AI_API_KEY", key)
    monkeypatch.setattr(pvf_settings, "AI_SERVICE", "opencode_go")
    monkeypatch.setattr(pvf_settings, "AI_MODEL", "glm-5.2")
    try:
        yield
    finally:
        settings._inject_startup_values({"ACTIVATE_AI_AGENTS": False})
        pvf_settings._inject_startup_values({"ACTIVATE_AI_AGENTS": False})
        monkeypatch.setattr(settings, "AI_API_KEY", "")
        monkeypatch.setattr(pvf_settings, "AI_API_KEY", "")


def test_context_ai_flag_default_false_and_secrets_absent(client, account):
    as_user(client, account.admin.id)
    response = client.post("/ws/core/get-user-customer-context", json={"include_account_status": False})
    assert response.status_code == 200
    payload = response.json().get("settings") or {}
    assert "ai_features_enabled" in payload
    assert payload["ai_features_enabled"] is bool(getattr(settings, "ACTIVATE_AI_AGENTS", False))
    assert payload.get("ai_providers_configured") is False
    blob = str(payload).lower()
    assert "ai_api_key" not in blob
    assert "glm-5.2" not in blob
    assert "opencode" not in blob
    assert "test-ai-key" not in blob


def test_context_ai_flag_true_when_enabled(client, account, monkeypatch):
    as_user(client, account.admin.id)
    with _ai_enabled(monkeypatch):
        response = client.post("/ws/core/get-user-customer-context", json={"include_account_status": False})
    assert response.status_code == 200
    payload = response.json().get("settings") or {}
    assert payload.get("ai_features_enabled") is True
    assert payload.get("ai_providers_configured") is True
    blob = str(payload).lower()
    assert "test-ai-key" not in blob
    assert "ai_api_key" not in blob


def test_factor_suggest_forbidden_when_disabled(client, account):
    project = create_project(account, title="Pick a lunch")
    as_user(client, account.admin.id)
    res = client.post(
        "/ws/custproject-content/factor-suggest",
        json={"project_id": project.id, "project_title": "Pick a lunch", "project_description": "Choose a weekday lunch option"},
    )
    assert res.status_code == 403


def test_factor_suggest_non_admin_forbidden(client, account, monkeypatch):
    project = create_project(account, title="Pick a lunch")
    as_user(client, account.member.id)
    with _ai_enabled(monkeypatch):
        res = client.post(
            "/ws/custproject-content/factor-suggest",
            json={"project_id": project.id, "project_title": "Pick a lunch", "project_description": "Choose a weekday lunch option"},
        )
    assert res.status_code == 403


def test_factor_suggest_mocked(client, account, monkeypatch):
    project = create_project(account, title="Pick a lunch")
    as_user(client, account.admin.id)

    async def _fake(*, title, description, customer=None):
        assert "lunch" in title.lower() or "lunch" in description.lower()
        return [
            {"title": "Cost", "description": "Price of the meal"},
            {"title": "Speed", "description": "How quickly food arrives"},
        ]

    monkeypatch.setattr("src.utils.ai.worker.suggest_factors", _fake)
    with _ai_enabled(monkeypatch):
        res = client.post(
            "/ws/custproject-content/factor-suggest",
            json={
                "project_id": project.id,
                "project_title": "Pick a lunch",
                "project_description": "Choose a weekday lunch option",
            },
        )
    assert res.status_code == 200
    body = res.json()
    assert not body.get("failure_reason"), body
    titles = [s["title"] for s in body.get("suggestions") or []]
    assert titles == ["Cost", "Speed"]
    listed = client.get(f"/ws/custproject-content/factors-get-by-project-id?project_id={project.id}")
    assert listed.status_code == 200
    assert not (listed.json().get("factor_info_list") or [])


def test_factor_suggest_unauthenticated(client, account, monkeypatch):
    project = create_project(account, title="T")
    clear_auth(client)
    with _ai_enabled(monkeypatch):
        res = client.post(
            "/ws/custproject-content/factor-suggest",
            json={"project_id": project.id, "project_title": "T", "project_description": "D"},
        )
    assert res.status_code in (401, 403)


def test_build_report_excludes_ai_and_emits_baseline():
    alts = [{"id": 1, "alternative_title": "A"}, {"id": 2, "alternative_title": "B"}]
    human = {
        "id": 10,
        "participant_id": 10,
        "source": "session",
        "is_complete": True,
        "display_name": "Human",
    }
    ai = {
        "id": 11,
        "participant_id": 11,
        "source": "ai",
        "participant_key": AI_PARTICIPANT_KEY,
        "is_complete": True,
        "display_name": AI_DISPLAY_NAME,
    }
    human_group = {
        "participant_id": 10,
        "group_type": "alternative",
        "criterion_id": None,
        "status": "complete",
        "pass_index": 1,
        "item_ids_initial": [1, 2],
        "rank_order": [1, 2],
        "pairings": [{"winner_id": 1, "loser_id": 2, "response": "winner", "presented_left_id": 1, "presented_right_id": 2, "decision_seconds": 0}],
        "comparison_count": 1,
    }
    ai_group = {
        "participant_id": 11,
        "group_type": "alternative",
        "criterion_id": None,
        "status": "complete",
        "pass_index": 1,
        "item_ids_initial": [1, 2],
        "rank_order": [2, 1],
        "pairings": [{"winner_id": 2, "loser_id": 1, "response": "winner", "presented_left_id": 2, "presented_right_id": 1, "decision_seconds": 0}],
        "comparison_count": 1,
    }
    report = build_report_with_ai_baseline(
        alternatives=alts,
        factors=[],
        exclusive_mode=False,
        all_groups=[human_group, ai_group],
        participants=[human, ai],
    )
    assert report["unique_participants"] == 1
    names = [p.get("display_name") for p in (report.get("participants") or [])]
    assert AI_DISPLAY_NAME not in names
    baseline = report.get("ai_baseline") or {}
    assert baseline.get("available") is True
    assert baseline.get("label") == "Agents"
    assert baseline.get("option_ranking")
    analysis = report.get("analysis") or {}
    assert analysis.get("human")
    assert analysis.get("agents")
    assert analysis.get("combined")
    assert analysis.get("comparison")


def test_build_report_omits_incomplete_ai_baseline():
    alts = [{"id": 1, "alternative_title": "A"}, {"id": 2, "alternative_title": "B"}]
    ai = {
        "id": 11,
        "participant_id": 11,
        "source": "ai",
        "participant_key": AI_PARTICIPANT_KEY,
        "is_complete": False,
        "display_name": AI_DISPLAY_NAME,
    }
    ai_group = {
        "participant_id": 11,
        "group_type": "alternative",
        "status": "in_progress",
        "item_ids_initial": [1, 2],
        "rank_order": [],
        "pairings": [],
        "comparison_count": 0,
    }
    report = build_report_with_ai_baseline(
        alternatives=alts,
        factors=[],
        all_groups=[ai_group],
        participants=[ai],
    )
    assert report["unique_participants"] == 0
    assert (report.get("ai_baseline") or {}).get("available") is False


def _save_ai_voters(client, project, *, include=True, models=None):
    res = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": project.project_tag,
            "project_title": project.project_title,
            "project_description": project.project_description,
            "include_ai_agents": include,
            "ai_voter_models": list(models if models is not None else [DEFAULT_MODEL_KEY]),
            "disabled": False,
        },
    )
    assert res.status_code == 200, res.text
    assert not res.json().get("failure_reason"), res.json()
    got = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project.id}")
    assert got.status_code == 200
    info = got.json()["customer_project_info"]
    assert info.get("include_ai_agents") is include
    return info


def _ai_jobs(project):
    session = get_next_session()
    jobs = AiAgentJob.list_for_project(
        session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=True
    )
    return jobs


def _ai_parts(project):
    session = get_next_session()
    parts = ProjectVoteParticipant.list_for_project_system(
        session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=True
    )
    return [p for p in parts if p.source == VoteSource.ai]


def test_include_ai_agents_persists_on_create_and_update(client, account):
    as_user(client, account.admin.id)
    created = client.post(
        "/ws/custprojects/customer-project-create",
        json={
            "project_tag": uid("ai-inc"),
            "project_title": "Include AI",
            "project_description": "desc",
            "include_ai_agents": True,
            "ai_voter_models": ["glm-5.2", "glm-5.2", "default"],
            "disabled": False,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert not body.get("failure_reason"), body
    project = body["customer_project_info"]
    account.tracked_project_ids.append(project["id"])
    account.tracked_app_ids.append(project["id"])
    assert project.get("include_ai_agents") is True
    assert project.get("ai_voter_models") == ["glm-5.2", DEFAULT_MODEL_KEY]

    updated = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": project["project_tag"],
            "project_title": "Include AI",
            "project_description": "desc",
            "include_ai_agents": False,
            "ai_voter_models": ["glm-5.2", DEFAULT_MODEL_KEY],
            "disabled": False,
        },
    )
    assert updated.status_code == 200
    assert not updated.json().get("failure_reason"), updated.json()
    got = client.get(f"/ws/custprojects/customer-project-get-by-id?retrieve_by_id={project['id']}")
    info = got.json()["customer_project_info"]
    assert info.get("include_ai_agents") is False
    assert info.get("ai_voter_models") == ["glm-5.2", DEFAULT_MODEL_KEY]


def test_ai_baseline_run_forbidden_when_disabled(client, account):
    project = create_project(account)
    create_alternative(account, project_id=project.id, title="A")
    create_alternative(account, project_id=project.id, title="B")
    as_user(client, account.admin.id)
    res = client.post("/ws/project-votes/ai-baseline-run", json={"project_id": project.id})
    assert res.status_code == 403


def test_ai_baseline_run_skipped_when_include_off(client, account, monkeypatch):
    project = create_project(account, title="Office move")
    create_alternative(account, project_id=project.id, title="Downtown")
    create_alternative(account, project_id=project.id, title="Suburb")
    as_user(client, account.admin.id)
    with _ai_enabled(monkeypatch):
        _save_ai_voters(client, project, include=False, models=["glm-5.2", "grok-4.6"])
        res = client.post(
            "/ws/project-votes/ai-baseline-run",
            json={"project_id": project.id, "models": ["glm-5.2"]},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body.get("failure_reason")
        assert not (body.get("jobs") or [])
        assert _ai_jobs(project) == []
        assert _ai_parts(project) == []


def test_ai_baseline_run_empty_selection_when_include_on(client, account, monkeypatch):
    project = create_project(account, title="Office move")
    create_alternative(account, project_id=project.id, title="Downtown")
    create_alternative(account, project_id=project.id, title="Suburb")
    as_user(client, account.admin.id)
    with _ai_enabled(monkeypatch):
        _save_ai_voters(client, project, include=True, models=[])
        res = client.post("/ws/project-votes/ai-baseline-run", json={"project_id": project.id})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body.get("failure_reason")
        assert not (body.get("jobs") or [])
        assert _ai_jobs(project) == []


def test_ai_baseline_run_uses_saved_models_not_request(client, account, monkeypatch):
    project = create_project(account, title="Office move")
    create_alternative(account, project_id=project.id, title="Downtown")
    create_alternative(account, project_id=project.id, title="Suburb")
    as_user(client, account.admin.id)
    with _ai_enabled(monkeypatch):
        _save_ai_voters(client, project, include=True, models=["glm-5.2"])
        res = client.post(
            "/ws/project-votes/ai-baseline-run",
            json={"project_id": project.id, "models": ["grok-4.6"]},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert not body.get("failure_reason"), body
        jobs = _ai_jobs(project)
        assert len(jobs) == 1
        assert jobs[0].model_key == "glm-5.2"


def test_ai_baseline_run_dedupes_and_queues_new_models(client, account, monkeypatch):
    project = create_project(account, title="Office move")
    create_alternative(account, project_id=project.id, title="Downtown")
    create_alternative(account, project_id=project.id, title="Suburb")
    as_user(client, account.admin.id)
    with _ai_enabled(monkeypatch):
        _save_ai_voters(client, project, include=True, models=["default", "__default__", "glm-5.2"])
        first = client.post("/ws/project-votes/ai-baseline-run", json={"project_id": project.id})
        assert first.status_code == 200, first.text
        assert not first.json().get("failure_reason"), first.json()
        jobs = _ai_jobs(project)
        keys = sorted({j.model_key for j in jobs})
        assert keys == [DEFAULT_MODEL_KEY, "glm-5.2"]
        assert len(jobs) == 2

        replay = client.post("/ws/project-votes/ai-baseline-run", json={"project_id": project.id})
        assert replay.status_code == 200
        assert not replay.json().get("failure_reason"), replay.json()
        assert len(_ai_jobs(project)) == 2

        _save_ai_voters(client, project, include=True, models=["__default__", "glm-5.2", "grok-4.6"])
        added = client.post("/ws/project-votes/ai-baseline-run", json={"project_id": project.id})
        assert added.status_code == 200
        assert not added.json().get("failure_reason"), added.json()
        jobs = _ai_jobs(project)
        keys = sorted({j.model_key for j in jobs})
        assert keys == [DEFAULT_MODEL_KEY, "glm-5.2", "grok-4.6"]
        assert len(jobs) == 3


def test_ai_baseline_run_and_mocked_worker(client, account, monkeypatch):
    project = create_project(account, title="Office move")
    a1 = create_alternative(account, project_id=project.id, title="Downtown")
    a2 = create_alternative(account, project_id=project.id, title="Suburb")
    create_factor(account, project_id=project.id, title="Cost")
    as_user(client, account.admin.id)

    monkeypatch.setattr("src.utils.ai.worker.chat_text_sync", lambda **_k: "LEFT")
    with _ai_enabled(monkeypatch):
        _save_ai_voters(client, project, include=True, models=[DEFAULT_MODEL_KEY])
        res = client.post("/ws/project-votes/ai-baseline-run", json={"project_id": project.id})
        assert res.status_code == 200
        body = res.json()
        assert not body.get("failure_reason"), body
        assert body.get("already_complete") is False
        assert body.get("job", {}).get("status") == "queued"

        session = get_next_session()
        for _ in range(40):
            if not process_next_ai_job(session):
                break
        session.close()

        status = client.get("/ws/project-votes/ai-baseline-status", params={"project_id": project.id})
        assert status.status_code == 200
        st = status.json()
        assert st.get("already_complete") is True or (st.get("job") or {}).get("status") in ("complete", "in_progress", "queued")

        session = get_next_session()
        parts = ProjectVoteParticipant.list_for_project_system(
            session=session, customer_id=project.customer_id, project_id=project.id, clear_lock=False
        )
        ai_parts = [p for p in parts if p.source == VoteSource.ai]
        assert ai_parts
        assert ai_parts[0].participant_key in (AI_PARTICIPANT_KEY, "ai:system")
        assert ai_parts[0].is_ai is True
        assert str(ai_parts[0].display_name or "").startswith("AI AGENT:")
        groups = ProjectVoteGroupResult.list_for_participant_system(
            session=session, participant_id=ai_parts[0].id, clear_lock=True
        )
        assert groups
        assert any(g.pairings for g in groups)

        n_jobs = len(_ai_jobs(project))
        n_parts = len(_ai_parts(project))
        replay = client.post("/ws/project-votes/ai-baseline-run", json={"project_id": project.id})
        assert replay.status_code == 200
        assert len(_ai_jobs(project)) == n_jobs
        assert len(_ai_parts(project)) == n_parts

        report = client.post(
            "/ws/project-votes/project-report",
            json={"project_id": project.id, "include_participants": True},
        )
        assert report.status_code == 200
        rb = report.json()["report"]
        assert rb.get("unique_participants") == 0 or all(
            (p.get("source") != "ai") for p in (rb.get("participants") or [])
        )

    _ = (a1, a2)


def test_partition_vote_data_splits_ai():
    humans, hgroups, ais, agroups = partition_vote_data(
        [
            {"id": 1, "source": "session"},
            {"id": 2, "source": "ai", "participant_key": AI_PARTICIPANT_KEY},
        ],
        [
            {"participant_id": 1},
            {"participant_id": 2},
        ],
    )
    assert len(humans) == 1 and len(ais) == 1
    assert len(hgroups) == 1 and len(agroups) == 1


def test_encrypt_secret_roundtrip_and_blank():
    from src.pvf.utils.field_encryption import decrypt_secret, encrypt_secret, is_stored_secret

    assert encrypt_secret("") == ""
    assert decrypt_secret("") == ""
    stored = encrypt_secret("super-secret-key")
    assert stored != "super-secret-key"
    assert is_stored_secret(stored)
    assert decrypt_secret(stored) == "super-secret-key"


def test_unique_voter_models_dedupes_and_default():
    from src.utils.ai.config import DEFAULT_MODEL_KEY, unique_voter_models

    assert unique_voter_models(["glm-5.2", "glm-5.2", "grok-4.6"]) == ["glm-5.2", "grok-4.6"]
    assert unique_voter_models(["default", "__default__"]) == [DEFAULT_MODEL_KEY]


def test_customer_ai_settings_encrypts_and_masks(client, account, monkeypatch):
    as_user(client, account.admin.id)
    with _ai_enabled(monkeypatch):
        save = client.post(
            "/ws/core/customer-ai-settings",
            json={"ai_provider": "openrouter", "ai_model": "openai/gpt-4o", "ai_api_key": "plain-customer-key"},
        )
        assert save.status_code == 200, save.text
        body = save.json()
        assert not body.get("failure_reason"), body
        assert body.get("ai_provider") == "openrouter"
        assert body.get("ai_model") == "openai/gpt-4o"
        assert body.get("key_configured") is True
        stored = body.get("ai_api_key") or ""
        assert stored != "plain-customer-key"
        assert stored.startswith("enc:v1:")

        again = client.post(
            "/ws/core/customer-ai-settings",
            json={"ai_provider": "openrouter", "ai_model": "openai/gpt-4o", "ai_api_key": stored},
        )
        assert again.status_code == 200
        assert again.json().get("ai_api_key") == stored

        ctx = client.post("/ws/core/get-user-customer-context", json={"include_account_status": False})
        customer_record = ctx.json().get("customer_record") or {}
        assert "ai_api_key" not in customer_record
        blob = str(ctx.json()).lower()
        assert "plain-customer-key" not in blob


def test_customer_ai_settings_non_admin_forbidden(client, account, monkeypatch):
    as_user(client, account.member.id)
    with _ai_enabled(monkeypatch):
        res = client.post(
            "/ws/core/customer-ai-settings",
            json={"ai_provider": "opencode_go", "ai_api_key": "x"},
        )
    assert res.status_code == 200
    assert res.json().get("failure_reason")


def test_test_connection_uses_verify(client, account, monkeypatch):
    as_user(client, account.admin.id)

    def _fake_verify(provider, api_key, model=None):
        assert provider == "opencode_go"
        assert api_key == "plain-customer-key"
        return {"ok": True, "models": [{"id": "glm-5.2", "name": "GLM 5.2"}], "error": None, "provider": provider}

    monkeypatch.setattr("src.pvf.api.app_context_views.verify_llm_provider", _fake_verify)
    with _ai_enabled(monkeypatch):
        res = client.post(
            "/ws/core/test-customer-ai-connection",
            json={"ai_provider": "opencode_go", "ai_api_key": "plain-customer-key"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body.get("ok") is True
    assert body.get("models")[0]["id"] == "glm-5.2"


def _insert_job(project, *, status="queued", model_key="m", modify_date=None) -> int:
    session = get_next_session()
    row = AiAgentJob(
        customer_id=project.customer_id,
        project_id=project.id,
        job_type="ai_baseline",
        model_key=model_key,
        status=status,
        started_date=datetime.now() if status == "in_progress" else None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    if modify_date is not None:
        row.modify_date = modify_date
        session.add(row)
        session.commit()
        session.refresh(row)
    job_id = int(row.id)
    session.close()
    return job_id


def test_claim_next_fills_queued_under_cap(account, monkeypatch):
    project = create_project(account, title="Claim fill")
    queued_id = _insert_job(project, status="queued", model_key="q1")
    monkeypatch.setattr(AiAgentJob, "count_in_progress", staticmethod(lambda session, clear_lock=False: 0))
    session = get_next_session()
    claimed = AiAgentJob.claim_next(session, max_concurrent=2, clear_lock=False)
    claimed_id = claimed.id if claimed is not None else None
    claimed_status = claimed.status if claimed is not None else None
    started = claimed.started_date if claimed is not None else None
    session.close()
    assert claimed_id == queued_id
    assert claimed_status == "in_progress"
    assert started is not None


def test_claim_next_at_cap_does_not_start_queued(account, monkeypatch):
    project = create_project(account, title="Claim cap")
    queued_id = _insert_job(project, status="queued", model_key="q-cap")
    monkeypatch.setattr(AiAgentJob, "count_in_progress", staticmethod(lambda session, clear_lock=False: 2))
    session = get_next_session()
    claimed = AiAgentJob.claim_next(session, max_concurrent=2, clear_lock=False)
    claimed_id = claimed.id if claimed is not None else None
    claimed_status = claimed.status if claimed is not None else None
    held = session.get(AiAgentJob, queued_id)
    held_status = held.status if held is not None else None
    session.close()
    assert held_status == "queued"
    if claimed_id is not None:
        assert claimed_id != queued_id
        assert claimed_status == "in_progress"


def test_claim_next_round_robins_in_progress(account, monkeypatch):
    project = create_project(account, title="Claim rotate")
    older_id = _insert_job(project, status="in_progress", model_key="old", modify_date=datetime(2000, 1, 1))
    newer_id = _insert_job(project, status="in_progress", model_key="new", modify_date=datetime(2000, 1, 2))
    monkeypatch.setattr(AiAgentJob, "count_in_progress", staticmethod(lambda session, clear_lock=False: 2))
    session = get_next_session()
    first = AiAgentJob.claim_next(session, max_concurrent=2, clear_lock=False)
    first_id = first.id if first is not None else None
    second = AiAgentJob.claim_next(session, max_concurrent=2, clear_lock=False)
    second_id = second.id if second is not None else None
    session.close()
    assert first_id == older_id
    assert second_id == newer_id


def test_all_skipped_group_fails_job(account, monkeypatch):
    project = create_project(account, title="Skip abort")
    create_alternative(account, project_id=project.id, title="A")
    create_alternative(account, project_id=project.id, title="B")
    monkeypatch.setattr("src.utils.ai.worker.chat_text_sync", lambda **_k: "NOPE")
    with _ai_enabled(monkeypatch):
        session = get_next_session()
        job = AiAgentJob.enqueue_baseline(
            session=session,
            customer_id=project.customer_id,
            project_id=project.id,
            requested_by_user_id=account.admin.id,
            clear_lock=False,
        ).job_info
        assert job is not None
        _run_job(session, job)
        session.refresh(job)
        status = job.status
        error = job.error_summary
        skips = job.skip_count
        pairs = job.pair_count
        session.close()
    assert status == "failed"
    assert error == "AI baseline is incomplete"
    assert skips >= 1
    assert skips == pairs


def test_retryable_llm_error_does_not_skip(account, monkeypatch):
    project = create_project(account, title="Retry tick")
    create_alternative(account, project_id=project.id, title="A")
    create_alternative(account, project_id=project.id, title="B")

    def _boom(**_k):
        raise AiProviderError("temporarily unavailable", retryable=True)

    monkeypatch.setattr("src.utils.ai.worker.chat_text_sync", _boom)
    with _ai_enabled(monkeypatch):
        session = get_next_session()
        job = AiAgentJob.enqueue_baseline(
            session=session,
            customer_id=project.customer_id,
            project_id=project.id,
            requested_by_user_id=account.admin.id,
            clear_lock=False,
        ).job_info
        assert job is not None
        still_working = _run_job(session, job)
        session.refresh(job)
        status = job.status
        pairs = job.pair_count
        skips = job.skip_count
        session.close()
    assert still_working is True
    assert status != "failed"
    assert pairs == 0
    assert skips == 0


def test_factor_suggest_no_providers_message(client, account, monkeypatch):
    project = create_project(account, title="Pick a lunch")
    as_user(client, account.admin.id)
    settings._inject_startup_values({"ACTIVATE_AI_AGENTS": True})
    pvf_settings._inject_startup_values({"ACTIVATE_AI_AGENTS": True})
    monkeypatch.setattr(settings, "AI_API_KEY", "")
    monkeypatch.setattr(pvf_settings, "AI_API_KEY", "")
    try:
        res = client.post(
            "/ws/custproject-content/factor-suggest",
            json={"project_id": project.id, "project_title": "Pick a lunch", "project_description": "Choose a weekday lunch option"},
        )
    finally:
        settings._inject_startup_values({"ACTIVATE_AI_AGENTS": False})
        pvf_settings._inject_startup_values({"ACTIVATE_AI_AGENTS": False})
    assert res.status_code == 200
    assert "no providers configured" in str(res.json().get("failure_reason") or "").lower()
