"""PowerChoice external API endpoints (signed-header customer toolkit API).

The framework probe (/api-check) is provided by pvf; this router carries the
application-specific external endpoints and is registered on the external app.
"""
from typing import Any, Annotated
from pydantic import BaseModel

from sqlmodel import Field
from fastapi import APIRouter, Header

### NOTE PAYODY RESIDUE


from ..pvf.bindings.pvf_services import SessionDep, WebServiceDep

from ..db.models.customer_projects import CustomerProject, CustomerProjectResult_Many

router = APIRouter()


class DefinedProjectDetailsRequest(BaseModel):
    project_tag: str | None = Field(default=None, description="Specific project tag optionally used to filter result set")
    page_index: int = Field(default=0, description="Index of the page for pagination")
    page_size: int = Field(default=1000000, description="Number of records per page for pagination")


@router.post("/get-defined-project-records",
             summary="Retrieve information on defined projects matching criteria",
             tags=['general'],
             )
def get_defined_project_records(session: SessionDep,
                                  usr_context: WebServiceDep,
                                  data_request: DefinedProjectDetailsRequest,
                                    api_request_authentication: Annotated[str | None, Header()] = None,
                                    api_request_signature: Annotated[str | None, Header()] = None,
                                  ) -> CustomerProjectResult_Many:
    if data_request.project_tag not in (None, ''):
        data_row = CustomerProject.get_customer_project_by_tag_system(session, customer_id=usr_context.sess_user.customer_id, tag=data_request.project_tag, clear_lock=True)
        data_rows = [data_row] if data_row is not None else None
    else:
        data_rows = CustomerProject.get_all_customer_projects_system(session, usr_context=usr_context, clear_lock=True)
    return CustomerProjectResult_Many(customer_project_info_list=data_rows)
