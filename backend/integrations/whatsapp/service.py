import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from models.lead import Lead
from models.employee import Employee
from models.activity import LeadActivity
from models.whatsapp import Conversation, WhatsAppMessage
from .schemas import SendMessageRequest
from .config import WhatsAppConfig
from .providers.cloud_api import MetaWhatsAppCloudProvider

logger = logging.getLogger("whatsapp_service")

class WhatsAppService:
    provider = MetaWhatsAppCloudProvider()

    @staticmethod
    def clean_phone(phone: str) -> str:
        if not phone:
            return ""
        digits = "".join(filter(str.isdigit, phone))
        return digits

    @classmethod
    def get_or_create_conversation(
        cls, 
        db: Session, 
        phone: str, 
        lead_id: Optional[int] = None, 
        assigned_to: Optional[int] = None
    ) -> Conversation:
        clean_p = cls.clean_phone(phone)
        
        # 1. Try to find by lead_id first if given
        conv = None
        if lead_id:
            conv = db.query(Conversation).filter(Conversation.lead_id == lead_id).first()
        
        # 2. If not found by lead_id, search by phone
        if not conv and clean_p:
            conv = db.query(Conversation).filter(Conversation.phone.like(f"%{clean_p[-10:]}")).first()

        # 3. Match matching Lead if lead_id is missing
        matched_lead = None
        if lead_id:
            matched_lead = db.query(Lead).filter(Lead.id == lead_id).first()
        elif clean_p:
            matched_lead = db.query(Lead).filter(Lead.phone.like(f"%{clean_p[-10:]}")).first()

        contact_name = matched_lead.name if matched_lead else (conv.contact_name if conv else clean_p)
        effective_lead_id = matched_lead.id if matched_lead else lead_id
        effective_assigned = matched_lead.assigned_to if (matched_lead and matched_lead.assigned_to) else assigned_to

        if conv:
            # Sync metadata
            if not conv.lead_id and effective_lead_id:
                conv.lead_id = effective_lead_id
            if contact_name:
                conv.contact_name = contact_name
            if not conv.assigned_to and effective_assigned:
                conv.assigned_to = effective_assigned
            db.commit()
            return conv

        # Create new conversation
        conv = Conversation(
            lead_id=effective_lead_id,
            phone=clean_p or phone,
            contact_name=contact_name,
            assigned_to=effective_assigned,
            unread_count=0,
            is_archived=False,
            last_message_text="Conversation started",
            last_message_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    @classmethod
    def send_outbound_message(
        cls, 
        db: Session, 
        req: SendMessageRequest, 
        sender_employee: Optional[Employee] = None
    ) -> Dict[str, Any]:
        target_phone = req.phone
        if not target_phone and req.lead_id:
            lead = db.query(Lead).filter(Lead.id == req.lead_id).first()
            if lead and lead.phone:
                target_phone = lead.phone

        if not target_phone:
            return {"success": False, "error": "Target phone number or lead ID required"}

        conv = cls.get_or_create_conversation(
            db=db, 
            phone=target_phone, 
            lead_id=req.lead_id, 
            assigned_to=sender_employee.id if sender_employee else None
        )

        # Call provider API
        msg_type = (req.message_type or "TEXT").upper()
        res = {}
        
        if not WhatsAppConfig.is_configured():
            logger.warning("WhatsApp API credentials not configured in .env")
            res = {"success": False, "error": "WhatsApp integration not configured in .env", "status": "FAILED"}
        elif msg_type == "TEXT":
            res = cls.provider.send_text_message(conv.phone, req.body or "")
        elif msg_type == "TEMPLATE":
            res = cls.provider.send_template_message(conv.phone, req.template_name or "hello_world", req.language_code or "en_US")
        elif msg_type in ["IMAGE", "DOCUMENT"]:
            res = cls.provider.send_media_message(conv.phone, msg_type, req.media_url or "", req.caption or req.body)
        else:
            res = cls.provider.send_text_message(conv.phone, req.body or "")

        msg_body = req.body or (f"Template: {req.template_name}" if req.template_name else "Media attachment")
        status_val = "SENT" if res.get("success") else "FAILED"

        # Save Message record
        msg = WhatsAppMessage(
            conversation_id=conv.id,
            lead_id=conv.lead_id,
            sender_employee_id=sender_employee.id if sender_employee else None,
            direction="OUTBOUND",
            message_type=msg_type,
            body=msg_body,
            media_url=req.media_url,
            caption=req.caption,
            template_name=req.template_name,
            provider_message_id=res.get("message_id"),
            status=status_val,
            sent_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        db.add(msg)

        # Update Conversation
        conv.last_message_text = f"You: {msg_body[:80]}"
        conv.last_message_at = datetime.utcnow()
        conv.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(msg)

        # Record LeadActivity timeline if linked to lead
        if conv.lead_id:
            sender_name = sender_employee.name if sender_employee else "System"
            activity = LeadActivity(
                lead_id=conv.lead_id,
                performed_by=sender_employee.id if sender_employee else None,
                activity_type="WHATSAPP_SENT",
                description=f"{sender_name} sent WhatsApp ({msg_type}): {msg_body[:100]}",
                created_at=datetime.utcnow()
            )
            db.add(activity)
            db.commit()

        return {
            "success": res.get("success", False),
            "error": res.get("error"),
            "message_id": msg.id,
            "provider_message_id": res.get("message_id"),
            "status": status_val
        }

    @classmethod
    def process_inbound_webhook_payload(cls, db: Session, payload: Dict[str, Any]):
        """
        Processes Meta WhatsApp Webhook payloads (incoming messages & status receipts).
        """
        try:
            entries = payload.get("entry", [])
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    
                    # 1. Process Messages
                    messages = value.get("messages", [])
                    contacts = value.get("contacts", [])
                    sender_name = contacts[0].get("profile", {}).get("name") if contacts else None

                    for m in messages:
                        wamid = m.get("id")
                        from_phone = m.get("from")
                        msg_type_raw = m.get("type", "text").upper()
                        
                        body_text = ""
                        media_url = None

                        if msg_type_raw == "TEXT":
                            body_text = m.get("text", {}).get("body", "")
                        elif msg_type_raw in ["IMAGE", "DOCUMENT", "AUDIO", "VIDEO"]:
                            media_obj = m.get(msg_type_raw.lower(), {})
                            media_url = media_obj.get("id") or media_obj.get("link")
                            body_text = media_obj.get("caption") or f"[{msg_type_raw} Attachment]"
                        else:
                            body_text = f"[{msg_type_raw} Message]"

                        # Get/Create conversation
                        conv = cls.get_or_create_conversation(db=db, phone=from_phone)
                        if sender_name and not conv.contact_name:
                            conv.contact_name = sender_name

                        # Check if message already processed by provider_message_id
                        existing_msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.provider_message_id == wamid).first()
                        if existing_msg:
                            continue

                        # Create inbound message record
                        msg = WhatsAppMessage(
                            conversation_id=conv.id,
                            lead_id=conv.lead_id,
                            direction="INBOUND",
                            message_type=msg_type_raw if msg_type_raw in ["TEXT", "IMAGE", "DOCUMENT", "TEMPLATE"] else "TEXT",
                            body=body_text,
                            media_url=media_url,
                            provider_message_id=wamid,
                            status="DELIVERED",
                            sent_at=datetime.utcnow(),
                            delivered_at=datetime.utcnow(),
                            created_at=datetime.utcnow()
                        )
                        db.add(msg)

                        conv.unread_count += 1
                        conv.last_message_text = body_text[:80]
                        conv.last_message_at = datetime.utcnow()
                        conv.updated_at = datetime.utcnow()
                        db.commit()

                        # Log Lead Activity history
                        if conv.lead_id:
                            activity = LeadActivity(
                                lead_id=conv.lead_id,
                                performed_by=None,
                                activity_type="WHATSAPP_RECEIVED",
                                description=f"Received WhatsApp message from {conv.contact_name or from_phone}: {body_text[:100]}",
                                created_at=datetime.utcnow()
                            )
                            db.add(activity)
                            db.commit()

                    # 2. Process Status Updates (sent, delivered, read, failed)
                    statuses = value.get("statuses", [])
                    for st in statuses:
                        wamid = st.get("id")
                        st_name = st.get("status", "").upper() # SENT, DELIVERED, READ, FAILED
                        
                        target_msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.provider_message_id == wamid).first()
                        if target_msg:
                            target_msg.status = st_name
                            if st_name == "DELIVERED":
                                target_msg.delivered_at = datetime.utcnow()
                            elif st_name == "READ":
                                target_msg.read_at = datetime.utcnow()
                            db.commit()
        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook payload: {e}")

    @staticmethod
    def list_conversations(
        db: Session, 
        filter_tab: str = "all", 
        search: Optional[str] = None, 
        current_emp_id: Optional[int] = None
    ) -> List[Conversation]:
        query = db.query(Conversation)

        if filter_tab == "unread":
            query = query.filter(Conversation.unread_count > 0)
        elif filter_tab == "my" and current_emp_id:
            query = query.filter(Conversation.assigned_to == current_emp_id)
        elif filter_tab == "archived":
            query = query.filter(Conversation.is_archived == True)
        else:
            query = query.filter(Conversation.is_archived == False)

        if search:
            fmt = f"%{search}%"
            query = query.filter(
                or_(
                    Conversation.contact_name.ilike(fmt),
                    Conversation.phone.ilike(fmt),
                    Conversation.last_message_text.ilike(fmt)
                )
            )

        return query.order_by(desc(Conversation.last_message_at)).all()
