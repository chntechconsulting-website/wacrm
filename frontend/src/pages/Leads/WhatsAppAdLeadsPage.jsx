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
  FileSpreadsheet,
  Filter,
  Megaphone,
  MessageCircle,
  Phone,
  RefreshCw,
  RotateCcw,
  Search,
  Target,
  UserCheck,
  Users,
  X,
} from 'lucide-react';

import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { formatLeadReceivedFull } from '../../utils/dateUtils';
import './WhatsAppAdLeadsPage.css';

const PAGE_SIZE = 25;

const EMPTY_SUMMARY = {
  total: 0,
  unassigned: 0,
  assigned: 0,
  campaigns: 0,
  resolved_attribution: 0,
  pending_attribution: 0,
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

const statusClass = (status) => {
  const value = (status || '').toUpperCase();
  if (value.includes('CONVERTED') || value.includes('WON')) return 'is-won';
  if (value.includes('LOST') || value.includes('NOT')) return 'is-lost';
  if (value.includes('RE-INQUIRY') || value.includes('REINQUIRY')) return 'is-reinquiry';
  if (value.includes('CONTACTED')) return 'is-contacted';
  if (value.includes('INTERESTED')) return 'is-interested';
  if (value.includes('FOLLOW')) return 'is-followup';
  if (value.includes('ASSIGNED')) return 'is-assigned';
  return 'is-new';
};

const campaignLabel = (record) =>
  record?.campaign_name || record?.campaign_id || 'Not resolved yet';

const adLabel = (record) => record?.ad_name || record?.source_id || '—';

const WhatsAppAdLeadsPage = () => {
  const { user } = useAuth();
  const role = (user?.role || '').toUpperCase();
  const isAdmin = role === 'ADMIN';
  const isSalesRole = ['SALES_MANAGER', 'MANAGER', 'SALES_EXECUTIVE', 'SALES', 'EMPLOYEE'].includes(role);
  const leadPerms = user?.permissions?.leads || {};
  const canEdit = isAdmin || leadPerms.can_edit === true || (leadPerms.can_edit === undefined && isSalesRole);
  const canExport = isAdmin || leadPerms.can_export === true || (leadPerms.can_export === undefined && isSalesRole);

  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [filterOptions, setFilterOptions] = useState({ campaigns: [], employees: [], statuses: [] });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);

  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [campaign, setCampaign] = useState('ALL');
  const [employeeId, setEmployeeId] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  const [selected, setSelected] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [resolving, setResolving] = useState(false);

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
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    if (campaign && campaign !== 'ALL') params.campaign = campaign;
    if (employeeId) params.employee_id = employeeId;
    if (statusFilter && statusFilter !== 'ALL') params.status = statusFilter;
    return params;
  }, [search, dateFrom, dateTo, campaign, employeeId, statusFilter]);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const [listRes, summaryRes] = await Promise.all([
        API.get('/whatsapp-ad-leads', {
          params: { ...queryParams, page, page_size: PAGE_SIZE },
        }),
        API.get('/whatsapp-ad-leads/summary'),
      ]);
      const payload = listRes.data || {};
      setItems(Array.isArray(payload.items) ? payload.items : []);
      setTotal(payload.total || 0);
      setTotalPages(payload.total_pages || 0);
      setSummary({ ...EMPTY_SUMMARY, ...(summaryRes.data || {}) });
      if (payload.total_pages && page > payload.total_pages) {
        setPage(payload.total_pages);
      }
    } catch (err) {
      console.error('Failed to load WhatsApp Ad leads:', err);
      setError(err.response?.data?.detail || 'Unable to load WhatsApp Ad leads.');
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
    API.get('/whatsapp-ad-leads/filter-options')
      .then((res) => {
        if (!mounted) return;
        setFilterOptions({
          campaigns: res.data?.campaigns || [],
          employees: res.data?.employees || [],
          statuses: res.data?.statuses || [],
        });
      })
      .catch((err) => console.error('Failed to load WhatsApp Ad filter options:', err));
    return () => { mounted = false; };
  }, []);

  const resetFilters = () => {
    setSearchInput('');
    setSearch('');
    setDateFrom('');
    setDateTo('');
    setCampaign('ALL');
    setEmployeeId('');
    setStatusFilter('ALL');
    setPage(1);
  };

  const hasActiveFilters = Boolean(
    search || dateFrom || dateTo || campaign !== 'ALL' || employeeId || statusFilter !== 'ALL'
  );

  const openDetails = async (record) => {
    setSelected(record);
    setDetailLoading(true);
    try {
      const res = await API.get(`/whatsapp-ad-leads/${record.id}`);
      setSelected(res.data);
    } catch (err) {
      console.error('Failed to load WhatsApp Ad lead details:', err);
      showToast(err.response?.data?.detail || 'Unable to load the enquiry details.', 'error');
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetails = () => {
    if (resolving) return;
    setSelected(null);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await API.get('/whatsapp-ad-leads/export', {
        params: queryParams,
        responseType: 'blob',
      });
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `WhatsApp_Ad_Leads_${new Date().toISOString().slice(0, 10)}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      showToast('WhatsApp Ad leads exported to Excel.');
    } catch (err) {
      console.error('Failed to export WhatsApp Ad leads:', err);
      showToast(err.response?.data?.detail || 'Unable to export WhatsApp Ad leads.', 'error');
    } finally {
      setExporting(false);
    }
  };

  const handleResolve = async () => {
    if (!selected) return;
    setResolving(true);
    try {
      const res = await API.post(`/whatsapp-ad-leads/${selected.id}/resolve-attribution`);
      const data = res.data || {};
      setSelected((prev) => ({
        ...prev,
        campaign_id: data.campaign_id ?? prev?.campaign_id,
        campaign_name: data.campaign_name ?? prev?.campaign_name,
        ad_name: data.ad_name ?? prev?.ad_name,
        resolution_status: data.resolution_status ?? prev?.resolution_status,
        resolution_error: data.error ?? prev?.resolution_error,
      }));
      if (data.success) {
        showToast('Campaign and ad names resolved from Meta.');
      } else {
        showToast(data.error || 'Meta could not resolve this ad yet.', 'error');
      }
      loadData(true);
    } catch (err) {
      console.error('Failed to resolve ad attribution:', err);
      showToast(err.response?.data?.detail || 'Unable to resolve campaign/ad details.', 'error');
    } finally {
      setResolving(false);
    }
  };

  const pageList = buildPageList(page, totalPages);
  const startRecord = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const endRecord = Math.min(page * PAGE_SIZE, total);

  return (
    <div className="wa-ad-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <span className="wa-ad-title-icon"><MessageCircle size={22} /></span>
            WhatsApp Ad Leads
            <span className="wa-ad-source-pill">WhatsApp Ads</span>
          </h1>
          <p className="page-subtitle">
            Leads captured automatically from Meta Click-to-WhatsApp ads, with ad click attribution.
            Meta Instant Form leads remain under Meta Ads Leads.
          </p>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => loadData(true)}
            disabled={refreshing || loading}
          >
            <RefreshCw size={16} className={refreshing ? 'wa-ad-spin' : ''} />
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

      {toast && (
        <div className={`wa-ad-toast ${toast.type === 'error' ? 'is-error' : ''}`}>
          {toast.type === 'error' ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
          <span>{toast.message}</span>
        </div>
      )}

      {error && (
        <div className="wa-ad-alert">
          <AlertCircle size={18} /> <span>{String(error)}</span>
        </div>
      )}

      <div className="wa-ad-kpis">
        <div className="wa-ad-kpi">
          <span className="wa-ad-kpi-icon is-purple"><MessageCircle size={20} /></span>
          <div>
            <span className="wa-ad-kpi-label">Total ad enquiries</span>
            <strong className="wa-ad-kpi-value">{summary.total ?? 0}</strong>
          </div>
        </div>
        <div className="wa-ad-kpi">
          <span className="wa-ad-kpi-icon is-amber"><Clock size={20} /></span>
          <div>
            <span className="wa-ad-kpi-label">Unassigned</span>
            <strong className="wa-ad-kpi-value">{summary.unassigned ?? 0}</strong>
          </div>
        </div>
        <div className="wa-ad-kpi">
          <span className="wa-ad-kpi-icon is-blue"><Target size={20} /></span>
          <div>
            <span className="wa-ad-kpi-label">Campaigns resolved</span>
            <strong className="wa-ad-kpi-value">{summary.campaigns ?? 0}</strong>
          </div>
        </div>
        <div className="wa-ad-kpi">
          <span className="wa-ad-kpi-icon is-teal"><UserCheck size={20} /></span>
          <div>
            <span className="wa-ad-kpi-label">Assigned to team</span>
            <strong className="wa-ad-kpi-value">{summary.assigned ?? 0}</strong>
          </div>
        </div>
      </div>

      <div className="content-card wa-ad-table-card">
        <div className="wa-ad-toolbar">
          <div className="wa-ad-search">
            <Search size={17} className="wa-ad-search-icon" />
            <input
              type="text"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search name, phone, campaign, ad ID or click ID..."
              aria-label="Search WhatsApp Ad leads"
            />
            {searchInput && (
              <button
                type="button"
                className="wa-ad-search-clear"
                onClick={() => setSearchInput('')}
                aria-label="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>

          <div className="wa-ad-filter-grid">
            <label className="wa-ad-filter">
              <span><CalendarDays size={14} /> From date</span>
              <input
                type="date"
                value={dateFrom}
                onChange={(event) => { setDateFrom(event.target.value); setPage(1); }}
              />
            </label>

            <label className="wa-ad-filter">
              <span><CalendarDays size={14} /> To date</span>
              <input
                type="date"
                value={dateTo}
                onChange={(event) => { setDateTo(event.target.value); setPage(1); }}
              />
            </label>

            <label className="wa-ad-filter">
              <span><Megaphone size={14} /> Campaign</span>
              <select
                value={campaign}
                onChange={(event) => { setCampaign(event.target.value); setPage(1); }}
              >
                <option value="ALL">All campaigns</option>
                {filterOptions.campaigns.map((option) => (
                  <option key={option.id} value={option.id}>{option.name}</option>
                ))}
              </select>
            </label>

            <label className="wa-ad-filter">
              <span><Users size={14} /> Assigned employee</span>
              <select
                value={employeeId}
                onChange={(event) => { setEmployeeId(event.target.value); setPage(1); }}
              >
                <option value="">All employees</option>
                {filterOptions.employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>{employee.name}</option>
                ))}
              </select>
            </label>

            <label className="wa-ad-filter">
              <span><Filter size={14} /> Status</span>
              <select
                value={statusFilter}
                onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }}
              >
                <option value="ALL">All statuses</option>
                {filterOptions.statuses.map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </label>

            {hasActiveFilters && (
              <button type="button" className="wa-ad-reset" onClick={resetFilters}>
                <RotateCcw size={14} /> Clear filters
              </button>
            )}
          </div>
        </div>

        <div className="table-responsive">
          <table className="custom-table wa-ad-table">
            <thead>
              <tr>
                <th style={{ minWidth: '190px' }}>Customer</th>
                <th style={{ minWidth: '260px' }}>First Enquiry Message</th>
                <th style={{ minWidth: '170px' }}>Campaign</th>
                <th style={{ minWidth: '160px' }}>Ad</th>
                <th style={{ minWidth: '160px' }}>Received</th>
                <th style={{ minWidth: '150px' }}>Assigned To</th>
                <th style={{ minWidth: '130px' }}>Status</th>
                <th style={{ minWidth: '90px' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8}>
                    <div className="wa-ad-empty">Loading WhatsApp Ad leads…</div>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <div className="wa-ad-empty">
                      <MessageCircle size={30} />
                      <strong>No WhatsApp Ad leads yet</strong>
                      <span>
                        Leads appear here automatically when a customer messages your WhatsApp
                        Business number from a Meta Click-to-WhatsApp ad.
                      </span>
                    </div>
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id}>
                    <td className="wa-ad-customer-cell">
                      <div className="wa-ad-customer-name">
                        {item.customer_name}
                        <span className="wa-ad-row-badge">WhatsApp Ads</span>
                      </div>
                      <div className="wa-ad-phone">
                        <Phone size={12} /> {item.phone}
                      </div>
                      {item.is_reinquiry && (
                        <div className="wa-ad-reinquiry-note">
                          Re-inquiry #{item.reinquiry_count}
                        </div>
                      )}
                    </td>
                    <td className="wa-ad-message-cell">
                      <div className="wa-ad-message" title={item.first_enquiry_message || ''}>
                        {item.first_enquiry_message || '—'}
                      </div>
                      <div className="wa-ad-muted">
                        {formatLeadReceivedFull(item.message_timestamp)}
                      </div>
                    </td>
                    <td className="wa-ad-campaign-cell">
                      <div className="wa-ad-strong">{campaignLabel(item)}</div>
                      {item.campaign_id && item.campaign_name && (
                        <div className="wa-ad-muted">ID: {item.campaign_id}</div>
                      )}
                    </td>
                    <td className="wa-ad-campaign-cell">
                      <div className="wa-ad-strong">{adLabel(item)}</div>
                      {item.headline && (
                        <div className="wa-ad-muted" title={item.headline}>{item.headline}</div>
                      )}
                    </td>
                    <td>
                      <div className="wa-ad-strong">{formatLeadReceivedFull(item.created_at)}</div>
                      <div className="wa-ad-muted">Lead received</div>
                    </td>
                    <td>
                      {item.assigned_employee_name ? (
                        <div className="wa-ad-strong">{item.assigned_employee_name}</div>
                      ) : (
                        <span className="wa-ad-unassigned">Unassigned</span>
                      )}
                    </td>
                    <td>
                      <span className={`wa-ad-status ${statusClass(item.status)}`}>
                        {item.status || 'NEW'}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="wa-ad-view-btn"
                        onClick={() => openDetails(item)}
                      >
                        <Eye size={15} /> View
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {!loading && total > 0 && (
          <div className="leads-pagination wa-ad-pagination">
            <div className="leads-pagination-info">
              <span>Showing <strong>{startRecord}</strong>–<strong>{endRecord}</strong> of <strong>{total}</strong> ad enquiries</span>
              <span>Page <strong>{page}</strong> of <strong>{totalPages}</strong></span>
            </div>
            <div className="leads-pagination-controls">
              <button
                type="button"
                className="leads-pagination-btn"
                onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                disabled={page <= 1 || loading}
              >
                <ChevronLeft size={14} /> Previous
              </button>
              <div className="leads-pagination-pages">
                {pageList.map((entry, index) => (
                  entry === '...' ? (
                    <span key={`ellipsis-${index}`} className="wa-ad-ellipsis">…</span>
                  ) : (
                    <button
                      key={entry}
                      type="button"
                      className={`leads-pagination-page ${entry === page ? 'active' : ''}`}
                      onClick={() => setPage(entry)}
                      disabled={loading}
                    >
                      {entry}
                    </button>
                  )
                ))}
              </div>
              <button
                type="button"
                className="leads-pagination-btn"
                onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
                disabled={page >= totalPages || loading}
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {selected && (
        <div className="wa-ad-modal-backdrop" onClick={closeDetails}>
          <div className="wa-ad-modal" onClick={(event) => event.stopPropagation()}>
            <div className="wa-ad-modal-header">
              <div>
                <h2>
                  <MessageCircle size={20} /> {selected.customer_name}
                  <span className="wa-ad-source-pill">WhatsApp Ads</span>
                </h2>
                <p>
                  <Phone size={13} /> {selected.phone}
                  {selected.lead_id ? ` · Lead #${selected.lead_id}` : ''}
                  {selected.is_reinquiry ? ` · Re-inquiry #${selected.reinquiry_count}` : ''}
                </p>
              </div>
              <button type="button" className="wa-ad-modal-close" onClick={closeDetails} aria-label="Close details">
                <X size={18} />
              </button>
            </div>

            {detailLoading ? (
              <div className="wa-ad-empty">Loading enquiry details…</div>
            ) : (
              <div className="wa-ad-modal-body">
                <div className="wa-ad-detail-grid">
                  <div className="wa-ad-detail">
                    <span>Status</span>
                    <strong className={`wa-ad-status ${statusClass(selected.status)}`}>{selected.status || 'NEW'}</strong>
                  </div>
                  <div className="wa-ad-detail">
                    <span>Assigned employee</span>
                    <strong>{selected.assigned_employee_name || 'Unassigned'}</strong>
                  </div>
                  <div className="wa-ad-detail">
                    <span>Campaign</span>
                    <strong>{campaignLabel(selected)}</strong>
                    {selected.campaign_id && <small>ID: {selected.campaign_id}</small>}
                  </div>
                  <div className="wa-ad-detail">
                    <span>Ad</span>
                    <strong>{adLabel(selected)}</strong>
                    {selected.ad_name && selected.source_id && <small>ID: {selected.source_id}</small>}
                  </div>
                  <div className="wa-ad-detail">
                    <span>Attribution</span>
                    <strong>{selected.resolution_status || 'PENDING'}</strong>
                    {selected.resolution_error && <small>{selected.resolution_error}</small>}
                  </div>
                  <div className="wa-ad-detail">
                    <span>Received</span>
                    <strong>{formatLeadReceivedFull(selected.created_at)}</strong>
                    <small>Message: {formatLeadReceivedFull(selected.message_timestamp)}</small>
                  </div>
                </div>

                <div className="wa-ad-detail-section">
                  <h3>First enquiry message</h3>
                  <p className="wa-ad-message-full">{selected.first_enquiry_message || '—'}</p>
                </div>

                <div className="wa-ad-detail-section">
                  <h3>Ad click attribution</h3>
                  <div className="wa-ad-detail-grid">
                    <div className="wa-ad-detail">
                      <span>CTWA click ID</span>
                      <strong className="wa-ad-mono">{selected.ctwa_clid || 'Not provided by Meta'}</strong>
                    </div>
                    <div className="wa-ad-detail">
                      <span>Channel</span>
                      <strong>{selected.channel || 'WhatsApp'}</strong>
                    </div>
                    <div className="wa-ad-detail">
                      <span>Referral source type</span>
                      <strong>{selected.source_type || '—'}</strong>
                    </div>
                    <div className="wa-ad-detail">
                      <span>Ad ID (source_id)</span>
                      <strong className="wa-ad-mono">{selected.source_id || '—'}</strong>
                    </div>
                    <div className="wa-ad-detail">
                      <span>Source URL</span>
                      {selected.source_url ? (
                        <a href={selected.source_url} target="_blank" rel="noopener noreferrer">
                          Open ad link
                        </a>
                      ) : (
                        <strong>—</strong>
                      )}
                    </div>
                  </div>
                  {selected.headline && (
                    <div className="wa-ad-referral-box">
                      <strong>{selected.headline}</strong>
                      {selected.ad_body && <p>{selected.ad_body}</p>}
                    </div>
                  )}
                </div>

                {selected.lead && (
                  <div className="wa-ad-detail-section">
                    <h3>Lead profile</h3>
                    <div className="wa-ad-detail-grid">
                      <div className="wa-ad-detail">
                        <span>Lead source</span>
                        <strong>{selected.lead.source || 'WHATSAPP_ADS'}</strong>
                      </div>
                      <div className="wa-ad-detail">
                        <span>Total enquiries</span>
                        <strong>{selected.lead.total_enquiries || 1}</strong>
                      </div>
                      <div className="wa-ad-detail">
                        <span>Original requirement</span>
                        <strong>{selected.lead.requirement_notes || '—'}</strong>
                      </div>
                      <div className="wa-ad-detail">
                        <span>Email / company</span>
                        <strong>{selected.lead.email || '—'} · {selected.lead.company || '—'}</strong>
                      </div>
                    </div>
                  </div>
                )}

                {Array.isArray(selected.enquiries) && selected.enquiries.length > 0 && (
                  <div className="wa-ad-detail-section">
                    <h3>Enquiry history</h3>
                    <div className="wa-ad-history">
                      {selected.enquiries.map((enquiry) => (
                        <div key={enquiry.id} className="wa-ad-history-row">
                          <span>#{enquiry.enquiry_number} · {enquiry.enquiry_type}</span>
                          <strong>{enquiry.source}</strong>
                          <span>{formatLeadReceivedFull(enquiry.created_at)}</span>
                          {enquiry.requirement_notes && <p>{enquiry.requirement_notes}</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selected.raw_referral && (
                  <div className="wa-ad-detail-section">
                    <details>
                      <summary>Raw Meta referral payload</summary>
                      <pre>{JSON.stringify(selected.raw_referral, null, 2)}</pre>
                    </details>
                  </div>
                )}

                <div className="wa-ad-modal-actions">
                  {canEdit && (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={handleResolve}
                      disabled={resolving}
                    >
                      <Download size={15} className={resolving ? 'wa-ad-spin' : ''} />
                      {resolving ? 'Resolving…' : 'Resolve campaign / ad name'}
                    </button>
                  )}
                  <button type="button" className="btn btn-primary" onClick={closeDetails}>
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default WhatsAppAdLeadsPage;
