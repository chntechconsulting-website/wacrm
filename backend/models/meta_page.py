from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from database import Base

class MetaPage(Base):
    __tablename__ = "meta_pages"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(String(100), unique=True, index=True, nullable=False)
    page_name = Column(String(255), nullable=False)
    encrypted_access_token = Column(Text, nullable=False)
    status = Column(String(50), default="CONNECTED", nullable=False)  # CONNECTED, DISCONNECTED, ERROR
    category = Column(String(100), nullable=True)
    lead_count = Column(Integer, default=0, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    last_webhook_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
