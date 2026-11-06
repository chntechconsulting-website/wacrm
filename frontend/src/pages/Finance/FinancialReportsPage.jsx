import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import {
  FileText,
  Download,
  Calendar,
  Filter,
  ArrowUpRight,
  Printer,
  Table,
  CheckCircle,
  TrendingUp,
  CreditCard,
  ShieldCheck,
  RotateCcw
} from 'lucide-react';
import { formatDateDDMMYYYY } from '../../utils/dateUtils';
import PingoEmptyState from '../../components/Common/PingoEmptyState';

const formatINR = (val) => {
  const num = Number(val || 0);
  return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 2 });
};

const FinancialReportsPage = () => {
  const [reportType, setReportType] = useState('monthly');
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [dateRange, setDateRange] = useState({
    start_date: '',
    end_date: ''
  });

  const reportsConfig = [
    { id: 'daily', label: 'Daily Revenue', desc: 'Day-by-day revenue collection stream' },
    { id: 'monthly', label: 'Monthly Revenue', desc: 'Month-by-month revenue, transactions & trend' },
    { id: 'yearly', label: 'Yearly Revenue', desc: 'Annual turnover & historic comparison' },
    { id: 'collections', label: 'Payment Collections', desc: 'Collections grouped by payment mode (UPI, Razorpay, Bank)' },
    { id: 'gst', label: 'Statutory GST Report', desc: 'Taxable turnover, Intra (CGST+SGST) vs Inter (IGST), GSTIN' },
    { id: 'refunds', label: 'Refunds Audit Report', desc: 'Disbursements, reversals and processing history' }
  ];

  const fetchReport = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await API.get('/finance/reports', {
        params: {
          type: reportType,
          start_date: dateRange.start_date || undefined,
          end_date: dateRange.end_date || undefined
        }
      });
      if (res.data) {
        setReportData(res.data);
      }
    } catch (err) {
      console.error('Failed to load report:', err);
      setError('Unable to load report data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [reportType, dateRange.start_date, dateRange.end_date]);

  const handleExportCsv = () => {
    const params = new URLSearchParams({ type: reportType });
    if (dateRange.start_date) params.append('start_date', dateRange.start_date);
    if (dateRange.end_date) params.append('end_date', dateRange.end_date);
    window.open(`/api/finance/reports/export-csv?${params.toString()}`, '_blank');
  };

  const handlePrint = () => {
    window.print();
  };

  const rows = reportData?.rows || [];

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
            <FileText size={22} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>
              Financial Reports Suite
            </h1>
            <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '2px 0 0' }}>
              Statutory GST returns, revenue aggregation, collections & CSV/PDF exports
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={handleExportCsv}
            style={{
              padding: '9px 16px',
              borderRadius: '8px',
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
            <Download size={16} />
            <span>Export to Excel / CSV</span>
          </button>

          <button
            type="button"
            onClick={handlePrint}
            style={{
              padding: '9px 16px',
              borderRadius: '8px',
              backgroundColor: '#ffffff',
              color: '#334155',
              border: '1px solid #cbd5e1',
              fontWeight: '700',
              fontSize: '0.85rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer'
            }}
          >
            <Printer size={16} />
            <span>Print Report</span>
          </button>
        </div>
      </div>

      {/* 2. REPORT TYPE TABS */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '10px',
        marginBottom: '20px'
      }}>
        {reportsConfig.map((cfg) => {
          const isActive = reportType === cfg.id;
          return (
            <div
              key={cfg.id}
              onClick={() => setReportType(cfg.id)}
              style={{
                backgroundColor: isActive ? '#0f172a' : '#ffffff',
                color: isActive ? '#ffffff' : '#0f172a',
                padding: '14px',
                borderRadius: '12px',
                border: `1px solid ${isActive ? '#0f172a' : '#e2e8f0'}`,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                boxShadow: isActive ? '0 4px 12px rgba(15, 23, 42, 0.15)' : 'none'
              }}
            >
              <div style={{ fontWeight: '800', fontSize: '0.86rem', marginBottom: '2px' }}>
                {cfg.label}
              </div>
              <div style={{ fontSize: '0.72rem', color: isActive ? '#94a3b8' : '#64748b', lineHeight: 1.3 }}>
                {cfg.desc}
              </div>
            </div>
          );
        })}
      </div>

      {/* 3. REPORT CONTENT CARD */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '16px',
        border: '1px solid #e2e8f0',
        padding: '24px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', borderBottom: '1px solid #f1f5f9', paddingBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: '800', color: '#0f172a' }}>
              {reportData?.title || 'Report Table'}
            </h3>
            <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
              Generated on {new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
            </span>
          </div>

          {/* Totals Summary */}
          {reportData?.total_revenue !== undefined && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 14px', backgroundColor: '#f0fdf4', borderRadius: '8px', border: '1px solid #bbf7d0' }}>
              <span style={{ fontSize: '0.8rem', color: '#166534', fontWeight: '700' }}>Total Revenue:</span>
              <span style={{ fontSize: '1.05rem', color: '#15803d', fontWeight: '900' }}>{formatINR(reportData.total_revenue)}</span>
            </div>
          )}
          {reportData?.total_amount !== undefined && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 14px', backgroundColor: '#f0fdf4', borderRadius: '8px', border: '1px solid #bbf7d0' }}>
              <span style={{ fontSize: '0.8rem', color: '#166534', fontWeight: '700' }}>Gross Invoiced Total:</span>
              <span style={{ fontSize: '1.05rem', color: '#15803d', fontWeight: '900' }}>{formatINR(reportData.total_amount)}</span>
            </div>
          )}
        </div>

        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
            <div className="spinner" style={{ margin: '0 auto 12px', width: '32px', height: '32px', border: '3px solid #e2e8f0', borderTopColor: '#059669', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            <p style={{ margin: 0, fontWeight: '600', fontSize: '0.9rem' }}>Aggregating financial data...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '30px', textAlign: 'center', color: '#dc2626' }}>{error}</div>
        ) : rows.length === 0 ? (
          <PingoEmptyState title="No Records in Selected Period" description="Transactions matching this criteria will populate here automatically." />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0', backgroundColor: '#f8fafc', color: '#475569', fontSize: '0.76rem', textTransform: 'uppercase' }}>
                  {Object.keys(rows[0]).map((colKey) => (
                    <th key={colKey} style={{ padding: '10px 14px', fontWeight: '800' }}>
                      {colKey.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    {Object.entries(row).map(([k, v], cellIdx) => {
                      const isMoney = ['revenue', 'subtotal', 'cgst', 'sgst', 'igst', 'tax_total', 'grand_total', 'amount'].includes(k.toLowerCase());
                      return (
                        <td key={cellIdx} style={{ padding: '12px 14px', fontWeight: isMoney ? '700' : '500', color: isMoney ? '#059669' : '#0f172a' }}>
                          {isMoney ? formatINR(v) : (v || '—')}
                        </td>
                      );
                    })}
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

export default FinancialReportsPage;
