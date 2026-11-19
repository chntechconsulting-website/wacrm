import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Handshake, Search } from 'lucide-react';
import API from '../../services/api';
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Pagination,
  Panel,
  RefreshButton,
  StatusBadge,
  TableShell,
  buildQuery,
  formatBps,
  formatDateTime,
  valueOrDash,
} from './ChannelPartnerShared';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'terminated', label: 'Terminated' },
];

export default function ChannelPartnersPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');

  const fetchPartners = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const response = await API.get('/channel-partners/partners', {
        params: buildQuery({ page, limit: 25, status, search }),
        skipCache: isRefresh,
      });
      setRows(Array.isArray(response.data?.items) ? response.data.items : []);
      setPagination(response.data?.pagination || null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Partners could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, status, search]);

  useEffect(() => {
    fetchPartners();
  }, [fetchPartners]);

  const applySearch = (event) => {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  };

  return (
    <div className="cp-page">
      <PageHeader
        title="Channel Partners"
        description="Every partner mirrored from WA HRMS. Use the detail view for balances, logins, clients, coupons and commissions."
        actions={<RefreshButton onClick={() => fetchPartners(true)} refreshing={refreshing} />}
      />

      <Panel title="Filters" description="Search by partner name, code, legal name, email, city or GSTIN.">
        <form className="cp-filters" onSubmit={applySearch}>
          <label className="cp-field cp-grow">
            <span>Search</span>
            <input
              type="search"
              value={searchInput}
              placeholder="Partner name, code, email, city…"
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </label>
          <label className="cp-field">
            <span>Status</span>
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(1);
              }}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <button type="submit" className="cp-btn cp-btn-primary">
            <Search size={15} /> Search
          </button>
        </form>
      </Panel>

      <Panel title="Partners" description={pagination ? `${pagination.total.toLocaleString('en-IN')} partner(s) in the local mirror.` : undefined}>
        {loading ? <LoadingState label="Loading partners…" /> : null}
        {error && !loading ? <ErrorState message={error} onRetry={() => fetchPartners()} /> : null}
        {!loading && !error && !rows.length ? (
          <EmptyState
            title="No partners found"
            message="Partners appear after a successful sync with WA HRMS. Check Integration Settings if the mirror is empty."
          />
        ) : null}
        {!loading && !error && rows.length ? (
          <>
            <TableShell>
              <table className="cp-table">
                <thead>
                  <tr>
                    <th>Partner</th>
                    <th>Code</th>
                    <th>Location</th>
                    <th>Commission</th>
                    <th>Status</th>
                    <th>Last synced</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.id}
                      className="cp-row-clickable"
                      onClick={() => navigate(`/channel-partners/partners/${encodeURIComponent(row.id)}`)}
                    >
                      <td>
                        <strong>{valueOrDash(row.name)}</strong>
                        <small>{[row.email, row.phone].filter(Boolean).join(' · ') || 'No contact details'}</small>
                      </td>
                      <td>{valueOrDash(row.code)}</td>
                      <td>{[row.city, row.state].filter(Boolean).join(', ') || '—'}</td>
                      <td>{formatBps(row.commissionRateBps)}</td>
                      <td><StatusBadge status={row.status} /></td>
                      <td>{formatDateTime(row.syncedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableShell>
            <Pagination pagination={pagination} onPage={setPage} />
          </>
        ) : null}
      </Panel>

      <p className="cp-muted"><Handshake size={12} /> Partner records are read-only. Registration, status changes and terms are managed in WA HRMS.</p>
    </div>
  );
}
