import React, { useCallback, useEffect, useState } from 'react';
import { FileText, Search, ShieldCheck } from 'lucide-react';
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
  RefreshButton,
  StatusBadge,
  TableShell,
  buildQuery,
  formatDate,
  formatDateTime,
  titleCase,
  valueOrDash,
} from './ChannelPartnerShared';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];

export default function ChannelPartnerApplicationsPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [documentState, setDocumentState] = useState({});

  const permission = user?.permissions?.channel_partners;
  const canViewDocuments = (user?.role || '').toUpperCase() === 'ADMIN'
    || permission?.can_edit === true
    || permission?.can_approve === true;

  const fetchApplications = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const response = await API.get('/channel-partners/applications', {
        params: buildQuery({ page, limit: 25, status, search }),
        skipCache: isRefresh,
      });
      setRows(Array.isArray(response.data?.items) ? response.data.items : []);
      setPagination(response.data?.pagination || null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Applications could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, status, search]);

  useEffect(() => {
    fetchApplications();
  }, [fetchApplications]);

  const openApplication = async (row) => {
    setSelected(row);
    setDocumentState({});
    setDetailError('');
    setDetailLoading(true);
    try {
      const response = await API.get(`/channel-partners/applications/${encodeURIComponent(row.id)}`, {
        skipCache: true,
      });
      setSelected(response.data || row);
    } catch (err) {
      setDetailError(err.response?.data?.detail || 'Application detail could not be loaded.');
    } finally {
      setDetailLoading(false);
    }
  };

  const applySearch = (event) => {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  };

  const fetchDocument = async (documentType) => {
    if (!selected) return;
    setDocumentState((prev) => ({ ...prev, [documentType]: { loading: true } }));
    try {
      const response = await API.get(
        `/channel-partners/applications/${encodeURIComponent(selected.id)}/documents/${documentType}`,
        { skipCache: true },
      );
      setDocumentState((prev) => ({
        ...prev,
        [documentType]: { loading: false, data: response.data || {} },
      }));
    } catch (err) {
      setDocumentState((prev) => ({
        ...prev,
        [documentType]: {
          loading: false,
          error: err.response?.data?.detail?.message
            || err.response?.data?.detail
            || 'Document link could not be retrieved.',
        },
      }));
    }
  };

  const documents = selected?.documents || {};
  const documentKeys = Object.keys(documents);

  return (
    <div className="cp-page">
      <PageHeader
        title="Partner Applications"
        description="Applications submitted to the WA HRMS channel partner programme. Decisions are made in WA HRMS; this screen is read-only."
        actions={<RefreshButton onClick={() => fetchApplications(true)} refreshing={refreshing} />}
      />

      <Panel title="Filters" description="Search by business name, contact, email, phone or application ID.">
        <form className="cp-filters" onSubmit={applySearch}>
          <label className="cp-field cp-grow">
            <span>Search</span>
            <input
              type="search"
              value={searchInput}
              placeholder="Business or contact…"
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </label>
          <label className="cp-field">
            <span>Status</span>
            <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
              {STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <button type="submit" className="cp-btn cp-btn-primary"><Search size={15} /> Search</button>
        </form>
      </Panel>

      <Panel title="Applications" description={pagination ? `${pagination.total.toLocaleString('en-IN')} application(s).` : undefined}>
        {loading ? <LoadingState label="Loading applications…" /> : null}
        {error && !loading ? <ErrorState message={error} onRetry={() => fetchApplications()} /> : null}
        {!loading && !error && !rows.length ? <EmptyState title="No applications found" message="Applications appear after WA HRMS syncs them." /> : null}
        {!loading && !error && rows.length ? (
          <>
            <TableShell>
              <table className="cp-table">
                <thead>
                  <tr><th>Business</th><th>Contact</th><th>Location</th><th>PAN</th><th>Status</th><th>Submitted</th></tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="cp-row-clickable" onClick={() => openApplication(row)}>
                      <td><strong>{valueOrDash(row.businessName)}</strong><small>{valueOrDash(row.businessType)} · {titleCase(row.entityType)}</small></td>
                      <td>{valueOrDash(row.contactName)}<small>{[row.email, row.phone].filter(Boolean).join(' · ')}</small></td>
                      <td>{[row.city, row.state].filter(Boolean).join(', ') || '—'}</td>
                      <td>{valueOrDash(row.panMasked)}</td>
                      <td><StatusBadge status={row.status} /></td>
                      <td>{formatDate(row.createdAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableShell>
            <Pagination pagination={pagination} onPage={setPage} />
          </>
        ) : null}
      </Panel>

      <Modal
        open={Boolean(selected)}
        title={selected?.businessName || 'Application'}
        subtitle={selected ? `${titleCase(selected.entityType)} · ${selected.id}` : undefined}
        onClose={() => setSelected(null)}
        wide
      >
        {detailLoading ? <LoadingState label="Loading application detail…" /> : null}
        {detailError && !detailLoading ? <ErrorState message={detailError} /> : null}
        {selected && !detailLoading ? (
          <>
            <DefinitionList items={[
              { label: 'Status', value: <StatusBadge status={selected.status} /> },
              { label: 'Business type', value: valueOrDash(selected.businessType) },
              { label: 'Team size', value: valueOrDash(selected.teamSize) },
              { label: 'Years in business', value: valueOrDash(selected.yearsInBusiness) },
              { label: 'Website', value: valueOrDash(selected.website) },
              { label: 'Contact', value: valueOrDash(selected.contactName) },
              { label: 'Designation', value: valueOrDash(selected.designation) },
              { label: 'Email', value: valueOrDash(selected.email) },
              { label: 'Phone', value: valueOrDash(selected.phone) },
              { label: 'PAN', value: valueOrDash(selected.panMasked) },
              { label: 'GSTIN', value: valueOrDash(selected.gstin) },
              { label: 'Address', value: [selected.address?.line1, selected.address?.line2, selected.address?.city, selected.address?.state, selected.address?.pincode].filter(Boolean).join(', ') || '—' },
              { label: 'Regions', value: valueOrDash(selected.regions) },
              { label: 'Current clients', value: valueOrDash(selected.currentClients) },
              { label: 'Expected clients', value: valueOrDash(selected.expectedClients) },
              { label: 'Heard from', value: valueOrDash(selected.heardFrom) },
              { label: 'Consent', value: selected.consent === null || selected.consent === undefined ? '—' : (selected.consent ? 'Yes' : 'No') },
              { label: 'Review note', value: valueOrDash(selected.reviewNote) },
              { label: 'Reviewed at', value: formatDateTime(selected.reviewedAt) },
              { label: 'Partner', value: valueOrDash(selected.partnerExternalId) },
              { label: 'Submitted', value: formatDateTime(selected.createdAt) },
            ]} />

            {Array.isArray(selected.industries) && selected.industries.length ? (
              <div>
                <h3 className="cp-panel-head h2" style={{ fontSize: '0.82rem' }}>Industries</h3>
                <div className="cp-inline">
                  {selected.industries.map((industry) => <span key={industry} className="cp-raw-tag">{industry}</span>)}
                </div>
              </div>
            ) : null}

            {selected.message ? (
              <div className="cp-alert cp-alert-info">
                <FileText size={17} />
                <div><strong>Applicant message</strong><p>{selected.message}</p></div>
              </div>
            ) : null}

            <div>
              <h3 style={{ margin: '0 0 8px', fontSize: '0.85rem' }}>Identity documents</h3>
              {!canViewDocuments ? (
                <div className="cp-alert">
                  <ShieldCheck size={17} />
                  <div>
                    <strong>Restricted</strong>
                    <p>Viewing PAN/Aadhaar documents requires Channel Partner edit or approval permission.</p>
                  </div>
                </div>
              ) : null}
              {canViewDocuments ? (
                <div className="cp-stack">
                  <div className="cp-inline">
                    {['pan', 'aadhaar'].map((type) => (
                      <button
                        key={type}
                        type="button"
                        className="cp-btn cp-btn-secondary"
                        onClick={() => fetchDocument(type)}
                        disabled={documentState[type]?.loading || !documents[type]}
                      >
                        {documentState[type]?.loading ? 'Fetching…' : `View ${type.toUpperCase()} document`}
                      </button>
                    ))}
                    {!documentKeys.length ? <span className="cp-muted">No document metadata was returned.</span> : null}
                  </div>
                  {documentKeys.length ? (
                    <p className="cp-muted">
                      The document link expires after five minutes. Each view is recorded in the audit log.
                    </p>
                  ) : null}
                  {['pan', 'aadhaar'].map((type) => {
                    const state = documentState[type];
                    if (!state) return null;
                    if (state.error) return <div key={type} className="cp-alert cp-alert-error"><div><strong>{type.toUpperCase()} document</strong><p>{String(state.error)}</p></div></div>;
                    if (!state.data) return null;
                    const url = state.data.url;
                    return (
                      <div key={type} className="cp-alert cp-alert-info">
                        <div>
                          <strong>{type.toUpperCase()} document link</strong>
                          {url ? (
                            <p>
                              <a href={url} target="_blank" rel="noreferrer noopener" style={{ color: '#1d4ed8', fontWeight: 700 }}>
                                Open secure document
                              </a>
                              {state.data.expiresAt ? ` · expires ${formatDateTime(state.data.expiresAt)}` : ''}
                            </p>
                          ) : (
                            <p>WA HRMS did not return a document URL. The raw response is shown below.</p>
                          )}
                          <JsonBlock value={state.data} label="Document response" />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </div>

            <JsonBlock value={selected.raw} label="Raw application payload (sanitised)" />
          </>
        ) : null}
      </Modal>
    </div>
  );
}
