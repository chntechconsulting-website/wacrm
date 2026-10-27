from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class SalesTargetCreate(BaseModel):
    employee_id: int
    target_amount: float = Field(..., ge=0, description="Target amount in INR")
    period_type: str = Field("monthly", description="monthly, quarterly, yearly")
    period_month: Optional[int] = Field(None, ge=1, le=12, description="Month (1-12) for monthly targets")
    period_year: int = Field(..., ge=2020, le=2050, description="Year")

class SalesTargetUpdate(BaseModel):
    target_amount: float = Field(..., ge=0, description="Target amount in INR")

class SalesTargetOut(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    employee_department: Optional[str] = None
    target_amount: float
    period_type: str
    period_month: Optional[int] = None
    period_year: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EmployeeAchievementRow(BaseModel):
    employee_id: int
    employee_name: str
    department: Optional[str] = None
    assigned_target: float
    actual_revenue: float
    remaining_target: float
    achievement_percentage: float
    confirmed_invoices_count: int

class EmployeeMyTargetSummary(BaseModel):
    has_target: bool
    employee_id: int
    employee_name: str
    period_type: str
    period_month: Optional[int] = None
    period_year: int
    assigned_target: float
    actual_revenue: float
    remaining_target: float
    achievement_percentage: float
    confirmed_invoices_count: int

class CompanyRevenueItem(BaseModel):
    invoice_id: int
    invoice_number: str
    invoice_date: Optional[str] = None
    status: str
    payment_status: str
    subtotal: float
    tax_total: float
    grand_total: float
    amount_paid: float
    salesperson_name: str
    doc_type: str

class CompanyRevenueSummary(BaseModel):
    customer_id: int
    company_name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    total_confirmed_revenue: float
    total_collected_revenue: float
    invoices_count: int
    invoices: List[CompanyRevenueItem] = []
