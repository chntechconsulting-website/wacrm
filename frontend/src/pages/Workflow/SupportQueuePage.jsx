import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { formatDateDDMMYYYY, formatLeadReceivedFull } from '../../utils/dateUtils';
import IVRCallModal from '../../components/IVR/IVRCallModal';
import PingoPopupService from '../../services/pingoPopupService';
import './Workflow.css';
import {
  LifeBuoy,
  CheckCircle2,
  Clock,
  PhoneCall,
  Phone,
  MessageCircle,
  Play,
  Check,
  Search,
  RefreshCw,
  ExternalLink,
  User,
  UserCheck,
  Building2,
  Mail,
  FileText,
  AlertCircle,
  X,
  Package,
  Users,
  DollarSign,
  Calendar,
  ShieldCheck
} from 'lucide-react';

const formatINR = (val) => {
  if (val === null || val === undefined || isNaN(val)) return '₹0';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(val);
};

const LIFECYCLE_STAGES = [
  { key: 'PENDING_ONBOARDING', label: 'Pending Onboarding', badgeClass: 'wf-badge-pending' },
  { key: 'CONTACTED', label: 'Contacted', badgeClass: 'wf-badge-contacted' },
  { key: 'ONBOARDING_IN_PROGRESS', label: 'In Progress', badgeClass: 'wf-badge-inprogress' },
  { key: 'COMPLETED', label: 'Completed', badgeClass: 'wf-badge-completed' }
];

const SupportQueuePage = () => {
  const { user } = useAuth();
  const [tickets, setTickets] = useState([]);
  const [supportManagers, setSupportManagers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  // Status Update Modal
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [statusForm, setStatusForm] = useState({
    onboarding_status: 'PENDING_ONBOARDING',
    support_notes: '',
    assigned_agent_id: ''
  });
  const [updating, setUpdating] = useState(false);

  // Admin Reassign Modal
  const [reassignTicket, setReassignTicket] = useState(null);
  const [newSupportManagerId, setNewSupportManagerId] = useState('');
  const [reassigning, setReassigning] = useState(false);

  // Call / IVR Modal State
  const [showCallModal, setShowCallModal] = useState(false);
  const [selectedCallLead, setSelectedCallLead] = useState(null);

  const [toastMessage, setToastMessage] = useState(null);

  const isAdmin = user?.role === 'ADMIN' || user?.role?.toUpperCase() === 'ADMIN';

  const fetchTickets = async () => {
    try {
      setLoading(true);
      const params = {};
      if (activeTab !== 'all') params.status = activeTab;
      if (searchTerm.trim()) params.search = searchTerm.trim();

      const res = await API.get('/workflow/support/handoffs', { params });
      setTickets(res.data || []);
    } catch (err) {
      console.error('Failed to load support handoffs', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchSupportManagers = async () => {
    try {
      const res = await API.get('/workflow/support-managers');
      setSupportManagers(res.data || []);
    } catch (err) {
      console.error('Failed to load support managers', err);
    }
  };

  useEffect(() => {
    fetchTickets();
    fetchSupportManagers();
  }, [activeTab]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchTickets();
  };

  // Support Team Call Option
  const handleCallCustomer = (ticket) => {
    if (!ticket || !ticket.phone) {
      alert('Customer phone number is not available for this record.');
      return;
    }

    const contactPayload = {
      id: ticket.lead_id,
      lead_id: ticket.lead_id,
      deal_id: ticket.deal_id,
      customer_id: ticket.customer_id,
      name: ticket.customer_name,
      phone: ticket.phone,
      company: ticket.company_name
    };

    if (window.crmDial) {
      window.crmDial(ticket.phone, contactPayload);
    } else {
      setSelectedCallLead(contactPayload);
      setShowCallModal(true);
    }

    // If ticket is pending onboarding, show notification
    if (ticket.onboarding_status === 'PENDING_ONBOARDING') {
      setToastMessage(`Call placed to ${ticket.customer_name} (${ticket.phone}). Update status to CONTACTED once connected!`);
      setTimeout(() => setToastMessage(null), 6000);
    }
  };

  // WhatsApp Customer Option
  const handleWhatsAppCustomer = (ticket) => {
    if (!ticket || !ticket.phone) {
      alert('Customer phone number is not available.');
      return;
    }
    const cleanPhone = ticket.phone.replace(/[^0-9]/g, '');
    const formattedPhone = cleanPhone.length === 10 ? `91${cleanPhone}` : cleanPhone;
    const msg = encodeURIComponent(
      `Hello ${ticket.customer_name}, this is ${user?.username || 'Support'} from the Onboarding & Support Team regarding your onboarding for ${ticket.company_name || 'your company'}. How can we assist you today?`
    );
    window.open(`https://wa.me/${formattedPhone}?text=${msg}`, '_blank');
  };

  const handleOpenStatusModal = (ticket) => {
    setSelectedTicket(ticket);
    setStatusForm({
      onboarding_status: ticket.onboarding_status || 'PENDING_ONBOARDING',
      support_notes: ticket.support_notes || '',
      assigned_agent_id: ticket.assigned_agent_id || ''
    });
  };

  const handleUpdateStatus = async (e) => {
    e.preventDefault();
    if (!selectedTicket) return;

    try {
      setUpdating(true);
      await API.put(`/workflow/support/handoffs/${selectedTicket.id}/status`, {
        onboarding_status: statusForm.onboarding_status,
        support_notes: statusForm.support_notes,
        assigned_agent_id: statusForm.assigned_agent_id ? parseInt(statusForm.assigned_agent_id) : null
      });

      setToastMessage(`Onboarding ticket #${selectedTicket.id} updated to ${statusForm.onboarding_status}!`);
      setTimeout(() => setToastMessage(null), 5000);
      PingoPopupService.triggerStatusUpdate({
        module: 'Support Onboarding',
        status: statusForm.onboarding_status,
        reference: `Ticket #${selectedTicket.id}`,
        customMessage: `Ticket #${selectedTicket.id} status updated to ${statusForm.onboarding_status}!`
      });
      setSelectedTicket(null);
      fetchTickets();
    } catch (err) {
      alert('Error updating status: ' + (err.response?.data?.detail || err.message));
    } finally {
      setUpdating(false);
    }
  };

  const handleOpenReassignModal = (ticket) => {
    setReassignTicket(ticket);
    setNewSupportManagerId(ticket.support_manager_id ? String(ticket.support_manager_id) : '');
  };

  const handleReassignSubmit = async (e) => {
    e.preventDefault();
    if (!reassignTicket || !newSupportManagerId) return;

    try {
      setReassigning(true);
      const res = await API.put(`/workflow/support/handoffs/${reassignTicket.id}/reassign`, {
        support_manager_id: parseInt(newSupportManagerId, 10)
      });

      const selectedMgr = supportManagers.find(m => String(m.id) === String(newSupportManagerId));
      const mgrName = selectedMgr?.name || res.data?.support_manager_name || 'Support Manager';

      setToastMessage(`Deal #${reassignTicket.deal_id || reassignTicket.lead_id} reassigned to Support Manager – ${mgrName}!`);
      setTimeout(() => setToastMessage(null), 5000);
      setReassignTicket(null);
      fetchTickets();
      if (selectedTicket && selectedTicket.id === reassignTicket.id) {
        setSelectedTicket(prev => prev ? ({ ...prev, support_manager_id: parseInt(newSupportManagerId, 10), support_manager_name: mgrName }) : null);
      }
    } catch (err) {
      alert('Error reassigning support manager: ' + (err.response?.data?.detail || err.message));
    } finally {
      setReassigning(false);
    }
  };

  // KPI Calculations
  const pendingCount = tickets.filter((t) => t.onboarding_status === 'PENDING_ONBOARDING').length;
  const contactedCount = tickets.filter((t) => t.onboarding_status === 'CONTACTED').length;
  const inProgressCount = tickets.filter((t) => t.onboarding_status === 'ONBOARDING_IN_PROGRESS').length;
  const completedCount = tickets.filter((t) => t.onboarding_status === 'COMPLETED').length;

  const getStageBadge = (stage) => {
    const s = LIFECYCLE_STAGES.find((x) => x.key === stage);
    if (!s) return <span className="wf-badge wf-badge-pending">{stage}</span>;
    return <span className={`wf-badge ${s.badgeClass}`}>{s.label}</span>;
  };

  const getPaymentStatusBadge = (status) => {
    const st = (status || 'PAYMENT_PENDING').toUpperCase();
    if (st === 'PAID') {
      return (
        <span style={{
          backgroundColor: '#dcfce7',
          color: '#15803d',
          padding: '2px 8px',
          borderRadius: '12px',
          fontSize: '0.72rem',
          fontWeight: 700
        }}>
          PAID
        </span>
      );
    }
    if (st === 'PARTIALLY_PAID') {
      return (
        <span style={{
          backgroundColor: '#fef3c7',
          color: '#b45309',
          padding: '2px 8px',
          borderRadius: '12px',
          fontSize: '0.72rem',
          fontWeight: 700
        }}>
          PARTIAL
        </span>
      );
    }
    return (
      <span style={{
        backgroundColor: '#f1f5f9',
        color: '#64748b',
        padding: '2px 8px',
        borderRadius: '12px',
        fontSize: '0.72rem',
        fontWeight: 700
      }}>
        PENDING
      </span>
    );
  };

  return (
    <div className="workflow-page">
      {/* Toast Alert */}
      {toastMessage && (
        <div style={{
          position: 'fixed',
          top: '20px',
          right: '20px',
          zIndex: 2000,
          background: '#eff6ff',
          border: '1px solid #3b82f6',
          color: '#1e40af',
          borderRadius: '10px',
          padding: '14px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)'
        }}>
          <CheckCircle2 size={20} className="text-blue-600" />
          <span style={{ fontSize: '0.88rem', fontWeight: 600 }}>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="workflow-header">
        <div>
          <h1 className="workflow-header-title">
            <LifeBuoy size={30} className="text-blue-600" />
            Support Dashboard & Assigned Onboarding
          </h1>
          <p className="workflow-subtitle">
            Sales Deal WON &rarr; Assigned Support Manager Onboarding Queue (Exact Customer ID, Lead ID, Deal ID linked).
          </p>
        </div>
        <button
          type="button"
          onClick={fetchTickets}
          className="btn btn-secondary flex items-center gap-2"
          disabled={loading}
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* KPI Lifecycle Cards */}
      <div className="workflow-kpi-grid">
        <div className="workflow-kpi-card">
          <div className="workflow-kpi-icon" style={{ backgroundColor: '#fef3c7', color: '#b45309' }}>
            <Clock size={24} />
          </div>
          <div>
            <div className="workflow-kpi-label">Pending Onboarding</div>
            <div className="workflow-kpi-value text-amber-600">{pendingCount}</div>
            <div className="workflow-kpi-sub">Awaiting welcome call & setup</div>
          </div>
        </div>

        <div className="workflow-kpi-card">
          <div className="workflow-kpi-icon" style={{ backgroundColor: '#e0e7ff', color: '#4338ca' }}>
            <PhoneCall size={24} />
          </div>
          <div>
            <div className="workflow-kpi-label">Contacted</div>
            <div className="workflow-kpi-value text-indigo-700">{contactedCount}</div>
            <div className="workflow-kpi-sub">Intro call / welcome email sent</div>
          </div>
        </div>

        <div className="workflow-kpi-card">
          <div className="workflow-kpi-icon" style={{ backgroundColor: '#e0f2fe', color: '#0369a1' }}>
            <Play size={24} />
          </div>
          <div>
            <div className="workflow-kpi-label">In Progress</div>
            <div className="workflow-kpi-value text-sky-700">{inProgressCount}</div>
            <div className="workflow-kpi-sub">Configuration & setup</div>
          </div>
        </div>

        <div className="workflow-kpi-card">
          <div className="workflow-kpi-icon" style={{ backgroundColor: '#dcfce7', color: '#15803d' }}>
            <CheckCircle2 size={24} />
          </div>
          <div>
            <div className="workflow-kpi-label">Completed</div>
            <div className="workflow-kpi-value text-emerald-700">{completedCount}</div>
            <div className="workflow-kpi-sub">Services fully activated</div>
          </div>
        </div>
      </div>

      {/* Main Table Card */}
      <div className="workflow-main-card">
        <div className="workflow-toolbar">
          <div className="workflow-tabs">
            <button
              type="button"
              className={`workflow-tab-btn ${activeTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveTab('all')}
            >
              All Assignments ({tickets.length})
            </button>
            <button
              type="button"
              className={`workflow-tab-btn ${activeTab === 'PENDING_ONBOARDING' ? 'active' : ''}`}
              onClick={() => setActiveTab('PENDING_ONBOARDING')}
            >
              Pending ({pendingCount})
            </button>
            <button
              type="button"
              className={`workflow-tab-btn ${activeTab === 'CONTACTED' ? 'active' : ''}`}
              onClick={() => setActiveTab('CONTACTED')}
            >
              Contacted ({contactedCount})
            </button>
            <button
              type="button"
              className={`workflow-tab-btn ${activeTab === 'ONBOARDING_IN_PROGRESS' ? 'active' : ''}`}
              onClick={() => setActiveTab('ONBOARDING_IN_PROGRESS')}
            >
              In Progress ({inProgressCount})
            </button>
            <button
              type="button"
              className={`workflow-tab-btn ${activeTab === 'COMPLETED' ? 'active' : ''}`}
              onClick={() => setActiveTab('COMPLETED')}
            >
              Completed ({completedCount})
            </button>
          </div>

          <form onSubmit={handleSearchSubmit} className="workflow-search-box">
            <Search size={16} className="workflow-search-icon" />
            <input
              type="text"
              placeholder="Search deal, company, phone, support manager..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </form>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="workflow-table">
            <thead>
              <tr>
                <th>Deal ID / Customer</th>
                <th>Product / Service & Users</th>
                <th>Deal Amount & Payment</th>
                <th>Quotation & WON Date</th>
                <th>Sales Rep & Support Manager</th>
                <th>Onboarding Lifecycle</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tickets.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '48px', color: '#94a3b8' }}>
                    <AlertCircle size={32} style={{ margin: '0 auto 8px auto', color: '#cbd5e1' }} />
                    <p style={{ fontWeight: 600, color: '#475569', margin: 0 }}>No onboarding assignments found</p>
                    <small>When Sales marks a deal as WON and selects a Support Manager, it appears immediately here.</small>
                  </td>
                </tr>
              ) : (
                tickets.map((t) => (
                  <tr key={t.id}>
                    {/* 1. Customer & Company Name, Customer ID, Lead ID, Deal ID, and Phone Click-to-Call */}
                    <td>
                      <div style={{ fontWeight: 700, color: '#0f172a' }}>
                        {t.company_name || t.customer_name}
                      </div>
                      {t.company_name && t.customer_name && (
                        <div style={{ fontSize: '0.78rem', color: '#475569' }}>
                          Contact: {t.customer_name}
                        </div>
                      )}
                      <div style={{ fontSize: '0.74rem', color: '#0369a1', marginTop: '2px', fontWeight: 600 }}>
                        Deal #{t.deal_id || t.lead_id} &bull; Cust #{t.customer_id} &bull; Lead #{t.lead_id}
                      </div>
                      
                      {/* Click-to-Call & WhatsApp Option for Support Team */}
                      {t.phone && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '5px' }}>
                          <button
                            type="button"
                            onClick={() => handleCallCustomer(t)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '5px',
                              background: '#ecfdf5',
                              color: '#047857',
                              border: '1px solid #a7f3d0',
                              borderRadius: '6px',
                              padding: '2px 8px',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                              transition: 'all 0.15s ease'
                            }}
                            title={`Click to call ${t.customer_name} (${t.phone})`}
                          >
                            <PhoneCall size={12} style={{ color: '#059669' }} />
                            <span>{t.phone}</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleWhatsAppCustomer(t)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              background: '#f0fdf4',
                              color: '#16a34a',
                              border: '1px solid #bbf7d0',
                              borderRadius: '6px',
                              padding: '2px 6px',
                              fontSize: '0.75rem',
                              cursor: 'pointer'
                            }}
                            title={`Chat on WhatsApp with ${t.customer_name}`}
                          >
                            <MessageCircle size={12} />
                          </button>
                        </div>
                      )}
                    </td>

                    {/* 2. Product/Service & Number of Customer Employees/Users */}
                    <td>
                      <div style={{ fontWeight: 600, fontSize: '0.84rem', color: '#1e293b' }}>
                        {t.product_service || (t.purchased_products?.[0]?.description || 'CRM Subscription')}
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                        <div style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '0.74rem',
                          color: '#4338ca',
                          background: '#e0e7ff',
                          padding: '2px 8px',
                          borderRadius: '6px',
                          fontWeight: 600
                        }}>
                          <Users size={12} />
                          <span>{t.customer_users_count || 1} Customer Users</span>
                        </div>
                        {t.selected_bundle && (
                          <div style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontSize: '0.72rem',
                            color: '#1e40af',
                            background: '#dbeafe',
                            padding: '2px 8px',
                            borderRadius: '6px',
                            fontWeight: 700
                          }}>
                            <span>Bundle: {t.selected_bundle}</span>
                          </div>
                        )}
                        {t.biometric_device_count > 0 && (
                          <div style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontSize: '0.72rem',
                            color: '#92400e',
                            background: '#fef3c7',
                            padding: '2px 8px',
                            borderRadius: '6px',
                            fontWeight: 600
                          }}>
                            <span>{t.biometric_device_count} Biometric Device{t.biometric_device_count > 1 ? 's' : ''}</span>
                          </div>
                        )}
                      </div>
                    </td>

                    {/* 3. Total Deal Amount & Payment Status */}
                    <td>
                      <div style={{ fontWeight: 800, color: '#0f172a', fontSize: '0.92rem' }}>
                        {formatINR(t.total_deal_amount || t.paid_amount)}
                      </div>
                      <div style={{ marginTop: '4px' }}>
                        {getPaymentStatusBadge(t.payment_status)}
                      </div>
                    </td>

                    {/* 4. Proforma Number & WON Date & Time */}
                    <td>
                      <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#0f766e' }}>
                        {t.proforma_number || t.quotation_number || 'PI-PENDING'}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px' }}>
                        WON: {formatLeadReceivedFull(t.won_at || t.created_at)}
                      </div>
                    </td>

                    {/* 5. Sales Employee & Assigned Support Manager */}
                    <td>
                      <div style={{ fontSize: '0.78rem', color: '#475569' }}>
                        <span style={{ color: '#94a3b8' }}>Sales:</span> {t.sales_employee_name || 'Sales Rep'}
                      </div>
                      <div style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.76rem',
                        color: '#047857',
                        background: '#d1fae5',
                        padding: '2px 8px',
                        borderRadius: '6px',
                        marginTop: '4px',
                        fontWeight: 700
                      }}>
                        <UserCheck size={12} />
                        <span>Support Manager: {t.support_manager_name || 'Kumar'}</span>
                      </div>
                    </td>

                    {/* 6. Onboarding Lifecycle */}
                    <td>
                      {getStageBadge(t.onboarding_status)}
                      {t.assigned_agent_name && (
                        <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '3px' }}>
                          Agent: {t.assigned_agent_name}
                        </div>
                      )}
                    </td>

                    {/* 7. Actions: Dedicated Call Button, WhatsApp, Manage & Reassign */}
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                        {t.phone && (
                          <button
                            type="button"
                            onClick={() => handleCallCustomer(t)}
                            style={{
                              padding: '6px 10px',
                              background: '#10b981',
                              color: '#ffffff',
                              border: 'none',
                              borderRadius: '6px',
                              fontWeight: 700,
                              fontSize: '0.8rem',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              cursor: 'pointer',
                              boxShadow: '0 1px 3px rgba(16, 185, 129, 0.3)'
                            }}
                            title={`Call Customer: ${t.customer_name} (${t.phone})`}
                          >
                            <PhoneCall size={13} />
                            <span>Call</span>
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleOpenStatusModal(t)}
                          className="btn btn-sm btn-outline flex items-center gap-1"
                          style={{ padding: '6px 12px' }}
                        >
                          Manage
                        </button>
                        {isAdmin && (
                          <button
                            type="button"
                            onClick={() => handleOpenReassignModal(t)}
                            className="btn btn-sm btn-secondary flex items-center gap-1"
                            style={{ padding: '6px 10px', fontSize: '0.75rem' }}
                            title="Admin Reassign Support Manager"
                          >
                            Reassign
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
      </div>

      {/* Support Status / Manage Modal */}
      {selectedTicket && (
        <div className="wf-modal-overlay" onClick={() => setSelectedTicket(null)}>
          <div className="wf-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '640px' }}>
            <div className="wf-modal-header">
              <div>
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <LifeBuoy size={22} className="text-blue-600" />
                  Manage Support Onboarding Assignment
                </h3>
                <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                  Deal #{selectedTicket.deal_id || selectedTicket.lead_id} &bull; Cust #{selectedTicket.customer_id} &bull; {selectedTicket.company_name || selectedTicket.customer_name}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedTicket(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleUpdateStatus}>
              <div className="wf-modal-body">
                {/* 11 Required Passed Fields Card with CALL OPTION */}
                <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '16px', marginBottom: '16px' }}>
                  <div style={{
                    fontSize: '0.76rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    color: '#475569',
                    marginBottom: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}>
                    <span>Deal & Customer Information Handed Off from Sales</span>
                    {isAdmin && (
                      <button
                        type="button"
                        onClick={() => handleOpenReassignModal(selectedTicket)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#2563eb',
                          fontWeight: 700,
                          cursor: 'pointer',
                          fontSize: '0.74rem',
                          textDecoration: 'underline'
                        }}
                      >
                        Reassign Manager
                      </button>
                    )}
                  </div>

                  {/* Prominent Call & Contact Action Strip */}
                  {selectedTicket.phone && (
                    <div style={{
                      background: '#ecfdf5',
                      border: '1px solid #a7f3d0',
                      borderRadius: '8px',
                      padding: '10px 14px',
                      marginBottom: '14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '8px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Phone size={16} style={{ color: '#059669' }} />
                        <div>
                          <span style={{ fontSize: '0.72rem', color: '#065f46', display: 'block', fontWeight: 600 }}>Customer Contact Phone</span>
                          <strong style={{ fontSize: '0.92rem', color: '#047857' }}>{selectedTicket.phone}</strong>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <button
                          type="button"
                          onClick={() => handleCallCustomer(selectedTicket)}
                          style={{
                            padding: '6px 14px',
                            background: '#059669',
                            color: '#ffffff',
                            border: 'none',
                            borderRadius: '6px',
                            fontSize: '0.82rem',
                            fontWeight: 700,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            cursor: 'pointer',
                            boxShadow: '0 2px 4px rgba(5, 150, 105, 0.25)'
                          }}
                          title="Call Customer via CRM Dialer"
                        >
                          <PhoneCall size={14} />
                          <span>Call Customer</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleWhatsAppCustomer(selectedTicket)}
                          style={{
                            padding: '6px 12px',
                            background: '#25D366',
                            color: '#ffffff',
                            border: 'none',
                            borderRadius: '6px',
                            fontSize: '0.82rem',
                            fontWeight: 700,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '5px',
                            cursor: 'pointer'
                          }}
                          title="Send WhatsApp Message"
                        >
                          <MessageCircle size={14} />
                          <span>WhatsApp</span>
                        </button>
                      </div>
                    </div>
                  )}

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px', fontSize: '0.82rem' }}>
                    <div>
                      <span style={{ color: '#64748b' }}>Company / Customer:</span>
                      <strong style={{ display: 'block', color: '#0f172a' }}>{selectedTicket.company_name || selectedTicket.customer_name}</strong>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>Customer ID & Deal ID:</span>
                      <strong style={{ display: 'block', color: '#0f172a' }}>
                        Customer #{selectedTicket.customer_id} &bull; Deal #{selectedTicket.deal_id || selectedTicket.lead_id}
                      </strong>
                    </div>

                    <div>
                      <span style={{ color: '#64748b' }}>Product / Service:</span>
                      <strong style={{ display: 'block', color: '#0f172a' }}>
                        {selectedTicket.product_service || 'CRM Subscription'}
                      </strong>
                      {selectedTicket.selected_bundle && (
                        <span style={{ display: 'inline-block', marginTop: '2px', background: '#dbeafe', color: '#1e40af', padding: '1px 6px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 700 }}>
                          Bundle: {selectedTicket.selected_bundle}
                        </span>
                      )}
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>Customer Users / Licences:</span>
                      <strong style={{ display: 'block', color: '#4338ca' }}>
                        {selectedTicket.customer_users_count || 1} Licenced Users
                      </strong>
                      {selectedTicket.biometric_device_count > 0 && (
                        <span style={{ display: 'inline-block', marginTop: '2px', background: '#fef3c7', color: '#92400e', padding: '1px 6px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>
                          {selectedTicket.biometric_device_count} Biometric Device(s)
                        </span>
                      )}
                    </div>

                    <div>
                      <span style={{ color: '#64748b' }}>Total Deal Amount:</span>
                      <strong style={{ display: 'block', color: '#16a34a', fontSize: '0.9rem' }}>
                        {formatINR(selectedTicket.total_deal_amount || selectedTicket.paid_amount)}
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>Payment Status:</span>
                      <div style={{ marginTop: '2px' }}>
                        {getPaymentStatusBadge(selectedTicket.payment_status)}
                      </div>
                    </div>

                    <div>
                      <span style={{ color: '#64748b' }}>Proforma Invoice:</span>
                      <strong style={{ display: 'block', color: '#0f766e' }}>
                        {selectedTicket.proforma_number || selectedTicket.quotation_number || 'N/A'}
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>Sales Employee:</span>
                      <strong style={{ display: 'block', color: '#0f172a' }}>
                        {selectedTicket.sales_employee_name || 'Sales Rep'}
                      </strong>
                    </div>

                    <div>
                      <span style={{ color: '#64748b' }}>Assigned Support Manager:</span>
                      <strong style={{ display: 'block', color: '#059669', fontWeight: 800 }}>
                        {selectedTicket.support_manager_name || 'Kumar'}
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>WON Date & Time (IST):</span>
                      <strong style={{ display: 'block', color: '#0f172a' }}>
                        {formatLeadReceivedFull(selectedTicket.won_at || selectedTicket.created_at)}
                      </strong>
                    </div>
                  </div>

                  {/* Deal Adjustment Reason */}
                  {selectedTicket.deal_adjustment_reason && (
                    <div style={{ marginTop: '10px', padding: '8px 12px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '6px', fontSize: '0.78rem' }}>
                      <strong style={{ color: '#92400e' }}>Deal Amount Adjustment Reason: </strong>
                      <span style={{ color: '#78350f' }}>{selectedTicket.deal_adjustment_reason}</span>
                    </div>
                  )}

                  {/* Itemized Purchased Products Snapshot */}
                  {selectedTicket.purchased_products && selectedTicket.purchased_products.length > 0 && (
                    <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid #e2e8f0' }}>
                      <span style={{ color: '#0f172a', fontWeight: 700, fontSize: '0.8rem', display: 'block', marginBottom: '6px' }}>
                        Purchased Products & Plan:
                      </span>
                      <div style={{ maxHeight: '140px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
                          <thead style={{ background: '#f8fafc', color: '#475569' }}>
                            <tr>
                              <th style={{ padding: '6px 8px', textAlign: 'left' }}>Item</th>
                              <th style={{ padding: '6px 8px', textAlign: 'center' }}>Qty</th>
                              <th style={{ padding: '6px 8px', textAlign: 'right' }}>Total</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedTicket.purchased_products.map((item, idx) => (
                              <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                <td style={{ padding: '6px 8px' }}>
                                  <div style={{ fontWeight: 600 }}>{item.name || item.description}</div>
                                  {item.bundle && <div style={{ fontSize: '0.7rem', color: '#2563eb' }}>{item.bundle}</div>}
                                </td>
                                <td style={{ padding: '6px 8px', textAlign: 'center' }}>{item.quantity || 1}</td>
                                <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 600 }}>
                                  {formatINR(item.line_total || item.total_amount)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Add-ons list */}
                  {selectedTicket.addons_summary && selectedTicket.addons_summary.length > 0 && (
                    <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {selectedTicket.addons_summary.map((add, idx) => (
                        <span key={idx} style={{ background: '#fef3c7', color: '#92400e', padding: '2px 8px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>
                          Add-on: {add.name} (Qty: {add.quantity})
                        </span>
                      ))}
                    </div>
                  )}

                  {selectedTicket.customer_requirements && (
                    <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid #e2e8f0', fontSize: '0.8rem' }}>
                      <span style={{ color: '#64748b', display: 'block', fontWeight: 600 }}>Customer Requirements & Handover Notes:</span>
                      <p style={{ margin: '4px 0 0 0', color: '#334155' }}>{selectedTicket.customer_requirements}</p>
                    </div>
                  )}
                </div>

                <div className="wf-form-group">
                  <label>Support Lifecycle Stage</label>
                  <select
                    value={statusForm.onboarding_status}
                    onChange={(e) => setStatusForm({ ...statusForm, onboarding_status: e.target.value })}
                  >
                    <option value="PENDING_ONBOARDING">1. PENDING_ONBOARDING (Awaiting contact)</option>
                    <option value="CONTACTED">2. CONTACTED (Welcome call / email sent)</option>
                    <option value="ONBOARDING_IN_PROGRESS">3. ONBOARDING_IN_PROGRESS (Account & service setup)</option>
                    <option value="COMPLETED">4. COMPLETED (Onboarding completed & activated)</option>
                  </select>
                </div>

                <div className="wf-form-group">
                  <label>Support Onboarding Notes & Milestones</label>
                  <textarea
                    rows="3"
                    placeholder="Enter onboarding details, access credentials shared, training dates..."
                    value={statusForm.support_notes}
                    onChange={(e) => setStatusForm({ ...statusForm, support_notes: e.target.value })}
                  />
                </div>
              </div>

              <div className="wf-modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setSelectedTicket(null)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary flex items-center gap-1.5"
                  disabled={updating}
                >
                  <Check size={16} />
                  <span>{updating ? 'Saving...' : 'Update Stage & Log Activity'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Admin Reassign Support Manager Modal */}
      {reassignTicket && (
        <div className="wf-modal-overlay" onClick={() => setReassignTicket(null)}>
          <div className="wf-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
            <div className="wf-modal-header">
              <div>
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ShieldCheck size={20} className="text-emerald-600" />
                  Reassign Support Manager
                </h3>
                <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                  Admin control: Reassign Deal #{reassignTicket.deal_id || reassignTicket.lead_id} ({reassignTicket.company_name || reassignTicket.customer_name})
                </span>
              </div>
              <button
                type="button"
                onClick={() => setReassignTicket(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleReassignSubmit}>
              <div className="wf-modal-body">
                <div style={{ marginBottom: '14px' }}>
                  <span style={{ fontSize: '0.8rem', color: '#64748b', display: 'block' }}>Currently Assigned:</span>
                  <strong style={{ fontSize: '0.9rem', color: '#0f172a' }}>
                    {reassignTicket.support_manager_name || 'Unassigned'}
                  </strong>
                </div>

                <div className="wf-form-group">
                  <label>Select New Support Manager <span style={{ color: '#dc2626' }}>*</span></label>
                  <select
                    value={newSupportManagerId}
                    onChange={(e) => setNewSupportManagerId(e.target.value)}
                    required
                  >
                    <option value="">-- Choose Support Manager --</option>
                    {supportManagers.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.role.replace('_', ' ')}) &ndash; {m.email || m.username}
                      </option>
                    ))}
                  </select>
                  <small style={{ color: '#64748b', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
                    The selected manager will immediately gain access to this deal and receive a high-priority notification.
                  </small>
                </div>
              </div>

              <div className="wf-modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setReassignTicket(null)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary flex items-center gap-1.5"
                  disabled={reassigning || !newSupportManagerId}
                >
                  <UserCheck size={16} />
                  <span>{reassigning ? 'Reassigning...' : 'Confirm Reassignment'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Click-to-Call IVR Modal for Support Team */}
      <IVRCallModal
        isOpen={showCallModal}
        lead={selectedCallLead}
        customerPhone={selectedCallLead?.phone}
        onClose={() => setShowCallModal(false)}
        onCallComplete={() => {
          fetchTickets();
          setShowCallModal(false);
        }}
      />
    </div>
  );
};

export default SupportQueuePage;
