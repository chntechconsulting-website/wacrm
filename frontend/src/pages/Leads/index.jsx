import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import PingoPopupService from '../../services/pingoPopupService';
import TimePickerSelect from '../../components/Common/TimePickerSelect';
import { probeAudioDuration, rewindAfterProbe } from '../../utils/audioUtils';
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
const QuotationModal = React.lazy(() => import('../../components/Billing/QuotationModal'));
import DealWonModal from './DealWonModal';import PingoEmptyState from '../../components/Common/PingoEmptyState';
import { 
  formatDateDDMMYYYY, 
  formatTime12Hour,
  formatLeadReceived,
  formatLeadReceivedDate,
  formatLeadReceivedTime,
  formatLeadReceivedFull
} from '../../utils/dateUtils';

// ---------------------------------------------------------------------------
// Trial date helpers. Everything is built from the *local* calendar so "today"
// is never shifted by a day for IST users (Date.toISOString() is UTC-based).
// Date and duration stay in sync: a new duration recalculates the end date, a
// new start date re-anchors the same duration, and a new end date recalculates
// the duration. All three are editable in the Set Trial Period modal.
// ---------------------------------------------------------------------------
const toISODate = (date) => {
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return '';
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

const addDaysToISO = (isoDate, days) => {
  if (!isoDate || !Number.isFinite(days)) return '';
  const parts = String(isoDate).split('-').map(Number);
  if (parts.length !== 3 || parts.some(n => Number.isNaN(n))) return '';
  const d = new Date(parts[0], parts[1] - 1, parts[2] + days);
  return toISODate(d);
};

const diffDaysISO = (fromISO, toISO) => {
  if (!fromISO || !toISO) return NaN;
  const [fy, fm, fd] = String(fromISO).split('-').map(Number);
  const [ty, tm, td] = String(toISO).split('-').map(Number);
  if ([fy, fm, fd, ty, tm, td].some(n => Number.isNaN(n))) return NaN;
  const start = new Date(fy, fm - 1, fd);
  const end = new Date(ty, tm - 1, td);
  return Math.round((end - start) / 86400000);
};

const DEFAULT_TRIAL_DURATION_DAYS = 14;

// Human labels for the backend-derived Trial status projection.
const TRIAL_STATUS_LABELS = {
  TRIAL_ACTIVE: 'Active',
  TRIAL_EXPIRING_SOON: 'Expiring Soon',
  TRIAL_EXPIRED: 'Expired',
  TRIAL_CONVERTED: 'Converted',
  TRIAL_CANCELLED: 'Cancelled'
};

const trialStatusLabel = (lead) => {
  if (lead?.trial_status) {
    return TRIAL_STATUS_LABELS[lead.trial_status] || String(lead.trial_status).replace(/_/g, ' ');
  }
  if (lead?.is_trial_expired) return 'Expired';
  return '';
};

// Labels the trial Support assignment using the role that is actually stored
// on the employee record. New selections are validated as SUPPORT_MANAGER by
// the backend, while older rows can still hold a Support Executive, so the
// label follows the stored role instead of assuming one.
const trialSupportAssigneeLabel = (lead) => {
  if (!lead?.trial_support_employee_id) return 'Support';
  const role = String(lead.trial_support_employee_role || '').toUpperCase();
  return role === 'SUPPORT_MANAGER' ? 'Support Manager' : 'Support';
};

const STATUS_OPTIONS = [
  'NEW LEAD',
  'RE-INQUIRY',
  'CONTACTED',
  'INTERESTED',
  'TRIAL',
  'RNR',
  'DEMO / MEETING',
  'PROPOSAL SENT',
  'NEGOTIATION',
  'FOLLOW-UP',
  'WON',
  'CONVERTED_TO_SUPPORT',
  'LOST',
  'JUNK'
];

const SOURCE_OPTIONS = ['META', 'WHATSAPP_ADS', 'WEBSITE', 'MANUAL', 'EXCEL', 'REFERRAL'];
const RATING_OPTIONS = ['Hot', 'Warm', 'Cold'];
const PRIORITY_OPTIONS = ['High', 'Medium', 'Low'];

const normalizeLeadStatusValue = (value) =>
  String(value || '').trim().toUpperCase().replace(/-/g, '_').replace(/\s+/g, '_');

// Server-side pagination window for the Leads table
const LEADS_PAGE_SIZE = 150;

// Page numbers shown in the pagination bar, with ellipsis gaps
const buildPageList = (current, totalPages) => {
  if (!totalPages || totalPages <= 0) return [];
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }
  const pages = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(totalPages - 1, current + 1);
  if (start > 2) pages.push('...');
  for (let i = start; i <= end; i++) pages.push(i);
  if (end < totalPages - 1) pages.push('...');
  pages.push(totalPages);
  return pages;
};

const Leads = ({ defaultSource = '', defaultFilter = '', pageTitle = '', pageSubtitle = '' }) => {
  const navigate = useNavigate();
  const { user: currentUser } = useAuth();
  const canDeleteLead = currentUser?.role === 'ADMIN' || Boolean(currentUser?.permissions?.leads?.can_delete);
  const canAssignLead = currentUser?.role === 'ADMIN' || Boolean(currentUser?.permissions?.leads?.can_assign);
  const canEditLead = currentUser?.role === 'ADMIN' || Boolean(currentUser?.permissions?.leads?.can_edit);
  const canCallLead = currentUser?.role === 'ADMIN' || Boolean(currentUser?.permissions?.leads?.can_call);
  const canWhatsAppLead = currentUser?.role === 'ADMIN' || Boolean(currentUser?.permissions?.leads?.can_whatsapp);
  const normalizedRole = (currentUser?.role || '').toUpperCase();
  const canConvertToSupport = ['ADMIN', 'SALES_MANAGER', 'MANAGER'].includes(normalizedRole);
  const canAssignSupport = ['ADMIN', 'SUPPORT_MANAGER'].includes(normalizedRole);
  const [leads, setLeads] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1); // 1-based page number (server-side pagination)
  const [totalPages, setTotalPages] = useState(1);

  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const initialStatusFromUrl = searchParams.get('status') || searchParams.get('status_filter') || '';
  const initialSourceFromUrl = searchParams.get('source') || searchParams.get('source_filter') || defaultSource || '';
  const initialAssignedToFromUrl = searchParams.get('assigned_to') || searchParams.get('assigned_to_filter') || '';

  // Filters & Search
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState(initialStatusFromUrl);
  const [sourceFilter, setSourceFilter] = useState(initialSourceFromUrl);
  const [productFilter, setProductFilter] = useState('');
  const [assignedToFilter, setAssignedToFilter] = useState(initialAssignedToFromUrl);
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
  const latestLeadReqIdRef = useRef(0);
  const isInitialMount = useRef(true);
  const filtersRef = useRef({});

  // Synchronize ref on every render so intervals and callbacks always read active filters
  filtersRef.current = {
    search: debouncedSearch,
    statusFilter,
    sourceFilter,
    productFilter,
    assignedToFilter,
    sortOrder,
    receivedDateFilter,
    reinquiryFilter,
    defaultSource,
    defaultFilter,
    page,
    pageSize: LEADS_PAGE_SIZE
  };

  // Debounce typing so a search term issues one request instead of one per key.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Stable signature of the active search / filter / sort context.
  // Used to detect filter changes so pagination can restart at page 1 exactly once.
  const filtersKey = JSON.stringify([
    debouncedSearch,
    statusFilter,
    sourceFilter,
    productFilter,
    assignedToFilter,
    sortOrder,
    receivedDateFilter,
    reinquiryFilter,
    defaultSource,
    defaultFilter
  ]);
  const prevFiltersKeyRef = useRef(filtersKey);

  const hasActiveFilters = Boolean(
    search ||
    statusFilter ||
    (sourceFilter && sourceFilter !== defaultSource) ||
    productFilter ||
    assignedToFilter ||
    receivedDateFilter ||
    reinquiryFilter
  );

  const handleClearAllFilters = () => {
    setSearch('');
    setStatusFilter('');
    setSourceFilter(defaultSource || '');
    setProductFilter('');
    setAssignedToFilter('');
    setReceivedDateFilter('');
    setReinquiryFilter(false);
    setSortOrder('desc');
  };

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

  // Sync state if defaultSource prop or URL query params change
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const urlStatus = params.get('status') || params.get('status_filter');
    const urlSource = params.get('source') || params.get('source_filter');
    const urlAssigned = params.get('assigned_to') || params.get('assigned_to_filter');

    if (urlStatus !== null) setStatusFilter(urlStatus);
    if (urlSource !== null) setSourceFilter(urlSource);
    else if (isInitialMount.current && defaultSource) setSourceFilter(defaultSource);
    isInitialMount.current = false;
    if (urlAssigned !== null) setAssignedToFilter(urlAssigned);
  }, [location.search, defaultSource]);

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

  // Trial Dates Prompt State
  const [showTrialPromptModal, setShowTrialPromptModal] = useState(false);
  const [pendingTrialLead, setPendingTrialLead] = useState(null);
  const [pendingTrialData, setPendingTrialData] = useState({
    trial_duration_days: DEFAULT_TRIAL_DURATION_DAYS,
    trial_start_date: toISODate(new Date()),
    trial_end_date: addDaysToISO(toISODate(new Date()), DEFAULT_TRIAL_DURATION_DAYS),
    trial_support_employee_id: ''
  });
  // Active Support Managers for the trial dropdown, fetched from the API -
  // never hardcoded ids or names.
  const [trialSupportOptions, setTrialSupportOptions] = useState([]);
  const [trialSupportLoading, setTrialSupportLoading] = useState(false);
  const [trialSupportError, setTrialSupportError] = useState('');
  // True once the user actually touches the manager dropdown. Until then an
  // already-stored legacy value (written before Support Manager selection
  // existed) must be re-saved unchanged instead of being cleared.
  const [trialSupportTouched, setTrialSupportTouched] = useState(false);

  // Explicit Support Assignment modal (opened immediately after conversion or
  // later from a converted lead drawer).
  const [showSupportAssignModal, setShowSupportAssignModal] = useState(false);
  const [supportAssignLead, setSupportAssignLead] = useState(null);
  const [supportTeamMembers, setSupportTeamMembers] = useState([]);
  const [supportMembersLoading, setSupportMembersLoading] = useState(false);
  const [supportAgentId, setSupportAgentId] = useState('');
  const [supportRemarks, setSupportRemarks] = useState('');
  const [supportAssignError, setSupportAssignError] = useState('');
  const [assigningSupport, setAssigningSupport] = useState(false);

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
        fetchLeads(true);
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
        fetchLeads(true);
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
    const docStatus = String(newDoc?.status || '').toLowerCase();
    const docType = String(newDoc?.docType || 'quotation').toUpperCase();
    const isDraft = docStatus === 'draft';
    const amount = Number(newDoc?.grandTotal || 0);

    // Drafts must never overwrite the lead's official issued-quotation reference.
    if (selectedLead && !isDraft && newDoc?.id) {
      patchLeadRow(selectedLead.id, {
        quotetask_quotation_id: String(newDoc.id),
        quotetask_quotation_number: newDoc.number,
        quotetask_quotation_status: newDoc.status,
        quotetask_quotation_amount: newDoc.grandTotal
      });
    }

    setQuotationMessage(
      isDraft
        ? `Draft ${docType} #${newDoc?.number || ''} saved successfully!`
        : `Issued ${docType} #${newDoc?.number || ''} for Rs. ${amount.toLocaleString('en-IN')}!`
    );
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
    followup_time: '10:00 AM',
    trial_start_date: '',
    trial_end_date: ''
  });

  const [assigneeId, setAssigneeId] = useState('');
  const [noteText, setNoteText] = useState('');
  const [savingLeadId, setSavingLeadId] = useState(null);

  // Update only the affected row + an already-open drawer. This keeps filters,
  // search, pagination and scroll position untouched after a save.
  const patchLeadRow = (leadId, updates) => {
    setLeads(prev => prev.map(lead => (
      lead.id === leadId ? { ...lead, ...updates } : lead
    )));
    setSelectedLead(prev => (
      prev && prev.id === leadId ? { ...prev, ...updates } : prev
    ));
  };

  const removeLeadRow = (leadId) => {
    setLeads(prev => prev.filter(lead => lead.id !== leadId));
    const nextTotal = Math.max(0, total - 1);
    setTotal(nextTotal);
    setTotalPages(Math.max(1, Math.ceil(nextTotal / LEADS_PAGE_SIZE)));
    if (leads.length <= 1 && page > 1) {
      setPage(prevPage => Math.max(1, prevPage - 1));
    }
  };

  const fetchLeads = async (silent = false) => {
    const reqId = ++latestLeadReqIdRef.current;
    try {
      if (!silent) setLoading(true);
      const cur = filtersRef.current || {};
      const params = {};
      if (cur.search && cur.search.trim()) params.search = cur.search.trim();
      if (cur.statusFilter) params.status_filter = cur.statusFilter;

      if (cur.reinquiryFilter) {
        params.is_reinquiry_filter = true;
      }

      const effectiveSource = cur.sourceFilter || cur.defaultSource;
      if (effectiveSource && !cur.reinquiryFilter) params.source_filter = effectiveSource;
      if (cur.productFilter) params.product_category_filter = cur.productFilter;

      if (cur.sortOrder) params.sort_order = cur.sortOrder;
      if (cur.receivedDateFilter) params.date_filter = cur.receivedDateFilter;
      if (cur.assignedToFilter) params.assigned_to_filter = cur.assignedToFilter;

      // Server-side pagination: only the current page of records is requested
      const requestedPage = cur.page || 1;
      const requestedPageSize = cur.pageSize || LEADS_PAGE_SIZE;
      params.page = requestedPage;
      params.page_size = requestedPageSize;

      const endpoint = cur.defaultFilter === 'my-leads' ? '/leads/my' : '/leads/';
      const res = await API.get(endpoint, { params });

      // Stale response race-condition guard:
      if (reqId !== latestLeadReqIdRef.current) {
        return;
      }
      const items = res.data.items || [];
      const respTotal = res.data.total ?? items.length;
      const respPage = res.data.page ?? requestedPage;
      const respPageSize = res.data.page_size || requestedPageSize;
      const respTotalPages = res.data.total_pages ?? Math.ceil(respTotal / respPageSize);

      // The result set shrank (lead deleted/filtered away): snap back to a valid
      // page and let the effect refetch once instead of showing a stale window.
      if (respTotal === 0) {
        if (requestedPage !== 1) {
          setPage(1);
          return;
        }
      } else if (respPage > respTotalPages) {
        setPage(respTotalPages);
        return;
      }

      setLeads(items);
      setTotal(respTotal);
      setTotalPages(Math.max(respTotalPages, 1));
    } catch (err) {
      if (reqId === latestLeadReqIdRef.current) {
        if (!silent) {
          console.error(err);
          setError('Failed to fetch leads list.');
        }
      }
    } finally {
      if (reqId === latestLeadReqIdRef.current) {
        if (!silent) setLoading(false);
      }
    }
  };

  const fetchEmployees = async () => {
    try {
      const res = await API.get('/leads/sales-managers');
      setEmployees(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  // Refresh after a lead was created or imported. New records sort newest-first,
  // so jump back to page 1 while still issuing exactly one list request.
  const refreshAfterCreate = () => {
    fetchSourceCounts();
    if (page !== 1) {
      setPage(1); // the pagination effect refetches page 1
    } else {
      fetchLeads();
    }
  };

  // Employee list and source counters are independent of search/status/source
  // filters, so they must not be refetched on every filter change.
  useEffect(() => {
    fetchEmployees();
  }, []);

  useEffect(() => {
    fetchSourceCounts();
  }, [defaultFilter]);

  // Fetch the requested page. Any search/filter/sort change restarts pagination
  // at page 1, and the guard below guarantees a single request per change.
  useEffect(() => {
    const filtersChanged = prevFiltersKeyRef.current !== filtersKey;
    prevFiltersKeyRef.current = filtersKey;

    if (filtersChanged && page !== 1) {
      // Reset first, then let this effect run again with page 1 (one request).
      setPage(1);
      return;
    }
    fetchLeads();
  }, [filtersKey, page]);

  // Quiet background sync for newly arrived Meta/website leads. Polling is
  // paused while the tab is hidden and no longer runs every 5 seconds, which
  // previously produced ~24 list+stats requests per minute per open CRM tab.
  useEffect(() => {
    const syncInterval = setInterval(() => {
      if (document.hidden) return;
      fetchLeads(true);
      fetchSourceCounts();
    }, 30000);

    return () => clearInterval(syncInterval);
  }, []);

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
      followup_time: lead.followup_time || '10:00 AM',
      trial_start_date: lead.trial_start_date || '',
      trial_end_date: lead.trial_end_date || ''
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
    const searchParams = new URLSearchParams(location.search);
    const targetLeadId = searchParams.get('openLeadId');
    if (targetLeadId) {
      handleOpenDetailDrawer({ id: parseInt(targetLeadId, 10) });
    }

    const handleCustomOpenDrawer = (e) => {
      if (e.detail?.leadId) {
        handleOpenDetailDrawer({ id: e.detail.leadId });
      }
    };
    const handleDispositionSaved = (e) => {
      fetchLeads(true);
      fetchSourceCounts();
      const updatedLeadId = e.detail?.leadId;
      if (selectedLead && (!updatedLeadId || selectedLead.id === Number(updatedLeadId))) {
        fetchLeadCallLogs(selectedLead.id);
        API.get(`/leads/${selectedLead.id}`).then(res => {
          if (res.data) {
            setSelectedLead(prev => ({ ...prev, ...res.data }));
          }
        }).catch(() => {});
        API.get(`/activities?lead_id=${selectedLead.id}`).then(res => {
          if (res.data) {
            setSelectedLead(prev => prev ? ({ ...prev, activities: res.data }) : null);
          }
        }).catch(() => {});
      }
    };

    window.addEventListener('openLeadDrawer', handleCustomOpenDrawer);
    window.addEventListener('call-disposition-saved', handleDispositionSaved);
    return () => {
      window.removeEventListener('openLeadDrawer', handleCustomOpenDrawer);
      window.removeEventListener('call-disposition-saved', handleDispositionSaved);
    };
  }, [location.search, selectedLead]);

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
      refreshAfterCreate();
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
        followup_date: formData.followup_date && formData.followup_date.trim() ? formData.followup_date.trim() : null,
        trial_start_date: formData.trial_start_date && formData.trial_start_date.trim() ? formData.trial_start_date.trim() : null,
        trial_end_date: formData.trial_end_date && formData.trial_end_date.trim() ? formData.trial_end_date.trim() : null
      };
      const res = await API.put(`/leads/${selectedLead.id}`, payload);
      const assignedEmployee = employees.find(emp => String(emp.id) === String(payload.assigned_to));
      patchLeadRow(selectedLead.id, {
        ...payload,
        trial_days_remaining: res.data?.trial_days_remaining,
        is_trial_expired: res.data?.is_trial_expired || false,
        assigned_employee_name: assignedEmployee?.name ?? (payload.assigned_to ? selectedLead.assigned_employee_name : null)
      });
      setSuccess('Lead updated successfully!');
      setShowEditModal(false);
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
      const assignedEmployee = employees.find(emp => String(emp.id) === String(assigneeId));
      patchLeadRow(selectedLead.id, {
        assigned_to: parseInt(assigneeId, 10),
        assigned_employee_name: assignedEmployee?.name || null
      });
      setSuccess('Lead assigned successfully!');
      setShowAssignModal(false);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to assign lead.');
    } finally {
      setSubmitting(false);
    }
  };

  const loadSupportTeamMembers = async () => {
    if (!canAssignSupport) return;
    setSupportMembersLoading(true);
    try {
      const res = await API.get('/leads/support/team-members');
      setSupportTeamMembers(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to load active Support Team members:', err);
      setSupportTeamMembers([]);
      setSupportAssignError(
        err.response?.data?.detail || 'Failed to load active Support Team employees.'
      );
    } finally {
      setSupportMembersLoading(false);
    }
  };

  // Active Support Managers for the Set Trial Period modal. Sales users are
  // explicitly allowed to read this list by the backend; ids/names/roles always
  // come from the API (nothing is hardcoded) and regular Support Executives are
  // excluded by the backend.
  const loadTrialSupportOptions = async () => {
    setTrialSupportLoading(true);
    setTrialSupportError('');
    try {
      const res = await API.get('/leads/trial/support-options');
      setTrialSupportOptions(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to load active Support Managers for trial:', err);
      setTrialSupportOptions([]);
      setTrialSupportError(
        err.response?.data?.detail || 'Failed to load active Support Managers.'
      );
    } finally {
      setTrialSupportLoading(false);
    }
  };

  const openSupportAssignModal = (lead, overrides = {}) => {
    if (!lead?.id) return;
    const convertedLead = {
      ...lead,
      ...overrides,
      converted_to_support_at:
        overrides.converted_to_support_at ||
        lead.converted_to_support_at ||
        new Date().toISOString()
    };
    setSupportAssignLead(convertedLead);
    setSupportAgentId(
      convertedLead.support_assigned_to ? String(convertedLead.support_assigned_to) : ''
    );
    setSupportRemarks('');
    setSupportAssignError('');
    setSupportTeamMembers([]);
    setShowSupportAssignModal(true);
    if (canAssignSupport) {
      loadSupportTeamMembers();
    }
  };

  const closeSupportAssignModal = () => {
    setShowSupportAssignModal(false);
    setSupportAssignLead(null);
    setSupportAgentId('');
    setSupportRemarks('');
    setSupportAssignError('');
  };

  const handleAssignSupport = async (e) => {
    if (e) e.preventDefault();
    if (!supportAssignLead) return;

    const currentStatus = normalizeLeadStatusValue(supportAssignLead.status);
    if (currentStatus !== 'CONVERTED_TO_SUPPORT') {
      setSupportAssignError(
        'Support assignment is available only after the deal is explicitly converted to Support.'
      );
      return;
    }
    if (!supportAgentId) {
      setSupportAssignError('Please select an active Support Team employee.');
      return;
    }

    setAssigningSupport(true);
    setSupportAssignError('');
    try {
      const payload = { assigned_agent_id: parseInt(supportAgentId, 10) };
      if (supportRemarks.trim()) payload.remarks = supportRemarks.trim();
      const res = await API.put(`/leads/${supportAssignLead.id}/support-assign`, payload);

      const updatedLead = {
        support_assigned_to: res.data?.assigned_agent_id,
        support_assigned_to_name: res.data?.assigned_agent_name,
        support_assigned_at: res.data?.support_assigned_at,
        support_manager_id: res.data?.support_manager_id,
        support_manager_name: res.data?.support_manager_name,
        support_assignment_status: 'ASSIGNED'
      };
      patchLeadRow(supportAssignLead.id, updatedLead);
      setSuccess(
        res.data?.already_assigned
          ? `Lead #${supportAssignLead.id} is already assigned to ${updatedLead.support_assigned_to_name || 'this Support Executive'}.`
          : `Lead #${supportAssignLead.id} assigned to Support Executive ${updatedLead.support_assigned_to_name || ''} successfully.`
      );
      closeSupportAssignModal();
      window.dispatchEvent(new Event('leadStatsUpdated'));
    } catch (err) {
      console.error('Failed to assign Support Executive:', err);
      setSupportAssignError(
        err.response?.data?.detail || 'Failed to assign the Support Executive. Please try again.'
      );
    } finally {
      setAssigningSupport(false);
    }
  };

  const handleStatusChange = async (leadId, newStatus) => {
    // Won is a Sales-only milestone. The DealWonModal captures the proforma
    // snapshot; Support assignment remains blocked until conversion.
    if (newStatus === 'WON') {
      const targetLead = leads.find(l => l.id === leadId) || (selectedLead && selectedLead.id === leadId ? selectedLead : null);
      setPendingDealWonLead(targetLead || { id: leadId, name: `Lead #${leadId}` });
      setShowDealWonModal(true);
      return;
    }

    // Explicit Won -> Converted to Support transition (Admin / Sales Manager).
    if (newStatus === 'CONVERTED_TO_SUPPORT') {
      const targetLead = leads.find(l => l.id === leadId) || (selectedLead && selectedLead.id === leadId ? selectedLead : null);
      if (!canConvertToSupport) {
        setError('Only Admin and Sales Managers can convert a won deal to Support.');
        return;
      }
      const currentStatus = (targetLead?.status || '').toUpperCase();
      if (currentStatus !== 'WON' && currentStatus !== 'CONVERTED') {
        setError('Only a WON deal can be converted to Support. Mark the deal WON first.');
        return;
      }
      try {
        const res = await API.post(`/leads/${leadId}/convert-to-support`, {});

        // Ensure the assignment form always has the full lead projection even
        // when the status was changed from a table row that is not open in
        // the detail drawer.
        let baseLead = targetLead;
        if (!baseLead) {
          try {
            const detailRes = await API.get(`/leads/${leadId}`);
            baseLead = detailRes.data;
          } catch (detailErr) {
            console.error('Failed to load converted lead details:', detailErr);
          }
        }

        const convertedLead = {
          ...(baseLead || { id: leadId, name: `Lead #${leadId}` }),
          status: res.data?.status || 'CONVERTED_TO_SUPPORT',
          is_converted_to_support: true,
          converted_to_support_at:
            res.data?.converted_to_support_at || new Date().toISOString(),
          converted_to_support_by: res.data?.converted_by,
          converted_to_support_by_name: res.data?.converted_by_name,
          support_handoff_id:
            res.data?.support_handoff_id || baseLead?.support_handoff_id,
          support_assigned_to:
            res.data?.support_assigned_to || baseLead?.support_assigned_to,
          support_assigned_to_name:
            res.data?.support_assigned_to_name || baseLead?.support_assigned_to_name,
          support_assignment_status: res.data?.support_assigned
            ? 'ASSIGNED'
            : 'NOT_ASSIGNED'
        };

        PingoPopupService.triggerStatusUpdate({
          module: 'Lead',
          status: 'CONVERTED TO SUPPORT',
          reference: `Lead #${leadId}`
        });
        setSuccess(
          canAssignSupport
            ? `Lead #${leadId} converted to Support. Complete the Support assignment below.`
            : `Lead #${leadId} converted to Support. It is now Pending Support Assignment.`
        );
        patchLeadRow(leadId, {
          status: convertedLead.status,
          is_converted_to_support: true,
          converted_to_support_at: convertedLead.converted_to_support_at,
          converted_to_support_by: convertedLead.converted_to_support_by,
          converted_to_support_by_name: convertedLead.converted_to_support_by_name,
          support_handoff_id: convertedLead.support_handoff_id,
          support_assigned_to: convertedLead.support_assigned_to,
          support_assigned_to_name: convertedLead.support_assigned_to_name,
          support_assignment_status: convertedLead.support_assignment_status
        });

        // Open the Support Assignment form immediately after the status save.
        openSupportAssignModal(convertedLead);

        window.dispatchEvent(new CustomEvent('revenueUpdated', {
          detail: { lead_id: leadId, status: 'CONVERTED_TO_SUPPORT' }
        }));
        window.dispatchEvent(new Event('leadStatsUpdated'));
      } catch (err) {
        console.error(err);
        setError(err.response?.data?.detail || 'Failed to convert the deal to Support.');
      }
      return;
    }

    // If status is changed to TRIAL, prompt for Trial Duration + Support via Modal
    if (newStatus === 'TRIAL' || newStatus === 'TRIAL LEAD') {
      const targetLead = leads.find(l => l.id === leadId) || (selectedLead && selectedLead.id === leadId ? selectedLead : null);
      const todayStr = toISODate(new Date());
      // An existing trial keeps its original start date and duration; a new
      // trial starts today. The end date is always derived from the duration.
      const existingStart = targetLead?.trial_start_date || '';
      const startStr = existingStart || todayStr;
      let duration = DEFAULT_TRIAL_DURATION_DAYS;
      if (existingStart && targetLead?.trial_end_date) {
        const existingDays = diffDaysISO(existingStart, targetLead.trial_end_date);
        if (Number.isFinite(existingDays) && existingDays > 0) duration = existingDays;
      }
      setPendingTrialLead(targetLead || { id: leadId, name: `Lead #${leadId}` });
      setPendingTrialData({
        trial_duration_days: duration,
        trial_start_date: startStr,
        trial_end_date: addDaysToISO(startStr, duration),
        trial_support_employee_id: targetLead?.trial_support_employee_id
          ? String(targetLead.trial_support_employee_id)
          : ''
      });
      setTrialSupportOptions([]);
      setTrialSupportError('');
      setTrialSupportTouched(false);
      setShowTrialPromptModal(true);
      loadTrialSupportOptions();
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
        patchLeadRow(leadId, { status: 'PROPOSAL SENT' });
        navigate(`/waquotes?create=quotation&leadId=${leadId}`);
        return;
      } catch (err) {
        console.error(err);
        setError(err.response?.data?.detail || 'Failed to update status.');
        return;
      }
    }

    try {
      setSavingLeadId(leadId);
      await API.put(`/leads/${leadId}/status`, { status: newStatus });
      PingoPopupService.triggerStatusUpdate({
        module: 'Lead',
        status: newStatus,
        reference: `Lead #${leadId}`
      });
      setSuccess(`Lead #${leadId} status changed to ${newStatus}`);
      patchLeadRow(leadId, { status: newStatus });
      // Notify revenue dashboard and targets
      window.dispatchEvent(new CustomEvent('revenueUpdated', {
        detail: { lead_id: leadId, status: newStatus }
      }));
      window.dispatchEvent(new Event('leadStatsUpdated'));
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to update status.');
    } finally {
      setSavingLeadId(current => (current === leadId ? null : current));
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
      patchLeadRow(leadId, {
        status: 'FOLLOW-UP',
        followup_date: pendingFollowupData.followup_date,
        followup_time: pendingFollowupData.followup_time
      });
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to schedule follow-up.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTrialDurationChange = (e) => {
    const raw = e.target.value;
    if (raw === '') {
      setPendingTrialData(prev => ({ ...prev, trial_duration_days: '', trial_end_date: '' }));
      return;
    }
    const days = parseInt(raw, 10);
    setPendingTrialData(prev => {
      const next = {
        ...prev,
        trial_duration_days: Number.isFinite(days) ? days : '',
        trial_end_date: ''
      };
      if (next.trial_start_date && Number.isFinite(days) && days >= 1) {
        // Recalculated immediately on every keystroke.
        next.trial_end_date = addDaysToISO(next.trial_start_date, days);
      }
      return next;
    });
  };

  // Editable start date: re-anchors the current duration on the new day.
  const handleTrialStartChange = (e) => {
    const start = e.target.value;
    setPendingTrialData(prev => {
      const days = parseInt(prev.trial_duration_days, 10);
      const end = start && Number.isFinite(days) && days >= 1
        ? addDaysToISO(start, days)
        : '';
      return { ...prev, trial_start_date: start, trial_end_date: end };
    });
  };

  // Editable end date: recalculates the duration from start -> end. A date that
  // is not at least one day after the start is kept in the field so the submit
  // validation can explain the problem instead of silently overwriting it.
  const handleTrialEndChange = (e) => {
    const end = e.target.value;
    setPendingTrialData(prev => {
      if (!end) return { ...prev, trial_end_date: '' };
      const days = diffDaysISO(prev.trial_start_date, end);
      return {
        ...prev,
        trial_end_date: end,
        trial_duration_days: Number.isFinite(days) && days >= 1
          ? days
          : prev.trial_duration_days
      };
    });
  };

  const handleConfirmTrialSchedule = async (e) => {
    if (e) e.preventDefault();
    if (!pendingTrialLead) return;

    const duration = parseInt(pendingTrialData.trial_duration_days, 10);
    if (!Number.isFinite(duration) || duration < 1 || duration > 365) {
      setError('Trial Duration must be between 1 and 365 days.');
      return;
    }
    if (!pendingTrialData.trial_start_date) {
      setError('Trial Start Date is missing.');
      return;
    }
    const endDate = addDaysToISO(pendingTrialData.trial_start_date, duration);
    if (!endDate) {
      setError('Could not calculate the Trial End Date from the Trial Duration.');
      return;
    }
    // The editable dates and the duration must agree; if they do not, the end
    // date is before/equal to the start date.
    if (!pendingTrialData.trial_end_date) {
      setError('Trial End Date is missing.');
      return;
    }
    if (pendingTrialData.trial_end_date !== endDate) {
      setError('Trial End Date must be at least 1 day after the Trial Start Date.');
      return;
    }

    try {
      setSavingLeadId(pendingTrialLead.id);
      const payload = {
        status: 'TRIAL',
        trial_start_date: pendingTrialData.trial_start_date,
        trial_end_date: endDate,
        trial_duration_days: duration,
        // An id assigns the selected Support Manager; an explicit null clears
        // the assignment (=> "pending"). A stored legacy value that the
        // manager-only dropdown does not offer is re-saved unchanged while the
        // user has not touched the field, so an existing Support assignment is
        // never lost.
        trial_support_employee_id: (() => {
          const selected = pendingTrialData.trial_support_employee_id;
          if (selected) return parseInt(selected, 10);
          if (!trialSupportTouched && pendingTrialLead?.trial_support_employee_id) {
            return pendingTrialLead.trial_support_employee_id;
          }
          return null;
        })()
      };
      const res = await API.put(`/leads/${pendingTrialLead.id}`, payload);
      // Label the assignment from the role the server actually stored, so a
      // preserved legacy Support employee is never announced as a manager.
      const assignedRole = res.data?.trial_support_employee_role;
      const assignedName = res.data?.trial_support_employee_name;
      patchLeadRow(pendingTrialLead.id, {
        status: 'TRIAL',
        trial_start_date: res.data?.trial_start_date || payload.trial_start_date,
        trial_end_date: res.data?.trial_end_date || endDate,
        trial_duration_days: res.data?.trial_duration_days ?? duration,
        trial_days_remaining: res.data?.trial_days_remaining ?? null,
        is_trial_expired: res.data?.is_trial_expired || false,
        trial_status: res.data?.trial_status || null,
        trial_support_employee_id: res.data?.trial_support_employee_id ?? null,
        trial_support_employee_name: res.data?.trial_support_employee_name ?? null,
        trial_support_employee_role: res.data?.trial_support_employee_role ?? null,
        support_assigned_to: res.data?.support_assigned_to ?? null,
        support_assigned_to_name: res.data?.support_assigned_to_name ?? null,
        support_manager_id: res.data?.support_manager_id ?? null,
        support_manager_name: res.data?.support_manager_name ?? null
      });
      setShowTrialPromptModal(false);
      setPendingTrialLead(null);
      setSuccess(
        `Lead #${pendingTrialLead.id} set to TRIAL for ${duration} day(s) - ` +
        `${formatDateDDMMYYYY(payload.trial_start_date)} to ${formatDateDDMMYYYY(endDate)}. ` +
        (assignedName
          ? `${assignedRole === 'SUPPORT_MANAGER' ? 'Support Manager' : 'Support'} assigned to ${assignedName}.`
          : 'Support Manager assignment is pending.')
      );
      window.dispatchEvent(new Event('leadStatsUpdated'));
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to update Trial status.');
    } finally {
      setSavingLeadId(null);
    }
  };

  const handleConvertLead = (leadId) => {
    const targetLead = leads.find(l => l.id === leadId) || (selectedLead && selectedLead.id === leadId ? selectedLead : null);
    setPendingDealWonLead(targetLead || { id: leadId, name: `Lead #${leadId}` });
    setShowDealWonModal(true);
  };

  const handleConvertToSupport = (leadId) => {
    handleStatusChange(leadId, 'CONVERTED_TO_SUPPORT');
  };

  const handleDealWonSuccess = (data) => {
    setSuccess('Deal marked WON. Support assignment stays disabled until the deal is explicitly converted to Support.');
    const wonLeadId = data?.lead_id || pendingDealWonLead?.id;
    if (wonLeadId) {
      patchLeadRow(wonLeadId, { status: 'WON', support_assignment_status: 'AWAITING_CONVERSION' });
    }
    // Notify revenue dashboard and targets
    window.dispatchEvent(new CustomEvent('revenueUpdated', {
      detail: { lead_id: wonLeadId, status: 'WON' }
    }));
    window.dispatchEvent(new Event('leadStatsUpdated'));
  };

  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!noteText.trim() || submitting) return;

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
        removeLeadRow(leadId);
        fetchSourceCounts();
        window.dispatchEvent(new Event('leadStatsUpdated'));
      }
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
      refreshAfterCreate();
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
    if (s.includes('CONVERTED') && s.includes('SUPPORT')) return { bg: 'rgba(13, 148, 136, 0.14)', color: '#0f766e' };
    if (s === 'TRIAL' || s.includes('TRIAL')) return { bg: 'rgba(14, 165, 233, 0.14)', color: '#0369a1' };
    if (s.includes('NEW') || s === 'ASSIGNED') return { bg: 'rgba(59, 130, 246, 0.12)', color: '#2563eb' };
    if (s.includes('CONTACTED')) return { bg: 'rgba(14, 165, 233, 0.12)', color: '#0284c7' };
    if (s.includes('INTERESTED') && !s.includes('NOT')) return { bg: 'rgba(245, 158, 11, 0.12)', color: '#d97706' };
    if (s.includes('RNR')) return { bg: 'rgba(249, 115, 22, 0.12)', color: '#c2410c' };
    if (s.includes('JUNK')) return { bg: 'rgba(100, 116, 139, 0.14)', color: '#475569' };
    if (s.includes('QUALIFIED')) return { bg: 'rgba(20, 184, 166, 0.12)', color: '#0d9488' };
    if (s.includes('DEMO') || s.includes('MEETING')) return { bg: 'rgba(99, 102, 241, 0.12)', color: '#4f46e5' };
    if (s.includes('PROPOSAL')) return { bg: 'rgba(147, 51, 234, 0.12)', color: '#9333ea' };
    if (s.includes('NEGOTIATION')) return { bg: 'rgba(234, 88, 12, 0.12)', color: '#ea580c' };
    if (s.includes('FOLLOW')) return { bg: 'rgba(219, 39, 119, 0.12)', color: '#db2777' };
    if (s.includes('WON') || s.includes('CONVERTED')) return { bg: 'rgba(16, 185, 129, 0.15)', color: '#059669' };
    if (s.includes('LOST') || s.includes('NOT')) return { bg: 'rgba(220, 38, 38, 0.12)', color: '#dc2626' };
    return { bg: '#f1f5f9', color: '#64748b' };
  };

  const getSourceLabel = (source) => {
    const raw = (source || '').trim();
    const srcUpper = raw.toUpperCase();
    if (srcUpper === 'WHATSAPP_ADS' || srcUpper === 'WHATSAPP ADS') return 'WhatsApp Ads';
    return raw;
  };

  const getSourceBadgeStyle = (source) => {
    const srcUpper = (source || '').toUpperCase();
    if (srcUpper.includes('WHATSAPP')) return { bg: 'rgba(37, 211, 102, 0.14)', color: '#128c7e' };
    if (srcUpper.includes('META')) return { bg: 'rgba(59, 130, 246, 0.12)', color: '#1d4ed8' };
    if (srcUpper.includes('WEB')) return { bg: 'rgba(16, 185, 129, 0.12)', color: '#047857' };
    if (srcUpper.includes('EXCEL')) return { bg: 'rgba(245, 158, 11, 0.12)', color: '#b45309' };
    if (srcUpper.includes('MANUAL')) return { bg: 'rgba(107, 114, 128, 0.12)', color: '#374151' };
    return { bg: '#f1f5f9', color: '#475569' };
  };

  // Records range shown under the table (e.g. "Showing 1-150 of 850")
  const rangeStart = total === 0 ? 0 : (page - 1) * LEADS_PAGE_SIZE + 1;
  const rangeEnd = Math.min(page * LEADS_PAGE_SIZE, total);

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
                        setProductFilter('');
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
          <div className="search-box" style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={18} className="search-icon" />
            <input 
              type="text" 
              placeholder="Search leads by name, phone, email, or company..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ paddingRight: search ? '30px' : undefined }}
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                style={{
                  position: 'absolute',
                  right: '10px',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#94a3b8',
                  padding: '2px',
                  display: 'flex',
                  alignItems: 'center'
                }}
                title="Clear search"
              >
                <X size={15} />
              </button>
            )}
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

            <select 
              value={productFilter} 
              onChange={(e) => setProductFilter(e.target.value)}
              style={{ width: '150px' }}
              title="Filter by Product Category"
            >
              <option value="">All Products</option>
              <option value="BIOMETRIC">BIOMETRIC</option>
              <option value="WAHRMS">WAHRMS</option>
              <option value="UNCLASSIFIED">UNCLASSIFIED</option>
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

            {/* Clear All Active Filters */}
            {hasActiveFilters && (
              <button
                type="button"
                onClick={handleClearAllFilters}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '7px 12px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  backgroundColor: '#f1f5f9',
                  color: '#475569',
                  fontSize: '0.82rem',
                  fontWeight: '700',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
                title="Reset all active filters"
              >
                <X size={14} /> Clear
              </button>
            )}
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
                <th style={{ minWidth: '130px' }}>Product</th>
                <th style={{ minWidth: '140px' }}>Status</th>
                <th>Assigned To</th>
                <th style={{ minWidth: '145px' }}>Support Assigned To</th>
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
                  <td colSpan="10" className="text-center py-4 text-muted">
                    Loading leads data...
                  </td>
                </tr>
              ) : leads.length === 0 ? (
                <tr>
                  <td colSpan="10" style={{ padding: '36px 16px', background: '#f8fafc' }}>
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
                          {getSourceLabel(lead.source)}
                        </span>
                      </td>
                      <td>
                        {(() => {
                          const rawCat = (lead.product_category || 'UNCLASSIFIED').toUpperCase();
                          const isBio = rawCat === 'BIOMETRIC';
                          const isWahrms = rawCat === 'WAHRMS';
                          const bg = isBio ? '#eff6ff' : isWahrms ? '#f0fdf4' : '#f8fafc';
                          const color = isBio ? '#1d4ed8' : isWahrms ? '#15803d' : '#64748b';
                          const border = isBio ? '#bfdbfe' : isWahrms ? '#bbf7d0' : '#cbd5e1';
                          return (
                            <span style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '5px',
                              padding: '3px 9px',
                              borderRadius: '12px',
                              fontSize: '0.74rem',
                              fontWeight: 700,
                              backgroundColor: bg,
                              color: color,
                              border: `1px solid ${border}`,
                              whiteSpace: 'nowrap'
                            }}>
                              <span style={{
                                width: '6px',
                                height: '6px',
                                borderRadius: '50%',
                                backgroundColor: isBio ? '#2563eb' : isWahrms ? '#16a34a' : '#94a3b8'
                              }} />
                              {rawCat}
                            </span>
                          );
                        })()}
                      </td>
                      <td style={{ minWidth: '140px' }} onClick={(e) => e.stopPropagation()}>
                        <select
                          value={lead.status}
                          onChange={(e) => handleStatusChange(lead.id, e.target.value)}
                          disabled={savingLeadId === lead.id}
                          aria-busy={savingLeadId === lead.id}
                          title={savingLeadId === lead.id ? 'Saving status...' : 'Change lead status'}
                          style={{
                            padding: '5px 22px 5px 10px',
                            borderRadius: '16px',
                            fontSize: '0.78rem',
                            fontWeight: '600',
                            backgroundColor: badgeStyle.bg,
                            color: badgeStyle.color,
                            border: '1px solid rgba(0, 0, 0, 0.08)',
                            cursor: savingLeadId === lead.id ? 'wait' : 'pointer',
                            minWidth: '130px',
                            width: '100%',
                            outline: 'none',
                            appearance: 'auto',
                            boxSizing: 'border-box',
                            opacity: savingLeadId === lead.id ? 0.6 : 1
                          }}
                        >
                          {STATUS_OPTIONS.map(st => (
                            <option key={st} value={st} style={{ backgroundColor: '#ffffff', color: '#0f172a' }}>
                              {st.replace(/_/g, ' ')}
                            </option>
                          ))}
                        </select>
                        {lead.is_trial_expired && (
                          <div style={{ marginTop: '4px' }}>
                            <span style={{
                              display: 'inline-flex',
                              alignItems: 'center',
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
                          </div>
                        )}
                        {savingLeadId === lead.id && (
                          <span style={{ display: 'block', marginTop: 2, fontSize: '0.65rem', fontWeight: 600, color: '#64748b' }}>
                            Saving…
                          </span>
                        )}
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
                        {lead.support_assigned_to_name ? (
                          <span style={{ fontSize: '0.82rem', fontWeight: '600', color: '#0f766e' }}>
                            {lead.support_assigned_to_name}
                          </span>
                        ) : (
                          <span style={{
                            fontSize: '0.76rem',
                            padding: '3px 8px',
                            borderRadius: '12px',
                            backgroundColor: lead.is_converted_to_support ? '#fef3c7' : '#f1f5f9',
                            color: lead.is_converted_to_support ? '#92400e' : '#64748b',
                            fontWeight: '600',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}>
                            {lead.is_converted_to_support ? 'Pending Support Assignment' : 'Not Assigned'}
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

        {/* PAGINATION BAR (server-side: 150 leads per page) */}
        {total > 0 && (
          <div className="leads-pagination">
            <div className="leads-pagination-info">
              <span className="leads-pagination-range">
                Showing <strong>{rangeStart.toLocaleString()}</strong>–<strong>{rangeEnd.toLocaleString()}</strong> of <strong>{total.toLocaleString()}</strong> leads
              </span>
              <span className="leads-pagination-current">
                Page <strong>{page}</strong> of <strong>{totalPages}</strong>
              </span>
            </div>

            <div className="leads-pagination-controls">
              <button
                type="button"
                className="leads-pagination-btn"
                onClick={() => setPage(prev => Math.max(prev - 1, 1))}
                disabled={page <= 1 || loading}
                title="Go to the previous page"
              >
                <ChevronLeft size={14} /> Previous
              </button>

              <div className="leads-pagination-pages">
                {buildPageList(page, totalPages).map((p, idx) => (
                  p === '...' ? (
                    <span key={`gap-${idx}`} className="leads-pagination-gap">…</span>
                  ) : (
                    <button
                      key={p}
                      type="button"
                      className={`leads-pagination-page${p === page ? ' active' : ''}`}
                      onClick={() => setPage(p)}
                      disabled={loading}
                      aria-current={p === page ? 'page' : undefined}
                      title={`Go to page ${p}`}
                    >
                      {p}
                    </button>
                  )
                ))}
              </div>

              <button
                type="button"
                className="leads-pagination-btn"
                onClick={() => setPage(prev => Math.min(prev + 1, totalPages))}
                disabled={page >= totalPages || loading}
                title="Go to the next page"
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
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

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginTop: '12px' }}>
                  <div className="form-group">
                    <label>Trial Start Date</label>
                    <input 
                      type="date" 
                      value={formData.trial_start_date || ''}
                      onChange={(e) => setFormData({ ...formData, trial_start_date: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Trial End Date</label>
                    <input 
                      type="date" 
                      value={formData.trial_end_date || ''}
                      onChange={(e) => setFormData({ ...formData, trial_end_date: e.target.value })}
                    />
                  </div>
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
                          {getSourceLabel(selectedLead.source)}
                        </span>

                        {/* Product Category Pill */}
                        {(() => {
                          const cat = (selectedLead.product_category || 'UNCLASSIFIED').toUpperCase();
                          const isBio = cat === 'BIOMETRIC';
                          const isWahrms = cat === 'WAHRMS';
                          const bg = isBio ? '#eff6ff' : isWahrms ? '#f0fdf4' : '#f8fafc';
                          const color = isBio ? '#1d4ed8' : isWahrms ? '#15803d' : '#64748b';
                          const border = isBio ? '#bfdbfe' : isWahrms ? '#bbf7d0' : '#cbd5e1';
                          return (
                            <div style={{ position: 'relative' }} title="Product Classification: Click to change">
                              <select
                                value={cat}
                                onChange={async (e) => {
                                  const newCat = e.target.value;
                                  try {
                                    await API.put(`/leads/${selectedLead.id}`, { product_category: newCat });
                                    patchLeadRow(selectedLead.id, { product_category: newCat, product_category_confirmed: true });
                                  } catch (err) {
                                    console.error('Failed to update product category:', err);
                                  }
                                }}
                                style={{
                                  appearance: 'none',
                                  WebkitAppearance: 'none',
                                  padding: '4px 24px 4px 10px',
                                  borderRadius: '16px',
                                  fontSize: '0.74rem',
                                  fontWeight: '800',
                                  backgroundColor: bg,
                                  color: color,
                                  border: `1.5px solid ${border}`,
                                  cursor: 'pointer',
                                  outline: 'none'
                                }}
                              >
                                <option value="UNCLASSIFIED">UNCLASSIFIED</option>
                                <option value="BIOMETRIC">BIOMETRIC</option>
                                <option value="WAHRMS">WAHRMS</option>
                              </select>
                              <ChevronDown size={13} style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: color }} />
                            </div>
                          );
                        })()}

                        {/* Interactive Status Pill in Header */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <div style={{ position: 'relative' }} title="Change Lead Status">
                            <select
                              value={selectedLead.status}
                              onChange={(e) => handleStatusChange(selectedLead.id, e.target.value)}
                              disabled={savingLeadId === selectedLead.id}
                              aria-busy={savingLeadId === selectedLead.id}
                              title={savingLeadId === selectedLead.id ? 'Saving status...' : 'Change Lead Status'}
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
                                cursor: savingLeadId === selectedLead.id ? 'wait' : 'pointer',
                                outline: 'none',
                                opacity: savingLeadId === selectedLead.id ? 0.6 : 1
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
                    </div>

                    {/* DEDICATED TRIAL METRICS BANNER */}
                    {(selectedLead.trial_start_date || selectedLead.trial_end_date) && (
                      <div style={{
                        marginTop: '10px',
                        marginBottom: '4px',
                        padding: '10px 14px',
                        background: selectedLead.is_trial_expired ? '#fef2f2' : '#f0f9ff',
                        border: `1.5px solid ${selectedLead.is_trial_expired ? '#fca5a5' : '#bae6fd'}`,
                        borderRadius: '10px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: '8px'
                      }}>
                        <div>
                          <span style={{ fontSize: '0.8rem', fontWeight: '800', color: selectedLead.is_trial_expired ? '#b91c1c' : '#0369a1', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <Clock size={13} /> TRIAL PERIOD
                            {trialStatusLabel(selectedLead) && (
                              <span style={{
                                padding: '1px 7px',
                                borderRadius: '10px',
                                fontSize: '0.68rem',
                                letterSpacing: '0.03em',
                                textTransform: 'uppercase',
                                backgroundColor: selectedLead.trial_status === 'TRIAL_EXPIRING_SOON' ? '#fff7ed' : (selectedLead.is_trial_expired ? '#fee2e2' : '#e0f2fe'),
                                color: selectedLead.trial_status === 'TRIAL_EXPIRING_SOON' ? '#c2410c' : (selectedLead.is_trial_expired ? '#b91c1c' : '#0369a1'),
                                border: `1px solid ${selectedLead.trial_status === 'TRIAL_EXPIRING_SOON' ? '#fed7aa' : (selectedLead.is_trial_expired ? '#fca5a5' : '#bae6fd')}`
                              }}>
                                {trialStatusLabel(selectedLead)}
                              </span>
                            )}
                          </span>
                          <span style={{ fontSize: '0.78rem', color: selectedLead.is_trial_expired ? '#991b1b' : '#0c4a6e', marginTop: '2px', display: 'block' }}>
                            {formatDateDDMMYYYY(selectedLead.trial_start_date)} to {formatDateDDMMYYYY(selectedLead.trial_end_date)}
                            {selectedLead.trial_days_remaining !== null && selectedLead.trial_days_remaining !== undefined && (
                              <strong style={{ marginLeft: '6px' }}>
                                ({selectedLead.trial_days_remaining >= 0 ? `${selectedLead.trial_days_remaining} days left` : `Expired ${Math.abs(selectedLead.trial_days_remaining)} days ago`})
                              </strong>
                            )}
                          </span>
                        </div>
                        <div style={{
                          fontSize: '0.76rem',
                          fontWeight: 700,
                          color: selectedLead.trial_support_employee_name || selectedLead.support_assigned_to_name ? '#047857' : '#b45309',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px'
                        }}>
                          <UserCheck size={12} />
                          {trialSupportAssigneeLabel(selectedLead)}: {selectedLead.trial_support_employee_name
                            || selectedLead.support_assigned_to_name
                            || 'Pending assignment'}
                        </div>
                      </div>
                    )}

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
                                  {getSourceLabel(srcName)}
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
                        {['NEW LEAD', 'CONTACTED', 'FOLLOW-UP', 'RNR', 'WON', 'LOST', 'JUNK'].map(st => {
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

                    {/* Row 3: Conversion & Delete Actions */}
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                      gap: '8px',
                      marginTop: '8px'
                    }}>
                      {selectedLead.status !== 'WON' && selectedLead.status !== 'CONVERTED' && selectedLead.status !== 'CONVERTED_TO_SUPPORT' && selectedLead.status !== 'CONVERTED TO SUPPORT' && (
                        <button
                          type="button"
                          onClick={() => handleConvertLead(selectedLead.id)}
                          className="btn btn-outline"
                          style={{ fontSize: '0.8rem', fontWeight: '600', padding: '8px 12px', color: '#16a34a', borderColor: '#bbf7d0', backgroundColor: '#f0fdf4', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                          title="Mark as Won and prepare the Support handoff snapshot"
                        >
                          <Check size={14} /> Mark Won
                        </button>
                      )}

                      {canConvertToSupport && (selectedLead.status === 'WON' || selectedLead.status === 'CONVERTED') && (
                        <button
                          type="button"
                          onClick={() => handleConvertToSupport(selectedLead.id)}
                          className="btn btn-outline"
                          style={{ fontSize: '0.8rem', fontWeight: '600', padding: '8px 12px', color: '#0f766e', borderColor: '#99f6e4', backgroundColor: '#f0fdfa', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                          title="Explicitly convert this won deal to the Support onboarding queue"
                        >
                          <UserCheck size={14} /> Convert to Support
                        </button>
                      )}

                      {canAssignSupport && ['CONVERTED_TO_SUPPORT', 'CONVERTED TO SUPPORT'].includes((selectedLead.status || '').toUpperCase()) && (
                        <button
                          type="button"
                          onClick={() => openSupportAssignModal(selectedLead)}
                          className="btn btn-outline"
                          style={{ fontSize: '0.8rem', fontWeight: '600', padding: '8px 12px', color: '#7c3aed', borderColor: '#ddd6fe', backgroundColor: '#f5f3ff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                          title={selectedLead.support_assigned_to ? 'Review or change the Support Executive' : 'Assign an active Support Executive'}
                        >
                          <UserCheck size={14} /> {selectedLead.support_assigned_to ? 'Manage Support' : 'Assign Support'}
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
                          <div><strong>Sales Manager:</strong> {selectedLead.sales_manager_name || 'Not Assigned'}</div>
                          <div style={{ gridColumn: 'span 2', background: '#f0fdfa', padding: '8px 12px', borderRadius: '6px', border: '1px solid #ccfbf1', color: '#0f766e' }}>
                            <strong>Support Assigned To:</strong>{' '}
                            <span style={{ fontWeight: 700 }}>
                              {selectedLead.support_assigned_to_name || 'Not Assigned'}
                            </span>
                            {selectedLead.is_converted_to_support ? (
                              <span style={{ marginLeft: '10px', fontSize: '0.74rem', fontWeight: 700, color: selectedLead.support_assigned_to_name ? '#047857' : '#b45309' }}>
                                {selectedLead.support_assigned_to_name ? '• Support assignment active' : '• Pending Support Assignment'}
                              </span>
                            ) : selectedLead.trial_support_employee_id ? (
                              <span style={{ marginLeft: '10px', fontSize: '0.74rem', fontWeight: 700, color: '#047857' }}>
                                • Trial Support assignment active
                              </span>
                            ) : selectedLead.trial_status ? (
                              <span style={{ marginLeft: '10px', fontSize: '0.74rem', fontWeight: 700, color: '#b45309' }}>
                                • Pending Support Assignment (trial)
                              </span>
                            ) : (
                              <span style={{ marginLeft: '10px', fontSize: '0.74rem', fontWeight: 600, color: '#64748b' }}>
                                • Available after Won → Converted to Support
                              </span>
                            )}
                          </div>
                          {selectedLead.is_converted_to_support && (
                            <div style={{ gridColumn: 'span 2', fontSize: '0.8rem', color: '#475569' }}>
                              Converted to Support by <strong>{selectedLead.converted_to_support_by_name || 'Unknown'}</strong>
                              {selectedLead.converted_to_support_at ? ` on ${formatLeadReceived(selectedLead.converted_to_support_at).full}` : ''}
                            </div>
                          )}
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
                              {call.product_category && call.product_category !== 'UNCLASSIFIED' && (
                                <span style={{ marginLeft: '8px', padding: '2px 6px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 700, backgroundColor: call.product_category === 'BIOMETRIC' ? '#eff6ff' : '#f0fdf4', color: call.product_category === 'BIOMETRIC' ? '#1d4ed8' : '#15803d' }}>
                                  {call.product_category}
                                </span>
                              )}
                            </div>

                            {call.notes && (
                              <div style={{ marginTop: '6px', marginBottom: '6px', padding: '8px 10px', backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '0.8rem', color: '#334155' }}>
                                <strong style={{ color: '#0f172a' }}>Discussion / Notes:</strong> {call.notes}
                              </div>
                            )}
                            {call.recording_url && (
                              <div style={{ marginTop: '8px' }}>
                                <audio
                                  controls
                                  preload="metadata"
                                  src={call.recording_url}
                                  style={{ width: '100%', height: '32px' }}
                                  onLoadedMetadata={(e) => probeAudioDuration(e.currentTarget)}
                                  onDurationChange={(e) => rewindAfterProbe(e.currentTarget)}
                                  onTimeUpdate={(e) => rewindAfterProbe(e.currentTarget)}
                                />
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
                              <div><strong>Sales Manager:</strong> {selectedLead.sales_manager_name || 'Not Assigned'}</div>
                              <div><strong>Support Assigned To:</strong> {selectedLead.support_assigned_to_name || 'Not Assigned'}</div>
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
                                        {getSourceLabel(enq.source)}
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

      {/* TRIAL EXPIRY & DATES PROMPT MODAL */}
      {showTrialPromptModal && pendingTrialLead && (
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
                <div style={{ width: '40px', height: '40px', borderRadius: '10px', backgroundColor: '#e0f2fe', color: '#0369a1', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Clock size={22} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>Set Trial Period</h3>
                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Lead: {pendingTrialLead.name || `#${pendingTrialLead.id}`}</span>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => { setShowTrialPromptModal(false); setPendingTrialLead(null); }} 
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleConfirmTrialSchedule}>
              <p style={{ fontSize: '0.84rem', color: '#64748b', marginBottom: '16px', lineHeight: 1.45 }}>
                Set the trial duration or pick the start and end dates directly - the three fields stay in sync.
                Expiry reminders are scheduled for the Sales Manager and the assigned Support Manager at 3 days,
                1 day, and on the Trial Expiry Date.
              </p>

              {/* Trial Duration (days) */}
              <div className="form-group" style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px', display: 'block' }}>
                  Trial Duration (days) *
                </label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  step="1"
                  required
                  inputMode="numeric"
                  value={pendingTrialData.trial_duration_days}
                  onChange={handleTrialDurationChange}
                  placeholder="e.g. 14"
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                />
              </div>

              {/* Editable trial dates */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
                <div className="form-group">
                  <label style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px', display: 'block' }}>
                    Trial Start Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={pendingTrialData.trial_start_date || ''}
                    onChange={handleTrialStartChange}
                    style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                  />
                </div>

                <div className="form-group">
                  <label style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px', display: 'block' }}>
                    Trial End Date *
                  </label>
                  <input
                    type="date"
                    required
                    min={pendingTrialData.trial_start_date ? addDaysToISO(pendingTrialData.trial_start_date, 1) : undefined}
                    max={pendingTrialData.trial_start_date ? addDaysToISO(pendingTrialData.trial_start_date, 365) : undefined}
                    value={pendingTrialData.trial_end_date || ''}
                    onChange={handleTrialEndChange}
                    style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                  />
                </div>
              </div>

              {/* Live preview */}
              <div style={{
                marginBottom: '16px',
                padding: '10px 14px',
                borderRadius: '8px',
                backgroundColor: pendingTrialData.trial_end_date ? '#f0f9ff' : '#fff7ed',
                border: `1px solid ${pendingTrialData.trial_end_date ? '#bae6fd' : '#fed7aa'}`,
                color: pendingTrialData.trial_end_date ? '#0369a1' : '#9a3412',
                fontSize: '0.84rem',
                fontWeight: 600,
                lineHeight: 1.5
              }}>
                {pendingTrialData.trial_end_date && pendingTrialData.trial_start_date
                  ? <>Your trial will run from <strong>{formatDateDDMMYYYY(pendingTrialData.trial_start_date)}</strong> to <strong>{formatDateDDMMYYYY(pendingTrialData.trial_end_date)}</strong> (<strong>{pendingTrialData.trial_duration_days}</strong> days).</>
                  : 'Enter a valid Trial Duration to see the calculated trial period.'}
              </div>

              {/* Assign Support Manager */}
              <div className="form-group" style={{ marginBottom: '6px' }}>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px', display: 'block' }}>
                  Assign Support Manager
                </label>
                {/* A stored legacy value (a Support Executive saved before this
                    rule existed) is never rendered as a selectable option -
                    regular Support Employees must not appear in this list. It
                    is kept untouched unless the user picks a manager. */}
                {(() => {
                  const storedId = pendingTrialData.trial_support_employee_id;
                  const isListedManager = Boolean(storedId) &&
                    trialSupportOptions.some(opt => String(opt.id) === String(storedId));
                  const storedNotListed = Boolean(storedId) &&
                    !trialSupportLoading &&
                    trialSupportOptions.length > 0 &&
                    !isListedManager;
                  return (
                    <>
                      <select
                        value={storedNotListed ? '' : storedId}
                        onChange={(e) => {
                          setTrialSupportTouched(true);
                          setPendingTrialData({ ...pendingTrialData, trial_support_employee_id: e.target.value });
                        }}
                        disabled={trialSupportLoading}
                        style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff' }}
                      >
                        <option value="">
                          {trialSupportLoading ? 'Loading active Support Managers...' : 'Select Support Manager (optional)'}
                        </option>
                        {trialSupportOptions.map(member => (
                          <option key={member.id} value={String(member.id)}>
                            {member.name} ({(member.role || '').replace(/_/g, ' ')})
                          </option>
                        ))}
                      </select>

                      {storedNotListed && (
                        <p style={{ fontSize: '0.78rem', color: '#475569', marginTop: '6px', fontWeight: 600 }}>
                          Currently assigned: {pendingTrialLead?.trial_support_employee_name || `Employee #${storedId}`} - this existing Support assignment is kept unless you select a Support Manager.
                        </p>
                      )}
                      {trialSupportError && (
                        <p style={{ fontSize: '0.78rem', color: '#b91c1c', marginTop: '6px' }}>{trialSupportError}</p>
                      )}
                      {!trialSupportLoading && !trialSupportError && trialSupportOptions.length === 0 && (
                        <p style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '6px' }}>
                          No Support Manager available.
                        </p>
                      )}
                      {!storedId && (
                        <p style={{ fontSize: '0.78rem', color: '#b45309', marginTop: '6px', fontWeight: 600 }}>
                          Support assignment is pending - no Support Manager selected.
                        </p>
                      )}
                      {isListedManager && (
                        <p style={{ fontSize: '0.78rem', color: '#047857', marginTop: '6px', fontWeight: 600 }}>
                          Trial expiry reminders will also go to this Support Manager.
                        </p>
                      )}
                    </>
                  );
                })()}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '16px' }}>
                <button 
                  type="button" 
                  onClick={() => { setShowTrialPromptModal(false); setPendingTrialLead(null); }} 
                  className="btn btn-outline"
                  disabled={savingLeadId === pendingTrialLead.id}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  disabled={
                    savingLeadId === pendingTrialLead.id ||
                    !pendingTrialData.trial_end_date ||
                    !Number.isFinite(parseInt(pendingTrialData.trial_duration_days, 10)) ||
                    parseInt(pendingTrialData.trial_duration_days, 10) < 1
                  }
                  style={{ backgroundColor: '#0284c7', color: '#ffffff', fontWeight: 700, padding: '10px 18px', borderRadius: '8px' }}
                >
                  {savingLeadId === pendingTrialLead.id ? 'Saving...' : 'Set Trial & Update Status'}
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
              <h3 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-main, #0f172a)' }}>Assign Sales Manager &middot; Lead #{selectedLead?.id}</h3>
              <button onClick={() => setShowAssignModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleAssignLead}>
              <div className="form-group" style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-muted)' }}>Select Active Sales Manager</label>
                <select 
                  value={assigneeId} 
                  onChange={(e) => setAssigneeId(e.target.value)}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border-color)' }}
                >
                  <option value="">Select Sales Manager...</option>
                  {employees.map(emp => (
                    <option key={emp.id} value={emp.id}>{emp.name} ({emp.role})</option>
                  ))}
                </select>
                <small style={{ color: '#64748b', fontSize: '0.74rem', marginTop: '4px', display: 'block' }}>
                  Only active Sales Managers are eligible. Sales Executives, Support users and inactive employees are excluded.
                </small>
              </div>

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowAssignModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting || !assigneeId}>
                  {submitting ? 'Assigning...' : 'Assign Sales Manager'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* SUPPORT ASSIGNMENT MODAL - opens immediately after conversion */}
      {showSupportAssignModal && supportAssignLead && (
        <div
          className="modal-backdrop"
          style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 100001, padding: '16px'
          }}
          onClick={closeSupportAssignModal}
        >
          <div
            className="modal-content"
            style={{
              backgroundColor: 'var(--bg-card, #ffffff)',
              border: '1px solid var(--border-color)',
              borderRadius: '16px',
              width: '100%', maxWidth: '620px',
              maxHeight: '90vh', overflowY: 'auto',
              padding: '24px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
              position: 'relative', zIndex: 100002
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '1.18rem', fontWeight: 800, color: 'var(--text-main, #0f172a)', margin: 0 }}>
                  Support Assignment &middot; Lead #{supportAssignLead.id}
                </h3>
                <div style={{ marginTop: '7px' }}>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: '5px',
                    fontSize: '0.73rem', fontWeight: 800,
                    padding: '4px 9px', borderRadius: '12px',
                    backgroundColor: supportAssignLead.support_assigned_to ? '#dcfce7' : '#fef3c7',
                    color: supportAssignLead.support_assigned_to ? '#166534' : '#92400e'
                  }}>
                    {supportAssignLead.support_assigned_to ? 'Support Assigned' : 'Pending Support Assignment'}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={closeSupportAssignModal}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
                aria-label="Close Support Assignment form"
              >
                <X size={20} />
              </button>
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
              gap: '10px',
              backgroundColor: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '14px',
              marginBottom: '18px'
            }}>
              <div>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Lead Name</div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0f172a' }}>
                  {supportAssignLead.name || [supportAssignLead.first_name, supportAssignLead.last_name].filter(Boolean).join(' ') || '—'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Company Name</div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0f172a' }}>
                  {supportAssignLead.company || supportAssignLead.company_name || '—'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Lead ID</div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0f172a' }}>#{supportAssignLead.id}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Current Sales Manager</div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0f172a' }}>
                  {supportAssignLead.sales_manager_name || 'Not Assigned'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Conversion Date</div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0f172a' }}>
                  {formatLeadReceived(supportAssignLead.converted_to_support_at).full}
                </div>
              </div>
              {supportAssignLead.converted_to_support_by_name && (
                <div>
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Converted By</div>
                  <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0f172a' }}>
                    {supportAssignLead.converted_to_support_by_name}
                  </div>
                </div>
              )}
            </div>

            {!canAssignSupport ? (
              <div style={{
                background: '#fffbeb', border: '1px solid #fde68a', color: '#92400e',
                borderRadius: '9px', padding: '12px 14px', fontSize: '0.84rem', fontWeight: 600
              }}>
                The conversion is saved and this lead is now <strong>Pending Support Assignment</strong>.
                Only an Admin or Support Manager can assign an active Support Team employee.
              </div>
            ) : (
              <form onSubmit={handleAssignSupport}>
                <div style={{ marginBottom: '14px' }}>
                  <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.84rem', fontWeight: 700, color: '#334155' }}>
                    Support Team Employee *
                  </label>
                  <select
                    value={supportAgentId}
                    onChange={(e) => {
                      setSupportAgentId(e.target.value);
                      if (supportAssignError) setSupportAssignError('');
                    }}
                    disabled={supportMembersLoading || assigningSupport}
                    style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff' }}
                  >
                    <option value="">
                      {supportMembersLoading ? 'Loading active Support employees...' : 'Select an active Support Team employee...'}
                    </option>
                    {supportTeamMembers.map((member) => (
                      <option key={member.id} value={member.id}>
                        {member.name}{member.role ? ` (${member.role})` : ''}
                      </option>
                    ))}
                  </select>
                  <small style={{ color: '#64748b', fontSize: '0.73rem', marginTop: '5px', display: 'block' }}>
                    Only active Support Team employees are listed. Sales employees, managers/admins, inactive users and other departments are excluded.
                  </small>
                  {!supportMembersLoading && supportTeamMembers.length === 0 && (
                    <small style={{ color: '#b45309', fontSize: '0.73rem', marginTop: '4px', display: 'block', fontWeight: 600 }}>
                      No active Support Team employee is available. Please ask an Admin to activate a Support Executive.
                    </small>
                  )}
                </div>

                <div style={{ marginBottom: '14px' }}>
                  <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.84rem', fontWeight: 700, color: '#334155' }}>
                    Conversion Remarks <span style={{ color: '#94a3b8', fontWeight: 500 }}>(optional)</span>
                  </label>
                  <textarea
                    value={supportRemarks}
                    onChange={(e) => setSupportRemarks(e.target.value)}
                    rows={3}
                    maxLength={2000}
                    placeholder="Add handover notes for the Support team..."
                    style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', resize: 'vertical', fontFamily: 'inherit' }}
                  />
                </div>

                {supportAssignError && (
                  <div style={{
                    display: 'flex', alignItems: 'flex-start', gap: '7px',
                    background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c',
                    borderRadius: '8px', padding: '10px 12px', fontSize: '0.82rem', fontWeight: 600,
                    marginBottom: '14px'
                  }}>
                    <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '1px' }} />
                    <span>{supportAssignError}</span>
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', flexWrap: 'wrap', marginTop: '20px' }}>
                  <button type="button" className="btn btn-outline" onClick={closeSupportAssignModal} disabled={assigningSupport}>
                    {supportAssignLead.support_assigned_to ? 'Close' : 'Assign Later'}
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={assigningSupport || supportMembersLoading || !supportAgentId}
                  >
                    {assigningSupport ? 'Assigning...' : 'Assign to Support'}
                  </button>
                </div>
              </form>
            )}

            {!canAssignSupport && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '20px' }}>
                <button type="button" className="btn btn-primary" onClick={closeSupportAssignModal}>
                  Close
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Click-to-Call IVR Modal */}
      <IVRCallModal 
        isOpen={showCallModal}
        lead={selectedCallLead}
        onClose={() => setShowCallModal(false)}
        onCallComplete={() => {
          fetchLeads(true);
          if (selectedLead) fetchLeadCallLogs(selectedLead.id);
        }}
      />

      {/* Native Quotation Studio Modal (loaded on first use: pdfmake is heavy) */}
      {showBillingModal && (
        <React.Suspense fallback={null}>
          <QuotationModal
            isOpen={showBillingModal}
            onClose={() => setShowBillingModal(false)}
            initialData={billingInitialData}
            onSuccess={handleBillingSuccess}
          />
        </React.Suspense>
      )}

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
