import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import {
  Shield,
  ShieldCheck,
  Plus,
  Edit2,
  Trash2,
  Check,
  X,
  AlertCircle,
  Info,
  Lock,
  Layers,
  Eye,
  FileText,
  CheckCircle2,
  Sliders,
  Settings,
  Users,
  Phone,
  MessageCircle,
  Calendar,
  DollarSign,
  PieChart,
  Headphones,
  FileCheck,
  ArrowRight,
  Sparkles,
  HelpCircle
} from 'lucide-react';

const ACTION_COLUMNS = [
  { key: 'can_view', label: 'View' },
  { key: 'can_create', label: 'Create' },
  { key: 'can_edit', label: 'Edit' },
  { key: 'can_delete', label: 'Delete' },
  { key: 'can_export', label: 'Export' },
  { key: 'can_approve', label: 'Approve' },
  { key: 'can_assign', label: 'Assign' },
  { key: 'can_call', label: 'Call' },
  { key: 'can_whatsapp', label: 'WhatsApp' }
];

const SCOPE_OPTIONS = [
  { value: 'own', label: 'Own Records' },
  { value: 'team', label: 'Team Records' },
  { value: 'department', label: 'Department' },
  { value: 'company', label: 'Company-Wide' },
  { value: 'none', label: 'None' }
];

const RoleManagementMatrix = ({ onRoleCreatedOrUpdated }) => {
  const { user: currentUser } = useAuth();
  const [roles, setRoles] = useState([]);
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Selected Role for Quick View
  const [selectedRole, setSelectedRole] = useState(null);

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [roleToDelete, setRoleToDelete] = useState(null);
  const [saving, setSaving] = useState(false);

  // Form State
  const [formData, setFormData] = useState({
    name: '',
    display_name: '',
    description: '',
    is_active: true,
    permissions: []
  });

  const fetchRolesAndModules = async () => {
    try {
      setLoading(true);
      setError('');
      const [rolesRes, modulesRes] = await Promise.all([
        API.get('/roles'),
        API.get('/roles/modules')
      ]);
      setRoles(rolesRes.data);
      setModules(modulesRes.data);

      if (rolesRes.data.length > 0) {
        if (!selectedRole) {
          // Default select SALES or MANAGER or first role
          const defaultRole = rolesRes.data.find(r => r.name === 'SALES') || rolesRes.data[0];
          setSelectedRole(defaultRole);
        } else {
          const updatedSelected = rolesRes.data.find(r => r.id === selectedRole.id);
          if (updatedSelected) setSelectedRole(updatedSelected);
        }
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to load roles and permission catalog.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRolesAndModules();
  }, []);

  const initPermissionsForRole = (existingPerms = []) => {
    const permMap = {};
    (existingPerms || []).forEach(p => {
      permMap[p.module.toLowerCase()] = p;
    });

    return modules.map(m => {
      const existing = permMap[m.key.toLowerCase()];
      if (existing) {
        return {
          module: m.key,
          has_access: Boolean(existing.has_access),
          can_view: Boolean(existing.can_view),
          can_create: Boolean(existing.can_create),
          can_edit: Boolean(existing.can_edit),
          can_delete: Boolean(existing.can_delete),
          can_export: Boolean(existing.can_export),
          can_approve: Boolean(existing.can_approve),
          can_assign: Boolean(existing.can_assign),
          can_call: Boolean(existing.can_call),
          can_whatsapp: Boolean(existing.can_whatsapp),
          view_scope: existing.view_scope || 'own'
        };
      }
      return {
        module: m.key,
        has_access: false,
        can_view: false,
        can_create: false,
        can_edit: false,
        can_delete: false,
        can_export: false,
        can_approve: false,
        can_assign: false,
        can_call: false,
        can_whatsapp: false,
        view_scope: 'none'
      };
    });
  };

  const handleOpenCreateModal = () => {
    setFormData({
      name: '',
      display_name: '',
      description: '',
      is_active: true,
      permissions: initPermissionsForRole([])
    });
    setError('');
    setSuccess('');
    setShowCreateModal(true);
  };

  const handleOpenEditModal = (role) => {
    setFormData({
      id: role.id,
      name: role.name,
      display_name: role.display_name,
      description: role.description || '',
      is_active: role.is_active,
      is_system: role.is_system,
      permissions: initPermissionsForRole(role.permissions)
    });
    setError('');
    setSuccess('');
    setShowEditModal(true);
  };

  const handlePermissionChange = (moduleKey, field, value) => {
    setFormData(prev => {
      const updated = prev.permissions.map(p => {
        if (p.module === moduleKey) {
          const item = { ...p, [field]: value };
          // If enabling any action, auto-turn on has_access and can_view
          if (field !== 'has_access' && field !== 'view_scope' && value === true) {
            item.has_access = true;
            item.can_view = true;
            if (item.view_scope === 'none') {
              item.view_scope = 'own';
            }
          }
          // If turning off has_access, zero out actions
          if (field === 'has_access' && value === false) {
            item.can_view = false;
            item.can_create = false;
            item.can_edit = false;
            item.can_delete = false;
            item.can_export = false;
            item.can_approve = false;
            item.can_assign = false;
            item.can_call = false;
            item.can_whatsapp = false;
            item.view_scope = 'none';
          }
          // If turning on has_access, default can_view to true and scope to 'own'
          if (field === 'has_access' && value === true) {
            item.can_view = true;
            if (item.view_scope === 'none') {
              item.view_scope = 'own';
            }
          }
          return item;
        }
        return p;
      });
      return { ...prev, permissions: updated };
    });
  };

  const handleToggleAllActionsForModule = (moduleKey, enableAll) => {
    setFormData(prev => {
      const updated = prev.permissions.map(p => {
        if (p.module === moduleKey) {
          return {
            ...p,
            has_access: enableAll,
            can_view: enableAll,
            can_create: enableAll,
            can_edit: enableAll,
            can_delete: enableAll,
            can_export: enableAll,
            can_approve: enableAll,
            can_assign: enableAll,
            can_call: enableAll,
            can_whatsapp: enableAll,
            view_scope: enableAll ? (p.view_scope === 'none' ? 'own' : p.view_scope) : 'none'
          };
        }
        return p;
      });
      return { ...prev, permissions: updated };
    });
  };

  // Preset quick templates for Admin ease-of-use
  const applyPresetTemplate = (templateType) => {
    setFormData(prev => {
      const updated = prev.permissions.map(p => {
        const k = p.module.toLowerCase();
        if (templateType === 'sales') {
          const isSalesModule = ['leads', 'customers', 'contacts', 'quotations', 'calls', 'whatsapp', 'followups', 'activities'].includes(k);
          return {
            module: p.module,
            has_access: isSalesModule,
            can_view: isSalesModule,
            can_create: isSalesModule,
            can_edit: isSalesModule,
            can_delete: false, // Sales cannot delete
            can_export: ['leads', 'customers'].includes(k),
            can_approve: false,
            can_assign: false,
            can_call: ['calls', 'leads', 'followups'].includes(k),
            can_whatsapp: ['whatsapp', 'leads', 'quotations'].includes(k),
            view_scope: isSalesModule ? 'own' : 'none'
          };
        } else if (templateType === 'finance') {
          const isFinanceModule = ['payments', 'customers', 'reports'].includes(k);
          return {
            module: p.module,
            has_access: isFinanceModule,
            can_view: isFinanceModule,
            can_create: isFinanceModule,
            can_edit: isFinanceModule,
            can_delete: false,
            can_export: true,
            can_approve: ['payments'].includes(k),
            can_assign: false,
            can_call: false,
            can_whatsapp: false,
            view_scope: isFinanceModule ? 'company' : 'none'
          };
        } else if (templateType === 'support') {
          const isSupportModule = ['support_tickets', 'customers', 'contacts', 'whatsapp', 'activities', 'followups'].includes(k);
          return {
            module: p.module,
            has_access: isSupportModule,
            can_view: isSupportModule,
            can_create: isSupportModule,
            can_edit: isSupportModule,
            can_delete: false,
            can_export: false,
            can_approve: false,
            can_assign: ['support_tickets'].includes(k),
            can_call: true,
            can_whatsapp: true,
            view_scope: isSupportModule ? 'team' : 'none'
          };
        } else if (templateType === 'all') {
          return {
            module: p.module,
            has_access: true,
            can_view: true,
            can_create: true,
            can_edit: true,
            can_delete: true,
            can_export: true,
            can_approve: true,
            can_assign: true,
            can_call: true,
            can_whatsapp: true,
            view_scope: 'company'
          };
        } else if (templateType === 'clear') {
          return {
            module: p.module,
            has_access: false,
            can_view: false,
            can_create: false,
            can_edit: false,
            can_delete: false,
            can_export: false,
            can_approve: false,
            can_assign: false,
            can_call: false,
            can_whatsapp: false,
            view_scope: 'none'
          };
        }
        return p;
      });
      return { ...prev, permissions: updated };
    });
  };

  const handleSaveCreateRole = async (e) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.display_name.trim()) {
      setError('Role Identifier and Display Name are required.');
      return;
    }

    try {
      setSaving(true);
      setError('');
      const payload = {
        name: formData.name.trim().toUpperCase(),
        display_name: formData.display_name.trim(),
        description: formData.description?.trim() || null,
        permissions: formData.permissions
      };

      const res = await API.post('/roles', payload);
      setSuccess(`Role '${res.data.display_name}' created successfully!`);
      setShowCreateModal(false);
      await fetchRolesAndModules();
      setSelectedRole(res.data);
      if (onRoleCreatedOrUpdated) onRoleCreatedOrUpdated();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to create role.');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveEditRole = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setError('');
      const payload = {
        display_name: formData.display_name.trim(),
        description: formData.description?.trim() || null,
        is_active: formData.is_active,
        permissions: formData.permissions
      };

      const res = await API.put(`/roles/${formData.id}`, payload);
      setSuccess(`Permissions for role '${res.data.display_name}' updated successfully! Changes take effect immediately.`);
      setShowEditModal(false);
      await fetchRolesAndModules();
      setSelectedRole(res.data);
      if (onRoleCreatedOrUpdated) onRoleCreatedOrUpdated();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to update role permissions.');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteRole = async () => {
    if (!roleToDelete) return;
    try {
      setSaving(true);
      setError('');
      await API.delete(`/roles/${roleToDelete.id}`);
      setSuccess(`Role '${roleToDelete.display_name}' deleted successfully.`);
      setShowDeleteModal(false);
      setRoleToDelete(null);
      await fetchRolesAndModules();
      if (onRoleCreatedOrUpdated) onRoleCreatedOrUpdated();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to delete role.');
    } finally {
      setSaving(false);
    }
  };

  const getCategoryColor = (category) => {
    switch (category) {
      case 'Core': return '#6366f1';
      case 'Sales & CRM': return '#3b82f6';
      case 'Billing & Finance': return '#10b981';
      case 'Communication': return '#8b5cf6';
      case 'Operations & Support': return '#f59e0b';
      case 'Analytics': return '#06b6d4';
      case 'Administration': return '#ec4899';
      default: return '#6b7280';
    }
  };

  return (
    <div className="role-management-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Alert Banners */}
      {error && (
        <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', padding: '12px 16px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div style={{ backgroundColor: 'var(--success-light)', color: 'var(--success)', border: '1px solid rgba(16,185,129,0.3)', padding: '12px 16px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <CheckCircle2 size={18} />
          <span>{success}</span>
        </div>
      )}

      {/* Top Banner: Explanation & Actions */}
      <div style={{
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        borderLeft: '4px solid #0f766e',
        borderRadius: '12px',
        padding: '20px 24px',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '16px',
        boxShadow: '0 1px 3px rgba(15, 23, 42, 0.05)'
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
          <div style={{
            backgroundColor: '#f0fdfa',
            color: '#0f766e',
            padding: '10px',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '1px solid #ccfbf1',
            flexShrink: 0
          }}>
            <ShieldCheck size={24} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: '800', margin: '0 0 4px', color: '#0f172a' }}>
              Dynamic Role & Permission Matrix
            </h3>
            <p style={{ margin: 0, color: '#64748b', fontSize: '0.86rem', maxWidth: '780px', lineHeight: 1.5 }}>
              Configure granular module access, actions (View, Create, Edit, Delete, Export, Approve, Assign, Call, WhatsApp), 
              and data visibility scopes (Own, Team, Department, Company-Wide). Permissions are dynamically enforced across React UI and FastAPI backend.
            </p>
          </div>
        </div>

        {currentUser?.role === 'ADMIN' && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleOpenCreateModal}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 18px',
              fontWeight: '600',
              backgroundColor: '#0f766e',
              borderColor: '#0f766e',
              borderRadius: '8px',
              boxShadow: '0 2px 4px rgba(15, 118, 110, 0.2)'
            }}
          >
            <Plus size={18} /> Create New Role
          </button>
        )}
      </div>

      {/* Roles List Badges / Selector Grid */}
      <div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '10px'
        }}>
          <span style={{ fontSize: '0.82rem', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Available Roles ({roles.length})
          </span>
          <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
            Click a card to inspect and manage permissions
          </span>
        </div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))',
          gap: '12px'
        }}>
          {roles.map(r => {
            const isSelected = selectedRole?.id === r.id;
            const isAdminRole = r.name.toUpperCase() === 'ADMIN';

            return (
              <div
                key={r.id}
                onClick={() => setSelectedRole(r)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '10px',
                  padding: '12px 16px',
                  borderRadius: '10px',
                  border: isSelected ? '2px solid #0f766e' : '1px solid #e2e8f0',
                  backgroundColor: isSelected ? '#f0fdfa' : '#ffffff',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  boxShadow: isSelected ? '0 2px 8px rgba(15, 118, 110, 0.12)' : '0 1px 2px rgba(15, 23, 42, 0.04)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
                  <div style={{
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    flexShrink: 0,
                    backgroundColor: isAdminRole ? '#6366f1' : (r.is_active ? '#10b981' : '#94a3b8')
                  }} />
                  <div style={{ minWidth: 0, overflow: 'hidden' }}>
                    <div style={{
                      fontWeight: '700',
                      fontSize: '0.92rem',
                      color: isSelected ? '#0f766e' : '#0f172a',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}>
                      {r.display_name}
                    </div>
                    <div style={{ fontSize: '0.74rem', color: '#64748b' }}>
                      <span style={{ fontFamily: 'monospace', fontWeight: '600' }}>{r.name}</span> • {r.user_count} user{r.user_count !== 1 ? 's' : ''}
                    </div>
                  </div>
                </div>
                {isAdminRole ? (
                  <span style={{ fontSize: '0.68rem', backgroundColor: 'rgba(99, 102, 241, 0.12)', color: '#6366f1', padding: '2px 7px', borderRadius: '4px', fontWeight: '700', flexShrink: 0 }}>
                    CORE
                  </span>
                ) : isSelected ? (
                  <span style={{ fontSize: '0.68rem', backgroundColor: '#ccfbf1', color: '#0f766e', padding: '2px 7px', borderRadius: '4px', fontWeight: '700', flexShrink: 0 }}>
                    ACTIVE
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      {/* Selected Role Matrix Display Card */}
      {selectedRole && (
        <div style={{
          backgroundColor: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: '12px',
          padding: '24px',
          boxShadow: '0 1px 3px rgba(15, 23, 42, 0.05)'
        }}>
          {/* Header of Selected Role */}
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid #e2e8f0',
            paddingBottom: '18px',
            marginBottom: '20px',
            gap: '14px'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                <h4 style={{ margin: 0, fontSize: '1.25rem', fontWeight: '800', color: '#0f172a' }}>
                  {selectedRole.display_name}
                </h4>
                <span style={{
                  fontSize: '0.76rem',
                  padding: '3px 8px',
                  borderRadius: '6px',
                  backgroundColor: '#f1f5f9',
                  border: '1px solid #cbd5e1',
                  color: '#475569',
                  fontFamily: 'monospace',
                  fontWeight: '700'
                }}>
                  {selectedRole.name}
                </span>
                {selectedRole.is_system && (
                  <span style={{
                    fontSize: '0.74rem',
                    padding: '3px 8px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    color: '#2563eb',
                    border: '1px solid rgba(59, 130, 246, 0.2)',
                    fontWeight: '700'
                  }}>
                    System Protected
                  </span>
                )}
              </div>
              <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: '0.86rem' }}>
                {selectedRole.description || 'No role description provided.'}
              </p>
            </div>

            {currentUser?.role === 'ADMIN' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => handleOpenEditModal(selectedRole)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '0.88rem',
                    fontWeight: '600',
                    color: '#0f766e',
                    borderColor: '#0f766e',
                    borderRadius: '8px',
                    padding: '8px 14px'
                  }}
                >
                  <Edit2 size={16} /> Edit Role & Permissions
                </button>
                {!selectedRole.is_system && selectedRole.name !== 'ADMIN' && (
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => {
                      setRoleToDelete(selectedRole);
                      setShowDeleteModal(true);
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontSize: '0.88rem',
                      fontWeight: '600',
                      color: '#dc2626',
                      borderColor: '#fca5a5',
                      borderRadius: '8px',
                      padding: '8px 14px',
                      backgroundColor: '#fef2f2'
                    }}
                  >
                    <Trash2 size={16} /> Delete Role
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Matrix Table */}
          <div style={{
            overflowX: 'auto',
            border: '1px solid #e2e8f0',
            borderRadius: '10px'
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '12px 16px', fontWeight: '700', color: '#475569', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Module</th>
                  <th style={{ padding: '12px 14px', fontWeight: '700', color: '#475569', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Category</th>
                  <th style={{ padding: '12px 14px', fontWeight: '700', color: '#475569', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em', textAlign: 'center' }}>Access</th>
                  {ACTION_COLUMNS.map(col => (
                    <th key={col.key} style={{ padding: '12px 8px', fontWeight: '700', color: '#475569', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em', textAlign: 'center' }}>
                      {col.label}
                    </th>
                  ))}
                  <th style={{ padding: '12px 16px', fontWeight: '700', color: '#475569', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em', textAlign: 'center' }}>Data Scope</th>
                </tr>
              </thead>
              <tbody>
                {modules.map((mod, idx) => {
                  const perm = (selectedRole.permissions || []).find(p => p.module?.toLowerCase() === mod.key?.toLowerCase()) || {};
                  const isAdminRole = selectedRole.name.toUpperCase() === 'ADMIN';
                  const hasAccess = isAdminRole ? true : Boolean(perm.has_access);

                  return (
                    <tr
                      key={mod.key}
                      style={{
                        borderBottom: idx === modules.length - 1 ? 'none' : '1px solid #f1f5f9',
                        opacity: hasAccess ? 1 : 0.5,
                        backgroundColor: hasAccess ? (idx % 2 === 0 ? '#ffffff' : '#fafafa') : '#f8fafc'
                      }}
                    >
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ fontWeight: '600', color: '#0f172a' }}>{mod.label}</div>
                        <div style={{ fontSize: '0.74rem', color: '#64748b' }}>{mod.description}</div>
                      </td>
                      <td style={{ padding: '12px 14px' }}>
                        <span style={{
                          fontSize: '0.72rem',
                          padding: '3px 8px',
                          borderRadius: '12px',
                          backgroundColor: `${getCategoryColor(mod.category)}18`,
                          color: getCategoryColor(mod.category),
                          fontWeight: '700'
                        }}>
                          {mod.category}
                        </span>
                      </td>
                      <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                        {hasAccess ? (
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: '#059669',
                            backgroundColor: '#ecfdf5',
                            border: '1px solid #a7f3d0',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            fontSize: '0.75rem',
                            fontWeight: '700'
                          }}>
                            ● Enabled
                          </span>
                        ) : (
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: '#94a3b8',
                            backgroundColor: '#f1f5f9',
                            border: '1px solid #e2e8f0',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            fontSize: '0.75rem',
                            fontWeight: '600'
                          }}>
                            ✕ Disabled
                          </span>
                        )}
                      </td>
                      {ACTION_COLUMNS.map(col => {
                        const isGranted = isAdminRole ? true : (hasAccess && Boolean(perm[col.key]));
                        return (
                          <td key={col.key} style={{ padding: '12px 8px', textAlign: 'center' }}>
                            {isGranted ? (
                              <div style={{
                                width: '22px',
                                height: '22px',
                                borderRadius: '50%',
                                backgroundColor: '#ecfdf5',
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center'
                              }}>
                                <Check size={14} color="#059669" strokeWidth={3} />
                              </div>
                            ) : (
                              <span style={{ color: '#cbd5e1', fontSize: '1rem', fontWeight: '600' }}>—</span>
                            )}
                          </td>
                        );
                      })}
                      <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                        <span style={{
                          padding: '4px 10px',
                          borderRadius: '6px',
                          fontSize: '0.76rem',
                          fontWeight: '700',
                          backgroundColor: isAdminRole ? 'rgba(99, 102, 241, 0.12)' : '#f1f5f9',
                          color: isAdminRole ? '#6366f1' : '#334155',
                          border: isAdminRole ? '1px solid rgba(99, 102, 241, 0.25)' : '1px solid #e2e8f0',
                          textTransform: 'capitalize'
                        }}>
                          {isAdminRole ? 'Company-Wide' : (perm.view_scope || 'none')}
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

      {/* CREATE / EDIT ROLE MODAL WITH COMPLETE INTERACTIVE PERMISSION MATRIX */}
      {(showCreateModal || showEditModal) && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          backdropFilter: 'blur(3px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1100,
          padding: '20px'
        }}>
          <div style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: '16px',
            width: '100%',
            maxWidth: '1180px',
            maxHeight: '92vh',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
          }}>
            {/* Modal Header */}
            <div style={{
              padding: '20px 24px',
              borderBottom: '1px solid var(--border-color)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.3rem', fontWeight: '700' }}>
                  {showCreateModal ? 'Create New Custom Role' : `Edit Permissions for ${formData.display_name}`}
                </h3>
                <p style={{ margin: '4px 0 0', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  Configure module access, granular action checkboxes, and data visibility scope.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowCreateModal(false);
                  setShowEditModal(false);
                }}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={22} />
              </button>
            </div>

            {/* Modal Scrollable Body */}
            <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
              {/* Role Identifiers */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '20px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>
                    Role Identifier Code *
                  </label>
                  <input
                    type="text"
                    required
                    disabled={showEditModal}
                    placeholder="e.g. HR, OPERATIONS, PURCHASE"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value.toUpperCase().replace(/\s+/g, '_') })}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      border: '1px solid var(--border-color)',
                      backgroundColor: showEditModal ? 'var(--bg-hover)' : 'var(--bg-card)'
                    }}
                  />
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                    Uppercase code (e.g. HR, OPERATIONS). Cannot be changed once created.
                  </span>
                </div>

                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>
                    Display Title *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Human Resources Lead"
                    value={formData.display_name}
                    onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                    style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>
                    Description
                  </label>
                  <input
                    type="text"
                    placeholder="Brief description of responsibilities..."
                    value={formData.description || ''}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}
                  />
                </div>
              </div>

              {/* Quick Template Preset Buttons */}
              <div style={{
                backgroundColor: 'var(--bg-hover)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                padding: '12px 16px',
                marginBottom: '20px',
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '10px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.86rem', fontWeight: '600' }}>
                  <Sparkles size={16} color="#0f766e" />
                  <span>Quick Template Presets:</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => applyPresetTemplate('sales')}
                    style={{ fontSize: '0.78rem', padding: '5px 12px' }}
                  >
                    Sales Preset
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => applyPresetTemplate('finance')}
                    style={{ fontSize: '0.78rem', padding: '5px 12px' }}
                  >
                    Finance Preset
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => applyPresetTemplate('support')}
                    style={{ fontSize: '0.78rem', padding: '5px 12px' }}
                  >
                    Support Preset
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => applyPresetTemplate('all')}
                    style={{ fontSize: '0.78rem', padding: '5px 12px' }}
                  >
                    Grant All
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => applyPresetTemplate('clear')}
                    style={{ fontSize: '0.78rem', padding: '5px 12px', color: 'var(--danger)' }}
                  >
                    Clear All
                  </button>
                </div>
              </div>

              {/* Matrix Interactive Table */}
              <div style={{ border: '1px solid var(--border-color)', borderRadius: '10px', overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
                  <thead>
                    <tr style={{ backgroundColor: 'var(--bg-table-header, rgba(0,0,0,0.03))', borderBottom: '2px solid var(--border-color)' }}>
                      <th style={{ padding: '12px 14px', textAlign: 'left', fontWeight: '700', minWidth: '180px' }}>Module</th>
                      <th style={{ padding: '12px 8px', textAlign: 'center', fontWeight: '700' }}>Access</th>
                      {ACTION_COLUMNS.map(col => (
                        <th key={col.key} style={{ padding: '12px 8px', textAlign: 'center', fontWeight: '700' }}>
                          {col.label}
                        </th>
                      ))}
                      <th style={{ padding: '12px 14px', textAlign: 'center', fontWeight: '700', minWidth: '150px' }}>
                        Data Visibility Scope
                      </th>
                      <th style={{ padding: '12px 10px', textAlign: 'center', fontWeight: '700' }}>
                        Quick Select
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {modules.map(mod => {
                      const perm = (formData.permissions || []).find(p => p.module === mod.key) || {
                        module: mod.key,
                        has_access: false,
                        can_view: false,
                        can_create: false,
                        can_edit: false,
                        can_delete: false,
                        can_export: false,
                        can_approve: false,
                        can_assign: false,
                        can_call: false,
                        can_whatsapp: false,
                        view_scope: 'none'
                      };

                      return (
                        <tr
                          key={mod.key}
                          style={{
                            borderBottom: '1px solid var(--border-color)',
                            backgroundColor: perm.has_access ? 'transparent' : 'rgba(0,0,0,0.02)'
                          }}
                        >
                          <td style={{ padding: '10px 14px' }}>
                            <div style={{ fontWeight: '600' }}>{mod.label}</div>
                            <span style={{
                              fontSize: '0.68rem',
                              padding: '1px 6px',
                              borderRadius: '4px',
                              backgroundColor: `${getCategoryColor(mod.category)}18`,
                              color: getCategoryColor(mod.category),
                              fontWeight: '600'
                            }}>
                              {mod.category}
                            </span>
                          </td>

                          {/* Module Access Toggle */}
                          <td style={{ padding: '10px 8px', textAlign: 'center' }}>
                            <input
                              type="checkbox"
                              checked={perm.has_access}
                              onChange={(e) => handlePermissionChange(mod.key, 'has_access', e.target.checked)}
                              style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                              title={`Enable or disable access to ${mod.label}`}
                            />
                          </td>

                          {/* Action Checkboxes */}
                          {ACTION_COLUMNS.map(col => (
                            <td key={col.key} style={{ padding: '10px 8px', textAlign: 'center' }}>
                              <input
                                type="checkbox"
                                disabled={!perm.has_access}
                                checked={perm.has_access && Boolean(perm[col.key])}
                                onChange={(e) => handlePermissionChange(mod.key, col.key, e.target.checked)}
                                style={{
                                  width: '16px',
                                  height: '16px',
                                  cursor: perm.has_access ? 'pointer' : 'not-allowed',
                                  opacity: perm.has_access ? 1 : 0.35
                                }}
                              />
                            </td>
                          ))}

                          {/* Record Visibility Scope */}
                          <td style={{ padding: '10px 14px', textAlign: 'center' }}>
                            <select
                              disabled={!perm.has_access}
                              value={perm.has_access ? perm.view_scope : 'none'}
                              onChange={(e) => handlePermissionChange(mod.key, 'view_scope', e.target.value)}
                              style={{
                                padding: '6px 10px',
                                borderRadius: '6px',
                                border: '1px solid var(--border-color)',
                                fontSize: '0.82rem',
                                opacity: perm.has_access ? 1 : 0.45,
                                cursor: perm.has_access ? 'pointer' : 'not-allowed'
                              }}
                            >
                              {SCOPE_OPTIONS.map(opt => (
                                <option key={opt.value} value={opt.value}>
                                  {opt.label}
                                </option>
                              ))}
                            </select>
                          </td>

                          {/* Quick Toggle Row */}
                          <td style={{ padding: '10px 10px', textAlign: 'center' }}>
                            <button
                              type="button"
                              onClick={() => handleToggleAllActionsForModule(mod.key, !perm.has_access)}
                              style={{
                                border: 'none',
                                background: 'transparent',
                                color: perm.has_access ? 'var(--danger)' : '#0f766e',
                                cursor: 'pointer',
                                fontSize: '0.74rem',
                                fontWeight: '600'
                              }}
                            >
                              {perm.has_access ? 'Disable' : 'All'}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Modal Footer */}
            <div style={{
              padding: '16px 24px',
              borderTop: '1px solid var(--border-color)',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '12px'
            }}>
              <button
                type="button"
                className="btn btn-outline"
                disabled={saving}
                onClick={() => {
                  setShowCreateModal(false);
                  setShowEditModal(false);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={saving}
                onClick={showCreateModal ? handleSaveCreateRole : handleSaveEditRole}
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                {saving ? 'Saving Permissions...' : (showCreateModal ? 'Create Role' : 'Save Changes')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL */}
      {showDeleteModal && roleToDelete && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1200
        }}>
          <div style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: '12px',
            padding: '24px',
            maxWidth: '440px',
            width: '100%',
            boxShadow: 'var(--shadow-lg)'
          }}>
            <h4 style={{ margin: '0 0 12px', color: 'var(--danger)', fontSize: '1.2rem', fontWeight: '700' }}>
              Delete Role '{roleToDelete.display_name}'?
            </h4>
            <p style={{ margin: '0 0 20px', color: 'var(--text-color)', fontSize: '0.9rem', lineHeight: 1.5 }}>
              Are you sure you want to delete this custom role? This will permanently remove its permission matrix.
              {roleToDelete.user_count > 0 && (
                <span style={{ display: 'block', marginTop: '10px', color: 'var(--danger)', fontWeight: '600' }}>
                  ⚠️ Note: {roleToDelete.user_count} user(s) are currently assigned to this role. You must reassign them before deletion.
                </span>
              )}
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-outline"
                disabled={saving}
                onClick={() => {
                  setShowDeleteModal(false);
                  setRoleToDelete(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn"
                disabled={saving || roleToDelete.user_count > 0}
                onClick={handleDeleteRole}
                style={{ backgroundColor: 'var(--danger)', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: '600' }}
              >
                {saving ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RoleManagementMatrix;
