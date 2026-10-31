# Doocti Telephony & CRM API Integration Guide

This document provides the verified technical integration specifications for connecting the **Doocti Telephony / PBX System** with **WACRM**.

---

## 1. Integration Architecture Overview

WACRM connects with Doocti using a hybrid telephony architecture:

```
[Customer Phone] <====== Telephony / SIP Trunk ======> [Doocti Cloud PBX / Asterisk]
                                                                  |
                                      +---------------------------+---------------------------+
                                      | CDR Webhook Push (HTTP)                               | WebRTC / SIP Audio
                                      v                                                       v
                          [WACRM Backend API]                                    [Agent Browser WebPhone]
                     POST /api/doocti/call-log                                   Embedded Doocti Iframe
                                      |                                          (https://beta3-app.doocti.com/)
                                      v
                             [MySQL Database]
                            `call_logs` table
```

1. **Inbound & Outbound CDR Ingestion:** Doocti PBX pushes real-time call events (Call Detail Records) to WACRM via HTTP POST / GET webhooks.
2. **Agent Softphone Calling:** WACRM agents use an embedded in-app WebRTC dialer iframe (`https://beta3-app.doocti.com/`) communicating via HTML5 `postMessage`.
3. **Screen Pop-Up & Caller ID Lookup:** During an incoming call, Doocti queries WACRM to retrieve lead/contact details by caller number.
4. **Call Recording Delivery:** Doocti provides call recording URLs either immediately within the CDR payload or via a subsequent recording-ready webhook event.

---

## 2. Primary Webhook Endpoint (Call Detail Record)

### 2.1 Endpoint URL & HTTP Method
- **Production URL:** `https://www.wapluscrm.in/api/doocti/call-log`
- **Supported / Aliased URL:** `https://www.wapluscrm.in/api/v1/doocti/call-log`
- **HTTP Method:** `POST` *(also accepts `GET` with query parameters)*
- **Content-Type Supported:**
  - `application/json` *(Recommended)*
  - `application/x-www-form-urlencoded`
  - `multipart/form-data`

> **Alternative / Route Aliases:**  
> The CRM router also accepts webhooks on the following verified aliases:
> - `POST https://www.wapluscrm.in/api/doocti/push-call-log`
> - `POST https://www.wapluscrm.in/api/doocti/recording`
> - `POST https://www.wapluscrm.in/api/v1/doocti/call-log`

---

## 3. Headers & Authentication

| Header | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `Content-Type` | String | Yes | `application/json` or `application/x-www-form-urlencoded` |
| `User-Agent` | String | Optional | Client identifier (e.g., `Doocti-PBX-Webhook/1.0`) |
| `X-API-KEY` | String | Optional | Optional pre-shared secret token for network verification |

> **Authentication Policy:**  
> To guarantee maximum reliability with PBX webhook dispatchers that cannot supply custom HTTP headers, the `/api/doocti/call-log` endpoint does not reject incoming webhooks based on missing bearer tokens. Network-level IP whitelisting can be enabled on Cloudflare / Nginx upon request.

---

## 4. Request Payload Specification

The CRM accepts standard Doocti Push Call Log parameters as well as standard industry aliases.

### 4.1 Standard Doocti Fields

| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `uniqueid` | String | **Yes** | Unique PBX call session identifier. Used for idempotency and updating existing records. | `"1729584000.1234"` |
| `phone_number` | String | **Yes** | Customer phone number (or caller number for inbound). | `"9876543210"` |
| `station` | String/Int | Recommended | Agent SIP extension or workstation identifier. | `"1282"` |
| `agent` | String | Recommended | Agent username or identifier. | `"chntechnolog_agent01"` |
| `status` | String | Recommended | Call disposition/status (`ANSWERED`, `MISSED`, `BUSY`, `NO ANSWER`, `FAILED`, `COMPLETED`). | `"ANSWERED"` |
| `duration` | Integer | Recommended | Billable call talk time or total duration in seconds. | `90` |
| `start_time` | String | Optional | Call origination timestamp (`YYYY-MM-DD HH:MM:SS` or ISO-8601). | `"2026-10-22 10:00:00"` |
| `end_time` | String | Optional | Call disconnect timestamp. | `"2026-10-22 10:01:30"` |
| `record_location` | String | Optional | Playable recording URL. This is the field DooCTI's own portal and iframe player read. | `"https://media.doocti.com/.../rec_123.mp3"` |
| `recording_path` | String | Optional | Legacy alias for the recording URL (still accepted). | `"https://.../rec_123.mp3"` |

### 4.2 Additional Supported Fields & Aliases

| Field | Aliases Accepted | Description |
| :--- | :--- | :--- |
| **Call ID** | `call_id`, `provider_call_id`, `callid`, `CallId`, `session_id` | Fallback if `uniqueid` is omitted. |
| **Customer Phone** | `customer_number`, `to_number`, `from_number`, `caller` | Fallback if `phone_number` is named differently. |
| **Call Direction** | `call_direction`, `direction` | `"INBOUND"` or `"OUTBOUND"` (Defaults to `"OUTBOUND"` if unspecified). |
| **Agent Info** | `agent_name`, `user_name`, `agent_email`, `email` | Used to match CRM employee and assign call ownership. |
| **Agent Station** | `agent_number`, `extension`, `ext` | Agent PBX station. |
| **Duration** | `duration_seconds`, `billsec` | Duration in seconds. |
| **Recording** | `record_location`, `recording_url`, `recording`, `recording_link`, `record_url`, `audio_url` | Direct URL to the playable audio file. Unrendered template values (`%...%`, `{{...}}`, `$...`) are ignored. |
| **Notes / Disposition** | `disposition`, `call_purpose`, `lead_stage`, `notes` | Agent wrap-up notes saved into CRM lead activity history. |

---

## 5. Webhook Request Examples

### 5.1 Outbound Answered Call (JSON)
```http
POST /api/doocti/call-log HTTP/1.1
Host: www.wapluscrm.in
Content-Type: application/json

{
  "uniqueid": "1729584000.1001",
  "phone_number": "9876543210",
  "call_direction": "OUTBOUND",
  "station": "1282",
  "agent": "chntechnolog_agent01",
  "agent_email": "chntechnolog_agent01@doocti.com",
  "status": "ANSWERED",
  "duration": 125,
  "start_time": "2026-10-22 10:00:00",
  "end_time": "2026-10-22 10:02:05",
  "recording_path": "https://bmxrx2cviyka.compat.objectstorage.ap-mumbai-1.oraclecloud.com/doocti/cti_chntechnolog_20261009/1729584000.1001.mp3",
  "disposition": "Interested in CRM enterprise setup"
}
```

### 5.2 Inbound Missed Call (JSON)
```http
POST /api/doocti/call-log HTTP/1.1
Host: www.wapluscrm.in
Content-Type: application/json

{
  "uniqueid": "1729584000.1002",
  "phone_number": "9123456780",
  "call_direction": "INBOUND",
  "station": "1282",
  "status": "NO ANSWER",
  "duration": 0,
  "start_time": "2026-10-22 10:15:00",
  "end_time": "2026-10-22 10:15:30"
}
```

### 5.3 Form-Urlencoded POST Example
```http
POST /api/doocti/call-log HTTP/1.1
Host: www.wapluscrm.in
Content-Type: application/x-www-form-urlencoded

uniqueid=1729584000.1003&phone_number=9876543210&station=1282&status=COMPLETED&duration=45&recording_path=https%3A%2F%2Fstorage.oracle.com%2Fdoocti%2Frec.mp3
```

---

## 6. Expected Responses

### 6.1 Success Response (`200 OK`)
When a call log is processed and saved (or updated):
```json
{
  "status": "success",
  "message": "Call log processed and saved successfully",
  "uniqueid": "1729584000.1001",
  "call_log_id": 126,
  "employee_id": 1,
  "lead_id": 28,
  "call_status": "ANSWERED",
  "duration": 125,
  "recording_path": "https://bmxrx2cviyka.compat.objectstorage.ap-mumbai-1.oraclecloud.com/doocti/cti_chntechnolog_20261009/1729584000.1001.mp3"
}
```

### 6.2 Ghost Call Rejection Response (`200 OK`)
If an event contains an invalid phone number or station self-dial loop (e.g., `phone_number == station`):
```json
{
  "status": "ignored",
  "message": "Ghost call rejected: Customer number is missing or equals agent extension",
  "clean_target": "1282"
}
```

### 6.3 Validation Error Response (`400 Bad Request`)
If a required field is malformed or invalid:
```json
{
  "detail": "Phone number is required."
}
```

---

## 7. Supported Call Status & Mapping

WACRM normalizes incoming Doocti statuses to standard CRM call statuses:

| Doocti Raw Status | CRM Stored Status | Meaning |
| :--- | :--- | :--- |
| `ANSWERED`, `SUCCESS`, `CONNECTED` | `ANSWERED` | Call connected and conversation took place. |
| `COMPLETED`, `HANGUP`, `DISCONNECTED`, `ENDED` | `COMPLETED` | Call finished normally with duration. |
| `NO ANSWER`, `NO_ANSWER`, `NOT ANSWERED`, `NOANSWER` | `MISSED` (Inbound)<br>`NO_ANSWER` (Outbound) | Target party did not pick up. |
| `MISSED`, `UNANSWERED`, `DECLINED`, `REJECTED` | `MISSED` | Unanswered or rejected call. |
| `BUSY`, `ENGAGED` | `BUSY` | Line was busy. |
| `FAIL`, `ERROR` | `FAILED` | Telephony carrier / routing failure. |
| `RINGING`, `INCOMING` | `RINGING` | Active call currently ringing. |

---

## 8. Call Recording Delivery Workflow

Doocti handles call recordings through two supported delivery patterns:

### Pattern A: Immediate Delivery (Single CDR Webhook)
If the audio recording URL is already available when the call hangs up:
- Doocti includes `record_location` (or the legacy `recording_path`) in the initial `POST /api/doocti/call-log` webhook.
- WACRM stores the URL directly in `CallLog.recording_url`.
- A URL that is *confirmed* to be an empty placeholder (a header-only object under 500 bytes) is never stored.

### Pattern B: Delayed Delivery (Subsequent Recording-Ready Webhook)
If Asterisk or cloud storage transcribes/processes recordings with a delay:
- Doocti sends the initial call event with `status` and `duration`.
- When the recording upload finishes, Doocti dispatches a second webhook to `POST /api/doocti/call-log` (or `POST /api/doocti/recording`):
  ```json
  {
    "uniqueid": "1729584000.1001",
    "record_location": "https://media.doocti.com/.../1729584000.1001.mp3"
  }
  ```
- **Idempotency Guarantee:** WACRM identifies the existing call via `uniqueid`, attaches the recording URL, and preserves the call status and duration without creating duplicate call entries.

### Pattern C: Resolve Through DooCTI's recordingUrl API
Some calls have no usable object in the Oracle bucket: the object is missing, or it is a
144-byte MP3/LAME header with no audio frames. DooCTI's portal serves those calls from its
own API instead:

```http
GET {portal_url}/recordingUrl?tenant_code=<tenant_code>&date=YYYY-MM-DD&id=<uniqueid>
Authorization: Bearer <portal token>
```

WACRM can call the same endpoint and attach the returned `{ "url": "..." }` to the exact
`provider_call_id`. Configure it through `PUT /api/doocti/config` (all fields optional):

| Config key | Purpose |
| :--- | :--- |
| `portal_url` | Tenant portal host. If omitted, it is read from the login JWT claim `portal_domain`. |
| `recording_api_url` | Login API base (default `https://api-v2.doocti.com`). |
| `recording_api_username` / `recording_api_password` | DooCTI portal login used to obtain a Bearer token automatically (cached 30 minutes). |
| `recording_api_token` | Pre-issued Bearer token, if you already have one. |

The resolver only accepts the provider's response for the call's own authoritative
uniqueid; it never guesses by phone number, timestamp or file size.

> **Diagnostic note:** DooCTI's call list enables the play icon whenever
> `record_location` is a non-empty string. It does not verify that the object has audio
> frames. A 144-byte MP3 (header only) therefore looks playable in DooCTI but shows
> "No recording available" in WACRM. When the resolver returns the same stub URL, the
> recording genuinely failed on the PBX/storage side and must be re-recorded or fixed
> upstream.

### Automatic Localhost / Loopback URL Resolution
If Doocti PBX pushes an internal loopback URL (such as `http://127.0.0.1/audio/...`), WACRM's backend resolver automatically maps the relative path to the cloud storage bucket:
`https://bmxrx2cviyka.compat.objectstorage.ap-mumbai-1.oraclecloud.com/doocti/cti_chntechnolog_20261009/` and converts `.wav` extensions to `.mp3`.

---

## 9. Outbound Call-Initiation Architecture

### 9.1 Current Implementation: Client-Side WebPhone (In-App Dialer)
WACRM currently initiates Doocti calls through the **agent's browser** via an embedded Doocti WebPhone iframe:
- **Iframe Source:** `https://beta3-app.doocti.com/`
- **Component:** `frontend/src/components/Dialer/DooctiInAppDialer.jsx`
- **Method:** Dispatches an HTML5 `window.postMessage` event into the Doocti iframe when the agent clicks "Call" or dials from the keypad:
  ```javascript
  iframeRef.current.contentWindow.postMessage({
    action: "make_call",
    data: {
      phone_number: "9876543210",
      customer_name: "Customer Name"
    }
  }, "https://beta3-app.doocti.com");
  ```
- The Doocti WebPhone initiates the SIP/WebRTC audio call directly inside the agent's browser.

### 9.2 Backend Server-to-Server Click-to-Call (Not Implemented for Doocti)
- WACRM has server-side Click-to-Call providers for Twilio, Exotel, CloudShope, and Tata Smartflo (`POST /api/ivr/call`).
- **WACRM does NOT currently have a backend REST API outbound call-initiation provider for Doocti.**
- If the Doocti team supports server-side call origination, the details in Section 11 must be confirmed by Doocti.

---

## 10. Additional Supporting Doocti Telephony Endpoints

In addition to `/call-log`, WACRM implements the following endpoints to support Doocti agent pop-ups and phonebook sync:

### 10.1 Telephony Screen Pop-Up / Lead Lookup
- **Endpoint:** `GET /api/doocti/lead-by-number` (or `/api/doocti/leads/search`)
- **Query Parameter:** `number` or `phone` (e.g. `?number=9876543210`)
- **Optional Parameter:** `auto_create=true` (creates lead if not found)
- **Response:**
  ```json
  {
    "status": "success",
    "success": true,
    "exists": true,
    "entity_type": "Lead",
    "lead": {
      "id": 28,
      "name": "Ramesh Kumar",
      "phone": "9876543210",
      "lead_owner": "Alex Morgan",
      "status": "CONTACTED",
      "company": "Acme Corp"
    }
  }
  ```

### 10.2 Contact Directory (Phonebook Sync)
- **Endpoint:** `GET /api/doocti/contacts`
- **Query Parameters:** `limit` (default: 100), `offset` (default: 0)
- **Response:**
  ```json
  {
    "status": "success",
    "total": 45,
    "items": [
      {
        "id": 1,
        "name": "Aditi Sharma",
        "company": "TechCorp",
        "phone": "9876543210",
        "email": "aditi@techcorp.com",
        "location": "Chennai"
      }
    ]
  }
  ```

### 10.3 Lead Statuses Catalog
- **Endpoint:** `GET /api/doocti/lead-statuses`
- Returns valid CRM lead statuses for agent wrap-up dispositions.

### 10.4 Call Statuses Catalog
- **Endpoint:** `GET /api/doocti/call-statuses`
- Returns valid call disposition codes.

### 10.5 Agent Disposition Update
- **Endpoint:** `POST /api/doocti/lead/update`
- **Payload:**
  ```json
  {
    "lead_id": 28,
    "status": "INTERESTED",
    "call_notes": "Customer interested in annual enterprise plan. Schedule follow-up demo."
  }
  ```

### 10.6 Call Termination Trigger
- **Endpoint:** `POST /api/doocti/calls/{call_id}/disconnect` (or `/hangup`, `/reject`)
- Terminates or rejects an active call session from the CRM interface.

---

## 11. Technical Details to Confirm with Doocti Team

The following specific items should be requested from the Doocti team:

1. **Webhook Payload Confirmation:**
   - Confirm whether their PBX dispatches webhooks matching the standard fields: `uniqueid`, `phone_number`, `station`, `agent`, `status`, `duration`, `recording_path`.
   - Confirm whether their webhook sends `application/json` or `application/x-www-form-urlencoded`.

2. **Call Recording Delivery Mechanism:**
   - Does Doocti provide a direct, publicly accessible HTTPS recording URL in the CDR webhook?
   - Or are recordings pushed in a separate second webhook after audio transcoding?
   - What IP address or domain hosts the audio recordings?

3. **Inbound vs. Outbound Field Distinctions:**
   - When sending an incoming call CDR, which field contains the calling customer's number (`phone_number`, `caller`, `from_number`, or `customer_number`)?

4. **Server-Side Click-to-Call REST API (If desired):**
   - If Doocti supports server-to-server outbound call initiation (Click-to-Call via backend API instead of WebPhone iframe), please provide:
     - Outbound Originate API endpoint URL.
     - HTTP Headers & Authentication credentials.
     - Request body payload schema (`agent_extension`, `customer_number`, `caller_id`).
     - Webhook or callback event format for tracking the initiated call status.

5. **Webhook Authentication Requirements:**
   - Does Doocti require or support a pre-shared header token (e.g. `X-API-KEY` or `Authorization: Bearer <token>`)?
   - What are the source outbound IP addresses of the Doocti webhook servers for firewall whitelisting?

---

## 12. Verification & Test Summary

Automated integration tests were executed against the FastAPI backend using `backend/tests/test_doocti_integration.py`:

| Test Case | Method & Route | Tested Payload / Action | Result |
| :--- | :--- | :--- | :--- |
| **Call Status Catalog** | `GET /api/doocti/call-statuses` | Verifies list of telephony dispositions | **PASS** (200 OK) |
| **Lead Status Catalog** | `GET /api/doocti/lead-statuses` | Verifies list of CRM lead stages | **PASS** (200 OK) |
| **JSON Call Log Push** | `POST /api/doocti/call-log` | Full Doocti CDR payload (uniqueid, phone, station, agent, status, duration, recording) | **PASS** (200 OK) |
| **Form Data Call Log** | `POST /api/doocti/call-log` | `application/x-www-form-urlencoded` CDR push | **PASS** (200 OK) |
| **Query Param CDR** | `GET /api/doocti/call-log` | URL query parameters push | **PASS** (200 OK) |
| **Delayed Recording Update** | `POST /api/doocti/call-log` | Secondary webhook with `uniqueid` + `recording_path` preserving status & duration | **PASS** (200 OK) |
| **Ghost Call Protection** | `POST /api/doocti/call-log` | Self-extension loop detection (`phone == station`) | **PASS** (Ignored) |

All 7 integration unit tests passed in 0.587s.
