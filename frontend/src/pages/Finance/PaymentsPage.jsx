import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import {
  CreditCard,
  Plus,
  Search,
  Filter,
  CheckCircle,
  Clock,
  AlertTriangle,
  RotateCcw,
  Building2,
  Calendar,
  X,
  ExternalLink,
  Zap,
  ArrowUpRight
} from 'lucide-react';
import { formatDateDDMMYYYY, formatLocalDateTime } from '../../utils/dateUtils';
import PingoEmptyState from '../../components/Common/PingoEmptyState';

const formatINR = (val) => {
  const num = Number(val || 0);
  return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 2 });
};

const PaymentsPage = () => {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [methodFilter, setMethodFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const [customers, setCustomers] = useState([]);
  const [invoices, setInvoices] = useState([]);

  // Modals
  const [showManualModal, setShowManualModal] = useState(false);
  const [showRazorpayModal, setShowRazorpayModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [selectedPayment, setSelectedPayment] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Manual payment form
  const [manualForm, setManualForm] = useState({
    customer_id: '',
    invoice_id: '',
    amount: '',
    payment_method: 'BANK_TRANSFER',
    transaction_reference: '',
    bank_name: 'Axis Bank',
    payment_date: new Date().toISOString().split('T')[0],
    notes: ''
  });

  // Razorpay online payment form
  const [razorpayForm, setRazorpayForm] = useState({
    customer_id: '',
    invoice_id: '',
    amount: '',
    razorpay_payment_id: '',
    razorpay_order_id: '',
    notes: 'Online checkout payment via Razorpay'
  });

  const fetchPayments = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await API.get('/finance/payments', {
        params: {
          status: statusFilter !== 'ALL' ? statusFilter : undefined,
          type: typeFilter !== 'ALL' ? typeFilter : undefined,
          method: methodFilter !== 'ALL' ? methodFilter : undefined,
          search: searchTerm || undefined,
          page,
          limit: 25
        }
      });
      if (res.data) {
        setPayments(res.data.items || []);
        setTotalCount(res.data.total || 0);
      }
    } catch (err) {
      console.error('Failed to load payments:', err);
      setError('Unable to load payments. Please verify permissions or retry.');
    } finally {
      setLoading(false);
    }
  };

  const fetchDependencies = async () => {
    try {
      const [custRes, invRes] = await Promise.all([
        API.get('/customers'),
        API.get('/finance/invoices?status=unpaid&limit=100')
      ]);
      if (custRes.data) setCustomers(custRes.data);
      if (invRes.data?.items) setInvoices(invRes.data.items);
    } catch (e) {
      // Ignore
    }
  };

  useEffect(() => {
    fetchPayments();
  }, [statusFilter, typeFilter, methodFilter, searchTerm, page]);

  useEffect(() => {
    fetchDependencies();
  }, []);

  const handleManualSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      await API.post('/finance/payments/manual', {
        ...manualForm,
        customer_id: manualForm.customer_id ? parseInt(manualForm.customer_id) : undefined,
        invoice_id: manualForm.invoice_id ? parseInt(manualForm.invoice_id) : undefined,
        amount: parseFloat(manualForm.amount)
      });
      setShowManualModal(false);
      fetchPayments();
    } catch (err) {
      alert('Failed to record manual payment: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRazorpaySubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      // Auto-generate realistic Razorpay ID if left blank
      const payId = razorpayForm.razorpay_payment_id || `pay_${Math.random().toString(36).substring(2, 11)}`;
      const ordId = razorpayForm.razorpay_order_id || `order_${Math.random().toString(36).substring(2, 11)}`;

      await API.post('/finance/payments/razorpay/verify', {
        customer_id: razorpayForm.customer_id ? parseInt(razorpayForm.customer_id) : undefined,
        invoice_id: razorpayForm.invoice_id ? parseInt(razorpayForm.invoice_id) : undefined,
        amount: parseFloat(razorpayForm.amount),
        razorpay_payment_id: payId,
        razorpay_order_id: ordId,
        notes: razorpayForm.notes
      });
      setShowRazorpayModal(false);
      fetchPayments();
    } catch (err) {
      alert('Failed to verify Razorpay payment: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page-container" style={{ padding: '24px 32px 60px' }}>
      
      {/* 1. HEADER */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '24px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            backgroundColor: 'rgba(37, 99, 235, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#2563eb'
          }}>
            <CreditCard size={22} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>
              Payment Management
            </h1>
            <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '2px 0 0' }}>
              Online Razorpay & Manual Bank Transfers, UTR Verification & Transaction History
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => {
              setRazorpayForm({
                customer_id: '',
                invoice_id: '',
                amount: '',
                razorpay_payment_id: `pay_${Math.random().toString(36).substring(2, 10)}`,
                razorpay_order_id: `order_${Math.random().toString(36).substring(2, 10)}`,
                notes: 'Razorpay Instant Checkout Settlement'
              });
              setShowRazorpayModal(true);
            }}
            style={{
              padding: '10px 16px',
              borderRadius: '9px',
              backgroundColor: '#0284c7',
              color: '#ffffff',
              border: 'none',
              fontWeight: '700',
              fontSize: '0.86rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer'
            }}
          >
            <Zap size={16} />
            <span>Razorpay Online Payment</span>
          </button>

          <button
            type="button"
            onClick={() => setShowManualModal(true)}
            style={{
              padding: '10px 18px',
              borderRadius: '9px',
              backgroundColor: '#059669',
              color: '#ffffff',
              border: 'none',
              fontWeight: '700',
              fontSize: '0.86rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer'
            }}
          >
            <Plus size={18} />
            <span>Record Manual Payment</span>
          </button>
        </div>
      </div>

      {/* 2. FILTERS */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '14px',
        padding: '14px 18px',
        border: '1px solid #e2e8f0',
        marginBottom: '20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '14px'
      }}>
        {/* Status Filters */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {[
            { id: 'ALL', label: 'All Statuses' },
            { id: 'PAID', label: 'Paid' },
            { id: 'PARTIAL', label: 'Partial' },
            { id: 'PENDING', label: 'Pending' },
            { id: 'REFUNDED', label: 'Refunded' },
            { id: 'FAILED', label: 'Failed' }
          ].map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => { setStatusFilter(tab.id); setPage(1); }}
              style={{
                padding: '7px 14px',
                borderRadius: '8px',
                fontSize: '0.8rem',
                fontWeight: '700',
                border: 'none',
                cursor: 'pointer',
                backgroundColor: statusFilter === tab.id ? '#0f172a' : '#f1f5f9',
                color: statusFilter === tab.id ? '#ffffff' : '#64748b'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Method & Search */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            value={methodFilter}
            onChange={(e) => { setMethodFilter(e.target.value); setPage(1); }}
            style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
          >
            <option value="ALL">All Methods</option>
            <option value="BANK_TRANSFER">Bank Transfer (NEFT/RTGS)</option>
            <option value="RAZORPAY">Razorpay PG</option>
            <option value="UPI">UPI / QR</option>
            <option value="CHEQUE">Cheque</option>
            <option value="CASH">Cash</option>
          </select>

          <div style={{ position: 'relative', minWidth: '240px' }}>
            <Search size={16} color="#94a3b8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              placeholder="Search reference, customer..."
              value={searchTerm}
              onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
              style={{
                width: '100%',
                padding: '8px 12px 8px 36px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                fontSize: '0.82rem'
              }}
            />
          </div>
        </div>
      </div>

      {/* 3. TABLE */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '16px',
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        overflow: 'hidden'
      }}>
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
            <div className="spinner" style={{ margin: '0 auto 12px', width: '32px', height: '32px', border: '3px solid #e2e8f0', borderTopColor: '#2563eb', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            <p style={{ margin: 0, fontWeight: '600', fontSize: '0.9rem' }}>Loading payment transactions...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#dc2626' }}>
            <AlertTriangle size={32} style={{ margin: '0 auto 8px' }} />
            <p style={{ fontWeight: '700' }}>{error}</p>
            <button onClick={fetchPayments} style={{ marginTop: '8px', padding: '6px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', cursor: 'pointer' }}>Retry</button>
          </div>
        ) : payments.length === 0 ? (
          <div style={{ padding: '40px 20px' }}>
            <PingoEmptyState
              title="No Payments Found"
              description="No transactions match your current search and filters."
            />
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #f1f5f9', backgroundColor: '#f8fafc', color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  <th style={{ padding: '12px 16px' }}>Payment #</th>
                  <th style={{ padding: '12px 16px' }}>Customer / Company</th>
                  <th style={{ padding: '12px 16px' }}>Invoice #</th>
                  <th style={{ padding: '12px 16px' }}>Amount</th>
                  <th style={{ padding: '12px 16px' }}>Method</th>
                  <th style={{ padding: '12px 16px' }}>Type</th>
                  <th style={{ padding: '12px 16px' }}>Reference / UTR / Order</th>
                  <th style={{ padding: '12px 16px' }}>Status</th>
                  <th style={{ padding: '12px 16px' }}>Date</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => {
                  const isPaid = p.status === 'PAID';
                  const isRefunded = p.status === 'REFUNDED';
                  const isPartial = p.status === 'PARTIAL';

                  return (
                    <tr
                      key={p.id}
                      style={{ borderBottom: '1px solid #f1f5f9', cursor: 'pointer' }}
                      onClick={() => { setSelectedPayment(p); setShowDetailModal(true); }}
                    >
                      <td style={{ padding: '14px 16px', fontWeight: '800', color: '#2563eb' }}>
                        {p.payment_number}
                      </td>

                      <td style={{ padding: '14px 16px', fontWeight: '700', color: '#0f172a' }}>
                        {p.customer_name}
                      </td>

                      <td style={{ padding: '14px 16px', color: '#475569', fontWeight: '600' }}>
                        {p.invoice_number || 'Direct Payment'}
                      </td>

                      <td style={{ padding: '14px 16px', fontWeight: '800', color: isRefunded ? '#7c3aed' : '#059669' }}>
                        {formatINR(p.amount)}
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <span style={{
                          padding: '3px 8px',
                          borderRadius: '6px',
                          backgroundColor: p.payment_method === 'RAZORPAY' ? '#eff6ff' : '#f8fafc',
                          color: p.payment_method === 'RAZORPAY' ? '#0284c7' : '#334155',
                          fontWeight: '700',
                          fontSize: '0.74rem'
                        }}>
                          {p.payment_method}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px', color: '#64748b', fontSize: '0.78rem', fontWeight: '600' }}>
                        {p.payment_type}
                      </td>

                      <td style={{ padding: '14px 16px', color: '#334155', fontFamily: 'monospace', fontSize: '0.8rem' }}>
                        {p.transaction_reference || p.razorpay_payment_id || '—'}
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <span style={{
                          padding: '4px 9px',
                          borderRadius: '12px',
                          fontSize: '0.72rem',
                          fontWeight: '800',
                          backgroundColor: isPaid ? 'rgba(16, 185, 129, 0.12)' : (isRefunded ? 'rgba(124, 58, 237, 0.12)' : 'rgba(239, 68, 68, 0.12)'),
                          color: isPaid ? '#059669' : (isRefunded ? '#7c3aed' : '#dc2626')
                        }}>
                          {p.status}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px', color: '#64748b', fontSize: '0.78rem' }}>
                        {p.payment_date ? formatDateDDMMYYYY(p.payment_date) : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 4. MANUAL PAYMENT MODAL */}
      {showManualModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            maxWidth: '520px',
            width: '100%',
            padding: '24px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Plus size={20} color="#059669" />
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '800', color: '#0f172a' }}>
                  Record Manual Payment
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowManualModal(false)}
                style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#64748b' }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleManualSubmit}>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  Customer *
                </label>
                <select
                  required
                  value={manualForm.customer_id}
                  onChange={(e) => setManualForm({ ...manualForm, customer_id: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                >
                  <option value="">— Select Customer —</option>
                  {customers.map(c => (
                    <option key={c.id} value={c.id}>{c.company_name} ({c.contact_name})</option>
                  ))}
                </select>
              </div>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  Link to Unpaid Invoice (Optional)
                </label>
                <select
                  value={manualForm.invoice_id}
                  onChange={(e) => {
                    const invId = e.target.value;
                    const inv = invoices.find(i => String(i.id) === String(invId));
                    setManualForm({
                      ...manualForm,
                      invoice_id: invId,
                      amount: inv ? inv.pending_amount : manualForm.amount,
                      customer_id: inv ? inv.customer_id : manualForm.customer_id
                    });
                  }}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                >
                  <option value="">— Standalone Payment / Direct Advance —</option>
                  {invoices.map(inv => (
                    <option key={inv.id} value={inv.id}>
                      {inv.invoice_number} - {inv.company_name} (Due: {formatINR(inv.pending_amount)})
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Amount (INR) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={manualForm.amount}
                    onChange={(e) => setManualForm({ ...manualForm, amount: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.84rem', fontWeight: '700' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Method *</label>
                  <select
                    value={manualForm.payment_method}
                    onChange={(e) => setManualForm({ ...manualForm, payment_method: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                  >
                    <option value="BANK_TRANSFER">Bank Transfer (NEFT/RTGS/IMPS)</option>
                    <option value="UPI">UPI / QR Code</option>
                    <option value="CHEQUE">Cheque / Demand Draft</option>
                    <option value="CASH">Cash</option>
                    <option value="CARD">Credit / Debit Card</option>
                  </select>
                </div>
              </div>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  Transaction Reference / UTR / Cheque # *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. AXIS-UTR-293841 or Cheque 102934"
                  value={manualForm.transaction_reference}
                  onChange={(e) => setManualForm({ ...manualForm, transaction_reference: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Bank Name</label>
                  <input
                    type="text"
                    value={manualForm.bank_name}
                    onChange={(e) => setManualForm({ ...manualForm, bank_name: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Payment Date</label>
                  <input
                    type="date"
                    value={manualForm.payment_date}
                    onChange={(e) => setManualForm({ ...manualForm, payment_date: e.target.value })}
                    style={{ width: '100%', padding: '7px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Finance Notes</label>
                <textarea
                  rows="2"
                  value={manualForm.notes}
                  onChange={(e) => setManualForm({ ...manualForm, notes: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowManualModal(false)}
                  style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{ padding: '8px 18px', borderRadius: '6px', border: 'none', backgroundColor: '#059669', color: '#ffffff', fontWeight: '800', cursor: 'pointer' }}
                >
                  {submitting ? 'Recording...' : 'Record Payment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 5. RAZORPAY ONLINE PAYMENT MODAL */}
      {showRazorpayModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            maxWidth: '520px',
            width: '100%',
            padding: '24px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Zap size={20} color="#0284c7" />
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '800', color: '#0f172a' }}>
                  Razorpay Online Payment Verification
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowRazorpayModal(false)}
                style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#64748b' }}
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '14px' }}>
              Record or simulate an online checkout payment verified through the Razorpay Payment Gateway.
            </p>

            <form onSubmit={handleRazorpaySubmit}>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Customer *</label>
                <select
                  required
                  value={razorpayForm.customer_id}
                  onChange={(e) => setRazorpayForm({ ...razorpayForm, customer_id: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                >
                  <option value="">— Select Customer —</option>
                  {customers.map(c => (
                    <option key={c.id} value={c.id}>{c.company_name} ({c.contact_name})</option>
                  ))}
                </select>
              </div>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Amount (INR) *</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={razorpayForm.amount}
                  onChange={(e) => setRazorpayForm({ ...razorpayForm, amount: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.84rem', fontWeight: '700' }}
                />
              </div>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  Razorpay Payment Reference (pay_*) *
                </label>
                <input
                  type="text"
                  required
                  value={razorpayForm.razorpay_payment_id}
                  onChange={(e) => setRazorpayForm({ ...razorpayForm, razorpay_payment_id: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem', fontFamily: 'monospace' }}
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  Razorpay Order Reference (order_*)
                </label>
                <input
                  type="text"
                  value={razorpayForm.razorpay_order_id}
                  onChange={(e) => setRazorpayForm({ ...razorpayForm, razorpay_order_id: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem', fontFamily: 'monospace' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowRazorpayModal(false)}
                  style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{ padding: '8px 18px', borderRadius: '6px', border: 'none', backgroundColor: '#0284c7', color: '#ffffff', fontWeight: '800', cursor: 'pointer' }}
                >
                  {submitting ? 'Verifying...' : 'Verify & Record Payment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 6. DETAIL DRAWER / MODAL */}
      {showDetailModal && selectedPayment && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            maxWidth: '460px',
            width: '100%',
            padding: '24px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: '800' }}>Payment Receipt Detail</h3>
              <button type="button" onClick={() => setShowDetailModal(false)} style={{ border: 'none', background: 'none', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ fontSize: '0.84rem', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Receipt #:</span>
                <span style={{ fontWeight: '800', color: '#2563eb' }}>{selectedPayment.payment_number}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Customer:</span>
                <span style={{ fontWeight: '700' }}>{selectedPayment.customer_name}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Amount Settled:</span>
                <span style={{ fontWeight: '800', color: '#059669', fontSize: '1rem' }}>{formatINR(selectedPayment.amount)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Method:</span>
                <span style={{ fontWeight: '700' }}>{selectedPayment.payment_method} ({selectedPayment.payment_type})</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Transaction Ref / UTR:</span>
                <span style={{ fontWeight: '700', fontFamily: 'monospace' }}>{selectedPayment.transaction_reference || '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Bank / PG:</span>
                <span>{selectedPayment.bank_name || 'N/A'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Status:</span>
                <span style={{ fontWeight: '800', color: selectedPayment.status === 'PAID' ? '#059669' : '#dc2626' }}>{selectedPayment.status}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Payment Date:</span>
                <span>{selectedPayment.payment_date ? formatDateDDMMYYYY(selectedPayment.payment_date) : '—'}</span>
              </div>
              {selectedPayment.notes && (
                <div style={{ marginTop: '6px', padding: '8px 12px', backgroundColor: '#f8fafc', borderRadius: '6px', color: '#475569', fontSize: '0.78rem' }}>
                  <strong>Notes:</strong> {selectedPayment.notes}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '20px' }}>
              <button
                type="button"
                onClick={() => setShowDetailModal(false)}
                style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', backgroundColor: '#0f172a', color: '#ffffff', fontWeight: '700', cursor: 'pointer' }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default PaymentsPage;
