import React, { useState, useEffect, useMemo } from 'react';
import API from '../../services/api';
import './QuotationModal.css';
import { 
  FileText, 
  Plus, 
  Trash2, 
  Download, 
  Check, 
  X, 
  Building2, 
  User, 
  Phone, 
  Mail, 
  MapPin, 
  CreditCard,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Cpu,
  ShieldCheck,
  Layers
} from 'lucide-react';

import PingoMascot from '../Common/PingoMascot';
import PingoPopupService from '../../services/pingoPopupService';
import { 
  computeInvoice, 
  INDIAN_STATES, 
  COMPANY_DEFAULTS,
  COMPANIES,
  numberToIndianWords
} from '../../utils/billingMoney';
import { generateBillingPdf, generateQuotationPdf, generateProformaPdf, generateTaxInvoicePdf } from '../../utils/quotationPdf';
import { CHN_LOGO_BASE64, WAHRMS_LOGO_BASE64 } from '../../utils/logoBase64';

const DEFAULT_TERMS_QUOTATION = 
`1. Prices are subject to applicable GST as specified.
2. Software activation and onboarding will begin upon PO confirmation and receipt of payment.
3. Setup, training, and technical support will be provided as agreed.
4. The client is responsible for providing accurate employee and payroll data and verifying payroll calculations.
5. Timely subscription renewal is required to ensure uninterrupted software access.
6. Customization and third-party integrations may incur additional charges.
7. Confirmation of the purchase order constitutes acceptance of the quotation and these terms.`;

const DEFAULT_TERMS_BIOMETRIC_QUOTATION = 
`1. Prices are subject to applicable GST as specified.
2. Products carry a one-year manufacturer warranty covering manufacturing defects (excludes physical damage, electrical surge, or liquid ingress).
3. Delivery, device installation, and cloud punch synchronization will be scheduled upon receipt of purchase order and advance payment.
4. Client shall provide required power points, cabling infrastructure, and network access at installation sites.
5. Setup, device registration, and administrator training will be provided upon installation.
6. Confirmation of the purchase order constitutes acceptance of this quotation and terms.`;

const DEFAULT_TERMS_PROFORMA = 
`1. Payment terms: 100% advance payment against this Proforma Invoice.
2. Bank transfers to be credited to the Axis Bank account mentioned above.
3. Materials will be dispatched upon payment credit receipt.
4. Goods once sold will not be taken back.`;

const DEFAULT_TERMS_INVOICE = 
`1. Payment received and verified by Finance.
2. Services/goods supplied strictly in accordance with client order.
3. Official Statutory Tax Invoice issued under GST Rules.
4. Subject to Chennai jurisdiction.`;


const DEFAULT_NOTES_QUOTATION = '';

export const ADD_ON_SERVICES = [
  { 
    name: 'Shift Roster',
    description: 'Shift Roster', 
    hsn: '998314', 
    rate: 0, 
    qty: 1, 
    gstRate: 0.18 
  },
  { 
    name: 'Live Tracking',
    description: 'Live Tracking', 
    hsn: '998314', 
    rate: 0, 
    qty: 1, 
    gstRate: 0.18 
  },
  { 
    name: 'Biometric Integration',
    description: 'Biometric Integration', 
    hsn: '998314', 
    rate: 4999, 
    qty: 1, 
    gstRate: 0.18 
  },
  { 
    name: 'Software Installation',
    description: 'Software Installation', 
    hsn: '998315', 
    rate: 1000, 
    qty: 1, 
    gstRate: 0.18 
  },
  { 
    name: 'WA Payroll Setup',
    description: 'WA Payroll Cloud Setup & Deployment', 
    hsn: '998315', 
    rate: 5000, 
    qty: 1, 
    gstRate: 0.18 
  },
  { 
    name: 'Comprehensive AMC',
    description: 'Comprehensive Annual Maintenance Contract (AMC)', 
    hsn: '998719', 
    rate: 6000, 
    qty: 1, 
    gstRate: 0.18 
  }
];

export const PRESET_SERVICES = ADD_ON_SERVICES;

export const FALLBACK_WAHRMS_BUNDLES = [
  {
    bundleCode: 'hr_atm',
    name: 'HR + ATM',
    tagline: 'Core HR with attendance & time.',
    description: 'Integrated employee directory, leave management, and real-time biometric attendance capture.',
    badge: null,
    features: [
      'Core HR & Employee Directory',
      'Attendance & Time Tracking',
      'Leave & Holiday Management',
      'Biometric Device Integration'
    ],
    items: [
      {
        item_code: 'HR_ATM_SUB',
        name: 'WAHRMS HR + Attendance Subscription',
        description: 'WAHRMS HR + Attendance Subscription',
        hsn: '998314',
        qty: 120,
        rate: 45,
        gstRate: 0.18,
        discount: 0
      },
      {
        item_code: 'BIO_INTEGRATION',
        name: 'Biometric Integration',
        description: 'Biometric Integration',
        hsn: '998314',
        qty: 1,
        rate: 4999,
        gstRate: 0.18,
        discount: 0
      }
    ]
  },
  {
    bundleCode: 'hr_atm_payroll',
    name: 'HR + ATM + Payroll',
    tagline: 'The full suite.',
    description: 'The complete all-in-one workforce powerhouse: Core HR, biometric attendance, statutory payroll, and self-service.',
    badge: 'Full Suite • Best Value',
    features: [
      'Core HR & Lifecycle Management',
      'Biometric Attendance Sync',
      'Statutory Payroll & Compliance Engine',
      'One-Click Payslips & Direct Bank Advice'
    ],
    items: [
      {
        item_code: 'HR_ATM_PAYROLL_SUB',
        name: 'WAHRMS Complete Suite (HR + ATM + Payroll) Subscription',
        description: 'WAHRMS Complete Suite (HR + ATM + Payroll) Subscription',
        hsn: '998314',
        qty: 120,
        rate: 65,
        gstRate: 0.18,
        discount: 0
      },
      {
        item_code: 'BIO_PAYROLL_PACKAGE',
        name: 'bio & payroll Integrated Package',
        description: 'bio & payroll Integrated Package',
        hsn: '85437099',
        qty: 1,
        rate: 24500,
        gstRate: 0.18,
        discount: 0
      }
    ]
  },
  {
    bundleCode: 'hr_payroll',
    name: 'HR + Payroll',
    tagline: 'Core HR with payroll & statutory.',
    description: 'Comprehensive employee records paired with full salary computation, payslips, PF, ESI, TDS, and statutory compliance.',
    badge: null,
    features: [
      'Core HR & Employee Profiles',
      'Statutory Payroll Engine',
      'PF, ESI, PT & TDS Filings',
      'One-Click Payslips & Direct Bank Advice'
    ],
    items: [
      {
        item_code: 'HR_PAYROLL_SUB',
        name: 'WAHRMS HR + Payroll Cloud Subscription',
        description: 'WAHRMS HR + Payroll Cloud Subscription',
        hsn: '998314',
        qty: 120,
        rate: 50,
        gstRate: 0.18,
        discount: 0
      },
      {
        item_code: 'PAYROLL_SETUP',
        name: 'WA Payroll Cloud Setup & Deployment',
        description: 'WA Payroll Cloud Setup & Deployment',
        hsn: '998315',
        qty: 1,
        rate: 5000,
        gstRate: 0.18,
        discount: 0
      }
    ]
  }
];

export const BIOMETRIC_ADD_ON_SERVICES = [
  { 
    name: 'Device Installation',
    description: 'Installation & Calibration', 
    hsn: '998315', 
    rate: 1000, 
    qty: 1, 
    gstRate: 0.18 
  },
  { 
    name: 'Hardware Cloud Sync',
    description: 'Hardware Cloud Sync Bridge', 
    hsn: '998314', 
    rate: 4999, 
    qty: 1, 
    gstRate: 0.18 
  },
  { 
    name: '4G IoT SIM Card',
    description: '4G Data SIM Card with 1-Year IoT Connectivity', 
    hsn: '998412', 
    rate: 1500, 
    qty: 1, 
    gstRate: 0.18 
  },
  { 
    name: 'Biometric AMC Support',
    description: 'Comprehensive Annual Maintenance Contract (AMC)', 
    hsn: '998719', 
    rate: 6000, 
    qty: 1, 
    gstRate: 0.18 
  },
  { 
    name: 'Extra Power Adapter',
    description: '12V 2A Regulated Power Supply Unit', 
    hsn: '85044090', 
    rate: 750, 
    qty: 1, 
    gstRate: 0.18 
  }
];

export const FALLBACK_BIOMETRIC_BUNDLES = [
  {
    bundleCode: 'bio_standard',
    category: 'BIOMETRIC',
    name: 'Biometric Standard (MB160 Terminal)',
    tagline: 'Standalone facial & fingerprint terminal with cloud punch sync',
    description: 'Enterprise biometric terminal with face, fingerprint, and RFID recognition, bundled with 4G IoT SIM card, cloud synchronization bridge, and installation.',
    badge: 'Popular Hardware',
    features: [
      'MB160 Face + Fingerprint + RFID Terminal',
      '1x 4G IoT SIM Card Included',
      'Hardware Protocol Bridge & Cloud Sync',
      'Standard Wall Mount & Power Brick',
      'Onsite Hardware Setup & Testing'
    ],
    items: [
      {
        item_code: 'MB160_DEVICE',
        name: 'MB160 Biometric Device',
        description: 'MB160 Biometric Device',
        hsn: '85437099',
        qty: 1,
        rate: 22400,
        gstRate: 0.18,
        discount: 0
      },
      {
        item_code: 'BIO_CLOUD_SYNC',
        name: 'Hardware Cloud Sync Bridge',
        description: 'Hardware Cloud Sync Bridge',
        hsn: '998314',
        qty: 1,
        rate: 4999,
        gstRate: 0.18,
        discount: 0
      },
      {
        item_code: 'DEVICE_INSTALL',
        name: 'Installation & Calibration',
        description: 'Installation & Calibration',
        hsn: '998315',
        qty: 1,
        rate: 1000,
        gstRate: 0.18,
        discount: 0
      }
    ]
  },
  {
    bundleCode: 'bio_atm',
    category: 'BIOMETRIC',
    name: 'WA ATM Biometric Hardware',
    tagline: 'Cost-effective optical attendance machine for offices & retail',
    description: 'WA ATM biometric terminal designed for rapid shift attendance logging, cloud software integration, and effortless deployment.',
    badge: 'Cost Effective',
    features: [
      'WA ATM Machine & Biometric Hardware',
      'Dual Face & Optical Fingerprint Sensor',
      'TCP/IP & Cloud Sync Ready',
      'Wall Mounting & Power Adapter Included',
      'Setup & Device Training Included'
    ],
    items: [
      {
        item_code: 'WA_ATM_HARDWARE',
        name: 'WA ATM Machine Hardware',
        description: 'WA ATM Machine Hardware',
        hsn: '85437099',
        qty: 1,
        rate: 18500,
        gstRate: 0.18,
        discount: 0
      },
      {
        item_code: 'WA_ATM_SETUP',
        name: 'Setup & Deployment',
        description: 'Setup & Deployment',
        hsn: '998315',
        qty: 1,
        rate: 1000,
        gstRate: 0.18,
        discount: 0
      }
    ]
  },
  {
    bundleCode: 'bio_enterprise',
    category: 'BIOMETRIC',
    name: 'Biometric Multi-Location Suite',
    tagline: 'Dual terminal package for branch & multi-door deployments',
    description: 'Complete multi-location biometric setup with dual MB160 terminals, SIM cards, enterprise cloud integration bridge, and multi-device deployment.',
    badge: 'Multi-Door Enterprise',
    features: [
      '2x MB160 Face + Fingerprint + RFID Terminals',
      '2x 4G IoT SIM Cards Included',
      'Multi-Branch Central Cloud Sync Bridge',
      'Centralized Punch Dashboard Setup',
      'Multi-Device Installation & Operator Training'
    ],
    items: [
      {
        item_code: '2X_MB160_DEVICES',
        name: '2x MB160 Biometric Terminals',
        description: '2x MB160 Biometric Terminals',
        hsn: '85437099',
        qty: 1,
        rate: 44800,
        gstRate: 0.18,
        discount: 0
      },
      {
        item_code: 'MULTI_CLOUD_BRIDGE',
        name: 'Multi-Location Cloud Bridge',
        description: 'Multi-Location Cloud Bridge',
        hsn: '998314',
        qty: 1,
        rate: 7500,
        gstRate: 0.18,
        discount: 0
      },
      {
        item_code: 'MULTI_INSTALL',
        name: 'Multi-Device Deployment',
        description: 'Multi-Device Deployment',
        hsn: '998315',
        qty: 1,
        rate: 2000,
        gstRate: 0.18,
        discount: 0
      }
    ]
  }
];

export const ALL_FALLBACK_BUNDLES = [
  ...FALLBACK_WAHRMS_BUNDLES.map(b => ({ ...b, category: 'WAHRMS' })),
  ...FALLBACK_BIOMETRIC_BUNDLES.map(b => ({ ...b, category: 'BIOMETRIC' }))
];

export default function QuotationModal({
  isOpen,
  onClose,
  initialData = {},
  onSuccess
}) {
  if (!isOpen) return null;

  const isEditMode = Boolean(initialData?.id || initialData?.docId);

  const getLoggedInUser = () => {
    try {
      const saved = localStorage.getItem('crm_user');
      if (saved) return JSON.parse(saved);
    } catch (_) {}
    return null;
  };

  const currentUser = getLoggedInUser();
  const getLoggedInUserName = () => currentUser?.full_name || currentUser?.name || currentUser?.username || 'Ketziaya';
  const userRole = (currentUser?.role || '').toUpperCase();
  const isFinance = userRole === 'FINANCE';
  const isFinanceOrAdmin = userRole === 'ADMIN' || userRole === 'FINANCE';

  const [docType, setDocType] = useState(initialData.docType || 'quotation');
  const [selectedCompanyId, setSelectedCompanyId] = useState(initialData.companyId || 'wahrms');
  const [customerName, setCustomerName] = useState(initialData.name || initialData.customerName || '');
  const [companyName, setCompanyName] = useState(initialData.company || initialData.companyName || '');
  const [phone, setPhone] = useState(initialData.phone || '');
  const [email, setEmail] = useState(initialData.email || '');
  const [address, setAddress] = useState(initialData.address || initialData.location || '');
  const [state, setState] = useState(initialData.state || 'Tamil Nadu');
  const [stateCode, setStateCode] = useState('33');
  const [gstin, setGstin] = useState(initialData.gstin || '');
  const [preparedBy, setPreparedBy] = useState(() => initialData.preparedBy || initialData.employeeName || getLoggedInUserName());

  // Product category: 'wahrms' or 'biometric'
  const [productCategory, setProductCategory] = useState(
    (initialData.productCategory || initialData.product_category || 'wahrms').toLowerCase()
  );
  const [allowDuplicateIntent, setAllowDuplicateIntent] = useState(Boolean(initialData.allowDuplicate));

  // Manageable Product Bundle Master state (WAHRMS & Biometric)
  const [bundles, setBundles] = useState(ALL_FALLBACK_BUNDLES);
  const [bundlesLoading, setBundlesLoading] = useState(false);
  const [bundlesError, setBundlesError] = useState(null);
  const [selectedBundle, setSelectedBundle] = useState(
    initialData.selectedBundle || initialData.selected_bundle || (!isEditMode ? 'hr_atm' : null)
  );


  // Fetch bundles from backend master API with graceful fallback handling
  useEffect(() => {
    let isMounted = true;
    const fetchBundles = async () => {
      try {
        setBundlesLoading(true);
        setBundlesError(null);
        const res = await API.get('/integrations/waquote/bundles', { params: { category: 'all' } });
        if (res.data?.ok && Array.isArray(res.data.bundles) && res.data.bundles.length > 0) {
          if (isMounted) {
            setBundles(res.data.bundles);
          }
        }
      } catch (err) {
        console.warn('Failed to load bundles from server, using local master:', err);
        if (isMounted) {
          setBundlesError('Backend bundle master unavailable. Loaded verified bundle configuration.');
          setBundles(ALL_FALLBACK_BUNDLES);
        }
      } finally {
        if (isMounted) setBundlesLoading(false);
      }
    };
    if (isOpen) {
      fetchBundles();
    }
    return () => { isMounted = false; };
  }, [isOpen]);

  // If this document is an official Tax Invoice and the current user is NOT in the Finance team, force read-only mode
  const isTaxInvoice = (docType === 'invoice') || ((initialData.docType || '').toLowerCase() === 'invoice');
  const isReadOnly = isTaxInvoice && !isFinance;

  // Synchronize state whenever modal opens or initialData changes
  useEffect(() => {
    if (isOpen) {
      const type = (initialData.docType || 'quotation').toLowerCase();
      setDocType(type);
      const incomingCompany = initialData.companyId || (initialData.productCategory === 'biometric' ? 'chn-tech' : 'wahrms');
      setSelectedCompanyId(incomingCompany);
      setCustomerName(initialData.customerName || initialData.name || '');
      setCompanyName(initialData.companyName || initialData.company || '');
      setPhone(initialData.phone || '');
      setEmail(initialData.email || '');
      setAddress(initialData.address || initialData.location || '');
      const curState = initialData.state || 'Tamil Nadu';
      setState(curState);
      const curStateCode = initialData.stateCode || (INDIAN_STATES.find(s => s.name.toLowerCase() === curState.toLowerCase())?.code || '33');
      setStateCode(curStateCode);
      setGstin(initialData.gstin || '');
      setPreparedBy(initialData.preparedBy || initialData.employeeName || getLoggedInUserName());

      const incomingCategory = (initialData.productCategory || initialData.product_category || (incomingCompany === 'chn-tech' ? 'biometric' : 'wahrms')).toLowerCase();
      setProductCategory(incomingCategory);
      setAllowDuplicateIntent(Boolean(initialData.allowDuplicate));

      const defaultBundleCode = incomingCategory === 'biometric' ? 'bio_standard' : 'hr_atm';
      const incomingBundle = initialData.selectedBundle || initialData.selected_bundle || null;
      if (incomingBundle) {
        setSelectedBundle(incomingBundle);
      } else if (!isEditMode && (!initialData.lineItems || initialData.lineItems.length === 0)) {
        setSelectedBundle(defaultBundleCode);
      } else {
        setSelectedBundle(null);
      }

      if (initialData.lineItems && Array.isArray(initialData.lineItems) && initialData.lineItems.length > 0) {
        const isBio = incomingCategory === 'biometric';
        setLineItems(initialData.lineItems.map((item, idx) => ({
          id: item.id || Date.now() + idx,
          isBundleItem: item.isBundleItem !== undefined ? Boolean(item.isBundleItem) : Boolean(item.bundleId || (incomingBundle && idx < 2)),
          bundleId: item.bundleId || (item.isBundleItem ? incomingBundle : null),
          description: item.name || (item.description ? item.description.split('\n')[0] : ''),
          hsn: item.hsn || item.hsnCode || (isBio ? '85437099' : '998314'),
          qty: Number(item.qty ?? item.quantity ?? 1),
          rate: Number(item.rate ?? item.unitPrice ?? item.price ?? 0),
          gstRate: item.gstRate !== undefined ? Number(item.gstRate) : 0.18,
          discount: Number(item.discount ?? 0)
        })));
      } else {
        const defaultCode = incomingBundle || defaultBundleCode;
        const activeBundleObj = bundles.find(b => (b.bundleCode || b.bundle_code) === defaultCode) 
          || (incomingCategory === 'biometric' ? FALLBACK_BIOMETRIC_BUNDLES[0] : FALLBACK_WAHRMS_BUNDLES[0]);
        const targetCode = activeBundleObj.bundleCode || activeBundleObj.bundle_code;
        setSelectedBundle(targetCode);
        const isBio = incomingCategory === 'biometric';
        setLineItems((activeBundleObj.items || []).map((itm, idx) => ({
          id: Date.now() + idx,
          isBundleItem: true,
          bundleId: targetCode,
          description: itm.name || (itm.description ? itm.description.split('\n')[0] : ''),
          hsn: itm.hsn || (isBio ? '85437099' : '998314'),
          qty: Number(itm.qty !== undefined ? itm.qty : 1),
          rate: Number(itm.rate !== undefined ? itm.rate : 0),
          gstRate: itm.gstRate !== undefined ? Number(itm.gstRate) : 0.18,
          discount: Number(itm.discount || 0)
        })));
      }

      setTerms(
        initialData.terms !== undefined
          ? initialData.terms
          : (type === 'invoice' ? DEFAULT_TERMS_INVOICE : (type === 'proforma' ? DEFAULT_TERMS_PROFORMA : (incomingCategory === 'biometric' ? DEFAULT_TERMS_BIOMETRIC_QUOTATION : DEFAULT_TERMS_QUOTATION)))
      );
      setNotes(
        initialData.notes !== undefined
          ? initialData.notes
          : DEFAULT_NOTES_QUOTATION
      );
      setError('');
      setSuccessMsg('');
    }
  }, [isOpen, initialData]);


  const activeCompany = COMPANIES.find(c => c.id === selectedCompanyId) || COMPANIES[0];

  // Initialize line items
  const [lineItems, setLineItems] = useState(() => {
    if (initialData.lineItems && initialData.lineItems.length > 0) {
      const incomingBundle = initialData.selectedBundle || initialData.selected_bundle || null;
      return initialData.lineItems.map((item, idx) => ({
        id: item.id || Date.now() + idx,
        isBundleItem: item.isBundleItem !== undefined ? Boolean(item.isBundleItem) : Boolean(item.bundleId),
        bundleId: item.bundleId || (item.isBundleItem ? incomingBundle : null),
        description: item.name || (item.description ? item.description.split('\n')[0] : ''),
        hsn: item.hsn || item.hsnCode || '998314',
        qty: Number(item.qty ?? item.quantity ?? 1),
        rate: Number(item.rate ?? item.unitPrice ?? item.price ?? 0),
        gstRate: item.gstRate !== undefined ? Number(item.gstRate) : 0.18,
        discount: Number(item.discount ?? 0)
      }));
    }
    const defaultBundle = FALLBACK_WAHRMS_BUNDLES[0];
    return (defaultBundle.items || []).map((itm, idx) => ({
      id: Date.now() + idx,
      isBundleItem: true,
      bundleId: defaultBundle.bundleCode,
      description: itm.name || (itm.description ? itm.description.split('\n')[0] : ''),
      hsn: itm.hsn || '998314',
      qty: Number(itm.qty !== undefined ? itm.qty : 1),
      rate: Number(itm.rate !== undefined ? itm.rate : 0),
      gstRate: itm.gstRate !== undefined ? Number(itm.gstRate) : 0.18,
      discount: Number(itm.discount || 0)
    }));
  });

  const [terms, setTerms] = useState(() => 
    docType === 'invoice' ? DEFAULT_TERMS_INVOICE : (docType === 'proforma' ? DEFAULT_TERMS_PROFORMA : (productCategory === 'biometric' ? DEFAULT_TERMS_BIOMETRIC_QUOTATION : DEFAULT_TERMS_QUOTATION))
  );
  const [notes, setNotes] = useState(() => initialData.notes || DEFAULT_NOTES_QUOTATION);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Auto-update state code when state changes
  useEffect(() => {
    const found = INDIAN_STATES.find(s => s.name.toLowerCase() === state.toLowerCase());
    if (found) {
      setStateCode(found.code);
    } else {
      setStateCode('33');
    }
  }, [state]);

  // Tax mode: stateCode 33 is Tamil Nadu intra-state
  const taxMode = stateCode === '33' ? 'intra' : 'inter';

  // Compute live tax totals
  const calc = useMemo(() => {
    return computeInvoice(lineItems, taxMode, true);
  }, [lineItems, taxMode]);

  // Update terms on docType toggle
  const handleTypeChange = (newType) => {
    if (newType === 'invoice' && !isFinance) {
      setError('Tax Invoices can only be created and issued by the Finance Team.');
      return;
    }
    setError('');
    setDocType(newType);
    if (newType === 'proforma') {
      setTerms(DEFAULT_TERMS_PROFORMA);
    } else if (newType === 'invoice') {
      setTerms(DEFAULT_TERMS_INVOICE);
    } else {
      setTerms(productCategory === 'biometric' ? DEFAULT_TERMS_BIOMETRIC_QUOTATION : DEFAULT_TERMS_QUOTATION);
    }
  };

  // Bundle Selection Handler: replaces bundle modules while preserving additional custom products
  const handleSelectBundle = (bundle) => {
    const bCode = bundle.bundleCode || bundle.bundle_code;
    setSelectedBundle(bCode);
    if (bundle.category) {
      setProductCategory(bundle.category.toLowerCase());
    }

    // Keep all custom/extra products added separately by the user
    const customItems = lineItems.filter(item => !item.isBundleItem && !item.bundleId);

    // Build new bundle items from bundle master
    const isBio = (bundle.category || productCategory || '').toUpperCase() === 'BIOMETRIC';
    const newBundleItems = (bundle.items || []).map((itm, idx) => ({
      id: Date.now() + idx,
      isBundleItem: true,
      bundleId: bCode,
      description: itm.name || (itm.description ? itm.description.split('\n')[0] : ''),
      hsn: itm.hsn || (isBio ? '85437099' : '998314'),
      qty: Number(itm.qty !== undefined ? itm.qty : 1),
      rate: Number(itm.rate !== undefined ? itm.rate : 0),
      gstRate: itm.gstRate !== undefined ? Number(itm.gstRate) : 0.18,
      discount: Number(itm.discount || 0)
    }));

    // Avoid duplicate items and place bundle items first
    setLineItems([...newBundleItems, ...customItems]);
  };

  const handleCategoryChange = (newCat) => {
    const catLower = newCat.toLowerCase();
    setProductCategory(catLower);
    if (docType === 'quotation') {
      setTerms(catLower === 'biometric' ? DEFAULT_TERMS_BIOMETRIC_QUOTATION : DEFAULT_TERMS_QUOTATION);
    }
    const catBundles = bundles.filter(b => (b.category || 'WAHRMS').toLowerCase() === catLower);
    if (catBundles.length > 0) {
      handleSelectBundle(catBundles[0]);
    } else {
      const fallback = catLower === 'biometric' ? FALLBACK_BIOMETRIC_BUNDLES[0] : FALLBACK_WAHRMS_BUNDLES[0];
      handleSelectBundle(fallback);
    }
  };

  const handleCompanyChange = (newCompanyId) => {
    setSelectedCompanyId(newCompanyId);
    const targetCat = newCompanyId === 'chn-tech' ? 'biometric' : 'wahrms';
    handleCategoryChange(targetCat);
  };

  const handleClearBundle = () => {
    setSelectedBundle(null);
    const customItems = lineItems.filter(item => !item.isBundleItem && !item.bundleId);
    if (customItems.length === 0) {
      setLineItems([{
        id: Date.now(),
        isBundleItem: false,
        bundleId: null,
        description: '',
        hsn: productCategory === 'biometric' ? '85437099' : '998314',
        qty: 1,
        rate: 0,
        gstRate: 0.18,
        discount: 0
      }]);
    } else {
      setLineItems(customItems);
    }
  };

  const handleAddLine = (preset = null) => {
    const newItem = preset ? {
      id: Date.now(),
      isBundleItem: false,
      bundleId: null,
      description: preset.name || (preset.description ? preset.description.split('\n')[0] : ''),
      hsn: preset.hsn || '998314',
      qty: preset.qty !== undefined ? preset.qty : 1,
      rate: preset.rate !== undefined ? preset.rate : 0,
      gstRate: preset.gstRate !== undefined ? preset.gstRate : 0.18,
      discount: 0
    } : {
      id: Date.now(),
      isBundleItem: false,
      bundleId: null,
      description: '',
      hsn: '998314',
      qty: 1,
      rate: 0,
      gstRate: 0.18,
      discount: 0
    };
    setLineItems(prev => [...prev, newItem]);
  };

  const handleRemoveLine = (idx) => {
    if (lineItems.length <= 1) return;
    setLineItems(prev => prev.filter((_, i) => i !== idx));
  };

  const handleLineChange = (idx, field, val) => {
    setLineItems(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: val };
      return next;
    });
  };

  const [showDuplicateConflict, setShowDuplicateConflict] = useState(false);

  const buildDocPayload = (overrideAllowDuplicate = false) => {
    return {
      doc_type: docType,
      selected_bundle: selectedBundle,
      product_category: productCategory,
      source_quotation_id: initialData.sourceQuotationId || initialData.source_quotation_id || null,
      source_quotation_number: initialData.sourceQuotationNumber || initialData.source_quotation_number || null,
      allow_duplicate: Boolean(overrideAllowDuplicate || initialData.allowDuplicate || allowDuplicateIntent),
      lead_id: initialData.leadId ? Number(initialData.leadId) : null,
      customer_id: initialData.customerId ? Number(initialData.customerId) : null,
      customer_name: customerName.trim() || 'Valued Client',
      company_name: companyName.trim(),
      phone: phone.trim(),
      email: email.trim(),
      address: address.trim(),
      state,
      state_code: stateCode,
      gstin: gstin.trim(),
      company_id: selectedCompanyId,
      company: activeCompany,
      tax_mode: taxMode,
      subtotal: calc.taxableAmount,
      cgst: calc.cgstTotal,
      sgst: calc.sgstTotal,
      igst: calc.igstTotal,
      tax_total: calc.taxTotal,
      round_off: calc.roundOff,
      grand_total: calc.grandTotal,
      line_items: lineItems,
      terms_and_conditions: terms,
      notes,
      prepared_by: preparedBy.trim(),
      status: 'issued',
      payment_status: 'unpaid'
    };
  };


  const handleDownloadPdf = () => {
    const payload = buildDocPayload();
    const docData = {
      ...payload,
      docType,
      doc_type: docType,
      companyId: selectedCompanyId,
      company: activeCompany,
      number: isEditMode && (initialData.docNumber || initialData.number) 
        ? (initialData.docNumber || initialData.number)
        : `PREVIEW-${docType.toUpperCase()}`,
      customerName,
      companyName,
      phone,
      email,
      address,
      state,
      stateCode,
      gstin,
      preparedBy: preparedBy.trim() || 'Authorized Signatory',
      taxMode,
      subtotal: calc.taxableAmount,
      cgst: calc.cgstTotal,
      sgst: calc.sgstTotal,
      igst: calc.igstTotal,
      roundOff: calc.roundOff,
      grandTotal: calc.grandTotal,
      lineItems,
      terms,
      issueDateFormatted: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
      validTillFormatted: new Date(Date.now() + 7 * 86400000).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
    };
    if (docType === 'proforma') {
      generateProformaPdf(docData, true);
    } else if (docType === 'invoice') {
      generateTaxInvoicePdf(docData, true);
    } else {
      generateQuotationPdf(docData, true);
    }
    PingoPopupService.triggerDownloadSuccess({
      docType: docType === 'invoice' ? 'Tax Invoice' : (docType === 'proforma' ? 'Proforma Invoice' : 'Quotation'),
      reference: docData.number || customerName || 'Document',
      customMessage: `${docType === 'invoice' ? 'Tax Invoice' : (docType === 'proforma' ? 'Proforma Invoice' : 'Quotation')} downloaded successfully!`
    });
  };

  const handleSaveAndIssue = async () => {
    if (isReadOnly) {
      setError('Official Tax Invoices can only be modified and issued by the Finance Team.');
      return;
    }
    if (docType === 'invoice' && !isFinance) {
      setError('Access Denied: Only Finance team members can create or issue Tax Invoices.');
      return;
    }
    if (!customerName.trim() && !companyName.trim()) {
      setError('Please provide a Customer Name or Company Name.');
      return;
    }
    try {
      setSaving(true);
      setError('');
      const payload = buildDocPayload();
      const docId = initialData?.id || initialData?.docId;

      let res;
      if (isEditMode && docId) {
        res = await API.put(`/integrations/waquote/documents/${docId}`, payload);
      } else {
        res = await API.post('/integrations/waquote/documents', payload);
      }

      if (res.data?.ok) {
        setSuccessMsg(res.data.message || (isEditMode ? 'Document updated successfully!' : 'Document generated successfully!'));
        
        // Trigger auto download of the issued/updated PDF
        const issuedDoc = res.data.document || {};
        const finalDocData = {
          ...payload,
          docType,
          doc_type: docType,
          companyId: selectedCompanyId,
          company: activeCompany,
          number: issuedDoc.number || initialData.docNumber || 'DOC',
          customerName,
          companyName,
          phone,
          email,
          address,
          state,
          stateCode,
          gstin,
          preparedBy: preparedBy.trim() || 'Authorized Signatory',
          taxMode,
          subtotal: calc.taxableAmount,
          cgst: calc.cgstTotal,
          sgst: calc.sgstTotal,
          igst: calc.igstTotal,
          roundOff: calc.roundOff,
          grandTotal: calc.grandTotal,
          lineItems,
          terms,
          issueDateFormatted: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
          validTillFormatted: new Date(Date.now() + 7 * 86400000).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
        };
        if (docType === 'proforma') {
          generateProformaPdf(finalDocData, true);
        } else if (docType === 'invoice') {
          generateTaxInvoicePdf(finalDocData, true);
        } else {
          generateQuotationPdf(finalDocData, true);
        }

        PingoPopupService.triggerStatusUpdate({
          module: docType === 'invoice' ? 'Tax Invoice' : (docType === 'proforma' ? 'Proforma Invoice' : 'Quotation'),
          status: 'ISSUED',
          reference: finalDocData.number || 'DOC',
          customMessage: `${docType === 'invoice' ? 'Tax Invoice' : (docType === 'proforma' ? 'Proforma Invoice' : 'Quotation')} ${finalDocData.number} issued successfully!`
        });

        if (onSuccess) {
          onSuccess(res.data.document);
        }

        setTimeout(() => {
          onClose();
        }, 1400);
      }
    } catch (err) {
      console.error('Failed to save document:', err);
      if (err.response?.status === 409) {
        setError(err.response.data?.detail || 'An existing quotation already exists for this lead.');
        setShowDuplicateConflict(true);
      } else {
        setError(err.response?.data?.detail || (isEditMode ? 'Failed to update document.' : 'Failed to save and issue document.'));
      }
    } finally {
      setSaving(false);
    }
  };

  const handleForceCreateNew = async () => {
    setAllowDuplicateIntent(true);
    setShowDuplicateConflict(false);
    setError('');
    try {
      setSaving(true);
      const payload = buildDocPayload(true);
      const res = await API.post('/integrations/waquote/documents', payload);
      if (res.data?.ok) {
        setSuccessMsg(res.data.message || 'New quotation revision created successfully!');
        const issuedDoc = res.data.document || {};
        const finalDocData = {
          ...payload,
          docType,
          companyId: selectedCompanyId,
          company: activeCompany,
          number: issuedDoc.number || 'DOC',
          customerName,
          companyName,
          phone,
          email,
          address,
          state,
          stateCode,
          gstin,
          preparedBy: preparedBy.trim() || 'Authorized Signatory',
          taxMode,
          subtotal: calc.taxableAmount,
          cgst: calc.cgstTotal,
          sgst: calc.sgstTotal,
          igst: calc.igstTotal,
          roundOff: calc.roundOff,
          grandTotal: calc.grandTotal,
          lineItems,
          terms
        };
        generateQuotationPdf(finalDocData, true);
        if (onSuccess) onSuccess(res.data.document);
        setTimeout(() => onClose(), 1400);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save new quotation revision.');
    } finally {
      setSaving(false);
    }
  };


  return (
    <div className="quote-modal-overlay">
      <div className="quote-modal-container">
        {/* Header */}
        <div className="quote-modal-header">
          <div className="quote-modal-header-left">
            <div style={{
              background: 'rgba(255, 255, 255, 0.2)',
              borderRadius: '10px',
              padding: '2px 6px',
              display: 'flex',
              alignItems: 'flex-end',
              justifyContent: 'center'
            }}>
              <PingoMascot
                pose={docType === 'tax_invoice' || docType === 'proforma' ? 'celebrate' : 'point-right'}
                height={42}
                withShadow={false}
              />
            </div>
            <div>
              <h3>{isEditMode ? `Edit ${docType.toUpperCase()}` : 'Billing & Quotation Studio'}</h3>
              <div style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.85)' }}>
                {isEditMode
                  ? (initialData.docNumber ? `Document #${initialData.docNumber}` : 'Updating existing document')
                  : `${COMPANY_DEFAULTS.legalName} • GSTIN: ${COMPANY_DEFAULTS.gstin}`}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div className="quote-type-toggle">
              <button 
                type="button" 
                onClick={() => handleTypeChange('quotation')}
                className={`quote-type-btn ${docType === 'quotation' ? 'active' : ''}`}
                disabled={isReadOnly}
              >
                Quotation
              </button>
              <button 
                type="button" 
                onClick={() => handleTypeChange('proforma')}
                className={`quote-type-btn ${docType === 'proforma' ? 'active' : ''}`}
                disabled={isReadOnly}
              >
                Proforma Invoice
              </button>
              {isFinance ? (
                <button 
                  type="button" 
                  onClick={() => handleTypeChange('invoice')}
                  className={`quote-type-btn ${docType === 'invoice' ? 'active' : ''}`}
                >
                  Tax Invoice
                </button>
              ) : (
                docType === 'invoice' && (
                  <button 
                    type="button" 
                    className="quote-type-btn active"
                    disabled
                    title="Tax Invoices are issued exclusively by Finance"
                    style={{ opacity: 0.9, cursor: 'default' }}
                  >
                    Tax Invoice (View Only)
                  </button>
                )
              )}
            </div>
            <button 
              type="button" 
              onClick={onClose} 
              style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}
            >
              <X size={22} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="quote-modal-body">
          {/* Read-Only Banner for non-Finance users viewing issued Tax Invoice */}
          {isReadOnly && (
            <div style={{
              background: '#eff6ff',
              border: '1px solid #bfdbfe',
              color: '#1e40af',
              padding: '12px 16px',
              borderRadius: '8px',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.86rem',
              fontWeight: 600
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertCircle size={18} className="text-blue-600" />
                <span>Official Statutory Tax Invoice (Issued by Finance Team) &mdash; View Mode</span>
              </div>
              <span style={{ fontSize: '0.75rem', background: '#dbeafe', padding: '3px 8px', borderRadius: '6px' }}>
                View & Download Only
              </span>
            </div>
          )}

          {error && (
            <div style={{
              background: '#fef2f2',
              border: '1px solid #fecaca',
              color: '#b91c1c',
              padding: '12px 14px',
              borderRadius: '8px',
              marginBottom: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              fontSize: '0.86rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertCircle size={16} /> <span>{error}</span>
              </div>
              {showDuplicateConflict && (
                <div style={{ marginTop: '4px', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={handleForceCreateNew}
                    className="btn btn-primary"
                    style={{ fontSize: '0.78rem', padding: '5px 12px', backgroundColor: '#dc2626', borderColor: '#b91c1c' }}
                  >
                    Confirm & Create New Revision Anyway
                  </button>
                  <button
                    type="button"
                    onClick={() => { setShowDuplicateConflict(false); setError(''); }}
                    className="btn btn-outline"
                    style={{ fontSize: '0.78rem', padding: '5px 10px' }}
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          )}

          {successMsg && (
            <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#15803d', padding: '10px 14px', borderRadius: '8px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.86rem' }}>
              <Check size={16} /> {successMsg}
            </div>
          )}

          {/* Section 0: Company of Record (Issuer) — WAHRMS vs CHN TECH */}
          <div style={{
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            padding: '16px 18px',
            marginBottom: '20px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 800, color: '#334155', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Building2 size={16} style={{ color: '#dc2626' }} /> COMPANY OF RECORD (ISSUER)
              </label>
              <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>
                2 Quote Types / Companies Available
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              {/* Real Company Logo Thumbnail Matching Selected Quote Type */}
              <div style={{
                height: '42px',
                minWidth: '95px',
                padding: '4px 8px',
                backgroundColor: '#ffffff',
                border: '1px solid #cbd5e1',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                overflow: 'hidden'
              }}>
                <img
                  src={selectedCompanyId === 'chn-tech' ? CHN_LOGO_BASE64 : WAHRMS_LOGO_BASE64}
                  alt={selectedCompanyId === 'chn-tech' ? 'CHN Technologies Logo' : 'WA!HRMS Logo'}
                  style={{ maxHeight: '34px', maxWidth: '88px', width: 'auto', height: 'auto', objectFit: 'contain' }}
                />
              </div>

              {/* Company Selector Dropdown */}
              <select
                value={selectedCompanyId}
                onChange={(e) => handleCompanyChange(e.target.value)}
                style={{
                  flex: 1,
                  minWidth: '280px',
                  padding: '9px 12px',
                  fontSize: '0.86rem',
                  fontWeight: 700,
                  color: '#0f172a',
                  backgroundColor: '#ffffff',
                  border: '1.5px solid #cbd5e1',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  outline: 'none'
                }}
              >
                {COMPANIES.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.displayName}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ marginTop: '8px', display: 'flex', gap: '14px', flexWrap: 'wrap', fontSize: '0.76rem', color: '#64748b' }}>
              <span>GSTIN: <strong style={{ color: '#0f172a', fontFamily: 'monospace' }}>{activeCompany.gstin}</strong></span>
              <span>PAN: <strong style={{ color: '#0f172a', fontFamily: 'monospace' }}>{activeCompany.pan}</strong></span>
              <span>Prefix: <strong style={{ color: '#0f172a' }}>{selectedCompanyId === 'wahrms' ? 'CHN/QT/ (WAHRMS)' : 'CHN/QT/ (CHN TECH)'}</strong></span>
              <span>Category: <strong style={{ color: '#0f766e' }}>{selectedCompanyId === 'chn-tech' ? 'Biometric & Hardware' : 'WAHRMS Software'}</strong></span>
            </div>
          </div>

          {/* Section 1: Customer Details */}
          <div className="quote-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
              <h4 className="quote-section-title" style={{ margin: 0 }}>
                <User size={16} /> Customer & Billing Information
              </h4>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                {initialData.leadId && (
                  <span style={{ fontSize: '0.72rem', backgroundColor: '#e0e7ff', color: '#4338ca', padding: '3px 9px', borderRadius: '12px', fontWeight: '700', border: '1px solid #c7d2fe' }}>
                    CRM Lead #{initialData.leadId}
                  </span>
                )}
                {initialData.customerId && (
                  <span style={{ fontSize: '0.72rem', backgroundColor: '#dcfce7', color: '#15803d', padding: '3px 9px', borderRadius: '12px', fontWeight: '700', border: '1px solid #bbf7d0' }}>
                    Customer #{initialData.customerId}
                  </span>
                )}
              </div>
            </div>
            <div className="quote-form-grid">
              <div className="quote-field">
                <label>Contact Person *</label>
                <input 
                  type="text" 
                  value={customerName} 
                  onChange={(e) => setCustomerName(e.target.value)} 
                  placeholder="e.g. Rajesh Kumar" 
                />
              </div>
              <div className="quote-field">
                <label>Company / Organization</label>
                <input 
                  type="text" 
                  value={companyName} 
                  onChange={(e) => setCompanyName(e.target.value)} 
                  placeholder="e.g. Acme Tech Solutions" 
                />
              </div>
              <div className="quote-field">
                <label>Phone Number</label>
                <input 
                  type="text" 
                  value={phone} 
                  onChange={(e) => setPhone(e.target.value)} 
                  placeholder="e.g. 98844 50030" 
                />
              </div>
              <div className="quote-field">
                <label>Email Address</label>
                <input 
                  type="email" 
                  value={email} 
                  onChange={(e) => setEmail(e.target.value)} 
                  placeholder="e.g. client@example.com" 
                />
              </div>
              <div className="quote-field" style={{ gridColumn: 'span 2' }}>
                <label>Billing Address</label>
                <input 
                  type="text" 
                  value={address} 
                  onChange={(e) => setAddress(e.target.value)} 
                  placeholder="Street address, locality, city" 
                />
              </div>
              <div className="quote-field">
                <label>State & Code ({stateCode})</label>
                <select value={state} onChange={(e) => setState(e.target.value)}>
                  {INDIAN_STATES.map(s => (
                    <option key={s.code} value={s.name}>
                      {s.name} ({s.code}) {s.code === '33' ? '• Intra-State (CGST+SGST)' : '• Inter-State (IGST)'}
                    </option>
                  ))}
                </select>
              </div>
              <div className="quote-field">
                <label>Customer GSTIN</label>
                <input 
                  type="text" 
                  value={gstin} 
                  onChange={(e) => setGstin(e.target.value.toUpperCase())} 
                  placeholder="e.g. 33AAAAA0000A1Z5" 
                />
              </div>
              <div className="quote-field">
                <label>Prepared By (Staff / Rep Name)</label>
                <input 
                  type="text" 
                  value={preparedBy} 
                  onChange={(e) => setPreparedBy(e.target.value)} 
                  placeholder="e.g. Ketziaya or Your Name" 
                />
              </div>
            </div>
          </div>

          {/* Section 2: Product & Package Selection */}
          <div className="quote-section wahrms-bundle-section">
            <div className="wahrms-bundle-header">
              <div>
                <h4 className="quote-section-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Layers size={17} style={{ color: '#0f766e' }} /> {productCategory === 'biometric' ? 'Biometric Hardware Packages' : 'Product & Package Selection'}
                </h4>
                <p className="wahrms-bundle-subtitle">
                  {productCategory === 'biometric'
                    ? 'Select your Biometric Hardware configuration for CHN Technologies.'
                    : 'Select your package: HR + ATM, HR + ATM + Payroll, or HR + Payroll.'}
                </p>
              </div>
              {selectedBundle && (
                <button
                  type="button"
                  onClick={handleClearBundle}
                  className="wahrms-clear-bundle-btn"
                  title="Deselect package and preserve custom items"
                >
                  <X size={13} /> Clear Package
                </button>
              )}
            </div>

            {bundlesError && (
              <div className="wahrms-bundle-alert">
                <AlertCircle size={15} />
                <span>{bundlesError}</span>
              </div>
            )}

            <div className="wahrms-bundle-cards-grid">
              {bundles
                .filter(b => {
                  const bCat = (b.category || 'WAHRMS').toLowerCase();
                  if (productCategory === 'biometric') {
                    return bCat === 'biometric' || ['bio_standard', 'bio_atm', 'bio_enterprise'].includes(b.bundleCode || b.bundle_code);
                  }
                  return ['hr_atm', 'hr_atm_payroll', 'hr_payroll'].includes(b.bundleCode || b.bundle_code);
                })
                .sort((a, b) => {
                  const order = productCategory === 'biometric'
                    ? ['bio_standard', 'bio_atm', 'bio_enterprise']
                    : ['hr_atm', 'hr_atm_payroll', 'hr_payroll'];
                  const codeA = a.bundleCode || a.bundle_code;
                  const codeB = b.bundleCode || b.bundle_code;
                  return order.indexOf(codeA) - order.indexOf(codeB);
                })
                .map((bundle) => {
                  const bCode = bundle.bundleCode || bundle.bundle_code;
                  const isSelected = selectedBundle === bCode;

                  return (
                    <div
                      key={bCode}
                      className={`wahrms-bundle-card ${isSelected ? 'selected' : ''}`}
                      onClick={() => handleSelectBundle(bundle)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleSelectBundle(bundle);
                        }
                      }}
                    >
                      {bundle.badge && (
                        <div className="wahrms-bundle-badge">
                          {bundle.badge}
                        </div>
                      )}

                      <div className="wahrms-bundle-card-top">
                        <div className="wahrms-bundle-card-header">
                          <h5 className="wahrms-bundle-title">{bundle.name}</h5>
                          <div className={`wahrms-bundle-check-indicator ${isSelected ? 'checked' : ''}`}>
                            {isSelected ? (
                              <Check size={14} strokeWidth={3} />
                            ) : (
                              <span className="wahrms-check-dot" />
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="wahrms-bundle-features">
                        {(bundle.features || []).map((feat, fIdx) => (
                          <div key={fIdx} className="wahrms-bundle-feature-item">
                            <Check size={13} className="wahrms-feature-check" />
                            <span>{feat}</span>
                          </div>
                        ))}
                      </div>

                      <div className="wahrms-bundle-card-footer">
                        <div className={`wahrms-select-pill ${isSelected ? 'active' : ''}`}>
                          {isSelected ? (
                            <>
                              <Check size={13} strokeWidth={3} /> Active Package
                            </>
                          ) : (
                            'Select Package'
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Section 3: Line Items */}

          <div className="quote-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
              <h4 className="quote-section-title" style={{ margin: 0 }}>
                <CreditCard size={16} /> Line Items & Pricing
              </h4>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#0f766e', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  + Add-ons:
                </span>
                {(productCategory === 'biometric' ? BIOMETRIC_ADD_ON_SERVICES : ADD_ON_SERVICES).map((addon, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleAddLine(addon)}
                    className="btn btn-outline"
                    style={{ 
                      fontSize: '0.74rem', 
                      padding: '4px 10px', 
                      color: '#0f766e', 
                      borderColor: '#99f6e4', 
                      backgroundColor: '#f0fdfa',
                      borderRadius: '6px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                    title={`Add ${addon.name} to line items`}
                  >
                    + {addon.name}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table className="quote-items-table">
                <thead>
                  <tr>
                    <th style={{ width: '42%' }}>Item Description</th>
                    <th style={{ width: '12%' }}>HSN/SAC</th>
                    <th style={{ width: '10%' }}>Qty</th>
                    <th style={{ width: '14%' }}>Unit Rate (₹)</th>
                    <th style={{ width: '12%' }}>GST %</th>
                    <th style={{ width: '12%' }}>Total (₹)</th>
                    <th style={{ width: '38px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {lineItems.map((item, idx) => {
                    const lineTot = Math.max(0, (Number(item.qty || 1) * Number(item.rate || 0) - Number(item.discount || 0)) * (1 + Number(item.gstRate || 0.18)));
                    return (
                      <tr key={item.id || idx}>
                        <td>
                          {item.isBundleItem && (
                            <div style={{ marginBottom: '5px' }}>
                              <span className="bundle-item-indicator" title="Included in chosen WAHRMS bundle">
                                <CheckCircle2 size={11} /> Bundle Module
                              </span>
                            </div>
                          )}
                          <textarea 
                            rows={2}
                            value={item.description} 
                            onChange={(e) => handleLineChange(idx, 'description', e.target.value)} 
                            placeholder="Product or service name" 
                            style={{
                              width: '100%',
                              padding: '6px 8px',
                              fontSize: '0.84rem',
                              borderRadius: '6px',
                              border: '1px solid #cbd5e1',
                              lineHeight: '1.35',
                              resize: 'vertical'
                            }}
                          />
                        </td>
                        <td>
                          <input 
                            type="text" 
                            value={item.hsn} 
                            onChange={(e) => handleLineChange(idx, 'hsn', e.target.value)} 
                            placeholder="HSN" 
                          />
                        </td>
                        <td>
                          <input 
                            type="number" 
                            min="1" 
                            value={item.qty} 
                            onChange={(e) => handleLineChange(idx, 'qty', Number(e.target.value))} 
                          />
                        </td>
                        <td>
                          <input 
                            type="number" 
                            min="0" 
                            value={item.rate} 
                            onChange={(e) => handleLineChange(idx, 'rate', Number(e.target.value))} 
                          />
                        </td>
                        <td>
                          <select 
                            value={item.gstRate} 
                            onChange={(e) => handleLineChange(idx, 'gstRate', Number(e.target.value))}
                          >
                            <option value={0}>0%</option>
                            <option value={0.05}>5%</option>
                            <option value={0.12}>12%</option>
                            <option value={0.18}>18%</option>
                            <option value={0.28}>28%</option>
                          </select>
                        </td>
                        <td style={{ fontWeight: 700, textAlign: 'right', paddingRight: '8px', fontSize: '0.86rem', color: '#0f766e' }}>
                          ₹{lineTot.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                        </td>
                        <td>
                          <button 
                            type="button" 
                            onClick={() => handleRemoveLine(idx)}
                            style={{ background: 'none', border: 'none', color: '#dc2626', cursor: 'pointer', padding: '4px' }}
                            title="Remove row"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <button 
              type="button" 
              onClick={() => handleAddLine()}
              className="btn btn-outline"
              style={{ fontSize: '0.8rem', padding: '6px 12px', color: '#0f766e', borderColor: '#99f6e4', backgroundColor: '#f0fdfa', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            >
              <Plus size={14} /> Add Line Item
            </button>
          </div>

          {/* Section 3: Totals & Summary */}
          <div className="quote-totals-container">
            <div>
              <div className="quote-field" style={{ marginBottom: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label style={{ margin: 0, fontWeight: 600 }}>Terms & Conditions</label>
                  {docType === 'quotation' && (
                    <button
                      type="button"
                      onClick={() => setTerms(productCategory === 'biometric' ? DEFAULT_TERMS_BIOMETRIC_QUOTATION : DEFAULT_TERMS_QUOTATION)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#0f766e',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                        fontWeight: 600,
                        textDecoration: 'underline',
                        padding: 0
                      }}
                      title="Reset to official terms and conditions"
                    >
                      Reset to {productCategory === 'biometric' ? 'Official Biometric Terms' : 'Official WAHRMS Terms'}
                    </button>
                  )}
                </div>
                <textarea 
                  rows={8} 
                  value={terms} 
                  onChange={(e) => setTerms(e.target.value)} 
                  style={{ lineHeight: 1.45, fontSize: '0.84rem' }}
                />
              </div>

              {docType === 'proforma' && (
                <div style={{ background: '#fef2f2', border: '1px solid #fee2e2', borderRadius: '10px', padding: '12px', fontSize: '0.82rem', color: '#991b1b' }}>
                  <strong>Bank Account Snapshot:</strong><br />
                  Bank: {COMPANY_DEFAULTS.bank.bankName} • A/C: {COMPANY_DEFAULTS.bank.accountNumber} ({COMPANY_DEFAULTS.bank.accountType}) • IFSC: {COMPANY_DEFAULTS.bank.ifsc}
                </div>
              )}
            </div>

            <div className="quote-totals-card">
              <div className="quote-total-row">
                <span>Taxable Subtotal:</span>
                <strong>₹ {calc.taxableAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong>
              </div>

              {taxMode === 'intra' ? (
                <>
                  <div className="quote-total-row">
                    <span>CGST (Tamil Nadu):</span>
                    <span>₹ {calc.cgstTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="quote-total-row">
                    <span>SGST (Tamil Nadu):</span>
                    <span>₹ {calc.sgstTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                </>
              ) : (
                <div className="quote-total-row">
                  <span>IGST (Inter-State):</span>
                  <span>₹ {calc.igstTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </div>
              )}

              <div className="quote-total-row">
                <span>Round Off:</span>
                <span>₹ {calc.roundOff.toFixed(2)}</span>
              </div>

              <div className="quote-total-row grand">
                <span>Grand Total:</span>
                <span>₹ {calc.grandTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
              </div>

              <div style={{ fontSize: '0.78rem', color: '#0f766e', fontWeight: 600, marginTop: '8px', fontStyle: 'italic', lineHeight: '1.4' }}>
                {numberToIndianWords(calc.grandTotal)}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="quote-modal-footer">
          <div style={{ fontSize: '0.82rem', color: '#64748b' }}>
            Tax Engine: <strong>{taxMode === 'intra' ? 'Intra-State (CGST 50% + SGST 50%)' : 'Inter-State (IGST 100%)'}</strong>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button 
              type="button" 
              onClick={onClose} 
              className="btn btn-secondary"
              disabled={saving}
            >
              Cancel
            </button>
            <button 
              type="button" 
              onClick={handleDownloadPdf} 
              className="btn btn-outline"
              style={{
                color: docType === 'invoice' ? '#1e40af' : '#0f766e',
                borderColor: docType === 'invoice' ? '#93c5fd' : '#0f766e',
                backgroundColor: docType === 'invoice' ? '#eff6ff' : '#f0fdfa',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <Download size={15} /> {docType === 'invoice' ? 'Download Tax Invoice' : (docType === 'proforma' ? 'Download Proforma' : 'Download Quotation')}
            </button>
            {!isReadOnly && (
              <button 
                type="button" 
                onClick={handleSaveAndIssue} 
                className="btn btn-primary"
                style={{ backgroundColor: docType === 'invoice' ? '#1d4ed8' : '#0f766e', borderColor: docType === 'invoice' ? '#1d4ed8' : '#0f766e', display: 'flex', alignItems: 'center', gap: '6px' }}
                disabled={saving}
              >
                <Check size={16} /> {saving ? (isEditMode ? 'Saving Changes...' : 'Issuing...') : (isEditMode ? 'Save & Update' : `Issue ${docType === 'invoice' ? 'Tax Invoice' : docType.toUpperCase()}`)}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
