"""Dedicated Meta Click-to-WhatsApp webhook (verification + signed receiver)."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from database import get_db

from .config import WhatsAppAdConfig
from .service import WhatsAppAdLeadService, verify_challenge, verify_signature

logger = logging.getLogger("whatsapp_ads.webhook")

router = APIRouter(tags=["WhatsApp Ad Leads Webhook"])


@router.get("/webhook/whatsapp")
def verify_whatsapp_ad_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """
    Meta webhook verification.

    Configure this exact URL (plus the same URL under /api) as the WhatsApp
    Business Account callback URL and use WHATSAPP_AD_VERIFY_TOKEN as the
    verify token.
    """
    if not verify_challenge(hub_mode, hub_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook verification failed. Token mismatch.",
        )
    return PlainTextResponse(content=hub_challenge or "", status_code=200)


@router.post("/webhook/whatsapp")
async def receive_whatsapp_ad_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Signed receiver for Cloud API message + referral events.

    Only messages that carry a Click-to-WhatsApp `referral` object create
    leads. Delivery/read status events are ignored for lead creation and are
    only mirrored to the existing WhatsApp inbox.
    """
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    if not WhatsAppAdConfig.signature_verification_configured():
        logger.error(
            "WhatsApp Ad webhook rejected because no app secret is configured."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook signature verification is not configured.",
        )

    if not verify_signature(raw_body, signature):
        logger.warning("Rejected WhatsApp Ad webhook with invalid signature.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-Hub-Signature-256.",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Rejected malformed WhatsApp Ad webhook JSON: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        )

    if payload.get("object") not in (None, "whatsapp_business_account"):
        logger.info("Ignoring non-WhatsApp webhook object: %s", payload.get("object"))
        return {"status": "ignored"}

    try:
        summary = WhatsAppAdLeadService.process_payload(db, payload, raw_body)
        return {"status": "received", **summary}
    except Exception as exc:
        db.rollback()
        logger.error("WhatsApp Ad webhook processing failed: %s", exc, exc_info=True)
        # Return 500 so Meta retries. Event-level idempotency makes retries safe.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed.",
        )
