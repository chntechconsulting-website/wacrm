import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import {
  FileText,
  Plus,
  Search,
  Filter,
  Download,
  CreditCard,
  Eye,
  CheckCircle,
  AlertCircle,
  Clock,
  Building2,
  Calendar,
  X,
  Printer,
  ChevronDown,
  DollarSign
} from 'lucide-react';
import { formatDateDDMMYYYY } from '../../utils/dateUtils';
import PingoEmptyState from '../../components/Common/PingoEmptyState';

const formatINR = (val) => {
  const num = Number(val || 0);
  return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 2 });
};

const InvoicesPage = () => {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Customers list for generator dropdown
  const [customers, setCustomers] = useState([]);

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [invoiceDetail, setInvoiceDetail] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // New Invoice Form State
  const [formData, setFormData] = useState({
    customer_id: '',
    customer_name: '',
    company_name: '',
    phone: '',
    email: '',
    address: 'Chennai, Tamil Nadu',
    state: 'Tamil Nadu',
    state_code: '33',
    gstin: '',
    tax_mode: 'intra',
    due_date: '',
    notes: '',
    line_items: [
      { description: 'WAHRMS Business Solution Subscription (1 Year)', qty: 1, rate: 35000, amount: 35000 }
    ],
    amount_paid: 0,
    payment_method: 'BANK_TRANSFER',
    transaction_reference: '',
    bank_name: 'Axis Bank'
  });

  // Record Payment Form State
  const [paymentForm, setPaymentForm] = useState({
    amount: '',
    payment_method: 'BANK_TRANSFER',
    transaction_reference: '',
    bank_name: 'Axis Bank',
    payment_date: new Date().toISOString().split('T')[0],
    notes: ''
  });

  const fetchInvoices = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await API.get('/finance/invoices', {
        params: {
          status: statusFilter,
          search: searchTerm || undefined,
          page,
          limit: 25
        }
      });
      if (res.data) {
        setInvoices(res.data.items || []);
        setTotalCount(res.data.total || 0);
      }
    } catch (err) {
      console.error('Failed to load invoices:', err);
      setError('Unable to load invoices. Please verify permissions or retry.');
    } finally {
      setLoading(false);
    }
  };

  const fetchCustomers = async () => {
    try {
      const res = await API.get('/customers');
      if (res.data) setCustomers(res.data);
    } catch (e) {
      // Ignore
    }
  };

  useEffect(() => {
    fetchInvoices();
  }, [statusFilter, searchTerm, page]);

  useEffect(() => {
    fetchCustomers();
  }, []);

  const handleCustomerSelect = (custId) => {
    const cust = customers.find(c => String(c.id) === String(custId));
    if (cust) {
      setFormData(prev => ({
        ...prev,
        customer_id: cust.id,
        customer_name: cust.contact_name,
        company_name: cust.company_name,
        phone: cust.phone,
        email: cust.email || '',
        address: cust.location || prev.address
      }));
    }
  };

  const handleLineItemChange = (index, field, value) => {
    const items = [...formData.line_items];
    items[index][field] = value;
    if (field === 'qty' || field === 'rate') {
      const qty = parseFloat(items[index].qty) || 0;
      const rate = parseFloat(items[index].rate) || 0;
      items[index].amount = qty * rate;
    }
    setFormData(prev => ({ ...prev, line_items: items }));
  };

  const addLineItem = () => {
    setFormData(prev => ({
      ...prev,
      line_items: [
        ...prev.line_items,
        { description: 'Add-on Service', qty: 1, rate: 5000, amount: 5000 }
      ]
    }));
  };

  const removeLineItem = (index) => {
    if (formData.line_items.length <= 1) return;
    setFormData(prev => ({
      ...prev,
      line_items: prev.line_items.filter((_, i) => i !== index)
    }));
  };

  // Calculations for preview in modal
  const calcSubtotal = formData.line_items.reduce((sum, item) => sum + (parseFloat(item.amount) || 0), 0);
  const isIntra = formData.state_code === '33';
  const calcCGST = isIntra ? round2(calcSubtotal * 0.09) : 0;
  const calcSGP = isIntra ? round2(calcSubtotal * 0.09) : 0;
  const calcIGST = !isIntra ? round2(calcSubtotal * 0.18) : 0;
  const calcTotalTax = calcCGST + calcSGP + calcIGST;
  const calcGrandTotal = Math.round(calcSubtotal + calcTotalTax);

  function round2(num) {
    return Math.round((num + Number.EPSILON) * 100) / 100;
  }

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      await API.post('/finance/invoices', {
        ...formData,
        customer_id: formData.customer_id ? parseInt(formData.customer_id) : undefined,
        line_items: formData.line_items
      });
      setShowCreateModal(false);
      fetchInvoices();
    } catch (err) {
      alert('Failed to generate invoice: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSubmitting(false);
    }
  };

  const viewInvoiceDetail = async (inv) => {
    setSelectedInvoice(inv);
    setShowDetailModal(true);
    try {
      const res = await API.get(`/finance/invoices/${inv.id}`);
      setInvoiceDetail(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const openPaymentModal = (inv) => {
    setSelectedInvoice(inv);
    setPaymentForm({
      amount: inv.pending_amount || (inv.grand_total - inv.amount_paid),
      payment_method: 'BANK_TRANSFER',
      transaction_reference: '',
      bank_name: 'Axis Bank',
      payment_date: new Date().toISOString().split('T')[0],
      notes: `Settlement for invoice ${inv.invoice_number}`
    });
    setShowPaymentModal(true);
  };

  const handlePaymentSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      await API.post('/finance/payments/manual', {
        invoice_id: selectedInvoice.id,
        customer_id: selectedInvoice.customer_id,
        amount: parseFloat(paymentForm.amount),
        payment_method: paymentForm.payment_method,
        transaction_reference: paymentForm.transaction_reference,
        bank_name: paymentForm.bank_name,
        payment_date: paymentForm.payment_date,
        notes: paymentForm.notes
      });
      setShowPaymentModal(false);
      fetchInvoices();
      if (showDetailModal) {
        viewInvoiceDetail(selectedInvoice);
      }
    } catch (err) {
      alert('Failed to record payment: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSubmitting(false);
    }
  };

  const downloadPdf = (invId, invNum) => {
    window.open(`/api/finance/invoices/${invId}/pdf`, '_blank');
  };

  return (
    <div className="page-container" style={{ padding: '24px 32px 60px' }}>
      
      {/* 1. HEADER SECTION */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '24px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              backgroundColor: 'rgba(5, 150, 105, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#059669'
            }}>
              <FileText size={22} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>
                Customer Invoices
              </h1>
              <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '2px 0 0' }}>
                Generate statutory GST invoices, track payment status & download official PDFs
              </p>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowCreateModal(true)}
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
            gap: '8px',
            cursor: 'pointer',
            boxShadow: '0 2px 4px rgba(5, 150, 105, 0.2)'
          }}
        >
          <Plus size={18} />
          <span>Generate Customer Invoice</span>
        </button>
      </div>

      {/* 2. FILTER & SEARCH BAR */}
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
        {/* Status Tabs */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {[
            { id: 'all', label: 'All Invoices' },
            { id: 'paid', label: 'Paid' },
            { id: 'unpaid', label: 'Unpaid / Pending' },
            { id: 'partial', label: 'Partial' },
            { id: 'overdue', label: 'Overdue' }
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
                color: statusFilter === tab.id ? '#ffffff' : '#64748b',
                transition: 'all 0.15s ease'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div style={{ position: 'relative', minWidth: '280px' }}>
          <Search size={16} color="#94a3b8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
          <input
            type="text"
            placeholder="Search by invoice #, customer, company..."
            value={searchTerm}
            onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
            style={{
              width: '100%',
              padding: '8px 12px 8px 36px',
              borderRadius: '8px',
              border: '1px solid #cbd5e1',
              fontSize: '0.84rem'
            }}
          />
        </div>
      </div>

      {/* 3. INVOICES TABLE */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '16px',
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        overflow: 'hidden'
      }}>
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
            <div className="spinner" style={{ margin: '0 auto 12px', width: '32px', height: '32px', border: '3px solid #e2e8f0', borderTopColor: '#059669', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            <p style={{ margin: 0, fontWeight: '600', fontSize: '0.9rem' }}>Loading customer invoices...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#dc2626' }}>
            <AlertCircle size={32} style={{ margin: '0 auto 8px' }} />
            <p style={{ fontWeight: '700' }}>{error}</p>
            <button onClick={fetchInvoices} style={{ marginTop: '8px', padding: '6px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', cursor: 'pointer' }}>Retry</button>
          </div>
        ) : invoices.length === 0 ? (
          <div style={{ padding: '40px 20px' }}>
            <PingoEmptyState
              title="No Invoices Found"
              description="No invoice matches your current filter. Generate a new invoice above to get started."
            />
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #f1f5f9', backgroundColor: '#f8fafc', color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  <th style={{ padding: '12px 16px' }}>Invoice #</th>
                  <th style={{ padding: '12px 16px' }}>Customer / Company</th>
                  <th style={{ padding: '12px 16px' }}>Issue Date</th>
                  <th style={{ padding: '12px 16px' }}>Due Date</th>
                  <th style={{ padding: '12px 16px' }}>Grand Total</th>
                  <th style={{ padding: '12px 16px' }}>Amount Paid</th>
                  <th style={{ padding: '12px 16px' }}>Status</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => {
                  const isPaid = (inv.payment_status || '').toLowerCase() === 'paid';
                  const isPartial = (inv.payment_status || '').toLowerCase() === 'partial';

                  return (
                    <tr key={inv.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '14px 16px', fontWeight: '800', color: '#2563eb' }}>
                        {inv.invoice_number}
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ fontWeight: '700', color: '#0f172a' }}>
                          {inv.company_name || inv.customer_name}
                        </div>
                        {inv.company_name && (
                          <div style={{ fontSize: '0.74rem', color: '#64748b' }}>
                            {inv.customer_name}
                          </div>
                        )}
                      </td>

                      <td style={{ padding: '14px 16px', color: '#64748b' }}>
                        {inv.issue_date ? formatDateDDMMYYYY(inv.issue_date) : '—'}
                      </td>

                      <td style={{ padding: '14px 16px', color: inv.is_overdue ? '#dc2626' : '#64748b', fontWeight: inv.is_overdue ? '700' : '500' }}>
                        {inv.due_date ? formatDateDDMMYYYY(inv.due_date) : '—'}
                        {inv.is_overdue && (
                          <span style={{ marginLeft: '6px', fontSize: '0.68rem', padding: '2px 5px', borderRadius: '4px', backgroundColor: '#fee2e2', color: '#b91c1c' }}>
                            OVERDUE
                          </span>
                        )}
                      </td>

                      <td style={{ padding: '14px 16px', fontWeight: '800', color: '#0f172a' }}>
                        {formatINR(inv.grand_total)}
                        <span style={{ display: 'block', fontSize: '0.7rem', color: '#64748b', fontWeight: '500' }}>
                          Tax: {formatINR(inv.tax_total)}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px', fontWeight: '700', color: isPaid ? '#059669' : '#d97706' }}>
                        {formatINR(inv.amount_paid)}
                        {inv.pending_amount > 0 && (
                          <span style={{ display: 'block', fontSize: '0.7rem', color: '#dc2626', fontWeight: '600' }}>
                            Due: {formatINR(inv.pending_amount)}
                          </span>
                        )}
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <span style={{
                          padding: '4px 10px',
                          borderRadius: '12px',
                          fontSize: '0.72rem',
                          fontWeight: '800',
                          backgroundColor: isPaid ? 'rgba(16, 185, 129, 0.12)' : (isPartial ? 'rgba(245, 158, 11, 0.12)' : 'rgba(239, 68, 68, 0.12)'),
                          color: isPaid ? '#059669' : (isPartial ? '#d97706' : '#dc2626')
                        }}>
                          {(inv.payment_status || 'UNPAID').toUpperCase()}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          <button
                            type="button"
                            onClick={() => viewInvoiceDetail(inv)}
                            title="View Invoice Detail"
                            style={{
                              padding: '6px 10px',
                              borderRadius: '6px',
                              border: '1px solid #e2e8f0',
                              backgroundColor: '#ffffff',
                              color: '#334155',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '0.76rem',
                              fontWeight: '700'
                            }}
                          >
                            <Eye size={13} />
                            <span>View</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => downloadPdf(inv.id, inv.invoice_number)}
                            title="Download Official Tax Invoice PDF"
                            style={{
                              padding: '6px 10px',
                              borderRadius: '6px',
                              border: '1px solid #cbd5e1',
                              backgroundColor: '#f8fafc',
                              color: '#0f172a',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '0.76rem',
                              fontWeight: '700'
                            }}
                          >
                            <Download size={13} />
                            <span>PDF</span>
                          </button>

                          {!isPaid && (
                            <button
                              type="button"
                              onClick={() => openPaymentModal(inv)}
                              title="Record Payment against Invoice"
                              style={{
                                padding: '6px 10px',
                                borderRadius: '6px',
                                border: 'none',
                                backgroundColor: '#059669',
                                color: '#ffffff',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                fontSize: '0.76rem',
                                fontWeight: '700'
                              }}
                            >
                              <CreditCard size={13} />
                              <span>Pay</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 4. CREATE INVOICE MODAL */}
      {showCreateModal && (
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
            maxWidth: '750px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: '24px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <FileText size={22} color="#059669" />
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '800', color: '#0f172a' }}>
                  Generate Statutory Tax Invoice
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#64748b' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit}>
              {/* Customer Selection */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
                  Select Customer (or enter details below)
                </label>
                <select
                  value={formData.customer_id}
                  onChange={(e) => handleCustomerSelect(e.target.value)}
                  style={{ width: '100%', padding: '9px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.84rem' }}
                >
                  <option value="">— Select an existing customer —</option>
                  {customers.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.company_name} ({c.contact_name}) - {c.phone}
                    </option>
                  ))}
                </select>
              </div>

              {/* Customer Details Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#475569', marginBottom: '4px' }}>Customer / Contact Name *</label>
                  <input
                    type="text"
                    required
                    value={formData.customer_name}
                    onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#475569', marginBottom: '4px' }}>Company Name</label>
                  <input
                    type="text"
                    value={formData.company_name}
                    onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#475569', marginBottom: '4px' }}>Phone Number</label>
                  <input
                    type="text"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#475569', marginBottom: '4px' }}>Customer GSTIN</label>
                  <input
                    type="text"
                    placeholder="e.g. 33AAAAA0000A1Z5"
                    value={formData.gstin}
                    onChange={(e) => setFormData({ ...formData, gstin: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                  />
                </div>
              </div>

              {/* Tax Mode & Dates */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '18px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#475569', marginBottom: '4px' }}>State of Supply</label>
                  <select
                    value={formData.state_code}
                    onChange={(e) => setFormData({
                      ...formData,
                      state_code: e.target.value,
                      tax_mode: e.target.value === '33' ? 'intra' : 'inter',
                      state: e.target.value === '33' ? 'Tamil Nadu' : 'Other State'
                    })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                  >
                    <option value="33">Tamil Nadu (CGST 9% + SGST 9%)</option>
                    <option value="29">Karnataka (IGST 18%)</option>
                    <option value="27">Maharashtra (IGST 18%)</option>
                    <option value="07">Delhi (IGST 18%)</option>
                    <option value="99">Other Inter-State (IGST 18%)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#475569', marginBottom: '4px' }}>Due Date</label>
                  <input
                    type="date"
                    value={formData.due_date}
                    onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                    style={{ width: '100%', padding: '7px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#475569', marginBottom: '4px' }}>Custom Invoice # (Optional)</label>
                  <input
                    type="text"
                    placeholder="Auto-generated if blank"
                    value={formData.invoice_number || ''}
                    onChange={(e) => setFormData({ ...formData, invoice_number: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                  />
                </div>
              </div>

              {/* Line Items */}
              <div style={{ marginBottom: '18px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label style={{ fontSize: '0.82rem', fontWeight: '800', color: '#0f172a' }}>Subscription & Add-on Line Items</label>
                  <button
                    type="button"
                    onClick={addLineItem}
                    style={{
                      border: 'none',
                      background: 'none',
                      color: '#059669',
                      fontSize: '0.78rem',
                      fontWeight: '700',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    <Plus size={14} />
                    <span>Add Item</span>
                  </button>
                </div>

                {formData.line_items.map((item, idx) => (
                  <div key={idx} style={{ display: 'grid', gridTemplateColumns: '3fr 1fr 1.5fr 1.5fr 36px', gap: '8px', marginBottom: '8px', alignItems: 'center' }}>
                    <input
                      type="text"
                      placeholder="Product / Plan Description"
                      required
                      value={item.description}
                      onChange={(e) => handleLineItemChange(idx, 'description', e.target.value)}
                      style={{ padding: '7px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.8rem' }}
                    />
                    <input
                      type="number"
                      placeholder="Qty"
                      min="1"
                      value={item.qty}
                      onChange={(e) => handleLineItemChange(idx, 'qty', e.target.value)}
                      style={{ padding: '7px 8px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.8rem' }}
                    />
                    <input
                      type="number"
                      placeholder="Rate (₹)"
                      min="0"
                      value={item.rate}
                      onChange={(e) => handleLineItemChange(idx, 'rate', e.target.value)}
                      style={{ padding: '7px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.8rem' }}
                    />
                    <div style={{ fontWeight: '700', fontSize: '0.82rem', color: '#059669', padding: '7px 10px', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
                      {formatINR(item.amount)}
                    </div>
                    {formData.line_items.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeLineItem(idx)}
                        style={{ border: 'none', background: 'none', color: '#dc2626', cursor: 'pointer' }}
                      >
                        <X size={16} />
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {/* Calculations Box */}
              <div style={{
                backgroundColor: '#f8fafc',
                borderRadius: '10px',
                padding: '14px 18px',
                marginBottom: '18px',
                border: '1px solid #e2e8f0',
                fontSize: '0.82rem'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', color: '#475569' }}>
                  <span>Taxable Subtotal:</span>
                  <span style={{ fontWeight: '700' }}>{formatINR(calcSubtotal)}</span>
                </div>
                {isIntra ? (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', color: '#475569' }}>
                      <span>CGST (9%):</span>
                      <span style={{ fontWeight: '700' }}>{formatINR(calcCGST)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', color: '#475569' }}>
                      <span>SGST (9%):</span>
                      <span style={{ fontWeight: '700' }}>{formatINR(calcSGP)}</span>
                    </div>
                  </>
                ) : (
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', color: '#475569' }}>
                    <span>IGST (18%):</span>
                    <span style={{ fontWeight: '700' }}>{formatINR(calcIGST)}</span>
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '8px', borderTop: '1px solid #cbd5e1', fontSize: '1rem', fontWeight: '800', color: '#0f172a' }}>
                  <span>Grand Total (INR):</span>
                  <span style={{ color: '#059669' }}>{formatINR(calcGrandTotal)}</span>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  style={{ padding: '9px 16px', borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', color: '#64748b', cursor: 'pointer', fontWeight: '600' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{ padding: '9px 20px', borderRadius: '8px', border: 'none', backgroundColor: '#059669', color: '#ffffff', cursor: 'pointer', fontWeight: '800' }}
                >
                  {submitting ? 'Generating...' : 'Issue Invoice & Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 5. INVOICE DETAIL MODAL */}
      {showDetailModal && invoiceDetail && (
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
            maxWidth: '700px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: '24px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '800', color: '#0f172a' }}>
                  Tax Invoice {invoiceDetail.invoice_number}
                </h3>
                <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                  Issued on: {formatDateDDMMYYYY(invoiceDetail.issue_date)}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => downloadPdf(invoiceDetail.id, invoiceDetail.invoice_number)}
                  style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#f8fafc', fontWeight: '700', fontSize: '0.78rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <Download size={14} />
                  <span>Download PDF</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowDetailModal(false)}
                  style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#64748b' }}
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* Client Info */}
            <div style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '10px', marginBottom: '16px', fontSize: '0.82rem' }}>
              <div style={{ fontWeight: '800', color: '#0f172a', marginBottom: '4px' }}>
                {invoiceDetail.company_name || invoiceDetail.customer_name}
              </div>
              <div style={{ color: '#475569' }}>Contact: {invoiceDetail.customer_name} | {invoiceDetail.phone}</div>
              <div style={{ color: '#475569' }}>Address: {invoiceDetail.address}</div>
              {invoiceDetail.gstin && <div style={{ color: '#2563eb', fontWeight: '700' }}>GSTIN: {invoiceDetail.gstin}</div>}
            </div>

            {/* Line Items */}
            <div style={{ marginBottom: '16px' }}>
              <h4 style={{ fontSize: '0.86rem', fontWeight: '800', marginBottom: '8px' }}>Purchased Items</h4>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>
                    <th style={{ textAlign: 'left', padding: '6px 0' }}>Description</th>
                    <th style={{ textAlign: 'center', padding: '6px 0' }}>Qty</th>
                    <th style={{ textAlign: 'right', padding: '6px 0' }}>Rate</th>
                    <th style={{ textAlign: 'right', padding: '6px 0' }}>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {(invoiceDetail.line_items || []).map((item, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '8px 0', fontWeight: '600' }}>{item.description}</td>
                      <td style={{ textAlign: 'center', padding: '8px 0' }}>{item.qty}</td>
                      <td style={{ textAlign: 'right', padding: '8px 0' }}>{formatINR(item.rate)}</td>
                      <td style={{ textAlign: 'right', padding: '8px 0', fontWeight: '700', color: '#059669' }}>{formatINR(item.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Totals */}
            <div style={{ backgroundColor: '#f1f5f9', padding: '12px 16px', borderRadius: '8px', fontSize: '0.82rem', marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span>Subtotal:</span>
                <span style={{ fontWeight: '700' }}>{formatINR(invoiceDetail.subtotal)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span>Total GST Tax:</span>
                <span style={{ fontWeight: '700' }}>{formatINR(invoiceDetail.tax_total)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: '800', fontSize: '0.95rem', color: '#0f172a', paddingTop: '6px', borderTop: '1px solid #cbd5e1' }}>
                <span>Grand Total:</span>
                <span style={{ color: '#059669' }}>{formatINR(invoiceDetail.grand_total)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#2563eb', fontWeight: '700', marginTop: '4px' }}>
                <span>Amount Paid:</span>
                <span>{formatINR(invoiceDetail.amount_paid)}</span>
              </div>
              {invoiceDetail.pending_amount > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', color: '#dc2626', fontWeight: '800', marginTop: '2px' }}>
                  <span>Pending Due:</span>
                  <span>{formatINR(invoiceDetail.pending_amount)}</span>
                </div>
              )}
            </div>

            {/* Payment History */}
            <div>
              <h4 style={{ fontSize: '0.86rem', fontWeight: '800', marginBottom: '8px' }}>Payment Receipts & Transactions</h4>
              {(invoiceDetail.payments || []).length === 0 ? (
                <p style={{ fontSize: '0.78rem', color: '#94a3b8' }}>No payments recorded yet for this invoice.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {invoiceDetail.payments.map((p, idx) => (
                    <div key={idx} style={{ padding: '8px 12px', borderRadius: '6px', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
                      <div>
                        <span style={{ fontWeight: '700', color: '#2563eb' }}>{p.payment_number}</span> ({p.payment_method})
                        <span style={{ display: 'block', color: '#64748b' }}>Ref: {p.transaction_reference}</span>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <span style={{ fontWeight: '800', color: '#059669' }}>{formatINR(p.amount)}</span>
                        <span style={{ display: 'block', color: '#94a3b8' }}>{formatDateDDMMYYYY(p.payment_date)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 6. RECORD PAYMENT MODAL */}
      {showPaymentModal && selectedInvoice && (
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
            maxWidth: '480px',
            width: '100%',
            padding: '24px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CreditCard size={20} color="#059669" />
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: '800', color: '#0f172a' }}>
                  Record Payment
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowPaymentModal(false)}
                style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#64748b' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ marginBottom: '14px', fontSize: '0.82rem', backgroundColor: '#f8fafc', padding: '10px 14px', borderRadius: '8px' }}>
              <div><strong>Invoice:</strong> {selectedInvoice.invoice_number}</div>
              <div><strong>Client:</strong> {selectedInvoice.company_name || selectedInvoice.customer_name}</div>
              <div style={{ color: '#dc2626', fontWeight: '700', marginTop: '2px' }}>
                Pending Balance: {formatINR(selectedInvoice.pending_amount)}
              </div>
            </div>

            <form onSubmit={handlePaymentSubmit}>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  Amount Received (INR) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={paymentForm.amount}
                  onChange={(e) => setPaymentForm({ ...paymentForm, amount: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.86rem', fontWeight: '700' }}
                />
              </div>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  Payment Method *
                </label>
                <select
                  value={paymentForm.payment_method}
                  onChange={(e) => setPaymentForm({ ...paymentForm, payment_method: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                >
                  <option value="BANK_TRANSFER">Bank Transfer (NEFT / RTGS / IMPS)</option>
                  <option value="UPI">UPI / QR Code</option>
                  <option value="CHEQUE">Cheque / Demand Draft</option>
                  <option value="CASH">Cash</option>
                  <option value="CARD">Credit / Debit Card</option>
                </select>
              </div>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  Transaction Reference / UTR / Cheque No *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. AXIS-UTR-9823412 or Cheque #102934"
                  value={paymentForm.transaction_reference}
                  onChange={(e) => setPaymentForm({ ...paymentForm, transaction_reference: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                />
              </div>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  Deposited Bank Name
                </label>
                <input
                  type="text"
                  value={paymentForm.bank_name}
                  onChange={(e) => setPaymentForm({ ...paymentForm, bank_name: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  Payment Date
                </label>
                <input
                  type="date"
                  value={paymentForm.payment_date}
                  onChange={(e) => setPaymentForm({ ...paymentForm, payment_date: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowPaymentModal(false)}
                  style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', cursor: 'pointer', fontSize: '0.8rem' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{ padding: '8px 18px', borderRadius: '6px', border: 'none', backgroundColor: '#059669', color: '#ffffff', fontWeight: '800', cursor: 'pointer', fontSize: '0.82rem' }}
                >
                  {submitting ? 'Confirming...' : 'Confirm & Save Receipt'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};

export default InvoicesPage;
