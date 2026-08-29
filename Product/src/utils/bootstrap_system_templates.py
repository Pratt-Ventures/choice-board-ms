"""Load global shared project templates from project_templates.yml at startup."""
from __future__ import annotations

from pathlib import Path

import yaml
from sqlmodel import Session, select

from ..db.models.customer_project_alternatives_criteria import (
    CustomerFactorTemplates,
    FactorTemplateEntry,
    OptionTemplateEntry,
    _normalize_option_template_entries,
    _normalize_template_entries,
)
from ..pvf.bindings.pvf_services import PvfUser, log_event


def _workspace_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _project_templates_path() -> Path:
    root = _workspace_root()
    primary = root / "project_templates.yml"
    if primary.is_file():
        return primary
    # Backward-compatible fallback during rename
    return root / "criteria_templates.yml"


# Keep old name as alias for tests/imports that still reference it
def _criteria_templates_path() -> Path:
    return _project_templates_path()


def _load_yaml_templates(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    templates = data.get("templates") or []
    if not isinstance(templates, list):
        return []
    return [t for t in templates if isinstance(t, dict)]


def _find_system_admins(session: Session) -> list[PvfUser]:
    return list(
        session.exec(
            select(PvfUser).where(
                PvfUser.system_user_mode >= 2,
                PvfUser.deleted_date == None,  # noqa: E711
                PvfUser.access_disabled == 0,
            )
        ).all()
    )


def _existing_global_templates_by_title(session: Session) -> dict[str, CustomerFactorTemplates]:
    """Active and inactive global templates keyed by title.

    Soft-deleted and disabled rows count as existing so they are not re-created.
    """
    rows = session.exec(
        select(CustomerFactorTemplates).where(
            CustomerFactorTemplates.enable_global_share == True,  # noqa: E712
        )
    ).all()
    by_title: dict[str, CustomerFactorTemplates] = {}
    for row in rows:
        title = (row.factor_template_title or "").strip()
        if title and title not in by_title:
            by_title[title] = row
    return by_title


def _existing_global_template_titles(session: Session) -> set[str]:
    return set(_existing_global_templates_by_title(session).keys())


def _entries_from_yaml(raw_entries: list | None) -> list[dict]:
    if not raw_entries:
        return []
    normalized: list[FactorTemplateEntry] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        normalized.append(
            FactorTemplateEntry(
                factor_title=entry.get("factor_title"),
                factor_description=entry.get("factor_description"),
                comparison_question=entry.get("comparison_question"),
                factor_polarity_positive=bool(entry.get("factor_polarity_positive", True)),
                factor_polarity_note=entry.get("factor_polarity_note"),
            )
        )
    return _normalize_template_entries(normalized) or []


def _option_entries_from_yaml(raw_entries: list | None) -> list[dict]:
    if not raw_entries:
        return []
    normalized: list[OptionTemplateEntry] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        title = entry.get("alternative_title") or entry.get("option_title")
        desc = entry.get("alternative_description") or entry.get("option_description")
        normalized.append(
            OptionTemplateEntry(
                alternative_title=title,
                alternative_description=desc,
            )
        )
    return _normalize_option_template_entries(normalized) or []


def _bool_from_spec(spec: dict, key: str, default: bool) -> bool:
    if key not in spec or spec.get(key) is None:
        return default
    return bool(spec.get(key))


def _row_fields_from_spec(spec: dict) -> dict:
    return {
        "factor_template_description": spec.get("factor_template_description"),
        "factor_template_entries": _entries_from_yaml(spec.get("factor_template_entries")),
        "option_template_entries": _option_entries_from_yaml(spec.get("option_template_entries")),
        "use_with_projects": _bool_from_spec(spec, "use_with_projects", False),
        "use_with_options": _bool_from_spec(spec, "use_with_options", False),
        "use_with_factors": _bool_from_spec(spec, "use_with_factors", True),
        "project_exclusive_mode": _bool_from_spec(spec, "project_exclusive_mode", False),
        "private_participation": _bool_from_spec(spec, "private_participation", False),
    }


def bootstrap_system_shared_templates(session: Session) -> int:
    """
    Ensure each system-shared template from project_templates.yml exists.

    - Soft-deleted or disabled global templates count as existing (not re-seeded).
    - Active globals matching a YAML title have use flags and content refreshed from YAML
      (YAML is source of truth for system-shared seeds; enable_global_share stays true).
    - Titles missing entirely are created.
    - If no system admin users: severity-2 log_event and no inserts.
    - New rows are owned by the first system admin's customer with enable_global_share=True.

    Returns number of templates created (updates are not counted).
    """
    admins = _find_system_admins(session)
    if not admins:
        log_event(
            "bootstrap_system_shared_templates: no system admin users found; "
            "cannot seed global shared templates",
            severity=2,
        )
        return 0

    owner = admins[0]
    yaml_path = _project_templates_path()
    specs = _load_yaml_templates(yaml_path)
    if not specs:
        log_event(
            f"bootstrap_system_shared_templates: system admins present but no templates "
            f"defined in {yaml_path}",
            severity=2,
            customer_id=owner.customer_id,
            user_id=owner.id,
        )
        return 0

    existing_by_title = _existing_global_templates_by_title(session)
    created = 0
    updated = 0
    for spec in specs:
        title = (spec.get("factor_template_title") or "").strip()
        if not title:
            continue
        fields = _row_fields_from_spec(spec)
        existing = existing_by_title.get(title)
        if existing is not None:
            # Do not revive soft-deleted or disabled system templates
            if existing.deleted_date is not None or existing.disabled:
                continue
            changed = False
            for key, value in fields.items():
                if getattr(existing, key) != value:
                    setattr(existing, key, value)
                    changed = True
            if changed:
                session.add(existing)
                updated += 1
            continue

        row = CustomerFactorTemplates(
            customer_id=owner.customer_id,
            enable_global_share=True,
            factor_template_title=title,
            disabled=False,
            **fields,
        )
        session.add(row)
        existing_by_title[title] = row
        created += 1

    if created or updated:
        session.commit()
        log_event(
            f"bootstrap_system_shared_templates: seeded {created} / updated {updated} global "
            f"template(s) from {yaml_path.name} under customer_id={owner.customer_id} "
            f"(system admin user_id={owner.id})",
            severity=2,
            customer_id=owner.customer_id,
            user_id=owner.id,
            details_json={
                "created_count": created,
                "updated_count": updated,
                "yaml_path": str(yaml_path),
            },
        )
    return created
