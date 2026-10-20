import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, Query, Response, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.meta_page import MetaPage
from models.lead import Lead
from models.integration import IntegrationLog
from services.auth import require_roles
from .config import MetaConfig
from .service import MetaLeadService
from .crypto import decrypt_token, mask_token
from .schemas import (
    MetaIntegrationStatusResponse,
    MetaPageCreate,
    MetaPageRefresh,
    MetaPageOut,
    MetaPageActionResponse
)

logger = logging.getLogger("meta_webhook")

router = APIRouter(prefix="/integrations/meta", tags=["Meta Lead Ads Integration"])

def _to_page_out(page: MetaPage) -> MetaPageOut:
    plain = decrypt_token(page.encrypted_access_token)
    return MetaPageOut(
        id=page.id,
        page_id=page.page_id,
        page_name=page.page_name,
        status=page.status,
        masked_token=mask_token(plain),
        category=page.category,
        lead_count=page.lead_count or 0,
        last_synced_at=page.last_synced_at,
        last_webhook_at=page.last_webhook_at,
        error_message=page.error_message,
        created_at=page.created_at,
        updated_at=page.updated_at
    )

def _log_hub_event(db: Session, event_type: str, status_val: str, message: str):
    try:
        from datetime import datetime
        log = IntegrationLog(
            integration_type="META",
            event_type=event_type,
            status=status_val,
            message=message,
            created_at=datetime.utcnow()
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to write integration log: {e}")

@router.get("/webhook")
def verify_meta_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge")
):
    """
    Meta Webhook Verification Endpoint (GET).
    Called by Meta Developer platform when configuring Webhook subscriptions.
    Compares hub.verify_token against configured META_VERIFY_TOKEN.
    """
    expected_verify_token = MetaConfig.get_verify_token()

    if hub_mode == "subscribe" and hub_verify_token == expected_verify_token:
        logger.info(f"Meta webhook challenge verified successfully for token: {hub_verify_token}")
        return Response(content=hub_challenge, media_type="text/plain", status_code=200)

    logger.warning(f"Meta webhook verification failed! Received token: {hub_verify_token}, expected: {expected_verify_token}")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch."
    )

@router.post("/webhook")
async def receive_meta_leadgen_webhook(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Meta Leadgen Webhook Endpoint (POST).
    Receives real-time leadgen event notifications from Facebook Lead Ads.
    Identifies the Facebook Page ID and uses that Page's specific Access Token
    to fetch the lead details from Meta Graph API.
    """
    logger.info(f"Received Meta webhook payload: {payload}")

    entries = payload.get("entry", [])
    processed_leads = []

    for entry in entries:
        entry_page_id = str(entry.get("id") or "")
        changes = entry.get("changes", [])
        for change in changes:
            val = change.get("value", {})
            leadgen_id = str(val.get("leadgen_id") or "")
            form_id = str(val.get("form_id") or "")
            # Page ID can be inside change value or entry level
            page_id = str(val.get("page_id") or entry_page_id or "")

            if leadgen_id:
                lead = MetaLeadService.process_and_save_meta_lead(
                    db=db,
                    leadgen_id=leadgen_id,
                    form_id=form_id,
                    page_id=page_id
                )
                processed_leads.append({
                    "lead_id": lead.id,
                    "meta_lead_id": leadgen_id,
                    "page_id": page_id
                })

    _log_hub_event(
        db=db,
        event_type="WEBHOOK_RECEIVED",
        status_val="SUCCESS" if processed_leads else "INFO",
        message=f"Meta webhook processed {len(processed_leads)} leads across connected pages."
    )

    return {
        "status": "success",
        "processed_count": len(processed_leads),
        "processed_leads": processed_leads
    }

# ------------------------------------------------------------------------------
# MULTI-PAGE MANAGEMENT ENDPOINTS
# ------------------------------------------------------------------------------

@router.get("/pages", response_model=List[MetaPageOut])
def list_meta_pages(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    """
    Retrieves all connected Facebook Pages with masked tokens, status, and lead counters.
    """
    pages = MetaLeadService.get_all_pages(db)
    return [_to_page_out(p) for p in pages]

@router.post("/pages", response_model=MetaPageActionResponse)
def connect_new_meta_page(
    payload: MetaPageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    """
    Connects a new Facebook Page, securely storing its encrypted Page Access Token.
    Validates token with Meta Graph API.
    """
    success, msg, page, err_detail = MetaLeadService.connect_or_add_page(
        db=db,
        page_id=payload.page_id,
        access_token=payload.access_token,
        page_name=payload.page_name
    )

    _log_hub_event(
        db=db,
        event_type="PAGE_CONNECTED",
        status_val="SUCCESS" if success else "WARNING",
        message=f"Admin {current_user.username} added Facebook Page ID {payload.page_id}: {msg}"
    )

    return MetaPageActionResponse(
        success=success,
        message=msg,
        page=_to_page_out(page) if page else None,
        error_details=err_detail
    )

@router.post("/pages/{page_id}/sync", response_model=MetaPageActionResponse)
def sync_meta_page(
    page_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    """
    Synchronizes / tests connection for a specific connected Page independently.
    """
    success, msg, page, err_detail = MetaLeadService.sync_page(db=db, page_id=page_id)

    _log_hub_event(
        db=db,
        event_type="PAGE_SYNC",
        status_val="SUCCESS" if success else "ERROR",
        message=f"Page sync triggered for {page_id} by {current_user.username}: {msg}"
    )

    return MetaPageActionResponse(
        success=success,
        message=msg,
        page=_to_page_out(page) if page else None,
        error_details=err_detail
    )

@router.post("/pages/{page_id}/connect", response_model=MetaPageActionResponse)
def reconnect_meta_page(
    page_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    """
    Activates / reconnects a previously disconnected Facebook Page.
    """
    success, msg, page = MetaLeadService.reconnect_page(db=db, page_id=page_id)
    if not success:
        raise HTTPException(status_code=404, detail=msg)

    _log_hub_event(
        db=db,
        event_type="PAGE_CONNECTED",
        status_val="SUCCESS",
        message=f"Page {page_id} reconnected by {current_user.username}."
    )

    return MetaPageActionResponse(
        success=True,
        message=msg,
        page=_to_page_out(page) if page else None
    )

@router.post("/pages/{page_id}/disconnect", response_model=MetaPageActionResponse)
def disconnect_meta_page(
    page_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    """
    Disconnects a Facebook Page independently (pauses lead retrieval).
    """
    success, msg, page = MetaLeadService.disconnect_page(db=db, page_id=page_id)
    if not success:
        raise HTTPException(status_code=404, detail=msg)

    _log_hub_event(
        db=db,
        event_type="PAGE_DISCONNECTED",
        status_val="WARNING",
        message=f"Page {page_id} disconnected by {current_user.username}."
    )

    return MetaPageActionResponse(
        success=True,
        message=msg,
        page=_to_page_out(page) if page else None
    )

@router.post("/pages/{page_id}/refresh", response_model=MetaPageActionResponse)
def refresh_meta_page(
    page_id: str,
    payload: MetaPageRefresh,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    """
    Refreshes a Page independently, optionally updating the Page Access Token.
    """
    success, msg, page, err_detail = MetaLeadService.refresh_page(
        db=db,
        page_id=page_id,
        new_access_token=payload.access_token
    )

    _log_hub_event(
        db=db,
        event_type="PAGE_REFRESHED",
        status_val="SUCCESS" if success else "ERROR",
        message=f"Page {page_id} refreshed by {current_user.username}: {msg}"
    )

    return MetaPageActionResponse(
        success=success,
        message=msg,
        page=_to_page_out(page) if page else None,
        error_details=err_detail
    )

@router.delete("/pages/{page_id}")
def delete_meta_page(
    page_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    """
    Deletes a connected Facebook Page from the CRM.
    """
    deleted = MetaLeadService.delete_page(db=db, page_id=page_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Page ID '{page_id}' not found.")

    _log_hub_event(
        db=db,
        event_type="PAGE_DELETED",
        status_val="WARNING",
        message=f"Admin {current_user.username} deleted Facebook Page ID {page_id}."
    )

    return {"success": True, "message": f"Facebook Page ID '{page_id}' has been removed."}

# ------------------------------------------------------------------------------
# OVERALL STATUS ENDPOINT
# ------------------------------------------------------------------------------

@router.get("/status", response_model=MetaIntegrationStatusResponse)
def get_meta_integration_status(db: Session = Depends(get_db)):
    """
    Returns Meta Integration Status details, including connected pages summary.
    """
    pages = MetaLeadService.get_all_pages(db)
    connected_pages = [p for p in pages if p.status == "CONNECTED"]

    app_id = MetaConfig.get_app_id()
    version = MetaConfig.get_api_version()
    meta_leads_count = db.query(Lead).filter(Lead.source.in_(["META", "Meta Ads"])).count()

    last_wh = MetaLeadService.get_last_webhook_time()
    last_sync = MetaLeadService.get_last_sync_time()

    is_configured = len(pages) > 0 or MetaConfig.is_configured()

    return MetaIntegrationStatusResponse(
        configured=is_configured,
        status="CONNECTED" if len(connected_pages) > 0 else ("NOT_CONNECTED" if not pages else "DISCONNECTED"),
        page_id=connected_pages[0].page_id if connected_pages else (pages[0].page_id if pages else None),
        app_id=app_id if app_id else None,
        api_version=version,
        total_meta_leads=meta_leads_count,
        total_pages_connected=len(connected_pages),
        pages=[_to_page_out(p) for p in pages],
        last_webhook_received=last_wh,
        last_sync=last_sync,
        message=f"Meta Ads active with {len(connected_pages)} connected Facebook Page(s)." if connected_pages else "No active Facebook Pages connected. Connect your Pages in Integration Hub."
    )
