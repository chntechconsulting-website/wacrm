from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class MetaPage(Base):
    __tablename__ = "meta_pages"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(String(100), unique=True, index=True, nullable=False)
    page_name = Column(String(255), nullable=False)
    encrypted_access_token = Column(Text, nullable=False)
    status = Column(String(50), default="CONNECTED", nullable=False)  # CONNECTED, DISCONNECTED, ERROR, TOKEN_EXPIRED, ACCESS_REMOVED
    category = Column(String(100), nullable=True)
    lead_count = Column(Integer, default=0, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    last_webhook_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # --- Additive OAuth / asset discovery fields -----------------------------
    connection_id = Column(Integer, ForeignKey("meta_connections.id"), nullable=True, index=True)
    page_picture_url = Column(String(500), nullable=True)
    instagram_account_id = Column(String(100), nullable=True, index=True)
    instagram_username = Column(String(255), nullable=True)
    is_selected = Column(Boolean, default=True, nullable=False)
    auto_sync_enabled = Column(Boolean, default=True, nullable=False)
    webhook_subscribed = Column(Boolean, default=False, nullable=False)
    token_expires_at = Column(DateTime, nullable=True)
    forms_last_synced_at = Column(DateTime, nullable=True)
    last_lead_at = Column(DateTime, nullable=True)
    last_error_code = Column(String(50), nullable=True)

    connection = relationship("MetaConnection", back_populates="pages")
