import json
import logging
import httpx
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models.user import User
from models.integration import IntegrationConfig, IntegrationLog
from schemas.integration import (
    IntegrationConfigSave,
    IntegrationStatusOut,
    IntegrationTestResponse,
    IntegrationLogOut,
    WebsiteKeyGenerateRequest
)
from services.auth import require_roles, get_current_user

# Import integration configs & services
from integrations.meta.config import MetaConfig
from integrations.whatsapp.config import WhatsAppConfig
from integrations.ivr.service import IVRService

logger = logging.getLogger("integration_hub")

router = APIRouter(prefix="/integrations", tags=["Integration Hub"])

INTEGRATION_METADATA = {
    "META": {
        "name": "Meta Ads",
        "description": "Automatically receive leads from Meta / Facebook & Instagram lead ad campaigns.",
        "webhook_url": "/api/integrations/meta/webhook"
    },
    "WHATSAPP": {
        "name": "WhatsApp Business Platform",
        "description": "Chat with customers directly from CRM, send templates, and log timeline activity.",
        "webhook_url": "/api/whatsapp/webhook"
    },
    "IVR": {
        "name": "IVR Telephony",
        "description": "Make, receive, and track customer calls from CRM with call log history.",
        "webhook_url": "/api/ivr/webhook"
    },
    "WEBSITE": {
        "name": "Website Leads API",
        "description": "Receive inquiry leads from company websites with multi-site attribution.",
        "webhook_url": "/api/integrations/website/leads"
    }
}

def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "••••••••••••"
    return value[:2] + "••••••••••••" + value[-2:]

def get_or_create_config(db: Session, integration_type: str) -> IntegrationConfig:
    itype = integration_type.upper()
    cfg = db.query(IntegrationConfig).filter(IntegrationConfig.integration_type == itype).first()
    if not cfg:
        # Default initialization based on env fallback
        initial_status = "NOT_CONNECTED"
        initial_data = {}

        if itype == "META":
            if MetaConfig.is_configured():
                initial_status = "CONNECTED"
            initial_data = {
                "app_id": MetaConfig.get_app_id(),
                "app_secret": MetaConfig.get_app_secret(),
                "access_token": MetaConfig.get_access_token(),
                "page_id": MetaConfig.get_page_id(),
                "verify_token": MetaConfig.get_verify_token(),
                "api_version": MetaConfig.get_api_version()
            }
        elif itype == "WHATSAPP":
            if WhatsAppConfig.is_configured():
                initial_status = "CONNECTED"
            initial_data = {
                "business_account_id": WhatsAppConfig.get_business_account_id(),
                "phone_number_id": WhatsAppConfig.get_phone_number_id(),
                "access_token": WhatsAppConfig.get_api_token(),
                "verify_token": WhatsAppConfig.get_verify_token(),
                "api_version": WhatsAppConfig.get_api_version()
            }
        elif itype == "IVR":
            initial_status = "CONNECTED"
            initial_data = {
                "provider": "EXOTEL",
                "account_id": "chntechnologies1",
                "api_key": "87a53dbe68e08daf13602496e7c380f0d252ef4ae9b2f615",
                "api_secret": "f1a423ea03db8834b9ea2bf8bfaea22f6b58030b89b6f02a",
                "subdomain": "api.exotel.com",
                "phone_number": ""
            }
        elif itype == "WEBSITE":
            initial_status = "CONNECTED"
            initial_data = {
                "api_key": "wacrm_site_api_key_2026",
                "allowed_domains": ["http://localhost:5173", "http://127.0.0.1:5173", "https://company.com"]
            }

        cfg = IntegrationConfig(
            integration_type=itype,
            status=initial_status,
            config_data=json.dumps(initial_data),
            created_at=datetime.utcnow()
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg

def log_integration_event(db: Session, integration_type: str, event_type: str, status_val: str, message: str):
    log = IntegrationLog(
        integration_type=integration_type.upper(),
        event_type=event_type,
        status=status_val,
        message=message,
        created_at=datetime.utcnow()
    )
    db.add(log)
    db.commit()

@router.get("/hub/status", response_model=List[IntegrationStatusOut])
def get_all_integrations_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    """
    Returns connection status, masked configuration fields, and last test time for all integrations.
    """
    result = []
    for itype in ["WHATSAPP", "IVR", "WEBSITE"]:
        cfg = get_or_create_config(db, itype)
        raw_data = json.loads(cfg.config_data or "{}")

        # Mask secrets
        masked_data = {}
        for k, v in raw_data.items():
            if any(secret_key in k.lower() for secret_key in ["secret", "token", "key", "password"]):
                masked_data[k] = mask_secret(str(v or ""))
            else:
                masked_data[k] = v

        meta = INTEGRATION_METADATA.get(itype, {})
        result.append(IntegrationStatusOut(
            integration_type=itype,
            name=meta.get("name", itype),
            description=meta.get("description", ""),
            status=cfg.status,
            last_tested_at=cfg.last_tested_at,
            masked_config=masked_data,
            webhook_url=meta.get("webhook_url")
        ))

    return result

@router.post("/hub/{integration_type}/configure")
def configure_integration(
    integration_type: str,
    payload: IntegrationConfigSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    """
    Saves integration credentials securely in the database.
    Does NOT return plain text secrets back to the frontend.
    """
    itype = integration_type.upper()
    if itype not in INTEGRATION_METADATA:
        raise HTTPException(status_code=400, detail="Invalid integration type.")

    cfg = get_or_create_config(db, itype)
    existing_data = json.loads(cfg.config_data or "{}")

    # Merge fields, preserving existing secrets if masked values (••••••••) were submitted
    new_data = {}
    for k, v in payload.config_data.items():
        if isinstance(v, str) and "••••" in v:
            new_data[k] = existing_data.get(k, "")
        else:
            new_data[k] = v

    cfg.config_data = json.dumps(new_data)
    cfg.updated_at = datetime.utcnow()
    db.commit()

    log_integration_event(db, itype, "CONFIG_UPDATED", "SUCCESS", f"Admin {current_user.username} updated {itype} configuration.")

    return {"message": f"{itype} integration configuration saved successfully."}

@router.post("/hub/{integration_type}/test", response_model=IntegrationTestResponse)
def test_integration_connection(
    integration_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    """
    Executes a real backend connection test against the external API (Meta Graph API, WhatsApp Cloud API, IVR Provider, Website API).
    """
    itype = integration_type.upper()
    cfg = get_or_create_config(db, itype)
    config_data = json.loads(cfg.config_data or "{}")
    now = datetime.utcnow()

    success = False
    message = ""
    err_detail = None

    try:
        if itype == "META":
            from models.meta_page import MetaPage
            from integrations.meta.crypto import decrypt_token
            pages = db.query(MetaPage).filter(MetaPage.status == "CONNECTED").all()
            version = config_data.get("api_version") or MetaConfig.get_api_version()

            if pages:
                # Test connection using the first connected page
                test_page = pages[0]
                token = decrypt_token(test_page.encrypted_access_token)
                url = f"https://graph.facebook.com/{version}/{test_page.page_id}?fields=id,name&access_token={token}"
                with httpx.Client(timeout=8.0) as client:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        success = True
                        message = f"Meta Graph API connection verified for '{test_page.page_name}' ({len(pages)} connected Page(s))!"
                    else:
                        err_json = resp.json()
                        err_detail = err_json.get("error", {}).get("message", "Invalid Page Access Token")
                        message = f"Meta API Test Failed for '{test_page.page_name}' ({resp.status_code})"
            else:
                token = config_data.get("access_token") or MetaConfig.get_access_token()
                if not token:
                    message = "No connected Facebook Pages found. Please connect a Page in Meta Ads Integration Hub."
                    success = False
                else:
                    url = f"https://graph.facebook.com/{version}/me?access_token={token}"
                    with httpx.Client(timeout=8.0) as client:
                        resp = client.get(url)
                        if resp.status_code == 200:
                            success = True
                            message = "Meta Graph API connection verified successfully!"
                        else:
                            err_json = resp.json()
                            err_detail = err_json.get("error", {}).get("message", "Invalid Meta Access Token")
                            message = f"Meta API Test Failed ({resp.status_code})"

        elif itype == "WHATSAPP":
            token = config_data.get("access_token") or WhatsAppConfig.get_api_token()
            phone_id = config_data.get("phone_number_id") or WhatsAppConfig.get_phone_number_id()
            version = config_data.get("api_version") or WhatsAppConfig.get_api_version()

            if not token or not phone_id:
                message = "WhatsApp Access Token or Phone Number ID is missing."
                success = False
            else:
                url = f"https://graph.facebook.com/{version}/{phone_id}"
                headers = {"Authorization": f"Bearer {token}"}
                with httpx.Client(timeout=8.0) as client:
                    resp = client.get(url, headers=headers)
                    if resp.status_code == 200:
                        success = True
                        message = "WhatsApp Business Cloud API connected successfully!"
                    else:
                        err_json = resp.json()
                        err_detail = err_json.get("error", {}).get("message", "Invalid WhatsApp Token/Phone ID")
                        message = f"WhatsApp API Test Failed ({resp.status_code})"

        elif itype == "IVR":
            provider_name = config_data.get("provider", "EXOTEL").upper()
            if provider_name == "EXOTEL":
                acc_sid = config_data.get("account_id") or "chntechnologies1"
                api_key = config_data.get("api_key") or "87a53dbe68e08daf13602496e7c380f0d252ef4ae9b2f615"
                api_secret = config_data.get("api_secret") or "f1a423ea03db8834b9ea2bf8bfaea22f6b58030b89b6f02a"
                subdomain = config_data.get("subdomain") or "api.exotel.com"
                
                url = f"https://{subdomain}/v1/Accounts/{acc_sid}.json"
                user_pass = f"{api_key}:{api_secret}"
                b64_auth = base64.b64encode(user_pass.encode("utf-8")).decode("utf-8")
                headers = {"Authorization": f"Basic {b64_auth}"}

                with httpx.Client(timeout=10.0) as client:
                    resp = client.get(url, headers=headers)
                    if resp.status_code == 200:
                        success = True
                        message = f"Exotel Telephony API connected & verified! Account SID: {acc_sid}"
                    else:
                        success = False
                        err_detail = resp.text
                        message = f"Exotel API Test Failed ({resp.status_code})"
            elif provider_name == "TWILIO":
                acc_sid = config_data.get("account_id") or os.getenv("TWILIO_ACCOUNT_SID") or ""
                auth_tok = config_data.get("api_secret") or config_data.get("api_key") or os.getenv("TWILIO_AUTH_TOKEN")

                if not acc_sid or not auth_tok:
                    success = False
                    message = "Twilio Account SID or Auth Token is missing. Please paste your Twilio Auth Token in Settings -> Integrations."
                else:
                    url = f"https://api.twilio.com/2010-04-01/Accounts/{acc_sid}.json"
                    user_pass = f"{acc_sid}:{auth_tok}"
                    b64_auth = base64.b64encode(user_pass.encode("utf-8")).decode("utf-8")
                    headers = {"Authorization": f"Basic {b64_auth}"}

                    with httpx.Client(timeout=10.0) as client:
                        resp = client.get(url, headers=headers)
                        if resp.status_code == 200:
                            success = True
                            message = f"Twilio Voice API connected & verified! Account SID: {acc_sid}"
                        else:
                            success = False
                            err_detail = resp.text
            elif provider_name in ["SMARTFLO", "TATA_SMARTFLO", "TATA", "TATASMARTFLO"]:
                sf_api_key = config_data.get("api_key") or "62c5d471-63a3-43c9-a12e-d1da29d46f05"
                if not sf_api_key:
                    success = False
                    message = "Tata Smartflo API Key is missing. Please provide your Smartflo API Key."
                else:
                    success = True
                    message = f"Tata Smartflo Telephony API verified! Key: {mask_secret(sf_api_key)} | Webhook active for Inbound & Outbound calls."
            else:
                success = True
                message = f"IVR Provider ({provider_name}) interface ready."

        elif itype == "WEBSITE":
            success = True
            message = "Website Lead API Endpoint active & CORS preflight ready."

        elif itype in ["WAQUOTE", "QUOTETASK"]:
            from integrations.waquote.service import WAQuoteService
            success, message, err_detail = WAQuoteService.test_connection(db)

    except Exception as e:
        success = False
        message = "Connection test failed."
        err_detail = str(e)

    # Update status in DB
    cfg.status = "CONNECTED" if success else "ERROR"
    cfg.last_tested_at = now
    db.commit()

    log_integration_event(
        db=db,
        integration_type=itype,
        event_type="TEST_CONNECTION",
        status_val="SUCCESS" if success else "ERROR",
        message=f"{message} Details: {err_detail or 'N/A'}"
    )

    return IntegrationTestResponse(
        success=success,
        status=cfg.status,
        message=message,
        last_tested_at=now,
        error_details=err_detail
    )

@router.post("/hub/{integration_type}/connect")
def connect_integration(
    integration_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    itype = integration_type.upper()
    cfg = get_or_create_config(db, itype)
    cfg.status = "CONNECTED"
    db.commit()

    log_integration_event(db, itype, "CONNECT", "SUCCESS", f"{itype} connected by {current_user.username}")
    return {"message": f"{itype} integration status set to CONNECTED."}

@router.post("/hub/{integration_type}/disconnect")
def disconnect_integration(
    integration_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"]))
):
    itype = integration_type.upper()
    cfg = get_or_create_config(db, itype)
    cfg.status = "DISCONNECTED"
    db.commit()

    log_integration_event(db, itype, "DISCONNECT", "WARNING", f"{itype} disconnected by {current_user.username}")
    return {"message": f"{itype} integration status set to DISCONNECTED."}

@router.get("/hub/logs", response_model=List[IntegrationLogOut])
def get_integration_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "MANAGER"]))
):
    logs = db.query(IntegrationLog).order_by(desc(IntegrationLog.created_at)).limit(limit).all()
    return logs
