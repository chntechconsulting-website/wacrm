"""Public WA HRMS webhook receiver.

Security order is mandatory and deliberate:
1. read the raw body bytes,
2. verify HMAC-SHA256 over ``{t}.{rawBody}`` with a five-minute window,
3. only then parse JSON,
4. persist the event with its unique ``WAHRMS-Event-Id``,
5. acknowledge immediately and process in the background.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from database import SessionLocal
from integrations.wahrms_channel_partner.config import (
    get_integration_row,
    load_webhook_secret,
)
from integrations.wahrms_channel_partner.normalizers import parse_datetime_ist
from services.channel_partner_sync import (
    mark_event,
    process_webhook_event,
    record_webhook_rejection,
    store_webhook_event,
    verify_webhook_signature,
)
from utils.timezone import get_ist_now

logger = logging.getLogger("wacrm.channel_partner.webhook")

webhook_router = APIRouter(tags=["WA HRMS Channel Partner Webhook"])


def _headers_dict(request: Request) -> Dict[str, str]:
    return {key: value for key, value in request.headers.items()}


@webhook_router.post("/webhooks/wahrms")
async def receive_wahrms_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    signature = request.headers.get("WAHRMS-Signature")
    secret_db = SessionLocal()
    try:
        secret = load_webhook_secret(secret_db)
    finally:
        secret_db.close()

    ok, reason = verify_webhook_signature(raw_body, signature, secret)
    if not ok:
        db = SessionLocal()
        try:
            record_webhook_rejection(
                db,
                reason=reason,
                remote_ip=request.client.host if request.client else None,
                signature_header=signature,
                raw_body=raw_body,
            )
        finally:
            db.close()
        status_code = 503 if reason == "webhook_secret_not_configured" else 400
        logger.warning("Rejected WAHRMS webhook: %s", reason)
        return JSONResponse(
            status_code=status_code,
            content={"status": "rejected", "reason": reason},
        )

    try:
        payload: Any = json.loads(raw_body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse(
            status_code=400, content={"status": "rejected", "reason": "invalid_json"}
        )
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400, content={"status": "rejected", "reason": "invalid_payload"}
        )

    event_id = (
        request.headers.get("WAHRMS-Event-Id")
        or payload.get("id")
    )
    event_type = request.headers.get("WAHRMS-Event") or payload.get("type")
    if not event_id or not event_type:
        return JSONResponse(
            status_code=400,
            content={"status": "rejected", "reason": "missing_event_identity"},
        )

    db = SessionLocal()
    try:
        event, duplicate = store_webhook_event(
            db,
            event_id=str(event_id),
            event_type=str(event_type),
            payload=payload,
            headers=_headers_dict(request),
            created_at=parse_datetime_ist(payload.get("createdAt")) or get_ist_now(),
            source="webhook",
        )
        integration = get_integration_row(db)
        integration.webhook_last_received_at = get_ist_now()
        integration.webhook_last_event_type = str(event_type)[:80]
        db.commit()

        if duplicate:
            return {"status": "duplicate", "eventId": str(event_id)}

        if event is not None:
            background_tasks.add_task(process_webhook_event, event.id)
        return JSONResponse(
            status_code=200,
            content={"status": "accepted", "eventId": str(event_id)},
        )
    except Exception:
        db.rollback()
        logger.exception("Could not persist WAHRMS webhook event")
        return JSONResponse(
            status_code=500, content={"status": "error", "reason": "persistence_failed"}
        )
    finally:
        db.close()
