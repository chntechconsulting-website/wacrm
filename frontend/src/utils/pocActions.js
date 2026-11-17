// Shared Customer POC actions used by the Support screens, the dialer history
// and the incoming-call panel. These helpers never store or overwrite the
// customer's main contact number; they always act on the selected POC.

const digitsOnly = (value) => String(value || '').replace(/[^0-9]/g, '');

export const pocCallNumber = (poc) => {
  const value = poc?.mobile || poc?.whatsapp_number || poc?.alternate_mobile || '';
  return String(value || '').trim();
};

export const pocWhatsAppNumber = (poc) => {
  const raw = digitsOnly(poc?.whatsapp_number || poc?.mobile);
  if (!raw) return '';
  if (raw.length === 10) return `91${raw}`;
  return raw;
};

export const pocCallContact = (leadId, lead, poc) => {
  const company = lead?.company_name || lead?.company || lead?.name || '';
  const label = company ? `${company} — ${poc?.name || 'POC'}` : (poc?.name || 'POC');
  return {
    id: leadId,
    lead_id: leadId,
    name: label,
    phone: pocCallNumber(poc),
    company: lead?.company || lead?.company_name || '',
    customer_poc_id: poc?.id || null,
    poc_id: poc?.id || null,
    poc_name: poc?.name || null,
    // Always route through the Lead entity. A company field on the contact
    // would otherwise make the DooCTI dialer treat this as a generic Contact.
    entity_type: 'Leads',
  };
};

/**
 * Place a call to the selected POC using the existing CRM dialer.
 * Order: DooCTI in-app dialer -> DialerContext -> device tel: fallback.
 */
export const dialPoc = (leadId, lead, poc) => {
  const number = pocCallNumber(poc);
  if (!number) return false;
  const contact = pocCallContact(leadId, lead, poc);

  if (typeof window !== 'undefined' && typeof window.dooctiDial === 'function') {
    window.dooctiDial(number, contact);
    return true;
  }
  if (typeof window !== 'undefined' && typeof window.crmDial === 'function') {
    window.crmDial(number, contact);
    return true;
  }
  if (typeof window !== 'undefined') {
    window.location.href = `tel:${number}`;
    return true;
  }
  return false;
};

export const openPocEmail = (poc) => {
  const email = String(poc?.email || '').trim();
  if (!email || typeof window === 'undefined') return false;
  window.location.href = `mailto:${email}`;
  return true;
};

export const POC_METHOD_LABELS = {
  CALL: 'Call',
  WHATSAPP: 'WhatsApp',
  EMAIL: 'Email',
};

export const pocMethodLabel = (value) =>
  POC_METHOD_LABELS[String(value || 'CALL').toUpperCase()] || 'Call';
