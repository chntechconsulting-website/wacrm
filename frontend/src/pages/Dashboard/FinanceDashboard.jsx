import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import { useNavigate } from 'react-router-dom';
import {
  DollarSign,
  TrendingUp,
  Clock,
  CheckCircle,
  AlertTriangle,
  RotateCcw,
  FileText,
  CreditCard,
  Users,
  Calendar,
  ArrowUpRight,
  Download,
  Plus,
  RefreshCw,
  ShieldCheck,
  ChevronRight,
  Building2,
  Phone,
  Eye,
  Filter
} from 'lucide-react';
import { formatDateDDMMYYYY, formatLocalDateTime } from '../../utils/dateUtils';
import PingoEmptyState from '../../components/Common/PingoEmptyState';

const formatINR = (val) => {
  const num = Number(val || 0);
  return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 2 });
};

const FinanceDashboard = ({ data, onRefresh }) => {
  const navigate = useNavigate();
  const [statsData, setStatsData] = useState(data || null);
  const [loading, setLoading] = useState(!data);
  const [refreshing, setRefreshing] = useState(false);
  const [periodFilter, setPeriodFilter] = useState('This Month');

  const fetchStats = async () => {
    try {
      setRefreshing(true);
      const res = await API.get('/finance/dashboard/stats');
      if (res.data) {
        setStatsData(res.data);
      }
    } catch (e) {
      console.error('Failed to load finance stats:', e);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    if (data) {
      setStatsData(data);
      setLoading(false);
    } else {
      fetchStats();
    }
  }, [data]);

  const handleRefresh = () => {
    if (onRefresh) onRefresh();
    fetchStats();
  };

  const fin = statsData || data || {};

  const totalRevenue = fin.total_revenue ?? 0;
  const netRevenue = fin.net_revenue ?? totalRevenue;
  const currentMonthRevenue = fin.current_month_revenue ?? 0;
  const pendingAmount = fin.pending_payments_amount ?? 0;
  const pendingCount = fin.pending_payments_count ?? 0;
  const paidCount = fin.paid_invoices_count ?? 0;
  const paidAmount = fin.paid_invoices_amount ?? 0;
  const overdueAmount = fin.overdue_payments_amount ?? 0;
  const overdueCount = fin.overdue_payments_count ?? 0;
  const refundAmount = fin.total_refunds_amount ?? 0;
  const refundCount = fin.total_refunds_count ?? 0;
  const activeSubs = fin.active_subscriptions_count ?? 0;
  const upcomingRenewals = fin.upcoming_renewals_count ?? 0;
  const monthlyTrend = fin.monthly_trend || [];
  const paymentMethods = fin.payment_methods || [];
  const recentPayments = fin.recent_payments || [];

  const maxMonthRev = Math.max(...monthlyTrend.map(m => m.revenue || 0), 1);

  // 6 Primary KPI Cards matching Requirement 2
  const kpis = [
    {
      key: 'total_revenue',
      label: 'Total Revenue',
      value: formatINR(totalRevenue),
      subtext: `Net: ${formatINR(netRevenue)} (Collected & Settled)`,
      icon: DollarSign,
      color: '#059669',
      bg: 'rgba(5, 150, 105, 0.1)',
      onClick: () => navigate('/finance/payments?status=PAID')
    },
    {
      key: 'current_month_revenue',
      label: 'Current Month Revenue',
      value: formatINR(currentMonthRevenue),
      subtext: fin.revenue_growth_pct !== undefined 
        ? `${fin.revenue_growth_pct >= 0 ? '+' : ''}${fin.revenue_growth_pct}% vs last month`
        : 'Current billing cycle',
      icon: TrendingUp,
      color: '#2563eb',
      bg: 'rgba(37, 99, 235, 0.1)',
      onClick: () => navigate('/finance/reports?type=monthly')
    },
    {
      key: 'pending_payments',
      label: 'Pending Payments',
      value: formatINR(pendingAmount),
      subtext: `${pendingCount} unpaid / partial invoice${pendingCount === 1 ? '' : 's'}`,
      icon: Clock,
      color: '#d97706',
      bg: 'rgba(217, 119, 6, 0.1)',
      onClick: () => navigate('/finance/invoices?status=unpaid')
    },
    {
      key: 'paid_invoices',
      label: 'Paid Invoices',
      value: `${paidCount} Invoices`,
      subtext: `Total Value: ${formatINR(paidAmount)}`,
      icon: CheckCircle,
      color: '#10b981',
      bg: 'rgba(16, 185, 129, 0.1)',
      onClick: () => navigate('/finance/invoices?status=paid')
    },
    {
      key: 'overdue_payments',
      label: 'Overdue Payments',
      value: formatINR(overdueAmount),
      subtext: `${overdueCount} invoice${overdueCount === 1 ? '' : 's'} past payment due date`,
      icon: AlertTriangle,
      color: '#dc2626',
      bg: 'rgba(220, 38, 38, 0.1)',
      onClick: () => navigate('/finance/invoices?status=overdue')
    },
    {
      key: 'total_refunds',
      label: 'Total Refunds',
      value: formatINR(refundAmount),
      subtext: `${refundCount} processed refund${refundCount === 1 ? '' : 's'}`,
      icon: RotateCcw,
      color: '#7c3aed',
      bg: 'rgba(124, 58, 237, 0.1)',
      onClick: () => navigate('/finance/refunds?status=PROCESSED')
    }
  ];

  return (
    <div className="finance-dashboard-wrapper" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* HEADER BAR & CONTROLS */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        backgroundColor: '#ffffff',
        padding: '16px 20px',
        borderRadius: '16px',
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            backgroundColor: 'rgba(5, 150, 105, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#059669'
          }}>
            <DollarSign size={24} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>
              Finance Department Executive Dashboard
            </h2>
            <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '2px 0 0' }}>
              Statutory GST Invoicing, Payments, Subscriptions & Revenue Tracking
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => navigate('/finance/invoices')}
            style={{
              padding: '9px 16px',
              borderRadius: '9px',
              backgroundColor: '#059669',
              color: '#ffffff',
              border: 'none',
              fontWeight: '700',
              fontSize: '0.85rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer'
            }}
          >
            <Plus size={16} />
            <span>Generate Invoice</span>
          </button>

          <button
            type="button"
            onClick={() => navigate('/finance/payments')}
            style={{
              padding: '9px 16px',
              borderRadius: '9px',
              backgroundColor: '#2563eb',
              color: '#ffffff',
              border: 'none',
              fontWeight: '700',
              fontSize: '0.85rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer'
            }}
          >
            <CreditCard size={16} />
            <span>Record Payment</span>
          </button>

          <button
            type="button"
            onClick={() => navigate('/finance/reports')}
            style={{
              padding: '9px 16px',
              borderRadius: '9px',
              backgroundColor: '#ffffff',
              color: '#475569',
              border: '1px solid #cbd5e1',
              fontWeight: '700',
              fontSize: '0.85rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer'
            }}
          >
            <FileText size={16} />
            <span>Financial Reports</span>
          </button>

          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            title="Refresh Finance Data"
            style={{
              padding: '9px 12px',
              borderRadius: '9px',
              backgroundColor: '#f8fafc',
              color: '#475569',
              border: '1px solid #cbd5e1',
              fontWeight: '700',
              fontSize: '0.85rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              cursor: refreshing ? 'not-allowed' : 'pointer',
              opacity: refreshing ? 0.7 : 1
            }}
          >
            <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* 2. 6 KPI CARDS GRID */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '16px'
      }}>
        {kpis.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <div
              key={kpi.key}
              onClick={kpi.onClick}
              style={{
                backgroundColor: '#ffffff',
                borderRadius: '16px',
                padding: '20px',
                border: '1px solid #e2e8f0',
                boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                position: 'relative'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 6px 16px rgba(0,0,0,0.08)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'none';
                e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.04)';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '14px' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: '700', color: '#64748b' }}>
                  {kpi.label}
                </span>
                <div style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '10px',
                  backgroundColor: kpi.bg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: kpi.color
                }}>
                  <Icon size={20} />
                </div>
              </div>

              <div>
                <div style={{ fontSize: '1.75rem', fontWeight: '900', color: '#0f172a', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
                  {kpi.value}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '6px', fontWeight: '600' }}>
                  {kpi.subtext}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 3. REVENUE TREND & PAYMENT BREAKDOWN */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
        gap: '20px'
      }}>
        
        {/* Monthly Revenue Trend Chart */}
        <div style={{
          backgroundColor: '#ffffff',
          borderRadius: '16px',
          padding: '22px',
          border: '1px solid #e2e8f0',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>
                Revenue Collection Trend (Past 6 Months)
              </h3>
              <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '2px 0 0' }}>
                Real revenue collected per calendar month
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigate('/finance/reports?type=monthly')}
              style={{
                border: 'none',
                background: 'none',
                color: '#2563eb',
                fontSize: '0.8rem',
                fontWeight: '700',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                cursor: 'pointer'
              }}
            >
              <span>View Full Report</span>
              <ArrowUpRight size={14} />
            </button>
          </div>

          {monthlyTrend.length === 0 ? (
            <div style={{ padding: '30px 0' }}>
              <PingoEmptyState title="No Revenue Data" description="Revenue records will appear once payments are confirmed." />
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', height: '170px', gap: '14px', paddingTop: '20px' }}>
              {monthlyTrend.map((m, idx) => {
                const heightPct = Math.max(12, Math.round((m.revenue / maxMonthRev) * 100));
                return (
                  <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                    <div style={{ fontSize: '0.72rem', fontWeight: '700', color: '#059669', marginBottom: '6px' }}>
                      {m.revenue > 0 ? (m.revenue >= 1000 ? `₹${Math.round(m.revenue / 1000)}k` : `₹${m.revenue}`) : '₹0'}
                    </div>
                    <div
                      title={`${m.month}: ${formatINR(m.revenue)} (${m.invoices} invoices)`}
                      style={{
                        width: '100%',
                        maxWidth: '44px',
                        height: `${heightPct}%`,
                        backgroundColor: idx === monthlyTrend.length - 1 ? '#059669' : '#94a3b8',
                        borderRadius: '6px 6px 0 0',
                        transition: 'height 0.4s ease'
                      }}
                    />
                    <div style={{ fontSize: '0.75rem', fontWeight: '700', color: '#64748b', marginTop: '8px' }}>
                      {m.month_short}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Payment Methods & Collection Breakdown */}
        <div style={{
          backgroundColor: '#ffffff',
          borderRadius: '16px',
          padding: '22px',
          border: '1px solid #e2e8f0',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>
                Payment Collection Modes
              </h3>
              <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '2px 0 0' }}>
                Bank Transfer, Razorpay PG, UPI, Cheques
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigate('/finance/payments')}
              style={{
                border: 'none',
                background: 'none',
                color: '#2563eb',
                fontSize: '0.8rem',
                fontWeight: '700',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                cursor: 'pointer'
              }}
            >
              <span>View All</span>
              <ChevronRight size={14} />
            </button>
          </div>

          {paymentMethods.length === 0 ? (
            <div style={{ padding: '30px 0' }}>
              <PingoEmptyState title="No Payment Modes" description="Breakdown will update as payments are received." />
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {paymentMethods.map((pm, i) => {
                const totalAll = paymentMethods.reduce((a, b) => a + (b.amount || 0), 0) || 1;
                const pct = Math.round((pm.amount / totalAll) * 100);
                return (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', fontWeight: '700' }}>
                      <span style={{ color: '#1e293b' }}>{pm.label} ({pm.count} transactions)</span>
                      <span style={{ color: '#059669' }}>{formatINR(pm.amount)} ({pct}%)</span>
                    </div>
                    <div style={{ width: '100%', height: '8px', backgroundColor: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{
                        width: `${pct}%`,
                        height: '100%',
                        backgroundColor: i === 0 ? '#059669' : (i === 1 ? '#2563eb' : '#f59e0b'),
                        borderRadius: '4px'
                      }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Quick Subscription Summary Banner */}
          <div style={{
            marginTop: '20px',
            padding: '12px 16px',
            backgroundColor: '#f8fafc',
            borderRadius: '12px',
            border: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Users size={18} color="#2563eb" />
              <span style={{ fontSize: '0.82rem', fontWeight: '700', color: '#1e293b' }}>
                Active Subscriptions: <span style={{ color: '#059669' }}>{activeSubs}</span>
              </span>
            </div>
            {upcomingRenewals > 0 && (
              <span style={{
                fontSize: '0.75rem',
                fontWeight: '800',
                padding: '3px 8px',
                borderRadius: '6px',
                backgroundColor: '#fef3c7',
                color: '#d97706'
              }}>
                {upcomingRenewals} Upcoming Renewal{upcomingRenewals === 1 ? '' : 's'}
              </span>
            )}
          </div>
        </div>

      </div>

      {/* 4. RECENT TRANSACTIONS TABLE */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '16px',
        padding: '22px',
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>
              Recent Verified Payments
            </h3>
            <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '2px 0 0' }}>
              Live payment audit trail matching bank and gateway records
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/finance/payments')}
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
              backgroundColor: '#f8fafc',
              color: '#334155',
              fontSize: '0.8rem',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <span>View All Payments</span>
            <ChevronRight size={14} />
          </button>
        </div>

        {recentPayments.length === 0 ? (
          <PingoEmptyState title="No Recent Payments" description="Payment transactions recorded by Finance will show up here." />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #f1f5f9', color: '#64748b', fontSize: '0.76rem', textTransform: 'uppercase' }}>
                  <th style={{ padding: '10px 12px' }}>Payment #</th>
                  <th style={{ padding: '10px 12px' }}>Customer / Company</th>
                  <th style={{ padding: '10px 12px' }}>Amount</th>
                  <th style={{ padding: '10px 12px' }}>Method</th>
                  <th style={{ padding: '10px 12px' }}>Reference / UTR</th>
                  <th style={{ padding: '10px 12px' }}>Status</th>
                  <th style={{ padding: '10px 12px' }}>Date</th>
                </tr>
              </thead>
              <tbody>
                {recentPayments.map((p) => (
                  <tr key={p.id} style={{ borderBottom: '1px solid #f8fafc' }}>
                    <td style={{ padding: '12px', fontWeight: '700', color: '#2563eb' }}>
                      {p.payment_number}
                    </td>
                    <td style={{ padding: '12px', fontWeight: '600', color: '#0f172a' }}>
                      {p.customer_name}
                    </td>
                    <td style={{ padding: '12px', fontWeight: '800', color: '#059669' }}>
                      {formatINR(p.amount)}
                    </td>
                    <td style={{ padding: '12px', color: '#475569' }}>
                      <span style={{
                        padding: '3px 8px',
                        borderRadius: '6px',
                        backgroundColor: p.payment_method === 'RAZORPAY' ? '#eff6ff' : '#f8fafc',
                        color: p.payment_method === 'RAZORPAY' ? '#1d4ed8' : '#334155',
                        fontWeight: '700',
                        fontSize: '0.75rem'
                      }}>
                        {p.payment_method}
                      </span>
                    </td>
                    <td style={{ padding: '12px', color: '#64748b', fontFamily: 'monospace', fontSize: '0.8rem' }}>
                      {p.transaction_reference || '—'}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '3px 9px',
                        borderRadius: '12px',
                        fontSize: '0.72rem',
                        fontWeight: '800',
                        backgroundColor: p.status === 'PAID' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                        color: p.status === 'PAID' ? '#059669' : '#dc2626'
                      }}>
                        {p.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px', color: '#64748b', fontSize: '0.78rem' }}>
                      {p.payment_date ? formatDateDDMMYYYY(p.payment_date) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
};

export default FinanceDashboard;
