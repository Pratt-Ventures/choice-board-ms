"""Startup seeding of global shared templates from project_templates.yml."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import select

from src.db.models.customer_project_alternatives_criteria import CustomerFactorTemplates
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.auth_client import as_user
from src.tests.helpers.factories import uid
from src.utils.bootstrap_system_templates import (
    _criteria_templates_path,
    _load_yaml_templates,
    _project_templates_path,
    bootstrap_system_shared_templates,
)


def test_project_templates_yml_has_sample_sets():
    path = _project_templates_path()
    assert path.is_file(), f"missing {path}"
    assert path.name == "project_templates.yml"
    specs = _load_yaml_templates(path)
    assert 5 <= len(specs) <= 6
    titles = {s.get("factor_template_title") for s in specs}
    assert "Project Prioritization" in titles
    assert "Large Purchase Vendor Alternatives" in titles
    assert "Team 360 Evaluation" in titles
    for spec in specs:
        entries = spec.get("factor_template_entries") or []
        assert 3 <= len(entries) <= 6
        for e in entries:
            assert e.get("factor_title")
        title = spec.get("factor_template_title")
        if title == "Team 360 Evaluation":
            assert spec.get("use_with_projects") is True
            assert spec.get("use_with_factors") is True
            assert spec.get("private_participation") is True
            assert (spec.get("factor_template_description") or "").strip()
        else:
            assert spec.get("use_with_factors") is True
            assert spec.get("use_with_projects") in (False, None)


def test_criteria_templates_path_alias():
    assert _criteria_templates_path() == _project_templates_path()


def test_bootstrap_seeds_missing_titles_only(sysadmin_account, mocker):
    session = get_next_session()
    try:
        already_title = uid("tmpl-already")
        new_title = uid("tmpl-new")
        existing = CustomerFactorTemplates(
            customer_id=sysadmin_account.customer.id,
            enable_global_share=True,
            factor_template_title=already_title,
            factor_template_description="skip me",
            factor_template_entries=[{"factor_title": "A", "factor_description": None, "factor_polarity_positive": True, "factor_polarity_note": None}],
            use_with_factors=True,
            use_with_projects=False,
            use_with_options=False,
            project_exclusive_mode=False,
            private_participation=False,
            option_template_entries=[],
        )
        session.add(existing)
        session.commit()
        session.refresh(existing)
        sysadmin_account.tracked_template_ids.append(existing.id)

        mocker.patch(
            "src.utils.bootstrap_system_templates._find_system_admins",
            return_value=[sysadmin_account.admin],
        )
        mocker.patch(
            "src.utils.bootstrap_system_templates._load_yaml_templates",
            return_value=[
                {
                    "factor_template_title": already_title,
                    "factor_template_description": "skip me",
                    "factor_template_entries": [{"factor_title": "A"}],
                    "use_with_factors": True,
                },
                {
                    "factor_template_title": new_title,
                    "factor_template_description": "create me",
                    "factor_template_entries": [{"factor_title": "B"}],
                    "use_with_projects": True,
                    "use_with_factors": True,
                    "private_participation": True,
                },
            ],
        )
        created = bootstrap_system_shared_templates(session)
        assert created == 1
        rows = list(
            session.exec(
                select(CustomerFactorTemplates).where(
                    CustomerFactorTemplates.customer_id == sysadmin_account.customer.id,
                    CustomerFactorTemplates.factor_template_title == new_title,
                    CustomerFactorTemplates.deleted_date == None,  # noqa: E711
                )
            ).all()
        )
        assert len(rows) == 1
        assert rows[0].enable_global_share is True
        assert rows[0].use_with_projects is True
        assert rows[0].use_with_factors is True
        assert rows[0].private_participation is True
        sysadmin_account.tracked_template_ids.append(rows[0].id)
    finally:
        session.close()


def test_bootstrap_skips_soft_deleted_and_disabled_titles(sysadmin_account, mocker):
    session = get_next_session()
    try:
        soft_title = uid("tmpl-soft")
        disabled_title = uid("tmpl-dis")
        soft = CustomerFactorTemplates(
            customer_id=sysadmin_account.customer.id,
            enable_global_share=True,
            factor_template_title=soft_title,
            factor_template_entries=[{"factor_title": "X"}],
            deleted_date=datetime.now(),
        )
        disabled = CustomerFactorTemplates(
            customer_id=sysadmin_account.customer.id,
            enable_global_share=True,
            factor_template_title=disabled_title,
            factor_template_entries=[{"factor_title": "Y"}],
            disabled=True,
        )
        session.add(soft)
        session.add(disabled)
        session.commit()
        session.refresh(soft)
        session.refresh(disabled)
        sysadmin_account.tracked_template_ids.extend([soft.id, disabled.id])

        mocker.patch(
            "src.utils.bootstrap_system_templates._find_system_admins",
            return_value=[sysadmin_account.admin],
        )
        mocker.patch(
            "src.utils.bootstrap_system_templates._load_yaml_templates",
            return_value=[
                {
                    "factor_template_title": soft_title,
                    "factor_template_entries": [{"factor_title": "X"}],
                },
                {
                    "factor_template_title": disabled_title,
                    "factor_template_entries": [{"factor_title": "Y"}],
                },
            ],
        )
        created = bootstrap_system_shared_templates(session)
        assert created == 0
        active_soft = list(
            session.exec(
                select(CustomerFactorTemplates).where(
                    CustomerFactorTemplates.enable_global_share == True,  # noqa: E712
                    CustomerFactorTemplates.deleted_date == None,  # noqa: E711
                    CustomerFactorTemplates.factor_template_title == soft_title,
                )
            ).all()
        )
        assert active_soft == []
    finally:
        session.close()


def test_bootstrap_seeds_when_no_globals(sysadmin_account, mocker):
    session = get_next_session()
    try:
        mocker.patch(
            "src.utils.bootstrap_system_templates._existing_global_templates_by_title",
            return_value={},
        )
        mocker.patch(
            "src.utils.bootstrap_system_templates._find_system_admins",
            return_value=[sysadmin_account.admin],
        )
        created = bootstrap_system_shared_templates(session)
        assert created >= 5
        rows = list(
            session.exec(
                select(CustomerFactorTemplates).where(
                    CustomerFactorTemplates.customer_id == sysadmin_account.customer.id,
                    CustomerFactorTemplates.enable_global_share == True,  # noqa: E712
                    CustomerFactorTemplates.deleted_date == None,  # noqa: E711
                )
            ).all()
        )
        assert len(rows) >= 5
        by_title = {r.factor_template_title: r for r in rows}
        for r in rows:
            sysadmin_account.tracked_template_ids.append(r.id)
            assert r.enable_global_share is True
            assert r.factor_template_entries
        team = by_title.get("Team 360 Evaluation")
        if team:
            assert team.use_with_projects is True
            assert team.use_with_factors is True
            assert team.private_participation is True
    finally:
        session.close()


def test_bootstrap_updates_existing_global_flags(sysadmin_account, mocker):
    session = get_next_session()
    try:
        title = uid("tmpl-upd")
        row = CustomerFactorTemplates(
            customer_id=sysadmin_account.customer.id,
            enable_global_share=True,
            factor_template_title=title,
            factor_template_description="old",
            factor_template_entries=[{"factor_title": "Old"}],
            use_with_projects=False,
            use_with_factors=True,
            private_participation=False,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        sysadmin_account.tracked_template_ids.append(row.id)

        mocker.patch(
            "src.utils.bootstrap_system_templates._find_system_admins",
            return_value=[sysadmin_account.admin],
        )
        mocker.patch(
            "src.utils.bootstrap_system_templates._load_yaml_templates",
            return_value=[
                {
                    "factor_template_title": title,
                    "factor_template_description": "new desc",
                    "factor_template_entries": [{"factor_title": "New"}],
                    "use_with_projects": True,
                    "use_with_factors": True,
                    "private_participation": True,
                },
            ],
        )
        created = bootstrap_system_shared_templates(session)
        assert created == 0
        session.refresh(row)
        assert row.factor_template_description == "new desc"
        assert row.use_with_projects is True
        assert row.private_participation is True
        assert row.factor_template_entries[0]["factor_title"] == "New"
    finally:
        session.close()


def test_bootstrap_no_sysadmin_logs(mocker):
    session = get_next_session()
    try:
        mocker.patch(
            "src.utils.bootstrap_system_templates._find_system_admins",
            return_value=[],
        )
        log_mock = mocker.patch("src.utils.bootstrap_system_templates.log_event", return_value=1)
        created = bootstrap_system_shared_templates(session)
        assert created == 0
        assert log_mock.called
        args, kwargs = log_mock.call_args
        assert "no system admin" in args[0].lower()
        assert kwargs.get("severity") == 2
    finally:
        session.close()


def test_seeded_globals_visible_to_other_tenant(client, other_account):
    as_user(client, other_account.admin.id)
    avail = client.get("/ws/custproject-content/factor-templates-get-available")
    assert avail.status_code == 200
    titles = {
        (r.get("factor_template_title") or "")
        for r in (avail.json().get("factor_template_info_list") or [])
        if r.get("enable_global_share")
    }
    assert "Project Prioritization" in titles
    assert "Large Purchase Vendor Alternatives" in titles

    factors_only = client.get("/ws/custproject-content/factor-templates-get-available?for_use=factors")
    assert factors_only.status_code == 200
    factor_titles = {
        (r.get("factor_template_title") or "")
        for r in (factors_only.json().get("factor_template_info_list") or [])
        if r.get("enable_global_share")
    }
    assert "Project Prioritization" in factor_titles

    projects_only = client.get("/ws/custproject-content/factor-templates-get-available?for_use=projects")
    assert projects_only.status_code == 200
    project_titles = {
        (r.get("factor_template_title") or "")
        for r in (projects_only.json().get("factor_template_info_list") or [])
        if r.get("enable_global_share")
    }
    assert "Team 360 Evaluation" in project_titles
    assert "Project Prioritization" not in project_titles
