# STANDARD OPERATING PROCEDURE (SOP)
## External Proforma & Client Integration API
**Document Code**: SOP-INT-WACRM-001  
**Version**: 1.0.0  
**Effective Date**: October 2026  
**Target Audience**: Full-Stack Developers, Backend Engineers, ERP Integration Specialists  
**Security Level**: Confidential / Technical Integration  

---

### Executive Summary & Purpose
This document provides the technical Standard Operating Procedure (SOP) for connecting an external website, e-commerce store, billing portal, or ERP to **Wa CRM**.

By following this SOP, external systems can securely:
1. **Transmit customer and billing data** to Wa CRM in real-time.
2. **Issue or synchronize Proforma Invoices** with line-item accuracy.
3. **Obtain authoritative GST tax distributions** (CGST, SGST, IGST) calculated by the CRM.
4. **Retrieve secure PDF download links** for generated billing documents.
5. **Prevent duplicate transactions** using server-enforced idempotency keys.

---

### 1. Connection Prerequisites & Credentials

| Parameter | Production Value | Development / Local |
| :--- | :--- | :--- |
| **Protocol** | HTTPS (Strictly Enforced) | HTTP / HTTPS |
| **Base URL** | `http://www.wapluscrm.in` | `http://localhost:8000` |
| **Authentication Scheme** | API Key Header (`X-API-Key`) | API Key Header (`X-API-Key`) |
| **API Key** | `wacrm_ext_live_8849204128f73a0e691823c91` | `wacrm_ext_live_8849204128f73a0e691823c91` |
| **Data Format** | JSON (`application/json; charset=utf-8`) | JSON |
| **Interactive Docs** | `http://www.wapluscrm.in/docs` | `http://localhost:8000/docs` |

> [!IMPORTANT]
> **Security Requirement**: Never embed `wacrm_ext_live_...` in client-side JavaScript, single-page browser apps, or public source control. Store the credential in backend environment variables (`.env`).

---

### 2. Available Endpoints

| HTTP Method | Route | Purpose |
| :--- | :--- | :--- |
| **`POST`** | `/api/integrations/proforma` | **Main Integration Endpoint**: Ingests, validates, and creates/synchronizes a Proforma Invoice and Client record. |
| **`GET`** | `/api/integrations/proforma/{id_or_number}` | **Verification Endpoint**: Retrieves authoritative document details by numeric ID or Document Number (e.g. `PI-2026-0042`). |
| **`GET`** | `/api/integrations/proforma` | **Query Endpoint**: Lists and paginates Proformas with search, customer ID, and date filters. |
| **`OPTIONS`**| `/api/integrations/proforma` | **CORS Preflight**: Automatically responds `200 OK` for cross-origin preflight requests. |

---

### 3. Step-by-Step Developer Implementation Guide

#### Phase 1: Authentication Header Setup
Every outbound request from your server MUST include the authentication header. You can use either of the following two standard formats:

**Format A (Recommended):**
```http
X-API-Key: wacrm_ext_live_8849204128f73a0e691823c91
```

**Format B (Standard Bearer):**
```http
Authorization: Bearer wacrm_ext_live_8849204128f73a0e691823c91
```

*If this header is omitted or incorrect, the API immediately returns `HTTP 401 Unauthorized` or `HTTP 403 Forbidden`.*

---

#### Phase 2: Duplicate Prevention (Idempotency Key)
To prevent duplicate records from network timeouts, page refreshes, or retry loops:
- Generate a unique UUIDv4 (e.g., `idem_c9f28d84-a12b-4e8a-874e-7b24db0a59a3`) on your server for each transaction.
- Pass it in the header `X-Idempotency-Key` or in the payload field `idempotencyKey`.
- If an identical key is received within 24 hours, the CRM **returns the previously created document** (`processingStatus: "AUTHORITATIVE_VERIFIED"`) without creating a duplicate record.

---

#### Phase 3: Authoritative Tax & State Code Logic
The CRM automatically determines GST compliance based on the client's state code:
- **Intra-state Supply (State Code `33` - Tamil Nadu)**:  
  Taxes are split equally into **CGST (9%)** and **SGST (9%)**.
- **Inter-state Supply (All Other States / UTs)**:  
  Taxes are applied as **IGST (18%)**.
- **Authoritative Re-calculation**:  
  The CRM calculates: `Line Taxable = (rate * qty) - discount`. If the caller passes a miscalculated total, the CRM overrides it with the legally verified figures and flags an advisory note in `warnings`.

---

### 4. Payload Specifications: `POST /api/integrations/proforma`

#### Request JSON Schema & Field Dictionary

| Field | Type | Required? | Description & Allowed Values |
| :--- | :--- | :---: | :--- |
| `idempotencyKey` | `string` | Recommended | Unique transaction UUID for duplicate prevention. |
| `companyName` | `string` | **Yes\*** | Legal entity or trade name of the client. (\*Either `companyName` or `contactPerson` required). |
| `contactPerson` | `string` | **Yes\*** | Primary contact / signatory name. |
| `phone` | `string` | **Yes** | Phone number with country code (e.g. `+91 9876543210`). |
| `email` | `string` | Optional | Email address for invoice delivery. |
| `gstin` | `string` | Optional | 15-character GSTIN (e.g., `33AAAAA1234A1Z5`). |
| `billingAddress` | `object` | Optional | Structured address object containing `line1`, `city`, `state`, `stateCode`, `pincode`. |
| `proformaNumber`| `string` | Optional | Existing invoice number. If omitted, CRM auto-generates (e.g. `PI-2026-0042`). |
| `quotationNumber`| `string` | Optional | Linked quote reference (e.g. `QT-2026-0015`). |
| `productCategory`| `string` | Optional | `wahrms` (Software, default) or `biometric` (Hardware). |
| `selectedBundle` | `string` | Optional | `hr_atm`, `hr_payroll`, or `hr_atm_payroll`. |
| `lineItems` | `array` | **Yes** | Array of item objects (minimum 1 item required). |
| `lineItems[].name`| `string` | **Yes** | Item name or bundle title. |
| `lineItems[].description` | `string` | Optional | Detailed specification or scope of work. |
| `lineItems[].hsn` | `string` | Optional | HSN/SAC code (`998314` for software, `85437099` for biometric hardware). |
| `lineItems[].qty` | `number` | **Yes** | Quantity (must be $> 0$). |
| `lineItems[].rate`| `number` | **Yes** | Unit price excluding tax (must be $\ge 0$). |
| `lineItems[].discount` | `number` | Optional | Flat discount deducted from line item (default: `0.0`). |
| `lineItems[].gstRate` | `number` | Optional | Decimal e.g. `0.18` (18%) or integer percentage `18` (default: `0.18`). |
| `termsAndConditions` | `string` | Optional | Commercial and payment terms. |

---

### 5. Standard Request & Response Example

#### Live Example Request
```http
POST /api/integrations/proforma HTTP/1.1
Host: www.wapluscrm.in
X-API-Key: wacrm_ext_live_8849204128f73a0e691823c91
X-Idempotency-Key: idem_7b8a1c92-34ef-4b21-8809-5a9e32bf1014
Content-Type: application/json

{
  "idempotencyKey": "idem_7b8a1c92-34ef-4b21-8809-5a9e32bf1014",
  "companyName": "Acme Global Solutions Pvt Ltd",
  "contactPerson": "Rajesh Kumar",
  "phone": "+91 9876543210",
  "email": "billing@acmeglobal.com",
  "gstin": "33AAAAA1234A1Z5",
  "billingAddress": {
    "line1": "Level 4, Tidel Park, Rajiv Gandhi Salai",
    "city": "Chennai",
    "state": "Tamil Nadu",
    "stateCode": "33",
    "pincode": "600113",
    "country": "India"
  },
  "productCategory": "wahrms",
  "selectedBundle": "hr_payroll",
  "lineItems": [
    {
      "name": "WAHRMS Core HR + Payroll Cloud Suite",
      "description": "Annual software license for up to 50 active employees",
      "hsn": "998314",
      "qty": 1,
      "rate": 75000.00,
      "discount": 0.00,
      "gstRate": 0.18
    }
  ],
  "termsAndConditions": "1. Software onboarding commences upon receipt of payment.\n2. Prices subject to 18% GST."
}
```

#### Live Example Response (`201 Created`)
```json
{
  "success": true,
  "requestId": "req_88a91b2c4d",
  "idempotencyKey": "idem_7b8a1c92-34ef-4b21-8809-5a9e32bf1014",
  "processingStatus": "CREATED",
  "customerId": 101,
  "customerName": "Rajesh Kumar",
  "companyName": "Acme Global Solutions Pvt Ltd",
  "proformaId": 204,
  "proformaNumber": "PI-2026-0042",
  "quotationNumber": null,
  "authoritativeSummary": {
    "taxableSubtotal": 75000.0,
    "taxMode": "intra",
    "cgst": 6750.0,
    "sgst": 6750.0,
    "igst": 0.0,
    "totalTax": 13500.0,
    "roundOff": 0.0,
    "grandTotal": 88500.0,
    "lineItemsCount": 1
  },
  "pdfDownloadUrl": "/api/integrations/waquote/proformas/204/download",
  "syncedAt": "2026-10-17T11:10:00.000000+00:00",
  "message": "Proforma Invoice #PI-2026-0042 successfully registered in CRM.",
  "warnings": null
}
```

---

### 6. Ready-to-Copy Developer Code Snippets

#### A. Node.js (Axios)
```javascript
const axios = require('axios');
const crypto = require('crypto');

const CRM_BASE_URL = 'http://www.wapluscrm.in';
const CRM_API_KEY = process.env.CRM_EXTERNAL_API_KEY || 'wacrm_ext_live_8849204128f73a0e691823c91';

async function sendProformaToCrm(orderData) {
  const idempotencyKey = `idem_${crypto.randomUUID()}`;

  const payload = {
    idempotencyKey,
    companyName: orderData.companyName,
    contactPerson: orderData.contactName,
    phone: orderData.phone,
    email: orderData.email,
    gstin: orderData.gstin || '',
    billingAddress: {
      line1: orderData.addressLine1 || 'Address',
      city: orderData.city || 'Chennai',
      state: orderData.state || 'Tamil Nadu',
      stateCode: orderData.stateCode || '33',
      pincode: orderData.pincode || '600001',
      country: 'India'
    },
    productCategory: 'wahrms',
    lineItems: orderData.items.map(item => ({
      name: item.title,
      description: item.description || '',
      hsn: item.hsn || '998314',
      qty: Number(item.quantity || 1),
      rate: Number(item.unitPrice || 0),
      discount: Number(item.discount || 0),
      gstRate: 0.18
    })),
    termsAndConditions: 'Standard payment terms apply.'
  };

  try {
    const response = await axios.post(`${CRM_BASE_URL}/api/integrations/proforma`, payload, {
      headers: {
        'X-API-Key': CRM_API_KEY,
        'X-Idempotency-Key': idempotencyKey,
        'Content-Type': 'application/json'
      },
      timeout: 10000
    });

    console.log('CRM Proforma Created:', response.data.proformaNumber);
    console.log('Authoritative Total:', response.data.authoritativeSummary.grandTotal);
    return response.data;
  } catch (error) {
    console.error('CRM Integration Error:', error.response?.data || error.message);
    throw error;
  }
}

module.exports = { sendProformaToCrm };
```

#### B. Python (httpx)
```python
import os
import uuid
import httpx

CRM_BASE_URL = "http://www.wapluscrm.in"
CRM_API_KEY = os.getenv("CRM_EXTERNAL_API_KEY", "wacrm_ext_live_8849204128f73a0e691823c91")

def issue_proforma_in_crm(order_data: dict) -> dict:
    idempotency_key = f"idem_{uuid.uuid4()}"
    
    payload = {
        "idempotencyKey": idempotency_key,
        "companyName": order_data.get("company_name"),
        "contactPerson": order_data.get("contact_person"),
        "phone": order_data.get("phone"),
        "email": order_data.get("email"),
        "gstin": order_data.get("gstin"),
        "billingAddress": order_data.get("billing_address", {
            "line1": "123 Tech Park",
            "city": "Chennai",
            "state": "Tamil Nadu",
            "stateCode": "33",
            "pincode": "600001",
            "country": "India"
        }),
        "productCategory": "wahrms",
        "lineItems": [
            {
                "name": item["name"],
                "hsn": item.get("hsn", "998314"),
                "qty": float(item.get("qty", 1)),
                "rate": float(item["rate"]),
                "discount": float(item.get("discount", 0)),
                "gstRate": float(item.get("gst_rate", 0.18))
            }
            for item in order_data.get("items", [])
        ]
    }
    
    headers = {
        "X-API-Key": CRM_API_KEY,
        "X-Idempotency-Key": idempotency_key,
        "Content-Type": "application/json"
    }
    
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{CRM_BASE_URL}/api/integrations/proforma",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
```

#### C. PHP (cURL)
```php
<?php

function syncProformaToCrm($orderData) {
    $baseUrl = 'http://www.wapluscrm.in';
    $apiKey  = 'wacrm_ext_live_8849204128f73a0e691823c91';
    $idemKey = 'idem_' . bin2hex(random_bytes(16));

    $payload = [
        'idempotencyKey' => $idemKey,
        'companyName'    => $orderData['company_name'],
        'contactPerson'  => $orderData['contact_person'],
        'phone'          => $orderData['phone'],
        'email'          => $orderData['email'],
        'gstin'          => $orderData['gstin'] ?? '',
        'billingAddress' => [
            'line1'     => $orderData['address'] ?? 'Address on file',
            'city'      => 'Chennai',
            'state'     => 'Tamil Nadu',
            'stateCode' => '33',
            'pincode'   => '600001',
            'country'   => 'India'
        ],
        'productCategory' => 'wahrms',
        'lineItems'      => $orderData['items']
    ];

    $ch = curl_init($baseUrl . '/api/integrations/proforma');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'X-API-Key: ' . $apiKey,
        'X-Idempotency-Key: ' . $idemKey,
        'Content-Type: application/json'
    ]);
    curl_setopt($ch, CURLOPT_TIMEOUT, 10);

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($httpCode >= 200 && $httpCode < 300) {
        return json_decode($response, true);
    } else {
        throw new Exception("CRM Integration Failed (HTTP $httpCode): " . $response);
    }
}
```

---

### 7. Error Handling & Troubleshooting Guide

| HTTP Status Code | Meaning | Cause & Resolution |
| :---: | :--- | :--- |
| **`401 Unauthorized`** | Missing Authentication Header | Header `X-API-Key` or `Authorization: Bearer <KEY>` was not passed. Add the header. |
| **`403 Forbidden`** | Invalid API Key | The passed key did not match the configured secret. Verify that you are sending `wacrm_ext_live_8849204128f73a0e691823c91`. |
| **`422 Unprocessable`** | Missing Required Fields | `companyName`/`contactPerson` or `lineItems` was missing or empty. |
| **`429 Too Many Requests`** | Rate Limit Exceeded | Client exceeded 120 requests/minute. Implement exponential backoff. |
| **`500 Internal Error`** | Server Exception | Check request syntax or contact CRM Integration Support. |

---

### 8. Verification & Sign-off

- **Swagger UI Interactive Sandbox**: [http://www.wapluscrm.in/docs](http://www.wapluscrm.in/docs)
- **OpenAPI 3.0 Raw Specification File**: [`backend/docs/external_proforma_openapi.json`](file:///c:/Users/CHN/Desktop/Wa%20CRM/backend/docs/external_proforma_openapi.json)
- **CRM Integration Support**: `support@wapluscrm.in`
