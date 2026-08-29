from __future__ import annotations
from typing import Union, Any, List
from datetime import datetime

from pydantic import field_validator
from sqlmodel import SQLModel, Field, Session, select, or_
from sqlalchemy import func, DateTime, Column
from sqlalchemy.dialects.postgresql import JSONB

from ...pvf.bindings.pvf_services import PvfWsResultPackage, PvfUserContext, PvfCustomer, log_event
from ...utils.comparison_question import normalize_comparison_question
from ...utils.compare_prompt import normalize_compare_prompt

from .customer_projects import CustomerProject


class FactorTemplateEntry(SQLModel):
    factor_title: str | None = Field(default=None, description="Title of the factor within the template")
    factor_description: str | None = Field(default=None, description="Description of the factor within the template")
    comparison_question: str | None = Field(
        default=None,
        description="Optional question wording used when comparing options on this factor",
    )
    factor_polarity_positive: bool = Field(default=True, description="Indicates the polarity of the factor; True for positive, False for negative")
    factor_polarity_note: str | None = Field(default=None, description="Additional short string used in UI to distinguish the better outcome if not typical language based on polarity setting")

    @field_validator("comparison_question", mode="before")
    @classmethod
    def _normalize_comparison_question(cls, value: Any) -> str | None:
        return normalize_comparison_question(value)


class OptionTemplateEntry(SQLModel):
    alternative_title: str | None = Field(default=None, description="Title of the option within the template")
    alternative_description: str | None = Field(default=None, description="Description of the option within the template")


# --- Project / factor templates result DTOs ---

class CustomerFactorTemplateResult_One_Id(PvfWsResultPackage):
    factor_template_id: Union[int, None] = None

class CustomerFactorTemplateResult_One(PvfWsResultPackage):
    factor_template_info: Union[CustomerFactorTemplates, None] = None

class CustomerFactorTemplateResult_Many(PvfWsResultPackage):
    factor_template_info_list: Union[List[CustomerFactorTemplates], None] = None

class CustomerFactorTemplateDeleteResult(PvfWsResultPackage):
    success: bool = Field(default=False, description="Bool indicates if soft delete was successful")
    factor_template_id: int | None = Field(default=None, description="The internal ID of the template that was deleted")


# --- Project Alternatives result DTOs ---

class CustomerProjectAlternativeResult_One_Id(PvfWsResultPackage):
    alternative_id: Union[int, None] = None

class CustomerProjectAlternativeResult_One(PvfWsResultPackage):
    alternative_info: Union[CustomerProjectAlternatives, None] = None

class CustomerProjectAlternativeResult_Many(PvfWsResultPackage):
    alternative_info_list: Union[List[CustomerProjectAlternatives], None] = None

class CustomerProjectAlternativeDeleteResult(PvfWsResultPackage):
    success: bool = Field(default=False, description="Bool indicates if soft delete was successful")
    alternative_id: int | None = Field(default=None, description="Internal ID of the option (alternative) that was deleted")


# --- Project Factors result DTOs ---

class CustomerProjectFactorResult_One_Id(PvfWsResultPackage):
    factor_id: Union[int, None] = None

class CustomerProjectFactorResult_One(PvfWsResultPackage):
    factor_info: Union[CustomerProjectFactors, None] = None

class CustomerProjectFactorResult_Many(PvfWsResultPackage):
    factor_info_list: Union[List[CustomerProjectFactors], None] = None

class CustomerProjectFactorDeleteResult(PvfWsResultPackage):
    success: bool = Field(default=False, description="Bool indicates if soft delete was successful")
    factor_id: int | None = Field(default=None, description="The internal ID of the factor that was deleted")


def _normalize_template_entries(
    entries: list[FactorTemplateEntry] | list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    """Coerce API FactorTemplateEntry models to plain dicts for JSONB storage."""
    if entries is None:
        return None
    result: list[dict[str, Any]] = []
    for entry in entries:
        if isinstance(entry, FactorTemplateEntry):
            result.append(entry.model_dump())
        elif isinstance(entry, dict):
            result.append(FactorTemplateEntry.model_validate(entry).model_dump())
        elif hasattr(entry, "model_dump"):
            result.append(FactorTemplateEntry.model_validate(entry.model_dump()).model_dump())
        else:
            result.append(FactorTemplateEntry.model_validate(dict(entry)).model_dump())
    return result


def _normalize_option_template_entries(
    entries: list[OptionTemplateEntry] | list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    """Coerce option template entries to plain dicts for JSONB storage."""
    if entries is None:
        return None
    result: list[dict[str, Any]] = []
    for entry in entries:
        if isinstance(entry, OptionTemplateEntry):
            result.append(entry.model_dump())
        elif isinstance(entry, dict):
            # Accept option_title aliases from YAML/UI
            raw = dict(entry)
            if "alternative_title" not in raw and "option_title" in raw:
                raw["alternative_title"] = raw.pop("option_title")
            if "alternative_description" not in raw and "option_description" in raw:
                raw["alternative_description"] = raw.pop("option_description")
            result.append(OptionTemplateEntry.model_validate(raw).model_dump())
        elif hasattr(entry, "model_dump"):
            result.append(OptionTemplateEntry.model_validate(entry.model_dump()).model_dump())
        else:
            result.append(OptionTemplateEntry.model_validate(dict(entry)).model_dump())
    return result


class CustomerFactorTemplates(SQLModel, table=True):
    """Project/option/factor templates (table name kept for compatibility).

    Import is always a one-time copy into a project — no live link after apply.
    Visibility on Project / Options / Factors pages is controlled by use_with_*.
    """
    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True, unique=False)
    enable_global_share: bool = Field(default=False, description="Shared globally across all workspaces; only system admins may enable")
    factor_template_title: str | None = Field(default=None, description="Title of the template")
    factor_template_description: str | None = Field(default=None, description="Description of the template")
    factor_template_entries: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(JSONB, default=None, nullable=True),
        description="List of factor entry dicts (factor_title, factor_description, comparison_question, factor_polarity_*)",
    )
    option_template_entries: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(JSONB, default=None, nullable=True),
        description="List of option entry dicts (alternative_title, alternative_description)",
    )
    use_with_projects: bool = Field(default=False, description="Offer for import on the project settings page (full project scope)")
    use_with_options: bool = Field(default=False, description="Offer for import on the options page (options only)")
    use_with_factors: bool = Field(default=True, description="Offer for import on the factors page (factors only)")
    project_exclusive_mode: bool = Field(default=False, description="Pick one mode when imported at project scope (true); rank all when false")
    private_participation: bool = Field(default=False, description="Private participation setting when imported at project scope")
    disabled: bool = Field(default=False, description="Indicates a disabled template if true")
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))
    deleted_date: datetime | None = Field(default=None, description="Date entry was deleted; if not None, entry is considered deleted and not active")

    def _normalize_payload(self) -> None:
        self.factor_template_entries = _normalize_template_entries(self.factor_template_entries)
        self.option_template_entries = _normalize_option_template_entries(self.option_template_entries)

    def create_factor_template(self, session: Session, usr_context: PvfUserContext) -> CustomerFactorTemplateResult_One:
        if self.customer_id != usr_context.sess_user.customer_id:
            log_id = log_event(f"create_factor_template: PvfCustomer ID mismatch: {self.customer_id} != {usr_context.sess_user.customer_id}", usr_context=usr_context, severity=4)
            return CustomerFactorTemplateResult_One(failure_reason=f"Internal failure - PvfCustomer ID mismatch", log_id=log_id)
        if self.enable_global_share and usr_context.sess_user.system_user_mode < 2:
            log_id = log_event("create_factor_template: enable_global_share requires system admin", usr_context=usr_context, severity=3)
            return CustomerFactorTemplateResult_One(failure_reason="Not allowed; system user required to enable global share", log_id=log_id)
        if self.enable_global_share:
            log_event(
                f"create_factor_template: global share enabled for template title={self.factor_template_title!r}",
                usr_context=usr_context,
                severity=2,
            )
        self._normalize_payload()
        session.add(self)
        session.commit()
        session.refresh(self)
        return CustomerFactorTemplateResult_One(factor_template_info=self)

    def create_factor_template_system(self, session: Session, usr_context: PvfUserContext) -> CustomerFactorTemplateResult_One:
        if self.customer_id != usr_context.sess_user.customer_id and usr_context.sess_user.system_user_mode < 2:
            log_id = log_event(f"create_factor_template_system: PvfCustomer ID mismatch or non sys-admin", usr_context=usr_context, severity=4)
            return CustomerFactorTemplateResult_One(failure_reason="Internal failure - PvfCustomer ID mismatch", log_id=log_id)
        if self.enable_global_share and usr_context.sess_user.system_user_mode < 2:
            log_id = log_event("create_factor_template_system: enable_global_share requires system admin", usr_context=usr_context, severity=3)
            return CustomerFactorTemplateResult_One(failure_reason="Not allowed; system user required to enable global share", log_id=log_id)
        self._normalize_payload()
        session.add(self)
        session.commit()
        session.refresh(self)
        return CustomerFactorTemplateResult_One(factor_template_info=self)

    def update_factor_template(
        self,
        session: Session,
        usr_context: PvfUserContext,
        clear_lock: bool = True,
        update_fields: dict[str, Any] | None = None,
    ) -> CustomerFactorTemplateResult_One:
        existing_result = CustomerFactorTemplates.get_factor_template_by_id(session, id=self.id, usr_context=usr_context, clear_lock=False)
        if existing_result.failure_reason:
            if clear_lock:
                session.close()
            return existing_result
        existing = existing_result.factor_template_info
        failure_reason, log_id, existing = CustomerFactorTemplates.check_user_access(
            'update_factor_template', key=self.id, usr_context=usr_context, check_row=existing, update_mode=True
        )
        if existing is None or failure_reason != '':
            if clear_lock:
                session.close()
            return CustomerFactorTemplateResult_One(failure_reason=failure_reason, log_id=log_id)
        if update_fields is None:
            update_fields = self.model_dump(exclude_unset=True, exclude={'id', 'customer_id', 'create_date'})
        else:
            update_fields = {
                k: v for k, v in update_fields.items()
                if k not in ('id', 'customer_id', 'create_date', 'factor_template_id', 'modify_date', 'deleted_date')
            }
        if 'enable_global_share' in update_fields:
            new_share = bool(update_fields['enable_global_share'])
            if new_share != bool(existing.enable_global_share):
                if usr_context.sess_user.system_user_mode < 2:
                    if clear_lock:
                        session.close()
                    log_id = log_event(
                        "update_factor_template: enable_global_share change requires system admin",
                        usr_context=usr_context,
                        severity=3,
                    )
                    return CustomerFactorTemplateResult_One(
                        failure_reason="Not allowed; system user required to change global share",
                        log_id=log_id,
                    )
                log_event(
                    f"update_factor_template: global share set to {new_share} for template id={self.id}",
                    usr_context=usr_context,
                    severity=2,
                )
        if 'factor_template_entries' in update_fields:
            update_fields['factor_template_entries'] = _normalize_template_entries(update_fields['factor_template_entries'])
        if 'option_template_entries' in update_fields:
            update_fields['option_template_entries'] = _normalize_option_template_entries(update_fields['option_template_entries'])
        existing.sqlmodel_update(update_fields)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        if clear_lock:
            session.close()
        return CustomerFactorTemplateResult_One(factor_template_info=existing)

    def delete_factor_template(self, session: Session, usr_context: PvfUserContext) -> CustomerFactorTemplateDeleteResult:
        existing_result = CustomerFactorTemplates.get_factor_template_by_id(session, id=self.id, usr_context=usr_context, clear_lock=False)
        if existing_result.failure_reason or existing_result.factor_template_info is None:
            return CustomerFactorTemplateDeleteResult(success=False, failure_reason=existing_result.failure_reason or "not found", factor_template_id=self.id, log_id=existing_result.log_id)
        existing = existing_result.factor_template_info
        failure_reason, log_id, existing = CustomerFactorTemplates.check_user_access(
            'delete_factor_template', key=self.id, usr_context=usr_context, check_row=existing, update_mode=True
        )
        if existing is None or failure_reason != '':
            return CustomerFactorTemplateDeleteResult(failure_reason=failure_reason, log_id=log_id, factor_template_id=self.id)
        existing.deleted_date = datetime.now()
        session.add(existing)
        session.commit()
        return CustomerFactorTemplateDeleteResult(success=True, factor_template_id=existing.id)

    @staticmethod
    def get_factor_template_by_id(session: Session, *, id: int, usr_context: PvfUserContext, clear_lock: bool = True) -> CustomerFactorTemplateResult_One:
        row = session.exec(select(CustomerFactorTemplates).where(
            CustomerFactorTemplates.id == id,
            CustomerFactorTemplates.deleted_date == None,  # noqa: E711
        ).limit(1)).one_or_none()
        # Allow read of global templates from other tenants
        if row is not None and row.enable_global_share:
            failure_reason, log_id = '', 0
        else:
            failure_reason, log_id, row = CustomerFactorTemplates.check_user_access(
                'get_factor_template_by_id', key=id, usr_context=usr_context, check_row=row, update_mode=False
            )
        if clear_lock:
            session.close()
        return CustomerFactorTemplateResult_One(failure_reason=failure_reason, log_id=log_id, factor_template_info=row)

    @staticmethod
    def get_all_for_customer(session: Session, *, usr_context: PvfUserContext, clear_lock: bool = True) -> CustomerFactorTemplateResult_Many:
        rows = list(session.exec(select(CustomerFactorTemplates).where(
            CustomerFactorTemplates.customer_id == usr_context.sess_user.customer_id,
            CustomerFactorTemplates.deleted_date == None,  # noqa: E711
        )).all())
        if clear_lock:
            session.close()
        return CustomerFactorTemplateResult_Many(factor_template_info_list=rows)

    @staticmethod
    def get_available_templates(
        session: Session,
        *,
        usr_context: PvfUserContext,
        include_global: bool = True,
        for_use: str | None = None,
        clear_lock: bool = True,
    ) -> CustomerFactorTemplateResult_Many:
        customer_id = usr_context.sess_user.customer_id
        if include_global:
            rows = list(session.exec(select(CustomerFactorTemplates).where(
                CustomerFactorTemplates.deleted_date == None,  # noqa: E711
                CustomerFactorTemplates.disabled == False,  # noqa: E712
                or_(
                    CustomerFactorTemplates.customer_id == customer_id,
                    CustomerFactorTemplates.enable_global_share == True,  # noqa: E712
                ),
            )).all())
        else:
            rows = list(session.exec(select(CustomerFactorTemplates).where(
                CustomerFactorTemplates.customer_id == customer_id,
                CustomerFactorTemplates.deleted_date == None,  # noqa: E711
                CustomerFactorTemplates.disabled == False,  # noqa: E712
            )).all())
        if for_use == 'projects':
            rows = [r for r in rows if r.use_with_projects]
        elif for_use == 'options':
            rows = [r for r in rows if r.use_with_options]
        elif for_use == 'factors':
            rows = [r for r in rows if r.use_with_factors]
        if clear_lock:
            session.close()
        return CustomerFactorTemplateResult_Many(factor_template_info_list=rows)

    @staticmethod
    def check_user_access(action: str, *, key: Any, usr_context: PvfUserContext, check_row: CustomerFactorTemplates | None, update_mode: bool) -> tuple[str, int, CustomerFactorTemplates | None]:
        failure_reason = ''
        log_id = 0
        if check_row is None:
            log_id = log_event(log_message=f'{action} - Template {key}: NOT FOUND', severity=2, usr_context=usr_context)
            return 'Template not found', log_id, None
        if usr_context.sess_user.system_user_mode < 2 and check_row.customer_id != usr_context.sess_user.customer_id:
            log_id = log_event(log_message=f'{action} - Template {key}: customer mismatch', severity=3, usr_context=usr_context)
            return "Not allowed; system user mismatch", log_id, None
        if update_mode and usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
            log_id = log_event(log_message=f'{action} - Template {key}: non-admin', severity=3, usr_context=usr_context)
            return "Not allowed; non-admin", log_id, None
        return failure_reason, log_id, check_row


class CustomerProjectAlternatives(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True, unique=False)
    project_id: int = Field(index=True, unique=False, description="Project this option (alternative entry) belongs to")
    alternative_title: str | None = Field(default=None, description="Title of the option (API field name: alternative_title)")
    alternative_description: str | None = Field(default=None, description="Description of the option (API field name: alternative_description)")
    compare_prompt: str | None = Field(default=None, description="Concise LLM-rewritten label used for pairwise compares when set")
    disabled: bool = Field(default=False, description="When true, option is excluded from comparisons")

    @field_validator("compare_prompt", mode="before")
    @classmethod
    def _normalize_compare_prompt(cls, value: Any) -> str | None:
        return normalize_compare_prompt(value)
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))
    deleted_date: datetime | None = Field(default=None, description="Date entry was deleted; if not None, entry is considered deleted and not active")

    def create_alternative(self, session: Session, usr_context: PvfUserContext) -> CustomerProjectAlternativeResult_One:
        project = CustomerProject.get_customer_project_by_id_system(
            session=session, customer_id=usr_context.sess_user.customer_id if usr_context.sess_user.system_user_mode < 2 else self.customer_id or usr_context.sess_user.customer_id,
            id=self.project_id, clear_lock=False
        )
        if project is None and usr_context.sess_user.system_user_mode >= 2:
            project = session.exec(select(CustomerProject).where(
                CustomerProject.id == self.project_id,
                CustomerProject.deleted_date == None,  # noqa: E711
            ).limit(1)).one_or_none()
        if project is None:
            log_id = log_event(f"create_alternative: project {self.project_id} not found", usr_context=usr_context, severity=2)
            return CustomerProjectAlternativeResult_One(failure_reason="Project not found", log_id=log_id)
        if usr_context.sess_user.system_user_mode < 2 and project.customer_id != usr_context.sess_user.customer_id:
            log_id = log_event(f"create_alternative: project customer mismatch", usr_context=usr_context, severity=3)
            return CustomerProjectAlternativeResult_One(failure_reason="Not allowed; project customer mismatch", log_id=log_id)
        self.customer_id = project.customer_id
        if self.customer_id != usr_context.sess_user.customer_id and usr_context.sess_user.system_user_mode < 2:
            log_id = log_event(f"create_alternative: PvfCustomer ID mismatch", usr_context=usr_context, severity=4)
            return CustomerProjectAlternativeResult_One(failure_reason="Internal failure - PvfCustomer ID mismatch", log_id=log_id)
        session.add(self)
        session.commit()
        session.refresh(self)
        from ...utils.project_group_size import sync_project_group_sizes
        sync_project_group_sizes(
            session, project_id=self.project_id, customer_id=self.customer_id, kind="option"
        )
        return CustomerProjectAlternativeResult_One(alternative_info=self)

    def update_alternative(self, session: Session, usr_context: PvfUserContext, clear_lock: bool = True) -> CustomerProjectAlternativeResult_One:
        existing_result = CustomerProjectAlternatives.get_alternative_by_id(session, id=self.id, usr_context=usr_context, clear_lock=False)
        if existing_result.failure_reason:
            if clear_lock:
                session.close()
            return existing_result
        existing = existing_result.alternative_info
        failure_reason, log_id, existing = CustomerProjectAlternatives.check_user_access(
            'update_alternative', key=self.id, usr_context=usr_context, check_row=existing, update_mode=True
        )
        if existing is None or failure_reason != '':
            if clear_lock:
                session.close()
            return CustomerProjectAlternativeResult_One(failure_reason=failure_reason, log_id=log_id)
        update_fields = self.model_dump(exclude_unset=True, exclude={'id', 'customer_id', 'project_id', 'create_date'})
        existing.sqlmodel_update(update_fields)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        from ...utils.project_group_size import sync_project_group_sizes
        sync_project_group_sizes(
            session, project_id=existing.project_id, customer_id=existing.customer_id, kind="option"
        )
        if clear_lock:
            session.close()
        return CustomerProjectAlternativeResult_One(alternative_info=existing)

    def delete_alternative(self, session: Session, usr_context: PvfUserContext) -> CustomerProjectAlternativeDeleteResult:
        existing_result = CustomerProjectAlternatives.get_alternative_by_id(session, id=self.id, usr_context=usr_context, clear_lock=False)
        if existing_result.failure_reason or existing_result.alternative_info is None:
            return CustomerProjectAlternativeDeleteResult(success=False, failure_reason=existing_result.failure_reason or "not found", alternative_id=self.id, log_id=existing_result.log_id)
        existing = existing_result.alternative_info
        failure_reason, log_id, existing = CustomerProjectAlternatives.check_user_access(
            'delete_alternative', key=self.id, usr_context=usr_context, check_row=existing, update_mode=True
        )
        if existing is None or failure_reason != '':
            return CustomerProjectAlternativeDeleteResult(failure_reason=failure_reason, log_id=log_id, alternative_id=self.id)
        existing.deleted_date = datetime.now()
        session.add(existing)
        session.commit()
        from ...utils.project_group_size import sync_project_group_sizes
        sync_project_group_sizes(
            session, project_id=existing.project_id, customer_id=existing.customer_id, kind="option"
        )
        return CustomerProjectAlternativeDeleteResult(success=True, alternative_id=existing.id)

    @staticmethod
    def get_alternative_by_id(session: Session, *, id: int, usr_context: PvfUserContext, clear_lock: bool = True) -> CustomerProjectAlternativeResult_One:
        customer_id = usr_context.sess_user.customer_id
        if usr_context.sess_user.system_user_mode >= 2:
            row = session.exec(select(CustomerProjectAlternatives).where(
                CustomerProjectAlternatives.id == id,
                CustomerProjectAlternatives.deleted_date == None,  # noqa: E711
            ).limit(1)).one_or_none()
        else:
            row = session.exec(select(CustomerProjectAlternatives).where(
                CustomerProjectAlternatives.id == id,
                CustomerProjectAlternatives.customer_id == customer_id,
                CustomerProjectAlternatives.deleted_date == None,  # noqa: E711
            ).limit(1)).one_or_none()
        failure_reason, log_id, row = CustomerProjectAlternatives.check_user_access(
            'get_alternative_by_id', key=id, usr_context=usr_context, check_row=row, update_mode=False
        )
        if clear_lock:
            session.close()
        return CustomerProjectAlternativeResult_One(failure_reason=failure_reason, log_id=log_id, alternative_info=row)

    @staticmethod
    def get_all_by_project_id(session: Session, *, project_id: int, usr_context: PvfUserContext, clear_lock: bool = True) -> CustomerProjectAlternativeResult_Many:
        customer_id = usr_context.sess_user.customer_id
        project_result = CustomerProject.get_customer_project_by_id(session, id=project_id, usr_context=usr_context, clear_lock=False)
        if project_result.failure_reason or project_result.customer_project_info is None:
            if clear_lock:
                session.close()
            return CustomerProjectAlternativeResult_Many(failure_reason=project_result.failure_reason or "Project not found", log_id=project_result.log_id)
        rows = list(session.exec(select(CustomerProjectAlternatives).where(
            CustomerProjectAlternatives.project_id == project_id,
            CustomerProjectAlternatives.customer_id == project_result.customer_project_info.customer_id,
            CustomerProjectAlternatives.deleted_date == None,  # noqa: E711
        )).all())
        if clear_lock:
            session.close()
        return CustomerProjectAlternativeResult_Many(alternative_info_list=rows)

    @staticmethod
    def get_all_by_project_id_system(session: Session, *, project_id: int, customer_id: int, clear_lock: bool = True) -> list[CustomerProjectAlternatives]:
        rows = list(session.exec(select(CustomerProjectAlternatives).where(
            CustomerProjectAlternatives.project_id == project_id,
            CustomerProjectAlternatives.customer_id == customer_id,
            CustomerProjectAlternatives.deleted_date == None,  # noqa: E711
        )).all())
        if clear_lock:
            session.close()
        return rows

    @staticmethod
    def check_user_access(action: str, *, key: Any, usr_context: PvfUserContext, check_row: CustomerProjectAlternatives | None, update_mode: bool) -> tuple[str, int, CustomerProjectAlternatives | None]:
        failure_reason = ''
        log_id = 0
        if check_row is None:
            log_id = log_event(log_message=f'{action} - Alternative {key}: NOT FOUND', severity=2, usr_context=usr_context)
            return 'Alternative not found', log_id, None
        if usr_context.sess_user.system_user_mode < 2 and check_row.customer_id != usr_context.sess_user.customer_id:
            log_id = log_event(log_message=f'{action} - Alternative {key}: customer mismatch', severity=3, usr_context=usr_context)
            return "Not allowed; system user mismatch", log_id, None
        if update_mode and usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
            log_id = log_event(log_message=f'{action} - Alternative {key}: non-admin', severity=3, usr_context=usr_context)
            return "Not allowed; non-admin", log_id, None
        return failure_reason, log_id, check_row


class CustomerProjectFactors(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True, unique=False)
    project_id: int = Field(index=True, unique=False, description="The unique project ID associated with this factor")
    factor_title: str | None = Field(default=None, description="Title of the factor")
    factor_description: str | None = Field(default=None, description="Description of the factor")
    comparison_question: str | None = Field(
        default=None,
        description="Optional question wording used when comparing options on this factor",
    )
    compare_prompt: str | None = Field(default=None, description="Concise LLM-rewritten question used for pairwise compares when set")
    factor_polarity_positive: bool = Field(default=True, description="Indicates the polarity of the factor; True for positive, False for negative")
    factor_polarity_note: str | None = Field(default=None, description="Additional short string used in UI to distinguish the better outcome")

    @field_validator("comparison_question", mode="before")
    @classmethod
    def _normalize_comparison_question(cls, value: Any) -> str | None:
        return normalize_comparison_question(value)

    @field_validator("compare_prompt", mode="before")
    @classmethod
    def _normalize_compare_prompt(cls, value: Any) -> str | None:
        return normalize_compare_prompt(value)

    disabled: bool = Field(default=False, description="Indicates a disabled factor if true")
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))
    deleted_date: datetime | None = Field(default=None, description="Date entry was deleted; if not None, entry is considered deleted and not active")

    def create_factor(self, session: Session, usr_context: PvfUserContext) -> CustomerProjectFactorResult_One:
        project = CustomerProject.get_customer_project_by_id_system(
            session=session,
            customer_id=usr_context.sess_user.customer_id if usr_context.sess_user.system_user_mode < 2 else (self.customer_id or usr_context.sess_user.customer_id),
            id=self.project_id,
            clear_lock=False,
        )
        if project is None and usr_context.sess_user.system_user_mode >= 2:
            project = session.exec(select(CustomerProject).where(
                CustomerProject.id == self.project_id,
                CustomerProject.deleted_date == None,  # noqa: E711
            ).limit(1)).one_or_none()
        if project is None:
            log_id = log_event(f"create_factor: project {self.project_id} not found", usr_context=usr_context, severity=2)
            return CustomerProjectFactorResult_One(failure_reason="Project not found", log_id=log_id)
        if usr_context.sess_user.system_user_mode < 2 and project.customer_id != usr_context.sess_user.customer_id:
            log_id = log_event(f"create_factor: project customer mismatch", usr_context=usr_context, severity=3)
            return CustomerProjectFactorResult_One(failure_reason="Not allowed; project customer mismatch", log_id=log_id)
        self.customer_id = project.customer_id
        session.add(self)
        session.commit()
        session.refresh(self)
        from ...utils.project_group_size import sync_project_group_sizes
        sync_project_group_sizes(
            session, project_id=self.project_id, customer_id=self.customer_id, kind="factor"
        )
        return CustomerProjectFactorResult_One(factor_info=self)

    def update_factor(self, session: Session, usr_context: PvfUserContext, clear_lock: bool = True) -> CustomerProjectFactorResult_One:
        existing_result = CustomerProjectFactors.get_factor_by_id(session, id=self.id, usr_context=usr_context, clear_lock=False)
        if existing_result.failure_reason:
            if clear_lock:
                session.close()
            return existing_result
        existing = existing_result.factor_info
        failure_reason, log_id, existing = CustomerProjectFactors.check_user_access(
            'update_factor', key=self.id, usr_context=usr_context, check_row=existing, update_mode=True
        )
        if existing is None or failure_reason != '':
            if clear_lock:
                session.close()
            return CustomerProjectFactorResult_One(failure_reason=failure_reason, log_id=log_id)
        update_fields = self.model_dump(exclude_unset=True, exclude={'id', 'customer_id', 'project_id', 'create_date'})
        existing.sqlmodel_update(update_fields)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        from ...utils.project_group_size import sync_project_group_sizes
        sync_project_group_sizes(
            session, project_id=existing.project_id, customer_id=existing.customer_id, kind="factor"
        )
        if clear_lock:
            session.close()
        return CustomerProjectFactorResult_One(factor_info=existing)

    def delete_factor(self, session: Session, usr_context: PvfUserContext) -> CustomerProjectFactorDeleteResult:
        existing_result = CustomerProjectFactors.get_factor_by_id(session, id=self.id, usr_context=usr_context, clear_lock=False)
        if existing_result.failure_reason or existing_result.factor_info is None:
            return CustomerProjectFactorDeleteResult(success=False, failure_reason=existing_result.failure_reason or "not found", factor_id=self.id, log_id=existing_result.log_id)
        existing = existing_result.factor_info
        failure_reason, log_id, existing = CustomerProjectFactors.check_user_access(
            'delete_factor', key=self.id, usr_context=usr_context, check_row=existing, update_mode=True
        )
        if existing is None or failure_reason != '':
            return CustomerProjectFactorDeleteResult(failure_reason=failure_reason, log_id=log_id, factor_id=self.id)
        existing.deleted_date = datetime.now()
        session.add(existing)
        session.commit()
        from ...utils.project_group_size import sync_project_group_sizes
        sync_project_group_sizes(
            session, project_id=existing.project_id, customer_id=existing.customer_id, kind="factor"
        )
        return CustomerProjectFactorDeleteResult(success=True, factor_id=existing.id)

    @staticmethod
    def get_factor_by_id(session: Session, *, id: int, usr_context: PvfUserContext, clear_lock: bool = True) -> CustomerProjectFactorResult_One:
        customer_id = usr_context.sess_user.customer_id
        if usr_context.sess_user.system_user_mode >= 2:
            row = session.exec(select(CustomerProjectFactors).where(
                CustomerProjectFactors.id == id,
                CustomerProjectFactors.deleted_date == None,  # noqa: E711
            ).limit(1)).one_or_none()
        else:
            row = session.exec(select(CustomerProjectFactors).where(
                CustomerProjectFactors.id == id,
                CustomerProjectFactors.customer_id == customer_id,
                CustomerProjectFactors.deleted_date == None,  # noqa: E711
            ).limit(1)).one_or_none()
        failure_reason, log_id, row = CustomerProjectFactors.check_user_access(
            'get_factor_by_id', key=id, usr_context=usr_context, check_row=row, update_mode=False
        )
        if clear_lock:
            session.close()
        return CustomerProjectFactorResult_One(failure_reason=failure_reason, log_id=log_id, factor_info=row)

    @staticmethod
    def get_all_by_project_id(session: Session, *, project_id: int, usr_context: PvfUserContext, clear_lock: bool = True) -> CustomerProjectFactorResult_Many:
        project_result = CustomerProject.get_customer_project_by_id(session, id=project_id, usr_context=usr_context, clear_lock=False)
        if project_result.failure_reason or project_result.customer_project_info is None:
            if clear_lock:
                session.close()
            return CustomerProjectFactorResult_Many(failure_reason=project_result.failure_reason or "Project not found", log_id=project_result.log_id)
        rows = list(session.exec(select(CustomerProjectFactors).where(
            CustomerProjectFactors.project_id == project_id,
            CustomerProjectFactors.customer_id == project_result.customer_project_info.customer_id,
            CustomerProjectFactors.deleted_date == None,  # noqa: E711
        )).all())
        if clear_lock:
            session.close()
        return CustomerProjectFactorResult_Many(factor_info_list=rows)

    @staticmethod
    def get_all_by_project_id_system(session: Session, *, project_id: int, customer_id: int, clear_lock: bool = True) -> list[CustomerProjectFactors]:
        rows = list(session.exec(select(CustomerProjectFactors).where(
            CustomerProjectFactors.project_id == project_id,
            CustomerProjectFactors.customer_id == customer_id,
            CustomerProjectFactors.deleted_date == None,  # noqa: E711
        )).all())
        if clear_lock:
            session.close()
        return rows

    @staticmethod
    def check_user_access(action: str, *, key: Any, usr_context: PvfUserContext, check_row: CustomerProjectFactors | None, update_mode: bool) -> tuple[str, int, CustomerProjectFactors | None]:
        failure_reason = ''
        log_id = 0
        if check_row is None:
            log_id = log_event(log_message=f'{action} - Factor {key}: NOT FOUND', severity=2, usr_context=usr_context)
            return 'Factor not found', log_id, None
        if usr_context.sess_user.system_user_mode < 2 and check_row.customer_id != usr_context.sess_user.customer_id:
            log_id = log_event(log_message=f'{action} - Factor {key}: customer mismatch', severity=3, usr_context=usr_context)
            return "Not allowed; system user mismatch", log_id, None
        if update_mode and usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
            log_id = log_event(log_message=f'{action} - Factor {key}: non-admin', severity=3, usr_context=usr_context)
            return "Not allowed; non-admin", log_id, None
        return failure_reason, log_id, check_row
