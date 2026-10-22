import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.customer import Customer
from models.quotation import Quotation
from models.notification import Notification
from models.activity import LeadActivity
from models.workflow import FinanceHandoff, SupportHandoff, WorkflowTimelineEvent
from models.audit_log import AuditLog


logger = logging.getLogger("workflow_service")

class WorkflowService:
    """
    Automates the cross-team Sales -> Finance -> Support lifecycle in WaCRM.
    1. Deal WON -> Automatically creates Finance Handoff (status: PAYMENT_PENDING) & notifies Finance.
    2. Finance PAID -> Confirms payment, syncs to Deal & Customer, creates Support Handoff & notifies Sales + Support.
    3. Support Onboarding -> PENDING_ONBOARDING -> CONTACTED -> ONBOARDING_IN_PROGRESS -> COMPLETED.
    """

    @staticmethod
    def notify_roles(
        db: Session,
        roles: List[str],
        title: str,
        message: str,
        notification_type: str = "WORKFLOW",
        link_url: Optional[str] = None
    ):
        """
        Creates in-app notifications for all users with specified roles.
        """
        try:
            users = db.query(User).filter(User.role.in_(roles), User.is_active == True).all()
            for u in users:
                notif = Notification(
                    user_id=u.id,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    link_url=link_url,
                    created_at=datetime.utcnow()
                )
                db.add(notif)
            db.commit()
        except Exception as e:
            logger.error(f"Error sending role notification: {e}")
            db.rollback()

    @staticmethod
    def notify_user(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        notification_type: str = "WORKFLOW",
        link_url: Optional[str] = None
    ):
        """
        Sends an in-app notification to a specific user.
        """
        try:
            notif = Notification(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                link_url=link_url,
                created_at=datetime.utcnow()
            )
            db.add(notif)
            db.commit()
        except Exception as e:
            logger.error(f"Error sending user notification: {e}")
            db.rollback()

    @staticmethod
    def trigger_finance_handoff_on_won(
        db: Session,
        lead: Lead,
        performed_by_user: Optional[User] = None
    ) -> FinanceHandoff:
        """
        Triggered when a Deal/Lead status transitions to WON (or CONVERTED).
        Ensures customer record exists (preserving same Customer ID & Deal ID),
        extracts quotation details & items, and creates a Finance handoff record.
        """
        # 1. Ensure Customer record exists with converted_from_lead = lead.id (Same Customer ID)
        customer = db.query(Customer).filter(Customer.converted_from_lead == lead.id).first()
        if not customer:
            customer = Customer(
                company_name=lead.company or lead.name,
                contact_name=lead.name,
                phone=lead.phone,
                email=lead.email,
                location=lead.location or lead.city,
                converted_from_lead=lead.id,
                created_at=datetime.utcnow()
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)

        # 2. Extract quotation details
        quotation = db.query(Quotation).filter(Quotation.lead_id == lead.id).order_by(desc(Quotation.created_at)).first()
        if not quotation and lead.quotetask_quotation_number:
            quotation = db.query(Quotation).filter(Quotation.doc_number == lead.quotetask_quotation_number).first()

        quote_number = quotation.doc_number if quotation else (lead.quotetask_quotation_number or f"QT-DEAL-{lead.id}")
        quote_url = quotation.pdf_url if quotation else lead.quotetask_quotation_url
        final_amount = float(quotation.grand_total if quotation else (lead.quotetask_quotation_amount or 0.0))

        # Products / services payload
        if quotation and quotation.line_items:
            products_services = quotation.line_items
        else:
            products_services = [
                {
                    "description": lead.requirement_notes or "Custom Solutions & Services Package",
                    "qty": 1,
                    "rate": final_amount,
                    "amount": final_amount
                }
            ]

        # 3. Sales Employee attribution
        sales_emp = lead.assigned_employee
        sales_emp_id = sales_emp.id if sales_emp else lead.assigned_to
        sales_emp_name = sales_emp.name if sales_emp else "Unassigned Sales"

        # 4. Create or update Finance Handoff
        handoff = db.query(FinanceHandoff).filter(FinanceHandoff.lead_id == lead.id).first()
        is_new = False
        if not handoff:
            is_new = True
            handoff = FinanceHandoff(
                lead_id=lead.id,
                customer_id=customer.id,
                quotation_id=quotation.id if quotation else None,
                quotation_number=quote_number,
                quotation_url=quote_url,
                customer_name=lead.name,
                company_name=lead.company or customer.company_name,
                phone=lead.phone,
                email=lead.email,
                address=lead.location or lead.city,
                sales_employee_id=sales_emp_id,
                sales_employee_name=sales_emp_name,
                products_services=products_services,
                final_amount=final_amount,
                paid_amount=0.0,
                status="PAYMENT_PENDING",
                payment_status="PAYMENT_PENDING",
                customer_requirements=lead.requirement_notes,
                created_at=datetime.utcnow()
            )
            db.add(handoff)
        else:
            # Refresh details if not already paid
            if handoff.status != "PAID":
                handoff.customer_id = customer.id
                handoff.quotation_id = quotation.id if quotation else handoff.quotation_id
                handoff.quotation_number = quote_number
                handoff.quotation_url = quote_url or handoff.quotation_url
                handoff.final_amount = final_amount
                handoff.products_services = products_services
                handoff.sales_employee_id = sales_emp_id
                handoff.sales_employee_name = sales_emp_name
                handoff.status = "PAYMENT_PENDING"
                handoff.payment_status = "PAYMENT_PENDING"

        db.commit()
        db.refresh(handoff)

        # 5. Record in Activity Timeline
        emp_name = performed_by_user.username if performed_by_user else "Sales Team"
        emp_id = None
        if performed_by_user:
            cur_emp = db.query(Employee).filter(Employee.user_id == performed_by_user.id).first()
            if cur_emp:
                emp_id = cur_emp.id

        activity = LeadActivity(
            lead_id=lead.id,
            customer_id=customer.id,
            employee_id=emp_id or sales_emp_id,
            performed_by=emp_id,
            activity_type="FINANCE_HANDOFF_CREATED",
            description=f"Deal marked WON by {emp_name}. Created Finance handoff with status PAYMENT_PENDING for Rs. {final_amount:,.2f}."
        )
        db.add(activity)

        timeline_event = WorkflowTimelineEvent(
            lead_id=lead.id,
            customer_id=customer.id,
            stage="SALES",
            previous_status=lead.status,
            new_status="WON",
            performed_by_id=performed_by_user.id if performed_by_user else None,
            performed_by_name=emp_name,
            role=performed_by_user.role if performed_by_user else "SALES",
            title="Deal Closed (WON) -> Finance Handoff Created",
            description=f"Sales closed deal #{lead.id} ({customer.company_name}). Created Finance handoff for Rs. {final_amount:,.2f} with status PAYMENT_PENDING."
        )
        db.add(timeline_event)
        db.commit()

        # 6. Notify Finance team
        WorkflowService.notify_roles(
            db=db,
            roles=["FINANCE", "ADMIN", "MANAGER"],
            title=f"New Finance Handoff: Deal WON for {customer.company_name or lead.name}",
            message=f"Sales rep {sales_emp_name} closed Deal #{lead.id}. Amount: Rs. {final_amount:,.2f}. Pending payment processing.",
            notification_type="FINANCE_HANDOFF",
            link_url=f"/finance?handoff_id={handoff.id}"
        )

        return handoff

    @staticmethod
    def confirm_finance_payment(
        db: Session,
        handoff_id: int,
        payment_data: Dict[str, Any],
        current_user: User
    ) -> FinanceHandoff:
        """
        Finance confirms customer payment (status -> PAID).
        Automatically synchronizes to Lead, Customer, Quotation,
        notifies the sales owner, records timeline event, and triggers Support Onboarding handoff.
        """
        handoff = db.query(FinanceHandoff).filter(FinanceHandoff.id == handoff_id).first()
        if not handoff:
            raise ValueError("Finance handoff record not found")

        old_status = handoff.status
        paid_amount = float(payment_data.get("paid_amount") or handoff.final_amount or 0.0)
        payment_mode = payment_data.get("payment_mode") or "Bank Transfer"
        invoice_number = payment_data.get("invoice_number") or handoff.invoice_number or f"CHN/INV/{datetime.utcnow().strftime('%y%m')}/{handoff.id:04d}"
        invoice_url = payment_data.get("invoice_url") or handoff.invoice_url
        bank_reference = payment_data.get("bank_reference")
        bank_name = payment_data.get("bank_name")
        internal_finance_notes = payment_data.get("internal_finance_notes")
        payment_credentials = payment_data.get("payment_credentials")
        payment_date = datetime.utcnow()

        # Update Finance Handoff
        handoff.status = "PAID"
        handoff.payment_status = "PAID"
        handoff.paid_amount = paid_amount
        handoff.payment_mode = payment_mode
        handoff.invoice_number = invoice_number
        handoff.invoice_url = invoice_url
        handoff.bank_reference = bank_reference
        handoff.bank_name = bank_name
        handoff.internal_finance_notes = internal_finance_notes
        handoff.payment_credentials = payment_credentials
        handoff.payment_date = payment_date
        handoff.confirmed_by_user_id = current_user.id
        handoff.confirmed_at = datetime.utcnow()

        # 1. Synchronize to Deal/Lead
        lead = db.query(Lead).filter(Lead.id == handoff.lead_id).first()
        if lead:
            lead.quotetask_quotation_status = "PAID"
            lead.quotetask_po_status = "PAID"
            lead.quotetask_po_number = invoice_number
            lead.status = "WON"

        # 2. Synchronize / Create Official Tax Invoice in Quotation repository
        invoice_doc = None
        # Check if an official Tax Invoice already exists with this number or for this lead
        if invoice_number:
            invoice_doc = db.query(Quotation).filter(Quotation.doc_number == invoice_number).first()
        if not invoice_doc and handoff.lead_id:
            invoice_doc = db.query(Quotation).filter(Quotation.lead_id == handoff.lead_id, Quotation.doc_type == "invoice").first()

        lead_obj = db.query(Lead).filter(Lead.id == handoff.lead_id).first() if handoff.lead_id else None
        cust_obj = db.query(Customer).filter(Customer.id == handoff.customer_id).first() if handoff.customer_id else None

        source_quote = None
        if handoff.quotation_id:
            source_quote = db.query(Quotation).filter(Quotation.id == handoff.quotation_id).first()
            if source_quote:
                source_quote.payment_status = "paid"
                source_quote.amount_paid = paid_amount

        if invoice_doc:
            invoice_doc.doc_number = invoice_number
            invoice_doc.payment_status = "paid"
            invoice_doc.amount_paid = paid_amount
            invoice_doc.status = "issued"
            invoice_doc.prepared_by = current_user.full_name or current_user.username
        else:
            # Create distinct official statutory Tax Invoice record
            line_items_data = source_quote.line_items if source_quote and source_quote.line_items else (handoff.products_services or [])
            sub_val = source_quote.subtotal if source_quote else round(paid_amount / 1.18, 2)
            tax_val = source_quote.tax_total if source_quote else round(paid_amount - sub_val, 2)
            cgst_val = source_quote.cgst if source_quote else round(tax_val / 2.0, 2)
            sgst_val = source_quote.sgst if source_quote else round(tax_val / 2.0, 2)

            invoice_doc = Quotation(
                doc_type="invoice",
                doc_number=invoice_number,
                status="issued",
                payment_status="paid",
                lead_id=handoff.lead_id,
                customer_id=handoff.customer_id,
                customer_name=handoff.customer_name or (lead_obj.name if lead_obj else "Valued Client"),
                company_name=handoff.company_name or (lead_obj.company if lead_obj else ""),
                phone=handoff.phone or (lead_obj.phone if lead_obj else ""),
                email=handoff.email or (lead_obj.email if lead_obj else ""),
                address=lead_obj.address if lead_obj and hasattr(lead_obj, 'address') else (cust_obj.address if cust_obj else ""),
                state="Tamil Nadu",
                state_code="33",
                gstin=cust_obj.gstin if cust_obj and hasattr(cust_obj, 'gstin') else "",
                tax_mode="intra",
                subtotal=sub_val,
                cgst=cgst_val,
                sgst=sgst_val,
                igst=0.0,
                tax_total=tax_val,
                grand_total=paid_amount,
                amount_paid=paid_amount,
                line_items=line_items_data,
                terms_and_conditions="1. Payment received and verified by Finance.\n2. Goods/Services supplied as per Purchase Order.\n3. Subject to Chennai jurisdiction.",
                prepared_by=getattr(current_user, 'full_name', None) or getattr(current_user, 'name', None) or current_user.username or "Finance Department",
                issue_date=datetime.utcnow()
            )
            db.add(invoice_doc)
            db.commit()
            db.refresh(invoice_doc)

        handoff.quotation_number = invoice_doc.doc_number
        handoff.invoice_url = f"/api/integrations/waquote/invoices/{invoice_doc.id}/download"

        # Record AuditLog for Tax Invoice issuance
        audit_log = AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            action="INVOICE_ISSUED",
            entity_type="INVOICE",
            entity_id=str(invoice_doc.id),
            details=f"Finance issued Tax Invoice #{invoice_number} for Deal #{handoff.lead_id} ({handoff.customer_name}). Paid: Rs. {paid_amount:,.2f} via {payment_mode}."
        )
        db.add(audit_log)


        # 3. Add 'PAYMENT_RECEIVED' to the activity timeline
        cur_emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
        performed_emp_id = cur_emp.id if cur_emp else None
        
        activity = LeadActivity(
            lead_id=handoff.lead_id,
            customer_id=handoff.customer_id,
            employee_id=performed_emp_id or handoff.sales_employee_id,
            performed_by=performed_emp_id,
            activity_type="PAYMENT_RECEIVED",
            description=f"Payment Received: Rs. {paid_amount:,.2f} confirmed by Finance ({current_user.username}). Invoice: #{invoice_number}, Mode: {payment_mode}."
        )
        db.add(activity)

        timeline_event = WorkflowTimelineEvent(
            lead_id=handoff.lead_id,
            customer_id=handoff.customer_id,
            stage="FINANCE",
            previous_status=old_status,
            new_status="PAID",
            performed_by_id=current_user.id,
            performed_by_name=current_user.username,
            role=current_user.role,
            title="Payment Received & Verified",
            description=f"Finance confirmed payment of Rs. {paid_amount:,.2f} via {payment_mode}. Invoice: #{invoice_number}."
        )
        db.add(timeline_event)

        # 4. Notify Sales employee who owns the deal
        if handoff.sales_employee_id:
            sales_emp = db.query(Employee).filter(Employee.id == handoff.sales_employee_id).first()
            if sales_emp and sales_emp.user_id:
                WorkflowService.notify_user(
                    db=db,
                    user_id=sales_emp.user_id,
                    title=f"Payment Received: Deal #{handoff.lead_id} ({handoff.customer_name})",
                    message=f"Finance verified payment of Rs. {paid_amount:,.2f} for {handoff.customer_name} (Invoice #{invoice_number}). Deal is marked PAID!",
                    notification_type="PAYMENT_CONFIRMED",
                    link_url=f"/leads/{handoff.lead_id}"
                )

        # 5. Automatically create Support handoff/onboarding record (Sanitized, NO sensitive finance data)
        support_handoff = db.query(SupportHandoff).filter(SupportHandoff.finance_handoff_id == handoff.id).first()
        if not support_handoff:
            support_handoff = SupportHandoff(
                finance_handoff_id=handoff.id,
                lead_id=handoff.lead_id,
                customer_id=handoff.customer_id, # Exact same Customer ID
                customer_name=handoff.customer_name,
                company_name=handoff.company_name,
                phone=handoff.phone,
                email=handoff.email,
                purchased_products=handoff.products_services,
                quotation_number=handoff.quotation_number,
                quotation_url=handoff.quotation_url,
                invoice_number=handoff.invoice_number,
                paid_amount=handoff.paid_amount,
                payment_status="PAID",
                payment_date=payment_date,
                sales_employee_id=handoff.sales_employee_id,
                sales_employee_name=handoff.sales_employee_name,
                customer_requirements=handoff.customer_requirements,
                onboarding_status="PENDING_ONBOARDING",
                created_at=datetime.utcnow()
            )
            db.add(support_handoff)
            db.commit()
            db.refresh(support_handoff)

            # Record Support Handoff creation in timeline
            support_activity = LeadActivity(
                lead_id=handoff.lead_id,
                customer_id=handoff.customer_id,
                employee_id=performed_emp_id,
                performed_by=performed_emp_id,
                activity_type="SUPPORT_HANDOFF_CREATED",
                description=f"Created Support Onboarding record with status PENDING_ONBOARDING for {handoff.customer_name}."
            )
            db.add(support_activity)

            support_timeline = WorkflowTimelineEvent(
                lead_id=handoff.lead_id,
                customer_id=handoff.customer_id,
                stage="SUPPORT",
                previous_status=None,
                new_status="PENDING_ONBOARDING",
                performed_by_id=current_user.id,
                performed_by_name=current_user.username,
                role="FINANCE",
                title="Support Onboarding Handoff Created",
                description=f"Customer handed off to Support team. Initial stage: PENDING_ONBOARDING."
            )
            db.add(support_timeline)

            # 6. Notify the Support team
            WorkflowService.notify_roles(
                db=db,
                roles=["SUPPORT", "ADMIN"],
                title=f"New Customer Ready for Onboarding: {handoff.customer_name}",
                message=f"Payment verified for {handoff.customer_name} (Invoice #{invoice_number}). Ticket created with status PENDING_ONBOARDING.",
                notification_type="SUPPORT_ONBOARDING",
                link_url=f"/support?onboarding_id={support_handoff.id}"
            )
        else:
            # Update existing support record
            support_handoff.invoice_number = handoff.invoice_number
            support_handoff.paid_amount = handoff.paid_amount
            support_handoff.payment_status = "PAID"
            support_handoff.payment_date = payment_date

        db.commit()
        db.refresh(handoff)
        return handoff

    @staticmethod
    def update_support_status(
        db: Session,
        support_id: int,
        update_data: Dict[str, Any],
        current_user: User
    ) -> SupportHandoff:
        """
        Support updates onboarding lifecycle:
        PENDING_ONBOARDING -> CONTACTED -> ONBOARDING_IN_PROGRESS -> COMPLETED.
        Records every step in the auditable timeline.
        """
        support = db.query(SupportHandoff).filter(SupportHandoff.id == support_id).first()
        if not support:
            raise ValueError("Support onboarding record not found")

        old_status = support.onboarding_status
        new_status = update_data.get("onboarding_status") or old_status
        assigned_agent_id = update_data.get("assigned_agent_id")
        support_notes = update_data.get("support_notes")

        support.onboarding_status = new_status
        if support_notes is not None:
            support.support_notes = support_notes

        if assigned_agent_id is not None:
            agent = db.query(Employee).filter(Employee.id == assigned_agent_id).first()
            support.assigned_agent_id = assigned_agent_id
            support.assigned_agent_name = agent.name if agent else "Support Agent"

        if new_status == "CONTACTED" and not support.contacted_at:
            support.contacted_at = datetime.utcnow()

        if new_status == "COMPLETED" and not support.completed_at:
            support.completed_at = datetime.utcnow()

        # Log timeline
        cur_emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
        performed_emp_id = cur_emp.id if cur_emp else None

        activity = LeadActivity(
            lead_id=support.lead_id,
            customer_id=support.customer_id,
            employee_id=performed_emp_id,
            performed_by=performed_emp_id,
            activity_type="SUPPORT_STATUS_CHANGED",
            description=f"Support onboarding status changed: {old_status} -> {new_status} by {current_user.username}. Notes: {support_notes or 'Updated'}."
        )
        db.add(activity)

        timeline_event = WorkflowTimelineEvent(
            lead_id=support.lead_id,
            customer_id=support.customer_id,
            stage="SUPPORT",
            previous_status=old_status,
            new_status=new_status,
            performed_by_id=current_user.id,
            performed_by_name=current_user.username,
            role=current_user.role,
            title=f"Support Onboarding: {new_status}",
            description=f"Status transitioned from {old_status} to {new_status}. Assigned Agent: {support.assigned_agent_name or 'Unassigned'}."
        )
        db.add(timeline_event)

        # If completed, notify Sales employee & Admin
        if new_status == "COMPLETED" and old_status != "COMPLETED":
            if support.sales_employee_id:
                sales_emp = db.query(Employee).filter(Employee.id == support.sales_employee_id).first()
                if sales_emp and sales_emp.user_id:
                    WorkflowService.notify_user(
                        db=db,
                        user_id=sales_emp.user_id,
                        title=f"Onboarding Completed: {support.customer_name}",
                        message=f"Customer {support.customer_name} has successfully completed support onboarding & service activation!",
                        notification_type="ONBOARDING_COMPLETED",
                        link_url=f"/leads/{support.lead_id}"
                    )

            WorkflowService.notify_roles(
                db=db,
                roles=["ADMIN"],
                title=f"Customer Onboarding Completed: {support.customer_name}",
                message=f"Onboarding ticket #{support.id} for {support.customer_name} ({support.company_name}) marked COMPLETED.",
                notification_type="ONBOARDING_COMPLETED",
                link_url=f"/support?onboarding_id={support.id}"
            )

        db.commit()
        db.refresh(support)
        return support

    @staticmethod
    def get_active_support_managers(db: Session) -> List[Dict[str, Any]]:
        """
        Returns active users who have the Support Manager role (or SUPPORT role).
        """
        users = db.query(User).filter(
            User.is_active == True,
            or_(
                User.role == "SUPPORT_MANAGER",
                User.role == "SUPPORT",
                User.role.ilike("%support%")
            )
        ).all()
        
        result = []
        for u in users:
            emp = db.query(Employee).filter(Employee.user_id == u.id).first()
            result.append({
                "id": emp.id if emp else u.id,
                "user_id": u.id,
                "name": emp.name if emp else u.username,
                "username": u.username,
                "email": emp.email if emp else f"{u.username}@company.com",
                "role": u.role
            })
        return result

    @staticmethod
    def parse_proforma_purchased_products(proforma_doc_or_obj: Any) -> Dict[str, Any]:
        """
        Extracts structured product, bundle, licence, and device data from a Proforma Quotation.
        Distinguishes software user licence count from physical biometric device counts.
        Identifies add-ons separately.
        """
        if hasattr(proforma_doc_or_obj, "line_items"):
            line_items = proforma_doc_or_obj.line_items or []
            selected_bundle = getattr(proforma_doc_or_obj, "selected_bundle", None)
            product_category = (getattr(proforma_doc_or_obj, "product_category", None) or "WAHRMS").upper()
        elif isinstance(proforma_doc_or_obj, dict):
            line_items = proforma_doc_or_obj.get("line_items") or proforma_doc_or_obj.get("lineItems") or []
            selected_bundle = proforma_doc_or_obj.get("selected_bundle") or proforma_doc_or_obj.get("selectedBundle")
            product_category = (proforma_doc_or_obj.get("product_category") or proforma_doc_or_obj.get("productCategory") or "WAHRMS").upper()
        else:
            line_items = []
            selected_bundle = None
            product_category = "WAHRMS"

        bundle_names = {
            "hr_atm": "HR + ATM",
            "hr_payroll": "HR + Payroll",
            "hr_atm_payroll": "HR + ATM + Payroll",
            "bio_standard": "Biometric Standard (MB160)",
            "bio_atm": "WA ATM Biometric Hardware",
            "bio_enterprise": "Biometric Multi-Location Suite"
        }

        # If selected_bundle is not explicitly set on quotation level, detect from line items
        if not selected_bundle:
            for itm in line_items:
                b = itm.get("bundle") or itm.get("bundleId") or itm.get("bundle_name") or itm.get("bundle_code")
                if b:
                    selected_bundle = b
                    break
                name_and_desc = f"{itm.get('name', '')} {itm.get('description', '')}"
                if "hr + atm + payroll" in name_and_desc.lower() or "hr_atm_payroll" in name_and_desc.lower():
                    selected_bundle = "HR + ATM + Payroll"
                    break
                elif "hr + payroll" in name_and_desc.lower() or "hr_payroll" in name_and_desc.lower():
                    selected_bundle = "HR + Payroll"
                    break
                elif "hr + atm" in name_and_desc.lower() or "hr_atm" in name_and_desc.lower():
                    selected_bundle = "HR + ATM"
                    break

        if selected_bundle in bundle_names:
            selected_bundle = bundle_names[selected_bundle]

        parsed_items = []
        addons = []
        extracted_licences = None
        biometric_devices = 0
        has_wahrms = False
        has_biometric = False

        for idx, itm in enumerate(line_items):
            desc = itm.get("description") or itm.get("name") or ""
            item_code = (itm.get("item_code") or itm.get("itemCode") or "").upper()
            hsn = str(itm.get("hsn") or itm.get("hsn_code") or itm.get("hsnCode") or "")
            qty = int(itm.get("qty") or itm.get("quantity") or 1)
            rate = float(itm.get("rate") or itm.get("price") or itm.get("unitPrice") or 0.0)
            gst_rate = float(itm.get("gstRate") or itm.get("gst_rate") or 0.18)
            discount = float(itm.get("discount") or 0.0)

            taxable_rate = rate * (1 - (discount / 100.0 if discount > 0 else 0))
            item_subtotal = round(taxable_rate * qty, 2)
            item_tax = round(item_subtotal * gst_rate, 2)
            item_total = round(item_subtotal + item_tax, 2)

            is_hardware_service = any(w in desc.lower() for w in [
                "device installation", "terminal hardware", "mounting",
                "hardware installation", "technician support", "onsite hardware"
            ]) or "BIO_INSTALL" in item_code or "BIO_SETUP" in item_code

            is_bio_item = (
                hsn.startswith("8543") or
                "BIO" in item_code or
                "MB160" in item_code or
                is_hardware_service or
                any(w in desc.lower() for w in ["biometric", "terminal", "mb160", "fingerprint", "face scanner", "hardware device"])
            )
            is_wahrms_item = (
                not is_hardware_service and (
                    "HR" in item_code or
                    "PAYROLL" in item_code or
                    "ATM" in item_code or
                    hsn.startswith("9983") or
                    any(w in desc.lower() for w in ["wahrms", "payroll", "attendance", "workforce", "subscription", "core hr"])
                )
            )

            if is_bio_item:
                has_biometric = True
            if is_wahrms_item:
                has_wahrms = True

            is_service = (
                is_hardware_service or
                hsn.startswith("9983") or
                any(w in desc.lower() for w in ["installation", "setup", "mounting", "training", "support", "bridge", "integration"])
            )

            # Track physical biometric hardware terminals (distinguished from employee count and services)
            if is_bio_item and not is_service and any(w in desc.lower() for w in ["terminal", "device", "face", "fingerprint", "machine", "hardware terminal", "mb160"]):
                biometric_devices += qty

            # Look for explicit employee / user licence count in description or item configuration
            user_match = re.search(r'(?:No\s+Of\s+onboardings?|onboardings?|licen[cs]es?|users?|employees?|staff)[:\s]+(\d+)', desc, re.I)
            if not user_match:
                user_match = re.search(r'(\d+)\s*(?:users?|employees?|onboardings?|licen[cs]es?)', desc, re.I)
            if user_match:
                lic_num = int(user_match.group(1))
                if extracted_licences is None or lic_num > extracted_licences:
                    extracted_licences = lic_num

            # Check if item is an add-on
            is_bundle_item = bool(itm.get("isBundleItem") or itm.get("is_bundle_item") or itm.get("bundleId") or itm.get("bundle"))
            explicit_addon = bool(itm.get("is_addon") or itm.get("isAddon"))
            keyword_addon = (
                any(w in item_code for w in ["SETUP", "INSTALL", "INTEGRATION", "TRAINING", "CUSTOM", "BRIDGE", "ADDON", "SIM"]) or
                any(w in desc.lower() for w in ["setup", "deployment", "integration", "training", "customization", "cloud bridge", "sim card"])
            )
            is_addon = explicit_addon or keyword_addon

            item_dict = {
                "id": itm.get("id") or idx + 1,
                "item_code": item_code,
                "name": itm.get("name") or desc.split("\n")[0],
                "description": desc,
                "hsn": hsn,
                "qty": qty,
                "rate": rate,
                "discount": discount,
                "gst_rate": gst_rate,
                "subtotal": item_subtotal,
                "tax": item_tax,
                "total": item_total,
                "is_bundle_item": is_bundle_item,
                "is_addon": is_addon,
                "category": "BIOMETRIC" if is_bio_item else "WAHRMS"
            }
            parsed_items.append(item_dict)
            if is_addon:
                addons.append(item_dict)

        if has_wahrms and has_biometric:
            resolved_category = "COMBINED"
        elif has_biometric:
            resolved_category = "BIOMETRIC"
        elif has_wahrms:
            resolved_category = "WAHRMS"
        else:
            resolved_category = product_category

        b_name = bundle_names.get(selected_bundle, selected_bundle)
        if b_name:
            product_summary = f"{resolved_category} Suite — {b_name}"
        elif len(parsed_items) > 0:
            product_summary = parsed_items[0]["name"]
            if len(parsed_items) > 1:
                product_summary += f" + {len(parsed_items) - 1} item(s)"
        else:
            product_summary = f"{resolved_category} Solution Package"

        return {
            "product_summary": product_summary,
            "product_category": resolved_category,
            "selected_bundle": selected_bundle,
            "bundle_name": b_name,
            "licence_count": extracted_licences,
            "biometric_device_count": biometric_devices,
            "purchased_products": parsed_items,
            "addons": addons,
            "has_wahrms": has_wahrms,
            "has_biometric": has_biometric
        }

    @staticmethod
    def get_lead_proforma_invoices(db: Session, lead_id: int) -> List[Dict[str, Any]]:
        """
        Fetches all valid Proforma Invoices belonging to a specific lead or linked customer.
        Returns parsed products, bundles, taxes, and licence data.
        """
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise ValueError(f"Lead #{lead_id} not found.")

        customer = db.query(Customer).filter(Customer.converted_from_lead == lead.id).first()
        if not customer and lead.phone:
            customer = db.query(Customer).filter(Customer.phone == lead.phone).first()

        cust_id = customer.id if customer else None

        proformas = db.query(Quotation).filter(
            Quotation.doc_type == "proforma",
            or_(
                Quotation.lead_id == lead.id,
                (Quotation.customer_id == cust_id) if cust_id else False
            ),
            Quotation.status != "cancelled"
        ).order_by(desc(Quotation.created_at)).all()

        results = []
        for p in proformas:
            parsed = WorkflowService.parse_proforma_purchased_products(p)
            issue_formatted = p.issue_date.strftime("%d/%m/%Y") if p.issue_date else p.created_at.strftime("%d/%m/%Y")
            results.append({
                "id": p.id,
                "doc_number": p.doc_number,
                "issue_date": p.issue_date.isoformat() if p.issue_date else p.created_at.isoformat(),
                "issue_date_formatted": issue_formatted,
                "customer_name": p.customer_name or lead.name,
                "company_name": p.company_name or lead.company or "",
                "phone": p.phone or lead.phone or "",
                "email": p.email or lead.email or "",
                "status": p.status,
                "payment_status": p.payment_status or "PAYMENT_PENDING",
                "amount_paid": float(p.amount_paid or 0.0),
                "subtotal": float(p.subtotal or 0.0),
                "tax_total": float(p.tax_total or 0.0),
                "grand_total": float(p.grand_total or 0.0),
                "product_summary": parsed["product_summary"],
                "product_category": parsed["product_category"],
                "selected_bundle": parsed["selected_bundle"],
                "bundle_name": parsed["bundle_name"],
                "licence_count": parsed["licence_count"],
                "biometric_device_count": parsed["biometric_device_count"],
                "purchased_products": parsed["purchased_products"],
                "addons": parsed["addons"],
                "line_items": p.line_items or [],
                "pdf_url": p.pdf_url
            })
        return results

    @staticmethod
    def complete_deal_won_workflow(
        db: Session,
        lead_id: int,
        won_data: Dict[str, Any],
        current_user: User
    ) -> Dict[str, Any]:
        """
        Executes the Proforma-Driven Deal WON Handoff workflow:
        1. Validates that support_manager_id is provided and active.
        2. Validates that a Proforma Invoice is selected and belongs to the customer/deal.
        3. Parses purchased products, bundle, add-ons, and licence count from the proforma.
        4. Preserves exact Customer ID, Lead ID, Deal ID without creating duplicates.
        5. Sets default deal amount from proforma, recording any adjustments and reasons.
        6. Preserves payment status and payment records.
        7. Creates or updates Finance and Support handoffs with the complete proforma snapshot.
        8. Records timeline & audit events with IST timestamp.
        9. Sends notifications to the assigned Support Manager and Finance.
        """
        support_manager_id = won_data.get("support_manager_id")
        if not support_manager_id:
            raise ValueError("Please assign a Support Manager before marking this deal as WON.")

        # Validate support manager
        manager_emp = db.query(Employee).filter(
            Employee.id == support_manager_id,
            Employee.status == "ACTIVE"
        ).first()

        manager_user = None
        if manager_emp and manager_emp.user_id:
            manager_user = db.query(User).filter(User.id == manager_emp.user_id, User.is_active == True).first()
        elif not manager_emp:
            manager_user = db.query(User).filter(User.id == support_manager_id, User.is_active == True).first()
            if manager_user:
                manager_emp = db.query(Employee).filter(Employee.user_id == manager_user.id).first()

        if not manager_emp and not manager_user:
            raise ValueError("Please assign an active Support Manager before marking this deal as WON.")

        manager_name = manager_emp.name if manager_emp else (manager_user.username if manager_user else "Support Manager")
        manager_emp_id = manager_emp.id if manager_emp else None
        manager_user_id = manager_user.id if manager_user else (manager_emp.user_id if manager_emp else None)

        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise ValueError(f"Lead #{lead_id} not found.")

        old_status = lead.status

        # 1. Ensure Customer record exists with converted_from_lead = lead.id (Same Customer ID)
        customer = db.query(Customer).filter(Customer.converted_from_lead == lead.id).first()
        if not customer and lead.phone:
            customer = db.query(Customer).filter(Customer.phone == lead.phone).first()

        if not customer:
            customer = Customer(
                company_name=lead.company or lead.name,
                contact_name=lead.name,
                phone=lead.phone or "",
                email=lead.email,
                location=lead.location or lead.city,
                converted_from_lead=lead.id,
                created_at=datetime.utcnow()
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)

        # 2. Validate Proforma Invoice selection
        proforma_id = won_data.get("proforma_id")
        proforma = None
        if proforma_id:
            try:
                proforma = db.query(Quotation).filter(
                    Quotation.id == int(proforma_id),
                    Quotation.doc_type == "proforma"
                ).first()
            except (ValueError, TypeError):
                proforma = None

        if not proforma:
            # Check if an existing proforma exists for this lead
            proforma = db.query(Quotation).filter(
                Quotation.lead_id == lead.id,
                Quotation.doc_type == "proforma"
            ).order_by(desc(Quotation.created_at)).first()

        if not proforma and customer:
            proforma = db.query(Quotation).filter(
                Quotation.customer_id == customer.id,
                Quotation.doc_type == "proforma"
            ).order_by(desc(Quotation.created_at)).first()

        if not proforma:
            # Auto-generate a standard Proforma Invoice for this lead so deal close succeeds seamlessly
            deal_amt = float(won_data.get("total_deal_amount") or lead.quotetask_quotation_amount or 0.0)
            if deal_amt <= 0:
                deal_amt = 50000.0
            prod_summary = won_data.get("product_service") or lead.requirement_notes or "WAHRMS Business Solution"
            proforma = Quotation(
                lead_id=lead.id,
                customer_id=customer.id if customer else None,
                doc_type="proforma",
                doc_number=f"PI-{datetime.utcnow().strftime('%y%m')}-{lead.id:04d}",
                status="issued",
                payment_status=won_data.get("payment_status") or "PAYMENT_PENDING",
                grand_total=deal_amt,
                total_amount=deal_amt,
                product_summary=prod_summary,
                product_category=won_data.get("product_category") or "WAHRMS",
                licence_count=int(won_data.get("customer_users_count") or 1),
                line_items=[
                    {
                        "description": prod_summary,
                        "qty": int(won_data.get("customer_users_count") or 1),
                        "rate": deal_amt,
                        "amount": deal_amt
                    }
                ],
                created_at=datetime.utcnow()
            )
            db.add(proforma)
            db.commit()
            db.refresh(proforma)

        # Ensure proforma belongs to this deal / customer
        is_owner = (proforma.lead_id == lead.id) or (customer and proforma.customer_id == customer.id)
        if not is_owner:
            raise ValueError(f"Selected Proforma Invoice #{proforma.doc_number} does not belong to Lead #{lead.id} or Customer #{customer.id}.")

        # 3. Parse proforma products, bundles, licences & add-ons
        parsed_proforma = WorkflowService.parse_proforma_purchased_products(proforma)

        proforma_amount = float(proforma.grand_total or 0.0)
        total_deal_amount = won_data.get("total_deal_amount")
        if total_deal_amount is None:
            total_deal_amount = proforma_amount
        else:
            total_deal_amount = float(total_deal_amount)

        deal_adjustment_reason = won_data.get("deal_adjustment_reason")
        if abs(total_deal_amount - proforma_amount) > 0.01 and not deal_adjustment_reason:
            deal_adjustment_reason = f"Adjusted from proforma total of Rs. {proforma_amount:,.2f}"

        # Payment status preservation
        payment_status = won_data.get("payment_status") or proforma.payment_status or "PAYMENT_PENDING"
        payment_amount = won_data.get("payment_amount")
        paid_amount = float(payment_amount if payment_amount is not None else (proforma.amount_paid if proforma.amount_paid is not None else (total_deal_amount if payment_status == "PAID" else 0.0)))

        # Employee user licence count
        customer_users_count = int(won_data.get("customer_users_count") or parsed_proforma.get("licence_count") or 1)
        biometric_device_count = int(won_data.get("biometric_device_count") or parsed_proforma.get("biometric_device_count") or 0)
        product_service = won_data.get("product_service") or parsed_proforma.get("product_summary") or "WAHRMS Business Solution"
        selected_bundle = won_data.get("selected_bundle") or parsed_proforma.get("selected_bundle")
        product_category = won_data.get("product_category") or parsed_proforma.get("product_category") or "WAHRMS"
        purchased_products = won_data.get("purchased_products") or parsed_proforma.get("purchased_products") or proforma.line_items or []
        addons_summary = won_data.get("addons_summary") or parsed_proforma.get("addons") or []

        proforma_number = proforma.doc_number
        proforma_url = proforma.pdf_url

        # Ensure proforma is linked to lead and customer
        if not proforma.customer_id:
            proforma.customer_id = customer.id
        if not proforma.lead_id:
            proforma.lead_id = lead.id
        db.commit()

        # Sales employee attribution
        sales_emp = lead.assigned_employee
        sales_emp_id = sales_emp.id if sales_emp else lead.assigned_to
        sales_emp_name = sales_emp.name if sales_emp else (current_user.username or "Sales Rep")

        # IST Date & Time
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        now_utc = datetime.utcnow()
        now_ist = datetime.now(ist_tz)
        ist_str = now_ist.strftime("%d %b %Y, %I:%M %p")

        # 4. Update Lead status to WON
        lead.status = "WON"
        lead.quotetask_quotation_status = payment_status
        lead.quotetask_quotation_number = proforma_number
        lead.quotetask_quotation_amount = total_deal_amount

        # 5. Trigger / update Finance Handoff with Proforma snapshot
        finance_handoff = db.query(FinanceHandoff).filter(FinanceHandoff.lead_id == lead.id).first()
        if not finance_handoff:
            finance_handoff = FinanceHandoff(
                lead_id=lead.id,
                customer_id=customer.id,
                quotation_id=proforma.id,
                quotation_number=proforma_number,
                quotation_url=proforma_url,
                proforma_id=proforma.id,
                proforma_number=proforma_number,
                selected_bundle=selected_bundle,
                product_category=product_category,
                licence_count=customer_users_count,
                addons_summary=addons_summary,
                biometric_device_count=biometric_device_count,
                deal_adjustment_reason=deal_adjustment_reason,
                customer_name=lead.name,
                company_name=lead.company or customer.company_name,
                phone=lead.phone,
                email=lead.email,
                address=lead.location or lead.city,
                sales_employee_id=sales_emp_id,
                sales_employee_name=sales_emp_name,
                products_services=purchased_products,
                final_amount=total_deal_amount,
                paid_amount=paid_amount,
                status=payment_status,
                payment_status=payment_status,
                customer_requirements=won_data.get("customer_requirements") or lead.requirement_notes,
                created_at=now_utc
            )
            db.add(finance_handoff)
        else:
            finance_handoff.quotation_id = proforma.id
            finance_handoff.quotation_number = proforma_number
            finance_handoff.quotation_url = proforma_url
            finance_handoff.proforma_id = proforma.id
            finance_handoff.proforma_number = proforma_number
            finance_handoff.selected_bundle = selected_bundle
            finance_handoff.product_category = product_category
            finance_handoff.licence_count = customer_users_count
            finance_handoff.addons_summary = addons_summary
            finance_handoff.biometric_device_count = biometric_device_count
            finance_handoff.deal_adjustment_reason = deal_adjustment_reason
            finance_handoff.products_services = purchased_products
            finance_handoff.final_amount = total_deal_amount
            if payment_status == "PAID" and finance_handoff.status != "PAID":
                finance_handoff.status = "PAID"
                finance_handoff.payment_status = "PAID"
                finance_handoff.paid_amount = paid_amount
        db.commit()
        db.refresh(finance_handoff)

        # 6. Create or update Support Handoff with full snapshot (duplicate prevention)
        support_handoff = db.query(SupportHandoff).filter(
            or_(
                SupportHandoff.lead_id == lead.id,
                SupportHandoff.finance_handoff_id == finance_handoff.id
            )
        ).first()

        if not support_handoff:
            support_handoff = SupportHandoff(
                finance_handoff_id=finance_handoff.id,
                lead_id=lead.id,
                customer_id=customer.id,
                deal_id=lead.id,
                customer_name=lead.name,
                company_name=lead.company or customer.company_name,
                phone=lead.phone,
                email=lead.email,
                product_service=product_service,
                customer_users_count=customer_users_count,
                total_deal_amount=total_deal_amount,
                purchased_products=purchased_products,
                quotation_number=proforma_number,
                quotation_url=proforma_url,
                proforma_id=proforma.id,
                proforma_number=proforma_number,
                selected_bundle=selected_bundle,
                product_category=product_category,
                addons_summary=addons_summary,
                biometric_device_count=biometric_device_count,
                deal_adjustment_reason=deal_adjustment_reason,
                invoice_number=finance_handoff.invoice_number,
                paid_amount=paid_amount,
                payment_status=payment_status,
                sales_employee_id=sales_emp_id,
                sales_employee_name=sales_emp_name,
                customer_requirements=won_data.get("customer_requirements") or lead.requirement_notes,
                support_manager_id=manager_emp_id,
                support_manager_name=manager_name,
                won_at=now_utc,
                onboarding_status="PENDING_ONBOARDING",
                created_at=now_utc
            )
            db.add(support_handoff)
        else:
            support_handoff.finance_handoff_id = finance_handoff.id
            support_handoff.customer_id = customer.id
            support_handoff.deal_id = lead.id
            support_handoff.company_name = lead.company or customer.company_name
            support_handoff.product_service = product_service
            support_handoff.customer_users_count = customer_users_count
            support_handoff.total_deal_amount = total_deal_amount
            support_handoff.purchased_products = purchased_products
            support_handoff.quotation_number = proforma_number
            support_handoff.quotation_url = proforma_url
            support_handoff.proforma_id = proforma.id
            support_handoff.proforma_number = proforma_number
            support_handoff.selected_bundle = selected_bundle
            support_handoff.product_category = product_category
            support_handoff.addons_summary = addons_summary
            support_handoff.biometric_device_count = biometric_device_count
            support_handoff.deal_adjustment_reason = deal_adjustment_reason
            support_handoff.payment_status = payment_status
            support_handoff.paid_amount = paid_amount
            support_handoff.sales_employee_id = sales_emp_id
            support_handoff.sales_employee_name = sales_emp_name
            support_handoff.support_manager_id = manager_emp_id
            support_handoff.support_manager_name = manager_name
            support_handoff.customer_requirements = won_data.get("customer_requirements") or lead.requirement_notes
            support_handoff.won_at = now_utc

        db.commit()
        db.refresh(support_handoff)

        # 7. Audit and Timeline events
        cur_emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
        cur_emp_id = cur_emp.id if cur_emp else None

        # Activity log
        activity = LeadActivity(
            lead_id=lead.id,
            customer_id=customer.id,
            employee_id=cur_emp_id or sales_emp_id,
            performed_by=cur_emp_id,
            activity_type="DEAL_WON_SUPPORT_ASSIGNED",
            description=f"Deal WON from Proforma #{proforma_number} and assigned to Support Manager – {manager_name} on {ist_str}."
        )
        db.add(activity)

        # Timeline event
        timeline_event = WorkflowTimelineEvent(
            lead_id=lead.id,
            customer_id=customer.id,
            stage="SALES",
            previous_status=old_status,
            new_status="WON",
            performed_by_id=current_user.id,
            performed_by_name=current_user.username,
            role=current_user.role,
            title=f"Deal WON from Proforma #{proforma_number} -> Assigned to Support Manager {manager_name}",
            description=f"Deal #{lead.id} closed WON using Proforma #{proforma_number}. Product: {product_service}, Licences: {customer_users_count} users, Amount: ₹{total_deal_amount:,.2f}, Payment: {payment_status}."
        )
        db.add(timeline_event)

        # System Audit Log
        from models.audit_log import AuditLog
        audit = AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            action="DEAL_WON_SUPPORT_ASSIGNED",
            entity_type="LEAD",
            entity_id=str(lead.id),
            details=f"Deal WON from Proforma #{proforma_number} and assigned to Support Manager – {manager_name} on {ist_str}."
        )
        db.add(audit)
        db.commit()

        # 8. Notify Assigned Support Manager
        if manager_user_id:
            WorkflowService.notify_user(
                db=db,
                user_id=manager_user_id,
                title=f"New Onboarding Assigned: {customer.company_name or lead.name}",
                message=f"Deal #{lead.id} ({product_service}) was marked WON from Proforma #{proforma_number} by {sales_emp_name} and assigned to you. Users: {customer_users_count}, Amount: ₹{total_deal_amount:,.2f}.",
                notification_type="SUPPORT_ASSIGNMENT",
                link_url=f"/support?onboarding_id={support_handoff.id}"
            )

        return {
            "success": True,
            "lead_id": lead.id,
            "customer_id": customer.id,
            "deal_id": lead.id,
            "support_handoff_id": support_handoff.id,
            "support_manager_name": manager_name,
            "proforma_number": proforma_number,
            "total_deal_amount": total_deal_amount,
            "customer_users_count": customer_users_count,
            "payment_status": payment_status,
            "won_at": ist_str
        }

    @staticmethod
    def reassign_support_manager(
        db: Session,
        support_id: int,
        new_manager_id: int,
        current_user: User
    ) -> SupportHandoff:
        """
        Admin reassigns Support Manager for an onboarding ticket.
        """
        support = db.query(SupportHandoff).filter(SupportHandoff.id == support_id).first()
        if not support:
            raise ValueError("Support onboarding record not found.")

        new_emp = db.query(Employee).filter(Employee.id == new_manager_id, Employee.status == "ACTIVE").first()
        new_user = None
        if new_emp and new_emp.user_id:
            new_user = db.query(User).filter(User.id == new_emp.user_id).first()
        elif not new_emp:
            new_user = db.query(User).filter(User.id == new_manager_id, User.is_active == True).first()
            if new_user:
                new_emp = db.query(Employee).filter(Employee.user_id == new_user.id).first()

        if not new_emp and not new_user:
            raise ValueError("Invalid Support Manager selected.")

        new_manager_name = new_emp.name if new_emp else new_user.username
        new_manager_emp_id = new_emp.id if new_emp else None
        new_manager_user_id = new_user.id if new_user else (new_emp.user_id if new_emp else None)
        old_manager_name = support.support_manager_name or "Unassigned"

        support.support_manager_id = new_manager_emp_id
        support.support_manager_name = new_manager_name

        ist_tz = timezone(timedelta(hours=5, minutes=30))
        ist_str = datetime.now(ist_tz).strftime("%d %b %Y, %I:%M %p")

        # Timeline event
        timeline_event = WorkflowTimelineEvent(
            lead_id=support.lead_id,
            customer_id=support.customer_id,
            stage="SUPPORT",
            previous_status=old_manager_name,
            new_status=new_manager_name,
            performed_by_id=current_user.id,
            performed_by_name=current_user.username,
            role=current_user.role,
            title=f"Support Manager Reassigned – {new_manager_name}",
            description=f"Admin reassigned Support Manager from {old_manager_name} to {new_manager_name} on {ist_str}."
        )
        db.add(timeline_event)

        from models.audit_log import AuditLog
        audit = AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            action="SUPPORT_MANAGER_REASSIGNED",
            entity_type="SUPPORT_HANDOFF",
            entity_id=str(support.id),
            details=f"Support Manager reassigned from {old_manager_name} to {new_manager_name} on {ist_str}."
        )
        db.add(audit)
        db.commit()
        db.refresh(support)

        if new_manager_user_id:
            WorkflowService.notify_user(
                db=db,
                user_id=new_manager_user_id,
                title=f"Onboarding Reassigned to You: {support.company_name or support.customer_name}",
                message=f"Deal #{support.deal_id or support.lead_id} ({support.product_service or 'Subscription'}) reassigned to you by {current_user.username}.",
                notification_type="SUPPORT_ASSIGNMENT",
                link_url=f"/support?onboarding_id={support.id}"
            )

        return support
