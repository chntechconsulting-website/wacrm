import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useLocation, useNavigate, Navigate } from 'react-router-dom';
import API from '../../services/api';
import './WAQuotesPage.css';
import {
  FileText,
  Receipt,
  CreditCard,
  AlertCircle,
  CheckCircle2,
  Search,
  RefreshCw,
  ExternalLink,
  Eye,
  Download,
  X,
  Filter,
  Calendar,
  Building2,
  User,
  Mail,
  Phone,
  ArrowUpRight,
  Plus,
  Pencil
} from 'lucide-react';
import QuotationModal from '../../components/Billing/QuotationModal';
import { generateBillingPdf, generateQuotationPdf, generateProformaPdf, generateTaxInvoicePdf } from '../../utils/quotationPdf';
import { formatDateDDMMYYYY } from '../../utils/dateUtils';
import { useAuth } from '../../context/AuthContext';
import PingoEmptyState from '../../components/Common/PingoEmptyState';
import PingoPopupService from '../../services/pingoPopupService';


const formatINR = (val) => {
  if (val === null || val === undefined || isNaN(val)) return '₹0';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(val);
};

const formatDocDate = (formatted, raw) => {
  if (formatted && typeof formatted === 'string' && formatted !== '—') return formatted;
  if (!raw) return '—';
  if (typeof raw === 'number' || (!isNaN(raw) && !isNaN(parseFloat(raw)) && /^\d+$/.test(String(raw).trim()))) {
    const num = Number(raw);
    const d = new Date(num > 1e11 ? num : num * 1000);
    return formatDateDDMMYYYY(d);
  }
  return formatDateDDMMYYYY(raw);
};

const WAQuotesPage = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const [summary, setSummary] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [activeTab, setActiveTab] = useState('all'); // all, quotation, proforma, invoice, po
  const [searchQuery, setSearchQuery] = useState('');
  const [paymentFilter, setPaymentFilter] = useState('all'); // all, paid, unpaid, partial
  const [categoryFilter, setCategoryFilter] = useState('all'); // all, wahrms, biometric

  // Modal Detail
  const [selectedDoc, setSelectedDoc] = useState(null);

  // Native Billing & Quotation Studio Modal
  const [showQuoteModal, setShowQuoteModal] = useState(false);
  const [modalInitialData, setModalInitialData] = useState({});

  // Duplicate Prevention & Automatic Client Context State
  const [leadContextLoading, setLeadContextLoading] = useState(false);
  const [duplicatePromptData, setDuplicatePromptData] = useState(null);

  // Action status / Toast feedback
  const [convertingQuoteId, setConvertingQuoteId] = useState(null);
  const [retryingSyncId, setRetryingSyncId] = useState(null);
  const [actionToast, setActionToast] = useState(null);

  const { user } = useAuth();
  const userRole = (user?.role || '').toUpperCase();
  const isFinance = userRole === 'FINANCE';

  const fetchSummary = async () => {
    try {
      setSummaryLoading(true);
      const res = await API.get('/integrations/waquote/summary');
      if (res.data?.ok) {
        setSummary(res.data.metrics || null);
      }
    } catch (err) {
      console.error('Failed to load WA Quote summary', err);
      setSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  };

  const fetchDocuments = async (query = searchQuery) => {
    try {
      setLoading(true);
      setError(null);
      const params = {};
      if (activeTab && activeTab !== 'all') {
        params.doc_type = activeTab;
        params.docType = activeTab;
      }
      if (query && query.trim()) {
        params.search = query.trim();
      }
      if (paymentFilter && paymentFilter !== 'all') {
        params.payment_status = paymentFilter;
        params.paymentStatus = paymentFilter;
      }
      if (categoryFilter && categoryFilter !== 'all') {
        params.product_category = categoryFilter;
        params.productCategory = categoryFilter;
      }

      const res = await API.get('/integrations/waquote/documents', { params });
      if (res.data?.ok) {
        setDocuments(res.data.documents || []);
      } else {
        setDocuments([]);
      }
    } catch (err) {
      console.error('Failed to load documents', err);
      if (err.response?.status === 403) {
        setError('Access restricted: You do not have permission to view sales billing documents.');
      } else {
        setError('Could not load billing documents.');
      }
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  };

  // Re-fetch and clear cache when user/account changes
  useEffect(() => {
    setDocuments([]);
    setSummary(null);
    fetchSummary();
  }, [user?.id, user?.employee_id]);

  const isFirstMount = useRef(true);

  // Instant fetch on tab/status/category switch, debounced fetch on search query typing
  useEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      fetchDocuments(searchQuery);
      return;
    }
    const timer = setTimeout(() => {
      fetchDocuments(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [activeTab, paymentFilter, categoryFilter, searchQuery, user?.id, user?.employee_id]);

  // Handle immediate form submit
  const handleSearchSubmit = (e) => {
    if (e) e.preventDefault();
    fetchDocuments(searchQuery);
  };

  // Check URL params for automated create / lead context trigger
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const leadIdParam = params.get('leadId');
    const createType = params.get('create');

    if (leadIdParam) {
      const fetchLeadQuotationContext = async () => {
        try {
          setLeadContextLoading(true);
          const res = await API.get(`/integrations/waquote/lead-context/${leadIdParam}`);
          if (res.data?.ok) {
            const client = res.data.client || {};
            const existing = res.data.existingQuotations || [];
            if (res.data.hasExistingQuote && existing.length > 0) {
              setDuplicatePromptData({
                client,
                existingQuotes: existing,
                latestQuote: res.data.latestQuotation || existing[0]
              });
            } else {
              setModalInitialData({
                docType: createType || 'quotation',
                customerName: client.customerName || '',
                companyName: client.companyName || '',
                phone: client.phone || '',
                email: client.email || '',
                address: client.address || '',
                state: client.state || 'Tamil Nadu',
                stateCode: client.stateCode || '33',
                gstin: client.gstin || '',
                leadId: client.leadId,
                customerId: client.customerId,
                notes: client.notes || ''
              });
              setShowQuoteModal(true);
            }
          }
        } catch (err) {
          console.error('Failed to load lead context for quotation:', err);
          // Graceful fallback to query params
          setModalInitialData({
            docType: createType || 'quotation',
            customerName: params.get('customerName') || params.get('name') || '',
            companyName: params.get('companyName') || params.get('company') || '',
            phone: params.get('phone') || '',
            email: params.get('email') || '',
            address: params.get('address') || params.get('location') || '',
            state: params.get('state') || 'Tamil Nadu',
            gstin: params.get('gstin') || '',
            leadId: leadIdParam ? Number(leadIdParam) : null,
            notes: params.get('notes') || params.get('leadNotes') || ''
          });
          setShowQuoteModal(true);
        } finally {
          setLeadContextLoading(false);
        }
      };
      fetchLeadQuotationContext();
    } else if (createType) {
      setModalInitialData({
        docType: createType,
        customerName: params.get('customerName') || params.get('name') || '',
        companyName: params.get('companyName') || params.get('company') || '',
        phone: params.get('phone') || '',
        email: params.get('email') || '',
        address: params.get('address') || params.get('location') || '',
        state: params.get('state') || 'Tamil Nadu',
        gstin: params.get('gstin') || '',
        leadId: null,
        notes: params.get('notes') || params.get('leadNotes') || ''
      });
      setShowQuoteModal(true);
    }
  }, [location.search]);

  const handleOpenNewDoc = (type = 'quotation') => {
    setModalInitialData({ docType: type });
    setShowQuoteModal(true);
  };

  const handleEditDoc = (doc) => {
    if (!doc) return;
    const cleanId = String(doc.id || '').replace('local_', '') || null;
    setModalInitialData({
      id: cleanId,
      docId: cleanId,
      docType: (doc.docType || 'quotation').toLowerCase(),
      companyId: doc.companyId || (doc.company?.shortName?.toLowerCase().includes('chn') ? 'chn-tech' : 'wahrms'),
      customerName: doc.customer?.name || doc.customerName || doc.customer_name || '',
      companyName: doc.customer?.companyName || doc.companyName || doc.company_name || '',
      phone: doc.customer?.phone || doc.phone || '',
      email: doc.customer?.email || doc.email || '',
      address: doc.customer?.address?.line1 || doc.address || '',
      state: doc.customer?.address?.state || doc.state || 'Tamil Nadu',
      stateCode: doc.customer?.address?.stateCode || doc.stateCode || '33',
      gstin: doc.customer?.gstin || doc.gstin || '',
      lineItems: doc.lineItems || doc.items || doc.line_items || [],
      terms: doc.termsAndConditions || doc.terms || doc.terms_and_conditions || '',
      notes: doc.notes !== undefined ? doc.notes : '',
      leadId: doc.leadId || doc.lead_id || null,
      customerId: doc.customerId || doc.customer_id || null,
      docNumber: doc.number || doc.doc_number || '',
      selectedBundle: doc.selectedBundle || doc.selected_bundle || null,
      productCategory: doc.productCategory || doc.product_category || 'wahrms',
      preparedBy: doc.preparedBy || doc.prepared_by || ''
    });
    setShowQuoteModal(true);
  };

  const handleDocSuccess = () => {
    if (location.search) {
      navigate('/waquotes', { replace: true });
    }
    fetchSummary();
    fetchDocuments();
  };

  const handleOpenExistingQuote = async (quote) => {
    try {
      const cleanId = String(quote.id || '').replace('local_', '');
      const res = await API.get(`/integrations/waquote/documents/${cleanId}`);
      if (res.data?.ok && res.data.document) {
        setDuplicatePromptData(null);
        handleEditDoc(res.data.document);
        return;
      }
    } catch (err) {
      console.warn('Failed to fetch full quotation doc, using summary:', err);
    }
    setDuplicatePromptData(null);
    handleEditDoc(quote);
  };

  const handleProceedWithNewQuote = () => {
    if (!duplicatePromptData) return;
    const client = duplicatePromptData.client || {};
    setModalInitialData({
      docType: 'quotation',
      customerName: client.customerName || '',
      companyName: client.companyName || '',
      phone: client.phone || '',
      email: client.email || '',
      address: client.address || '',
      state: client.state || 'Tamil Nadu',
      stateCode: client.stateCode || '33',
      gstin: client.gstin || '',
      leadId: client.leadId,
      customerId: client.customerId,
      notes: client.notes || '',
      allowDuplicate: true
    });
    setDuplicatePromptData(null);
    setShowQuoteModal(true);
  };

  const handleCancelDuplicatePrompt = () => {
    setDuplicatePromptData(null);
    if (location.search) {
      navigate('/waquotes', { replace: true });
    }
  };

  const handleGenerateProforma = async (quote) => {
    const cleanId = String(quote.id || '').replace('local_', '');
    try {
      setConvertingQuoteId(quote.id);
      const res = await API.post(`/integrations/waquote/quotations/${cleanId}/generate-proforma`);
      if (res.data?.ok) {
        const msg = res.data.already_exists
          ? `Existing Proforma Invoice #${res.data.document?.number} opened for this quotation.`
          : `Proforma Invoice #${res.data.document?.number} generated successfully!`;
        setActionToast({ type: 'success', text: msg });
        setTimeout(() => setActionToast(null), 5000);
        fetchSummary();
        fetchDocuments();
      } else {
        setActionToast({ type: 'error', text: res.data?.detail || 'Failed to generate proforma.' });
      }
    } catch (err) {
      const errText = err.response?.data?.detail || err.message || 'Error generating proforma invoice';
      setActionToast({ type: 'error', text: errText });
    } finally {
      setConvertingQuoteId(null);
    }
  };

  const handleRetrySync = async (doc) => {
    if (!doc) return;
    const cleanId = String(doc.id || doc.docId || '').replace('local_', '');
    try {
      setRetryingSyncId(doc.id || doc.docId);
      const res = await API.post(`/integrations/waquote/proformas/${cleanId}/sync-destination`);
      if (res.data?.ok) {
        setActionToast({
          type: 'success',
          text: `Destination ERP Sync Successful! (Client ID: ${res.data.external_client_id || 'OK'}, Proforma ID: ${res.data.external_proforma_id || 'OK'})`
        });
        setTimeout(() => setActionToast(null), 6000);
        fetchDocuments();
        if (selectedDoc && (selectedDoc.id === doc.id || selectedDoc.number === doc.number)) {
          setSelectedDoc(prev => ({
            ...prev,
            destinationSyncStatus: 'SYNCED',
            externalClientId: res.data.external_client_id,
            externalProformaId: res.data.external_proforma_id,
            destinationSyncedAt: new Date().toISOString(),
            destinationSyncError: null
          }));
        }
      } else {
        const errorMsg = res.data?.error || res.data?.detail || 'ERP synchronization failed.';
        setActionToast({
          type: 'error',
          text: `ERP Sync Failed: ${errorMsg}`
        });
        fetchDocuments();
      }
    } catch (err) {
      const errText = err.response?.data?.detail || err.response?.data?.error || err.message || 'Error syncing to ERP';
      setActionToast({ type: 'error', text: `ERP Sync Error: ${errText}` });
      fetchDocuments();
    } finally {
      setRetryingSyncId(null);
    }
  };

  const handleDownloadDoc = async (doc) => {
    if (!doc) return;
    if (doc.pdfUrl) {
      window.open(doc.pdfUrl, '_blank');
      return;
    }
    const dType = (doc.docType || doc.doc_type || 'quotation').toLowerCase();
    const docId = doc.id || doc.docId || doc.number;

    // Call dedicated backend download endpoint
    try {
      const cleanId = String(docId).replace('local_', '').trim();
      let endpoint;
      let filenamePrefix;
      if (dType === 'invoice') {
        endpoint = `/integrations/waquote/invoices/${cleanId}/download`;
        filenamePrefix = 'Tax_Invoice';
      } else if (dType === 'proforma') {
        endpoint = `/integrations/waquote/proformas/${cleanId}/download`;
        filenamePrefix = 'Proforma_Invoice';
      } else {
        endpoint = `/integrations/waquote/quotations/${cleanId}/download`;
        filenamePrefix = 'Quotation';
      }

      const response = await API.get(endpoint, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const cleanNum = (doc.number || doc.doc_number || doc.docNumber || 'DOC').replace(/[\\/]/g, '-').replace(/[^a-zA-Z0-9-_]/g, '');
      link.download = `${filenamePrefix}_${cleanNum}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      PingoPopupService.triggerDownloadSuccess({
        docType: dType === 'invoice' ? 'Tax Invoice' : (dType === 'proforma' ? 'Proforma Invoice' : 'Quotation'),
        reference: cleanNum,
        customMessage: `${dType === 'invoice' ? 'Tax Invoice' : (dType === 'proforma' ? 'Proforma Invoice' : 'Quotation')} downloaded successfully!`
      });
      return;
    } catch (err) {
      console.warn('Backend download endpoint call failed, falling back to client-side generator', err);
    }

    // Instant client-side fallback
    const docData = {
      ...doc,
      docType: dType,
      doc_type: dType,
      customerName: doc.customer?.name || doc.customer_name || 'Customer',
      companyName: doc.customer?.companyName || doc.company_name || '',
      phone: doc.customer?.phone || doc.phone || '',
      email: doc.customer?.email || doc.email || '',
      address: doc.customer?.address?.line1 || doc.address || '',
      state: doc.customer?.address?.state || doc.state || 'Tamil Nadu',
      stateCode: doc.customer?.address?.stateCode || doc.state_code || '33',
      gstin: doc.customer?.gstin || doc.gstin || '',
      lineItems: doc.lineItems || doc.line_items || [],
      terms: doc.termsAndConditions || doc.terms_and_conditions || '',
      preparedBy: doc.preparedBy || doc.prepared_by || ''
    };

    if (dType === 'proforma') {
      generateProformaPdf(docData, true);
    } else if (dType === 'invoice') {
      generateTaxInvoicePdf(docData, true);
    } else {
      generateQuotationPdf(docData, true);
    }
    const cleanNum = (doc.number || doc.doc_number || doc.docNumber || 'DOC').replace(/[\\/]/g, '-').replace(/[^a-zA-Z0-9-_]/g, '');
    PingoPopupService.triggerDownloadSuccess({
      docType: dType === 'invoice' ? 'Tax Invoice' : (dType === 'proforma' ? 'Proforma Invoice' : 'Quotation'),
      reference: cleanNum,
      customMessage: `${dType === 'invoice' ? 'Tax Invoice' : (dType === 'proforma' ? 'Proforma Invoice' : 'Quotation')} generated & downloaded successfully!`
    });
  };

  const handleRefresh = () => {
    fetchSummary();
    fetchDocuments();
  };

  const financials = summary?.financials || {};
  const quotations = summary?.quotations || {};
  const proformas = summary?.proformas || {};
  const invoices = summary?.invoices || {};

  return (
    <div className="waquotes-page">
      {/* Header */}
      <div className="waquotes-header">
        <div className="waquotes-title-area">
          <h1>
            <FileText size={28} className="text-blue-600" />
            WA Quotes & Invoices
          </h1>
          <p className="waquotes-subtitle">
            Native CRM workspace for quotations, proformas & invoices.
          </p>
        </div>
        <div className="waquotes-actions">
          <button 
            type="button" 
            onClick={() => handleOpenNewDoc('quotation')} 
            className="btn btn-teal flex items-center gap-1.5"
            style={{ backgroundColor: '#0f766e', color: '#fff', borderColor: '#0f766e', padding: '8px 14px', borderRadius: '8px', fontSize: '0.84rem' }}
          >
            <Plus size={16} />
            New Quotation
          </button>
          <button 
            type="button" 
            onClick={() => handleOpenNewDoc('proforma')} 
            className="btn btn-teal-outline flex items-center gap-1.5"
            style={{ backgroundColor: '#f0fdfa', color: '#0f766e', borderColor: '#99f6e4', padding: '8px 14px', borderRadius: '8px', fontSize: '0.84rem' }}
          >
            <Plus size={16} />
            New Proforma
          </button>
          {isFinance && (
            <button 
              type="button" 
              onClick={() => handleOpenNewDoc('invoice')} 
              className="btn flex items-center gap-1.5"
              style={{ backgroundColor: '#1e40af', color: '#fff', borderColor: '#1e40af', padding: '8px 14px', borderRadius: '8px', fontSize: '0.84rem' }}
              title="Finance Only: Issue official Tax Invoice"
            >
              <Plus size={16} />
              New Tax Invoice
            </button>
          )}
          <button 
            type="button" 
            onClick={handleRefresh} 
            className="btn btn-secondary flex items-center gap-2"
            disabled={loading || summaryLoading}
          >
            <RefreshCw size={16} className={(loading || summaryLoading) ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="waquotes-kpi-grid">
        <div className="waquotes-card">
          <div className="waquotes-card-icon" style={{ backgroundColor: '#eff6ff', color: '#2563eb' }}>
            <CreditCard size={24} />
          </div>
          <div>
            <div className="waquotes-card-label">Total Billed</div>
            <div className="waquotes-card-val">
              {summaryLoading ? '...' : formatINR(financials.totalBilled || 0)}
            </div>
            <div className="waquotes-card-sub">From issued invoices & proformas</div>
          </div>
        </div>

        <div className="waquotes-card">
          <div className="waquotes-card-icon" style={{ backgroundColor: '#fee2e2', color: '#dc2626' }}>
            <AlertCircle size={24} />
          </div>
          <div>
            <div className="waquotes-card-label">Outstanding Balance</div>
            <div className="waquotes-card-val text-red-600">
              {summaryLoading ? '...' : formatINR(financials.totalOutstanding ?? financials.totalUnpaid ?? 0)}
            </div>
            <div className="waquotes-card-sub">Pending customer payments</div>
          </div>
        </div>

        <div className="waquotes-card">
          <div className="waquotes-card-icon" style={{ backgroundColor: '#f0fdf4', color: '#16a34a' }}>
            <CheckCircle2 size={24} />
          </div>
          <div>
            <div className="waquotes-card-label">Total Paid</div>
            <div className="waquotes-card-val text-emerald-600">
              {summaryLoading ? '...' : formatINR(financials.totalPaid || 0)}
            </div>
            <div className="waquotes-card-sub">{financials.collectionRatePercent || 0}% collection rate</div>
          </div>
        </div>

        <div className="waquotes-card">
          <div className="waquotes-card-icon" style={{ backgroundColor: '#eff6ff', color: '#3b82f6' }}>
            <FileText size={24} />
          </div>
          <div>
            <div className="waquotes-card-label">Quotations</div>
            <div className="waquotes-card-val">
              {summaryLoading ? '...' : quotations.totalCount || 0}
            </div>
            <div className="waquotes-card-sub">Value: {formatINR(quotations.totalAmount || 0)}</div>
          </div>
        </div>

        <div className="waquotes-card">
          <div className="waquotes-card-icon" style={{ backgroundColor: '#faf5ff', color: '#9333ea' }}>
            <Receipt size={24} />
          </div>
          <div>
            <div className="waquotes-card-label">Proformas</div>
            <div className="waquotes-card-val">
              {summaryLoading ? '...' : proformas.total || 0}
            </div>
            <div className="waquotes-card-sub">Unpaid: {formatINR(proformas.unpaid?.amount || 0)}</div>
          </div>
        </div>
      </div>

      {/* Main Table Container */}
      <div className="waquotes-table-container">
        {/* Toolbar */}
        <div className="waquotes-toolbar">
          {/* Document Type Tabs */}
          <div className="waquotes-tabs">
            <button
              type="button"
              className={`waquotes-tab ${activeTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveTab('all')}
            >
              All Documents
            </button>
            <button
              type="button"
              className={`waquotes-tab ${activeTab === 'quotation' ? 'active' : ''}`}
              onClick={() => setActiveTab('quotation')}
            >
              Quotations
            </button>
            <button
              type="button"
              className={`waquotes-tab ${activeTab === 'proforma' ? 'active' : ''}`}
              onClick={() => setActiveTab('proforma')}
            >
              Proformas
            </button>
            <button
              type="button"
              className={`waquotes-tab ${activeTab === 'invoice' ? 'active' : ''}`}
              onClick={() => setActiveTab('invoice')}
            >
              Tax Invoices
            </button>
            <button
              type="button"
              className={`waquotes-tab ${activeTab === 'po' ? 'active' : ''}`}
              onClick={() => setActiveTab('po')}
            >
              Purchase Orders
            </button>
          </div>

          {/* Search & Filter Controls */}
          <div className="waquotes-search-filters">
            <form onSubmit={handleSearchSubmit} className="waquotes-search-box" style={{ position: 'relative' }}>
              <Search size={16} />
              <input
                type="text"
                placeholder="Search number, customer, phone..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ paddingRight: searchQuery ? '28px' : '10px' }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  style={{
                    position: 'absolute',
                    right: '8px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: '#94a3b8',
                    padding: 0,
                    display: 'flex',
                    alignItems: 'center'
                  }}
                  title="Clear search"
                >
                  <X size={14} />
                </button>
              )}
            </form>

            <select
              className="waquotes-filter-select"
              value={paymentFilter}
              onChange={(e) => setPaymentFilter(e.target.value)}
            >
              <option value="all">All Payment Statuses</option>
              <option value="paid">Paid</option>
              <option value="unpaid">Unpaid</option>
              <option value="partial">Partial</option>
            </select>

            <select
              className="waquotes-filter-select"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              title="Filter by product category"
            >
              <option value="all">All Categories</option>
              <option value="wahrms">WAHRMS Software</option>
              <option value="biometric">Biometric Hardware</option>
            </select>
          </div>
        </div>

        {/* Action Toast / Feedback Banner */}
        {actionToast && (
          <div style={{
            padding: '12px 24px',
            backgroundColor: actionToast.type === 'error' ? '#fef2f2' : '#f0fdf4',
            color: actionToast.type === 'error' ? '#b91c1c' : '#15803d',
            borderBottom: '1px solid #cbd5e1',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.86rem',
            fontWeight: 600
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {actionToast.type === 'error' ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
              <span>{actionToast.text}</span>
            </div>
            <button
              type="button"
              onClick={() => setActionToast(null)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
            >
              <X size={16} />
            </button>
          </div>
        )}

        {/* Error Banner */}
        {error && (
          <div style={{ padding: '16px 24px', backgroundColor: '#fef2f2', color: '#b91c1c', borderBottom: '1px solid #fee2e2', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {/* Table Content */}
        <div style={{ overflowX: 'auto' }}>
          <table className="waquotes-table">
            <thead>
              <tr>
                <th>Document #</th>
                <th>Type & Category</th>
                <th>Customer / Company</th>
                <th>Issue Date</th>
                <th>Due Date</th>
                <th>Total</th>
                <th>Balance</th>
                <th>Payment</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '48px', color: '#64748b' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                      <RefreshCw size={24} className="animate-spin text-blue-600" />
                      <span>Loading documents from WA Quote...</span>
                    </div>
                  </td>
                </tr>
              ) : documents.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{ padding: '36px 16px', background: '#f8fafc' }}>
                    <PingoEmptyState
                      pose="playful"
                      height={120}
                      title="No Billing Documents Found"
                      description={
                        searchQuery || activeTab !== 'all' || paymentFilter !== 'all' || categoryFilter !== 'all'
                          ? "No documents match your active search or filters."
                          : "Create your first professional Quotation or Proforma Invoice with Pingo!"
                      }
                      actionLabel="Create Quotation"
                      onAction={() => handleOpenCreate('quotation')}
                      actionIcon={Plus}
                      secondaryActionLabel={
                        searchQuery || activeTab !== 'all' || paymentFilter !== 'all' || categoryFilter !== 'all'
                          ? "Clear Filters"
                          : null
                      }
                      onSecondaryAction={() => {
                        setSearchQuery('');
                        setActiveTab('all');
                        setPaymentFilter('all');
                        setCategoryFilter('all');
                      }}
                    />
                  </td>
                </tr>
              ) : (
                documents.map((doc) => {
                  const docType = (doc.docType || 'quotation').toLowerCase();
                  const paymentStatus = (doc.paymentStatus || 'unpaid').toLowerCase();
                  const customerName = doc.customer?.name || 'Walk-in / Unknown';
                  const companyName = doc.customer?.companyName || '';
                  const total = doc.financials?.grandTotal ?? doc.grandTotal ?? 0;
                  const balance = doc.financials?.balance ?? doc.balance ?? (paymentStatus === 'paid' ? 0 : total);
                  const isBiometric = (doc.productCategory || 'wahrms').toLowerCase() === 'biometric';

                  return (
                    <tr key={doc.id || doc.number}>
                      <td>
                        <strong style={{ color: '#0f172a', display: 'block' }}>{doc.number}</strong>
                        <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>{doc.status || 'issued'}</span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-start' }}>
                          <span className={`waquotes-type-badge waquotes-type-${docType}`}>
                            {docType}
                          </span>
                          <span style={{
                            fontSize: '0.67rem',
                            fontWeight: 700,
                            textTransform: 'uppercase',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            backgroundColor: isBiometric ? '#fef3c7' : '#e0f2fe',
                            color: isBiometric ? '#b45309' : '#0369a1',
                            letterSpacing: '0.03em'
                          }}>
                            {isBiometric ? 'Biometric' : 'WAHRMS'}
                          </span>
                          {doc.sourceQuotationNumber && (
                            <span style={{ fontSize: '0.69rem', color: '#0f766e', fontWeight: 600 }}>
                              From {doc.sourceQuotationNumber}
                            </span>
                          )}
                          {docType === 'proforma' && (
                            <span
                              style={{
                                fontSize: '0.66rem',
                                fontWeight: 700,
                                padding: '2px 6px',
                                borderRadius: '4px',
                                backgroundColor:
                                  doc.destinationSyncStatus === 'SYNCED'
                                    ? '#dcfce7'
                                    : doc.destinationSyncStatus === 'FAILED'
                                    ? '#fee2e2'
                                    : doc.destinationSyncStatus === 'NOT_APPLICABLE'
                                    ? '#f1f5f9'
                                    : '#eff6ff',
                                color:
                                  doc.destinationSyncStatus === 'SYNCED'
                                    ? '#15803d'
                                    : doc.destinationSyncStatus === 'FAILED'
                                    ? '#b91c1c'
                                    : doc.destinationSyncStatus === 'NOT_APPLICABLE'
                                    ? '#64748b'
                                    : '#1d4ed8',
                                cursor: doc.destinationSyncStatus === 'FAILED' ? 'pointer' : 'default',
                                border: `1px solid ${
                                  doc.destinationSyncStatus === 'SYNCED'
                                    ? '#bbf7d0'
                                    : doc.destinationSyncStatus === 'FAILED'
                                    ? '#fecaca'
                                    : '#e2e8f0'
                                }`,
                                marginTop: '2px'
                              }}
                              title={
                                doc.destinationSyncStatus === 'SYNCED'
                                  ? `Synced with Destination ERP (Doc ID: ${doc.externalProformaId || doc.externalClientId || 'OK'})`
                                  : doc.destinationSyncStatus === 'FAILED'
                                  ? `Sync Failed: ${doc.destinationSyncError || 'Click to retry'}`
                                  : doc.destinationSyncStatus === 'NOT_APPLICABLE'
                                  ? 'Biometric and mixed documents remain exclusively inside CRM (External Sync Not Applicable)'
                                  : 'Destination ERP Sync Pending'
                              }
                              onClick={() => {
                                if (doc.destinationSyncStatus === 'FAILED') {
                                  handleRetrySync(doc);
                                }
                              }}
                            >
                              {doc.destinationSyncStatus === 'SYNCED'
                                ? '✓ ERP Synced'
                                : doc.destinationSyncStatus === 'FAILED'
                                ? '✕ ERP Sync Failed'
                                : doc.destinationSyncStatus === 'NOT_APPLICABLE'
                                ? '— Internal CRM Only'
                                : '○ ERP Pending'}
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: '#1e293b' }}>{customerName}</div>
                        {companyName && (
                          <div style={{ fontSize: '0.76rem', color: '#64748b' }}>{companyName}</div>
                        )}
                        {doc.customer?.phone && (
                          <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{doc.customer.phone}</div>
                        )}
                      </td>
                      <td>{formatDocDate(doc.issueDateFormatted, doc.issueDate)}</td>
                      <td>{formatDocDate(doc.dueDateFormatted, doc.dueDate)}</td>
                      <td>
                        <strong style={{ color: '#0f172a' }}>{formatINR(total)}</strong>
                      </td>
                      <td>
                        <span style={{ color: balance > 0 ? '#dc2626' : '#16a34a', fontWeight: 600 }}>
                          {formatINR(balance)}
                        </span>
                      </td>
                      <td>
                        <span className={`waquotes-payment-badge waquotes-payment-${paymentStatus}`}>
                          {paymentStatus}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end', alignItems: 'center' }}>
                          {/* Proforma ERP Retry Action */}
                          {docType === 'proforma' && doc.destinationSyncStatus === 'FAILED' && (
                            <button
                              type="button"
                              onClick={() => handleRetrySync(doc)}
                              className="btn btn-sm btn-outline flex items-center gap-1"
                              style={{ color: '#dc2626', borderColor: '#fca5a5', backgroundColor: '#fef2f2' }}
                              title={`Retry ERP synchronization: ${doc.destinationSyncError || 'Failed'}`}
                              disabled={retryingSyncId === doc.id}
                            >
                              <RefreshCw size={12} className={retryingSyncId === doc.id ? "animate-spin" : ""} />
                              Retry ERP
                            </button>
                          )}

                          {/* If Quotation, allow instant one-click Proforma Invoice generation */}
                          {docType === 'quotation' && (
                            <button
                              type="button"
                              onClick={() => handleGenerateProforma(doc)}
                              className="btn btn-sm btn-outline flex items-center gap-1"
                              style={{ color: '#0f766e', borderColor: '#99f6e4', backgroundColor: '#f0fdfa' }}
                              title="Convert this quotation to an independent Proforma Invoice"
                              disabled={convertingQuoteId === doc.id}
                            >
                              {convertingQuoteId === doc.id ? (
                                <RefreshCw size={13} className="animate-spin" />
                              ) : (
                                <ArrowUpRight size={13} />
                              )}
                              To Proforma
                            </button>
                          )}

                          {/* Tax Invoices: only Finance can Edit; Sales can View */}
                          {(docType !== 'invoice' || isFinance) ? (
                            <button
                              type="button"
                              onClick={() => handleEditDoc(doc)}
                              className="btn btn-sm btn-outline flex items-center gap-1"
                              style={{ color: '#2563eb', borderColor: '#bfdbfe', backgroundColor: '#eff6ff' }}
                              title={docType === 'invoice' ? "Edit Tax Invoice (Finance)" : "Edit Document"}
                            >
                              <Pencil size={13} />
                              Edit
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleEditDoc(doc)}
                              className="btn btn-sm btn-outline flex items-center gap-1"
                              style={{ color: '#475569', borderColor: '#cbd5e1', backgroundColor: '#f8fafc' }}
                              title="View Tax Invoice (Read-Only)"
                            >
                              <Eye size={13} />
                              View
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => setSelectedDoc(doc)}
                            className="btn btn-sm btn-outline flex items-center gap-1"
                            title="View Document Details"
                          >
                            <Eye size={13} />
                            Details
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDownloadDoc(doc)}
                            className="btn btn-sm btn-outline flex items-center gap-1"
                            style={{ color: '#0f766e', borderColor: '#99f6e4', backgroundColor: '#f0fdfa' }}
                            title="Download PDF"
                          >
                            <Download size={13} />
                            PDF
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Document Detail Modal */}
      {selectedDoc && (
        <div className="waquotes-modal-overlay" onClick={() => setSelectedDoc(null)}>
          <div className="waquotes-modal" onClick={(e) => e.stopPropagation()}>
            <div className="waquotes-modal-header">
              <div>
                <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {selectedDoc.number}
                  <span className={`waquotes-type-badge waquotes-type-${(selectedDoc.docType || 'quotation').toLowerCase()}`}>
                    {selectedDoc.docType}
                  </span>
                </h3>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  Issued on {formatDocDate(selectedDoc.issueDateFormatted, selectedDoc.issueDate)}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDoc(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={20} />
              </button>
            </div>

            <div className="waquotes-modal-body">
              {/* Customer and Meta Details Grid */}
              <div className="waquotes-detail-grid">
                <div className="waquotes-detail-item">
                  <label>Customer Name</label>
                  <strong>{selectedDoc.customer?.name || 'Walk-in'}</strong>
                </div>
                {selectedDoc.customer?.companyName && (
                  <div className="waquotes-detail-item">
                    <label>Company</label>
                    <strong>{selectedDoc.customer.companyName}</strong>
                  </div>
                )}
                {selectedDoc.customer?.phone && (
                  <div className="waquotes-detail-item">
                    <label>Phone</label>
                    <strong>{selectedDoc.customer.phone}</strong>
                  </div>
                )}
                {selectedDoc.customer?.email && (
                  <div className="waquotes-detail-item">
                    <label>Email</label>
                    <strong>{selectedDoc.customer.email}</strong>
                  </div>
                )}
                <div className="waquotes-detail-item">
                  <label>Payment Status</label>
                  <span className={`waquotes-payment-badge waquotes-payment-${(selectedDoc.paymentStatus || 'unpaid').toLowerCase()}`}>
                    {selectedDoc.paymentStatus || 'unpaid'}
                  </span>
                </div>
                <div className="waquotes-detail-item">
                  <label>Due Date</label>
                  <strong>{formatDocDate(selectedDoc.dueDateFormatted, selectedDoc.dueDate)}</strong>
                </div>
                <div className="waquotes-detail-item">
                  <label>Product Category</label>
                  <strong style={{ textTransform: 'uppercase', color: (selectedDoc.productCategory || 'wahrms').toLowerCase() === 'biometric' ? '#b45309' : '#0369a1' }}>
                    {(selectedDoc.productCategory || 'wahrms').toLowerCase() === 'biometric' ? 'Biometric Hardware' : 'WAHRMS Software'}
                  </strong>
                </div>
                {selectedDoc.sourceQuotationNumber && (
                  <div className="waquotes-detail-item">
                    <label>Source Quotation</label>
                    <strong style={{ color: '#0f766e' }}>{selectedDoc.sourceQuotationNumber}</strong>
                  </div>
                )}
              </div>

              {/* Destination ERP Integration Card for Proformas */}
              {(selectedDoc.docType || selectedDoc.doc_type || '').toLowerCase() === 'proforma' && (
                <div style={{
                  marginBottom: '20px',
                  padding: '14px 18px',
                  backgroundColor: selectedDoc.destinationSyncStatus === 'SYNCED' ? '#f0fdf4' : (selectedDoc.destinationSyncStatus === 'FAILED' ? '#fef2f2' : '#f8fafc'),
                  border: `1px solid ${selectedDoc.destinationSyncStatus === 'SYNCED' ? '#bbf7d0' : (selectedDoc.destinationSyncStatus === 'FAILED' ? '#fecaca' : '#e2e8f0')}`,
                  borderRadius: '10px'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '0.86rem', fontWeight: 700, color: '#1e293b' }}>Destination ERP Synchronization</span>
                      <span style={{
                        fontSize: '0.70rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        backgroundColor: selectedDoc.destinationSyncStatus === 'SYNCED' ? '#dcfce7' : (selectedDoc.destinationSyncStatus === 'FAILED' ? '#fee2e2' : '#f1f5f9'),
                        color: selectedDoc.destinationSyncStatus === 'SYNCED' ? '#15803d' : (selectedDoc.destinationSyncStatus === 'FAILED' ? '#b91c1c' : '#475569')
                      }}>
                        {selectedDoc.destinationSyncStatus || 'PENDING'}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRetrySync(selectedDoc)}
                      disabled={retryingSyncId === (selectedDoc.id || selectedDoc.docId)}
                      className="btn btn-sm btn-outline flex items-center gap-1.5"
                      style={{
                        fontSize: '0.78rem',
                        padding: '5px 12px',
                        backgroundColor: '#ffffff',
                        borderColor: selectedDoc.destinationSyncStatus === 'FAILED' ? '#f87171' : '#cbd5e1',
                        color: selectedDoc.destinationSyncStatus === 'FAILED' ? '#dc2626' : '#1e293b',
                        borderRadius: '6px'
                      }}
                      title="Trigger server-to-server synchronization with destination ERP"
                    >
                      <RefreshCw size={13} className={retryingSyncId === (selectedDoc.id || selectedDoc.docId) ? 'animate-spin' : ''} />
                      {selectedDoc.destinationSyncStatus === 'SYNCED' ? 'Force Re-sync to ERP' : 'Retry ERP Sync'}
                    </button>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px', fontSize: '0.78rem', color: '#475569' }}>
                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.72rem' }}>External Client ID</span>
                      <strong style={{ color: '#0f172a' }}>{selectedDoc.externalClientId || 'Not mapped yet'}</strong>
                    </div>
                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.72rem' }}>External Proforma ID</span>
                      <strong style={{ color: '#0f172a' }}>{selectedDoc.externalProformaId || 'Not mapped yet'}</strong>
                    </div>
                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.72rem' }}>Sync Attempts</span>
                      <strong style={{ color: '#0f172a' }}>{selectedDoc.destinationSyncAttempts || 0}</strong>
                    </div>
                    {selectedDoc.destinationSyncedAt && (
                      <div>
                        <span style={{ color: '#64748b', display: 'block', fontSize: '0.72rem' }}>Last Synced Timestamp</span>
                        <strong style={{ color: '#0f172a' }}>{formatDocDate(null, selectedDoc.destinationSyncedAt)}</strong>
                      </div>
                    )}
                  </div>
                  {selectedDoc.destinationSyncError && (
                    <div style={{
                      marginTop: '10px',
                      fontSize: '0.76rem',
                      color: '#b91c1c',
                      backgroundColor: '#fff5f5',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: '1px solid #fee2e2',
                      wordBreak: 'break-word'
                    }}>
                      <strong>Error: </strong> {selectedDoc.destinationSyncError}
                    </div>
                  )}
                </div>
              )}

              {/* Line Items Table */}
              <h4 style={{ fontSize: '0.92rem', fontWeight: 700, color: '#334155', marginBottom: '12px' }}>
                Line Items
              </h4>
              <table className="waquotes-items-table">
                <thead>
                  <tr>
                    <th>Item Description</th>
                    <th style={{ textAlign: 'center' }}>Qty</th>
                    <th style={{ textAlign: 'right' }}>Rate</th>
                    <th style={{ textAlign: 'right' }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {(selectedDoc.lineItemsSummary || selectedDoc.items || selectedDoc.lineItems || []).map((item, idx) => (
                    <tr key={idx}>
                      <td>
                        <div style={{ fontWeight: 600, whiteSpace: 'pre-line', lineHeight: '1.4' }}>
                          {item.description || item.name || 'Custom Item'}
                        </div>
                        {item.notes && <div style={{ fontSize: '0.74rem', color: '#64748b' }}>{item.notes}</div>}
                      </td>
                      <td style={{ textAlign: 'center' }}>{item.qty ?? item.quantity ?? 1}</td>
                      <td style={{ textAlign: 'right' }}>{formatINR(item.rate ?? 0)}</td>
                      <td style={{ textAlign: 'right', fontWeight: 600 }}>
                        {formatINR(item.total ?? ((item.qty || 1) * (item.rate || 0)))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Totals Summary */}
              <div className="waquotes-totals-box">
                <div className="waquotes-total-row">
                  <span>Subtotal:</span>
                  <span>{formatINR(selectedDoc.financials?.subtotal ?? selectedDoc.subtotal ?? selectedDoc.financials?.grandTotal ?? selectedDoc.grandTotal ?? 0)}</span>
                </div>
                {((selectedDoc.financials?.taxAmount ?? selectedDoc.taxTotal ?? 0) > 0) && (
                  <div className="waquotes-total-row">
                    <span>Tax / GST:</span>
                    <span>{formatINR(selectedDoc.financials?.taxAmount ?? selectedDoc.taxTotal ?? 0)}</span>
                  </div>
                )}
                <div className="waquotes-total-row">
                  <span>Paid:</span>
                  <span style={{ color: '#16a34a' }}>{formatINR(selectedDoc.financials?.totalPaid ?? selectedDoc.amountPaid ?? 0)}</span>
                </div>
                <div className="waquotes-total-row">
                  <span>Balance Due:</span>
                  <span style={{ color: '#dc2626', fontWeight: 600 }}>
                    {formatINR(selectedDoc.financials?.balance ?? selectedDoc.balance ?? ((selectedDoc.paymentStatus || '').toLowerCase() === 'paid' ? 0 : (selectedDoc.financials?.grandTotal ?? selectedDoc.grandTotal ?? 0)))}
                  </span>
                </div>
                <div className="waquotes-total-row grand-total">
                  <span>Grand Total:</span>
                  <span>{formatINR(selectedDoc.financials?.grandTotal ?? selectedDoc.grandTotal ?? 0)}</span>
                </div>
              </div>
            </div>

            <div className="waquotes-modal-footer">
              <button
                type="button"
                onClick={() => {
                  const docToEdit = selectedDoc;
                  setSelectedDoc(null);
                  handleEditDoc(docToEdit);
                }}
                className="btn btn-outline flex items-center gap-1.5"
                style={{ color: '#2563eb', borderColor: '#bfdbfe', backgroundColor: '#eff6ff' }}
              >
                <Pencil size={15} />
                Edit Document
              </button>
              <button
                type="button"
                onClick={() => handleDownloadDoc(selectedDoc)}
                className="btn btn-primary flex items-center gap-2"
                style={{
                  backgroundColor: '#0f766e',
                  borderColor: '#0f766e'
                }}
              >
                <Download size={16} />
                {(selectedDoc.docType || selectedDoc.doc_type) === 'proforma' ? 'Download Proforma' : 'Download Quotation'}
              </button>
              <button
                type="button"
                onClick={() => setSelectedDoc(null)}
                className="btn btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Lead Context Loading Spinner Overlay */}
      {leadContextLoading && (
        <div className="waquotes-modal-overlay" style={{ zIndex: 1060 }}>
          <div style={{
            background: '#ffffff',
            padding: '24px 32px',
            borderRadius: 12,
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            display: 'flex',
            alignItems: 'center',
            gap: 14
          }}>
            <RefreshCw size={22} className="spinning" style={{ color: '#0f766e' }} />
            <div>
              <div style={{ fontWeight: 600, color: '#0f172a', fontSize: 15 }}>Loading Client Details...</div>
              <div style={{ fontSize: 13, color: '#64748b' }}>Fetching authoritative lead and billing context</div>
            </div>
          </div>
        </div>
      )}

      {/* Duplicate Quotation Prevention Modal */}
      {duplicatePromptData && (
        <div className="waquotes-modal-overlay" style={{ zIndex: 1050 }}>
          <div className="waquotes-modal-container" style={{ maxWidth: 540, padding: 0, overflow: 'hidden' }}>
            <div className="waquotes-modal-header" style={{ borderBottom: '1px solid #e2e8f0', padding: '18px 24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 38,
                  height: 38,
                  borderRadius: '50%',
                  backgroundColor: '#fef3c7',
                  color: '#d97706',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  <AlertCircle size={22} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: '#0f172a' }}>
                    Existing Quotation Found
                  </h3>
                  <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
                    A quotation already exists for this lead
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="waquotes-modal-close-btn"
                onClick={handleCancelDuplicatePrompt}
                title="Cancel and close"
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ padding: '20px 24px' }}>
              <p style={{ fontSize: 14, color: '#334155', lineHeight: 1.5, margin: '0 0 16px 0' }}>
                A quotation has already been generated for{' '}
                <strong>{duplicatePromptData.client?.companyName || duplicatePromptData.client?.customerName || 'this client'}</strong>
                {duplicatePromptData.client?.leadId ? ` (Lead #${duplicatePromptData.client.leadId})` : ''}.
                To avoid accidental duplicates, please choose how you would like to proceed:
              </p>

              {/* Summary of Existing Quote */}
              <div style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: '14px 16px',
                marginBottom: 20
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#0f172a' }}>
                    {duplicatePromptData.latestQuote?.number || duplicatePromptData.latestQuote?.doc_number || 'Quotation'}
                  </span>
                  <span style={{
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    padding: '2px 8px',
                    borderRadius: 12,
                    backgroundColor: '#dbeafe',
                    color: '#1d4ed8'
                  }}>
                    {duplicatePromptData.latestQuote?.status || 'Active'}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: '#64748b', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div>
                    <strong>Category:</strong> {duplicatePromptData.latestQuote?.productCategory ? String(duplicatePromptData.latestQuote.productCategory).toUpperCase() : 'WAHRMS'}
                  </div>
                  {duplicatePromptData.latestQuote?.financials?.grandTotal !== undefined && (
                    <div>
                      <strong>Total:</strong> {formatINR(duplicatePromptData.latestQuote.financials.grandTotal)}
                    </div>
                  )}
                  {duplicatePromptData.latestQuote?.date && (
                    <div>
                      <strong>Date:</strong> {formatDateDDMMYYYY(duplicatePromptData.latestQuote.date)}
                    </div>
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => handleOpenExistingQuote(duplicatePromptData.latestQuote)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    width: '100%',
                    padding: '11px 16px',
                    backgroundColor: '#0f766e',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: 6,
                    fontWeight: 600,
                    fontSize: 14,
                    cursor: 'pointer'
                  }}
                >
                  <FileText size={16} />
                  Open Existing Quotation (Recommended)
                </button>

                <button
                  type="button"
                  onClick={handleProceedWithNewQuote}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    width: '100%',
                    padding: '11px 16px',
                    backgroundColor: '#ffffff',
                    color: '#334155',
                    border: '1px solid #cbd5e1',
                    borderRadius: 6,
                    fontWeight: 600,
                    fontSize: 14,
                    cursor: 'pointer'
                  }}
                >
                  <Plus size={16} />
                  Create Another Quotation Intentionally
                </button>

                <button
                  type="button"
                  onClick={handleCancelDuplicatePrompt}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '100%',
                    padding: '9px 16px',
                    backgroundColor: 'transparent',
                    color: '#64748b',
                    border: 'none',
                    fontWeight: 500,
                    fontSize: 13,
                    cursor: 'pointer'
                  }}
                >
                  Cancel & Preserve Lead
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Native Billing & Quotation Studio Modal */}
      <QuotationModal
        isOpen={showQuoteModal}
        onClose={() => {
          setShowQuoteModal(false);
          if (location.search) navigate('/waquotes', { replace: true });
        }}
        initialData={modalInitialData}
        onSuccess={handleDocSuccess}
      />
    </div>
  );
};

export default WAQuotesPage;
