import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import PingoPopupService from '../../services/pingoPopupService';
import TimePickerSelect from '../../components/Common/TimePickerSelect';
import { 
  Users, 
  Plus, 
  Search, 
  Filter, 
  Edit2, 
  Trash2, 
  UserCheck, 
  Clock, 
  Eye, 
  X, 
  AlertCircle, 
  Check,
  Send,
  Building,
  Phone,
  Mail,
  PhoneCall,
  MapPin,
  Calendar,
  MessageSquare,
  MessageCircle,
  Upload,
  Download,
  FileSpreadsheet,
  ArrowRight,
  Zap,
  ExternalLink,
  FileText,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Maximize2,
  Minimize2,
  RotateCcw,
  History,
  Layers
} from 'lucide-react';
import WhatsAppChatPanel from '../../components/WhatsApp/WhatsAppChatPanel';
import IVRCallModal from '../../components/IVR/IVRCallModal';
import QuotationModal from '../../components/Billing/QuotationModal';
import DealWonModal from './DealWonModal';
import PingoEmptyState from '../../components/Common/PingoEmptyState';
import { 
  formatDateDDMMYYYY, 
  formatTime12Hour,
  formatLeadReceived,
  formatLeadReceivedDate,
  formatLeadReceivedTime,
  formatLeadReceivedFull
} from '../../utils/dateUtils';

const STATUS_OPTIONS = [
  'NEW LEAD',
  'RE-INQUIRY',
  'CONTACTED',
  'INTERESTED',
  'QUALIFIED',
  'DEMO / MEETING',
  'PROPOSAL SENT',
  'NEGOTIATION',
  'FOLLOW-UP',
  'WON',
  'LOST'
];

const SOURCE_OPTIONS = ['META', 'WEBSITE', 'MANUAL', 'EXCEL', 'REFERRAL'];
const RATING_OPTIONS = ['Hot', 'Warm', 'Cold'];
const PRIORITY_OPTIONS = ['High', 'Medium', 'Low'];

const Leads = ({ defaultSource = '', defaultFilter = '', pageTitle = '', pageSubtitle = '' }) => {
  const navigate = useNavigate();
  const { user: currentUser } = useAuth();
  const canDeleteLead = currentUser?.role === 'ADMIN' || Boolean(currentUser?.permissions?.leads?.can_delete);
  const canAssignLead = currentUser?.role === 'ADMIN' || Boolean(currentUser?.permissions?.leads?.can_assign);
  const canEditLead = currentUser?.role === 'ADMIN' || Boolean(currentUser?.permissions?.leads?.can_edit);
  const canCallLead = currentUser?.role === 'ADMIN' || Boolean(currentUser?.permissions?.leads?.can_call);
  const canWhatsAppLead = currentUser?.role === 'ADMIN' || Boolean(currentUser?.permissions?.leads?.can_whatsapp);
  const [leads, setLeads] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);

  // Filters & Search
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState(defaultSource);
  const [sortOrder, setSortOrder] = useState('desc'); // 'desc' = newest received first, 'asc' = oldest received first
  const [receivedDateFilter, setReceivedDateFilter] = useState(''); // 'YYYY-MM-DD'

  // Source Stats Counts
  const [sourceCounts, setSourceCounts] = useState({
    allLeads: 0,
    metaLeads: 0,
    websiteLeads: 0,
    manualLeads: 0,
    excelLeads: 0,
    reinquiryLeads: 0
  });

  const [reinquiryFilter, setReinquiryFilter] = useState(false);

  const fetchSourceCounts = async () => {
    try {
      const params = {};
      if (defaultFilter === 'my-leads') {
        params.only_my = true;
      }
      const res = await API.get('/leads/stats', { params });
      if (res.data) {
        setSourceCounts({
          allLeads: res.data.allLeads ?? 0,
          metaLeads: res.data.metaLeads ?? 0,
          websiteLeads: res.data.websiteLeads ?? 0,
          manualLeads: res.data.manualLeads ?? 0,
          excelLeads: res.data.excelLeads ?? 0,
          reinquiryLeads: res.data.reinquiryLeads ?? 0
        });
      }
    } catch (e) {
      // Ignore
    }
  };

  // Sync state if defaultSource prop changes
  useEffect(() => {
    if (defaultSource) {
      setSourceFilter(defaultSource);
    }
  }, [defaultSource]);

  // Alerts
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [showDetailDrawer, setShowDetailDrawer] = useState(false);
  const [isDrawerFullScreen, setIsDrawerFullScreen] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);

  // Import State
  const [importFile, setImportFile] = useState(null);
  const [importSummary, setImportSummary] = useState(null);
  const [importing, setImporting] = useState(false);

  // Selected Lead State
  const [selectedLead, setSelectedLead] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // IVR Click-to-Call State
  const [showCallModal, setShowCallModal] = useState(false);
  const [selectedCallLead, setSelectedCallLead] = useState(null);
  const [drawerTab, setDrawerTab] = useState('overview');
  const [leadCallLogs, setLeadCallLogs] = useState([]);

  // QuoteTask Integration State
  const [creatingQuotation, setCreatingQuotation] = useState(false);
  const [syncingQuotation, setSyncingQuotation] = useState(false);
  const [quotationMessage, setQuotationMessage] = useState('');

  // Follow-up Date Prompt Modal State
  const [showFollowupPromptModal, setShowFollowupPromptModal] = useState(false);
  const [pendingFollowupLead, setPendingFollowupLead] = useState(null);
  const [pendingFollowupData, setPendingFollowupData] = useState({
    followup_date: new Date(Date.now() + 86400000).toISOString().split('T')[0],
    followup_time: '10:00 AM',
    priority: 'MEDIUM',
    notes: ''
  });

  // Deal WON & Support Manager Assignment State
  const [showDealWonModal, setShowDealWonModal] = useState(false);
  const [pendingDealWonLead, setPendingDealWonLead] = useState(null);

  const handleCreateQuoteTaskQuotation = async (lead) => {
    if (!lead) return;
    try {
      setCreatingQuotation(true);
      setError('');
      setQuotationMessage('');
      const res = await API.post(`/leads/${lead.id}/quotetask/create-quotation`, {
        notes: lead.requirement_notes,
        estimated_amount: 15000.0
      });
      if (res.data) {
        setQuotationMessage(`Quotation #${res.data.quotation_number} created successfully in QuoteTask!`);
        fetchLeads();
        setSelectedLead(prev => prev ? ({ ...prev, ...res.data }) : null);
        setTimeout(() => setQuotationMessage(''), 5000);
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to create quotation in QuoteTask.');
    } finally {
      setCreatingQuotation(false);
    }
  };

  const handleSyncQuoteTaskStatus = async (lead) => {
    if (!lead) return;
    try {
      setSyncingQuotation(true);
      setError('');
      setQuotationMessage('');
      const res = await API.post(`/leads/${lead.id}/quotetask/sync`);
      if (res.data) {
        setQuotationMessage(`Synced status: ${res.data.quotation_status}`);
        fetchLeads();
        setSelectedLead(prev => prev ? ({ ...prev, ...res.data }) : null);
        setTimeout(() => setQuotationMessage(''), 4000);
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to sync quotation status from QuoteTask.');
    } finally {
      setSyncingQuotation(false);
    }
  };

  // Native Quotation Studio Modal State for Leads
  const [showBillingModal, setShowBillingModal] = useState(false);
  const [billingInitialData, setBillingInitialData] = useState({});

  const handleOpenCreateQuotationForLead = (lead, type = 'quotation') => {
    if (!lead) return;
    setBillingInitialData({
      docType: type,
      leadId: lead.id,
      name: lead.name,
      company: lead.company,
      phone: lead.phone,
      email: lead.email,
      address: lead.location || [lead.city, lead.state].filter(Boolean).join(', '),
      state: lead.state || 'Tamil Nadu',
      notes: lead.requirement_notes || ''
    });
    setShowBillingModal(true);
  };

  const handleBillingSuccess = (newDoc) => {
    fetchLeads();
    if (selectedLead) {
      setSelectedLead(prev => prev ? ({
        ...prev,
        quotetask_quotation_id: String(newDoc.id),
        quotetask_quotation_number: newDoc.number,
        quotetask_quotation_status: newDoc.status,
        quotetask_quotation_amount: newDoc.grandTotal
      }) : null);
    }
    setQuotationMessage(`Issued ${newDoc.docType.toUpperCase()} #${newDoc.number} for Rs. ${newDoc.grandTotal.toLocaleString('en-IN')}!`);
    setTimeout(() => setQuotationMessage(''), 5000);
  };

  const handleDownloadLeadDoc = async (lead, type = 'quotation') => {
    if (!lead) return;
    try {
      const endpoint = type === 'proforma'
        ? `/leads/${lead.id}/download-proforma`
        : `/leads/${lead.id}/download-quotation`;

      const response = await API.get(endpoint, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const cleanNum = (lead.quotetask_quotation_number || `LEAD-${lead.id}`).replace(/[\\/]/g, '-').replace(/[^a-zA-Z0-9-_]/g, '');
      link.download = type === 'proforma' ? `Proforma_Invoice_${cleanNum}.pdf` : `Quotation_${cleanNum}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      PingoPopupService.triggerDownloadSuccess({
        docType: type === 'proforma' ? 'Proforma Invoice' : 'Quotation',
        reference: cleanNum,
        customMessage: `${type === 'proforma' ? 'Proforma Invoice' : 'Quotation'} PDF downloaded successfully!`
      });
    } catch (err) {
      console.error(`Failed to download ${type}`, err);
      setError(`Failed to download ${type}. Please try again.`);
    }
  };

  const fetchLeadCallLogs = async (leadId) => {
    if (!leadId) return;
    try {
      const res = await API.get(`/ivr/calls?lead_id=${leadId}`);
      setLeadCallLogs(res.data?.items || []);
    } catch (e) {
      console.error("Failed to load call logs for lead:", e);
    }
  };

  const handleTriggerCall = (leadToCall) => {
    if (window.crmDial) {
      window.crmDial(leadToCall?.phone, leadToCall);
    } else {
      setSelectedCallLead(leadToCall);
      setShowCallModal(true);
    }
  };

  // Comprehensive Form State
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    whatsapp_number: '',
    email: '',
    designation: '',

    company: '',
    industry: '',
    website: '',
    company_size: '',
    city: '',
    state: '',

    source: defaultSource || 'MANUAL',
    status: 'NEW',
    campaign_name: '',
    rating: 'Warm',
    assigned_to: '',
    priority: 'Medium',

    requirement_notes: '',

    followup_date: '',
    followup_time: '10:00 AM'
  });

  const [assigneeId, setAssigneeId] = useState('');
  const [noteText, setNoteText] = useState('');

  const fetchLeads = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const params = {};
      if (search) params.search = search;
      if (statusFilter) params.status_filter = statusFilter;

      if (reinquiryFilter) {
        params.is_reinquiry_filter = true;
      }

      const effectiveSource = sourceFilter || defaultSource;
      if (effectiveSource && !reinquiryFilter) params.source_filter = effectiveSource;

      if (sortOrder) params.sort_order = sortOrder;
      if (receivedDateFilter) params.date_filter = receivedDateFilter;

      const endpoint = defaultFilter === 'my-leads' ? '/leads/my' : '/leads/';
      const res = await API.get(endpoint, { params });
      setLeads(res.data.items);
      setTotal(res.data.total);
      window.dispatchEvent(new Event('leadStatsUpdated'));
    } catch (err) {
      if (!silent) {
        console.error(err);
        setError('Failed to fetch leads list.');
      }
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const fetchEmployees = async () => {
    try {
      const res = await API.get('/employees/?status_filter=ACTIVE');
      setEmployees(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchLeads();
    fetchEmployees();
    fetchSourceCounts();
  }, [search, statusFilter, sourceFilter, defaultSource, defaultFilter, reinquiryFilter, sortOrder, receivedDateFilter]);

  // Real-time automatic lead synchronization: poll quietly every 5 seconds so new Meta leads appear automatically
  useEffect(() => {
    const syncInterval = setInterval(() => {
      fetchLeads(true);
      fetchSourceCounts();
    }, 5000);

    return () => clearInterval(syncInterval);
  }, [search, statusFilter, sourceFilter, defaultSource, defaultFilter, reinquiryFilter, sortOrder, receivedDateFilter]);

  const handleOpenCreateModal = () => {
    setFormData({
      first_name: '',
      last_name: '',
      phone: '',
      whatsapp_number: '',
      email: '',
      designation: '',

      company: '',
      industry: '',
      website: '',
      company_size: '',
      city: '',
      state: '',

      source: 'Manual',
      status: 'NEW',
      campaign_name: '',
      rating: 'Warm',
      assigned_to: currentUser?.employee_id || '',
      priority: 'Medium',

      requirement_notes: '',

      followup_date: '',
      followup_time: '10:00 AM'
    });
    setError('');
    setShowCreateModal(true);
  };

  const handleOpenEditModal = (lead) => {
    setSelectedLead(lead);
    setFormData({
      first_name: lead.first_name || '',
      last_name: lead.last_name || '',
      phone: lead.phone || '',
      whatsapp_number: lead.whatsapp_number || '',
      email: lead.email || '',
      designation: lead.designation || '',

      company: lead.company || '',
      industry: lead.industry || '',
      website: lead.website || '',
      company_size: lead.company_size || '',
      city: lead.city || '',
      state: lead.state || '',

      source: lead.source || 'Manual',
      status: lead.status || 'NEW',
      campaign_name: lead.campaign_name || '',
      rating: lead.rating || 'Warm',
      assigned_to: lead.assigned_to || '',
      priority: lead.priority || 'Medium',

      requirement_notes: lead.requirement_notes || '',

      followup_date: lead.followup_date || '',
      followup_time: lead.followup_time || '10:00 AM'
    });
    setError('');
    setShowEditModal(true);
  };

  const handleOpenAssignModal = (lead) => {
    setSelectedLead(lead);
    setAssigneeId(lead.assigned_to || '');
    setError('');
    setShowAssignModal(true);
  };

  const handleOpenDetailDrawer = async (lead) => {
    if (!lead) return;
    if (noteText.trim()) {
      if (!window.confirm('You have an unsaved note. Are you sure you want to switch leads?')) {
        return;
      }
    }
    try {
      setSelectedLead(null); // Instantly clear previous lead data to prevent stale activity display
      setNoteText('');
      setDrawerTab('overview');
      setShowDetailDrawer(true);

      const [leadRes, actRes] = await Promise.all([
        API.get(`/leads/${lead.id}`),
        API.get('/activities', { params: { lead_id: lead.id } })
      ]);

      const leadData = leadRes.data;
      leadData.activities = actRes.data || leadData.activities || [];
      setSelectedLead(leadData);
      fetchLeadCallLogs(lead.id);
    } catch (err) {
      console.error(err);
      setError('Failed to load lead timeline details.');
    }
  };

  const handleCloseDetailDrawer = () => {
    if (noteText.trim()) {
      if (!window.confirm('You have an unsaved note. Are you sure you want to close?')) {
        return;
      }
    }
    setShowDetailDrawer(false);
  };

  // Prevent background page from scrolling while drawer is open
  useEffect(() => {
    if (showDetailDrawer) {
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = originalOverflow || 'unset';
      };
    }
  }, [showDetailDrawer]);

  // Close drawer on Escape key press
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && showDetailDrawer) {
        handleCloseDetailDrawer();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showDetailDrawer, noteText]);

  // Automatically open lead details drawer from URL search parameter (?openLeadId=123) or custom window event
  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const targetLeadId = searchParams.get('openLeadId');
    if (targetLeadId) {
      handleOpenDetailDrawer({ id: parseInt(targetLeadId, 10) });
    }

    const handleCustomOpenDrawer = (e) => {
      if (e.detail?.leadId) {
        handleOpenDetailDrawer({ id: e.detail.leadId });
      }
    };
    window.addEventListener('openLeadDrawer', handleCustomOpenDrawer);
    return () => {
      window.removeEventListener('openLeadDrawer', handleCustomOpenDrawer);
    };
  }, []);

  const handleCreateLead = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!formData.first_name || !formData.phone || !formData.source || !formData.status || !formData.assigned_to) {
      setError('First Name, Mobile Number, Source, Status, and Assign To are required.');
      return;
    }

    try {
      setSubmitting(true);
      const payload = {
        ...formData,
        name: `${formData.first_name || ''} ${formData.last_name || ''}`.trim(),
        email: formData.email && formData.email.trim() ? formData.email.trim() : null,
        whatsapp_number: formData.whatsapp_number && formData.whatsapp_number.trim() ? formData.whatsapp_number.trim() : null,
        company: formData.company && formData.company.trim() ? formData.company.trim() : null,
        industry: formData.industry && formData.industry.trim() ? formData.industry.trim() : null,
        website: formData.website && formData.website.trim() ? formData.website.trim() : null,
        city: formData.city && formData.city.trim() ? formData.city.trim() : null,
        state: formData.state && formData.state.trim() ? formData.state.trim() : null,
        designation: formData.designation && formData.designation.trim() ? formData.designation.trim() : null,
        requirement_notes: formData.requirement_notes && formData.requirement_notes.trim() ? formData.requirement_notes.trim() : null,
        assigned_to: formData.assigned_to ? parseInt(formData.assigned_to, 10) : null,
        followup_date: formData.followup_date && formData.followup_date.trim() ? formData.followup_date.trim() : null
      };

      const res = await API.post('/leads/', payload);
      if (res.data?.is_reinquiry) {
        setSuccess(`🔁 Existing customer/lead matched! Recorded as RE-INQUIRY #${res.data.reinquiry_count} (Total Enquiries: ${res.data.total_enquiries}).`);
      } else {
        setSuccess('Lead created successfully!');
      }
      setShowCreateModal(false);
      fetchLeads();
      fetchSourceCounts();
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail;
      let errMsg = 'Failed to create lead.';
      if (typeof detail === 'string') errMsg = detail;
      else if (Array.isArray(detail)) errMsg = detail.map(d => (d.loc?.[d.loc.length-1] ? `${d.loc[d.loc.length-1]}: ${d.msg || d.message}` : (d.msg || d.message || JSON.stringify(d)))).join('; ');
      else if (detail && typeof detail === 'object') errMsg = detail.msg || detail.message || JSON.stringify(detail);
      else if (err.message) errMsg = err.message;
      setError(errMsg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateLead = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      setSubmitting(true);
      const payload = {
        ...formData,
        name: `${formData.first_name || ''} ${formData.last_name || ''}`.trim(),
        email: formData.email && formData.email.trim() ? formData.email.trim() : null,
        whatsapp_number: formData.whatsapp_number && formData.whatsapp_number.trim() ? formData.whatsapp_number.trim() : null,
        company: formData.company && formData.company.trim() ? formData.company.trim() : null,
        industry: formData.industry && formData.industry.trim() ? formData.industry.trim() : null,
        website: formData.website && formData.website.trim() ? formData.website.trim() : null,
        city: formData.city && formData.city.trim() ? formData.city.trim() : null,
        state: formData.state && formData.state.trim() ? formData.state.trim() : null,
        designation: formData.designation && formData.designation.trim() ? formData.designation.trim() : null,
        requirement_notes: formData.requirement_notes && formData.requirement_notes.trim() ? formData.requirement_notes.trim() : null,
        assigned_to: formData.assigned_to ? parseInt(formData.assigned_to, 10) : null,
        followup_date: formData.followup_date && formData.followup_date.trim() ? formData.followup_date.trim() : null
      };
      await API.put(`/leads/${selectedLead.id}`, payload);
      setSuccess('Lead updated successfully!');
      setShowEditModal(false);
      fetchLeads();
      if (formData.status?.toUpperCase() === 'PROPOSAL SENT') {
        navigate(`/waquotes?create=quotation&leadId=${selectedLead.id}`);
      }
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail;
      let errMsg = 'Failed to update lead.';
      if (typeof detail === 'string') errMsg = detail;
      else if (Array.isArray(detail)) errMsg = detail.map(d => (d.loc?.[d.loc.length-1] ? `${d.loc[d.loc.length-1]}: ${d.msg || d.message}` : (d.msg || d.message || JSON.stringify(d)))).join('; ');
      else if (detail && typeof detail === 'object') errMsg = detail.msg || detail.message || JSON.stringify(detail);
      else if (err.message) errMsg = err.message;
      setError(errMsg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleAssignLead = async (e) => {
    e.preventDefault();
    if (!assigneeId) return;

    try {
      setSubmitting(true);
      await API.put(`/leads/${selectedLead.id}/assign`, { assigned_to: parseInt(assigneeId) });
      setSuccess('Lead assigned successfully!');
      setShowAssignModal(false);
      fetchLeads();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to assign lead.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatusChange = async (leadId, newStatus) => {
    // If status is changed to WON, prompt for Support Manager assignment via DealWonModal
    if (newStatus === 'WON') {
      const targetLead = leads.find(l => l.id === leadId) || (selectedLead && selectedLead.id === leadId ? selectedLead : null);
      setPendingDealWonLead(targetLead || { id: leadId, name: `Lead #${leadId}` });
      setShowDealWonModal(true);
      return;
    }

    // If status is changed to FOLLOW-UP or FOLLOW_UP, prompt for Next Follow-up Date via Modal
    if (newStatus === 'FOLLOW-UP' || newStatus === 'FOLLOW_UP') {
      const targetLead = leads.find(l => l.id === leadId) || (selectedLead && selectedLead.id === leadId ? selectedLead : null);
      const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0];
      
      setPendingFollowupLead(targetLead || { id: leadId, name: `Lead #${leadId}` });
      setPendingFollowupData({
        followup_date: targetLead?.followup_date || tomorrow,
        followup_time: targetLead?.followup_time || '10:00 AM',
        priority: targetLead?.priority === 'High' || targetLead?.priority === 'HIGH' ? 'HIGH' : (targetLead?.priority === 'Low' || targetLead?.priority === 'LOW' ? 'LOW' : 'MEDIUM'),
        notes: ''
      });
      setShowFollowupPromptModal(true);
      return;
    }

    // If status is changed to PROPOSAL SENT, automatically navigate to Quotation Creation page for this lead
    if (newStatus?.toUpperCase() === 'PROPOSAL SENT') {
      try {
        await API.put(`/leads/${leadId}/status`, { status: 'PROPOSAL SENT' });
        PingoPopupService.triggerStatusUpdate({
          module: 'Lead',
          status: 'PROPOSAL SENT',
          reference: `Lead #${leadId}`
        });
        setSuccess(`Lead #${leadId} status changed to PROPOSAL SENT. Opening Quotation Creation...`);
        fetchLeads();
        if (selectedLead && selectedLead.id === leadId) {
          setSelectedLead(prev => ({ ...prev, status: 'PROPOSAL SENT' }));
        }
        navigate(`/waquotes?create=quotation&leadId=${leadId}`);
        return;
      } catch (err) {
        console.error(err);
        setError(err.response?.data?.detail || 'Failed to update status.');
        return;
      }
    }

    try {
      await API.put(`/leads/${leadId}/status`, { status: newStatus });
      PingoPopupService.triggerStatusUpdate({
        module: 'Lead',
        status: newStatus,
        reference: `Lead #${leadId}`
      });
      setSuccess(`Lead #${leadId} status changed to ${newStatus}`);
      fetchLeads();
      if (selectedLead && selectedLead.id === leadId) {
        setSelectedLead(prev => ({ ...prev, status: newStatus }));
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to update status.');
    }
  };

  const handleConfirmFollowupSchedule = async (e) => {
    e.preventDefault();
    if (!pendingFollowupLead) return;

    if (!pendingFollowupData.followup_date) {
      setError('Please select a valid next follow-up date.');
      return;
    }

    try {
      setSubmitting(true);
      const leadId = pendingFollowupLead.id;

      // 1. Update Lead status to FOLLOW-UP and set followup_date/time on lead
      await API.put(`/leads/${leadId}/status`, { status: 'FOLLOW-UP' });
      await API.put(`/leads/${leadId}`, {
        followup_date: pendingFollowupData.followup_date,
        followup_time: pendingFollowupData.followup_time
      });

      // 2. Schedule Followup task in backend followups table
      const followupPayload = {
        lead_id: leadId,
        assigned_to: pendingFollowupLead.assigned_to || currentUser?.employee_id || 1,
        followup_date: pendingFollowupData.followup_date,
        followup_time: pendingFollowupData.followup_time || '10:00 AM',
        priority: pendingFollowupData.priority || 'MEDIUM',
        notes: pendingFollowupData.notes || 'Scheduled via status change to FOLLOW-UP',
        status: 'Pending'
      };

      await API.post('/followups/', followupPayload);

      PingoPopupService.triggerStatusUpdate({
        module: 'Lead',
        status: 'FOLLOW-UP',
        reference: `Lead #${leadId}`,
        customMessage: `Follow-up scheduled for ${formatDateDDMMYYYY(pendingFollowupData.followup_date)} at ${formatTime12Hour(pendingFollowupData.followup_time)}!`
      });

      setSuccess(`Lead status changed to FOLLOW-UP & follow-up scheduled for ${formatDateDDMMYYYY(pendingFollowupData.followup_date)} at ${formatTime12Hour(pendingFollowupData.followup_time)}!`);
      setShowFollowupPromptModal(false);
      setPendingFollowupLead(null);
      fetchLeads();
      if (selectedLead && selectedLead.id === leadId) {
        setSelectedLead(prev => ({ 
          ...prev, 
          status: 'FOLLOW-UP', 
          followup_date: pendingFollowupData.followup_date,
          followup_time: pendingFollowupData.followup_time 
        }));
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to schedule follow-up.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleConvertLead = (leadId) => {
    const targetLead = leads.find(l => l.id === leadId) || (selectedLead && selectedLead.id === leadId ? selectedLead : null);
    setPendingDealWonLead(targetLead || { id: leadId, name: `Lead #${leadId}` });
    setShowDealWonModal(true);
  };

  const handleDealWonSuccess = (data, managerName) => {
    setSuccess(`Deal WON and assigned to Support Manager – ${managerName}!`);
    fetchLeads();
    if (selectedLead && (selectedLead.id === data?.lead_id || selectedLead.id === pendingDealWonLead?.id)) {
      setSelectedLead(prev => prev ? ({ ...prev, status: 'WON' }) : null);
    }
  };

  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!noteText.trim()) return;

    try {
      setSubmitting(true);
      await API.post(`/leads/${selectedLead.id}/notes`, { note: noteText });
      const [leadRes, actRes] = await Promise.all([
        API.get(`/leads/${selectedLead.id}`),
        API.get('/activities', { params: { lead_id: selectedLead.id } })
      ]);
      const leadData = leadRes.data;
      leadData.activities = actRes.data || leadData.activities || [];
      setSelectedLead(leadData);
      setNoteText('');
      setSuccess('Note added to timeline!');
      fetchLeads();
    } catch (err) {
      console.error(err);
      setError('Failed to add note.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteLead = async (leadId) => {
    const isManager = (currentUser?.role || '').toUpperCase() === 'MANAGER';
    const confirmMsg = isManager 
      ? 'Deleting this lead requires Admin approval. Submit a delete request to Admin?' 
      : 'Are you sure you want to permanently delete this lead?';

    if (!window.confirm(confirmMsg)) return;

    try {
      const res = await API.delete(`/leads/${leadId}`);
      if (res.data?.status === 'pending_approval') {
        setSuccess(res.data.message || 'Deletion request submitted to Admin for approval.');
      } else {
        setSuccess(res.data?.message || 'Lead deleted successfully.');
      }
      fetchLeads();
      if (selectedLead?.id === leadId) {
        setShowDetailDrawer(false);
        setSelectedLead(null);
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to delete lead.');
    }
  };

  // EXCEL IMPORT HANDLERS
  const handleDownloadTemplate = async () => {
    try {
      const res = await API.get('/leads/export/template', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'Leads_Import_Template.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      PingoPopupService.triggerDownloadSuccess({
        docType: 'Excel Template',
        fileName: 'Leads_Import_Template.xlsx',
        reference: 'Template',
        customMessage: 'Leads import template downloaded successfully!'
      });
    } catch (err) {
      setError('Failed to download Excel template. Please try again.');
    }
  };

  const handleUploadExcel = async (e) => {
    e.preventDefault();
    if (!importFile) return;

    try {
      setImporting(true);
      setError('');
      const formDataFile = new FormData();
      formDataFile.append('file', importFile);

      const res = await API.post('/leads/import/excel', formDataFile, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setImportSummary(res.data);
      setSuccess(`Imported ${res.data.imported} leads successfully!`);
      fetchLeads();
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to import Excel file.');
    } finally {
      setImporting(false);
    }
  };

  const handleDownloadErrors = async () => {
    if (!importSummary || !importSummary.invalid_rows) return;

    try {
      const res = await API.post('/leads/import/download-errors', importSummary.invalid_rows, {
        responseType: 'blob'
      });

      const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Import_Errors.xlsx';
      a.click();
    } catch (err) {
      console.error(err);
      setError('Failed to download error rows.');
    }
  };

  const getStatusBadgeStyle = (status) => {
    const s = (status || '').toUpperCase();
    if (s.includes('RE-INQUIRY') || s.includes('REINQUIRY')) return { bg: 'rgba(124, 58, 237, 0.14)', color: '#7c3aed' };
    if (s.includes('NEW') || s === 'ASSIGNED') return { bg: 'rgba(59, 130, 246, 0.12)', color: '#2563eb' };
    if (s.includes('CONTACTED')) return { bg: 'rgba(14, 165, 233, 0.12)', color: '#0284c7' };
    if (s.includes('INTERESTED') && !s.includes('NOT')) return { bg: 'rgba(245, 158, 11, 0.12)', color: '#d97706' };
    if (s.includes('QUALIFIED')) return { bg: 'rgba(20, 184, 166, 0.12)', color: '#0d9488' };
    if (s.includes('DEMO') || s.includes('MEETING')) return { bg: 'rgba(99, 102, 241, 0.12)', color: '#4f46e5' };
    if (s.includes('PROPOSAL')) return { bg: 'rgba(147, 51, 234, 0.12)', color: '#9333ea' };
    if (s.includes('NEGOTIATION')) return { bg: 'rgba(234, 88, 12, 0.12)', color: '#ea580c' };
    if (s.includes('FOLLOW')) return { bg: 'rgba(219, 39, 119, 0.12)', color: '#db2777' };
    if (s.includes('WON') || s.includes('CONVERTED')) return { bg: 'rgba(16, 185, 129, 0.15)', color: '#059669' };
    if (s.includes('LOST') || s.includes('NOT')) return { bg: 'rgba(220, 38, 38, 0.12)', color: '#dc2626' };
    return { bg: '#f1f5f9', color: '#64748b' };
  };

  const getSourceBadgeStyle = (source) => {
    const srcUpper = (source || '').toUpperCase();
    if (srcUpper.includes('META')) return { bg: 'rgba(59, 130, 246, 0.12)', color: '#1d4ed8' };
    if (srcUpper.includes('WEB')) return { bg: 'rgba(16, 185, 129, 0.12)', color: '#047857' };
    if (srcUpper.includes('EXCEL')) return { bg: 'rgba(245, 158, 11, 0.12)', color: '#b45309' };
    if (srcUpper.includes('MANUAL')) return { bg: 'rgba(107, 114, 128, 0.12)', color: '#374151' };
    return { bg: '#f1f5f9', color: '#475569' };
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">{pageTitle || 'Lead Management'}</h1>
          <p className="page-subtitle">{pageSubtitle || `Track, assign, update, and convert sales leads (${total} total leads).`}</p>
        </div>
        <div className="header-actions">
          <button className="btn btn-secondary" onClick={() => navigate('/leads/create?tab=import')}>
            <Upload size={18} /> Import Leads
          </button>
          <button className="btn btn-primary" onClick={() => navigate('/leads/create')}>
            <Plus size={18} /> Create Lead
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error mb-4">
          <AlertCircle size={18} /> <span>{typeof error === 'object' ? JSON.stringify(error) : String(error)}</span>
        </div>
      )}

      {success && (
        <div className="alert alert-success mb-4" style={{ backgroundColor: 'var(--success-light)', color: 'var(--success)', border: '1px solid rgba(16,185,129,0.3)', padding: '12px', borderRadius: '8px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Check size={18} /> <span>{success}</span>
        </div>
      )}

      <div className="content-card">
        {/* SOURCE FILTER TABS BAR (Meta Ads, Website, Manual, Excel, All Leads) */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          marginBottom: '20px',
          borderBottom: '1px solid var(--border-color)',
          paddingBottom: '14px',
          overflowX: 'auto',
          scrollbarWidth: 'thin'
        }}>
          <button
            type="button"
            onClick={() => setSourceFilter('')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              borderRadius: '20px',
              border: '1px solid',
              borderColor: sourceFilter === '' ? 'var(--primary)' : 'var(--border-color)',
              backgroundColor: sourceFilter === '' ? 'var(--primary-light)' : '#f8fafc',
              color: sourceFilter === '' ? 'var(--primary)' : 'var(--text-muted)',
              fontWeight: '700',
              fontSize: '0.85rem',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              boxShadow: sourceFilter === '' ? '0 2px 8px rgba(16, 185, 129, 0.15)' : 'none',
              transition: 'all 0.2s'
            }}
          >
            All Leads
            <span style={{
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '12px',
              backgroundColor: sourceFilter === '' ? 'var(--primary)' : '#e2e8f0',
              color: sourceFilter === '' ? '#ffffff' : '#475569',
              fontWeight: '700'
            }}>
              {sourceCounts.allLeads}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setSourceFilter('META')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              borderRadius: '20px',
              border: '1px solid',
              borderColor: sourceFilter === 'META' ? '#8b5cf6' : 'var(--border-color)',
              backgroundColor: sourceFilter === 'META' ? 'rgba(139, 92, 246, 0.12)' : '#f8fafc',
              color: sourceFilter === 'META' ? '#7c3aed' : 'var(--text-muted)',
              fontWeight: '700',
              fontSize: '0.85rem',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              boxShadow: sourceFilter === 'META' ? '0 2px 8px rgba(139, 92, 246, 0.2)' : 'none',
              transition: 'all 0.2s'
            }}
          >
            Meta Ads
            <span style={{
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '12px',
              backgroundColor: sourceFilter === 'META' ? '#8b5cf6' : '#e2e8f0',
              color: sourceFilter === 'META' ? '#ffffff' : '#475569',
              fontWeight: '700'
            }}>
              {sourceCounts.metaLeads}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setSourceFilter('WEBSITE')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              borderRadius: '20px',
              border: '1px solid',
              borderColor: sourceFilter === 'WEBSITE' ? '#0d9488' : 'var(--border-color)',
              backgroundColor: sourceFilter === 'WEBSITE' ? 'rgba(20, 184, 166, 0.12)' : '#f8fafc',
              color: sourceFilter === 'WEBSITE' ? '#0f766e' : 'var(--text-muted)',
              fontWeight: '700',
              fontSize: '0.85rem',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              boxShadow: sourceFilter === 'WEBSITE' ? '0 2px 8px rgba(20, 184, 166, 0.2)' : 'none',
              transition: 'all 0.2s'
            }}
          >
            Website
            <span style={{
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '12px',
              backgroundColor: sourceFilter === 'WEBSITE' ? '#0d9488' : '#e2e8f0',
              color: sourceFilter === 'WEBSITE' ? '#ffffff' : '#475569',
              fontWeight: '700'
            }}>
              {sourceCounts.websiteLeads}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setSourceFilter('MANUAL')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              borderRadius: '20px',
              border: '1px solid',
              borderColor: sourceFilter === 'MANUAL' ? '#475569' : 'var(--border-color)',
              backgroundColor: sourceFilter === 'MANUAL' ? 'rgba(100, 116, 139, 0.12)' : '#f8fafc',
              color: sourceFilter === 'MANUAL' ? '#334155' : 'var(--text-muted)',
              fontWeight: '700',
              fontSize: '0.85rem',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              boxShadow: sourceFilter === 'MANUAL' ? '0 2px 8px rgba(100, 116, 139, 0.2)' : 'none',
              transition: 'all 0.2s'
            }}
          >
            Manual
            <span style={{
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '12px',
              backgroundColor: sourceFilter === 'MANUAL' ? '#475569' : '#e2e8f0',
              color: sourceFilter === 'MANUAL' ? '#ffffff' : '#475569',
              fontWeight: '700'
            }}>
              {sourceCounts.manualLeads}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setSourceFilter('EXCEL')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              borderRadius: '20px',
              border: '1px solid',
              borderColor: sourceFilter === 'EXCEL' ? '#d97706' : 'var(--border-color)',
              backgroundColor: sourceFilter === 'EXCEL' ? 'rgba(245, 158, 11, 0.12)' : '#f8fafc',
              color: sourceFilter === 'EXCEL' ? '#b45309' : 'var(--text-muted)',
              fontWeight: '700',
              fontSize: '0.85rem',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              boxShadow: sourceFilter === 'EXCEL' ? '0 2px 8px rgba(245, 158, 11, 0.2)' : 'none',
              transition: 'all 0.2s'
            }}
          >
            Excel
            <span style={{
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '12px',
              backgroundColor: sourceFilter === 'EXCEL' ? '#d97706' : '#e2e8f0',
              color: sourceFilter === 'EXCEL' ? '#ffffff' : '#475569',
              fontWeight: '700'
            }}>
              {sourceCounts.excelLeads}
            </span>
          </button>

          <button
            type="button"
            onClick={() => {
              setReinquiryFilter(prev => !prev);
              setSourceFilter('');
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              borderRadius: '20px',
              border: '1px solid',
              borderColor: reinquiryFilter ? '#7c3aed' : 'var(--border-color)',
              backgroundColor: reinquiryFilter ? 'rgba(124, 58, 237, 0.14)' : '#f8fafc',
              color: reinquiryFilter ? '#7c3aed' : 'var(--text-muted)',
              fontWeight: '700',
              fontSize: '0.85rem',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              marginLeft: 'auto',
              boxShadow: reinquiryFilter ? '0 2px 8px rgba(124, 58, 237, 0.25)' : 'none',
              transition: 'all 0.2s'
            }}
          >
            <RotateCcw size={14} />
            Re-Inquiries
            <span style={{
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '12px',
              backgroundColor: reinquiryFilter ? '#7c3aed' : '#e2e8f0',
              color: reinquiryFilter ? '#ffffff' : '#475569',
              fontWeight: '700'
            }}>
              {sourceCounts.reinquiryLeads ?? 0}
            </span>
          </button>
        </div>
        <div className="table-toolbar" style={{ flexWrap: 'wrap', gap: '12px' }}>
          <div className="search-box">
            <Search size={18} className="search-icon" />
            <input 
              type="text" 
              placeholder="Search leads by name, phone, email, or company..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
            <select 
              value={statusFilter} 
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ width: '150px' }}
            >
              <option value="">All Statuses</option>
              {STATUS_OPTIONS.map(st => <option key={st} value={st}>{st.replace(/_/g, ' ')}</option>)}
            </select>

            <select 
              value={sourceFilter} 
              onChange={(e) => setSourceFilter(e.target.value)}
              style={{ width: '140px' }}
            >
              <option value="">All Sources</option>
              {SOURCE_OPTIONS.map(src => <option key={src} value={src}>{src}</option>)}
            </select>

            {/* Sort by Lead Received Date/Time */}
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value)}
              style={{ width: '185px', fontWeight: '600', backgroundColor: '#f8fafc' }}
              title="Sort leads by Lead Received Date/Time"
            >
              <option value="desc">Received: Newest First ↓</option>
              <option value="asc">Received: Oldest First ↑</option>
            </select>

            {/* Filter by Lead Received Date */}
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
              <input
                type="date"
                value={receivedDateFilter}
                onChange={(e) => setReceivedDateFilter(e.target.value)}
                title="Filter leads by Received Date (Asia/Kolkata IST)"
                style={{
                  padding: '7px 10px',
                  borderRadius: '8px',
                  border: receivedDateFilter ? '1.5px solid #2563eb' : '1px solid var(--border-color)',
                  backgroundColor: receivedDateFilter ? '#eff6ff' : '#ffffff',
                  fontSize: '0.82rem',
                  outline: 'none',
                  color: 'var(--text-main)',
                  fontWeight: receivedDateFilter ? '600' : '400'
                }}
              />
              {receivedDateFilter && (
                <button
                  type="button"
                  onClick={() => setReceivedDateFilter('')}
                  style={{
                    border: '1px solid #cbd5e1',
                    background: '#f1f5f9',
                    color: '#475569',
                    padding: '6px 9px',
                    borderRadius: '6px',
                    fontSize: '0.74rem',
                    fontWeight: '700',
                    cursor: 'pointer'
                  }}
                  title="Clear Received Date filter"
                >
                  Clear Date
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th style={{ width: '70px' }}>ID</th>
                <th>Contact Name</th>
                <th>Phone</th>
                <th>Company</th>
                <th>Source</th>
                <th style={{ minWidth: '140px' }}>Status</th>
                <th>Assigned To</th>
                <th 
                  onClick={() => setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
                  style={{ cursor: 'pointer', userSelect: 'none', minWidth: '165px' }}
                  title="Click to toggle sorting: Latest Received vs Oldest Received (Asia/Kolkata IST)"
                >
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                    <span>Lead Received</span>
                    <span style={{ 
                      fontSize: '0.70rem', 
                      padding: '2px 6px', 
                      borderRadius: '4px', 
                      backgroundColor: '#eff6ff', 
                      color: '#2563eb', 
                      fontWeight: '800' 
                    }}>
                      {sortOrder === 'desc' ? '↓ Newest' : '↑ Oldest'}
                    </span>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="8" className="text-center py-4 text-muted">
                    Loading leads data...
                  </td>
                </tr>
              ) : leads.length === 0 ? (
                <tr>
                  <td colSpan="8" style={{ padding: '36px 16px', background: '#f8fafc' }}>
                    <PingoEmptyState
                      pose="playful"
                      height={120}
                      title="No Leads Found"
                      description={search || statusFilter || sourceFilter ? "No leads matched your search or filters. Try adjusting your filter settings." : "There are no leads in your pipeline yet. Start capturing conversations!"}
                      actionLabel="Create Lead"
                      onAction={() => navigate('/leads/create')}
                      actionIcon={Plus}
                      secondaryActionLabel={search || statusFilter || sourceFilter ? "Reset Filters" : null}
                      onSecondaryAction={() => {
                        setSearch('');
                        setStatusFilter('');
                        setSourceFilter('');
                      }}
                    />
                  </td>
                </tr>
              ) : (
                leads.map((lead) => {
                  const badgeStyle = getStatusBadgeStyle(lead.status);
                  const srcBadgeStyle = getSourceBadgeStyle(lead.source);
                  const isSelected = showDetailDrawer && selectedLead?.id === lead.id;
                  return (
                    <tr 
                      key={lead.id}
                      onClick={() => handleOpenDetailDrawer(lead)}
                      className={`clickable-lead-row ${isSelected ? 'row-active' : ''}`}
                      title="Click anywhere to open Lead Details & Actions"
                    >
                      <td>
                        <strong>#{lead.id}</strong>
                      </td>
                      <td>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                            <strong style={{ color: 'var(--text-main)' }}>{lead.name}</strong>
                            {lead.is_reinquiry ? (
                              <span 
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '3px',
                                  padding: '2px 7px',
                                  borderRadius: '10px',
                                  fontSize: '0.7rem',
                                  fontWeight: '800',
                                  backgroundColor: 'rgba(124, 58, 237, 0.12)',
                                  color: '#7c3aed',
                                  border: '1px solid rgba(124, 58, 237, 0.25)',
                                  whiteSpace: 'nowrap'
                                }}
                                title={`Re-Inquiry count: ${lead.reinquiry_count} | Total Enquiries: ${lead.total_enquiries || lead.reinquiry_count + 1}`}
                              >
                                <RotateCcw size={10} /> RE-INQUIRY × {lead.reinquiry_count}
                              </span>
                            ) : (
                              <span 
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  padding: '1px 5px',
                                  borderRadius: '8px',
                                  fontSize: '0.66rem',
                                  fontWeight: '700',
                                  backgroundColor: 'rgba(59, 130, 246, 0.08)',
                                  color: '#2563eb',
                                  whiteSpace: 'nowrap'
                                }}
                              >
                                NEW LEAD
                              </span>
                            )}
                          </div>
                          {lead.email && <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{lead.email}</div>}
                        </div>
                      </td>
                      <td>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontWeight: '500' }}>{lead.phone || '-'}</span>
                          {lead.phone && (
                            <button
                              type="button"
                              className="btn-table-dial"
                              onClick={(e) => {
                                e.stopPropagation();
                                if (window.crmDial) {
                                  window.crmDial(lead.phone, lead);
                                }
                              }}
                              title={`Dial ${lead.name || lead.phone}`}
                            >
                              <PhoneCall size={12} />
                            </button>
                          )}
                        </div>
                      </td>
                      <td>{lead.company || '-'}</td>
                      <td>
                        <span style={{ fontSize: '0.75rem', padding: '3px 8px', borderRadius: '6px', backgroundColor: srcBadgeStyle.bg, color: srcBadgeStyle.color, fontWeight: '600' }}>
                          {lead.source}
                        </span>
                      </td>
                      <td style={{ minWidth: '140px' }} onClick={(e) => e.stopPropagation()}>
                        <select
                          value={lead.status}
                          onChange={(e) => handleStatusChange(lead.id, e.target.value)}
                          style={{
                            padding: '5px 22px 5px 10px',
                            borderRadius: '16px',
                            fontSize: '0.78rem',
                            fontWeight: '600',
                            backgroundColor: badgeStyle.bg,
                            color: badgeStyle.color,
                            border: '1px solid rgba(0, 0, 0, 0.08)',
                            cursor: 'pointer',
                            minWidth: '130px',
                            width: '100%',
                            outline: 'none',
                            appearance: 'auto',
                            boxSizing: 'border-box'
                          }}
                        >
                          {STATUS_OPTIONS.map(st => (
                            <option key={st} value={st} style={{ backgroundColor: '#ffffff', color: '#0f172a' }}>
                              {st.replace(/_/g, ' ')}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        {lead.assigned_employee_name ? (
                          <span style={{ fontSize: '0.85rem', fontWeight: '500' }}>{lead.assigned_employee_name}</span>
                        ) : (
                          <span style={{ 
                            fontSize: '0.76rem', 
                            padding: '3px 8px', 
                            borderRadius: '12px', 
                            backgroundColor: '#fef3c7', 
                            color: '#92400e', 
                            fontWeight: '600',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}>
                            <Clock size={12} /> Unassigned (1h Timeout)
                          </span>
                        )}
                      </td>
                      <td>
                        {(() => {
                          const received = formatLeadReceived(lead.created_at);
                          const latestRec = lead.is_reinquiry && lead.latest_enquiry_date 
                            ? formatLeadReceived(lead.latest_enquiry_date) 
                            : null;
                          return (
                            <div 
                              style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}
                              title={`Lead Received: ${received.full} (Asia/Kolkata IST)`}
                            >
                              <div style={{ fontSize: '0.84rem', fontWeight: '700', color: 'var(--text-main)', whiteSpace: 'nowrap' }}>
                                {received.date}
                              </div>
                              <div style={{ fontSize: '0.76rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px', whiteSpace: 'nowrap' }}>
                                <Clock size={11} style={{ color: '#0d9488', flexShrink: 0 }} />
                                <span>{received.time}</span>
                              </div>
                              {latestRec && (
                                <div 
                                  style={{ fontSize: '0.70rem', color: '#7c3aed', fontWeight: '700', marginTop: '2px', whiteSpace: 'nowrap' }} 
                                  title={`Latest Enquiry Received: ${latestRec.full}`}
                                >
                                  Latest: {latestRec.date}, {latestRec.time}
                                </div>
                              )}
                            </div>
                          );
                        })()}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>



      {/* EDIT LEAD MODAL */}
      {showEditModal && (
        <div className="modal-backdrop" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          backdropFilter: 'blur(3px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000,
          padding: '20px'
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: '640px', maxHeight: '88vh',
            display: 'flex', flexDirection: 'column',
            boxShadow: 'var(--shadow-lg)', overflow: 'hidden'
          }}>
            <div className="modal-header" style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '20px 24px', borderBottom: '1px solid var(--border-color)'
            }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: '700' }}>Edit Lead #{selectedLead?.id}</h3>
              <button onClick={() => setShowEditModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleUpdateLead} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
              <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                  <div className="form-group">
                    <label>First Name</label>
                    <input 
                      type="text" 
                      value={formData.first_name}
                      onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Last Name</label>
                    <input 
                      type="text" 
                      value={formData.last_name}
                      onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                  <div className="form-group">
                    <label>Mobile Number</label>
                    <input 
                      type="tel" 
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Email Address</label>
                    <input 
                      type="email" 
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                  <div className="form-group">
                    <label>Company</label>
                    <input 
                      type="text" 
                      value={formData.company}
                      onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>City</label>
                    <input 
                      type="text" 
                      value={formData.city}
                      onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>Requirement / Notes</label>
                  <textarea 
                    rows="3" 
                    value={formData.requirement_notes}
                    onChange={(e) => setFormData({ ...formData, requirement_notes: e.target.value })}
                    style={{ paddingTop: '10px' }}
                  />
                </div>
              </div>

              <div className="modal-footer" style={{
                display: 'flex', justifyContent: 'flex-end', gap: '12px',
                padding: '16px 24px', borderTop: '1px solid var(--border-color)',
                backgroundColor: 'var(--bg-card)'
              }}>
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

      {/* LEAD DETAILS & ACTIONS RIGHT-SIDE DRAWER */}
      {showDetailDrawer && selectedLead && (
        <div className="lead-drawer-overlay" onClick={handleCloseDetailDrawer}>
          <div className={`lead-drawer-panel ${isDrawerFullScreen ? 'fullscreen' : ''}`} onClick={(e) => e.stopPropagation()}>
            
            {/* STICKY HEADER */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '16px 24px',
              borderBottom: '1px solid var(--border-color)',
              background: '#ffffff',
              position: 'sticky',
              top: 0,
              zIndex: 10
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h3 style={{ fontSize: '1.2rem', fontWeight: '800', margin: 0, color: 'var(--text-main)' }}>
                    Lead Details
                  </h3>
                  <span style={{
                    fontSize: '0.75rem',
                    padding: '2px 8px',
                    borderRadius: '6px',
                    backgroundColor: '#e0f2fe',
                    color: '#0369a1',
                    fontWeight: '700'
                  }}>
                    #{selectedLead.id}
                  </span>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Created {formatDateDDMMYYYY(selectedLead.created_at)}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {/* Full page expand / collapse toggle */}
                <button 
                  type="button"
                  onClick={() => setIsDrawerFullScreen(prev => !prev)} 
                  title={isDrawerFullScreen ? "Collapse to side panel" : "Expand to full page view"}
                  style={{
                    padding: '5px 10px',
                    background: isDrawerFullScreen ? '#eff6ff' : '#ffffff',
                    border: '1px solid var(--border-color)',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    color: isDrawerFullScreen ? '#2563eb' : 'var(--text-main)',
                    fontSize: '0.78rem',
                    fontWeight: '600'
                  }}
                >
                  {isDrawerFullScreen ? (
                    <>
                      <Minimize2 size={15} />
                      <span>Collapse</span>
                    </>
                  ) : (
                    <>
                      <Maximize2 size={15} />
                      <span>Full Page</span>
                    </>
                  )}
                </button>

                {/* Cycle through leads without navigating away */}
                <div style={{ display: 'inline-flex', borderRadius: '6px', overflow: 'hidden', border: '1px solid var(--border-color)' }}>
                  <button 
                    type="button"
                    title="Previous Lead"
                    disabled={leads.findIndex(l => l.id === selectedLead.id) <= 0}
                    onClick={() => {
                      const idx = leads.findIndex(l => l.id === selectedLead.id);
                      if (idx > 0) handleOpenDetailDrawer(leads[idx - 1]);
                    }}
                    style={{ padding: '4px 8px', background: '#ffffff', border: 'none', cursor: 'pointer', borderRight: '1px solid var(--border-color)', display: 'flex', alignItems: 'center' }}
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <button 
                    type="button"
                    title="Next Lead"
                    disabled={leads.findIndex(l => l.id === selectedLead.id) >= leads.length - 1}
                    onClick={() => {
                      const idx = leads.findIndex(l => l.id === selectedLead.id);
                      if (idx < leads.length - 1) handleOpenDetailDrawer(leads[idx + 1]);
                    }}
                    style={{ padding: '4px 8px', background: '#ffffff', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>

                <button 
                  type="button"
                  onClick={handleCloseDetailDrawer} 
                  title="Close Side Panel (Esc)"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '4px', display: 'flex', alignItems: 'center' }}
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* SCROLLABLE BODY */}
            <div className="lead-drawer-body">
              <div className={isDrawerFullScreen ? "lead-drawer-fullscreen-grid" : ""}>
                {/* COLUMN 1: Profile & Contact Information */}
                <div>
                  {/* Profile Card & Action Bar */}
                  <div style={{
                    background: '#ffffff',
                    border: '1px solid var(--border-color)',
                    borderRadius: '12px',
                    padding: '18px',
                    marginBottom: '16px',
                    boxShadow: 'var(--shadow-sm)'
                  }}>
                    {/* Header Row: Name & Badges */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
                      <div style={{ flex: 1, minWidth: '180px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <h2 style={{ fontSize: '1.35rem', fontWeight: '800', margin: 0, color: 'var(--text-main)' }}>
                            {selectedLead.name}
                          </h2>
                          <span style={{
                            fontSize: '0.74rem',
                            padding: '2px 7px',
                            borderRadius: '6px',
                            backgroundColor: '#f1f5f9',
                            color: '#64748b',
                            fontWeight: '700'
                          }}>
                            #{selectedLead.id}
                          </span>
                        </div>
                        {selectedLead.company && (
                          <div style={{ fontSize: '0.88rem', color: '#64748b', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '5px', marginTop: '3px' }}>
                            <Building size={14} style={{ color: '#94a3b8' }} /> {selectedLead.company}
                          </div>
                        )}
                      </div>

                      {/* Header Right Badges: Re-Inquiry Badge + Source + Interactive Status Dropdown Pill */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        {selectedLead.is_reinquiry ? (
                          <span style={{
                            fontSize: '0.74rem',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            backgroundColor: 'rgba(124, 58, 237, 0.14)',
                            color: '#7c3aed',
                            fontWeight: '800',
                            letterSpacing: '0.02em',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            border: '1px solid rgba(124, 58, 237, 0.3)'
                          }}>
                            <RotateCcw size={12} /> RE-INQUIRY × {selectedLead.reinquiry_count}
                          </span>
                        ) : (
                          <span style={{
                            fontSize: '0.74rem',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            color: '#2563eb',
                            fontWeight: '700',
                            letterSpacing: '0.02em'
                          }}>
                            NEW LEAD
                          </span>
                        )}

                        <span style={{
                          fontSize: '0.74rem',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          backgroundColor: getSourceBadgeStyle(selectedLead.source).bg,
                          color: getSourceBadgeStyle(selectedLead.source).color,
                          fontWeight: '700',
                          letterSpacing: '0.02em'
                        }}>
                          {selectedLead.source}
                        </span>

                        {/* Interactive Status Pill in Header */}
                        <div style={{ position: 'relative' }} title="Change Lead Status">
                          <select
                            value={selectedLead.status}
                            onChange={(e) => handleStatusChange(selectedLead.id, e.target.value)}
                            style={{
                              appearance: 'none',
                              WebkitAppearance: 'none',
                              padding: '4px 26px 4px 10px',
                              borderRadius: '16px',
                              fontSize: '0.74rem',
                              fontWeight: '800',
                              backgroundColor: getStatusBadgeStyle(selectedLead.status).bg,
                              color: getStatusBadgeStyle(selectedLead.status).color,
                              border: `1.5px solid ${getStatusBadgeStyle(selectedLead.status).color}40`,
                              cursor: 'pointer',
                              outline: 'none'
                            }}
                          >
                            {STATUS_OPTIONS.map(st => (
                              <option key={st} value={st} style={{ background: '#ffffff', color: '#0f172a' }}>
                                {st.replace(/_/g, ' ')}
                              </option>
                            ))}
                          </select>
                          <ChevronDown size={13} style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: getStatusBadgeStyle(selectedLead.status).color }} />
                        </div>
                      </div>
                    </div>

                    {/* DEDICATED RE-INQUIRY METRICS BANNER */}
                    {selectedLead.is_reinquiry ? (
                      <div style={{
                        marginTop: '12px',
                        marginBottom: '4px',
                        padding: '12px 14px',
                        background: 'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)',
                        border: '1.5px solid #d8b4fe',
                        borderRadius: '10px'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
                          <span style={{ fontSize: '0.82rem', fontWeight: '800', color: '#6b21a8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <RotateCcw size={13} style={{ color: '#7c3aed' }} /> RE-INQUIRY DETAILS (× {selectedLead.reinquiry_count})
                          </span>
                          <span style={{ fontSize: '0.75rem', fontWeight: '700', color: '#7c3aed', background: '#ffffff', padding: '2px 8px', borderRadius: '8px', border: '1px solid #e9d5ff' }}>
                            Total Enquiries: {selectedLead.total_enquiries || (selectedLead.reinquiry_count + 1)}
                          </span>
                        </div>

                        <div style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(auto-fit, minmax(115px, 1fr))',
                          gap: '8px',
                          fontSize: '0.78rem'
                        }}>
                          <div style={{ background: '#ffffff', padding: '7px 10px', borderRadius: '7px', border: '1px solid #e9d5ff' }}>
                            <span style={{ color: '#6b7280', fontSize: '0.7rem', display: 'block', fontWeight: '600' }}>Original Received Time</span>
                            <strong style={{ color: '#1f2937' }}>{formatLeadReceivedFull(selectedLead.first_enquiry_date || selectedLead.created_at)}</strong>
                          </div>
                          <div style={{ background: '#ffffff', padding: '7px 10px', borderRadius: '7px', border: '1px solid #e9d5ff' }}>
                            <span style={{ color: '#6b7280', fontSize: '0.7rem', display: 'block', fontWeight: '600' }}>Latest Received Time</span>
                            <strong style={{ color: '#7c3aed' }}>{formatLeadReceivedFull(selectedLead.latest_enquiry_date || selectedLead.created_at)}</strong>
                          </div>
                          <div style={{ background: '#ffffff', padding: '7px 10px', borderRadius: '7px', border: '1px solid #e9d5ff' }}>
                            <span style={{ color: '#6b7280', fontSize: '0.7rem', display: 'block', fontWeight: '600' }}>Re-Inquiry Count</span>
                            <strong style={{ color: '#1f2937' }}>{selectedLead.reinquiry_count} repeat{selectedLead.reinquiry_count === 1 ? '' : 's'}</strong>
                          </div>
                          <div style={{ background: '#ffffff', padding: '7px 10px', borderRadius: '7px', border: '1px solid #e9d5ff' }}>
                            <span style={{ color: '#6b7280', fontSize: '0.7rem', display: 'block', fontWeight: '600' }}>Total Enquiries</span>
                            <strong style={{ color: '#047857' }}>{selectedLead.total_enquiries || (selectedLead.reinquiry_count + 1)}</strong>
                          </div>
                        </div>

                        {/* Previous Sources List */}
                        <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', fontSize: '0.76rem' }}>
                          <span style={{ color: '#6b21a8', fontWeight: '700' }}>Previous Sources:</span>
                          {(selectedLead.previous_sources || selectedLead.source || '')
                            .split(',')
                            .map(s => s.trim())
                            .filter(Boolean)
                            .map((srcName, idx) => {
                              const sStyle = getSourceBadgeStyle(srcName);
                              return (
                                <span key={idx} style={{
                                  padding: '1px 7px',
                                  borderRadius: '5px',
                                  fontSize: '0.72rem',
                                  fontWeight: '700',
                                  backgroundColor: sStyle.bg,
                                  color: sStyle.color,
                                  border: '1px solid rgba(0,0,0,0.06)'
                                }}>
                                  {srcName}
                                </span>
                              );
                            })}
                          {selectedLead.latest_source && (
                            <span style={{ fontSize: '0.72rem', color: '#475569', marginLeft: 'auto' }}>
                              Latest source: <strong>{selectedLead.latest_source}</strong>
                            </span>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div style={{
                        marginTop: '10px',
                        marginBottom: '4px',
                        padding: '6px 12px',
                        background: '#f8fafc',
                        border: '1px solid var(--border-color)',
                        borderRadius: '8px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '0.78rem'
                      }}>
                        <span style={{ color: '#64748b' }}>
                          <strong style={{ color: '#2563eb' }}>NEW LEAD</strong> (Single Enquiry) • Total Enquiries: 1
                        </span>
                        <span style={{ color: '#64748b' }}>
                          Lead Received: <strong style={{ color: '#0f172a' }}>{formatLeadReceivedFull(selectedLead.created_at)}</strong> (IST)
                        </span>
                      </div>
                    )}

                    {/* Quick Contact Chips Row */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #f1f5f9', fontSize: '0.82rem' }}>
                      <a 
                        href={`tel:${selectedLead.phone}`} 
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: '#2563eb', fontWeight: '600', textDecoration: 'none' }}
                        title="Click to dial"
                      >
                        <Phone size={13} /> {selectedLead.phone}
                      </a>
                      {selectedLead.email && (
                        <a 
                          href={`mailto:${selectedLead.email}`} 
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: '#64748b', textDecoration: 'none' }}
                          title="Click to email"
                        >
                          <Mail size={13} style={{ color: '#ea580c' }} /> {selectedLead.email}
                        </a>
                      )}
                      {selectedLead.location && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#64748b' }}>
                          <MapPin size={13} style={{ color: '#dc2626' }} /> {selectedLead.location}
                        </span>
                      )}
                    </div>

                    {/* Dedicated Status Update & Pipeline Bar */}
                    <div style={{
                      marginTop: '12px',
                      padding: '12px 14px',
                      background: '#f8fafc',
                      borderRadius: '10px',
                      border: '1px solid var(--border-color)'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: '800', letterSpacing: '0.04em', color: '#64748b', display: 'flex', alignItems: 'center', gap: '5px' }}>
                          <RefreshCw size={12} /> Status Update
                        </span>
                        <span style={{ fontSize: '0.74rem', fontWeight: '700', color: getStatusBadgeStyle(selectedLead.status).color }}>
                          Current: {selectedLead.status}
                        </span>
                      </div>

                      {/* 1-Click Fast Status Pills */}
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {['NEW LEAD', 'CONTACTED', 'FOLLOW-UP', 'QUALIFIED', 'WON', 'LOST'].map(st => {
                          const isActive = selectedLead.status === st;
                          const badge = getStatusBadgeStyle(st);
                          return (
                            <button
                              key={st}
                              type="button"
                              onClick={() => handleStatusChange(selectedLead.id, st)}
                              style={{
                                fontSize: '0.72rem',
                                fontWeight: isActive ? '800' : '600',
                                padding: '4px 9px',
                                borderRadius: '6px',
                                border: isActive ? `1.5px solid ${badge.color}` : '1px solid #cbd5e1',
                                backgroundColor: isActive ? badge.bg : '#ffffff',
                                color: isActive ? badge.color : '#475569',
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                transition: 'all 0.15s ease'
                              }}
                              title={`Change status to ${st}`}
                            >
                              {isActive && <Check size={11} />}
                              {st}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* ACTION BUTTONS: Perfectly Aligned 2-Tier Grid */}
                    {/* Row 1: Primary Communications (2 Equal Columns - 50% / 50%) */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '12px' }}>
                      <button 
                        type="button" 
                        onClick={() => handleTriggerCall(selectedLead)} 
                        className="btn btn-primary" 
                        style={{ backgroundColor: '#2563eb', padding: '9px 12px', fontSize: '0.85rem', fontWeight: '600', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '8px', borderRadius: '8px' }}
                        title="Click-to-Call IVR"
                      >
                        <PhoneCall size={15} /> Call
                      </button>

                      <button 
                        type="button" 
                        onClick={() => setDrawerTab('whatsapp')} 
                        className="btn" 
                        style={{ backgroundColor: '#25d366', color: '#ffffff', border: 'none', padding: '9px 12px', fontSize: '0.85rem', fontWeight: '600', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '8px', borderRadius: '8px' }}
                        title="Open WhatsApp Chat"
                      >
                        <MessageCircle size={15} /> WhatsApp
                      </button>
                    </div>

                    {/* Row 2: Management Actions (3 Equal Columns - 33% each) */}
                    <div className="lead-drawer-action-tier2">
                      <button 
                        type="button" 
                        onClick={() => handleOpenEditModal(selectedLead)} 
                        className="btn btn-outline"
                        style={{ padding: '8px 10px', fontSize: '0.8rem', fontWeight: '600', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                        title="Edit Lead Information"
                      >
                        <Edit2 size={13} /> Edit Lead
                      </button>

                      <button 
                        type="button" 
                        onClick={() => handleOpenAssignModal(selectedLead)} 
                        className="btn btn-outline"
                        style={{ padding: '8px 10px', fontSize: '0.8rem', fontWeight: '600', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px', color: 'var(--accent)' }}
                        title="Assign / Reassign"
                      >
                        <UserCheck size={13} /> {selectedLead.assigned_to ? 'Reassign' : 'Assign'}
                      </button>

                      <button
                        type="button"
                        onClick={() => handleStatusChange(selectedLead.id, 'FOLLOW-UP')}
                        className="btn btn-outline"
                        style={{ fontSize: '0.8rem', fontWeight: '600', padding: '8px 10px', color: '#d97706', borderColor: '#fde68a', backgroundColor: '#fffbeb', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                        title="Schedule follow-up date and time"
                      >
                        <Calendar size={13} /> Follow-up
                      </button>
                    </div>

                    {/* Row 2.5: WA Quote & Invoicing Actions */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px' }}>
                      <button
                        type="button"
                        onClick={() => handleOpenCreateQuotationForLead(selectedLead, 'quotation')}
                        className="btn btn-outline"
                        style={{ fontSize: '0.8rem', fontWeight: '600', padding: '8px 10px', color: '#0f766e', borderColor: '#99f6e4', backgroundColor: '#f0fdfa', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                        title="Create Quotation in WA Quote for this lead"
                      >
                        <FileText size={13} /> + Quotation
                      </button>
                      <button
                        type="button"
                        onClick={() => handleOpenCreateQuotationForLead(selectedLead, 'proforma')}
                        className="btn btn-outline"
                        style={{ fontSize: '0.8rem', fontWeight: '600', padding: '8px 10px', color: '#7c3aed', borderColor: '#ddd6fe', backgroundColor: '#f5f3ff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                        title="Create Proforma Invoice in WA Quote for this lead"
                      >
                        <FileSpreadsheet size={13} /> + Proforma
                      </button>
                    </div>

                    {/* Row 3: Conversion & Delete Actions (Balanced 2 Columns - 50% each) */}
                    <div style={{ 
                      display: 'grid', 
                      gridTemplateColumns: canDeleteLead && (selectedLead.status !== 'WON' && selectedLead.status !== 'CONVERTED') ? '1fr 1fr' : '1fr', 
                      gap: '8px', 
                      marginTop: '8px' 
                    }}>
                      {selectedLead.status !== 'WON' && selectedLead.status !== 'CONVERTED' && (
                        <button
                          type="button"
                          onClick={() => handleConvertLead(selectedLead.id)}
                          className="btn btn-outline"
                          style={{ fontSize: '0.8rem', fontWeight: '600', padding: '8px 12px', color: '#16a34a', borderColor: '#bbf7d0', backgroundColor: '#f0fdf4', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                          title="Mark as Won and Convert to Customer"
                        >
                          <Check size={14} /> Mark Won
                        </button>
                      )}

                      {canDeleteLead && (
                        <button
                          type="button"
                          onClick={() => handleDeleteLead(selectedLead.id)}
                          className="btn btn-outline"
                          style={{ fontSize: '0.8rem', fontWeight: '600', padding: '8px 12px', color: '#dc2626', borderColor: '#fecaca', backgroundColor: '#fef2f2', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                          title="Delete Lead"
                        >
                          <Trash2 size={13} /> Delete
                        </button>
                      )}
                    </div>

                    {/* Card Footer: Assigned Rep & Quick Assignment */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginTop: '12px',
                      paddingTop: '10px',
                      borderTop: '1px solid var(--border-color)',
                      fontSize: '0.8rem'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                        <span style={{ color: '#64748b' }}>Assigned:</span>
                        <strong style={{ color: selectedLead.assigned_employee_name ? '#0f172a' : '#d97706', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                          {selectedLead.assigned_employee_name || 'Unassigned'}
                        </strong>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleOpenAssignModal(selectedLead)}
                        style={{ background: 'none', border: 'none', color: '#2563eb', fontSize: '0.78rem', fontWeight: '700', cursor: 'pointer', padding: '2px 6px', borderRadius: '4px' }}
                      >
                        Change
                      </button>
                    </div>

                  </div>

                  {/* If Fullscreen: Render Information Grid & Inquiry box in Column 1 */}
                  {isDrawerFullScreen && (
                    <>
                      {/* Detailed Information Grid */}
                      <div style={{ background: '#f8fafc', borderRadius: '12px', padding: '18px', marginBottom: '16px', border: '1px solid var(--border-color)' }}>
                        <h4 style={{ fontSize: '0.92rem', fontWeight: '800', marginBottom: '14px', color: 'var(--text-main)', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                          Prospect Details
                        </h4>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', fontSize: '0.86rem' }}>
                          <div style={{ gridColumn: 'span 2', background: '#f0fdfa', padding: '10px 14px', borderRadius: '8px', border: '1px solid #ccfbf1', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#0f766e', fontSize: '0.86rem' }}>
                              <Clock size={15} style={{ color: '#0d9488' }} />
                              <strong>Lead Received:</strong>
                              <span style={{ fontWeight: 700, color: '#134e4a' }}>
                                {formatLeadReceivedDate(selectedLead.created_at)}, {formatLeadReceivedTime(selectedLead.created_at)}
                              </span>
                              <span style={{ fontSize: '0.72rem', color: '#0d9488', fontWeight: 700 }}>(Asia/Kolkata IST)</span>
                            </div>
                            <span style={{ fontSize: '0.72rem', backgroundColor: '#e6fffa', color: '#0f766e', padding: '2px 8px', borderRadius: '12px', border: '1px solid #99f6e4', fontWeight: 700 }}>
                              Source: {selectedLead.source}
                            </span>
                          </div>
                          <div><Phone size={14} style={{ display: 'inline', marginRight: '6px', color: '#2563eb' }} /> <strong>Mobile:</strong> {selectedLead.phone}</div>
                          <div><Phone size={14} style={{ display: 'inline', marginRight: '6px', color: '#25d366' }} /> <strong>WhatsApp:</strong> {selectedLead.whatsapp_number || selectedLead.phone || '-'}</div>
                          <div><Mail size={14} style={{ display: 'inline', marginRight: '6px', color: '#ea580c' }} /> <strong>Email:</strong> {selectedLead.email || '-'}</div>
                          <div><strong>Department / Role:</strong> {selectedLead.designation || '-'}</div>
                          <div><Building size={14} style={{ display: 'inline', marginRight: '6px', color: '#475569' }} /> <strong>Company:</strong> {selectedLead.company || '-'}</div>
                          <div><strong>Team Size:</strong> {selectedLead.company_size || '-'}</div>
                          <div><strong>Industry:</strong> {selectedLead.industry || '-'}</div>
                          <div><MapPin size={14} style={{ display: 'inline', marginRight: '6px', color: '#dc2626' }} /> <strong>City/State:</strong> {selectedLead.location || [selectedLead.city, selectedLead.state].filter(Boolean).join(', ') || '-'}</div>
                          <div><strong>Source:</strong> <span style={{ fontWeight: '700', color: selectedLead.source === 'WEBSITE' ? '#047857' : '#1d4ed8' }}>{selectedLead.source}</span></div>
                          <div><strong>Rating / Priority:</strong> {selectedLead.rating} / {selectedLead.priority}</div>
                          <div><strong>Assigned To:</strong> {selectedLead.assigned_employee_name || 'Unassigned'}</div>
                          <div><strong>Lead ID:</strong> #{selectedLead.id}</div>
                          {selectedLead.followup_date && (
                            <div style={{ gridColumn: 'span 2', background: '#fffbeb', padding: '8px 12px', borderRadius: '6px', border: '1px solid #fef3c7', color: '#92400e' }}>
                              <Calendar size={14} style={{ display: 'inline', marginRight: '6px' }} />
                              <strong>Next Follow-up:</strong> {formatDateDDMMYYYY(selectedLead.followup_date)} at {selectedLead.followup_time || '10:00 AM'}
                            </div>
                          )}
                          {selectedLead.website_name && (
                            <div><strong>Website:</strong> {selectedLead.website_name}</div>
                          )}
                          {selectedLead.landing_page && (
                            <div style={{ gridColumn: 'span 2' }}>
                              <strong>Landing Page:</strong> <a href={selectedLead.landing_page} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', textDecoration: 'underline', wordBreak: 'break-all' }}>{selectedLead.landing_page}</a>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Submitted Inquiry & Requirements Box */}
                      {selectedLead.requirement_notes && (
                        <div style={{
                          background: '#eff6ff',
                          border: '1px solid #bfdbfe',
                          borderRadius: '12px',
                          padding: '16px',
                          marginBottom: '16px'
                        }}>
                          <h4 style={{ fontSize: '0.92rem', fontWeight: '800', color: '#1e40af', margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <FileText size={16} /> Submitted Inquiry & Requirements
                          </h4>
                          <div style={{ fontSize: '0.86rem', color: '#1e293b', whiteSpace: 'pre-wrap', lineHeight: '1.5', background: '#ffffff', padding: '12px', borderRadius: '8px', border: '1px solid #dbeafe' }}>
                            {selectedLead.requirement_notes}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* COLUMN 2 (or sequential in non-fullscreen): Tabs & Work Area */}
                <div>
                  {/* TABS SELECTOR */}
                  <div style={{ display: 'flex', gap: '6px', marginBottom: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
                    <button
                      type="button"
                      onClick={() => setDrawerTab('overview')}
                      className={`btn ${drawerTab === 'overview' ? 'btn-primary' : 'btn-outline'}`}
                      style={{ fontSize: '0.82rem', padding: '7px 14px', flex: 1 }}
                    >
                      <FileText size={14} /> Details & History
                    </button>
                    <button
                      type="button"
                      onClick={() => { setDrawerTab('calls'); fetchLeadCallLogs(selectedLead.id); }}
                      className={`btn ${drawerTab === 'calls' ? 'btn-primary' : 'btn-outline'}`}
                      style={{ fontSize: '0.82rem', padding: '7px 14px', flex: 1 }}
                    >
                      <PhoneCall size={14} /> Calls ({leadCallLogs.length})
                    </button>
                    <button
                      type="button"
                      onClick={() => setDrawerTab('whatsapp')}
                      className={`btn ${drawerTab === 'whatsapp' ? 'btn-primary' : 'btn-outline'}`}
                      style={{ 
                        fontSize: '0.82rem', padding: '7px 14px', flex: 1,
                        backgroundColor: drawerTab === 'whatsapp' ? '#25d366' : 'transparent', 
                        borderColor: '#25d366', 
                        color: drawerTab === 'whatsapp' ? '#ffffff' : '#15803d' 
                      }}
                    >
                      <MessageCircle size={14} /> WhatsApp
                    </button>
                  </div>

                  {/* TAB CONTENT: WHATSAPP */}
                  {drawerTab === 'whatsapp' ? (
                    <div style={{ height: isDrawerFullScreen ? 'calc(100vh - 190px)' : 'calc(100vh - 350px)', minHeight: '440px', border: '1px solid var(--border-color)', borderRadius: '12px', overflow: 'hidden' }}>
                      <WhatsAppChatPanel 
                        leadId={selectedLead.id} 
                        leadPhone={selectedLead.phone} 
                        leadName={selectedLead.name} 
                      />
                    </div>
                  ) : drawerTab === 'calls' ? (
                    /* TAB CONTENT: CALL HISTORY */
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <h4 style={{ fontSize: '0.94rem', fontWeight: 700, margin: 0 }}>Lead Call History</h4>
                        <button 
                          onClick={() => handleTriggerCall(selectedLead)} 
                          className="btn btn-primary" 
                          style={{ fontSize: '0.78rem', padding: '5px 10px', backgroundColor: '#2563eb' }}
                        >
                          <PhoneCall size={13} /> Initiate New Call
                        </button>
                      </div>

                      {leadCallLogs.length === 0 ? (
                        <p style={{ color: '#94a3b8', fontSize: '0.86rem' }}>No calls logged for this lead yet.</p>
                      ) : (
                        leadCallLogs.map((call) => (
                          <div key={call.id} style={{ background: '#f8fafc', padding: '14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                              <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#0f172a' }}>
                                {new Date(call.created_at).toLocaleString()}
                              </span>
                              <span className={`status-badge ${call.call_status.toLowerCase()}`}>
                                {call.call_status}
                              </span>
                            </div>

                            <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '6px' }}>
                              Agent: <strong>{call.employee_name || 'Agent #' + (call.employee_id || '')}</strong> ({call.from_number}) • Duration: <strong>{call.duration_seconds || 0}s</strong>
                            </div>

                            {call.recording_url && (
                              <div style={{ marginTop: '8px' }}>
                                <audio controls src={call.recording_url} style={{ width: '100%', height: '32px' }} />
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  ) : (
                    /* TAB CONTENT: OVERVIEW */
                    <>
                      {/* If NOT fullscreen: show Information Grid & Inquiry Box here inside Overview */}
                      {!isDrawerFullScreen && (
                        <>
                          <div style={{ background: '#f8fafc', borderRadius: '12px', padding: '16px', marginBottom: '16px', border: '1px solid var(--border-color)' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '0.85rem' }}>
                              <div style={{ gridColumn: 'span 2', background: '#f0fdfa', padding: '10px 12px', borderRadius: '8px', border: '1px solid #ccfbf1', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#0f766e', fontSize: '0.84rem' }}>
                                  <Clock size={14} style={{ color: '#0d9488' }} />
                                  <strong>Lead Received:</strong>
                                  <span style={{ fontWeight: 700, color: '#134e4a' }}>
                                    {formatLeadReceivedDate(selectedLead.created_at)}, {formatLeadReceivedTime(selectedLead.created_at)}
                                  </span>
                                  <span style={{ fontSize: '0.70rem', color: '#0d9488', fontWeight: 700 }}>(Asia/Kolkata IST)</span>
                                </div>
                                <span style={{ fontSize: '0.70rem', backgroundColor: '#e6fffa', color: '#0f766e', padding: '2px 8px', borderRadius: '12px', border: '1px solid #99f6e4', fontWeight: 700 }}>
                                  Source: {selectedLead.source}
                                </span>
                              </div>
                              <div><Phone size={13} style={{ display: 'inline', marginRight: '6px', color: '#2563eb' }} /> <strong>Mobile:</strong> {selectedLead.phone}</div>
                              <div><Phone size={13} style={{ display: 'inline', marginRight: '6px', color: '#25d366' }} /> <strong>WhatsApp:</strong> {selectedLead.whatsapp_number || selectedLead.phone || '-'}</div>
                              <div><Mail size={13} style={{ display: 'inline', marginRight: '6px', color: '#ea580c' }} /> <strong>Email:</strong> {selectedLead.email || '-'}</div>
                              <div><strong>Department / Role:</strong> {selectedLead.designation || '-'}</div>
                              <div><Building size={13} style={{ display: 'inline', marginRight: '6px', color: '#475569' }} /> <strong>Company:</strong> {selectedLead.company || '-'}</div>
                              <div><strong>Team Size:</strong> {selectedLead.company_size || '-'}</div>
                              <div><strong>Industry:</strong> {selectedLead.industry || '-'}</div>
                              <div><MapPin size={13} style={{ display: 'inline', marginRight: '6px', color: '#dc2626' }} /> <strong>City/State:</strong> {selectedLead.location || [selectedLead.city, selectedLead.state].filter(Boolean).join(', ') || '-'}</div>
                              <div><strong>Source:</strong> <span style={{ fontWeight: '700', color: selectedLead.source === 'WEBSITE' ? '#047857' : '#1d4ed8' }}>{selectedLead.source}</span></div>
                              <div><strong>Rating / Priority:</strong> {selectedLead.rating} / {selectedLead.priority}</div>
                              <div><strong>Assigned To:</strong> {selectedLead.assigned_employee_name || 'Unassigned'}</div>
                              <div><strong>Lead ID:</strong> #{selectedLead.id}</div>
                              {selectedLead.followup_date && (
                                <div style={{ gridColumn: 'span 2', background: '#fffbeb', padding: '6px 10px', borderRadius: '6px', border: '1px solid #fef3c7', color: '#92400e' }}>
                                  <Calendar size={13} style={{ display: 'inline', marginRight: '6px' }} />
                                  <strong>Next Follow-up:</strong> {formatDateDDMMYYYY(selectedLead.followup_date)} at {selectedLead.followup_time || '10:00 AM'}
                                </div>
                              )}
                              {selectedLead.website_name && (
                                <div><strong>Website:</strong> {selectedLead.website_name}</div>
                              )}
                              {selectedLead.landing_page && (
                                <div style={{ gridColumn: 'span 2' }}>
                                  <strong>Landing Page:</strong> <a href={selectedLead.landing_page} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', textDecoration: 'underline', wordBreak: 'break-all' }}>{selectedLead.landing_page}</a>
                                </div>
                              )}
                            </div>
                          </div>

                          {selectedLead.requirement_notes && (
                            <div style={{
                              background: '#eff6ff',
                              border: '1px solid #bfdbfe',
                              borderRadius: '12px',
                              padding: '14px',
                              marginBottom: '16px'
                            }}>
                              <h4 style={{ fontSize: '0.88rem', fontWeight: '800', color: '#1e40af', margin: '0 0 8px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <FileText size={15} /> Submitted Inquiry & Requirements
                              </h4>
                              <div style={{ fontSize: '0.84rem', color: '#1e293b', whiteSpace: 'pre-wrap', lineHeight: '1.5', background: '#ffffff', padding: '10px', borderRadius: '8px', border: '1px solid #dbeafe' }}>
                                {selectedLead.requirement_notes}
                              </div>
                            </div>
                          )}
                        </>
                      )}

                      {/* WA Quote Integration Panel */}
                      <div style={{
                        background: '#f0fdf4',
                        border: '1px solid #bbf7d0',
                        borderRadius: '12px',
                        padding: '16px',
                        marginBottom: '20px'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                          <h4 style={{ fontSize: '0.92rem', fontWeight: '800', color: '#166534', margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <FileText size={16} style={{ color: '#15803d' }} /> WA Quote Documents & Invoicing
                          </h4>
                          {selectedLead.quotetask_quotation_id && (
                            <span style={{ fontSize: '0.72rem', padding: '2px 8px', borderRadius: '10px', backgroundColor: '#16a34a', color: '#ffffff', fontWeight: '700' }}>
                              LINKED
                            </span>
                          )}
                        </div>

                        {quotationMessage && (
                          <div style={{ background: '#dcfce7', color: '#15803d', padding: '6px 10px', borderRadius: '6px', marginBottom: '10px', fontSize: '0.8rem', fontWeight: '600' }}>
                            {quotationMessage}
                          </div>
                        )}

                        {!selectedLead.quotetask_quotation_id ? (
                          <div>
                            <p style={{ fontSize: '0.8rem', color: '#374151', marginBottom: '10px' }}>
                              Draft quotations, proformas, or match with documents issued in <strong>WA Quote</strong>.
                            </p>
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
                              <button
                                type="button"
                                onClick={() => handleOpenCreateQuotationForLead(selectedLead, 'quotation')}
                                className="btn btn-primary"
                                style={{ backgroundColor: '#16a34a', borderColor: '#16a34a', display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', fontWeight: 700, padding: '7px 13px' }}
                              >
                                <FileText size={14} /> + Quotation
                              </button>
                              <button
                                type="button"
                                onClick={() => handleOpenCreateQuotationForLead(selectedLead, 'proforma')}
                                className="btn btn-primary"
                                style={{ backgroundColor: '#7c3aed', borderColor: '#7c3aed', display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', fontWeight: 700, padding: '7px 13px' }}
                              >
                                <FileSpreadsheet size={14} /> + Proforma
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDownloadLeadDoc(selectedLead, 'quotation')}
                                className="btn btn-outline"
                                style={{ color: '#16a34a', borderColor: '#bbf7d0', backgroundColor: '#f0fdf4', display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', fontWeight: 600, padding: '6px 12px' }}
                                title="Download Quotation PDF"
                              >
                                <Download size={13} /> Download Quotation
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDownloadLeadDoc(selectedLead, 'proforma')}
                                className="btn btn-outline"
                                style={{ color: '#7c3aed', borderColor: '#ddd6fe', backgroundColor: '#f5f3ff', display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', fontWeight: 600, padding: '6px 12px' }}
                                title="Download Proforma PDF"
                              >
                                <Download size={13} /> Download Proforma
                              </button>
                            </div>
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                              <button
                                type="button"
                                onClick={() => handleSyncQuoteTaskStatus(selectedLead)}
                                disabled={syncingQuotation}
                                className="btn btn-outline"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', padding: '5px 10px', backgroundColor: '#ffffff' }}
                              >
                                <RefreshCw size={12} className={syncingQuotation ? 'spin' : ''} />
                                <span>{syncingQuotation ? 'Searching...' : 'Sync from WA Quote'}</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => navigate(`/waquotes?q=${encodeURIComponent(selectedLead.phone || selectedLead.name || '')}`)}
                                className="btn btn-outline"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', padding: '5px 10px', backgroundColor: '#ffffff' }}
                              >
                                <ExternalLink size={12} /> View All Quotes
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px', fontSize: '0.82rem', marginBottom: '12px' }}>
                              <div>Doc: <strong>#{selectedLead.quotetask_quotation_number || selectedLead.quotetask_quotation_id}</strong></div>
                              <div>
                                Status: {' '}
                                <span style={{
                                  fontSize: '0.72rem',
                                  padding: '2px 6px',
                                  borderRadius: '8px',
                                  backgroundColor: selectedLead.quotetask_quotation_status === 'APPROVED' || selectedLead.quotetask_quotation_status === 'ISSUED' ? '#dcfce7' : '#e0f2fe',
                                  color: selectedLead.quotetask_quotation_status === 'APPROVED' || selectedLead.quotetask_quotation_status === 'ISSUED' ? '#15803d' : '#0369a1',
                                  fontWeight: '700'
                                }}>
                                  {selectedLead.quotetask_quotation_status || 'ISSUED'}
                                </span>
                              </div>
                              <div>Total: <strong>₹{(selectedLead.quotetask_quotation_amount || 0).toLocaleString()}</strong></div>
                              <div>Payment: <strong style={{ color: selectedLead.quotetask_po_status === 'PAID' ? '#16a34a' : '#ea580c' }}>{selectedLead.quotetask_po_status || 'UNPAID'}</strong></div>
                            </div>

                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
                              <button
                                type="button"
                                onClick={() => handleOpenCreateQuotationForLead(selectedLead, 'quotation')}
                                className="btn btn-primary"
                                style={{ backgroundColor: '#16a34a', borderColor: '#16a34a', display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', fontWeight: 600, padding: '6px 12px' }}
                              >
                                <FileText size={13} /> + New Quote
                              </button>
                              <button
                                type="button"
                                onClick={() => handleOpenCreateQuotationForLead(selectedLead, 'proforma')}
                                className="btn btn-primary"
                                style={{ backgroundColor: '#7c3aed', borderColor: '#7c3aed', display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', fontWeight: 600, padding: '6px 12px' }}
                              >
                                <FileSpreadsheet size={13} /> + New Proforma
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDownloadLeadDoc(selectedLead, 'quotation')}
                                className="btn btn-outline"
                                style={{ color: '#16a34a', borderColor: '#bbf7d0', backgroundColor: '#f0fdf4', display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', fontWeight: 600, padding: '6px 12px' }}
                                title="Download Quotation PDF"
                              >
                                <Download size={13} /> Download Quotation
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDownloadLeadDoc(selectedLead, 'proforma')}
                                className="btn btn-outline"
                                style={{ color: '#7c3aed', borderColor: '#ddd6fe', backgroundColor: '#f5f3ff', display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', fontWeight: 600, padding: '6px 12px' }}
                                title="Download Proforma PDF"
                              >
                                <Download size={13} /> Download Proforma
                              </button>
                            </div>

                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                              <button
                                type="button"
                                onClick={() => navigate(`/waquotes?q=${encodeURIComponent(selectedLead.phone || selectedLead.name || '')}`)}
                                className="btn btn-outline"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', padding: '6px 12px', backgroundColor: '#ffffff' }}
                              >
                                <ExternalLink size={13} /> View in WA Quotes
                              </button>

                              <button
                                type="button"
                                onClick={() => handleSyncQuoteTaskStatus(selectedLead)}
                                disabled={syncingQuotation}
                                className="btn btn-outline"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', padding: '6px 12px', backgroundColor: '#ffffff' }}
                              >
                                <RefreshCw size={13} className={syncingQuotation ? 'spin' : ''} />
                                <span>{syncingQuotation ? 'Syncing...' : 'Sync Status'}</span>
                              </button>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Note Input Box */}
                      <div style={{ marginBottom: '22px' }}>
                        <h4 style={{ fontSize: '0.92rem', fontWeight: '700', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <MessageSquare size={16} /> Add Follow-up Note
                        </h4>
                        <form onSubmit={handleAddNote} style={{ display: 'flex', gap: '8px' }}>
                          <input 
                            type="text" 
                            placeholder="Type a follow-up note or call summary..." 
                            value={noteText}
                            onChange={(e) => setNoteText(e.target.value)}
                            style={{ flex: 1, fontSize: '0.85rem' }}
                          />
                          <button type="submit" className="btn btn-primary" disabled={submitting || !noteText.trim()}>
                            <Send size={15} />
                          </button>
                        </form>
                      </div>

                      {/* Multi-Enquiry History Card */}
                      {selectedLead.enquiries && selectedLead.enquiries.length > 0 && (
                        <div style={{
                          background: '#ffffff',
                          border: '1px solid var(--border-color)',
                          borderRadius: '12px',
                          padding: '16px',
                          marginBottom: '22px',
                          boxShadow: 'var(--shadow-sm)'
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '6px' }}>
                            <h4 style={{ fontSize: '0.92rem', fontWeight: '800', margin: 0, display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-main)' }}>
                              <History size={16} style={{ color: '#7c3aed' }} /> Complete Enquiry History ({selectedLead.total_enquiries || selectedLead.enquiries.length})
                            </h4>
                            {selectedLead.is_reinquiry && (
                              <span style={{ fontSize: '0.72rem', padding: '2px 8px', borderRadius: '10px', backgroundColor: '#f3e8ff', color: '#7c3aed', fontWeight: '700' }}>
                                {selectedLead.reinquiry_count} Re-Inquir{selectedLead.reinquiry_count === 1 ? 'y' : 'ies'} Linked
                              </span>
                            )}
                          </div>

                          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {selectedLead.enquiries.map((enq, idx) => {
                              const isRe = enq.enquiry_type === 'RE-INQUIRY' || enq.enquiry_number > 1;
                              const sStyle = getSourceBadgeStyle(enq.source);
                              return (
                                <div key={enq.id || idx} style={{
                                  background: isRe ? 'rgba(124, 58, 237, 0.04)' : '#f8fafc',
                                  border: `1px solid ${isRe ? '#e9d5ff' : '#e2e8f0'}`,
                                  borderRadius: '8px',
                                  padding: '12px 14px'
                                }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', flexWrap: 'wrap', gap: '6px' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                      <span style={{
                                        fontSize: '0.72rem',
                                        fontWeight: '800',
                                        padding: '2px 8px',
                                        borderRadius: '10px',
                                        backgroundColor: isRe ? '#7c3aed' : '#2563eb',
                                        color: '#ffffff'
                                      }}>
                                        Enquiry #{enq.enquiry_number}
                                      </span>
                                      <span style={{
                                        fontSize: '0.72rem',
                                        fontWeight: '700',
                                        padding: '2px 7px',
                                        borderRadius: '6px',
                                        backgroundColor: sStyle.bg,
                                        color: sStyle.color
                                      }}>
                                        {enq.source}
                                      </span>
                                      {isRe && (
                                        <span style={{ fontSize: '0.7rem', color: '#7c3aed', fontWeight: '700' }}>
                                          • RE-INQUIRY
                                        </span>
                                      )}
                                    </div>
                                    <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                                      {new Date(enq.created_at).toLocaleString()}
                                    </span>
                                  </div>

                                  {enq.campaign_name && (
                                    <div style={{ fontSize: '0.78rem', color: '#475569', marginBottom: '4px' }}>
                                      Campaign: <strong>{enq.campaign_name}</strong>
                                    </div>
                                  )}
                                  {enq.website_name && (
                                    <div style={{ fontSize: '0.78rem', color: '#475569', marginBottom: '4px' }}>
                                      Website: <strong>{enq.website_name}</strong>
                                      {enq.landing_page && <span> • <a href={enq.landing_page} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb' }}>{enq.landing_page}</a></span>}
                                    </div>
                                  )}
                                  {enq.requirement_notes && (
                                    <div style={{ fontSize: '0.8rem', color: '#1e293b', background: '#ffffff', padding: '6px 10px', borderRadius: '6px', border: '1px solid #e2e8f0', marginTop: '6px', whiteSpace: 'pre-wrap' }}>
                                      {enq.requirement_notes}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Activity History Timeline */}
                      <div style={{ marginBottom: '24px' }}>
                        <h4 style={{ fontSize: '0.92rem', fontWeight: '700', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Clock size={16} /> Activity & Status History
                        </h4>

                        <div className="timeline" style={{ borderLeft: '2px solid var(--border-color)', paddingLeft: '18px', marginLeft: '6px' }}>
                          {selectedLead.activities.length === 0 ? (
                            <p className="text-muted" style={{ fontSize: '0.84rem' }}>No activity logged yet.</p>
                          ) : (
                            selectedLead.activities.map((act) => {
                              const isReinquiry = act.activity_type === 'RE_INQUIRY' || (act.description || '').includes('RE-INQUIRY');
                              return (
                                <div key={act.id} style={{ 
                                  position: 'relative', 
                                  marginBottom: '16px',
                                  backgroundColor: isReinquiry ? 'rgba(124, 58, 237, 0.05)' : 'transparent',
                                  padding: isReinquiry ? '8px 12px' : '0',
                                  borderRadius: isReinquiry ? '8px' : '0',
                                  border: isReinquiry ? '1px solid rgba(124, 58, 237, 0.2)' : 'none'
                                }}>
                                  <div style={{
                                    position: 'absolute', 
                                    left: isReinquiry ? '-31px' : '-25px', 
                                    top: isReinquiry ? '8px' : '2px',
                                    width: isReinquiry ? '12px' : '10px', 
                                    height: isReinquiry ? '12px' : '10px', 
                                    borderRadius: '50%',
                                    backgroundColor: isReinquiry ? '#7c3aed' : 'var(--primary)',
                                    boxShadow: isReinquiry ? '0 0 0 3px rgba(124, 58, 237, 0.25)' : 'none'
                                  }}></div>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                                    {isReinquiry && (
                                      <span style={{
                                        fontSize: '0.68rem',
                                        fontWeight: '800',
                                        padding: '1px 6px',
                                        borderRadius: '4px',
                                        backgroundColor: '#7c3aed',
                                        color: '#ffffff'
                                      }}>
                                        RE-INQUIRY
                                      </span>
                                    )}
                                    <span style={{ fontSize: '0.85rem', fontWeight: isReinquiry ? '700' : '600', color: isReinquiry ? '#5b21b6' : 'var(--text-main)' }}>
                                      {act.description}
                                    </span>
                                  </div>
                                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                                    by {act.performed_by_name} • {new Date(act.created_at).toLocaleString()}
                                  </div>
                                </div>
                              );
                            })
                          )}
                        </div>
                      </div>

                      {/* Lead Assignment History */}
                      <div>
                        <h4 style={{ fontSize: '0.92rem', fontWeight: '700', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <UserCheck size={16} /> Assignment Audit History
                        </h4>

                        {(!selectedLead.assignments || selectedLead.assignments.length === 0) ? (
                          <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-color)', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                            No assignment history records found. Lead is currently unassigned (queued for 1-hour auto-assignment timeout).
                          </div>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {selectedLead.assignments.map((asgn) => {
                              const isAuto = asgn.assignment_method === 'AUTOMATIC';
                              return (
                                <div key={asgn.id} style={{
                                  background: isAuto ? '#f0fdf4' : '#f8fafc',
                                  border: `1px solid ${isAuto ? '#bbf7d0' : '#e2e8f0'}`,
                                  borderRadius: '8px',
                                  padding: '10px 14px'
                                }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                                    <span style={{ fontSize: '0.84rem', fontWeight: '700', color: '#0f172a' }}>
                                      Assigned to {asgn.assigned_to_name}
                                    </span>
                                    <span style={{
                                      fontSize: '0.7rem',
                                      padding: '2px 6px',
                                      borderRadius: '10px',
                                      backgroundColor: isAuto ? '#22c55e' : '#3b82f6',
                                      color: '#ffffff',
                                      fontWeight: '700'
                                    }}>
                                      {isAuto ? 'AUTOMATIC' : 'MANUAL'}
                                    </span>
                                  </div>
                                  <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                                    Assigned by: <strong>{asgn.assigned_by_name}</strong> • {new Date(asgn.assigned_at).toLocaleString()}
                                  </div>
                                  {asgn.notes && (
                                    <div style={{ fontSize: '0.75rem', color: '#475569', marginTop: '3px', fontStyle: 'italic' }}>
                                      {asgn.notes}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* EXCEL IMPORT MODAL */}
      {showImportModal && (
        <div className="modal-backdrop" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          backdropFilter: 'blur(3px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: '560px', padding: '28px',
            boxShadow: 'var(--shadow-lg)'
          }}>
            <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileSpreadsheet size={22} className="text-primary" /> Import Leads from Excel (.xlsx)
              </h3>
              <button onClick={() => setShowImportModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ background: '#f8fafc', padding: '14px', borderRadius: '8px', marginBottom: '20px', fontSize: '0.85rem' }}>
              <p style={{ marginBottom: '8px', fontWeight: '600' }}>1. Download standard template format:</p>
              <button onClick={handleDownloadTemplate} className="btn btn-outline" style={{ padding: '6px 12px', fontSize: '0.82rem' }}>
                <Download size={15} /> Download Excel Template
              </button>
            </div>

            <form onSubmit={handleUploadExcel}>
              <div className="form-group">
                <label>2. Choose .xlsx Excel File *</label>
                <input 
                  type="file" 
                  accept=".xlsx, .xls"
                  required 
                  onChange={(e) => setImportFile(e.target.files[0])}
                  style={{ paddingTop: '10px' }}
                />
              </div>

              {importSummary && (
                <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid var(--border-color)' }}>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: '700', marginBottom: '10px' }}>Import Summary:</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.88rem' }}>
                    <div>Total Rows: <strong>{importSummary.total_rows}</strong></div>
                    <div style={{ color: 'var(--success)' }}>Imported Valid: <strong>{importSummary.imported}</strong></div>
                    <div style={{ color: 'var(--warning)' }}>Duplicates Detected: <strong>{importSummary.duplicates}</strong></div>
                    <div style={{ color: 'var(--danger)' }}>Invalid Rows: <strong>{importSummary.invalid}</strong></div>
                  </div>

                  {importSummary.invalid_rows && importSummary.invalid_rows.length > 0 && (
                    <div style={{ marginTop: '14px' }}>
                      <button type="button" onClick={handleDownloadErrors} className="btn btn-outline" style={{ color: 'var(--danger)', borderColor: 'rgba(239, 68, 68, 0.4)', padding: '6px 12px', fontSize: '0.82rem' }}>
                        <Download size={14} /> Download Invalid/Error Rows Excel
                      </button>
                    </div>
                  )}
                </div>
              )}

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowImportModal(false)}>
                  Close
                </button>
                <button type="submit" className="btn btn-primary" disabled={importing || !importFile}>
                  {importing ? 'Processing & Validating...' : 'Upload & Import Leads'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* NEXT FOLLOW-UP DATE PROMPT MODAL */}
      {showFollowupPromptModal && pendingFollowupLead && (
        <div className="modal-backdrop" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.65)',
          backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000, padding: '20px'
        }}>
          <div className="modal-content" style={{
            backgroundColor: '#ffffff',
            borderRadius: '18px',
            width: '100%', maxWidth: '480px', padding: '24px',
            boxShadow: '0 20px 40px rgba(0,0,0,0.25)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', borderBottom: '1px solid #e2e8f0', paddingBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '40px', height: '40px', borderRadius: '10px', backgroundColor: '#fef3c7', color: '#b45309', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Calendar size={22} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>Schedule Next Follow-up</h3>
                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Lead: {pendingFollowupLead.name || `#${pendingFollowupLead.id}`}</span>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => { setShowFollowupPromptModal(false); setPendingFollowupLead(null); fetchLeads(); }} 
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleConfirmFollowupSchedule}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                <div className="form-group">
                  <label style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px', display: 'block' }}>
                    Next Follow-up Date *
                  </label>
                  <input 
                    type="date" 
                    required 
                    value={pendingFollowupData.followup_date}
                    onChange={(e) => setPendingFollowupData({ ...pendingFollowupData, followup_date: e.target.value })}
                    style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                  />
                </div>

                <div className="form-group">
                  <label style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px', display: 'block' }}>
                    Time
                  </label>
                  <TimePickerSelect 
                    value={pendingFollowupData.followup_time}
                    onChange={(e) => setPendingFollowupData({ ...pendingFollowupData, followup_time: e.target.value })}
                    style={{ padding: '10px' }}
                  />
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: '16px' }}>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px', display: 'block' }}>
                  Follow-up Priority
                </label>
                <select 
                  value={pendingFollowupData.priority}
                  onChange={(e) => setPendingFollowupData({ ...pendingFollowupData, priority: e.target.value })}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                >
                  <option value="HIGH">HIGH</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="LOW">LOW</option>
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: '20px' }}>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px', display: 'block' }}>
                  Follow-up Agenda / Notes (Optional)
                </label>
                <textarea 
                  rows={3}
                  placeholder="e.g. Call client back to discuss proposal and pricing options..."
                  value={pendingFollowupData.notes}
                  onChange={(e) => setPendingFollowupData({ ...pendingFollowupData, notes: e.target.value })}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button 
                  type="button" 
                  onClick={() => { setShowFollowupPromptModal(false); setPendingFollowupLead(null); fetchLeads(); }} 
                  className="btn btn-outline"
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  disabled={submitting || !pendingFollowupData.followup_date}
                  style={{ backgroundColor: '#2563eb', color: '#ffffff', fontWeight: 700, padding: '10px 18px', borderRadius: '8px' }}
                >
                  {submitting ? 'Saving...' : 'Set Follow-up & Schedule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ASSIGN LEAD MODAL - Rendered at top stack after drawer */}
      {showAssignModal && (
        <div className="modal-backdrop" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.65)',
          backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 99999,
          padding: '20px'
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'var(--bg-card, #ffffff)',
            border: '1px solid var(--border-color)',
            borderRadius: '16px',
            width: '100%', maxWidth: '440px', padding: '28px',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
            position: 'relative',
            zIndex: 100000
          }}>
            <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-main, #0f172a)' }}>Assign Lead #{selectedLead?.id}</h3>
              <button onClick={() => setShowAssignModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleAssignLead}>
              <div className="form-group" style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-muted)' }}>Select Sales Representative</label>
                <select 
                  value={assigneeId} 
                  onChange={(e) => setAssigneeId(e.target.value)}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border-color)' }}
                >
                  <option value="">Select Employee...</option>
                  {employees.map(emp => (
                    <option key={emp.id} value={emp.id}>{emp.name} ({emp.role})</option>
                  ))}
                </select>
              </div>

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowAssignModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting || !assigneeId}>
                  {submitting ? 'Assigning...' : 'Assign Lead'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Click-to-Call IVR Modal */}
      <IVRCallModal 
        isOpen={showCallModal}
        lead={selectedCallLead}
        onClose={() => setShowCallModal(false)}
        onCallComplete={() => {
          fetchLeads();
          if (selectedLead) fetchLeadCallLogs(selectedLead.id);
        }}
      />

      {/* Native Quotation Studio Modal */}
      <QuotationModal
        isOpen={showBillingModal}
        onClose={() => setShowBillingModal(false)}
        initialData={billingInitialData}
        onSuccess={handleBillingSuccess}
      />

      {/* Deal WON & Support Manager Assignment Modal */}
      <DealWonModal
        isOpen={showDealWonModal}
        onClose={() => {
          setShowDealWonModal(false);
          setPendingDealWonLead(null);
        }}
        lead={pendingDealWonLead}
        onSuccess={handleDealWonSuccess}
      />
    </div>
  );
};

export default Leads;
