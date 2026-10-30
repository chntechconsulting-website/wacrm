import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import CallAISummaryModal from '../../components/IVR/CallAISummaryModal';
import { probeAudioDuration, rewindAfterProbe } from '../../utils/audioUtils';
import { 
  Users, 
  PhoneCall, 
  Clock, 
  TrendingUp, 
  Activity, 
  MapPin, 
  ShieldCheck, 
  Calendar, 
  Filter, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Search,
  ExternalLink,
  RefreshCw,
  Eye,
  Camera,
  MessageCircle,
  Award,
  Check,
  Lock,
  ArrowRight,
  Sparkles,
  Volume2,
  FileText,
  Brain,
  Headphones,
  Play
} from 'lucide-react';

const EmployeeMonitoring = () => {
  const navigate = useNavigate();
  const { user: currentUser } = useAuth();
  const isEmployeeRole = currentUser?.role?.toUpperCase() === 'EMPLOYEE';

  const [activeTab, setActiveTab] = useState('overview');
  const [dateFilter, setDateFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);

  // Stats & Lists
  const [overview, setOverview] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [activities, setActivities] = useState([]);
  const [fieldVisits, setFieldVisits] = useState([]);
  const [callLogs, setCallLogs] = useState([]);
  const [selectedCallLog, setSelectedCallLog] = useState(null);
  const [showAIModal, setShowAIModal] = useState(false);

  const [retentionSettings, setRetentionSettings] = useState({
    activity_retention_days: 90,
    call_retention_days: 180,
    field_retention_days: 180
  });

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [callEmployeeFilter, setCallEmployeeFilter] = useState('');
  const [callStatusFilter, setCallStatusFilter] = useState('');

  // Field Check-in Form State
  const [showCheckinModal, setShowCheckinModal] = useState(false);
  const [checkinForm, setCheckinForm] = useState({
    customer_name: '',
    checkin_lat: '13.0827',
    checkin_lng: '80.2707',
    notes: '',
    photo_url: ''
  });
  const [submittingCheckin, setSubmittingCheckin] = useState(false);
  const [toastMessage, setToastMessage] = useState('');

  const fetchMonitoringData = async () => {
    try {
      setLoading(true);
      const [overviewRes, empRes, actRes, visitRes, callsRes, settingsRes] = await Promise.all([
        API.get(`/employee-monitoring/overview?date_filter=${dateFilter}`).catch(() => ({ data: null })),
        API.get(`/employee-monitoring/employees?date_filter=${dateFilter}`).catch(() => ({ data: [] })),
        API.get(`/employee-monitoring/activity?date_filter=${dateFilter}`).catch(() => ({ data: [] })),
        API.get(`/employee-monitoring/field-visits`).catch(() => ({ data: [] })),
        API.get(`/employee-monitoring/calls?date_filter=${dateFilter}`).catch(() => ({ data: [] })),
        API.get(`/employee-monitoring/settings/retention`).catch(() => ({ data: null }))
      ]);

      if (overviewRes.data) setOverview(overviewRes.data);
      if (empRes.data) setEmployees(empRes.data);
      if (actRes.data) setActivities(actRes.data);
      if (visitRes.data) setFieldVisits(visitRes.data);
      if (callsRes.data) setCallLogs(callsRes.data);
      if (settingsRes.data) setRetentionSettings(settingsRes.data);
    } catch (err) {
      console.error("Error fetching monitoring data:", err);
    } finally {
      setLoading(false);
    }
  };

  // Heartbeat presence recording
  useEffect(() => {
    const sendHeartbeat = async () => {
      try {
        await API.post('/employee-monitoring/presence/heartbeat');
      } catch (e) {
        // Silently ignore
      }
    };
    sendHeartbeat();
    const interval = setInterval(sendHeartbeat, 60000); // Heartbeat every 60s
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    fetchMonitoringData();
  }, [dateFilter]);

  const handleSaveRetention = async (e) => {
    e.preventDefault();
    try {
      await API.put('/employee-monitoring/settings/retention', retentionSettings);
      setToastMessage('Retention settings updated successfully.');
      setTimeout(() => setToastMessage(''), 3000);
    } catch (e) {
      setToastMessage('Only ADMIN can update retention settings.');
      setTimeout(() => setToastMessage(''), 3000);
    }
  };

  const handleCheckinSubmit = async (e) => {
    e.preventDefault();
    if (!checkinForm.customer_name) return;
    try {
      setSubmittingCheckin(true);
      await API.post('/employee-monitoring/field-visits/check-in', checkinForm);
      setShowCheckinModal(false);
      setToastMessage('Field visit check-in recorded successfully!');
      setTimeout(() => setToastMessage(''), 3000);
      setCheckinForm({ customer_name: '', checkin_lat: '13.0827', checkin_lng: '80.2707', notes: '', photo_url: '' });
      fetchMonitoringData();
    } catch (err) {
      console.error(err);
    } finally {
      setSubmittingCheckin(false);
    }
  };

  const formatDuration = (secs) => {
    if (!secs || secs <= 0) return '0s';
    const hours = Math.floor(secs / 3600);
    const mins = Math.floor((secs % 3600) / 60);
    const remainingSecs = Math.floor(secs % 60);

    if (hours > 0) {
      return remainingSecs > 0 ? `${hours}h ${mins}m ${remainingSecs}s` : `${hours}h ${mins}m`;
    }
    if (mins > 0) {
      return remainingSecs > 0 ? `${mins}m ${remainingSecs}s` : `${mins}m`;
    }
    return `${remainingSecs}s`;
  };

  const displayEmployees = employees || [];
  const displayActivities = activities || [];
  const displayFieldVisits = fieldVisits || [];

  const filteredEmployees = displayEmployees.filter(e => 
    e.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    e.role.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (e.department && e.department.toLowerCase().includes(searchQuery.toLowerCase())) ||
    e.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="page-container" style={{ paddingBottom: '40px' }}>
      {/* Header & Controls */}
      <div className="page-header" style={{ marginBottom: '24px' }}>
        <div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
            <Link to="/dashboard" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Dashboard</Link> / {' '}
            <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>Team Insights</span>
          </div>
          <h1 className="page-title" style={{ fontSize: '1.65rem', fontWeight: '800', margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <ShieldCheck size={26} style={{ color: '#2563eb' }} />
            <span>Team Insights & Performance Analytics</span>
          </h1>
          <p className="page-subtitle" style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Comprehensive team performance analytics: Call stats, lead conversion rates, business activities, and field visits.
          </p>
        </div>

        {/* Date Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', backgroundColor: '#ffffff', padding: '4px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
            {[
              { id: 'ALL', label: 'All Time' },
              { id: 'THIS_MONTH', label: 'This Month' },
              { id: 'THIS_WEEK', label: 'This Week' },
              { id: 'TODAY', label: 'Today' },
              { id: 'YESTERDAY', label: 'Yesterday' }
            ].map(f => (
              <button
                key={f.id}
                type="button"
                onClick={() => setDateFilter(f.id)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: dateFilter === f.id ? '#2563eb' : 'transparent',
                  color: dateFilter === f.id ? '#ffffff' : '#64748b',
                  fontWeight: '700',
                  fontSize: '0.78rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {toastMessage && (
        <div className="alert alert-success" style={{ backgroundColor: '#d1fae5', color: '#047857', border: '1px solid #a7f3d0', padding: '12px 16px', borderRadius: '10px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Check size={18} />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Privacy Policy Banner */}
      <div style={{
        backgroundColor: '#eff6ff',
        border: '1px solid #bfdbfe',
        borderRadius: '14px',
        padding: '14px 20px',
        marginBottom: '24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        flexWrap: 'wrap'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Lock size={20} style={{ color: '#2563eb', flexShrink: 0 }} />
          <div style={{ fontSize: '0.84rem', color: '#1e40af', fontWeight: '500' }}>
            <strong>Operational Transparency & Privacy Policy:</strong> Tracks CRM business actions (calls, lead status, logins, conversions). Background location is <strong>never</strong> continuously tracked. Location is collected only during explicit Field Visit Check-Ins.
          </div>
        </div>

        <button 
          onClick={() => setShowCheckinModal(true)} 
          className="btn btn-primary"
          style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', whiteSpace: 'nowrap', flexShrink: 0 }}
        >
          <MapPin size={16} />
          <span>Start Field Visit Check-in</span>
        </button>
      </div>

      {/* Navigation Tabs */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        backgroundColor: '#ffffff',
        padding: '6px',
        borderRadius: '16px',
        border: '1px solid #e2e8f0',
        marginBottom: '24px',
        boxShadow: '0 2px 8px rgba(15, 23, 42, 0.04)',
        overflowX: 'auto',
        scrollbarWidth: 'thin'
      }}>
        {[
          { id: 'overview', label: '1. Overview', icon: Users },
          { id: 'calls', label: '2. Call Analytics', icon: PhoneCall },
          { id: 'conversions', label: '3. Lead Conversion', icon: TrendingUp },
          { id: 'timeline', label: '4. Activity Timeline', icon: Activity },
          { id: 'online', label: '5. Online / Presence', icon: Clock },
          { id: 'field', label: '6. Field Visits', icon: MapPin },
          { id: 'privacy', label: '7. Retention & Privacy', icon: ShieldCheck }
        ].map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '9px 16px',
                borderRadius: '12px',
                border: 'none',
                backgroundColor: activeTab === tab.id ? '#2563eb' : 'transparent',
                color: activeTab === tab.id ? '#ffffff' : '#64748b',
                fontWeight: '700',
                fontSize: '0.84rem',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                boxShadow: activeTab === tab.id ? '0 4px 12px rgba(37, 99, 235, 0.25)' : 'none',
                transition: 'all 0.2s'
              }}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* SECTION 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Overview Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
              <div style={{ width: '44px', height: '44px', borderRadius: '12px', backgroundColor: 'rgba(37, 99, 235, 0.12)', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Users size={22} />
              </div>
              <div>
                <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Total Active Team</div>
                <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#0f172a' }}>{overview?.total_employees || displayEmployees.length}</div>
              </div>
            </div>

            <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
              <div style={{ width: '44px', height: '44px', borderRadius: '12px', backgroundColor: 'rgba(16, 185, 129, 0.12)', color: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Clock size={22} />
              </div>
              <div>
                <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Online Now</div>
                <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#059669' }}>🟢 {displayEmployees.filter(e => e.online_status === 'ONLINE').length} Online</div>
              </div>
            </div>

            <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
              <div style={{ width: '44px', height: '44px', borderRadius: '12px', backgroundColor: 'rgba(139, 92, 246, 0.12)', color: '#8b5cf6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <PhoneCall size={22} />
              </div>
              <div>
                <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Total Calls</div>
                <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#0f172a' }}>{overview?.total_calls || displayEmployees.reduce((acc, curr) => acc + (curr.total_calls || 0), 0)}</div>
              </div>
            </div>

            <div className="stat-card" style={{ padding: '18px 20px', borderRadius: '16px' }}>
              <div style={{ width: '44px', height: '44px', borderRadius: '12px', backgroundColor: 'rgba(245, 158, 11, 0.12)', color: '#f59e0b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <TrendingUp size={22} />
              </div>
              <div>
                <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Total Converted</div>
                <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#059669' }}>{overview?.total_converted_leads || displayEmployees.reduce((acc, curr) => acc + (curr.converted_leads || 0), 0)}</div>
              </div>
            </div>
          </div>

          {/* Employee Performance Table */}
          <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>Factual Employee Performance Table</h3>
              <div className="search-box" style={{ maxWidth: '300px' }}>
                <Search size={16} className="search-icon" />
                <input 
                  type="text" 
                  placeholder="Search employee by name..." 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>

            <div className="table-responsive">
              <table className="custom-table" style={{ width: '100%', fontSize: '0.84rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                    <th style={{ padding: '10px 12px' }}>Employee</th>
                    <th style={{ padding: '10px 12px' }}>Department</th>
                    <th style={{ padding: '10px 12px' }}>Role</th>
                    <th style={{ padding: '10px 12px' }}>Presence</th>
                    <th style={{ padding: '10px 12px' }}>Assigned</th>
                    <th style={{ padding: '10px 12px' }}>Contacted</th>
                    <th style={{ padding: '10px 12px' }}>Converted</th>
                    <th style={{ padding: '10px 12px' }}>Total Calls</th>
                    <th style={{ padding: '10px 12px' }}>Talk Time</th>
                    <th style={{ padding: '10px 12px' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEmployees.length === 0 ? (
                    <tr>
                      <td colSpan={10} style={{ textAlign: 'center', padding: '48px 16px', color: '#64748b' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                          <Users size={32} style={{ color: '#94a3b8' }} />
                          <div style={{ fontWeight: 600, fontSize: '0.92rem', color: '#334155' }}>
                            {searchQuery ? `No employees found matching "${searchQuery}"` : 'No employee performance records available for your role.'}
                          </div>
                          <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                            {searchQuery ? 'Try adjusting your search criteria.' : 'Only employees within your authorized team and reporting hierarchy are displayed.'}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredEmployees.map((e) => (
                      <tr key={e.employee_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '12px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{ width: '32px', height: '32px', borderRadius: '50%', backgroundColor: '#2563eb', color: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '700', fontSize: '0.82rem' }}>
                              {e.name[0]}
                            </div>
                            <div>
                              <strong style={{ color: '#0f172a' }}>{e.name}</strong>
                              <div style={{ fontSize: '0.72rem', color: '#64748b' }}>EMP{e.employee_id}</div>
                            </div>
                          </div>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <span style={{ 
                            padding: '3px 8px', 
                            borderRadius: '10px', 
                            fontSize: '0.72rem', 
                            fontWeight: '700', 
                            backgroundColor: (e.department === 'SUPPORT') ? '#ccfbf1' : (e.department === 'FINANCE') ? '#fef3c7' : (e.department === 'ADMIN' || e.department === 'ADMINISTRATION') ? '#f3e8ff' : '#dbeafe', 
                            color: (e.department === 'SUPPORT') ? '#0f766e' : (e.department === 'FINANCE') ? '#b45309' : (e.department === 'ADMIN' || e.department === 'ADMINISTRATION') ? '#6b21a8' : '#1d4ed8' 
                          }}>
                            {e.department || 'Sales'}
                          </span>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <span style={{ padding: '3px 8px', borderRadius: '10px', fontSize: '0.72rem', fontWeight: '700', backgroundColor: '#f1f5f9', color: '#475569' }}>
                            {e.role}
                          </span>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <span style={{ padding: '3px 10px', borderRadius: '12px', fontSize: '0.72rem', fontWeight: '800', backgroundColor: e.online_status === 'ONLINE' ? '#d1fae5' : '#f1f5f9', color: e.online_status === 'ONLINE' ? '#047857' : '#64748b' }}>
                            {e.online_status === 'ONLINE' ? '🟢 Online' : '⚪ Offline'}
                          </span>
                        </td>
                        <td style={{ padding: '12px' }}>{e.assigned_leads}</td>
                        <td style={{ padding: '12px' }}>{e.contacted_leads}</td>
                        <td style={{ padding: '12px', fontWeight: '700', color: '#059669' }}>{e.converted_leads}</td>
                        <td style={{ padding: '12px' }}>{e.total_calls} calls</td>
                        <td style={{ padding: '12px', fontWeight: '600' }}>{formatDuration(e.total_talk_time_seconds)}</td>
                        <td style={{ padding: '12px' }}>
                          <button 
                            onClick={() => navigate(`/employee-monitoring/${e.employee_id}`)}
                            className="btn btn-outline"
                            style={{ padding: '4px 10px', fontSize: '0.78rem', fontWeight: '700', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                          >
                            <span>View Detail</span>
                            <ArrowRight size={14} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 2: CALL ANALYTICS & CALL RECORDS OVERSIGHT */}
      {activeTab === 'calls' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Top Call Aggregates Table */}
          <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <PhoneCall size={20} style={{ color: '#2563eb' }} />
              Team Call Performance Summary
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '20px' }}>
              Aggregate talk time and call metrics across sales and support agents.
            </p>

            <div className="table-responsive">
              <table className="custom-table" style={{ width: '100%', fontSize: '0.84rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                    <th style={{ padding: '10px' }}>Employee</th>
                    <th style={{ padding: '10px' }}>Total Calls</th>
                    <th style={{ padding: '10px' }}>Answered</th>
                    <th style={{ padding: '10px' }}>Missed</th>
                    <th style={{ padding: '10px' }}>Talk Time</th>
                    <th style={{ padding: '10px' }}>Avg Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {displayEmployees.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '32px 16px', color: '#64748b' }}>
                        No team call performance records available for your role.
                      </td>
                    </tr>
                  ) : (
                    displayEmployees.map(e => (
                      <tr key={e.employee_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '10px' }}><strong>{e.name}</strong></td>
                        <td style={{ padding: '10px' }}>{e.total_calls}</td>
                        <td style={{ padding: '10px', color: '#059669', fontWeight: '700' }}>{e.answered_calls}</td>
                        <td style={{ padding: '10px', color: '#dc2626', fontWeight: '700' }}>{e.missed_calls}</td>
                        <td style={{ padding: '10px', fontWeight: '600' }}>{formatDuration(e.total_talk_time_seconds)}</td>
                        <td style={{ padding: '10px' }}>{formatDuration(e.avg_duration_seconds)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Manager / Admin Call Records & Audio Recordings Table */}
          <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Headphones size={22} style={{ color: '#2563eb' }} />
                  Employees' Call Records & Audio Recordings
                </h3>
                <p style={{ fontSize: '0.84rem', color: '#64748b', margin: '4px 0 0 0' }}>
                  Listen to call audio recordings to review employee customer conversations, AI transcripts, & summaries.
                </p>
              </div>

              {/* Filters */}
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <select 
                  value={callEmployeeFilter} 
                  onChange={(e) => setCallEmployeeFilter(e.target.value)}
                  style={{ padding: '6px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                >
                  <option value="">All Employees</option>
                  {displayEmployees.map(emp => (
                    <option key={emp.employee_id} value={emp.name}>{emp.name}</option>
                  ))}
                </select>

                <select 
                  value={callStatusFilter} 
                  onChange={(e) => setCallStatusFilter(e.target.value)}
                  style={{ padding: '6px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.82rem' }}
                >
                  <option value="">All Call Statuses</option>
                  <option value="COMPLETED">Completed</option>
                  <option value="MISSED">Missed / Unanswered</option>
                  <option value="BUSY">Busy</option>
                  <option value="FAILED">Failed</option>
                </select>
              </div>
            </div>

            <div className="table-responsive">
              <table className="custom-table" style={{ width: '100%', fontSize: '0.84rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #e2e8f0', background: '#f8fafc', color: '#64748b', textAlign: 'left' }}>
                    <th style={{ padding: '12px' }}>Employee</th>
                    <th style={{ padding: '12px' }}>Lead / Customer Phone</th>
                    <th style={{ padding: '12px' }}>Direction & Status</th>
                    <th style={{ padding: '12px' }}>Duration</th>
                    <th style={{ padding: '12px' }}>Date & Time</th>
                    <th style={{ padding: '12px' }}>Audio Recording</th>
                    <th style={{ padding: '12px', textAlign: 'right' }}>AI Review & Transcript</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const logs = callLogs || [];
                    const filteredLogs = logs.filter(c => {
                      if (callEmployeeFilter) {
                        const empName = (c.employee_name || '').toLowerCase();
                        const filterVal = callEmployeeFilter.toLowerCase();
                        if (!empName.includes(filterVal) && String(c.employee_id) !== String(callEmployeeFilter)) {
                          return false;
                        }
                      }
                      if (callStatusFilter) {
                        const statusUpper = (c.call_status || '').toUpperCase();
                        if (callStatusFilter === 'COMPLETED' || callStatusFilter === 'ANSWERED') {
                          if (!['ANSWERED', 'CONNECTED', 'COMPLETED'].includes(statusUpper)) return false;
                        } else if (callStatusFilter === 'MISSED') {
                          if (!['MISSED', 'NOANSWER', 'NO_ANSWER', 'BUSY', 'FAILED', 'CANCEL'].includes(statusUpper)) return false;
                        } else if (statusUpper !== callStatusFilter.toUpperCase()) {
                          return false;
                        }
                      }
                      return true;
                    });

                    if (filteredLogs.length === 0) {
                      return (
                        <tr>
                          <td colSpan={7} style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
                            No call records found matching selected filters.
                          </td>
                        </tr>
                      );
                    }

                    return filteredLogs.map(log => {
                      const isConnected = ['ANSWERED', 'CONNECTED', 'COMPLETED'].includes((log.call_status || '').toUpperCase());
                      return (
                        <tr key={log.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '12px' }}>
                            <div style={{ fontWeight: '700', color: '#0f172a' }}>{log.employee_name || 'Sales Agent'}</div>
                            <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{log.employee_role || 'Agent'}</div>
                          </td>

                          <td style={{ padding: '12px' }}>
                            <div style={{ fontWeight: '700', color: '#0f172a' }}>{log.lead_name || 'Prospect'}</div>
                            <div style={{ fontSize: '0.78rem', color: '#2563eb', fontWeight: '500' }}>{log.customer_phone || log.to_number}</div>
                          </td>

                          <td style={{ padding: '12px' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <span style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: '600' }}>
                                {log.call_direction || 'OUTBOUND'}
                              </span>
                              <span style={{
                                padding: '2px 8px', borderRadius: '10px', fontSize: '0.72rem', fontWeight: '800', display: 'inline-block', width: 'fit-content',
                                backgroundColor: isConnected ? '#d1fae5' : '#fee2e2',
                                color: isConnected ? '#047857' : '#dc2626'
                              }}>
                                {isConnected ? 'COMPLETED' : log.call_status}
                              </span>
                            </div>
                          </td>

                          <td style={{ padding: '12px', fontWeight: '700' }}>{formatDuration(log.duration_seconds)}</td>

                          <td style={{ padding: '12px', color: '#475569' }}>
                            <div style={{ fontSize: '0.8rem', fontWeight: '600' }}>{new Date(log.created_at).toLocaleDateString()}</div>
                            <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>{new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                          </td>

                          <td style={{ padding: '12px' }}>
                            {log.duration_seconds > 0 && log.recording_url ? (
                              <audio
                                controls
                                preload="metadata"
                                src={log.recording_url}
                                style={{ height: '32px', maxWidth: '175px' }}
                                onLoadedMetadata={(e) => probeAudioDuration(e.currentTarget)}
                                onDurationChange={(e) => rewindAfterProbe(e.currentTarget)}
                                onTimeUpdate={(e) => rewindAfterProbe(e.currentTarget)}
                              />
                            ) : (
                              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>No recording</span>
                            )}
                          </td>

                          <td style={{ padding: '12px', textAlign: 'right' }}>
                            <button
                              onClick={() => {
                                setSelectedCallLog(log);
                                setShowAIModal(true);
                              }}
                              className="btn btn-outline"
                              style={{
                                padding: '5px 12px',
                                fontSize: '0.78rem',
                                fontWeight: '700',
                                color: '#2563eb',
                                borderColor: '#bfdbfe',
                                backgroundColor: '#eff6ff',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px'
                              }}
                            >
                              <Sparkles size={14} />
                              <span>AI Review & Transcript</span>
                            </button>
                          </td>
                        </tr>
                      );
                    });
                  })()}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 3: LEAD CONVERSION ANALYTICS */}
      {activeTab === 'conversions' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: '800', color: '#0f172a', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingUp size={20} style={{ color: '#059669' }} />
            Lead Conversion Analytics (Formula: Converted / Assigned × 100)
          </h3>

          <div className="table-responsive">
            <table className="custom-table" style={{ width: '100%', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                  <th style={{ padding: '10px' }}>Employee</th>
                  <th style={{ padding: '10px' }}>Assigned</th>
                  <th style={{ padding: '10px' }}>Contacted</th>
                  <th style={{ padding: '10px' }}>Qualified</th>
                  <th style={{ padding: '10px' }}>Converted</th>
                  <th style={{ padding: '10px' }}>Conversion Rate</th>
                </tr>
              </thead>
              <tbody>
                {displayEmployees.map(e => {
                  const rate = e.assigned_leads > 0 ? ((e.converted_leads / e.assigned_leads) * 100).toFixed(1) : 0;
                  return (
                    <tr key={e.employee_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '10px' }}><strong>{e.name}</strong></td>
                      <td style={{ padding: '10px' }}>{e.assigned_leads}</td>
                      <td style={{ padding: '10px' }}>{e.contacted_leads}</td>
                      <td style={{ padding: '10px' }}>{e.qualified_leads}</td>
                      <td style={{ padding: '10px', fontWeight: '700', color: '#059669' }}>{e.converted_leads}</td>
                      <td style={{ padding: '10px' }}>
                        <span style={{ padding: '3px 10px', borderRadius: '10px', fontSize: '0.78rem', fontWeight: '800', backgroundColor: '#d1fae5', color: '#047857' }}>
                          {rate}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SECTION 4: ACTIVITY TIMELINE */}
      {activeTab === 'timeline' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={20} style={{ color: '#8b5cf6' }} />
            Business Activity Timeline
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {displayActivities.map(act => (
              <div key={act.activity_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', borderRadius: '12px', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ width: '36px', height: '36px', borderRadius: '10px', backgroundColor: '#e0f2fe', color: '#0284c7', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <Activity size={18} />
                  </div>
                  <div>
                    <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#0f172a' }}>{act.description}</div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '2px' }}>
                      <strong>{act.employee_name}</strong> &bull; {new Date(act.timestamp).toLocaleString()}
                    </div>
                  </div>
                </div>
                <span style={{ padding: '4px 10px', borderRadius: '8px', fontSize: '0.72rem', fontWeight: '700', backgroundColor: '#e2e8f0', color: '#334155', flexShrink: 0 }}>
                  {act.activity_type}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION 5: ONLINE / PRESENCE STATUS */}
      {activeTab === 'online' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={20} style={{ color: '#10b981' }} />
            Live App Presence & Attendance Status
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
            {displayEmployees.map(e => (
              <div key={e.employee_id} style={{ background: '#f8fafc', padding: '16px', borderRadius: '14px', border: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '50%', backgroundColor: '#2563eb', color: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '700' }}>
                    {e.name[0]}
                  </div>
                  <div>
                    <div style={{ fontSize: '0.92rem', fontWeight: '800', color: '#0f172a' }}>{e.name}</div>
                    <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                      Last seen: {new Date(e.last_activity_time || Date.now()).toLocaleTimeString()}
                    </div>
                  </div>
                </div>

                <span style={{ padding: '4px 12px', borderRadius: '16px', fontSize: '0.78rem', fontWeight: '800', backgroundColor: e.online_status === 'ONLINE' ? '#d1fae5' : '#f1f5f9', color: e.online_status === 'ONLINE' ? '#047857' : '#64748b' }}>
                  {e.online_status === 'ONLINE' ? '🟢 Online' : '⚪ Offline'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION 6: FIELD VISITS */}
      {activeTab === 'field' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: '800', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <MapPin size={20} style={{ color: '#ef4444' }} />
                Explicit Field Visit Check-Ins
              </h3>
              <p style={{ fontSize: '0.84rem', color: '#64748b', margin: '4px 0 0 0' }}>
                GPS coordinates & location details captured solely during explicit employee visit check-ins.
              </p>
            </div>
            <button onClick={() => setShowCheckinModal(true)} className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <MapPin size={16} />
              <span>New Check-in</span>
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
            {displayFieldVisits.map(visit => (
              <div key={visit.id} style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '14px', padding: '18px', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
                  <div>
                    <h4 style={{ fontSize: '1rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>{visit.customer_name}</h4>
                    <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '3px' }}>
                      Visited by: <strong>{visit.employee_name || 'Field Agent'}</strong>
                    </div>
                  </div>
                  <span style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: '800', backgroundColor: visit.checkout_time ? '#e2e8f0' : '#d1fae5', color: visit.checkout_time ? '#475569' : '#047857' }}>
                    {visit.checkout_time ? 'Completed Visit' : '🟢 Active Visit'}
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', margin: '14px 0', fontSize: '0.82rem', background: '#f8fafc', padding: '12px', borderRadius: '10px' }}>
                  <div>
                    <span style={{ color: '#64748b', fontWeight: '600' }}>GPS Location:</span>{' '}
                    <strong>{visit.checkin_lat}, {visit.checkin_lng}</strong>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontWeight: '600' }}>Address:</span>{' '}
                    <strong>{visit.checkin_address || 'Anna Salai Commercial Zone'}</strong>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontWeight: '600' }}>Check-in Time:</span>{' '}
                    <strong>{new Date(visit.checkin_time).toLocaleTimeString()}</strong>
                  </div>
                </div>

                {visit.notes && (
                  <div style={{ fontSize: '0.82rem', color: '#334155', background: '#eff6ff', padding: '10px 12px', borderRadius: '8px', borderLeft: '3px solid #2563eb' }}>
                    <strong>Visit Notes:</strong> {visit.notes}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION 7: RETENTION & PRIVACY SETTINGS */}
      {activeTab === 'privacy' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '28px', maxWidth: '800px' }}>
          <form onSubmit={handleSaveRetention}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldCheck size={20} style={{ color: '#2563eb' }} />
              Data Retention & Privacy Configuration
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="form-group">
                <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569' }}>Activity Logs Retention (Days)</label>
                <input 
                  type="number" 
                  value={retentionSettings.activity_retention_days}
                  onChange={(e) => setRetentionSettings({ ...retentionSettings, activity_retention_days: parseInt(e.target.value) || 90 })}
                />
              </div>

              <div className="form-group">
                <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569' }}>Call Logs Retention (Days)</label>
                <input 
                  type="number" 
                  value={retentionSettings.call_retention_days}
                  onChange={(e) => setRetentionSettings({ ...retentionSettings, call_retention_days: parseInt(e.target.value) || 180 })}
                />
              </div>

              <div className="form-group">
                <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569' }}>Field Visit Check-In Retention (Days)</label>
                <input 
                  type="number" 
                  value={retentionSettings.field_retention_days}
                  onChange={(e) => setRetentionSettings({ ...retentionSettings, field_retention_days: parseInt(e.target.value) || 180 })}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '24px' }}>
              <button type="submit" className="btn btn-primary">
                <span>Save Retention Policy</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Field Visit Check-In Modal */}
      {showCheckinModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15,23,42,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '20px' }}>
          <div className="content-card" style={{ width: '100%', maxWidth: '500px', borderRadius: '18px', padding: '28px' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <MapPin size={20} style={{ color: '#2563eb' }} />
              Field Visit Check-In Form
            </h3>

            <form onSubmit={handleCheckinSubmit}>
              <div className="form-group">
                <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569' }}>Customer / Lead Name *</label>
                <input 
                  type="text" 
                  required
                  placeholder="e.g. Priya Sharma" 
                  value={checkinForm.customer_name}
                  onChange={(e) => setCheckinForm({ ...checkinForm, customer_name: e.target.value })}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569' }}>Latitude</label>
                  <input type="text" readOnly value={checkinForm.checkin_lat} />
                </div>
                <div className="form-group">
                  <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569' }}>Longitude</label>
                  <input type="text" readOnly value={checkinForm.checkin_lng} />
                </div>
              </div>

              <div className="form-group">
                <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569' }}>Visit Notes</label>
                <textarea 
                  rows="3" 
                  placeholder="Notes about meeting discussion..." 
                  value={checkinForm.notes}
                  onChange={(e) => setCheckinForm({ ...checkinForm, notes: e.target.value })}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '20px' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowCheckinModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={submittingCheckin}>
                  <span>{submittingCheckin ? 'Submitting...' : 'Confirm Check-In'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Call AI Review & Transcript Modal */}
      <CallAISummaryModal
        isOpen={showAIModal}
        onClose={() => setShowAIModal(false)}
        callLog={selectedCallLog}
      />
    </div>
  );
};

export default EmployeeMonitoring;
