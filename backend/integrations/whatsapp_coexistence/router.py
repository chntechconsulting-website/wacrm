"""Admin-only API for WhatsApp Business App coexistence onboarding."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.audit import log_audit
from services.auth import require_admin

from .config import WhatsAppCoexistenceConfig
from .schemas import (
    ConnectionOut,
    EventOut,
    ExchangeCodeIn,
    SessionLogIn,
    StatusOut,
    SyncRequestIn,
    TemplateCreateIn,
    TemplateOut,
)
from .service import WhatsAppCoexistenceError, WhatsAppCoexistenceService

logger = logging.getLogger("whatsapp_coexistence.router")

router = APIRouter(prefix="/whatsapp/coexistence", tags=["WhatsApp Coexistence"])


def _http_error(exc: WhatsAppCoexistenceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/status", response_model=StatusOut)
def get_coexistence_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Safe connection status. Tokens are never included."""
    return WhatsAppCoexistenceService.get_status(db)


@router.post("/session-log")
def log_embedded_signup_session(
    body: SessionLogIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Capture Embedded Signup session logging for audit.

    The frontend calls this as soon as Meta posts a ``WA_EMBEDDED_SIGNUP``
    message. It is safe to call before the connection row exists.
    """
    data = body.data or {}
    # Never store an authorization code in the session log.
    data.pop("code", None)
    return WhatsAppCoexistenceService.log_session_event(
        db, event_type=body.type, event=body.event, data=data
    )


@router.post("/exchange", response_model=ConnectionOut)
def exchange_embedded_signup_code(
    body: ExchangeCodeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Exchange the 30-second Embedded Signup code and start onboarding.

    This is the only endpoint that changes Meta-side state: it subscribes the
    app to the customer WABA and requests the one-time contacts/history sync.
    It is hard-locked unless ``WHATSAPP_COEXISTENCE_ENABLED=true``.
    """
    if not WhatsAppCoexistenceConfig.is_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Coexistence onboarding is locked. Set "
                "WHATSAPP_COEXISTENCE_ENABLED=true only when you are ready to "
                "connect a real WhatsApp Business App number."
            ),
        )
    try:
        connection = WhatsAppCoexistenceService.exchange_code(
            db=db,
            code=body.code,
            waba_id=body.waba_id,
            phone_number_id=body.phone_number_id,
            business_id=body.business_id,
            session_event=body.session_event,
        )
        log_audit(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="WHATSAPP_COEXISTENCE_ONBOARDED",
            entity_type="WHATSAPP",
            entity_id=connection.get("id"),
            details=(
                f"Coexistence onboarding started for WABA {connection.get('waba_id')} "
                f"phone {connection.get('phone_number_id')}."
            ),
        )
        return connection
    except WhatsAppCoexistenceError as exc:
        raise _http_error(exc)


@router.post("/refresh", response_model=ConnectionOut)
def refresh_coexistence_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Re-read the phone number and app subscription from Meta."""
    try:
        connection = WhatsAppCoexistenceService.refresh_connection(db)
        log_audit(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="WHATSAPP_COEXISTENCE_REFRESHED",
            entity_type="WHATSAPP",
            entity_id=connection.get("id"),
            details="Coexistence connection status refreshed from Meta.",
        )
        return connection
    except WhatsAppCoexistenceError as exc:
        raise _http_error(exc)


@router.post("/sync")
def request_coexistence_sync(
    body: SyncRequestIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Retry the one-time contacts or history sync before the 24h deadline."""
    try:
        result = WhatsAppCoexistenceService.request_sync(db, body.sync_type)
        log_audit(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="WHATSAPP_COEXISTENCE_SYNC_REQUESTED",
            entity_type="WHATSAPP",
            entity_id=(result.get("connection") or {}).get("id"),
            details=f"Requested {body.sync_type} synchronization.",
        )
        return result
    except WhatsAppCoexistenceError as exc:
        raise _http_error(exc)


@router.get("/templates", response_model=List[TemplateOut])
def list_message_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        return WhatsAppCoexistenceService.list_templates(db)
    except WhatsAppCoexistenceError as exc:
        raise _http_error(exc)


@router.post("/templates")
def create_message_template(
    body: TemplateCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        result = WhatsAppCoexistenceService.create_template(
            db=db,
            name=body.name,
            language=body.language,
            category=body.category,
            body_text=body.body_text,
            footer_text=body.footer_text,
        )
        log_audit(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="WHATSAPP_TEMPLATE_CREATED",
            entity_type="WHATSAPP",
            entity_id=result.get("id"),
            details=f"Created WhatsApp template {body.name}.",
        )
        return result
    except WhatsAppCoexistenceError as exc:
        raise _http_error(exc)


@router.get("/events", response_model=List[EventOut])
def list_coexistence_events(
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return WhatsAppCoexistenceService.list_events(db, limit=limit)
