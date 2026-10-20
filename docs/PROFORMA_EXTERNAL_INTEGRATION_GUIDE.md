# 🚀 Wa CRM External Proforma & Client Integration API
### Developer Integration Guide & Reference

This guide explains how your external website, ERP, or billing system can securely exchange **client details** and **Proforma Invoices** with **Wa CRM** via our documented server-to-server integration endpoint:

```http
POST /api/integrations/proforma
```

---

## 1. Core Endpoints & Base URLs

| Environment | Base URL | Protocol |
| :--- | :--- | :--- |
| **Production** | `http://www.wapluscrm.in` | HTTPS (Enforced) |
| **Local / Dev** | `http://localhost:8000` | HTTP |

### Supported API Routes

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **`POST`** | `/api/integrations/proforma` | Submit, ingest, or authoritatively synchronize a Proforma Invoice and client profile. |
| **`GET`** | `/api/integrations/proforma/{id_or_number}` | Query/verify single authoritative Proforma by ID or Number (e.g., `PI-2026-0042`). |
| **`GET`** | `/api/integrations/proforma` | List and paginate authoritative Proforma Invoices with search and customer filters. |
| **`OPTIONS`**| `/api/integrations/proforma` | CORS preflight handler for browser-based callers. |

---

## 2. Authentication & Security

All requests must be authenticated using a pre-shared server-to-server API Key passed in either of the following standard headers:

### Header Option A (Recommended):
```http
X-API-Key: YOUR_SECURE_INTEGRATION_KEY
```

### Header Option B (Bearer Format):
```http
Authorization: Bearer YOUR_SECURE_INTEGRATION_KEY
```

### Security Rules:
1. **Never expose the API key in client-side JavaScript or public frontend repositories.**
2. **Rate Limiting**: Throttled at **120 requests per minute** per client IP / key. Exceeding callers receive `HTTP 429 Too Many Requests`.
3. **Data Sanitization**: Secrets and bearer tokens are automatically scrubbed from CRM error logs and database traces.

---

## 3. Duplicate Prevention & Idempotency Rules

To guarantee that network retries or double clicks never duplicate documents or customer accounts in the CRM:

1. **Provide an Idempotency Key**:
   Send a unique client UUID or transaction ID either in the header:
   ```http
   X-Idempotency-Key: idem_unique_request_uuid_v4
   ```
   or in the JSON payload body as `idempotencyKey`.

2. **Deduplication Behavior**:
   - If a request with the same `idempotencyKey` or `proformaNumber` is retried, the CRM returns the existing authoritative record with status:
     ```json
     "processingStatus": "AUTHORITATIVE_VERIFIED"
     ```
   - No duplicate database record is created.

---

## 4. Authoritative Verification vs Arbitrary Totals

**Key Rule**: The CRM enforces strict, authoritative calculation:
- Line item rates, quantities, and discounts are verified server-side.
- **GST Distribution**:
  - If client billing state is **Tamil Nadu (State Code `33`)**, the CRM applies intra-state tax (**CGST 9% + SGST 9%**).
  - If billing state is outside Tamil Nadu, the CRM applies inter-state tax (**IGST 18%**).
- If an external caller passes an arbitrary or miscalculated `grandTotal`, the CRM computes the authoritative tax and returns it in `authoritativeSummary`, along with an advisory warning in `warnings`.

---

## 5. Ingest / Synchronize Proforma Request

### HTTP Request
```http
POST /api/integrations/proforma HTTP/1.1
Host: www.wapluscrm.in
X-API-Key: YOUR_INTEGRATION_KEY
X-Idempotency-Key: idem_req_20261017_9921
Content-Type: application/json
```

### Request Payload (`application/json`)
```json
{
  "idempotencyKey": "idem_req_20261017_9921",
  "customerId": 101,
  "companyName": "Acme Global Solutions Pvt Ltd",
  "contactPerson": "Rajesh Kumar",
  "email": "billing@acmeglobal.com",
  "phone": "+91 9876543210",
  "gstin": "33AAAAA1234A1Z5",
  "billingAddress": {
    "line1": "Level 4, Tidel Park, Rajiv Gandhi Salai",
    "city": "Chennai",
    "state": "Tamil Nadu",
    "stateCode": "33",
    "pincode": "600113",
    "country": "India"
  },
  "quotationNumber": "QT-2026-0012",
  "proformaNumber": "PI-2026-0042",
  "productCategory": "wahrms",
  "selectedBundle": "hr_payroll",
  "lineItems": [
    {
      "name": "WAHRMS Core HR + Payroll Cloud Suite",
      "description": "Annual subscription for 50 employees including statutory compliance & payroll processing",
      "hsn": "998314",
      "qty": 1,
      "rate": 75000.00,
      "discount": 0.00,
      "gstRate": 0.18
    }
  ],
  "subtotal": 75000.00,
  "grandTotal": 88500.00,
  "termsAndConditions": "1. Software onboarding commences upon payment receipt.\n2. Prices subject to 18% GST."
}
```

---

## 6. Response Formats

### A. Success Response (`201 Created` or `200 OK`)
```json
{
  "success": true,
  "requestId": "req_88a91b2c4d",
  "idempotencyKey": "idem_req_20261017_9921",
  "processingStatus": "CREATED",
  "customerId": 101,
  "customerName": "Rajesh Kumar",
  "companyName": "Acme Global Solutions Pvt Ltd",
  "proformaId": 204,
  "proformaNumber": "PI-2026-0042",
  "quotationNumber": "QT-2026-0012",
  "authoritativeSummary": {
    "taxableSubtotal": 75000.00,
    "taxMode": "intra",
    "cgst": 6750.00,
    "sgst": 6750.00,
    "igst": 0.00,
    "totalTax": 13500.00,
    "roundOff": 0.00,
    "grandTotal": 88500.00,
    "lineItemsCount": 1
  },
  "pdfDownloadUrl": "/api/integrations/waquote/proformas/204/download",
  "syncedAt": "2026-10-17T10:45:00.000000+00:00",
  "message": "Proforma Invoice #PI-2026-0042 successfully registered in CRM.",
  "warnings": null
}
```

### B. Unauthorized (`401 Unauthorized`)
```json
{
  "detail": "Missing server-to-server authentication. Provide 'X-API-Key: <key>' or 'Authorization: Bearer <key>'."
}
```

### C. Rate Limit (`429 Too Many Requests`)
```json
{
  "detail": "Rate limit exceeded. Maximum 120 requests per minute allowed."
}
```

---

## 7. Working Integration Code Examples

### cURL
```bash
curl -X POST "http://www.wapluscrm.in/api/integrations/proforma" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "X-Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{
    "companyName": "Test Client Corp",
    "contactPerson": "Suresh Raina",
    "phone": "9840012345",
    "email": "finance@testclient.com",
    "productCategory": "wahrms",
    "lineItems": [
      {
        "name": "WAHRMS HR + ATM",
        "hsn": "998314",
        "qty": 1,
        "rate": 50000.00,
        "gstRate": 0.18
      }
    ]
  }'
```

### Node.js (Axios)
```javascript
const axios = require('axios');
const crypto = require('crypto');

async function syncProformaToCrm(proformaData) {
  const idempotencyKey = crypto.randomUUID();

  try {
    const response = await axios.post(
      'http://www.wapluscrm.in/api/integrations/proforma',
      proformaData,
      {
        headers: {
          'X-API-Key': process.env.CRM_INTEGRATION_KEY,
          'X-Idempotency-Key': idempotencyKey,
          'Content-Type': 'application/json'
        },
        timeout: 10000
      }
    );

    console.log('CRM Proforma Ingested Successfully:', response.data);
    return response.data;
  } catch (error) {
    console.error('CRM Integration Failed:', error.response?.data || error.message);
    throw error;
  }
}
```

### Python (httpx)
```python
import httpx
import uuid

def push_proforma_to_crm(proforma_payload: dict, api_key: str):
    headers = {
        "X-API-Key": api_key,
        "X-Idempotency-Key": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }

    with httpx.Client(timeout=10.0) as client:
        resp = client.post(
            "http://www.wapluscrm.in/api/integrations/proforma",
            headers=headers,
            json=proforma_payload
        )
        resp.raise_for_status()
        return resp.json()
```

---

## 8. Proforma Issue Workflow (Push & Pull)

The CRM supports two cooperative integration models:

```
[ CRM User issues Proforma ]
              │
              ├──> PUSH (Real-time Webhook / DestinationSyncService)
              │    CRM immediately pushes client & proforma payload to Destination ERP
              │
              └──> PULL / QUERY API
                   External website calls POST /api/integrations/proforma (or GET)
                   to verify, fetch, or authoritatively synchronize billing records
```
