/**
 * Money + Indian GST calculation engine and currency-in-words converter.
 */

export function round2(n) {
  return Math.round((Number(n || 0) + Number.EPSILON) * 100) / 100;
}

export function computeLine(line, mode = 'intra') {
  const qty = Number(line.qty || 0);
  const rate = Number(line.rate || 0);
  const discount = Number(line.discount || 0);
  const gstRate = Number(line.gstRate || 0.18);

  const gross = qty * rate;
  const amount = Math.max(0, round2(gross - discount));
  const tax = round2(amount * gstRate);

  let cgst = 0;
  let sgst = 0;
  let igst = 0;

  if (mode === 'intra') {
    cgst = round2(tax / 2);
    sgst = round2(tax - cgst);
  } else {
    igst = tax;
  }

  const total = round2(amount + cgst + sgst + igst);
  return { amount, cgst, sgst, igst, total };
}

export function computeInvoice(lines = [], mode = 'intra', roundOff = true) {
  const computedLines = lines.map((l) => computeLine(l, mode));
  const taxableAmount = round2(computedLines.reduce((s, l) => s + l.amount, 0));
  const cgstTotal = round2(computedLines.reduce((s, l) => s + l.cgst, 0));
  const sgstTotal = round2(computedLines.reduce((s, l) => s + l.sgst, 0));
  const igstTotal = round2(computedLines.reduce((s, l) => s + l.igst, 0));
  const taxTotal = round2(cgstTotal + sgstTotal + igstTotal);
  
  const rawGrand = taxableAmount + taxTotal;
  const grandRounded = roundOff ? Math.round(rawGrand) : round2(rawGrand);
  const roundOffAmount = round2(grandRounded - rawGrand);

  return {
    lines: computedLines,
    taxableAmount,
    cgstTotal,
    sgstTotal,
    igstTotal,
    taxTotal,
    roundOff: roundOffAmount,
    grandTotal: grandRounded
  };
}

export function numberToIndianWords(num) {
  if (!Number.isFinite(num)) return '';
  const isNegative = num < 0;
  const n = Math.abs(num);
  const rupees = Math.floor(n);
  const paise = Math.round((n - rupees) * 100);

  const ones = [
    '', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
    'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen',
    'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'
  ];
  const tens = [
    '', '', 'Twenty', 'Thirty', 'Forty', 'Fifty',
    'Sixty', 'Seventy', 'Eighty', 'Ninety'
  ];

  function convertTwoDigits(v) {
    if (v < 20) return ones[v];
    const t = Math.floor(v / 10);
    const o = v % 10;
    return `${tens[t]}${o ? ' ' + ones[o] : ''}`.trim();
  }

  function convertThreeDigits(v) {
    const h = Math.floor(v / 100);
    const rem = v % 100;
    const hPart = h ? `${ones[h]} Hundred` : '';
    const remPart = rem ? convertTwoDigits(rem) : '';
    if (hPart && remPart) return `${hPart} and ${remPart}`;
    return hPart || remPart;
  }

  if (rupees === 0 && paise === 0) return 'Zero Rupees Only';

  let remaining = rupees;
  const chunks = [];

  const crores = Math.floor(remaining / 10000000);
  remaining %= 10000000;

  const lakhs = Math.floor(remaining / 100000);
  remaining %= 100000;

  const thousands = Math.floor(remaining / 1000);
  remaining %= 1000;

  const hundreds = remaining;

  if (crores > 0) chunks.push(`${numberToIndianWords(crores).replace(/ Rupees Only$/, '')} Crore`);
  if (lakhs > 0) chunks.push(`${convertTwoDigits(lakhs)} Lakh`);
  if (thousands > 0) chunks.push(`${convertTwoDigits(thousands)} Thousand`);
  if (hundreds > 0) chunks.push(convertThreeDigits(hundreds));

  let words = chunks.join(' ').trim();
  if (!words) words = 'Zero';

  let result = `Rupees ${words}`;
  if (paise > 0) {
    result += ` and ${convertTwoDigits(paise)} Paise`;
  }
  result += ' Only';

  return isNegative ? `Minus ${result}` : result;
}

export const INDIAN_STATES = [
  { code: '33', name: 'Tamil Nadu' },
  { code: '29', name: 'Karnataka' },
  { code: '32', name: 'Kerala' },
  { code: '37', name: 'Andhra Pradesh' },
  { code: '36', name: 'Telangana' },
  { code: '27', name: 'Maharashtra' },
  { code: '07', name: 'Delhi' },
  { code: '09', name: 'Uttar Pradesh' },
  { code: '24', name: 'Gujarat' },
  { code: '19', name: 'West Bengal' },
  { code: '23', name: 'Madhya Pradesh' },
  { code: '08', name: 'Rajasthan' },
  { code: '06', name: 'Haryana' },
  { code: '03', name: 'Punjab' },
  { code: '21', name: 'Odisha' },
  { code: '10', name: 'Bihar' },
  { code: '34', name: 'Puducherry' }
];

export const COMPANIES = [
  {
    id: 'wahrms',
    legalName: 'CHN TECHNOLOGIES PVT LTD',
    shortName: 'WAHRMS',
    displayName: 'CHN TECHNOLOGIES PVT LTD (WAHRMS) ★ Default — GSTIN: 33AAJCC3705A1ZC',
    brandBadge: 'WA!HRMS',
    logoType: 'wahrms',
    gstin: '33AAJCC3705A1ZC',
    pan: 'AAJCC3705A',
    state: 'Tamil Nadu',
    stateCode: '33',
    address: {
      line1: 'No, 28 Fourth Main Road, CIT Nagar',
      line2: '',
      city: 'Chennai',
      state: 'Tamil Nadu',
      pincode: '600035',
      country: 'India'
    },
    email: 'info@chnindia.com',
    phone: '+91 84366 00600',
    bank: {
      bankName: 'HDFC Bank',
      accountName: 'CHN TECHNOLOGIES PRIVATE LIMITED',
      accountNumber: '50200120393881',
      ifsc: 'HDFC0001867',
      branch: 'Mahalingapuram Branch',
      accountType: 'Current'
    },
    footer: 'For any enquiry, reach out via email at info@chnindia.com, call on +91 84366 00600'
  },
  {
    id: 'chn-tech',
    legalName: 'CHN TECHNOLOGIES PVT LTD',
    shortName: 'CHN TECH',
    displayName: 'CHN TECHNOLOGIES PVT LTD (CHN TECH) ★ Default — GSTIN: 33AAJCC3705A1ZC',
    brandBadge: 'CHN TECH',
    logoType: 'chn-tech',
    gstin: '33AAJCC3705A1ZC',
    pan: 'AAJCC3705A',
    state: 'Tamil Nadu',
    stateCode: '33',
    address: {
      line1: 'No, 28 Fourth Main Road, CIT Nagar',
      line2: '',
      city: 'Chennai',
      state: 'Tamil Nadu',
      pincode: '600035',
      country: 'India'
    },
    email: 'info@chnindia.com',
    phone: '+91 84366 00600',
    bank: {
      bankName: 'HDFC Bank',
      accountName: 'CHN TECHNOLOGIES PRIVATE LIMITED',
      accountNumber: '50200120393881',
      ifsc: 'HDFC0001867',
      branch: 'Mahalingapuram Branch',
      accountType: 'Current'
    },
    footer: 'For any enquiry, reach out via email at info@chnindia.com, call on +91 84366 00600'
  }
];

export const COMPANY_DEFAULTS = COMPANIES[0];

