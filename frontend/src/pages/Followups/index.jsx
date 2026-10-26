import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { 
  CalendarClock, 
  Plus, 
  Search, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Edit2, 
  Trash2, 
  X, 
  AlertCircle, 
  Check,
  Calendar,
  User,
  Phone,
  PhoneCall,
  Tag
} from 'lucide-react';
import { formatDateDDMMYYYY, formatTime12Hour } from '../../utils/dateUtils';
import PingoMascot from '../../components/Common/PingoMascot';
import PingoEmptyState from '../../components/Common/PingoEmptyState';
import TimePickerSelect from '../../components/Common/TimePickerSelect';

const PRIORITIES = ['LOW', 'MEDIUM', 'HIGH'];
const STATUSES = ['Pending', 'Completed', 'Cancelled'];

const Followups = () => {
  const { user: currentUser } = useAuth();
  const normRole = (currentUser?.role || '').toUpperCase();
  const isManagerOrAdmin = ['ADMIN', 'MANAGER', 'SALES_MANAGER', 'SUPPORT_MANAGER'].includes(normRole);
  const [followups, setFollowups] = useState([]);
  const [leads, setLeads] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const [statusFilter, setStatusFilter] = useState(queryParams.get('status') || queryParams.get('status_filter') || '');
  const [priorityFilter, setPriorityFilter] = useState(queryParams.get('priority') || queryParams.get('priority_filter') || '');
  const [search, setSearch] = useState('');

  // Alerts
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Modals state
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedFollowup, setSelectedFollowup] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Form State
  const [formData, setFormData] = useState({
    lead_id: '',
    assigned_to: '',
    followup_date: new Date().toISOString().split('T')[0],
    followup_time: '10:00 AM',
    notes: '',
    priority: 'MEDIUM',
    status: 'Pending'
  });

  const fetchFollowups = async () => {
    try {
      setLoading(true);
      const params = {};
      if (statusFilter) params.status_filter = statusFilter;
      if (priorityFilter) params.priority_filter = priorityFilter;

      const res = await API.get('/followups/', { params });
      setFollowups(res.data);
      window.dispatchEvent(new Event('leadStatsUpdated'));
    } catch (err) {
      console.error(err);
      setError('Failed to fetch follow-ups list.');
    } finally {
      setLoading(false);
    }
  };

  const fetchDropdownData = async () => {
    try {
      const [leadsRes, empRes] = await Promise.all([
        API.get('/leads/'),
        API.get('/employees/?status_filter=ACTIVE')
      ]);
      setLeads(leadsRes.data.items || []);
      setEmployees(empRes.data || []);
    } catch (err) {
      console.error(err);
    }
  };

  // Sync filters if URL query params change
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const urlStatus = params.get('status') || params.get('status_filter');
    const urlPriority = params.get('priority') || params.get('priority_filter');
    if (urlStatus !== null) setStatusFilter(urlStatus);
    if (urlPriority !== null) setPriorityFilter(urlPriority);
  }, [location.search]);

  useEffect(() => {
    fetchFollowups();
    fetchDropdownData();
  }, [statusFilter, priorityFilter, currentUser?.id, currentUser?.employee_id]);

  const handleOpenScheduleModal = () => {
    setFormData({
      lead_id: leads.length > 0 ? leads[0].id : '',
      assigned_to: currentUser?.employee_id || '',
      followup_date: new Date().toISOString().split('T')[0],
      followup_time: '10:00 AM',
      notes: '',
      priority: 'MEDIUM',
      status: 'Pending'
    });
    setError('');
    setShowScheduleModal(true);
  };

  const handleOpenEditModal = (f) => {
    setSelectedFollowup(f);
    setFormData({
      lead_id: f.lead_id,
      assigned_to: f.assigned_to,
      followup_date: f.followup_date,
      followup_time: f.followup_time || '10:00 AM',
      notes: f.notes || '',
      priority: f.priority,
      status: f.status
    });
    setError('');
    setShowEditModal(true);
  };

  const handleCreateFollowup = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!formData.lead_id || !formData.followup_date) {
      setError('Please select a lead and follow-up date.');
      return;
    }

    try {
      setSubmitting(true);
      const payload = {
        ...formData,
        lead_id: parseInt(formData.lead_id),
        assigned_to: isManagerOrAdmin && formData.assigned_to ? parseInt(formData.assigned_to) : (currentUser?.employee_id || null)
      };

      await API.post('/followups/', payload);
      setSuccess('Follow-up scheduled successfully!');
      setShowScheduleModal(false);
      fetchFollowups();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to schedule follow-up.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateFollowup = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      setSubmitting(true);
      await API.put(`/followups/${selectedFollowup.id}`, formData);
      setSuccess('Follow-up updated successfully!');
      setShowEditModal(false);
      window.dispatchEvent(new Event('followupReminderRefresh'));
      fetchFollowups();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to update follow-up.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleQuickStatusChange = async (followupId, newStatus) => {
    try {
      await API.put(`/followups/${followupId}`, { status: newStatus });
      setSuccess(`Follow-up status marked as ${newStatus}`);
      window.dispatchEvent(new Event('followupReminderRefresh'));
      fetchFollowups();
    } catch (err) {
      console.error(err);
      setError('Failed to update status.');
    }
  };

  const handleDeleteFollowup = async (id) => {
    const isManager = (currentUser?.role || '').toUpperCase() === 'MANAGER';
    const confirmMsg = isManager 
      ? 'Deleting this follow-up requires Admin approval. Submit a delete request to Admin?' 
      : 'Are you sure you want to permanently delete this follow-up?';

    if (!window.confirm(confirmMsg)) return;

    try {
      const res = await API.delete(`/followups/${id}`);
      if (res.data?.status === 'pending_approval') {
        setSuccess(res.data.message || 'Deletion request submitted to Admin for approval.');
      } else {
        setSuccess(res.data?.message || 'Follow-up deleted successfully.');
      }
      fetchFollowups();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to delete follow-up.');
    }
  };

  const filteredFollowups = followups.filter(f => 
    f.lead_name.toLowerCase().includes(search.toLowerCase()) ||
    f.lead_phone.toLowerCase().includes(search.toLowerCase()) ||
    (f.notes && f.notes.toLowerCase().includes(search.toLowerCase())) ||
    f.assigned_employee_name.toLowerCase().includes(search.toLowerCase())
  );

  const getPriorityBadgeStyle = (priority) => {
    switch (priority) {
      case 'HIGH': return { bg: 'rgba(239, 68, 68, 0.12)', color: '#dc2626' };
      case 'MEDIUM': return { bg: 'rgba(245, 158, 11, 0.12)', color: '#d97706' };
      case 'LOW': return { bg: 'rgba(59, 130, 246, 0.12)', color: '#2563eb' };
      default: return { bg: '#f1f5f9', color: '#64748b' };
    }
  };

  const getStatusBadgeStyle = (status) => {
    switch (status) {
      case 'Completed': return { bg: 'rgba(16, 185, 129, 0.12)', color: '#059669' };
      case 'Pending': return { bg: 'rgba(245, 158, 11, 0.12)', color: '#d97706' };
      case 'Cancelled': return { bg: 'rgba(239, 68, 68, 0.12)', color: '#dc2626' };
      default: return { bg: '#f1f5f9', color: '#64748b' };
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Follow-up Management</h1>
          <p className="page-subtitle">Schedule, track, and manage scheduled calls and follow-ups with leads.</p>
        </div>
        <div className="header-actions">
          <button className="btn btn-primary" onClick={handleOpenScheduleModal}>
            <Plus size={18} /> Schedule Follow-up
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error mb-4">
          <AlertCircle size={18} /> <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="alert alert-success mb-4" style={{ backgroundColor: 'var(--success-light)', color: 'var(--success)', border: '1px solid rgba(16,185,129,0.3)', padding: '12px', borderRadius: '8px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Check size={18} /> <span>{success}</span>
        </div>
      )}

      <div className="content-card">
        <div className="table-toolbar" style={{ flexWrap: 'wrap', gap: '12px' }}>
          <div className="search-box">
            <Search size={18} className="search-icon" />
            <input 
              type="text" 
              placeholder="Search follow-ups by lead name, phone, notes..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <select 
              value={statusFilter} 
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ paddingLeft: '14px', width: '150px' }}
            >
              <option value="">All Statuses</option>
              {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>

            <select 
              value={priorityFilter} 
              onChange={(e) => setPriorityFilter(e.target.value)}
              style={{ paddingLeft: '14px', width: '150px' }}
            >
              <option value="">All Priorities</option>
              {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>

        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Lead Name</th>
                <th>Phone</th>
                <th>Assigned Rep</th>
                <th>Date & Time</th>
                <th>Priority</th>
                <th>Notes</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="9" className="text-center py-4 text-muted">
                    Loading follow-ups...
                  </td>
                </tr>
              ) : filteredFollowups.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{ padding: '36px 16px', background: '#f8fafc' }}>
                    <PingoEmptyState
                      pose="run"
                      height={120}
                      title="No Scheduled Follow-ups"
                      description={search || statusFilter || priorityFilter ? "No follow-up tasks match your filter criteria." : "All follow-ups completed! Keep your sales momentum running."}
                      actionLabel="Schedule Follow-up"
                      onAction={handleOpenScheduleModal}
                      actionIcon={Plus}
                      secondaryActionLabel={search || statusFilter || priorityFilter ? "Reset Filters" : null}
                      onSecondaryAction={() => {
                        setSearch('');
                        setStatusFilter('');
                        setPriorityFilter('');
                      }}
                    />
                  </td>
                </tr>
              ) : (
                filteredFollowups.map((f) => {
                  const prioStyle = getPriorityBadgeStyle(f.priority);
                  const statusStyle = getStatusBadgeStyle(f.status);

                  return (
                    <tr key={f.id}>
                      <td>{f.id}</td>
                      <td><strong>{f.lead_name}</strong></td>
                      <td>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          <span>{f.lead_phone || '-'}</span>
                          {f.lead_phone && (
                            <button
                              type="button"
                              className="btn-table-dial"
                              onClick={() => {
                                if (window.crmDial) {
                                  window.crmDial(f.lead_phone, { name: f.lead_name, phone: f.lead_phone, id: f.lead_id });
                                }
                              }}
                              title={`Dial ${f.lead_name}`}
                            >
                              <PhoneCall size={12} />
                            </button>
                          )}
                        </div>
                      </td>
                      <td>{f.assigned_employee_name}</td>
                      <td>
                        <div>
                          <strong>{formatDateDDMMYYYY(f.followup_date)}</strong>
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{formatTime12Hour(f.followup_time)}</div>
                        </div>
                      </td>
                      <td>
                        <span style={{
                          padding: '3px 8px',
                          borderRadius: '10px',
                          fontSize: '0.75rem',
                          fontWeight: '600',
                          backgroundColor: prioStyle.bg,
                          color: prioStyle.color
                        }}>
                          {f.priority}
                        </span>
                      </td>
                      <td>
                        <div style={{ maxWidth: '200px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={f.notes}>
                          {f.notes || '-'}
                        </div>
                      </td>
                      <td>
                        <select
                          value={f.status}
                          onChange={(e) => handleQuickStatusChange(f.id, e.target.value)}
                          style={{
                            padding: '4px 8px',
                            borderRadius: '12px',
                            fontSize: '0.75rem',
                            fontWeight: '600',
                            backgroundColor: statusStyle.bg,
                            color: statusStyle.color,
                            border: 'none',
                            cursor: 'pointer'
                          }}
                        >
                          {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                      <td>
                        <div className="action-buttons" style={{ display: 'flex', gap: '6px' }}>
                          <button 
                            className="btn btn-outline" 
                            style={{ padding: '6px 8px' }}
                            title="Edit Follow-up"
                            onClick={() => handleOpenEditModal(f)}
                          >
                            <Edit2 size={15} />
                          </button>
                          {(currentUser?.role === 'ADMIN' || currentUser?.role === 'MANAGER') && (
                            <button 
                              className="btn btn-outline" 
                              style={{ padding: '6px 8px', color: 'var(--danger)' }}
                              title="Delete Follow-up"
                              onClick={() => handleDeleteFollowup(f.id)}
                            >
                              <Trash2 size={15} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* SCHEDULE FOLLOW-UP MODAL */}
      {showScheduleModal && (
        <div className="modal-backdrop" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: '520px', padding: '28px',
            boxShadow: 'var(--shadow-lg)'
          }}>
            <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: '700' }}>Schedule Follow-up</h3>
              <button onClick={() => setShowScheduleModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateFollowup}>
              <div className="form-group">
                <label>Select Lead *</label>
                <select 
                  required
                  value={formData.lead_id} 
                  onChange={(e) => setFormData({ ...formData, lead_id: e.target.value })}
                  style={{ paddingLeft: '14px' }}
                >
                  <option value="">Choose Lead...</option>
                  {leads.map(lead => (
                    <option key={lead.id} value={lead.id}>#{lead.id} - {lead.name} ({lead.phone})</option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label>Follow-up Date *</label>
                  <input 
                    type="date" 
                    required 
                    value={formData.followup_date}
                    onChange={(e) => setFormData({ ...formData, followup_date: e.target.value })}
                    style={{ paddingLeft: '14px' }}
                  />
                </div>

                <div className="form-group">
                  <label>Time</label>
                  <TimePickerSelect 
                    value={formData.followup_time}
                    onChange={(e) => setFormData({ ...formData, followup_time: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label>Priority</label>
                  <select 
                    value={formData.priority} 
                    onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                    style={{ paddingLeft: '14px' }}
                  >
                    {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>

                <div className="form-group">
                  <label>Assign to Rep</label>
                  {isManagerOrAdmin ? (
                    <select 
                      value={formData.assigned_to} 
                      onChange={(e) => setFormData({ ...formData, assigned_to: e.target.value })}
                      style={{ paddingLeft: '14px' }}
                    >
                      <option value="">Default (Lead Rep)</option>
                      {employees.map(emp => (
                        <option key={emp.id} value={emp.id}>{emp.name}</option>
                      ))}
                    </select>
                  ) : (
                    <input 
                      type="text" 
                      disabled 
                      value={currentUser?.name || currentUser?.employee_name || currentUser?.username || 'Myself'} 
                      style={{ paddingLeft: '14px', backgroundColor: 'var(--bg-muted, #f1f5f9)', cursor: 'not-allowed' }}
                    />
                  )}
                </div>
              </div>

              <div className="form-group">
                <label>Notes / Objective</label>
                <textarea 
                  rows="3" 
                  placeholder="e.g. Call to discuss product demo and pricing quote..." 
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  style={{ paddingLeft: '14px', paddingTop: '10px' }}
                />
              </div>

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowScheduleModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Scheduling...' : 'Schedule Follow-up'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT FOLLOW-UP MODAL */}
      {showEditModal && (
        <div className="modal-backdrop" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: '520px', padding: '28px',
            boxShadow: 'var(--shadow-lg)'
          }}>
            <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: '700' }}>Edit Follow-up #{selectedFollowup?.id}</h3>
              <button onClick={() => setShowEditModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleUpdateFollowup}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label>Follow-up Date</label>
                  <input 
                    type="date" 
                    value={formData.followup_date}
                    onChange={(e) => setFormData({ ...formData, followup_date: e.target.value })}
                    style={{ paddingLeft: '14px' }}
                  />
                </div>

                <div className="form-group">
                  <label>Time</label>
                  <TimePickerSelect 
                    value={formData.followup_time}
                    onChange={(e) => setFormData({ ...formData, followup_time: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label>Priority</label>
                  <select 
                    value={formData.priority} 
                    onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                    style={{ paddingLeft: '14px' }}
                  >
                    {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>

                <div className="form-group">
                  <label>Status</label>
                  <select 
                    value={formData.status} 
                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                    style={{ paddingLeft: '14px' }}
                  >
                    {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>Notes</label>
                <textarea 
                  rows="3" 
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  style={{ paddingLeft: '14px', paddingTop: '10px' }}
                />
              </div>

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowEditModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Followups;
