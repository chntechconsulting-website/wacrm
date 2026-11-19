import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, Ticket } from 'lucide-react';
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
  formatBps,
  formatDateTime,
  usePartnerOptions,
  valueOrDash,
} from './ChannelPartnerShared';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'expired', label: 'Expired' },
  { value: 'removed', label: 'Removed' },
];

export default function ChannelPartnerCouponsPage() {
  const partnerOptions = usePartnerOptions();
  const partnerNames = useMemo(() => {
    const map = {};
    partnerOptions.forEach((option) => { map[option.value] = option.label; });
    return map;
  }, [partnerOptions]);

  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [partnerId, setPartnerId] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);

  const fetchCoupons = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const response = await API.get('/channel-partners/coupons', {
        params: buildQuery({ page, limit: 25, status, partnerId, search }),
        skipCache: isRefresh,
      });
      setRows(Array.isArray(response.data?.items) ? response.data.items : []);
      setPagination(response.data?.pagination || null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Partner coupons could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, status, partnerId, search]);

  useEffect(() => {
    fetchCoupons();
  }, [fetchCoupons]);

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
    setPage(1);
  };

  return (
    <div className="cp-page">
      <PageHeader
        title="Partner Coupons"
        description="Coupons assigned to channel partners. Coupon creation, discount rules and removal are managed in WA HRMS."
        actions={<RefreshButton onClick={() => fetchCoupons(true)} refreshing={refreshing} />}
      />

      <Panel title="Filters" description="Filter by partner or status, or search by coupon code and description.">
        <form className="cp-filters" onSubmit={applySearch}>
          <label className="cp-field cp-grow">
            <span>Search</span>
            <input
              type="search"
              value={searchInput}
              placeholder="Coupon code or description…"
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
          <button type="submit" className="cp-btn cp-btn-primary"><Search size={15} /> Search</button>
          <button type="button" className="cp-btn cp-btn-secondary" onClick={resetFilters}>Reset</button>
        </form>
      </Panel>

      <Panel title="Coupons" description={pagination ? `${pagination.total.toLocaleString('en-IN')} coupon assignment(s).` : undefined}>
        {loading ? <LoadingState label="Loading partner coupons…" /> : null}
        {error && !loading ? <ErrorState message={error} onRetry={() => fetchCoupons()} /> : null}
        {!loading && !error && !rows.length ? (
          <EmptyState title="No partner coupons found" message="Coupons appear here after WA HRMS assigns them to a partner." />
        ) : null}
        {!loading && !error && rows.length ? (
          <>
            <TableShell>
              <table className="cp-table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Partner</th>
                    <th>Discount</th>
                    <th>Status</th>
                    <th>Assigned</th>
                    <th>Expires</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="cp-row-clickable" onClick={() => setSelected(row)}>
                      <td>
                        <strong>{valueOrDash(row.code)}</strong>
                        <small>{valueOrDash(row.description)}</small>
                      </td>
                      <td>
                        {valueOrDash(partnerNames[row.partnerId])}
                        {row.partnerId ? <small>{row.partnerId}</small> : null}
                      </td>
                      <td>{formatBps(row.discountBps)}</td>
                      <td><StatusBadge status={row.status} /></td>
                      <td>{formatDateTime(row.assignedAt)}</td>
                      <td>{formatDateTime(row.expiresAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableShell>
            <Pagination pagination={pagination} onPage={setPage} />
          </>
        ) : null}
      </Panel>

      <p className="cp-muted"><Ticket size={12} /> Coupons cannot be created, edited or revoked from this CRM.</p>

      <Modal
        open={Boolean(selected)}
        title={selected?.code || 'Coupon'}
        subtitle={selected ? `Coupon ${selected.couponId || selected.id}` : undefined}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <>
            <DefinitionList items={[
              { label: 'Status', value: <StatusBadge status={selected.status} /> },
              { label: 'Code', value: valueOrDash(selected.code) },
              { label: 'Description', value: valueOrDash(selected.description) },
              { label: 'Discount', value: formatBps(selected.discountBps) },
              { label: 'Partner', value: valueOrDash(partnerNames[selected.partnerId]) },
              { label: 'Partner ID', value: valueOrDash(selected.partnerId) },
              { label: 'Assigned', value: formatDateTime(selected.assignedAt) },
              { label: 'Expires', value: formatDateTime(selected.expiresAt) },
              { label: 'Updated', value: formatDateTime(selected.updatedAt) },
            ]} />
            <JsonBlock value={selected.details} label="Coupon details" />
            <JsonBlock value={selected.raw} label="Raw coupon payload (sanitised)" />
          </>
        ) : null}
      </Modal>
    </div>
  );
}
