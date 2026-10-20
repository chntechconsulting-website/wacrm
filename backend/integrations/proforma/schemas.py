from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, EmailStr


class BillingAddressSchema(BaseModel):
    line1: Optional[str] = Field(default="Address on file", description="Street address line 1")
    line2: Optional[str] = Field(default=None, description="Street address line 2 or landmark")
    city: Optional[str] = Field(default="Chennai", description="City / District")
    state: Optional[str] = Field(default="Tamil Nadu", description="State name")
    stateCode: Optional[str] = Field(default="33", description="2-digit GST state code (e.g. 33 for Tamil Nadu)")
    pincode: Optional[str] = Field(default="600001", description="6-digit postal code")
    country: Optional[str] = Field(default="India", description="Country")


class LineItemSchema(BaseModel):
    id: Optional[str] = Field(default=None, description="Optional external line item identifier")
    name: Optional[str] = Field(default=None, description="Product / Service bundle name")
    description: Optional[str] = Field(default="Product / Service item", description="Full item description")
    hsn: Optional[str] = Field(default="998314", description="HSN/SAC code (e.g. 998314 for software, 85437099 for biometric)")
    qty: float = Field(default=1.0, gt=0, description="Quantity (must be greater than 0)")
    rate: float = Field(default=0.0, ge=0, description="Unit price / rate excluding tax")
    discount: float = Field(default=0.0, ge=0, description="Line discount amount")
    gstRate: float = Field(default=0.18, ge=0, description="GST rate as decimal (e.g. 0.18 for 18%) or integer percentage (18)")
    amount: Optional[float] = Field(default=None, description="Calculated line taxable amount ((qty * rate) - discount)")
    total: Optional[float] = Field(default=None, description="Calculated line total including GST")


class TaxBreakdownSchema(BaseModel):
    cgst: float = Field(default=0.0, description="Central GST amount")
    sgst: float = Field(default=0.0, description="State GST amount")
    igst: float = Field(default=0.0, description="Integrated GST amount (for inter-state supply)")
    totalTax: float = Field(default=0.0, description="Total GST amount")


class ProformaIntegrationPayload(BaseModel):
    # Customer / Client Identifiers
    customerId: Optional[Union[int, str]] = Field(default=None, description="Authoritative CRM customer ID if known")
    customer_id: Optional[Union[int, str]] = Field(default=None, description="Alias for customerId")
    companyName: Optional[str] = Field(default=None, description="Client legal or trade entity name")
    company_name: Optional[str] = Field(default=None, description="Alias for companyName")
    contactPerson: Optional[str] = Field(default=None, description="Primary contact person name")
    contact_person: Optional[str] = Field(default=None, description="Alias for contactPerson")
    customerName: Optional[str] = Field(default=None, description="Alternative contact name")
    customer_name: Optional[str] = Field(default=None, description="Alias for customerName")
    email: Optional[str] = Field(default=None, description="Contact email address for invoice delivery")
    phone: Optional[str] = Field(default=None, description="Contact phone number with area/country code")
    billingAddress: Optional[Union[BillingAddressSchema, Dict[str, Any], str]] = Field(default=None, description="Billing address details")
    address: Optional[Union[BillingAddressSchema, Dict[str, Any], str]] = Field(default=None, description="Alias for billingAddress")
    gstin: Optional[str] = Field(default=None, description="15-character GSTIN identifier")

    # Document & Reference Identifiers
    quotationId: Optional[Union[int, str]] = Field(default=None, description="Source quotation ID in CRM")
    quotation_id: Optional[Union[int, str]] = Field(default=None, description="Alias for quotationId")
    quotationNumber: Optional[str] = Field(default=None, description="Source quotation number (e.g. QT-2026-0015)")
    quotation_number: Optional[str] = Field(default=None, description="Alias for quotationNumber")
    proformaId: Optional[Union[int, str]] = Field(default=None, description="Authoritative proforma ID in CRM if querying/verifying")
    proforma_id: Optional[Union[int, str]] = Field(default=None, description="Alias for proformaId")
    proformaNumber: Optional[str] = Field(default=None, description="Proforma invoice document number (e.g. PI-2026-0042)")
    proforma_number: Optional[str] = Field(default=None, description="Alias for proformaNumber")
    issueDate: Optional[Union[int, str]] = Field(default=None, description="Issue date in epoch ms or ISO-8601 string")
    issue_date: Optional[Union[int, str]] = Field(default=None, description="Alias for issueDate")
    dueDate: Optional[Union[int, str]] = Field(default=None, description="Due date in epoch ms or ISO-8601 string")
    due_date: Optional[Union[int, str]] = Field(default=None, description="Alias for dueDate")
    productCategory: Optional[str] = Field(default="wahrms", description="Product category: 'wahrms' or 'biometric'")
    product_category: Optional[str] = Field(default=None, description="Alias for productCategory")
    selectedBundle: Optional[str] = Field(default=None, description="Configured bundle: 'hr_atm', 'hr_payroll', or 'hr_atm_payroll'")

    # Line Items
    lineItems: List[LineItemSchema] = Field(default=[], description="Array of purchased software/hardware line items")
    line_items: Optional[List[LineItemSchema]] = Field(default=None, description="Alias for lineItems")

    # Financials (Client provided figures - will be authoritatively validated)
    subtotal: Optional[float] = Field(default=None, description="Taxable subtotal before taxes")
    taxBreakdown: Optional[Union[TaxBreakdownSchema, Dict[str, Any]]] = Field(default=None, description="Tax breakdown structure")
    grandTotal: Optional[float] = Field(default=None, description="Grand total inclusive of GST")
    grand_total: Optional[float] = Field(default=None, description="Alias for grandTotal")

    # Terms & Meta
    termsAndConditions: Optional[str] = Field(default=None, description="Commercial and legal terms for this proforma")
    terms_and_conditions: Optional[str] = Field(default=None, description="Alias for termsAndConditions")
    pdfUrl: Optional[str] = Field(default=None, description="Secure PDF document URL if already rendered")
    pdf_url: Optional[str] = Field(default=None, description="Alias for pdfUrl")
    notes: Optional[str] = Field(default=None, description="Internal integration notes or external reference notes")

    # Idempotency & Request Tracking
    idempotencyKey: Optional[str] = Field(default=None, description="Unique client request ID to prevent duplicate document creation")
    idempotency_key: Optional[str] = Field(default=None, description="Alias for idempotencyKey")
    requestId: Optional[str] = Field(default=None, description="External tracking or webhook event ID")
    request_id: Optional[str] = Field(default=None, description="Alias for requestId")

    class Config:
        json_schema_extra = {
            "example": {
                "idempotencyKey": "idem_req_20261017_9921",
                "customerId": 101,
                "companyName": "Acme Global Solutions Pvt Ltd",
                "contactPerson": "Rajesh Kumar",
                "email": "billing@acmeglobal.com",
                "phone": "+91 9876543210",
                "gstin": "33AAAAA1234A1Z5",
                "billingAddress": {
                    "line1": "Level 4, Tidel Park, Rajiv Gandhi Salai",
                    "city": "Chennai",
                    "state": "Tamil Nadu",
                    "stateCode": "33",
                    "pincode": "600113",
                    "country": "India"
                },
                "quotationNumber": "QT-2026-0012",
                "proformaNumber": "PI-2026-0042",
                "productCategory": "wahrms",
                "selectedBundle": "hr_payroll",
                "lineItems": [
                    {
                        "name": "WAHRMS Core HR + Payroll Cloud Suite",
                        "description": "Annual subscription for 50 employees including statutory compliance & payroll processing",
                        "hsn": "998314",
                        "qty": 1,
                        "rate": 75000.00,
                        "discount": 0.00,
                        "gstRate": 0.18
                    }
                ],
                "subtotal": 75000.00,
                "grandTotal": 88500.00,
                "termsAndConditions": "1. Software onboarding commences upon payment receipt.\n2. Prices subject to 18% GST."
            }
        }


class AuthoritativeFinancialSummary(BaseModel):
    taxableSubtotal: float = Field(..., description="Server-verified taxable subtotal")
    taxMode: str = Field(..., description="'intra' (CGST+SGST) or 'inter' (IGST)")
    cgst: float = Field(..., description="Server-verified Central GST amount")
    sgst: float = Field(..., description="Server-verified State GST amount")
    igst: float = Field(..., description="Server-verified Integrated GST amount")
    totalTax: float = Field(..., description="Server-verified total tax amount")
    roundOff: float = Field(default=0.0, description="Round off adjustment")
    grandTotal: float = Field(..., description="Authoritative verified grand total payable")
    lineItemsCount: int = Field(..., description="Number of validated line items")


class ProformaIntegrationResponse(BaseModel):
    success: bool = Field(..., description="Indicates whether the integration request completed successfully")
    requestId: str = Field(..., description="Server or caller tracking request ID")
    idempotencyKey: Optional[str] = Field(default=None, description="Echoed idempotency key")
    processingStatus: str = Field(..., description="Status: 'AUTHORITATIVE_VERIFIED', 'CREATED', 'ALREADY_PROCESSED', or 'SYNCHRONIZED'")
    customerId: Optional[int] = Field(default=None, description="Authoritative CRM customer ID")
    customerName: Optional[str] = Field(default=None, description="Client / Contact Name")
    companyName: Optional[str] = Field(default=None, description="Company Name")
    proformaId: int = Field(..., description="Authoritative CRM Proforma document ID")
    proformaNumber: str = Field(..., description="Authoritative Proforma document number (e.g. PI-2026-0042)")
    quotationNumber: Optional[str] = Field(default=None, description="Linked quotation number if present")
    authoritativeSummary: AuthoritativeFinancialSummary = Field(..., description="Authoritative financial breakdown computed by CRM")
    pdfDownloadUrl: Optional[str] = Field(default=None, description="Secure CRM endpoint to download generated PDF")
    syncedAt: str = Field(..., description="ISO-8601 UTC timestamp of synchronization")
    message: str = Field(..., description="Human-readable processing message")
    warnings: Optional[List[str]] = Field(default=None, description="Any discrepancies or non-blocking warnings detected")
