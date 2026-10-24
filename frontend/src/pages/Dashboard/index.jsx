import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { 
  Users, 
  TrendingUp, 
  Clock, 
  UserCheck, 
  XCircle, 
  Plus, 
  PhoneCall, 
  Calendar, 
  Layers, 
  ArrowUpRight, 
  MessageCircle, 
  CheckCircle,
  FileText,
  Filter,
  Check,
  Award,
  ChevronDown
} from 'lucide-react';
import { formatDateDDMMYYYY, formatTime12Hour, formatLocalDateTime } from '../../utils/dateUtils';
import PingoMascot from '../../components/Common/PingoMascot';
import PingoEmptyState from '../../components/Common/PingoEmptyState';

const Dashboard = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [recentLeads, setRecentLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  // Time filters
  const [overviewFilter, setOverviewFilter] = useState('This Month');
  const [sourceFilter, setSourceFilter] = useState('This Month');
  const [funnelFilter, setFunnelFilter] = useState('All Leads');
  const [teamFilter, setTeamFilter] = useState('This Month');

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [statsRes, leadsRes] = await Promise.all([
        API.get('/reports/dashboard').catch(() => ({ data: null })),
        API.get('/leads/?limit=5').catch(() => ({ data: { items: [] } }))
      ]);

      if (statsRes.data) setStats(statsRes.data);
      if (leadsRes.data?.items) setRecentLeads(leadsRes.data.items);
    } catch (err) {
      console.error("Dashboard data fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const userName = user?.employee_name || user?.name || user?.username || 'Chandra Mohan';

  // Dynamic time-of-day greeting (Good Morning, Good Afternoon, Good Evening)
  const greeting = (() => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good Morning';
    if (hour < 17) return 'Good Afternoon';
    return 'Good Evening';
  })();

  const isEmployeeRole = user?.role?.toUpperCase() === 'EMPLOYEE';

  // Calculated KPI numbers - strictly live from backend database
  const totalLeadsCount = stats?.total_leads ?? 0;
  const newLeadsCount = stats?.new_leads ?? 0;
  const contactedCount = stats?.contacted_leads !== undefined 
    ? stats.contacted_leads 
    : (stats?.connected_calls ? Math.min(stats.connected_calls, totalLeadsCount) : 0);
  const connectedCallsCount = stats?.connected_calls ?? 0;
  const followupsCount = stats?.followup_leads ?? 0;
  const convertedCount = stats?.converted_leads ?? 0;
  const lostCount = stats?.lost_leads ?? 0;

  // Source breakdown calculation directly from database counts
  const sourceLeadCounts = stats?.source_lead_counts || [];
  const getSourceCount = (srcKey) => {
    return sourceLeadCounts
      .filter(item => (item.source || '').toUpperCase().includes(srcKey.toUpperCase()))
      .reduce((acc, curr) => acc + (curr.count || 0), 0);
  };

  const metaCount = getSourceCount('META');
  const excelCount = getSourceCount('EXCEL');
  const websiteCount = getSourceCount('WEB');
  const manualCount = getSourceCount('MANUAL');
  const knownTotal = metaCount + excelCount + websiteCount + manualCount;
  const othersCount = Math.max(0, totalLeadsCount - knownTotal);

  const sourceBreakdown = [
    { name: 'Meta Ads', count: metaCount, percentage: totalLeadsCount > 0 ? Math.round((metaCount / totalLeadsCount) * 100) : 0, color: '#2563eb' },
    { name: 'Excel Import', count: excelCount, percentage: totalLeadsCount > 0 ? Math.round((excelCount / totalLeadsCount) * 100) : 0, color: '#10b981' },
    { name: 'Website', count: websiteCount, percentage: totalLeadsCount > 0 ? Math.round((websiteCount / totalLeadsCount) * 100) : 0, color: '#8b5cf6' },
    { name: 'Manual', count: manualCount, percentage: totalLeadsCount > 0 ? Math.round((manualCount / totalLeadsCount) * 100) : 0, color: '#f59e0b' },
    { name: 'Others', count: othersCount, percentage: totalLeadsCount > 0 ? Math.round((othersCount / totalLeadsCount) * 100) : 0, color: '#94a3b8' }
  ];

  // Helper to extract stage counts dynamically based on funnel filter (All Leads vs Meta Leads)
  const activeStatusCounts = funnelFilter === 'Meta Leads' 
    ? (stats?.meta_status_lead_counts || []) 
    : (stats?.status_lead_counts || []);

  const getStatusSum = (filterFn) => {
    return activeStatusCounts
      .filter(item => filterFn((item.status || '').toUpperCase()))
      .reduce((acc, curr) => acc + (curr.count || 0), 0);
  };

  const funnelNewCount = funnelFilter === 'Meta Leads'
    ? getStatusSum(s => s === 'NEW' || s === 'NEW LEAD' || s.startsWith('NEW'))
    : newLeadsCount;

  const funnelContactedCount = funnelFilter === 'Meta Leads'
    ? getStatusSum(s => s === 'CONTACTED' || s.includes('CONTACT'))
    : contactedCount;

  const funnelInterestedCount = funnelFilter === 'Meta Leads'
    ? getStatusSum(s => s === 'INTERESTED' || s === 'QUALIFIED')
    : (stats?.qualified_leads ?? 0);

  const funnelProposalCount = funnelFilter === 'Meta Leads'
    ? getStatusSum(s => s === 'PROPOSAL SENT' || s.includes('PROPOSAL'))
    : (stats?.proposal_leads ?? 0);

  const funnelFollowupCount = funnelFilter === 'Meta Leads'
    ? getStatusSum(s => s === 'FOLLOW_UP' || s === 'FOLLOW-UP' || s.includes('FOLLOW'))
    : followupsCount;

  const funnelConvertedCount = funnelFilter === 'Meta Leads'
    ? getStatusSum(s => s === 'CONVERTED' || s === 'WON')
    : convertedCount;

  const funnelTotalDenominator = funnelFilter === 'Meta Leads'
    ? activeStatusCounts.reduce((acc, curr) => acc + (curr.count || 0), 0)
    : totalLeadsCount;

  const calcPercentage = (count) => {
    if (!funnelTotalDenominator || funnelTotalDenominator <= 0) return 0;
    return Math.min(100, Math.round((count / funnelTotalDenominator) * 100));
  };

  // Lead status funnel levels formatted cleanly
  const funnelStages = isEmployeeRole ? [
    { label: 'Assigned Leads', count: funnelTotalDenominator, percentage: funnelTotalDenominator > 0 ? 100 : 0, color: '#2563eb' },
    { label: 'Contacted', count: funnelContactedCount, percentage: calcPercentage(funnelContactedCount), color: '#7c3aed' },
    { label: 'Proposal Sent', count: funnelProposalCount, percentage: calcPercentage(funnelProposalCount), color: '#3b82f6' },
    { label: 'Follow-up', count: funnelFollowupCount, percentage: calcPercentage(funnelFollowupCount), color: '#f59e0b' },
    { label: 'Converted', count: funnelConvertedCount, percentage: calcPercentage(funnelConvertedCount), color: '#10b981' }
  ] : [
    { label: 'New Leads', count: funnelNewCount, percentage: calcPercentage(funnelNewCount), color: '#2563eb' },
    { label: 'Contacted', count: funnelContactedCount, percentage: calcPercentage(funnelContactedCount), color: '#7c3aed' },
    { label: 'Interested', count: funnelInterestedCount, percentage: calcPercentage(funnelInterestedCount), color: '#10b981' },
    { label: 'Proposal Sent', count: funnelProposalCount, percentage: calcPercentage(funnelProposalCount), color: '#3b82f6' },
    { label: 'Follow-up', count: funnelFollowupCount, percentage: calcPercentage(funnelFollowupCount), color: '#f59e0b' },
    { label: 'Converted', count: funnelConvertedCount, percentage: calcPercentage(funnelConvertedCount), color: '#ef4444' }
  ];

  // Real Follow-up reminders from database
  const followupReminders = stats?.upcoming_followups?.length ? stats.upcoming_followups : [];

  // Real Activities from database
  const todayActivities = stats?.today_activities?.length ? stats.today_activities : [];

  // Real Top Performing Team members from database
  const teamMembers = stats?.team_performance?.length ? stats.team_performance : [];

  const getSourceBadgeColor = (src) => {
    const s = (src || '').toUpperCase();
    if (s.includes('META')) return { bg: '#eff6ff', color: '#2563eb' };
    if (s.includes('WEB')) return { bg: '#f0fdf4', color: '#16a34a' };
    if (s.includes('EXCEL')) return { bg: '#fefce8', color: '#ca8a04' };
    return { bg: '#f8fafc', color: '#475569' };
  };

  const getStatusBadgeColor = (st) => {
    const s = (st || '').toUpperCase();
    if (s.includes('NEW')) return { bg: '#eff6ff', color: '#2563eb' };
    if (s.includes('FOLLOW')) return { bg: '#fef3c7', color: '#d97706' };
    if (s.includes('INTERESTED')) return { bg: '#ecfdf5', color: '#059669' };
    if (s.includes('CONVERTED') || s.includes('WON')) return { bg: '#d1fae5', color: '#047857' };
    return { bg: '#f1f5f9', color: '#64748b' };
  };

  return (
    <div className="page-container" style={{ paddingBottom: '40px' }}>
      
      {/* 1. GREETING BANNER */}
      <div className="dashboard-greeting-banner">
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
          <img 
            src="/wa-crm-logo-transparent.png" 
            alt="WA! CRM Logo" 
            style={{
              height: '48px',
              width: 'auto',
              maxWidth: '190px',
              objectFit: 'contain',
              borderRadius: '10px',
              filter: 'drop-shadow(0 3px 8px rgba(0, 0, 0, 0.08))',
              display: 'block'
            }}
          />
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <h1 style={{ fontSize: '1.75rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>
                {greeting}, <span style={{ color: '#1e40af' }}>{userName}</span>
              </h1>
              <span style={{ fontSize: '1.75rem' }}>👋</span>
            </div>
            <p style={{ color: '#475569', fontSize: '0.95rem', margin: 0, fontWeight: '500' }}>
              Here's what's happening with your CRM today.
            </p>
          </div>
        </div>

        {/* Right Graphic Badge with Pingo */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '14px',
          background: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(8px)',
          padding: '10px 18px',
          borderRadius: '16px',
          border: '1px solid rgba(255, 255, 255, 0.9)',
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.04)',
          flexWrap: 'wrap'
        }}>
          <PingoMascot pose="salute" height={68} withShadow={false} />
          <div>
            <div style={{ fontSize: '0.86rem', fontWeight: '700', color: '#1e293b' }}>
              “ More conversations, More opportunities,
            </div>
            <div style={{ fontSize: '0.86rem', fontWeight: '800', color: '#2563eb' }}>
              Better business. ”
            </div>
          </div>
        </div>
      </div>

      {/* 2. TOP METRIC CARDS GRID (6 KPI CARDS) */}
      <div className="dashboard-kpi-grid">
        {/* Total Leads */}
        <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
          <div style={{
            width: '46px', height: '46px', borderRadius: '14px',
            backgroundColor: 'rgba(59, 130, 246, 0.12)', color: '#2563eb',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
          }}>
            <Users size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>
              {user?.role?.toUpperCase() === 'EMPLOYEE' ? 'Assigned Leads' : 'Total Leads'}
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', lineHeight: '1.2' }}>
              {totalLeadsCount.toLocaleString()}
            </div>
          </div>
        </div>

        {/* New Leads */}
        <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
          <div style={{
            width: '46px', height: '46px', borderRadius: '14px',
            backgroundColor: 'rgba(16, 185, 129, 0.12)', color: '#10b981',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
          }}>
            <Plus size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>
              {user?.role?.toUpperCase() === 'EMPLOYEE' ? 'My New Leads' : 'New Leads'}
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', lineHeight: '1.2' }}>
              {newLeadsCount.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Connected Calls */}
        <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
          <div style={{
            width: '46px', height: '46px', borderRadius: '14px',
            backgroundColor: 'rgba(139, 92, 246, 0.12)', color: '#8b5cf6',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
          }}>
            <PhoneCall size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>
              {user?.role?.toUpperCase() === 'EMPLOYEE' ? 'My Calls' : 'Connected Calls'}
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', lineHeight: '1.2' }}>
              {connectedCallsCount.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Follow-ups */}
        <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
          <div style={{
            width: '46px', height: '46px', borderRadius: '14px',
            backgroundColor: 'rgba(245, 158, 11, 0.12)', color: '#f59e0b',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
          }}>
            <Clock size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>
              {user?.role?.toUpperCase() === 'EMPLOYEE' ? 'My Follow-ups' : 'Follow-ups'}
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', lineHeight: '1.2' }}>
              {followupsCount.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Converted Leads */}
        <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
          <div style={{
            width: '46px', height: '46px', borderRadius: '14px',
            backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#059669',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
          }}>
            <CheckCircle size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>{isEmployeeRole ? 'My Converted' : 'Converted Leads'}</div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', lineHeight: '1.2' }}>
              {convertedCount.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Lost Leads */}
        <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
          <div style={{
            width: '46px', height: '46px', borderRadius: '14px',
            backgroundColor: 'rgba(239, 68, 68, 0.12)', color: '#ef4444',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
          }}>
            <XCircle size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>{isEmployeeRole ? 'My Lost' : 'Lost Leads'}</div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', lineHeight: '1.2' }}>
              {lostCount.toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      {/* 3. ROW 2: CHARTS & FUNNEL (3 COLUMNS GRID) */}
      <div className="dashboard-charts-grid">
        {/* CARD 1: LEADS OVERVIEW CHART */}
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column', height: '100%', boxSizing: 'border-box', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', gap: '8px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px', whiteSpace: 'nowrap', flexShrink: 0 }}>
              <TrendingUp size={20} style={{ color: '#2563eb', flexShrink: 0 }} />
              <span>Leads Overview</span>
            </h3>
            <select 
              value={overviewFilter} 
              onChange={(e) => setOverviewFilter(e.target.value)}
              style={{
                fontSize: '0.78rem', fontWeight: '600', padding: '4px 10px',
                borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', cursor: 'pointer',
                width: 'auto', maxWidth: '125px', flexShrink: 0
              }}
            >
              <option value="This Month">This Month</option>
              <option value="Last Month">Last Month</option>
              <option value="This Quarter">This Quarter</option>
            </select>
          </div>

          {/* Chart Legend */}
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '14px', fontSize: '0.75rem', fontWeight: '600' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#2563eb', flexShrink: 0 }} />
              <span style={{ color: '#475569' }}>New Leads</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#8b5cf6', flexShrink: 0 }} />
              <span style={{ color: '#475569' }}>Follow-ups</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#10b981', flexShrink: 0 }} />
              <span style={{ color: '#475569' }}>Converted</span>
            </div>
          </div>

          {/* Curved Interactive SVG Chart & Axis */}
          <div style={{ width: '100%', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', minHeight: '190px' }}>
            {totalLeadsCount === 0 ? (
              <div style={{ textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem', padding: '24px 0' }}>
                <TrendingUp size={36} style={{ color: '#cbd5e1', margin: '0 auto 8px auto', display: 'block' }} />
                <div style={{ fontWeight: '600' }}>No lead trend activity recorded yet.</div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '4px' }}>Trends will populate automatically as leads are added.</div>
              </div>
            ) : (
              <>
                <div style={{ width: '100%', height: '160px', position: 'relative' }}>
                  <svg viewBox="0 0 500 170" style={{ width: '100%', height: '100%' }}>
                    <defs>
                      <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#2563eb" stopOpacity="0.25" />
                        <stop offset="100%" stopColor="#2563eb" stopOpacity="0.0" />
                      </linearGradient>
                      <linearGradient id="greenGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
                        <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    {/* Grid Lines */}
                    <line x1="0" y1="35" x2="500" y2="35" stroke="#f1f5f9" strokeDasharray="4 4" />
                    <line x1="0" y1="70" x2="500" y2="70" stroke="#f1f5f9" strokeDasharray="4 4" />
                    <line x1="0" y1="105" x2="500" y2="105" stroke="#f1f5f9" strokeDasharray="4 4" />
                    <line x1="0" y1="140" x2="500" y2="140" stroke="#f1f5f9" strokeDasharray="4 4" />

                    {/* Converted Green Line & Area */}
                    <path d="M 0 130 Q 80 110 160 120 T 320 100 T 500 70 L 500 160 L 0 160 Z" fill="url(#greenGrad)" />
                    <path d="M 0 130 Q 80 110 160 120 T 320 100 T 500 70" fill="none" stroke="#10b981" strokeWidth="3" />

                    {/* Follow-ups Purple Line */}
                    <path d="M 0 100 Q 80 70 160 85 T 320 65 T 500 35" fill="none" stroke="#8b5cf6" strokeWidth="3" />

                    {/* New Leads Blue Line & Area */}
                    <path d="M 0 140 Q 80 90 160 110 T 320 80 T 500 45 L 500 160 L 0 160 Z" fill="url(#blueGrad)" />
                    <path d="M 0 140 Q 80 90 160 110 T 320 80 T 500 45" fill="none" stroke="#2563eb" strokeWidth="3" />

                    {/* Data points */}
                    <circle cx="160" cy="110" r="4" fill="#2563eb" />
                    <circle cx="320" cy="80" r="4" fill="#2563eb" />
                    <circle cx="500" cy="45" r="4" fill="#2563eb" />
                  </svg>
                </div>

                {/* X-Axis Dates */}
                <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: '0.72rem', marginTop: '6px', padding: '0 4px', width: '100%' }}>
                  <span>Day 1</span>
                  <span>Day 5</span>
                  <span>Day 10</span>
                  <span>Day 15</span>
                  <span>Day 20</span>
                  <span>Day 30</span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* CARD 2: LEAD SOURCE DONUT CHART */}
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column', height: '100%', justifyContent: 'space-between', boxSizing: 'border-box', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', gap: '8px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px', whiteSpace: 'nowrap', flexShrink: 0 }}>
              <Layers size={20} style={{ color: '#10b981', flexShrink: 0 }} />
              <span>Lead Source</span>
            </h3>
            <select 
              value={sourceFilter} 
              onChange={(e) => setSourceFilter(e.target.value)}
              style={{
                fontSize: '0.78rem', fontWeight: '600', padding: '4px 10px',
                borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', cursor: 'pointer',
                width: 'auto', maxWidth: '125px', flexShrink: 0
              }}
            >
              <option value="This Month">This Month</option>
              <option value="All Time">All Time</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1 }}>
            {/* Donut Chart graphic */}
            <div style={{ position: 'relative', width: '120px', height: '120px', flexShrink: 0 }}>
              <svg viewBox="0 0 36 36" style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
                {/* Background Ring */}
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="#f1f5f9" strokeWidth="4.5" />
                
                {/* Dynamic Segments based on sourceBreakdown */}
                {(() => {
                  let accumulatedOffset = 0;
                  return sourceBreakdown.map((item) => {
                    const dashVal = item.percentage;
                    const offsetVal = -accumulatedOffset;
                    accumulatedOffset += item.percentage;
                    return (
                      <circle
                        key={item.name}
                        cx="18"
                        cy="18"
                        r="15.915"
                        fill="none"
                        stroke={item.color}
                        strokeWidth="4.5"
                        strokeDasharray={`${dashVal} ${100 - dashVal}`}
                        strokeDashoffset={offsetVal}
                      />
                    );
                  });
                })()}
              </svg>
              {/* Inner Hole text */}
              <div style={{
                position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                textAlign: 'center'
              }}>
                <span style={{ fontSize: '1.1rem', fontWeight: '800', color: '#0f172a', lineHeight: '1' }}>
                  {totalLeadsCount.toLocaleString()}
                </span>
                <span style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: '600', marginTop: '2px' }}>
                  Total Leads
                </span>
              </div>
            </div>

            {/* Legend List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1, overflow: 'hidden' }}>
              {sourceBreakdown.map((item) => (
                <div key={item.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.78rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: item.color, flexShrink: 0 }} />
                    <span style={{ color: '#475569', fontWeight: '600', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.name}</span>
                  </div>
                  <span style={{ color: '#0f172a', fontWeight: '700', whiteSpace: 'nowrap', marginLeft: '6px', flexShrink: 0 }}>
                    {item.count}&nbsp;<span style={{ color: '#94a3b8', fontWeight: '500' }}>({item.percentage}%)</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* CARD 3: LEAD STATUS FUNNEL */}
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column', height: '100%', justifyContent: 'space-between', boxSizing: 'border-box', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', gap: '8px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px', whiteSpace: 'nowrap', flexShrink: 0 }}>
              <Filter size={20} style={{ color: '#7c3aed', flexShrink: 0 }} />
              <span>Lead Status Funnel</span>
            </h3>
            <select 
              value={funnelFilter} 
              onChange={(e) => setFunnelFilter(e.target.value)}
              style={{
                fontSize: '0.78rem', fontWeight: '600', padding: '4px 10px',
                borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff', cursor: 'pointer',
                width: 'auto', maxWidth: '125px', flexShrink: 0
              }}
            >
              <option value="All Leads">All Leads</option>
              <option value="Meta Leads">Meta Leads</option>
            </select>
          </div>

          {/* Lead Status Funnel Visualization */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '9px', width: '100%', flex: 1, justifyContent: 'center' }}>
            {funnelStages.map((stage) => (
              <div 
                key={stage.label}
                style={{
                  width: '100%',
                  backgroundColor: stage.color,
                  borderRadius: '10px',
                  padding: '8px 14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '5px',
                  color: '#ffffff',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
                  boxSizing: 'border-box',
                  transition: 'all 0.3s ease'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                    <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#ffffff', flexShrink: 0 }} />
                    <span style={{ fontSize: '0.78rem', fontWeight: '700', whiteSpace: 'nowrap' }}>{stage.label}</span>
                  </div>
                  <span style={{ fontSize: '0.78rem', fontWeight: '800', whiteSpace: 'nowrap', marginLeft: '10px', flexShrink: 0 }}>
                    {stage.count.toLocaleString()}&nbsp;<span style={{ opacity: 0.9, fontWeight: '500' }}>({stage.percentage}%)</span>
                  </span>
                </div>
                {/* Visual Progress Bar inside the pill */}
                <div style={{ width: '100%', height: '3.5px', backgroundColor: 'rgba(255, 255, 255, 0.28)', borderRadius: '2px', overflow: 'hidden' }}>
                  <div 
                    style={{ 
                      width: `${Math.min(100, Math.max(0, stage.percentage))}%`, 
                      height: '100%', 
                      backgroundColor: '#ffffff', 
                      borderRadius: '2px',
                      transition: 'width 0.4s ease'
                    }} 
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 4. ROW 3: RECENT LEADS & FOLLOW-UP REMINDERS (2 COLUMNS GRID) */}
      <div className="dashboard-tables-grid">
        {/* CARD 1: RECENT LEADS TABLE */}
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Users size={20} style={{ color: '#2563eb' }} /> {isEmployeeRole ? 'My Recent Assigned Leads' : 'Recent Leads'}
            </h3>
            <Link to={isEmployeeRole ? '/leads/my' : '/leads'} style={{ fontSize: '0.82rem', color: '#2563eb', fontWeight: '700', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}>
              View All <ArrowUpRight size={15} />
            </Link>
          </div>

          <div className="table-responsive" style={{ flex: 1 }}>
            <table className="custom-table" style={{ width: '100%', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                  <th style={{ padding: '8px 10px' }}>#</th>
                  <th style={{ padding: '8px 10px' }}>Name</th>
                  <th style={{ padding: '8px 10px' }}>Phone</th>
                  <th style={{ padding: '8px 10px' }}>Source</th>
                  <th style={{ padding: '8px 10px' }}>Status</th>
                  <th style={{ padding: '8px 10px' }}>Assigned To</th>
                  <th style={{ padding: '8px 10px' }}>Date</th>
                </tr>
              </thead>
              <tbody>
                {recentLeads.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="text-center py-4 text-muted">No recent leads found.</td>
                  </tr>
                ) : (
                  recentLeads.map((ld, idx) => {
                    const srcStyle = getSourceBadgeColor(ld.source);
                    const stStyle = getStatusBadgeColor(ld.status);
                    return (
                      <tr key={ld.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '10px' }}>{idx + 1}</td>
                        <td style={{ padding: '10px' }}>
                          <strong>{ld.name}</strong>
                        </td>
                        <td style={{ padding: '10px' }}>{ld.phone}</td>
                        <td style={{ padding: '10px' }}>
                          <span style={{ padding: '3px 8px', borderRadius: '6px', backgroundColor: srcStyle.bg, color: srcStyle.color, fontWeight: '700', fontSize: '0.72rem' }}>
                            {ld.source || 'Manual'}
                          </span>
                        </td>
                        <td style={{ padding: '10px' }}>
                          <span style={{ padding: '3px 8px', borderRadius: '12px', backgroundColor: stStyle.bg, color: stStyle.color, fontWeight: '700', fontSize: '0.72rem' }}>
                            {ld.status || 'NEW'}
                          </span>
                        </td>
                        <td style={{ padding: '10px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <div style={{ width: '22px', height: '22px', borderRadius: '50%', backgroundColor: '#e2e8f0', color: '#475569', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', fontWeight: '700' }}>
                              {(ld.assigned_employee_name || 'U')[0]}
                            </div>
                            <span>{ld.assigned_employee_name || 'Unassigned'}</span>
                          </div>
                        </td>
                        <td style={{ padding: '10px', color: '#64748b' }}>
                          {formatDateDDMMYYYY(ld.created_at)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* CARD 2: FOLLOW-UP REMINDERS */}
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Clock size={20} style={{ color: '#f59e0b' }} /> Follow-up Reminders
            </h3>
            <Link to="/communication/followups" style={{ fontSize: '0.82rem', color: '#2563eb', fontWeight: '700', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}>
              View All <ArrowUpRight size={15} />
            </Link>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
            {followupReminders.length === 0 ? (
              <PingoEmptyState
                pose="playful"
                height={85}
                compact={true}
                title="All Caught Up!"
                description="No upcoming follow-up reminders right now."
              />
            ) : (
              followupReminders.map((item) => (
                <div key={item.id} style={{
                  background: '#f8fafc',
                  padding: '12px 16px',
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '36px', height: '36px', borderRadius: '10px',
                      backgroundColor: item.type === 'whatsapp' ? 'rgba(37, 211, 102, 0.12)' : 'rgba(37, 99, 235, 0.12)',
                      color: item.type === 'whatsapp' ? '#25d366' : '#2563eb',
                      display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      {item.type === 'whatsapp' ? <MessageCircle size={18} /> : <PhoneCall size={18} />}
                    </div>
                    <div>
                      <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#0f172a' }}>{item.lead_name || item.name}</div>
                      <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{item.notes || item.note || 'Follow-up call'}</div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '500' }}>
                      {item.followup_date ? `${formatDateDDMMYYYY(item.followup_date)} ${formatTime12Hour(item.followup_time)}` : (item.time || '-')}
                    </span>
                    <span style={{
                      padding: '3px 10px', borderRadius: '10px', fontSize: '0.72rem', fontWeight: '700',
                      backgroundColor: (item.priority || '').toUpperCase() === 'HIGH' ? '#ffe4e6' : (item.priority || '').toUpperCase() === 'MEDIUM' ? '#fef3c7' : '#e0f2fe',
                      color: (item.priority || '').toUpperCase() === 'HIGH' ? '#e11d48' : (item.priority || '').toUpperCase() === 'MEDIUM' ? '#d97706' : '#0284c7'
                    }}>
                      {item.priority || 'Medium'}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* 5. ROW 4: ACTIVITIES, TEAM PERFORMANCE & META LEADS (3 COLUMNS GRID) */}
      <div className="dashboard-bottom-grid">
        {/* CARD 1: TODAY'S ACTIVITIES */}
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Calendar size={20} style={{ color: '#2563eb' }} /> Today's Activities
            </h3>
            <Link to="/communication/activities" style={{ fontSize: '0.82rem', color: '#2563eb', fontWeight: '700', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}>
              View All <ArrowUpRight size={15} />
            </Link>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {todayActivities.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px 0', color: '#94a3b8', fontSize: '0.85rem' }}>
                No activities recorded today.
              </div>
            ) : (
              todayActivities.map((act) => (
                <div key={act.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f1f5f9' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{
                      width: '32px', height: '32px', borderRadius: '8px',
                      backgroundColor: '#f1f5f9', color: '#475569',
                      display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      {act.icon === 'call' ? <PhoneCall size={16} /> : act.icon === 'whatsapp' ? <MessageCircle size={16} /> : <Calendar size={16} />}
                    </div>
                    <div>
                      <div style={{ fontSize: '0.82rem', fontWeight: '700', color: '#0f172a' }}>{act.title}</div>
                      <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{act.time}</div>
                    </div>
                  </div>

                  <span style={{
                    padding: '3px 8px', borderRadius: '10px', fontSize: '0.72rem', fontWeight: '700',
                    backgroundColor: act.status === 'Completed' ? '#d1fae5' : act.status === 'Pending' ? '#fef3c7' : '#e0f2fe',
                    color: act.status === 'Completed' ? '#059669' : act.status === 'Pending' ? '#d97706' : '#2563eb'
                  }}>
                    {act.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* CARD 2: TOP PERFORMING TEAM (Only for ADMIN & MANAGER) */}
        {user?.role?.toUpperCase() !== 'EMPLOYEE' && (
          <div className="content-card" style={{ borderRadius: '18px', padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Award size={20} style={{ color: '#f59e0b' }} /> Top Performing Team
              </h3>
              <select 
                value={teamFilter} 
                onChange={(e) => setTeamFilter(e.target.value)}
                style={{
                  fontSize: '0.78rem', fontWeight: '600', padding: '4px 8px',
                  borderRadius: '8px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', cursor: 'pointer',
                  width: 'auto', maxWidth: '115px', flexShrink: 0
                }}
              >
                <option value="This Month">This Month</option>
              </select>
            </div>

            <div className="table-responsive" style={{ flex: 1 }}>
              <table className="custom-table" style={{ width: '100%', fontSize: '0.8rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                    <th style={{ padding: '6px 8px' }}>#</th>
                    <th style={{ padding: '6px 8px' }}>Name</th>
                    <th style={{ padding: '6px 8px' }}>Total Leads</th>
                    <th style={{ padding: '6px 8px' }}>Calls</th>
                    <th style={{ padding: '6px 8px' }}>Follow-ups</th>
                    <th style={{ padding: '6px 8px' }}>Converted</th>
                  </tr>
                </thead>
                <tbody>
                  {teamMembers.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="text-center py-4 text-muted">No team performance records available.</td>
                    </tr>
                  ) : (
                    teamMembers.map((tm, idx) => (
                      <tr key={tm.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '8px' }}>{idx + 1}</td>
                        <td style={{ padding: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <div style={{ width: '24px', height: '24px', borderRadius: '50%', backgroundColor: '#3b82f6', color: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.72rem', fontWeight: '700' }}>
                              {tm.avatar}
                            </div>
                            <strong>{tm.name}</strong>
                          </div>
                        </td>
                        <td style={{ padding: '8px' }}>{tm.leads}</td>
                        <td style={{ padding: '8px' }}>{tm.calls}</td>
                        <td style={{ padding: '8px' }}>{tm.followups}</td>
                        <td style={{ padding: '8px', fontWeight: '700', color: '#059669' }}>{tm.converted}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

    </div>
  );
};

export default Dashboard;
