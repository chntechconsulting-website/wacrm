import React, { useCallback, useEffect, useMemo, useState } from 'react';
import API from '../../services/api';
import { formatDateDDMMYYYY, formatLeadReceivedFull } from '../../utils/dateUtils';
import {
  AlertCircle,
  CalendarCheck2,
  CalendarDays,
  CheckCircle2,
  Clock,
  History,
  Loader2,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  UserCheck,
  Users,
  X,
  XCircle,
} from 'lucide-react';
import './SupportManagerPage.css';

const LEAVE_TYPES = ['CASUAL', 'SICK', 'ANNUAL', 'MATERNITY', 'UNPAID', 'OTHER'];

const formatDateTime = (value) => {
  if (!value) return '—';
  const formatted = formatLeadReceivedFull(value);
  return formatted === '-' ? String(value) : formatted;
};

const statusClass = (status) => String(status || '').toLowerCase().replace(/\s+/g, '-');

const emptyLeaveForm = () => ({
  employee_id: '',
  leave_type: 'CASUAL',
  start_date: '',
  end_date: '',
  reason: '',
});

export default function SupportManagerPage() {
  const [overview, setOverview] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [leaves, setLeaves] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  const [leaveForm, setLeaveForm] = useState(emptyLeaveForm);
  const [savingLeave, setSavingLeave] = useState(false);

  const [coverageLeave, setCoverageLeave] = useState(null);
  const [coverageCustomers, setCoverageCustomers] = useState([]);
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [selectedBackupId, setSelectedBackupId] = useState('');
  const [selectedLeadIds, setSelectedLeadIds] = useState([]);
  const [assigningCoverage, setAssigningCoverage] = useState(false);

  const showToast = (message) => {
    setToast(message);
    setTimeout(() => setToast(''), 4000);
  };

  const fetchAll = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const [overviewResponse, employeesResponse, leavesResponse] = await Promise.all([
        API.get('/support/manager/overview'),
        API.get('/support/employees'),
        API.get('/support/leaves', { params: { include_past: true } }),
      ]);
      setOverview(overviewResponse.data || null);
      setEmployees(Array.isArray(employeesResponse.data) ? employeesResponse.data : []);
      setLeaves(Array.isArray(leavesResponse.data) ? leavesResponse.data : []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Support Manager data could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const availableBackups = useMemo(() => {
    if (!coverageLeave) return employees;
    return employees.filter(
      (employee) =>
        employee.employee_id !== coverageLeave.employee_id &&
        employee.available &&
        !employee.on_approved_leave
    );
  }, [employees, coverageLeave]);

  const handleCreateLeave = async (event) => {
    event.preventDefault();
    if (!leaveForm.employee_id || !leaveForm.start_date || !leaveForm.end_date) {
      showToast('Select an employee and both leave dates.');
      return;
    }
    if (leaveForm.end_date < leaveForm.start_date) {
      showToast('Leave end date cannot be before the start date.');
      return;
    }
    setSavingLeave(true);
    try {
      await API.post('/support/leaves', {
        employee_id: Number(leaveForm.employee_id),
        leave_type: leaveForm.leave_type,
        start_date: leaveForm.start_date,
        end_date: leaveForm.end_date,
        reason: leaveForm.reason || null,
      });
      setLeaveForm(emptyLeaveForm());
      showToast('Leave request recorded. Approve it to assign temporary coverage.');
      await fetchAll(true);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Leave request could not be created.');
    } finally {
      setSavingLeave(false);
    }
  };

  const handleDecision = async (leaveId, action) => {
    try {
      const response = await API.post(`/support/leaves/${leaveId}/${action}`, {});
      showToast(`Leave ${action === 'approve' ? 'approved' : 'rejected'}.`);
      await fetchAll(true);
      if (action === 'approve') {
        const customers = response.data?.customers_needing_coverage || [];
        const leave = response.data?.leave;
        if (leave) {
          await openCoverageModal(leave, customers);
        }
      }
    } catch (err) {
      showToast(err.response?.data?.detail || `Leave could not be ${action}d.`);
    }
  };

  const handleCancelLeave = async (leaveId) => {
    if (!window.confirm('Cancel this leave? Active coverage must be ended first.')) return;
    try {
      await API.post(`/support/leaves/${leaveId}/cancel`);
      showToast('Leave cancelled.');
      await fetchAll(true);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Leave could not be cancelled.');
    }
  };

  const openCoverageModal = async (leave, preloadedCustomers = null) => {
    setCoverageLeave(leave);
    setCoverageLoading(true);
    setSelectedBackupId('');
    try {
      if (Array.isArray(preloadedCustomers)) {
        setCoverageCustomers(preloadedCustomers);
      } else {
        const response = await API.get(`/support/leaves/${leave.id}/customers`);
        setCoverageCustomers(response.data?.customers || []);
      }
      setCoverageLoading(false);
    } catch (err) {
      setCoverageLoading(false);
      showToast(err.response?.data?.detail || 'Affected customers could not be loaded.');
    }
  };

  useEffect(() => {
    if (!coverageLeave) return;
    const requiredIds = coverageCustomers
      .filter((customer) => customer.coverage_required)
      .map((customer) => customer.lead_id);
    setSelectedLeadIds(requiredIds);
  }, [coverageLeave, coverageCustomers]);

  const toggleLead = (leadId) => {
    setSelectedLeadIds((prev) =>
      prev.includes(leadId) ? prev.filter((id) => id !== leadId) : [...prev, leadId]
    );
  };

  const handleAssignCoverage = async () => {
    if (!coverageLeave || !selectedBackupId || selectedLeadIds.length === 0) {
      showToast('Select a backup employee and at least one uncovered customer.');
      return;
    }
    setAssigningCoverage(true);
    try {
      const response = await API.post(`/support/leaves/${coverageLeave.id}/coverage`, {
        backup_employee_id: Number(selectedBackupId),
        lead_ids: selectedLeadIds,
        all_assigned_customers: false,
      });
      const created = response.data?.created_count || 0;
      const skipped = response.data?.skipped_count || 0;
      showToast(`Temporary coverage assigned to ${created} customer(s)${skipped ? `; ${skipped} already covered` : ''}.`);
      setCoverageLeave(null);
      setCoverageCustomers([]);
      setSelectedLeadIds([]);
      await fetchAll(true);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Temporary coverage could not be assigned.');
    } finally {
      setAssigningCoverage(false);
    }
  };

  const handleRestore = async (coverage) => {
    const confirmed = window.confirm(
      `End temporary coverage for ${coverage.customer_name || `customer #${coverage.lead_id}`}? ` +
        `Permanent owner #${coverage.original_employee_id} will remain unchanged.`
    );
    if (!confirmed) return;
    try {
      await API.post(`/support/coverage/${coverage.id}/restore`);
      showToast('Temporary coverage ended. Permanent ownership was not modified.');
      await fetchAll(true);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Coverage could not be restored automatically.');
    }
  };

  if (loading) {
    return (
      <div className="support-manager-page">
        <div className="support-history-state">
          <Loader2 size={24} className="spin-icon" />
          <p>Loading Support Manager controls...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="support-manager-page">
        <div className="support-history-state error">
          <AlertCircle size={24} />
          <p>{error}</p>
          <button type="button" className="support-history-secondary-btn" onClick={() => fetchAll(true)}>
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      </div>
    );
  }

  const overviewData = overview || {};
  const overviewEmployees = overviewData.employees || [];
  const approvedLeaves = overviewData.approved_leaves || [];
  const activeCoverage = overviewData.active_coverage || [];
  const pendingIssues = overviewData.pending_issues || [];
  const overdueFollowUps = overviewData.overdue_follow_ups || [];
  const upcomingFollowUps = overviewData.upcoming_follow_ups || [];
  const handoverHistory = overviewData.handover_history || [];

  return (
    <div className="support-manager-page">
      {toast && <div className="support-manager-toast">{toast}</div>}

      <div className="support-manager-page-header">
        <div>
          <h1>Support Manager Controls</h1>
          <p>
            Availability, approved leave, temporary backup coverage, pending issues and handover
            history. Permanent Support ownership is never rewritten by coverage.
          </p>
        </div>
        <button type="button" className="support-manager-refresh" onClick={() => fetchAll(true)} disabled={refreshing}>
          <RefreshCw size={15} className={refreshing ? 'spin-icon' : ''} />
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="support-manager-kpis">
        <div className="support-manager-kpi">
          <Users size={20} />
          <span>Support employees</span>
          <strong>{overviewEmployees.length}</strong>
        </div>
        <div className="support-manager-kpi amber">
          <CalendarCheck2 size={20} />
          <span>Approved leave</span>
          <strong>{approvedLeaves.length}</strong>
        </div>
        <div className="support-manager-kpi blue">
          <UserCheck size={20} />
          <span>Temporary coverage</span>
          <strong>{overviewData.temporary_coverage_count || 0}</strong>
        </div>
        <div className="support-manager-kpi red">
          <AlertCircle size={20} />
          <span>Pending issues</span>
          <strong>{overviewData.pending_issue_count || 0}</strong>
        </div>
        <div className="support-manager-kpi red">
          <Clock size={20} />
          <span>Overdue follow-ups</span>
          <strong>{overviewData.overdue_follow_up_count || 0}</strong>
        </div>
      </div>

      <section className="support-manager-card">
        <div className="support-manager-card-head">
          <h2>
            <Users size={18} /> Employee availability
          </h2>
          <span>Presence comes from employee_presence; approved leave is shown separately.</span>
        </div>
        <div className="support-manager-table-wrap">
          <table className="support-manager-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Role</th>
                <th>Presence</th>
                <th>Availability</th>
                <th>Approved leave</th>
                <th>Assigned customers</th>
                <th>Temporary coverage</th>
              </tr>
            </thead>
            <tbody>
              {overviewEmployees.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-cell">No Support employees in your team.</td>
                </tr>
              ) : (
                overviewEmployees.map((employee) => (
                  <tr key={employee.employee_id}>
                    <td>
                      <strong>{employee.employee_name}</strong>
                      <span className="support-manager-muted">#{employee.employee_id}</span>
                    </td>
                    <td>{employee.role || '—'}</td>
                    <td>
                      <span className={`support-manager-pill ${employee.online ? 'online' : 'offline'}`}>
                        {employee.presence_status || 'OFFLINE'}
                      </span>
                    </td>
                    <td>
                      {employee.on_approved_leave ? (
                        <span className="support-manager-pill leave">ON LEAVE</span>
                      ) : employee.available ? (
                        <span className="support-manager-pill available">AVAILABLE</span>
                      ) : (
                        <span className="support-manager-pill offline">UNAVAILABLE</span>
                      )}
                    </td>
                    <td>
                      {employee.leave
                        ? `${formatDateDDMMYYYY(employee.leave.start_date)} → ${formatDateDDMMYYYY(employee.leave.end_date)}`
                        : '—'}
                    </td>
                    <td>{employee.assigned_customer_count || 0}</td>
                    <td>{employee.temporary_coverage_count || 0}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div className="support-manager-two-column">
        <section className="support-manager-card">
          <div className="support-manager-card-head">
            <h2>
              <CalendarDays size={18} /> Leave requests &amp; history
            </h2>
            <span>Only approved leave can create temporary coverage.</span>
          </div>

          <form className="support-manager-leave-form" onSubmit={handleCreateLeave}>
            <select
              value={leaveForm.employee_id}
              onChange={(event) => setLeaveForm((prev) => ({ ...prev, employee_id: event.target.value }))}
              required
            >
              <option value="">Select Support employee</option>
              {employees.map((employee) => (
                <option key={employee.employee_id} value={employee.employee_id}>
                  {employee.employee_name}
                </option>
              ))}
            </select>
            <select
              value={leaveForm.leave_type}
              onChange={(event) => setLeaveForm((prev) => ({ ...prev, leave_type: event.target.value }))}
            >
              {LEAVE_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
            <input
              type="date"
              value={leaveForm.start_date}
              onChange={(event) => setLeaveForm((prev) => ({ ...prev, start_date: event.target.value }))}
              required
            />
            <input
              type="date"
              value={leaveForm.end_date}
              onChange={(event) => setLeaveForm((prev) => ({ ...prev, end_date: event.target.value }))}
              required
            />
            <input
              type="text"
              placeholder="Reason (optional)"
              value={leaveForm.reason}
              onChange={(event) => setLeaveForm((prev) => ({ ...prev, reason: event.target.value }))}
            />
            <button type="submit" disabled={savingLeave}>
              {savingLeave ? <Loader2 size={14} className="spin-icon" /> : <CalendarCheck2 size={14} />}
              {savingLeave ? 'Saving...' : 'Record leave'}
            </button>
          </form>

          <div className="support-manager-table-wrap">
            <table className="support-manager-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Type</th>
                  <th>Dates</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {leaves.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="empty-cell">No leave records.</td>
                  </tr>
                ) : (
                  leaves.map((leave) => (
                    <tr key={leave.id}>
                      <td>
                        <strong>{leave.employee_name || `Employee #${leave.employee_id}`}</strong>
                        {leave.reason ? <span className="support-manager-muted">{leave.reason}</span> : null}
                      </td>
                      <td>{leave.leave_type}</td>
                      <td>
                        {formatDateDDMMYYYY(leave.start_date)} → {formatDateDDMMYYYY(leave.end_date)}
                      </td>
                      <td>
                        <span className={`support-manager-pill ${statusClass(leave.status)}`}>{leave.status}</span>
                      </td>
                      <td>
                        <div className="support-manager-row-actions">
                          {leave.status === 'PENDING' && (
                            <>
                              <button type="button" className="approve" onClick={() => handleDecision(leave.id, 'approve')}>
                                <CheckCircle2 size={13} /> Approve
                              </button>
                              <button type="button" className="reject" onClick={() => handleDecision(leave.id, 'reject')}>
                                <XCircle size={13} /> Reject
                              </button>
                            </>
                          )}
                          {leave.status === 'APPROVED' && (
                            <button type="button" className="coverage" onClick={() => openCoverageModal(leave)}>
                              <UserCheck size={13} /> Assign backup
                            </button>
                          )}
                          {['PENDING', 'APPROVED'].includes(leave.status) && (
                            <button type="button" className="cancel" onClick={() => handleCancelLeave(leave.id)}>
                              Cancel
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="support-manager-card">
          <div className="support-manager-card-head">
            <h2>
              <ShieldCheck size={18} /> Active temporary coverage
            </h2>
            <span>Restore only when the permanent owner is still unchanged.</span>
          </div>
          <div className="support-manager-table-wrap">
            <table className="support-manager-table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Original owner</th>
                  <th>Backup</th>
                  <th>Dates</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {activeCoverage.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="empty-cell">No active temporary coverage.</td>
                  </tr>
                ) : (
                  activeCoverage.map((coverage) => (
                    <tr key={coverage.id}>
                      <td>
                        <strong>{coverage.customer_name || `Lead #${coverage.lead_id}`}</strong>
                        <span className="support-manager-muted">{coverage.company_name || `Lead #${coverage.lead_id}`}</span>
                      </td>
                      <td>{coverage.original_employee_name || `#${coverage.original_employee_id}`}</td>
                      <td>{coverage.backup_employee_name || `#${coverage.backup_employee_id}`}</td>
                      <td>
                        {formatDateDDMMYYYY(coverage.start_date)} → {formatDateDDMMYYYY(coverage.end_date)}
                      </td>
                      <td>
                        <button type="button" className="restore" onClick={() => handleRestore(coverage)}>
                          <RotateCcw size={13} /> End coverage
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <div className="support-manager-two-column">
        <section className="support-manager-card">
          <div className="support-manager-card-head">
            <h2>
              <AlertCircle size={18} /> Pending issues
            </h2>
            <span>Latest recorded interaction per customer still carrying a pending issue.</span>
          </div>
          <div className="support-manager-table-wrap">
            <table className="support-manager-table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Pending issue</th>
                  <th>Handled by</th>
                  <th>Interaction time</th>
                </tr>
              </thead>
              <tbody>
                {pendingIssues.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="empty-cell">No pending Support issues.</td>
                  </tr>
                ) : (
                  pendingIssues.map((issue) => (
                    <tr key={issue.interaction_id}>
                      <td>
                        <strong>{issue.customer_name || `Lead #${issue.lead_id}`}</strong>
                        <span className="support-manager-muted">Lead #{issue.lead_id}</span>
                      </td>
                      <td>{issue.pending_issues}</td>
                      <td>{issue.handling_employee_name || '—'}</td>
                      <td>{formatDateTime(issue.interaction_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="support-manager-card">
          <div className="support-manager-card-head">
            <h2>
              <Clock size={18} /> Overdue &amp; upcoming follow-ups
            </h2>
            <span>Overdue comes from the latest Support interaction follow-up date/time.</span>
          </div>
          <div className="support-manager-list">
            {overdueFollowUps.length === 0 && upcomingFollowUps.length === 0 ? (
              <div className="support-manager-empty">No Support follow-ups recorded.</div>
            ) : (
              <>
                {overdueFollowUps.map((followUp) => (
                  <div key={`overdue-${followUp.interaction_id}`} className="support-manager-list-row overdue">
                    <div>
                      <strong>{followUp.customer_name || `Lead #${followUp.lead_id}`}</strong>
                      <span>{followUp.next_action || 'Follow-up action not recorded'}</span>
                    </div>
                    <span>{formatDateTime(followUp.follow_up_at)}</span>
                  </div>
                ))}
                {upcomingFollowUps.map((followUp) => (
                  <div key={`upcoming-${followUp.interaction_id}`} className="support-manager-list-row">
                    <div>
                      <strong>{followUp.customer_name || `Lead #${followUp.lead_id}`}</strong>
                      <span>{followUp.next_action || 'Follow-up action not recorded'}</span>
                    </div>
                    <span>{formatDateTime(followUp.follow_up_at)}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </section>
      </div>

      <section className="support-manager-card">
        <div className="support-manager-card-head">
          <h2>
            <History size={18} /> Backup / handover history
          </h2>
          <span>Every temporary coverage assignment and ending is kept as an audit record.</span>
        </div>
        <div className="support-manager-table-wrap">
          <table className="support-manager-table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>Original owner</th>
                <th>Backup</th>
                <th>Coverage dates</th>
                <th>Status</th>
                <th>Assigned at</th>
                <th>Ended at</th>
              </tr>
            </thead>
            <tbody>
              {handoverHistory.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-cell">No temporary coverage has been assigned yet.</td>
                </tr>
              ) : (
                handoverHistory.map((coverage) => (
                  <tr key={coverage.id}>
                    <td>
                      <strong>{coverage.customer_name || `Lead #${coverage.lead_id}`}</strong>
                      <span className="support-manager-muted">{coverage.company_name || '—'}</span>
                    </td>
                    <td>{coverage.original_employee_name || `#${coverage.original_employee_id}`}</td>
                    <td>{coverage.backup_employee_name || `#${coverage.backup_employee_id}`}</td>
                    <td>
                      {formatDateDDMMYYYY(coverage.start_date)} → {formatDateDDMMYYYY(coverage.end_date)}
                    </td>
                    <td>
                      <span className={`support-manager-pill ${statusClass(coverage.status)}`}>{coverage.status}</span>
                    </td>
                    <td>{formatDateTime(coverage.assigned_at)}</td>
                    <td>{coverage.ended_at ? formatDateTime(coverage.ended_at) : '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {coverageLeave && (
        <div className="support-manager-modal-backdrop" onClick={() => setCoverageLeave(null)}>
          <div className="support-manager-modal" onClick={(event) => event.stopPropagation()}>
            <div className="support-manager-modal-head">
              <div>
                <h3>
                  <UserCheck size={18} /> Assign temporary coverage
                </h3>
                <span>
                  {coverageLeave.employee_name} • {formatDateDDMMYYYY(coverageLeave.start_date)} →{' '}
                  {formatDateDDMMYYYY(coverageLeave.end_date)}
                </span>
              </div>
              <button type="button" onClick={() => setCoverageLeave(null)} title="Close">
                <X size={18} />
              </button>
            </div>

            <div className="support-manager-modal-body">
              {coverageLoading ? (
                <div className="support-history-state">
                  <Loader2 size={20} className="spin-icon" />
                  <p>Loading affected customers...</p>
                </div>
              ) : (
                <>
                  <div className="support-manager-field">
                    <label>Backup Support employee</label>
                    <select value={selectedBackupId} onChange={(event) => setSelectedBackupId(event.target.value)}>
                      <option value="">Select an available employee</option>
                      {availableBackups.map((employee) => (
                        <option key={employee.employee_id} value={employee.employee_id}>
                          {employee.employee_name} • {employee.assigned_customer_count || 0} own customers
                        </option>
                      ))}
                    </select>
                    <small>
                      The employee on leave and anyone also on approved leave during these dates cannot be selected.
                    </small>
                  </div>

                  <div className="support-manager-coverage-list">
                    <div className="support-manager-coverage-list-head">
                      <strong>Affected customers ({coverageCustomers.length})</strong>
                      <button
                        type="button"
                        onClick={() =>
                          setSelectedLeadIds(
                            coverageCustomers
                              .filter((customer) => customer.coverage_required)
                              .map((customer) => customer.lead_id)
                          )
                        }
                      >
                        Select all uncovered
                      </button>
                    </div>
                    {coverageCustomers.length === 0 ? (
                      <div className="support-manager-empty">This employee has no assigned customers requiring coverage.</div>
                    ) : (
                      coverageCustomers.map((customer) => (
                        <label
                          key={customer.lead_id}
                          className={`support-manager-coverage-item ${customer.coverage_required ? '' : 'covered'}`}
                        >
                          <input
                            type="checkbox"
                            disabled={!customer.coverage_required}
                            checked={selectedLeadIds.includes(customer.lead_id)}
                            onChange={() => toggleLead(customer.lead_id)}
                          />
                          <div>
                            <strong>{customer.customer_name || `Lead #${customer.lead_id}`}</strong>
                            <span>
                              {customer.company_name || 'Individual customer'}
                              {customer.product_service ? ` • ${customer.product_service}` : ''}
                            </span>
                          </div>
                          <span className={`support-manager-pill ${customer.coverage_required ? 'pending' : 'active'}`}>
                            {customer.coverage_required ? 'NEEDS COVERAGE' : 'ALREADY COVERED'}
                          </span>
                        </label>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>

            <div className="support-manager-modal-foot">
              <button type="button" className="cancel" onClick={() => setCoverageLeave(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                disabled={assigningCoverage || !selectedBackupId || selectedLeadIds.length === 0}
                onClick={handleAssignCoverage}
              >
                {assigningCoverage ? <Loader2 size={14} className="spin-icon" /> : <UserCheck size={14} />}
                {assigningCoverage ? 'Assigning...' : `Assign coverage (${selectedLeadIds.length})`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
