import pdfMake from 'pdfmake/build/pdfmake';
import pdfFonts from 'pdfmake/build/vfs_fonts';
import { numberToIndianWords, COMPANY_DEFAULTS, COMPANIES } from './billingMoney';
import { WAHRMS_LOGO_BASE64, CHN_LOGO_BASE64 } from './logoBase64';
import { CHN_QR_CARD_BASE64 } from './paymentQrBase64';

// Ensure virtual file system fonts are loaded
if (pdfFonts && pdfFonts.pdfMake && pdfFonts.pdfMake.vfs) {
  pdfMake.vfs = pdfFonts.pdfMake.vfs;
} else if (pdfFonts && pdfFonts.vfs) {
  pdfMake.vfs = pdfFonts.vfs;
}

const BRAND = {
  ink900: '#0f172a',
  ink700: '#1e293b',
  ink500: '#475569',
  ink400: '#64748b',
  ink300: '#94a3b8',
  ink200: '#cbd5e1',
  ink100: '#e2e8f0',
  ink50: '#f8fafc',
  highlight: '#f1f5f9',
  brand700: '#b91c1c', // Rich crimson red for title, labels & grand total
  brand600: '#dc2626', // Vibrant red for header dividing rule
  brand100: '#fee2e2', // Light red accent/border
  brand50: '#fef2f2'   // Soft red tint background for grand total
};

const CONTENT_WIDTH = 539; // Portrait A4 width (595) minus 28pt margins on either side

function fmt(n) {
  const val = Number(n || 0);
  return new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(Number.isFinite(val) ? val : 0);
}

function formatDateDisplay(d) {
  if (!d) return '';
  const dateObj = typeof d === 'number' || typeof d === 'string' ? new Date(d) : d;
  if (isNaN(dateObj.getTime())) return String(d);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric'
  }).format(dateObj);
}

export function splitDescriptionIntoLines(rawDescription) {
  if (!rawDescription) return ['—'];
  
  const rawStr = String(rawDescription).trim();
  // Split on existing linebreaks first
  const rawLines = rawStr.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  
  const finalLines = [];
  const delimiterPattern = /(?=(?:WaPayroll|Duration\s*:?|No\s*Of\s*onboardings\s*:?|No\s*of\s*onboarding\s*:?|Onboardings?\s*:?|Unit\s*Price\s*:?|Price\s*per\s*user\s*:?|SIM\s*Card|FACE\+FINGER))/i;
  
  for (const line of rawLines) {
    const normalized = line.replace(/\s+/g, ' ');
    const parts = normalized.split(delimiterPattern).map(p => p.trim()).filter(Boolean);
    if (parts.length > 1) {
      finalLines.push(...parts);
    } else {
      finalLines.push(line);
    }
  }
  
  return finalLines.length > 0 ? finalLines : ['—'];
}

export function generateBillingPdf(docData, download = true) {
  const docType = (docData.docType || docData.doc_type || 'quotation').toLowerCase();
  const isQuotation = docType === 'quotation';
  const isProforma = docType === 'proforma';
  const isInvoice = docType === 'invoice';
  const isPO = docType === 'po';
  const isRedThemed = isQuotation || isProforma;

  const headerWord = isProforma
    ? 'PROFORMA INVOICE'
    : isInvoice
    ? 'TAX INVOICE'
    : isPO
    ? 'PURCHASE ORDER'
    : 'QUOTATION';

  // Determine issuer company - preserve selected company (WAHRMS vs CHN TECH)
  const companyId = docData.companyId || (docData.company?.shortName?.toLowerCase().includes('chn') ? 'chn-tech' : 'wahrms');
  const matchedCompany = COMPANIES.find(c => c.id === companyId) || docData.company || COMPANY_DEFAULTS;
  const company = {
    ...COMPANY_DEFAULTS,
    ...matchedCompany,
    address: {
      ...COMPANY_DEFAULTS.address,
      ...(matchedCompany.address || {})
    }
  };

  const isIntra = (docData.taxMode || 'intra') === 'intra';

  // Preserve logo without changing it: WAHRMS uses WAHRMS logo, CHN TECH uses CHN logo
  let logoToUse = docData.logoBase64 || docData.logo;
  if (!logoToUse) {
    logoToUse = companyId === 'chn-tech' ? CHN_LOGO_BASE64 : WAHRMS_LOGO_BASE64;
  }

  // ---------- Header Block ---------------------------------------------------
  const headerLeft = [];
  if (logoToUse) {
    headerLeft.push({
      image: logoToUse,
      width: 135,
      margin: [0, 10, 0, 0]
    });
  } else {
    headerLeft.push({ text: company.legalName, style: 'companyName', margin: [0, 10, 0, 0] });
  }

  const headerRight = [
    {
      text: headerWord.toUpperCase(),
      style: isRedThemed ? 'docHeaderTitleRed' : 'docHeaderTitle',
      alignment: 'right'
    },
    {
      text: docData.number || 'DRAFT',
      style: 'docHeaderNumber',
      alignment: 'right',
      margin: [0, 2, 0, 6]
    }
  ];

  const metaRows = [
    [
      { text: 'Issue Date', style: 'metaLabel', alignment: 'right' },
      { text: formatDateDisplay(docData.issueDate || docData.issueDateFormatted || new Date()), style: 'metaValue', alignment: 'right' }
    ]
  ];

  if (isQuotation) {
    metaRows.push([
      { text: 'Valid Till', style: 'metaLabel', alignment: 'right' },
      { text: formatDateDisplay(docData.validTill || docData.validTillFormatted || new Date(Date.now() + 7 * 86400000)), style: 'metaValue', alignment: 'right' }
    ]);
  } else {
    const dueVal = docData.dueDate || docData.dueDateFormatted || docData.validTill || docData.validTillFormatted || new Date(Date.now() + 7 * 86400000);
    metaRows.push([
      { text: 'Due Date', style: 'metaLabel', alignment: 'right' },
      { text: formatDateDisplay(dueVal), style: 'metaValue', alignment: 'right' }
    ]);
  }

  const customerState = docData.state || docData.customer?.address?.state || 'Tamil Nadu';
  const customerStateCode = docData.stateCode || docData.customer?.address?.stateCode || '33';

  metaRows.push([
    { text: 'Place of Supply', style: 'metaLabel', alignment: 'right' },
    { text: `${customerState} (${customerStateCode})`, style: 'metaValue', alignment: 'right' }
  ]);

  metaRows.push([
    { text: 'Tax Mode', style: 'metaLabel', alignment: 'right' },
    { text: isIntra ? 'Intra-state (CGST + SGST)' : 'Inter-state (IGST)', style: 'metaValue', alignment: 'right' }
  ]);

  const preparedBy = docData.preparedBy?.trim() || docData.employeeName || 'Authorized Signatory';
  metaRows.push([
    { text: 'Prepared By', style: 'metaLabel', alignment: 'right' },
    { text: preparedBy, style: 'metaValue', alignment: 'right' }
  ]);

  headerRight.push({
    table: { widths: ['*', 'auto'], body: metaRows },
    layout: {
      hLineWidth: () => 0,
      vLineWidth: () => 0,
      paddingTop: () => 1.5,
      paddingBottom: () => 1.5,
      paddingLeft: () => 6,
      paddingRight: () => 0
    },
    margin: [0, 2, 0, 0]
  });

  const headerBlock = {
    columns: [
      { width: '*', stack: headerLeft },
      { width: 220, stack: headerRight }
    ],
    columnGap: 16,
    margin: [0, 0, 0, 10]
  };

  const headerRule = {
    canvas: [
      {
        type: 'line',
        x1: 0,
        y1: 0,
        x2: CONTENT_WIDTH,
        y2: 0,
        lineWidth: 1.5,
        lineColor: isRedThemed ? BRAND.brand600 : '#0f766e'
      }
    ],
    margin: [0, 4, 0, 12]
  };

  // ---------- Billed-By and Billed-To Panels -----------------------------
  const billedByStack = [
    {
      text: 'ISSUED BY',
      style: 'panelLabel',
      color: isRedThemed ? BRAND.brand600 : undefined
    },
    { text: company.legalName, style: 'panelName', margin: [0, 3, 0, 2] },
    {
      text: [
        company.address.line1,
        company.address.line2 ? `, ${company.address.line2}` : '',
        `\n${company.address.city}, ${company.address.state} ${company.address.pincode}`
      ].join(''),
      style: 'panelAddr'
    }
  ];

  if (company.gstin) {
    billedByStack.push({
      text: `GSTIN: ${company.gstin}`,
      style: 'panelMeta',
      margin: [0, 3, 0, 0]
    });
  }
  if (company.pan) {
    billedByStack.push({
      text: `PAN: ${company.pan}`,
      style: 'panelMeta',
      margin: [0, 2, 0, 0]
    });
  }
  const companyEmail = company.email || docData.companyEmail || 'info@chnindia.com';
  if (companyEmail) {
    billedByStack.push({
      text: `Email: ${companyEmail}`,
      style: 'panelMeta',
      margin: [0, 2, 0, 0]
    });
  }
  if (company.phone) {
    billedByStack.push({
      text: `Phone: ${company.phone}`,
      style: 'panelMeta',
      margin: [0, 2, 0, 0]
    });
  }

  const billedByCell = {
    stack: billedByStack,
    fillColor: BRAND.ink50,
    margin: [10, 8, 10, 8]
  };

  const customerName = docData.customerName || docData.customer?.name || '';
  const customerCompany = docData.companyName || docData.customer?.companyName || '';
  const customerPhone = docData.phone || docData.customer?.phone || '';
  const customerEmail = docData.email || docData.customer?.email || '';
  const customerAddress = docData.address || docData.customer?.address?.line1 || '';
  const customerCity = docData.city || docData.customer?.address?.city || '';
  const customerPincode = docData.pincode || docData.customer?.address?.pincode || '';
  const customerGstin = (docData.gstin || docData.customer?.gstin || '').toUpperCase().trim();
  const customerPan = docData.pan || docData.customer?.pan || (customerGstin.length === 15 ? customerGstin.slice(2, 12) : '');

  const billedToStack = [
    {
      text: isQuotation ? 'QUOTATION FOR' : isPO ? 'VENDOR / SUPPLIER' : 'BILLED TO',
      style: 'panelLabel',
      color: isRedThemed ? BRAND.brand600 : undefined
    }
  ];

  if (customerCompany) {
    billedToStack.push({ text: customerCompany, style: 'panelName', margin: [0, 3, 0, 2] });
    if (customerName) {
      billedToStack.push({ text: `Contact: ${customerName}`, style: 'panelContact', margin: [0, 0, 0, 2] });
    }
  } else if (customerName) {
    billedToStack.push({ text: customerName, style: 'panelName', margin: [0, 3, 0, 2] });
  }

  if (customerAddress) {
    billedToStack.push({
      text: [
        customerAddress,
        `\n${customerCity ? customerCity + ', ' : ''}${customerState} ${customerPincode}`
      ].join(''),
      style: 'panelAddr'
    });
  }

  if (customerGstin) {
    billedToStack.push({ text: `GSTIN: ${customerGstin}`, style: 'panelMeta', margin: [0, 3, 0, 0] });
  }
  if (customerPan) {
    billedToStack.push({ text: `PAN: ${customerPan}`, style: 'panelMeta', margin: [0, 2, 0, 0] });
  }
  if (customerEmail) {
    billedToStack.push({ text: `Email: ${customerEmail}`, style: 'panelMeta', margin: [0, 2, 0, 0] });
  }
  if (customerPhone) {
    billedToStack.push({ text: `Phone: ${customerPhone}`, style: 'panelMeta', margin: [0, 2, 0, 0] });
  }

  const billedToCell = {
    stack: billedToStack,
    fillColor: isRedThemed ? BRAND.brand50 : BRAND.ink50,
    margin: [10, 8, 10, 8]
  };

  const partiesBlock = {
    table: {
      widths: ['*', '*'],
      body: [[billedByCell, billedToCell]]
    },
    layout: {
      hLineWidth: () => 0,
      vLineWidth: () => 0
    },
    margin: [0, 0, 0, 10]
  };

  const tableTitleBlock = isRedThemed ? {
    columns: [
      {
        text: [
          { text: isProforma ? 'PROFORMA INVOICE' : 'QUOTATION', style: 'docTitle', color: BRAND.brand700 },
          docData.number ? { text: `   ${docData.number}`, style: 'docTitleNumber' } : { text: '' }
        ],
        alignment: 'left',
        width: '*'
      }
    ],
    margin: [0, 0, 0, 6]
  } : null;

  // ---------- Line-Items Table -------------------------------------------
  const tableHeader = [
    { text: '#', style: isRedThemed ? 'thQuotation' : 'th', alignment: 'center' },
    { text: 'Item / Description', style: isRedThemed ? 'thQuotation' : 'th' },
    { text: 'HSN', style: isRedThemed ? 'thQuotation' : 'th', alignment: 'center' },
    { text: 'Qty', style: isRedThemed ? 'thQuotation' : 'th', alignment: 'right' },
    { text: 'Rate', style: isRedThemed ? 'thQuotation' : 'th', alignment: 'right' },
    { text: 'Amount', style: isRedThemed ? 'thQuotation' : 'th', alignment: 'right' },
    { text: 'Tax %', style: isRedThemed ? 'thQuotation' : 'th', alignment: 'center' },
    ...(isIntra
      ? [
          { text: 'CGST', style: isRedThemed ? 'thQuotation' : 'th', alignment: 'right' },
          { text: 'SGST', style: isRedThemed ? 'thQuotation' : 'th', alignment: 'right' }
        ]
      : [{ text: 'IGST', style: isRedThemed ? 'thQuotation' : 'th', alignment: 'right' }]),
    { text: 'Total', style: isRedThemed ? 'thQuotation' : 'th', alignment: 'right' }
  ];

  let calculatedTaxable = 0;
  let calculatedCgst = 0;
  let calculatedSgst = 0;
  let calculatedIgst = 0;

  const itemRows = (docData.lineItems || []).map((line, idx) => {
    const qty = Number(line.qty || 1);
    const rate = Number(line.rate || 0);
    const discount = Number(line.discount || 0);
    const amount = Math.max(0, qty * rate - discount);
    const gstRate = Number(line.gstRate !== undefined ? line.gstRate : 0.18);
    const tax = amount * gstRate;

    let cgst = 0;
    let sgst = 0;
    let igst = 0;

    if (isIntra) {
      cgst = Math.round((tax / 2) * 100) / 100;
      sgst = Math.round((tax - cgst) * 100) / 100;
    } else {
      igst = Math.round(tax * 100) / 100;
    }

    const total = amount + cgst + sgst + igst;

    calculatedTaxable += amount;
    calculatedCgst += cgst;
    calculatedSgst += sgst;
    calculatedIgst += igst;

    const descParts = splitDescriptionIntoLines(line.description);
    const firstLine = descParts[0] || '—';
    const otherLines = descParts.slice(1);

    const descCell = {
      stack: [
        { text: firstLine, style: 'tdItem' },
        ...otherLines.map((t) => ({ text: t, style: 'tdDesc', margin: [0, 1.5, 0, 0] }))
      ]
    };

    const taxPercent = Math.round(gstRate * 100);

    return [
      { text: String(idx + 1), style: 'td', alignment: 'center', noWrap: true },
      descCell,
      { text: line.hsn || '—', style: 'td', alignment: 'center', noWrap: true },
      { text: String(qty), style: 'tdNum', alignment: 'right', noWrap: true },
      { text: fmt(rate), style: 'tdNum', alignment: 'right', noWrap: true },
      { text: fmt(amount), style: 'tdNum', alignment: 'right', noWrap: true },
      { text: `${taxPercent}%`, style: 'td', alignment: 'center', noWrap: true },
      ...(isIntra
        ? [
            { text: fmt(line.cgst !== undefined ? line.cgst : cgst), style: 'tdNum', alignment: 'right', noWrap: true },
            { text: fmt(line.sgst !== undefined ? line.sgst : sgst), style: 'tdNum', alignment: 'right', noWrap: true }
          ]
        : [{ text: fmt(line.igst !== undefined ? line.igst : igst), style: 'tdNum', alignment: 'right', noWrap: true }]),
      { text: fmt(line.total !== undefined ? line.total : total), style: 'tdNum', alignment: 'right', noWrap: true }
    ];
  });

  const intraWidths = [16, '*', 46, 22, 54, 56, 30, 50, 50, 58];
  const interWidths = [16, '*', 46, 22, 58, 62, 32, 62, 66];

  const itemsTable = {
    table: {
      headerRows: 1,
      widths: isIntra ? intraWidths : interWidths,
      body: [tableHeader, ...itemRows]
    },
    layout: {
      hLineWidth: (i, node) => (i === 0 || i === 1 || i === node.table.body.length ? 0.5 : 0.5),
      vLineWidth: () => 0,
      hLineColor: (i) => (i === 0 || i === 1 ? (isRedThemed ? BRAND.brand600 : BRAND.ink200) : BRAND.ink100),
      paddingTop: (i) => (i === 0 ? 5.5 : 4.5),
      paddingBottom: (i) => (i === 0 ? 5.5 : 4.5),
      paddingLeft: () => 3,
      paddingRight: () => 3,
      fillColor: (rowIndex) => (rowIndex === 0 ? (isRedThemed ? BRAND.brand600 : BRAND.ink50) : null)
    },
    margin: [0, 0, 0, 8]
  };

  // ---------- Totals Summary Block ---------------------------------------
  const taxableAmount = docData.subtotal !== undefined ? docData.subtotal : calculatedTaxable;
  const cgstTotal = docData.cgst !== undefined ? docData.cgst : calculatedCgst;
  const sgstTotal = docData.sgst !== undefined ? docData.sgst : calculatedSgst;
  const igstTotal = docData.igst !== undefined ? docData.igst : calculatedIgst;
  const grandTotal = docData.grandTotal !== undefined ? docData.grandTotal : Math.round(taxableAmount + cgstTotal + sgstTotal + igstTotal);
  const roundOff = docData.roundOff !== undefined ? docData.roundOff : (grandTotal - (taxableAmount + cgstTotal + sgstTotal + igstTotal));

  const totalsRows = [
    [
      { text: 'Taxable Amount', style: 'sumLabel' },
      { text: fmt(taxableAmount), style: 'sumValue', alignment: 'right' }
    ],
    ...(isIntra
      ? [
          [
            { text: 'CGST', style: 'sumLabel' },
            { text: fmt(cgstTotal), style: 'sumValue', alignment: 'right' }
          ],
          [
            { text: 'SGST', style: 'sumLabel' },
            { text: fmt(sgstTotal), style: 'sumValue', alignment: 'right' }
          ]
        ]
      : [
          [
            { text: 'IGST', style: 'sumLabel' },
            { text: fmt(igstTotal), style: 'sumValue', alignment: 'right' }
          ]
        ]),
    ...(roundOff !== 0
      ? [
          [
            { text: 'Round Off', style: 'sumLabel' },
            { text: fmt(roundOff), style: 'sumValue', alignment: 'right' }
          ]
        ]
      : []),
    [
      { text: 'Total (INR)', style: 'sumGrandLabel' },
      { text: fmt(grandTotal), style: 'sumGrandValue', alignment: 'right' }
    ]
  ];

  const totalsBlock = {
    columns: [
      { width: '*', text: '' },
      {
        width: 220,
        table: { widths: ['*', 'auto'], body: totalsRows },
        layout: {
          hLineWidth: (i, node) => (i === 0 || i === node.table.body.length ? 0 : 0.5),
          vLineWidth: () => 0,
          hLineColor: () => BRAND.ink100,
          paddingTop: () => 3.5,
          paddingBottom: () => 3.5,
          paddingLeft: () => 4,
          paddingRight: () => 4,
          fillColor: (rowIndex, node) => (rowIndex === node.table.body.length - 1 ? (isRedThemed ? BRAND.brand50 : BRAND.ink50) : null)
        }
      }
    ],
    margin: [0, 2, 0, 6]
  };

  const words = numberToIndianWords(grandTotal);
  const amountInWordsBlock = {
    text: [
      { text: 'Amount in Words: ', style: 'awLabel' },
      { text: words, style: 'awValue' }
    ],
    margin: [0, 4, 0, 10]
  };

  // ---------- Terms & Conditions -----------------------------------------
  const defaultTerms = [
    '1. Prices are subject to applicable GST as specified.',
    '2. Software activation and onboarding will begin upon PO confirmation and receipt of payment.',
    '3. Setup, training, and technical support will be provided as agreed.',
    '4. The client is responsible for providing accurate employee and payroll data and verifying payroll calculations.',
    '5. Timely subscription renewal is required to ensure uninterrupted software access.',
    '6. Customization and third-party integrations may incur additional charges.',
    '7. Confirmation of the purchase order constitutes acceptance of the quotation and these terms.'
  ].join('\n');

  const termsText = docData.terms || docData.termsAndConditions || (isQuotation ? defaultTerms : '');

  const termsBlock = termsText ? {
    stack: [
      { text: 'TERMS & CONDITIONS', style: 'sectionHeading', margin: [0, 4, 0, 4] },
      { text: termsText, style: 'terms' }
    ],
    margin: [0, 4, 0, 8]
  } : null;

  // ---------- Notes Section (Removed per request) -----------------------
  // The NOTES section has been removed so only TERMS & CONDITIONS is displayed.

  // Proforma Invoice Payment Details for Page 1
  const proformaPaymentBlock = {
    stack: [
      { text: 'PAYMENT DETAILS', style: 'sectionHeading', margin: [0, 8, 0, 4] },
      { text: company.bank.accountName, style: 'panelName', fontSize: 10.5, margin: [0, 0, 0, 4] },
      {
        table: {
          widths: ['auto', 'auto'],
          body: [
            [{ text: 'Bank:', style: 'p1BankLabel' }, { text: company.bank.bankName, style: 'p1BankVal' }],
            [{ text: 'A/c:', style: 'p1BankLabel' }, { text: company.bank.accountNumber, style: 'p1BankVal' }],
            [{ text: 'IFSC:', style: 'p1BankLabel' }, { text: company.bank.ifsc, style: 'p1BankVal' }],
            ...(company.bank.branch ? [[{ text: 'Branch:', style: 'p1BankLabel' }, { text: company.bank.branch, style: 'p1BankVal' }]] : []),
            [{ text: 'Type:', style: 'p1BankLabel' }, { text: company.bank.accountType, style: 'p1BankVal' }]
          ]
        },
        layout: {
          hLineWidth: () => 0,
          vLineWidth: () => 0,
          paddingTop: () => 2,
          paddingBottom: () => 2,
          paddingLeft: () => 0,
          paddingRight: () => 8
        },
        margin: [0, 2, 0, 6]
      }
    ],
    margin: [0, 4, 0, 6]
  };

  // ---------- Bank Details (Only if Invoice or explicitly requested, Quotations don't show by default) ---
  const showBank = (!isProforma && (isInvoice || Boolean(docData.showBankDetails)));
  const bankPanel = showBank ? {
    table: {
      widths: ['*'],
      body: [
        [
          {
            stack: [
              { text: 'BANK DETAILS', style: 'panelLabel', margin: [0, 0, 0, 4] },
              {
                table: {
                  widths: ['auto', '*'],
                  body: [
                    [{ text: 'Bank', style: 'bankLabel' }, { text: company.bank.bankName, style: 'bankValue' }],
                    [{ text: 'A/c No', style: 'bankLabel' }, { text: company.bank.accountNumber, style: 'bankValue' }],
                    [{ text: 'IFSC', style: 'bankLabel' }, { text: company.bank.ifsc, style: 'bankValue' }],
                    [{ text: 'Beneficiary', style: 'bankLabel' }, { text: company.bank.accountName, style: 'bankValue' }],
                    [{ text: 'Type', style: 'bankLabel' }, { text: company.bank.accountType, style: 'bankValue' }]
                  ]
                },
                layout: {
                  hLineWidth: () => 0,
                  vLineWidth: () => 0,
                  paddingTop: () => 2,
                  paddingBottom: () => 2,
                  paddingLeft: () => 0,
                  paddingRight: () => 4
                }
              }
            ]
          }
        ]
      ]
    },
    layout: {
      hLineWidth: () => 0.5,
      vLineWidth: () => 0.5,
      hLineColor: () => BRAND.ink100,
      vLineColor: () => BRAND.ink100,
      paddingTop: () => 6,
      paddingBottom: () => 6,
      paddingLeft: () => 8,
      paddingRight: () => 8,
      fillColor: () => BRAND.ink50
    },
    margin: [0, 8, 0, 6]
  } : null;

  const signatureBlock = {
    text: 'This is a computer-generated document. No physical signature is required. Errors and omissions excepted.',
    style: 'disclaimer',
    margin: [0, 10, 0, 0]
  };

  // ---------- PDFmake Document Definition ---------------------------------
  const styles = {
    companyName: { fontSize: 11, bold: true, color: BRAND.ink900 },
    companyAddr: { fontSize: 8, color: BRAND.ink500, lineHeight: 1.25 },
    companyMeta: { fontSize: 8, color: BRAND.ink900, bold: true },
    docHeaderTitle: { fontSize: 18, bold: true, color: BRAND.ink900, characterSpacing: 0.5 },
    docHeaderTitleRed: { fontSize: 18, bold: true, color: BRAND.brand700, characterSpacing: 0.5 },
    docHeaderTitleProforma: { fontSize: 18, bold: true, color: BRAND.brand700, characterSpacing: 0.5 },
    docHeaderNumber: { fontSize: 11, bold: true, color: BRAND.ink900 },
    metaLabel: { fontSize: 8, color: BRAND.ink500 },
    metaValue: { fontSize: 8.5, color: BRAND.ink900, bold: true },
    panelLabel: { fontSize: 8, bold: true, color: BRAND.ink500, characterSpacing: 0.5 },
    panelName: { fontSize: 9.5, bold: true, color: BRAND.ink900 },
    panelContact: { fontSize: 8.5, color: BRAND.ink700, bold: true },
    panelAddr: { fontSize: 8, color: BRAND.ink500, lineHeight: 1.25 },
    panelMeta: { fontSize: 8, color: BRAND.ink700 },
    th: { fontSize: 8, bold: true, color: BRAND.ink700 },
    thQuotation: { fontSize: 8, bold: true, color: '#ffffff' },
    td: { fontSize: 8, color: BRAND.ink700 },
    tdNum: { fontSize: 8, color: BRAND.ink900 },
    tdItem: { fontSize: 8.5, color: BRAND.ink900, bold: true, lineHeight: 1.15 },
    tdDesc: { fontSize: 7.5, color: BRAND.ink500, lineHeight: 1.15, margin: [0, 1, 0, 0] },
    docTitle: { fontSize: 10.5, bold: true, color: BRAND.brand700, characterSpacing: 0.5 },
    docTitleNumber: { fontSize: 10.5, bold: true, color: BRAND.ink900 },
    sumLabel: { fontSize: 8.5, color: BRAND.ink700 },
    sumValue: { fontSize: 8.5, color: BRAND.ink900 },
    sumGrandLabel: { fontSize: 10, bold: true, color: isRedThemed ? BRAND.brand700 : BRAND.ink900 },
    sumGrandValue: { fontSize: 11, bold: true, color: isRedThemed ? BRAND.brand700 : BRAND.ink900 },
    awLabel: { fontSize: 8.5, color: BRAND.ink500 },
    awValue: { fontSize: 8.5, color: BRAND.ink900, bold: true, italics: true },
    sectionHeading: { fontSize: 8.5, bold: true, color: BRAND.ink900, characterSpacing: 0.5 },
    terms: { fontSize: 8, color: BRAND.ink700, lineHeight: 1.35 },
    bankLabel: { fontSize: 8, color: BRAND.ink500 },
    bankValue: { fontSize: 8, color: BRAND.ink900, bold: true },
    p1BankLabel: { fontSize: 9, color: BRAND.ink500 },
    p1BankVal: { fontSize: 9.5, bold: true, color: BRAND.ink900 },
    qrPageRef: { fontSize: 8, bold: true, color: BRAND.brand700 },
    scanToPayTitle: { fontSize: 16, bold: true, color: BRAND.brand700, characterSpacing: 0.5 },
    scanToPayDocNo: { fontSize: 10.5, color: BRAND.ink700 },
    scanToPayAmount: { fontSize: 12.5, bold: true, color: BRAND.ink900 },
    scanInstruction: { fontSize: 8.5, color: BRAND.ink500, italics: true },
    p2BankLabel: { fontSize: 8.5, color: BRAND.ink500 },
    p2BankValue: { fontSize: 8.5, bold: true, color: BRAND.ink900 },
    p2CompanyLegal: { fontSize: 10.5, bold: true, color: BRAND.ink900 },
    p2CompanyContact: { fontSize: 8.5, color: BRAND.ink500 },
    disclaimer: { fontSize: 7, color: BRAND.ink500, italics: true, lineHeight: 1.2 },
    footer: { fontSize: 7.5, color: BRAND.ink500 }
  };

  const content = [
    headerBlock,
    headerRule,
    partiesBlock,
    ...(tableTitleBlock ? [tableTitleBlock] : []),
    itemsTable,
    totalsBlock,
    amountInWordsBlock
  ];

  if (isProforma) {
    content.push(proformaPaymentBlock);
  } else {
    if (termsBlock) content.push(termsBlock);
    if (bankPanel) content.push(bankPanel);
  }

  const docDefinition = {
    pageSize: 'A4',
    pageOrientation: 'portrait',
    pageMargins: [28, 24, 28, 38],
    defaultStyle: { font: 'Roboto', color: BRAND.ink900 },
    styles,
    content,
    footer: (currentPage, pageCount) => ({
      stack: [
        {
          text: 'This is a computer-generated document. No physical signature is required. Errors and omissions excepted.',
          style: 'disclaimer',
          alignment: 'center',
          margin: [0, 0, 0, 4]
        },
        {
          columns: [
            {
              text: `For any enquiry, reach out via email at ${company.email}, call on ${company.phone}`,
              style: 'footer',
              alignment: 'left',
              width: '*'
            },
            {
              text: `Page ${currentPage} of ${pageCount}`,
              style: 'footer',
              alignment: 'right',
              width: 80
            }
          ]
        }
      ],
      margin: [28, 0, 28, 10]
    })
  };

  const pdf = pdfMake.createPdf(docDefinition);
  if (download) {
    const rawNum = docData.number || docData.doc_number || docData.docNumber || '0001';
    const cleanNum = String(rawNum).replace(/[\\/]/g, '-').replace(/[^a-zA-Z0-9-_]/g, '');
    let filename;
    if (isProforma) {
      filename = `Proforma_Invoice_${cleanNum}.pdf`;
    } else if (isQuotation) {
      filename = `Quotation_${cleanNum}.pdf`;
    } else if (isInvoice) {
      filename = `Tax_Invoice_${cleanNum}.pdf`;
    } else {
      filename = `${headerWord.replace(/\s+/g, '_')}_${cleanNum}.pdf`;
    }
    pdf.download(filename);
  }
  return pdf;
}

export function generateQuotationPdf(docData, download = true) {
  return generateBillingPdf({
    ...docData,
    docType: 'quotation',
    doc_type: 'quotation'
  }, download);
}

export function generateProformaPdf(docData, download = true) {
  return generateBillingPdf({
    ...docData,
    docType: 'proforma',
    doc_type: 'proforma'
  }, download);
}

export function generatePoPdf(docData, download = true) {
  return generateBillingPdf({
    ...docData,
    docType: 'po',
    doc_type: 'po'
  }, download);
}

import { buildTaxInvoiceModelPdf } from './taxInvoicePdf';

export function generateTaxInvoicePdf(docData, download = true) {
  return buildTaxInvoiceModelPdf(docData, download);
}

/**
 * Returns a Promise that resolves to a Blob of the generated PDF document.
 * Works uniformly for quotation, po, proforma, and tax invoice.
 */
export function getPdfBlob(docData) {
  return new Promise((resolve, reject) => {
    try {
      const dType = (docData.docType || docData.doc_type || 'quotation').toLowerCase();
      let pdfObj;
      if (dType === 'invoice') {
        pdfObj = generateTaxInvoicePdf(docData, false);
      } else if (dType === 'proforma') {
        pdfObj = generateProformaPdf(docData, false);
      } else if (dType === 'po' || dType === 'purchase_order') {
        pdfObj = generatePoPdf(docData, false);
      } else {
        pdfObj = generateQuotationPdf(docData, false);
      }

      if (pdfObj && typeof pdfObj.getBlob === 'function') {
        pdfObj.getBlob((blob) => {
          resolve(blob);
        });
      } else {
        reject(new Error('PDF generator object did not expose getBlob method.'));
      }
    } catch (err) {
      reject(err);
    }
  });
}

