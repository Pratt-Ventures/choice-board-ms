from __future__ import annotations
from typing import TYPE_CHECKING, Union, Any
from datetime import datetime
import uuid 

from sqlmodel import SQLModel, Field, Session, select
from sqlalchemy import func, DateTime, Column
from sqlalchemy.dialects.postgresql import JSONB

from ...pvf.bindings.pvf_services import PvfWsResultPackage, PvfUserContext, PvfCustomer, log_event

from ...config.config_settings import settings

class CustomerProjectResult_One_Id(PvfWsResultPackage):
    customer_project_id: Union[int, None] = None

class CustomerProjectResult_One(PvfWsResultPackage):
    customer_project_info: Union[CustomerProject, None] = None
    private_participation_locked: bool = Field(
        default=False,
        description="True when private participation is on and non-creator comparisons exist; only system admin may turn it off",
    )

class CustomerProjectResult_Many(PvfWsResultPackage):
    customer_project_info_list: Union[list[CustomerProject], None] = None

class CustomerProjectDeleteResult(PvfWsResultPackage):
    success: bool = Field(default=False, description="Bool indicates if soft delete was successful")
    customer_project_id: int | None = Field(default=None, description="The internal ID of the customer project that was deleted")
    customer_project_tag: str | None = Field(default=None, description="The project tag of the customer project that was deleted")

class CustomerProject(SQLModel, table=True):
    id: int = Field(primary_key=True)
    customer_id: int = Field(index=True, unique=False)
    magic_token: str | None = Field(default=None, index=True, unique=True, description="Assigned token key on project creation to identify this project in external URLs or resources.")

    project_tag: str = Field(index=True, unique=False, description="A unique project tag within the customer that is associated with a unique product/service")
    project_title: str | None = Field(default=None, description="A unique project title within the customer that is associated with a unique product/service")
    project_description: str | None = Field(default=None, index=False, unique=False, description="The description of this specific project associated with the customer")
    project_exclusive_mode: bool = Field(default=False, description="Pick one mode (true): select a single winner. Rank all mode (false): full option ranking.")
    ranking_mode: str = Field(
        default="rank_all",
        description="Compare target: find_best, find_top_3, find_top_half, or rank_all",
    )
    private_participation: bool = Field(default=False, description="When true, individual participant names are hidden in reports and views; labels use unique participant N per view")
    participant_influence_mode: str = Field(
        default="comparisons",
        description=(
            "How group Results balance influence: comparisons (each comparison equal), "
            "balanced (moderate participant normalization), participants_normalized "
            "(strong participant normalization, not fully equal)"
        ),
    )
    participant_influence_min_comparisons: int = Field(
        default=10,
        description="Soft floor on calculable comparisons before participant influence is amplified (minimum 3)",
    )
    factor_weight_floor_alpha: float = Field(
        default=0.5,
        description=(
            "Scales the factor-weight floor as alpha×(n−1) before normalizing importance weights. "
            "Lower = more spread between factors; higher = more equal. Default 0.5 matches classic 75/25 for two clear ranks."
        ),
    )
    min_expected_passes: int = Field(
        default=2,
        description="Target minimum sort passes per participant (1–5); used for progress and encouragement",
    )
    max_recommended_passes: int = Field(
        default=2,
        description="Recommended maximum sort passes per participant (≥ min expected, ≤ 10); hard limit is max + 1",
    )
    include_ai_agents: bool = Field(
        default=False,
        description="When true, saved AI agents can be queued; when false, the selection is kept but ignored at queue time",
    )
    ai_voter_models: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, default=list),
        description="Unique LLM model keys that vote as AI agents; __default__ uses the resolved default model",
    )
    option_questions_per_group: int = Field(
        default=20,
        description=(
            "Pairwise comparisons per option group. Follows the Ford–Johnson default "
            "for the current option count unless option_questions_per_group_explicit is true"
        ),
    )
    factor_questions_per_group: int = Field(
        default=20,
        description=(
            "Pairwise comparisons per factor-importance group. Follows the Ford–Johnson "
            "default for the current factor count unless factor_questions_per_group_explicit is true"
        ),
    )
    option_questions_per_group_explicit: bool = Field(
        default=False,
        description="True when option comparisons per group were set by the user instead of the Ford–Johnson default",
    )
    factor_questions_per_group_explicit: bool = Field(
        default=False,
        description="True when factor comparisons per group were set by the user instead of the Ford–Johnson default",
    )
    project_created_by: int = Field(index=True, unique=False, description="The ID of the user who created the project")
    project_criteria_template: int = Field(default=0, description="ID of the last factor template applied, if any; later edits may diverge from the template")
    disabled: bool = Field(default=False, description="When true, input is closed and new comparisons are not accepted")
    end_time: datetime | None = Field(
        default=None,
        description="Optional close datetime for comparison collection; None means no deadline",
    )
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    # from https://github.com/fastapi/sqlmodel/discussions/990 regarding onupdate support simulation in sqlmodel
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))
    deleted_date: datetime | None = Field(default=None, description="Date project entry was deleted; if not None, entry is considered deleted and not active")

    def create_customer_project(self, session: Session, usr_context: PvfUserContext) -> CustomerProjectResult_One:
        if self.customer_id != usr_context.sess_user.customer_id:
            log_id = log_event(f"create_customer_project: PvfCustomer ID mismatch: {self.customer_id} != {usr_context.sess_user.customer_id}", usr_context=usr_context, severity=4)
            return CustomerProjectResult_One(failure_reason=f"Internal failure - PvfCustomer ID mismatch: {self.customer_id} != {usr_context.sess_user.customer_id}", log_id=log_id)
        self.magic_token = uuid.uuid4().hex[:12].upper()
        self.project_tag = self.project_tag.strip() if self.project_tag else ''
        self.project_title = self.project_title.strip() if self.project_title else ''
        self.project_description = self.project_description.strip() if self.project_description else ''
        session.add(self)
        session.commit()
        session.refresh(self)
        return CustomerProjectResult_One(customer_project_info=self)

    def create_customer_project_system(self, session: Session, usr_context: PvfUserContext) -> CustomerProjectResult_One:
        if self.customer_id != usr_context.sess_user.customer_id and usr_context.sess_user.system_user_mode < 2:
            log_id = log_event(f"create_customer_project_system: PvfCustomer ID mismatch or non sys-admin: {self.customer_id} != {usr_context.sess_user.customer_id}", usr_context=usr_context, severity=4)
            return CustomerProjectResult_One(failure_reason=f"Internal failure - PvfCustomer ID mismatch: {self.customer_id} != {usr_context.sess_user.customer_id}", log_id=log_id)
        elif self.customer_id != usr_context.sess_user.customer_id :
            customer_info = PvfCustomer.get_customer_by_id(session, id=self.customer_id, usr_context=usr_context)
            if customer_info is None:
                log_id = log_event(f"create_customer_project_system: Specified customer not found: {self.customer_id}", usr_context=usr_context, severity=4)
                return CustomerProjectResult_One(failure_reason=f"Internal failure - Specified customer not found: {self.customer_id}", log_id=log_id)
        session.add(self)
        session.commit()
        session.refresh(self)
        return CustomerProjectResult_One(customer_project_info=self)

    def update_customer_project(self, session: Session, usr_context: PvfUserContext, clear_lock: bool=True) -> CustomerProjectResult_One:
        if self.id not in (None, 0, -1):
            customer_project_info_result = CustomerProject.get_customer_project_by_id(session, id=self.id, usr_context=usr_context)
            access_key = self.id
        else:
            customer_project_info_result = CustomerProject.get_customer_project_by_tag(session, tag=self.project_tag, usr_context=usr_context)
            access_key = self.project_tag
        if customer_project_info_result.failure_reason:
            return customer_project_info_result
        customer_project_info = customer_project_info_result.customer_project_info
        failure_reason, log_id, customer_project_info  = CustomerProject.check_user_access_to_customer_project('update_customer_project', key=access_key, usr_context=usr_context, check_customer_project=customer_project_info, update_mode=True)
        if customer_project_info is None or failure_reason != '':
            return CustomerProjectResult_One(failure_reason=failure_reason, log_id=log_id)
        self.id = customer_project_info.id
        if self.project_tag in (None, ''):
            self.project_tag = customer_project_info.project_tag
        update_fields = self.model_dump(exclude_unset=True)
        customer_project_info.sqlmodel_update(update_fields)
        session.add(customer_project_info)
        return_user = CustomerProject(**customer_project_info.model_dump())
        session.commit()
        session.refresh(customer_project_info)
        if clear_lock: session.close()
        return CustomerProjectResult_One(customer_project_info=return_user)
    
    def delete_customer_project(self, session: Session, usr_context: PvfUserContext) -> CustomerProjectDeleteResult:
        if self.id not in (None, 0, -1):
            customer_project_info_result = CustomerProject.get_customer_project_by_id(session, id=self.id, usr_context=usr_context)
            used_app_id = self.id
            used_app_tag = None
        else:
            customer_project_info_result = CustomerProject.get_customer_project_by_tag(session, tag=self.project_tag, usr_context=usr_context)
            used_app_id = None
            used_app_tag = self.project_tag
        if customer_project_info_result.failure_reason:
            return CustomerProjectDeleteResult(success=False, failure_reason=customer_project_info_result.failure_reason, customer_project_id=used_app_id, customer_project_tag=used_app_tag)

        customer_project_info = customer_project_info_result.customer_project_info
        failure_reason, log_id, customer_project_info  = CustomerProject.check_user_access_to_customer_project('delete_customer_project', key=used_app_id if used_app_id is not None else used_app_tag, usr_context=usr_context, check_customer_project=customer_project_info, update_mode=True)
        if customer_project_info is None or failure_reason != '':
            return CustomerProjectDeleteResult(failure_reason=failure_reason, log_id=log_id, customer_project_id=used_app_id, customer_project_tag=used_app_tag)
       
        customer_project_info.deleted_date = datetime.now()
        session.add(customer_project_info)
        session.commit()
        return CustomerProjectDeleteResult(success=True, customer_project_id=customer_project_info.id, customer_project_tag=customer_project_info.project_tag)

    @staticmethod
    def get_customer_project_by_tag(session: Session, *, tag: str, usr_context: PvfUserContext, customer_id: int=-1, clear_lock: bool=True) -> CustomerProjectResult_One:
        customer_id = usr_context.sess_customer.id if customer_id in (-1, 0, None) else customer_id
        customer_project_info = session.exec(select(CustomerProject).where(CustomerProject.project_tag == tag, CustomerProject.customer_id == customer_id, CustomerProject.deleted_date == None).limit(1)).one_or_none()
        failure_reason, log_id, customer_project_info = CustomerProject.check_user_access_to_customer_project('get_customer_project_by_tag', key=tag, usr_context=usr_context, check_customer_project=customer_project_info, update_mode=False)
        if clear_lock: session.close()
        return CustomerProjectResult_One(failure_reason=failure_reason, log_id=log_id, customer_project_info=customer_project_info)

    @staticmethod
    def get_customer_project_by_tag_system(session: Session, *, customer_id: int, tag: str, clear_lock: bool=True) -> CustomerProject:
        customer_project_info = session.exec(select(CustomerProject).where(CustomerProject.project_tag == tag, CustomerProject.customer_id == customer_id, CustomerProject.deleted_date == None).limit(1)).one_or_none()
        if clear_lock: session.close()
        return customer_project_info

    @staticmethod
    def get_customer_project_by_magic_token(session: Session, *, magic_token: str, usr_context: PvfUserContext, customer_id: int=-1, clear_lock: bool=True) -> CustomerProjectResult_One:
        customer_id = usr_context.sess_customer.id if customer_id in (-1, 0, None) else customer_id
        customer_project_info = session.exec(select(CustomerProject).where(CustomerProject.magic_token == magic_token, CustomerProject.customer_id == customer_id, CustomerProject.deleted_date == None).limit(1)).one_or_none()
        failure_reason, log_id, customer_project_info = CustomerProject.check_user_access_to_customer_project('get_customer_project_by_magic_token', key=magic_token, usr_context=usr_context, check_customer_project=customer_project_info, update_mode=False)
        if clear_lock: session.close()
        return CustomerProjectResult_One(failure_reason=failure_reason, log_id=log_id, customer_project_info=customer_project_info)

    @staticmethod
    def get_customer_project_by_magic_token_system(session: Session, *, customer_id: int, magic_token: str, clear_lock: bool=True) -> CustomerProject:
        customer_project_info = session.exec(select(CustomerProject).where(CustomerProject.magic_token == magic_token, CustomerProject.customer_id == customer_id, CustomerProject.deleted_date == None).limit(1)).one_or_none()
        if clear_lock: session.close()
        return customer_project_info

    @staticmethod
    def get_customer_project_by_id(session: Session, *, id: int, usr_context: PvfUserContext, customer_id: int=-1, clear_lock: bool=True) -> CustomerProjectResult_One:
        customer_id = usr_context.sess_customer.id if customer_id in (-1, 0, None) else customer_id
        customer_project_info = session.exec(select(CustomerProject).where(CustomerProject.id == id, CustomerProject.customer_id == customer_id, CustomerProject.deleted_date == None).limit(1)).one_or_none()
        failure_reason, log_id, customer_project_info = CustomerProject.check_user_access_to_customer_project('get_customer_project_by_id', key=id, usr_context=usr_context, check_customer_project=customer_project_info, update_mode=False)
        if clear_lock: session.close()
        return CustomerProjectResult_One(failure_reason=failure_reason, log_id=log_id, customer_project_info=customer_project_info)

    @staticmethod
    def get_customer_project_by_id_system(session: Session, *, customer_id: int, id: int, clear_lock: bool=True) -> CustomerProject:
        customer_project_info = session.exec(select(CustomerProject).where(CustomerProject.id == id, CustomerProject.customer_id == customer_id, CustomerProject.deleted_date == None).limit(1)).one_or_none()
        if clear_lock: session.close()
        return customer_project_info

    @staticmethod
    def get_all_customer_projects(session: Session, *, usr_context: PvfUserContext, clear_lock: bool=True) -> CustomerProjectResult_Many:
        # supports a 'my team' type list...
        customer_project_info_list = session.exec(select(CustomerProject).where(CustomerProject.customer_id == usr_context.sess_user.customer_id, CustomerProject.deleted_date == None)).all()
        if clear_lock: session.close()
        return CustomerProjectResult_Many(customer_project_info_list=customer_project_info_list)

    @staticmethod
    def get_all_customer_projects_system(session: Session, *, usr_context: PvfUserContext, clear_lock: bool=True) -> list[CustomerProject]:
        # supports a 'my team' type list...
        customer_project_info_list = session.exec(select(CustomerProject).where(CustomerProject.customer_id == usr_context.sess_user.customer_id, CustomerProject.deleted_date == None)).all()
        if clear_lock: session.close()
        return customer_project_info_list

    @staticmethod
    def check_user_access_to_customer_project(action: str, *, key: any, usr_context: PvfUserContext, check_customer_project: CustomerProject, update_mode: bool) -> tuple[str, int, CustomerProject]:
        failure_reason = ''
        log_id = 0
        if check_customer_project is None:
            log_id = log_event(log_message=f'{action} - PvfCustomer Project {key}: NOT FOUND', severity=2, 
                               usr_context=usr_context) 
            check_customer_project = None
            failure_reason = 'PvfCustomer Project not found'
        elif usr_context.sess_user.system_user_mode < 2 and check_customer_project.customer_id != usr_context.sess_user.customer_id:
            log_id = log_event(log_message=f'{action} - PvfCustomer Project {key}: PvfCustomer {check_customer_project.id} cust {check_customer_project.customer_id} PvfCustomer mismatch - SYSTEM USER REQURIED', 
                        severity=3, usr_context=usr_context)
            check_customer_project = None
            failure_reason = "Not allowed; system user mismatch"
        elif update_mode and usr_context.sess_user.customer_admin is False:
            log_id = log_event(log_message=f'{action} - PvfCustomer Project {key}: PvfCustomer {check_customer_project.id} cust {check_customer_project.customer_id} NON-ADMIN USER MISMATCH', 
                        severity=3, usr_context=usr_context)
            check_customer_project = None
            failure_reason = "Not allowed; non-admin"
        return failure_reason, log_id, check_customer_project

