import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import './SalesTargetsPage.css';
import {
  Target,
  LayoutDashboard,
  TrendingUp,
  Plus,
  Edit2,
  Trash2,
  Calendar,
  Users,
  Award,
  CheckCircle2,
  Clock,
  Filter,
  DollarSign,
  AlertCircle,
  X,
  Building,
  FileText,
  Search
} from 'lucide-react';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const SalesTargetsPage = () => {
  const { user } = useAuth();
  const isAdmin = ['ADMIN', 'SUPERADMIN'].includes((user?.role || '').toUpperCase());

  const now = new Date();
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1); // 1-12
  const [selectedPeriodType, setSelectedPeriodType] = useState('monthly');
  const [selectedDepartment, setSelectedDepartment] = useState('All');
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(0);

  const [achievements, setAchievements] = useState([]);
  const [targetsList, setTargetsList] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modal State for Create / Edit Target
  const [showModal, setShowModal] = useState(false);
  const [editingTargetId, setEditingTargetId] = useState(null);
  const [formEmpId, setFormEmpId] = useState('');
  const [formPeriodType, setFormPeriodType] = useState('monthly');
  const [formMonth, setFormMonth] = useState(now.getMonth() + 1);
  const [formYear, setFormYear] = useState(now.getFullYear());
  const [formAmount, setFormAmount] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState(null);

  // Tab: 'achievements' or 'manage_targets'
  const [activeSubTab, setActiveSubTab] = useState('achievements');

  // Load active employees list for selectors
  useEffect(() => {
    API.get('/employees/')
      .then(res => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.items || []);
        const active = list.filter(e => (e.status || 'ACTIVE').toUpperCase() === 'ACTIVE');
        setEmployees(active);
        if (active.length > 0 && !formEmpId) {
          setFormEmpId(active[0].id);
        }
      })
      .catch(err => console.error('Failed to load employees for targets', err));
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const achParams = {
        period_year: selectedYear,
        period_type: selectedPeriodType
      };
      if (selectedPeriodType !== 'yearly') {
        achParams.period_month = selectedMonth;
      }
      if (selectedDepartment && selectedDepartment !== 'All') {
        achParams.department = selectedDepartment;
      }
      if (selectedEmployeeId && selectedEmployeeId !== 0) {
        achParams.employee_id = selectedEmployeeId;
      }

      const [achRes, tgtRes] = await Promise.all([
        API.get('/sales-targets/achievement', { params: achParams }),
        API.get('/sales-targets', {
          params: {
            period_year: selectedYear,
            period_type: selectedPeriodType
          }
        })
      ]);

      setAchievements(achRes.data || []);
      setTargetsList(tgtRes.data || []);
    } catch (err) {
      console.error('Failed to load targets and achievements', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    // Auto-update listeners for real-time reactivity without manual refresh
    const handleRevenueUpdate = () => {
      fetchData();
    };

    window.addEventListener('revenueUpdated', handleRevenueUpdate);

    return () => {
      window.removeEventListener('revenueUpdated', handleRevenueUpdate);
    };
  }, [selectedYear, selectedMonth, selectedPeriodType, selectedDepartment, selectedEmployeeId]);

  const handleOpenAddModal = (empId = null) => {
    setEditingTargetId(null);
    setFormEmpId(empId || (employees[0]?.id || ''));
    setFormPeriodType(selectedPeriodType);
    setFormMonth(selectedMonth);
    setFormYear(selectedYear);
    setFormAmount('');
    setModalError(null);
    setShowModal(true);
  };

  const handleOpenEditModal = (targetItem) => {
    setEditingTargetId(targetItem.id);
    setFormEmpId(targetItem.employee_id);
    setFormPeriodType(targetItem.period_type);
    setFormMonth(targetItem.period_month || 1);
    setFormYear(targetItem.period_year);
    setFormAmount(targetItem.target_amount);
    setModalError(null);
    setShowModal(true);
  };

  const handleSaveTarget = async (e) => {
    e.preventDefault();
    if (!formAmount || Number(formAmount) < 0) {
      setModalError('Please enter a valid target amount.');
      return;
    }

    try {
      setSubmitting(true);
      setModalError(null);

      if (editingTargetId) {
        await API.put(`/sales-targets/${editingTargetId}`, {
          target_amount: Number(formAmount)
        });
      } else {
        await API.post('/sales-targets', {
          employee_id: Number(formEmpId),
          target_amount: Number(formAmount),
          period_type: formPeriodType,
          period_month: formPeriodType === 'yearly' ? null : Number(formMonth),
          period_year: Number(formYear)
        });
      }

      setShowModal(false);
      fetchData();
    } catch (err) {
      setModalError(err.response?.data?.detail || 'Failed to save sales target.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteTarget = async (targetId) => {
    if (!window.confirm('Are you sure you want to delete this target?')) return;
    try {
      await API.delete(`/sales-targets/${targetId}`);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete target.');
    }
  };

  const formatINR = (amt) => {
    return `₹${Math.round(amt || 0).toLocaleString('en-IN')}`;
  };

  // Aggregated Summary Cards
  const totalAssigned = achievements.reduce((acc, row) => acc + (row.assigned_target || 0), 0);
  const totalActual = achievements.reduce((acc, row) => acc + (row.actual_revenue || 0), 0);
  const totalRemaining = Math.max(0, totalAssigned - totalActual);
  const overallAchievement = totalAssigned > 0 ? ((totalActual / totalAssigned) * 100).toFixed(1) : '0.0';

  return (
    <div className="sales-targets-container">
      {/* Top Switcher Tabs between Reports & Targets */}
      <div className="report-switcher-tabs">
        <Link to="/reports" className="report-tab-btn">
          <LayoutDashboard size={15} />
          <span>Sales Overview</span>
        </Link>
        <Link to="/reports?tab=revenue" className="report-tab-btn">
          <TrendingUp size={15} />
          <span>Sales Revenue</span>
        </Link>
        <Link to="/reports?tab=targets" className="report-tab-btn active">
          <Target size={15} />
          <span>Target Management</span>
        </Link>
      </div>

      {/* Header & Controls */}
      <div className="st-header">
        <div className="st-title-area">
          <div className="st-icon-badge">
            <Target size={24} />
          </div>
          <div className="st-title-text">
            <h1>Sales Target Management</h1>
            <p className="st-subtitle">
              Set employee targets, inspect confirmed invoice revenue, and track live achievement metrics.
            </p>
          </div>
        </div>

        {isAdmin && (
          <button
            type="button"
            className="st-btn-primary"
            onClick={() => handleOpenAddModal()}
          >
            <Plus size={16} />
            <span>Assign Target</span>
          </button>
        )}
      </div>

      {/* Filter Toolbar */}
      <div className="st-filter-card">
        <div className="st-filters-row">
          {/* Period Type */}
          <div className="st-filter-group">
            <label>Period Type</label>
            <select
              value={selectedPeriodType}
              onChange={(e) => setSelectedPeriodType(e.target.value)}
              className="st-select"
            >
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="yearly">Yearly</option>
            </select>
          </div>

          {/* Month (for Monthly & Quarterly) */}
          {selectedPeriodType !== 'yearly' && (
            <div className="st-filter-group">
              <label>Month</label>
              <select
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(Number(e.target.value))}
                className="st-select"
              >
                {MONTH_NAMES.map((name, idx) => (
                  <option key={idx + 1} value={idx + 1}>
                    {name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Year */}
          <div className="st-filter-group">
            <label>Year</label>
            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(Number(e.target.value))}
              className="st-select"
            >
              {[2024, 2025, 2026, 2027].map(yr => (
                <option key={yr} value={yr}>{yr}</option>
              ))}
            </select>
          </div>

          {/* Department */}
          <div className="st-filter-group">
            <label>Department</label>
            <select
              value={selectedDepartment}
              onChange={(e) => setSelectedDepartment(e.target.value)}
              className="st-select"
            >
              <option value="All">All Departments</option>
              <option value="SALES">Sales</option>
              <option value="SUPPORT">Support</option>
              <option value="ADMINISTRATION">Administration</option>
            </select>
          </div>

          {/* Employee */}
          <div className="st-filter-group">
            <label>Employee</label>
            <select
              value={selectedEmployeeId}
              onChange={(e) => setSelectedEmployeeId(Number(e.target.value))}
              className="st-select"
            >
              <option value={0}>All Employees</option>
              {employees.map(emp => (
                <option key={emp.id} value={emp.id}>{emp.name}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="st-kpi-grid">
        <div className="st-kpi-card">
          <div className="st-kpi-header">
            <span className="st-kpi-label">Assigned Target</span>
            <div className="st-kpi-icon-wrap" style={{ background: '#eff6ff', color: '#2563eb' }}>
              <Target size={20} />
            </div>
          </div>
          <div className="st-kpi-val">{formatINR(totalAssigned)}</div>
          <div className="st-kpi-footer">
            <span>Period: {selectedPeriodType === 'yearly' ? selectedYear : `${MONTH_NAMES[selectedMonth - 1]} ${selectedYear}`}</span>
          </div>
        </div>

        <div className="st-kpi-card">
          <div className="st-kpi-header">
            <span className="st-kpi-label">Actual Revenue</span>
            <div className="st-kpi-icon-wrap" style={{ background: '#f0fdf4', color: '#16a34a' }}>
              <TrendingUp size={20} />
            </div>
          </div>
          <div className="st-kpi-val" style={{ color: '#16a34a' }}>{formatINR(totalActual)}</div>
          <div className="st-kpi-footer">
            <span>Confirmed billing invoices only</span>
          </div>
        </div>

        <div className="st-kpi-card">
          <div className="st-kpi-header">
            <span className="st-kpi-label">Remaining Target</span>
            <div className="st-kpi-icon-wrap" style={{ background: '#fff7ed', color: '#ea580c' }}>
              <Clock size={20} />
            </div>
          </div>
          <div className="st-kpi-val" style={{ color: totalRemaining > 0 ? '#ea580c' : '#16a34a' }}>
            {formatINR(totalRemaining)}
          </div>
          <div className="st-kpi-footer">
            <span>MAX(Target - Revenue, 0)</span>
          </div>
        </div>

        <div className="st-kpi-card">
          <div className="st-kpi-header">
            <span className="st-kpi-label">Overall Achievement</span>
            <div className="st-kpi-icon-wrap" style={{ background: '#faf5ff', color: '#9333ea' }}>
              <Award size={20} />
            </div>
          </div>
          <div className="st-kpi-val" style={{ color: Number(overallAchievement) >= 100 ? '#16a34a' : '#2563eb' }}>
            {overallAchievement}%
          </div>
          <div className="st-progress-track">
            <div
              className="st-progress-fill"
              style={{
                width: `${Math.min(100, Number(overallAchievement))}%`,
                background: Number(overallAchievement) >= 100 ? '#16a34a' : '#2563eb'
              }}
            />
          </div>
        </div>
      </div>

      {/* Sub-Tabs: Achievement Table vs Target List */}
      <div className="st-subtab-bar">
        <button
          type="button"
          className={`st-subtab-btn ${activeSubTab === 'achievements' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('achievements')}
        >
          <Award size={15} />
          <span>Employee Achievement Leaderboard ({achievements.length})</span>
        </button>

        {isAdmin && (
          <button
            type="button"
            className={`st-subtab-btn ${activeSubTab === 'manage_targets' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('manage_targets')}
          >
            <Target size={15} />
            <span>Assigned Target History & Admin Editor ({targetsList.length})</span>
          </button>
        )}
      </div>

      {/* Main Content Area */}
      {activeSubTab === 'achievements' && (
        <div className="st-card">
          <div className="st-card-header">
            <div>
              <h2 className="st-card-title">Employee Achievement Summary</h2>
              <p className="st-card-subtitle">
                Revenue comes strictly from confirmed eligible Tax Invoices attributed to that salesperson.
              </p>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="st-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Department</th>
                  <th style={{ textAlign: 'right' }}>Target</th>
                  <th style={{ textAlign: 'right' }}>Actual Revenue</th>
                  <th style={{ textAlign: 'right' }}>Remaining</th>
                  <th style={{ textAlign: 'center' }}>Achievement</th>
                  <th>Invoices</th>
                  {isAdmin && <th style={{ textAlign: 'center' }}>Action</th>}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={isAdmin ? 8 : 7} style={{ textAlign: 'center', padding: '36px', color: '#64748b' }}>
                      Loading employee achievement figures...
                    </td>
                  </tr>
                ) : achievements.length === 0 ? (
                  <tr>
                    <td colSpan={isAdmin ? 8 : 7} style={{ textAlign: 'center', padding: '36px', color: '#64748b' }}>
                      No active sales personnel records found for the selected period.
                    </td>
                  </tr>
                ) : (
                  achievements.map((row) => {
                    const isCompleted = row.achievement_percentage >= 100;
                    return (
                      <tr key={row.employee_id}>
                        <td>
                          <div className="st-emp-cell">
                            <div className="st-emp-avatar">
                              {row.employee_name ? row.employee_name[0].toUpperCase() : 'E'}
                            </div>
                            <span className="st-emp-name">{row.employee_name}</span>
                          </div>
                        </td>
                        <td>
                          <span className="st-dept-badge">{row.department || 'Sales'}</span>
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 600 }}>
                          {formatINR(row.assigned_target)}
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 700, color: '#16a34a' }}>
                          {formatINR(row.actual_revenue)}
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 600, color: row.remaining_target > 0 ? '#ea580c' : '#64748b' }}>
                          {formatINR(row.remaining_target)}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <div className="st-achieve-cell">
                            <span
                              className={`st-achieve-badge ${isCompleted ? 'badge-won' : (row.achievement_percentage >= 50 ? 'badge-mid' : 'badge-low')}`}
                            >
                              {row.achievement_percentage}%
                            </span>
                            <div className="st-mini-track">
                              <div
                                className="st-mini-fill"
                                style={{
                                  width: `${Math.min(100, row.achievement_percentage)}%`,
                                  background: isCompleted ? '#16a34a' : (row.achievement_percentage >= 50 ? '#2563eb' : '#ea580c')
                                }}
                              />
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="st-invoices-count">{row.confirmed_invoices_count} inv</span>
                        </td>
                        {isAdmin && (
                          <td style={{ textAlign: 'center' }}>
                            <button
                              type="button"
                              className="st-btn-edit"
                              onClick={() => handleOpenAddModal(row.employee_id)}
                              title="Set or update target"
                            >
                              <Edit2 size={13} />
                              <span>Set Target</span>
                            </button>
                          </td>
                        )}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Target History & Admin Management Table */}
      {activeSubTab === 'manage_targets' && isAdmin && (
        <div className="st-card">
          <div className="st-card-header">
            <div>
              <h2 className="st-card-title">Assigned Targets History</h2>
              <p className="st-card-subtitle">
                Manage, edit, and audit employee targets across months and years.
              </p>
            </div>
            <button
              type="button"
              className="st-btn-primary"
              onClick={() => handleOpenAddModal()}
            >
              <Plus size={15} />
              <span>New Target</span>
            </button>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="st-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Employee</th>
                  <th>Department</th>
                  <th>Period Type</th>
                  <th>Period</th>
                  <th style={{ textAlign: 'right' }}>Target Amount</th>
                  <th>Created At</th>
                  <th style={{ textAlign: 'center' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {targetsList.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', padding: '36px', color: '#64748b' }}>
                      No targets assigned yet for {selectedYear}. Click "Assign Target" to create one.
                    </td>
                  </tr>
                ) : (
                  targetsList.map((t, idx) => (
                    <tr key={t.id}>
                      <td style={{ color: '#94a3b8' }}>{idx + 1}</td>
                      <td>
                        <strong style={{ color: '#0f172a' }}>{t.employee_name || `Employee #${t.employee_id}`}</strong>
                      </td>
                      <td>
                        <span className="st-dept-badge">{t.employee_department || 'Sales'}</span>
                      </td>
                      <td>
                        <span style={{ textTransform: 'capitalize' }}>{t.period_type}</span>
                      </td>
                      <td>
                        {t.period_type === 'yearly'
                          ? t.period_year
                          : `${MONTH_NAMES[(t.period_month || 1) - 1]} ${t.period_year}`}
                      </td>
                      <td style={{ textAlign: 'right', fontWeight: 700, color: '#2563eb' }}>
                        {formatINR(t.target_amount)}
                      </td>
                      <td style={{ color: '#64748b', fontSize: '0.78rem' }}>
                        {new Date(t.created_at).toLocaleDateString()}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <div style={{ display: 'inline-flex', gap: '8px' }}>
                          <button
                            type="button"
                            className="st-action-icon"
                            onClick={() => handleOpenEditModal(t)}
                            title="Edit target amount"
                          >
                            <Edit2 size={14} />
                          </button>
                          <button
                            type="button"
                            className="st-action-icon delete"
                            onClick={() => handleDeleteTarget(t.id)}
                            title="Delete target"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Target Create / Edit Modal */}
      {showModal && (
        <div className="st-modal-overlay" onClick={() => setShowModal(false)}>
          <div className="st-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="st-modal-header">
              <h3>{editingTargetId ? 'Edit Sales Target' : 'Assign Sales Target'}</h3>
              <button
                type="button"
                className="st-modal-close"
                onClick={() => setShowModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveTarget} className="st-modal-form">
              {modalError && (
                <div className="st-modal-alert">
                  <AlertCircle size={16} />
                  <span>{modalError}</span>
                </div>
              )}

              {/* Employee Selector */}
              <div className="st-form-group">
                <label>Employee / Salesperson</label>
                <select
                  value={formEmpId}
                  onChange={(e) => setFormEmpId(e.target.value)}
                  disabled={Boolean(editingTargetId)}
                  className="st-form-input"
                  required
                >
                  {employees.map(emp => (
                    <option key={emp.id} value={emp.id}>
                      {emp.name} ({emp.department || 'Sales'})
                    </option>
                  ))}
                </select>
              </div>

              {/* Period Type */}
              <div className="st-form-group">
                <label>Period Type</label>
                <select
                  value={formPeriodType}
                  onChange={(e) => setFormPeriodType(e.target.value)}
                  disabled={Boolean(editingTargetId)}
                  className="st-form-input"
                  required
                >
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="yearly">Yearly</option>
                </select>
              </div>

              {/* Month Selection */}
              {formPeriodType !== 'yearly' && (
                <div className="st-form-group">
                  <label>Target Month</label>
                  <select
                    value={formMonth}
                    onChange={(e) => setFormMonth(Number(e.target.value))}
                    disabled={Boolean(editingTargetId)}
                    className="st-form-input"
                    required
                  >
                    {MONTH_NAMES.map((name, idx) => (
                      <option key={idx + 1} value={idx + 1}>
                        {name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Year Selection */}
              <div className="st-form-group">
                <label>Target Year</label>
                <select
                  value={formYear}
                  onChange={(e) => setFormYear(Number(e.target.value))}
                  disabled={Boolean(editingTargetId)}
                  className="st-form-input"
                  required
                >
                  {[2024, 2025, 2026, 2027].map(yr => (
                    <option key={yr} value={yr}>{yr}</option>
                  ))}
                </select>
              </div>

              {/* Target Amount */}
              <div className="st-form-group">
                <label>Target Amount (in INR ₹)</label>
                <div className="st-input-currency-wrapper">
                  <span className="st-currency-symbol">₹</span>
                  <input
                    type="number"
                    step="1000"
                    min="0"
                    placeholder="e.g. 200000"
                    value={formAmount}
                    onChange={(e) => setFormAmount(e.target.value)}
                    className="st-form-input st-input-with-symbol"
                    required
                  />
                </div>
              </div>

              <div className="st-modal-actions">
                <button
                  type="button"
                  className="st-btn-secondary"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="st-btn-primary"
                  disabled={submitting}
                >
                  {submitting ? 'Saving...' : (editingTargetId ? 'Update Target' : 'Save Target')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default SalesTargetsPage;
