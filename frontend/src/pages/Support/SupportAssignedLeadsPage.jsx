import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { formatDateDDMMYYYY, formatLeadReceivedFull } from '../../utils/dateUtils';
import CustomerPurchaseDetails from '../../components/Support/CustomerPurchaseDetails';
import SupportInteractionTimeline from '../../components/Support/SupportInteractionTimeline';
import './SupportAssignedLeadsPage.css';

import {
  Users,
  UserCheck,
  Building2,
  Phone,
  Mail,
  MapPin,
  Calendar,
  Clock,
  Search,
  RefreshCw,
  Eye,
  FilePlus,
  CalendarPlus,
  UserPlus,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  X,
  ChevronLeft,
  ChevronRight,
  Filter,
  Tag,
  Briefcase,
  ShieldCheck,
  MessageSquare,
  History
} from 'lucide-react';

// Support status is independent from the Sales lead status. The backend
// normalises these values, while the labels below are display-only.
const SUPPORT_STATUS_OPTIONS = [
  { value: 'NEW', label: 'New' },
  { value: 'ONBOARDING', label: 'Onboarding' },
  { value: 'INSTALLATION_PENDING', label: 'Onboarding Pending' },
  { value: 'INSTALLATION_COMPLETED', label: 'Onboarding Completed' },
  { value: 'TRAINING', label: 'Training' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'ISSUE_RAISED', label: 'Issue Raised' },
  { value: 'RESOLVED', label: 'Resolved' },
];

const LEGACY_SUPPORT_STATUS_MAP = {
  PENDING_ONBOARDING: 'NEW',
  PENDING_CONTACT: 'NEW',
  CONTACTED: 'ONBOARDING',
  ONBOARDING_IN_PROGRESS: 'ONBOARDING',
  IN_PROGRESS: 'ONBOARDING',
  IN_TRAINING: 'TRAINING',
  LIVE: 'ACTIVE',
  COMPLETED: 'RESOLVED',
  COMPLETE: 'RESOLVED',
  DONE: 'RESOLVED',
};

const normalizeSupportStatus = (value) => {
  const key = String(value || 'NEW').trim().toUpperCase().replace(/[\s-]/g, '_');
  return LEGACY_SUPPORT_STATUS_MAP[key] || key;
};

const supportStatusLabel = (value) => {
  const canonical = normalizeSupportStatus(value);
  const option = SUPPORT_STATUS_OPTIONS.find((item) => item.value === canonical);
  return option?.label || canonical.replace(/_/g, ' ');
};

const OPEN_SUPPORT_STATUSES = [
  'ONBOARDING',
  'INSTALLATION_PENDING',
  'INSTALLATION_COMPLETED',
  'TRAINING',
  'ISSUE_RAISED',
];

const PRIORITY_OPTIONS = ['ALL', 'HIGH', 'MEDIUM', 'LOW'];

const SOURCE_OPTIONS = ['ALL', 'META', 'WEBSITE', 'MANUAL', 'EXCEL', 'REFERRAL'];

export default function SupportAssignedLeadsPage() {
  const { user } = useAuth();
  const userRole = (user?.role || '').toUpperCase();
  const isManager = userRole === 'SUPPORT_MANAGER' || userRole === 'ADMIN';
  const isAdmin = userRole === 'ADMIN';

  // State
  const [leads, setLeads] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [teamMembers, setTeamMembers] = useState([]);

  // Filters & Pagination
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [priorityFilter, setPriorityFilter] = useState('ALL');
  const [sourceFilter, setSourceFilter] = useState('ALL');
  const [agentFilter, setAgentFilter] = useState('');
  const [page, setPage] = useState(1);
  const limit = 25;

  // Modals & Drawers
  const [selectedLead, setSelectedLead] = useState(null);
  const [activeDrawerTab, setActiveDrawerTab] = useState('overview');
  const [leadActivities, setLeadActivities] = useState([]);
  const [loadingActivities, setLoadingActivities] = useState(false);

  // Quick Action Modals
  const [activityModalLead, setActivityModalLead] = useState(null);
  const [activityDesc, setActivityDesc] = useState('');
  const [activityType, setActivityType] = useState('NOTE');
  const [savingActivity, setSavingActivity] = useState(false);

  const [followupModalLead, setFollowupModalLead] = useState(null);
  const [followupDate, setFollowupDate] = useState('');
  const [followupTime, setFollowupTime] = useState('11:00');
  const [followupNote, setFollowupNote] = useState('');
  const [savingFollowup, setSavingFollowup] = useState(false);

  const [assignModalLead, setAssignModalLead] = useState(null);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [savingAssign, setSavingAssign] = useState(false);

  // Toast Notification
  const [toastMessage, setToastMessage] = useState(null);
  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const [searchParams] = useSearchParams();

  // Auto-open lead drawer if openLeadId query parameter is provided
  useEffect(() => {
    const targetLeadId = searchParams.get('openLeadId');
    if (!targetLeadId) return;
    const leadIdNum = parseInt(targetLeadId, 10);
    if (!leadIdNum) return;

    const match = leads.find(l => l.id === leadIdNum);
    if (match) {
      handleOpenLeadDrawer(match);
    } else {
      API.get(`/leads/${leadIdNum}`)
        .then(res => {
          if (res.data) {
            handleOpenLeadDrawer(res.data);
          }
        })
        .catch(err => {
          console.error('Failed to load targeted lead details:', err);
        });
    }
  }, [searchParams, leads]);

  // Update one visible row + an open drawer without replacing the table with a
  // loading state or losing filters/pagination.
  const patchLeadRow = (leadId, updates) => {
    setLeads(prev => prev.map(lead => (
      lead.id === leadId ? { ...lead, ...updates } : lead
    )));
    setSelectedLead(prev => (
      prev && prev.id === leadId ? { ...prev, ...updates } : prev
    ));
  };

  // Fetch Team Members (for Support Manager / Admin assignment)
  useEffect(() => {
    if (isManager) {
      API.get('/leads/support/team-members')
        .then(res => {
          if (Array.isArray(res.data)) {
            setTeamMembers(res.data);
          }
        })
        .catch(err => {
          console.error('Failed to load support team members:', err);
        });
    }
  }, [isManager]);

  // Debounce the search box (one request per pause instead of per keystroke).
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Fetch Assigned Leads
  const fetchAssignedLeads = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const params = {
        skip: (page - 1) * limit,
        limit: limit
      };

      if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
      if (statusFilter !== 'ALL') params.status = statusFilter;
      if (priorityFilter !== 'ALL') params.priority = priorityFilter;
      if (sourceFilter !== 'ALL') params.source = sourceFilter;
      if (agentFilter) params.assigned_agent_id = agentFilter;

      const res = await API.get('/leads/support/assigned', { params });
      if (res.data) {
        setLeads(res.data.items || []);
        setTotal(res.data.total || 0);
      }
    } catch (err) {
      console.error('Error fetching support assigned leads:', err);
      showToast(err.response?.data?.detail || 'Failed to fetch assigned leads.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, limit, debouncedSearch, statusFilter, priorityFilter, sourceFilter, agentFilter]);

  useEffect(() => {
    fetchAssignedLeads();
  }, [fetchAssignedLeads]);

  // Fetch Activities for Selected Lead Drawer
  const fetchLeadActivities = async (leadId) => {
    setLoadingActivities(true);
    try {
      const res = await API.get(`/activities?lead_id=${leadId}&limit=50`);
      if (Array.isArray(res.data)) {
        setLeadActivities(res.data);
      }
    } catch (err) {
      console.error('Failed to load lead activities:', err);
    } finally {
      setLoadingActivities(false);
    }
  };

  const handleOpenLeadDrawer = (lead) => {
    setSelectedLead(lead);
    setActiveDrawerTab('overview');
    fetchLeadActivities(lead.id);
  };

  // Support status change. This deliberately uses the Support-only endpoint
  // and never touches the Sales lead status.
  const handleStatusChange = async (leadId, newStatus) => {
    try {
      const canonicalStatus = normalizeSupportStatus(newStatus);
      await API.put(`/leads/${leadId}/support-status`, {
        support_status: canonicalStatus,
      });
      showToast(
        `Customer #${leadId} Support status updated to ${supportStatusLabel(canonicalStatus)}`
      );
      patchLeadRow(leadId, {
        support_status: canonicalStatus,
        onboarding_status: canonicalStatus,
      });
    } catch (err) {
      console.error('Failed to update Support status:', err);
      showToast(err.response?.data?.detail || 'Failed to update Support status.');
    }
  };

  // Save Activity / Note
  const handleSaveActivity = async () => {
    if (!activityDesc.trim()) return;
    setSavingActivity(true);
    try {
      await API.post('/activities', {
        lead_id: activityModalLead.id,
        activity_type: activityType,
        description: activityDesc.trim()
      });
      showToast('Activity note added successfully.');
      const activityLeadId = activityModalLead.id;
      setActivityModalLead(null);
      setActivityDesc('');
      if (selectedLead && selectedLead.id === activityLeadId) {
        fetchLeadActivities(selectedLead.id);
      }
    } catch (err) {
      console.error('Failed to add activity:', err);
      showToast(err.response?.data?.detail || 'Failed to add activity.');
    } finally {
      setSavingActivity(false);
    }
  };

  // Save Follow-up
  const handleSaveFollowup = async () => {
    if (!followupDate) return;
    setSavingFollowup(true);
    try {
      await API.post('/followups', {
        lead_id: followupModalLead.id,
        followup_date: followupDate,
        followup_time: followupTime,
        note: followupNote.trim(),
        status: 'Pending'
      });
      showToast('Follow-up scheduled successfully.');
      const followupLeadId = followupModalLead.id;
      patchLeadRow(followupLeadId, {
        next_followup_date: followupDate,
        next_followup_time: followupTime
      });
      setFollowupModalLead(null);
      setFollowupDate('');
      setFollowupNote('');
      window.dispatchEvent(new Event('leadStatsUpdated'));
    } catch (err) {
      console.error('Failed to schedule follow-up:', err);
      showToast(err.response?.data?.detail || 'Failed to schedule follow-up.');
    } finally {
      setSavingFollowup(false);
    }
  };

  // Assign Support Agent (Support Manager & Admin). The backend additionally
  // enforces that the deal is explicitly CONVERTED_TO_SUPPORT and that the
  // target is an active Support Executive.
  const handleSaveAssign = async () => {
    if (!selectedAgentId) return;
    const salesStatus = normalizeSupportStatus(
      assignModalLead?.sales_status || assignModalLead?.status || ''
    );
    if (salesStatus !== 'CONVERTED_TO_SUPPORT') {
      showToast('Support assignment is enabled only after the deal is converted to Support.');
      return;
    }
    setSavingAssign(true);
    try {
      const res = await API.put(`/leads/${assignModalLead.id}/support-assign`, {
        assigned_agent_id: parseInt(selectedAgentId, 10)
      });
      showToast(
        res.data?.already_assigned
          ? 'This Support Executive is already assigned.'
          : 'Lead assigned to support executive.'
      );
      patchLeadRow(assignModalLead.id, {
        assigned_support_executive_id: res.data?.assigned_agent_id,
        assigned_support_executive_name: res.data?.assigned_agent_name,
        support_assigned_to: res.data?.assigned_agent_id,
        support_assigned_to_name: res.data?.assigned_agent_name,
        support_assigned_at: res.data?.support_assigned_at,
        support_manager_id: res.data?.support_manager_id,
        support_manager_name: res.data?.support_manager_name,
        support_assignment_status: 'ASSIGNED'
      });
      setAssignModalLead(null);
      setSelectedAgentId('');
      window.dispatchEvent(new Event('leadStatsUpdated'));
    } catch (err) {
      console.error('Failed to assign support agent:', err);
      showToast(err.response?.data?.detail || 'Failed to assign agent.');
    } finally {
      setSavingAssign(false);
    }
  };

  // Reset Filters
  const handleResetFilters = () => {
    setSearch('');
    setStatusFilter('ALL');
    setPriorityFilter('ALL');
    setSourceFilter('ALL');
    setAgentFilter('');
    setPage(1);
  };

  // KPI Calculations (Support status only; Sales status is read-only)
  const kpiPendingCount = leads.filter(
    l => normalizeSupportStatus(l.support_status || l.onboarding_status) === 'NEW'
  ).length;
  const kpiInProgressCount = leads.filter(
    l => OPEN_SUPPORT_STATUSES.includes(normalizeSupportStatus(l.support_status || l.onboarding_status))
  ).length;
  const kpiHighPriorityCount = leads.filter(l => (l.priority || '').toUpperCase() === 'HIGH').length;

  return (
    <div className="support-leads-container">
      {/* Toast Notification */}
      {toastMessage && <div className="support-toast">{toastMessage}</div>}

      {/* Header */}
      <div className="support-leads-header">
        <div className="support-header-title-area">
          <h1>
            <UserCheck size={26} color="#2563eb" />
            Support Assigned Leads
          </h1>
          <p>Complete customer issue management, onboarding, and service tracking for your assigned leads.</p>
        </div>
        <div className="support-header-actions">
          <button
            type="button"
            className="support-btn-refresh"
            onClick={() => fetchAssignedLeads(true)}
            disabled={refreshing || loading}
          >
            <RefreshCw size={15} className={refreshing ? 'spin-icon' : ''} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="support-kpi-grid">
        <div className="support-kpi-card">
          <div className="kpi-icon-wrap blue">
            <Users size={22} />
          </div>
          <div className="kpi-info-wrap">
            <span className="kpi-label">Total Assigned</span>
            <span className="kpi-value">{total}</span>
          </div>
        </div>

        <div className="support-kpi-card">
          <div className="kpi-icon-wrap amber">
            <Clock size={22} />
          </div>
          <div className="kpi-info-wrap">
            <span className="kpi-label">Pending Onboarding</span>
            <span className="kpi-value">{kpiPendingCount}</span>
          </div>
        </div>

        <div className="support-kpi-card">
          <div className="kpi-icon-wrap purple">
            <Briefcase size={22} />
          </div>
          <div className="kpi-info-wrap">
            <span className="kpi-label">In Progress</span>
            <span className="kpi-value">{kpiInProgressCount}</span>
          </div>
        </div>

        <div className="support-kpi-card">
          <div className="kpi-icon-wrap green">
            <AlertCircle size={22} />
          </div>
          <div className="kpi-info-wrap">
            <span className="kpi-label">High Priority</span>
            <span className="kpi-value">{kpiHighPriorityCount}</span>
          </div>
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="support-toolbar-card">
        <div className="support-toolbar-row">
          <div className="support-search-wrap">
            <Search size={16} className="search-input-icon" />
            <input
              type="text"
              className="support-search-input"
              placeholder="Search by customer, company, phone, email, requirements..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>

          <div className="support-select-wrap">
            <select
              className="support-select"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="ALL">All Support Statuses</option>
              {SUPPORT_STATUS_OPTIONS.map(status => (
                <option key={status.value} value={status.value}>{status.label}</option>
              ))}
            </select>
          </div>

          <div className="support-select-wrap">
            <select
              className="support-select"
              value={priorityFilter}
              onChange={(e) => {
                setPriorityFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="ALL">All Priorities</option>
              {PRIORITY_OPTIONS.filter(p => p !== 'ALL').map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          <div className="support-select-wrap">
            <select
              className="support-select"
              value={sourceFilter}
              onChange={(e) => {
                setSourceFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="ALL">All Sources</option>
              {SOURCE_OPTIONS.filter(src => src !== 'ALL').map(src => (
                <option key={src} value={src}>{src}</option>
              ))}
            </select>
          </div>

          {isManager && teamMembers.length > 0 && (
            <div className="support-select-wrap">
              <select
                className="support-select"
                value={agentFilter}
                onChange={(e) => {
                  setAgentFilter(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All Support Agents</option>
                {teamMembers.map(tm => (
                  <option key={tm.id} value={tm.id}>{tm.name} ({tm.role})</option>
                ))}
              </select>
            </div>
          )}

          <button
            type="button"
            className="support-btn-reset"
            onClick={handleResetFilters}
            title="Reset Filters"
          >
            <Filter size={14} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* Main Table */}
      <div className="support-table-card">
        {loading ? (
          <div className="support-empty-state">
            <div className="empty-icon-wrap">
              <RefreshCw size={28} className="spin-icon" />
            </div>
            <h3>Loading assigned leads...</h3>
            <p>Fetching authorized support records from server.</p>
          </div>
        ) : leads.length === 0 ? (
          <div className="support-empty-state">
            <div className="empty-icon-wrap">
              <HelpCircle size={28} />
            </div>
            <h3>No assigned support leads found</h3>
            <p>There are no support leads matching your filters or assigned to your scope.</p>
            <button type="button" className="support-btn-reset" onClick={handleResetFilters}>
              Clear Filters
            </button>
          </div>
        ) : (
          <div className="support-table-responsive">
            <table className="support-leads-table">
              <thead>
                <tr>
                  <th>Lead ID</th>
                  <th>Customer / Company</th>
                  <th>Contact Info</th>
                  <th>Location</th>
                  <th>Product / Service</th>
                  <th>Support Requirements</th>
                  <th>Assigned Agent</th>
                  <th>Sales Status</th>
                  <th>Support Status</th>
                  <th>Priority</th>
                  <th>Next Follow-up</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => {
                  const supportStatus = normalizeSupportStatus(
                    lead.support_status || lead.onboarding_status
                  );
                  const supportStatusClean = supportStatus.toLowerCase().replace(/[\s-]/g, '_');
                  const salesStatus = lead.sales_status || lead.status || 'NEW';
                  const salesStatusClean = salesStatus.toLowerCase().replace(/[\s-]/g, '_');
                  const priorityClean = (lead.priority || 'medium').toLowerCase();

                  return (
                    <tr key={lead.id}>
                      {/* 1. Lead ID */}
                      <td>
                        <button
                          type="button"
                          className="lead-id-pill"
                          onClick={() => handleOpenLeadDrawer(lead)}
                          title="View Lead Details"
                        >
                          #{lead.id}
                        </button>
                      </td>

                      {/* 2. Customer / Company */}
                      <td>
                        <div className="lead-company-cell">
                          <span className="company-name">
                            <Building2 size={13} color="#64748b" />
                            {lead.company_name || lead.company || 'Individual Client'}
                          </span>
                          <span className="contact-name">
                            {lead.contact_person || lead.name || 'Direct Contact'}
                          </span>
                        </div>
                      </td>

                      {/* 3. Contact Info */}
                      <td>
                        <div className="contact-links-cell">
                          {lead.phone && (
                            <a href={`tel:${lead.phone}`} className="contact-link">
                              <Phone size={12} />
                              <span>{lead.phone}</span>
                            </a>
                          )}
                          {lead.email && (
                            <a href={`mailto:${lead.email}`} className="contact-link">
                              <Mail size={12} />
                              <span>{lead.email}</span>
                            </a>
                          )}
                        </div>
                      </td>

                      {/* 4. Company Address / Location */}
                      <td>
                        <span className="location-tag">
                          <MapPin size={12} />
                          {lead.location || (lead.city ? `${lead.city}, ${lead.state || ''}` : 'Location N/A')}
                        </span>
                      </td>

                      {/* 5. Product / Service Interest */}
                      <td>
                        <span className="product-tag" title={lead.product_service}>
                          {lead.product_service || 'Support & Services'}
                        </span>
                      </td>

                      {/* 6. Support Requirements / Issue Details */}
                      <td>
                        <div className="req-notes-preview" title={lead.support_requirements || 'No notes specified'}>
                          {lead.support_requirements || 'No specific requirements recorded'}
                        </div>
                      </td>

                      {/* 7. Assigned Support Executive & Manager */}
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontWeight: 600, color: '#0f172a', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <UserCheck size={12} color="#2563eb" />
                            {lead.assigned_support_executive_name
                              || (lead.trial_status && !lead.support_handoff_id
                                ? (lead.assigned_support_manager_name
                                    ? `Support Manager: ${lead.assigned_support_manager_name}`
                                    : 'Pending assignment')
                                : 'Unassigned Agent')}
                          </span>
                          {lead.assigned_support_manager_name && (
                            <span style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                              Mgr: {lead.assigned_support_manager_name}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* 8. Sales Status (read-only) */}
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                          <span
                            className={`status-pill ${salesStatusClean}`}
                            title="Sales status is managed by the Sales team"
                          >
                            {salesStatus.replace(/_/g, ' ')}
                          </span>
                          {lead.is_trial_expired && (
                            <span style={{
                              padding: '2px 7px',
                              borderRadius: '10px',
                              backgroundColor: '#fee2e2',
                              color: '#b91c1c',
                              border: '1px solid #fca5a5',
                              fontWeight: '800',
                              fontSize: '0.68rem',
                              letterSpacing: '0.03em',
                              textTransform: 'uppercase'
                            }}>
                              Expired
                            </span>
                          )}
                          {!lead.is_trial_expired && lead.trial_status === 'TRIAL_EXPIRING_SOON' && (
                            <span style={{
                              padding: '2px 7px',
                              borderRadius: '10px',
                              backgroundColor: '#fff7ed',
                              color: '#c2410c',
                              border: '1px solid #fed7aa',
                              fontWeight: '800',
                              fontSize: '0.68rem',
                              letterSpacing: '0.03em',
                              textTransform: 'uppercase'
                            }}>
                              Trial Expiring Soon
                            </span>
                          )}
                        </div>
                      </td>

                      {/* 9. Support Status (editable by Support only) */}
                      <td>
                        {lead.support_handoff_id ? (
                          <select
                            className={`status-pill ${supportStatusClean}`}
                            value={supportStatus}
                            onChange={(e) => handleStatusChange(lead.id, e.target.value)}
                            title="Support status is independent from Sales status"
                          >
                            {SUPPORT_STATUS_OPTIONS.map(st => (
                              <option key={st.value} value={st.value}>{st.label}</option>
                            ))}
                          </select>
                        ) : (
                          <span
                            className={`status-pill ${supportStatusClean}`}
                            title="Support status becomes editable once the deal is converted to Support"
                          >
                            {(SUPPORT_STATUS_OPTIONS.find(st => st.value === supportStatus) || {}).label || supportStatus.replace(/_/g, ' ')}
                          </span>
                        )}
                      </td>

                      {/* 10. Priority */}
                      <td>
                        <span className={`priority-pill ${priorityClean}`}>
                          {lead.priority || 'MEDIUM'}
                        </span>
                      </td>

                      {/* 11. Next Follow-up Date */}
                      <td>
                        {lead.next_followup_date ? (
                          <div style={{ display: 'flex', flexDirection: 'column', fontSize: '12px', color: '#0f172a' }}>
                            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <Calendar size={12} color="#64748b" />
                              {formatDateDDMMYYYY(lead.next_followup_date)}
                            </span>
                            {lead.next_followup_time && (
                              <span style={{ fontSize: '11px', color: '#64748b' }}>
                                {lead.next_followup_time}
                              </span>
                            )}
                          </div>
                        ) : (
                          <button
                            type="button"
                            className="support-btn-reset"
                            style={{ padding: '3px 8px', fontSize: '11px' }}
                            onClick={() => setFollowupModalLead(lead)}
                          >
                            + Schedule
                          </button>
                        )}
                      </td>

                      {/* 12. Actions */}
                      <td>
                        <div className="support-row-actions">
                          <button
                            type="button"
                            className="action-btn-icon blue"
                            title="View Full Lead Details"
                            onClick={() => handleOpenLeadDrawer(lead)}
                          >
                            <Eye size={15} />
                          </button>

                          <button
                            type="button"
                            className="action-btn-icon amber"
                            title="Log Activity / Note"
                            onClick={() => setActivityModalLead(lead)}
                          >
                            <FilePlus size={15} />
                          </button>

                          <button
                            type="button"
                            className="action-btn-icon green"
                            title="Schedule Follow-up"
                            onClick={() => setFollowupModalLead(lead)}
                          >
                            <CalendarPlus size={15} />
                          </button>

                          {isManager && (() => {
                            const assignmentSalesStatus = normalizeSupportStatus(
                              lead.sales_status || lead.status || ''
                            );
                            const isConverted = assignmentSalesStatus === 'CONVERTED_TO_SUPPORT';
                            return (
                              <button
                                type="button"
                                className="action-btn-icon"
                                title={isConverted
                                  ? 'Assign Support Agent'
                                  : 'Support assignment is enabled only after the Sales team converts the deal to Support'}
                                disabled={!isConverted}
                                onClick={() => {
                                  if (!isConverted) return;
                                  setAssignModalLead(lead);
                                  setSelectedAgentId(lead.assigned_support_executive_id || '');
                                }}
                              >
                                <UserPlus size={15} />
                              </button>
                            );
                          })()}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {total > limit && (
          <div className="support-pagination">
            <span className="pagination-text">
              Showing {(page - 1) * limit + 1} to {Math.min(page * limit, total)} of {total} leads
            </span>
            <div className="pagination-controls">
              <button
                type="button"
                className="pagination-btn"
                disabled={page <= 1}
                onClick={() => setPage(prev => Math.max(prev - 1, 1))}
              >
                <ChevronLeft size={14} style={{ verticalAlign: 'middle' }} /> Previous
              </button>
              <button
                type="button"
                className="pagination-btn"
                disabled={page * limit >= total}
                onClick={() => setPage(prev => prev + 1)}
              >
                Next <ChevronRight size={14} style={{ verticalAlign: 'middle' }} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* LEAD DETAILS DRAWER / MODAL */}
      {/* ========================================================================= */}
      {selectedLead && (
        <div className="support-modal-backdrop" onClick={() => setSelectedLead(null)}>
          <div className="support-modal-card drawer-mode" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <UserCheck size={20} color="#2563eb" />
                Support Lead Details: #{selectedLead.id} - {selectedLead.company_name || selectedLead.name}
              </h2>
              <button type="button" className="modal-close-btn" onClick={() => setSelectedLead(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {/* Tab Navigation */}
              <div className="modal-tabs">
                <button
                  type="button"
                  className={`modal-tab-btn ${activeDrawerTab === 'overview' ? 'active' : ''}`}
                  onClick={() => setActiveDrawerTab('overview')}
                >
                  Overview & Contact
                </button>
                <button
                  type="button"
                  className={`modal-tab-btn ${activeDrawerTab === 'requirements' ? 'active' : ''}`}
                  onClick={() => setActiveDrawerTab('requirements')}
                >
                  Product & Requirements
                </button>
                <button
                  type="button"
                  className={`modal-tab-btn ${activeDrawerTab === 'activities' ? 'active' : ''}`}
                  onClick={() => setActiveDrawerTab('activities')}
                >
                  Activities & Timeline ({leadActivities.length})
                </button>
                <button
                  type="button"
                  className={`modal-tab-btn ${activeDrawerTab === 'purchase' ? 'active' : ''}`}
                  onClick={() => setActiveDrawerTab('purchase')}
                >
                  Customer Purchase Details
                </button>
                <button
                  type="button"
                  className={`modal-tab-btn ${activeDrawerTab === 'history' ? 'active' : ''}`}
                  onClick={() => setActiveDrawerTab('history')}
                >
                  <History size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                  Support History
                </button>
              </div>

              {/* Tab 1: Overview & Contact */}
              {activeDrawerTab === 'overview' && (
                <div className="detail-grid">
                  <div className="detail-item">
                    <span className="detail-label">Lead ID</span>
                    <span className="detail-value">#{selectedLead.id}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Customer / Company Name</span>
                    <span className="detail-value">{selectedLead.company_name || selectedLead.company || 'N/A'}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Contact Person</span>
                    <span className="detail-value">{selectedLead.contact_person || selectedLead.name || 'N/A'}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Phone Number</span>
                    <span className="detail-value">{selectedLead.phone || 'N/A'}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Email Address</span>
                    <span className="detail-value">{selectedLead.email || 'N/A'}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Company Address / Location</span>
                    <span className="detail-value">{selectedLead.location || `${selectedLead.city || ''}, ${selectedLead.state || ''}`.trim() || 'N/A'}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Lead Source</span>
                    <span className="detail-value">{selectedLead.source || 'Manual'}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Sales Status (read-only)</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      <span className="detail-value" style={{ textTransform: 'capitalize' }}>
                        {(selectedLead.sales_status || selectedLead.status)?.replace(/_/g, ' ') || 'NEW'}
                      </span>
                      {selectedLead.is_trial_expired && (
                        <span style={{
                          padding: '2px 7px',
                          borderRadius: '10px',
                          backgroundColor: '#fee2e2',
                          color: '#b91c1c',
                          border: '1px solid #fca5a5',
                          fontWeight: '800',
                          fontSize: '0.68rem',
                          letterSpacing: '0.03em',
                          textTransform: 'uppercase'
                        }}>
                          Expired
                        </span>
                      )}
                    </div>
                  </div>

                  {(selectedLead.trial_start_date || selectedLead.trial_end_date) && (
                    <div className="detail-item" style={{ gridColumn: 'span 2', backgroundColor: selectedLead.is_trial_expired ? '#fef2f2' : '#f0f9ff', padding: '10px 14px', borderRadius: '8px', border: `1px solid ${selectedLead.is_trial_expired ? '#fecaca' : '#bae6fd'}` }}>
                      <span className="detail-label" style={{ color: selectedLead.is_trial_expired ? '#b91c1c' : '#0369a1', fontWeight: 700 }}>
                        Trial Period {selectedLead.is_trial_expired ? '(EXPIRED)' : ''}
                      </span>
                      <span className="detail-value" style={{ color: selectedLead.is_trial_expired ? '#991b1b' : '#0c4a6e', marginTop: '4px', display: 'block' }}>
                        {formatDateDDMMYYYY(selectedLead.trial_start_date)} to {formatDateDDMMYYYY(selectedLead.trial_end_date)}
                        {selectedLead.trial_days_remaining !== null && selectedLead.trial_days_remaining !== undefined && (
                          <span style={{ marginLeft: '8px', fontWeight: 600 }}>
                            ({selectedLead.trial_days_remaining >= 0 ? `${selectedLead.trial_days_remaining} days remaining` : `Expired ${Math.abs(selectedLead.trial_days_remaining)} days ago`})
                          </span>
                        )}
                      </span>
                    </div>
                  )}

                  <div className="detail-item">
                    <span className="detail-label">Support Status</span>
                    <span className="detail-value">
                      {supportStatusLabel(selectedLead.support_status || selectedLead.onboarding_status)}
                    </span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Customer / Handover Reference</span>
                    <span className="detail-value">
                      {selectedLead.customer_id ? `Customer #${selectedLead.customer_id}` : 'Customer N/A'}
                      {selectedLead.support_handoff_id ? ` · Handover #${selectedLead.support_handoff_id}` : ''}
                    </span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Original Sales Handover</span>
                    <span className="detail-value">
                      {selectedLead.sales_employee_name || 'Sales N/A'}
                      {selectedLead.won_at ? ` · WON ${formatDateDDMMYYYY(selectedLead.won_at)}` : ''}
                    </span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Priority</span>
                    <span className="detail-value">{selectedLead.priority || 'MEDIUM'}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Assigned Support Executive</span>
                    <span className="detail-value">{selectedLead.assigned_support_executive_name || 'Unassigned'}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Assigned Support Manager</span>
                    <span className="detail-value">{selectedLead.assigned_support_manager_name || 'N/A'}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Assignment Date</span>
                    <span className="detail-value">{selectedLead.assignment_date ? formatDateDDMMYYYY(selectedLead.assignment_date) : 'N/A'}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Last Updated</span>
                    <span className="detail-value">{selectedLead.last_updated ? formatLeadReceivedFull(selectedLead.last_updated) : 'N/A'}</span>
                  </div>

                  <div className="detail-item">
                    <span className="detail-label">Next Follow-up</span>
                    <span className="detail-value">
                      {selectedLead.next_followup_date ? `${formatDateDDMMYYYY(selectedLead.next_followup_date)} ${selectedLead.next_followup_time || ''}` : 'None Scheduled'}
                    </span>
                  </div>
                </div>
              )}

              {/* Tab 2: Product & Requirements */}
              {activeDrawerTab === 'requirements' && (
                <div className="detail-grid">
                  <div className="detail-item full-width">
                    <span className="detail-label">Product / Service Interest</span>
                    <span className="detail-value">{selectedLead.product_service || 'Support & Services'}</span>
                  </div>

                  <div className="detail-item full-width">
                    <span className="detail-label">Support Requirements / Issue Details</span>
                    <div style={{ background: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid #e2e8f0', marginTop: '4px', fontSize: '13px', whiteSpace: 'pre-wrap' }}>
                      {selectedLead.support_requirements || selectedLead.requirement_notes || 'No specific requirements or notes entered.'}
                    </div>
                  </div>

                  <div className="detail-item full-width">
                    <span className="detail-label">Support Status</span>
                    <span className="detail-value">
                      {supportStatusLabel(selectedLead.support_status || selectedLead.onboarding_status)}
                    </span>
                  </div>
                </div>
              )}

              {/* Tab 3: Activities & Timeline */}
              {activeDrawerTab === 'activities' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>Activity Audit Log</span>
                    <button
                      type="button"
                      className="support-btn-reset"
                      onClick={() => setActivityModalLead(selectedLead)}
                    >
                      <FilePlus size={14} />
                      <span>Add Note</span>
                    </button>
                  </div>

                  {loadingActivities ? (
                    <div style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                      <RefreshCw size={20} className="spin-icon" style={{ marginBottom: '8px' }} />
                      <p>Loading timeline...</p>
                    </div>
                  ) : leadActivities.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '30px', color: '#64748b', background: '#f8fafc', borderRadius: '8px' }}>
                      <MessageSquare size={24} style={{ marginBottom: '6px', color: '#94a3b8' }} />
                      <p>No activity records logged for this lead yet.</p>
                    </div>
                  ) : (
                    <div className="activity-stream">
                      {leadActivities.map(act => (
                        <div key={act.id || Math.random()} className="activity-item">
                          <div className="activity-bullet" />
                          <div className="activity-content">
                            <div className="activity-desc">{act.description || act.activity_type}</div>
                            <div className="activity-meta">
                              {act.created_at ? formatLeadReceivedFull(act.created_at) : 'Recent'} &bull; By {act.performed_by_name || 'System / Support'}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Tab 4: Customer Purchase Details */}
              {activeDrawerTab === 'purchase' && (
                <CustomerPurchaseDetails
                  purchaseDetails={selectedLead.purchase_details}
                  leadId={selectedLead.id}
                />
              )}

              {/* Tab 5: Append-only Support interaction history */}
              {activeDrawerTab === 'history' && (
                <SupportInteractionTimeline
                  leadId={selectedLead.id}
                  customerId={selectedLead.customer_id}
                  canAdd
                  onChanged={() => {
                    fetchLeadActivities(selectedLead.id);
                    fetchAssignedLeads(true);
                  }}
                />
              )}
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="modal-btn-cancel"
                onClick={() => setSelectedLead(null)}
              >
                Close
              </button>
              <button
                type="button"
                className="modal-btn-primary"
                onClick={() => {
                  setFollowupModalLead(selectedLead);
                }}
              >
                Schedule Follow-up
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ADD NOTE / LOG ACTIVITY MODAL */}
      {/* ========================================================================= */}
      {activityModalLead && (
        <div className="support-modal-backdrop" onClick={() => setActivityModalLead(null)}>
          <div className="support-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <FilePlus size={18} color="#2563eb" />
                Add Activity / Note for #{activityModalLead.id}
              </h2>
              <button type="button" className="modal-close-btn" onClick={() => setActivityModalLead(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Activity Category</label>
                <select
                  className="form-select"
                  value={activityType}
                  onChange={(e) => setActivityType(e.target.value)}
                >
                  <option value="NOTE">General Note</option>
                  <option value="CALL">Call Record</option>
                  <option value="WHATSAPP">WhatsApp Communication</option>
                  <option value="ONBOARDING_UPDATE">Onboarding Progress</option>
                  <option value="ISSUE_RESOLVED">Issue Resolution</option>
                </select>
              </div>

              <div className="form-group">
                <label>Description / Note Details *</label>
                <textarea
                  className="form-textarea"
                  placeholder="Enter details of customer communication, support progress, or action items..."
                  value={activityDesc}
                  onChange={(e) => setActivityDesc(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="modal-btn-cancel"
                onClick={() => setActivityModalLead(null)}
                disabled={savingActivity}
              >
                Cancel
              </button>
              <button
                type="button"
                className="modal-btn-primary"
                onClick={handleSaveActivity}
                disabled={savingActivity || !activityDesc.trim()}
              >
                {savingActivity ? 'Saving...' : 'Save Activity'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SCHEDULE FOLLOW-UP MODAL */}
      {/* ========================================================================= */}
      {followupModalLead && (
        <div className="support-modal-backdrop" onClick={() => setFollowupModalLead(null)}>
          <div className="support-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <CalendarPlus size={18} color="#2563eb" />
                Schedule Follow-up: #{followupModalLead.id} - {followupModalLead.company_name || followupModalLead.name}
              </h2>
              <button type="button" className="modal-close-btn" onClick={() => setFollowupModalLead(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Follow-up Date *</label>
                <input
                  type="date"
                  className="form-input"
                  value={followupDate}
                  onChange={(e) => setFollowupDate(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>Follow-up Time</label>
                <input
                  type="time"
                  className="form-input"
                  value={followupTime}
                  onChange={(e) => setFollowupTime(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>Follow-up Agenda / Note</label>
                <textarea
                  className="form-textarea"
                  placeholder="Purpose of follow-up (e.g., Check software installation, review credentials, customer training)..."
                  value={followupNote}
                  onChange={(e) => setFollowupNote(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="modal-btn-cancel"
                onClick={() => setFollowupModalLead(null)}
                disabled={savingFollowup}
              >
                Cancel
              </button>
              <button
                type="button"
                className="modal-btn-primary"
                onClick={handleSaveFollowup}
                disabled={savingFollowup || !followupDate}
              >
                {savingFollowup ? 'Scheduling...' : 'Schedule Follow-up'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ASSIGN SUPPORT AGENT MODAL (Support Manager & Admin) */}
      {/* ========================================================================= */}
      {assignModalLead && (
        <div className="support-modal-backdrop" onClick={() => setAssignModalLead(null)}>
          <div className="support-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <UserCheck size={18} color="#2563eb" />
                Assign Support Executive: #{assignModalLead.id}
              </h2>
              <button type="button" className="modal-close-btn" onClick={() => setAssignModalLead(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              {normalizeSupportStatus(assignModalLead.sales_status || assignModalLead.status || '') !== 'CONVERTED_TO_SUPPORT' && (
                <div style={{ background: '#fffbeb', border: '1px solid #fde68a', color: '#92400e', borderRadius: '8px', padding: '10px 12px', marginBottom: '12px', fontSize: '0.82rem', fontWeight: 600 }}>
                  Support assignment is disabled until Sales marks the deal WON and explicitly converts it to Support.
                </div>
              )}
              <div className="form-group">
                <label>Select Support Executive *</label>
                <select
                  className="form-select"
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                  disabled={normalizeSupportStatus(assignModalLead.sales_status || assignModalLead.status || '') !== 'CONVERTED_TO_SUPPORT'}
                >
                  <option value="">-- Choose Support Executive --</option>
                  {teamMembers.map(tm => (
                    <option key={tm.id} value={tm.id}>
                      {tm.name} ({tm.role})
                    </option>
                  ))}
                </select>
                <small style={{ color: '#64748b', marginTop: '6px', display: 'block' }}>
                  Only active Support Executives are eligible. Sales employees, Managers/Admins and inactive users are excluded.
                </small>
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="modal-btn-cancel"
                onClick={() => setAssignModalLead(null)}
                disabled={savingAssign}
              >
                Cancel
              </button>
              <button
                type="button"
                className="modal-btn-primary"
                onClick={handleSaveAssign}
                disabled={
                  savingAssign ||
                  !selectedAgentId ||
                  normalizeSupportStatus(assignModalLead.sales_status || assignModalLead.status || '') !== 'CONVERTED_TO_SUPPORT'
                }
              >
                {savingAssign ? 'Assigning...' : 'Assign Executive'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
