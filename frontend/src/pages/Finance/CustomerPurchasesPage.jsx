import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import {
  Users,
  Search,
  CheckCircle,
  Clock,
  Eye,
  Building2,
  Calendar,
  Package,
  Layers,
  Sparkles,
  Phone,
  Mail,
  UserCheck,
  ShieldCheck,
  X
} from 'lucide-react';
import { formatDateDDMMYYYY } from '../../utils/dateUtils';
import PingoEmptyState from '../../components/Common/PingoEmptyState';

const formatINR = (val) => {
  const num = Number(val || 0);
  return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 2 });
};

const CustomerPurchasesPage = () => {
  const [purchases, setPurchases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [showModal, setShowModal] = useState(false);

  const fetchPurchases = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await API.get('/finance/customer-purchases', {
        params: {
          search: searchTerm || undefined,
          page,
          limit: 25
        }
      });
      if (res.data) {
        setPurchases(res.data.items || []);
        setTotalCount(res.data.total || 0);
      }
    } catch (err) {
      console.error('Failed to load customer purchase details:', err);
      setError('Unable to load customer purchase details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPurchases();
  }, [searchTerm, page]);

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
            <Package size={22} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>
              Customer Purchase Details
            </h1>
            <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '2px 0 0' }}>
              Purchases from converted Sales leads: plans, add-ons, amounts, GST & renewal dates
            </p>
          </div>
        </div>

        {/* Search */}
        <div style={{ position: 'relative', minWidth: '300px' }}>
          <Search size={16} color="#94a3b8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
          <input
            type="text"
            placeholder="Search customer, company..."
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

      {/* 2. TABLE */}
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
            <p style={{ margin: 0, fontWeight: '600', fontSize: '0.9rem' }}>Loading customer purchases...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#dc2626' }}>
            <p style={{ fontWeight: '700' }}>{error}</p>
            <button onClick={fetchPurchases} style={{ marginTop: '8px', padding: '6px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', cursor: 'pointer' }}>Retry</button>
          </div>
        ) : purchases.length === 0 ? (
          <div style={{ padding: '40px 20px' }}>
            <PingoEmptyState
              title="No Customer Purchases"
              description="When Sales converts a lead into a customer, their commercial details will appear here."
            />
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #f1f5f9', backgroundColor: '#f8fafc', color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  <th style={{ padding: '12px 16px' }}>Customer & Company</th>
                  <th style={{ padding: '12px 16px' }}>Sales Rep</th>
                  <th style={{ padding: '12px 16px' }}>Subscription Plan</th>
                  <th style={{ padding: '12px 16px' }}>Add-on Products</th>
                  <th style={{ padding: '12px 16px' }}>Base Amount</th>
                  <th style={{ padding: '12px 16px' }}>GST (18%)</th>
                  <th style={{ padding: '12px 16px' }}>Final Amount</th>
                  <th style={{ padding: '12px 16px' }}>Payment</th>
                  <th style={{ padding: '12px 16px' }}>Renewal Date</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {purchases.map((p) => {
                  const isPaid = (p.payment_status || '').toUpperCase() === 'PAID';
                  const isPro = (p.plan_code || '').toLowerCase() === 'pro';

                  return (
                    <tr key={p.customer_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ fontWeight: '800', color: '#0f172a' }}>
                          {p.company_name || p.customer_name}
                        </div>
                        {p.company_name && (
                          <div style={{ fontSize: '0.74rem', color: '#64748b' }}>
                            {p.customer_name}
                          </div>
                        )}
                      </td>

                      <td style={{ padding: '14px 16px', color: '#475569', fontWeight: '600' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <UserCheck size={13} color="#2563eb" />
                          <span>{p.sales_employee_name}</span>
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <span style={{
                          padding: '4px 10px',
                          borderRadius: '8px',
                          fontWeight: '800',
                          fontSize: '0.76rem',
                          backgroundColor: isPro ? 'rgba(124, 58, 237, 0.1)' : 'rgba(37, 99, 235, 0.1)',
                          color: isPro ? '#7c3aed' : '#2563eb'
                        }}>
                          {p.plan_name} ({p.licence_count} Licences)
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        {p.addons && p.addons.length > 0 ? (
                          <span style={{ fontSize: '0.75rem', fontWeight: '700', color: '#059669', padding: '3px 8px', borderRadius: '6px', backgroundColor: 'rgba(5, 150, 105, 0.08)' }}>
                            {p.addons.length} Add-on{p.addons.length === 1 ? '' : 's'}
                          </span>
                        ) : (
                          <span style={{ color: '#94a3b8', fontSize: '0.78rem' }}>None</span>
                        )}
                      </td>

                      <td style={{ padding: '14px 16px', color: '#475569', fontWeight: '600' }}>
                        {formatINR(p.subscription_amount)}
                      </td>

                      <td style={{ padding: '14px 16px', color: '#64748b' }}>
                        {formatINR(p.gst_amount)}
                      </td>

                      <td style={{ padding: '14px 16px', fontWeight: '800', color: '#0f172a' }}>
                        {formatINR(p.final_amount)}
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <span style={{
                          padding: '3px 8px',
                          borderRadius: '12px',
                          fontSize: '0.72rem',
                          fontWeight: '800',
                          backgroundColor: isPaid ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)',
                          color: isPaid ? '#059669' : '#d97706'
                        }}>
                          {p.payment_status}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px', color: '#64748b', fontSize: '0.78rem', fontWeight: '600' }}>
                        {p.renewal_date ? formatDateDDMMYYYY(p.renewal_date) : '—'}
                      </td>

                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        <button
                          type="button"
                          onClick={() => { setSelectedCustomer(p); setShowModal(true); }}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '6px',
                            border: '1px solid #cbd5e1',
                            backgroundColor: '#ffffff',
                            color: '#0f172a',
                            fontWeight: '700',
                            fontSize: '0.76rem',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                        >
                          <Eye size={13} />
                          <span>Drill-down</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 3. DRILL DOWN MODAL */}
      {showModal && selectedCustomer && (
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
            maxWidth: '560px',
            width: '100%',
            padding: '24px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Package size={20} color="#059669" />
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: '800' }}>
                  {selectedCustomer.company_name || selectedCustomer.customer_name}
                </h3>
              </div>
              <button type="button" onClick={() => setShowModal(false)} style={{ border: 'none', background: 'none', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ fontSize: '0.84rem', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Primary Contact:</span>
                <span style={{ fontWeight: '700' }}>{selectedCustomer.customer_name} ({selectedCustomer.phone})</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Sales Representative:</span>
                <span style={{ fontWeight: '700', color: '#2563eb' }}>{selectedCustomer.sales_employee_name}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Purchased Plan:</span>
                <span style={{ fontWeight: '800' }}>{selectedCustomer.plan_name} ({selectedCustomer.licence_count} Licences)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Purchase / Start Date:</span>
                <span>{formatDateDDMMYYYY(selectedCustomer.purchase_date)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Renewal Date:</span>
                <span style={{ fontWeight: '700', color: '#d97706' }}>{formatDateDDMMYYYY(selectedCustomer.renewal_date)}</span>
              </div>

              {/* Addons List */}
              <div style={{ marginTop: '8px', padding: '12px', backgroundColor: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div style={{ fontWeight: '800', marginBottom: '6px', fontSize: '0.8rem', color: '#0f172a' }}>
                  Purchased Add-on Products:
                </div>
                {(!selectedCustomer.addons || selectedCustomer.addons.length === 0) ? (
                  <div style={{ color: '#94a3b8', fontSize: '0.78rem' }}>Standard package without add-ons.</div>
                ) : (
                  selectedCustomer.addons.map((add, idx) => (
                    <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '4px' }}>
                      <span>• {add.name} (Qty: {add.qty || 1})</span>
                      <span style={{ fontWeight: '700', color: '#059669' }}>{formatINR(add.amount || add.total)}</span>
                    </div>
                  ))
                )}
              </div>

              {/* Financial Summary */}
              <div style={{ marginTop: '8px', padding: '12px', backgroundColor: '#f1f5f9', borderRadius: '8px', border: '1px solid #cbd5e1' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span>Subscription Amount (Base):</span>
                  <span style={{ fontWeight: '700' }}>{formatINR(selectedCustomer.subscription_amount)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span>GST Breakdown (18%):</span>
                  <span style={{ fontWeight: '700' }}>{formatINR(selectedCustomer.gst_amount)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: '800', fontSize: '0.96rem', paddingTop: '6px', borderTop: '1px solid #cbd5e1', color: '#0f172a' }}>
                  <span>Final Amount:</span>
                  <span style={{ color: '#059669' }}>{formatINR(selectedCustomer.final_amount)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px', fontSize: '0.8rem' }}>
                  <span>Payment Status:</span>
                  <span style={{ fontWeight: '800', color: '#059669' }}>{selectedCustomer.payment_status}</span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
              <button
                type="button"
                onClick={() => setShowModal(false)}
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

export default CustomerPurchasesPage;
