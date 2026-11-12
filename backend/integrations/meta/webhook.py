"""Meta Lead Ads webhook + legacy multi-Page management endpoints.

The webhook receiver now:
  * verifies ``X-Hub-Signature-256`` against the raw body and fails closed,
  * validates the Page, selected Lead Form and Auto Sync flags,
  * stores every leadgen event in ``meta_lead_events`` for idempotency,
  * processes the lead immediately and leaves failures for the background
    retry worker (``MetaLeadService.start_meta_lead_worker``).

All existing manual Page management endpoints remain available for backward
compatibility and are still protected by ADMIN/MANAGER roles.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from database import get_db
from models.lead import Lead
from models.meta_connection import MetaLeadEvent
from models.meta_page import MetaPage
from models.user import User
from services.auth import require_roles

from .config import MetaConfig
from .crypto import decrypt_token, mask_token
from .schemas import (
    MetaIntegrationStatusResponse,
    MetaPageActionResponse,
    MetaPageCreate,
    MetaPageOut,
    MetaPageRefresh,
)
from .service import META_SOURCE_VALUES, MetaLeadService, verify_webhook_signature

logger = logging.getLogger("meta_webhook")

router = APIRouter(prefix="/integrations/meta", tags=["Meta Lead Ads Integration"])


def _to_page_out(page: MetaPage, db: Optional[Session] = None) -> MetaPageOut:
    plain = decrypt_token(page.encrypted_access_token)
    form_count = 0
    selected_form_count = 0
    if db is not None:
        from models.meta_connection import MetaLeadForm

        form_count = (
            db.query(MetaLeadForm).filter(MetaLeadForm.page_id == page.page_id).count()
        )
        selected_form_count = (
            db.query(MetaLeadForm)
            .filter(
                MetaLeadForm.page_id == page.page_id,
                MetaLeadForm.is_selected.is_(True),
            )
            .count()
        )
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
        updated_at=page.updated_at,
        connection_id=page.connection_id,
        page_picture_url=page.page_picture_url,
        instagram_account_id=page.instagram_account_id,
        instagram_username=page.instagram_username,
        is_selected=bool(page.is_selected),
        auto_sync_enabled=bool(page.auto_sync_enabled),
        webhook_subscribed=bool(page.webhook_subscribed),
        token_expires_at=page.token_expires_at,
        forms_last_synced_at=page.forms_last_synced_at,
        last_lead_at=page.last_lead_at,
        last_error_code=page.last_error_code,
        form_count=form_count,
        selected_form_count=selected_form_count,
    )


def _log_hub_event(db: Session, event_type: str, status_val: str, message: str):
    MetaLeadService.log_activity(db, event_type, status_val, message)


@router.get("/webhook")
def verify_meta_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification endpoint (GET)."""
    expected_verify_token = MetaConfig.get_verify_token()
    if hub_mode == "subscribe" and hub_verify_token == expected_verify_token:
        logger.info("Meta webhook challenge verified successfully.")
        return Response(content=hub_challenge or "", media_type="text/plain", status_code=200)

    # Never echo the expected token in logs.
    logger.warning("Meta webhook verification failed (token mismatch).")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch.",
    )


@router.post("/webhook")
async def receive_meta_leadgen_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Signed receiver for Facebook & Instagram Instant Form leads."""
    raw_body = await request.body()

    if not MetaConfig.signature_verification_configured():
        logger.error(
            "Meta webhook rejected because META_APP_SECRET is not configured."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook signature verification is not configured.",
        )

    signature = request.headers.get("x-hub-signature-256")
    if not verify_webhook_signature(raw_body, signature):
        logger.warning("Rejected Meta webhook with missing/invalid signature.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-Hub-Signature-256.",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        )

    if payload.get("object") not in (None, "page"):
        logger.info("Ignoring non-Page Meta webhook object: %s", payload.get("object"))
        return {"status": "ignored"}

    connection = MetaLeadService.get_connection(db)
    summary = {
        "received": 0,
        "processed": 0,
        "duplicates": 0,
        "ignored": 0,
        "failed": 0,
        "queued": 0,
    }

    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        entry_page_id = str(entry.get("id") or "").strip()
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            if change.get("field") not in (None, "leadgen"):
                continue
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue
            leadgen_id = str(value.get("leadgen_id") or "").strip()
            if not leadgen_id:
                continue
            summary["received"] += 1
            page_id = str(value.get("page_id") or entry_page_id or "").strip()
            form_id = str(value.get("form_id") or "").strip() or None

            event, duplicate = MetaLeadService.create_event(
                db=db,
                leadgen_id=leadgen_id,
                page_id=page_id,
                form_id=form_id,
                payload=value,
                platform=str(value.get("platform") or "") or None,
            )
            if duplicate and event.status in {"PROCESSED", "DUPLICATE"}:
                summary["duplicates"] += 1
                continue

            # Validate CRM-side configuration before touching Graph API.
            page = MetaLeadService.get_page_by_id(db, page_id) if page_id else None
            ignore_reason = None
            if not page:
                # Legacy env-only Page configuration is still supported.
                if not (page_id and page_id == MetaConfig.get_page_id()):
                    event.status = "FAILED"
                    event.last_error = (
                        f"Page {page_id or '(unknown)'} is not connected in CHN CRM. "
                        "Connect it from Settings → Integrations → Facebook & Instagram."
                    )
                    event.next_retry_at = None
                    event.updated_at = datetime.utcnow()
                    db.commit()
                    summary["failed"] += 1
                    continue
            else:
                if not page.is_selected:
                    ignore_reason = "Page is not selected for Auto Sync in CHN CRM."
                elif page.status == "DISCONNECTED":
                    ignore_reason = "Page is disconnected in CHN CRM."
                elif page.status == "ACCESS_REMOVED":
                    ignore_reason = "Page access was removed in Meta Business Manager."
                elif not page.auto_sync_enabled:
                    ignore_reason = "Auto Sync is disabled for this Page."
                elif connection and not connection.auto_sync_enabled:
                    ignore_reason = "Auto Sync is disabled for the Facebook connection."

                if not ignore_reason and form_id:
                    from models.meta_connection import MetaLeadForm

                    form = (
                        db.query(MetaLeadForm)
                        .filter(MetaLeadForm.form_id == form_id)
                        .first()
                    )
                    if form and not form.is_selected:
                        ignore_reason = (
                            f"Lead Form '{form.name or form_id}' is not selected for sync."
                        )

            if ignore_reason:
                event.status = "IGNORED"
                event.last_error = ignore_reason
                event.processed_at = datetime.utcnow()
                event.updated_at = datetime.utcnow()
                db.commit()
                summary["ignored"] += 1
                continue

            try:
                # Graph API + DB work is synchronous; run it in the threadpool
                # so one slow Meta response cannot block the event loop.
                result = await run_in_threadpool(
                    MetaLeadService.process_lead_event, db, event
                )
            except Exception as exc:  # keep Meta retries safe
                db.rollback()
                logger.error("Meta webhook event processing crashed: %s", exc)
                result = "FAILED"

            if result == "PROCESSED":
                summary["processed"] += 1
            elif result == "DUPLICATE":
                summary["duplicates"] += 1
            elif result == "IGNORED":
                summary["ignored"] += 1
            else:
                summary["failed"] += 1
                summary["queued"] += 1

    try:
        MetaLeadService.log_activity(
            db,
            "WEBHOOK_RECEIVED",
            "SUCCESS" if not summary["failed"] else "WARNING",
            (
                "Meta webhook: "
                f"{summary['received']} received, {summary['processed']} processed, "
                f"{summary['duplicates']} duplicate(s), {summary['ignored']} ignored, "
                f"{summary['failed']} queued for retry."
            ),
        )
    except Exception as exc:
        logger.error("Failed to write Meta webhook activity log: %s", exc)
        db.rollback()

    return {"status": "received", **summary}


# ------------------------------------------------------------------------------
# MULTI-PAGE MANAGEMENT ENDPOINTS (legacy manual flow, still supported)
# ------------------------------------------------------------------------------

@router.get("/pages", response_model=List[MetaPageOut])
def list_meta_pages(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    """Retrieves all connected Facebook Pages with masked tokens and counters."""
    pages = MetaLeadService.get_all_pages(db)
    return [_to_page_out(p, db) for p in pages]


@router.post("/pages", response_model=MetaPageActionResponse)
def connect_new_meta_page(
    payload: MetaPageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    success, msg, page, err_detail = MetaLeadService.connect_or_add_page(
        db=db,
        page_id=payload.page_id,
        access_token=payload.access_token,
        page_name=payload.page_name,
    )
    _log_hub_event(
        db,
        "PAGE_CONNECTED",
        "SUCCESS" if success else "WARNING",
        f"Admin {current_user.username} added Facebook Page ID {payload.page_id}: {msg}",
    )
    return MetaPageActionResponse(
        success=success,
        message=msg,
        page=_to_page_out(page, db) if page else None,
        error_details=err_detail,
    )


@router.post("/pages/{page_id}/sync", response_model=MetaPageActionResponse)
def sync_meta_page(
    page_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    success, msg, page, err_detail = MetaLeadService.sync_page(db=db, page_id=page_id)
    _log_hub_event(
        db,
        "PAGE_SYNC",
        "SUCCESS" if success else "ERROR",
        f"Page sync triggered for {page_id} by {current_user.username}: {msg}",
    )
    return MetaPageActionResponse(
        success=success,
        message=msg,
        page=_to_page_out(page, db) if page else None,
        error_details=err_detail,
    )


@router.post("/pages/{page_id}/connect", response_model=MetaPageActionResponse)
def reconnect_meta_page(
    page_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    success, msg, page = MetaLeadService.reconnect_page(db=db, page_id=page_id)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    _log_hub_event(
        db,
        "PAGE_CONNECTED",
        "SUCCESS",
        f"Page {page_id} reconnected by {current_user.username}.",
    )
    return MetaPageActionResponse(
        success=True,
        message=msg,
        page=_to_page_out(page, db) if page else None,
    )


@router.post("/pages/{page_id}/disconnect", response_model=MetaPageActionResponse)
def disconnect_meta_page(
    page_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    success, msg, page = MetaLeadService.disconnect_page(db=db, page_id=page_id)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    _log_hub_event(
        db,
        "PAGE_DISCONNECTED",
        "WARNING",
        f"Page {page_id} disconnected by {current_user.username}.",
    )
    return MetaPageActionResponse(
        success=True,
        message=msg,
        page=_to_page_out(page, db) if page else None,
    )


@router.post("/pages/{page_id}/refresh", response_model=MetaPageActionResponse)
def refresh_meta_page(
    page_id: str,
    payload: MetaPageRefresh,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    success, msg, page, err_detail = MetaLeadService.refresh_page(
        db=db,
        page_id=page_id,
        new_access_token=payload.access_token,
    )
    _log_hub_event(
        db,
        "PAGE_REFRESHED",
        "SUCCESS" if success else "ERROR",
        f"Page {page_id} refreshed by {current_user.username}: {msg}",
    )
    return MetaPageActionResponse(
        success=success,
        message=msg,
        page=_to_page_out(page, db) if page else None,
        error_details=err_detail,
    )


@router.delete("/pages/{page_id}")
def delete_meta_page(
    page_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    deleted = MetaLeadService.delete_page(db=db, page_id=page_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Page ID '{page_id}' not found.")
    _log_hub_event(
        db,
        "PAGE_DELETED",
        "WARNING",
        f"Admin {current_user.username} deleted Facebook Page ID {page_id}.",
    )
    return {"success": True, "message": f"Facebook Page ID '{page_id}' has been removed."}


# ------------------------------------------------------------------------------
# OVERALL STATUS ENDPOINT (legacy)
# ------------------------------------------------------------------------------

@router.get("/status", response_model=MetaIntegrationStatusResponse)
def get_meta_integration_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    pages = MetaLeadService.get_all_pages(db)
    connected_pages = [p for p in pages if p.status == "CONNECTED"]
    app_id = MetaConfig.get_app_id()
    version = MetaConfig.get_api_version()
    meta_leads_count = (
        db.query(Lead).filter(Lead.source.in_(META_SOURCE_VALUES)).count()
    )
    last_wh = MetaLeadService.get_last_webhook_time()
    last_sync = MetaLeadService.get_last_sync_time()
    is_configured = len(pages) > 0 or MetaConfig.is_configured()

    return MetaIntegrationStatusResponse(
        configured=is_configured,
        status=(
            "CONNECTED"
            if connected_pages
            else ("NOT_CONNECTED" if not pages else "DISCONNECTED")
        ),
        page_id=(
            connected_pages[0].page_id
            if connected_pages
            else (pages[0].page_id if pages else None)
        ),
        app_id=app_id if app_id else None,
        api_version=version,
        total_meta_leads=meta_leads_count,
        total_pages_connected=len(connected_pages),
        pages=[_to_page_out(p, db) for p in pages],
        last_webhook_received=last_wh,
        last_sync=last_sync,
        message=(
            f"Meta Lead Ads active with {len(connected_pages)} connected Page(s)."
            if connected_pages
            else "No active Facebook Pages connected. Connect your Pages in Integration Hub."
        ),
    )
