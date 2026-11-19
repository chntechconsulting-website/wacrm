"""
Local mirror of the WA HRMS Channel Partner integration.

The CRM never owns channel-partner registrations, approvals, commission rules
or payouts. WA HRMS remains the system of record; these tables are an additive,
read-only copy used for fast CRM screens, filtering and audit. Every row keeps
the external WA HRMS UUID plus the (sanitised) raw API/webhook payload so fields
that are not mapped yet are still available.

Sensitive values (full PAN, Aadhaar, bank account numbers, document links) are
never stored here. They are redacted before persistence; PAN is kept masked and
identity documents are fetched only through the documented short-lived API.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.types import JSON

from database import Base
from utils.timezone import get_ist_now

# MySQL TEXT is only 64 KB. Webhook payloads and raw API objects can be much
# larger, so use LONGTEXT on MySQL while staying portable on SQLite (tests).
LongText = Text().with_variant(LONGTEXT(), "mysql")


class ChannelPartnerIntegration(Base):
    """Singleton integration configuration and health."""

    __tablename__ = "channel_partner_integration"

    id = Column(Integer, primary_key=True, default=1)

    # Admin override. Secrets themselves are only ever stored encrypted.
    base_url = Column(String(500), nullable=True)
    api_key_encrypted = Column(Text, nullable=True)
    api_key_last4 = Column(String(8), nullable=True)
    webhook_secret_encrypted = Column(Text, nullable=True)
    webhook_secret_last4 = Column(String(8), nullable=True)

    # Latest GET /summary payload exactly as returned (sanitised).
    summary_json = Column(JSON, nullable=True)
    summary_synced_at = Column(DateTime, nullable=True)

    last_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(30), nullable=True)
    last_sync_error = Column(Text, nullable=True)

    last_event_poll_at = Column(DateTime, nullable=True)
    last_event_poll_error = Column(Text, nullable=True)

    webhook_last_received_at = Column(DateTime, nullable=True)
    webhook_last_event_type = Column(String(80), nullable=True)

    created_at = Column(DateTime, default=get_ist_now, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)


class ChannelPartnerSyncRun(Base):
    """One manual or scheduled synchronisation attempt."""

    __tablename__ = "channel_partner_sync_runs"

    id = Column(Integer, primary_key=True, index=True)
    trigger = Column(String(30), nullable=False, index=True)  # manual / poll / startup / webhook
    scope = Column(String(40), nullable=False, index=True)  # full / events / ...
    status = Column(String(30), nullable=False, default="running", index=True)
    triggered_by_user_id = Column(Integer, nullable=True)
    started_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True)
    stats_json = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)


class ChannelPartnerSyncCheckpoint(Base):
    """Durable polling cursor (`nextAfter`) per event stream."""

    __tablename__ = "channel_partner_sync_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    checkpoint_key = Column(String(80), nullable=False, unique=True, index=True)
    last_after = Column(BigInteger, nullable=False, default=0)
    last_success_at = Column(DateTime, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)


class ChannelPartner(Base):
    __tablename__ = "channel_partners"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(64), nullable=False, unique=True, index=True)

    name = Column(String(255), nullable=True, index=True)
    code = Column(String(60), nullable=True, index=True)
    entity_type = Column(String(30), nullable=True)
    legal_name = Column(String(255), nullable=True)

    email = Column(String(255), nullable=True)
    phone = Column(String(40), nullable=True)

    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(120), nullable=True, index=True)
    state = Column(String(120), nullable=True)
    state_code = Column(String(10), nullable=True)
    pincode = Column(String(20), nullable=True)

    pan_masked = Column(String(20), nullable=True)
    pan_last4 = Column(String(8), nullable=True)
    pan_present = Column(Boolean, default=False, nullable=False)
    gst_registered = Column(Boolean, nullable=True)
    gstin = Column(String(30), nullable=True)
    gst_rate_bps = Column(Integer, nullable=True)

    commission_rate_bps = Column(Integer, nullable=True)
    payout_frequency = Column(String(30), nullable=True)
    hold_days = Column(Integer, nullable=True)
    min_payout_paise = Column(BigInteger, nullable=True)
    first_client_discount_bps = Column(Integer, nullable=True)

    tds_certificate_rate_bps = Column(Integer, nullable=True)
    tds_certificate_number = Column(String(80), nullable=True)
    tds_certificate_valid_until = Column(Date, nullable=True)

    status = Column(String(30), nullable=True, index=True)
    notes = Column(Text, nullable=True)

    balances_json = Column(JSON, nullable=True)
    monthly_commission_series_json = Column(JSON, nullable=True)
    tds_status_json = Column(JSON, nullable=True)
    inactivity_status_json = Column(JSON, nullable=True)
    first_client_offer_json = Column(JSON, nullable=True)
    application_documents_json = Column(JSON, nullable=True)

    list_raw = Column(JSON, nullable=True)
    detail_raw = Column(JSON, nullable=True)

    source_updated_at = Column(DateTime, nullable=True)
    source_created_at = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, default=get_ist_now, nullable=False)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)

    __table_args__ = (
        Index("ix_channel_partners_status_name", "status", "name"),
    )


class ChannelPartnerLogin(Base):
    __tablename__ = "channel_partner_logins"

    id = Column(Integer, primary_key=True, index=True)
    record_key = Column(String(160), nullable=False, unique=True, index=True)
    external_id = Column(String(64), nullable=True, index=True)
    partner_external_id = Column(String(64), nullable=False, index=True)

    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(40), nullable=True)
    role = Column(String(40), nullable=True)
    is_active = Column(Boolean, nullable=True)
    invite_status = Column(String(40), nullable=True)
    invited_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)

    raw_data = Column(JSON, nullable=True)
    synced_at = Column(DateTime, default=get_ist_now, nullable=False)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)


class ChannelPartnerApplication(Base):
    __tablename__ = "channel_partner_applications"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(64), nullable=False, unique=True, index=True)

    entity_type = Column(String(30), nullable=True)
    business_name = Column(String(255), nullable=True, index=True)
    business_type = Column(String(120), nullable=True)
    team_size = Column(String(40), nullable=True)
    years_in_business = Column(String(40), nullable=True)
    website = Column(String(255), nullable=True)

    pan_masked = Column(String(20), nullable=True)
    pan_last4 = Column(String(8), nullable=True)
    pan_present = Column(Boolean, default=False, nullable=False)
    gstin = Column(String(30), nullable=True)

    contact_name = Column(String(255), nullable=True)
    designation = Column(String(120), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(40), nullable=True)

    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(120), nullable=True)
    state = Column(String(120), nullable=True)
    state_code = Column(String(10), nullable=True)
    pincode = Column(String(20), nullable=True)

    regions = Column(Text, nullable=True)
    industries_json = Column(JSON, nullable=True)
    current_clients = Column(String(40), nullable=True)
    expected_clients = Column(String(40), nullable=True)
    heard_from = Column(String(120), nullable=True)
    message = Column(Text, nullable=True)
    consent = Column(Boolean, nullable=True)

    status = Column(String(30), nullable=True, index=True)
    review_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    partner_external_id = Column(String(64), nullable=True, index=True)

    document_metadata_json = Column(JSON, nullable=True)
    raw_data = Column(JSON, nullable=True)

    source_created_at = Column(DateTime, nullable=True, index=True)
    source_updated_at = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, default=get_ist_now, nullable=False)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)

    __table_args__ = (
        Index("ix_channel_partner_applications_status_created", "status", "source_created_at"),
    )


class ChannelPartnerLead(Base):
    __tablename__ = "channel_partner_leads"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(64), nullable=False, unique=True, index=True)
    partner_external_id = Column(String(64), nullable=True, index=True)
    partner_name = Column(String(255), nullable=True)

    status = Column(String(30), nullable=True, index=True)
    company_name = Column(String(255), nullable=True)
    contact_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(40), nullable=True)
    city = Column(String(120), nullable=True)
    state = Column(String(120), nullable=True)
    source = Column(String(120), nullable=True)
    message = Column(Text, nullable=True)

    review_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    organization_id = Column(String(64), nullable=True, index=True)
    subscription_order_id = Column(String(64), nullable=True, index=True)
    converted_at = Column(DateTime, nullable=True)
    protection_until = Column(DateTime, nullable=True)

    raw_data = Column(JSON, nullable=True)

    source_created_at = Column(DateTime, nullable=True, index=True)
    source_updated_at = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, default=get_ist_now, nullable=False)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)

    __table_args__ = (
        Index("ix_channel_partner_leads_partner_status", "partner_external_id", "status"),
        Index("ix_channel_partner_leads_status_created", "status", "source_created_at"),
    )


class ChannelPartnerClientAttribution(Base):
    __tablename__ = "channel_partner_client_attributions"

    id = Column(Integer, primary_key=True, index=True)
    record_key = Column(String(160), nullable=False, unique=True, index=True)
    external_id = Column(String(64), nullable=True, index=True)
    partner_external_id = Column(String(64), nullable=False, index=True)

    organization_id = Column(String(64), nullable=True, index=True)
    organization_name = Column(String(255), nullable=True)
    subscription_order_id = Column(String(64), nullable=True, index=True)
    order_number = Column(String(120), nullable=True)
    status = Column(String(30), nullable=True, index=True)
    effective_from = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    end_reason = Column(Text, nullable=True)

    attribution_data = Column(JSON, nullable=True)
    raw_data = Column(JSON, nullable=True)

    source_created_at = Column(DateTime, nullable=True)
    source_updated_at = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, default=get_ist_now, nullable=False)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)


class ChannelPartnerCoupon(Base):
    __tablename__ = "channel_partner_coupons"

    id = Column(Integer, primary_key=True, index=True)
    record_key = Column(String(160), nullable=False, unique=True, index=True)
    external_id = Column(String(64), nullable=True, index=True)
    partner_external_id = Column(String(64), nullable=False, index=True)

    code = Column(String(80), nullable=True, index=True)
    status = Column(String(30), nullable=True, index=True)
    description = Column(Text, nullable=True)
    discount_bps = Column(Integer, nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    details_json = Column(JSON, nullable=True)
    raw_data = Column(JSON, nullable=True)

    source_updated_at = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, default=get_ist_now, nullable=False)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)


class ChannelPartnerCommission(Base):
    __tablename__ = "channel_partner_commissions"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(64), nullable=False, unique=True, index=True)
    partner_external_id = Column(String(64), nullable=True, index=True)

    description = Column(String(255), nullable=True)
    amount_paise = Column(BigInteger, nullable=True)
    base_paise = Column(BigInteger, nullable=True)
    rate_bps = Column(Integer, nullable=True)
    status = Column(String(30), nullable=True, index=True)
    hold_until = Column(DateTime, nullable=True)
    invoice_number = Column(String(120), nullable=True)
    client_name = Column(String(255), nullable=True)
    entry_type = Column(String(40), nullable=True)
    reason = Column(Text, nullable=True)

    raw_data = Column(JSON, nullable=True)

    earned_at = Column(DateTime, nullable=True, index=True)
    source_updated_at = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, default=get_ist_now, nullable=False)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)

    __table_args__ = (
        Index("ix_channel_partner_commissions_partner_status", "partner_external_id", "status"),
    )


class ChannelPartnerPayout(Base):
    __tablename__ = "channel_partner_payouts"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(64), nullable=False, unique=True, index=True)
    partner_external_id = Column(String(64), nullable=True, index=True)
    partner_name = Column(String(255), nullable=True)

    status = Column(String(30), nullable=True, index=True)
    gross_paise = Column(BigInteger, nullable=True)
    net_paise = Column(BigInteger, nullable=True)
    tds_paise = Column(BigInteger, nullable=True)
    gst_paise = Column(BigInteger, nullable=True)
    adjustment_paise = Column(BigInteger, nullable=True)

    payment_method = Column(String(40), nullable=True)
    payment_reference = Column(String(160), nullable=True)
    payment_date = Column(DateTime, nullable=True)
    partner_invoice_number = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)

    commission_entries_json = Column(JSON, nullable=True)
    raw_data = Column(JSON, nullable=True)

    source_created_at = Column(DateTime, nullable=True)
    source_updated_at = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, default=get_ist_now, nullable=False)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)

    __table_args__ = (
        Index("ix_channel_partner_payouts_status_created", "status", "source_created_at"),
    )


class ChannelPartnerWebhookEvent(Base):
    __tablename__ = "channel_partner_webhook_events"

    id = Column(Integer, primary_key=True, index=True)

    # WAHRMS-Event-Id (stable across retries) is the idempotency key.
    event_id = Column(String(191), nullable=False, unique=True, index=True)
    delivery_id = Column(String(191), nullable=True, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    event_created_at = Column(DateTime, nullable=True, index=True)
    sequence = Column(BigInteger, nullable=True, index=True)

    source = Column(String(20), nullable=False, default="webhook", index=True)  # webhook / poll
    status = Column(String(30), nullable=False, default="pending", index=True)
    # pending / processed / failed / ignored / stale
    error = Column(Text, nullable=True)

    related_partner_external_id = Column(String(64), nullable=True, index=True)
    related_lead_external_id = Column(String(64), nullable=True, index=True)
    related_client_external_id = Column(String(64), nullable=True, index=True)

    payload = Column(LongText, nullable=True)
    headers_json = Column(JSON, nullable=True)

    received_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)


class ChannelPartnerWebhookRejection(Base):
    """Invalid webhook attempts, kept without trusting their contents."""

    __tablename__ = "channel_partner_webhook_rejections"

    id = Column(Integer, primary_key=True, index=True)
    reason = Column(String(120), nullable=False, index=True)
    remote_ip = Column(String(80), nullable=True)
    signature_header = Column(String(500), nullable=True)
    body_sha256 = Column(String(64), nullable=True)
    received_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)
