# Brochure Download API — Website Integration Handoff

Use this API on the company website to record brochure download form
submissions. Records appear only in **Website Enquiries → Brochure Download
People** inside the CRM. They do not create or appear as normal Leads.

---

## Endpoint

| Item | Value |
| :--- | :--- |
| Method | `POST` |
| Production URL | `https://www.wapluscrm.in/api/integrations/website/brochures` |
| Alias URL | `https://www.wapluscrm.in/api/integrations/website/brochure` |
| Local test URL | `http://127.0.0.1:8000/api/integrations/website/brochures` |
| Authentication | None — public website endpoint |
| Content-Type | `application/json` |
| Response | `201 Created` |

If the CRM is hosted on a different domain, replace `https://www.wapluscrm.in`
with that domain. The path stays the same. If HTTPS is not enabled on the CRM
host, use `http://www.wapluscrm.in` instead. When the form and the CRM run on
the same domain, a relative URL works too:

```text
/api/integrations/website/brochures
```

---

## Request Body

Send JSON. Unknown extra fields are ignored.

| Field | Type | Required | Notes |
| :--- | :--- | :--- | :--- |
| `name` | string | **Yes** | Customer full name |
| `phone` | string | **Yes\*** | WhatsApp/contact number. Include country code or send it in `countryCode` |
| `countryCode` | string | Recommended | Country calling code, e.g. `"91"` |
| `email` | string | Optional | Required only when `phone` is not supplied |
| `whatsapp` / `whatsapp_number` / `whatsappNumber` | string | Optional | Alternative to `phone` |
| `product_name` | string | Recommended | Product the brochure belongs to, e.g. `"HRMS"` |
| `product_id` | string | Optional | Your website's product ID |
| `brochure_name` | string | Recommended | Brochure/document name, e.g. `"HRMS Product Brochure"` |
| `brochure_id` | string | Optional | Your website's brochure/document ID |
| `website_id` | string | Optional | Website identifier, e.g. `"wapluscrm"` |
| `website_name` | string | Optional | Website display name |
| `landing_page` | string | Optional | Page URL where the form was submitted |
| `campaign` | string | Optional | Campaign/source label |
| `form_type` | string | Recommended | Use `"brochure_download"` |
| `message` | string | Optional | Additional message from the visitor |
| `firstName` + `lastName` | string | Optional | Can be sent instead of `name` |

\* At least one of `phone` or `email` is required.

### Minimum payload

```json
{
  "name": "Arun Kumar",
  "phone": "9876543210",
  "countryCode": "91",
  "brochure_name": "HRMS Product Brochure"
}
```

### Recommended full payload

```json
{
  "name": "Arun Kumar",
  "phone": "9876543210",
  "countryCode": "91",
  "email": "arun@example.com",
  "product_name": "HRMS",
  "product_id": "prod-hrms",
  "brochure_name": "HRMS Product Brochure",
  "brochure_id": "brochure-hrms-2026",
  "website_id": "wapluscrm",
  "website_name": "WA Plus CRM",
  "landing_page": "https://www.wapluscrm.in/hrms",
  "campaign": "HRMS Brochure Download",
  "form_type": "brochure_download"
}
```

---

## Success Response (`201`)

```json
{
  "success": true,
  "message": "Brochure download recorded successfully",
  "lead_id": null,
  "enquiry_id": 12,
  "record_type": "BROCHURE_ENQUIRY",
  "is_duplicate": false,
  "submission_count": 1
}
```

### Repeat submission response (`201`)

Same contact + same product/brochure is deduplicated:

```json
{
  "success": true,
  "message": "Brochure download already recorded; submission updated successfully",
  "lead_id": null,
  "enquiry_id": 12,
  "record_type": "BROCHURE_ENQUIRY",
  "is_duplicate": true,
  "submission_count": 2
}
```

`lead_id` is only populated when the phone/email already exists as a Lead in the
CRM. It is a reference — **this API never creates a Lead or Customer**.

### Error responses

| Status | Meaning | Example |
| :--- | :--- | :--- |
| `400` | Missing name | `{"detail": "Contact name is required."}` |
| `400` | Missing phone and email | `{"detail": "A phone/WhatsApp number or email address is required."}` |
| `422` | Malformed JSON/field type | FastAPI validation details |
| `500` | CRM processing failure | `{"detail": "Failed to process brochure download: ..."}` |

Recommended handling: show a thank-you message and start the brochure download
regardless of the API result.

---

## JavaScript Example (download-safe)

The brochure download must **not** wait for the CRM request. Start the download
first, then record the enquiry in the background.

```html
<form id="brochureForm">
  <input type="text" name="name" placeholder="Your Name" required />
  <input type="tel" name="phone" placeholder="WhatsApp Number" required />
  <input type="email" name="email" placeholder="Email" />
  <button type="submit">Download Brochure</button>
</form>

<script>
  const BROCHURE_API =
    'https://www.wapluscrm.in/api/integrations/website/brochures';

  function recordBrochureEnquiry(form) {
    const fields = form.elements;
    const payload = {
      name: fields.name.value.trim(),
      phone: fields.phone.value.trim(),
      countryCode: '91',
      email: fields.email.value.trim() || undefined,
      product_name: 'HRMS',
      product_id: 'prod-hrms',
      brochure_name: 'HRMS Product Brochure',
      brochure_id: 'brochure-hrms-2026',
      website_id: 'wapluscrm',
      website_name: 'WA Plus CRM',
      landing_page: window.location.href,
      campaign: 'HRMS Brochure Download',
      form_type: 'brochure_download'
    };

    return fetch(BROCHURE_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true
    })
      .then((response) => response.json())
      .then((data) => {
        console.log('Brochure enquiry saved:', data);
        return data;
      })
      .catch((error) => {
        console.warn('Brochure enquiry was not saved:', error);
      });
  }

  document
    .getElementById('brochureForm')
    .addEventListener('submit', function (event) {
      event.preventDefault();

      // 1. Start the file download immediately.
      window.location.href = '/files/hrms-brochure.pdf';

      // 2. Record the enquiry in the background (no await).
      recordBrochureEnquiry(event.currentTarget);
    });
</script>
```

---

## cURL Example

```bash
curl -X POST "https://www.wapluscrm.in/api/integrations/website/brochures" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Arun Kumar",
    "phone": "9876543210",
    "countryCode": "91",
    "email": "arun@example.com",
    "product_name": "HRMS",
    "brochure_name": "HRMS Product Brochure",
    "brochure_id": "brochure-hrms-2026",
    "website_name": "WA Plus CRM",
    "landing_page": "https://www.wapluscrm.in/hrms",
    "campaign": "HRMS Brochure Download",
    "form_type": "brochure_download"
  }'
```

Use your own test contact details for the first check. The response returns the
`enquiry_id` so the CRM admin can locate and remove the test record if needed.

---

## PHP Example

```php
<?php
$payload = [
    'name'          => trim($_POST['name'] ?? ''),
    'phone'         => trim($_POST['phone'] ?? ''),
    'countryCode'   => '91',
    'email'         => trim($_POST['email'] ?? ''),
    'product_name'  => 'HRMS',
    'product_id'    => 'prod-hrms',
    'brochure_name' => 'HRMS Product Brochure',
    'brochure_id'   => 'brochure-hrms-2026',
    'website_id'    => 'wapluscrm',
    'website_name'  => 'WA Plus CRM',
    'landing_page'  => 'https://www.wapluscrm.in/hrms',
    'campaign'      => 'HRMS Brochure Download',
    'form_type'     => 'brochure_download',
];

$ch = curl_init('https://www.wapluscrm.in/api/integrations/website/brochures');
curl_setopt_array($ch, [
    CURLOPT_POST           => true,
    CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
    CURLOPT_POSTFIELDS     => json_encode($payload),
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT        => 5,
]);

$response = curl_exec($ch);
$status   = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

// Do not block the brochure download if this request fails.
if ($status !== 201) {
    error_log('Brochure enquiry failed: ' . $response);
}
```

---

## How Deduplication Works

- Identity = normalized phone (or email when no phone) + product/brochure name.
- Same person downloading the **same** brochure again updates the existing
  record:
  - `submission_count` increases
  - latest submission time updates
  - contact fields refresh
  - follow-up status and internal notes are preserved
- Same person downloading a **different** brochure creates a separate record.
- No duplicate rows are created for repeated submissions.

---

## What the CRM Stores

| Website field | CRM column |
| :--- | :--- |
| `name` | Customer Name |
| `phone` / `whatsapp` + `countryCode` | WhatsApp Number (with country code) |
| `email` | Email |
| `product_name` / `brochure_name` | Product / Brochure Name |
| Server time of submission | Download Date & Time (IST) |
| — | Assigned Employee (set inside CRM) |
| — | Follow-up Status (set inside CRM) |
| `website_name`, `campaign`, `landing_page` | Website attribution shown in details |

Submission date/time is recorded by the CRM. No need to send it.

---

## Integration Checklist

1. Point the brochure form submit handler at
   `POST /api/integrations/website/brochures`.
2. Send `name`, `phone` + `countryCode`, `email`, `product_name`,
   `brochure_name`, and `form_type: "brochure_download"`.
3. Start the file download **before/independently of** the API call.
4. Log the returned `enquiry_id` for troubleshooting.
5. Submit the form once and confirm `201` + `record_type: "BROCHURE_ENQUIRY"`.
6. In the CRM, open **Website Enquiries → Brochure Download People** and search
   by name or phone.
7. Submit the same brochure twice and confirm `is_duplicate: true` with
   `submission_count: 2` and only one CRM row.
8. Because the endpoint is public, keep the website's honeypot/rate-limit/spam
   protection in place.

---

## Quick Test Results Expected

```text
POST /api/integrations/website/brochures  ->  201 Created
record_type                             ->  BROCHURE_ENQUIRY
enquiry_id                              ->  number
is_duplicate                            ->  false (first time)
submission_count                        ->  1
```

The record must appear only under **Website Enquiries → Brochure Download
People**, not under **Leads**.
