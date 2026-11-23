# External Proforma Payment Webhook

This document describes how the WA Quote / WAHRMS ERP notifies Wa CRM that a
customer payment has been confirmed. A verified successful payment updates the
Proforma, records a Finance `Payment`, and moves the linked Sales Lead to
`WON`.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/api/integrations/proforma/payments/webhook` | Preferred endpoint |
| `POST` | `/api/integrations/proforma/payments/callback` | Alias |
| `POST` | `/api/integrations/proforma/webhook` | Alias |
| `POST` | `/api/integrations/waquote/webhook` | Existing WA Quote endpoint; same processor |
| `GET` | `/api/integrations/proforma/{id_or_number}/payments` | Payment history for a Proforma |

## Authentication

All webhook deliveries must be authenticated. Two modes are supported.

### 1. HMAC signature (preferred)

Send one of these headers:

```http
X-WAQuote-Signature: t=1763884800,v1=<hex hmac>
```

```http
X-Hub-Signature-256: sha256=<hex hmac>
```

- `t=...,v1=...` signs `<t>.<raw request body>` with HMAC-SHA256. The timestamp
  must be within five minutes of the CRM server time.
- `sha256=...` (or a bare hex value) signs the raw request body only.

The signing secret is read from, in order:

1. `WAQUOTE_WEBHOOK_SECRET`
2. `PROFORMA_WEBHOOK_SECRET`
3. `CRM_WEBHOOK_SECRET`
4. `webhook_secret` / `signing_secret` / `hmac_secret` in the `WAQUOTE`,
   `QUOTETASK`, `PROFORMA_API`, `EXTERNAL_API` or `DESTINATION_ERP` integration
   configuration.

If a signature header is present but invalid, the request is rejected even when
a valid API key is also supplied.

### 2. API key fallback

```http
X-API-Key: YOUR_SECURE_INTEGRATION_KEY
```

or:

```http
Authorization: Bearer YOUR_SECURE_INTEGRATION_KEY
```

The key is the same integration key used by the inbound Proforma API.

## Canonical payload

```json
{
  "event": "payment.success",
  "eventId": "evt_8f2c1d9a",
  "data": {
    "document": {
      "id": "ERP-DOC-1001",
      "number": "PI-2026-0042",
      "totalPaid": 40000,
      "currency": "INR"
    },
    "payment": {
      "id": "EXT-PAY-7781",
      "transactionId": "UTR-20261123-9911",
      "amount": 40000,
      "currency": "INR",
      "method": "UPI",
      "paymentDate": "2026-11-23T10:30:00+05:30",
      "bankName": "HDFC Bank"
    }
  },
  "metadata": {
    "crmProformaId": 42
  }
}
```

### Proforma resolution

The CRM resolves the target Proforma using the identifiers supplied by the ERP:

1. `metadata.crmProformaId` (or `crmProformaId` at the payload root),
2. `Quotation.external_proforma_id` (`document.id`, `proformaId`,
   `externalProformaId`, ...),
3. the Proforma number (`document.number`, `proformaNumber`, ...).

Every supplied identifier must resolve to the same Proforma. If two identifiers
point at different documents, the event is acknowledged but ignored; no Lead is
changed. The CRM never matches a payment by customer name or phone number.

### Amounts

- `payment.amount` is the amount of **this transaction**.
- `document.totalPaid` / `cumulativePaid` / `amountPaid` on the document is the
  cumulative amount paid so far. The CRM uses the larger of
  `existing + transaction` and the cumulative value.
- A `PAID` event without any amount is treated as payment of the remaining
  balance. A `PARTIALLY_PAID` event without an amount is ignored as ambiguous.

### Status values

Processed as successful (case-insensitive, punctuation ignored):

`PAID`, `PAYMENT_RECEIVED`, `RECEIVED`, `SUCCESS`, `SUCCESSFUL`, `SUCCEEDED`,
`CAPTURED`, `SETTLED`, `COMPLETED`, `CONFIRMED`, `PAYMENT_SUCCESS`,
`PARTIALLY_PAID`, `PARTIAL`, `PARTIAL_PAYMENT`, `PART_PAYMENT`, `PARTLY_PAID`.

Ignored without changing the Lead:

`FAILED`, `PAYMENT_FAILED`, `CANCELLED`, `PENDING`, `PROCESSING`, `INITIATED`,
`REFUNDED`, `UNVERIFIED`, `REJECTED`, `DECLINED`, `EXPIRED`, `VOID`, `UNPAID`,
`NOT_PAID`, plus any unknown/unverified status.

A negative event name (for example `payment.failed`) overrides a stale paid
document status. Proforma lifecycle events such as `proforma.created`,
`proforma.sent` and `proforma.updated` do not mark a Lead `WON`; they need an
explicit payment block/transaction ID to be treated as payment evidence.

## Behaviour

For a confirmed successful payment, in one database transaction:

1. A `proforma_payment_events` idempotency row is written.
2. One `Payment` row is recorded with the external transaction ID, method,
   bank and payment date.
3. `Quotation.amount_paid` and `payment_status` are updated (`paid` or
   `partial`). The outstanding balance is derived as
   `grand_total - amount_paid`.
4. The linked `Lead` is set to `WON` unless it is already `WON`/`CONVERTED` or
   has advanced to `CONVERTED_TO_SUPPORT`. A `LeadStatusHistory` row preserves
   the previous status, and Sales ownership is not changed.
5. The `FinanceHandoff` is created or updated. A partial payment keeps the
   handoff `PAYMENT_PENDING` with `payment_status=PARTIALLY_PAID`; a full
   payment sets both to `PAID`.
6. A `SupportHandoff` is created on the first successful payment (including a
   partial payment) so onboarding can begin. Later payments update the amount
   without creating another handoff.
7. Sales, Finance and Support users receive in-app notifications. The payment is
   written to the Lead activity timeline and the workflow timeline, and an
   `AuditLog` and `IntegrationLog` entry are written.

A partial payment still marks the Lead `WON`; it does not wait for the balance.

## Idempotency and retries

- `eventId` (or `X-Webhook-Event-ID` / `X-Event-ID`) is stored uniquely.
- `(provider, transactionId)` is unique. Two events describing the same bank
  transaction are treated as duplicates.
- If the ERP omits both identifiers, a deterministic fingerprint of the
  Proforma, status and amount is used, so a retry does not double-count the
  payment.
- A duplicate delivery returns HTTP `200` with:

```json
{
  "ok": true,
  "status": "duplicate",
  "duplicate": true,
  "reason": "duplicate_transaction_id",
  "transaction_id": "UTR-20261123-9911"
}
```

Ignored events also return HTTP `200` with `"status": "ignored"` so the ERP
does not retry a terminal failure forever. Invalid credentials return `401` or
`403`; malformed JSON returns `400`; unexpected processing failures return
`500` so the ERP can retry.

## Response example

```json
{
  "ok": true,
  "status": "processed",
  "duplicate": false,
  "proforma_id": 42,
  "proforma_number": "PI-2026-0042",
  "lead_id": 17,
  "lead_status": "WON",
  "lead_status_changed": true,
  "payment_id": 903,
  "payment_number": "PAY-2026-WQ0007",
  "transaction_id": "UTR-20261123-9911",
  "amount_received": 40000.0,
  "total_paid": 40000.0,
  "outstanding_balance": 60000.0,
  "payment_status": "PARTIALLY_PAID",
  "finance_handoff_id": 88,
  "support_handoff_id": 54,
  "support_handoff_created": true,
  "auth_mode": "signature",
  "source": "PROFORMA_API"
}
```

## Signed request example

```bash
BODY='{"event":"payment.success","data":{"document":{"id":"ERP-DOC-1001"},"payment":{"transactionId":"UTR-1","amount":1000}}}'
TS=$(date +%s)
SIG=$(printf '%s.%s' "$TS" "$BODY" | openssl dgst -sha256 -hmac "$WAQUOTE_WEBHOOK_SECRET" -hex | sed 's/^.* //')

curl -X POST https://crm.example.com/api/integrations/proforma/payments/webhook \
  -H "Content-Type: application/json" \
  -H "X-WAQuote-Signature: t=$TS,v1=$SIG" \
  --data "$BODY"
```

## Tests

The isolated SQLite suite covers full, partial and multiple payments,
idempotency, failed/pending events, ambiguous Proforma references, signature and
API-key authentication, and `CONVERTED_TO_SUPPORT` preservation:

```bash
backend/venv/Scripts/python.exe backend/tests/test_proforma_payment_won.py -v
```
