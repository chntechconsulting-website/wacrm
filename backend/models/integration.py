from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from datetime import datetime
from database import Base

class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id = Column(Integer, primary_key=True, index=True)
    integration_type = Column(String(50), unique=True, index=True, nullable=False) # META, WHATSAPP, IVR, WEBSITE
    status = Column(String(30), default="NOT_CONNECTED", nullable=False)            # NOT_CONNECTED, CONNECTED, ERROR, DISCONNECTED, TESTING
    config_data = Column(Text, nullable=True)                                      # Encrypted or JSON string config data
    last_tested_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class IntegrationLog(Base):
    __tablename__ = "integration_logs"

    id = Column(Integer, primary_key=True, index=True)
    integration_type = Column(String(50), index=True, nullable=False)              # META, WHATSAPP, IVR, WEBSITE
    event_type = Column(String(50), index=True, nullable=False)                    # TEST_CONNECTION, WEBHOOK_RECEIVED, LEAD_INGESTED, OUTBOUND_MESSAGE, ERROR
    status = Column(String(20), nullable=False)                                     # SUCCESS, ERROR, WARNING, INFO
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
