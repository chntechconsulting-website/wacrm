"""WhatsApp Business App coexistence onboarding and synchronization.

Scope and safety:
- No function here is called until an administrator explicitly launches Meta
  Embedded Signup with coexistence enabled.
- Existing CRM leads are never created, reassigned or overwritten from a phone
  address-book sync.
- Business-App echoes are mirrored into the inbox; they are never re-sent.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from integrations.meta.crypto import decrypt_token, encrypt_token
from models.whatsapp import Conversation, WhatsAppMessage
from models.whatsapp_coexistence import (
    WhatsAppCoexistenceConnection,
    WhatsAppCoexistenceEvent,
    WhatsAppSmbContact,
)

from .config import WhatsAppCoexistenceConfig

logger = logging.getLogger("whatsapp_coexistence")

COEXISTENCE_FIELDS = (
    "account_update",
    "history",
    "smb_app_state_sync",
    "smb_message_echoes",
)


class WhatsAppCoexistenceError(Exception):
    """Safe, user-facing error. Never contains a token or app secret."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _as_datetime(timestamp: Any) -> datetime:
    try:
        return datetime.utcfromtimestamp(int(timestamp))
    except (TypeError, ValueError, OSError):
        return datetime.utcnow()


def _loads(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _graph_error_message(body: Dict[str, Any], status_code: int) -> str:
    error = body.get("error") or {}
    message = (
        error.get("message")
        or body.get("error_description")
        or f"Graph API request failed with HTTP {status_code}"
    )
    code = error.get("code")
    subcode = error.get("error_subcode")
    suffix = ""
    if code is not None:
        suffix = f" (code {code}"
        if subcode is not None:
            suffix += f", subcode {subcode}"
        suffix += ")"
    return f"{message}{suffix}"


def _event_key(*parts: Any) -> str:
    raw = "|".join(str(part if part is not None else "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
    return f"{parts[0]}:{digest}" if parts else digest


_SECRET_KEYS = {
    "code",
    "access_token",
    "app_secret",
    "client_secret",
    "token",
    "authorization_code",
}


def _redact_session_data(value: Any) -> Any:
    """Recursively remove one-time codes and tokens from session logs."""
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).lower() in _SECRET_KEYS:
                cleaned[key] = "[redacted]"
            else:
                cleaned[key] = _redact_session_data(item)
        return cleaned
    if isinstance(value, list):
        return [_redact_session_data(item) for item in value]
    return value


def _message_content(message: Dict[str, Any]) -> Tuple[str, str, Optional[str], Optional[str]]:
    """Return (db_message_type, body, media_url, template_name)."""
    message_type = str(message.get("type") or "unknown").lower()
    media_url = None
    template_name = None

    if message_type == "text":
        body = (message.get("text") or {}).get("body") or ""
        return "TEXT", body, None, None

    if message_type in {"image", "video", "document", "audio", "sticker"}:
        media = message.get(message_type) or {}
        media_url = media.get("id") or media.get("link") or media.get("url")
        body = media.get("caption") or f"[{message_type.title()} attachment]"
        db_type = "IMAGE" if message_type in {"image", "sticker"} else (
            "DOCUMENT" if message_type == "document" else "TEXT"
        )
        return db_type, body, str(media_url) if media_url else None, None

    if message_type == "template":
        template = message.get("template") or {}
        template_name = template.get("name")
        body = f"Template: {template_name or 'unknown'}"
        return "TEMPLATE", body, None, template_name

    if message_type == "location":
        location = message.get("location") or {}
        label = location.get("name") or location.get("address") or ""
        return "TEXT", f"[Location] {label}".strip(), None, None

    if message_type == "contacts":
        contacts = message.get("contacts") or []
        names = []
        for contact in contacts:
            name = (contact.get("name") or {}).get("formatted_name")
            if name:
                names.append(name)
        return "TEXT", f"[Contact] {', '.join(names)}".strip(), None, None

    if message_type == "button":
        return "TEXT", (message.get("button") or {}).get("text") or "[Button reply]", None, None

    if message_type == "interactive":
        interactive = message.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return "TEXT", reply.get("title") or "[Interactive reply]", None, None

    if message_type == "reaction":
        emoji = (message.get("reaction") or {}).get("emoji") or ""
        return "TEXT", f"[Reaction] {emoji}".strip(), None, None

    if message_type == "media_placeholder":
        return "TEXT", "[Media message]", None, None

    if message_type == "revoke":
        return "TEXT", "[Message deleted]", None, None

    if message_type == "edit":
        edited = (message.get("edit") or {}).get("message") or {}
        return _message_content(edited)

    return "TEXT", f"[{message_type} message]", None, None


class WhatsAppCoexistenceService:
    # ------------------------------------------------------------------
    # Graph API
    # ------------------------------------------------------------------
    @classmethod
    def graph_request(
        cls,
        method: str,
        path: str,
        token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = WhatsAppCoexistenceConfig.graph_url(path)
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                response = client.request(
                    method.upper(),
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                )
        except httpx.HTTPError as exc:
            logger.error("Graph API transport error for %s: %s", path, exc)
            raise WhatsAppCoexistenceError(
                "Could not reach Meta Graph API. Check the server's network "
                "connection and try again.",
                status_code=502,
            ) from exc

        try:
            body = response.json()
        except ValueError:
            body = {"error": {"message": response.text[:300]}}

        if response.status_code >= 400:
            message = _graph_error_message(body, response.status_code)
            logger.warning("Graph API error for %s: %s", path, message)
            raise WhatsAppCoexistenceError(message, status_code=400)

        return body if isinstance(body, dict) else {"data": body}

    # ------------------------------------------------------------------
    # Connection lookup / serialization
    # ------------------------------------------------------------------
    @staticmethod
    def get_connection(db: Session) -> Optional[WhatsAppCoexistenceConnection]:
        return (
            db.query(WhatsAppCoexistenceConnection)
            .order_by(desc(WhatsAppCoexistenceConnection.id))
            .first()
        )

    @staticmethod
    def get_active_connection(db: Session) -> Optional[WhatsAppCoexistenceConnection]:
        """Connection usable for sending and receiving, newest first."""
        return (
            db.query(WhatsAppCoexistenceConnection)
            .filter(
                WhatsAppCoexistenceConnection.status.in_(
                    ["CONNECTED", "SYNCING", "SYNC_COMPLETE"]
                )
            )
            .order_by(desc(WhatsAppCoexistenceConnection.id))
            .first()
        )

    @staticmethod
    def get_connection_by_waba(
        db: Session, waba_id: str
    ) -> Optional[WhatsAppCoexistenceConnection]:
        return (
            db.query(WhatsAppCoexistenceConnection)
            .filter(WhatsAppCoexistenceConnection.waba_id == str(waba_id))
            .first()
        )

    @staticmethod
    def serialize_connection(
        connection: Optional[WhatsAppCoexistenceConnection],
    ) -> Optional[Dict[str, Any]]:
        if not connection:
            return None
        return {
            "id": connection.id,
            "waba_id": connection.waba_id,
            "phone_number_id": connection.phone_number_id,
            "business_id": connection.business_id,
            "display_phone_number": connection.display_phone_number,
            "verified_name": connection.verified_name,
            "quality_rating": connection.quality_rating,
            "status": connection.status,
            "onboarding_status": connection.onboarding_status,
            "is_on_biz_app": connection.is_on_biz_app,
            "platform_type": connection.platform_type,
            "webhook_subscribed": bool(connection.webhook_subscribed),
            "webhook_fields": _loads(connection.webhook_fields, []),
            "contacts_sync_requested_at": connection.contacts_sync_requested_at,
            "history_sync_requested_at": connection.history_sync_requested_at,
            "sync_deadline_at": connection.sync_deadline_at,
            "history_progress": connection.history_progress or 0,
            "history_phase": connection.history_phase,
            "messages_synced": connection.messages_synced or 0,
            "contacts_synced": connection.contacts_synced or 0,
            "last_webhook_at": connection.last_webhook_at,
            "last_synced_at": connection.last_synced_at,
            "last_error": connection.last_error,
            "onboarded_at": connection.onboarded_at,
            "created_at": connection.created_at,
            "updated_at": connection.updated_at,
        }

    @classmethod
    def get_status(cls, db: Session) -> Dict[str, Any]:
        connection = cls.get_connection(db)
        config = WhatsAppCoexistenceConfig.public_config()
        return {
            "config": config,
            "connection": cls.serialize_connection(connection),
            "webhook": {
                "callback_url": config["callback_url"],
                "expected_fields": list(
                    WhatsAppCoexistenceConfig.REQUIRED_WEBHOOK_FIELDS
                ),
                "note": (
                    "The callback URL and these fields are configured once in the "
                    "Meta App Dashboard > WhatsApp > Configuration. The app must "
                    "also be subscribed to the customer WABA."
                ),
            },
            "server_time": datetime.utcnow(),
        }

    # ------------------------------------------------------------------
    # Embedded Signup onboarding
    # ------------------------------------------------------------------
    @classmethod
    def _resolve_phone_number_id(
        cls, waba_id: str, access_token: str
    ) -> str:
        """Resolve the coexistence number when session logging omits it.

        Meta's coexistence session event may return only ``waba_id``. The
        business token can list the WABA's numbers; prefer an explicit
        Business App number and refuse to guess when multiple match.
        """
        numbers = cls.graph_request(
            "GET",
            f"{waba_id}/phone_numbers",
            token=access_token,
            params={
                "fields": "id,display_phone_number,is_on_biz_app,platform_type"
            },
        )
        items = [
            item for item in (numbers.get("data") or []) if item.get("id")
        ]
        if not items:
            raise WhatsAppCoexistenceError(
                "Meta returned no phone numbers for the selected WhatsApp "
                "Business Account. No connection was saved."
            )
        if len(items) == 1:
            return str(items[0]["id"])

        coexistence = [
            item for item in items if item.get("is_on_biz_app") is True
        ]
        if len(coexistence) == 1:
            return str(coexistence[0]["id"])

        raise WhatsAppCoexistenceError(
            "Meta returned more than one phone number for this WABA and the "
            "Business App number could not be identified. Relaunch Embedded "
            "Signup and select the existing WhatsApp Business App number. No "
            "connection was saved."
        )

    @classmethod
    def exchange_code(
        cls,
        db: Session,
        code: str,
        waba_id: str,
        phone_number_id: Optional[str] = None,
        business_id: Optional[str] = None,
        session_event: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not WhatsAppCoexistenceConfig.is_enabled():
            raise WhatsAppCoexistenceError(
                "Coexistence onboarding is locked. Set "
                "WHATSAPP_COEXISTENCE_ENABLED=true only when you are ready.",
                status_code=403,
            )
        if not WhatsAppCoexistenceConfig.is_configured():
            raise WhatsAppCoexistenceError(
                "Coexistence is not configured. Add the Meta app ID, app secret "
                "and Facebook Login for Business configuration ID.",
                status_code=503,
            )

        code = (code or "").strip()
        waba_id = _digits(waba_id)
        phone_number_id = _digits(phone_number_id)
        if not code:
            raise WhatsAppCoexistenceError("The Embedded Signup code is missing.")
        if not waba_id:
            raise WhatsAppCoexistenceError(
                "The WABA ID returned by Embedded Signup is required."
            )

        # Step 1: exchange the 30-second code for a business token.
        token_response = cls.graph_request(
            "GET",
            "oauth/access_token",
            params={
                "client_id": WhatsAppCoexistenceConfig.get_app_id(),
                "client_secret": WhatsAppCoexistenceConfig.get_app_secret(),
                "code": code,
            },
        )
        access_token = str(token_response.get("access_token") or "").strip()
        if not access_token:
            raise WhatsAppCoexistenceError(
                "Meta did not return a business token for this code. The code may "
                "have expired; launch Embedded Signup again."
            )

        # The coexistence session event sometimes contains only ``waba_id``.
        # Resolve the phone number with the newly issued business token before
        # saving anything.
        resolved_phone_id = False
        if not phone_number_id:
            phone_number_id = cls._resolve_phone_number_id(waba_id, access_token)
            resolved_phone_id = True

        # Step 2: prove the phone number belongs to the claimed WABA before
        # storing anything. This prevents onboarding arbitrary asset IDs.
        phone = cls.graph_request(
            "GET",
            phone_number_id,
            token=access_token,
            params={
                "fields": (
                    "display_phone_number,verified_name,quality_rating,"
                    "is_on_biz_app,platform_type,whatsapp_business_account"
                )
            },
        )
        owner = phone.get("whatsapp_business_account") or {}
        owner_id = str(owner.get("id") or "").strip() if isinstance(owner, dict) else ""
        if owner_id and owner_id != waba_id:
            raise WhatsAppCoexistenceError(
                "The selected phone number does not belong to the WABA returned "
                "by Embedded Signup. No connection was saved."
            )
        if not owner_id and not resolved_phone_id:
            numbers = cls.graph_request(
                "GET",
                f"{waba_id}/phone_numbers",
                token=access_token,
                params={"fields": "id"},
            )
            ids = {
                str(item.get("id"))
                for item in (numbers.get("data") or [])
                if item.get("id")
            }
            if ids and phone_number_id not in ids:
                raise WhatsAppCoexistenceError(
                    "The selected phone number does not belong to the WABA returned "
                    "by Embedded Signup. No connection was saved."
                )

        waba = cls.graph_request(
            "GET",
            waba_id,
            token=access_token,
            params={"fields": "id,name,account_review_status"},
        )

        # Step 3: create or update the local connection.
        connection = (
            db.query(WhatsAppCoexistenceConnection)
            .filter(
                (WhatsAppCoexistenceConnection.waba_id == waba_id)
                | (WhatsAppCoexistenceConnection.phone_number_id == phone_number_id)
            )
            .first()
        )
        is_new = connection is None
        if connection is None:
            connection = WhatsAppCoexistenceConnection(
                waba_id=waba_id,
                phone_number_id=phone_number_id,
                encrypted_access_token=encrypt_token(access_token),
                status="CONNECTED",
                onboarding_status="EXCHANGED",
            )
            db.add(connection)
        else:
            # Re-onboarding the same asset refreshes the token. Existing
            # messages and conversations are never deleted.
            connection.waba_id = waba_id
            connection.phone_number_id = phone_number_id
            connection.encrypted_access_token = encrypt_token(access_token)
            connection.status = (
                connection.status
                if connection.status in {"SYNCING", "SYNC_COMPLETE"}
                else "CONNECTED"
            )
            connection.onboarding_status = "EXCHANGED"
            connection.last_error = None

        connection.business_id = str(business_id).strip() if business_id else connection.business_id
        connection.display_phone_number = phone.get("display_phone_number") or connection.display_phone_number
        connection.verified_name = phone.get("verified_name") or waba.get("name") or connection.verified_name
        connection.quality_rating = phone.get("quality_rating") or connection.quality_rating
        connection.is_on_biz_app = phone.get("is_on_biz_app")
        connection.platform_type = phone.get("platform_type")
        connection.token_obtained_at = datetime.utcnow()
        connection.onboarded_at = connection.onboarded_at or datetime.utcnow()
        connection.webhook_fields = json.dumps(
            list(WhatsAppCoexistenceConfig.REQUIRED_WEBHOOK_FIELDS)
        )
        db.commit()
        db.refresh(connection)

        # Step 4: subscribe the app to the customer's WABA.
        try:
            subscription = cls.graph_request(
                "POST", f"{waba_id}/subscribed_apps", token=access_token
            )
            connection.webhook_subscribed = bool(subscription.get("success"))
            connection.onboarding_status = "SUBSCRIBED"
            db.commit()
        except WhatsAppCoexistenceError as exc:
            connection.status = "ERROR"
            connection.onboarding_status = "FAILED"
            connection.last_error = f"WABA subscription failed: {exc.message}"
            db.commit()
            raise

        # Step 5: ask Meta to start contacts + history synchronization. Each
        # request is allowed once per onboarding, so only request what is missing.
        sync_errors = []
        try:
            if not connection.contacts_sync_requested_at:
                cls._request_sync_for_connection(db, connection, access_token, "contacts")
            if not connection.history_sync_requested_at:
                cls._request_sync_for_connection(db, connection, access_token, "history")
        except WhatsAppCoexistenceError as exc:
            sync_errors.append(exc.message)

        if connection.contacts_sync_requested_at and connection.history_sync_requested_at:
            connection.status = "SYNCING"
            connection.onboarding_status = "SYNC_REQUESTED"
            connection.sync_deadline_at = datetime.utcnow() + timedelta(
                hours=WhatsAppCoexistenceConfig.get_sync_deadline_hours()
            )
        if sync_errors:
            connection.status = "ERROR"
            connection.last_error = " | ".join(sync_errors)
        db.commit()
        db.refresh(connection)

        cls._record_event(
            db,
            connection.id,
            "SESSION",
            _event_key(
                "session",
                waba_id,
                phone_number_id,
                session_event or "FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING",
                datetime.utcnow().isoformat(),
            ),
            status="PROCESSED",
            detail=f"Embedded Signup completed ({session_event or 'FINISH'}).",
        )

        if sync_errors:
            raise WhatsAppCoexistenceError(
                "The number was connected, but synchronization could not be "
                f"started: {' | '.join(sync_errors)}. Use Retry sync on the "
                "connection page before the 24-hour window closes.",
                status_code=502,
            )

        return cls.serialize_connection(connection) or {}

    @classmethod
    def _request_sync_for_connection(
        cls,
        db: Session,
        connection: WhatsAppCoexistenceConnection,
        access_token: str,
        sync_type: str,
    ) -> Dict[str, Any]:
        sync_type = str(sync_type or "").strip().lower()
        if sync_type not in {"contacts", "history"}:
            raise WhatsAppCoexistenceError("sync_type must be contacts or history.")

        meta_sync_type = "smb_app_state_sync" if sync_type == "contacts" else "history"
        response = cls.graph_request(
            "POST",
            f"{connection.phone_number_id}/smb_app_data",
            token=access_token,
            json_body={
                "messaging_product": "whatsapp",
                "sync_type": meta_sync_type,
            },
        )
        now = datetime.utcnow()
        request_id = response.get("request_id")
        if sync_type == "contacts":
            connection.contacts_sync_requested_at = now
            connection.contacts_sync_request_id = (
                str(request_id) if request_id else None
            )
        else:
            connection.history_sync_requested_at = now
            connection.history_sync_request_id = str(request_id) if request_id else None
        connection.status = "SYNCING"
        connection.onboarding_status = "SYNC_REQUESTED"
        connection.sync_deadline_at = now + timedelta(
            hours=WhatsAppCoexistenceConfig.get_sync_deadline_hours()
        )
        connection.last_error = None
        db.commit()
        db.refresh(connection)
        return response

    @classmethod
    def request_sync(
        cls, db: Session, sync_type: str, connection: Optional[WhatsAppCoexistenceConnection] = None
    ) -> Dict[str, Any]:
        connection = connection or cls.get_connection(db)
        if not connection:
            raise WhatsAppCoexistenceError("No WhatsApp connection exists yet.", 404)

        sync_type = str(sync_type or "").strip().lower()
        if sync_type == "contacts" and connection.contacts_sync_requested_at:
            raise WhatsAppCoexistenceError(
                "Contact synchronization was already requested. Meta allows one "
                "request per onboarding."
            )
        if sync_type == "history" and connection.history_sync_requested_at:
            raise WhatsAppCoexistenceError(
                "History synchronization was already requested. Meta allows one "
                "request per onboarding."
            )

        token = decrypt_token(connection.encrypted_access_token)
        if not token:
            raise WhatsAppCoexistenceError(
                "The stored business token is unavailable. Reconnect the number.",
                409,
            )
        response = cls._request_sync_for_connection(db, connection, token, sync_type)
        return {"success": True, "request_id": response.get("request_id"), "connection": cls.serialize_connection(connection)}

    @classmethod
    def refresh_connection(
        cls,
        db: Session,
        connection: Optional[WhatsAppCoexistenceConnection] = None,
    ) -> Dict[str, Any]:
        connection = connection or cls.get_connection(db)
        if not connection:
            raise WhatsAppCoexistenceError("No WhatsApp connection exists yet.", 404)

        token = decrypt_token(connection.encrypted_access_token)
        if not token:
            raise WhatsAppCoexistenceError(
                "The stored business token is unavailable. Reconnect the number.",
                409,
            )

        phone = cls.graph_request(
            "GET",
            connection.phone_number_id,
            token=token,
            params={
                "fields": (
                    "display_phone_number,verified_name,quality_rating,"
                    "is_on_biz_app,platform_type"
                )
            },
        )
        connection.display_phone_number = phone.get("display_phone_number") or connection.display_phone_number
        connection.verified_name = phone.get("verified_name") or connection.verified_name
        connection.quality_rating = phone.get("quality_rating") or connection.quality_rating
        connection.is_on_biz_app = phone.get("is_on_biz_app")
        connection.platform_type = phone.get("platform_type")

        subscriptions = cls.graph_request(
            "GET",
            f"{connection.waba_id}/subscribed_apps",
            token=token,
        )
        app_id = WhatsAppCoexistenceConfig.get_app_id()
        subscribed = False
        for item in subscriptions.get("data") or []:
            if str(item.get("whatsapp_business_api_data", {}).get("id") or item.get("id")) == app_id:
                subscribed = True
                break
        connection.webhook_subscribed = subscribed
        connection.last_synced_at = datetime.utcnow()
        if connection.status == "ERROR":
            connection.last_error = None
        db.commit()
        db.refresh(connection)
        return cls.serialize_connection(connection) or {}

    # ------------------------------------------------------------------
    # Webhook processing
    # ------------------------------------------------------------------
    @staticmethod
    def payload_has_coexistence_fields(payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                if str(change.get("field") or "") in COEXISTENCE_FIELDS:
                    return True
        return False

    @classmethod
    def process_payload(cls, db: Session, payload: Dict[str, Any]) -> Dict[str, int]:
        summary = {
            "history_messages": 0,
            "contacts_synced": 0,
            "echoes": 0,
            "account_updates": 0,
            "ignored": 0,
        }
        if not isinstance(payload, dict):
            return summary

        for entry in payload.get("entry") or []:
            waba_id = str(entry.get("id") or "").strip()
            connection = cls.get_connection_by_waba(db, waba_id) if waba_id else None

            # ``account_update`` may put the partner business ID in entry.id and
            # the real WABA ID inside value.waba_info.waba_id. Resolve it before
            # deciding the delivery is unrelated.
            if not connection:
                for change in entry.get("changes") or []:
                    if str(change.get("field") or "") != "account_update":
                        continue
                    info = (change.get("value") or {}).get("waba_info") or {}
                    alt_waba = str(info.get("waba_id") or "").strip()
                    if alt_waba:
                        connection = cls.get_connection_by_waba(db, alt_waba)
                        if connection:
                            break

            if not connection:
                summary["ignored"] += 1
                continue

            for change in entry.get("changes") or []:
                field = str(change.get("field") or "")
                value = change.get("value") or {}
                change_connection = connection
                if field == "account_update":
                    info = value.get("waba_info") or {}
                    alt_waba = str(info.get("waba_id") or "").strip()
                    if alt_waba:
                        change_connection = (
                            cls.get_connection_by_waba(db, alt_waba) or connection
                        )
                change_connection.last_webhook_at = datetime.utcnow()
                try:
                    if field == "history":
                        summary["history_messages"] += cls._handle_history(
                            db, change_connection, value
                        )
                    elif field == "smb_app_state_sync":
                        summary["contacts_synced"] += cls._handle_state_sync(
                            db, change_connection, value
                        )
                    elif field == "smb_message_echoes":
                        summary["echoes"] += cls._handle_echoes(
                            db, change_connection, value, entry.get("time")
                        )
                    elif field == "account_update":
                        cls._handle_account_update(
                            db, change_connection, value, entry.get("time")
                        )
                        summary["account_updates"] += 1
                    else:
                        summary["ignored"] += 1
                except Exception as exc:  # one bad field must not drop the rest
                    db.rollback()
                    logger.error(
                        "Coexistence webhook field %s failed: %s",
                        field,
                        exc,
                        exc_info=True,
                    )
                    connection = cls.get_connection_by_waba(db, waba_id) or connection
                    connection.last_error = f"{field}: {exc}"
                    db.commit()
            db.commit()

        return summary

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------
    @classmethod
    def _handle_history(
        cls,
        db: Session,
        connection: WhatsAppCoexistenceConnection,
        value: Dict[str, Any],
    ) -> int:
        from integrations.whatsapp.service import WhatsAppService

        business_phone = _digits(connection.display_phone_number)
        ingested = 0

        # Meta sends the media follow-up as ``field: history`` with a top-level
        # ``messages`` array (not inside ``history``). Ingest it so a
        # ``media_placeholder`` row is upgraded to the real media message.
        for message in value.get("messages") or []:
            wamid = str(message.get("id") or "").strip()
            if not wamid:
                continue
            from_phone = _digits(message.get("from"))
            to_phone = _digits(message.get("to"))
            is_outbound = bool(
                (business_phone and from_phone == business_phone) or to_phone
            )
            customer_phone = to_phone if is_outbound and to_phone else from_phone
            if not customer_phone:
                continue

            msg_type, body, media_url, template_name = _message_content(message)
            media_key = _event_key(
                "history-media",
                connection.waba_id,
                wamid,
                msg_type,
                body,
                media_url,
            )
            if cls._event_processed(db, media_key):
                continue

            conversation = WhatsAppService.get_or_create_conversation(
                db, phone=customer_phone
            )
            existing_row = (
                db.query(WhatsAppMessage)
                .filter(WhatsAppMessage.provider_message_id == wamid)
                .first()
            )
            timestamp = _as_datetime(message.get("timestamp"))

            if existing_row is not None:
                if (
                    existing_row.body == "[Media message]"
                    and body
                    and body != "[Media message]"
                ):
                    existing_row.message_type = msg_type
                    existing_row.body = body
                    existing_row.media_url = media_url or existing_row.media_url
                    existing_row.template_name = (
                        template_name or existing_row.template_name
                    )
                    if (
                        not conversation.last_message_at
                        or timestamp >= conversation.last_message_at
                    ):
                        conversation.last_message_at = timestamp
                        conversation.last_message_text = (body or "")[:80]
            else:
                history_status = str(
                    (message.get("history_context") or {}).get("status")
                    or ("SENT" if is_outbound else "DELIVERED")
                ).upper()
                record = WhatsAppMessage(
                    conversation_id=conversation.id,
                    lead_id=conversation.lead_id,
                    sender_employee_id=None,
                    direction="OUTBOUND" if is_outbound else "INBOUND",
                    message_type=msg_type,
                    body=body,
                    media_url=media_url,
                    template_name=template_name,
                    provider_message_id=wamid,
                    status=history_status,
                    sent_at=timestamp,
                    delivered_at=(
                        timestamp
                        if history_status in {"DELIVERED", "READ", "PLAYED"}
                        else None
                    ),
                    read_at=timestamp if history_status == "READ" else None,
                    created_at=timestamp,
                )
                db.add(record)
                ingested += 1
                if (
                    not conversation.last_message_at
                    or timestamp >= conversation.last_message_at
                ):
                    conversation.last_message_at = timestamp
                    conversation.last_message_text = (body or "")[:80]

            cls._record_event(
                db,
                connection.id,
                "HISTORY",
                media_key,
                status="PROCESSED",
                detail=f"Media follow-up for message {wamid}",
            )
            db.commit()

        for chunk in value.get("history") or []:
            metadata = chunk.get("metadata") or {}
            phase = metadata.get("phase")
            chunk_order = metadata.get("chunk_order")
            progress = metadata.get("progress")
            chunk_fingerprint = hashlib.sha256(
                json.dumps(chunk, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()[:32]
            key = _event_key(
                "history",
                connection.waba_id,
                connection.phone_number_id,
                phase,
                chunk_order,
                progress,
                chunk_fingerprint,
            )
            if cls._event_processed(db, key):
                continue

            for thread in chunk.get("threads") or []:
                customer_phone = _digits(thread.get("id"))
                messages = thread.get("messages") or []
                if not customer_phone or not messages:
                    continue

                conversation = WhatsAppService.get_or_create_conversation(
                    db, phone=customer_phone
                )
                wamids = [str(msg.get("id")) for msg in messages if msg.get("id")]
                existing = {}
                if wamids:
                    rows = (
                        db.query(WhatsAppMessage)
                        .filter(WhatsAppMessage.provider_message_id.in_(wamids))
                        .all()
                    )
                    existing = {
                        row.provider_message_id: row
                        for row in rows
                        if row.provider_message_id
                    }

                for message in messages:
                    wamid = str(message.get("id") or "").strip()
                    from_phone = _digits(message.get("from"))
                    to_phone = _digits(message.get("to"))
                    direction = (
                        "OUTBOUND"
                        if (business_phone and from_phone == business_phone) or to_phone
                        else "INBOUND"
                    )
                    msg_type, body, media_url, template_name = _message_content(
                        message
                    )

                    existing_row = existing.get(wamid) if wamid else None
                    if existing_row is not None:
                        # Meta follows a ``media_placeholder`` history message
                        # with a second webhook carrying the real media ID.
                        # Update the placeholder instead of dropping the media.
                        if (
                            existing_row.body == "[Media message]"
                            and body
                            and body != "[Media message]"
                        ):
                            existing_row.message_type = msg_type
                            existing_row.body = body
                            existing_row.media_url = media_url or existing_row.media_url
                            existing_row.template_name = (
                                template_name or existing_row.template_name
                            )
                        continue

                    timestamp = _as_datetime(message.get("timestamp"))
                    history_status = str(
                        (message.get("history_context") or {}).get("status")
                        or ("DELIVERED" if direction == "INBOUND" else "SENT")
                    ).upper()

                    record = WhatsAppMessage(
                        conversation_id=conversation.id,
                        lead_id=conversation.lead_id,
                        sender_employee_id=None,
                        direction=direction,
                        message_type=msg_type,
                        body=body,
                        media_url=media_url,
                        template_name=template_name,
                        provider_message_id=wamid or None,
                        status=history_status,
                        sent_at=timestamp,
                        delivered_at=(
                            timestamp
                            if history_status in {"DELIVERED", "READ", "PLAYED"}
                            else None
                        ),
                        read_at=timestamp if history_status == "READ" else None,
                        created_at=timestamp,
                    )
                    db.add(record)
                    existing[wamid] = record
                    ingested += 1

                    if not conversation.last_message_at or timestamp >= conversation.last_message_at:
                        conversation.last_message_at = timestamp
                        conversation.last_message_text = (body or "")[:80]

            connection.history_progress = max(
                int(connection.history_progress or 0), int(progress or 0)
            )
            if phase is not None:
                connection.history_phase = int(phase)
            if int(progress or 0) >= 100:
                connection.status = "SYNC_COMPLETE"
                connection.onboarding_status = "COMPLETE"
                connection.last_synced_at = datetime.utcnow()
                connection.sync_deadline_at = None

            cls._record_event(
                db,
                connection.id,
                "HISTORY",
                key,
                status="PROCESSED",
                detail=(
                    f"phase={phase} chunk={chunk_order} progress={progress}% "
                    f"messages={len(chunk.get('threads') or [])} threads"
                ),
            )
            db.commit()

        connection.messages_synced = int(connection.messages_synced or 0) + ingested
        db.commit()
        return ingested

    # ------------------------------------------------------------------
    # Contacts
    # ------------------------------------------------------------------
    @classmethod
    def _handle_state_sync(
        cls,
        db: Session,
        connection: WhatsAppCoexistenceConnection,
        value: Dict[str, Any],
    ) -> int:
        synced = 0
        for item in value.get("state_sync") or []:
            contact = item.get("contact") or {}
            phone = _digits(contact.get("phone_number"))
            if not phone:
                continue
            action = str(item.get("action") or "add").lower()
            timestamp = (item.get("metadata") or {}).get("timestamp")
            key = _event_key(
                "state", connection.waba_id, phone, action, timestamp
            )
            if cls._event_processed(db, key):
                continue

            row = (
                db.query(WhatsAppSmbContact)
                .filter(
                    WhatsAppSmbContact.connection_id == connection.id,
                    WhatsAppSmbContact.phone_number == phone,
                )
                .first()
            )
            if row is None:
                row = WhatsAppSmbContact(
                    connection_id=connection.id,
                    phone_number=phone,
                    full_name=contact.get("full_name"),
                    first_name=contact.get("first_name"),
                    last_action=action,
                    last_synced_at=datetime.utcnow(),
                )
                db.add(row)
            else:
                row.last_action = action
                row.last_synced_at = datetime.utcnow()
                if action != "remove":
                    row.full_name = contact.get("full_name") or row.full_name
                    row.first_name = contact.get("first_name") or row.first_name

            if action != "remove" and contact.get("full_name"):
                conversations = (
                    db.query(Conversation)
                    .filter(Conversation.phone.like(f"%{phone[-10:]}"))
                    .all()
                )
                for conversation in conversations:
                    conversation.contact_name = contact.get("full_name")

            cls._record_event(
                db,
                connection.id,
                "STATE_SYNC",
                key,
                status="PROCESSED",
                detail=f"{action} contact ending {phone[-4:]}",
            )
            synced += 1

        connection.contacts_synced = int(connection.contacts_synced or 0) + synced
        db.commit()
        return synced

    # ------------------------------------------------------------------
    # Business App echoes
    # ------------------------------------------------------------------
    @classmethod
    def _handle_echoes(
        cls,
        db: Session,
        connection: WhatsAppCoexistenceConnection,
        value: Dict[str, Any],
        entry_time: Any,
    ) -> int:
        from integrations.whatsapp.service import WhatsAppService

        handled = 0
        for message in value.get("message_echoes") or []:
            wamid = str(message.get("id") or "").strip()
            message_type = str(message.get("type") or "").lower()

            if message_type == "revoke":
                original_id = str(
                    (message.get("revoke") or {}).get("original_message_id") or ""
                )
                original = (
                    db.query(WhatsAppMessage)
                    .filter(WhatsAppMessage.provider_message_id == original_id)
                    .first()
                )
                if original:
                    original.body = "[Message deleted by business]"
                cls._record_event(
                    db,
                    connection.id,
                    "ECHO",
                    _event_key("echo-revoke", connection.waba_id, original_id, entry_time),
                    status="PROCESSED",
                    detail="Business App message revoked.",
                )
                handled += 1
                continue

            if message_type == "edit":
                original_id = str(
                    (message.get("edit") or {}).get("original_message_id") or ""
                )
                edited = (message.get("edit") or {}).get("message") or {}
                original = (
                    db.query(WhatsAppMessage)
                    .filter(WhatsAppMessage.provider_message_id == original_id)
                    .first()
                )
                if original:
                    msg_type, body, media_url, template_name = _message_content(edited)
                    original.message_type = msg_type
                    original.body = body
                    original.media_url = media_url or original.media_url
                    original.template_name = template_name or original.template_name
                cls._record_event(
                    db,
                    connection.id,
                    "ECHO",
                    _event_key("echo-edit", connection.waba_id, original_id, entry_time),
                    status="PROCESSED",
                    detail="Business App message edited.",
                )
                handled += 1
                continue

            if not wamid:
                continue
            if (
                db.query(WhatsAppMessage.id)
                .filter(WhatsAppMessage.provider_message_id == wamid)
                .first()
            ):
                continue

            customer_phone = _digits(message.get("to"))
            if not customer_phone:
                continue
            conversation = WhatsAppService.get_or_create_conversation(
                db, phone=customer_phone
            )
            msg_type, body, media_url, template_name = _message_content(message)
            timestamp = _as_datetime(message.get("timestamp"))
            record = WhatsAppMessage(
                conversation_id=conversation.id,
                lead_id=conversation.lead_id,
                sender_employee_id=None,
                direction="OUTBOUND",
                message_type=msg_type,
                body=body,
                media_url=media_url,
                template_name=template_name,
                provider_message_id=wamid,
                status="SENT",
                sent_at=timestamp,
                created_at=timestamp,
            )
            db.add(record)

            conversation.last_message_text = f"You: {(body or '')[:80]}"
            conversation.last_message_at = timestamp
            conversation.updated_at = datetime.utcnow()

            cls._record_event(
                db,
                connection.id,
                "ECHO",
                _event_key("echo", connection.waba_id, wamid),
                status="PROCESSED",
                detail="Business App message mirrored into the CRM inbox.",
            )
            handled += 1

        db.commit()
        return handled

    # ------------------------------------------------------------------
    # Account lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def _handle_account_update(
        cls,
        db: Session,
        connection: WhatsAppCoexistenceConnection,
        value: Dict[str, Any],
        entry_time: Any,
    ) -> None:
        event = str(value.get("event") or "").upper()
        disconnection = value.get("disconnection_info") or {}
        reason = disconnection.get("reason") or ""
        initiated_by = disconnection.get("initiated_by") or ""
        key = _event_key("account", connection.waba_id, event, entry_time)

        if event in {"PARTNER_REMOVED", "ACCOUNT_OFFBOARDED"}:
            connection.status = "DISCONNECTED"
            connection.onboarding_status = "FAILED"
            connection.webhook_subscribed = False
            detail = f"Disconnected: {event}"
            if reason:
                detail += f" ({reason}"
                if initiated_by:
                    detail += f", by {initiated_by}"
                detail += ")"
            connection.last_error = detail
        elif event == "ACCOUNT_RECONNECTED":
            if connection.status == "DISCONNECTED":
                connection.status = "CONNECTED"
            connection.last_error = None
        else:
            connection.last_error = None

        cls._record_event(
            db,
            connection.id,
            "ACCOUNT_UPDATE",
            key,
            status="PROCESSED",
            detail=f"{event or 'account update'} {reason} {initiated_by}".strip(),
        )
        db.commit()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    @staticmethod
    def _event_processed(db: Session, key: str) -> bool:
        return (
            db.query(WhatsAppCoexistenceEvent.id)
            .filter(
                WhatsAppCoexistenceEvent.event_key == key,
                WhatsAppCoexistenceEvent.status == "PROCESSED",
            )
            .first()
            is not None
        )

    @classmethod
    def _record_event(
        cls,
        db: Session,
        connection_id: Optional[int],
        event_type: str,
        key: str,
        status: str = "PROCESSED",
        detail: Optional[str] = None,
        payload: Optional[str] = None,
    ) -> Optional[WhatsAppCoexistenceEvent]:
        existing = (
            db.query(WhatsAppCoexistenceEvent)
            .filter(WhatsAppCoexistenceEvent.event_key == key)
            .first()
        )
        if existing:
            if status == "PROCESSED" and existing.status != "PROCESSED":
                existing.status = status
                existing.processed_at = datetime.utcnow()
                db.commit()
            return existing

        event = WhatsAppCoexistenceEvent(
            connection_id=connection_id,
            event_type=event_type,
            event_key=key,
            status=status,
            detail=detail,
            payload=payload,
            processed_at=datetime.utcnow() if status == "PROCESSED" else None,
        )
        db.add(event)
        try:
            db.commit()
        except IntegrityError:
            # A concurrent delivery inserted the same event first.
            db.rollback()
            return (
                db.query(WhatsAppCoexistenceEvent)
                .filter(WhatsAppCoexistenceEvent.event_key == key)
                .first()
            )
        db.refresh(event)
        return event

    @classmethod
    def log_session_event(
        cls, db: Session, event_type: str, event: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Persist Embedded Signup session logging for audit.

        Session logs can arrive before the connection row exists. The raw
        payload is stored only for this event type; it contains asset IDs, not
        message content.
        """
        safe_data = _redact_session_data(dict(data or {}))
        waba_id = str(safe_data.get("waba_id") or "").strip()
        connection = cls.get_connection_by_waba(db, waba_id) if waba_id else None
        key = _event_key(
            "session-log",
            event_type,
            event,
            waba_id,
            safe_data.get("phone_number_id"),
            safe_data.get("session_id"),
            datetime.utcnow().isoformat(),
        )
        record = cls._record_event(
            db,
            connection.id if connection else None,
            "SESSION_LOG",
            key,
            status="PROCESSED",
            detail=f"{event_type}:{event}",
            payload=json.dumps(safe_data)[:20000],
        )
        return {
            "logged": True,
            "event_id": record.id if record else None,
            "event": event,
        }

    @classmethod
    def list_events(
        cls, db: Session, limit: int = 25
    ) -> List[WhatsAppCoexistenceEvent]:
        return (
            db.query(WhatsAppCoexistenceEvent)
            .order_by(desc(WhatsAppCoexistenceEvent.id))
            .limit(max(1, min(limit, 100)))
            .all()
        )

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------
    @classmethod
    def list_templates(cls, db: Session) -> List[Dict[str, Any]]:
        connection = cls.get_active_connection(db)
        if not connection:
            raise WhatsAppCoexistenceError("No active WhatsApp connection.", 404)
        token = decrypt_token(connection.encrypted_access_token)
        response = cls.graph_request(
            "GET",
            f"{connection.waba_id}/message_templates",
            token=token,
            params={
                "fields": "id,name,status,category,language,components",
                "limit": 100,
            },
        )
        items = []
        for item in response.get("data") or []:
            items.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "status": item.get("status"),
                    "category": item.get("category"),
                    "language": item.get("language"),
                    "components": item.get("components"),
                }
            )
        return items

    @classmethod
    def create_template(
        cls,
        db: Session,
        name: str,
        language: str,
        category: str,
        body_text: str,
        footer_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        connection = cls.get_active_connection(db)
        if not connection:
            raise WhatsAppCoexistenceError("No active WhatsApp connection.", 404)

        name = (name or "").strip().lower()
        if not name or len(name) > 512:
            raise WhatsAppCoexistenceError("Template name is required.")
        if not all(ch.isalnum() or ch == "_" for ch in name):
            raise WhatsAppCoexistenceError(
                "Template names may only contain lowercase letters, numbers and underscores."
            )
        components = [
            {"type": "BODY", "text": (body_text or "").strip()},
        ]
        if footer_text and footer_text.strip():
            components.append({"type": "FOOTER", "text": footer_text.strip()[:60]})
        if not components[0]["text"]:
            raise WhatsAppCoexistenceError("Template body text is required.")

        token = decrypt_token(connection.encrypted_access_token)
        response = cls.graph_request(
            "POST",
            f"{connection.waba_id}/message_templates",
            token=token,
            json_body={
                "name": name,
                "language": (language or "en_US").strip(),
                "category": (category or "UTILITY").strip().upper(),
                "components": components,
            },
        )
        return {
            "id": response.get("id"),
            "status": response.get("status"),
            "category": response.get("category"),
        }
