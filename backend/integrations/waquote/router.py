import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from pydantic import BaseModel

from database import get_db
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.customer import Customer
from models.activity import LeadActivity
from models.quotation import Quotation, WAHRMSBundle
from models.audit_log import AuditLog
from services.auth import get_current_user, require_roles
from services.permission_service import (
    is_finance_or_admin, 
    is_finance_team,
    user_has_permission,
    apply_billing_scope_filter,
    is_user_authorized_for_billing_doc
)
from services.hierarchy_service import (
    normalize_role,
    get_team_employee_ids_from_user,
    get_team_user_ids,
    ROLE_ADMIN,
    ROLE_SALES_MANAGER,
    ROLE_SALES_EXECUTIVE,
    ROLE_SUPPORT_MANAGER,
    ROLE_SUPPORT_EXECUTIVE
)

logger = logging.getLogger("waquote_router")

router = APIRouter(prefix="/integrations/waquote", tags=["WA Quote ERP Integration"])

class LineItemInput(BaseModel):
    description: str
    hsn: Optional[str] = ""
    qty: float = 1.0
    rate: float = 0.0
    gstRate: float = 0.18
    discount: float = 0.0
    amount: Optional[float] = 0.0

class CreateDocumentRequest(BaseModel):
    doc_type: str = "quotation" # quotation, proforma, invoice, po
    selected_bundle: Optional[str] = None # hr_atm, hr_payroll, hr_atm_payroll, bio_standard...
    product_category: Optional[str] = "wahrms" # wahrms, biometric
    allow_duplicate: Optional[bool] = False
    doc_number: Optional[str] = None
    status: str = "issued"
    payment_status: str = "unpaid"
    
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    source_quotation_id: Optional[int] = None
    source_quotation_number: Optional[str] = None

    
    customer_name: str
    company_name: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    address: Optional[str] = ""
    state: Optional[str] = "Tamil Nadu"
    state_code: Optional[str] = "33"
    gstin: Optional[str] = ""
    
    tax_mode: Optional[str] = "intra"
    subtotal: float = 0.0
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0
    tax_total: float = 0.0
    round_off: float = 0.0
    grand_total: float = 0.0
    amount_paid: float = 0.0
    
    line_items: List[Dict[str, Any]] = []
    terms_and_conditions: Optional[str] = ""
    notes: Optional[str] = ""
    prepared_by: Optional[str] = ""
    pdf_url: Optional[str] = ""
    company_id: Optional[str] = "wahrms"
    company: Optional[Dict[str, Any]] = None

@router.post("/test")
def test_waquote_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    """
    Test native CRM Quotations Engine.
    """
    count = db.query(Quotation).count()
    return {
        "success": True,
        "message": f"Connected to native CRM Quotes engine. {count} billing documents in database.",
        "error_details": None
    }

DEFAULT_WAHRMS_BUNDLES = [
    {
        "bundle_code": "hr_atm",
        "name": "HR + ATM",
        "tagline": "Core HR with attendance & time.",
        "description": "Integrated employee directory, leave management, and real-time biometric attendance capture.",
        "badge": None,
        "features": [
            "Core HR & Employee Directory",
            "Attendance & Time Tracking",
            "Leave & Holiday Management",
            "Biometric Device Integration"
        ],
        "items": [
            {
                "item_code": "HR_ATM_SUB",
                "name": "WAHRMS HR + Attendance Subscription",
                "description": "WAHRMS HR + Attendance Subscription",
                "hsn": "998314",
                "qty": 120,
                "rate": 45.0,
                "gstRate": 0.18,
                "discount": 0.0
            },
            {
                "item_code": "BIO_INTEGRATION",
                "name": "Biometric Integration",
                "description": "Biometric Integration",
                "hsn": "998314",
                "qty": 1,
                "rate": 4999.0,
                "gstRate": 0.18,
                "discount": 0.0
            }
        ],
        "sort_order": 1,
        "is_active": 1
    },
    {
        "bundle_code": "hr_atm_payroll",
        "name": "HR + ATM + Payroll",
        "tagline": "The full suite.",
        "description": "The complete all-in-one workforce powerhouse: Core HR, biometric attendance, statutory payroll, and self-service.",
        "badge": "Full Suite • Best Value",
        "features": [
            "Core HR & Lifecycle Management",
            "Biometric Attendance Sync",
            "Statutory Payroll & Compliance Engine",
            "One-Click Payslips & Direct Bank Advice"
        ],
        "items": [
            {
                "item_code": "HR_ATM_PAYROLL_SUB",
                "name": "WAHRMS Complete Suite (HR + ATM + Payroll) Subscription",
                "description": "WAHRMS Complete Suite (HR + ATM + Payroll) Subscription",
                "hsn": "998314",
                "qty": 120,
                "rate": 65.0,
                "gstRate": 0.18,
                "discount": 0.0
            },
            {
                "item_code": "BIO_PAYROLL_PACKAGE",
                "name": "bio & payroll Integrated Package",
                "description": "bio & payroll Integrated Package",
                "hsn": "85437099",
                "qty": 1,
                "rate": 24500.0,
                "gstRate": 0.18,
                "discount": 0.0
            }
        ],
        "sort_order": 2,
        "is_active": 1
    },
    {
        "bundle_code": "hr_payroll",
        "name": "HR + Payroll",
        "tagline": "Core HR with payroll & statutory.",
        "description": "Comprehensive employee records paired with full salary computation, payslips, PF, ESI, TDS, and statutory compliance.",
        "badge": None,
        "features": [
            "Core HR & Employee Profiles",
            "Statutory Payroll Engine",
            "PF, ESI, PT & TDS Filings",
            "One-Click Payslips & Direct Bank Advice"
        ],
        "items": [
            {
                "item_code": "HR_PAYROLL_SUB",
                "name": "WAHRMS HR + Payroll Cloud Subscription",
                "description": "WAHRMS HR + Payroll Cloud Subscription",
                "hsn": "998314",
                "qty": 120,
                "rate": 50.0,
                "gstRate": 0.18,
                "discount": 0.0
            },
            {
                "item_code": "PAYROLL_SETUP",
                "name": "WA Payroll Cloud Setup & Deployment",
                "description": "WA Payroll Cloud Setup & Deployment",
                "hsn": "998315",
                "qty": 1,
                "rate": 5000.0,
                "gstRate": 0.18,
                "discount": 0.0
            }
        ],
        "sort_order": 3,
        "is_active": 1
    }
]

DEFAULT_BIOMETRIC_BUNDLES = [
    {
        "bundle_code": "bio_standard",
        "category": "BIOMETRIC",
        "name": "Biometric Standard (MB160 Terminal)",
        "tagline": "Standalone facial & fingerprint terminal with cloud punch sync",
        "description": "Enterprise biometric terminal with face, fingerprint, and RFID recognition, bundled with 4G IoT SIM card, cloud synchronization bridge, and installation.",
        "badge": "Popular Hardware",
        "features": [
            "MB160 Face + Fingerprint + RFID Terminal",
            "1x 4G IoT SIM Card Included",
            "Hardware Protocol Bridge & Cloud Sync",
            "Standard Wall Mount & Power Brick",
            "Onsite Hardware Setup & Testing"
        ],
        "items": [
            {
                "name": "MB160 Biometric Device",
                "description": "MB160 Biometric Device",
                "hsn": "85437099",
                "rate": 22400.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18
            },
            {
                "name": "Hardware Cloud Sync Bridge",
                "description": "Hardware Cloud Sync Bridge",
                "hsn": "998314",
                "rate": 4999.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18
            },
            {
                "name": "Installation & Calibration",
                "description": "Installation & Calibration",
                "hsn": "998315",
                "rate": 1000.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18
            }
        ],
        "sort_order": 1,
        "is_active": 1
    },
    {
        "bundle_code": "bio_atm",
        "category": "BIOMETRIC",
        "name": "WA ATM Biometric Hardware",
        "tagline": "Cost-effective optical attendance machine for offices & retail",
        "description": "WA ATM biometric terminal designed for rapid shift attendance logging, cloud software integration, and effortless deployment.",
        "badge": "Cost Effective",
        "features": [
            "WA ATM Machine & Biometric Hardware",
            "Dual Face & Optical Fingerprint Sensor",
            "TCP/IP & Cloud Sync Ready",
            "Wall Mounting & Power Adapter Included",
            "Setup & Device Training Included"
        ],
        "items": [
            {
                "name": "WA ATM Machine Hardware",
                "description": "WA ATM Machine Hardware",
                "hsn": "85437099",
                "rate": 18500.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18
            },
            {
                "name": "Setup & Deployment",
                "description": "Setup & Deployment",
                "hsn": "998315",
                "rate": 1000.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18
            }
        ],
        "sort_order": 2,
        "is_active": 1
    },
    {
        "bundle_code": "bio_enterprise",
        "category": "BIOMETRIC",
        "name": "Biometric Multi-Location Suite",
        "tagline": "Dual terminal package for branch & multi-door deployments",
        "description": "Complete multi-location biometric setup with dual MB160 terminals, SIM cards, enterprise cloud integration bridge, and multi-device deployment.",
        "badge": "Multi-Door Enterprise",
        "features": [
            "2x MB160 Face + Fingerprint + RFID Terminals",
            "2x 4G IoT SIM Cards Included",
            "Multi-Branch Central Cloud Sync Bridge",
            "Centralized Punch Dashboard Setup",
            "Multi-Device Installation & Operator Training"
        ],
        "items": [
            {
                "name": "2x MB160 Biometric Terminals",
                "description": "2x MB160 Biometric Terminals",
                "hsn": "85437099",
                "rate": 44800.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18
            },
            {
                "name": "Multi-Location Cloud Bridge",
                "description": "Multi-Location Cloud Bridge",
                "hsn": "998314",
                "rate": 7500.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18
            },
            {
                "name": "Multi-Device Deployment",
                "description": "Multi-Device Deployment",
                "hsn": "998315",
                "rate": 2000.0,
                "qty": 1,
                "discount": 0.0,
                "gstRate": 0.18
            }
        ],
        "sort_order": 3,
        "is_active": 1
    }
]

@router.get("/bundles")

def get_wahrms_bundles(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches the manageable WAHRMS & Biometric product bundle master.
    Optional category filter: 'WAHRMS', 'BIOMETRIC', or 'all'.
    Seeds default configuration if not present.
    """
    try:
        q = db.query(WAHRMSBundle).filter(WAHRMSBundle.is_active == 1)
        if category and category.strip().lower() != "all":
            q = q.filter(WAHRMSBundle.category.ilike(category.strip()))
        bundles = q.order_by(WAHRMSBundle.sort_order).all()
        
        if not bundles and (not category or category.strip().lower() == "all" or category.strip().upper() == "WAHRMS"):
            # Seed default bundles
            for b_data in DEFAULT_WAHRMS_BUNDLES:
                new_b = WAHRMSBundle(**b_data)
                db.add(new_b)
            db.commit()
            q = db.query(WAHRMSBundle).filter(WAHRMSBundle.is_active == 1)
            if category and category.strip().lower() != "all":
                q = q.filter(WAHRMSBundle.category.ilike(category.strip()))
            bundles = q.order_by(WAHRMSBundle.sort_order).all()

        formatted = []
        for b in bundles:
            formatted.append({
                "id": b.id,
                "bundleCode": b.bundle_code,
                "category": getattr(b, "category", "WAHRMS") or "WAHRMS",
                "name": b.name,
                "tagline": b.tagline,
                "description": b.description,
                "badge": b.badge,
                "features": b.features or [],
                "items": b.items or [],
                "isActive": bool(b.is_active),
                "sortOrder": b.sort_order
            })
        return {
            "ok": True,
            "bundles": formatted
        }
    except Exception as e:
        logger.error(f"Error fetching product bundles: {e}")
        all_fallbacks = [
            {**b, "category": "WAHRMS"} for b in DEFAULT_WAHRMS_BUNDLES
        ]
        if category and category.strip().upper() == "BIOMETRIC":
            active_fallback = DEFAULT_BIOMETRIC_BUNDLES
        elif category and category.strip().upper() == "WAHRMS":
            active_fallback = all_fallbacks
        else:
            active_fallback = all_fallbacks + DEFAULT_BIOMETRIC_BUNDLES

        return {
            "ok": True,
            "fallback": True,
            "bundles": [
                {
                    "id": idx + 1,
                    "bundleCode": b["bundle_code"],
                    "category": b.get("category", "WAHRMS"),
                    "name": b["name"],
                    "tagline": b["tagline"],
                    "description": b["description"],
                    "badge": b["badge"],
                    "features": b["features"],
                    "items": b["items"],
                    "isActive": True,
                    "sortOrder": b["sort_order"]
                }
                for idx, b in enumerate(active_fallback)
            ]
        }


@router.post("/bundles")
def create_or_update_wahrms_bundle(
    bundle_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    """
    Manageable bundle master: Create or update a bundle configuration.
    """
    code = bundle_data.get("bundleCode") or bundle_data.get("bundle_code")
    if not code:
        raise HTTPException(status_code=400, detail="bundleCode is required.")
    
    b = db.query(WAHRMSBundle).filter(WAHRMSBundle.bundle_code == code).first()
    if not b:
        b = WAHRMSBundle(bundle_code=code)
        db.add(b)
    
    if "name" in bundle_data: b.name = bundle_data["name"]
    if "tagline" in bundle_data: b.tagline = bundle_data["tagline"]
    if "description" in bundle_data: b.description = bundle_data.get("description")
    if "badge" in bundle_data: b.badge = bundle_data.get("badge")
    if "features" in bundle_data: b.features = bundle_data.get("features", [])
    if "items" in bundle_data: b.items = bundle_data.get("items", [])
    if "sortOrder" in bundle_data: b.sort_order = int(bundle_data["sortOrder"])
    if "isActive" in bundle_data: b.is_active = 1 if bundle_data["isActive"] else 0
    b.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(b)
    return {
        "ok": True,
        "message": f"Bundle '{b.name}' saved successfully.",
        "bundle": {
            "id": b.id,
            "bundleCode": b.bundle_code,
            "name": b.name,
            "tagline": b.tagline,
            "items": b.items
        }
    }

@router.get("/summary")
def get_waquote_summary(
    company_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches real-time financial metrics and billing summaries directly from local database,
    strictly scoped to the authenticated user's role, department, and team authorization.
    Avoids double-counting when a quotation becomes a proforma or tax invoice.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        if not user_has_permission(current_user, "quotations", "view", db) and not user_has_permission(current_user, "invoices", "view", db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Support team cannot access Sales billing documents."
            )

    authorized_query = apply_billing_scope_filter(db.query(Quotation), current_user, db)
    local_docs = authorized_query.all()

    # Partition documents by type (excluding cancelled records)
    all_active_invoices = [d for d in local_docs if d.doc_type == "invoice" and d.status != "cancelled"]
    all_active_proformas = [d for d in local_docs if d.doc_type == "proforma" and d.status != "cancelled"]
    all_active_quotes = [d for d in local_docs if d.doc_type == "quotation" and d.status != "cancelled"]

    # Prevent double-counting: an active proforma is superseded if an active invoice references it
    superseded_proforma_ids = set()
    for inv in all_active_invoices:
        if inv.source_quotation_id:
            superseded_proforma_ids.add(inv.source_quotation_id)
        if inv.source_quotation_number:
            for pf in all_active_proformas:
                if pf.doc_number == inv.source_quotation_number:
                    superseded_proforma_ids.add(pf.id)

    # Billing pool consists of authoritative issued Tax Invoices and independent/pending Proformas
    billing_pool = list(all_active_invoices) + [pf for pf in all_active_proformas if pf.id not in superseded_proforma_ids]

    local_total_billed = sum(float(d.grand_total or 0.0) for d in billing_pool)
    local_paid = sum(float(d.amount_paid or (d.grand_total if d.payment_status == 'paid' else 0.0)) for d in billing_pool)
    local_unpaid = sum(max(0.0, float(d.grand_total or 0.0) - float(d.amount_paid or (d.grand_total if d.payment_status == 'paid' else 0.0))) for d in billing_pool)
    collection_rate = round((local_paid / local_total_billed * 100), 1) if local_total_billed > 0 else 0.0

    # Quotations summary (proposals/estimates - not counted as billed or collected payments)
    quotes_count = len(all_active_quotes)
    quotes_val = sum(float(d.grand_total or 0.0) for d in all_active_quotes)

    # Proformas summary
    proformas_count = len(all_active_proformas)
    proformas_val = sum(float(d.grand_total or 0.0) for d in all_active_proformas)
    proformas_unpaid_val = sum(max(0.0, float(d.grand_total or 0.0) - float(d.amount_paid or (d.grand_total if d.payment_status == 'paid' else 0.0))) for d in all_active_proformas)
    proformas_unpaid_count = sum(1 for d in all_active_proformas if float(d.grand_total or 0.0) > float(d.amount_paid or (d.grand_total if d.payment_status == 'paid' else 0.0)))

    # Invoices summary
    invoices_count = len(all_active_invoices)
    invoices_val = sum(float(d.grand_total or 0.0) for d in all_active_invoices)
    invoices_unpaid_val = sum(max(0.0, float(d.grand_total or 0.0) - float(d.amount_paid or (d.grand_total if d.payment_status == 'paid' else 0.0))) for d in all_active_invoices)
    invoices_unpaid_count = sum(1 for d in all_active_invoices if float(d.grand_total or 0.0) > float(d.amount_paid or (d.grand_total if d.payment_status == 'paid' else 0.0)))

    return {
        "ok": True,
        "metrics": {
            "financials": {
                "totalBilled": local_total_billed,
                "totalPaid": local_paid,
                "totalUnpaid": local_unpaid,
                "totalOutstanding": local_unpaid,
                "collectionRatePercent": collection_rate
            },
            "quotations": {
                "total": quotes_count,
                "totalCount": quotes_count,
                "totalAmount": quotes_val
            },
            "proformas": {
                "total": proformas_count,
                "totalCount": proformas_count,
                "totalAmount": proformas_val,
                "unpaid": {
                    "count": proformas_unpaid_count,
                    "amount": proformas_unpaid_val
                }
            },
            "invoices": {
                "total": invoices_count,
                "totalCount": invoices_count,
                "totalAmount": invoices_val,
                "unpaid": {
                    "count": invoices_unpaid_count,
                    "amount": invoices_unpaid_val
                }
            }
        }
    }

@router.get("/documents")
def list_waquote_documents(
    doc_type: Optional[str] = Query(None),
    docType: Optional[str] = Query(None),
    product_category: Optional[str] = Query(None),
    productCategory: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    customerId: Optional[int] = Query(None),
    lead_id: Optional[int] = Query(None),
    leadId: Optional[int] = Query(None),
    payment_status: Optional[str] = Query(None),
    paymentStatus: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search and list quotations, proformas, invoices, and POs directly from local CRM database,
    strictly filtered by authenticated role and department scope.
    """
    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        if not user_has_permission(current_user, "quotations", "view", db) and not user_has_permission(current_user, "invoices", "view", db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Support team cannot access Sales billing documents."
            )

    q = apply_billing_scope_filter(db.query(Quotation), current_user, db)

    def _clean_str(val):
        return val.strip().lower() if isinstance(val, str) else None

    # Resolve camelCase and snake_case query params uniformly
    doc_type_val = _clean_str(docType) or _clean_str(doc_type) or "all"
    cat_val = _clean_str(productCategory) or _clean_str(product_category) or "all"
    pay_val = _clean_str(paymentStatus) or _clean_str(payment_status) or "all"
    search_val = search.strip() if isinstance(search, str) else ""
    cust_id_val = customerId if isinstance(customerId, int) else (customer_id if isinstance(customer_id, int) else None)
    lead_id_val = leadId if isinstance(leadId, int) else (lead_id if isinstance(lead_id, int) else None)
    stat_val = _clean_str(status_filter) or "all"

    if doc_type_val and doc_type_val != "all":
        if doc_type_val in ["po", "purchase_order"]:
            q = q.filter(Quotation.doc_type.in_(["po", "purchase_order"]))
        else:
            q = q.filter(Quotation.doc_type == doc_type_val)

    if cat_val and cat_val != "all":
        if cat_val == "wahrms":
            q = q.filter(or_(Quotation.product_category == "wahrms", Quotation.product_category == None, Quotation.product_category == ""))
        else:
            q = q.filter(Quotation.product_category == cat_val)

    if cust_id_val:
        q = q.filter(Quotation.customer_id == cust_id_val)
    if lead_id_val:
        q = q.filter(Quotation.lead_id == lead_id_val)

    if pay_val and pay_val != "all":
        if pay_val == "unpaid":
            q = q.filter(or_(Quotation.payment_status == None, Quotation.payment_status == "", Quotation.payment_status == "unpaid"))
        else:
            q = q.filter(Quotation.payment_status == pay_val)

    if stat_val and stat_val != "all":
        q = q.filter(Quotation.status == stat_val)

    if search_val:
        term = f"%{search_val}%"
        q = q.filter(
            or_(
                Quotation.doc_number.ilike(term),
                Quotation.customer_name.ilike(term),
                Quotation.company_name.ilike(term),
                Quotation.phone.ilike(term),
                Quotation.email.ilike(term),
                Quotation.source_quotation_number.ilike(term)
            )
        )
    
    page_val = page if isinstance(page, int) else 1
    limit_val = limit if isinstance(limit, int) else 50
    total_count = q.count()
    local_records = q.order_by(desc(Quotation.created_at)).offset((page_val - 1) * limit_val).limit(limit_val).all()
    local_formatted = []
    for r in local_records:
        issue_formatted = r.issue_date.strftime("%d/%m/%Y") if r.issue_date else "—"
        due_formatted = r.due_date.strftime("%d/%m/%Y") if r.due_date else "—"
        total_val = float(r.grand_total or 0.0)
        paid_val = float(r.amount_paid or 0.0)
        balance_val = max(0.0, total_val - paid_val)

        local_formatted.append({
            "id": f"local_{r.id}",
            "rawId": r.id,
            "number": r.doc_number,
            "docType": r.doc_type,
            "status": r.status,
            "paymentStatus": r.payment_status,
            "issueDate": int(r.issue_date.timestamp() * 1000) if r.issue_date else None,
            "issueDateFormatted": issue_formatted,
            "dueDateFormatted": due_formatted,
            "grandTotal": total_val,
            "taxTotal": float(r.tax_total or 0.0),
            "subtotal": float(r.subtotal or 0.0),
            "financials": {
                "grandTotal": total_val,
                "subtotal": float(r.subtotal or 0.0),
                "taxAmount": float(r.tax_total or 0.0),
                "totalPaid": paid_val,
                "balance": balance_val
            },
            "customer": {
                "name": r.customer_name,
                "companyName": r.company_name,
                "phone": r.phone,
                "email": r.email,
                "address": {
                    "line1": r.address or "",
                    "state": r.state or "Tamil Nadu",
                    "stateCode": r.state_code or "33"
                },
                "gstin": r.gstin or ""
            },
            "lineItems": r.line_items or [],
            "selectedBundle": r.selected_bundle,
            "productCategory": getattr(r, "product_category", "wahrms") or "wahrms",
            "sourceQuotationId": r.source_quotation_id,
            "sourceQuotationNumber": r.source_quotation_number,
            "termsAndConditions": r.terms_and_conditions or "",
            "notes": r.notes or "",
            "preparedBy": r.prepared_by or "",
            "pdfUrl": r.pdf_url,
            "leadId": r.lead_id,
            "customerId": r.customer_id,
            "destinationSyncStatus": getattr(r, "destination_sync_status", "PENDING") or "PENDING",
            "externalClientId": getattr(r, "external_client_id", None),
            "externalProformaId": getattr(r, "external_proforma_id", None),
            "destinationSyncedAt": r.destination_synced_at.strftime("%d/%m/%Y %H:%M") if getattr(r, "destination_synced_at", None) else None,
            "destinationSyncError": getattr(r, "destination_sync_error", None),
            "destinationSyncAttempts": getattr(r, "destination_sync_attempts", 0) or 0,
            "source": "Local CRM"
        })

    return {
        "ok": True,
        "documents": local_formatted,
        "pagination": {
            "total": total_count,
            "limit": limit,
            "page": page
        }
    }

@router.get("/lead-context/{lead_id}")
def get_lead_context_for_quotation(
    lead_id: int,
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches authoritative CRM client details and existing quotation history for a lead.
    Used for automatically populating the quotation creation modal and category-scoped duplicate prevention.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead #{lead_id} not found.")

    norm_role = normalize_role(current_user.role)
    if norm_role in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Support team cannot access Sales quotations."
        )

    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if norm_role == ROLE_SALES_EXECUTIVE:
        if emp and lead.assigned_to != emp.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only create or view quotations for leads assigned to you."
            )
    elif norm_role == ROLE_SALES_MANAGER:
        team_emp_ids = get_team_employee_ids_from_user(current_user, db)
        if lead.assigned_to and lead.assigned_to not in team_emp_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only create or view quotations for your sales team."
            )

    # Check for linked customer
    customer = None
    if hasattr(lead, "customer") and lead.customer:
        customer = lead.customer
    else:
        customer = db.query(Customer).filter(Customer.converted_from_lead == lead.id).first()
        if not customer and lead.phone:
            customer = db.query(Customer).filter(Customer.phone == lead.phone).first()

    # Look for previous quotations/invoices for tax and address details (e.g. GSTIN, state_code)
    prev_quote = db.query(Quotation).filter(
        or_(Quotation.lead_id == lead.id, Quotation.phone == lead.phone)
    ).order_by(desc(Quotation.created_at)).first()

    contact_name = (lead.name or f"{lead.first_name or ''} {lead.last_name or ''}").strip()
    if not contact_name and customer:
        contact_name = customer.contact_name or ""

    company_name = lead.company or (customer.company_name if customer else "") or contact_name
    phone = lead.phone or (customer.phone if customer else "")
    email = lead.email or (customer.email if customer else "")

    address = lead.location or ""
    if not address and (lead.city or lead.state):
        address = ", ".join(filter(None, [lead.city, lead.state]))
    if not address and customer:
        address = customer.location or ""
    if not address and prev_quote:
        address = prev_quote.address or ""

    state = lead.state or (prev_quote.state if prev_quote else "Tamil Nadu")
    state_code = prev_quote.state_code if prev_quote else ("33" if (state or "").lower() == "tamil nadu" else "33")
    gstin = prev_quote.gstin if prev_quote else ""
    notes = lead.requirement_notes or ""

    # Fetch existing quotations for this lead
    existing_quotes = db.query(Quotation).filter(
        Quotation.lead_id == lead.id,
        Quotation.doc_type == "quotation"
    ).order_by(desc(Quotation.created_at)).all()

    formatted_quotes = []
    for q in existing_quotes:
        formatted_quotes.append({
            "id": f"local_{q.id}",
            "rawId": q.id,
            "number": q.doc_number,
            "docType": q.doc_type,
            "status": q.status,
            "paymentStatus": q.payment_status,
            "selectedBundle": q.selected_bundle,
            "productCategory": getattr(q, 'product_category', 'wahrms') or 'wahrms',
            "sourceQuotationId": q.source_quotation_id,
            "sourceQuotationNumber": q.source_quotation_number,
            "grandTotal": q.grand_total,
            "subtotal": q.subtotal,
            "taxTotal": q.tax_total,
            "issueDate": q.issue_date.strftime("%d/%m/%Y") if q.issue_date else "—",
            "createdAt": q.created_at.strftime("%d/%m/%Y %H:%M") if q.created_at else "—",
            "pdfUrl": q.pdf_url
        })

    target_category = category.lower().strip() if category and category.strip().lower() != "all" else None
    cat_quotes = [q for q in formatted_quotes if (q.get("productCategory") or "").lower() == target_category] if target_category else formatted_quotes

    client_details = {
        "leadId": lead.id,
        "customerId": customer.id if customer else None,
        "customerName": contact_name,
        "companyName": company_name,
        "phone": phone,
        "email": email,
        "address": address,
        "state": state,
        "stateCode": state_code,
        "gstin": gstin,
        "notes": notes,
        "status": lead.status
    }

    return {
        "ok": True,
        "client": client_details,
        "hasExistingQuote": len(cat_quotes) > 0,
        "existingQuotations": cat_quotes,
        "allQuotations": formatted_quotes,
        "latestQuotation": cat_quotes[0] if cat_quotes else None
    }

@router.post("/documents")
def create_document(
    payload: CreateDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new quotation, proforma, or invoice directly in MySQL,
    links it to the Lead / Customer, and creates a lead activity timeline event.
    Supports separate WAHRMS and Biometric document creation.
    """
    doc_type_norm = (payload.doc_type or "quotation").lower().strip()
    cat_norm = (payload.product_category or "wahrms").lower().strip()

    current_emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    creator_emp_id = current_emp.id if current_emp else None
    norm_role = normalize_role(current_user.role)

    # STRICT PERMISSION: Only Finance Team can create or issue Tax Invoices
    if doc_type_norm == "invoice":
        if not is_finance_team(current_user, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Only the Finance Team can create or issue Tax Invoices. Sales and other teams may create Quotations and Proforma Invoices."
            )

    # Support roles cannot create Sales quotations/proformas unless explicitly authorized
    if norm_role in [ROLE_SUPPORT_MANAGER, ROLE_SUPPORT_EXECUTIVE]:
        if not user_has_permission(current_user, "quotations", "create", db) and not user_has_permission(current_user, "invoices", "create", db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Support team members cannot create Sales quotations or billing documents."
            )

    # Lead authorization check: Reps can only create billing docs for authorized leads
    target_assigned_to = creator_emp_id
    lead = None
    if payload.lead_id:
        lead = db.query(Lead).filter(Lead.id == payload.lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead #{payload.lead_id} not found.")

        if norm_role == ROLE_SALES_EXECUTIVE:
            if current_emp and lead.assigned_to and lead.assigned_to != current_emp.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: You can only create billing documents for leads assigned to you."
                )
            target_assigned_to = current_emp.id if current_emp else None
        elif norm_role == ROLE_SALES_MANAGER:
            team_emp_ids = get_team_employee_ids_from_user(current_user, db)
            if current_emp and current_emp.id not in team_emp_ids:
                team_emp_ids.append(current_emp.id)
            if lead.assigned_to and lead.assigned_to not in team_emp_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: You can only create billing documents for leads in your sales team."
                )
            target_assigned_to = lead.assigned_to or creator_emp_id
        else:
            target_assigned_to = lead.assigned_to or creator_emp_id

    # DUPLICATE QUOTATION PREVENTION (Per Product Category)
    if doc_type_norm == "quotation" and not payload.allow_duplicate:
        q_dup = db.query(Quotation).filter(
            Quotation.doc_type == "quotation",
            Quotation.product_category == cat_norm,
            Quotation.status != "cancelled"
        )
        if payload.lead_id:
            q_dup = q_dup.filter(Quotation.lead_id == payload.lead_id)
        elif payload.customer_id:
            q_dup = q_dup.filter(Quotation.customer_id == payload.customer_id)
        else:
            q_dup = None

        if q_dup:
            existing_dup = q_dup.order_by(desc(Quotation.created_at)).first()
            if existing_dup:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"An existing {cat_norm.upper()} quotation #{existing_dup.doc_number} (Rs. {existing_dup.grand_total:,.2f}) already exists for this client. Please open the existing quotation or set allow_duplicate=true."
                )

    # DUPLICATE PROFORMA PREVENTION (Per Source Quotation)
    if doc_type_norm == "proforma" and payload.source_quotation_id and not payload.allow_duplicate:
        existing_pf = db.query(Quotation).filter(
            Quotation.doc_type == "proforma",
            Quotation.source_quotation_id == payload.source_quotation_id,
            Quotation.status != "cancelled"
        ).first()
        if existing_pf:
            return {
                "ok": True,
                "already_exists": True,
                "message": f"Proforma Invoice #{existing_pf.doc_number} already exists for Quotation #{existing_pf.source_quotation_number or payload.source_quotation_id}.",
                "document": {
                    "id": f"local_{existing_pf.id}",
                    "rawId": existing_pf.id,
                    "number": existing_pf.doc_number,
                    "docType": existing_pf.doc_type,
                    "selectedBundle": existing_pf.selected_bundle,
                    "productCategory": existing_pf.product_category,
                    "sourceQuotationId": existing_pf.source_quotation_id,
                    "sourceQuotationNumber": existing_pf.source_quotation_number,
                    "status": existing_pf.status,
                    "grandTotal": existing_pf.grand_total,
                    "pdfUrl": existing_pf.pdf_url
                }
            }

    # Generate document number if not provided or DRAFT
    now = datetime.utcnow()
    yr = now.year % 100
    fy_str = f"{yr}{yr+1}"
    prefix_map = {
        "quotation": "CHN/QT",
        "proforma": "CHN/PI",
        "invoice": "CHN/INV",
        "po": "CHN/PO"
    }
    prefix = prefix_map.get(doc_type_norm, "CHN/DOC")

    doc_num = payload.doc_number
    if not doc_num or doc_num == "DRAFT":
        count = db.query(Quotation).filter(Quotation.doc_type == doc_type_norm).count() + 1
        doc_num = f"{prefix}/{fy_str}/{count:04d}"
        while db.query(Quotation).filter(Quotation.doc_number == doc_num).first():
            count += 1
            doc_num = f"{prefix}/{fy_str}/{count:04d}"
    else:
        # Ensure document number uniqueness
        existing_with_num = db.query(Quotation).filter(Quotation.doc_number == doc_num).first()
        if existing_with_num:
            if doc_type_norm == "invoice":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tax Invoice number '{doc_num}' already exists in records. Invoice numbers must be strictly unique."
                )
            # For quotation/proforma auto numbering conflicts, increment sequence to next free slot
            count = db.query(Quotation).filter(Quotation.doc_type == doc_type_norm).count() + 1
            doc_num = f"{prefix}/{fy_str}/{count:04d}"
            while db.query(Quotation).filter(Quotation.doc_number == doc_num).first():
                count += 1
                doc_num = f"{prefix}/{fy_str}/{count:04d}"

    new_doc = Quotation(
        doc_type=doc_type_norm,
        selected_bundle=payload.selected_bundle,
        product_category=cat_norm,
        source_quotation_id=payload.source_quotation_id,
        source_quotation_number=payload.source_quotation_number,
        doc_number=doc_num,
        status=payload.status,
        payment_status=payload.payment_status,
        lead_id=payload.lead_id,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        company_name=payload.company_name,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        state=payload.state,
        state_code=payload.state_code,
        gstin=payload.gstin,
        tax_mode=payload.tax_mode,
        subtotal=payload.subtotal,
        cgst=payload.cgst,
        sgst=payload.sgst,
        igst=payload.igst,
        tax_total=payload.tax_total,
        round_off=payload.round_off,
        grand_total=payload.grand_total,
        amount_paid=payload.amount_paid,
        line_items=payload.line_items,
        terms_and_conditions=payload.terms_and_conditions,
        created_by=creator_emp_id,
        created_by_user_id=current_user.id,
        assigned_to=target_assigned_to,
        notes=payload.notes,
        prepared_by=payload.prepared_by or (current_user.employee.name if (current_user and current_user.employee) else (current_user.username if current_user else "")),
        pdf_url=payload.pdf_url,
        issue_date=datetime.utcnow()
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    # If linked to a lead, update lead quotation status and create activity log
    if payload.lead_id:
        lead = db.query(Lead).filter(Lead.id == payload.lead_id).first()
        if lead:
            lead.quotetask_quotation_id = str(new_doc.id)
            lead.quotetask_quotation_number = new_doc.doc_number
            lead.quotetask_quotation_status = new_doc.status
            lead.quotetask_quotation_amount = new_doc.grand_total
            if payload.status == "issued" and lead.status not in ["PROPOSAL SENT", "NEGOTIATION", "WON", "CONVERTED"]:
                lead.status = "PROPOSAL SENT"
            
            # Log lead activity
            emp_id = current_user.employee.id if (current_user and current_user.employee) else None
            activity = LeadActivity(
                lead_id=lead.id,
                employee_id=emp_id,
                performed_by=emp_id,
                activity_type="PROPOSAL_CREATED",
                description=f"Issued {new_doc.doc_type.capitalize()} #{new_doc.doc_number} ({new_doc.product_category.upper()}) for Rs. {new_doc.grand_total:,.2f}"
            )
            db.add(activity)
            db.commit()

    # Record AuditLog for document creation / invoice issuance
    audit_action = "INVOICE_ISSUED" if new_doc.doc_type == "invoice" else f"{new_doc.doc_type.upper()}_CREATED"
    audit_entry = AuditLog(
        user_id=current_user.id if current_user else None,
        username=current_user.username if current_user else "SYSTEM",
        action=audit_action,
        entity_type="INVOICE" if new_doc.doc_type == "invoice" else "QUOTATION",
        entity_id=str(new_doc.id),
        details=f"Created {new_doc.doc_type} #{new_doc.doc_number} ({new_doc.product_category.upper()}) for {new_doc.customer_name} ({new_doc.company_name or 'N/A'}), Total: Rs. {new_doc.grand_total:,.2f}, Status: {new_doc.status}"
    )
    db.add(audit_entry)
    db.commit()

    # Automatically synchronize WAHRMS Proforma Invoice to Destination ERP / External Website
    sync_result = None
    if doc_type_norm == "proforma":
        try:
            from services.destination_sync_service import DestinationSyncService
            from services.product_validation_service import ProductValidationService
            is_eligible, reason, val = ProductValidationService.is_eligible_for_external_sync(new_doc, db)
            if not is_eligible:
                new_doc.destination_sync_status = "NOT_APPLICABLE"
                new_doc.destination_sync_error = None
                new_doc.destination_sync_response = {
                    "eligible": False,
                    "status": "NOT_APPLICABLE",
                    "reason": reason,
                    "category": val.resolved_category
                }
                db.commit()
                sync_result = {
                    "ok": True,
                    "status": "NOT_APPLICABLE",
                    "sync_status": "NOT_APPLICABLE",
                    "eligible": False,
                    "message": "Biometric document remains internal to CRM (external sync Not Applicable)."
                }
            else:
                new_doc.destination_sync_status = "PENDING"
                db.commit()
                sync_result = DestinationSyncService.sync_proforma_to_destination(db, new_doc.id)
                db.refresh(new_doc)
        except Exception as e:
            logger.error(f"Error executing destination ERP sync for Proforma #{new_doc.doc_number}: {e}")

    return {
        "ok": True,
        "message": f"{payload.doc_type.capitalize()} #{new_doc.doc_number} created successfully!",
        "destinationSync": sync_result,
        "document": {
            "id": f"local_{new_doc.id}",
            "rawId": new_doc.id,
            "number": new_doc.doc_number,
            "docType": new_doc.doc_type,
            "selectedBundle": new_doc.selected_bundle,
            "productCategory": new_doc.product_category,
            "sourceQuotationId": new_doc.source_quotation_id,
            "sourceQuotationNumber": new_doc.source_quotation_number,
            "status": new_doc.status,
            "grandTotal": new_doc.grand_total,
            "pdfUrl": new_doc.pdf_url,
            "destinationSyncStatus": getattr(new_doc, "destination_sync_status", "PENDING") or "PENDING",
            "externalClientId": getattr(new_doc, "external_client_id", None),
            "externalProformaId": getattr(new_doc, "external_proforma_id", None),
            "destinationSyncedAt": new_doc.destination_synced_at.strftime("%d/%m/%Y %H:%M") if getattr(new_doc, "destination_synced_at", None) else None,
            "destinationSyncError": getattr(new_doc, "destination_sync_error", None),
            "destinationSyncAttempts": getattr(new_doc, "destination_sync_attempts", 0) or 0
        }
    }


@router.get("/documents/{doc_id}")
def get_waquote_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches a single document's itemized lines, installments, and PDF links from local CRM database.
    """
    clean_id = doc_id.replace("local_", "").strip()
    r = None
    if clean_id.isdigit():
        r = db.query(Quotation).filter(Quotation.id == int(clean_id)).first()
    if not r:
        r = db.query(Quotation).filter(Quotation.doc_number == doc_id.strip()).first()
    if not r:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not is_user_authorized_for_billing_doc(current_user, r, db, "view"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not authorized to view this billing document."
        )

    issue_formatted = r.issue_date.strftime("%d/%m/%Y") if r.issue_date else "—"
    due_formatted = r.due_date.strftime("%d/%m/%Y") if r.due_date else "—"
    total_val = float(r.grand_total or 0.0)
    paid_val = float(r.amount_paid or 0.0)
    balance_val = max(0.0, total_val - paid_val)

    return {
        "ok": True,
        "document": {
            "id": f"local_{r.id}",
            "number": r.doc_number,
            "docType": r.doc_type,
            "status": r.status,
            "paymentStatus": r.payment_status,
            "issueDate": int(r.issue_date.timestamp() * 1000) if r.issue_date else None,
            "issueDateFormatted": issue_formatted,
            "dueDateFormatted": due_formatted,
            "grandTotal": total_val,
            "taxTotal": float(r.tax_total or 0.0),
            "subtotal": float(r.subtotal or 0.0),
            "financials": {
                "grandTotal": total_val,
                "subtotal": float(r.subtotal or 0.0),
                "taxAmount": float(r.tax_total or 0.0),
                "totalPaid": paid_val,
                "balance": balance_val
            },
            "customer": {
                "name": r.customer_name,
                "companyName": r.company_name,
                "phone": r.phone,
                "email": r.email,
                "address": {
                    "line1": r.address or "",
                    "state": r.state or "Tamil Nadu",
                    "stateCode": r.state_code or "33"
                },
                "gstin": r.gstin or ""
            },
            "lineItems": r.line_items or [],
            "selectedBundle": r.selected_bundle,
            "productCategory": getattr(r, 'product_category', 'wahrms') or 'wahrms',
            "sourceQuotationId": r.source_quotation_id,
            "sourceQuotationNumber": r.source_quotation_number,
            "termsAndConditions": r.terms_and_conditions or "",
            "notes": r.notes or "",
            "preparedBy": r.prepared_by or "",
            "pdfUrl": r.pdf_url,
            "leadId": r.lead_id,
            "customerId": r.customer_id,
            "destinationSyncStatus": getattr(r, "destination_sync_status", "PENDING") or "PENDING",
            "externalClientId": getattr(r, "external_client_id", None),
            "externalProformaId": getattr(r, "external_proforma_id", None),
            "destinationSyncedAt": r.destination_synced_at.strftime("%d/%m/%Y %H:%M") if getattr(r, "destination_synced_at", None) else None,
            "destinationSyncError": getattr(r, "destination_sync_error", None),
            "destinationSyncAttempts": getattr(r, "destination_sync_attempts", 0) or 0,
            "source": "Local CRM"
        }
    }

@router.put("/documents/{doc_id}")
def update_waquote_document(
    doc_id: str,
    payload: CreateDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates an existing quotation, proforma, or invoice in MySQL.
    """
    clean_id = doc_id.replace("local_", "").strip()
    r = None
    if clean_id.isdigit():
        r = db.query(Quotation).filter(Quotation.id == int(clean_id)).first()
    if not r:
        r = db.query(Quotation).filter(Quotation.doc_number == doc_id.strip()).first()
    if not r:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not is_user_authorized_for_billing_doc(current_user, r, db, "edit"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not authorized to update this billing document."
        )

    target_type = (payload.doc_type or r.doc_type).lower().strip()
    # STRICT PERMISSION: If modifying an invoice or attempting to change a doc to an invoice
    if r.doc_type == "invoice" or target_type == "invoice":
        if not is_finance_team(current_user, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Only authorized Finance Team members can edit, issue, or finalize Tax Invoices."
            )

    r.doc_type = target_type
    if payload.customer_name:
        r.customer_name = payload.customer_name
    r.company_name = payload.company_name
    r.phone = payload.phone
    r.email = payload.email
    r.address = payload.address
    r.state = payload.state
    r.state_code = payload.state_code
    r.gstin = payload.gstin
    r.tax_mode = payload.tax_mode
    r.subtotal = payload.subtotal
    r.cgst = payload.cgst
    r.sgst = payload.sgst
    r.igst = payload.igst
    r.tax_total = payload.tax_total
    r.round_off = payload.round_off
    r.grand_total = payload.grand_total
    r.line_items = payload.line_items
    if payload.selected_bundle is not None:
        r.selected_bundle = payload.selected_bundle
    if payload.product_category is not None:
        r.product_category = payload.product_category.lower()
    if payload.source_quotation_id is not None:
        r.source_quotation_id = payload.source_quotation_id
    if payload.source_quotation_number is not None:
        r.source_quotation_number = payload.source_quotation_number
    r.terms_and_conditions = payload.terms_and_conditions
    r.notes = payload.notes
    if payload.prepared_by is not None:
        r.prepared_by = payload.prepared_by
    if payload.payment_status:
        r.payment_status = payload.payment_status
    if payload.status:
        r.status = payload.status

    db.commit()
    db.refresh(r)

    # If linked to lead, update lead quotation amount
    if r.lead_id:
        lead = db.query(Lead).filter(Lead.id == r.lead_id).first()
        if lead:
            lead.quotetask_quotation_amount = r.grand_total
            db.commit()

    # Record AuditLog for document modification
    audit_action = "INVOICE_UPDATED" if r.doc_type == "invoice" else f"{r.doc_type.upper()}_UPDATED"
    audit_entry = AuditLog(
        user_id=current_user.id if current_user else None,
        username=current_user.username if current_user else "SYSTEM",
        action=audit_action,
        entity_type="INVOICE" if r.doc_type == "invoice" else "QUOTATION",
        entity_id=str(r.id),
        details=f"Updated {r.doc_type} #{r.doc_number}. Grand Total: Rs. {r.grand_total:,.2f}, Payment Status: {r.payment_status}, Status: {r.status}"
    )
    db.add(audit_entry)
    db.commit()

    return {
        "ok": True,
        "message": f"{r.doc_type.capitalize()} #{r.doc_number} updated successfully!",
        "document": {
            "id": f"local_{r.id}",
            "number": r.doc_number,
            "docType": r.doc_type,
            "selectedBundle": r.selected_bundle,
            "productCategory": getattr(r, 'product_category', 'wahrms') or 'wahrms',
            "sourceQuotationId": r.source_quotation_id,
            "sourceQuotationNumber": r.source_quotation_number,
            "status": r.status,
            "grandTotal": r.grand_total,
            "pdfUrl": r.pdf_url
        }
    }


@router.post("/webhook")
async def waquote_webhook_receiver(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receives webhook notifications from WA Quote when documents are created, updated, or paid.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Invalid JSON in WA Quote webhook: {e}")
        return {"ok": False, "error": "Invalid JSON"}

@router.post("/quotations/{quote_id}/generate-proforma")
def generate_proforma_from_quotation(
    quote_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generates an independent Proforma Invoice from an existing Quotation.
    Links the new Proforma Invoice via source_quotation_id and source_quotation_number.
    Prevents duplicate proforma creation for the same quotation unless previous was cancelled.
    """
    clean_id = quote_id.replace("local_", "").strip()
    q = None
    if clean_id.isdigit():
        q = db.query(Quotation).filter(Quotation.id == int(clean_id)).first()
    if not q:
        q = db.query(Quotation).filter(Quotation.doc_number == quote_id.strip()).first()
    if not q:
        raise HTTPException(status_code=404, detail="Source Quotation not found.")

    if not is_user_authorized_for_billing_doc(current_user, q, db, "view"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not authorized to generate a proforma from this quotation."
        )

    # Check if a non-cancelled Proforma already exists for this quotation
    existing_pf = db.query(Quotation).filter(
        Quotation.doc_type == "proforma",
        Quotation.source_quotation_id == q.id,
        Quotation.status != "cancelled"
    ).first()

    if existing_pf:
        return {
            "ok": True,
            "already_exists": True,
            "message": f"Proforma Invoice #{existing_pf.doc_number} already exists for Quotation #{q.doc_number}.",
            "document": {
                "id": f"local_{existing_pf.id}",
                "rawId": existing_pf.id,
                "number": existing_pf.doc_number,
                "docType": "proforma",
                "selectedBundle": existing_pf.selected_bundle,
                "productCategory": getattr(existing_pf, 'product_category', 'wahrms') or 'wahrms',
                "sourceQuotationId": existing_pf.source_quotation_id,
                "sourceQuotationNumber": existing_pf.source_quotation_number,
                "status": existing_pf.status,
                "grandTotal": existing_pf.grand_total,
                "pdfUrl": existing_pf.pdf_url
            }
        }

    now = datetime.utcnow()
    fy_start = now.year if now.month >= 4 else now.year - 1
    fy_str = f"{str(fy_start)[2:]}-{str(fy_start + 1)[2:]}"
    prefix = "CHN/PI"

    count = db.query(Quotation).filter(Quotation.doc_type == "proforma").count() + 1
    doc_num = f"{prefix}/{fy_str}/{count:04d}"
    while db.query(Quotation).filter(Quotation.doc_number == doc_num).first():
        count += 1
        doc_num = f"{prefix}/{fy_str}/{count:04d}"

    cat_val = getattr(q, 'product_category', 'wahrms') or 'wahrms'
    current_emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    creator_emp_id = current_emp.id if current_emp else None

    new_pf = Quotation(
        doc_type="proforma",
        selected_bundle=q.selected_bundle,
        product_category=cat_val,
        source_quotation_id=q.id,
        source_quotation_number=q.doc_number,
        created_by=creator_emp_id,
        created_by_user_id=current_user.id,
        assigned_to=creator_emp_id or q.assigned_to,
        doc_number=doc_num,
        status="sent",
        payment_status="unpaid",
        lead_id=q.lead_id,
        customer_id=q.customer_id,
        customer_name=q.customer_name,
        company_name=q.company_name,
        phone=q.phone,
        email=q.email,
        address=q.address,
        state=q.state or "Tamil Nadu",
        state_code=q.state_code or "33",
        gstin=q.gstin,
        tax_mode=q.tax_mode or "exclusive",
        subtotal=q.subtotal,
        cgst=q.cgst,
        sgst=q.sgst,
        igst=q.igst,
        tax_total=q.tax_total,
        round_off=q.round_off,
        grand_total=q.grand_total,
        amount_paid=0.0,
        line_items=q.line_items or [],
        terms_and_conditions=q.terms_and_conditions,
        notes=q.notes or f"Generated from Quotation #{q.doc_number}",
        prepared_by=getattr(current_user, 'full_name', None) or getattr(current_user, 'name', None) or (current_user.username if current_user else q.prepared_by),
        issue_date=now,
        due_date=now + timedelta(days=15),
        created_at=now,
        pdf_url=f"/api/v1/integrations/waquote/proforma/{doc_num.replace('/', '-')}/download"
    )

    db.add(new_pf)
    db.commit()
    db.refresh(new_pf)

    new_pf.pdf_url = f"/api/v1/integrations/waquote/proforma/{new_pf.id}/download"
    if q.status in ["draft", "sent"]:
        q.status = "approved"
    db.commit()

    if new_pf.lead_id:
        act = LeadActivity(
            lead_id=new_pf.lead_id,
            employee_id=creator_emp_id,
            performed_by=creator_emp_id,
            activity_type="PROFORMA_GENERATED",
            description=f"Generated {cat_val.upper()} Proforma Invoice #{new_pf.doc_number} (Rs. {new_pf.grand_total:,.2f}) from Quotation #{q.doc_number}."
        )
        db.add(act)
        db.commit()

    audit_entry = AuditLog(
        user_id=current_user.id if current_user else None,
        username=current_user.username if current_user else "SYSTEM",
        action="PROFORMA_GENERATED",
        entity_type="PROFORMA",
        entity_id=str(new_pf.id),
        details=f"Generated {cat_val.upper()} Proforma #{new_pf.doc_number} from Quotation #{q.doc_number}. Total: Rs. {new_pf.grand_total:,.2f}"
    )
    db.add(audit_entry)
    db.commit()

    # Automatically synchronize Client and WAHRMS Proforma Invoice to Destination ERP / External Website
    sync_result = None
    try:
        from services.destination_sync_service import DestinationSyncService
        from services.product_validation_service import ProductValidationService
        is_eligible, reason, val = ProductValidationService.is_eligible_for_external_sync(new_pf, db)
        if not is_eligible:
            new_pf.destination_sync_status = "NOT_APPLICABLE"
            new_pf.destination_sync_error = None
            new_pf.destination_sync_response = {
                "eligible": False,
                "status": "NOT_APPLICABLE",
                "reason": reason,
                "category": val.resolved_category
            }
            db.commit()
            sync_result = {
                "ok": True,
                "status": "NOT_APPLICABLE",
                "sync_status": "NOT_APPLICABLE",
                "eligible": False,
                "message": "Biometric document remains internal to CRM (external sync Not Applicable)."
            }
        else:
            new_pf.destination_sync_status = "PENDING"
            db.commit()
            sync_result = DestinationSyncService.sync_proforma_to_destination(db, new_pf.id)
            db.refresh(new_pf)
    except Exception as e:
        logger.error(f"Error executing automatic destination ERP sync for Proforma #{new_pf.doc_number}: {e}")

    return {
        "ok": True,
        "message": f"Proforma Invoice #{new_pf.doc_number} successfully generated from Quotation #{q.doc_number}!",
        "destinationSync": sync_result,
        "document": {
            "id": f"local_{new_pf.id}",
            "rawId": new_pf.id,
            "number": new_pf.doc_number,
            "docType": "proforma",
            "selectedBundle": new_pf.selected_bundle,
            "productCategory": new_pf.product_category,
            "sourceQuotationId": new_pf.source_quotation_id,
            "sourceQuotationNumber": new_pf.source_quotation_number,
            "status": new_pf.status,
            "grandTotal": new_pf.grand_total,
            "pdfUrl": new_pf.pdf_url,
            "destinationSyncStatus": getattr(new_pf, "destination_sync_status", "PENDING") or "PENDING",
            "externalClientId": getattr(new_pf, "external_client_id", None),
            "externalProformaId": getattr(new_pf, "external_proforma_id", None),
            "destinationSyncedAt": new_pf.destination_synced_at.strftime("%d/%m/%Y %H:%M") if getattr(new_pf, "destination_synced_at", None) else None,
            "destinationSyncError": getattr(new_pf, "destination_sync_error", None),
            "destinationSyncAttempts": getattr(new_pf, "destination_sync_attempts", 0) or 0
        }
    }


@router.post("/proformas/{doc_id}/sync-destination")
@router.post("/documents/{doc_id}/sync-destination")
def sync_proforma_destination_manual(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually retries synchronizing a Proforma Invoice to the destination ERP.
    """
    clean_id = doc_id.replace("local_", "").strip()
    pf = None
    if clean_id.isdigit():
        pf = db.query(Quotation).filter(Quotation.id == int(clean_id)).first()
    if not pf:
        pf = db.query(Quotation).filter(Quotation.doc_number == doc_id.strip()).first()
    if not pf:
        raise HTTPException(status_code=404, detail="Proforma document not found.")

    if pf.doc_type != "proforma":
        raise HTTPException(status_code=400, detail="Only Proforma Invoices can be synchronized to the destination ERP.")

    # Strict Product Category check: Block any biometric or mixed documents from external synchronization
    from services.product_validation_service import ProductValidationService
    is_eligible, block_reason, val_result = ProductValidationService.is_eligible_for_external_sync(pf, db)
    if not is_eligible:
        pf.destination_sync_status = "NOT_APPLICABLE"
        pf.destination_sync_error = None
        db.commit()
        return {
            "ok": False,
            "status": "NOT_APPLICABLE",
            "eligible": False,
            "message": f"Synchronization Not Applicable: {block_reason}",
            "document": {
                "id": f"local_{pf.id}",
                "number": pf.doc_number,
                "docType": pf.doc_type,
                "destinationSyncStatus": "NOT_APPLICABLE",
                "externalClientId": getattr(pf, "external_client_id", None),
                "externalProformaId": getattr(pf, "external_proforma_id", None),
                "destinationSyncedAt": None,
                "destinationSyncError": None,
                "destinationSyncAttempts": getattr(pf, "destination_sync_attempts", 0) or 0
            }
        }

    from services.destination_sync_service import DestinationSyncService
    sync_result = DestinationSyncService.sync_proforma_to_destination(db, pf.id, force_retry=True)
    db.refresh(pf)

    return {
        "ok": sync_result.get("success", False),
        "syncResult": sync_result,
        "message": sync_result.get("message") or sync_result.get("error"),
        "document": {
            "id": f"local_{pf.id}",
            "number": pf.doc_number,
            "docType": pf.doc_type,
            "destinationSyncStatus": getattr(pf, "destination_sync_status", "PENDING") or "PENDING",
            "externalClientId": getattr(pf, "external_client_id", None),
            "externalProformaId": getattr(pf, "external_proforma_id", None),
            "destinationSyncedAt": pf.destination_synced_at.strftime("%d/%m/%Y %H:%M") if getattr(pf, "destination_synced_at", None) else None,
            "destinationSyncError": getattr(pf, "destination_sync_error", None),
            "destinationSyncAttempts": getattr(pf, "destination_sync_attempts", 0) or 0
        }
    }


@router.get("/quotations/{doc_id}/download")
def download_quotation_pdf(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Dedicated endpoint to generate and download official Quotation PDF.
    """
    clean_id = doc_id.replace("local_", "").strip()
    r = None
    if clean_id.isdigit():
        r = db.query(Quotation).filter(Quotation.id == int(clean_id)).first()
    if not r:
        r = db.query(Quotation).filter(Quotation.doc_number == doc_id.strip()).first()
    if not r:
        raise HTTPException(status_code=404, detail="Quotation document not found.")

    if not is_user_authorized_for_billing_doc(current_user, r, db, "view"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not authorized to download this quotation."
        )

    from services.pdf_service import generate_quotation_pdf
    pdf_bytes = generate_quotation_pdf(r)
    clean_num = (r.doc_number or f"QT-{r.id}").replace("/", "-").replace("\\", "-")
    filename = f"Quotation_{clean_num}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Document-Type": "quotation"
        }
    )


@router.get("/proformas/{doc_id}/download")
def download_proforma_pdf(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Dedicated endpoint to generate and download official Proforma Invoice PDF.
    """
    clean_id = doc_id.replace("local_", "").strip()
    r = None
    if clean_id.isdigit():
        r = db.query(Quotation).filter(Quotation.id == int(clean_id)).first()
    if not r:
        r = db.query(Quotation).filter(Quotation.doc_number == doc_id.strip()).first()
    if not r:
        raise HTTPException(status_code=404, detail="Proforma Invoice document not found.")

    if not is_user_authorized_for_billing_doc(current_user, r, db, "view"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not authorized to download this proforma invoice."
        )

    from services.pdf_service import generate_proforma_pdf
    pdf_bytes = generate_proforma_pdf(r)
    clean_num = (r.doc_number or f"PI-{r.id}").replace("/", "-").replace("\\", "-")
    filename = f"Proforma_Invoice_{clean_num}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Document-Type": "proforma"
        }
    )


@router.get("/invoices/{doc_id:path}/download")
def download_tax_invoice_pdf(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Dedicated endpoint to generate and download official statutory Tax Invoice PDF.
    Accessible to authorized users (Finance, Admin, and Sales viewing issued invoices).
    """
    clean_id = doc_id.replace("local_", "").strip()
    r = None
    if clean_id.isdigit():
        r = db.query(Quotation).filter(Quotation.id == int(clean_id)).first()
    if not r:
        r = db.query(Quotation).filter(Quotation.doc_number == doc_id.strip()).first()
    if not r:
        from models.workflow import FinanceHandoff
        handoff = db.query(FinanceHandoff).filter(
            or_(
                FinanceHandoff.invoice_number == doc_id.strip(),
                FinanceHandoff.id == (int(clean_id) if clean_id.isdigit() else -1)
            )
        ).first()
        if handoff:
            invoice_num = handoff.invoice_number or f"CHN/INV/26/{handoff.id:04d}"
            paid_amt = float(handoff.paid_amount or handoff.final_amount or 0.0)
            sub_val = round(paid_amt / 1.18, 2)
            tax_val = round(paid_amt - sub_val, 2)
            cgst_val = round(tax_val / 2.0, 2)
            sgst_val = round(tax_val / 2.0, 2)

            line_items_data = handoff.products_services or [
                {
                    "description": handoff.customer_requirements or "WAHRMS Business Solution Subscription",
                    "qty": 1,
                    "rate": paid_amt,
                    "amount": paid_amt
                }
            ]

            r = Quotation(
                doc_type="invoice",
                doc_number=invoice_num,
                status="issued",
                payment_status="paid" if handoff.status == "PAID" else "unpaid",
                lead_id=handoff.lead_id,
                customer_id=handoff.customer_id,
                customer_name=handoff.customer_name or "Valued Client",
                company_name=handoff.company_name or "",
                phone=handoff.phone or "",
                email=handoff.email or "",
                address=handoff.address or "Chennai, Tamil Nadu",
                state="Tamil Nadu",
                state_code="33",
                tax_mode="intra",
                subtotal=sub_val,
                cgst=cgst_val,
                sgst=sgst_val,
                igst=0.0,
                tax_total=tax_val,
                grand_total=paid_amt,
                amount_paid=paid_amt if handoff.status == "PAID" else 0.0,
                line_items=line_items_data,
                terms_and_conditions="1. Payment received and verified by Finance.\n2. Goods/Services supplied as per Purchase Order.\n3. Subject to Chennai jurisdiction.",
                prepared_by=getattr(current_user, 'full_name', None) or getattr(current_user, 'name', None) or current_user.username or "Finance Department",
                issue_date=handoff.payment_date or handoff.confirmed_at or handoff.created_at or datetime.utcnow()
            )
            db.add(r)
            handoff.invoice_number = invoice_num
            handoff.invoice_url = f"/api/integrations/waquote/invoices/{invoice_num}/download"
            db.commit()
            db.refresh(r)

    if not r:
        raise HTTPException(status_code=404, detail="Tax Invoice document not found.")

    if not is_user_authorized_for_billing_doc(current_user, r, db, "view"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not authorized to download this tax invoice."
        )

    from services.pdf_service import generate_tax_invoice_pdf
    pdf_bytes = generate_tax_invoice_pdf(r)
    clean_num = (r.doc_number or f"INV-{r.id}").replace("/", "-").replace("\\", "-")
    filename = f"Tax_Invoice_{clean_num}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Document-Type": "invoice"
        }
    )

