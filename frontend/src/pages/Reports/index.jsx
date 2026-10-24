import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import PingoPopupService from '../../services/pingoPopupService';
import { 
  BarChart3, 
  PieChart, 
  TrendingUp, 
  Users, 
  Award, 
  CheckCircle2, 
  Download,
  Clock,
  Layers,
  FileSpreadsheet
} from 'lucide-react';

const Reports = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchReportData = async () => {
    try {
      setLoading(true);
      const res = await API.get('/reports/dashboard');
      if (res.data) setStats(res.data);
    } catch (err) {
      console.error("Failed to load report data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReportData();
  }, []);

  const totalLeads = stats?.total_leads || 0;
  const convertedLeads = stats?.converted_leads || 0;
  const conversionRate = totalLeads > 0 ? ((convertedLeads / totalLeads) * 100).toFixed(1) : '0.0';

  // Real source breakdown directly from database
  const getSourceCount = (srcKey) => {
    const list = stats?.source_lead_counts || [];
    const item = list.find(s => (s.source || '').toUpperCase().includes(srcKey.toUpperCase()));
    return item ? item.count : 0;
  };

  const metaCount = getSourceCount('META');
  const excelCount = getSourceCount('EXCEL');
  const websiteCount = getSourceCount('WEB');
  const manualCount = getSourceCount('MANUAL');
  const othersCount = Math.max(0, totalLeads - (metaCount + excelCount + websiteCount + manualCount));

  const sourceBreakdown = [
    { source: 'Meta Ads', count: metaCount, color: '#2563eb' },
    { source: 'Excel Import', count: excelCount, color: '#10b981' },
    { source: 'Website Forms', count: websiteCount, color: '#8b5cf6' },
    { source: 'Quick Add', count: manualCount, color: '#f59e0b' },
    { source: 'Others', count: othersCount, color: '#94a3b8' }
  ];

  // Real Pipeline Stages
  const pipelineStages = [
    { stage: 'New Leads', count: stats?.new_leads || 0, color: '#2563eb' },
    { stage: 'Contacted', count: stats?.assigned_leads || 0, color: '#7c3aed' },
    { stage: 'Qualified', count: stats?.qualified_leads || 0, color: '#10b981' },
    { stage: 'Follow-up', count: stats?.followup_leads || 0, color: '#f59e0b' },
    { stage: 'Converted', count: convertedLeads, color: '#059669' }
  ];

  // Real Employee performance breakdown
  const employeePerformance = (stats?.team_performance && stats.team_performance.length > 0)
    ? stats.team_performance.map(t => ({
        employee_name: t.name,
        count: t.leads || 0,
        converted: t.converted || 0,
        rate: t.leads > 0 ? `${((t.converted / t.leads) * 100).toFixed(1)}%` : '0%'
      }))
    : (stats?.employee_lead_counts && stats.employee_lead_counts.length > 0)
      ? stats.employee_lead_counts.map(e => ({
          employee_name: e.employee_name,
          count: e.count || 0,
          converted: 0,
          rate: '0%'
        }))
      : [];

  // Determine top channel dynamically
  const sourceList = [
    { name: 'Meta Ads', count: metaCount },
    { name: 'Excel Import', count: excelCount },
    { name: 'Website Forms', count: websiteCount },
    { name: 'Quick Add', count: manualCount },
    { name: 'Others', count: othersCount }
  ];
  sourceList.sort((a, b) => b.count - a.count);
  const topChannel = totalLeads > 0 && sourceList[0].count > 0 ? sourceList[0] : null;

  // Export handler simulation
  const handleExportReport = () => {
    const csvContent = "data:text/csv;charset=utf-8,Category,Value\nTotal Leads," + totalLeads + "\nConverted Leads," + convertedLeads + "\nFollow-up Leads," + (stats?.followup_leads || 0);
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "CRM_Reports_Analytics_Summary.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    PingoPopupService.triggerDownloadSuccess({
      docType: 'Report',
      fileName: 'CRM_Reports_Analytics_Summary.csv',
      reference: 'Summary Report',
      customMessage: 'Summary Report CSV exported successfully!'
    });
  };

  return (
    <div className="page-container" style={{ paddingBottom: '40px' }}>
      {/* Page Header */}
      <div className="page-header" style={{ marginBottom: '24px' }}>
        <div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
            <Link to="/dashboard" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Dashboard</Link> / {' '}
            <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>Reports & Analytics</span>
          </div>
          <h1 className="page-title" style={{ fontSize: '1.6rem', fontWeight: '800', margin: 0 }}>Reports & Analytics</h1>
          <p className="page-subtitle" style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Comprehensive insights on lead acquisition channels, conversion funnels, and sales team productivity.
          </p>
        </div>
        <div className="header-actions">
          <button className="btn btn-outline" onClick={handleExportReport} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Download size={16} />
            <span>Export Summary Report</span>
          </button>
        </div>
      </div>

      {/* Top Metric KPI Row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '16px',
        marginBottom: '24px'
      }}>
        <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
          <div style={{ width: '46px', height: '46px', borderRadius: '14px', backgroundColor: 'rgba(37, 99, 235, 0.12)', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <TrendingUp size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Overall Conversion Rate</div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', lineHeight: '1.2' }}>{conversionRate}%</div>
            <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: '600', marginTop: '4px' }}>
              {totalLeads > 0 ? `${convertedLeads} of ${totalLeads} leads` : '0 conversions recorded'}
            </div>
          </div>
        </div>

        <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
          <div style={{ width: '46px', height: '46px', borderRadius: '14px', backgroundColor: 'rgba(16, 185, 129, 0.12)', color: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <CheckCircle2 size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Converted Deals</div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', lineHeight: '1.2' }}>{convertedLeads.toLocaleString()}</div>
            <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: '600', marginTop: '4px' }}>
              {convertedLeads > 0 ? 'Closed Deals' : '0 deals converted'}
            </div>
          </div>
        </div>

        <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
          <div style={{ width: '46px', height: '46px', borderRadius: '14px', backgroundColor: 'rgba(139, 92, 246, 0.12)', color: '#8b5cf6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Clock size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Avg. Response Time</div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', lineHeight: '1.2' }}>{totalLeads > 0 ? 'Instant' : 'N/A'}</div>
            <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: '600', marginTop: '4px' }}>Direct Realtime Sync</div>
          </div>
        </div>

        <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
          <div style={{ width: '46px', height: '46px', borderRadius: '14px', backgroundColor: 'rgba(245, 158, 11, 0.12)', color: '#f59e0b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Award size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Top Acquisition Channel</div>
            <div style={{ fontSize: '1.3rem', fontWeight: '800', color: '#0f172a', lineHeight: '1.2' }}>{topChannel ? topChannel.name : 'None yet'}</div>
            <div style={{ fontSize: '0.72rem', color: '#2563eb', fontWeight: '700', marginTop: '4px' }}>
              {topChannel ? `${Math.round((topChannel.count / totalLeads) * 100)}% of total leads` : '0% of total leads'}
            </div>
          </div>
        </div>
      </div>

      {/* Main Charts & Breakdown Section (2 Columns Grid) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 420px), 1fr))',
        gap: '20px',
        marginBottom: '24px'
      }}>
        {/* CARD 1: LEAD ACQUISITION BY SOURCE */}
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column', height: '100%', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <PieChart size={20} style={{ color: '#2563eb' }} /> Lead Acquisition by Source
            </h3>
            <span style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>{totalLeads.toLocaleString()} Total Leads</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1, justifyContent: 'center' }}>
            {sourceBreakdown.map((item) => {
              const count = item.count || 0;
              const pct = totalLeads > 0 ? Math.round((count / totalLeads) * 100) : 0;
              return (
                <div key={item.source || item.name}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: '700', marginBottom: '6px' }}>
                    <span style={{ color: '#334155' }}>{item.source || item.name}</span>
                    <span style={{ color: '#0f172a' }}>{count} leads <span style={{ color: '#94a3b8', fontWeight: '500' }}>({pct}%)</span></span>
                  </div>
                  <div style={{ width: '100%', height: '10px', backgroundColor: '#f1f5f9', borderRadius: '6px', overflow: 'hidden' }}>
                    <div style={{ width: `${pct}%`, height: '100%', backgroundColor: item.color || '#2563eb', borderRadius: '6px', transition: 'width 0.4s ease' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* CARD 2: PIPELINE STATUS BREAKDOWN */}
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column', height: '100%', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <BarChart3 size={20} style={{ color: '#10b981' }} /> Lead Pipeline Funnel Status
            </h3>
            <span style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>5 Active Stages</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1, justifyContent: 'center' }}>
            {pipelineStages.map((stg) => {
              const pct = totalLeads > 0 ? Math.round((stg.count / totalLeads) * 100) : 0;
              return (
                <div key={stg.stage}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: '700', marginBottom: '6px' }}>
                    <span style={{ color: '#334155' }}>{stg.stage}</span>
                    <span style={{ color: stg.color }}>{stg.count.toLocaleString()} <span style={{ color: '#94a3b8', fontWeight: '500' }}>({pct}%)</span></span>
                  </div>
                  <div style={{ width: '100%', height: '10px', backgroundColor: '#f1f5f9', borderRadius: '6px', overflow: 'hidden' }}>
                    <div style={{ width: `${pct}%`, height: '100%', backgroundColor: stg.color, borderRadius: '6px', transition: 'width 0.4s ease' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Sales Team Leaderboard & Productivity */}
      <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Award size={20} style={{ color: '#f59e0b' }} /> Sales Team Productivity & Conversion Leaderboard
          </h3>
          <span style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Updated Today</span>
        </div>

        <div className="table-responsive">
          <table className="custom-table" style={{ width: '100%', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                <th style={{ padding: '10px 12px' }}>Rank</th>
                <th style={{ padding: '10px 12px' }}>Employee Name</th>
                <th style={{ padding: '10px 12px' }}>Assigned Leads</th>
                <th style={{ padding: '10px 12px' }}>Converted Leads</th>
                <th style={{ padding: '10px 12px' }}>Conversion Share</th>
              </tr>
            </thead>
            <tbody>
              {employeePerformance.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '32px', color: '#94a3b8' }}>
                    No sales team performance recorded yet.
                  </td>
                </tr>
              ) : (
                employeePerformance.map((emp, idx) => {
                  const assignedCount = emp.count || emp.assigned_count || 0;
                  const convCount = emp.converted || 0;
                  const convRate = emp.rate || `${assignedCount > 0 ? ((convCount / assignedCount) * 100).toFixed(1) : 0}%`;
                return (
                  <tr key={emp.employee_name || idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '3px 10px',
                        borderRadius: '12px',
                        fontSize: '0.75rem',
                        fontWeight: '800',
                        backgroundColor: idx === 0 ? '#fef3c7' : idx === 1 ? '#e0f2fe' : '#f1f5f9',
                        color: idx === 0 ? '#d97706' : idx === 1 ? '#0284c7' : '#475569'
                      }}>
                        #{idx + 1}
                      </span>
                    </td>
                    <td style={{ padding: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{
                          width: '28px', height: '28px', borderRadius: '50%',
                          backgroundColor: '#3b82f6', color: '#ffffff',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: '0.78rem', fontWeight: '700'
                        }}>
                          {(emp.employee_name || 'E')[0]}
                        </div>
                        <strong>{emp.employee_name}</strong>
                      </div>
                    </td>
                    <td style={{ padding: '12px' }}>{assignedCount} leads</td>
                    <td style={{ padding: '12px', fontWeight: '700', color: '#059669' }}>{convCount} converted</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '3px 10px',
                        borderRadius: '10px',
                        fontSize: '0.75rem',
                        fontWeight: '700',
                        backgroundColor: '#d1fae5',
                        color: '#047857'
                      }}>
                        {convRate}
                      </span>
                    </td>
                  </tr>
                );
              }))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Reports;
