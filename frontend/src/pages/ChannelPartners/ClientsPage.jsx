import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Building2, Search } from 'lucide-react';
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
  { value: 'active', label: 'Active' },
  { value: 'ended', label: 'Ended' },
];

export default function ChannelPartnerClientsPage() {
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

  const fetchClients = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const response = await API.get('/channel-partners/clients', {
        params: buildQuery({ page, limit: 25, status, partnerId, search }),
        skipCache: isRefresh,
      });
      setRows(Array.isArray(response.data?.items) ? response.data.items : []);
      setPagination(response.data?.pagination || null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Partner clients could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, status, partnerId, search]);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

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
        title="Partner Clients"
        description="Client accounts attributed to a channel partner. Attribution changes and customer ownership are managed in WA HRMS."
        actions={<RefreshButton onClick={() => fetchClients(true)} refreshing={refreshing} />}
      />

      <Panel title="Filters" description="Filter by partner, attribution status or search by organisation, order or subscription ID.">
        <form className="cp-filters" onSubmit={applySearch}>
          <label className="cp-field cp-grow">
            <span>Search</span>
            <input
              type="search"
              value={searchInput}
              placeholder="Organisation, order number, organization ID…"
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

      <Panel title="Client attributions" description={pagination ? `${pagination.total.toLocaleString('en-IN')} attributed client record(s).` : undefined}>
        {loading ? <LoadingState label="Loading partner clients…" /> : null}
        {error && !loading ? <ErrorState message={error} onRetry={() => fetchClients()} /> : null}
        {!loading && !error && !rows.length ? (
          <EmptyState title="No attributed clients found" message="Client attributions appear when a partner lead converts or WA HRMS assigns a client." />
        ) : null}
        {!loading && !error && rows.length ? (
          <>
            <TableShell>
              <table className="cp-table">
                <thead>
                  <tr>
                    <th>Organisation</th>
                    <th>Partner</th>
                    <th>Order</th>
                    <th>Status</th>
                    <th>Effective from</th>
                    <th>Ended</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="cp-row-clickable" onClick={() => setSelected(row)}>
                      <td>
                        <strong>{valueOrDash(row.organizationName)}</strong>
                        <small>{valueOrDash(row.organizationId)}</small>
                      </td>
                      <td>
                        {valueOrDash(partnerNames[row.partnerId])}
                        {row.partnerId ? <small>{row.partnerId}</small> : null}
                      </td>
                      <td>
                        {valueOrDash(row.orderNumber)}
                        {row.subscriptionOrderId ? <small>{row.subscriptionOrderId}</small> : null}
                      </td>
                      <td><StatusBadge status={row.status} /></td>
                      <td>{formatDateTime(row.effectiveFrom)}</td>
                      <td>{formatDateTime(row.endedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableShell>
            <Pagination pagination={pagination} onPage={setPage} />
          </>
        ) : null}
      </Panel>

      <p className="cp-muted"><Building2 size={12} /> Ending an attribution stops future commission in WA HRMS. This CRM can only display the outcome.</p>

      <Modal
        open={Boolean(selected)}
        title={selected?.organizationName || 'Client attribution'}
        subtitle={selected ? `Attribution ${selected.attributionId || selected.id}` : undefined}
        onClose={() => setSelected(null)}
        wide
      >
        {selected ? (
          <>
            <DefinitionList items={[
              { label: 'Status', value: <StatusBadge status={selected.status} /> },
              { label: 'Organisation', value: valueOrDash(selected.organizationName) },
              { label: 'Organization ID', value: valueOrDash(selected.organizationId) },
              { label: 'Partner', value: valueOrDash(partnerNames[selected.partnerId]) },
              { label: 'Partner ID', value: valueOrDash(selected.partnerId) },
              { label: 'Order number', value: valueOrDash(selected.orderNumber) },
              { label: 'Subscription order ID', value: valueOrDash(selected.subscriptionOrderId) },
              { label: 'Attribution ID', value: valueOrDash(selected.attributionId) },
              { label: 'Effective from', value: formatDateTime(selected.effectiveFrom) },
              { label: 'Ended at', value: formatDateTime(selected.endedAt) },
              { label: 'End reason', value: valueOrDash(selected.endReason) },
              { label: 'Created', value: formatDateTime(selected.createdAt) },
              { label: 'Updated', value: formatDateTime(selected.updatedAt) },
            ]} />
            <JsonBlock value={selected.attribution} label="Attribution details" />
            <JsonBlock value={selected.raw} label="Raw attribution payload (sanitised)" />
          </>
        ) : null}
      </Modal>
    </div>
  );
}
