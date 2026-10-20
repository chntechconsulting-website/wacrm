from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel

class FinanceHandoffOut(BaseModel):
    id: int
    lead_id: int
    customer_id: int
    quotation_id: Optional[int] = None
    quotation_number: Optional[str] = None
    quotation_url: Optional[str] = None
    customer_name: str
    company_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    
    sales_employee_id: Optional[int] = None
    sales_employee_name: Optional[str] = None
    
    products_services: Optional[Any] = None
    final_amount: float
    paid_amount: float
    
    proforma_id: Optional[int] = None
    proforma_number: Optional[str] = None
    selected_bundle: Optional[str] = None
    product_category: Optional[str] = None
    licence_count: Optional[int] = None
    addons_summary: Optional[Any] = None
    biometric_device_count: Optional[int] = 0
    deal_adjustment_reason: Optional[str] = None

    status: str
    payment_status: str
    payment_mode: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_url: Optional[str] = None
    payment_date: Optional[datetime] = None
    customer_requirements: Optional[str] = None
    
    # Sensitive Finance fields (Omitted for non-Finance roles)
    bank_reference: Optional[str] = None
    bank_name: Optional[str] = None
    internal_finance_notes: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SupportHandoffOut(BaseModel):
    """
    Support View: strictly scoped to onboarding requirements.
    DOES NOT expose bank references, payment credentials, or internal finance notes.
    """
    id: int
    finance_handoff_id: Optional[int] = None
    lead_id: int
    deal_id: Optional[int] = None
    customer_id: int
    customer_name: str
    company_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    
    product_service: Optional[str] = None
    customer_users_count: Optional[int] = 1
    total_deal_amount: Optional[float] = 0.0
    purchased_products: Optional[Any] = None
    quotation_number: Optional[str] = None
    quotation_url: Optional[str] = None
    invoice_number: Optional[str] = None
    
    proforma_id: Optional[int] = None
    proforma_number: Optional[str] = None
    selected_bundle: Optional[str] = None
    product_category: Optional[str] = None
    addons_summary: Optional[Any] = None
    biometric_device_count: Optional[int] = 0
    deal_adjustment_reason: Optional[str] = None

    paid_amount: float
    payment_status: str
    payment_date: Optional[datetime] = None
    
    sales_employee_id: Optional[int] = None
    sales_employee_name: Optional[str] = None
    customer_requirements: Optional[str] = None
    
    support_manager_id: Optional[int] = None
    support_manager_name: Optional[str] = None
    won_at: Optional[datetime] = None
    
    onboarding_status: str
    assigned_agent_id: Optional[int] = None
    assigned_agent_name: Optional[str] = None
    support_notes: Optional[str] = None
    
    contacted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class WorkflowTimelineEventOut(BaseModel):
    id: int
    lead_id: int
    customer_id: Optional[int] = None
    stage: str
    previous_status: Optional[str] = None
    new_status: str
    performed_by_id: Optional[int] = None
    performed_by_name: Optional[str] = None
    role: Optional[str] = None
    title: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True

class FinancePaymentConfirmRequest(BaseModel):
    paid_amount: Optional[float] = None
    payment_mode: Optional[str] = "Bank Transfer"
    invoice_number: Optional[str] = None
    invoice_url: Optional[str] = None
    bank_reference: Optional[str] = None
    bank_name: Optional[str] = None
    internal_finance_notes: Optional[str] = None
    payment_credentials: Optional[str] = None

class SupportStatusUpdateRequest(BaseModel):
    onboarding_status: Optional[str] = None
    assigned_agent_id: Optional[int] = None
    support_notes: Optional[str] = None

class SupportManagerOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    name: str
    username: str
    email: Optional[str] = None
    role: str

    class Config:
        from_attributes = True

class DealWonRequest(BaseModel):
    support_manager_id: Optional[int] = None
    proforma_id: Optional[int] = None
    proforma_number: Optional[str] = None
    product_service: Optional[str] = None
    selected_bundle: Optional[str] = None
    product_category: Optional[str] = None
    customer_users_count: Optional[int] = 1
    total_deal_amount: Optional[float] = None
    payment_status: Optional[str] = "PAYMENT_PENDING"
    payment_amount: Optional[float] = None
    quotation_number: Optional[str] = None
    customer_requirements: Optional[str] = None
    purchased_products: Optional[List[Dict[str, Any]]] = None
    addons_summary: Optional[List[Dict[str, Any]]] = None
    biometric_device_count: Optional[int] = 0
    deal_adjustment_reason: Optional[str] = None

class SupportReassignRequest(BaseModel):
    support_manager_id: int
