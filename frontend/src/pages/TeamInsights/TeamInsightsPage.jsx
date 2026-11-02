import React, { useState, useEffect, useMemo } from 'react';
import { 
  Users, 
  UserCheck, 
  UserPlus, 
  Phone, 
  PhoneCall, 
  PhoneIncoming, 
  PhoneOutgoing, 
  PhoneMissed, 
  PhoneOff, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  TrendingUp, 
  BarChart3, 
  PieChart, 
  Download, 
  RefreshCw, 
  Search, 
  Filter, 
  ArrowUpRight, 
  ArrowDownRight, 
  Minus, 
  Calendar, 
  Layers, 
  Award, 
  Info, 
  ChevronDown, 
  Smartphone, 
  Headphones, 
  FileSpreadsheet, 
  FileText,
  User,
  ArrowUpDown
} from 'lucide-react';
import API from '../../services/api';
import DrilldownModal from './DrilldownModal';
import { 
  PRESETS, 
  DEFAULT_FILTERS, 
  buildParams, 
  formatNumber, 
  formatPercent, 
  formatDuration, 
  formatDateTime, 
  formatDateOnly, 
  badgeClass, 
  statusTone, 
  downloadInsightsExport, 
  apiErrorMessage,
  METRIC_TITLES
} from './insightsUtils';
import './TeamInsights.css';

const TeamInsightsPage = () => {
  // State
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Drilldown modal state
  const [drilldownState, setDrilldownState] = useState({
    isOpen: false,
    metric: null,
    employeeContext: null,
    totalExpected: null,
  });

  // Export dropdown state
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [exportingDataset, setExportingDataset] = useState(null);

  // Table search & sort state
  const [empSearch, setEmpSearch] = useState('');
  const [sortField, setSortField] = useState('rank');
  const [sortAsc, setSortAsc] = useState(true);

  // Timeline filter state
  const [timelineFilter, setTimelineFilter] = useState('ALL');

  // Chart hover state for conversion trend
  const [hoveredTrendPoint, setHoveredTrendPoint] = useState(null);

  // Fetch dashboard data
  const fetchDashboardData = async (isManualRefresh = false) => {
    try {
      if (isManualRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);

      const params = buildParams(filters);
      const res = await API.get('/team-insights/dashboard', { params });
      setData(res.data);
    } catch (err) {
      console.error('Failed to load team insights dashboard:', err);
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [
    filters.preset, 
    filters.employee_id, 
    filters.department, 
    filters.lead_source, 
    filters.call_source
  ]);

  const handleCustomDateSubmit = (e) => {
    e.preventDefault();
    if (filters.start_date && filters.end_date) {
      fetchDashboardData();
    }
  };

  // Filter change handlers
  const handlePresetChange = (preset) => {
    setFilters((prev) => ({
      ...prev,
      preset,
      ...(preset !== 'CUSTOM' ? { start_date: '', end_date: '' } : {}),
    }));
  };

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleResetFilters = () => {
    setFilters(DEFAULT_FILTERS);
  };

  // Drilldown open handler
  const openDrilldown = (metric, totalExpected = null, employeeContext = null) => {
    setDrilldownState({
      isOpen: true,
      metric,
      employeeContext,
      totalExpected,
    });
  };

  const closeDrilldown = () => {
    setDrilldownState({
      isOpen: false,
      metric: null,
      employeeContext: null,
      totalExpected: null,
    });
  };

  // Full dataset export handler
  const handleDatasetExport = async (dataset, format = 'csv') => {
    try {
      setExportingDataset(`${dataset}_${format}`);
      await downloadInsightsExport({
        dataset,
        format,
        filters,
      });
      setShowExportMenu(false);
    } catch (err) {
      console.error('Export failed:', err);
      alert('Export failed: ' + apiErrorMessage(err));
    } finally {
      setExportingDataset(null);
    }
  };

  // Sorted and searched employee rows
  const sortedEmployees = useMemo(() => {
    const list = data?.employees || [];
    let filtered = list;
    if (empSearch.trim()) {
      const q = empSearch.toLowerCase();
      filtered = list.filter(
        (e) =>
          e.name?.toLowerCase().includes(q) ||
          e.email?.toLowerCase().includes(q) ||
          e.department?.toLowerCase().includes(q) ||
          e.role?.toLowerCase().includes(q)
      );
    }

    return [...filtered].sort((a, b) => {
      let valA = a[sortField];
      let valB = b[sortField];
      if (typeof valA === 'string') valA = valA.toLowerCase();
      if (typeof valB === 'string') valB = valB.toLowerCase();
      if (valA < valB) return sortAsc ? -1 : 1;
      if (valA > valB) return sortAsc ? 1 : -1;
      return 0;
    });
  }, [data?.employees, empSearch, sortField, sortAsc]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false); // Default to descending on new column
    }
  };

  // Filtered timeline items
  const filteredTimeline = useMemo(() => {
    const list = data?.timeline || [];
    if (timelineFilter === 'ALL') return list;
    return list.filter((item) => item.event_type === timelineFilter);
  }, [data?.timeline, timelineFilter]);

  // Helpers for Comparison indicators
  const renderComparisonBadge = (cmp) => {
    if (!cmp) return null;
    const { direction, change_percentage, has_baseline, current, previous } = cmp;
    if (!has_baseline && previous === 0 && current === 0) {
      return (
        <span className="ti-trend-badge ti-trend-flat" title="No change vs previous period">
          <Minus size={11} /> 0%
        </span>
      );
    }
    if (direction === 'up') {
      return (
        <span className="ti-trend-badge ti-trend-up" title={`+${change_percentage ?? current} vs previous period`}>
          <ArrowUpRight size={12} />
          {change_percentage !== null ? `${change_percentage}%` : `+${current}`}
        </span>
      );
    }
    if (direction === 'down') {
      return (
        <span className="ti-trend-badge ti-trend-down" title={`${change_percentage}% vs previous period`}>
          <ArrowDownRight size={12} />
          {change_percentage}%
        </span>
      );
    }
    return (
      <span className="ti-trend-badge ti-trend-flat" title="Equal to previous period">
        <Minus size={11} /> 0%
      </span>
    );
  };

  const overview = data?.overview || {};
  const leadAnalytics = data?.lead_analytics || {};
  const callAnalytics = data?.call_analytics || {};
  const followupAnalytics = data?.followup_analytics || {};
  const conversionAnalytics = data?.conversion_analytics || {};
  const teamTotals = data?.team_totals || {};
  const filterOptions = data?.filter_options || {};

  return (
    <div className="ti-container">
      {/* ----------------------------------------------------------------------
         Header
         ---------------------------------------------------------------------- */}
      <div className="ti-header">
        <div className="ti-header-left">
          <div className="ti-header-icon-badge">
            <BarChart3 size={24} />
          </div>
          <div className="ti-header-title-area">
            <h1>Team Insights & Analytics</h1>
            <p className="ti-header-subtitle">
              <span>Performance and activity intelligence</span>
              <span className="ti-timezone-pill">
                <Clock size={12} /> IST (Asia/Kolkata)
              </span>
              {data?.generated_at && (
                <span>• Generated: {formatDateTime(data.generated_at)}</span>
              )}
            </p>
          </div>
        </div>

        <div className="ti-header-actions">
          {/* Refresh button */}
          <button
            type="button"
            className="ti-btn ti-btn-outline"
            onClick={() => fetchDashboardData(true)}
            disabled={loading || refreshing}
            title="Refresh analytics data"
          >
            <RefreshCw size={15} className={refreshing ? 'ti-spinner' : ''} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>

          {/* Export Dropdown */}
          <div style={{ position: 'relative' }}>
            <button
              type="button"
              className="ti-btn ti-btn-primary"
              onClick={() => setShowExportMenu(!showExportMenu)}
              disabled={loading}
              title="Export report datasets"
            >
              <Download size={15} />
              <span>Export Report</span>
              <ChevronDown size={14} />
            </button>

            {showExportMenu && (
              <div 
                className="ti-card" 
                style={{
                  position: 'absolute',
                  right: 0,
                  top: '110%',
                  zIndex: 100,
                  width: 250,
                  padding: 10,
                  boxShadow: '0 10px 25px -5px rgba(0,0,0,0.15)',
                }}
              >
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#64748b', padding: '6px 8px', textTransform: 'uppercase' }}>
                  Download Excel (.xlsx)
                </div>
                <button
                  type="button"
                  className="ti-btn ti-btn-ghost ti-btn-sm"
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                  onClick={() => handleDatasetExport('employees', 'xlsx')}
                >
                  <FileSpreadsheet size={14} style={{ color: '#059669' }} />
                  <span>Employee Performance</span>
                </button>
                <button
                  type="button"
                  className="ti-btn ti-btn-ghost ti-btn-sm"
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                  onClick={() => handleDatasetExport('conversion_employees', 'xlsx')}
                >
                  <FileSpreadsheet size={14} style={{ color: '#059669' }} />
                  <span>Conversions by Employee</span>
                </button>
                <button
                  type="button"
                  className="ti-btn ti-btn-ghost ti-btn-sm"
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                  onClick={() => handleDatasetExport('conversion_sources', 'xlsx')}
                >
                  <FileSpreadsheet size={14} style={{ color: '#059669' }} />
                  <span>Conversions by Lead Source</span>
                </button>
                <button
                  type="button"
                  className="ti-btn ti-btn-ghost ti-btn-sm"
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                  onClick={() => handleDatasetExport('timeline', 'xlsx')}
                >
                  <FileSpreadsheet size={14} style={{ color: '#059669' }} />
                  <span>Activity Timeline</span>
                </button>

                <div style={{ height: 1, background: '#e2e8f0', margin: '6px 0' }} />

                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#64748b', padding: '6px 8px', textTransform: 'uppercase' }}>
                  Download CSV (.csv)
                </div>
                <button
                  type="button"
                  className="ti-btn ti-btn-ghost ti-btn-sm"
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                  onClick={() => handleDatasetExport('employees', 'csv')}
                >
                  <FileText size={14} style={{ color: '#2563eb' }} />
                  <span>Employee Performance CSV</span>
                </button>
                <button
                  type="button"
                  className="ti-btn ti-btn-ghost ti-btn-sm"
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                  onClick={() => handleDatasetExport('timeline', 'csv')}
                >
                  <FileText size={14} style={{ color: '#2563eb' }} />
                  <span>Activity Timeline CSV</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ----------------------------------------------------------------------
         Filter Toolbar (Working Filters)
         ---------------------------------------------------------------------- */}
      <div className="ti-filter-toolbar">
        {/* Top Row: Preset Buttons */}
        <div className="ti-filter-top-row">
          <div className="ti-presets-group">
            {PRESETS.map((p) => (
              <button
                key={p.value}
                type="button"
                className={`ti-preset-btn ${filters.preset === p.value ? 'active' : ''}`}
                onClick={() => handlePresetChange(p.value)}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Custom Date Pickers when CUSTOM is active */}
          {filters.preset === 'CUSTOM' && (
            <form onSubmit={handleCustomDateSubmit} className="ti-custom-date-inputs">
              <input
                type="date"
                value={filters.start_date || ''}
                onChange={(e) => handleFilterChange('start_date', e.target.value)}
                className="ti-date-input"
                required
              />
              <span className="ti-date-sep">to</span>
              <input
                type="date"
                value={filters.end_date || ''}
                onChange={(e) => handleFilterChange('end_date', e.target.value)}
                className="ti-date-input"
                required
              />
              <button type="submit" className="ti-btn ti-btn-primary ti-btn-sm">
                Apply
              </button>
            </form>
          )}
        </div>

        {/* Bottom Row: Dimension Dropdowns */}
        <div className="ti-filter-bottom-row">
          <div className="ti-dropdown-group">
            {/* Employee Filter */}
            <div className="ti-select-wrapper">
              <User size={14} className="ti-select-icon" />
              <select
                value={filters.employee_id || ''}
                onChange={(e) => handleFilterChange('employee_id', e.target.value ? Number(e.target.value) : '')}
                className="ti-select"
              >
                <option value="">All Employees</option>
                {(filterOptions.employees || []).map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.name} ({emp.role || emp.department})
                  </option>
                ))}
              </select>
            </div>

            {/* Department Filter */}
            <div className="ti-select-wrapper">
              <Layers size={14} className="ti-select-icon" />
              <select
                value={filters.department || ''}
                onChange={(e) => handleFilterChange('department', e.target.value)}
                className="ti-select"
              >
                <option value="">All Departments</option>
                {(filterOptions.departments || []).map((dept) => (
                  <option key={dept} value={dept}>
                    {dept}
                  </option>
                ))}
              </select>
            </div>

            {/* Lead Source Filter */}
            <div className="ti-select-wrapper">
              <Filter size={14} className="ti-select-icon" />
              <select
                value={filters.lead_source || ''}
                onChange={(e) => handleFilterChange('lead_source', e.target.value)}
                className="ti-select"
              >
                <option value="">All Lead Sources</option>
                {(filterOptions.lead_sources || []).map((src) => (
                  <option key={src} value={src}>
                    {src}
                  </option>
                ))}
              </select>
            </div>

            {/* Call Source Filter */}
            <div className="ti-select-wrapper">
              <Phone size={14} className="ti-select-icon" />
              <select
                value={filters.call_source || ''}
                onChange={(e) => handleFilterChange('call_source', e.target.value)}
                className="ti-select"
              >
                <option value="">All Call Sources</option>
                {(filterOptions.call_sources || []).map((src) => (
                  <option key={src.value} value={src.value}>
                    {src.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Reset Button */}
            {(filters.employee_id || filters.department || filters.lead_source || filters.call_source || filters.preset !== 'LAST_30_DAYS') && (
              <button
                type="button"
                className="ti-btn ti-btn-ghost ti-btn-sm"
                onClick={handleResetFilters}
              >
                Reset Filters
              </button>
            )}
          </div>

          {/* Active Period Info */}
          {data?.period && (
            <div className="ti-active-filter-summary">
              <Calendar size={14} />
              <span>
                {data.period.label}: {formatDateOnly(data.period.start)} – {formatDateOnly(data.period.end)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ----------------------------------------------------------------------
         Error Alert
         ---------------------------------------------------------------------- */}
      {error && (
        <div className="ti-card" style={{ marginBottom: 20, borderColor: '#fca5a5', background: '#fef2f2' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <AlertCircle size={24} style={{ color: '#dc2626' }} />
            <div>
              <div style={{ fontWeight: 700, color: '#991b1b' }}>Failed to load insights</div>
              <div style={{ fontSize: '0.82rem', color: '#b91c1c' }}>{error}</div>
            </div>
            <button
              type="button"
              className="ti-btn ti-btn-outline ti-btn-sm"
              style={{ marginLeft: 'auto' }}
              onClick={() => fetchDashboardData()}
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------------
         Section A: Team Overview (8 KPI Cards)
         ---------------------------------------------------------------------- */}
      <section className="ti-section">
        <div className="ti-section-header">
          <div className="ti-section-title-wrap">
            <Users size={20} className="ti-section-icon" />
            <div>
              <h2 className="ti-section-title">Team Overview</h2>
              <p className="ti-section-desc">Key operational metrics across team, leads, calls & follow-ups</p>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="ti-kpi-grid-8">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="ti-skeleton ti-skeleton-kpi" />
            ))}
          </div>
        ) : (
          <div className="ti-kpi-grid-8">
            {/* 1. Total Employees */}
            <div 
              className="ti-kpi-card" 
              onClick={() => openDrilldown('total_employees', overview.total_employees)}
              title="Click to view all employees"
            >
              <div className="ti-kpi-card-header">
                <span className="ti-kpi-label">Total Employees</span>
                <div className="ti-kpi-icon-wrap ti-icon-slate">
                  <Users size={18} />
                </div>
              </div>
              <div className="ti-kpi-value-row">
                <span className="ti-kpi-value">{formatNumber(overview.total_employees)}</span>
                <span className="ti-badge ti-badge-slate">In Scope</span>
              </div>
              <div className="ti-kpi-subtext">
                <span>Active company roster</span>
                <span className="ti-clickable-hint">View list →</span>
              </div>
            </div>

            {/* 2. Active Employees */}
            <div 
              className="ti-kpi-card" 
              onClick={() => openDrilldown('active_employees', overview.active_employees)}
              title="Click to view active employees"
            >
              <div className="ti-kpi-card-header">
                <span className="ti-kpi-label">Active Employees</span>
                <div className="ti-kpi-icon-wrap ti-icon-emerald">
                  <UserCheck size={18} />
                </div>
              </div>
              <div className="ti-kpi-value-row">
                <span className="ti-kpi-value">{formatNumber(overview.active_employees)}</span>
                <span className="ti-badge ti-badge-green">Online</span>
              </div>
              <div className="ti-kpi-subtext">
                <span>Accounts active</span>
                <span className="ti-clickable-hint">View list →</span>
              </div>
            </div>

            {/* 3. Total Assigned Leads */}
            <div 
              className="ti-kpi-card" 
              onClick={() => openDrilldown('total_assigned_leads', overview.total_assigned_leads)}
              title="Click to view assigned leads"
            >
              <div className="ti-kpi-card-header">
                <span className="ti-kpi-label">Total Assigned Leads</span>
                <div className="ti-kpi-icon-wrap ti-icon-blue">
                  <UserPlus size={18} />
                </div>
              </div>
              <div className="ti-kpi-value-row">
                <span className="ti-kpi-value">{formatNumber(overview.total_assigned_leads)}</span>
                <span className="ti-badge ti-badge-blue">Allocated</span>
              </div>
              <div className="ti-kpi-subtext">
                <span>Under employee care</span>
                <span className="ti-clickable-hint">View leads →</span>
              </div>
            </div>

            {/* 4. New Leads */}
            <div 
              className="ti-kpi-card" 
              onClick={() => openDrilldown('new_leads', overview.new_leads)}
              title="Click to view new leads created in period"
            >
              <div className="ti-kpi-card-header">
                <span className="ti-kpi-label">New Leads</span>
                <div className="ti-kpi-icon-wrap ti-icon-indigo">
                  <Layers size={18} />
                </div>
              </div>
              <div className="ti-kpi-value-row">
                <span className="ti-kpi-value">{formatNumber(overview.new_leads)}</span>
                {renderComparisonBadge(overview.comparison?.new_leads)}
              </div>
              <div className="ti-kpi-subtext">
                <span>Created in selected period</span>
                <span className="ti-clickable-hint">View leads →</span>
              </div>
            </div>

            {/* 5. Total Calls */}
            <div 
              className="ti-kpi-card" 
              onClick={() => openDrilldown('total_calls', overview.total_calls)}
              title="Click to view all call logs"
            >
              <div className="ti-kpi-card-header">
                <span className="ti-kpi-label">Total Calls</span>
                <div className="ti-kpi-icon-wrap ti-icon-violet">
                  <Phone size={18} />
                </div>
              </div>
              <div className="ti-kpi-value-row">
                <span className="ti-kpi-value">{formatNumber(overview.total_calls)}</span>
                {renderComparisonBadge(overview.comparison?.total_calls)}
              </div>
              <div className="ti-kpi-subtext">
                <span>Telephony & Mobile calls</span>
                <span className="ti-clickable-hint">View calls →</span>
              </div>
            </div>

            {/* 6. Connected Calls */}
            <div 
              className="ti-kpi-card" 
              onClick={() => openDrilldown('connected_calls', overview.connected_calls)}
              title="Click to view connected calls (duration > 0s)"
            >
              <div className="ti-kpi-card-header">
                <span className="ti-kpi-label">Connected Calls</span>
                <div className="ti-kpi-icon-wrap ti-icon-emerald">
                  <PhoneCall size={18} />
                </div>
              </div>
              <div className="ti-kpi-value-row">
                <span className="ti-kpi-value">{formatNumber(overview.connected_calls)}</span>
                {renderComparisonBadge(overview.comparison?.connected_calls)}
              </div>
              <div className="ti-kpi-subtext">
                <span>Duration &gt; 0s answered</span>
                <span className="ti-clickable-hint">View calls →</span>
              </div>
            </div>

            {/* 7. Converted Leads */}
            <div 
              className="ti-kpi-card" 
              onClick={() => openDrilldown('converted_leads', overview.converted_leads)}
              title="Click to view converted leads"
            >
              <div className="ti-kpi-card-header">
                <span className="ti-kpi-label">Converted Leads</span>
                <div className="ti-kpi-icon-wrap ti-icon-emerald">
                  <CheckCircle2 size={18} />
                </div>
              </div>
              <div className="ti-kpi-value-row">
                <span className="ti-kpi-value">{formatNumber(overview.converted_leads)}</span>
                {renderComparisonBadge(overview.comparison?.converted_leads)}
              </div>
              <div className="ti-kpi-subtext">
                <span>Closed won & onboarded</span>
                <span className="ti-clickable-hint">View leads →</span>
              </div>
            </div>

            {/* 8. Pending Follow-ups */}
            <div 
              className="ti-kpi-card" 
              onClick={() => openDrilldown('pending_followups', overview.pending_followups)}
              title="Click to view pending follow-ups"
            >
              <div className="ti-kpi-card-header">
                <span className="ti-kpi-label">Pending Follow-ups</span>
                <div className="ti-kpi-icon-wrap ti-icon-amber">
                  <Clock size={18} />
                </div>
              </div>
              <div className="ti-kpi-value-row">
                <span className="ti-kpi-value">{formatNumber(overview.pending_followups)}</span>
                {renderComparisonBadge(overview.comparison?.pending_followups)}
              </div>
              <div className="ti-kpi-subtext">
                <span>Scheduled follow-ups</span>
                <span className="ti-clickable-hint">View follow-ups →</span>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* ----------------------------------------------------------------------
         Section B: Employee Performance Table
         ---------------------------------------------------------------------- */}
      <section className="ti-section">
        <div className="ti-card">
          <div className="ti-table-toolbar">
            <div className="ti-section-title-wrap">
              <Award size={20} className="ti-section-icon" />
              <div>
                <h2 className="ti-section-title">Employee Performance Table</h2>
                <p className="ti-section-desc">Employee-by-employee execution, telecalling and conversion metrics</p>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div className="ti-modal-search-box" style={{ maxWidth: 220 }}>
                <Search size={14} className="ti-search-icon" />
                <input
                  type="text"
                  placeholder="Filter employee..."
                  value={empSearch}
                  onChange={(e) => setEmpSearch(e.target.value)}
                  className="ti-modal-search-input"
                />
              </div>

              <button
                type="button"
                className="ti-btn ti-btn-outline ti-btn-sm"
                onClick={() => handleDatasetExport('employees', 'csv')}
                title="Download CSV"
              >
                <Download size={13} />
                <span>Export</span>
              </button>
            </div>
          </div>

          <div className="ti-table-responsive">
            <table className="ti-table">
              <thead>
                <tr>
                  <th onClick={() => handleSort('rank')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Rank <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('name')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Employee Name <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('department')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Department / Role <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('assigned_leads')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Assigned Leads <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('contacted_leads')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Contacted Leads <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('total_calls')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Total Calls <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('inbound_calls')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Inbound Calls <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('outbound_calls')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Outbound Calls <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('connected_calls')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Connected Calls <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('followups_completed')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Follow-ups Completed <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('pending_followups')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Pending Follow-ups <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('converted_leads')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Converted Leads <ArrowUpDown size={12} />
                    </span>
                  </th>
                  <th onClick={() => handleSort('conversion_percentage')}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Conversion % <ArrowUpDown size={12} />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedEmployees.length === 0 ? (
                  <tr>
                    <td colSpan={13} style={{ textAlign: 'center', padding: '40px 20px', color: '#94a3b8' }}>
                      No employees match the current filters or search query.
                    </td>
                  </tr>
                ) : (
                  sortedEmployees.map((emp) => (
                    <tr key={emp.employee_id}>
                      {/* Rank */}
                      <td>
                        <span className={`ti-rank-badge ${
                          emp.rank === 1 ? 'ti-rank-1' :
                          emp.rank === 2 ? 'ti-rank-2' :
                          emp.rank === 3 ? 'ti-rank-3' : 'ti-rank-other'
                        }`}>
                          {emp.rank}
                        </span>
                      </td>

                      {/* Employee Name */}
                      <td>
                        <div className="ti-emp-cell">
                          <div className="ti-emp-avatar">
                            {emp.name.charAt(0).toUpperCase()}
                          </div>
                          <div className="ti-emp-info">
                            <span className="ti-emp-name">{emp.name}</span>
                            <span className="ti-emp-email">{emp.email}</span>
                          </div>
                        </div>
                      </td>

                      {/* Department / Role */}
                      <td>
                        <span className={badgeClass(statusTone(emp.role))}>
                          {emp.department} • {emp.role.replace(/_/g, ' ')}
                        </span>
                      </td>

                      {/* Assigned Leads (Clickable) */}
                      <td>
                        <span 
                          className="ti-click-cell"
                          onClick={() => openDrilldown('assigned_leads', emp.assigned_leads, emp)}
                          title="Click to view assigned leads for this employee"
                        >
                          {formatNumber(emp.assigned_leads)}
                        </span>
                      </td>

                      {/* Contacted Leads */}
                      <td>
                        <span 
                          className="ti-click-cell"
                          onClick={() => openDrilldown('contacted_leads', emp.contacted_leads, emp)}
                          title="Click to view contacted leads for this employee"
                        >
                          {formatNumber(emp.contacted_leads)}
                        </span>
                      </td>

                      {/* Total Calls (Clickable) */}
                      <td>
                        <span 
                          className="ti-click-cell"
                          onClick={() => openDrilldown('total_calls', emp.total_calls, emp)}
                          title="Click to view all calls made by this employee"
                        >
                          {formatNumber(emp.total_calls)}
                        </span>
                      </td>

                      {/* Inbound Calls */}
                      <td>
                        <span 
                          className="ti-click-cell"
                          onClick={() => openDrilldown('inbound_calls', emp.inbound_calls, emp)}
                        >
                          {formatNumber(emp.inbound_calls)}
                        </span>
                      </td>

                      {/* Outbound Calls */}
                      <td>
                        <span 
                          className="ti-click-cell"
                          onClick={() => openDrilldown('outbound_calls', emp.outbound_calls, emp)}
                        >
                          {formatNumber(emp.outbound_calls)}
                        </span>
                      </td>

                      {/* Connected Calls */}
                      <td>
                        <span 
                          className="ti-click-cell"
                          style={{ color: '#059669', fontWeight: 700 }}
                          onClick={() => openDrilldown('connected_calls', emp.connected_calls, emp)}
                          title="Click to view connected calls for this employee"
                        >
                          {formatNumber(emp.connected_calls)}
                        </span>
                      </td>

                      {/* Follow-ups Completed */}
                      <td>
                        <span 
                          className="ti-click-cell"
                          onClick={() => openDrilldown('completed_followups', emp.followups_completed, emp)}
                        >
                          {formatNumber(emp.followups_completed)}
                        </span>
                      </td>

                      {/* Pending Follow-ups */}
                      <td>
                        <span 
                          className="ti-click-cell"
                          style={{ color: '#d97706' }}
                          onClick={() => openDrilldown('pending_followups', emp.pending_followups, emp)}
                        >
                          {formatNumber(emp.pending_followups)}
                        </span>
                      </td>

                      {/* Converted Leads */}
                      <td>
                        <span 
                          className="ti-click-cell"
                          style={{ color: '#15803d', fontWeight: 700 }}
                          onClick={() => openDrilldown('converted_leads', emp.converted_leads, emp)}
                        >
                          {formatNumber(emp.converted_leads)}
                        </span>
                      </td>

                      {/* Conversion % with progress meter */}
                      <td>
                        <div className="ti-progress-cell">
                          <span style={{ fontWeight: 600, minWidth: 42 }}>
                            {formatPercent(emp.conversion_percentage)}
                          </span>
                          <div className="ti-progress-track">
                            <div 
                              className="ti-progress-bar"
                              style={{ width: `${Math.min(100, emp.conversion_percentage)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>

              {/* Team Totals Row */}
              {sortedEmployees.length > 0 && (
                <tfoot>
                  <tr>
                    <td colSpan={3}>Team Totals ({sortedEmployees.length} Employees)</td>
                    <td>{formatNumber(teamTotals.assigned_leads)}</td>
                    <td>{formatNumber(teamTotals.contacted_leads)}</td>
                    <td>{formatNumber(teamTotals.total_calls)}</td>
                    <td>{formatNumber(teamTotals.inbound_calls)}</td>
                    <td>{formatNumber(teamTotals.outbound_calls)}</td>
                    <td>{formatNumber(teamTotals.connected_calls)}</td>
                    <td>{formatNumber(teamTotals.followups_completed)}</td>
                    <td>{formatNumber(teamTotals.pending_followups)}</td>
                    <td>{formatNumber(teamTotals.converted_leads)}</td>
                    <td>{formatPercent(teamTotals.conversion_percentage)}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------------------
         Row: Section C (Lead Analytics) & Section D (Call Analytics)
         ---------------------------------------------------------------------- */}
      <div className="ti-grid-2-col" style={{ marginBottom: 28 }}>
        {/* Section C: Lead Analytics */}
        <div className="ti-card">
          <div className="ti-section-header">
            <div className="ti-section-title-wrap">
              <Layers size={18} className="ti-section-icon" />
              <div>
                <h3 className="ti-section-title" style={{ fontSize: '1.05rem' }}>Lead Analytics</h3>
                <p className="ti-section-desc">Pipeline status breakdown for selected period</p>
              </div>
            </div>
            <span className="ti-badge ti-badge-blue">
              {formatPercent(leadAnalytics.conversion_percentage)} Win Rate
            </span>
          </div>

          <div className="ti-metric-card-row">
            <div className="ti-mini-stat" onClick={() => openDrilldown('new_leads', leadAnalytics.new_leads)}>
              <div className="ti-mini-stat-label">New Leads</div>
              <div className="ti-mini-stat-val" style={{ color: '#6366f1' }}>{formatNumber(leadAnalytics.new_leads)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('assigned_leads', leadAnalytics.assigned_leads)}>
              <div className="ti-mini-stat-label">Assigned</div>
              <div className="ti-mini-stat-val" style={{ color: '#2563eb' }}>{formatNumber(leadAnalytics.assigned_leads)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('unassigned_leads', leadAnalytics.unassigned_leads)}>
              <div className="ti-mini-stat-label">Unassigned</div>
              <div className="ti-mini-stat-val" style={{ color: '#64748b' }}>{formatNumber(leadAnalytics.unassigned_leads)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('contacted_leads', leadAnalytics.contacted_leads)}>
              <div className="ti-mini-stat-label">Contacted</div>
              <div className="ti-mini-stat-val" style={{ color: '#0891b2' }}>{formatNumber(leadAnalytics.contacted_leads)}</div>
            </div>
          </div>

          <div className="ti-metric-card-row">
            <div className="ti-mini-stat" onClick={() => openDrilldown('interested_leads', leadAnalytics.interested_leads)}>
              <div className="ti-mini-stat-label">Interested</div>
              <div className="ti-mini-stat-val" style={{ color: '#d97706' }}>{formatNumber(leadAnalytics.interested_leads)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('converted_leads', leadAnalytics.converted_leads)}>
              <div className="ti-mini-stat-label">Converted</div>
              <div className="ti-mini-stat-val" style={{ color: '#059669' }}>{formatNumber(leadAnalytics.converted_leads)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('lost_leads', leadAnalytics.lost_leads)}>
              <div className="ti-mini-stat-label">Lost Leads</div>
              <div className="ti-mini-stat-val" style={{ color: '#dc2626' }}>{formatNumber(leadAnalytics.lost_leads)}</div>
            </div>
          </div>

          {/* Visual Funnel Bar */}
          <div style={{ marginTop: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', color: '#64748b', marginBottom: 6 }}>
              <span>Conversion Funnel Progress</span>
              <span>{leadAnalytics.converted_leads || 0} / {leadAnalytics.assigned_leads || 0} converted</span>
            </div>
            <div style={{ display: 'flex', height: 10, borderRadius: 5, overflow: 'hidden', background: '#f1f5f9' }}>
              <div 
                style={{ 
                  width: `${leadAnalytics.assigned_leads ? ((leadAnalytics.contacted_leads || 0) / leadAnalytics.assigned_leads) * 100 : 0}%`, 
                  background: '#0891b2' 
                }} 
                title={`Contacted: ${leadAnalytics.contacted_leads}`} 
              />
              <div 
                style={{ 
                  width: `${leadAnalytics.assigned_leads ? ((leadAnalytics.interested_leads || 0) / leadAnalytics.assigned_leads) * 100 : 0}%`, 
                  background: '#d97706' 
                }} 
                title={`Interested: ${leadAnalytics.interested_leads}`} 
              />
              <div 
                style={{ 
                  width: `${leadAnalytics.assigned_leads ? ((leadAnalytics.converted_leads || 0) / leadAnalytics.assigned_leads) * 100 : 0}%`, 
                  background: '#059669' 
                }} 
                title={`Converted: ${leadAnalytics.converted_leads}`} 
              />
            </div>
          </div>
        </div>

        {/* Section D: Call Analytics */}
        <div className="ti-card">
          <div className="ti-section-header">
            <div className="ti-section-title-wrap">
              <PhoneCall size={18} className="ti-section-icon" />
              <div>
                <h3 className="ti-section-title" style={{ fontSize: '1.05rem' }}>Call Analytics</h3>
                <p className="ti-section-desc">Telephony metrics, call direction & durations</p>
              </div>
            </div>
            <span className="ti-badge ti-badge-green">
              {formatPercent(callAnalytics.answer_rate)} Answer Rate
            </span>
          </div>

          <div className="ti-metric-card-row">
            <div className="ti-mini-stat" onClick={() => openDrilldown('total_calls', callAnalytics.total_calls)}>
              <div className="ti-mini-stat-label">Total Calls</div>
              <div className="ti-mini-stat-val">{formatNumber(callAnalytics.total_calls)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('inbound_calls', callAnalytics.inbound_calls)}>
              <div className="ti-mini-stat-label">Inbound</div>
              <div className="ti-mini-stat-val" style={{ color: '#6d28d9' }}>{formatNumber(callAnalytics.inbound_calls)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('outbound_calls', callAnalytics.outbound_calls)}>
              <div className="ti-mini-stat-label">Outbound</div>
              <div className="ti-mini-stat-val" style={{ color: '#2563eb' }}>{formatNumber(callAnalytics.outbound_calls)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('answered_calls', callAnalytics.answered_calls)}>
              <div className="ti-mini-stat-label">Answered</div>
              <div className="ti-mini-stat-val" style={{ color: '#059669' }}>{formatNumber(callAnalytics.answered_calls)}</div>
            </div>
          </div>

          <div className="ti-metric-card-row">
            <div className="ti-mini-stat" onClick={() => openDrilldown('missed_calls', callAnalytics.missed_calls)}>
              <div className="ti-mini-stat-label">Missed Calls</div>
              <div className="ti-mini-stat-val" style={{ color: '#d97706' }}>{formatNumber(callAnalytics.missed_calls)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('failed_calls', callAnalytics.failed_calls)}>
              <div className="ti-mini-stat-label">Failed Calls</div>
              <div className="ti-mini-stat-val" style={{ color: '#dc2626' }}>{formatNumber(callAnalytics.failed_calls)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('mobile_calls', callAnalytics.mobile_calls)}>
              <div className="ti-mini-stat-label">Mobile Calls</div>
              <div className="ti-mini-stat-val" style={{ color: '#0891b2' }}>{formatNumber(callAnalytics.mobile_calls)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('doocti_calls', callAnalytics.doocti_calls)}>
              <div className="ti-mini-stat-label">Doocti Calls</div>
              <div className="ti-mini-stat-val" style={{ color: '#2563eb' }}>{formatNumber(callAnalytics.doocti_calls)}</div>
            </div>
          </div>

          {/* Duration Metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 14 }}>
            <div 
              style={{ background: '#f8fafc', padding: 12, borderRadius: 8, border: '1px solid #edf2f7', cursor: 'pointer' }}
              onClick={() => openDrilldown('connected_duration_seconds', callAnalytics.connected_calls)}
              title="Click to view connected calls"
            >
              <div style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 600 }}>CONNECTED CALL DURATION</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#059669', marginTop: 4 }}>
                {formatDuration(callAnalytics.connected_duration_seconds)}
              </div>
            </div>

            <div 
              style={{ background: '#f8fafc', padding: 12, borderRadius: 8, border: '1px solid #edf2f7', cursor: 'pointer' }}
              onClick={() => openDrilldown('avg_connected_duration_seconds', callAnalytics.connected_calls)}
              title="Click to view connected calls"
            >
              <div style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 600 }}>AVERAGE CONNECTED DURATION</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', marginTop: 4 }}>
                {formatDuration(callAnalytics.avg_connected_duration_seconds)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ----------------------------------------------------------------------
         Row: Section E (Follow-up Analytics) & Section F (Conversion Analytics)
         ---------------------------------------------------------------------- */}
      <div className="ti-grid-2-col" style={{ marginBottom: 28 }}>
        {/* Section E: Follow-up Analytics */}
        <div className="ti-card">
          <div className="ti-section-header">
            <div className="ti-section-title-wrap">
              <Clock size={18} className="ti-section-icon" />
              <div>
                <h3 className="ti-section-title" style={{ fontSize: '1.05rem' }}>Follow-up Analytics</h3>
                <p className="ti-section-desc">Task completion, overdue schedule & employee execution</p>
              </div>
            </div>
            <span className="ti-badge ti-badge-amber">
              {formatPercent(followupAnalytics.completion_rate)} Completed
            </span>
          </div>

          <div className="ti-metric-card-row">
            <div className="ti-mini-stat" onClick={() => openDrilldown('completed_followups', followupAnalytics.completed_followups)}>
              <div className="ti-mini-stat-label">Completed</div>
              <div className="ti-mini-stat-val" style={{ color: '#059669' }}>{formatNumber(followupAnalytics.completed_followups)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('pending_followups', followupAnalytics.pending_followups)}>
              <div className="ti-mini-stat-label">Pending</div>
              <div className="ti-mini-stat-val" style={{ color: '#d97706' }}>{formatNumber(followupAnalytics.pending_followups)}</div>
            </div>
            <div className="ti-mini-stat" onClick={() => openDrilldown('overdue_followups', followupAnalytics.overdue_followups)}>
              <div className="ti-mini-stat-label">Overdue</div>
              <div className="ti-mini-stat-val" style={{ color: '#dc2626' }}>{formatNumber(followupAnalytics.overdue_followups)}</div>
            </div>
          </div>

          {/* Employee-wise Follow-up Performance */}
          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: 8, textTransform: 'uppercase' }}>
              Employee Follow-up Performance
            </div>
            <div className="ti-table-responsive" style={{ maxHeight: 200 }}>
              <table className="ti-table">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Completed</th>
                    <th>Pending</th>
                    <th>Overdue</th>
                    <th>Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {(followupAnalytics.by_employee || []).map((emp) => (
                    <tr key={emp.employee_id}>
                      <td style={{ fontWeight: 600 }}>{emp.name}</td>
                      <td style={{ color: '#059669' }}>{formatNumber(emp.completed)}</td>
                      <td style={{ color: '#d97706' }}>{formatNumber(emp.pending)}</td>
                      <td style={{ color: '#dc2626' }}>{formatNumber(emp.overdue)}</td>
                      <td>{formatPercent(emp.completion_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Section F: Conversion Analytics */}
        <div className="ti-card">
          <div className="ti-section-header">
            <div className="ti-section-title-wrap">
              <TrendingUp size={18} className="ti-section-icon" />
              <div>
                <h3 className="ti-section-title" style={{ fontSize: '1.05rem' }}>Conversion Analytics</h3>
                <p className="ti-section-desc">Employee conversions, lead source performance & trends</p>
              </div>
            </div>
            <span className="ti-badge ti-badge-green">
              {formatPercent(conversionAnalytics.overall_conversion_percentage)} Overall
            </span>
          </div>

          {/* Lead Source-wise Conversions */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: 8, textTransform: 'uppercase' }}>
              Conversions by Lead Source
            </div>
            <div className="ti-table-responsive">
              <table className="ti-table">
                <thead>
                  <tr>
                    <th>Lead Source</th>
                    <th>Assigned Leads</th>
                    <th>Converted Leads</th>
                    <th>Conversion %</th>
                  </tr>
                </thead>
                <tbody>
                  {(conversionAnalytics.sources || []).length === 0 ? (
                    <tr>
                      <td colSpan={4} style={{ textAlign: 'center', color: '#94a3b8' }}>No source conversions in period.</td>
                    </tr>
                  ) : (
                    (conversionAnalytics.sources || []).map((src) => (
                      <tr key={src.source}>
                        <td style={{ fontWeight: 600 }}>{src.source}</td>
                        <td>{formatNumber(src.assigned_leads)}</td>
                        <td style={{ color: '#059669', fontWeight: 700 }}>{formatNumber(src.converted_leads)}</td>
                        <td>{formatPercent(src.conversion_percentage)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Period-wise Conversion Trends Interactive Chart */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase' }}>
                Period-wise Lead Intake & Trends
              </span>
              {hoveredTrendPoint && (
                <span style={{ fontSize: '0.75rem', color: '#059669', fontWeight: 600 }}>
                  {hoveredTrendPoint.label}: {hoveredTrendPoint.new_leads} new leads ({hoveredTrendPoint.converted_leads} converted)
                </span>
              )}
            </div>

            {/* Native Responsive SVG Chart */}
            <div className="ti-chart-container" style={{ height: 160 }}>
              {(() => {
                const trend = conversionAnalytics.trend || [];
                if (trend.length === 0) {
                  return <div className="ti-modal-empty" style={{ padding: 30 }}>No trend data available for period.</div>;
                }
                const maxVal = Math.max(5, ...trend.map((d) => Math.max(d.new_leads, d.converted_leads)));
                const w = 500;
                const h = 140;
                const padX = 20;
                const padY = 20;
                const innerW = w - padX * 2;
                const innerH = h - padY * 2;

                const step = trend.length > 1 ? innerW / (trend.length - 1) : innerW / 2;
                const points = trend.map((d, i) => {
                  const x = padX + (trend.length > 1 ? i * step : innerW / 2);
                  const y = h - padY - (d.new_leads / maxVal) * innerH;
                  return { x, y, data: d };
                });

                const pathD = points.reduce(
                  (acc, p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`),
                  ''
                );
                const areaD = `${pathD} L ${points[points.length - 1].x} ${h - padY} L ${points[0].x} ${h - padY} Z`;

                return (
                  <svg viewBox={`0 0 ${w} ${h}`} className="ti-chart-svg" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="tiTrendGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#059669" stopOpacity="0.25" />
                        <stop offset="100%" stopColor="#059669" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    {/* Baseline */}
                    <line x1={padX} y1={h - padY} x2={w - padX} y2={h - padY} stroke="#e2e8f0" strokeWidth="1" />

                    {/* Area fill */}
                    <path d={areaD} fill="url(#tiTrendGrad)" />

                    {/* Line */}
                    <path d={pathD} fill="none" stroke="#059669" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

                    {/* Data Points */}
                    {points.map((p, idx) => (
                      <circle
                        key={idx}
                        cx={p.x}
                        cy={p.y}
                        r={p.data.new_leads > 0 ? 4 : 2}
                        fill="#ffffff"
                        stroke="#059669"
                        strokeWidth="2"
                        style={{ cursor: 'pointer' }}
                        onMouseEnter={() => setHoveredTrendPoint(p.data)}
                        onMouseLeave={() => setHoveredTrendPoint(null)}
                      />
                    ))}
                  </svg>
                );
              })()}
            </div>
          </div>
        </div>
      </div>

      {/* ----------------------------------------------------------------------
         Section G: Team Activity Timeline
         ---------------------------------------------------------------------- */}
      <section className="ti-section">
        <div className="ti-card">
          <div className="ti-section-header">
            <div className="ti-section-title-wrap">
              <Calendar size={20} className="ti-section-icon" />
              <div>
                <h2 className="ti-section-title">Team Activity Timeline</h2>
                <p className="ti-section-desc">Audited chronological stream of lead creation, assignment, calls & updates</p>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              {['ALL', 'CALL', 'LEAD_CREATED', 'LEAD_ASSIGNED', 'STATUS_CHANGED', 'FOLLOWUP_COMPLETED'].map((type) => (
                <button
                  key={type}
                  type="button"
                  className={`ti-preset-btn ti-btn-sm ${timelineFilter === type ? 'active' : ''}`}
                  onClick={() => setTimelineFilter(type)}
                >
                  {type === 'ALL' ? 'All Activities' : type.replace(/_/g, ' ')}
                </button>
              ))}

              <button
                type="button"
                className="ti-btn ti-btn-outline ti-btn-sm"
                onClick={() => handleDatasetExport('timeline', 'csv')}
                title="Export timeline to CSV"
                style={{ marginLeft: 8 }}
              >
                <Download size={13} />
                <span>Export Timeline</span>
              </button>
            </div>
          </div>

          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[...Array(4)].map((_, i) => (
                <div key={i} className="ti-skeleton" style={{ height: 50, borderRadius: 8 }} />
              ))}
            </div>
          ) : filteredTimeline.length === 0 ? (
            <div className="ti-modal-empty" style={{ padding: '40px 20px' }}>
              <Calendar size={36} style={{ color: '#cbd5e1', marginBottom: 10 }} />
              <h3>No timeline events recorded</h3>
              <p>No activity records match the selected type or date filters.</p>
            </div>
          ) : (
            <div className="ti-timeline-feed">
              {filteredTimeline.map((item) => {
                const isCall = item.event_type === 'CALL';
                const isLeadCreated = item.event_type === 'LEAD_CREATED';
                const isLeadAssigned = item.event_type === 'LEAD_ASSIGNED';
                const isStatus = item.event_type === 'STATUS_CHANGED';
                const isFollowup = item.event_type === 'FOLLOWUP_COMPLETED';

                return (
                  <div key={item.id} className="ti-timeline-item">
                    <div 
                      className="ti-timeline-icon"
                      style={{
                        background: isCall ? '#ede9fe' : isLeadCreated ? '#dbeafe' : isLeadAssigned ? '#fef3c7' : isStatus ? '#ffedd5' : '#dcfce7',
                        color: isCall ? '#7c3aed' : isLeadCreated ? '#2563eb' : isLeadAssigned ? '#d97706' : isStatus ? '#ea580c' : '#15803d',
                      }}
                    >
                      {isCall && <PhoneCall size={16} />}
                      {isLeadCreated && <UserPlus size={16} />}
                      {isLeadAssigned && <UserCheck size={16} />}
                      {isStatus && <TrendingUp size={16} />}
                      {isFollowup && <CheckCircle2 size={16} />}
                    </div>

                    <div className="ti-timeline-content">
                      <div className="ti-timeline-top">
                        <span className="ti-timeline-title">{item.title}</span>
                        <span className="ti-timeline-time">{formatDateTime(item.timestamp)}</span>
                      </div>
                      <p className="ti-timeline-desc">{item.description}</p>
                      <div className="ti-timeline-author">
                        Actor: {item.employee_name || 'System'}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* ----------------------------------------------------------------------
         Section: Metric Definitions / Source of Truth Note
         ---------------------------------------------------------------------- */}
      <div 
        style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: 8,
          padding: '14px 18px',
          fontSize: '0.78rem',
          color: '#64748b',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 10,
        }}
      >
        <Info size={16} style={{ color: '#059669', flexShrink: 0, marginTop: 2 }} />
        <div>
          <span style={{ fontWeight: 600, color: '#334155' }}>Data Accuracy & Source of Truth: </span>
          All metrics are calculated directly from verified production CRM tables (`leads`, `call_logs`, `followups`, `employees`). Test fixtures and demo records are rigorously excluded. Connected call duration requires verified positive duration. Timezones consistently evaluated in Asia/Kolkata. Clicking any KPI card or cell opens the verified underlying records matching the count.
        </div>
      </div>

      {/* ----------------------------------------------------------------------
         KPI Drilldown Modal
         ---------------------------------------------------------------------- */}
      <DrilldownModal
        isOpen={drilldownState.isOpen}
        onClose={closeDrilldown}
        metric={drilldownState.metric}
        filters={filters}
        employeeContext={drilldownState.employeeContext}
        totalExpected={drilldownState.totalExpected}
      />
    </div>
  );
};

export default TeamInsightsPage;
