import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import PingoPopupService from '../../services/pingoPopupService';
import './SalesRevenueReport.css';
import {
  BarChart3,
  Wallet,
  Target,
  PieChart,
  Trophy,
  Calendar,
  RefreshCw,
  Download,
  MoreVertical,
  TrendingUp,
  LayoutDashboard
} from 'lucide-react';

const SalesRevenueReport = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Filters state
  const [selectedTeam, setSelectedTeam] = useState('All Teams');
  const [selectedSalesperson, setSelectedSalesperson] = useState(0);
  const [dateRange, setDateRange] = useState('Oct 01, 2026 - Oct 31, 2026');

  const fetchRevenue = async () => {
    try {
      setLoading(true);
      const params = {};
      if (selectedTeam && selectedTeam !== 'All Teams') params.team = selectedTeam;
      if (selectedSalesperson && selectedSalesperson !== 0) params.salesperson_id = selectedSalesperson;

      const res = await API.get('/reports/sales-revenue', { params });
      if (res.data) {
        setData(res.data);
      }
    } catch (err) {
      console.error('Failed to load sales revenue report', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRevenue();
  }, []);

  const handleApply = () => {
    fetchRevenue();
  };

  const handleExportDeals = () => {
    if (!dealsDetails || !dealsDetails.length) return;
    const headers = ['ID', 'Customer', 'Deal Name', 'Salesperson', 'Amount', 'Status', 'Expected Close', 'Won Date'];
    const rows = dealsDetails.map(d => [
      `"${d.id || ''}"`,
      `"${(d.customer || '').replace(/"/g, '""')}"`,
      `"${(d.deal_name || '').replace(/"/g, '""')}"`,
      `"${(d.salesperson || '').replace(/"/g, '""')}"`,
      `"${(d.amount || '').replace(/"/g, '""')}"`,
      `"${(d.status || '').replace(/"/g, '""')}"`,
      `"${(d.expected_close || '').replace(/"/g, '""')}"`,
      `"${(d.won_date || '').replace(/"/g, '""')}"`
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', 'Deal_Revenue_Details.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    PingoPopupService.triggerDownloadSuccess({
      docType: 'Report',
      fileName: 'Deal_Revenue_Details.csv',
      reference: 'Deal / Revenue',
      customMessage: 'Deal & Revenue details exported successfully!'
    });
  };

  // Helper for SVG Donut chart calculation
  const renderDonutChart = (items, totalStr) => {
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
          const ratio = item.percentage / 100;
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

  // Monthly Revenue Trend Multi-Line SVG Chart
  const renderMonthlyTrendChart = (trend) => {
    if (!trend || !trend.months) return null;

    const width = 640;
    const height = 240;
    const padding = { top: 30, right: 35, bottom: 35, left: 50 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;
    const allVals = [...(trend.revenue || []), ...(trend.target || [])];
    const maxData = Math.max(0.2, ...allVals);
    const maxVal = Math.max(1, Math.ceil(maxData * 1.25 * 10) / 10);

    const getX = (idx) => padding.left + (idx / Math.max(1, trend.months.length - 1)) * chartW;
    const getY = (val) => padding.top + chartH - (Math.max(0, val) / maxVal) * chartH;

    const step = maxVal / 4;
    const gridLines = [0, step, step * 2, step * 3, maxVal].map(v => Number(v.toFixed(2)));

    // Build SVG Path
    const buildPath = (vals) => {
      return vals.map((v, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(v)}`).join(' ');
    };

    const buildArea = (vals) => {
      const line = buildPath(vals);
      const lastX = getX(vals.length - 1);
      const firstX = getX(0);
      const bottomY = padding.top + chartH;
      return `${line} L ${lastX} ${bottomY} L ${firstX} ${bottomY} Z`;
    };

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="sr-chart-svg">
        <defs>
          <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Gridlines */}
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
                x={padding.left - 10}
                y={y + 4}
                textAnchor="end"
                fontSize="11"
                fill="#94a3b8"
                fontWeight="500"
              >
                {gl >= 1 ? `₹${gl.toFixed(1)} L` : `₹${Math.round(gl * 100)}k`}
              </text>
            </g>
          );
        })}

        {/* X-Axis Month labels */}
        {trend.months.map((m, idx) => (
          <text
            key={idx}
            x={getX(idx)}
            y={height - 10}
            textAnchor="middle"
            fontSize="11"
            fill="#94a3b8"
            fontWeight="500"
          >
            {m}
          </text>
        ))}

        {/* Revenue Area Fill */}
        <path d={buildArea(trend.revenue)} fill="url(#revenueGrad)" />

        {/* Target Line (Blue) */}
        <path
          d={buildPath(trend.target)}
          fill="none"
          stroke="#3b82f6"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
        {trend.target.map((v, idx) => (
          <circle
            key={`tgt-${idx}`}
            cx={getX(idx)}
            cy={getY(v)}
            r="3.5"
            fill="#3b82f6"
          />
        ))}

        {/* Revenue Line (Green) */}
        <path
          d={buildPath(trend.revenue)}
          fill="none"
          stroke="#10b981"
          strokeWidth="2.6"
          strokeLinecap="round"
        />
        {trend.revenue.map((v, idx) => (
          <g key={`rev-${idx}`}>
            <circle
              cx={getX(idx)}
              cy={getY(v)}
              r="4.2"
              fill="#ffffff"
              stroke="#10b981"
              strokeWidth="2.4"
            />
            {/* Value Label above point */}
            <text
              x={getX(idx)}
              y={getY(v) - 9}
              textAnchor="middle"
              fontSize="10"
              fontWeight="700"
              fill="#0f172a"
            >
              ₹{v} L
            </text>
          </g>
        ))}
      </svg>
    );
  };

  // Name formatter to prevent label collisions on chart axes
  const formatChartName = (name, shortName) => {
    if (shortName) return shortName;
    if (!name) return '';
    const trimmed = name.trim();
    if (/^system\s+administrator$/i.test(trimmed)) return 'Admin';
    const parts = trimmed.split(/\s+/);
    if (parts.length > 1) {
      return `${parts[0]} ${parts[1][0]}.`;
    }
    if (trimmed.length > 9) {
      return `${trimmed.slice(0, 8)}…`;
    }
    return trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  };

  // Vertical Bar Chart Helper for Salesperson
  const renderSalespersonChart = (items) => {
    if (!items || items.length === 0) return null;

    const width = 520;
    const height = 250;
    const padding = { top: 32, right: 20, bottom: 42, left: 50 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;
    const maxData = Math.max(0.2, ...items.map(i => i.revenue || 0));
    const maxVal = Math.max(1, Math.ceil(maxData * 1.25 * 10) / 10);

    const barW = Math.min(38, Math.max(22, Math.floor(chartW / Math.max(1, items.length * 1.8))));
    const getY = (val) => padding.top + chartH - (Math.max(0, val) / maxVal) * chartH;
    const step = maxVal / 4;
    const gridLines = [0, step, step * 2, step * 3, maxVal].map(v => Number(v.toFixed(2)));

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="sr-chart-svg">
        {/* Gridlines */}
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
                x={padding.left - 8}
                y={y + 4}
                textAnchor="end"
                fontSize="11"
                fill="#94a3b8"
                fontWeight="500"
              >
                {gl >= 1 ? `₹${gl.toFixed(1)} L` : `₹${Math.round(gl * 100)}k`}
              </text>
            </g>
          );
        })}

        {/* Bars */}
        {items.map((sp, idx) => {
          const cx = padding.left + (idx + 0.5) * (chartW / items.length);
          const x = cx - barW / 2;
          const y = getY(sp.revenue);
          const bH = (padding.top + chartH) - y;
          const displayName = formatChartName(sp.name, sp.short_name);

          return (
            <g key={idx}>
              <title>{sp.name}: {sp.formatted}</title>

              {/* Value Label above Bar */}
              <text
                x={cx}
                y={y - 8}
                textAnchor="middle"
                fontSize="11"
                fontWeight="700"
                fill="#0f172a"
              >
                {sp.formatted}
              </text>

              {/* Bar Rect */}
              <rect
                x={x}
                y={y}
                width={barW}
                height={bH}
                fill={sp.color}
                rx="4"
              />

              {/* Salesperson Name under bar */}
              <text
                x={cx}
                y={height - 12}
                textAnchor="middle"
                fontSize="11"
                fontWeight="600"
                fill="#475569"
              >
                {displayName}
              </text>
            </g>
          );
        })}
      </svg>
    );
  };

  // Vertical Bar Chart Helper for Deal Status by Revenue
  const renderDealStatusChart = (items) => {
    if (!items || items.length === 0) return null;

    const width = 520;
    const height = 250;
    const padding = { top: 32, right: 20, bottom: 42, left: 50 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;
    const maxData = Math.max(0.2, ...items.map(i => i.val || 0));
    const maxVal = Math.max(1, Math.ceil(maxData * 1.25 * 10) / 10);

    const barW = Math.min(42, Math.max(24, Math.floor(chartW / Math.max(1, items.length * 1.8))));
    const getY = (val) => padding.top + chartH - (Math.max(0, val) / maxVal) * chartH;
    const step = maxVal / 4;
    const gridLines = [0, step, step * 2, step * 3, maxVal].map(v => Number(v.toFixed(2)));

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="sr-chart-svg">
        {/* Gridlines */}
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
                x={padding.left - 8}
                y={y + 4}
                textAnchor="end"
                fontSize="11"
                fill="#94a3b8"
                fontWeight="500"
              >
                {gl >= 1 ? `₹${gl.toFixed(1)} L` : `₹${Math.round(gl * 100)}k`}
              </text>
            </g>
          );
        })}

        {/* Bars */}
        {items.map((st, idx) => {
          const cx = padding.left + (idx + 0.5) * (chartW / items.length);
          const x = cx - barW / 2;
          const y = getY(st.val);
          const bH = (padding.top + chartH) - y;
          const stageDisplay = st.stage === 'Proposal Sent' ? 'Proposal' : st.stage;

          return (
            <g key={idx}>
              <title>{st.stage}: {st.amount}</title>

              {/* Value Label above Bar */}
              <text
                x={cx}
                y={y - 8}
                textAnchor="middle"
                fontSize="11"
                fontWeight="700"
                fill="#0f172a"
              >
                {st.amount}
              </text>

              {/* Bar Rect */}
              <rect
                x={x}
                y={y}
                width={barW}
                height={bH}
                fill={st.color}
                rx="4"
              />

              {/* Stage label under bar */}
              <text
                x={cx}
                y={height - 12}
                textAnchor="middle"
                fontSize="10.5"
                fontWeight="600"
                fill="#475569"
              >
                {stageDisplay}
              </text>
            </g>
          );
        })}
      </svg>
    );
  };

  const kpis = data?.kpis || {};
  const monthlyTrend = data?.monthly_trend || { months: [], revenue: [], target: [] };
  const revenueBySalesperson = data?.revenue_by_salesperson || [];
  const revenueBySource = data?.revenue_by_source || [];
  const dealStatusByRevenue = data?.deal_status_by_revenue || [];
  const dealsDetails = data?.deals_details || [];
  const filterOptions = data?.filter_options || {
    teams: ['All Teams'],
    salespersons: [{ id: 0, name: 'All Salespersons' }]
  };

  return (
    <div className="sales-revenue-container">
      {/* Report Switcher Tabs */}
      <div className="report-switcher-tabs">
        <Link to="/reports" className="report-tab-btn">
          <LayoutDashboard size={15} />
          <span>Sales Overview</span>
        </Link>
        <Link to="/reports?tab=revenue" className="report-tab-btn active">
          <TrendingUp size={15} />
          <span>Sales Revenue</span>
        </Link>
      </div>

      {/* 1. Header & Filters */}
      <div className="sr-header">
        <div className="sr-title-area">
          <div className="sr-icon-badge">
            <BarChart3 size={24} />
          </div>
          <div className="sr-title-text">
            <h1>Sales Revenue Report</h1>
            <p className="sr-subtitle">{data?.date_range || 'Oct 1, 2026 - Oct 31, 2026'}</p>
          </div>
        </div>

        <div className="sr-filters-bar">
          <div className="sr-date-btn">
            <Calendar size={15} color="#3b82f6" />
            <span>{dateRange}</span>
          </div>

          <select
            className="sr-filter-select"
            value={selectedTeam}
            onChange={(e) => setSelectedTeam(e.target.value)}
          >
            {filterOptions.teams?.map((t, idx) => (
              <option key={idx} value={t}>{t}</option>
            ))}
          </select>

          <select
            className="sr-filter-select"
            value={selectedSalesperson}
            onChange={(e) => setSelectedSalesperson(Number(e.target.value))}
          >
            {filterOptions.salespersons?.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>

          <button
            type="button"
            className="sr-apply-btn"
            onClick={handleApply}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Apply
          </button>
        </div>
      </div>

      {/* 2. Top 4 KPI Cards */}
      <div className="sr-kpi-grid">
        {/* Total Revenue */}
        <div className="sr-kpi-card">
          <div className="sr-kpi-top">
            <div className="sr-kpi-icon" style={{ backgroundColor: '#dcfce7', color: '#059669' }}>
              <Wallet size={22} />
            </div>
            <div className="sr-kpi-meta">
              <span className="sr-kpi-label">Total Revenue</span>
              <span className="sr-kpi-val" style={{ color: '#059669' }}>{kpis.total_revenue?.value || '₹0'}</span>
            </div>
          </div>
          <div className="sr-kpi-footer">
            <span>&uarr; {kpis.total_revenue?.change || '0%'}</span>
            <span className="label">{kpis.total_revenue?.vs_label || 'vs last month'}</span>
          </div>
        </div>

        {/* Target */}
        <div className="sr-kpi-card">
          <div className="sr-kpi-top">
            <div className="sr-kpi-icon" style={{ backgroundColor: '#e0f2fe', color: '#0284c7' }}>
              <Target size={22} />
            </div>
            <div className="sr-kpi-meta">
              <span className="sr-kpi-label">Target</span>
              <span className="sr-kpi-val" style={{ color: '#2563eb' }}>{kpis.target?.value || '₹0'}</span>
            </div>
          </div>
          <div className="sr-progress-track">
            <div
              className="sr-progress-fill"
              style={{ width: `${kpis.target?.achieved_pct || 0}%`, backgroundColor: '#2563eb' }}
            />
          </div>
          <div className="sr-kpi-footer">
            <span className="label">{kpis.target?.vs_label || '0% achieved'}</span>
          </div>
        </div>

        {/* Pipeline Value */}
        <div className="sr-kpi-card">
          <div className="sr-kpi-top">
            <div className="sr-kpi-icon" style={{ backgroundColor: '#f3e8ff', color: '#7e22ce' }}>
              <PieChart size={22} />
            </div>
            <div className="sr-kpi-meta">
              <span className="sr-kpi-label">Pipeline Value</span>
              <span className="sr-kpi-val" style={{ color: '#7e22ce' }}>{kpis.pipeline_value?.value || '₹0'}</span>
            </div>
          </div>
          <div className="sr-kpi-footer">
            <span>&uarr; {kpis.pipeline_value?.change || '0%'}</span>
            <span className="label">{kpis.pipeline_value?.vs_label || 'vs last month'}</span>
          </div>
        </div>

        {/* Achievement */}
        <div className="sr-kpi-card">
          <div className="sr-kpi-top">
            <div className="sr-kpi-icon" style={{ backgroundColor: '#fef3c7', color: '#d97706' }}>
              <Trophy size={22} />
            </div>
            <div className="sr-kpi-meta">
              <span className="sr-kpi-label">Achievement</span>
              <span className="sr-kpi-val" style={{ color: '#ea580c' }}>{kpis.achievement?.value || '0%'}</span>
            </div>
          </div>
          <div className="sr-kpi-footer">
            <span>&uarr; {kpis.achievement?.change || '0%'}</span>
            <span className="label">{kpis.achievement?.vs_label || 'vs last month'}</span>
          </div>
        </div>
      </div>

      {/* 3. Row 2: Monthly Revenue Trend & Revenue by Salesperson */}
      <div className="sr-row-2">
        {/* Left: Monthly Revenue Trend */}
        <div className="sr-card">
          <div className="sr-card-header">
            <h2 className="sr-card-title">Monthly Revenue Trend</h2>
            <div className="sr-card-legends">
              <div className="sr-legend-item">
                <span className="sr-legend-dot" style={{ backgroundColor: '#10b981' }} />
                <span>Revenue</span>
              </div>
              <div className="sr-legend-item">
                <span className="sr-legend-dot" style={{ backgroundColor: '#3b82f6' }} />
                <span>Target</span>
              </div>
            </div>
          </div>
          <div className="sr-chart-container">
            {renderMonthlyTrendChart(monthlyTrend)}
          </div>
        </div>

        {/* Right: Revenue by Salesperson */}
        <div className="sr-card">
          <div className="sr-card-header">
            <h2 className="sr-card-title">Revenue by Salesperson</h2>
          </div>
          <div className="sr-chart-container">
            {renderSalespersonChart(revenueBySalesperson)}
          </div>
        </div>
      </div>

      {/* 4. Row 3: Revenue by Lead Source & Deal Status by Revenue */}
      <div className="sr-row-3">
        {/* Left: Revenue by Lead Source */}
        <div className="sr-card">
          <div className="sr-card-header">
            <h2 className="sr-card-title">Revenue by Lead Source</h2>
          </div>
          <div className="sr-donut-layout">
            <div className="sr-donut-wrapper">
              {renderDonutChart(revenueBySource, kpis.total_revenue?.value || '₹0')}
              <div className="sr-donut-center">
                <div className="sr-donut-total">{kpis.total_revenue?.value || '₹0'}</div>
                <div className="sr-donut-sub">Total Revenue</div>
              </div>
            </div>

            <table className="sr-source-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Leads</th>
                  <th>Won</th>
                  <th>Revenue</th>
                  <th>%</th>
                </tr>
              </thead>
              <tbody>
                {revenueBySource.map((s, idx) => (
                  <tr key={idx}>
                    <td>
                      <div className="sr-source-name">
                        <span className="sr-legend-dot" style={{ backgroundColor: s.color }} />
                        <span>{s.source}</span>
                      </div>
                    </td>
                    <td>{s.leads}</td>
                    <td>{s.won}</td>
                    <td style={{ fontWeight: 700 }}>{s.revenue}</td>
                    <td style={{ color: '#64748b' }}>{s.percentage}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: Deal Status by Revenue */}
        <div className="sr-card">
          <div className="sr-card-header">
            <h2 className="sr-card-title">Deal Status by Revenue</h2>
          </div>
          <div className="sr-chart-container">
            {renderDealStatusChart(dealStatusByRevenue)}
          </div>
        </div>
      </div>

      {/* 5. Row 4: Deal / Revenue Details */}
      <div className="sr-card">
        <div className="sr-card-header">
          <h2 className="sr-card-title">Deal / Revenue Details</h2>
          <button type="button" className="sr-export-btn" onClick={handleExportDeals}>
            <Download size={14} />
            <span>Export</span>
          </button>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="sr-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Customer</th>
                <th>Deal Name</th>
                <th>Salesperson</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Expected Close Date</th>
                <th>Won Date</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {dealsDetails.map((d) => {
                const badgeClass = d.status === 'Won'
                  ? 'sr-badge-won'
                  : (d.status === 'Proposal Sent' ? 'sr-badge-proposal' : 'sr-badge-negotiation');

                return (
                  <tr key={d.id}>
                    <td style={{ color: '#64748b', fontWeight: 600 }}>{d.id}</td>
                    <td style={{ fontWeight: 700, color: '#0f172a' }}>{d.customer}</td>
                    <td>{d.deal_name}</td>
                    <td>{d.salesperson}</td>
                    <td style={{ fontWeight: 700, color: '#0f172a' }}>{d.amount}</td>
                    <td>
                      <span className={badgeClass}>{d.status}</span>
                    </td>
                    <td style={{ color: '#64748b' }}>{d.expected_close}</td>
                    <td style={{ color: '#64748b' }}>{d.won_date}</td>
                    <td style={{ textAlign: 'right' }}>
                      <button type="button" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}>
                        <MoreVertical size={16} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default SalesRevenueReport;
