import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import PingoPopupService from '../../services/pingoPopupService';
import { 
  PieChart, 
  BarChart3, 
  TrendingUp, 
  Users, 
  Award, 
  CheckCircle2, 
  ArrowUpRight,
  Download
} from 'lucide-react';

const AnalyticsPage = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalyticsData = async () => {
      try {
        const res = await API.get('/reports/dashboard');
        setStats(res.data);
      } catch (e) {
        // Fallback
      } finally {
        setLoading(false);
      }
    };
    fetchAnalyticsData();
  }, []);

  const totalLeads = stats?.total_leads || 0;
  const convertedLeads = stats?.converted_leads || 0;
  const conversionRate = totalLeads > 0 ? ((convertedLeads / totalLeads) * 100).toFixed(1) : '0.0';

  const getSourceCount = (srcKey) => {
    const list = stats?.source_lead_counts || [];
    const item = list.find(s => (s.source || '').toUpperCase().includes(srcKey.toUpperCase()));
    return item ? item.count : 0;
  };

  const metaCount = getSourceCount('META');
  const excelCount = getSourceCount('EXCEL');
  const websiteCount = getSourceCount('WEB');

  const handleExportAnalytics = () => {
    const csvContent = "data:text/csv;charset=utf-8,Metric,Value\n" +
      `Total Leads,${totalLeads}\n` +
      `Converted Leads,${convertedLeads}\n` +
      `Conversion Rate,${conversionRate}%\n` +
      `Meta Leads,${metaCount}\n` +
      `Website Leads,${websiteCount}\n` +
      `Excel Imported Leads,${excelCount}\n`;
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "CRM_Analytics_Metrics.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    PingoPopupService.triggerDownloadSuccess({
      docType: 'Report',
      fileName: 'CRM_Analytics_Metrics.csv',
      reference: 'Analytics',
      customMessage: 'Analytics report exported successfully!'
    });
  };
  const manualCount = getSourceCount('MANUAL');

  const sourceData = [
    { source: 'Meta Ads', count: metaCount, percentage: totalLeads > 0 ? Math.round((metaCount / totalLeads) * 100) : 0, color: '#7c3aed' },
    { source: 'Website Forms', count: websiteCount, percentage: totalLeads > 0 ? Math.round((websiteCount / totalLeads) * 100) : 0, color: '#0d9488' },
    { source: 'Manual Entry', count: manualCount, percentage: totalLeads > 0 ? Math.round((manualCount / totalLeads) * 100) : 0, color: '#2563eb' },
    { source: 'Excel Uploads', count: excelCount, percentage: totalLeads > 0 ? Math.round((excelCount / totalLeads) * 100) : 0, color: '#f59e0b' }
  ];

  const statusPipeline = [
    { status: 'New Leads', count: stats?.new_leads || 0, color: '#3b82f6' },
    { status: 'Contacted', count: stats?.assigned_leads || 0, color: '#06b6d4' },
    { status: 'Follow Up', count: stats?.followup_leads || 0, color: '#eab308' },
    { status: 'Qualified', count: stats?.qualified_leads || 0, color: '#8b5cf6' },
    { status: 'Converted', count: convertedLeads, color: '#10b981' }
  ];

  const topPerformers = (stats?.team_performance && stats.team_performance.length > 0)
    ? stats.team_performance.map(t => ({
        name: t.name,
        converted: t.converted || 0,
        revenue: t.revenue_formatted || ('₹ ' + Number(t.revenue || 0).toLocaleString('en-IN')),
        rate: t.leads > 0 ? `${((t.converted / t.leads) * 100).toFixed(1)}%` : '0%'
      }))
    : [];

  const sourceList = [
    { name: 'Meta Ads', count: metaCount },
    { name: 'Excel Uploads', count: excelCount },
    { name: 'Website Forms', count: websiteCount },
    { name: 'Manual Entry', count: manualCount }
  ];
  sourceList.sort((a, b) => b.count - a.count);
  const topChannel = totalLeads > 0 && sourceList[0].count > 0 ? sourceList[0] : null;

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <div style={{ fontSize: '0.82rem', color: '#64748b', marginBottom: '6px' }}>
            <Link to="/dashboard" style={{ color: '#2563eb', textDecoration: 'none' }}>Dashboard</Link> / {' '}
            <span style={{ color: '#0f172a', fontWeight: 600 }}>Analytics</span>
          </div>
          <h1 className="page-title">Advanced CRM Analytics</h1>
          <p className="page-subtitle">Visual breakdowns of lead conversion rates, channel sources, and sales performance.</p>
        </div>
        <div className="header-actions">
          <button className="btn btn-outline" onClick={handleExportAnalytics}>
            <Download size={16} />
            <span>Export Analytics Summary</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="dashboard-grid">
        <div className="stat-card">
          <div className="stat-icon icon-blue"><TrendingUp size={24} /></div>
          <div className="stat-details">
            <span className="stat-label">Overall Conversion Rate</span>
            <span className="stat-value">{conversionRate}%</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon icon-green"><CheckCircle2 size={24} /></div>
          <div className="stat-details">
            <span className="stat-label">Converted Deals</span>
            <span className="stat-value">{convertedLeads} Deals</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon icon-purple"><BarChart3 size={24} /></div>
          <div className="stat-details">
            <span className="stat-label">Avg. Response Time</span>
            <span className="stat-value">{totalLeads > 0 ? 'Instant' : 'N/A'}</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon icon-teal"><Award size={24} /></div>
          <div className="stat-details">
            <span className="stat-label">Top Channel</span>
            <span className="stat-value">{topChannel ? topChannel.name : 'None yet'}</span>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 400px), 1fr))', gap: '24px', marginBottom: '24px' }}>
        {/* Source Breakdown */}
        <div className="content-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a' }}>Lead Acquisition by Source</h3>
            <PieChart size={20} style={{ color: '#2563eb' }} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {sourceData.map(item => (
              <div key={item.source}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.88rem', fontWeight: 600, marginBottom: '6px' }}>
                  <span>{item.source}</span>
                  <span style={{ color: item.color }}>{item.count} leads ({item.percentage}%)</span>
                </div>
                <div style={{ width: '100%', height: '10px', backgroundColor: '#e2e8f0', borderRadius: '5px', overflow: 'hidden' }}>
                  <div style={{ width: `${item.percentage}%`, height: '100%', backgroundColor: item.color, borderRadius: '5px', transition: 'width 0.5s ease' }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Pipeline Funnel */}
        <div className="content-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a' }}>Lead Pipeline Funnel</h3>
            <BarChart3 size={20} style={{ color: '#10b981' }} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {statusPipeline.map(pipe => (
              <div key={pipe.status}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.88rem', fontWeight: 600, marginBottom: '6px' }}>
                  <span>{pipe.status}</span>
                  <span style={{ color: pipe.color }}>{pipe.count} leads</span>
                </div>
                <div style={{ width: '100%', height: '10px', backgroundColor: '#e2e8f0', borderRadius: '5px', overflow: 'hidden' }}>
                  <div style={{ width: `${(pipe.count / 240) * 100}%`, height: '100%', backgroundColor: pipe.color, borderRadius: '5px', transition: 'width 0.5s ease' }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top Performers Leaderboard */}
      <div className="content-card">
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a', marginBottom: '16px' }}>Sales Team Leaderboard</h3>
        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Sales Representative</th>
                <th>Deals Converted</th>
                <th>Pipeline Value</th>
                <th>Conversion Rate</th>
              </tr>
            </thead>
            <tbody>
              {topPerformers.map((agent, index) => (
                <tr key={agent.name}>
                  <td>
                    <span className="role-badge role-admin" style={{ backgroundColor: index === 0 ? '#fef3c7' : '#f1f5f9', color: index === 0 ? '#d97706' : '#475569', border: 'none', fontWeight: 800 }}>
                      #{index + 1}
                    </span>
                  </td>
                  <td style={{ fontWeight: 700, color: '#0f172a' }}>{agent.name}</td>
                  <td style={{ fontWeight: 600 }}>{agent.converted} Converted</td>
                  <td style={{ fontWeight: 600, color: '#10b981' }}>{agent.revenue}</td>
                  <td>
                    <span className="role-badge role-employee">{agent.rate}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsPage;
