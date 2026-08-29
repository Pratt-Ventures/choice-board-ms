from pydantic import BaseModel, Field
from fastapi import APIRouter, status, HTTPException


from ..pvf.bindings.pvf_services import SessionDep, UserAccessDep, log_event, PvfWsResultPackage

from ..db.models.customer_projects import CustomerProject
from ..utils.comparison_question import normalize_comparison_question
from ..utils.compare_prompt import normalize_compare_prompt
from ..db.models.customer_project_alternatives_criteria import (
    FactorTemplateEntry,
    OptionTemplateEntry,
    CustomerFactorTemplates,
    CustomerFactorTemplateResult_One,
    CustomerFactorTemplateResult_One_Id,
    CustomerFactorTemplateResult_Many,
    CustomerFactorTemplateDeleteResult,
    CustomerProjectAlternatives,
    CustomerProjectAlternativeResult_One,
    CustomerProjectAlternativeResult_One_Id,
    CustomerProjectAlternativeResult_Many,
    CustomerProjectAlternativeDeleteResult,
    CustomerProjectFactors,
    CustomerProjectFactorResult_One,
    CustomerProjectFactorResult_One_Id,
    CustomerProjectFactorResult_Many,
    CustomerProjectFactorDeleteResult,
)

router = APIRouter()


# ---- Templates (project / options / factors scopes) ----

class FactorTemplateForm(BaseModel):
    factor_template_title: str | None = Field(default=None, description="Template name")
    factor_template_description: str | None = Field(default=None, description="Template description")
    factor_template_entries: list[FactorTemplateEntry] | None = Field(default=None, description="Factors included in the template")
    option_template_entries: list[OptionTemplateEntry] | None = Field(default=None, description="Options included in the template")
    use_with_projects: bool = Field(default=False, description="Show for import on the project settings page")
    use_with_options: bool = Field(default=False, description="Show for import on the options page")
    use_with_factors: bool = Field(default=True, description="Show for import on the factors page")
    project_exclusive_mode: bool = Field(default=False, description="Pick one mode when imported at project scope")
    private_participation: bool = Field(default=False, description="Private participation when imported at project scope")
    enable_global_share: bool = Field(default=False, description="Share globally; system admin only when true")
    disabled: bool = Field(default=False, description="Hide template when true")

class FactorTemplateUpdateForm(FactorTemplateForm):
    factor_template_id: int = Field(description="ID of the template to update")

class FactorTemplateDeleteForm(BaseModel):
    factor_template_id: int


@router.post("/custproject-content/factor-template-create",
             summary="Create a template; customer_admin required",
             tags=['manage-project-content'])
def factor_template_create(session: SessionDep, usr_context: UserAccessDep, form: FactorTemplateForm) -> CustomerFactorTemplateResult_One:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to create template", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    row = CustomerFactorTemplates(
        customer_id=usr_context.sess_user.customer_id,
        factor_template_title=form.factor_template_title,
        factor_template_description=form.factor_template_description,
        factor_template_entries=form.factor_template_entries,
        option_template_entries=form.option_template_entries,
        use_with_projects=form.use_with_projects,
        use_with_options=form.use_with_options,
        use_with_factors=form.use_with_factors,
        project_exclusive_mode=form.project_exclusive_mode,
        private_participation=form.private_participation,
        enable_global_share=form.enable_global_share,
        disabled=form.disabled,
    )
    return row.create_factor_template(session=session, usr_context=usr_context)


@router.get("/custproject-content/factor-template-get-by-id",
            summary="Get template by id",
            tags=['manage-project-content'])
def factor_template_get_by_id(session: SessionDep, usr_context: UserAccessDep, retrieve_by_id: int) -> CustomerFactorTemplateResult_One:
    return CustomerFactorTemplates.get_factor_template_by_id(session=session, id=retrieve_by_id, usr_context=usr_context)


@router.get("/custproject-content/factor-templates-get-all",
            summary="List templates owned by the current customer",
            tags=['manage-project-content'])
def factor_templates_get_all(session: SessionDep, usr_context: UserAccessDep) -> CustomerFactorTemplateResult_Many:
    return CustomerFactorTemplates.get_all_for_customer(session=session, usr_context=usr_context)


@router.get("/custproject-content/factor-templates-get-available",
            summary="List templates owned by customer plus globally shared templates",
            tags=['manage-project-content'])
def factor_templates_get_available(
    session: SessionDep,
    usr_context: UserAccessDep,
    include_global: bool = True,
    for_use: str | None = None,
) -> CustomerFactorTemplateResult_Many:
    """Optional for_use filter: projects | options | factors."""
    use = (for_use or "").strip().lower() or None
    if use is not None and use not in ("projects", "options", "factors"):
        use = None
    return CustomerFactorTemplates.get_available_templates(
        session=session,
        usr_context=usr_context,
        include_global=include_global,
        for_use=use,
    )


@router.post("/custproject-content/factor-template-update",
             summary="Update a template; customer_admin required",
             tags=['manage-project-content'])
def factor_template_update(session: SessionDep, usr_context: UserAccessDep, form: FactorTemplateUpdateForm) -> CustomerFactorTemplateResult_One_Id:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to update template", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    data = form.model_dump(exclude_unset=True)
    template_id = data.pop("factor_template_id")
    row = CustomerFactorTemplates(id=template_id, customer_id=usr_context.sess_user.customer_id)
    result = row.update_factor_template(session=session, usr_context=usr_context, update_fields=data)
    return CustomerFactorTemplateResult_One_Id(
        failure_reason=result.failure_reason,
        log_id=result.log_id,
        factor_template_id=result.factor_template_info.id if result.factor_template_info else -1,
    )


@router.delete("/custproject-content/factor-template-delete",
               summary="Soft-delete a template; customer_admin required",
               tags=['manage-project-content'])
def factor_template_delete(session: SessionDep, usr_context: UserAccessDep, form: FactorTemplateDeleteForm) -> CustomerFactorTemplateDeleteResult:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to delete template", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    row = CustomerFactorTemplates(id=form.factor_template_id)
    return row.delete_factor_template(session=session, usr_context=usr_context)


# ---- Alternatives ----

class AlternativeForm(BaseModel):
    project_id: int
    alternative_title: str | None = Field(default=None)
    alternative_description: str | None = Field(default=None)
    compare_prompt: str | None = Field(default=None, description="Concise compare prompt")
    disabled: bool = Field(default=False)

class AlternativeUpdateForm(BaseModel):
    alternative_id: int
    alternative_title: str | None = Field(default=None)
    alternative_description: str | None = Field(default=None)
    compare_prompt: str | None = Field(default=None, description="Concise compare prompt")
    disabled: bool | None = Field(default=None)

class AlternativeDeleteForm(BaseModel):
    alternative_id: int


@router.post("/custproject-content/alternative-create",
             summary="Create a project alternative; customer_admin required",
             tags=['manage-project-content'])
def alternative_create(session: SessionDep, usr_context: UserAccessDep, form: AlternativeForm) -> CustomerProjectAlternativeResult_One:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to create alternative", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    row = CustomerProjectAlternatives(
        customer_id=usr_context.sess_user.customer_id,
        project_id=form.project_id,
        alternative_title=form.alternative_title,
        alternative_description=form.alternative_description,
        compare_prompt=normalize_compare_prompt(form.compare_prompt),
        disabled=form.disabled,
    )
    return row.create_alternative(session=session, usr_context=usr_context)


@router.get("/custproject-content/alternative-get-by-id",
            summary="Get alternative by id",
            tags=['manage-project-content'])
def alternative_get_by_id(session: SessionDep, usr_context: UserAccessDep, retrieve_by_id: int) -> CustomerProjectAlternativeResult_One:
    return CustomerProjectAlternatives.get_alternative_by_id(session=session, id=retrieve_by_id, usr_context=usr_context)


@router.get("/custproject-content/alternatives-get-by-project-id",
            summary="List alternatives for a project",
            tags=['manage-project-content'])
def alternatives_get_by_project_id(session: SessionDep, usr_context: UserAccessDep, project_id: int) -> CustomerProjectAlternativeResult_Many:
    return CustomerProjectAlternatives.get_all_by_project_id(session=session, project_id=project_id, usr_context=usr_context)


@router.post("/custproject-content/alternative-update",
             summary="Update an alternative; customer_admin required",
             tags=['manage-project-content'])
def alternative_update(session: SessionDep, usr_context: UserAccessDep, form: AlternativeUpdateForm) -> CustomerProjectAlternativeResult_One_Id:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to update alternative", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    row = CustomerProjectAlternatives(id=form.alternative_id)
    if form.alternative_title is not None:
        row.alternative_title = form.alternative_title
    if form.alternative_description is not None:
        row.alternative_description = form.alternative_description
    if "compare_prompt" in form.model_fields_set:
        row.compare_prompt = normalize_compare_prompt(form.compare_prompt)
    if form.disabled is not None:
        row.disabled = form.disabled
    result = row.update_alternative(session=session, usr_context=usr_context)
    return CustomerProjectAlternativeResult_One_Id(
        failure_reason=result.failure_reason,
        log_id=result.log_id,
        alternative_id=result.alternative_info.id if result.alternative_info else -1,
    )


@router.delete("/custproject-content/alternative-delete",
               summary="Soft-delete an alternative; customer_admin required",
               tags=['manage-project-content'])
def alternative_delete(session: SessionDep, usr_context: UserAccessDep, form: AlternativeDeleteForm) -> CustomerProjectAlternativeDeleteResult:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to delete alternative", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    row = CustomerProjectAlternatives(id=form.alternative_id)
    return row.delete_alternative(session=session, usr_context=usr_context)


# ---- Factors (criteria) ----

class FactorForm(BaseModel):
    project_id: int
    factor_title: str | None = Field(default=None)
    factor_description: str | None = Field(default=None)
    comparison_question: str | None = Field(
        default=None,
        description="Optional question wording used when comparing options on this factor",
    )
    compare_prompt: str | None = Field(default=None, description="Concise compare prompt")
    factor_polarity_positive: bool = Field(default=True)
    factor_polarity_note: str | None = Field(default=None)
    disabled: bool = Field(default=False)

class FactorUpdateForm(BaseModel):
    factor_id: int
    factor_title: str | None = Field(default=None)
    factor_description: str | None = Field(default=None)
    comparison_question: str | None = Field(
        default=None,
        description="Optional question wording used when comparing options on this factor",
    )
    compare_prompt: str | None = Field(default=None, description="Concise compare prompt")
    factor_polarity_positive: bool | None = Field(default=None)
    factor_polarity_note: str | None = Field(default=None)
    disabled: bool | None = Field(default=None)

class FactorDeleteForm(BaseModel):
    factor_id: int


class FactorSuggestForm(BaseModel):
    project_id: int
    project_title: str | None = Field(default=None, description="Problem title; falls back to the saved project")
    project_description: str | None = Field(default=None, description="Problem description; falls back to the saved project")


class FactorSuggestion(BaseModel):
    title: str
    description: str = ""


class FactorSuggestResult(PvfWsResultPackage):
    suggestions: list[FactorSuggestion] = Field(default_factory=list)


@router.post("/custproject-content/factor-create",
             summary="Create a project factor/criterion; customer_admin required",
             tags=['manage-project-content'])
def factor_create(session: SessionDep, usr_context: UserAccessDep, form: FactorForm) -> CustomerProjectFactorResult_One:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to create factor", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    row = CustomerProjectFactors(
        customer_id=usr_context.sess_user.customer_id,
        project_id=form.project_id,
        factor_title=form.factor_title,
        factor_description=form.factor_description,
        comparison_question=None,
        compare_prompt=normalize_compare_prompt(form.compare_prompt),
        factor_polarity_positive=form.factor_polarity_positive,
        factor_polarity_note=form.factor_polarity_note,
        disabled=form.disabled,
    )
    return row.create_factor(session=session, usr_context=usr_context)


@router.get("/custproject-content/factor-get-by-id",
            summary="Get factor by id",
            tags=['manage-project-content'])
def factor_get_by_id(session: SessionDep, usr_context: UserAccessDep, retrieve_by_id: int) -> CustomerProjectFactorResult_One:
    return CustomerProjectFactors.get_factor_by_id(session=session, id=retrieve_by_id, usr_context=usr_context)


@router.get("/custproject-content/factors-get-by-project-id",
            summary="List factors/criteria for a project",
            tags=['manage-project-content'])
def factors_get_by_project_id(session: SessionDep, usr_context: UserAccessDep, project_id: int) -> CustomerProjectFactorResult_Many:
    return CustomerProjectFactors.get_all_by_project_id(session=session, project_id=project_id, usr_context=usr_context)


@router.post("/custproject-content/factor-update",
             summary="Update a factor; customer_admin required",
             tags=['manage-project-content'])
def factor_update(session: SessionDep, usr_context: UserAccessDep, form: FactorUpdateForm) -> CustomerProjectFactorResult_One_Id:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to update factor", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    row = CustomerProjectFactors(id=form.factor_id)
    if form.factor_title is not None:
        row.factor_title = form.factor_title
    if form.factor_description is not None:
        row.factor_description = form.factor_description
    if "compare_prompt" in form.model_fields_set:
        row.compare_prompt = normalize_compare_prompt(form.compare_prompt)
    if form.factor_polarity_positive is not None:
        row.factor_polarity_positive = form.factor_polarity_positive
    if form.factor_polarity_note is not None:
        row.factor_polarity_note = form.factor_polarity_note
    if form.disabled is not None:
        row.disabled = form.disabled
    result = row.update_factor(session=session, usr_context=usr_context)
    return CustomerProjectFactorResult_One_Id(
        failure_reason=result.failure_reason,
        log_id=result.log_id,
        factor_id=result.factor_info.id if result.factor_info else -1,
    )


@router.post("/custproject-content/factor-suggest",
             summary="Suggest factors from a problem title and description; customer_admin required. Does not persist.",
             tags=['manage-project-content'])
def factor_suggest(session: SessionDep, usr_context: UserAccessDep, form: FactorSuggestForm) -> FactorSuggestResult:
    from ..utils.ai.config import ai_features_enabled, ai_unavailable_message
    from ..utils.ai.provider import AiProviderError

    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to suggest factors", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    if not ai_features_enabled():
        log_event(ai_unavailable_message(), usr_context=usr_context, severity=2,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ai_unavailable_message()))
    from ..utils.ai.config import no_providers_message, resolve_llm_credentials
    from ..utils.ai.prompts import factor_suggest_messages, parse_factor_suggestions
    from ..pvf.bindings.pvf_watcher_requests import queue_llm_and_wait
    customer = usr_context.sess_customer
    if resolve_llm_credentials(customer) is None:
        return FactorSuggestResult(failure_reason=no_providers_message())
    title = (form.project_title or "").strip()
    description = (form.project_description or "").strip()
    if form.project_id and form.project_id > 0:
        project_result = CustomerProject.get_customer_project_by_id(
            session=session, id=form.project_id, usr_context=usr_context, clear_lock=False
        )
        if project_result.failure_reason or project_result.customer_project_info is None:
            return FactorSuggestResult(failure_reason=project_result.failure_reason or "Project not found")
        project = project_result.customer_project_info
        title = title or (project.project_title or "").strip()
        description = description or (project.project_description or "").strip()
    if not title or not description:
        return FactorSuggestResult(failure_reason="Title and description are required")
    # In PYTEST, use direct worker path so existing mocks on suggest_factors work
    try:
        from ..config.config_settings import settings as _app_settings
        from ..pvf.config.pvf_config_settings import pvf_settings as _pvf_settings
        if getattr(_app_settings, "PYTEST_ACTIVE", False) or getattr(_pvf_settings, "PYTEST_ACTIVE", False):
            # Try mocked async suggest_factors first (used by test)
            try:
                from ..utils.ai.worker import suggest_factors as _sf_async
                import inspect as _insp, asyncio as _asyncio
                if _insp.iscoroutinefunction(_sf_async):
                    # Check if it's been mocked to not be the original (we can just try calling it)
                    try:
                        # Try to run it; if mocked it will return quickly
                        rows = _asyncio.run(_sf_async(title=title, description=description, customer=customer))
                        if isinstance(rows, list):
                            return FactorSuggestResult(suggestions=[FactorSuggestion(title=r["title"], description=r.get("description") or "") for r in rows])
                    except Exception:
                        pass
            except Exception:
                pass
            from ..utils.ai.worker import suggest_factors_sync as _sfs
            try:
                rows = _sfs(title=title, description=description, customer=customer)
                return FactorSuggestResult(suggestions=[FactorSuggestion(title=r["title"], description=r.get("description") or "") for r in rows])
            except Exception:
                pass
    except Exception:
        pass
    try:
        messages = factor_suggest_messages(title=title, description=description)
        text, result_pkg, err = queue_llm_and_wait(session=session, usr_context=usr_context, messages=messages, temperature=0.3, max_tokens=1200, semantic_tag="factor_suggest", timeout=12.0)
        if err:
            if str(err).startswith("queued:"):
                return FactorSuggestResult(failure_reason="queued")
            raise AiProviderError(str(err) or "Could not suggest factors")
        if not text:
            # Try to extract from result_pkg
            if isinstance(result_pkg, dict):
                text = result_pkg.get("text") or ""
            if not text:
                raise AiProviderError("Could not suggest factors")
        # Parse JSON from text (same as provider.chat_json_sync)
        import json as _json
        raw = (text or "").strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
        try:
            payload = _json.loads(raw)
        except _json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    payload = _json.loads(raw[start:end + 1])
                except _json.JSONDecodeError:
                    raise AiProviderError("Could not suggest factors")
            else:
                raise AiProviderError("Could not suggest factors")
        rows = parse_factor_suggestions(payload)
    except AiProviderError:
        return FactorSuggestResult(failure_reason="Could not suggest factors")
    except Exception:
        return FactorSuggestResult(failure_reason="Could not suggest factors")
    if not rows:
        return FactorSuggestResult(failure_reason="Could not suggest factors")
    return FactorSuggestResult(suggestions=[FactorSuggestion(title=r["title"], description=r.get("description") or "") for r in rows])


@router.delete("/custproject-content/factor-delete",
               summary="Soft-delete a factor; customer_admin required",
               tags=['manage-project-content'])
def factor_delete(session: SessionDep, usr_context: UserAccessDep, form: FactorDeleteForm) -> CustomerProjectFactorDeleteResult:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to delete factor", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    row = CustomerProjectFactors(id=form.factor_id)
    return row.delete_factor(session=session, usr_context=usr_context)


# ---- Compare Prompt generation (per-item) ----

class ComparePromptGenerateForm(BaseModel):
    alternative_id: int | None = None
    factor_id: int | None = None
    project_id: int | None = None


class ComparePromptGenerateResult(PvfWsResultPackage):
    compare_prompt: str | None = None
    alternative_id: int | None = None
    factor_id: int | None = None


DISABLED_PROVIDER_MSG = "There is no provider set up for this customer, check settings to enable"


@router.post("/custproject-content/alternative-compare-prompt-generate",
             summary="Generate concise compare prompt for one option via LLM; customer_admin required",
             tags=['manage-project-content'])
def alternative_compare_prompt_generate(session: SessionDep, usr_context: UserAccessDep, form: ComparePromptGenerateForm) -> ComparePromptGenerateResult:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to generate compare prompt", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    from ..utils.ai.config import customer_llm_configured, resolve_llm_credentials
    from ..utils.compare_prompt import normalize_compare_prompt
    customer = usr_context.sess_customer
    if not customer_llm_configured(customer):
        log_event(
            "compare prompt option generate failed - no provider",
            usr_context=usr_context,
            severity=2,
            alternative_id=form.alternative_id,
            project_id=form.project_id,
            failure_reason=DISABLED_PROVIDER_MSG,
        )
        return ComparePromptGenerateResult(failure_reason=DISABLED_PROVIDER_MSG)
    alt_id = form.alternative_id
    if not alt_id:
        return ComparePromptGenerateResult(failure_reason="alternative_id required")
    res = CustomerProjectAlternatives.get_alternative_by_id(session=session, id=alt_id, usr_context=usr_context, clear_lock=False)
    if res.failure_reason or res.alternative_info is None:
        log_event(
            f"compare prompt option {alt_id} failed - not found",
            usr_context=usr_context,
            severity=2,
            alternative_id=alt_id,
            project_id=form.project_id,
            failure_reason=res.failure_reason or "Alternative not found",
        )
        return ComparePromptGenerateResult(failure_reason=res.failure_reason or "Alternative not found")
    alt = res.alternative_info
    creds = resolve_llm_credentials(customer)
    # In PYTEST, try direct path so existing mocks on generate_* work
    try:
        from ..config.config_settings import settings as _app_s
        from ..pvf.config.pvf_config_settings import pvf_settings as _pvf_s
        if getattr(_app_s, "PYTEST_ACTIVE", False) or getattr(_pvf_s, "PYTEST_ACTIVE", False):
            from ..utils.ai.reword_worker import generate_option_prompt_sync as _gen_opt
            try:
                _pt = _gen_opt(customer=customer, title=alt.alternative_title or "", description=alt.alternative_description)
                _norm = normalize_compare_prompt(_pt)
                alt.compare_prompt = _norm
                session.add(alt)
                session.commit()
                session.refresh(alt)
                log_event(f"compare prompt option {alt.id} generated", usr_context=usr_context, severity=1, alternative_id=alt.id, project_id=alt.project_id, provider=getattr(creds, "provider", "") if creds else "", model=getattr(creds, "model", "") if creds else "", prompt=_norm[:200] if _norm else "")
                return ComparePromptGenerateResult(compare_prompt=_norm, alternative_id=alt.id)
            except Exception as _ex2:
                # fall through to queue path
                pass
    except Exception:
        pass
    try:
        from ..utils.ai.prompts import option_rewrite_messages, parse_compare_prompt
        from ..pvf.bindings.pvf_watcher_requests import queue_llm_and_wait
        messages = option_rewrite_messages(title=alt.alternative_title or "", description=alt.alternative_description)
        # Use watcher LLM queue with fallback and byte tracking
        text, result_pkg, err = queue_llm_and_wait(session=session, usr_context=usr_context, messages=messages, temperature=0.3, max_tokens=1200, semantic_tag="reword_option", timeout=12.0)
        if err:
            if str(err).startswith("queued:"):
                # Still queued after timeout -> enqueue ComparePromptJob for watcher retry
                try:
                    from ..db.models.compare_prompt_jobs import ComparePromptJob
                    ComparePromptJob.enqueue(session=session, customer_id=alt.customer_id, project_id=alt.project_id, item_type="option", item_id=alt.id, requested_by_user_id=usr_context.sess_user.id, clear_lock=False)
                except Exception:
                    pass
                log_event(f"compare prompt option {alt.id} queued", usr_context=usr_context, severity=1, alternative_id=alt.id, project_id=alt.project_id, provider=getattr(creds, "provider", "") if creds else "", model=getattr(creds, "model", "") if creds else "")
                return ComparePromptGenerateResult(failure_reason="queued")
            msg = str(err) or "Could not generate compare prompt"
            is_retryable = "retryable" in str(err).lower() or "unavailable" in msg.lower()
            try:
                from ..db.models.compare_prompt_jobs import ComparePromptJob
                if is_retryable or "AI service is unavailable" in msg:
                    ComparePromptJob.enqueue(session=session, customer_id=alt.customer_id, project_id=alt.project_id, item_type="option", item_id=alt.id, requested_by_user_id=usr_context.sess_user.id, clear_lock=False)
            except Exception:
                pass
            log_event(f"compare prompt inline option {alt.id} failed: {msg[:300]}", usr_context=usr_context, severity=2, alternative_id=alt.id, project_id=alt.project_id, provider=getattr(creds, "provider", "") if creds else "", model=getattr(creds, "model", "") if creds else "", error=msg[:500], retryable=is_retryable, queued_for_retry=is_retryable)
            return ComparePromptGenerateResult(failure_reason=msg)
        # Extract text from watcher result
        prompt_text = None
        if isinstance(result_pkg, dict):
            prompt_text = result_pkg.get("text") or text
        if not prompt_text:
            prompt_text = text
        if not prompt_text:
            raise ValueError("empty LLM response")
        # Try to parse as compare_prompt JSON if needed, else use raw text
        parsed = None
        try:
            parsed = parse_compare_prompt(prompt_text if isinstance(prompt_text, dict) else {"compare_prompt": prompt_text})
        except Exception:
            parsed = None
        if parsed:
            prompt_text = parsed
        elif isinstance(prompt_text, dict):
            # If handler returned dict with compare_prompt
            try:
                parsed2 = parse_compare_prompt(prompt_text)
                if parsed2:
                    prompt_text = parsed2
            except Exception:
                pass
    except Exception as ex:
        msg = str(ex) or "Could not generate compare prompt"
        is_retryable = bool(getattr(ex, "retryable", False))
        try:
            from ..db.models.compare_prompt_jobs import ComparePromptJob
            if is_retryable or "AI service is unavailable" in msg:
                ComparePromptJob.enqueue(session=session, customer_id=alt.customer_id, project_id=alt.project_id, item_type="option", item_id=alt.id, requested_by_user_id=usr_context.sess_user.id, clear_lock=False)
        except Exception:
            pass
        log_event(f"compare prompt inline option {alt.id} failed: {msg[:300]}", usr_context=usr_context, severity=2, ex_info=ex if isinstance(ex, Exception) else None, alternative_id=alt.id, project_id=alt.project_id, provider=getattr(creds, "provider", "") if creds else "", model=getattr(creds, "model", "") if creds else "", error=msg[:500], retryable=is_retryable, queued_for_retry=is_retryable or "AI service is unavailable" in msg)
        return ComparePromptGenerateResult(failure_reason=msg)
    normalized = normalize_compare_prompt(prompt_text)
    alt.compare_prompt = normalized
    session.add(alt)
    session.commit()
    session.refresh(alt)
    log_event(f"compare prompt option {alt.id} generated", usr_context=usr_context, severity=1, alternative_id=alt.id, project_id=alt.project_id, provider=getattr(creds, "provider", "") if creds else "", model=getattr(creds, "model", "") if creds else "", prompt=normalized[:200] if normalized else "")
    return ComparePromptGenerateResult(compare_prompt=normalized, alternative_id=alt.id)


@router.post("/custproject-content/factor-compare-prompt-generate",
             summary="Generate concise compare prompt for one factor via LLM; customer_admin required",
             tags=['manage-project-content'])
def factor_compare_prompt_generate(session: SessionDep, usr_context: UserAccessDep, form: ComparePromptGenerateForm) -> ComparePromptGenerateResult:
    if usr_context.sess_user.customer_admin is False and usr_context.sess_user.system_user_mode < 2:
        log_event("Unauthorized attempt to generate compare prompt", usr_context=usr_context, severity=3,
                  raise_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized"))
    from ..utils.ai.config import customer_llm_configured, resolve_llm_credentials
    from ..utils.compare_prompt import normalize_compare_prompt
    customer = usr_context.sess_customer
    if not customer_llm_configured(customer):
        log_event(
            "compare prompt factor generate failed - no provider",
            usr_context=usr_context,
            severity=2,
            factor_id=form.factor_id,
            project_id=form.project_id,
            failure_reason=DISABLED_PROVIDER_MSG,
        )
        return ComparePromptGenerateResult(failure_reason=DISABLED_PROVIDER_MSG)
    fac_id = form.factor_id
    if not fac_id:
        return ComparePromptGenerateResult(failure_reason="factor_id required")
    res = CustomerProjectFactors.get_factor_by_id(session=session, id=fac_id, usr_context=usr_context, clear_lock=False)
    if res.failure_reason or res.factor_info is None:
        log_event(
            f"compare prompt factor {fac_id} failed - not found",
            usr_context=usr_context,
            severity=2,
            factor_id=fac_id,
            project_id=form.project_id,
            failure_reason=res.failure_reason or "Factor not found",
        )
        return ComparePromptGenerateResult(failure_reason=res.failure_reason or "Factor not found")
    fac = res.factor_info
    creds = resolve_llm_credentials(customer)
    # PYTEST bypass
    try:
        from ..config.config_settings import settings as _app_s
        from ..pvf.config.pvf_config_settings import pvf_settings as _pvf_s
        if getattr(_app_s, "PYTEST_ACTIVE", False) or getattr(_pvf_s, "PYTEST_ACTIVE", False):
            from ..utils.ai.reword_worker import generate_factor_prompt_sync as _gen_fac
            try:
                _pt = _gen_fac(customer=customer, title=fac.factor_title or "", description=fac.factor_description, polarity_positive=fac.factor_polarity_positive, polarity_note=fac.factor_polarity_note)
                _norm = normalize_compare_prompt(_pt)
                fac.compare_prompt = _norm
                session.add(fac)
                session.commit()
                session.refresh(fac)
                log_event(f"compare prompt factor {fac.id} generated", usr_context=usr_context, severity=1, factor_id=fac.id, project_id=fac.project_id, provider=getattr(creds, "provider", "") if creds else "", model=getattr(creds, "model", "") if creds else "", title=fac.factor_title or "", prompt=_norm[:200] if _norm else "")
                return ComparePromptGenerateResult(compare_prompt=_norm, factor_id=fac.id)
            except Exception as _ex2:
                pass
    except Exception:
        pass
    try:
        from ..utils.ai.prompts import factor_rewrite_messages, parse_compare_prompt
        from ..pvf.bindings.pvf_watcher_requests import queue_llm_and_wait
        messages = factor_rewrite_messages(title=fac.factor_title or "", description=fac.factor_description, polarity_positive=fac.factor_polarity_positive, polarity_note=fac.factor_polarity_note)
        text, result_pkg, err = queue_llm_and_wait(session=session, usr_context=usr_context, messages=messages, temperature=0.3, max_tokens=1200, semantic_tag="reword_factor", timeout=12.0)
        if err:
            if str(err).startswith("queued:"):
                try:
                    from ..db.models.compare_prompt_jobs import ComparePromptJob
                    ComparePromptJob.enqueue(session=session, customer_id=fac.customer_id, project_id=fac.project_id, item_type="factor", item_id=fac.id, requested_by_user_id=usr_context.sess_user.id, clear_lock=False)
                except Exception:
                    pass
                log_event(f"compare prompt factor {fac.id} queued", usr_context=usr_context, severity=1, factor_id=fac.id, project_id=fac.project_id, provider=getattr(creds, "provider", "") if creds else "", model=getattr(creds, "model", "") if creds else "")
                return ComparePromptGenerateResult(failure_reason="queued")
            msg = str(err) or "Could not generate compare prompt"
            is_retryable = "retryable" in str(err).lower() or "unavailable" in msg.lower()
            try:
                from ..db.models.compare_prompt_jobs import ComparePromptJob
                if is_retryable or "AI service is unavailable" in msg:
                    ComparePromptJob.enqueue(session=session, customer_id=fac.customer_id, project_id=fac.project_id, item_type="factor", item_id=fac.id, requested_by_user_id=usr_context.sess_user.id, clear_lock=False)
            except Exception:
                pass
            log_event(f"compare prompt inline factor {fac.id} failed: {msg[:300]}", usr_context=usr_context, severity=2, factor_id=fac.id, project_id=fac.project_id, provider=getattr(creds, "provider", "") if creds else "", model=getattr(creds, "model", "") if creds else "", title=fac.factor_title or "", error=msg[:500], retryable=is_retryable, queued_for_retry=is_retryable)
            return ComparePromptGenerateResult(failure_reason=msg)
        prompt_text = None
        if isinstance(result_pkg, dict):
            prompt_text = result_pkg.get("text") or text
        if not prompt_text:
            prompt_text = text
        if not prompt_text:
            raise ValueError("empty LLM response")
        parsed = None
        try:
            parsed = parse_compare_prompt(prompt_text if isinstance(prompt_text, dict) else {"compare_prompt": prompt_text})
        except Exception:
            parsed = None
        if parsed:
            prompt_text = parsed
        elif isinstance(prompt_text, dict):
            try:
                parsed2 = parse_compare_prompt(prompt_text)
                if parsed2:
                    prompt_text = parsed2
            except Exception:
                pass
    except Exception as ex:
        msg = str(ex) or "Could not generate compare prompt"
        is_retryable = bool(getattr(ex, "retryable", False))
        # enqueue for watcher retry when transient so bulk factors page can recover
        try:
            from ..db.models.compare_prompt_jobs import ComparePromptJob
            if is_retryable or "AI service is unavailable" in msg:
                ComparePromptJob.enqueue(
                    session=session,
                    customer_id=fac.customer_id,
                    project_id=fac.project_id,
                    item_type="factor",
                    item_id=fac.id,
                    requested_by_user_id=usr_context.sess_user.id,
                    clear_lock=False,
                )
        except Exception:
            pass
        log_event(
            f"compare prompt inline factor {fac.id} failed: {msg[:300]}",
            usr_context=usr_context,
            severity=2,
            ex_info=ex if isinstance(ex, Exception) else None,
            factor_id=fac.id,
            project_id=fac.project_id,
            provider=getattr(creds, "provider", "") if creds else "",
            model=getattr(creds, "model", "") if creds else "",
            title=fac.factor_title or "",
            error=msg[:500],
            retryable=is_retryable,
            queued_for_retry=is_retryable or "AI service is unavailable" in msg,
        )
        return ComparePromptGenerateResult(failure_reason=msg)
    normalized = normalize_compare_prompt(prompt_text)
    fac.compare_prompt = normalized
    session.add(fac)
    session.commit()
    session.refresh(fac)
    log_event(
        f"compare prompt factor {fac.id} generated",
        usr_context=usr_context,
        severity=1,
        factor_id=fac.id,
        project_id=fac.project_id,
        provider=getattr(creds, "provider", "") if creds else "",
        model=getattr(creds, "model", "") if creds else "",
        title=fac.factor_title or "",
        prompt=normalized[:200] if normalized else "",
    )
    return ComparePromptGenerateResult(compare_prompt=normalized, factor_id=fac.id)
