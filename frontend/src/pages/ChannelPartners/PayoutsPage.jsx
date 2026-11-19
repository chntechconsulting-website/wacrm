import React, { useCallback, useEffect, useState } from 'react';
import { Search, Wallet } from 'lucide-react';
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
  formatDate,
  formatDateTime,
  formatMoney,
  usePartnerOptions,
  valueOrDash,
} from './ChannelPartnerShared';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
  { value: 'paid', label: 'Paid' },
  { value: 'cancelled', label: 'Cancelled' },
];

export default function ChannelPartnerPayoutsPage() {
  const partnerOptions = usePartnerOptions();
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
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');

  const fetchPayouts = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const response = await API.get('/channel-partners/payouts', {
        params: buildQuery({ page, limit: 25, status, partnerId, search }),
        skipCache: isRefresh,
      });
      setRows(Array.isArray(response.data?.items) ? response.data.items : []);
      setPagination(response.data?.pagination || null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Payouts could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, status, partnerId, search]);

  useEffect(() => {
    fetchPayouts();
  }, [fetchPayouts]);

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

  const openPayout = async (row) => {
    setSelected(row);
    setDetailError('');
    setDetailLoading(true);
    try {
      const response = await API.get(`/channel-partners/payouts/${encodeURIComponent(row.id)}`, {
        skipCache: true,
      });
      setSelected(response.data || row);
    } catch (err) {
      setDetailError(err.response?.data?.detail || 'Payout detail could not be loaded.');
    } finally {
      setDetailLoading(false);
    }
  };

  const commissionEntries = Array.isArray(selected?.commissionEntries)
    ? selected.commissionEntries
    : [];

  return (
    <div className="cp-page">
      <PageHeader
        title="Payouts"
        description="Partner payout records mirrored from WA HRMS. This CRM never creates, approves or pays a payout; the mirror exists for finance visibility only."
        actions={<RefreshButton onClick={() => fetchPayouts(true)} refreshing={refreshing} />}
      />

      <Panel title="Filters" description="Filter by partner or payout status, or search by partner, payment reference, invoice number or payout ID.">
        <form className="cp-filters" onSubmit={applySearch}>
          <label className="cp-field cp-grow">
            <span>Search</span>
            <input
              type="search"
              value={searchInput}
              placeholder="Partner, reference, invoice or payout ID…"
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

      <Panel title="Payout records" description={pagination ? `${pagination.total.toLocaleString('en-IN')} payout(s).` : undefined}>
        {loading ? <LoadingState label="Loading payouts…" /> : null}
        {error && !loading ? <ErrorState message={error} onRetry={() => fetchPayouts()} /> : null}
        {!loading && !error && !rows.length ? (
          <EmptyState title="No payouts found" message="Payouts appear after WA HRMS generates them for a partner." />
        ) : null}
        {!loading && !error && rows.length ? (
          <>
            <TableShell>
              <table className="cp-table">
                <thead>
                  <tr>
                    <th>Payout</th>
                    <th>Partner</th>
                    <th className="cp-right">Net</th>
                    <th className="cp-right">TDS</th>
                    <th>Status</th>
                    <th>Payment date</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="cp-row-clickable" onClick={() => openPayout(row)}>
                      <td>
                        <strong className="cp-code">{row.id}</strong>
                        <small>{valueOrDash(row.partnerInvoiceNumber)}</small>
                      </td>
                      <td>{valueOrDash(row.partnerName)}</td>
                      <td className="cp-right"><strong>{formatMoney(row.netPaise)}</strong></td>
                      <td className="cp-right">{formatMoney(row.tdsPaise)}</td>
                      <td><StatusBadge status={row.status} /></td>
                      <td>{formatDate(row.paymentDate)}</td>
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

      <p className="cp-muted"><Wallet size={12} /> Payout bank details are never stored or shown. Payment execution stays inside WA HRMS.</p>

      <Modal
        open={Boolean(selected)}
        title={selected?.partnerName ? `Payout · ${selected.partnerName}` : 'Payout'}
        subtitle={selected ? selected.id : undefined}
        onClose={() => setSelected(null)}
        wide
      >
        {detailLoading ? <LoadingState label="Loading payout detail…" /> : null}
        {detailError && !detailLoading ? <ErrorState message={detailError} /> : null}
        {selected && !detailLoading ? (
          <>
            <DefinitionList items={[
              { label: 'Status', value: <StatusBadge status={selected.status} /> },
              { label: 'Partner', value: valueOrDash(selected.partnerName) },
              { label: 'Partner ID', value: valueOrDash(selected.partnerId) },
              { label: 'Gross', value: formatMoney(selected.grossPaise) },
              { label: 'Net payable', value: formatMoney(selected.netPaise) },
              { label: 'TDS', value: formatMoney(selected.tdsPaise) },
              { label: 'GST', value: formatMoney(selected.gstPaise) },
              { label: 'Adjustment', value: formatMoney(selected.adjustmentPaise) },
              { label: 'Payment method', value: valueOrDash(selected.paymentMethod) },
              { label: 'Payment reference', value: valueOrDash(selected.paymentReference) },
              { label: 'Payment date', value: formatDate(selected.paymentDate) },
              { label: 'Partner invoice', value: valueOrDash(selected.partnerInvoiceNumber) },
              { label: 'Created', value: formatDateTime(selected.createdAt) },
              { label: 'Updated', value: formatDateTime(selected.updatedAt) },
              { label: 'Synced', value: formatDateTime(selected.syncedAt) },
            ]} />

            {selected.notes ? (
              <div className="cp-alert cp-alert-info">
                <div><strong>Notes</strong><p>{selected.notes}</p></div>
              </div>
            ) : null}
            {selected.cancellationReason ? (
              <div className="cp-alert cp-alert-error">
                <div><strong>Cancellation reason</strong><p>{selected.cancellationReason}</p></div>
              </div>
            ) : null}

            {commissionEntries.length ? (
              <div>
                <h3 style={{ margin: '0 0 8px', fontSize: '0.85rem' }}>Commission entries in this payout</h3>
                <TableShell>
                  <table className="cp-table">
                    <thead>
                      <tr><th>Description</th><th>Client</th><th className="cp-right">Amount</th><th>Status</th><th>Earned</th></tr>
                    </thead>
                    <tbody>
                      {commissionEntries.map((entry, index) => (
                        <tr key={entry.id || entry.entryId || `${index}`}>
                          <td>{valueOrDash(entry.description)}</td>
                          <td>{valueOrDash(entry.clientName)}</td>
                          <td className="cp-right">{formatMoney(entry.amountPaise)}</td>
                          <td>{entry.status ? <StatusBadge status={entry.status} /> : '—'}</td>
                          <td>{formatDateTime(entry.earnedAt)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableShell>
              </div>
            ) : null}

            <JsonBlock value={selected.raw} label="Raw payout payload (sanitised)" />
          </>
        ) : null}
      </Modal>
    </div>
  );
}
