import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import {
  Calendar,
  Search,
  Filter,
  CheckCircle,
  Clock,
  AlertTriangle,
  RotateCcw,
  Plus,
  ArrowUpRight,
  TrendingUp,
  Sparkles,
  CreditCard,
  Building2,
  X
} from 'lucide-react';
import { formatDateDDMMYYYY } from '../../utils/dateUtils';
import PingoEmptyState from '../../components/Common/PingoEmptyState';

const formatINR = (val) => {
  const num = Number(val || 0);
  return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 2 });
};

const SubscriptionsPage = () => {
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Modals state
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [showAddonModal, setShowAddonModal] = useState(false);
  const [showRenewalModal, setShowRenewalModal] = useState(false);
  const [selectedSub, setSelectedSub] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Upgrade / Downgrade form
  const [upgradeForm, setUpgradeForm] = useState({
    plan_code: 'pro',
    licence_count: 50
  });

  // Addon form
  const [addonForm, setAddonForm] = useState({
    name: 'WhatsApp Automation Pack',
    code: 'wa_alerts',
    amount: 3500,
    qty: 1
  });

  // Renewal form
  const [renewalForm, setRenewalForm] = useState({
    payment_method: 'BANK_TRANSFER',
    transaction_reference: ''
  });

  const fetchSubscriptions = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await API.get('/finance/subscriptions', {
        params: {
          status: statusFilter !== 'all' ? statusFilter : undefined,
          search: searchTerm || undefined,
          page,
          limit: 25
        }
      });
      if (res.data) {
        setSubscriptions(res.data.items || []);
        setTotalCount(res.data.total || 0);
      }
    } catch (err) {
      console.error('Failed to load subscriptions:', err);
      setError('Unable to load subscriptions.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubscriptions();
  }, [statusFilter, searchTerm, page]);

  const handleUpgradeSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      await API.post(`/finance/subscriptions/${selectedSub.id}/upgrade-downgrade`, {
        plan_code: upgradeForm.plan_code,
        licence_count: parseInt(upgradeForm.licence_count)
      });
      setShowUpgradeModal(false);
      fetchSubscriptions();
    } catch (err) {
      alert('Failed to modify plan: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddonSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      await API.post(`/finance/subscriptions/${selectedSub.id}/add-on`, {
        ...addonForm,
        amount: parseFloat(addonForm.amount),
        qty: parseInt(addonForm.qty)
      });
      setShowAddonModal(false);
      fetchSubscriptions();
    } catch (err) {
      alert('Failed to add add-on: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRenewalSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      await API.post(`/finance/subscriptions/${selectedSub.id}/renew`, {
        payment_method: renewalForm.payment_method,
        transaction_reference: renewalForm.transaction_reference
      });
      setShowRenewalModal(false);
      fetchSubscriptions();
    } catch (err) {
      alert('Failed to renew subscription: ' + (err.response?.data?.detail || err.message));
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
            backgroundColor: 'rgba(5, 150, 105, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#059669'
          }}>
            <Calendar size={22} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>
              Subscription & Renewal Management
            </h1>
            <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '2px 0 0' }}>
              Monitor active subscriptions, upcoming renewals, plan upgrades/downgrades & add-ons
            </p>
          </div>
        </div>

        <div style={{ position: 'relative', minWidth: '280px' }}>
          <Search size={16} color="#94a3b8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
          <input
            type="text"
            placeholder="Search plan, customer..."
            value={searchTerm}
            onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
            style={{
              width: '100%',
              padding: '9px 12px 9px 36px',
              borderRadius: '8px',
              border: '1px solid #cbd5e1',
              fontSize: '0.84rem'
            }}
          />
        </div>
      </div>

      {/* 2. STATUS TABS */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '14px',
        padding: '12px 16px',
        border: '1px solid #e2e8f0',
        marginBottom: '20px',
        display: 'flex',
        gap: '6px',
        flexWrap: 'wrap'
      }}>
        {[
          { id: 'all', label: 'All Subscriptions' },
          { id: 'ACTIVE', label: 'Active Subscriptions' },
          { id: 'UPCOMING_RENEWAL', label: 'Upcoming Renewals (Next 30 Days)' },
          { id: 'EXPIRED', label: 'Expired' }
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

      {/* 3. SUBSCRIPTIONS TABLE */}
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
            <p style={{ margin: 0, fontWeight: '600', fontSize: '0.9rem' }}>Loading subscriptions...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#dc2626' }}>
            <p style={{ fontWeight: '700' }}>{error}</p>
            <button onClick={fetchSubscriptions} style={{ marginTop: '8px', padding: '6px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', cursor: 'pointer' }}>Retry</button>
          </div>
        ) : subscriptions.length === 0 ? (
          <div style={{ padding: '40px 20px' }}>
            <PingoEmptyState
              title="No Subscriptions Found"
              description="Subscriptions created from converted sales contracts will appear here."
            />
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #f1f5f9', backgroundColor: '#f8fafc', color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  <th style={{ padding: '12px 16px' }}>Subscription #</th>
                  <th style={{ padding: '12px 16px' }}>Customer / Company</th>
                  <th style={{ padding: '12px 16px' }}>Current Plan</th>
                  <th style={{ padding: '12px 16px' }}>Licences</th>
                  <th style={{ padding: '12px 16px' }}>Cycle Amount</th>
                  <th style={{ padding: '12px 16px' }}>Add-ons</th>
                  <th style={{ padding: '12px 16px' }}>Status</th>
                  <th style={{ padding: '12px 16px' }}>Renewal Date</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {subscriptions.map((sub) => {
                  const isUrgent = sub.is_urgent_renewal;
                  const isExpired = sub.days_to_renew < 0;

                  return (
                    <tr key={sub.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '14px 16px', fontWeight: '800', color: '#2563eb' }}>
                        {sub.subscription_number}
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ fontWeight: '700', color: '#0f172a' }}>
                          {sub.company_name || sub.customer_name}
                        </div>
                        {sub.company_name && (
                          <div style={{ fontSize: '0.74rem', color: '#64748b' }}>
                            {sub.customer_name}
                          </div>
                        )}
                      </td>

                      <td style={{ padding: '14px 16px', fontWeight: '800', color: '#0f172a' }}>
                        {sub.plan_name}
                      </td>

                      <td style={{ padding: '14px 16px', color: '#475569', fontWeight: '600' }}>
                        {sub.licence_count} Seats
                      </td>

                      <td style={{ padding: '14px 16px', fontWeight: '800', color: '#059669' }}>
                        {formatINR(sub.total_amount)}
                        <span style={{ display: 'block', fontSize: '0.7rem', color: '#64748b', fontWeight: '500' }}>
                          Base: {formatINR(sub.subscription_amount)}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        {sub.addons && sub.addons.length > 0 ? (
                          <span style={{ fontSize: '0.75rem', fontWeight: '700', color: '#7c3aed', padding: '2px 7px', borderRadius: '4px', backgroundColor: 'rgba(124, 58, 237, 0.08)' }}>
                            {sub.addons.length} Add-on{sub.addons.length === 1 ? '' : 's'}
                          </span>
                        ) : (
                          <span style={{ color: '#94a3b8', fontSize: '0.76rem' }}>—</span>
                        )}
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <span style={{
                          padding: '4px 10px',
                          borderRadius: '12px',
                          fontSize: '0.72rem',
                          fontWeight: '800',
                          backgroundColor: isExpired ? 'rgba(239, 68, 68, 0.12)' : (isUrgent ? 'rgba(245, 158, 11, 0.12)' : 'rgba(16, 185, 129, 0.12)'),
                          color: isExpired ? '#dc2626' : (isUrgent ? '#d97706' : '#059669')
                        }}>
                          {isExpired ? 'EXPIRED' : (isUrgent ? 'RENEWAL DUE' : sub.status)}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px', color: isExpired ? '#dc2626' : (isUrgent ? '#d97706' : '#64748b'), fontWeight: isUrgent || isExpired ? '700' : '500' }}>
                        {sub.renewal_date ? formatDateDDMMYYYY(sub.renewal_date) : '—'}
                        <span style={{ display: 'block', fontSize: '0.7rem', color: '#94a3b8' }}>
                          {isExpired ? `${Math.abs(sub.days_to_renew)} days ago` : `in ${sub.days_to_renew} days`}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedSub(sub);
                              setUpgradeForm({ plan_code: sub.plan_code === 'pro' ? 'business' : 'pro', licence_count: sub.licence_count });
                              setShowUpgradeModal(true);
                            }}
                            title="Upgrade or Downgrade Plan"
                            style={{
                              padding: '5px 9px',
                              borderRadius: '6px',
                              border: '1px solid #cbd5e1',
                              backgroundColor: '#ffffff',
                              color: '#334155',
                              cursor: 'pointer',
                              fontSize: '0.76rem',
                              fontWeight: '700'
                            }}
                          >
                            Plan
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              setSelectedSub(sub);
                              setShowAddonModal(true);
                            }}
                            title="Add Add-on Product"
                            style={{
                              padding: '5px 9px',
                              borderRadius: '6px',
                              border: '1px solid #cbd5e1',
                              backgroundColor: '#ffffff',
                              color: '#7c3aed',
                              cursor: 'pointer',
                              fontSize: '0.76rem',
                              fontWeight: '700'
                            }}
                          >
                            + Add-on
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              setSelectedSub(sub);
                              setRenewalForm({ payment_method: 'BANK_TRANSFER', transaction_reference: '' });
                              setShowRenewalModal(true);
                            }}
                            title="Process Annual Renewal"
                            style={{
                              padding: '5px 10px',
                              borderRadius: '6px',
                              border: 'none',
                              backgroundColor: '#059669',
                              color: '#ffffff',
                              cursor: 'pointer',
                              fontSize: '0.76rem',
                              fontWeight: '800'
                            }}
                          >
                            Renew
                          </button>
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

      {/* 4. UPGRADE / DOWNGRADE MODAL */}
      {showUpgradeModal && selectedSub && (
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
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: '800' }}>Modify Subscription Plan</h3>
              <button type="button" onClick={() => setShowUpgradeModal(false)} style={{ border: 'none', background: 'none', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '14px' }}>
              Client: <strong>{selectedSub.company_name || selectedSub.customer_name}</strong> (Current: {selectedSub.plan_name})
            </p>

            <form onSubmit={handleUpgradeSubmit}>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Select Target Plan *</label>
                <select
                  value={upgradeForm.plan_code}
                  onChange={(e) => setUpgradeForm({ ...upgradeForm, plan_code: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.84rem' }}
                >
                  <option value="business">WAHRMS Business (₹700 / seat / year)</option>
                  <option value="pro">WAHRMS Pro (₹800 / seat / year)</option>
                </select>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Licence / User Seat Count *</label>
                <input
                  type="number"
                  min="5"
                  step="5"
                  required
                  value={upgradeForm.licence_count}
                  onChange={(e) => setUpgradeForm({ ...upgradeForm, licence_count: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.84rem' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowUpgradeModal(false)}
                  style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{ padding: '8px 18px', borderRadius: '6px', border: 'none', backgroundColor: '#2563eb', color: '#ffffff', fontWeight: '800', cursor: 'pointer' }}
                >
                  {submitting ? 'Applying...' : 'Apply Plan Change'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 5. ADD ADD-ON MODAL */}
      {showAddonModal && selectedSub && (
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
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: '800' }}>Add Add-on Product</h3>
              <button type="button" onClick={() => setShowAddonModal(false)} style={{ border: 'none', background: 'none', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddonSubmit}>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Add-on Package *</label>
                <select
                  value={addonForm.code}
                  onChange={(e) => {
                    const c = e.target.value;
                    let name = 'WhatsApp Automation Pack';
                    let amt = 3500;
                    if (c === 'bio_sync') { name = 'Biometric Hardware Sync Agent'; amt = 5000; }
                    if (c === 'multi_branch') { name = 'Multi-Branch Master Controller'; amt = 6000; }
                    if (c === 'payroll_compliance') { name = 'Statutory PF/ESI Filing Connector'; amt = 4500; }
                    setAddonForm({ ...addonForm, code: c, name, amount: amt });
                  }}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.84rem' }}
                >
                  <option value="wa_alerts">WhatsApp Automation Pack (₹3,500)</option>
                  <option value="bio_sync">Biometric Hardware Sync Agent (₹5,000)</option>
                  <option value="multi_branch">Multi-Branch Master Controller (₹6,000)</option>
                  <option value="payroll_compliance">Statutory PF/ESI Filing Connector (₹4,500)</option>
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Rate (₹) *</label>
                  <input
                    type="number"
                    required
                    value={addonForm.amount}
                    onChange={(e) => setAddonForm({ ...addonForm, amount: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.84rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Quantity *</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={addonForm.qty}
                    onChange={(e) => setAddonForm({ ...addonForm, qty: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.84rem' }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowAddonModal(false)}
                  style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{ padding: '8px 18px', borderRadius: '6px', border: 'none', backgroundColor: '#7c3aed', color: '#ffffff', fontWeight: '800', cursor: 'pointer' }}
                >
                  {submitting ? 'Adding...' : 'Attach Add-on'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 6. RENEWAL MODAL */}
      {showRenewalModal && selectedSub && (
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
                Process Annual Renewal
              </h3>
              <button type="button" onClick={() => setShowRenewalModal(false)} style={{ border: 'none', background: 'none', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ backgroundColor: '#f8fafc', padding: '12px', borderRadius: '8px', fontSize: '0.82rem', marginBottom: '14px' }}>
              <div><strong>Client:</strong> {selectedSub.company_name || selectedSub.customer_name}</div>
              <div><strong>Plan:</strong> {selectedSub.plan_name} ({selectedSub.licence_count} seats)</div>
              <div style={{ marginTop: '4px', fontWeight: '800', color: '#059669' }}>
                Renewal Due Amount: {formatINR(selectedSub.total_amount)}
              </div>
            </div>

            <form onSubmit={handleRenewalSubmit}>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Payment Mode *</label>
                <select
                  value={renewalForm.payment_method}
                  onChange={(e) => setRenewalForm({ ...renewalForm, payment_method: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                >
                  <option value="BANK_TRANSFER">Bank Transfer (NEFT/RTGS)</option>
                  <option value="RAZORPAY">Razorpay PG</option>
                  <option value="UPI">UPI / QR Code</option>
                  <option value="CHEQUE">Cheque</option>
                </select>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Bank Reference / UTR # *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. AXIS-UTR-29384912"
                  value={renewalForm.transaction_reference}
                  onChange={(e) => setRenewalForm({ ...renewalForm, transaction_reference: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowRenewalModal(false)}
                  style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{ padding: '8px 18px', borderRadius: '6px', border: 'none', backgroundColor: '#059669', color: '#ffffff', fontWeight: '800', cursor: 'pointer' }}
                >
                  {submitting ? 'Processing...' : 'Confirm Renewal (+1 Year)'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};

export default SubscriptionsPage;
