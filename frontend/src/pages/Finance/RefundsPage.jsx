import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import {
  RotateCcw,
  Search,
  Filter,
  CheckCircle,
  Clock,
  AlertTriangle,
  Plus,
  ArrowUpRight,
  ShieldCheck,
  Building2,
  X,
  FileText
} from 'lucide-react';
import { formatDateDDMMYYYY } from '../../utils/dateUtils';
import PingoEmptyState from '../../components/Common/PingoEmptyState';

const formatINR = (val) => {
  const num = Number(val || 0);
  return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 2 });
};

const RefundsPage = () => {
  const [refunds, setRefunds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const [customers, setCustomers] = useState([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showProcessModal, setShowProcessModal] = useState(false);
  const [selectedRefund, setSelectedRefund] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // New refund request form
  const [newRefund, setNewRefund] = useState({
    customer_id: '',
    amount: '',
    reason: ''
  });

  // Process / UTR form
  const [processForm, setProcessForm] = useState({
    transaction_reference: '',
    status: 'PROCESSED'
  });

  const fetchRefunds = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await API.get('/finance/refunds', {
        params: {
          status: statusFilter !== 'all' ? statusFilter : undefined,
          search: searchTerm || undefined,
          page,
          limit: 25
        }
      });
      if (res.data) {
        setRefunds(res.data.items || []);
        setTotalCount(res.data.total || 0);
      }
    } catch (err) {
      console.error('Failed to load refunds:', err);
      setError('Unable to load refunds.');
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
    fetchRefunds();
  }, [statusFilter, searchTerm, page]);

  useEffect(() => {
    fetchCustomers();
  }, []);

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      await API.post('/finance/refunds', {
        customer_id: parseInt(newRefund.customer_id),
        amount: parseFloat(newRefund.amount),
        reason: newRefund.reason
      });
      setShowCreateModal(false);
      setNewRefund({ customer_id: '', amount: '', reason: '' });
      fetchRefunds();
    } catch (err) {
      alert('Failed to request refund: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatusUpdate = async (refundId, newStatus, extraData = {}) => {
    try {
      setSubmitting(true);
      await API.put(`/finance/refunds/${refundId}/status`, {
        status: newStatus,
        ...extraData
      });
      fetchRefunds();
    } catch (err) {
      alert('Failed to update refund status: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSubmitting(false);
    }
  };

  const handleProcessSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      await API.put(`/finance/refunds/${selectedRefund.id}/status`, {
        status: 'PROCESSED',
        transaction_reference: processForm.transaction_reference
      });
      setShowProcessModal(false);
      fetchRefunds();
    } catch (err) {
      alert('Failed to process refund: ' + (err.response?.data?.detail || err.message));
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
            backgroundColor: 'rgba(124, 58, 237, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#7c3aed'
          }}>
            <RotateCcw size={22} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>
              Refund Management & Approval Workflow
            </h1>
            <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '2px 0 0' }}>
              Review customer refund requests, authorize settlements & track gateway reversals
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowCreateModal(true)}
          style={{
            padding: '10px 18px',
            borderRadius: '9px',
            backgroundColor: '#7c3aed',
            color: '#ffffff',
            border: 'none',
            fontWeight: '700',
            fontSize: '0.86rem',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer'
          }}
        >
          <Plus size={18} />
          <span>New Refund Request</span>
        </button>
      </div>

      {/* 2. STATUS TABS */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '14px',
        padding: '12px 16px',
        border: '1px solid #e2e8f0',
        marginBottom: '20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '14px'
      }}>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {[
            { id: 'all', label: 'All Requests' },
            { id: 'REQUESTED', label: 'Requested' },
            { id: 'UNDER_REVIEW', label: 'Under Review' },
            { id: 'APPROVED', label: 'Approved' },
            { id: 'PROCESSED', label: 'Processed & Settled' },
            { id: 'REJECTED', label: 'Rejected' }
          ].map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => { setStatusFilter(tab.id); setPage(1); }}
              style={{
                padding: '7px 14px',
                borderRadius: '8px',
                fontSize: '0.82rem',
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

        <div style={{ position: 'relative', minWidth: '240px' }}>
          <Search size={16} color="#94a3b8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
          <input
            type="text"
            placeholder="Search refund #, customer..."
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
            <div className="spinner" style={{ margin: '0 auto 12px', width: '32px', height: '32px', border: '3px solid #e2e8f0', borderTopColor: '#7c3aed', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            <p style={{ margin: 0, fontWeight: '600', fontSize: '0.9rem' }}>Loading refund requests...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#dc2626' }}>
            <p style={{ fontWeight: '700' }}>{error}</p>
            <button onClick={fetchRefunds} style={{ marginTop: '8px', padding: '6px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', cursor: 'pointer' }}>Retry</button>
          </div>
        ) : refunds.length === 0 ? (
          <div style={{ padding: '40px 20px' }}>
            <PingoEmptyState
              title="No Refund Requests"
              description="No refund records match your selected status filter."
            />
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #f1f5f9', backgroundColor: '#f8fafc', color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  <th style={{ padding: '12px 16px' }}>Refund #</th>
                  <th style={{ padding: '12px 16px' }}>Customer / Company</th>
                  <th style={{ padding: '12px 16px' }}>Amount</th>
                  <th style={{ padding: '12px 16px' }}>Reason</th>
                  <th style={{ padding: '12px 16px' }}>Status</th>
                  <th style={{ padding: '12px 16px' }}>Bank UTR / Ref</th>
                  <th style={{ padding: '12px 16px' }}>Requested Date</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>Workflow Action</th>
                </tr>
              </thead>
              <tbody>
                {refunds.map((ref) => {
                  const isProcessed = ref.status === 'PROCESSED';
                  const isApproved = ref.status === 'APPROVED';
                  const isUnderReview = ref.status === 'UNDER_REVIEW';
                  const isRejected = ref.status === 'REJECTED';

                  return (
                    <tr key={ref.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '14px 16px', fontWeight: '800', color: '#7c3aed' }}>
                        {ref.refund_number}
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ fontWeight: '700', color: '#0f172a' }}>
                          {ref.company_name || ref.customer_name}
                        </div>
                        {ref.company_name && (
                          <div style={{ fontSize: '0.74rem', color: '#64748b' }}>
                            {ref.customer_name}
                          </div>
                        )}
                      </td>

                      <td style={{ padding: '14px 16px', fontWeight: '800', color: '#dc2626' }}>
                        {formatINR(ref.amount)}
                      </td>

                      <td style={{ padding: '14px 16px', color: '#475569', maxWidth: '240px' }}>
                        {ref.reason}
                        {ref.rejection_reason && (
                          <div style={{ fontSize: '0.72rem', color: '#dc2626', marginTop: '2px' }}>
                            Reason: {ref.rejection_reason}
                          </div>
                        )}
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <span style={{
                          padding: '3px 9px',
                          borderRadius: '12px',
                          fontSize: '0.72rem',
                          fontWeight: '800',
                          backgroundColor: isProcessed ? 'rgba(16, 185, 129, 0.12)' : (isApproved ? 'rgba(37, 99, 235, 0.12)' : (isRejected ? 'rgba(239, 68, 68, 0.12)' : 'rgba(245, 158, 11, 0.12)')),
                          color: isProcessed ? '#059669' : (isApproved ? '#2563eb' : (isRejected ? '#dc2626' : '#d97706'))
                        }}>
                          {ref.status}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px', fontFamily: 'monospace', fontSize: '0.78rem', color: '#64748b' }}>
                        {ref.transaction_reference || '—'}
                      </td>

                      <td style={{ padding: '14px 16px', color: '#64748b', fontSize: '0.78rem' }}>
                        {ref.created_at ? formatDateDDMMYYYY(ref.created_at) : '—'}
                      </td>

                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          {ref.status === 'REQUESTED' && (
                            <>
                              <button
                                type="button"
                                onClick={() => handleStatusUpdate(ref.id, 'APPROVED')}
                                style={{
                                  padding: '5px 10px',
                                  borderRadius: '6px',
                                  border: 'none',
                                  backgroundColor: '#2563eb',
                                  color: '#ffffff',
                                  fontSize: '0.76rem',
                                  fontWeight: '700',
                                  cursor: 'pointer'
                                }}
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  const reason = prompt('Please enter rejection reason:');
                                  if (reason) handleStatusUpdate(ref.id, 'REJECTED', { rejection_reason: reason });
                                }}
                                style={{
                                  padding: '5px 10px',
                                  borderRadius: '6px',
                                  border: '1px solid #fecaca',
                                  backgroundColor: '#fff1f2',
                                  color: '#dc2626',
                                  fontSize: '0.76rem',
                                  fontWeight: '700',
                                  cursor: 'pointer'
                                }}
                              >
                                Reject
                              </button>
                            </>
                          )}

                          {ref.status === 'APPROVED' && (
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedRefund(ref);
                                setProcessForm({ transaction_reference: `REF-UTR-${ref.id}-2026`, status: 'PROCESSED' });
                                setShowProcessModal(true);
                              }}
                              style={{
                                padding: '5px 12px',
                                borderRadius: '6px',
                                border: 'none',
                                backgroundColor: '#059669',
                                color: '#ffffff',
                                fontSize: '0.76rem',
                                fontWeight: '800',
                                cursor: 'pointer'
                              }}
                            >
                              Mark Processed
                            </button>
                          )}

                          {isProcessed && (
                            <span style={{ fontSize: '0.75rem', color: '#059669', fontWeight: '700' }}>
                              ✓ Settled
                            </span>
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

      {/* 4. CREATE REFUND MODAL */}
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
            maxWidth: '480px',
            width: '100%',
            padding: '24px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: '800' }}>Create Refund Request</h3>
              <button type="button" onClick={() => setShowCreateModal(false)} style={{ border: 'none', background: 'none', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit}>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Customer *</label>
                <select
                  required
                  value={newRefund.customer_id}
                  onChange={(e) => setNewRefund({ ...newRefund, customer_id: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                >
                  <option value="">— Select Customer —</option>
                  {customers.map(c => (
                    <option key={c.id} value={c.id}>{c.company_name} ({c.contact_name})</option>
                  ))}
                </select>
              </div>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Refund Amount (INR) *</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={newRefund.amount}
                  onChange={(e) => setNewRefund({ ...newRefund, amount: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.84rem', fontWeight: '700' }}
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Reason for Refund *</label>
                <textarea
                  rows="3"
                  required
                  placeholder="e.g. Client requested contract downgrade; duplicate transaction reversal; SLA guarantee credit."
                  value={newRefund.reason}
                  onChange={(e) => setNewRefund({ ...newRefund, reason: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{ padding: '8px 18px', borderRadius: '6px', border: 'none', backgroundColor: '#7c3aed', color: '#ffffff', fontWeight: '800', cursor: 'pointer' }}
                >
                  {submitting ? 'Submitting...' : 'Submit Request'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 5. MARK PROCESSED MODAL */}
      {showProcessModal && selectedRefund && (
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
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: '800', color: '#059669' }}>
                Settle & Process Refund
              </h3>
              <button type="button" onClick={() => setShowProcessModal(false)} style={{ border: 'none', background: 'none', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ backgroundColor: '#f8fafc', padding: '12px', borderRadius: '8px', fontSize: '0.82rem', marginBottom: '14px' }}>
              <div><strong>Refund #:</strong> {selectedRefund.refund_number}</div>
              <div><strong>Client:</strong> {selectedRefund.company_name || selectedRefund.customer_name}</div>
              <div style={{ color: '#dc2626', fontWeight: '800', marginTop: '4px' }}>
                Amount to Refund: {formatINR(selectedRefund.amount)}
              </div>
            </div>

            <form onSubmit={handleProcessSubmit}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  Bank UTR or Payment Gateway Refund ID *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. AXIS-REF-UTR-98124 or rzp_ref_1029"
                  value={processForm.transaction_reference}
                  onChange={(e) => setProcessForm({ ...processForm, transaction_reference: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowProcessModal(false)}
                  style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{ padding: '8px 18px', borderRadius: '6px', border: 'none', backgroundColor: '#059669', color: '#ffffff', fontWeight: '800', cursor: 'pointer' }}
                >
                  {submitting ? 'Settling...' : 'Confirm Settlement'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};

export default RefundsPage;
