import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import CallAISummaryModal from '../../components/IVR/CallAISummaryModal';
import { 
  Users, 
  PhoneCall, 
  Clock, 
  TrendingUp, 
  Activity, 
  MapPin, 
  ShieldCheck, 
  ArrowLeft, 
  CheckCircle2, 
  XCircle, 
  AlertCircle,
  Calendar,
  MessageCircle,
  Award,
  Sparkles,
  Volume2,
  Headphones
} from 'lucide-react';

const createDefaultDetail = (empId) => ({
  employee_id: empId || 1,
  name: empId == '2' ? 'Sarah Jenkins' : empId == '3' ? 'David Chen' : empId == '4' ? 'Priya Sharma' : 'Alex Morgan',
  email: empId == '2' ? 'sarah.j@company.com' : empId == '3' ? 'david.c@company.com' : empId == '4' ? 'priya.s@company.com' : 'alex.m@company.com',
  role: empId == '2' ? 'Account Manager' : empId == '3' ? 'Sales Representative' : empId == '4' ? 'Field Sales Specialist' : 'Senior Sales Executive',
  status: 'ACTIVE',
  online_status: empId == '3' ? 'OFFLINE' : 'ONLINE',
  metrics: {
    assigned_leads: empId == '2' ? 15 : empId == '3' ? 22 : empId == '4' ? 12 : 18,
    contacted_leads: empId == '2' ? 12 : empId == '3' ? 16 : empId == '4' ? 10 : 14,
    interested_leads: empId == '2' ? 7 : empId == '3' ? 8 : empId == '4' ? 6 : 9,
    qualified_leads: empId == '2' ? 6 : empId == '3' ? 7 : empId == '4' ? 5 : 8,
    converted_leads: empId == '2' ? 4 : empId == '3' ? 3 : empId == '4' ? 3 : 5,
    lost_leads: 1,
    pending_followups: 4,
    conversion_rate: empId == '2' ? 26.7 : empId == '3' ? 13.6 : empId == '4' ? 25.0 : 27.8,
    total_calls: empId == '2' ? 18 : empId == '3' ? 14 : empId == '4' ? 12 : 24,
    answered_calls: empId == '2' ? 15 : empId == '3' ? 10 : empId == '4' ? 10 : 19,
    missed_calls: empId == '2' ? 3 : empId == '3' ? 4 : empId == '4' ? 2 : 5,
    failed_calls: 0,
    total_talk_time_seconds: empId == '2' ? 4320 : empId == '3' ? 3260 : empId == '4' ? 2890 : 6300,
    avg_duration_seconds: 240
  }
});

const DEFAULT_CALLS = [
  { 
    id: 1, 
    lead_name: 'TechCorp Solutions', 
    phone_number: '+91 98765 43210', 
    to_number: '+91 98765 43210',
    call_direction: 'OUTGOING', 
    call_status: 'ANSWERED', 
    duration_seconds: 275, 
    recording_url: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
    transcript: '[Agent]: Hello! This is Alex from WaCRM. Am I speaking with TechCorp Solutions?\n[TechCorp]: Hi Alex! Yes, we reviewed the Click-to-Call IVR and WhatsApp integration specs.\n[Agent]: Excellent! We can have your 18-agent sales team onboarded by Friday.\n[TechCorp]: Perfect, please send over the enterprise agreement.',
    ai_summary: '🎯 KEY DISCUSSION: Discussed enterprise onboarding for 18 sales agents. Customer confirmed readiness to sign agreement.\n✅ SENTIMENT: Highly Interested\n📌 ACTION ITEM: Email enterprise contract by 5:00 PM.',
    sentiment: 'Positive',
    created_at: new Date(Date.now() - 900000).toISOString() 
  },
  { 
    id: 2, 
    lead_name: 'Acme Industries', 
    phone_number: '+91 91234 56789', 
    to_number: '+91 91234 56789',
    call_direction: 'INCOMING', 
    call_status: 'ANSWERED', 
    duration_seconds: 180, 
    recording_url: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3',
    transcript: '[Agent]: Good afternoon! Sarah here following up on Acme Industries\' proposal.\n[Acme Rep]: Hi Sarah. The pricing looks good, but we need custom WhatsApp template approval.\n[Agent]: I will submit your WhatsApp templates to Meta directly today.',
    ai_summary: '🎯 KEY DISCUSSION: Reviewed proposal pricing. Customer requested Meta WhatsApp template verification.\n✅ SENTIMENT: Interested / Conditional\n📌 ACTION ITEM: Submit custom WhatsApp templates via Meta Business API.',
    sentiment: 'Neutral',
    created_at: new Date(Date.now() - 3600000).toISOString() 
  },
  { 
    id: 3, 
    lead_name: 'Global Systems Ltd', 
    phone_number: '+91 99887 76655', 
    to_number: '+91 99887 76655',
    call_direction: 'OUTGOING', 
    call_status: 'MISSED', 
    duration_seconds: 0, 
    recording_url: null,
    created_at: new Date(Date.now() - 7200000).toISOString() 
  }
];

const DEFAULT_LEADS = [
  { id: 101, name: 'TechCorp Solutions', email: 'contact@techcorp.com', phone: '+91 98765 43210', status: 'QUALIFIED', created_at: new Date(Date.now() - 86400000).toISOString() },
  { id: 102, name: 'Acme Industries', email: 'info@acme.com', phone: '+91 91234 56789', status: 'CONTACTED', created_at: new Date(Date.now() - 172800000).toISOString() },
  { id: 103, name: 'Global Systems Ltd', email: 'sales@globalsys.com', phone: '+91 99887 76655', status: 'CONVERTED', created_at: new Date(Date.now() - 259200000).toISOString() }
];

const DEFAULT_VISITS = [
  { id: 1, customer_name: 'TechCorp India HQ', checkin_lat: '13.0827', checkin_lng: '80.2707', checkin_address: 'Anna Salai, Chennai Central, TN', checkin_time: new Date(Date.now() - 7200000).toISOString(), checkout_time: new Date(Date.now() - 3600000).toISOString(), notes: 'Discussed Enterprise plan rollout. Presented architecture demo to VP of Operations.' }
];

const EmployeeDetailPage = () => {
  const { employeeId } = useParams();
  const navigate = useNavigate();
  const { user: currentUser } = useAuth();

  const [detail, setDetail] = useState(null);
  const [calls, setCalls] = useState([]);
  const [leads, setLeads] = useState([]);
  const [activities, setActivities] = useState([]);
  const [fieldVisits, setFieldVisits] = useState([]);
  const [selectedCallLog, setSelectedCallLog] = useState(null);
  const [showAIModal, setShowAIModal] = useState(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    const fetchEmployeeData = async () => {
      try {
        setLoading(true);
        setError('');
        
        // 1. Fetch employee details first (enforces strict authorization scope on backend)
        const detailRes = await API.get(`/employee-monitoring/${employeeId}`);
        setDetail(detailRes.data);

        // 2. Fetch subordinate sub-records
        const [callsRes, leadsRes, actRes, visitsRes] = await Promise.all([
          API.get(`/employee-monitoring/${employeeId}/calls`).catch(() => ({ data: [] })),
          API.get(`/employee-monitoring/${employeeId}/leads`).catch(() => ({ data: [] })),
          API.get('/activities', { params: { employee_id: employeeId } }).catch(() => ({ data: [] })),
          API.get(`/employee-monitoring/${employeeId}/field-visits`).catch(() => ({ data: [] }))
        ]);

        setCalls(callsRes.data || []);
        setLeads(leadsRes.data || []);
        setActivities(actRes.data || []);
        setFieldVisits(visitsRes.data || []);
      } catch (err) {
        console.error("Employee detail fetch error:", err);
        if (err.response?.status === 403) {
          setError(err.response?.data?.detail || 'Access Denied (403): You do not have permission to view performance details for this employee.');
        } else if (err.response?.status === 404) {
          setError('Employee not found (404).');
        } else {
          setError('Failed to load employee performance details.');
        }
      } finally {
        setLoading(false);
      }
    };

    if (employeeId) {
      fetchEmployeeData();
    }
  }, [employeeId]);

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

  if (loading) {
    return (
      <div className="page-container" style={{ textAlign: 'center', padding: '60px 0' }}>
        <p style={{ color: '#64748b', fontSize: '1rem', fontWeight: '600' }}>Loading employee monitoring metrics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container" style={{ maxWidth: '800px', margin: '0 auto', padding: '40px 0' }}>
        <div className="alert alert-error mb-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', padding: '16px', borderRadius: '12px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <AlertCircle size={22} />
          <span style={{ fontWeight: '600', fontSize: '0.95rem' }}>{error}</span>
        </div>
        <button onClick={() => navigate('/dashboard')} className="btn btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          <ArrowLeft size={16} />
          <span>Return to Dashboard</span>
        </button>
      </div>
    );
  }

  const m = detail?.metrics || {};

  // Dynamically calculate talk time and call metrics from actual call logs list
  const actualTalkTimeSeconds = calls && calls.length > 0 
    ? calls.reduce((acc, c) => acc + (c.duration_seconds || 0), 0) 
    : (m.total_talk_time_seconds || 0);

  const actualTotalCalls = calls && calls.length > 0 ? calls.length : (m.total_calls || 0);

  const actualAvgDurationSeconds = actualTotalCalls > 0 
    ? Math.round(actualTalkTimeSeconds / actualTotalCalls) 
    : (m.avg_duration_seconds || 0);

  return (
    <div className="page-container" style={{ maxWidth: '1100px', margin: '0 auto', paddingBottom: '40px' }}>
      {/* Header & Back Button */}
      <div className="page-header" style={{ marginBottom: '24px' }}>
        <div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
            <Link to="/dashboard" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Dashboard</Link> / {' '}
            <Link to="/employee-monitoring" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Team Insights</Link> / {' '}
            <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>{detail?.name}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <h1 className="page-title" style={{ fontSize: '1.65rem', fontWeight: '800', margin: 0 }}>{detail?.name}</h1>
            <span style={{ padding: '4px 12px', borderRadius: '16px', fontSize: '0.78rem', fontWeight: '800', backgroundColor: detail?.online_status === 'ONLINE' ? '#d1fae5' : '#f1f5f9', color: detail?.online_status === 'ONLINE' ? '#047857' : '#64748b' }}>
              {detail?.online_status === 'ONLINE' ? '🟢 Online' : '⚪ Offline'}
            </span>
          </div>
          <p className="page-subtitle" style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Employee ID: <strong>EMP{detail?.employee_id}</strong> &bull; Department: <strong style={{ color: '#0f766e' }}>{detail?.department || 'Sales'}</strong> &bull; Role: <strong>{detail?.role}</strong> &bull; Email: <strong>{detail?.email}</strong>
          </p>
        </div>

        <div className="header-actions">
          <Link to="/employee-monitoring" className="btn btn-outline" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ArrowLeft size={16} />
            <span>Back to Team Insights</span>
          </Link>
        </div>
      </div>

      {/* Top Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div className="stat-card" style={{ padding: '16px', borderRadius: '14px' }}>
          <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Assigned Leads</div>
          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#0f172a' }}>{m.assigned_leads || 0}</div>
        </div>

        <div className="stat-card" style={{ padding: '16px', borderRadius: '14px' }}>
          <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Converted Leads</div>
          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#059669' }}>{m.converted_leads || 0}</div>
          <div style={{ fontSize: '0.72rem', color: '#059669', fontWeight: '700' }}>{m.conversion_rate || 0}% Conversion Rate</div>
        </div>

        <div className="stat-card" style={{ padding: '16px', borderRadius: '14px' }}>
          <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Total Calls</div>
          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#2563eb' }}>{actualTotalCalls}</div>
        </div>

        <div className="stat-card" style={{ padding: '16px', borderRadius: '14px' }}>
          <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Talk Time</div>
          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#7c3aed' }}>{formatDuration(actualTalkTimeSeconds)}</div>
        </div>

        <div className="stat-card" style={{ padding: '16px', borderRadius: '14px' }}>
          <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Pending Follow-ups</div>
          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#f59e0b' }}>{m.pending_followups || 0}</div>
        </div>
      </div>

      {/* Tabs */}
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
        overflowX: 'auto'
      }}>
        {[
          { id: 'overview', label: 'Overview' },
          { id: 'calls', label: `Calls (${calls.length})` },
          { id: 'leads', label: `Leads (${leads.length})` },
          { id: 'activities', label: `Activity Log (${activities.length})` },
          { id: 'field', label: `Field Visits (${fieldVisits.length})` }
        ].map(t => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: '8px 16px',
              borderRadius: '10px',
              border: 'none',
              backgroundColor: activeTab === t.id ? '#2563eb' : 'transparent',
              color: activeTab === t.id ? '#ffffff' : '#64748b',
              fontWeight: '700',
              fontSize: '0.84rem',
              cursor: 'pointer'
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab: Overview */}
      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 400px), 1fr))', gap: '20px' }}>
          <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px' }}>Factual Conversion Breakdown</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '0.88rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
                <span>Assigned Leads:</span>
                <strong>{m.assigned_leads || 0}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
                <span>Contacted:</span>
                <strong>{m.contacted_leads || 0}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
                <span>Interested:</span>
                <strong>{m.interested_leads || 0}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
                <span>Qualified:</span>
                <strong>{m.qualified_leads || 0}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
                <span>Converted / Won:</span>
                <strong style={{ color: '#059669' }}>{m.converted_leads || 0}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
                <span>Lost Leads:</span>
                <strong style={{ color: '#dc2626' }}>{m.lost_leads || 0}</strong>
              </div>
            </div>
          </div>

          <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px' }}>Call & Communication Metrics</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '0.88rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
                <span>Total Calls Logged:</span>
                <strong>{actualTotalCalls}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
                <span>Answered Calls:</span>
                <strong style={{ color: '#059669' }}>{m.answered_calls || 0}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
                <span>Missed Calls:</span>
                <strong style={{ color: '#dc2626' }}>{m.missed_calls || 0}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
                <span>Total Talk Time:</span>
                <strong style={{ color: '#7c3aed' }}>{formatDuration(actualTalkTimeSeconds)}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
                <span>Average Call Duration:</span>
                <strong>{formatDuration(actualAvgDurationSeconds)}</strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Calls */}
      {activeTab === 'calls' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Headphones size={20} style={{ color: '#2563eb' }} /> Call History & Audio Recordings
          </h3>
          <div className="table-responsive">
            <table className="custom-table" style={{ width: '100%', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2e8f0', background: '#f8fafc', textAlign: 'left' }}>
                  <th style={{ padding: '10px' }}>Lead / Contact</th>
                  <th style={{ padding: '10px' }}>Phone Number</th>
                  <th style={{ padding: '10px' }}>Direction</th>
                  <th style={{ padding: '10px' }}>Status</th>
                  <th style={{ padding: '10px' }}>Duration</th>
                  <th style={{ padding: '10px' }}>Time</th>
                  <th style={{ padding: '10px' }}>Audio Recording</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>AI Review</th>
                </tr>
              </thead>
              <tbody>
                {calls.map(c => {
                  const isConnected = ['ANSWERED', 'CONNECTED', 'COMPLETED'].includes((c.call_status || '').toUpperCase());
                  return (
                    <tr key={c.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '10px' }}><strong>{c.lead_name || 'Prospect'}</strong></td>
                      <td style={{ padding: '10px', color: '#2563eb' }}>{c.phone_number || c.to_number || '-'}</td>
                      <td style={{ padding: '10px' }}>{c.call_direction}</td>
                      <td style={{ padding: '10px' }}>
                        <span style={{ padding: '3px 8px', borderRadius: '8px', fontSize: '0.72rem', fontWeight: '700', backgroundColor: isConnected ? '#d1fae5' : '#fee2e2', color: isConnected ? '#047857' : '#dc2626' }}>
                          {c.call_status}
                        </span>
                      </td>
                      <td style={{ padding: '10px', fontWeight: '700' }}>{formatDuration(c.duration_seconds)}</td>
                      <td style={{ padding: '10px', color: '#64748b' }}>{new Date(c.created_at).toLocaleString()}</td>
                      <td style={{ padding: '10px' }}>
                        {c.duration_seconds > 0 && c.recording_url ? (
                          <audio controls preload="metadata" src={c.recording_url} style={{ height: '30px', maxWidth: '160px' }} />
                        ) : (
                          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>No recording</span>
                        )}
                      </td>
                      <td style={{ padding: '10px', textAlign: 'right' }}>
                        <button
                          onClick={() => {
                            setSelectedCallLog({
                              ...c,
                              employee_name: detail?.name || 'Sales Agent'
                            });
                            setShowAIModal(true);
                          }}
                          className="btn btn-outline"
                          style={{
                            padding: '4px 10px',
                            fontSize: '0.76rem',
                            fontWeight: '700',
                            color: '#2563eb',
                            backgroundColor: '#eff6ff',
                            borderColor: '#bfdbfe',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                        >
                          <Sparkles size={13} />
                          <span>AI Review</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab: Leads */}
      {activeTab === 'leads' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px' }}>Assigned Leads List</h3>
          <div className="table-responsive">
            <table className="custom-table" style={{ width: '100%', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                  <th style={{ padding: '10px' }}>Lead Name</th>
                  <th style={{ padding: '10px' }}>Email</th>
                  <th style={{ padding: '10px' }}>Phone</th>
                  <th style={{ padding: '10px' }}>Stage / Status</th>
                  <th style={{ padding: '10px' }}>Assigned Date</th>
                </tr>
              </thead>
              <tbody>
                {leads.map(l => (
                  <tr key={l.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px' }}><strong>{l.name}</strong></td>
                    <td style={{ padding: '10px' }}>{l.email}</td>
                    <td style={{ padding: '10px' }}>{l.phone}</td>
                    <td style={{ padding: '10px' }}>
                      <span style={{ padding: '3px 10px', borderRadius: '10px', fontSize: '0.75rem', fontWeight: '700', backgroundColor: '#e0f2fe', color: '#0284c7' }}>
                        {l.status}
                      </span>
                    </td>
                    <td style={{ padding: '10px', color: '#64748b' }}>{new Date(l.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab: Activities */}
      {activeTab === 'activities' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px' }}>Individual Activity Timeline</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {activities.map(act => (
              <div key={act.activity_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderRadius: '12px', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Activity size={18} style={{ color: '#2563eb' }} />
                  <div>
                    <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#0f172a' }}>{act.description}</div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '2px' }}>{new Date(act.timestamp).toLocaleString()}</div>
                  </div>
                </div>
                <span style={{ padding: '3px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: '700', backgroundColor: '#e2e8f0', color: '#334155' }}>
                  {act.activity_type}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Field Visits */}
      {activeTab === 'field' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px' }}>Field Visit Check-Ins</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {fieldVisits.map(visit => (
              <div key={visit.id} style={{ background: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: '800', color: '#0f172a', margin: 0 }}>{visit.customer_name}</h4>
                  <span style={{ fontSize: '0.75rem', fontWeight: '700', padding: '3px 8px', borderRadius: '8px', backgroundColor: '#d1fae5', color: '#047857' }}>
                    GPS Check-In
                  </span>
                </div>
                <div style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '6px' }}>
                  Location: <strong>{visit.checkin_lat}, {visit.checkin_lng}</strong> &bull; Address: <strong>{visit.checkin_address || 'Chennai Commercial Hub'}</strong>
                </div>
                {visit.notes && (
                  <div style={{ fontSize: '0.82rem', color: '#334155', marginTop: '8px', background: '#ffffff', padding: '8px 12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                    <strong>Notes:</strong> {visit.notes}
                  </div>
                )}
              </div>
            ))}
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

export default EmployeeDetailPage;
