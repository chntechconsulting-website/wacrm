# Website Lead Capture Integration Guide

This guide explains how to integrate any public website (HTML, React, Vue, Next.js, WordPress, PHP, or cURL) to automatically submit leads into **WaCRM**.

---

## 🚀 Public Endpoint Specification

- **Endpoint**: `POST /api/integrations/website/leads`
- **Authentication**: None (Public Endpoint for Contact Forms)
- **Content-Type**: `application/json`

---

## 📥 Request Payload Format

```json
{
  "name": "Arun",
  "phone": "9876543210",
  "email": "arun@gmail.com",
  "company": "ABC",
  "message": "Interested in your service"
}
```

### Field Definitions

| Field Name | Type   | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | string | **YES** | Contact / Prospect full name |
| `phone` | string | **YES** | Contact phone number |
| `email` | string | Optional | Contact email address |
| `company` | string | Optional | Company or Organization name |
| `message` | string | Optional | Inquiry note or customer message |

---

## 🔒 Backend Automatic Rules & Enforcement

- **Source Enforcement**: The backend automatically sets `source = "WEBSITE"`. Any payload attempts to supply or override `source` are ignored.
- **Initial Status**: Automatically set to `status = "NEW"`.
- **Assignment**: Automatically set to `assigned_to = NULL` (Unassigned pool for sales reps to claim or manager to assign).
- **Deduplication**: Checks database for matching `phone` or `email`. If matched, logs a `WEBSITE_INQUIRY_RECEIVED` timeline activity without throwing duplicate errors.
- **Timeline Activity**: Records a `CREATED_FROM_WEBSITE` audit trail activity upon creation.

---

## 📤 Response Format

### Success Response (`HTTP 201 Created`)

```json
{
  "success": true,
  "message": "Lead submitted successfully",
  "lead_id": 8
}
```

### Validation Error Response (`HTTP 400 Bad Request`)

```json
{
  "detail": "Contact name is required."
}
```

---

## 💻 Code Snippets & Examples

### 1. Plain JavaScript (`fetch`)

```html
<form id="contactForm">
  <input type="text" id="name" placeholder="Your Name" required />
  <input type="tel" id="phone" placeholder="Phone Number" required />
  <input type="email" id="email" placeholder="Email Address" />
  <input type="text" id="company" placeholder="Company Name" />
  <textarea id="message" placeholder="How can we help?"></textarea>
  <button type="submit">Submit Inquiry</button>
</form>

<script>
  document.getElementById('contactForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const data = {
      name: document.getElementById('name').value,
      phone: document.getElementById('phone').value,
      email: document.getElementById('email').value,
      company: document.getElementById('company').value,
      message: document.getElementById('message').value
    };

    try {
      const response = await fetch('http://www.wapluscrm.in/api/integrations/website/leads', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      });

      const result = await response.json();
      if (response.ok && result.success) {
        alert('Thank you! Your inquiry has been submitted successfully.');
        e.target.reset();
      } else {
        alert(result.detail || 'Submission failed.');
      }
    } catch (err) {
      console.error(err);
      alert('Network error. Please try again.');
    }
  });
</script>
```

---

### 2. React / Axios Component Example

```jsx
import React, { useState } from 'react';
import axios from 'axios';

const ContactUsForm = () => {
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    company: '',
    message: ''
  });
  const [status, setStatus] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post('http://www.wapluscrm.in/api/integrations/website/leads', formData);
      if (res.data.success) {
        setStatus('Lead submitted successfully!');
        setFormData({ name: '', phone: '', email: '', company: '', message: '' });
      }
    } catch (err) {
      setStatus(err.response?.data?.detail || 'Failed to submit form.');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input 
        type="text" 
        placeholder="Name" 
        value={formData.name} 
        onChange={e => setFormData({ ...formData, name: e.target.value })} 
        required 
      />
      <input 
        type="text" 
        placeholder="Phone" 
        value={formData.phone} 
        onChange={e => setFormData({ ...formData, phone: e.target.value })} 
        required 
      />
      <input 
        type="email" 
        placeholder="Email" 
        value={formData.email} 
        onChange={e => setFormData({ ...formData, email: e.target.value })} 
      />
      <textarea 
        placeholder="Message" 
        value={formData.message} 
        onChange={e => setFormData({ ...formData, message: e.target.value })} 
      />
      <button type="submit">Submit</button>
      {status && <p>{status}</p>}
    </form>
  );
};

export default ContactUsForm;
```

---

### 3. cURL Command Line Example

```bash
curl -X POST "http://127.0.0.1:8000/api/integrations/website/leads" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "Arun",
           "phone": "9876543210",
           "email": "arun@gmail.com",
           "company": "ABC",
           "message": "Interested in your service"
         }'
```

---

## 📺 CRM Dashboard & Sidebar View

Submitted leads will immediately appear in:
1. **Sidebar Badge**: Under `LEADS` $\rightarrow$ `Website Leads`.
2. **Page View**: Navigating to `/leads/website` calls `GET /api/leads?source=WEBSITE` and lists all website inquiries.
