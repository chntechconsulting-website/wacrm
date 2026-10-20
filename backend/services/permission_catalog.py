"""
Standard system modules and permission definition catalog.
Admin can configure any module access and action for any role.
"""

SYSTEM_MODULES = [
    {
        "key": "dashboard",
        "label": "Dashboard",
        "category": "Core",
        "description": "High-level KPI metrics, pipeline summaries, and charts"
    },
    {
        "key": "leads",
        "label": "Leads",
        "category": "Sales & CRM",
        "description": "Prospects and inquiries pipeline management"
    },
    {
        "key": "customers",
        "label": "Customers",
        "category": "Sales & CRM",
        "description": "Converted clients and accounts"
    },
    {
        "key": "contacts",
        "label": "Contacts",
        "category": "Sales & CRM",
        "description": "Individual points of contact and stakeholders"
    },
    {
        "key": "quotations",
        "label": "Quotations",
        "category": "Billing & Finance",
        "description": "Price estimates, proformas, and quotes"
    },
    {
        "key": "invoices",
        "label": "Invoices",
        "category": "Billing & Finance",
        "description": "Tax invoices, POs, and billing records"
    },
    {
        "key": "payments",
        "label": "Payments",
        "category": "Billing & Finance",
        "description": "Payment confirmations, banking reconciliation, and UTR tracking"
    },
    {
        "key": "calls",
        "label": "Calls",
        "category": "Communication",
        "description": "Click-to-Call IVR logs, recordings, and AI audio summaries"
    },
    {
        "key": "whatsapp",
        "label": "WhatsApp",
        "category": "Communication",
        "description": "Direct chat, template broadcasting, and incoming messages"
    },
    {
        "key": "followups",
        "label": "Follow-ups",
        "category": "Communication",
        "description": "Scheduled call-backs, reminders, and agendas"
    },
    {
        "key": "activities",
        "label": "Activities",
        "category": "Communication",
        "description": "Timeline audit trails and client notes"
    },
    {
        "key": "support_tickets",
        "label": "Support Tickets",
        "category": "Operations & Support",
        "description": "Client onboarding, fulfillment, and helpdesk tickets"
    },
    {
        "key": "reports",
        "label": "Reports",
        "category": "Analytics",
        "description": "Custom reporting, data exports, and audit summaries"
    },
    {
        "key": "analytics",
        "label": "Analytics",
        "category": "Analytics",
        "description": "Business intelligence, conversion trends, and forecasting"
    },
    {
        "key": "employees",
        "label": "Employees",
        "category": "Administration",
        "description": "Employee directory, profiles, and performance tracking"
    },
    {
        "key": "users",
        "label": "Users",
        "category": "Administration",
        "description": "Login credentials and account statuses"
    },
    {
        "key": "roles",
        "label": "Roles & Permissions",
        "category": "Administration",
        "description": "Role matrix configuration, action grants, and scope"
    },
    {
        "key": "integrations",
        "label": "Integrations",
        "category": "Administration",
        "description": "Meta Webhooks, WA Quote, website APIs, and 3rd party sync"
    },
    {
        "key": "settings",
        "label": "Settings",
        "category": "Administration",
        "description": "System preferences, security, auto-assignment rules, and data deletion"
    }
]

MODULE_KEYS = [m["key"] for m in SYSTEM_MODULES]
