import React, { useCallback, useEffect, useState } from 'react';
import { Activity, RefreshCw, RotateCcw, Search } from 'lucide-react';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
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
  titleCase,
  usePartnerOptions,
  valueOrDash,
} from './ChannelPartnerShared';

const EVENT_TYPES = [
  'application.submitted',
  'application.approved',
  'application.rejected',
  'partner.created',
  'partner.updated',
  'partner.status_changed',
  'partner.user_invited',
  'lead.created',
  'lead.updated',
  'lead.converted',
  'client.assigned',
  'client.unassigned',
  'coupon.assigned',
  'coupon.removed',
  'commission.earned',
  'commission.reversed',
  'commission.adjusted',
  'payout.created',
  'payout.approved',
  'payout.paid',
  'payout.cancelled',
  'ping',
];

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'processed', label: 'Processed' },
  { value: 'ignored', label: 'Ignored' },
  { value: 'failed', label: 'Failed' },
];

export default function ChannelPartnerEventsPage() {
  const { user } = useAuth();
  const isAdmin = (user?.role || '').toUpperCase() === 'ADMIN';
  const partnerOptions = usePartnerOptions();

  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [page, setPage] = useState(1);
  const [eventType, setEventType] = useState('');
  const [status, setStatus] = useState('');
  const [partnerId, setPartnerId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [reprocessing, setReprocessing] = useState(false);
  const [polling, setPolling] = useState(false);

  const fetchEvents = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const response = await API.get('/channel-partners/events', {
        params: buildQuery({
          page,
          limit: 25,
          type: eventType,
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
      setError(err.response?.data?.detail || 'Partner events could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, eventType, status, partnerId, dateFrom, dateTo, search]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const applySearch = (event) => {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  };

  const resetFilters = () => {
    setSearchInput('');
    setSearch('');
    setEventType('');
    setStatus('');
    setPartnerId('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const openEvent = async (row) => {
    setSelected(row);
    setDetailError('');
    setDetailLoading(true);
    try {
      const response = await API.get(`/channel-partners/events/${encodeURIComponent(row.id)}`, {
        skipCache: true,
      });
      setSelected(response.data || row);
    } catch (err) {
      setDetailError(err.response?.data?.detail || 'Event detail could not be loaded.');
    } finally {
      setDetailLoading(false);
    }
  };

  const pollNow = async () => {
    setPolling(true);
    setNotice('');
    try {
      const response = await API.post('/channel-partners/sync/events');
      setNotice(`Event poll queued (run #${response.data?.runId}).`);
      await fetchEvents(true);
    } catch (err) {
      setNotice(err.response?.data?.detail || 'Event poll could not be started.');
    } finally {
      setPolling(false);
    }
  };

  const reprocess = async () => {
    if (!selected) return;
    setReprocessing(true);
    setDetailError('');
    try {
      await API.post(`/channel-partners/events/${encodeURIComponent(selected.id)}/reprocess`);
      setNotice(`Event ${selected.id} queued for reprocessing.`);
      setSelected(null);
      await fetchEvents(true);
    } catch (err) {
      setDetailError(err.response?.data?.detail || 'Event could not be queued for reprocessing.');
    } finally {
      setReprocessing(false);
    }
  };

  return (
    <div className="cp-page">
      <PageHeader
        title="Partner Activity / Events"
        description="Webhook deliveries and polled events from WA HRMS. Webhooks are primary; the scheduled poll recovers anything missed."
        actions={(
          <>
            <RefreshButton onClick={() => fetchEvents(true)} refreshing={refreshing} />
            {isAdmin ? (
              <button type="button" className="cp-btn cp-btn-primary" onClick={pollNow} disabled={polling}>
                <RefreshCw size={15} className={polling ? 'cp-spin' : undefined} />
                {polling ? 'Queueing…' : 'Poll events now'}
              </button>
            ) : null}
          </>
        )}
      />

      {notice ? (
        <div className="cp-alert cp-alert-info">
          <Activity size={17} />
          <div><strong>Event processing</strong><p>{notice}</p></div>
        </div>
      ) : null}

      <Panel title="Filters" description="Narrow by event type, processing status, partner or event date.">
        <form className="cp-filters" onSubmit={applySearch}>
          <label className="cp-field cp-grow">
            <span>Search</span>
            <input
              type="search"
              value={searchInput}
              placeholder="Event ID, partner ID, lead ID, client ID…"
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </label>
          <label className="cp-field">
            <span>Event type</span>
            <select value={eventType} onChange={(event) => { setEventType(event.target.value); setPage(1); }}>
              <option value="">All event types</option>
              {EVENT_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </label>
          <label className="cp-field">
            <span>Status</span>
            <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
              {STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <PartnerFilter
            value={partnerId}
            onChange={(value) => { setPartnerId(value); setPage(1); }}
            options={partnerOptions}
          />
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

      <Panel title="Event log" description={pagination ? `${pagination.total.toLocaleString('en-IN')} event(s) stored locally.` : undefined}>
        {loading ? <LoadingState label="Loading partner events…" /> : null}
        {error && !loading ? <ErrorState message={error} onRetry={() => fetchEvents()} /> : null}
        {!loading && !error && !rows.length ? (
          <EmptyState title="No partner events found" message="Events appear when WA HRMS posts a webhook or the scheduled poll fetches them." />
        ) : null}
        {!loading && !error && rows.length ? (
          <>
            <TableShell>
              <table className="cp-table">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Type</th>
                    <th>Related</th>
                    <th>Status</th>
                    <th>Source</th>
                    <th>Event time</th>
                    <th>Received</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="cp-row-clickable" onClick={() => openEvent(row)}>
                      <td>
                        <strong className="cp-code">{row.id}</strong>
                        {row.sequence !== null && row.sequence !== undefined ? <small>Seq #{row.sequence}</small> : null}
                      </td>
                      <td>{row.type}</td>
                      <td>
                        {row.partnerId || row.leadId || row.clientId || '—'}
                        {row.leadId ? <small>Lead {row.leadId}</small> : null}
                        {row.clientId ? <small>Client {row.clientId}</small> : null}
                      </td>
                      <td><StatusBadge status={row.status} /></td>
                      <td><span className="cp-raw-tag">{titleCase(row.source)}</span></td>
                      <td>{formatDateTime(row.eventCreatedAt)}</td>
                      <td>{formatDateTime(row.receivedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableShell>
            <Pagination pagination={pagination} onPage={setPage} />
          </>
        ) : null}
      </Panel>

      <p className="cp-muted"><Activity size={12} /> Failed events can be replayed by an Admin. Event payloads are untrusted input and are sanitised before storage.</p>

      <Modal
        open={Boolean(selected)}
        title={selected?.type || 'Partner event'}
        subtitle={selected ? selected.id : undefined}
        onClose={() => setSelected(null)}
        wide
        footer={isAdmin && selected ? (
          <button
            type="button"
            className="cp-btn cp-btn-secondary"
            onClick={reprocess}
            disabled={reprocessing || selected.status === 'processed'}
          >
            <RotateCcw size={15} className={reprocessing ? 'cp-spin' : undefined} />
            {reprocessing ? 'Queueing…' : 'Reprocess event'}
          </button>
        ) : null}
      >
        {detailLoading ? <LoadingState label="Loading event detail…" /> : null}
        {detailError && !detailLoading ? <ErrorState message={detailError} /> : null}
        {selected && !detailLoading ? (
          <>
            <DefinitionList items={[
              { label: 'Status', value: <StatusBadge status={selected.status} /> },
              { label: 'Event type', value: valueOrDash(selected.type) },
              { label: 'Source', value: titleCase(selected.source) },
              { label: 'Sequence', value: selected.sequence ?? '—' },
              { label: 'Delivery ID', value: valueOrDash(selected.deliveryId) },
              { label: 'Partner ID', value: valueOrDash(selected.partnerId) },
              { label: 'Lead ID', value: valueOrDash(selected.leadId) },
              { label: 'Client ID', value: valueOrDash(selected.clientId) },
              { label: 'Event time', value: formatDateTime(selected.eventCreatedAt) },
              { label: 'Received', value: formatDateTime(selected.receivedAt) },
              { label: 'Processed', value: formatDateTime(selected.processedAt) },
            ]} />
            {selected.error ? (
              <div className="cp-alert cp-alert-error">
                <div><strong>Processing error</strong><p className="cp-error-text">{selected.error}</p></div>
              </div>
            ) : null}
            <JsonBlock value={selected.data} label="Event data (sanitised)" />
            <JsonBlock value={selected.headers} label="Accepted headers" />
          </>
        ) : null}
      </Modal>
    </div>
  );
}
