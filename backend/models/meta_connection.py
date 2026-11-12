"""Additive Meta/Facebook & Instagram Lead Ads connection models.

These tables extend the existing `meta_pages` / `leads` integration without
replacing it.  One row in ``meta_connections`` represents an official Meta
OAuth connection (the long-lived user token).  Authorized Pages continue to
live in ``meta_pages`` so the existing manual Page endpoints keep working.

``meta_lead_forms`` stores every discovered Instant Form and whether the admin
selected it.  ``meta_lead_events`` is the durable webhook/lead ingestion queue
used for idempotency, retry and the activity log.  ``meta_import_jobs`` tracks
historical backfills so the UI can show progress.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class MetaConnection(Base):
    __tablename__ = "meta_connections"

    id = Column(Integer, primary_key=True, index=True)
    fb_user_id = Column(String(100), unique=True, index=True, nullable=False)
    fb_user_name = Column(String(255), nullable=True)
    encrypted_access_token = Column(Text, nullable=False)
    token_issued_at = Column(DateTime, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    scopes = Column(Text, nullable=True)
    status = Column(String(30), default="CONNECTED", nullable=False, index=True)
    auto_sync_enabled = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(DateTime, nullable=True)
    last_webhook_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    connected_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    pages = relationship("MetaPage", back_populates="connection")


class MetaLeadForm(Base):
    __tablename__ = "meta_lead_forms"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(String(100), unique=True, index=True, nullable=False)
    page_id = Column(String(100), index=True, nullable=False)
    page_db_id = Column(Integer, ForeignKey("meta_pages.id"), nullable=True)
    name = Column(String(255), nullable=True)
    status = Column(String(30), default="ACTIVE", nullable=False)
    locale = Column(String(20), nullable=True)
    questions_json = Column(Text, nullable=True)
    is_selected = Column(Boolean, default=True, nullable=False, index=True)
    leads_count = Column(Integer, default=0, nullable=False)
    last_lead_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    meta_created_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class MetaLeadEvent(Base):
    __tablename__ = "meta_lead_events"

    id = Column(Integer, primary_key=True, index=True)
    event_key = Column(String(255), unique=True, index=True, nullable=False)
    leadgen_id = Column(String(100), index=True, nullable=True)
    page_id = Column(String(100), index=True, nullable=True)
    form_id = Column(String(100), index=True, nullable=True)
    platform = Column(String(20), nullable=True)
    status = Column(String(30), default="RECEIVED", nullable=False, index=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=8, nullable=False)
    next_retry_at = Column(DateTime, index=True, nullable=True)
    last_error = Column(Text, nullable=True)
    payload_json = Column(Text, nullable=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    is_reinquiry = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    processed_at = Column(DateTime, nullable=True)


class MetaImportJob(Base):
    __tablename__ = "meta_import_jobs"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(30), default="PENDING", nullable=False, index=True)
    range_preset = Column(String(20), nullable=True)
    since = Column(DateTime, nullable=True)
    until = Column(DateTime, nullable=True)
    page_ids_json = Column(Text, nullable=True)
    form_ids_json = Column(Text, nullable=True)
    total_forms = Column(Integer, default=0, nullable=False)
    processed_forms = Column(Integer, default=0, nullable=False)
    total_fetched = Column(Integer, default=0, nullable=False)
    imported = Column(Integer, default=0, nullable=False)
    duplicates = Column(Integer, default=0, nullable=False)
    failed = Column(Integer, default=0, nullable=False)
    error = Column(Text, nullable=True)
    current_item = Column(String(255), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
