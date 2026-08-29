from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel

from ..db.models.branding_images import (
    PvfBrandingImageResult,
    PvfCustomerBrandingImage,
    PvfProjectBrandingImage,
)
from ..db.models.customer_user import PvfCustomer
from ..db.models.share_link_tracking import PvfShareLink
from ..depends.api_session_dependencies import SessionDep
from ..depends.check_user_session_jwt_dependencies import UserAccessDep
from ..bindings.pvf_invocation import get_hooks
from ..utils.pvf_base_internal_resources import PvfWsResultPackage
from ..utils.branding_image import process_branding_upload
from ..utils.log_event import log_event
from .share_link_manage import get_token_cookie, make_token_cookie

router = APIRouter()
share_router = APIRouter()


class BrandingMeta(BaseModel):
    customer_name: str | None = None
    has_customer_image: bool = False
    customer_image_modify_date: datetime | None = None
    project_title: str | None = None
    has_project_image: bool = False
    project_image_modify_date: datetime | None = None


class ShareBrandingMetaResult(PvfWsResultPackage):
    branding: BrandingMeta | None = None


def _row_meta(row) -> PvfBrandingImageResult:
    if row is None:
        return PvfBrandingImageResult(has_image=False)
    return PvfBrandingImageResult(
        has_image=True,
        content_type=row.content_type,
        file_name=row.file_name,
        original_file_name=getattr(row, "original_file_name", None) or row.file_name,
        original_byte_size=(
            getattr(row, "original_byte_size", None)
            if getattr(row, "original_byte_size", None) is not None
            else row.byte_size
        ),
        byte_size=row.byte_size,
        was_compressed=bool(getattr(row, "was_compressed", False)),
        modify_date=row.modify_date,
    )


def _read_processed_upload(file: UploadFile):
    data = file.file.read()
    try:
        return process_branding_upload(
            data,
            content_type_hint=file.content_type,
            filename=file.filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _meta_from_rows(
    *,
    customer: PvfCustomer | None,
    project_display_name: str | None,
    cust_img: PvfCustomerBrandingImage | None,
    proj_img: PvfProjectBrandingImage | None,
) -> BrandingMeta:
    return BrandingMeta(
        customer_name=customer.customer_name if customer else None,
        has_customer_image=cust_img is not None,
        customer_image_modify_date=cust_img.modify_date if cust_img else None,
        project_title=project_display_name,
        has_project_image=proj_img is not None,
        project_image_modify_date=proj_img.modify_date if proj_img else None,
    )


def _resolve_entity_for_user(session, usr_context, entity_id: int):
    """Resolve and tenancy-check an application entity via the registered entity_resolver hook.

    Returns the PvfResolvedEntity, or None when the entity does not exist or belongs to
    a different customer.
    """
    resolver = get_hooks().entity_resolver
    if resolver is None:
        log_event("Branding image store requires the application entity_resolver hook", severity=4,
                  raise_exception=HTTPException(status_code=500, detail="Branding image support is not fully configured"))
    resolved = resolver(session=session, usr_context=usr_context, entity_id=entity_id)
    if resolved is None or resolved.customer_id != usr_context.sess_user.customer_id:
        return None
    return resolved


def _resolve_share_link(session, token: str):
    result = PvfShareLink.get_shared_link_by_id_or_magic_token_system(
        session=session,
        shared_magic_token=token,
        clear_lock=False,
        allow_disabled_link_retrieval=False,
    )
    if result.failure_reason or result.link_info is None:
        return None, result.failure_reason or "Share link not found"
    return result.link_info, None


def _share_session_authenticated(request: Request, shared_magic_token: str) -> bool:
    """True when the httponly share view cookie is present and valid for this token."""
    view_token, display_name, email, make_cookies_better = get_token_cookie(request)
    if view_token is None or make_cookies_better is None:
        return False
    expected, _ = make_token_cookie(
        shared_magic_token=shared_magic_token,
        display_name=display_name,
        email=email,
        make_cookies_better=make_cookies_better,
    )
    return view_token == expected


def _require_share_session(request: Request, token: str) -> None:
    if not _share_session_authenticated(request, token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Share authentication required to download branding images",
        )


def _image_response(row) -> Response:
    return Response(
        content=bytes(row.image_data),
        media_type=row.content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


def _upsert_kwargs(processed) -> dict:
    return dict(
        content_type=processed.content_type,
        image_data=processed.image_data,
        file_name=processed.file_name,
        original_file_name=processed.original_file_name,
        original_byte_size=processed.original_byte_size,
        was_compressed=processed.was_compressed,
    )


# ---- Authenticated workspace branding ----


@router.get(
    "/branding/customer-meta",
    summary="Workspace branding image metadata",
    tags=["context"],
)
def get_customer_branding_meta(
    session: SessionDep, usr_context: UserAccessDep
) -> PvfBrandingImageResult:
    customer_id = usr_context.sess_user.customer_id
    row = PvfCustomerBrandingImage.get_by_customer_id_system(
        session=session, customer_id=customer_id, clear_lock=False
    )
    return _row_meta(row)


@router.get(
    "/branding/customer-image",
    summary="Download workspace branding image",
    tags=["context"],
)
def get_customer_branding_image(session: SessionDep, usr_context: UserAccessDep):
    customer_id = usr_context.sess_user.customer_id
    row = PvfCustomerBrandingImage.get_by_customer_id_system(
        session=session, customer_id=customer_id, clear_lock=False
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No branding image")
    return _image_response(row)


@router.post(
    "/branding/customer-image",
    summary="Admin: upload or replace workspace branding image",
    tags=["context"],
)
def upload_customer_branding_image(
    session: SessionDep,
    usr_context: UserAccessDep,
    file: UploadFile = File(...),
) -> PvfBrandingImageResult:
    if not usr_context.sess_user.customer_admin:
        log_id = log_event(
            "Non-admin attempted to upload customer branding image",
            usr_context=usr_context,
            severity=3,
        )
        return PvfBrandingImageResult(failure_reason="PvfCustomer admin access required", log_id=log_id)
    processed = _read_processed_upload(file)
    row = PvfCustomerBrandingImage.upsert_system(
        session=session,
        customer_id=usr_context.sess_user.customer_id,
        clear_lock=False,
        **_upsert_kwargs(processed),
    )
    return _row_meta(row)


@router.delete(
    "/branding/customer-image",
    summary="Admin: delete workspace branding image",
    tags=["context"],
)
def delete_customer_branding_image(
    session: SessionDep, usr_context: UserAccessDep
) -> PvfBrandingImageResult:
    if not usr_context.sess_user.customer_admin:
        log_id = log_event(
            "Non-admin attempted to delete customer branding image",
            usr_context=usr_context,
            severity=3,
        )
        return PvfBrandingImageResult(failure_reason="PvfCustomer admin access required", log_id=log_id)
    PvfCustomerBrandingImage.delete_by_customer_id_system(
        session=session, customer_id=usr_context.sess_user.customer_id, clear_lock=False
    )
    return PvfBrandingImageResult(has_image=False)


@router.get(
    "/branding/project-meta",
    summary="Project branding image metadata",
    tags=["manage-projects"],
)
def get_project_branding_meta(
    session: SessionDep,
    usr_context: UserAccessDep,
    project_id: int,
) -> PvfBrandingImageResult:
    customer_id = usr_context.sess_user.customer_id
    if _resolve_entity_for_user(session, usr_context, project_id) is None:
        return PvfBrandingImageResult(failure_reason="Project not found")
    row = PvfProjectBrandingImage.get_by_project_id_system(
        session=session, customer_id=customer_id, project_id=project_id, clear_lock=False
    )
    return _row_meta(row)


@router.get(
    "/branding/project-image",
    summary="Download project branding image",
    tags=["manage-projects"],
)
def get_project_branding_image(
    session: SessionDep,
    usr_context: UserAccessDep,
    project_id: int,
):
    customer_id = usr_context.sess_user.customer_id
    if _resolve_entity_for_user(session, usr_context, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    row = PvfProjectBrandingImage.get_by_project_id_system(
        session=session, customer_id=customer_id, project_id=project_id, clear_lock=False
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No branding image")
    return _image_response(row)


@router.post(
    "/branding/project-image",
    summary="Admin: upload or replace project branding image",
    tags=["manage-projects"],
)
def upload_project_branding_image(
    session: SessionDep,
    usr_context: UserAccessDep,
    project_id: int = Form(...),
    file: UploadFile = File(...),
) -> PvfBrandingImageResult:
    if not usr_context.sess_user.customer_admin:
        log_id = log_event(
            "Non-admin attempted to upload project branding image",
            usr_context=usr_context,
            severity=3,
        )
        return PvfBrandingImageResult(failure_reason="PvfCustomer admin access required", log_id=log_id)
    customer_id = usr_context.sess_user.customer_id
    if _resolve_entity_for_user(session, usr_context, project_id) is None:
        return PvfBrandingImageResult(failure_reason="Project not found")
    processed = _read_processed_upload(file)
    row = PvfProjectBrandingImage.upsert_system(
        session=session,
        customer_id=customer_id,
        project_id=project_id,
        clear_lock=False,
        **_upsert_kwargs(processed),
    )
    return _row_meta(row)


@router.delete(
    "/branding/project-image",
    summary="Admin: delete project branding image",
    tags=["manage-projects"],
)
def delete_project_branding_image(
    session: SessionDep,
    usr_context: UserAccessDep,
    project_id: int,
) -> PvfBrandingImageResult:
    if not usr_context.sess_user.customer_admin:
        log_id = log_event(
            "Non-admin attempted to delete project branding image",
            usr_context=usr_context,
            severity=3,
        )
        return PvfBrandingImageResult(failure_reason="PvfCustomer admin access required", log_id=log_id)
    customer_id = usr_context.sess_user.customer_id
    if _resolve_entity_for_user(session, usr_context, project_id) is None:
        return PvfBrandingImageResult(failure_reason="Project not found")
    PvfProjectBrandingImage.delete_by_project_id_system(
        session=session, customer_id=customer_id, project_id=project_id, clear_lock=False
    )
    return PvfBrandingImageResult(has_image=False)


# ---- Share branding: meta by valid token; binary only after share session cookie ----


@share_router.get(
    "/share/{token}/branding",
    summary="Branding meta for a share link (valid token; no image bytes)",
    tags=["share_ext"],
)
def share_branding_meta(session: SessionDep, token: str) -> ShareBrandingMetaResult:
    link, err = _resolve_share_link(session, token)
    if link is None:
        return ShareBrandingMetaResult(failure_reason=err or "Share link not found")
    customer = PvfCustomer.get_customer_by_id_system(session=session, id=link.customer_id, clear_lock=False)
    cust_img = PvfCustomerBrandingImage.get_by_customer_id_system(
        session=session, customer_id=link.customer_id, clear_lock=False
    )
    proj_img = PvfProjectBrandingImage.get_by_project_id_system(
        session=session,
        customer_id=link.customer_id,
        project_id=link.shared_entity_db_id,
        clear_lock=False,
    )
    return ShareBrandingMetaResult(
        branding=_meta_from_rows(
            customer=customer, project_display_name=link.share_link_name, cust_img=cust_img, proj_img=proj_img
        )
    )


@share_router.get(
    "/share/{token}/customer-image",
    summary="Workspace branding image (requires authenticated share session)",
    tags=["share_ext"],
)
def share_customer_image(session: SessionDep, request: Request, token: str):
    link, err = _resolve_share_link(session, token)
    if link is None:
        raise HTTPException(status_code=404, detail=err or "Share link not found")
    _require_share_session(request, token)
    row = PvfCustomerBrandingImage.get_by_customer_id_system(
        session=session, customer_id=link.customer_id, clear_lock=False
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No branding image")
    return _image_response(row)


@share_router.get(
    "/share/{token}/project-image",
    summary="Project branding image (requires authenticated share session)",
    tags=["share_ext"],
)
def share_project_image(session: SessionDep, request: Request, token: str):
    link, err = _resolve_share_link(session, token)
    if link is None:
        raise HTTPException(status_code=404, detail=err or "Share link not found")
    _require_share_session(request, token)
    row = PvfProjectBrandingImage.get_by_project_id_system(
        session=session,
        customer_id=link.customer_id,
        project_id=link.shared_entity_db_id,
        clear_lock=False,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No branding image")
    return _image_response(row)
