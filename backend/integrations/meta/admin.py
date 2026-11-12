"""Admin API for Facebook & Instagram Lead Ads.

Routes:
  * official Meta OAuth start/callback (signed stateless state),
  * connection status / disconnect / auto-sync,
  * Page and Lead Form discovery/selection/subscription,
  * historical imports with progress,
  * dashboard, activity log and failed-lead retries.

Only ADMIN users can change the integration; ADMIN and MANAGER can read it.
Access tokens are never returned to the browser.
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.meta_connection import MetaConnection
from models.meta_page import MetaPage
from models.user import User
from services.auth import require_roles

from .config import MetaConfig
from .schemas import (
    MetaAutoSyncUpdate,
    MetaFormsSelectionUpdate,
    MetaImportRequest,
    MetaPageSelectionUpdate,
)
from .service import MetaGraphError, MetaLeadService

logger = logging.getLogger("meta_admin")

router = APIRouter(prefix="/integrations/meta", tags=["Meta Lead Ads Admin"])

OAUTH_STATE_TTL_SECONDS = 600


# ------------------------------------------------------------------------------
# Signed OAuth state
# ------------------------------------------------------------------------------
def _state_secret() -> str:
    return MetaConfig.get_app_secret() or settings.SECRET_KEY


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_oauth_state(user: User, redirect_uri: str, frontend_uri: str) -> str:
    payload = {
        "uid": user.id,
        "username": user.username,
        "exp": int(time.time()) + OAUTH_STATE_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(16),
        "redirect_uri": redirect_uri,
        "frontend": frontend_uri,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        _state_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{body}.{signature}"


def verify_oauth_state(state: Optional[str]) -> Optional[Dict[str, Any]]:
    if not state or "." not in state:
        return None
    body, signature = state.rsplit(".", 1)
    expected = hmac.new(
        _state_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        payload = json.loads(_b64decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if int(payload.get("exp") or 0) < int(time.time()):
        return None
    if not payload.get("uid"):
        return None
    frontend = str(payload.get("frontend") or "")
    parsed = urlparse(frontend)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return payload


def _frontend_redirect(frontend_uri: str, **params) -> RedirectResponse:
    query = urlencode({k: v for k, v in params.items() if v not in (None, "")})
    separator = "&" if "?" in frontend_uri else "?"
    return RedirectResponse(
        url=f"{frontend_uri}{separator}{query}" if query else frontend_uri,
        status_code=status.HTTP_302_FOUND,
    )


def _oauth_error(message: str) -> str:
    safe = str(message or "Meta connection failed.").replace("\n", " ")[:300]
    return safe


# ------------------------------------------------------------------------------
# OAuth
# ------------------------------------------------------------------------------
@router.get("/oauth/start")
def start_meta_oauth(
    request: Request,
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Build the official Meta OAuth dialog URL for the current admin."""
    if not MetaConfig.oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "META_APP_ID and META_APP_SECRET must be configured on the server "
                "before Facebook can be connected."
            ),
        )
    redirect_uri = MetaConfig.get_oauth_redirect_uri()
    frontend_uri = MetaConfig.get_frontend_redirect_uri()
    state = create_oauth_state(current_user, redirect_uri, frontend_uri)
    params = {
        "client_id": MetaConfig.get_app_id(),
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": MetaConfig.get_oauth_scopes(),
        "response_type": "code",
    }
    authorize_url = (
        f"https://www.facebook.com/{MetaConfig.get_api_version()}/dialog/oauth?"
        + urlencode(params)
    )
    return {
        "authorize_url": authorize_url,
        "redirect_uri": redirect_uri,
        "scopes": [s for s in MetaConfig.get_oauth_scopes().split(",") if s],
        "api_version": MetaConfig.get_api_version(),
    }


@router.get("/oauth/callback")
def meta_oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Meta redirects here after authorization. Never exposes tokens."""
    state_data = verify_oauth_state(state)
    if not state_data:
        logger.warning("Meta OAuth callback rejected: invalid/expired state.")
        return _frontend_redirect(
            MetaConfig.get_frontend_redirect_uri(),
            meta_oauth="error",
            message="OAuth state validation failed or expired. Please try connecting again.",
        )

    frontend_uri = str(state_data["frontend"])
    if error:
        logger.warning("Meta OAuth denied: %s", error)
        MetaLeadService.log_activity(
            db, "OAUTH_FAILED", "ERROR",
            f"Meta OAuth was not completed: {_oauth_error(error_description or error)}",
        )
        return _frontend_redirect(
            frontend_uri,
            meta_oauth="error",
            message=_oauth_error(error_description or error),
        )

    if not code:
        return _frontend_redirect(
            frontend_uri,
            meta_oauth="error",
            message="Meta did not return an authorization code.",
        )

    # Confirm the admin still exists and is authorised.
    user = db.query(User).filter(User.id == int(state_data["uid"])).first()
    if not user or (user.role or "").upper() != "ADMIN":
        return _frontend_redirect(
            frontend_uri,
            meta_oauth="error",
            message="The administrator account is no longer authorized.",
        )

    try:
        token_data = MetaLeadService.exchange_oauth_code(
            code=code,
            redirect_uri=str(state_data.get("redirect_uri") or MetaConfig.get_oauth_redirect_uri()),
        )
        connection = MetaLeadService.save_oauth_connection(db, token_data, user.id)
        MetaLeadService.log_activity(
            db, "OAUTH_CONNECTED", "SUCCESS",
            f"Facebook account '{connection.fb_user_name or connection.fb_user_id}' connected by {user.username}.",
        )
        try:
            summary = MetaLeadService.sync_connection_assets(db, connection, fetch_forms=True)
            message = (
                f"Connected. Discovered {summary['pages']} Page(s) and "
                f"{summary['forms']} Lead Form(s)."
            )
        except MetaGraphError as exc:
            message = (
                "Facebook account connected, but asset discovery needs attention: "
                f"{exc.message}"
            )
            logger.warning("Post-OAuth asset sync failed: %s", exc.message)
        return _frontend_redirect(
            frontend_uri, meta_oauth="success", message=message[:300]
        )
    except MetaGraphError as exc:
        logger.error("Meta OAuth token exchange failed: %s", exc.message)
        MetaLeadService.log_activity(
            db, "OAUTH_FAILED", "ERROR", f"Token exchange failed: {exc.message}"
        )
        return _frontend_redirect(
            frontend_uri,
            meta_oauth="error",
            message=_oauth_error(exc.message),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected Meta OAuth callback failure")
        return _frontend_redirect(
            frontend_uri,
            meta_oauth="error",
            message="Unexpected server error while completing Meta authorization.",
        )


# ------------------------------------------------------------------------------
# Connection / settings
# ------------------------------------------------------------------------------
@router.get("/connection")
def get_meta_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    dashboard = MetaLeadService.get_dashboard(db)
    return {
        "configured": dashboard["configured"],
        "oauth_configured": MetaConfig.oauth_configured(),
        "app_id": dashboard["app_id"],
        "api_version": dashboard["api_version"],
        "webhook_url": dashboard["webhook_url"],
        "webhook_status": dashboard["webhook_status"],
        "connection": dashboard["connection"],
        "token": dashboard["token"],
        "stats": dashboard["stats"],
        "required_scopes": [s for s in MetaConfig.get_oauth_scopes().split(",") if s],
    }


@router.post("/connection/disconnect")
def disconnect_meta_connection(
    revoke_permissions: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    connection = MetaLeadService.get_connection(db)
    if not connection:
        raise HTTPException(status_code=404, detail="No Facebook connection found.")
    success, message = MetaLeadService.disconnect_connection(
        db, connection, also_revoke=revoke_permissions
    )
    return {"success": success, "message": message}


@router.post("/connection/auto-sync")
def set_meta_auto_sync(
    payload: MetaAutoSyncUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    connection = MetaLeadService.get_connection(db)
    if not connection:
        raise HTTPException(status_code=404, detail="No Facebook connection found.")
    connection.auto_sync_enabled = bool(payload.enabled)
    connection.updated_at = datetime.utcnow()
    db.commit()
    MetaLeadService.log_activity(
        db,
        "AUTO_SYNC_" + ("ENABLED" if payload.enabled else "DISABLED"),
        "SUCCESS",
        f"Auto Sync {'enabled' if payload.enabled else 'disabled'} by {current_user.username}.",
    )
    return {
        "success": True,
        "enabled": bool(connection.auto_sync_enabled),
        "message": f"Auto Sync {'enabled' if payload.enabled else 'disabled'}.",
    }


@router.post("/sync-now")
def sync_meta_now(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    try:
        summary = MetaLeadService.sync_now(db)
    except MetaGraphError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    MetaLeadService.log_activity(
        db,
        "SYNC_NOW",
        "SUCCESS",
        f"Manual Sync Now completed by {current_user.username}: {summary}",
    )
    return {"success": True, "message": "Sync completed.", "summary": summary}


# ------------------------------------------------------------------------------
# Pages / Instagram assets
# ------------------------------------------------------------------------------
@router.get("/assets/pages")
def list_assets(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    pages = MetaLeadService.get_dashboard(db)["pages"]
    return {"pages": pages}


@router.post("/pages/{page_id}/select")
def select_page(
    page_id: str,
    payload: MetaPageSelectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    page = MetaLeadService.get_page_by_id(db, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found.")
    page.is_selected = bool(payload.selected)
    if payload.auto_sync_enabled is not None:
        page.auto_sync_enabled = bool(payload.auto_sync_enabled)
    page.updated_at = datetime.utcnow()
    db.commit()

    subscription = None
    if page.is_selected:
        ok, message = MetaLeadService.subscribe_page(db, page)
        subscription = {"success": ok, "message": message}
    MetaLeadService.log_activity(
        db,
        "PAGE_SELECTED" if page.is_selected else "PAGE_DESELECTED",
        "SUCCESS",
        f"Page '{page.page_name}' {'selected' if page.is_selected else 'deselected'} by {current_user.username}.",
    )
    return {
        "success": True,
        "page_id": page.page_id,
        "is_selected": bool(page.is_selected),
        "auto_sync_enabled": bool(page.auto_sync_enabled),
        "subscription": subscription,
    }


@router.post("/pages/{page_id}/auto-sync")
def set_page_auto_sync(
    page_id: str,
    payload: MetaAutoSyncUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    page = MetaLeadService.get_page_by_id(db, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found.")
    page.auto_sync_enabled = bool(payload.enabled)
    page.updated_at = datetime.utcnow()
    db.commit()
    MetaLeadService.log_activity(
        db,
        "PAGE_AUTO_SYNC_" + ("ENABLED" if payload.enabled else "DISABLED"),
        "SUCCESS",
        f"Page '{page.page_name}' Auto Sync {'enabled' if payload.enabled else 'disabled'} by {current_user.username}.",
    )
    return {"success": True, "enabled": bool(page.auto_sync_enabled)}


@router.post("/pages/{page_id}/subscribe")
def subscribe_page(
    page_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    page = MetaLeadService.get_page_by_id(db, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found.")
    ok, message = MetaLeadService.subscribe_page(db, page)
    MetaLeadService.log_activity(
        db,
        "PAGE_SUBSCRIBED",
        "SUCCESS" if ok else "ERROR",
        f"Webhook subscription for '{page.page_name}' requested by {current_user.username}: {message}",
    )
    return {"success": ok, "message": message, "webhook_subscribed": bool(page.webhook_subscribed)}


@router.post("/pages/{page_id}/forms/sync")
def sync_forms(
    page_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    page = MetaLeadService.get_page_by_id(db, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found.")
    try:
        forms = MetaLeadService.sync_page_forms(db, page)
    except MetaGraphError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    MetaLeadService.log_activity(
        db,
        "FORMS_SYNCED",
        "SUCCESS",
        f"{len(forms)} Lead Form(s) refreshed for '{page.page_name}' by {current_user.username}.",
    )
    return {
        "success": True,
        "count": len(forms),
        "forms": [
            {
                "form_id": f.form_id,
                "name": f.name,
                "status": f.status,
                "is_selected": bool(f.is_selected),
                "leads_count": f.leads_count or 0,
            }
            for f in forms
        ],
    }


# ------------------------------------------------------------------------------
# Lead Forms
# ------------------------------------------------------------------------------
@router.get("/forms")
def list_forms(
    page_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    forms = MetaLeadService.get_forms(db, page_id=page_id)
    page_names = {p.page_id: p.page_name for p in db.query(MetaPage).all()}
    return {
        "forms": [
            {
                "id": f.id,
                "form_id": f.form_id,
                "page_id": f.page_id,
                "page_name": page_names.get(f.page_id),
                "name": f.name,
                "status": f.status,
                "locale": f.locale,
                "is_selected": bool(f.is_selected),
                "leads_count": f.leads_count or 0,
                "last_lead_at": f.last_lead_at.isoformat() if f.last_lead_at else None,
                "last_synced_at": f.last_synced_at.isoformat() if f.last_synced_at else None,
            }
            for f in forms
        ]
    }


@router.post("/forms/selection")
def update_forms_selection(
    payload: MetaFormsSelectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    form_ids = list(payload.form_ids or [])
    if payload.select_all_for_page:
        if not payload.page_id:
            raise HTTPException(
                status_code=400,
                detail="page_id is required when select_all_for_page is true.",
            )
        form_ids = [
            f.form_id
            for f in MetaLeadService.get_forms(db, page_id=payload.page_id)
        ]
    updated = MetaLeadService.set_forms_selection(
        db, form_ids=form_ids, selected=bool(payload.selected)
    )
    MetaLeadService.log_activity(
        db,
        "FORMS_SELECTION_UPDATED",
        "SUCCESS",
        f"{updated} Lead Form(s) {'selected' if payload.selected else 'deselected'} by {current_user.username}.",
    )
    return {
        "success": True,
        "updated": updated,
        "selected": bool(payload.selected),
    }


# ------------------------------------------------------------------------------
# Historical import
# ------------------------------------------------------------------------------
@router.post("/import")
def start_historical_import(
    payload: MetaImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    try:
        job = MetaLeadService.create_import_job(
            db=db,
            user_id=current_user.id,
            preset=payload.range,
            since=payload.since,
            until=payload.until,
            page_ids=payload.page_ids,
            form_ids=payload.form_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MetaGraphError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    MetaLeadService.start_import_job(job.id)
    return {
        "success": True,
        "message": "Historical import started.",
        "job": MetaLeadService.get_import_job(db, job.id),
    }


@router.get("/import/jobs")
def list_import_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    return {"jobs": MetaLeadService.list_import_jobs(db, limit=limit)}


@router.get("/import/jobs/{job_id}")
def get_import_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    job = MetaLeadService.get_import_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found.")
    return {"job": job}


@router.post("/import/jobs/{job_id}/cancel")
def cancel_import_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    ok, message = MetaLeadService.cancel_import_job(db, job_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


# ------------------------------------------------------------------------------
# Events / failed lead retries
# ------------------------------------------------------------------------------
@router.get("/events")
def list_lead_events(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    return {
        "events": MetaLeadService.list_events(
            db, status_filter=status_filter, limit=limit
        )
    }


@router.post("/events/retry-failed")
def retry_failed_lead_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    count = MetaLeadService.retry_failed_events(db)
    MetaLeadService.log_activity(
        db,
        "RETRY_FAILED_LEADS",
        "SUCCESS" if count else "INFO",
        f"{count} failed Meta lead event(s) reset for retry by {current_user.username}.",
    )
    return {
        "success": True,
        "reset": count,
        "message": (
            f"{count} failed lead(s) queued for retry."
            if count
            else "No failed leads to retry."
        ),
    }


@router.post("/events/{event_id}/retry")
def retry_lead_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    ok, message = MetaLeadService.retry_event(db, event_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


# ------------------------------------------------------------------------------
# Dashboard / activity
# ------------------------------------------------------------------------------
@router.get("/dashboard")
def get_meta_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    return MetaLeadService.get_dashboard(db)


@router.get("/activity")
def get_meta_activity(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    return {"activity": MetaLeadService.get_activity_log(db, limit=limit)}
