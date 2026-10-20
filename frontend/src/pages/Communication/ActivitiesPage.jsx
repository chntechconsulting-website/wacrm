import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { 
  Search, 
  PhoneCall, 
  Mail, 
  Calendar, 
  FileText,
  Clock,
  CheckCircle,
  RefreshCw,
  MessageCircle,
  UserCheck,
  Zap,
  Filter
} from 'lucide-react';

const getActivityIconAndColor = (type = '') => {
  const t = (type || '').toUpperCase();
  if (t.includes('CALL')) return { icon: PhoneCall, color: '#2563eb' };
  if (t.includes('WHATSAPP')) return { icon: MessageCircle, color: '#25d366' };
  if (t.includes('FOLLOW')) return { icon: Calendar, color: '#f59e0b' };
  if (t.includes('STATUS') || t.includes('CONVERTED')) return { icon: CheckCircle, color: '#10b981' };
  if (t.includes('EMAIL')) return { icon: Mail, color: '#0d9488' };
  if (t.includes('NOTE')) return { icon: FileText, color: '#8b5cf6' };
  return { icon: Zap, color: '#6366f1' };
};

const ActivitiesPage = () => {
  const { user } = useAuth();
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [scopeFilter, setScopeFilter] = useState(user?.role === 'ADMIN' ? 'ALL' : 'MY');

  const fetchActivities = async () => {
    setLoading(true);
    setActivities([]); // Immediately clear previous state to prevent stale data display
    try {
      const params = {};
      if (typeFilter) params.activity_type = typeFilter;
      if (scopeFilter) params.scope = scopeFilter;

      const res = await API.get('/activities', { params });
      setActivities(res.data || []);
    } catch (err) {
      console.error('Failed to fetch activities:', err);
      setActivities([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActivities();
  }, [typeFilter, scopeFilter]);

  const filteredActivities = activities.filter(act => {
    if (!search.trim()) return true;
    const term = search.toLowerCase();
    const leadName = (act.lead_name || '').toLowerCase();
    const empName = (act.created_by_name || '').toLowerCase();
    const desc = (act.description || '').toLowerCase();
    const actType = (act.activity_type || '').toLowerCase();

    return leadName.includes(term) || empName.includes(term) || desc.includes(term) || actType.includes(term);
  });

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <div style={{ fontSize: '0.82rem', color: '#64748b', marginBottom: '6px' }}>
            <Link to="/dashboard" style={{ color: '#2563eb', textDecoration: 'none' }}>Dashboard</Link> / {' '}
            <span style={{ color: '#0f172a', fontWeight: 600 }}>Activities</span>
          </div>
          <h1 className="page-title">Activity Audit Stream</h1>
          <p className="page-subtitle">Real-time contextual sales actions, status changes, calls, and follow-ups powered by live database records.</p>
        </div>
        <button className="btn btn-secondary" onClick={fetchActivities} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Toolbar */}
      <div className="table-toolbar">
        <div className="search-box">
          <Search size={18} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search by lead, employee, or details..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <select 
            value={scopeFilter} 
            onChange={(e) => setScopeFilter(e.target.value)}
            style={{ width: '170px' }}
          >
            <option value="MY">My Activities</option>
            {user?.role === 'MANAGER' && <option value="MANAGER">Team Activities</option>}
            {user?.role === 'ADMIN' && <option value="ALL">All Company Activities</option>}
          </select>

          <select 
            value={typeFilter} 
            onChange={(e) => setTypeFilter(e.target.value)}
            style={{ width: '180px' }}
          >
            <option value="">All Activity Types</option>
            <option value="CALL">Calls</option>
            <option value="FOLLOWUP">Follow-ups</option>
            <option value="WHATSAPP">WhatsApp</option>
            <option value="STATUS_CHANGED">Status Changes</option>
            <option value="NOTE_ADDED">Notes</option>
            <option value="CREATED">Lead Creations</option>
          </select>
        </div>
      </div>

      {/* Timeline Card */}
      <div className="content-card">
        {loading ? (
          <div className="text-center py-4 text-muted" style={{ padding: '40px' }}>
            <RefreshCw size={24} className="spin" style={{ marginBottom: '10px', color: '#2563eb' }} />
            <div>Loading contextual activity log...</div>
          </div>
        ) : filteredActivities.length === 0 ? (
          <div className="text-center py-4 text-muted" style={{ padding: '40px' }}>
            No activity records found matching the current context and filters.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {filteredActivities.map((act) => {
              const { icon: IconComp, color: iconColor } = getActivityIconAndColor(act.activity_type);
              const formattedTime = act.created_at ? new Date(act.created_at).toLocaleString() : 'N/A';

              return (
                <div key={act.activity_id || act.id} style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
                  <div style={{ 
                    width: '42px', 
                    height: '42px', 
                    borderRadius: '50%', 
                    backgroundColor: `${iconColor}15`, 
                    color: iconColor, 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    flexShrink: 0,
                    border: `1px solid ${iconColor}30`
                  }}>
                    <IconComp size={20} />
                  </div>

                  <div style={{ flex: 1, backgroundColor: '#f8fafc', padding: '16px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <div>
                        {act.lead_name && (
                          <span style={{ fontWeight: 700, color: '#0f172a', marginRight: '8px' }}>
                            {act.lead_name} (Lead {act.lead_id})
                          </span>
                        )}
                        <span className="role-badge" style={{ backgroundColor: `${iconColor}15`, color: iconColor, border: `1px solid ${iconColor}30`, fontWeight: 700 }}>
                          {act.activity_type}
                        </span>
                      </div>
                      <span style={{ fontSize: '0.78rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={13} /> {formattedTime}
                      </span>
                    </div>

                    <p style={{ fontSize: '0.88rem', color: '#334155', marginBottom: '8px', lineHeight: 1.5 }}>
                      {act.description}
                    </p>

                    <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                      Logged by: <span style={{ fontWeight: 600, color: '#0f172a' }}>{act.created_by_name || 'System / Auto'}</span>
                      {act.related_entity_type && (
                        <span style={{ marginLeft: '12px', color: '#94a3b8' }}>
                          Ref: {act.related_entity_type} #{act.related_entity_id}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default ActivitiesPage;
