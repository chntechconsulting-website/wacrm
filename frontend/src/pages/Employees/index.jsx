import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { 
  Users, 
  Plus, 
  Search, 
  Edit2, 
  UserX, 
  UserCheck, 
  KeyRound, 
  X, 
  AlertCircle,
  Check,
  Shield,
  Clock,
  History,
  User,
  Activity,
  ShieldCheck,
  ArrowRightLeft,
  Briefcase,
  Building2,
  ChevronDown,
  Info,
  Download
} from 'lucide-react';
import RoleManagementMatrix from './RoleManagementMatrix';

const DEPARTMENTS = [
  { value: 'SALES', label: 'Sales' },
  { value: 'SUPPORT', label: 'Support' },
  { value: 'FINANCE', label: 'Finance' },
  { value: 'ADMINISTRATION', label: 'Administration' }
];

const STANDARD_ROLES = [
  { value: 'SALES_EXECUTIVE', label: 'Sales Executive', department: 'SALES', managerReq: 'Required: Active Sales Manager' },
  { value: 'SALES_MANAGER', label: 'Sales Manager', department: 'SALES', managerReq: 'Required: Active Administrator' },
  { value: 'SUPPORT_EXECUTIVE', label: 'Support Executive', department: 'SUPPORT', managerReq: 'Required: Active Support Manager' },
  { value: 'SUPPORT_MANAGER', label: 'Support Manager', department: 'SUPPORT', managerReq: 'Required: Active Administrator' },
  { value: 'FINANCE', label: 'Finance', department: 'FINANCE', managerReq: 'Required: Active Administrator' },
  { value: 'ADMIN', label: 'Admin', department: 'ADMINISTRATION', managerReq: 'None (Top of hierarchy)' }
];

const Employees = () => {
  const { user: currentUser } = useAuth();
  const [activeTab, setActiveTab] = useState('users'); // 'users', 'roles', or 'audit'

  // Users State
  const [usersList, setUsersList] = useState([]);
  const [eligibleManagers, setEligibleManagers] = useState([]);
  const [loadingEligibleManagers, setLoadingEligibleManagers] = useState(false);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('ALL');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Audit Logs State
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditLoading, setAuditLoading] = useState(false);

  // Modals state
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showResetPwdModal, setShowResetPwdModal] = useState(false);
  const [showReassignModal, setShowReassignModal] = useState(false);

  // Form State
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    username: '',
    password: '',
    role: 'SALES_EXECUTIVE',
    department: 'SALES',
    reporting_manager_id: '',
    status: 'ACTIVE'
  });

  const [resetPwdData, setResetPwdData] = useState({
    userId: null,
    username: '',
    newPassword: ''
  });

  // Reassign reports modal state
  const [reassignData, setReassignData] = useState({
    sourceUser: null,
    newManagerId: '',
    availableTargetManagers: []
  });

  const [selectedUser, setSelectedUser] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const res = await API.get('/users');
      setUsersList(res.data);
    } catch (err) {
      console.error(err);
      setError('Failed to load user management list.');
    } finally {
      setLoading(false);
    }
  };

  const fetchEligibleManagers = async (role, excludeUserId = null) => {
    if (!role || role === 'ADMIN') {
      setEligibleManagers([]);
      return;
    }
    try {
      setLoadingEligibleManagers(true);
      const params = { role };
      if (excludeUserId) {
        params.exclude_user_id = excludeUserId;
      }
      const res = await API.get('/users/eligible-managers', { params });
      setEligibleManagers(res.data || []);
    } catch (err) {
      console.error('Failed to load eligible managers', err);
      setEligibleManagers([]);
    } finally {
      setLoadingEligibleManagers(false);
    }
  };

  const fetchAuditLogs = async () => {
    try {
      setAuditLoading(true);
      const res = await API.get('/users/audit-logs');
      setAuditLogs(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setAuditLoading(false);
    }
  };

  // Roles State
  const [availableRoles, setAvailableRoles] = useState([]);

  const fetchAvailableRoles = async () => {
    try {
      const res = await API.get('/roles');
      setAvailableRoles(res.data);
    } catch (err) {
      console.error('Failed to load roles catalog', err);
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchAvailableRoles();
  }, []);

  useEffect(() => {
    if (activeTab === 'audit') {
      fetchAuditLogs();
    }
  }, [activeTab]);

  const handleDepartmentChangeInForm = (newDept, currentUserId = null) => {
    let defaultRole = 'SALES_EXECUTIVE';
    if (newDept === 'SALES') defaultRole = 'SALES_EXECUTIVE';
    else if (newDept === 'SUPPORT') defaultRole = 'SUPPORT_EXECUTIVE';
    else if (newDept === 'FINANCE') defaultRole = 'FINANCE';
    else if (newDept === 'ADMINISTRATION') defaultRole = 'ADMIN';

    // Check if current role is already valid for new department
    const rolesInDept = STANDARD_ROLES.filter(r => r.department === newDept).map(r => r.value);
    const targetRole = rolesInDept.includes(formData.role) ? formData.role : defaultRole;

    setFormData(prev => ({
      ...prev,
      department: newDept,
      role: targetRole,
      reporting_manager_id: targetRole === 'ADMIN' ? '' : prev.reporting_manager_id
    }));

    fetchEligibleManagers(targetRole, currentUserId);
  };

  const handleRoleChangeInForm = (newRole, currentUserId = null) => {
    let dept = 'SALES';
    if (newRole === 'ADMIN') dept = 'ADMINISTRATION';
    else if (newRole === 'SALES_MANAGER' || newRole === 'SALES_EXECUTIVE' || newRole === 'SALES' || newRole === 'MANAGER') dept = 'SALES';
    else if (newRole === 'SUPPORT_MANAGER' || newRole === 'SUPPORT_EXECUTIVE' || newRole === 'SUPPORT') dept = 'SUPPORT';
    else if (newRole === 'FINANCE') dept = 'FINANCE';

    setFormData(prev => ({
      ...prev,
      role: newRole,
      department: dept,
      reporting_manager_id: newRole === 'ADMIN' ? '' : prev.reporting_manager_id
    }));

    fetchEligibleManagers(newRole, currentUserId);
  };

  const handleOpenAddModal = () => {
    setFormData({
      name: '',
      phone: '',
      username: '',
      email: '',
      password: '',
      department: 'SALES',
      role: 'SALES_EXECUTIVE',
      reporting_manager_id: '',
      status: 'ACTIVE'
    });
    setError('');
    fetchEligibleManagers('SALES_EXECUTIVE', null);
    setShowAddModal(true);
  };

  const handleOpenEditModal = (usr) => {
    setSelectedUser(usr);
    const userRole = usr.role || 'SALES_EXECUTIVE';
    let userDept = usr.department || 'SALES';
    if (userDept === 'ADMIN') userDept = 'ADMINISTRATION';

    setFormData({
      name: usr.name,
      phone: usr.phone || '',
      username: usr.username,
      email: usr.email,
      password: '',
      department: userDept,
      role: userRole,
      reporting_manager_id: usr.reporting_manager_id ? String(usr.reporting_manager_id) : '',
      status: usr.status
    });
    setError('');
    fetchEligibleManagers(userRole, usr.id);
    setShowEditModal(true);
  };

  const handleOpenResetPwdModal = (usr) => {
    setResetPwdData({
      userId: usr.id,
      username: usr.username,
      newPassword: ''
    });
    setError('');
    setShowResetPwdModal(true);
  };

  const handleOpenReassignModal = (usr) => {
    // Filter managers who can accept the reports of usr
    const isSales = (usr.role || '').includes('SALES') || usr.department === 'SALES';
    const isSupport = (usr.role || '').includes('SUPPORT') || usr.department === 'SUPPORT';
    
    const candidates = usersList.filter(u => {
      if (u.id === usr.id) return false;
      if (!u.is_active) return false;
      if (isSales && (u.role === 'SALES_MANAGER' || u.role === 'ADMIN')) return true;
      if (isSupport && (u.role === 'SUPPORT_MANAGER' || u.role === 'ADMIN')) return true;
      if (u.role === 'ADMIN') return true;
      return false;
    });

    setReassignData({
      sourceUser: usr,
      newManagerId: candidates.length > 0 ? String(candidates[0].id) : '',
      availableTargetManagers: candidates
    });
    setError('');
    setShowReassignModal(true);
  };

  const handleReassignReportsSubmit = async (e) => {
    e.preventDefault();
    if (!reassignData.newManagerId) {
      setError('Please select a replacement manager.');
      return;
    }
    try {
      setSubmitting(true);
      setError('');
      const res = await API.post(`/users/${reassignData.sourceUser.id}/reassign-reports`, {
        new_manager_id: parseInt(reassignData.newManagerId, 10)
      });
      setSuccess(res.data.message || 'Direct reports reassigned successfully.');
      setShowReassignModal(false);
      fetchUsers();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to reassign direct reports.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!formData.name || !formData.email || !formData.username || !formData.password) {
      setError('Name, email, username, and password are required.');
      return;
    }

    if (formData.role !== 'ADMIN' && !formData.reporting_manager_id) {
      setError(`Reporting manager is required for role ${formData.role}.`);
      return;
    }

    try {
      setSubmitting(true);
      const payload = {
        name: formData.name.trim(),
        email: formData.email.trim(),
        phone: formData.phone?.trim() || null,
        username: formData.username.trim(),
        password: formData.password,
        role: formData.role,
        department: formData.department,
        reporting_manager_id: formData.role === 'ADMIN' ? null : parseInt(formData.reporting_manager_id, 10),
        status: formData.status
      };

      await API.post('/users', payload);
      setSuccess(`User '${formData.username}' created successfully!`);
      setShowAddModal(false);
      fetchUsers();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to create user account.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateUser = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (formData.role !== 'ADMIN' && !formData.reporting_manager_id) {
      setError(`Reporting manager is required for role ${formData.role}.`);
      return;
    }

    try {
      setSubmitting(true);
      const updatePayload = {
        name: formData.name.trim(),
        email: formData.email.trim(),
        phone: formData.phone?.trim() || null,
        role: formData.role,
        department: formData.department,
        reporting_manager_id: formData.role === 'ADMIN' ? null : parseInt(formData.reporting_manager_id, 10),
        status: formData.status
      };

      await API.put(`/users/${selectedUser.id}`, updatePayload);
      setSuccess(`User #${selectedUser.id} (${formData.name}) updated successfully!`);
      setShowEditModal(false);
      fetchUsers();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to update user account.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetPasswordSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!resetPwdData.newPassword) {
      setError('New password is required.');
      return;
    }

    try {
      setSubmitting(true);
      await API.post(`/users/${resetPwdData.userId}/reset-password`, {
        new_password: resetPwdData.newPassword
      });
      setSuccess(`Password for '${resetPwdData.username}' reset successfully!`);
      setShowResetPwdModal(false);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to reset password.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (usr) => {
    // If activating, no report check needed
    if (!usr.is_active) {
      try {
        const res = await API.post(`/users/${usr.id}/toggle-status`);
        setSuccess(`User '${usr.username}' activated successfully.`);
        fetchUsers();
      } catch (err) {
        console.error(err);
        setError(err.response?.data?.detail || 'Failed to activate user account.');
      }
      return;
    }

    // If deactivating and user has active reports, direct to reassign modal
    if (usr.direct_reports_count > 0) {
      setError(`Cannot deactivate ${usr.name}: They have ${usr.direct_reports_count} direct report(s). Please reassign reports first.`);
      handleOpenReassignModal(usr);
      return;
    }

    try {
      const res = await API.post(`/users/${usr.id}/toggle-status`);
      setSuccess(`User '${usr.username}' status changed to ${res.data.status}`);
      fetchUsers();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to update user status.');
    }
  };

  const getDepartmentBadgeStyle = (deptStr) => {
    const d = (deptStr || '').toUpperCase();
    if (d === 'SALES') {
      return { bg: 'rgba(37, 99, 235, 0.1)', color: '#2563eb', border: '1px solid rgba(37, 99, 235, 0.25)', label: 'Sales' };
    }
    if (d === 'SUPPORT') {
      return { bg: 'rgba(13, 148, 136, 0.1)', color: '#0d9488', border: '1px solid rgba(13, 148, 136, 0.25)', label: 'Support' };
    }
    if (d === 'FINANCE') {
      return { bg: 'rgba(217, 119, 6, 0.1)', color: '#d97706', border: '1px solid rgba(217, 119, 6, 0.25)', label: 'Finance' };
    }
    if (d === 'ADMINISTRATION' || d === 'ADMIN') {
      return { bg: 'rgba(124, 58, 237, 0.1)', color: '#7c3aed', border: '1px solid rgba(124, 58, 237, 0.25)', label: 'Administration' };
    }
    return { bg: 'rgba(100, 116, 139, 0.1)', color: '#64748b', border: '1px solid rgba(100, 116, 139, 0.25)', label: deptStr || 'Unassigned' };
  };

  const getRoleBadgeStyle = (roleStr) => {
    const r = (roleStr || '').toUpperCase();
    if (r === 'ADMIN') {
      return { bg: 'rgba(239, 68, 68, 0.12)', color: '#dc2626', border: '1px solid rgba(239, 68, 68, 0.25)', label: 'Admin' };
    }
    if (r === 'SALES_MANAGER' || r === 'MANAGER') {
      return { bg: 'rgba(37, 99, 235, 0.12)', color: '#2563eb', border: '1px solid rgba(37, 99, 235, 0.25)', label: 'Sales Manager' };
    }
    if (r === 'SALES_EXECUTIVE' || r === 'SALES' || r === 'EMPLOYEE') {
      return { bg: 'rgba(2, 132, 199, 0.12)', color: '#0284c7', border: '1px solid rgba(2, 132, 199, 0.25)', label: 'Sales Executive' };
    }
    if (r === 'SUPPORT_MANAGER') {
      return { bg: 'rgba(13, 148, 136, 0.12)', color: '#0d9488', border: '1px solid rgba(13, 148, 136, 0.25)', label: 'Support Manager' };
    }
    if (r === 'SUPPORT_EXECUTIVE' || r === 'SUPPORT') {
      return { bg: 'rgba(5, 150, 105, 0.12)', color: '#059669', border: '1px solid rgba(5, 150, 105, 0.25)', label: 'Support Executive' };
    }
    if (r === 'FINANCE') {
      return { bg: 'rgba(217, 119, 6, 0.12)', color: '#d97706', border: '1px solid rgba(217, 119, 6, 0.25)', label: 'Finance' };
    }
    return { bg: 'rgba(100, 116, 139, 0.12)', color: '#64748b', border: '1px solid rgba(100, 116, 139, 0.25)', label: roleStr };
  };

  const getRoleRequirementText = (role) => {
    if (role === 'ADMIN') return 'Not required for Administrator';
    if (role === 'SALES_MANAGER') return 'Required: Active Administrator';
    if (role === 'SALES_EXECUTIVE') return 'Required: Active Sales Manager';
    if (role === 'SUPPORT_MANAGER') return 'Required: Active Administrator';
    if (role === 'SUPPORT_EXECUTIVE') return 'Required: Active Support Manager';
    if (role === 'FINANCE') return 'Required: Active Administrator';
    return 'Required: Active Manager';
  };

  const filteredUsers = usersList.filter(usr => {
    const matchesSearch = 
      usr.name?.toLowerCase().includes(search.toLowerCase()) ||
      usr.email?.toLowerCase().includes(search.toLowerCase()) ||
      usr.username?.toLowerCase().includes(search.toLowerCase()) ||
      usr.role?.toLowerCase().includes(search.toLowerCase()) ||
      usr.department?.toLowerCase().includes(search.toLowerCase()) ||
      usr.reporting_manager_name?.toLowerCase().includes(search.toLowerCase());

    const matchesDept = deptFilter === 'ALL' || 
      (usr.department || '').toUpperCase() === deptFilter.toUpperCase() ||
      (deptFilter === 'ADMINISTRATION' && (usr.department === 'ADMIN' || usr.department === 'ADMINISTRATION'));

    const matchesRole = roleFilter === 'ALL' || usr.role === roleFilter;

    return matchesSearch && matchesDept && matchesRole;
  });

  const handleExportUsersCSV = () => {
    const headers = ['ID', 'Full Name', 'Username', 'Email', 'Phone', 'Department', 'Role', 'Reporting Manager', 'Status'];
    const rows = filteredUsers.map(u => [
      u.id,
      `"${(u.name || '').replace(/"/g, '""')}"`,
      `"${(u.username || '').replace(/"/g, '""')}"`,
      `"${(u.email || '').replace(/"/g, '""')}"`,
      `"${(u.phone || '').replace(/"/g, '""')}"`,
      `"${(u.department || '').replace(/"/g, '""')}"`,
      `"${(u.role || '').replace(/"/g, '""')}"`,
      `"${(u.reporting_manager_name || '').replace(/"/g, '""')}"`,
      `"${(u.status || '').replace(/"/g, '""')}"`
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `wacrm_users_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const formatDate = (dtStr) => {
    if (!dtStr) return 'Never';
    try {
      return new Date(dtStr).toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch {
      return dtStr;
    }
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 className="page-title" style={{ fontSize: '1.6rem', fontWeight: '800', margin: 0, color: '#0f172a', letterSpacing: '-0.02em' }}>
            Users & Reporting Hierarchy
          </h1>
          <p className="page-subtitle" style={{ color: '#64748b', marginTop: '4px', fontSize: '0.9rem' }}>
            Manage CRM employees, strict team-based reporting relationships, RBAC roles, and security audit logs.
          </p>
        </div>
        {currentUser?.role === 'ADMIN' && activeTab === 'users' && (
          <div className="header-actions">
            <button
              className="btn btn-primary"
              onClick={handleOpenAddModal}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: '#0f766e',
                borderColor: '#0f766e',
                borderRadius: '8px',
                padding: '9px 16px',
                fontWeight: '600'
              }}
            >
              <Plus size={18} /> Add User Account
            </button>
          </div>
        )}
      </div>

      {/* Modern Segmented Navigation Tabs */}
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        backgroundColor: '#f1f5f9',
        padding: '5px',
        borderRadius: '12px',
        marginBottom: '22px',
        border: '1px solid #e2e8f0'
      }}>
        <button
          type="button"
          onClick={() => setActiveTab('users')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 18px',
            borderRadius: '9px',
            border: 'none',
            backgroundColor: activeTab === 'users' ? '#0f766e' : 'transparent',
            color: activeTab === 'users' ? '#ffffff' : '#64748b',
            fontWeight: activeTab === 'users' ? '700' : '600',
            fontSize: '0.88rem',
            cursor: 'pointer',
            boxShadow: activeTab === 'users' ? '0 1px 3px rgba(15, 118, 110, 0.25)' : 'none',
            transition: 'all 0.15s ease'
          }}
        >
          <Users size={17} /> User Accounts & Hierarchy
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('roles')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 18px',
            borderRadius: '9px',
            border: 'none',
            backgroundColor: activeTab === 'roles' ? '#0f766e' : 'transparent',
            color: activeTab === 'roles' ? '#ffffff' : '#64748b',
            fontWeight: activeTab === 'roles' ? '700' : '600',
            fontSize: '0.88rem',
            cursor: 'pointer',
            boxShadow: activeTab === 'roles' ? '0 1px 3px rgba(15, 118, 110, 0.25)' : 'none',
            transition: 'all 0.15s ease'
          }}
        >
          <ShieldCheck size={17} /> Roles & Permissions Matrix
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('audit')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 18px',
            borderRadius: '9px',
            border: 'none',
            backgroundColor: activeTab === 'audit' ? '#0f766e' : 'transparent',
            color: activeTab === 'audit' ? '#ffffff' : '#64748b',
            fontWeight: activeTab === 'audit' ? '700' : '600',
            fontSize: '0.88rem',
            cursor: 'pointer',
            boxShadow: activeTab === 'audit' ? '0 1px 3px rgba(15, 118, 110, 0.25)' : 'none',
            transition: 'all 0.15s ease'
          }}
        >
          <History size={17} /> Security Audit Logs
        </button>
      </div>

      {error && (
        <div className="alert alert-error mb-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#dc2626', border: '1px solid rgba(239, 68, 68, 0.25)', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <AlertCircle size={18} /> <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="alert alert-success mb-4" style={{ backgroundColor: 'rgba(16, 185, 129, 0.1)', color: '#059669', border: '1px solid rgba(16, 185, 129, 0.25)', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Check size={18} /> <span>{success}</span>
        </div>
      )}

      {/* USER ACCOUNTS TAB */}
      {activeTab === 'users' && (
        <div className="content-card">
          <div className="table-toolbar" style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="search-box" style={{ position: 'relative', width: '100%', maxWidth: '340px' }}>
              <Search size={18} className="search-icon" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
              <input 
                type="text" 
                placeholder="Search by name, email, department, manager..." 
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ width: '100%', padding: '9px 12px 9px 38px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
              />
            </div>

            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <select
                value={deptFilter}
                onChange={(e) => setDeptFilter(e.target.value)}
                style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.85rem', fontWeight: '500' }}
              >
                <option value="ALL">All Departments</option>
                {DEPARTMENTS.map(d => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>

              <select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.85rem', fontWeight: '500' }}
              >
                <option value="ALL">All Roles</option>
                {STANDARD_ROLES.map(r => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>

              <button
                type="button"
                onClick={handleExportUsersCSV}
                className="btn btn-outline"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  borderRadius: '8px',
                  fontSize: '0.85rem',
                  fontWeight: '600',
                  color: '#334155',
                  borderColor: '#cbd5e1'
                }}
                title="Export filtered users to CSV"
              >
                <Download size={15} /> Export CSV
              </button>
            </div>
          </div>

          <div className="table-responsive">
            <table className="custom-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left', backgroundColor: '#f8fafc' }}>
                  <th style={{ padding: '12px 14px', fontSize: '0.8rem', color: '#64748b', fontWeight: '700' }}>ID</th>
                  <th style={{ padding: '12px 14px', fontSize: '0.8rem', color: '#64748b', fontWeight: '700' }}>EMPLOYEE</th>
                  <th style={{ padding: '12px 14px', fontSize: '0.8rem', color: '#64748b', fontWeight: '700' }}>DEPARTMENT</th>
                  <th style={{ padding: '12px 14px', fontSize: '0.8rem', color: '#64748b', fontWeight: '700' }}>ROLE</th>
                  <th style={{ padding: '12px 14px', fontSize: '0.8rem', color: '#64748b', fontWeight: '700' }}>REPORTING MANAGER</th>
                  <th style={{ padding: '12px 14px', fontSize: '0.8rem', color: '#64748b', fontWeight: '700' }}>DIRECT REPORTS</th>
                  <th style={{ padding: '12px 14px', fontSize: '0.8rem', color: '#64748b', fontWeight: '700' }}>STATUS</th>
                  {currentUser?.role === 'ADMIN' && <th style={{ padding: '12px 14px', fontSize: '0.8rem', color: '#64748b', fontWeight: '700', textAlign: 'right' }}>ACTIONS</th>}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan="8" style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>
                      Loading users & reporting hierarchy...
                    </td>
                  </tr>
                ) : filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan="8" style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>
                      No user accounts found matching criteria.
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map((usr) => {
                    const deptBadge = getDepartmentBadgeStyle(usr.department);
                    const roleBadge = getRoleBadgeStyle(usr.role);
                    return (
                      <tr key={usr.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '12px 14px', color: '#64748b', fontSize: '0.85rem' }}>#{usr.id}</td>
                        <td style={{ padding: '12px 14px' }}>
                          <div>
                            <strong style={{ color: '#0f172a', fontSize: '0.92rem' }}>{usr.name}</strong>
                            <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '2px' }}>
                              {usr.email} &bull; <code style={{ fontSize: '0.75rem', backgroundColor: '#f1f5f9', padding: '1px 5px', borderRadius: '4px' }}>@{usr.username}</code>
                            </div>
                          </div>
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <span style={{
                            padding: '4px 10px',
                            borderRadius: '12px',
                            fontSize: '0.75rem',
                            fontWeight: '700',
                            backgroundColor: deptBadge.bg,
                            color: deptBadge.color,
                            border: deptBadge.border,
                            display: 'inline-block'
                          }}>
                            {deptBadge.label}
                          </span>
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <span style={{
                            padding: '4px 10px',
                            borderRadius: '12px',
                            fontSize: '0.75rem',
                            fontWeight: '700',
                            backgroundColor: roleBadge.bg,
                            color: roleBadge.color,
                            border: roleBadge.border,
                            display: 'inline-block'
                          }}>
                            {roleBadge.label}
                          </span>
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          {usr.reporting_manager_name ? (
                            <div>
                              <strong style={{ fontSize: '0.85rem', color: '#1e293b' }}>{usr.reporting_manager_name}</strong>
                              {usr.reporting_manager_role && (
                                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                                  ({getRoleBadgeStyle(usr.reporting_manager_role).label})
                                </div>
                              )}
                            </div>
                          ) : (
                            <span style={{ color: '#94a3b8', fontSize: '0.85rem', fontStyle: 'italic' }}>
                              {usr.role === 'ADMIN' ? '— None (Top Level) —' : '— Not Assigned —'}
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          {usr.direct_reports_count > 0 ? (
                            <span style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '3px 8px',
                              borderRadius: '10px',
                              fontSize: '0.75rem',
                              fontWeight: '700',
                              backgroundColor: '#ecfdf5',
                              color: '#059669',
                              border: '1px solid #a7f3d0'
                            }}>
                              <Users size={12} /> {usr.direct_reports_count} direct report{usr.direct_reports_count > 1 ? 's' : ''}
                            </span>
                          ) : (
                            <span style={{ color: '#cbd5e1', fontSize: '0.8rem' }}>0</span>
                          )}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <span style={{
                            padding: '4px 10px',
                            borderRadius: '12px',
                            fontSize: '0.75rem',
                            fontWeight: '600',
                            backgroundColor: usr.status === 'ACTIVE' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                            color: usr.status === 'ACTIVE' ? '#059669' : '#dc2626',
                            border: usr.status === 'ACTIVE' ? '1px solid rgba(16, 185, 129, 0.25)' : '1px solid rgba(239, 68, 68, 0.25)'
                          }}>
                            {usr.status}
                          </span>
                        </td>
                        {currentUser?.role === 'ADMIN' && (
                          <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                            <div className="action-buttons" style={{ display: 'inline-flex', gap: '6px' }}>
                              <button 
                                className="btn btn-outline" 
                                style={{ padding: '5px 8px', borderRadius: '6px' }}
                                title="Edit User & Hierarchy"
                                onClick={() => handleOpenEditModal(usr)}
                              >
                                <Edit2 size={14} />
                              </button>
                              
                              {usr.direct_reports_count > 0 && (
                                <button 
                                  className="btn btn-outline" 
                                  style={{ padding: '5px 8px', borderRadius: '6px', color: '#2563eb', borderColor: '#bfdbfe' }}
                                  title={`Reassign ${usr.direct_reports_count} direct report(s)`}
                                  onClick={() => handleOpenReassignModal(usr)}
                                >
                                  <ArrowRightLeft size={14} />
                                </button>
                              )}

                              <button 
                                className="btn btn-outline" 
                                style={{ padding: '5px 8px', borderRadius: '6px', color: '#d97706', borderColor: '#fde68a' }}
                                title="Reset Password"
                                onClick={() => handleOpenResetPwdModal(usr)}
                              >
                                <KeyRound size={14} />
                              </button>
                              
                              <button 
                                className="btn btn-outline" 
                                style={{ 
                                  padding: '5px 8px', 
                                  borderRadius: '6px',
                                  color: usr.status === 'ACTIVE' ? '#dc2626' : '#059669',
                                  borderColor: usr.status === 'ACTIVE' ? '#fecaca' : '#a7f3d0'
                                }}
                                title={usr.status === 'ACTIVE' ? 'Deactivate Account' : 'Activate Account'}
                                onClick={() => handleToggleStatus(usr)}
                              >
                                {usr.status === 'ACTIVE' ? <UserX size={14} /> : <UserCheck size={14} />}
                              </button>
                            </div>
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

      {/* ROLES & PERMISSION MATRIX TAB */}
      {activeTab === 'roles' && (
        <RoleManagementMatrix onRoleCreatedOrUpdated={fetchAvailableRoles} />
      )}

      {/* AUDIT LOGS TAB */}
      {activeTab === 'audit' && (
        <div className="content-card">
          <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '700', margin: 0 }}>System Security & Audit Activity</h3>
            <button className="btn btn-outline" onClick={fetchAuditLogs} disabled={auditLoading}>
              Refresh Logs
            </button>
          </div>

          <div className="table-responsive">
            <table className="custom-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2e8f0', textAlign: 'left', backgroundColor: '#f8fafc' }}>
                  <th style={{ padding: '12px' }}>ID</th>
                  <th style={{ padding: '12px' }}>Timestamp</th>
                  <th style={{ padding: '12px' }}>User</th>
                  <th style={{ padding: '12px' }}>Action</th>
                  <th style={{ padding: '12px' }}>Details</th>
                  <th style={{ padding: '12px' }}>IP Address</th>
                </tr>
              </thead>
              <tbody>
                {auditLoading ? (
                  <tr>
                    <td colSpan="6" style={{ padding: '24px', textAlign: 'center', color: '#94a3b8' }}>
                      Loading audit logs...
                    </td>
                  </tr>
                ) : auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan="6" style={{ padding: '24px', textAlign: 'center', color: '#94a3b8' }}>
                      No audit history recorded yet.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '12px', color: '#64748b' }}>#{log.id}</td>
                      <td style={{ padding: '12px', fontSize: '0.85rem', color: '#64748b' }}>
                        {formatDate(log.created_at)}
                      </td>
                      <td style={{ padding: '12px' }}><strong>{log.username || 'System'}</strong></td>
                      <td style={{ padding: '12px' }}>
                        <span style={{
                          padding: '3px 8px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: '700',
                          backgroundColor: 'rgba(59, 130, 246, 0.1)', color: '#2563eb'
                        }}>
                          {log.action}
                        </span>
                      </td>
                      <td style={{ padding: '12px', fontSize: '0.88rem' }}>{log.details}</td>
                      <td style={{ padding: '12px', fontSize: '0.82rem', color: '#94a3b8' }}>{log.ip_address || '127.0.0.1'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ADD USER MODAL */}
      {showAddModal && (
        <div className="modal-backdrop" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.55)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            width: '100%', maxWidth: '540px', maxHeight: '90vh', overflowY: 'auto', padding: '28px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
          }}>
            <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: '800', margin: 0, color: '#0f172a' }}>Add New User Account</h3>
                <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#64748b' }}>Create user credentials with strictly validated reporting manager assignment.</p>
              </div>
              <button onClick={() => setShowAddModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateUser}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>Full Name *</label>
                  <input 
                    type="text" 
                    required 
                    placeholder="e.g. Ramesh Kumar" 
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                  />
                </div>

                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>Phone Number</label>
                  <input 
                    type="text" 
                    placeholder="+91 9876543210" 
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>Login Username *</label>
                  <input 
                    type="text" 
                    required 
                    placeholder="ramesh" 
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                  />
                </div>

                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>Email Address *</label>
                  <input 
                    type="email" 
                    required 
                    placeholder="ramesh@company.com" 
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                  />
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>Login Password *</label>
                <input 
                  type="password" 
                  required 
                  placeholder="Enter secure initial password" 
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                />
              </div>

              {/* 6. Department — NEW REQUIRED FIELD (Immediately before Role) */}
              <div className="form-group" style={{ marginBottom: '14px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', fontWeight: '700', fontSize: '0.85rem', color: '#0f766e' }}>
                  <Building2 size={15} /> Department *
                </label>
                <select 
                  required
                  value={formData.department} 
                  onChange={(e) => handleDepartmentChangeInForm(e.target.value, null)}
                  style={{ 
                    width: '100%', 
                    padding: '9px 12px', 
                    borderRadius: '6px', 
                    border: '2px solid #0d9488', 
                    backgroundColor: '#f0fdfa',
                    fontWeight: '600',
                    color: '#0f766e'
                  }}
                >
                  {DEPARTMENTS.map(d => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
                <span style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '3px', display: 'block' }}>
                  Select the business department. Compatible roles and managers will adjust automatically.
                </span>
              </div>

              {/* 7. Role */}
              <div className="form-group" style={{ marginBottom: '14px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>
                  <Shield size={15} /> Role *
                </label>
                <select 
                  value={formData.role} 
                  onChange={(e) => handleRoleChangeInForm(e.target.value, null)}
                  style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                >
                  {STANDARD_ROLES
                    .filter(r => !formData.department || r.department === formData.department)
                    .map(r => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                </select>
              </div>

              {/* Reporting Manager Assignment Field */}
              <div className="form-group" style={{ marginBottom: '16px', backgroundColor: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label style={{ fontWeight: '700', fontSize: '0.88rem', color: '#0f172a' }}>
                    Reporting Manager {formData.role === 'ADMIN' ? '(Optional/None)' : '*'}
                  </label>
                  <span style={{ fontSize: '0.75rem', color: '#0d9488', fontWeight: '600' }}>
                    {getRoleRequirementText(formData.role)}
                  </span>
                </div>

                {formData.role === 'ADMIN' ? (
                  <div style={{ padding: '10px 12px', backgroundColor: '#f1f5f9', borderRadius: '6px', fontSize: '0.85rem', color: '#64748b' }}>
                    <Info size={14} style={{ display: 'inline', marginRight: '6px' }} />
                    Administrator accounts sit at the root of the hierarchy and do not require a reporting manager.
                  </div>
                ) : (
                  <>
                    <select 
                      value={formData.reporting_manager_id} 
                      onChange={(e) => setFormData({ ...formData, reporting_manager_id: e.target.value })}
                      required={formData.role !== 'ADMIN'}
                      disabled={loadingEligibleManagers}
                      style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff' }}
                    >
                      <option value="">-- Select Reporting Manager --</option>
                      {eligibleManagers.map(m => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({getRoleBadgeStyle(m.role).label})
                        </option>
                      ))}
                    </select>
                    {eligibleManagers.length === 0 && !loadingEligibleManagers && (
                      <div style={{ marginTop: '6px', fontSize: '0.78rem', color: '#dc2626' }}>
                        No eligible active managers found for role '{formData.role}'. Please verify that an active manager exists.
                      </div>
                    )}
                  </>
                )}
              </div>

              <div className="form-group" style={{ marginBottom: '18px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>Initial Account Status</label>
                <select 
                  value={formData.status} 
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                >
                  <option value="ACTIVE">ACTIVE (Can login immediately)</option>
                  <option value="INACTIVE">INACTIVE (Login disabled)</option>
                </select>
              </div>

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowAddModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Creating User...' : 'Create User Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT USER MODAL */}
      {showEditModal && (
        <div className="modal-backdrop" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.55)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            width: '100%', maxWidth: '520px', maxHeight: '90vh', overflowY: 'auto', padding: '28px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
          }}>
            <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: '800', margin: 0, color: '#0f172a' }}>
                  Edit User #{selectedUser?.id} ({selectedUser?.username})
                </h3>
                <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#64748b' }}>
                  Update role, reporting manager assignment, and account status.
                </p>
              </div>
              <button onClick={() => setShowEditModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleUpdateUser}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>Full Name</label>
                  <input 
                    type="text" 
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                  />
                </div>

                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>Phone Number</label>
                  <input 
                    type="text" 
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                  />
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>Email Address</label>
                <input 
                  type="email" 
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                />
              </div>

              {/* Department — Immediately before Role */}
              <div className="form-group" style={{ marginBottom: '14px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', fontWeight: '700', fontSize: '0.85rem', color: '#0f766e' }}>
                  <Building2 size={15} /> Department *
                </label>
                <select 
                  required
                  value={formData.department} 
                  onChange={(e) => handleDepartmentChangeInForm(e.target.value, selectedUser?.id)}
                  style={{ 
                    width: '100%', 
                    padding: '9px 12px', 
                    borderRadius: '6px', 
                    border: '2px solid #0d9488', 
                    backgroundColor: '#f0fdfa',
                    fontWeight: '600',
                    color: '#0f766e'
                  }}
                >
                  {DEPARTMENTS.map(d => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
                <span style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '3px', display: 'block' }}>
                  Changing department updates role selection and manager assignment eligibility.
                </span>
              </div>

              {/* Role */}
              <div className="form-group" style={{ marginBottom: '14px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>
                  <Shield size={15} /> Role *
                </label>
                <select 
                  value={formData.role} 
                  onChange={(e) => handleRoleChangeInForm(e.target.value, selectedUser?.id)}
                  style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                >
                  {STANDARD_ROLES
                    .filter(r => !formData.department || r.department === formData.department)
                    .map(r => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                </select>
              </div>

              {/* Reporting Manager Assignment Field */}
              <div className="form-group" style={{ marginBottom: '16px', backgroundColor: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label style={{ fontWeight: '700', fontSize: '0.88rem', color: '#0f172a' }}>
                    Reporting Manager {formData.role === 'ADMIN' ? '(Optional/None)' : '*'}
                  </label>
                  <span style={{ fontSize: '0.75rem', color: '#0d9488', fontWeight: '600' }}>
                    {getRoleRequirementText(formData.role)}
                  </span>
                </div>

                {formData.role === 'ADMIN' ? (
                  <div style={{ padding: '10px 12px', backgroundColor: '#f1f5f9', borderRadius: '6px', fontSize: '0.85rem', color: '#64748b' }}>
                    <Info size={14} style={{ display: 'inline', marginRight: '6px' }} />
                    Administrator accounts sit at the root of the hierarchy and do not report to anyone.
                  </div>
                ) : (
                  <>
                    <select 
                      value={formData.reporting_manager_id} 
                      onChange={(e) => setFormData({ ...formData, reporting_manager_id: e.target.value })}
                      required={formData.role !== 'ADMIN'}
                      disabled={loadingEligibleManagers}
                      style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff' }}
                    >
                      <option value="">-- Select Reporting Manager --</option>
                      {eligibleManagers.map(m => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({getRoleBadgeStyle(m.role).label})
                        </option>
                      ))}
                    </select>
                    {eligibleManagers.length === 0 && !loadingEligibleManagers && (
                      <div style={{ marginTop: '6px', fontSize: '0.78rem', color: '#dc2626' }}>
                        No eligible active managers found for role '{formData.role}'.
                      </div>
                    )}
                  </>
                )}
              </div>

              <div className="form-group" style={{ marginBottom: '18px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>Account Status</label>
                <select 
                  value={formData.status} 
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                >
                  <option value="ACTIVE">ACTIVE</option>
                  <option value="INACTIVE">INACTIVE</option>
                </select>
                {selectedUser?.direct_reports_count > 0 && formData.status === 'INACTIVE' && (
                  <div style={{ marginTop: '6px', padding: '8px 10px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', fontSize: '0.78rem', color: '#dc2626' }}>
                    Warning: This user has {selectedUser.direct_reports_count} direct report(s). Please reassign their reports before deactivating.
                  </div>
                )}
              </div>

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowEditModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Saving Changes...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* REASSIGN DIRECT REPORTS MODAL */}
      {showReassignModal && (
        <div className="modal-backdrop" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1050
        }}>
          <div className="modal-content" style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            width: '100%', maxWidth: '480px', padding: '26px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: '800', margin: 0, color: '#0f172a' }}>
                  Reassign Direct Reports
                </h3>
                <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#64748b' }}>
                  Transfer reportees of <strong>{reassignData.sourceUser?.name}</strong> to another active manager.
                </p>
              </div>
              <button onClick={() => setShowReassignModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleReassignReportsSubmit}>
              <div style={{ backgroundColor: '#eff6ff', padding: '12px', borderRadius: '8px', border: '1px solid #bfdbfe', marginBottom: '16px', fontSize: '0.85rem', color: '#1e40af' }}>
                <strong>{reassignData.sourceUser?.direct_reports_count} direct report(s)</strong> currently report to {reassignData.sourceUser?.name}. Select a replacement manager below to safely transfer them.
              </div>

              <div className="form-group" style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '700', fontSize: '0.88rem' }}>
                  New Reporting Manager *
                </label>
                <select 
                  value={reassignData.newManagerId} 
                  onChange={(e) => setReassignData({ ...reassignData, newManagerId: e.target.value })}
                  required
                  style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                >
                  <option value="">-- Select Replacement Manager --</option>
                  {reassignData.availableTargetManagers.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({getRoleBadgeStyle(m.role).label})
                    </option>
                  ))}
                </select>
              </div>

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowReassignModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Reassigning...' : 'Confirm Reassignment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* RESET PASSWORD MODAL */}
      {showResetPwdModal && (
        <div className="modal-backdrop" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.55)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            width: '100%', maxWidth: '420px', padding: '26px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)'
          }}>
            <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: '800', margin: 0 }}>Reset User Password</h3>
              <button onClick={() => setShowResetPwdModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleResetPasswordSubmit}>
              <p style={{ fontSize: '0.88rem', color: '#64748b', marginBottom: '16px' }}>
                Setting new credentials for login account <strong>@{resetPwdData.username}</strong>:
              </p>

              <div className="form-group" style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.85rem' }}>New Password *</label>
                <input 
                  type="password" 
                  required 
                  placeholder="Enter new password" 
                  value={resetPwdData.newPassword}
                  onChange={(e) => setResetPwdData({ ...resetPwdData, newPassword: e.target.value })}
                  style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                />
              </div>

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowResetPwdModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Resetting...' : 'Confirm Reset Password'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Employees;
