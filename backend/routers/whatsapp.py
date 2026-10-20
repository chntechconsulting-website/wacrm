from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models.user import User
from models.employee import Employee
from models.lead import Lead
from models.whatsapp import Conversation, WhatsAppMessage

from integrations.whatsapp.schemas import (
    SendMessageRequest,
    ConversationOut,
    ConversationDetailOut,
    WhatsAppMessageOut
)
from integrations.whatsapp.service import WhatsAppService
from integrations.whatsapp.config import WhatsAppConfig
from services.auth import get_current_user
from services.audit import log_audit

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Module"])

def get_employee_for_user(user: User, db: Session) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()

def build_message_out(msg: WhatsAppMessage) -> WhatsAppMessageOut:
    sender_name = msg.sender_employee.name if msg.sender_employee else None
    return WhatsAppMessageOut(
        id=msg.id,
        conversation_id=msg.conversation_id,
        lead_id=msg.lead_id,
        sender_employee_id=msg.sender_employee_id,
        sender_employee_name=sender_name,
        direction=msg.direction,
        message_type=msg.message_type,
        body=msg.body,
        media_url=msg.media_url,
        caption=msg.caption,
        template_name=msg.template_name,
        provider_message_id=msg.provider_message_id,
        status=msg.status,
        sent_at=msg.sent_at,
        delivered_at=msg.delivered_at,
        read_at=msg.read_at,
        created_at=msg.created_at
    )

def build_conversation_out(conv: Conversation) -> ConversationOut:
    lead_name = conv.lead.name if conv.lead else None
    emp_name = conv.assigned_employee.name if conv.assigned_employee else None
    return ConversationOut(
        id=conv.id,
        lead_id=conv.lead_id,
        lead_name=lead_name,
        phone=conv.phone,
        contact_name=conv.contact_name or lead_name or conv.phone,
        assigned_to=conv.assigned_to,
        assigned_employee_name=emp_name,
        unread_count=conv.unread_count,
        is_archived=conv.is_archived,
        last_message_text=conv.last_message_text,
        last_message_at=conv.last_message_at,
        created_at=conv.created_at,
        updated_at=conv.updated_at
    )

@router.get("/config-status")
def get_whatsapp_config_status():
    """
    Returns whether WhatsApp Business API credentials are configured.
    """
    configured = WhatsAppConfig.is_configured()
    return {
        "configured": configured,
        "message": "WhatsApp integration configured" if configured else "WhatsApp integration not configured"
    }

@router.post("/send-message")
def send_whatsapp_message(
    req: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sends an outbound WhatsApp message (Text, Template, or Media) to a customer/lead.
    """
    current_emp = get_employee_for_user(current_user, db)

    # BACKEND RBAC SECURITY CHECK
    if current_user.role == "EMPLOYEE":
        if req.lead_id:
            lead = db.query(Lead).filter(Lead.id == req.lead_id).first()
            if lead and current_emp and lead.assigned_to != current_emp.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You can only send WhatsApp messages to leads assigned to you."
                )

    res = WhatsAppService.send_outbound_message(db=db, req=req, sender_employee=current_emp)
    if not res.get("success") and "not configured" in str(res.get("error", "")).lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WhatsApp integration not configured"
        )

    log_audit(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="WHATSAPP_MESSAGE_SENT",
        entity_type="WHATSAPP",
        entity_id=req.lead_id,
        details=f"WhatsApp message sent to lead #{req.lead_id}."
    )

    return res

@router.get("/conversations", response_model=List[ConversationOut])
def list_whatsapp_conversations(
    tab: str = Query("all", description="all, unread, my, archived"),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists WhatsApp conversations filtered by tab (All, Unread, My Conversations, Archived) and search text.
    Enforces employee lead visibility.
    """
    current_emp = get_employee_for_user(current_user, db)
    emp_id = current_emp.id if current_emp else None

    # If role is EMPLOYEE, force tab to "my"
    effective_tab = tab
    if current_user.role == "EMPLOYEE":
        effective_tab = "my"

    convs = WhatsAppService.list_conversations(
        db=db, 
        filter_tab=effective_tab, 
        search=search, 
        current_emp_id=emp_id
    )

    # Further filter out any conversations not assigned to employee
    if current_user.role == "EMPLOYEE" and emp_id:
        convs = [c for c in convs if c.assigned_to == emp_id or (c.lead and c.lead.assigned_to == emp_id)]

    return [build_conversation_out(c) for c in convs]

@router.get("/conversations/by-lead/{lead_id}", response_model=ConversationDetailOut)
def get_conversation_by_lead_id(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Gets or initializes the WhatsApp conversation associated with a specific lead_id.
    Enforces 403 Forbidden for unauthorized employees.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    current_emp = get_employee_for_user(current_user, db)
    if current_user.role == "EMPLOYEE":
        if not current_emp or lead.assigned_to != current_emp.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view WhatsApp conversations for leads assigned to you."
            )

    conv = WhatsAppService.get_or_create_conversation(db=db, phone=lead.phone, lead_id=lead.id)
    conv.unread_count = 0
    db.commit()

    conv_out = build_conversation_out(conv)
    msgs_out = [build_message_out(m) for m in conv.messages]
    return ConversationDetailOut(**conv_out.dict(), messages=msgs_out)

@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
def get_whatsapp_conversation_detail(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves full details and message history for a specific WhatsApp conversation.
    Enforces 403 Forbidden for unauthorized employees.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    current_emp = get_employee_for_user(current_user, db)
    if current_user.role == "EMPLOYEE":
        if not current_emp or (conv.assigned_to != current_emp.id and (conv.lead and conv.lead.assigned_to != current_emp.id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view WhatsApp conversations for leads assigned to you."
            )

    conv.unread_count = 0
    db.commit()

    conv_out = build_conversation_out(conv)
    msgs_out = [build_message_out(m) for m in conv.messages]
    return ConversationDetailOut(**conv_out.dict(), messages=msgs_out)

@router.put("/conversations/{conversation_id}/read")
def mark_whatsapp_conversation_read(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    current_emp = get_employee_for_user(current_user, db)
    if current_user.role == "EMPLOYEE":
        if not current_emp or (conv.assigned_to != current_emp.id and (conv.lead and conv.lead.assigned_to != current_emp.id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only access conversations for leads assigned to you."
            )

    conv.unread_count = 0
    db.commit()
    return {"message": "Conversation marked as read"}

@router.put("/conversations/{conversation_id}/archive")
def archive_whatsapp_conversation(
    conversation_id: int,
    archive: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    current_emp = get_employee_for_user(current_user, db)
    if current_user.role == "EMPLOYEE":
        if not current_emp or (conv.assigned_to != current_emp.id and (conv.lead and conv.lead.assigned_to != current_emp.id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only access conversations for leads assigned to you."
            )

    conv.is_archived = archive
    db.commit()
    return {"message": f"Conversation {'archived' if archive else 'unarchived'} successfully"}
