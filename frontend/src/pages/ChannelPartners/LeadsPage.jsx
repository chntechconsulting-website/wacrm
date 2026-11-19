import React, { useCallback, useEffect, useState } from 'react';
import { RefreshCw, Search, UserPlus } from 'lucide-react';
import API from '../../services/api';
import {
  DefinitionList,
  EmptyState,
  ErrorState,
  JsonBlock,
  LoadingState,
  Modal,
  PageHeader,
  Pagination,
  Panel,
  PartnerFilter,
  RefreshButton,
  StatusBadge,
  TableShell,
  buildQuery,
  formatDateTime,
  usePartnerOptions,
  valueOrDash,
} from './ChannelPartnerShared';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'qualified', label: 'Qualified' },
  { value: 'converted', label: 'Converted' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'lost', label: 'Lost' },
];

// Only CRM statuses with a documented WA HRMS equivalent can be pushed from
// this page. Converted must go through the All Leads WON workflow so the CRM
// finance and Support handoffs stay consistent.
const CRM_STATUS_OPTIONS = [
  { value: 'NEW', label: 'NEW / NEW LEAD — WA HRMS: submitted' },
  { value: 'QUALIFIED', label: 'QUALIFIED — WA HRMS: qualified' },
  { value: 'REJECTED', label: 'REJECTED — WA HRMS: rejected' },
  { value: 'LOST', label: 'LOST — WA HRMS: lost' },
];

const CP_REVIEW_NOTE_REQUIRED_MESSAGE =
  'A review note is required when marking a Channel Partner lead as rejected or lost. The note is shown to the partner.';

const normalizeCrmStatus = (value) => String(value || '')
  .trim()
  .toUpperCase()
  .replace(/[-\s]+/g, '_');

// NEW and NEW LEAD both mean the WA HRMS "submitted" state, so the editor
// shows them as the same canonical option.
const canonicalCrmStatus = (value) => {
  const normalized = normalizeCrmStatus(value);
  return normalized === 'NEW_LEAD' ? 'NEW' : normalized;
};

const SYNC_STATUS_META = {
  SYNCED: { label: 'Synced', tone: 'green' },
  PENDING: { label: 'Pending Sync', tone: 'amber' },
  FAILED: { label: 'Failed', tone: 'red' },
};

function SyncBadge({ status }) {
  const meta = SYNC_STATUS_META[String(status || '').toUpperCase()] || {
    label: 'Not Synced',
    tone: 'slate',
  };
  return <span className={`cp-badge cp-badge-${meta.tone}`}>{meta.label}</span>;
}

export default function ChannelPartnerLeadsPage() {
  const partnerOptions = usePartnerOptions();
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [partnerId, setPartnerId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [crmStatus, setCrmStatus] = useState('');
  const [reviewNote, setReviewNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [syncError, setSyncError] = useState('');
  const [syncMessage, setSyncMessage] = useState('');

  const fetchLeads = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const response = await API.get('/channel-partners/leads', {
        params: buildQuery({
          page,
          limit: 25,
          status,
          partnerId,
          from: dateFrom,
          to: dateTo,
          search,
        }),
        skipCache: isRefresh,
      });
      setRows(Array.isArray(response.data?.items) ? response.data.items : []);
      setPagination(response.data?.pagination || null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Partner leads could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, status, partnerId, dateFrom, dateTo, search]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  const applySearch = (event) => {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  };

  const resetFilters = () => {
    setSearchInput('');
    setSearch('');
    setStatus('');
    setPartnerId('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const resetSyncEditor = (row) => {
    const normalized = canonicalCrmStatus(row?.crmStatus);
    setCrmStatus(CRM_STATUS_OPTIONS.some((option) => option.value === normalized) ? normalized : '');
    setReviewNote('');
    setSyncError('');
    setSyncMessage('');
  };

  const applyUpdatedLead = (data) => {
    if (!data) return;
    setSelected((prev) => (prev && prev.id === data.id ? { ...prev, ...data } : prev));
    setRows((prev) => prev.map((item) => (item.id === data.id ? { ...item, ...data } : item)));
  };

  const openLead = async (row) => {
    setSelected(row);
    setDetailError('');
    resetSyncEditor(row);
    setDetailLoading(true);
    try {
      const response = await API.get(`/channel-partners/leads/${encodeURIComponent(row.id)}`, {
        skipCache: true,
      });
      setSelected(response.data || row);
      resetSyncEditor(response.data || row);
    } catch (err) {
      setDetailError(err.response?.data?.detail || 'Lead detail could not be loaded.');
    } finally {
      setDetailLoading(false);
    }
  };

  const submitStatusChange = async (event) => {
    event.preventDefault();
    if (!selected) return;
    const target = normalizeCrmStatus(crmStatus);
    if (!target) {
      setSyncError('Select the CRM status to send to WA HRMS.');
      return;
    }
    const note = reviewNote.trim();
    if ((target === 'LOST' || target === 'REJECTED') && !note) {
      setSyncError(CP_REVIEW_NOTE_REQUIRED_MESSAGE);
      return;
    }
    if (
      target === normalizeCrmStatus(selected.crmStatus) &&
      String(selected.syncStatus || '').toUpperCase() === 'SYNCED' &&
      !note
    ) {
      setSyncMessage('CRM and WA HRMS are already synchronized for this status.');
      return;
    }

    setSaving(true);
    setSyncError('');
    setSyncMessage('');
    try {
      const response = await API.put(
        `/channel-partners/leads/${encodeURIComponent(selected.id)}/status`,
        { status: target, review_note: note || undefined },
      );
      const data = response.data || {};
      applyUpdatedLead(data);
      if (String(data.syncStatus || '').toUpperCase() === 'FAILED') {
        setSyncError(
          data.lastSyncError ||
          data.syncMessage ||
          'WA HRMS rejected the status update. The CRM status was still saved.',
        );
      } else {
        setSyncMessage(data.syncMessage || 'CRM status updated and synced to WA HRMS.');
        setReviewNote('');
      }
    } catch (err) {
      setSyncError(err.response?.data?.detail || 'Failed to update the Channel Partner lead status.');
    } finally {
      setSaving(false);
    }
  };

  const retrySync = async () => {
    if (!selected) return;
    setSaving(true);
    setSyncError('');
    setSyncMessage('');
    try {
      const response = await API.post(
        `/channel-partners/leads/${encodeURIComponent(selected.id)}/retry-sync`,
      );
      const data = response.data || {};
      applyUpdatedLead(data);
      if (String(data.syncStatus || '').toUpperCase() === 'FAILED') {
        setSyncError(data.lastSyncError || data.syncMessage || 'WA HRMS rejected the retry.');
      } else {
        setSyncMessage(data.syncMessage || 'WA HRMS sync retried.');
      }
    } catch (err) {
      setSyncError(err.response?.data?.detail || 'Failed to retry WA HRMS sync.');
    } finally {
      setSaving(false);
    }
  };

  const requiresNote = ['LOST', 'REJECTED'].includes(normalizeCrmStatus(crmStatus));
  const noteMissing = requiresNote && !reviewNote.trim();
  const canRetrySync = ['FAILED', 'PENDING'].includes(
    String(selected?.syncStatus || '').toUpperCase(),
  );

  return (
    <div className="cp-page">
      <PageHeader
        title="Partner Leads"
        description="Leads shared by channel partners. Status changes made here are pushed to WA HRMS through PATCH /leads/{id}."
        actions={<RefreshButton onClick={() => fetchLeads(true)} refreshing={refreshing} />}
      />

      <Panel title="Filters" description="Filter by partner, status, creation date or search by company, contact, email, phone or lead ID.">
        <form className="cp-filters" onSubmit={applySearch}>
          <label className="cp-field cp-grow">
            <span>Search</span>
            <input
              type="search"
              value={searchInput}
              placeholder="Company, contact, email, phone or lead ID…"
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </label>
          <PartnerFilter
            value={partnerId}
            onChange={(value) => { setPartnerId(value); setPage(1); }}
            options={partnerOptions}
          />
          <label className="cp-field">
            <span>Status</span>
            <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
              {STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label className="cp-field">
            <span>From</span>
            <input type="date" value={dateFrom} onChange={(event) => { setDateFrom(event.target.value); setPage(1); }} />
          </label>
          <label className="cp-field">
            <span>To</span>
            <input type="date" value={dateTo} onChange={(event) => { setDateTo(event.target.value); setPage(1); }} />
          </label>
          <button type="submit" className="cp-btn cp-btn-primary"><Search size={15} /> Search</button>
          <button type="button" className="cp-btn cp-btn-secondary" onClick={resetFilters}>Reset</button>
        </form>
      </Panel>

      <Panel title="Leads" description={pagination ? `${pagination.total.toLocaleString('en-IN')} lead(s) in the local mirror.` : undefined}>
        {loading ? <LoadingState label="Loading partner leads…" /> : null}
        {error && !loading ? <ErrorState message={error} onRetry={() => fetchLeads()} /> : null}
        {!loading && !error && !rows.length ? (
          <EmptyState title="No partner leads found" message="Leads appear after WA HRMS syncs them or sends a lead webhook." />
        ) : null}
        {!loading && !error && rows.length ? (
          <>
            <TableShell>
              <table className="cp-table">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Contact</th>
                    <th>Partner</th>
                    <th>WA HRMS status</th>
                    <th>CRM / Sync</th>
                    <th>Protection until</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="cp-row-clickable" onClick={() => openLead(row)}>
                      <td>
                        <strong>{valueOrDash(row.companyName)}</strong>
                        <small>{[row.city, row.state].filter(Boolean).join(', ') || '—'}</small>
                      </td>
                      <td>
                        {valueOrDash(row.contactName)}
                        <small>{[row.email, row.phone].filter(Boolean).join(' · ') || '—'}</small>
                      </td>
                      <td>
                        {valueOrDash(row.partnerName)}
                        {row.partnerId ? <small>{row.partnerId}</small> : null}
                      </td>
                      <td><StatusBadge status={row.status} /></td>
                      <td>
                        <div>{valueOrDash(row.crmStatus)}</div>
                        <small><SyncBadge status={row.syncStatus} /></small>
                      </td>
                      <td>{formatDateTime(row.protectionUntil)}</td>
                      <td>{formatDateTime(row.createdAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableShell>
            <Pagination pagination={pagination} onPage={setPage} />
          </>
        ) : null}
      </Panel>

      <p className="cp-muted"><UserPlus size={12} /> Partner attribution and protection windows are controlled by WA HRMS. Status changes are synchronized both ways.</p>

      <Modal
        open={Boolean(selected)}
        title={selected?.companyName || 'Partner lead'}
        subtitle={selected ? `Lead ${selected.id}` : undefined}
        onClose={() => setSelected(null)}
        wide
      >
        {detailLoading ? <LoadingState label="Loading lead detail…" /> : null}
        {detailError && !detailLoading ? <ErrorState message={detailError} /> : null}
        {selected && !detailLoading ? (
          <>
            <DefinitionList items={[
              { label: 'WA HRMS status', value: <StatusBadge status={selected.status} /> },
              { label: 'CRM lead status', value: valueOrDash(selected.crmStatus) },
              { label: 'Sync status', value: <SyncBadge status={selected.syncStatus} /> },
              { label: 'Last successful sync', value: formatDateTime(selected.lastSyncedAt) },
              { label: 'Pending sync', value: valueOrDash(selected.pendingStatus) },
              { label: 'Last sync error', value: selected.lastSyncError ? <span className="cp-text-danger">{selected.lastSyncError}</span> : '—' },
              { label: 'Partner', value: valueOrDash(selected.partnerName) },
              { label: 'Partner ID', value: valueOrDash(selected.partnerId) },
              { label: 'Contact', value: valueOrDash(selected.contactName) },
              { label: 'Email', value: valueOrDash(selected.email) },
              { label: 'Phone', value: valueOrDash(selected.phone) },
              { label: 'City', value: valueOrDash(selected.city) },
              { label: 'State', value: valueOrDash(selected.state) },
              { label: 'Source', value: valueOrDash(selected.source) },
              { label: 'Organization ID', value: valueOrDash(selected.organizationId) },
              { label: 'Subscription order', value: valueOrDash(selected.subscriptionOrderId) },
              { label: 'Converted at', value: formatDateTime(selected.convertedAt) },
              { label: 'Protection until', value: formatDateTime(selected.protectionUntil) },
              { label: 'Reviewed at', value: formatDateTime(selected.reviewedAt) },
              { label: 'Review note', value: valueOrDash(selected.reviewNote) },
              { label: 'Created', value: formatDateTime(selected.createdAt) },
              { label: 'Updated', value: formatDateTime(selected.updatedAt) },
              { label: 'Synced', value: formatDateTime(selected.syncedAt) },
            ]} />

            {!selected.crmLeadId ? (
              <div className="cp-alert cp-alert-info">
                <div>
                  <strong>Not linked to a CRM lead yet</strong>
                  <p>This partner lead has no All Leads row, so its status cannot be changed from this page.</p>
                </div>
              </div>
            ) : (
              <Panel title="Change CRM status &amp; sync to WA HRMS" description="Only statuses with a documented WA HRMS equivalent are sent. Internal CRM notes are never shared.">
                <form className="cp-filters" onSubmit={submitStatusChange}>
                  <label className="cp-field">
                    <span>CRM status</span>
                    <select
                      value={crmStatus}
                      onChange={(event) => { setCrmStatus(event.target.value); setSyncError(''); setSyncMessage(''); }}
                      disabled={saving}
                    >
                      <option value="">Select a status…</option>
                      {CRM_STATUS_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                  <label className="cp-field cp-grow">
                    <span>Partner-visible review note {requiresNote ? '(required)' : '(optional)'}</span>
                    <textarea
                      rows={3}
                      maxLength={500}
                      value={reviewNote}
                      onChange={(event) => setReviewNote(event.target.value)}
                      disabled={saving}
                      required={requiresNote}
                      aria-required={requiresNote}
                      placeholder="Explain the status to the Channel Partner. This note is shown in WA HRMS."
                    />
                    {noteMissing ? (
                      <small className="cp-text-danger" style={{ fontWeight: 600 }}>
                        {CP_REVIEW_NOTE_REQUIRED_MESSAGE}
                      </small>
                    ) : null}
                  </label>
                  <div className="cp-filter-actions">
                    <button
                      type="submit"
                      className="cp-btn cp-btn-primary"
                      disabled={saving || !crmStatus || noteMissing}
                    >
                      {saving ? 'Updating…' : 'Update CRM & Sync'}
                    </button>
                    {canRetrySync ? (
                      <button type="button" className="cp-btn cp-btn-secondary" onClick={retrySync} disabled={saving}>
                        <RefreshCw size={14} /> Retry Sync
                      </button>
                    ) : null}
                  </div>
                </form>
                {syncError ? (
                  <div className="cp-alert cp-alert-error" style={{ marginTop: '10px' }}>
                    <div><strong>WA HRMS sync failed</strong><p>{syncError}</p></div>
                  </div>
                ) : null}
                {syncMessage ? (
                  <div className="cp-alert cp-alert-success" style={{ marginTop: '10px' }}>
                    <div><strong>Sync status</strong><p>{syncMessage}</p></div>
                  </div>
                ) : null}
                <p className="cp-muted" style={{ marginTop: '8px' }}>
                  NEW and NEW LEAD → submitted · QUALIFIED → qualified · REJECTED → rejected · LOST → lost.
                  WA HRMS keeps rejected leads as rejected; choosing LOST records the same closed
                  outcome in the CRM without sending an invalid upstream change. Converted is sent
                  through the All Leads WON workflow and is validated by WA HRMS.
                </p>
              </Panel>
            )}

            {selected.message ? (
              <div className="cp-alert cp-alert-info">
                <div><strong>Lead message</strong><p>{selected.message}</p></div>
              </div>
            ) : null}
            <JsonBlock value={selected.raw} label="Raw lead payload (sanitised)" />
          </>
        ) : null}
      </Modal>
    </div>
  );
}
