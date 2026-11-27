/**
 * Quotation/proforma terms and bank details.
 *
 * Kept dependency-free so the quotation editor can use these defaults without
 * loading the pdfmake bundle. quotationPdf.js re-exports them for existing
 * callers.
 */

// Biometric hardware documents are billed to the dedicated Axis Bank
// collection account. WAHRMS documents keep using the company profile bank
// details from billingMoney.js.
export const BIOMETRIC_BANK = {
  accountName: 'CHN TECHNOLOGIES PRIVATE LIMITED',
  bankName: 'AXIS BANK',
  accountNumber: '921020014696411',
  ifsc: 'UTIB0003702',
  accountType: 'Current'
};

export const WAHRMS_TERMS_AND_CONDITIONS = [
  '1. Prices are subject to applicable GST as specified.',
  '2. Software activation and onboarding will begin upon PO confirmation and receipt of payment.',
  '3. Setup, training, and technical support will be provided as agreed.',
  '4. The client is responsible for providing accurate employee and payroll data and verifying payroll calculations.',
  '5. Timely subscription renewal is required to ensure uninterrupted software access.',
  '6. Customization and third-party integrations may incur additional charges.',
  '7. Confirmation of the purchase order constitutes acceptance of the quotation and these terms.'
].join('\n');

export const BIOMETRIC_TERMS_AND_CONDITIONS = [
  '1. All civil works must be done by the client.',
  '2. Electrical Cable and Casing Pipe, Switch & Socket as per the Cost. Charged by Electrician (Clients Scope).',
  '3. Cable Per Meter Rs.45/-, Cable Laying Charges Per Meter Rs.35/-',
  '4. Warranty: Products have one-year Manufacturer warranty. The warranty does not cover any physical damages.',
  '5. Device Installation Charges Rs.1000- Per Location Per Device in Chennai and Coimbatore Only (Other Cities within TN Rs.2000).',
  '6. Local or Remote ESSL Software Installation Charges: Chennai and Coimbatore Only: ₹1000 per location per device. Other Cities within TN: ₹1500 per location per device.',
  '',
  'Payment Terms:',
  '• 75% advance payment is required before mobilization and commencement of work.',
  '• The remaining 25% balance payment is payable immediately upon successful completion of the work.'
].join('\n');

const LEGACY_PROFORMA_TERMS = [
  [
    '1. Payment terms: 100% advance payment against this Proforma Invoice.',
    '2. Bank transfers to be credited to the Axis Bank account mentioned above.',
    '3. Materials will be dispatched upon payment credit receipt.',
    '4. Goods once sold will not be taken back.'
  ].join('\n'),
  [
    '1. 100% advance payment against Proforma Invoice.',
    '2. Service will be activated upon payment confirmation.',
    '3. Taxes applicable as per GST guidelines.'
  ].join('\n'),
  [
    '1. Software access activates upon payment.',
    '2. Prices subject to applicable GST.'
  ].join('\n')
];

function normalizeTerms(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

const LEGACY_PROFORMA_TERMS_NORMALIZED = new Set(LEGACY_PROFORMA_TERMS.map(normalizeTerms));
const LEGACY_BIOMETRIC_PLACEHOLDERS = new Set(['biometric terms', 'biometric terms and conditions']);

export function resolveDocumentTerms(terms, docType, productCategory = '') {
  const type = String(docType || '').toLowerCase();
  // Proforma Invoices intentionally carry no Terms & Conditions, regardless
  // of the product category or any value stored on the document.
  if (type === 'proforma') {
    return '';
  }
  const cleaned = String(terms || '').trim();
  const isBiometric = String(productCategory || '').trim().toLowerCase() === 'biometric';
  if (type === 'quotation') {
    const normalized = normalizeTerms(cleaned);
    if (
      !cleaned ||
      LEGACY_PROFORMA_TERMS_NORMALIZED.has(normalized) ||
      (isBiometric && LEGACY_BIOMETRIC_PLACEHOLDERS.has(normalized.toLowerCase()))
    ) {
      return isBiometric ? BIOMETRIC_TERMS_AND_CONDITIONS : WAHRMS_TERMS_AND_CONDITIONS;
    }
  }
  return cleaned;
}
