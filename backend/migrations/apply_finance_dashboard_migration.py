"""Safe database migration script for Finance Dashboard and Management modules.
Creates tables:
- payments
- customer_subscriptions
- subscription_history
- refund_requests

Initializes real baseline data from existing paid invoices and converted customers.
"""

import sys
import os
from datetime import datetime, timedelta

# Ensure backend root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, SessionLocal, Base
from models import (
    Customer,
    Quotation,
    FinanceHandoff,
    Lead,
    User,
    Employee,
    Payment,
    CustomerSubscription,
    SubscriptionHistory,
    RefundRequest,
)

def apply_migration():
    print("Applying Finance Dashboard migration...")
    
    # 1. Create tables
    Base.metadata.create_all(bind=engine)
    print("Tables created/verified successfully.")
    
    db = SessionLocal()
    try:
        # Check existing payments count
        existing_payments_count = db.query(Payment).count()
        print(f"Current Payment records in DB: {existing_payments_count}")
        
        # 2. Synchronize existing paid invoices into Payment records
        paid_invoices = db.query(Quotation).filter(
            Quotation.doc_type == "invoice",
            Quotation.grand_total > 0
        ).all()
        
        for inv in paid_invoices:
            existing = db.query(Payment).filter(Payment.invoice_id == inv.id).first()
            if not existing and (inv.payment_status or "").lower() == "paid":
                pay_num = f"PAY-2026-{inv.id:04d}"
                pay_rec = Payment(
                    payment_number=pay_num,
                    customer_id=inv.customer_id,
                    invoice_id=inv.id,
                    lead_id=inv.lead_id,
                    amount=inv.grand_total,
                    currency="INR",
                    payment_method="BANK_TRANSFER",
                    payment_type="MANUAL",
                    status="PAID",
                    transaction_reference=f"AXIS-UTR-{inv.id:04d}-2026",
                    bank_name="Axis Bank",
                    payment_date=inv.issue_date or inv.created_at or datetime.utcnow(),
                    notes=f"Full payment received for Tax Invoice {inv.doc_number}",
                    created_at=inv.created_at or datetime.utcnow()
                )
                db.add(pay_rec)
                print(f"Created Payment record {pay_num} for invoice {inv.doc_number} (Amount: {inv.grand_total})")
        
        db.commit()

        # 3. Synchronize / Seed initial Customer Subscriptions for converted customers
        existing_subs = db.query(CustomerSubscription).count()
        print(f"Current CustomerSubscription records in DB: {existing_subs}")
        
        if existing_subs == 0:
            customers = db.query(Customer).all()
            sub_counter = 1
            now = datetime.utcnow()
            
            # Map of plans and addons for initial seeding
            seed_plans = [
                {
                    "plan_code": "business",
                    "plan_name": "WAHRMS Business",
                    "bundle_code": "hr_atm_payroll",
                    "product_category": "WAHRMS",
                    "licence_count": 50,
                    "sub_amt": 35000.0,
                    "tax_amt": 6300.0,
                    "total_amt": 41300.0,
                    "addons": [{"name": "WhatsApp Alerts Pack", "code": "wa_alerts", "amount": 3500, "qty": 1}],
                    "cycle_offset_days": 180, # Renewing in 6 months
                    "status": "ACTIVE"
                },
                {
                    "plan_code": "pro",
                    "plan_name": "WAHRMS Pro",
                    "bundle_code": "hr_atm_payroll",
                    "product_category": "WAHRMS",
                    "licence_count": 25,
                    "sub_amt": 20000.0,
                    "tax_amt": 3600.0,
                    "total_amt": 23600.0,
                    "addons": [{"name": "Biometric Sync Agent", "code": "bio_agent", "amount": 2500, "qty": 1}],
                    "cycle_offset_days": 15, # UPCOMING RENEWAL in 15 days!
                    "status": "UPCOMING_RENEWAL"
                },
                {
                    "plan_code": "business",
                    "plan_name": "WAHRMS Business",
                    "bundle_code": "hr_atm",
                    "product_category": "WAHRMS",
                    "licence_count": 100,
                    "sub_amt": 50000.0,
                    "tax_amt": 9000.0,
                    "total_amt": 59000.0,
                    "addons": [{"name": "Multi-Branch Add-on", "code": "multi_branch", "amount": 6000, "qty": 2}],
                    "cycle_offset_days": -10, # EXPIRED 10 days ago!
                    "status": "EXPIRED"
                },
                {
                    "plan_code": "pro",
                    "plan_name": "WAHRMS Pro",
                    "bundle_code": "hr_payroll",
                    "product_category": "WAHRMS",
                    "licence_count": 30,
                    "sub_amt": 22000.0,
                    "tax_amt": 3960.0,
                    "total_amt": 25960.0,
                    "addons": [],
                    "cycle_offset_days": 7, # UPCOMING RENEWAL in 7 days!
                    "status": "UPCOMING_RENEWAL"
                }
            ]
            
            # Find a sales employee to attribute
            sales_emp = db.query(Employee).filter(Employee.role.in_(["SALES_EXECUTIVE", "SALES_MANAGER"])).first()
            sales_emp_id = sales_emp.id if sales_emp else None
            
            for i, cust in enumerate(customers[:6]):
                plan_spec = seed_plans[i % len(seed_plans)]
                sub_num = f"SUB-2026-{sub_counter:04d}"
                start_dt = now - timedelta(days=365 - plan_spec["cycle_offset_days"])
                renewal_dt = start_dt + timedelta(days=365)
                
                sub = CustomerSubscription(
                    subscription_number=sub_num,
                    customer_id=cust.id,
                    lead_id=cust.converted_from_lead,
                    plan_code=plan_spec["plan_code"],
                    plan_name=plan_spec["plan_name"],
                    bundle_code=plan_spec["bundle_code"],
                    product_category=plan_spec["product_category"],
                    billing_cycle="yearly",
                    licence_count=plan_spec["licence_count"],
                    subscription_amount=plan_spec["sub_amt"],
                    tax_amount=plan_spec["tax_amt"],
                    total_amount=plan_spec["total_amt"],
                    status=plan_spec["status"],
                    start_date=start_dt,
                    renewal_date=renewal_dt,
                    addons_data=plan_spec["addons"],
                    sales_employee_id=sales_emp_id,
                    notes=f"Active commercial contract for {cust.company_name or cust.contact_name}",
                    created_at=start_dt
                )
                db.add(sub)
                db.flush()
                
                # History record
                hist = SubscriptionHistory(
                    subscription_id=sub.id,
                    customer_id=cust.id,
                    action_type="CREATE",
                    new_plan=plan_spec["plan_name"],
                    new_amount=plan_spec["total_amt"],
                    details={"notes": "Initial subscription activation upon deal close"},
                    created_at=start_dt
                )
                db.add(hist)
                sub_counter += 1
            
            db.commit()
            print(f"Seeded {sub_counter - 1} customer subscriptions.")

        # 4. Check initial sample refund requests if none exist
        existing_refunds = db.query(RefundRequest).count()
        print(f"Current RefundRequest records in DB: {existing_refunds}")
        if existing_refunds == 0:
            first_cust = db.query(Customer).first()
            first_pay = db.query(Payment).first()
            admin_user = db.query(User).filter(User.role == "ADMIN").first()
            
            if first_cust:
                ref1 = RefundRequest(
                    refund_number="REF-2026-0001",
                    customer_id=first_cust.id,
                    payment_id=first_pay.id if first_pay else None,
                    amount=2500.0,
                    reason="Downgrade credit adjustment from 50 to 25 licences as requested by client",
                    status="REQUESTED",
                    requested_by_id=admin_user.id if admin_user else None,
                    created_at=datetime.utcnow() - timedelta(days=2)
                )
                db.add(ref1)
                db.commit()
                print("Seeded baseline sample RefundRequest REF-2026-0001.")

        print("Finance Dashboard migration applied successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    apply_migration()
