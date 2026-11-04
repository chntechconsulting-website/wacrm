"""
Meta Click-to-WhatsApp (CTWA) ad lead attribution models.

These tables are an additive attribution/event layer on top of the existing
Lead / LeadEnquiry tables. They never replace or duplicate the lead system:
every WhatsApp Ad enquiry is still a normal Lead (source = WHATSAPP_ADS), and
one attribution row stores the ad click / referral details for that enquiry.

Keeping attribution separate means:
  * existing lead listing, assignment, permissions and reporting keep working,
  * one lead can have multiple ad enquiries (re-inquiry) with different ads,
  * raw Meta referral payloads can be retained for auditing and later
    Marketing API campaign/ad name resolution.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base
from utils.timezone import get_ist_now


class WhatsAppAdAttribution(Base):
    """One Click-to-WhatsApp ad enquiry, linked to exactly one lead enquiry."""

    __tablename__ = "whatsapp_ad_attributions"

    id = Column(Integer, primary_key=True, index=True)

    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_enquiry_id = Column(
        Integer,
        ForeignKey("lead_enquiries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Meta message identity
    wamid = Column(String(191), unique=True, index=True, nullable=True)
    phone = Column(String(30), nullable=False, index=True)
    contact_name = Column(String(150), nullable=True)
    message_text = Column(Text, nullable=True)
    message_type = Column(String(40), nullable=True)
    message_timestamp = Column(DateTime, nullable=True, index=True)

    # Channel classification is always WhatsApp; the Meta referral's own
    # source_type (usually "ad") is kept separately below.
    channel = Column(String(30), default="WHATSAPP", nullable=False, index=True)
    business_account_id = Column(String(100), nullable=True, index=True)
    phone_number_id = Column(String(100), nullable=True, index=True)

    # Referral / click attribution
    ctwa_clid = Column(String(191), unique=True, index=True, nullable=True)
    source_type = Column(String(50), nullable=True)
    source_id = Column(String(191), nullable=True, index=True)  # Meta ad ID
    source_url = Column(String(500), nullable=True)
    headline = Column(String(500), nullable=True)
    ad_body = Column(Text, nullable=True)
    media_type = Column(String(50), nullable=True)
    media_url = Column(String(1000), nullable=True)
    welcome_message = Column(Text, nullable=True)

    # Resolved later through the Marketing API (ads_read permission)
    campaign_id = Column(String(191), nullable=True, index=True)
    campaign_name = Column(String(255), nullable=True)
    ad_name = Column(String(255), nullable=True)
    resolution_status = Column(
        String(30), default="PENDING", nullable=False, index=True
    )  # PENDING, RESOLVED, FAILED, SKIPPED
    resolution_error = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Exact Meta referral object for audit / future-field compatibility
    raw_referral = Column(Text, nullable=True)

    created_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)
    updated_at = Column(
        DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False
    )

    lead = relationship("Lead", foreign_keys=[lead_id])
    lead_enquiry = relationship("LeadEnquiry", foreign_keys=[lead_enquiry_id])


class WhatsAppWebhookEvent(Base):
    """Idempotency + audit log for every inbound WhatsApp webhook event."""

    __tablename__ = "whatsapp_webhook_events"

    id = Column(Integer, primary_key=True, index=True)

    # Stable key (wamid where available, otherwise a deterministic hash)
    event_key = Column(String(191), unique=True, index=True, nullable=False)
    event_type = Column(String(30), default="MESSAGE", nullable=False, index=True)
    wamid = Column(String(191), nullable=True, index=True)
    phone_number_id = Column(String(100), nullable=True, index=True)
    business_account_id = Column(String(100), nullable=True, index=True)
    sender_phone = Column(String(30), nullable=True, index=True)

    status = Column(
        String(30), default="RECEIVED", nullable=False, index=True
    )  # RECEIVED, PROCESSED, SKIPPED, SKIPPED_DUPLICATE, FAILED
    lead_id = Column(
        Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    attribution_id = Column(
        Integer,
        ForeignKey("whatsapp_ad_attributions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error = Column(Text, nullable=True)
    payload = Column(Text, nullable=True)

    received_at = Column(DateTime, default=get_ist_now, nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)
