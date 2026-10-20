from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    phone = Column(String(30), nullable=False, index=True)
    contact_name = Column(String(100), nullable=True)
    assigned_to = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    
    unread_count = Column(Integer, default=0, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    
    last_message_text = Column(Text, nullable=True)
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    lead = relationship("Lead", backref="conversations")
    assigned_employee = relationship("Employee", foreign_keys=[assigned_to])
    messages = relationship("WhatsAppMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="WhatsAppMessage.created_at.asc()")

class WhatsAppMessage(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    sender_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    
    direction = Column(String(20), nullable=False, index=True)  # INBOUND, OUTBOUND
    message_type = Column(String(30), nullable=False, default="TEXT") # TEXT, IMAGE, DOCUMENT, TEMPLATE
    
    body = Column(Text, nullable=True)
    media_url = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    template_name = Column(String(100), nullable=True)
    
    provider_message_id = Column(String(100), unique=True, index=True, nullable=True)
    status = Column(String(30), nullable=False, default="SENT", index=True) # SENT, DELIVERED, READ, FAILED
    
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    conversation = relationship("Conversation", back_populates="messages")
    lead = relationship("Lead", backref="whatsapp_messages")
    sender_employee = relationship("Employee", foreign_keys=[sender_employee_id])
