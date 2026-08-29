from src.tests.helpers.auth_client import as_user
from src.tests.helpers.factories import create_project, create_alternative, create_factor, create_factor_template, uid


def test_alternative_crud(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)

    create_res = client.post(
        "/ws/custproject-content/alternative-create",
        json={
            "project_id": project.id,
            "alternative_title": "Option A",
            "alternative_description": "desc",
        },
    )
    assert create_res.status_code == 200
    body = create_res.json()
    assert body.get("failure_reason", "") in ("", None)
    alt = body["alternative_info"]
    account.tracked_alternative_ids.append(alt["id"])

    list_res = client.get(
        f"/ws/custproject-content/alternatives-get-by-project-id?project_id={project.id}"
    )
    assert list_res.status_code == 200
    rows = list_res.json().get("alternative_info_list") or []
    assert any(r["id"] == alt["id"] for r in rows)

    get_res = client.get(f"/ws/custproject-content/alternative-get-by-id?retrieve_by_id={alt['id']}")
    assert get_res.status_code == 200
    assert get_res.json().get("alternative_info", {}).get("id") == alt["id"]

    upd = client.post(
        "/ws/custproject-content/alternative-update",
        json={"alternative_id": alt["id"], "alternative_title": "Option A2"},
    )
    assert upd.status_code == 200
    assert upd.json().get("failure_reason", "") in ("", None)

    delete_res = client.request(
        "DELETE",
        "/ws/custproject-content/alternative-delete",
        json={"alternative_id": alt["id"]},
    )
    assert delete_res.status_code == 200
    assert delete_res.json().get("success") is True


def test_factor_crud(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)

    create_res = client.post(
        "/ws/custproject-content/factor-create",
        json={
            "project_id": project.id,
            "factor_title": "Cost",
            "factor_description": "lower is better",
            "factor_polarity_positive": False,
        },
    )
    assert create_res.status_code == 200
    body = create_res.json()
    assert body.get("failure_reason", "") in ("", None)
    factor = body["factor_info"]
    account.tracked_factor_ids.append(factor["id"])

    list_res = client.get(
        f"/ws/custproject-content/factors-get-by-project-id?project_id={project.id}"
    )
    assert list_res.status_code == 200
    rows = list_res.json().get("factor_info_list") or []
    assert any(r["id"] == factor["id"] for r in rows)

    delete_res = client.request(
        "DELETE",
        "/ws/custproject-content/factor-delete",
        json={"factor_id": factor["id"]},
    )
    assert delete_res.status_code == 200
    assert delete_res.json().get("success") is True


def test_factor_comparison_question_roundtrip(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    question = "Which option has lower Engineering Cost?"

    # comparison_question is deprecated on factor-create — writes are ignored, compare_prompt is canonical
    create_res = client.post(
        "/ws/custproject-content/factor-create",
        json={
            "project_id": project.id,
            "factor_title": "Engineering Cost",
            "factor_description": "Prefer lower cost",
            "comparison_question": f"  {question}  ",
        },
    )
    assert create_res.status_code == 200
    factor = create_res.json()["factor_info"]
    account.tracked_factor_ids.append(factor["id"])
    # writes disabled → stored as None (legacy reads ignored)
    assert factor.get("comparison_question") in (None, "")
    # compare_prompt is the canonical single question field
    cp_res = client.post(
        "/ws/custproject-content/factor-create",
        json={
            "project_id": project.id,
            "factor_title": "Cost Prompt",
            "factor_description": "Prefer lower cost",
            "compare_prompt": f"  {question}  ",
        },
    )
    assert cp_res.status_code == 200
    cp_factor = cp_res.json()["factor_info"]
    account.tracked_factor_ids.append(cp_factor["id"])
    # normalize_compare_prompt preserves question punctuation; blank becomes None
    assert cp_factor.get("compare_prompt") == question

    blank = client.post(
        "/ws/custproject-content/factor-create",
        json={
            "project_id": project.id,
            "factor_title": "Quality",
            "comparison_question": "   ",
        },
    )
    assert blank.status_code == 200
    blank_factor = blank.json()["factor_info"]
    account.tracked_factor_ids.append(blank_factor["id"])
    assert blank_factor.get("comparison_question") in (None, "")

    upd = client.post(
        "/ws/custproject-content/factor-update",
        json={"factor_id": factor["id"], "comparison_question": ""},
    )
    assert upd.status_code == 200
    got = client.get(f"/ws/custproject-content/factor-get-by-id?retrieve_by_id={factor['id']}")
    assert (got.json().get("factor_info") or {}).get("comparison_question") in (None, "")

    tmpl = client.post(
        "/ws/custproject-content/factor-template-create",
        json={
            "factor_template_title": "Cost questions",
            "factor_template_entries": [
                {
                    "factor_title": "Engineering Cost",
                    "factor_description": "Prefer lower cost",
                    "comparison_question": f"  {question}  ",
                }
            ],
            "use_with_factors": True,
        },
    )
    assert tmpl.status_code == 200
    info = tmpl.json()["factor_template_info"]
    account.tracked_template_ids.append(info["id"])
    entries = info.get("factor_template_entries") or []
    assert entries[0].get("comparison_question") == question


def test_alternative_non_admin_forbidden(client, account):
    project = create_project(account)
    as_user(client, account.member.id)
    response = client.post(
        "/ws/custproject-content/alternative-create",
        json={"project_id": project.id, "alternative_title": "X"},
    )
    assert response.status_code == 403


def test_alternative_cross_tenant_denied(client, account, other_account):
    project = create_project(other_account)
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/custproject-content/alternative-create",
        json={"project_id": project.id, "alternative_title": "steal"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason")


def test_factor_template_create_and_list(client, account):
    as_user(client, account.admin.id)
    create_res = client.post(
        "/ws/custproject-content/factor-template-create",
        json={
            "factor_template_title": "Default criteria",
            "factor_template_description": "desc",
            "factor_template_entries": [
                {"factor_title": "Cost", "factor_polarity_positive": False},
                {"factor_title": "Quality", "factor_polarity_positive": True},
            ],
            "option_template_entries": [
                {"alternative_title": "Option A", "alternative_description": "first"},
            ],
            "use_with_projects": True,
            "use_with_options": True,
            "use_with_factors": True,
            "project_exclusive_mode": True,
            "private_participation": True,
            "enable_global_share": False,
        },
    )
    assert create_res.status_code == 200
    body = create_res.json()
    assert body.get("failure_reason", "") in ("", None)
    template = body["factor_template_info"]
    account.tracked_template_ids.append(template["id"])
    assert template.get("use_with_projects") is True
    assert template.get("use_with_options") is True
    assert template.get("private_participation") is True
    assert len(template.get("option_template_entries") or []) == 1

    all_res = client.get("/ws/custproject-content/factor-templates-get-all")
    assert all_res.status_code == 200
    rows = all_res.json().get("factor_template_info_list") or []
    assert any(r["id"] == template["id"] for r in rows)

    avail = client.get("/ws/custproject-content/factor-templates-get-available")
    assert avail.status_code == 200
    avail_rows = avail.json().get("factor_template_info_list") or []
    assert any(r["id"] == template["id"] for r in avail_rows)

    projects = client.get("/ws/custproject-content/factor-templates-get-available?for_use=projects")
    assert any(r["id"] == template["id"] for r in (projects.json().get("factor_template_info_list") or []))

    upd = client.post(
        "/ws/custproject-content/factor-template-update",
        json={
            "factor_template_id": template["id"],
            "use_with_options": False,
            "factor_template_title": "Default criteria",
        },
    )
    assert upd.status_code == 200
    assert upd.json().get("failure_reason", "") in ("", None)
    got = client.get(f"/ws/custproject-content/factor-template-get-by-id?retrieve_by_id={template['id']}")
    info = got.json().get("factor_template_info") or {}
    assert info.get("use_with_options") is False
    assert info.get("use_with_projects") is True  # partial update preserves other fields
    assert info.get("private_participation") is True


def test_factor_template_global_share_requires_sysadmin(client, account, sysadmin_account, other_account):
    as_user(client, account.admin.id)
    denied = client.post(
        "/ws/custproject-content/factor-template-create",
        json={
            "factor_template_title": "Global try",
            "enable_global_share": True,
        },
    )
    assert denied.status_code == 200
    assert denied.json().get("failure_reason")

    as_user(client, sysadmin_account.admin.id)
    ok = client.post(
        "/ws/custproject-content/factor-template-create",
        json={
            "factor_template_title": "Global template",
            "enable_global_share": True,
            "factor_template_entries": [{"factor_title": "Risk", "factor_polarity_positive": False}],
            "use_with_factors": True,
        },
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body.get("failure_reason", "") in ("", None)
    template = body["factor_template_info"]
    sysadmin_account.tracked_template_ids.append(template["id"])
    assert template.get("enable_global_share") is True

    as_user(client, other_account.admin.id)
    avail = client.get("/ws/custproject-content/factor-templates-get-available")
    assert avail.status_code == 200
    rows = avail.json().get("factor_template_info_list") or []
    assert any(r["id"] == template["id"] for r in rows)

    # other tenant cannot update foreign global template
    upd = client.post(
        "/ws/custproject-content/factor-template-update",
        json={
            "factor_template_id": template["id"],
            "factor_template_title": "hijack",
            "enable_global_share": True,
        },
    )
    assert upd.status_code == 200
    assert upd.json().get("failure_reason") or upd.json().get("factor_template_id") in (-1, None)

    # non-sysadmin cannot enable global share via update on own template
    as_user(client, account.admin.id)
    own = client.post(
        "/ws/custproject-content/factor-template-create",
        json={
            "factor_template_title": "Local only",
            "factor_template_entries": [{"factor_title": "A"}],
            "enable_global_share": False,
        },
    )
    own_body = own.json()["factor_template_info"]
    account.tracked_template_ids.append(own_body["id"])
    deny_share = client.post(
        "/ws/custproject-content/factor-template-update",
        json={
            "factor_template_id": own_body["id"],
            "enable_global_share": True,
        },
    )
    assert deny_share.status_code == 200
    assert deny_share.json().get("failure_reason")


def test_list_by_project_via_factory(client, account):
    project = create_project(account)
    create_alternative(account, project_id=project.id)
    create_factor(account, project_id=project.id)
    as_user(client, account.admin.id)
    alts = client.get(f"/ws/custproject-content/alternatives-get-by-project-id?project_id={project.id}")
    factors = client.get(f"/ws/custproject-content/factors-get-by-project-id?project_id={project.id}")
    assert len(alts.json().get("alternative_info_list") or []) >= 1
    assert len(factors.json().get("factor_info_list") or []) >= 1


def test_group_size_retargets_on_item_add_remove_unless_explicit(client, account):
    from src.utils.sort_compare import default_questions_per_group_for_n

    project = create_project(account)
    as_user(client, account.admin.id)
    tag = project.project_tag
    ids = []
    for title in ("A", "B", "C", "D", "E"):
        res = client.post(
            "/ws/custproject-content/alternative-create",
            json={"project_id": project.id, "alternative_title": title},
        )
        assert res.status_code == 200
        body = res.json()
        assert not body.get("failure_reason"), body
        alt = body["alternative_info"]
        ids.append(alt["id"])
        account.tracked_alternative_ids.append(alt["id"])

    got = client.get(f"/ws/custprojects/customer-project-get-by-tag?retrieve_by_tag={tag}")
    info = got.json()["customer_project_info"]
    assert info["option_questions_per_group_explicit"] is False
    assert info["option_questions_per_group"] == default_questions_per_group_for_n(5)

    locked = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": tag,
            "project_title": project.project_title,
            "project_description": project.project_description,
            "option_questions_per_group": 8,
            "option_questions_per_group_explicit": True,
        },
    )
    assert locked.status_code == 200
    assert not locked.json().get("failure_reason"), locked.json()

    extra = client.post(
        "/ws/custproject-content/alternative-create",
        json={"project_id": project.id, "alternative_title": "F"},
    )
    assert extra.status_code == 200
    extra_id = extra.json()["alternative_info"]["id"]
    account.tracked_alternative_ids.append(extra_id)
    got = client.get(f"/ws/custprojects/customer-project-get-by-tag?retrieve_by_tag={tag}")
    info = got.json()["customer_project_info"]
    assert info["option_questions_per_group_explicit"] is True
    assert info["option_questions_per_group"] == 8

    reset = client.post(
        "/ws/custprojects/customer-project-update",
        json={
            "project_tag": tag,
            "project_title": project.project_title,
            "project_description": project.project_description,
            "option_questions_per_group_explicit": False,
        },
    )
    assert reset.status_code == 200
    got = client.get(f"/ws/custprojects/customer-project-get-by-tag?retrieve_by_tag={tag}")
    info = got.json()["customer_project_info"]
    assert info["option_questions_per_group_explicit"] is False
    assert info["option_questions_per_group"] == default_questions_per_group_for_n(6)

    deleted = client.request(
        "DELETE",
        "/ws/custproject-content/alternative-delete",
        json={"alternative_id": extra_id},
    )
    assert deleted.status_code == 200
    got = client.get(f"/ws/custprojects/customer-project-get-by-tag?retrieve_by_tag={tag}")
    info = got.json()["customer_project_info"]
    assert info["option_questions_per_group_explicit"] is False
    assert info["option_questions_per_group"] == default_questions_per_group_for_n(5)
