import pdfMake from 'pdfmake/build/pdfmake';
import pdfFonts from 'pdfmake/build/vfs_fonts';
import { numberToIndianWords } from './billingMoney';
import { CHN_LOGO_BASE64, WAHRMS_LOGO_BASE64 } from './logoBase64';

// Ensure virtual file system fonts are loaded
if (pdfFonts && pdfFonts.pdfMake && pdfFonts.pdfMake.vfs) {
  pdfMake.vfs = pdfFonts.pdfMake.vfs;
} else if (pdfFonts && pdfFonts.vfs) {
  pdfMake.vfs = pdfFonts.vfs;
}

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
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const day = String(dateObj.getDate()).padStart(2, '0');
  const month = months[dateObj.getMonth()];
  const yr = String(dateObj.getFullYear()).slice(-2);
  return `${day}-${month}-${yr}`;
}

export function buildTaxInvoiceModelPdf(docData, download = true) {
  const items = docData.line_items || docData.lineItems || [];
  const subtotal = Number(docData.subtotal || 0);
  const cgst = Number(docData.cgst || 0);
  const sgst = Number(docData.sgst || 0);
  const igst = Number(docData.igst || 0);
  const grandTotal = Number(docData.grand_total || docData.grandTotal || (subtotal + cgst + sgst + igst));

  const docNum = docData.number || docData.doc_number || docData.docNumber || 'CHN/26-27/151';
  const rawDate = docData.date || docData.issue_date || docData.issueDate || new Date();
  const dateStr = formatDateDisplay(rawDate);

  const customerName = docData.company_name || docData.companyName || docData.customer_name || docData.customerName || 'Valued Client';
  const customerAddress = docData.address || docData.customer_address || 'Chennai - 600041';
  const customerGstin = docData.gstin || docData.customer_gstin || '33AAFCP5736J1Z9';
  const customerState = docData.state || 'Tamil Nadu';
  const customerStateCode = docData.state_code || docData.stateCode || '33';

  const companyId = docData.companyId || (docData.company?.shortName?.toLowerCase().includes('chn') ? 'chn-tech' : 'wahrms');
  // Use WAHRMS logo unless explicitly specified as chn-tech
  const invoiceLogo = docData.logoBase64 || docData.logo || (companyId === 'chn-tech' ? CHN_LOGO_BASE64 : WAHRMS_LOGO_BASE64);

  // Group items by HSN for statutory tax breakdown
  const hsnMap = {};
  let totalQty = 0;
  items.forEach(it => {
    const hsn = it.hsn || it.hsn_sac || '85437099';
    const qty = Number(it.quantity || it.qty || 1);
    const rate = Number(it.unit_price || it.rate || 0);
    const amt = Number(it.amount || (qty * rate));
    totalQty += qty;
    hsnMap[hsn] = (hsnMap[hsn] || 0) + amt;
  });

  const hsnRows = Object.entries(hsnMap).map(([hsn, taxableVal]) => {
    const cTax = taxableVal * 0.09;
    const sTax = taxableVal * 0.09;
    const totTax = cTax + sTax;
    return [
      { text: hsn, fontSize: 7, alignment: 'left' },
      { text: fmt(taxableVal), fontSize: 7, alignment: 'right' },
      { text: '9%', fontSize: 7, alignment: 'center' },
      { text: fmt(cTax), fontSize: 7, alignment: 'right' },
      { text: '9%', fontSize: 7, alignment: 'center' },
      { text: fmt(sTax), fontSize: 7, alignment: 'right' },
      { text: fmt(totTax), fontSize: 7, alignment: 'right' }
    ];
  });

  // Table body for line items
  const itemRows = [];
  items.forEach((it, idx) => {
    const name = it.name || it.description || 'Hardware and Networking';
    const subDesc = it.sub_description || it.subDescription || it.details || '';
    const hsn = it.hsn || it.hsn_sac || '85437099';
    const qty = Number(it.quantity || it.qty || 1);
    const rate = Number(it.unit_price || it.rate || 0);
    const amt = Number(it.amount || (qty * rate));

    itemRows.push([
      { text: String(idx + 1), fontSize: 7.5, alignment: 'center', border: [true, false, true, false] },
      {
        stack: [
          { text: name, bold: true, fontSize: 7.5 },
          subDesc ? { text: subDesc, italics: true, fontSize: 7, color: '#334155' } : { text: '' }
        ],
        border: [true, false, true, false]
      },
      { text: hsn, fontSize: 7.5, alignment: 'center', border: [true, false, true, false] },
      { text: `${qty} NOS`, bold: true, fontSize: 7.5, alignment: 'right', border: [true, false, true, false] },
      { text: fmt(rate), fontSize: 7.5, alignment: 'right', border: [true, false, true, false] },
      { text: 'NOS', fontSize: 7.5, alignment: 'center', border: [true, false, true, false] },
      { text: fmt(amt), bold: true, fontSize: 7.5, alignment: 'right', border: [true, false, true, false] }
    ]);
  });

  // Add subtotal separator line & taxes inside the items table
  itemRows.push([
    { text: '', border: [true, false, true, false] },
    { text: '', border: [true, false, true, false] },
    { text: '', border: [true, false, true, false] },
    { text: '', border: [true, false, true, false] },
    { text: '', border: [true, false, true, false] },
    { text: '', border: [true, false, true, false] },
    { text: fmt(subtotal), bold: true, fontSize: 8, alignment: 'right', border: [true, true, true, false] }
  ]);

  if (igst > 0) {
    itemRows.push([
      { text: '', border: [true, false, true, false] },
      { text: 'Output IGST@ 18%', bold: true, fontSize: 7.5, alignment: 'right', border: [true, false, true, false] },
      { text: '', border: [true, false, true, false] },
      { text: '', border: [true, false, true, false] },
      { text: '', border: [true, false, true, false] },
      { text: '18 %', fontSize: 7.5, alignment: 'center', border: [true, false, true, false] },
      { text: fmt(igst), bold: true, fontSize: 7.5, alignment: 'right', border: [true, false, true, false] }
    ]);
  } else {
    itemRows.push([
      { text: '', border: [true, false, true, false] },
      { text: 'Output CGST@ 9%', bold: true, fontSize: 7.5, alignment: 'right', border: [true, false, true, false] },
      { text: '', border: [true, false, true, false] },
      { text: '', border: [true, false, true, false] },
      { text: '', border: [true, false, true, false] },
      { text: '9 %', fontSize: 7.5, alignment: 'center', border: [true, false, true, false] },
      { text: fmt(cgst), bold: true, fontSize: 7.5, alignment: 'right', border: [true, false, true, false] }
    ]);
    itemRows.push([
      { text: '', border: [true, false, true, false] },
      { text: 'Output SGST@ 9%', bold: true, fontSize: 7.5, alignment: 'right', border: [true, false, true, false] },
      { text: '', border: [true, false, true, false] },
      { text: '', border: [true, false, true, false] },
      { text: '', border: [true, false, true, false] },
      { text: '9 %', fontSize: 7.5, alignment: 'center', border: [true, false, true, false] },
      { text: fmt(sgst), bold: true, fontSize: 7.5, alignment: 'right', border: [true, false, true, false] }
    ]);
  }

  // Padding empty row to give height to table matching statutory model
  itemRows.push([
    { text: ' ', margin: [0, 50, 0, 0], border: [true, false, true, false] },
    { text: ' ', border: [true, false, true, false] },
    { text: ' ', border: [true, false, true, false] },
    { text: ' ', border: [true, false, true, false] },
    { text: ' ', border: [true, false, true, false] },
    { text: ' ', border: [true, false, true, false] },
    { text: ' ', border: [true, false, true, false] }
  ]);

  const docDefinition = {
    pageSize: 'A4',
    pageMargins: [28, 20, 28, 20],
    content: [
      // Centered Title
      {
        text: 'Tax Invoice',
        bold: true,
        fontSize: 10.5,
        alignment: 'center',
        margin: [0, 0, 0, 4]
      },

      // Outer Container Table
      {
        table: {
          widths: ['*'],
          body: [
            [
              {
                margin: [0, 0, 0, 0],
                stack: [
                  // 1. TOP HEADER & METADATA SECTION
                  {
                    table: {
                      widths: [260, '*'],
                      body: [
                        [
                          // Left: Company + Consignee + Buyer
                          {
                            margin: [0, 0, 0, 0],
                            stack: [
                              // Company Info Block
                              {
                                columns: [
                                  {
                                    image: invoiceLogo,
                                    width: 58,
                                    margin: [2, 10, 4, 4]
                                  },
                                  {
                                    margin: [4, 4, 4, 4],
                                    stack: [
                                      { text: 'CHN TECHNOLOGIES PVT LTD', bold: true, fontSize: 8.5 },
                                      { text: 'NO: 28, 4th Main Road,CIT Nagar,\nChennai - 600035', fontSize: 5.5 },
                                      { text: 'Branch Addres :Door No.1650, 2nd Floor\nAAA Towers,Avinashi Rd, Near\nHope College, Coimbatore - 641004', fontSize: 5.5 },
                                      { text: 'GSTIN/UIN: 33AAJCC3705A1ZC', fontSize: 5.5, bold: true },
                                      { text: 'State Name :  Tamil Nadu, Code : 33', fontSize: 5.5 },
                                      { text: 'Contact : 9884450030 / 7010203031', fontSize: 5.5 },
                                      { text: 'E-Mail : info@chnindia.com', fontSize: 5.5 }
                                    ]
                                  }
                                ]
                              },
                              // Consignee (Ship to)
                              {
                                table: {
                                  widths: ['*'],
                                  body: [
                                    [
                                      {
                                        fillColor: '#ffffff',
                                        margin: [3, 2, 3, 2],
                                        stack: [
                                          { text: 'Consignee (Ship to)', fontSize: 7, color: '#334155' },
                                          { text: customerName, bold: true, fontSize: 8 },
                                          { text: customerAddress, fontSize: 7 },
                                          { text: `GSTIN/UIN : ${customerGstin}`, fontSize: 7 },
                                          { text: `State Name : ${customerState}, Code : ${customerStateCode}`, fontSize: 7 }
                                        ]
                                      }
                                    ]
                                  ]
                                },
                                layout: {
                                  hLineWidth: (i) => (i === 0 ? 0.6 : 0),
                                  vLineWidth: () => 0
                                }
                              },
                              // Buyer (Bill to)
                              {
                                table: {
                                  widths: ['*'],
                                  body: [
                                    [
                                      {
                                        fillColor: '#ffffff',
                                        margin: [3, 2, 3, 2],
                                        stack: [
                                          { text: 'Buyer (Bill to)', fontSize: 7, color: '#334155' },
                                          { text: customerName, bold: true, fontSize: 8 },
                                          { text: customerAddress, fontSize: 7 },
                                          { text: `GSTIN/UIN : ${customerGstin}`, fontSize: 7 },
                                          { text: `State Name : ${customerState}, Code : ${customerStateCode}`, fontSize: 7 }
                                        ]
                                      }
                                    ]
                                  ]
                                },
                                layout: {
                                  hLineWidth: (i) => (i === 0 ? 0.6 : 0),
                                  vLineWidth: () => 0
                                }
                              }
                            ]
                          },
                          // Right: Metadata 2-column Grid
                          {
                            margin: [0, 0, 0, 0],
                            table: {
                              widths: ['50%', '50%'],
                              body: [
                                [
                                  { stack: [{ text: 'Invoice No.', fontSize: 6.5, color: '#475569' }, { text: docNum, bold: true, fontSize: 8 }] },
                                  { stack: [{ text: 'Dated', fontSize: 6.5, color: '#475569' }, { text: dateStr, bold: true, fontSize: 8 }] }
                                ],
                                [
                                  { stack: [{ text: 'Delivery Note', fontSize: 6.5, color: '#475569' }, { text: ' ', fontSize: 7 }] },
                                  { stack: [{ text: 'Mode/Terms of Payment', fontSize: 6.5, color: '#475569' }, { text: ' ', fontSize: 7 }] }
                                ],
                                [
                                  { stack: [{ text: 'Reference No. & Date.', fontSize: 6.5, color: '#475569' }, { text: `${docNum} dt. ${dateStr}`, bold: true, fontSize: 7 }] },
                                  { stack: [{ text: 'Other References', fontSize: 6.5, color: '#475569' }, { text: ' ', fontSize: 7 }] }
                                ],
                                [
                                  { stack: [{ text: "Buyer's Order No.", fontSize: 6.5, color: '#475569' }, { text: ' ', fontSize: 7 }] },
                                  { stack: [{ text: 'Dated', fontSize: 6.5, color: '#475569' }, { text: ' ', fontSize: 7 }] }
                                ],
                                [
                                  { stack: [{ text: 'Dispatch Doc No.', fontSize: 6.5, color: '#475569' }, { text: ' ', fontSize: 7 }] },
                                  { stack: [{ text: 'Delivery Note Date', fontSize: 6.5, color: '#475569' }, { text: ' ', fontSize: 7 }] }
                                ],
                                [
                                  { stack: [{ text: 'Dispatched through', fontSize: 6.5, color: '#475569' }, { text: ' ', fontSize: 7 }] },
                                  { stack: [{ text: 'Destination', fontSize: 6.5, color: '#475569' }, { text: ' ', fontSize: 7 }] }
                                ],
                                [
                                  { colSpan: 2, stack: [{ text: 'Terms of Delivery', fontSize: 6.5, color: '#475569' }, { text: ' ', fontSize: 7 }] },
                                  {}
                                ]
                              ]
                            },
                            layout: {
                              hLineWidth: () => 0.6,
                              vLineWidth: (i) => (i === 1 ? 0.6 : 0),
                              paddingLeft: () => 4,
                              paddingRight: () => 4,
                              paddingTop: () => 2.5,
                              paddingBottom: () => 2.5
                            }
                          }
                        ]
                      ]
                    },
                    layout: {
                      hLineWidth: () => 0,
                      vLineWidth: (i) => (i === 1 ? 0.6 : 0)
                    }
                  },

                  // 2. LINE ITEMS TABLE
                  {
                    table: {
                      headerRows: 1,
                      widths: [20, 210, 48, 48, 48, 25, '*'],
                      body: [
                        [
                          { text: 'Sl\nNo.', bold: true, fontSize: 7.5, alignment: 'center', border: [true, true, true, true] },
                          { text: 'Description of\nGoods and Services', bold: true, fontSize: 7.5, alignment: 'center', border: [true, true, true, true] },
                          { text: '\nHSN/SAC', bold: true, fontSize: 7.5, alignment: 'center', border: [true, true, true, true] },
                          { text: '\nQuantity', bold: true, fontSize: 7.5, alignment: 'center', border: [true, true, true, true] },
                          { text: '\nRate', bold: true, fontSize: 7.5, alignment: 'center', border: [true, true, true, true] },
                          { text: '\nper', bold: true, fontSize: 7.5, alignment: 'center', border: [true, true, true, true] },
                          { text: '\nAmount', bold: true, fontSize: 7.5, alignment: 'center', border: [true, true, true, true] }
                        ],
                        ...itemRows,
                        // Total Row
                        [
                          { text: '', border: [true, true, true, true] },
                          { text: 'Total', bold: true, fontSize: 8, alignment: 'right', border: [true, true, true, true] },
                          { text: '', border: [true, true, true, true] },
                          { text: `${totalQty} NOS`, bold: true, fontSize: 8, alignment: 'right', border: [true, true, true, true] },
                          { text: '', border: [true, true, true, true] },
                          { text: '', border: [true, true, true, true] },
                          { text: `₹ ${fmt(grandTotal)}`, bold: true, fontSize: 9, alignment: 'right', border: [true, true, true, true] }
                        ]
                      ]
                    },
                    layout: {
                      hLineWidth: (i, node) => (i === 0 || i === 1 || i === node.table.body.length - 1 || i === node.table.body.length ? 0.6 : 0),
                      vLineWidth: () => 0.6,
                      paddingLeft: () => 3,
                      paddingRight: () => 3,
                      paddingTop: () => 2.5,
                      paddingBottom: () => 2.5
                    }
                  },

                  // 3. AMOUNT IN WORDS & E. & O.E
                  {
                    table: {
                      widths: ['*'],
                      body: [
                        [
                          {
                            margin: [3, 2, 3, 2],
                            stack: [
                              {
                                columns: [
                                  { text: 'Amount Chargeable (in words)', fontSize: 7, color: '#334155' },
                                  { text: 'E. & O.E', italics: true, fontSize: 7, alignment: 'right' }
                                ]
                              },
                              { text: `INR ${numberToIndianWords(grandTotal).replace(/^Rupees\s+/i, '')}`, bold: true, fontSize: 8 }
                            ]
                          }
                        ]
                      ]
                    },
                    layout: {
                      hLineWidth: () => 0.6,
                      vLineWidth: () => 0
                    }
                  },

                  // 4. STATUTORY HSN/SAC TAX SUMMARY TABLE
                  {
                    table: {
                      headerRows: 2,
                      widths: [200, 56, 32, 54, 32, 54, '*'],
                      body: [
                        [
                          { text: 'HSN/SAC', bold: true, fontSize: 7, rowSpan: 2, alignment: 'center', margin: [0, 6, 0, 0] },
                          { text: 'Taxable\nValue', bold: true, fontSize: 7, rowSpan: 2, alignment: 'center', margin: [0, 3, 0, 0] },
                          { text: 'CGST', bold: true, fontSize: 7, colSpan: 2, alignment: 'center' },
                          {},
                          { text: 'SGST/UTGST', bold: true, fontSize: 7, colSpan: 2, alignment: 'center' },
                          {},
                          { text: 'Total\nTax Amount', bold: true, fontSize: 7, rowSpan: 2, alignment: 'center', margin: [0, 3, 0, 0] }
                        ],
                        [
                          {},
                          {},
                          { text: 'Rate', bold: true, fontSize: 6.5, alignment: 'center' },
                          { text: 'Amount', bold: true, fontSize: 6.5, alignment: 'center' },
                          { text: 'Rate', bold: true, fontSize: 6.5, alignment: 'center' },
                          { text: 'Amount', bold: true, fontSize: 6.5, alignment: 'center' },
                          {}
                        ],
                        ...hsnRows,
                        // Total Row for HSN table
                        [
                          { text: 'Total', bold: true, fontSize: 7, alignment: 'right' },
                          { text: fmt(subtotal), bold: true, fontSize: 7, alignment: 'right' },
                          { text: '', fontSize: 7 },
                          { text: fmt(cgst), bold: true, fontSize: 7, alignment: 'right' },
                          { text: '', fontSize: 7 },
                          { text: fmt(sgst), bold: true, fontSize: 7, alignment: 'right' },
                          { text: fmt(cgst + sgst + igst), bold: true, fontSize: 7, alignment: 'right' }
                        ]
                      ]
                    },
                    layout: {
                      hLineWidth: () => 0.6,
                      vLineWidth: () => 0.6,
                      paddingLeft: () => 3,
                      paddingRight: () => 3,
                      paddingTop: () => 2,
                      paddingBottom: () => 2
                    }
                  },

                  // 5. TAX AMOUNT IN WORDS
                  {
                    table: {
                      widths: ['*'],
                      body: [
                        [
                          {
                            margin: [3, 2, 3, 2],
                            columns: [
                              { text: 'Tax Amount (in words)  : ', fontSize: 7, width: 100 },
                              { text: `INR ${numberToIndianWords(cgst + sgst + igst).replace(/^Rupees\s+/i, '')}`, bold: true, fontSize: 7.5, width: '*' }
                            ]
                          }
                        ]
                      ]
                    },
                    layout: {
                      hLineWidth: () => 0.6,
                      vLineWidth: () => 0
                    }
                  },

                  // 6. BOTTOM DETAILS: REMARKS, DECLARATION, BANK & SIGNATURES
                  {
                    table: {
                      widths: [260, '*'],
                      body: [
                        [
                          // Left: Remarks & Declaration
                          {
                            margin: [4, 4, 4, 4],
                            stack: [
                              { text: 'Remarks:', italics: true, fontSize: 7 },
                              { text: docData.notes || `Being towards Sale of ${items[0]?.name || 'Hardware and Networking and Software'}`, fontSize: 7 },
                              { text: 'Declaration', bold: true, fontSize: 7, margin: [0, 10, 0, 2] },
                              { text: 'We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct.', fontSize: 6.8 }
                            ]
                          },
                          // Right: Bank Details & Signatures
                          {
                            margin: [0, 0, 0, 0],
                            stack: [
                              {
                                margin: [4, 4, 4, 4],
                                stack: [
                                  { text: "Company's Bank Details", bold: true, fontSize: 7 },
                                  {
                                    columns: [
                                      { text: "A/c Holder's Name :", fontSize: 6.8, width: 95 },
                                      { text: 'CHN TECHNOLOGIES PVT LTD', bold: true, fontSize: 6.8, width: '*' }
                                    ]
                                  },
                                  {
                                    columns: [
                                      { text: 'Bank Name :', fontSize: 6.8, width: 95 },
                                      { text: 'Axis Bank - 921020014696411', bold: true, fontSize: 6.8, width: '*' }
                                    ]
                                  },
                                  {
                                    columns: [
                                      { text: 'A/c No. :', fontSize: 6.8, width: 95 },
                                      { text: '921020014696411', bold: true, fontSize: 6.8, width: '*' }
                                    ]
                                  },
                                  {
                                    columns: [
                                      { text: 'Branch & IFS Code :', fontSize: 6.8, width: 95 },
                                      { text: 'UTIB0003702', bold: true, fontSize: 6.8, width: '*' }
                                    ]
                                  }
                                ]
                              },
                              // Signatures Box
                              {
                                table: {
                                  widths: ['*'],
                                  body: [
                                    [
                                      {
                                        margin: [4, 2, 4, 2],
                                        stack: [
                                          { text: 'for CHN TECHNOLOGIES PVT LTD', bold: true, fontSize: 7.5, alignment: 'right' },
                                          {
                                            columns: [
                                              { text: 'Prepared by', fontSize: 7 },
                                              { text: 'Verified by', fontSize: 7, alignment: 'center' },
                                              { text: 'Authorised Signatory', fontSize: 7, alignment: 'right' }
                                            ],
                                            margin: [0, 20, 0, 2]
                                          }
                                        ]
                                      }
                                    ]
                                  ]
                                },
                                layout: {
                                  hLineWidth: (i) => (i === 0 ? 0.6 : 0),
                                  vLineWidth: () => 0
                                }
                              }
                            ]
                          }
                        ]
                      ]
                    },
                    layout: {
                      hLineWidth: () => 0,
                      vLineWidth: (i) => (i === 1 ? 0.6 : 0)
                    }
                  }
                ]
              }
            ]
          ]
        },
        layout: {
          hLineWidth: () => 0.6,
          vLineWidth: () => 0.6,
          paddingLeft: () => 0,
          paddingRight: () => 0,
          paddingTop: () => 0,
          paddingBottom: () => 0
        }
      },

      // Bottom Computer Generated Invoice notice
      {
        text: 'This is a Computer Generated Invoice',
        fontSize: 7,
        alignment: 'center',
        margin: [0, 4, 0, 0]
      }
    ],
    defaultStyle: {
      fontSize: 8,
      color: '#0f172a'
    }
  };

  const pdf = pdfMake.createPdf(docDefinition);
  if (download) {
    const rawNum = docData.number || docData.doc_number || docData.docNumber || '0001';
    const cleanNum = String(rawNum).replace(/[\\/]/g, '-').replace(/[^a-zA-Z0-9-_]/g, '');
    pdf.download(`Tax_Invoice_${cleanNum}.pdf`);
  }
  return pdf;
}
