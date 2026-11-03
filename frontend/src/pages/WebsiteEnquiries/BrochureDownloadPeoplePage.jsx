import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Download,
  Eye,
  FileDown,
  FileSpreadsheet,
  FileText,
  Filter,
  Mail,
  MessageCircle,
  Pencil,
  Phone,
  RefreshCw,
  RotateCcw,
  Search,
  TrendingUp,
  UserCheck,
  Users,
  X,
} from 'lucide-react';

import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { formatDateDDMMYYYY, formatLeadReceivedFull } from '../../utils/dateUtils';
import './BrochureDownloadPeoplePage.css';

const PAGE_SIZE = 25;

const STATUS_OPTIONS = [
  { value: 'ALL', label: 'All follow-up statuses' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'FOLLOW_UP', label: 'Follow-up scheduled' },
  { value: 'CONTACTED', label: 'Contacted' },
  { value: 'CONVERTED', label: 'Converted' },
  { value: 'NOT_INTERESTED', label: 'Not interested' },
];

const STATUS_META = {
  PENDING: { label: 'Pending', className: 'is-pending' },
  FOLLOW_UP: { label: 'Follow-up', className: 'is-followup' },
  CONTACTED: { label: 'Contacted', className: 'is-contacted' },
  CONVERTED: { label: 'Converted', className: 'is-converted' },
  NOT_INTERESTED: { label: 'Not interested', className: 'is-not-interested' },
};

const EMPTY_SUMMARY = {
  total_downloads: 0,
  pending_followups: 0,
  contacted_customers: 0,
  converted_customers: 0,
};

const buildPageList = (current, totalPages) => {
  if (!totalPages || totalPages <= 0) return [];
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const pages = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(totalPages - 1, current + 1);
  if (start > 2) pages.push('...');
  for (let i = start; i <= end; i += 1) pages.push(i);
  if (end < totalPages - 1) pages.push('...');
  pages.push(totalPages);
  return pages;
};

const getBrochureLabel = (record) => {
  if (!record) return '—';
  const product = (record.product_name || '').trim();
  const brochure = (record.brochure_name || '').trim();
  if (product && brochure && product.toLowerCase() !== brochure.toLowerCase()) {
    return `${product} · ${brochure}`;
  }
  return brochure || product || '—';
};

const getWhatsAppLink = (record) => {
  if (!record) return null;
  const raw = record.whatsapp_number || record.phone || '';
  let digits = String(raw).replace(/\D/g, '');
  if (!digits) return null;
  const countryDigits = String(record.country_code || '').replace(/\D/g, '');
  if (countryDigits && !digits.startsWith(countryDigits) && digits.length <= 10) {
    digits = `${countryDigits}${digits}`;
  }
  return `https://wa.me/${digits}`;
};

const statusMeta = (status) => STATUS_META[status] || { label: status || '—', className: '' };

const toEditForm = (record) => ({
  followup_status: record?.followup_status || 'PENDING',
  assigned_to: record?.assigned_to ?? '',
  next_followup_date: record?.next_followup_date || '',
  next_followup_time: record?.next_followup_time || '',
});

const BrochureDownloadPeoplePage = () => {
  const { user } = useAuth();
  const normRole = (user?.role || '').toUpperCase();
  const isAdmin = normRole === 'ADMIN';
  const isSalesRole = ['SALES_MANAGER', 'MANAGER', 'SALES_EXECUTIVE', 'SALES', 'EMPLOYEE'].includes(normRole);
  const modulePerms = user?.permissions?.brochure_downloads || {};
  const canEdit = isAdmin || modulePerms.can_edit === true || (modulePerms.can_edit === undefined && isSalesRole);
  const canAssign = isAdmin || modulePerms.can_assign === true;
  const canExport = isAdmin || modulePerms.can_export === true || (modulePerms.can_export === undefined && isSalesRole);
  const canWhatsApp = isAdmin || modulePerms.can_whatsapp !== false;

  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [filterOptions, setFilterOptions] = useState({ brochures: [], employees: [], statuses: [] });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');

  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [brochureFilter, setBrochureFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [employeeFilter, setEmployeeFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  const [selected, setSelected] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [editForm, setEditForm] = useState(toEditForm(null));
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type });
    window.setTimeout(() => setToast(null), 3500);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const queryParams = useMemo(() => {
    const params = {};
    if (search) params.search = search;
    if (brochureFilter !== 'ALL') params.brochure = brochureFilter;
    if (statusFilter !== 'ALL') params.followup_status = statusFilter;
    if (employeeFilter) params.employee_id = employeeFilter;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    return params;
  }, [search, brochureFilter, statusFilter, employeeFilter, dateFrom, dateTo]);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');

    try {
      const [listRes, summaryRes] = await Promise.all([
        API.get('/brochure-enquiries', {
          params: { ...queryParams, page, page_size: PAGE_SIZE },
        }),
        API.get('/brochure-enquiries/summary'),
      ]);

      const payload = listRes.data || {};
      setRecords(Array.isArray(payload.items) ? payload.items : []);
      setTotal(payload.total || 0);
      setTotalPages(payload.total_pages || 0);
      setSummary({ ...EMPTY_SUMMARY, ...(summaryRes.data || {}) });

      if (payload.total_pages && page > payload.total_pages) {
        setPage(payload.total_pages);
      }
    } catch (err) {
      console.error('Failed to load brochure enquiries:', err);
      setError(err.response?.data?.detail || 'Unable to load brochure download enquiries.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, queryParams]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    let mounted = true;
    API.get('/brochure-enquiries/filter-options')
      .then((res) => {
        if (!mounted) return;
        setFilterOptions({
          brochures: res.data?.brochures || [],
          employees: res.data?.employees || [],
          statuses: res.data?.statuses || [],
        });
      })
      .catch((err) => console.error('Failed to load brochure filter options:', err));
    return () => { mounted = false; };
  }, []);

  const resetFilters = () => {
    setSearchInput('');
    setSearch('');
    setBrochureFilter('ALL');
    setStatusFilter('ALL');
    setEmployeeFilter('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const hasActiveFilters = Boolean(
    search || brochureFilter !== 'ALL' || statusFilter !== 'ALL' || employeeFilter || dateFrom || dateTo
  );

  const openDetails = async (record) => {
    setSelected(record);
    setEditForm(toEditForm(record));
    setNote('');
    setDetailLoading(true);
    try {
      const res = await API.get(`/brochure-enquiries/${record.id}`);
      setSelected(res.data);
      setEditForm(toEditForm(res.data));
    } catch (err) {
      console.error('Failed to load brochure enquiry details:', err);
      showToast(err.response?.data?.detail || 'Unable to load the full enquiry details.', 'error');
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetails = () => {
    if (saving) return;
    setSelected(null);
    setNote('');
  };

  const handleWhatsApp = (record) => {
    const link = getWhatsAppLink(record);
    if (!link) {
      showToast('This enquiry does not have a usable WhatsApp number.', 'error');
      return;
    }
    window.open(link, '_blank', 'noopener,noreferrer');
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const payload = {
        followup_status: editForm.followup_status,
        next_followup_date: editForm.next_followup_date || null,
        next_followup_time: editForm.next_followup_time || null,
      };
      if (note.trim()) payload.note = note.trim();
      if (canAssign) {
        payload.assigned_to = editForm.assigned_to ? Number(editForm.assigned_to) : null;
      }

      const res = await API.patch(`/brochure-enquiries/${selected.id}`, payload);
      setSelected(res.data);
      setEditForm(toEditForm(res.data));
      setNote('');
      showToast('Brochure enquiry updated successfully.');
      loadData(true);
    } catch (err) {
      console.error('Failed to update brochure enquiry:', err);
      showToast(err.response?.data?.detail || 'Unable to update the brochure enquiry.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await API.get('/brochure-enquiries/export', {
        params: queryParams,
        responseType: 'blob',
      });
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Brochure_Download_People_${new Date().toISOString().slice(0, 10)}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      showToast('Brochure download records exported to Excel.');
    } catch (err) {
      console.error('Failed to export brochure enquiries:', err);
      showToast(err.response?.data?.detail || 'Unable to export the brochure download records.', 'error');
    } finally {
      setExporting(false);
    }
  };

  const pageList = buildPageList(page, totalPages);
  const startRecord = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const endRecord = Math.min(page * PAGE_SIZE, total);
  const selectedStatus = statusMeta(selected?.followup_status);
  const whatsappLink = getWhatsAppLink(selected);

  return (
    <div className="brochure-page">
      <div className="page-header brochure-page-header">
        <div>
          <h1 className="page-title">
            <span className="brochure-title-icon"><FileDown size={22} /></span>
            Brochure Download People
          </h1>
          <p className="page-subtitle">
            Website brochure download enquiries only. Normal leads, Meta Instant Form leads and other
            enquiries are intentionally excluded.
          </p>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => loadData(true)}
            disabled={refreshing || loading}
          >
            <RefreshCw size={16} className={refreshing ? 'brochure-spin' : ''} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
          {canExport && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleExport}
              disabled={exporting || loading || total === 0}
            >
              <FileSpreadsheet size={16} />
              {exporting ? 'Exporting...' : 'Export Excel'}
            </button>
          )}
        </div>
      </div>

      <div className="brochure-kpi-grid">
        <div className="brochure-kpi-card kpi-purple">
          <span className="brochure-kpi-icon"><Download size={22} /></span>
          <div>
            <span className="brochure-kpi-label">Total brochure downloads</span>
            <strong className="brochure-kpi-value">{summary.total_downloads ?? 0}</strong>
          </div>
        </div>
        <div className="brochure-kpi-card kpi-amber">
          <span className="brochure-kpi-icon"><Clock size={22} /></span>
          <div>
            <span className="brochure-kpi-label">Pending follow-ups</span>
            <strong className="brochure-kpi-value">{summary.pending_followups ?? 0}</strong>
          </div>
        </div>
        <div className="brochure-kpi-card kpi-blue">
          <span className="brochure-kpi-icon"><UserCheck size={22} /></span>
          <div>
            <span className="brochure-kpi-label">Contacted customers</span>
            <strong className="brochure-kpi-value">{summary.contacted_customers ?? 0}</strong>
          </div>
        </div>
        <div className="brochure-kpi-card kpi-green">
          <span className="brochure-kpi-icon"><TrendingUp size={22} /></span>
          <div>
            <span className="brochure-kpi-label">Converted customers</span>
            <strong className="brochure-kpi-value">{summary.converted_customers ?? 0}</strong>
          </div>
        </div>
      </div>

      <div className="content-card brochure-table-card">
        <div className="brochure-toolbar">
          <div className="brochure-search">
            <Search size={17} className="brochure-search-icon" />
            <input
              type="text"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search by customer name, phone, email or brochure..."
              aria-label="Search brochure download people"
            />
            {searchInput && (
              <button
                type="button"
                className="brochure-search-clear"
                onClick={() => setSearchInput('')}
                aria-label="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>

          <div className="brochure-filter-row">
            <label className="brochure-filter">
              <span><FileText size={14} /> Brochure / Product</span>
              <select
                value={brochureFilter}
                onChange={(event) => { setBrochureFilter(event.target.value); setPage(1); }}
              >
                <option value="ALL">All brochures / products</option>
                {filterOptions.brochures.map((brochure) => (
                  <option key={brochure} value={brochure}>{brochure}</option>
                ))}
              </select>
            </label>

            <label className="brochure-filter">
              <span><Filter size={14} /> Status</span>
              <select
                value={statusFilter}
                onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }}
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>

            <label className="brochure-filter">
              <span><Users size={14} /> Assigned employee</span>
              <select
                value={employeeFilter}
                onChange={(event) => { setEmployeeFilter(event.target.value); setPage(1); }}
              >
                <option value="">All employees</option>
                {filterOptions.employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>{employee.name}</option>
                ))}
              </select>
            </label>

            <label className="brochure-filter">
              <span><CalendarDays size={14} /> Downloaded from</span>
              <input
                type="date"
                value={dateFrom}
                max={dateTo || undefined}
                onChange={(event) => { setDateFrom(event.target.value); setPage(1); }}
              />
            </label>

            <label className="brochure-filter">
              <span><CalendarDays size={14} /> Downloaded to</span>
              <input
                type="date"
                value={dateTo}
                min={dateFrom || undefined}
                onChange={(event) => { setDateTo(event.target.value); setPage(1); }}
              />
            </label>

            <button
              type="button"
              className="brochure-reset-btn"
              onClick={resetFilters}
              disabled={!hasActiveFilters}
            >
              <RotateCcw size={14} />
              Reset
            </button>
          </div>
        </div>

        {error && (
          <div className="brochure-error">
            <AlertCircle size={17} />
            <span>{error}</span>
            <button type="button" onClick={() => loadData()}>Try again</button>
          </div>
        )}

        {loading ? (
          <div className="brochure-state">
            <RefreshCw size={22} className="brochure-spin" />
            <span>Loading brochure download enquiries...</span>
          </div>
        ) : records.length === 0 ? (
          <div className="brochure-state">
            <FileDown size={28} />
            <strong>No brochure download enquiries found</strong>
            <span>
              {hasActiveFilters
                ? 'Try clearing the filters or search term.'
                : 'New website brochure form submissions will appear here automatically.'}
            </span>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="custom-table brochure-table">
              <thead>
                <tr>
                  <th>Customer Name</th>
                  <th>WhatsApp Number</th>
                  <th>Email</th>
                  <th>Product / Brochure Name</th>
                  <th>Download Date &amp; Time</th>
                  <th>Assigned Employee</th>
                  <th>Follow-up Status</th>
                  <th className="brochure-actions-head">Actions</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => {
                  const status = statusMeta(record.followup_status);
                  const product = (record.product_name || '').trim();
                  const brochure = (record.brochure_name || '').trim();
                  return (
                    <tr key={record.id}>
                      <td>
                        <div className="brochure-customer">
                          <span className="brochure-avatar">
                            {(record.name || '?').charAt(0).toUpperCase()}
                          </span>
                          <div>
                            <strong>{record.name || '—'}</strong>
                            <span className="brochure-subtext">
                              {record.website_name || 'Company website'}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td>
                        {canWhatsApp && (record.whatsapp_number || record.phone) ? (
                          <button
                            type="button"
                            className="brochure-phone-link"
                            onClick={() => handleWhatsApp(record)}
                            title="Open WhatsApp chat"
                          >
                            <MessageCircle size={14} />
                            {record.whatsapp_number || record.phone}
                          </button>
                        ) : (
                          <span className="brochure-muted">{record.whatsapp_number || record.phone || '—'}</span>
                        )}
                      </td>
                      <td>
                        {record.email ? (
                          <a className="brochure-email" href={`mailto:${record.email}`}>
                            <Mail size={13} />
                            {record.email}
                          </a>
                        ) : (
                          <span className="brochure-muted">—</span>
                        )}
                      </td>
                      <td>
                        <div className="brochure-product-cell">
                          <strong>{brochure || product || '—'}</strong>
                          {product && brochure && product.toLowerCase() !== brochure.toLowerCase() && (
                            <span className="brochure-subtext">Product: {product}</span>
                          )}
                          {record.submission_count > 1 && (
                            <span className="brochure-repeat-note">
                              {record.submission_count} submissions
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="brochure-date-cell">
                          <span>{formatLeadReceivedFull(record.download_at)}</span>
                          {record.last_submitted_at && record.last_submitted_at !== record.download_at && (
                            <span className="brochure-subtext">
                              Last: {formatLeadReceivedFull(record.last_submitted_at)}
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        {record.assigned_employee_name ? (
                          <span className="brochure-assignee">
                            <UserCheck size={13} />
                            {record.assigned_employee_name}
                          </span>
                        ) : (
                          <span className="brochure-unassigned">Unassigned</span>
                        )}
                      </td>
                      <td>
                        <span className={`brochure-status ${status.className}`}>{status.label}</span>
                        {record.next_followup_date && (
                          <span className="brochure-subtext brochure-next-followup">
                            <CalendarDays size={12} />
                            {formatDateDDMMYYYY(record.next_followup_date)}
                            {record.next_followup_time ? ` · ${record.next_followup_time}` : ''}
                          </span>
                        )}
                      </td>
                      <td>
                        <div className="brochure-row-actions">
                          <button
                            type="button"
                            className="brochure-icon-btn"
                            title="View customer details"
                            onClick={() => openDetails(record)}
                          >
                            <Eye size={16} />
                          </button>
                          {canEdit && (
                            <button
                              type="button"
                              className="brochure-icon-btn"
                              title="Edit follow-up"
                              onClick={() => openDetails(record)}
                            >
                              <Pencil size={15} />
                            </button>
                          )}
                          {canWhatsApp && (
                            <button
                              type="button"
                              className="brochure-icon-btn brochure-wa-btn"
                              title="Open WhatsApp chat"
                              onClick={() => handleWhatsApp(record)}
                            >
                              <MessageCircle size={16} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {!loading && total > 0 && (
          <div className="leads-pagination brochure-pagination">
            <div className="leads-pagination-info">
              <span>Showing <strong>{startRecord}</strong>–<strong>{endRecord}</strong> of <strong>{total}</strong></span>
              <span>Page <strong>{page}</strong> of <strong>{totalPages}</strong></span>
            </div>
            <div className="leads-pagination-controls">
              <button
                type="button"
                className="leads-pagination-btn"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={page <= 1}
              >
                <ChevronLeft size={15} /> Previous
              </button>
              <div className="leads-pagination-pages">
                {pageList.map((item, index) => (
                  item === '...' ? (
                    <span key={`gap-${index}`} className="leads-pagination-gap">…</span>
                  ) : (
                    <button
                      key={item}
                      type="button"
                      className={`leads-pagination-page ${item === page ? 'active' : ''}`}
                      onClick={() => setPage(item)}
                      aria-current={item === page ? 'page' : undefined}
                    >
                      {item}
                    </button>
                  )
                ))}
              </div>
              <button
                type="button"
                className="leads-pagination-btn"
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                disabled={page >= totalPages}
              >
                Next <ChevronRight size={15} />
              </button>
            </div>
          </div>
        )}
      </div>

      {selected && (
        <div className="modal-backdrop" role="presentation" onClick={closeDetails}>
          <div
            className="modal-content brochure-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="brochure-detail-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="brochure-modal-header">
              <div className="brochure-modal-title">
                <span className="brochure-avatar brochure-avatar-lg">
                  {(selected.name || '?').charAt(0).toUpperCase()}
                </span>
                <div>
                  <h2 id="brochure-detail-title">{selected.name || 'Brochure enquiry'}</h2>
                  <div className="brochure-modal-meta">
                    <span className={`brochure-status ${selectedStatus.className}`}>{selectedStatus.label}</span>
                    <span className="brochure-subtext">Enquiry #{selected.id}</span>
                    {selected.submission_count > 1 && (
                      <span className="brochure-subtext">{selected.submission_count} submissions</span>
                    )}
                  </div>
                </div>
              </div>
              <button type="button" className="brochure-icon-btn" onClick={closeDetails} aria-label="Close details">
                <X size={18} />
              </button>
            </div>

            <div className="brochure-modal-body">
              {detailLoading && (
                <div className="brochure-detail-loading">
                  <RefreshCw size={16} className="brochure-spin" /> Refreshing latest details...
                </div>
              )}

              <div className="brochure-detail-grid">
                <div className="brochure-detail-item">
                  <span className="brochure-detail-label"><Phone size={14} /> WhatsApp number</span>
                  <strong>{selected.whatsapp_number || selected.phone || '—'}</strong>
                  {selected.country_code && <span className="brochure-subtext">Country code: {selected.country_code}</span>}
                </div>
                <div className="brochure-detail-item">
                  <span className="brochure-detail-label"><Mail size={14} /> Email</span>
                  <strong>{selected.email || '—'}</strong>
                </div>
                <div className="brochure-detail-item">
                  <span className="brochure-detail-label"><FileText size={14} /> Product / brochure</span>
                  <strong>{getBrochureLabel(selected)}</strong>
                  {selected.brochure_id && <span className="brochure-subtext">Brochure ID: {selected.brochure_id}</span>}
                </div>
                <div className="brochure-detail-item">
                  <span className="brochure-detail-label"><CalendarDays size={14} /> Download date &amp; time</span>
                  <strong>{formatLeadReceivedFull(selected.download_at)}</strong>
                  {selected.last_submitted_at && selected.last_submitted_at !== selected.download_at && (
                    <span className="brochure-subtext">Last submission: {formatLeadReceivedFull(selected.last_submitted_at)}</span>
                  )}
                </div>
                <div className="brochure-detail-item">
                  <span className="brochure-detail-label"><UserCheck size={14} /> Assigned employee</span>
                  <strong>{selected.assigned_employee_name || 'Unassigned'}</strong>
                </div>
                <div className="brochure-detail-item">
                  <span className="brochure-detail-label"><FileDown size={14} /> Website source</span>
                  <strong>{selected.website_name || selected.website_id || 'Company website'}</strong>
                  {selected.campaign && <span className="brochure-subtext">Campaign: {selected.campaign}</span>}
                </div>
                {selected.landing_page && (
                  <div className="brochure-detail-item brochure-detail-wide">
                    <span className="brochure-detail-label"><Download size={14} /> Landing page</span>
                    <a href={selected.landing_page} target="_blank" rel="noreferrer">{selected.landing_page}</a>
                  </div>
                )}
                {(selected.lead_id || selected.customer_id) && (
                  <div className="brochure-detail-item brochure-detail-wide">
                    <span className="brochure-detail-label"><Users size={14} /> Existing CRM reference</span>
                    <strong>
                      {selected.lead_id ? `Lead #${selected.lead_id}${selected.linked_lead_name ? ` · ${selected.linked_lead_name}` : ''}` : ''}
                      {selected.lead_id && selected.customer_id ? ' | ' : ''}
                      {selected.customer_id ? `Customer #${selected.customer_id}${selected.linked_customer_name ? ` · ${selected.linked_customer_name}` : ''}` : ''}
                    </strong>
                    <span className="brochure-subtext">Reference only; this enquiry is not listed as a normal lead.</span>
                  </div>
                )}
                {selected.message && (
                  <div className="brochure-detail-item brochure-detail-wide">
                    <span className="brochure-detail-label"><AlertCircle size={14} /> Website message</span>
                    <p className="brochure-message">{selected.message}</p>
                  </div>
                )}
              </div>

              <div className="brochure-followup-panel">
                <div className="brochure-panel-heading">
                  <div>
                    <h3>Follow-up &amp; notes</h3>
                    <p>Keep the website brochure follow-up status and internal notes on this dedicated record.</p>
                  </div>
                </div>

                <div className="brochure-followup-grid">
                  <label className="brochure-field">
                    <span>Follow-up status</span>
                    <select
                      value={editForm.followup_status}
                      onChange={(event) => setEditForm((current) => ({ ...current, followup_status: event.target.value }))}
                      disabled={!canEdit || saving}
                    >
                      {STATUS_OPTIONS.filter((option) => option.value !== 'ALL').map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>

                  <label className="brochure-field">
                    <span>Assigned employee</span>
                    {canAssign ? (
                      <select
                        value={editForm.assigned_to}
                        onChange={(event) => setEditForm((current) => ({ ...current, assigned_to: event.target.value }))}
                        disabled={saving}
                      >
                        <option value="">Unassigned</option>
                        {filterOptions.employees.map((employee) => (
                          <option key={employee.id} value={employee.id}>{employee.name}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={selected.assigned_employee_name || 'Unassigned'}
                        readOnly
                      />
                    )}
                  </label>

                  <label className="brochure-field">
                    <span>Next follow-up date</span>
                    <input
                      type="date"
                      value={editForm.next_followup_date}
                      onChange={(event) => setEditForm((current) => ({ ...current, next_followup_date: event.target.value }))}
                      disabled={!canEdit || saving}
                    />
                  </label>

                  <label className="brochure-field">
                    <span>Next follow-up time</span>
                    <input
                      type="time"
                      value={editForm.next_followup_time}
                      onChange={(event) => setEditForm((current) => ({ ...current, next_followup_time: event.target.value }))}
                      disabled={!canEdit || saving}
                    />
                  </label>
                </div>

                <label className="brochure-field brochure-note-field">
                  <span>Add a note</span>
                  <textarea
                    rows={3}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    placeholder="Add call outcome, customer response, or next steps..."
                    disabled={!canEdit || saving}
                  />
                </label>

                {selected.notes && (
                  <div className="brochure-notes-history">
                    <span className="brochure-detail-label">Notes history</span>
                    <pre>{selected.notes}</pre>
                  </div>
                )}
              </div>
            </div>

            <div className="brochure-modal-footer">
              <div className="brochure-modal-footer-left">
                {canWhatsApp && whatsappLink && (
                  <button type="button" className="btn btn-secondary" onClick={() => handleWhatsApp(selected)}>
                    <MessageCircle size={16} /> WhatsApp
                  </button>
                )}
                {selected.last_contacted_at && (
                  <span className="brochure-subtext">
                    Last contacted: {formatLeadReceivedFull(selected.last_contacted_at)}
                  </span>
                )}
              </div>
              <div className="brochure-modal-footer-right">
                <button type="button" className="btn btn-secondary" onClick={closeDetails} disabled={saving}>
                  Close
                </button>
                {canEdit && (
                  <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saving}>
                    {saving ? <RefreshCw size={15} className="brochure-spin" /> : <CheckCircle2 size={15} />}
                    {saving ? 'Saving...' : 'Save changes'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className={`brochure-toast ${toast.type === 'error' ? 'is-error' : ''}`}>
          {toast.type === 'error' ? <AlertCircle size={17} /> : <CheckCircle2 size={17} />}
          <span>{toast.message}</span>
        </div>
      )}
    </div>
  );
};

export default BrochureDownloadPeoplePage;
