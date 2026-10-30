import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import './SalesOverviewReport.css';
import {
  BarChart3,
  Users,
  Phone,
  Target,
  CheckCircle2,
  Handshake,
  XCircle,
  X,
  Calendar,
  Filter,
  RefreshCw,
  PhoneCall,
  Video,
  MessageCircle,
  Mail,
  ChevronDown,
  ArrowUpRight,
  TrendingUp,
  LayoutDashboard
} from 'lucide-react';
import PingoMascot from '../../components/Common/PingoMascot';

const SalesOverviewReport = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Filters state
  const [selectedTeam, setSelectedTeam] = useState('All Teams');
  const [selectedSalesperson, setSelectedSalesperson] = useState(0);
  const [selectedSource, setSelectedSource] = useState('All Lead Sources');
  const [dateRange, setDateRange] = useState('Oct 01, 2026 - Oct 31, 2026');

  const hasActiveFilters = Boolean(
    (selectedTeam && selectedTeam !== 'All Teams') ||
    (selectedSalesperson && selectedSalesperson !== 0) ||
    (selectedSource && selectedSource !== 'All Lead Sources')
  );

  const handleClearFilters = () => {
    setSelectedTeam('All Teams');
    setSelectedSalesperson(0);
    setSelectedSource('All Lead Sources');
    API.get('/reports/sales-overview', { params: {} })
      .then(res => { if (res.data) setData(res.data); })
      .catch(() => {});
  };

  // Interactive Hover states for Chart
  const [hoveredPoint, setHoveredPoint] = useState(null);

  const fetchOverview = async () => {
    try {
      setLoading(true);
      const params = {};
      if (selectedTeam && selectedTeam !== 'All Teams') params.team = selectedTeam;
      if (selectedSalesperson && selectedSalesperson !== 0) params.salesperson_id = selectedSalesperson;
      if (selectedSource && selectedSource !== 'All Lead Sources') params.source = selectedSource;

      const res = await API.get('/reports/sales-overview', { params });
      if (res.data) {
        setData(res.data);
      }
    } catch (err) {
      console.error('Failed to load sales overview report', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
  }, []);

  const handleApplyFilters = () => {
    fetchOverview();
  };

  // Helper for SVG Donut chart calculation
  const renderDonutChart = (items, total) => {
    const size = 150;
    const strokeWidth = 26;
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    let accumulatedAngle = 0;

    return (
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#f1f5f9"
          strokeWidth={strokeWidth}
        />
        {items.map((item, idx) => {
          const ratio = total > 0 ? item.count / total : 0;
          const strokeDasharray = `${ratio * circumference} ${circumference}`;
          const strokeDashoffset = -accumulatedAngle * circumference;
          accumulatedAngle += ratio;

          return (
            <circle
              key={idx}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={item.color}
              strokeWidth={strokeWidth}
              strokeDasharray={strokeDasharray}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="butt"
              style={{ transition: 'stroke-dasharray 0.5s ease' }}
            />
          );
        })}
      </svg>
    );
  };

  // Helper for Trapezoid Sales Funnel SVG
  const renderFunnelSvg = (funnelData) => {
    if (!funnelData || funnelData.length === 0) return null;

    const width = 380;
    const height = 245;
    const segH = 29;
    const gap = 4;
    const startY = 4;
    const labelX = 110;
    const funnelCenterX = 250;

    // Tapering widths from top to bottom
    const widths = [
      { top: 226, btm: 198 },
      { top: 198, btm: 170 },
      { top: 170, btm: 142 },
      { top: 142, btm: 116 },
      { top: 116, btm: 92 },
      { top: 92, btm: 70 },
      { top: 70, btm: 52 }
    ];

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="so-funnel-svg">
        {funnelData.map((fn, idx) => {
          const y1 = startY + idx * (segH + gap);
          const y2 = y1 + segH;
          const wConf = widths[idx] || { top: 70, btm: 50 };
          const x1 = funnelCenterX - wConf.top / 2;
          const x2 = funnelCenterX + wConf.top / 2;
          const x3 = funnelCenterX + wConf.btm / 2;
          const x4 = funnelCenterX - wConf.btm / 2;

          return (
            <g key={idx}>
              {/* Stage Label on the left */}
              <text
                x={labelX}
                y={y1 + segH / 2 + 4}
                textAnchor="end"
                fontSize="11.5"
                fontWeight="600"
                fill="#334155"
              >
                {fn.stage}
              </text>

              {/* Tapered Trapezoid Polygon */}
              <polygon
                points={`${x1},${y1} ${x2},${y1} ${x3},${y2} ${x4},${y2}`}
                fill={fn.color}
                style={{ filter: 'drop-shadow(0 1px 1px rgba(0,0,0,0.06))' }}
              />

              {/* Centered White Value Inside Segment */}
              <text
                x={funnelCenterX}
                y={y1 + segH / 2 + 4}
                textAnchor="middle"
                fontSize="10.5"
                fontWeight="700"
                fill="#ffffff"
              >
                {fn.count.toLocaleString()} ({fn.percentage}%)
              </text>
            </g>
          );
        })}
      </svg>
    );
  };

  // Helper for SVG Multi-Line Trend Chart
  const renderLineChart = (trend) => {
    if (!trend || !trend.series) return null;

    const width = 760;
    const height = 240;
    const padding = { top: 20, right: 30, bottom: 35, left: 45 };

    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;
    const maxVal = 200;

    const seriesConfig = [
      { key: 'new_leads', name: 'New Leads', color: '#2563eb', gradient: 'gradBlue' },
      { key: 'interested', name: 'Interested', color: '#10b981', gradient: 'gradGreen' },
      { key: 'qualified', name: 'Qualified', color: '#f59e0b', gradient: 'gradAmber' },
      { key: 'won', name: 'Won', color: '#8b5cf6', gradient: 'gradPurple' }
    ];

    const numPoints = trend.series.new_leads?.length || 7;
    const getX = (idx) => padding.left + (idx / (numPoints - 1)) * chartW;
    const getY = (val) => padding.top + chartH - (val / maxVal) * chartH;

    // Build smooth cubic Bezier curve string
    const buildSmoothPath = (values) => {
      if (!values || values.length === 0) return '';
      const points = values.map((val, idx) => ({ x: getX(idx), y: getY(val) }));
      let d = `M ${points[0].x} ${points[0].y}`;

      for (let i = 0; i < points.length - 1; i++) {
        const p0 = points[i === 0 ? 0 : i - 1];
        const p1 = points[i];
        const p2 = points[i + 1];
        const p3 = points[i + 2] || p2;

        const cp1x = p1.x + (p2.x - p0.x) / 6;
        const cp1y = p1.y + (p2.y - p0.y) / 6;
        const cp2x = p2.x - (p3.x - p1.x) / 6;
        const cp2y = p2.y - (p3.y - p1.y) / 6;

        d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
      }
      return d;
    };

    const buildAreaPath = (values) => {
      const lineD = buildSmoothPath(values);
      if (!lineD) return '';
      const lastX = getX(values.length - 1);
      const firstX = getX(0);
      const bottomY = padding.top + chartH;
      return `${lineD} L ${lastX} ${bottomY} L ${firstX} ${bottomY} Z`;
    };

    const gridLines = [0, 50, 100, 150, 200];
    const xLabels = trend.labels || ["Oct 1", "Oct 5", "Oct 10", "Oct 15", "Oct 20", "Oct 25", "Oct 31"];

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="so-chart-svg">
        <defs>
          <linearGradient id="gradBlue" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2563eb" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#2563eb" stopOpacity="0.0" />
          </linearGradient>
          <linearGradient id="gradGreen" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity="0.20" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
          </linearGradient>
          <linearGradient id="gradAmber" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.0" />
          </linearGradient>
          <linearGradient id="gradPurple" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Horizontal Grid lines & Y-Axis */}
        {gridLines.map((gl) => {
          const y = getY(gl);
          return (
            <g key={gl}>
              <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke="#f1f5f9"
                strokeDasharray="4 4"
                strokeWidth="1"
              />
              <text
                x={padding.left - 12}
                y={y + 4}
                textAnchor="end"
                fontSize="11"
                fill="#94a3b8"
                fontWeight="500"
              >
                {gl}
              </text>
            </g>
          );
        })}

        {/* X-Axis labels */}
        {xLabels.map((lbl, idx) => {
          const x = padding.left + (idx / (xLabels.length - 1)) * chartW;
          return (
            <text
              key={idx}
              x={x}
              y={height - 10}
              textAnchor="middle"
              fontSize="11"
              fill="#94a3b8"
              fontWeight="500"
            >
              {lbl}
            </text>
          );
        })}

        {/* Area Gradient Fills */}
        {seriesConfig.map((sc) => (
          <path
            key={`area-${sc.key}`}
            d={buildAreaPath(trend.series[sc.key])}
            fill={`url(#${sc.gradient})`}
          />
        ))}

        {/* Lines and Points */}
        {seriesConfig.map((sc) => {
          const vals = trend.series[sc.key] || [];
          return (
            <g key={`series-${sc.key}`}>
              <path
                d={buildSmoothPath(vals)}
                fill="none"
                stroke={sc.color}
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {vals.map((v, idx) => {
                const cx = getX(idx);
                const cy = getY(v);
                return (
                  <circle
                    key={idx}
                    cx={cx}
                    cy={cy}
                    r={hoveredPoint === `${sc.key}-${idx}` ? "5.5" : "3.2"}
                    fill="#ffffff"
                    stroke={sc.color}
                    strokeWidth="2.2"
                    onMouseEnter={() => setHoveredPoint(`${sc.key}-${idx}`)}
                    onMouseLeave={() => setHoveredPoint(null)}
                    style={{ cursor: 'pointer', transition: 'r 0.15s ease' }}
                  >
                    <title>{`${sc.name}: ${v}`}</title>
                  </circle>
                );
              })}
            </g>
          );
        })}
      </svg>
    );
  };

  const kpis = data?.kpis || {};
  const funnel = data?.sales_funnel || [];
  const leadsBySource = data?.leads_by_source || [];
  const leadsByStatus = data?.leads_by_status || [];
  const leadsByLocation = data?.leads_by_location || [];
  const topSalespersons = data?.top_salespersons || [];
  const recentDeals = data?.recent_deals || [];
  const upcomingFollowups = data?.upcoming_followups || [];
  const filterOptions = data?.filter_options || {
    teams: ['All Teams'],
    salespersons: [{ id: 0, name: 'All Salespersons' }],
    lead_sources: ['All Lead Sources']
  };

  const totalSourceLeads = leadsBySource.reduce((acc, curr) => acc + curr.count, 0) || 1240;
  const totalStatusLeads = leadsByStatus.reduce((acc, curr) => acc + curr.count, 0) || 1240;

  return (
    <div className="sales-overview-container">
      {/* Report Switcher Tabs */}
      <div className="report-switcher-tabs">
        <Link to="/reports" className="report-tab-btn active">
          <LayoutDashboard size={15} />
          <span>Sales Overview</span>
        </Link>
        <Link to="/reports?tab=revenue" className="report-tab-btn">
          <TrendingUp size={15} />
          <span>Sales Revenue</span>
        </Link>
        <Link to="/reports?tab=targets" className="report-tab-btn">
          <Target size={15} />
          <span>Target Management</span>
        </Link>
      </div>

      {/* 1. Header & Filters Bar */}
      <div className="so-header">
        <div className="so-title-area">
          <div className="so-icon-badge">
            <BarChart3 size={24} />
          </div>
          <div className="so-title-text">
            <h1>Sales Overview Report</h1>
            <p className="so-subtitle">{data?.date_range || 'Oct 1, 2026 - Oct 31, 2026'}</p>
          </div>
        </div>

        <div className="so-filters-bar">
          <div className="so-date-btn">
            <Calendar size={15} color="#3b82f6" />
            <span>{dateRange}</span>
          </div>

          <select
            className="so-filter-select"
            value={selectedTeam}
            onChange={(e) => setSelectedTeam(e.target.value)}
          >
            {filterOptions.teams?.map((t, idx) => (
              <option key={idx} value={t}>{t}</option>
            ))}
          </select>

          <select
            className="so-filter-select"
            value={selectedSalesperson}
            onChange={(e) => setSelectedSalesperson(Number(e.target.value))}
          >
            {filterOptions.salespersons?.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>

          <select
            className="so-filter-select"
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
          >
            {filterOptions.lead_sources?.map((src, idx) => (
              <option key={idx} value={src}>{src}</option>
            ))}
          </select>

          <button
            type="button"
            className="so-apply-btn"
            onClick={handleApplyFilters}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Apply
          </button>

          {hasActiveFilters && (
            <button
              type="button"
              className="btn-clear-filters"
              onClick={handleClearFilters}
              disabled={loading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '8px 14px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                backgroundColor: '#f1f5f9',
                color: '#475569',
                fontSize: '0.84rem',
                fontWeight: '700',
                cursor: 'pointer'
              }}
              title="Reset all active filters"
            >
              <X size={14} /> Clear
            </button>
          )}
        </div>
      </div>

      {/* 2. Top 6 KPI Metric Cards */}
      <div className="so-kpi-grid">
        {/* Total Leads */}
        <div className="so-kpi-card">
          <div className="so-kpi-top">
            <div className="so-kpi-icon" style={{ backgroundColor: '#eff6ff', color: '#2563eb' }}>
              <Users size={22} />
            </div>
            <div className="so-kpi-meta">
              <span className="so-kpi-label">Total Leads</span>
              <span className="so-kpi-val">{kpis.total_leads?.value?.toLocaleString() || '1,240'}</span>
            </div>
          </div>
          <div className="so-kpi-footer">
            <span className="so-delta-badge">&uarr; {kpis.total_leads?.change || '+12.5%'}</span>
            <span className="so-delta-label">{kpis.total_leads?.vs_label || 'vs last month (1,102)'}</span>
          </div>
        </div>

        {/* Contacted */}
        <div className="so-kpi-card">
          <div className="so-kpi-top">
            <div className="so-kpi-icon" style={{ backgroundColor: '#ecfdf5', color: '#10b981' }}>
              <Phone size={22} />
            </div>
            <div className="so-kpi-meta">
              <span className="so-kpi-label">Contacted</span>
              <span className="so-kpi-val">{kpis.contacted?.value?.toLocaleString() || '980'}</span>
            </div>
          </div>
          <div className="so-kpi-footer">
            <span className="so-delta-badge">&uarr; {kpis.contacted?.change || '+10.2%'}</span>
            <span className="so-delta-label">{kpis.contacted?.vs_label || 'vs last month (889)'}</span>
          </div>
        </div>

        {/* Interested */}
        <div className="so-kpi-card">
          <div className="so-kpi-top">
            <div className="so-kpi-icon" style={{ backgroundColor: '#fff1f2', color: '#f43f5e' }}>
              <Target size={22} />
            </div>
            <div className="so-kpi-meta">
              <span className="so-kpi-label">Interested</span>
              <span className="so-kpi-val">{kpis.interested?.value?.toLocaleString() || '620'}</span>
            </div>
          </div>
          <div className="so-kpi-footer">
            <span className="so-delta-badge">&uarr; {kpis.interested?.change || '+15.3%'}</span>
            <span className="so-delta-label">{kpis.interested?.vs_label || 'vs last month (538)'}</span>
          </div>
        </div>

        {/* Qualified */}
        <div className="so-kpi-card">
          <div className="so-kpi-top">
            <div className="so-kpi-icon" style={{ backgroundColor: '#f0fdf4', color: '#16a34a' }}>
              <CheckCircle2 size={22} />
            </div>
            <div className="so-kpi-meta">
              <span className="so-kpi-label">Qualified</span>
              <span className="so-kpi-val">{kpis.qualified?.value?.toLocaleString() || '420'}</span>
            </div>
          </div>
          <div className="so-kpi-footer">
            <span className="so-delta-badge">&uarr; {kpis.qualified?.change || '+8.1%'}</span>
            <span className="so-delta-label">{kpis.qualified?.vs_label || 'vs last month (388)'}</span>
          </div>
        </div>

        {/* Won Deals */}
        <div className="so-kpi-card">
          <div className="so-kpi-top">
            <div className="so-kpi-icon" style={{ backgroundColor: '#fffbeb', color: '#f59e0b' }}>
              <Handshake size={22} />
            </div>
            <div className="so-kpi-meta">
              <span className="so-kpi-label">Won Deals</span>
              <span className="so-kpi-val">{kpis.won_deals?.value?.toLocaleString() || '98'}</span>
            </div>
          </div>
          <div className="so-kpi-footer">
            <span className="so-delta-badge">&uarr; {kpis.won_deals?.change || '+18.1%'}</span>
            <span className="so-delta-label">{kpis.won_deals?.vs_label || 'vs last month (83)'}</span>
          </div>
        </div>

        {/* Lost Deals */}
        <div className="so-kpi-card">
          <div className="so-kpi-top">
            <div className="so-kpi-icon" style={{ backgroundColor: '#fef2f2', color: '#ef4444' }}>
              <XCircle size={22} />
            </div>
            <div className="so-kpi-meta">
              <span className="so-kpi-label">Lost Deals</span>
              <span className="so-kpi-val">{kpis.lost_deals?.value?.toLocaleString() || '72'}</span>
            </div>
          </div>
          <div className="so-kpi-footer">
            <span className="so-delta-badge">&uarr; {kpis.lost_deals?.change || '+5.9%'}</span>
            <span className="so-delta-label">{kpis.lost_deals?.vs_label || 'vs last month (68)'}</span>
          </div>
        </div>
      </div>

      {/* 3. Row 2: Lead Trend & Sales Funnel */}
      <div className="so-row-2">
        {/* Left: Lead Trend */}
        <div className="so-card">
          <div className="so-card-header">
            <h2 className="so-card-title">Lead Trend</h2>
            <div className="so-card-legends">
              <div className="so-legend-item">
                <span className="so-legend-dot" style={{ backgroundColor: '#2563eb' }} />
                <span>New Leads</span>
              </div>
              <div className="so-legend-item">
                <span className="so-legend-dot" style={{ backgroundColor: '#10b981' }} />
                <span>Interested</span>
              </div>
              <div className="so-legend-item">
                <span className="so-legend-dot" style={{ backgroundColor: '#f59e0b' }} />
                <span>Qualified</span>
              </div>
              <div className="so-legend-item">
                <span className="so-legend-dot" style={{ backgroundColor: '#8b5cf6' }} />
                <span>Won</span>
              </div>
            </div>
          </div>
          <div className="so-chart-container">
            {renderLineChart(data?.lead_trend)}
          </div>
        </div>

        {/* Right: Sales Funnel */}
        <div className="so-card">
          <div className="so-card-header">
            <h2 className="so-card-title">Sales Funnel</h2>
          </div>
          <div className="so-funnel-svg-container">
            {renderFunnelSvg(funnel)}
          </div>
        </div>
      </div>

      {/* 4. Row 3: 3 Breakdown Cards */}
      <div className="so-row-3">
        {/* Leads by Source */}
        <div className="so-card">
          <div className="so-card-header">
            <h2 className="so-card-title">Leads by Source</h2>
          </div>
          <div className="so-donut-layout">
            <div className="so-donut-svg-wrapper">
              {renderDonutChart(leadsBySource, totalSourceLeads)}
              <div className="so-donut-center-text">
                <div className="so-donut-total">{totalSourceLeads.toLocaleString()}</div>
                <div className="so-donut-sub">Total Leads</div>
              </div>
            </div>

            <div className="so-donut-legend-list">
              {leadsBySource.map((s, idx) => (
                <div key={idx} className="so-donut-legend-row">
                  <div className="so-donut-legend-name">
                    <span className="so-legend-dot" style={{ backgroundColor: s.color }} />
                    <span>{s.name}</span>
                  </div>
                  <div className="so-donut-legend-vals">
                    <span className="so-donut-count">{s.count.toLocaleString()}</span>
                    <span className="so-donut-percent">{s.percentage}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Leads by Status */}
        <div className="so-card">
          <div className="so-card-header">
            <h2 className="so-card-title">Leads by Status</h2>
          </div>
          <div className="so-donut-layout">
            <div className="so-donut-svg-wrapper">
              {renderDonutChart(leadsByStatus, totalStatusLeads)}
              <div className="so-donut-center-text">
                <div className="so-donut-total">{totalStatusLeads.toLocaleString()}</div>
                <div className="so-donut-sub">Total Leads</div>
              </div>
            </div>

            <div className="so-donut-legend-list">
              {leadsByStatus.map((st, idx) => (
                <div key={idx} className="so-donut-legend-row">
                  <div className="so-donut-legend-name">
                    <span className="so-legend-dot" style={{ backgroundColor: st.color }} />
                    <span>{st.name}</span>
                  </div>
                  <div className="so-donut-legend-vals">
                    <span className="so-donut-count">{st.count.toLocaleString()}</span>
                    <span className="so-donut-percent">{st.percentage}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Leads by Location */}
        <div className="so-card">
          <div className="so-card-header">
            <h2 className="so-card-title">Leads by Location</h2>
          </div>
          <div className="so-location-list">
            {leadsByLocation.map((loc, idx) => {
              const maxLoc = 320;
              const fillPct = Math.min(100, Math.round((loc.count / maxLoc) * 100));
              return (
                <div key={idx} className="so-location-row">
                  <span className="so-loc-name">{loc.city}</span>
                  <div className="so-loc-bar-bg">
                    <div
                      className="so-loc-bar-fill"
                      style={{
                        width: `${fillPct}%`,
                        backgroundColor: loc.color
                      }}
                    />
                  </div>
                  <span className="so-loc-count">{loc.count}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 5. Row 4: 3 Detailed Tables */}
      <div className="so-row-4">
        {/* Top Salespersons (Leads & Deals) */}
        <div className="so-card">
          <div className="so-card-header">
            <h2 className="so-card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <PingoMascot pose="victory" height={28} withShadow={false} />
              <span>Top Salespersons (Leads & Deals)</span>
            </h2>
            <a href="#view-all" className="so-view-all-link">View All</a>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="so-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Salesperson</th>
                  <th>Total Leads</th>
                  <th>Contacted</th>
                  <th>Qualified</th>
                  <th>Won Deals</th>
                  <th>Conversion</th>
                  <th>Revenue</th>
                </tr>
              </thead>
              <tbody>
                {topSalespersons.map((sp) => (
                  <tr key={sp.rank}>
                    <td className="so-rank">{sp.rank}</td>
                    <td className="so-user-cell">{sp.name}</td>
                    <td className="so-num-cell">{sp.total_leads}</td>
                    <td className="so-num-cell">{sp.contacted}</td>
                    <td className="so-num-cell">{sp.qualified}</td>
                    <td className="so-num-cell">{sp.won_deals}</td>
                    <td>
                      <span className="so-conv-badge">{sp.conversion_rate}</span>
                    </td>
                    <td className="so-rev-val">{sp.revenue}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Deals */}
        <div className="so-card">
          <div className="so-card-header">
            <h2 className="so-card-title">Recent Deals</h2>
            <a href="#view-all" className="so-view-all-link">View All</a>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="so-table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Deal Name</th>
                  <th>Amount</th>
                  <th>Stage</th>
                </tr>
              </thead>
              <tbody>
                {recentDeals.map((d, idx) => {
                  const stageClass = d.stage === 'Won'
                    ? 'so-stage-won'
                    : (d.stage === 'Proposal' ? 'so-stage-proposal' : (d.stage === 'Negotiation' ? 'so-stage-negotiation' : 'so-stage-followup'));
                  return (
                    <tr key={idx}>
                      <td className="so-user-cell">{d.customer}</td>
                      <td>{d.deal_name}</td>
                      <td className="so-num-cell">{d.amount}</td>
                      <td>
                        <span className={`so-stage-badge ${stageClass}`}>{d.stage}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Upcoming Follow-ups */}
        <div className="so-card">
          <div className="so-card-header">
            <h2 className="so-card-title">Upcoming Follow-ups</h2>
            <a href="#view-all" className="so-view-all-link">View All</a>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="so-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Customer</th>
                  <th>Salesperson</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {upcomingFollowups.map((uf, idx) => {
                  let typeClass = 'so-type-call';
                  let Icon = PhoneCall;
                  if (uf.type === 'Meeting') {
                    typeClass = 'so-type-meeting';
                    Icon = Video;
                  } else if (uf.type === 'WhatsApp') {
                    typeClass = 'so-type-whatsapp';
                    Icon = MessageCircle;
                  } else if (uf.type === 'Email') {
                    typeClass = 'so-type-email';
                    Icon = Mail;
                  }

                  return (
                    <tr key={idx}>
                      <td>{uf.time}</td>
                      <td className="so-user-cell">{uf.customer}</td>
                      <td>{uf.salesperson}</td>
                      <td>
                        <div className={`so-type-cell ${typeClass}`}>
                          <Icon size={14} />
                          <span>{uf.type}</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SalesOverviewReport;
