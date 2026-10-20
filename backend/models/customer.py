from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(150), nullable=False)
    contact_name = Column(String(100), nullable=False)
    phone = Column(String(30), nullable=False)
    email = Column(String(100), nullable=True)
    location = Column(String(100), nullable=True)
    external_client_id = Column(String(100), nullable=True) # Mapped client ID in destination ERP
    destination_synced_at = Column(DateTime, nullable=True)
    converted_from_lead = Column(Integer, ForeignKey("leads.id"), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead", back_populates="customer")
