from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, LargeBinary, UniqueConstraint
from sqlalchemy import func
from sqlmodel import Field, Session, SQLModel, select

from ...utils.pvf_base_internal_resources import PvfWsResultPackage

from ...utils.branding_image import (
    MAX_BRANDING_STORED_BYTES,
    MAX_BRANDING_UPLOAD_BYTES,
    ALLOWED_BRANDING_CONTENT_TYPES,
)

# re-export limits for callers
__all__ = [
    "MAX_BRANDING_STORED_BYTES",
    "MAX_BRANDING_UPLOAD_BYTES",
    "ALLOWED_BRANDING_CONTENT_TYPES",
    "PvfBrandingImageResult",
    "PvfCustomerBrandingImage",
    "PvfProjectBrandingImage",
]


class PvfBrandingImageResult(PvfWsResultPackage):
    has_image: bool = False
    content_type: str | None = None
    file_name: str | None = None
    original_file_name: str | None = None
    original_byte_size: int | None = None
    byte_size: int | None = None
    was_compressed: bool = False
    modify_date: datetime | None = None


class PvfCustomerBrandingImage(SQLModel, table=True):
    __tablename__ = "pvf_customerbrandingimage"
    __table_args__ = (UniqueConstraint("customer_id", name="uq_pvf_customerbrandingimage_customer_id"),)

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True, description="PvfCustomer (workspace) this branding image belongs to")
    content_type: str = Field(description="MIME type of stored image bytes")
    file_name: str | None = Field(default=None, description="Original base file name from upload")
    original_file_name: str | None = Field(default=None, description="Original base file name from upload")
    original_byte_size: int | None = Field(default=None, description="Byte size of the uploaded file before compression")
    image_data: bytes = Field(
        sa_column=Column(LargeBinary, nullable=False),
        description=f"Stored image bytes (target max {MAX_BRANDING_STORED_BYTES})",
    )
    byte_size: int = Field(description="Stored byte length of image_data")
    was_compressed: bool = Field(
        default=False,
        description="True when upload was compressed/resized to meet storage limit",
    )
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))

    @staticmethod
    def get_by_customer_id_system(
        session: Session, customer_id: int, *, clear_lock: bool = True
    ) -> PvfCustomerBrandingImage | None:
        row = session.exec(
            select(PvfCustomerBrandingImage).where(PvfCustomerBrandingImage.customer_id == customer_id).limit(1)
        ).one_or_none()
        if clear_lock:
            session.close()
        return row

    @staticmethod
    def upsert_system(
        session: Session,
        *,
        customer_id: int,
        content_type: str,
        image_data: bytes,
        file_name: str | None = None,
        original_file_name: str | None = None,
        original_byte_size: int | None = None,
        was_compressed: bool = False,
        clear_lock: bool = True,
    ) -> PvfCustomerBrandingImage:
        row = session.exec(
            select(PvfCustomerBrandingImage).where(PvfCustomerBrandingImage.customer_id == customer_id).limit(1)
        ).one_or_none()
        orig_name = original_file_name or file_name
        if row is None:
            row = PvfCustomerBrandingImage(
                customer_id=customer_id,
                content_type=content_type,
                file_name=file_name or orig_name,
                original_file_name=orig_name,
                original_byte_size=original_byte_size if original_byte_size is not None else len(image_data),
                image_data=image_data,
                byte_size=len(image_data),
                was_compressed=was_compressed,
            )
        else:
            row.content_type = content_type
            row.file_name = file_name or orig_name
            row.original_file_name = orig_name
            row.original_byte_size = original_byte_size if original_byte_size is not None else len(image_data)
            row.image_data = image_data
            row.byte_size = len(image_data)
            row.was_compressed = was_compressed
        session.add(row)
        session.commit()
        session.refresh(row)
        result = PvfCustomerBrandingImage(**{k: v for k, v in row.model_dump().items()})
        if clear_lock:
            session.close()
        return result

    @staticmethod
    def delete_by_customer_id_system(
        session: Session, customer_id: int, *, clear_lock: bool = True
    ) -> bool:
        row = session.exec(
            select(PvfCustomerBrandingImage).where(PvfCustomerBrandingImage.customer_id == customer_id).limit(1)
        ).one_or_none()
        if row is None:
            if clear_lock:
                session.close()
            return False
        session.delete(row)
        session.commit()
        if clear_lock:
            session.close()
        return True


class PvfProjectBrandingImage(SQLModel, table=True):
    __tablename__ = "pvf_projectbrandingimage"
    __table_args__ = (UniqueConstraint("project_id", name="uq_pvf_projectbrandingimage_project_id"),)

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(index=True, description="Owning customer for tenancy checks")
    project_id: int = Field(index=True, description="Project this branding image belongs to")
    content_type: str = Field(description="MIME type of stored image bytes")
    file_name: str | None = Field(default=None, description="Original base file name from upload")
    original_file_name: str | None = Field(default=None, description="Original base file name from upload")
    original_byte_size: int | None = Field(default=None, description="Byte size of the uploaded file before compression")
    image_data: bytes = Field(
        sa_column=Column(LargeBinary, nullable=False),
        description=f"Stored image bytes (target max {MAX_BRANDING_STORED_BYTES})",
    )
    byte_size: int = Field(description="Stored byte length of image_data")
    was_compressed: bool = Field(
        default=False,
        description="True when upload was compressed/resized to meet storage limit",
    )
    create_date: datetime = Field(sa_column=Column(DateTime, default=func.now()))
    modify_date: datetime = Field(sa_column=Column(DateTime, default=func.now(), onupdate=func.now()))

    @staticmethod
    def get_by_project_id_system(
        session: Session, customer_id: int, project_id: int, *, clear_lock: bool = True
    ) -> PvfProjectBrandingImage | None:
        row = session.exec(
            select(PvfProjectBrandingImage)
            .where(
                PvfProjectBrandingImage.customer_id == customer_id,
                PvfProjectBrandingImage.project_id == project_id,
            )
            .limit(1)
        ).one_or_none()
        if clear_lock:
            session.close()
        return row

    @staticmethod
    def upsert_system(
        session: Session,
        *,
        customer_id: int,
        project_id: int,
        content_type: str,
        image_data: bytes,
        file_name: str | None = None,
        original_file_name: str | None = None,
        original_byte_size: int | None = None,
        was_compressed: bool = False,
        clear_lock: bool = True,
    ) -> PvfProjectBrandingImage:
        row = session.exec(
            select(PvfProjectBrandingImage)
            .where(
                PvfProjectBrandingImage.customer_id == customer_id,
                PvfProjectBrandingImage.project_id == project_id,
            )
            .limit(1)
        ).one_or_none()
        orig_name = original_file_name or file_name
        if row is None:
            row = PvfProjectBrandingImage(
                customer_id=customer_id,
                project_id=project_id,
                content_type=content_type,
                file_name=file_name or orig_name,
                original_file_name=orig_name,
                original_byte_size=original_byte_size if original_byte_size is not None else len(image_data),
                image_data=image_data,
                byte_size=len(image_data),
                was_compressed=was_compressed,
            )
        else:
            row.content_type = content_type
            row.file_name = file_name or orig_name
            row.original_file_name = orig_name
            row.original_byte_size = original_byte_size if original_byte_size is not None else len(image_data)
            row.image_data = image_data
            row.byte_size = len(image_data)
            row.was_compressed = was_compressed
        session.add(row)
        session.commit()
        session.refresh(row)
        result = PvfProjectBrandingImage(**{k: v for k, v in row.model_dump().items()})
        if clear_lock:
            session.close()
        return result

    @staticmethod
    def delete_by_project_id_system(
        session: Session, customer_id: int, project_id: int, *, clear_lock: bool = True
    ) -> bool:
        row = session.exec(
            select(PvfProjectBrandingImage)
            .where(
                PvfProjectBrandingImage.customer_id == customer_id,
                PvfProjectBrandingImage.project_id == project_id,
            )
            .limit(1)
        ).one_or_none()
        if row is None:
            if clear_lock:
                session.close()
            return False
        session.delete(row)
        session.commit()
        if clear_lock:
            session.close()
        return True
