"""Models for WhatsApp Business App coexistence (Embedded Signup onboarding).

These tables are additive. They do not modify or disconnect any existing
WhatsApp Business App number. A connection row is only created after a business
explicitly completes Meta Embedded Signup.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class WhatsAppCoexistenceConnection(Base):
    __tablename__ = "whatsapp_coexistence_connections"

    id = Column(Integer, primary_key=True, index=True)

    # Meta asset identifiers returned by Embedded Signup session logging.
    waba_id = Column(String(64), unique=True, index=True, nullable=False)
    phone_number_id = Column(String(64), unique=True, index=True, nullable=False)
    business_id = Column(String(64), nullable=True)

    display_phone_number = Column(String(32), nullable=True)
    verified_name = Column(String(255), nullable=True)
    quality_rating = Column(String(32), nullable=True)

    # PENDING -> CONNECTED -> SYNCING -> SYNC_COMPLETE
    # DISCONNECTED / ERROR are terminal until the business re-onboards.
    status = Column(String(32), default="PENDING", nullable=False, index=True)
    onboarding_status = Column(
        String(32), default="PENDING", nullable=False
    )  # PENDING, EXCHANGED, SUBSCRIBED, SYNC_REQUESTED, COMPLETE, FAILED

    # Business integration system user token. Always encrypted at rest and
    # never returned by an API response.
    encrypted_access_token = Column(Text, nullable=False)
    token_obtained_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    is_on_biz_app = Column(Boolean, nullable=True)
    platform_type = Column(String(32), nullable=True)
    webhook_subscribed = Column(Boolean, default=False, nullable=False)
    webhook_fields = Column(Text, nullable=True)  # JSON list of expected fields

    contacts_sync_requested_at = Column(DateTime, nullable=True)
    contacts_sync_request_id = Column(String(100), nullable=True)
    history_sync_requested_at = Column(DateTime, nullable=True)
    history_sync_request_id = Column(String(100), nullable=True)
    sync_deadline_at = Column(DateTime, nullable=True)

    history_progress = Column(Integer, default=0, nullable=False)
    history_phase = Column(Integer, nullable=True)
    messages_synced = Column(Integer, default=0, nullable=False)
    contacts_synced = Column(Integer, default=0, nullable=False)

    last_webhook_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)

    onboarded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    events = relationship(
        "WhatsAppCoexistenceEvent",
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    contacts = relationship(
        "WhatsAppSmbContact",
        back_populates="connection",
        cascade="all, delete-orphan",
    )


class WhatsAppCoexistenceEvent(Base):
    """Idempotency + audit trail for session logs and webhook deliveries.

    Raw payloads are only stored for Embedded Signup session logs. Message
    payloads are already persisted in the existing ``messages`` table, so
    storing them again here would duplicate customer data.
    """

    __tablename__ = "whatsapp_coexistence_events"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(
        Integer,
        ForeignKey("whatsapp_coexistence_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type = Column(String(64), nullable=False, index=True)
    event_key = Column(String(255), unique=True, index=True, nullable=False)
    status = Column(String(32), default="RECEIVED", nullable=False, index=True)
    detail = Column(Text, nullable=True)
    payload = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    connection = relationship(
        "WhatsAppCoexistenceConnection", back_populates="events"
    )


class WhatsAppSmbContact(Base):
    """Contacts synchronized from the business's WhatsApp Business App.

    Contacts are stored separately from CRM leads on purpose. Syncing a phone
    address book must never create or overwrite sales leads.
    """

    __tablename__ = "whatsapp_smb_contacts"
    __table_args__ = (
        UniqueConstraint(
            "connection_id", "phone_number", name="uq_whatsapp_smb_contact"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(
        Integer,
        ForeignKey("whatsapp_coexistence_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    phone_number = Column(String(32), nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_action = Column(String(20), default="add", nullable=False)
    last_synced_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    connection = relationship(
        "WhatsAppCoexistenceConnection", back_populates="contacts"
    )
