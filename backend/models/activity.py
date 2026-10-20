from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    performed_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    activity_type = Column(String(50), nullable=False)  # CREATED, ASSIGNED, ASSIGNMENT_CHANGED, STATUS_CHANGED, NOTE_ADDED, FOLLOW_UP_CREATED, CONVERTED, LOST, CALL, FOLLOWUP, WHATSAPP
    related_entity_type = Column(String(50), nullable=True)  # LEAD, CUSTOMER, CALL, FOLLOWUP, WHATSAPP, EMPLOYEE
    related_entity_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead", back_populates="activities", foreign_keys=[lead_id])
    customer = relationship("Customer", foreign_keys=[customer_id])
    employee = relationship("Employee", foreign_keys=[employee_id])
    performed_by_employee = relationship("Employee", foreign_keys=[performed_by])

    def to_dict(self):
        emp_name = None
        if self.performed_by_employee:
            emp_name = self.performed_by_employee.name
        elif self.employee:
            emp_name = self.employee.name

        lead_name_str = None
        if self.lead:
            lead_name_str = self.lead.name

        return {
            "activity_id": self.id,
            "id": self.id,
            "activity_type": self.activity_type,
            "lead_id": self.lead_id,
            "customer_id": self.customer_id,
            "employee_id": self.employee_id or self.performed_by,
            "created_by": self.performed_by,
            "created_by_name": emp_name,
            "lead_name": lead_name_str,
            "related_entity_type": self.related_entity_type or ("LEAD" if self.lead_id else "CUSTOMER" if self.customer_id else "EMPLOYEE" if self.employee_id else "SYSTEM"),
            "related_entity_id": self.related_entity_id or self.lead_id or self.customer_id or self.employee_id,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
