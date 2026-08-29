"""Watcher queue tables — hybrid dedicated + generic.

Four tables:
  watcher_llm_requests   — dedicated LLM
  watcher_email_requests — dedicated email
  watcher_api_requests   — dedicated API callback
  watcher_generic_jobs   — generic fallback for arbitrary work_type

Every table participates in the same status lifecycle (queued → trying → {complete|will_retry|no_retry|max_retries_exceeded})
and the same claim pattern (SELECT … FOR UPDATE SKIP LOCKED ordered by next_attempt_at, id).

These models are re-exported via src/pvf/db/models/watcher_*.py so pvf_bootstrap can register them.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _now_column():
    return Column(DateTime, default=func.now())

def _updated_column():
    return Column(DateTime, default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------------------
# LLM dedicated queue
# ---------------------------------------------------------------------------

class PvfWatcherLlmRequest(SQLModel, table=True):
    __tablename__ = "pvf_watcher_llm_requests"
    __table_args__ = (
        Index("ix_pvf_watcher_llm_requests_claim", "status", "next_attempt_at", "id"),
        Index("ix_pvf_watcher_llm_requests_customer", "customer_id", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int | None = Field(default=None, index=True, description="Tenancy: customer_id from usr_context or NULL for _system")
    created_by_user_id: int | None = Field(default=None, index=True, description="Tenancy: user_id from usr_context or NULL for _system")

    provider: str = Field(default="opencode_go", description="LLM provider key (normalized)")
    model: str = Field(default="", description="Requested model identifier")
    api_key_encrypted: str | None = Field(default=None, description="Encrypted api_key; never plaintext in request_package")
    key_source: str | None = Field(default=None, description="Source of api_key: customer | system | api | None")
    prompt_hash: str | None = Field(default=None, description="SHA256 of prompt/messages for dedup/redaction grouping")
    prompt_bytes: int | None = Field(default=None, description="Total bytes sent for prompt/messages payload (utf-8)")
    response_bytes: int | None = Field(default=None, description="Total bytes received in LLM response (text/json)")

    messages_json: dict | list | None = Field(default=None, sa_column=Column(JSONB, nullable=True), description="Stored only when CAPTURE allowed for this tag")
    request_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True), description="{messages, temperature, max_tokens, metadata, semantic_tag}")
    result_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True), description="{text, usage, latency_ms}")
    raw_trace: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True), description="Full provider trace, honored only when CAPTURE allowed")
    error_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True), description="{code, message, retryable, traceback}")

    semantic_tag: str | None = Field(default=None, index=True, description="App-supplied tag e.g. SHORTEN_PRODUCT_NAME, participates in no_log filter")

    status: str = Field(default="queued", index=True, description="queued | trying | complete | will_retry | no_retry | max_retries_exceeded | failed")
    attempts: int = Field(default=0, description="Number of attempts already made")
    max_attempts: int = Field(default=3, description="Max attempts before max_retries_exceeded")
    next_attempt_at: datetime | None = Field(default=None, index=True, description="Earliest time this row is eligible to be claimed again")

    created_at: datetime = Field(sa_column=_now_column())
    updated_at: datetime = Field(sa_column=_updated_column())
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))


# ---------------------------------------------------------------------------
# Email dedicated queue
# ---------------------------------------------------------------------------

class PvfWatcherEmailRequest(SQLModel, table=True):
    __tablename__ = "pvf_watcher_email_requests"
    __table_args__ = (
        Index("ix_pvf_watcher_email_requests_claim", "status", "next_attempt_at", "id"),
        Index("ix_pvf_watcher_email_requests_customer", "customer_id", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int | None = Field(default=None, index=True)
    created_by_user_id: int | None = Field(default=None, index=True)

    to_email: str = Field(index=True, description="Destination email address")
    template_type: str = Field(default="", description="Email template / type code")
    params_json: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    payload_json: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    request_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    result_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    error_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    semantic_tag: str | None = Field(default=None, index=True)

    status: str = Field(default="queued", index=True)
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=5)
    next_attempt_at: datetime | None = Field(default=None, index=True)

    created_at: datetime = Field(sa_column=_now_column())
    updated_at: datetime = Field(sa_column=_updated_column())
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))


# ---------------------------------------------------------------------------
# API dedicated queue (generalized callback_delivery)
# ---------------------------------------------------------------------------

class PvfWatcherApiRequest(SQLModel, table=True):
    __tablename__ = "pvf_watcher_api_requests"
    __table_args__ = (
        Index("ix_pvf_watcher_api_requests_claim", "status", "next_attempt_at", "id"),
        Index("ix_pvf_watcher_api_requests_customer", "customer_id", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int | None = Field(default=None, index=True)
    created_by_user_id: int | None = Field(default=None, index=True)

    target_url: str = Field(default="", description="Destination URL for the API callback")
    http_method: str = Field(default="POST", description="HTTP method (default POST)")
    connection_protocol: str = Field(default="pvf", index=True, description="V1 always 'pvf'; future ssh/bearer without migration")
    auth_protocol: str = Field(default="pvf", index=True, description="V1 always 'pvf'")
    auth_params_encrypted: str | None = Field(default=None, description="Encrypted auth_params JSON string")
    headers_json: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    payload_json: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    request_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    result_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    error_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    semantic_tag: str | None = Field(default=None, index=True)

    status: str = Field(default="queued", index=True)
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=5)
    next_attempt_at: datetime | None = Field(default=None, index=True)

    created_at: datetime = Field(sa_column=_now_column())
    updated_at: datetime = Field(sa_column=_updated_column())
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))


# ---------------------------------------------------------------------------
# Generic queue — any work_type not listed still served here
# ---------------------------------------------------------------------------

class PvfWatcherGenericJob(SQLModel, table=True):
    __tablename__ = "pvf_watcher_generic_jobs"
    __table_args__ = (
        Index("ix_pvf_watcher_generic_jobs_claim", "status", "next_attempt_at", "id"),
        Index("ix_pvf_watcher_generic_jobs_customer", "customer_id", "status"),
        Index("ix_pvf_watcher_generic_jobs_work_type", "work_type"),
    )

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int | None = Field(default=None, index=True)
    created_by_user_id: int | None = Field(default=None, index=True)

    work_type: str = Field(index=True, description="Application semantic work type (e.g. SHORTEN_PRODUCT_NAME)")
    request_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    result_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    error_package: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    semantic_tag: str | None = Field(default=None, index=True)

    status: str = Field(default="queued", index=True)
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=3)
    next_attempt_at: datetime | None = Field(default=None, index=True)

    created_at: datetime = Field(sa_column=_now_column())
    updated_at: datetime = Field(sa_column=_updated_column())
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))
