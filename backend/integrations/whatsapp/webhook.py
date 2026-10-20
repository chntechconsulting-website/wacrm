from fastapi import APIRouter, Depends, Request, Response, Query, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from .service import WhatsAppService

webhook_router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Webhook"])

@webhook_router.get("/webhook")
def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    Webhook verification endpoint for Meta WhatsApp Cloud API.
    Responds with hub.challenge if hub.verify_token matches configured WHATSAPP_VERIFY_TOKEN.
    """
    challenge = WhatsAppService.provider.verify_webhook(hub_mode, hub_token, hub_challenge)
    if challenge:
        return Response(content=challenge, media_type="text/plain", status_code=200)
    raise HTTPException(status_code=403, detail="Webhook verification failed. Token mismatch.")

@webhook_router.post("/webhook")
async def receive_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Inbound webhook receiver for Meta WhatsApp Cloud API events.
    Receives incoming customer messages & delivery/read status updates.
    """
    try:
        payload = await request.json()
        WhatsAppService.process_inbound_webhook_payload(db, payload)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
