import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  BadgePercent,
  Building2,
  Handshake,
  Ticket,
  UserCheck,
} from 'lucide-react';
import API from '../../services/api';
import {
  DefinitionList,
  EmptyState,
  ErrorState,
  JsonBlock,
  LoadingState,
  PageHeader,
  Panel,
  RefreshButton,
  StatusBadge,
  TableShell,
  formatBps,
  formatDateTime,
  formatMoney,
  titleCase,
  valueOrDash,
} from './ChannelPartnerShared';

const TABS = [
  { key: 'overview', label: 'Overview', icon: Handshake },
  { key: 'clients', label: 'Clients', icon: Building2 },
  { key: 'coupons', label: 'Coupons', icon: Ticket },
  { key: 'commissions', label: 'Commissions', icon: BadgePercent },
];

const formatMaybePaise = (key, value) => {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number' && /paise/i.test(key)) return formatMoney(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const objectDefinitions = (value, label) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
  return Object.entries(value)
    .filter(([, item]) => item !== null && item !== undefined)
    .map(([key, item]) => ({
      label: `${label} · ${titleCase(key)}`,
      value: formatMaybePaise(key, item),
    }));
};

export default function ChannelPartnerDetailPage() {
  const { partnerId } = useParams();
  const navigate = useNavigate();
  const [partner, setPartner] = useState(null);
  const [clients, setClients] = useState([]);
  const [coupons, setCoupons] = useState([]);
  const [commissions, setCommissions] = useState([]);
  const [relatedLoading, setRelatedLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('overview');

  const fetchPartner = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    setRelatedLoading(true);
    try {
      const response = await API.get(`/channel-partners/partners/${encodeURIComponent(partnerId)}`, {
        skipCache: isRefresh,
      });
      setPartner(response.data || null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Partner details could not be loaded.');
      setLoading(false);
      setRefreshing(false);
      setRelatedLoading(false);
      return;
    }

    try {
      const [clientsResponse, couponsResponse, commissionsResponse] = await Promise.allSettled([
        API.get(`/channel-partners/partners/${encodeURIComponent(partnerId)}/clients`, {
          params: { limit: 100 },
          skipCache: isRefresh,
        }),
        API.get(`/channel-partners/partners/${encodeURIComponent(partnerId)}/coupons`, {
          params: { limit: 100 },
          skipCache: isRefresh,
        }),
        API.get(`/channel-partners/partners/${encodeURIComponent(partnerId)}/commissions`, {
          params: { limit: 100 },
          skipCache: isRefresh,
        }),
      ]);
      setClients(clientsResponse.status === 'fulfilled' ? clientsResponse.value.data?.items || [] : []);
      setCoupons(couponsResponse.status === 'fulfilled' ? couponsResponse.value.data?.items || [] : []);
      setCommissions(commissionsResponse.status === 'fulfilled' ? commissionsResponse.value.data?.items || [] : []);
    } finally {
      setRelatedLoading(false);
      setLoading(false);
      setRefreshing(false);
    }
  }, [partnerId]);

  useEffect(() => {
    fetchPartner();
  }, [fetchPartner]);

  if (loading) return <div className="cp-page"><LoadingState label="Loading partner…" /></div>;
  if (error) return <div className="cp-page"><ErrorState message={error} onRetry={() => fetchPartner()} /></div>;
  if (!partner) return <div className="cp-page"><ErrorState message="Partner not found." /></div>;

  const logins = Array.isArray(partner.logins) ? partner.logins : [];
  const tds = partner.tdsCertificate || {};
  const offerDefinitions = objectDefinitions(partner.firstClientOffer, 'First-client offer');
  const balanceDefinitions = objectDefinitions(partner.balances, 'Balance');
  const tdsStatusDefinitions = objectDefinitions(partner.tdsStatus, 'TDS');

  return (
    <div className="cp-page">
      <div>
        <button type="button" className="cp-btn cp-btn-secondary cp-btn-small" onClick={() => navigate('/channel-partners/partners')}>
          <ArrowLeft size={14} /> All partners
        </button>
      </div>

      <PageHeader
        eyebrow="Partner detail"
        title={partner.name || 'Unnamed partner'}
        description={[partner.legalName, partner.code ? `Code ${partner.code}` : null, partner.entityType ? titleCase(partner.entityType) : null].filter(Boolean).join(' · ')}
        actions={(
          <>
            <StatusBadge status={partner.status} />
            <RefreshButton onClick={() => fetchPartner(true)} refreshing={refreshing} />
          </>
        )}
      />

      <div className="cp-kpi-grid">
        <div className="cp-kpi cp-kpi-blue">
          <span className="cp-kpi-icon"><BadgePercent size={18} /></span>
          <span className="cp-kpi-copy"><span className="cp-kpi-label">Commission rate</span><strong>{formatBps(partner.commissionRateBps)}</strong><small>{titleCase(partner.payoutFrequency || '—')} payout</small></span>
        </div>
        <div className="cp-kpi cp-kpi-amber">
          <span className="cp-kpi-icon"><UserCheck size={18} /></span>
          <span className="cp-kpi-copy"><span className="cp-kpi-label">Hold period</span><strong>{partner.holdDays ?? '—'} days</strong><small>Minimum payout {formatMoney(partner.minPayoutPaise)}</small></span>
        </div>
        <div className="cp-kpi cp-kpi-green">
          <span className="cp-kpi-icon"><Building2 size={18} /></span>
          <span className="cp-kpi-copy"><span className="cp-kpi-label">Clients</span><strong>{partner.relatedCounts?.clients ?? clients.length}</strong><small>{partner.relatedCounts?.commissions ?? commissions.length} commission entries</small></span>
        </div>
        <div className="cp-kpi cp-kpi-violet">
          <span className="cp-kpi-icon"><Handshake size={18} /></span>
          <span className="cp-kpi-copy"><span className="cp-kpi-label">PAN</span><strong>{partner.panPresent ? 'On file' : 'Missing'}</strong><small>{partner.panMasked || 'Not supplied'}</small></span>
        </div>
      </div>

      <div className="cp-tabs">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} type="button" className={`cp-tab ${tab === key ? 'active' : ''}`} onClick={() => setTab(key)}>
            <Icon size={14} style={{ marginRight: 5, verticalAlign: '-2px' }} />{label}
          </button>
        ))}
      </div>

      {tab === 'overview' ? (
        <>
          <div className="cp-grid-2">
            <Panel title="Contact and address">
              <DefinitionList items={[
                { label: 'Email', value: valueOrDash(partner.email) },
                { label: 'Phone', value: valueOrDash(partner.phone) },
                { label: 'Address line 1', value: valueOrDash(partner.address?.line1) },
                { label: 'Address line 2', value: valueOrDash(partner.address?.line2) },
                { label: 'City', value: valueOrDash(partner.address?.city) },
                { label: 'State', value: valueOrDash(partner.address?.state) },
                { label: 'State code', value: valueOrDash(partner.address?.stateCode) },
                { label: 'Pincode', value: valueOrDash(partner.address?.pincode) },
                { label: 'Notes', value: valueOrDash(partner.notes) },
              ]} />
            </Panel>

            <Panel title="Compliance and terms">
              <DefinitionList items={[
                { label: 'PAN', value: partner.panMasked || '—' },
                { label: 'GST registered', value: partner.gstRegistered === null ? '—' : (partner.gstRegistered ? 'Yes' : 'No') },
                { label: 'GSTIN', value: valueOrDash(partner.gstin) },
                { label: 'GST rate', value: formatBps(partner.gstRateBps) },
                { label: 'First-client discount', value: formatBps(partner.firstClientDiscountBps) },
                { label: 'TDS certificate rate', value: formatBps(tds.rateBps) },
                { label: 'TDS certificate number', value: valueOrDash(tds.number) },
                { label: 'TDS certificate valid until', value: valueOrDash(tds.validUntil) },
                { label: 'Source created', value: formatDateTime(partner.sourceCreatedAt) },
                { label: 'Last synced', value: formatDateTime(partner.syncedAt) },
              ]} />
            </Panel>
          </div>

          {(balanceDefinitions.length || tdsStatusDefinitions.length || offerDefinitions.length) ? (
            <Panel title="Balances and programme status" description="Values exactly as reported by WA HRMS. Amounts ending in Paise are shown in rupees.">
              <DefinitionList items={[...balanceDefinitions, ...tdsStatusDefinitions, ...offerDefinitions]} />
            </Panel>
          ) : null}

          <Panel title="Partner logins" description="Invited users attached to this partner. Passwords and invite links are never stored.">
            {logins.length ? (
              <TableShell>
                <table className="cp-table">
                  <thead>
                    <tr><th>Name</th><th>Email</th><th>Role</th><th>Invite</th><th>Last login</th></tr>
                  </thead>
                  <tbody>
                    {logins.map((login, index) => (
                      <tr key={login.id || `${login.email}-${index}`}>
                        <td><strong>{valueOrDash(login.name)}</strong><small>{valueOrDash(login.phone)}</small></td>
                        <td>{valueOrDash(login.email)}</td>
                        <td>{titleCase(login.role)}</td>
                        <td>
                          <StatusBadge status={login.inviteStatus} />
                          {login.isActive === false ? <small>Inactive</small> : null}
                        </td>
                        <td>{formatDateTime(login.lastLoginAt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableShell>
            ) : <EmptyState title="No logins recorded" message="WA HRMS did not return any partner login for this partner." />}
          </Panel>

          {partner.monthlyCommissionSeries ? (
            <Panel title="Monthly commission series">
              <JsonBlock value={partner.monthlyCommissionSeries} label="Monthly series payload" />
            </Panel>
          ) : null}

          {partner.applicationDocuments ? (
            <Panel title="Application documents" description="Only document metadata is mirrored. Identity documents are fetched on demand and each view is audited.">
              <JsonBlock value={partner.applicationDocuments} label="Document metadata" />
            </Panel>
          ) : null}

          <JsonBlock value={partner.raw} label="Raw partner payload (sanitised, PAN masked)" />
        </>
      ) : null}

      {tab === 'clients' ? (
        <Panel title="Partner clients" description="Client attributions that earn commission for this partner.">
          {relatedLoading ? <LoadingState label="Loading clients…" /> : null}
          {!relatedLoading && !clients.length ? <EmptyState title="No clients" message="No client attribution has been synced for this partner yet." /> : null}
          {!relatedLoading && clients.length ? (
            <TableShell>
              <table className="cp-table">
                <thead>
                  <tr><th>Client</th><th>Organization ID</th><th>Order</th><th>Status</th><th>Effective from</th><th>Ended</th></tr>
                </thead>
                <tbody>
                  {clients.map((row) => (
                    <tr key={row.id}>
                      <td><strong>{valueOrDash(row.organizationName)}</strong><small>{valueOrDash(row.attributionId)}</small></td>
                      <td>{valueOrDash(row.organizationId)}</td>
                      <td>{valueOrDash(row.orderNumber || row.subscriptionOrderId)}</td>
                      <td><StatusBadge status={row.status} /></td>
                      <td>{formatDateTime(row.effectiveFrom)}</td>
                      <td>{formatDateTime(row.endedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableShell>
          ) : null}
        </Panel>
      ) : null}

      {tab === 'coupons' ? (
        <Panel title="Partner coupons" description="Coupons assigned to this partner in WA HRMS.">
          {relatedLoading ? <LoadingState label="Loading coupons…" /> : null}
          {!relatedLoading && !coupons.length ? <EmptyState title="No coupons" message="No coupon has been assigned to this partner yet." /> : null}
          {!relatedLoading && coupons.length ? (
            <TableShell>
              <table className="cp-table">
                <thead>
                  <tr><th>Code</th><th>Status</th><th>Discount</th><th>Assigned</th><th>Expires</th></tr>
                </thead>
                <tbody>
                  {coupons.map((row) => (
                    <tr key={row.id}>
                      <td><strong>{valueOrDash(row.code)}</strong><small>{valueOrDash(row.description)}</small></td>
                      <td><StatusBadge status={row.status} /></td>
                      <td>{formatBps(row.discountBps)}</td>
                      <td>{formatDateTime(row.assignedAt)}</td>
                      <td>{formatDateTime(row.expiresAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableShell>
          ) : null}
        </Panel>
      ) : null}

      {tab === 'commissions' ? (
        <Panel title="Commission ledger" description="The latest commission entries returned for this partner.">
          {relatedLoading ? <LoadingState label="Loading commissions…" /> : null}
          {!relatedLoading && !commissions.length ? <EmptyState title="No commission entries" message="No commission has been recorded for this partner yet." /> : null}
          {!relatedLoading && commissions.length ? (
            <TableShell>
              <table className="cp-table">
                <thead>
                  <tr><th>Description</th><th>Client</th><th>Invoice</th><th className="cp-right">Amount</th><th>Status</th><th>Earned</th></tr>
                </thead>
                <tbody>
                  {commissions.map((row) => (
                    <tr key={row.id}>
                      <td><strong>{valueOrDash(row.description || titleCase(row.type))}</strong><small>{valueOrDash(row.id)}</small></td>
                      <td>{valueOrDash(row.clientName)}</td>
                      <td>{valueOrDash(row.invoiceNumber)}</td>
                      <td className="cp-right">{formatMoney(row.amountPaise)}</td>
                      <td><StatusBadge status={row.status} /></td>
                      <td>{formatDateTime(row.earnedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableShell>
          ) : null}
          <div>
            <Link to={`/channel-partners/commissions?partnerId=${encodeURIComponent(partner.id)}`} className="cp-btn cp-btn-secondary cp-btn-small">
              Open full commission ledger
            </Link>
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
