import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { formatDateDDMMYYYY } from '../../utils/dateUtils';
import PingoPopupService from '../../services/pingoPopupService';
import './Workflow.css';
import {
  CreditCard,
  CheckCircle2,
  Clock,
  AlertCircle,
  Search,
  RefreshCw,
  Eye,
  Check,
  X,
  FileText,
  DollarSign,
  Building2,
  User,
  ShieldCheck,
  ArrowRight,
  Download
} from 'lucide-react';


const formatINR = (val) => {
  if (val === null || val === undefined || isNaN(val)) return '₹0';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(val);
};

const FinanceQueuePage = () => {
  const { user } = useAuth();
  const [handoffs, setHandoffs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all'); // all, PAYMENT_PENDING, PAID
  const [searchTerm, setSearchTerm] = useState('');

  // Payment Confirmation Modal
  const [confirmModalDoc, setConfirmModalDoc] = useState(null);
  const [confirmForm, setConfirmForm] = useState({
    paid_amount: '',
    payment_mode: 'Bank Transfer / NEFT',
    bank_reference: '',
    bank_name: 'HDFC Bank',
    invoice_number: '',
    internal_finance_notes: ''
  });
  const [confirming, setConfirming] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  const fetchHandoffs = async () => {
    try {
      setLoading(true);
      const params = {};
      if (activeTab !== 'all') params.status = activeTab;
      if (searchTerm.trim()) params.search = searchTerm.trim();

      const res = await API.get('/workflow/finance/handoffs', { params });
      setHandoffs(res.data || []);
    } catch (err) {
      console.error('Failed to load finance handoffs', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHandoffs();
  }, [activeTab]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchHandoffs();
  };

  const handleOpenConfirmModal = (doc) => {
    setConfirmModalDoc(doc);
    setConfirmForm({
      paid_amount: doc.final_amount,
      payment_mode: 'Bank Transfer / NEFT',
      bank_reference: '',
      bank_name: 'HDFC Bank',
      invoice_number: `CHN/INV/${new Date().getFullYear().toString().slice(-2)}/${String(doc.id).padStart(4, '0')}`,
      internal_finance_notes: ''
    });
  };

  const handleConfirmPayment = async (e) => {
    e.preventDefault();
    if (!confirmModalDoc) return;

    try {
      setConfirming(true);
      await API.post(`/workflow/finance/handoffs/${confirmModalDoc.id}/confirm-payment`, {
        paid_amount: parseFloat(confirmForm.paid_amount) || confirmModalDoc.final_amount,
        payment_mode: confirmForm.payment_mode,
        bank_reference: confirmForm.bank_reference,
        bank_name: confirmForm.bank_name,
        invoice_number: confirmForm.invoice_number,
        internal_finance_notes: confirmForm.internal_finance_notes
      });

      setToastMessage(`Payment of ${formatINR(confirmForm.paid_amount)} confirmed! Deal marked PAID and Support Onboarding created.`);
      setTimeout(() => setToastMessage(null), 5000);
      PingoPopupService.triggerStatusUpdate({
        module: 'Finance',
        status: 'PAID',
        reference: `Handoff #${confirmModalDoc.id}`,
        customMessage: `Payment of ${formatINR(confirmForm.paid_amount)} confirmed! Deal marked PAID.`
      });
      setConfirmModalDoc(null);
      fetchHandoffs();
    } catch (err) {
      alert('Error confirming payment: ' + (err.response?.data?.detail || err.message));
    } finally {
      setConfirming(false);
    }
  };

  const handleDownloadInvoice = async (item) => {
    try {
      let endpoint = `/workflow/finance/handoffs/${item.id}/download-invoice`;
      if (item.invoice_url) {
        endpoint = item.invoice_url.replace(/^\/api/, '');
      } else if (item.id) {
        endpoint = `/workflow/finance/handoffs/${item.id}/download-invoice`;
      } else if (item.lead_id) {
        endpoint = `/leads/${item.lead_id}/download-invoice`;
      } else if (item.invoice_number) {
        endpoint = `/integrations/waquote/invoices/${encodeURIComponent(item.invoice_number)}/download`;
      } else {
        alert('Invoice details not found for this record.');
        return;
      }
      const response = await API.get(endpoint, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const cleanNum = (item.invoice_number || `INV-${item.id}`).replace(/[\\/]/g, '-').replace(/[^a-zA-Z0-9-_]/g, '');
      link.download = `Tax_Invoice_${cleanNum}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      PingoPopupService.triggerDownloadSuccess({
        docType: 'Tax Invoice',
        reference: cleanNum,
        customMessage: `Tax Invoice ${cleanNum} downloaded successfully!`
      });
    } catch (err) {
      console.error('Failed to download tax invoice', err);
      alert('Error downloading tax invoice: ' + (err.response?.data?.detail || err.message));
    }
  };


  // KPI Calculations
  const pendingCount = handoffs.filter((h) => h.status === 'PAYMENT_PENDING').length;
  const pendingAmount = handoffs.filter((h) => h.status === 'PAYMENT_PENDING').reduce((acc, h) => acc + (h.final_amount || 0), 0);
  const paidCount = handoffs.filter((h) => h.status === 'PAID').length;
  const paidAmount = handoffs.filter((h) => h.status === 'PAID').reduce((acc, h) => acc + (h.paid_amount || h.final_amount || 0), 0);

  const isFinanceOrAdmin = user?.role === 'ADMIN' || user?.role === 'FINANCE' || user?.role === 'MANAGER';

  return (
    <div className="workflow-page">
      {/* Toast Alert */}
      {toastMessage && (
        <div style={{
          position: 'fixed',
          top: '20px',
          right: '20px',
          zIndex: 2000,
          background: '#ecfdf5',
          border: '1px solid #10b981',
          color: '#065f46',
          borderRadius: '10px',
          padding: '14px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)'
        }}>
          <CheckCircle2 size={20} className="text-emerald-600" />
          <span style={{ fontSize: '0.88rem', fontWeight: 600 }}>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="workflow-header">
        <div>
          <h1 className="workflow-header-title">
            <CreditCard size={30} className="text-emerald-600" />
            Finance & Payment Verification Queue
          </h1>
          <p className="workflow-subtitle">
            Sales &rarr; Finance Handoff: Verify received customer payments, generate tax invoices, and authorize Support onboarding.
          </p>
        </div>
        <button
          type="button"
          onClick={fetchHandoffs}
          className="btn btn-secondary flex items-center gap-2"
          disabled={loading}
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* KPI Cards */}
      <div className="workflow-kpi-grid">
        <div className="workflow-kpi-card">
          <div className="workflow-kpi-icon" style={{ backgroundColor: '#fef3c7', color: '#b45309' }}>
            <Clock size={24} />
          </div>
          <div>
            <div className="workflow-kpi-label">Pending Verification</div>
            <div className="workflow-kpi-value text-amber-600">{pendingCount}</div>
            <div className="workflow-kpi-sub">Total: {formatINR(pendingAmount)}</div>
          </div>
        </div>

        <div className="workflow-kpi-card">
          <div className="workflow-kpi-icon" style={{ backgroundColor: '#dcfce7', color: '#15803d' }}>
            <CheckCircle2 size={24} />
          </div>
          <div>
            <div className="workflow-kpi-label">Confirmed & Paid</div>
            <div className="workflow-kpi-value text-emerald-700">{paidCount}</div>
            <div className="workflow-kpi-sub">Total: {formatINR(paidAmount)}</div>
          </div>
        </div>

        <div className="workflow-kpi-card">
          <div className="workflow-kpi-icon" style={{ backgroundColor: '#eff6ff', color: '#2563eb' }}>
            <DollarSign size={24} />
          </div>
          <div>
            <div className="workflow-kpi-label">Total Verified Revenue</div>
            <div className="workflow-kpi-value text-blue-700">{formatINR(paidAmount)}</div>
            <div className="workflow-kpi-sub">Across closed deals</div>
          </div>
        </div>
      </div>

      {/* Main Content Card */}
      <div className="workflow-main-card">
        <div className="workflow-toolbar">
          <div className="workflow-tabs">
            <button
              type="button"
              className={`workflow-tab-btn ${activeTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveTab('all')}
            >
              All Records ({handoffs.length})
            </button>
            <button
              type="button"
              className={`workflow-tab-btn ${activeTab === 'PAYMENT_PENDING' ? 'active' : ''}`}
              onClick={() => setActiveTab('PAYMENT_PENDING')}
            >
              Payment Pending ({pendingCount})
            </button>
            <button
              type="button"
              className={`workflow-tab-btn ${activeTab === 'PAID' ? 'active' : ''}`}
              onClick={() => setActiveTab('PAID')}
            >
              Paid & Verified ({paidCount})
            </button>
          </div>

          <form onSubmit={handleSearchSubmit} className="workflow-search-box">
            <Search size={16} className="workflow-search-icon" />
            <input
              type="text"
              placeholder="Search customer, quotation, invoice..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </form>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="workflow-table">
            <thead>
              <tr>
                <th>Deal ID / Date</th>
                <th>Customer & Company</th>
                <th>Sales Rep</th>
                <th>Quotation / Amount</th>
                <th>Payment Status</th>
                <th>Invoice #</th>
                {isFinanceOrAdmin && <th>Sensitive Ref</th>}
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {handoffs.length === 0 ? (
                <tr>
                  <td colSpan={isFinanceOrAdmin ? 8 : 7} style={{ textAlign: 'center', padding: '48px', color: '#94a3b8' }}>
                    <AlertCircle size={32} style={{ margin: '0 auto 8px auto', color: '#cbd5e1' }} />
                    <p style={{ fontWeight: 600, color: '#475569', margin: 0 }}>No Finance records found</p>
                    <small>When Sales marks deals as WON, they will appear here automatically.</small>
                  </td>
                </tr>
              ) : (
                handoffs.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong style={{ color: '#0f172a' }}>Deal #{item.lead_id}</strong>
                      <div style={{ fontSize: '0.74rem', color: '#64748b' }}>
                        {formatDateDDMMYYYY(item.created_at)}
                      </div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: '#1e293b' }}>{item.customer_name}</div>
                      {item.company_name && (
                        <div style={{ fontSize: '0.76rem', color: '#64748b' }}>{item.company_name}</div>
                      )}
                      {item.phone && (
                        <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{item.phone}</div>
                      )}
                    </td>
                    <td>
                      <span style={{ fontWeight: 500, color: '#334155' }}>
                        {item.sales_employee_name || 'Sales Rep'}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, color: '#0f172a' }}>{formatINR(item.final_amount)}</div>
                      <span style={{ fontSize: '0.74rem', color: '#0f766e' }}>
                        {item.quotation_number || 'Quotation'}
                      </span>
                    </td>
                    <td>
                      <span className={`wf-badge ${item.status === 'PAID' ? 'wf-badge-paid' : 'wf-badge-pending'}`}>
                        {item.status === 'PAID' ? 'Paid' : 'Payment Pending'}
                      </span>
                    </td>
                    <td>
                      {item.invoice_number ? (
                        <strong style={{ color: '#0369a1', fontSize: '0.8rem' }}>{item.invoice_number}</strong>
                      ) : (
                        <span style={{ color: '#94a3b8', fontSize: '0.76rem' }}>Pending</span>
                      )}
                    </td>
                    {isFinanceOrAdmin && (
                      <td>
                        <span style={{ fontSize: '0.76rem', color: '#475569', fontFamily: 'monospace' }}>
                          {item.bank_reference || '—'}
                        </span>
                      </td>
                    )}
                      <td style={{ textAlign: 'right' }}>
                        {item.status === 'PAYMENT_PENDING' && isFinanceOrAdmin ? (
                          <button
                            type="button"
                            onClick={() => handleOpenConfirmModal(item)}
                            className="btn btn-sm btn-primary flex items-center gap-1.5"
                            style={{ backgroundColor: '#16a34a', borderColor: '#16a34a', padding: '6px 12px' }}
                          >
                            <Check size={14} />
                            Confirm Payment
                          </button>
                        ) : (
                          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '0.78rem', color: '#16a34a', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              <CheckCircle2 size={14} />
                              Verified
                            </span>
                            <button
                              type="button"
                              onClick={() => handleDownloadInvoice(item)}
                              className="btn btn-sm btn-outline flex items-center gap-1"
                              style={{ color: '#0369a1', borderColor: '#bae6fd', backgroundColor: '#f0f9ff', padding: '4px 8px', fontSize: '0.74rem' }}
                              title="Download Tax Invoice PDF"
                            >
                              <Download size={12} />
                              Tax Invoice
                            </button>
                          </div>
                        )}
                      </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Payment Confirmation Modal */}
      {confirmModalDoc && (
        <div className="wf-modal-overlay" onClick={() => setConfirmModalDoc(null)}>
          <div className="wf-modal" onClick={(e) => e.stopPropagation()}>
            <div className="wf-modal-header">
              <div>
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ShieldCheck size={22} className="text-emerald-600" />
                  Confirm Customer Payment
                </h3>
                <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                  Deal #{confirmModalDoc.lead_id} &bull; {confirmModalDoc.customer_name} ({confirmModalDoc.company_name})
                </span>
              </div>
              <button
                type="button"
                onClick={() => setConfirmModalDoc(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleConfirmPayment}>
              <div className="wf-modal-body">
                <div className="wf-info-banner">
                  <strong>Finance Verification & Invoicing:</strong> Review received payment, customer billing details, and GST information. Confirming this action generates an official <strong>Statutory Tax Invoice</strong>, marks the deal as <strong>PAID</strong>, and hands off to Support Onboarding.
                </div>

                {/* Commercial Review Details */}
                <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '12px 14px', marginBottom: '14px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.8rem' }}>
                  <div><span style={{ color: '#64748b' }}>Customer:</span> <strong>{confirmModalDoc.customer_name}</strong></div>
                  <div><span style={{ color: '#64748b' }}>Company:</span> <strong>{confirmModalDoc.company_name || 'Individual'}</strong></div>
                  <div><span style={{ color: '#64748b' }}>Phone:</span> <strong>{confirmModalDoc.phone || '—'}</strong></div>
                  <div><span style={{ color: '#64748b' }}>Email:</span> <strong>{confirmModalDoc.email || '—'}</strong></div>
                  <div><span style={{ color: '#64748b' }}>Source Quotation:</span> <strong>{confirmModalDoc.quotation_number || '—'}</strong></div>
                  <div><span style={{ color: '#64748b' }}>Billing State:</span> <strong>Tamil Nadu (Code 33)</strong></div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="wf-form-group">
                    <label>Total Deal Amount</label>
                    <input
                      type="text"
                      disabled
                      value={formatINR(confirmModalDoc.final_amount)}
                      style={{ background: '#f8fafc', fontWeight: 700 }}
                    />
                  </div>

                  <div className="wf-form-group">
                    <label>Confirmed Paid Amount (₹)</label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={confirmForm.paid_amount}
                      onChange={(e) => setConfirmForm({ ...confirmForm, paid_amount: e.target.value })}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="wf-form-group">
                    <label>Payment Mode</label>
                    <select
                      value={confirmForm.payment_mode}
                      onChange={(e) => setConfirmForm({ ...confirmForm, payment_mode: e.target.value })}
                    >
                      <option value="Bank Transfer / NEFT">Bank Transfer / NEFT</option>
                      <option value="RTGS / IMPS">RTGS / IMPS</option>
                      <option value="UPI">UPI</option>
                      <option value="Cheque">Cheque</option>
                      <option value="Credit / Debit Card">Credit / Debit Card</option>
                      <option value="Cash">Cash</option>
                    </select>
                  </div>

                  <div className="wf-form-group">
                    <label>Tax Invoice Number</label>
                    <input
                      type="text"
                      required
                      value={confirmForm.invoice_number}
                      onChange={(e) => setConfirmForm({ ...confirmForm, invoice_number: e.target.value })}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="wf-form-group">
                    <label>Bank Reference / UTR / Transaction ID</label>
                    <input
                      type="text"
                      placeholder="e.g. UTR12349876..."
                      value={confirmForm.bank_reference}
                      onChange={(e) => setConfirmForm({ ...confirmForm, bank_reference: e.target.value })}
                    />
                  </div>

                  <div className="wf-form-group">
                    <label>Deposited Bank</label>
                    <input
                      type="text"
                      placeholder="e.g. HDFC Bank, ICICI..."
                      value={confirmForm.bank_name}
                      onChange={(e) => setConfirmForm({ ...confirmForm, bank_name: e.target.value })}
                    />
                  </div>
                </div>

                <div className="wf-form-group">
                  <label>Internal Finance Notes (Protected from Support)</label>
                  <textarea
                    rows="2"
                    placeholder="e.g. Reconciled with corporate statement..."
                    value={confirmForm.internal_finance_notes}
                    onChange={(e) => setConfirmForm({ ...confirmForm, internal_finance_notes: e.target.value })}
                  />
                </div>
              </div>

              <div className="wf-modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setConfirmModalDoc(null)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary flex items-center gap-2"
                  style={{ backgroundColor: '#16a34a', borderColor: '#16a34a' }}
                  disabled={confirming}
                >
                  <Check size={16} />
                  <span>{confirming ? 'Processing...' : 'Confirm & Authorize Onboarding'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default FinanceQueuePage;
