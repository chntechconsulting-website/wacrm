import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { BadgePercent } from 'lucide-react';
import API from '../../services/api';
import {
  DefinitionList,
  EmptyState,
  ErrorState,
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
  formatMoney,
  titleCase,
  usePartnerOptions,
  valueOrDash,
} from './ChannelPartnerShared';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'on_hold', label: 'On hold' },
  { value: 'available', label: 'Available' },
  { value: 'in_payout', label: 'In payout' },
  { value: 'paid', label: 'Paid' },
  { value: 'cancelled', label: 'Cancelled' },
];

export default function ChannelPartnerCommissionsPage() {
  const [searchParams] = useSearchParams();
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
  const [partnerId, setPartnerId] = useState(() => searchParams.get('partnerId') || '');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [selected, setSelected] = useState(null);

  const fetchCommissions = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const response = await API.get('/channel-partners/commissions', {
        params: buildQuery({ page, limit: 25, status, partnerId, from: dateFrom, to: dateTo }),
        skipCache: isRefresh,
      });
      setRows(Array.isArray(response.data?.items) ? response.data.items : []);
      setPagination(response.data?.pagination || null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Commission entries could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, status, partnerId, dateFrom, dateTo]);

  useEffect(() => {
    fetchCommissions();
  }, [fetchCommissions]);

  const resetFilters = () => {
    setStatus('');
    setPartnerId('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  return (
    <div className="cp-page">
      <PageHeader
        title="Commissions"
        description="Commission ledger mirrored from WA HRMS. Amounts are stored in paise and displayed in INR. All adjustments happen upstream."
        actions={<RefreshButton onClick={() => fetchCommissions(true)} refreshing={refreshing} />}
      />

      <Panel title="Filters" description="Filter by partner, commission status or the date the commission was earned.">
        <form className="cp-filters" onSubmit={(event) => event.preventDefault()}>
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
          <button type="button" className="cp-btn cp-btn-secondary" onClick={resetFilters}>Reset</button>
        </form>
      </Panel>

      <Panel title="Commission ledger" description={pagination ? `${pagination.total.toLocaleString('en-IN')} commission entries.` : undefined}>
        {loading ? <LoadingState label="Loading commissions…" /> : null}
        {error && !loading ? <ErrorState message={error} onRetry={() => fetchCommissions()} /> : null}
        {!loading && !error && !rows.length ? (
          <EmptyState title="No commission entries found" message="Commission entries appear when a partner-attributed invoice is paid in WA HRMS." />
        ) : null}
        {!loading && !error && rows.length ? (
          <>
            <TableShell>
              <table className="cp-table">
                <thead>
                  <tr>
                    <th>Entry</th>
                    <th>Partner</th>
                    <th>Client / Invoice</th>
                    <th className="cp-right">Amount</th>
                    <th>Rate</th>
                    <th>Status</th>
                    <th>Hold until</th>
                    <th>Earned</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="cp-row-clickable" onClick={() => setSelected(row)}>
                      <td>
                        <strong>{valueOrDash(row.description)}</strong>
                        <small>{row.type ? titleCase(row.type) : row.id}</small>
                      </td>
                      <td>
                        {valueOrDash(partnerNames[row.partnerId])}
                        {row.partnerId ? <small>{row.partnerId}</small> : null}
                      </td>
                      <td>
                        {valueOrDash(row.clientName)}
                        {row.invoiceNumber ? <small>{row.invoiceNumber}</small> : null}
                      </td>
                      <td className="cp-right"><strong>{formatMoney(row.amountPaise)}</strong></td>
                      <td>{formatBps(row.rateBps)}</td>
                      <td><StatusBadge status={row.status} /></td>
                      <td>{formatDateTime(row.holdUntil)}</td>
                      <td>{formatDateTime(row.earnedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableShell>
            <Pagination pagination={pagination} onPage={setPage} />
          </>
        ) : null}
      </Panel>

      <p className="cp-muted"><BadgePercent size={12} /> Commission status changes, reversals and adjustments are performed in WA HRMS, not here.</p>

      <Modal
        open={Boolean(selected)}
        title={selected?.description || 'Commission entry'}
        subtitle={selected ? `Entry ${selected.id}` : undefined}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <>
            <DefinitionList items={[
              { label: 'Status', value: <StatusBadge status={selected.status} /> },
              { label: 'Amount', value: formatMoney(selected.amountPaise) },
              { label: 'Base amount', value: formatMoney(selected.basePaise) },
              { label: 'Rate', value: formatBps(selected.rateBps) },
              { label: 'Type', value: selected.type ? titleCase(selected.type) : '—' },
              { label: 'Reason', value: valueOrDash(selected.reason) },
              { label: 'Client', value: valueOrDash(selected.clientName) },
              { label: 'Invoice', value: valueOrDash(selected.invoiceNumber) },
              { label: 'Partner', value: valueOrDash(partnerNames[selected.partnerId]) },
              { label: 'Partner ID', value: valueOrDash(selected.partnerId) },
              { label: 'Hold until', value: formatDateTime(selected.holdUntil) },
              { label: 'Earned', value: formatDateTime(selected.earnedAt) },
              { label: 'Updated', value: formatDateTime(selected.updatedAt) },
              { label: 'Synced', value: formatDateTime(selected.syncedAt) },
            ]} />
          </>
        ) : null}
      </Modal>
    </div>
  );
}
