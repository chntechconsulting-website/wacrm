import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertCircle,
  ArrowRight,
  BadgePercent,
  Building2,
  CheckCircle2,
  Clock,
  FileText,
  Handshake,
  RefreshCw,
  Radio,
  Ticket,
  UserPlus,
  Wallet,
} from 'lucide-react';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import {
  ErrorState,
  KpiCard,
  LoadingState,
  PageHeader,
  Panel,
  RefreshButton,
  StatusBadge,
  formatDateTime,
  formatMoney,
  titleCase,
  valueOrDash,
} from './ChannelPartnerShared';

const QUICK_LINKS = [
  { to: '/channel-partners/partners', label: 'Partners', icon: Handshake, copy: 'Active, suspended and terminated partners' },
  { to: '/channel-partners/applications', label: 'Applications', icon: FileText, copy: 'Review submitted partner applications' },
  { to: '/channel-partners/leads', label: 'Partner Leads', icon: UserPlus, copy: 'Leads registered by channel partners' },
  { to: '/channel-partners/clients', label: 'Partner Clients', icon: Building2, copy: 'Client attributions earning commission' },
  { to: '/channel-partners/coupons', label: 'Partner Coupons', icon: Ticket, copy: 'Coupons assigned to partners' },
  { to: '/channel-partners/commissions', label: 'Commissions', icon: BadgePercent, copy: 'Commission ledger and status' },
  { to: '/channel-partners/payouts', label: 'Payouts', icon: Wallet, copy: 'Draft, approved, paid and cancelled payouts' },
  { to: '/channel-partners/events', label: 'Partner Activity / Events', icon: Activity, copy: 'Webhook and polling event log' },
];

const primitiveSummaryEntries = (summary) => {
  if (!summary || typeof summary !== 'object' || Array.isArray(summary)) return [];
  return Object.entries(summary)
    .filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value))
    .slice(0, 12);
};

export default function ChannelPartnerOverviewPage() {
  const { user } = useAuth();
  const isAdmin = (user?.role || '').toUpperCase() === 'ADMIN';
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [syncing, setSyncing] = useState(false);

  const fetchOverview = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const response = await API.get('/channel-partners/overview', {
        skipCache: isRefresh,
      });
      setData(response.data || null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Overview could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  const handleSync = async () => {
    setSyncing(true);
    setNotice('');
    try {
      const response = await API.post('/channel-partners/sync', { scope: 'full' });
      setNotice(
        response.data?.status === 'already_running'
          ? `A sync is already running (run #${response.data.runId}).`
          : `Full sync queued (run #${response.data?.runId}). Refresh in a moment to see progress.`,
      );
      await fetchOverview(true);
    } catch (err) {
      setNotice(err.response?.data?.detail || 'Sync could not be started.');
    } finally {
      setSyncing(false);
    }
  };

  if (loading) return <div className="cp-page"><LoadingState /></div>;
  if (error) return <div className="cp-page"><ErrorState message={error} onRetry={() => fetchOverview()} /></div>;
  if (!data) return <div className="cp-page"><ErrorState message="Overview returned no data." /></div>;

  const counts = data.counts || {};
  const integration = data.integration || {};
  const pendingApplications = counts.applications?.byStatus?.pending || 0;
  const availableCommission = counts.commissions?.byStatus?.available?.amountPaise || 0;
  const failedEvents = counts.events?.failed || 0;
  const summaryEntries = primitiveSummaryEntries(data.summary);

  return (
    <div className="cp-page">
      <PageHeader
        title="Channel Partner Overview"
        description="A read-only mirror of WA HRMS channel partners. WA HRMS remains the source of truth for registrations, approvals, commissions and payouts."
        actions={(
          <>
            <RefreshButton onClick={() => fetchOverview(true)} refreshing={refreshing} />
            {isAdmin ? (
              <button type="button" className="cp-btn cp-btn-primary" onClick={handleSync} disabled={syncing}>
                <RefreshCw size={15} className={syncing ? 'cp-spin' : undefined} />
                {syncing ? 'Starting…' : 'Run full sync'}
              </button>
            ) : null}
          </>
        )}
      />

      {notice ? (
        <div className="cp-alert cp-alert-info">
          <CheckCircle2 size={18} />
          <div><strong>Sync</strong><p>{notice}</p></div>
        </div>
      ) : null}

      {!integration.configured ? (
        <div className="cp-alert">
          <AlertCircle size={18} />
          <div>
            <strong>WA HRMS credentials are not configured</strong>
            <p>
              Partners, applications, leads and payouts stay empty until an Admin saves the API key
              in <Link to="/channel-partners/settings">Integration Settings</Link>. The key and signing
              secret are only ever read server-side.
            </p>
          </div>
        </div>
      ) : null}

      {integration.configured && !integration.webhookConfigured ? (
        <div className="cp-alert">
          <AlertCircle size={18} />
          <div>
            <strong>Webhook signing secret is not configured</strong>
            <p>
              Event polling still runs as recovery, but live updates need the
              signing secret saved in <code className="cp-code">Integration Settings</code> or{' '}
              <code className="cp-code">WAHRMS_CHANNEL_PARTNER_WEBHOOK_SECRET</code> on the server.
            </p>
          </div>
        </div>
      ) : null}

      <div className="cp-kpi-grid">
        <KpiCard icon={Handshake} label="Partners" value={(counts.partners?.total || 0).toLocaleString('en-IN')} hint={`${counts.partners?.byStatus?.active || 0} active`} tone="blue" to="/channel-partners/partners" />
        <KpiCard icon={FileText} label="Applications" value={(counts.applications?.total || 0).toLocaleString('en-IN')} hint={`${pendingApplications} pending review`} tone="amber" to="/channel-partners/applications" />
        <KpiCard icon={UserPlus} label="Partner Leads" value={(counts.leads?.total || 0).toLocaleString('en-IN')} hint={`${counts.leads?.byStatus?.converted || 0} converted`} tone="violet" to="/channel-partners/leads" />
        <KpiCard icon={Building2} label="Partner Clients" value={(counts.clients?.total || 0).toLocaleString('en-IN')} hint="Attributed client accounts" tone="green" to="/channel-partners/clients" />
        <KpiCard icon={BadgePercent} label="Available Commission" value={formatMoney(availableCommission, { compact: true })} hint={`${counts.commissions?.total || 0} ledger entries`} tone="green" to="/channel-partners/commissions" />
        <KpiCard icon={Wallet} label="Payouts" value={(counts.payouts?.total || 0).toLocaleString('en-IN')} hint={`${counts.payouts?.byStatus?.paid || 0} paid`} tone="rose" to="/channel-partners/payouts" />
      </div>

      <div className="cp-grid-2">
        <Panel
          title="Integration health"
          description="Server-to-server sync status. No secrets are displayed here."
          actions={<Link to="/channel-partners/settings" className="cp-btn cp-btn-secondary cp-btn-small">Open settings <ArrowRight size={13} /></Link>}
        >
          <div className="cp-definitions">
            <div><dt>API configured</dt><dd>{integration.configured ? <StatusBadge status="active" tone="green" /> : <StatusBadge status="not configured" tone="red" />}</dd></div>
            <div><dt>Webhook</dt><dd>{integration.webhookConfigured ? <StatusBadge status="configured" tone="green" /> : <StatusBadge status="missing secret" tone="amber" />}</dd></div>
            <div><dt>Last sync</dt><dd>{formatDateTime(integration.lastSyncAt)}</dd></div>
            <div><dt>Last sync status</dt><dd>{integration.lastSyncStatus ? <StatusBadge status={integration.lastSyncStatus} /> : '—'}</dd></div>
            <div><dt>Last event poll</dt><dd>{formatDateTime(integration.lastEventPollAt)}</dd></div>
            <div><dt>Event checkpoint</dt><dd>{Number(integration.lastProcessedCheckpoint || 0).toLocaleString('en-IN')}</dd></div>
            <div><dt>Mode</dt><dd><span className="cp-raw-tag">Read only</span></dd></div>
            <div><dt>Failed events</dt><dd>{failedEvents ? <StatusBadge status={`${failedEvents} failed`} tone="red" /> : 'None'}</dd></div>
          </div>
          {data.latestSyncRun ? (
            <div className="cp-sync-run">
              <div>
                <strong>Run #{data.latestSyncRun.id} · {titleCase(data.latestSyncRun.scope)}</strong>
                <small>{titleCase(data.latestSyncRun.trigger)} · started {formatDateTime(data.latestSyncRun.startedAt)}</small>
              </div>
              <StatusBadge status={data.latestSyncRun.status} />
            </div>
          ) : (
            <p className="cp-muted">No synchronisation has run yet.</p>
          )}
        </Panel>

        <Panel
          title="WA HRMS programme summary"
          description={data.summarySyncedAt ? `Last received ${formatDateTime(data.summarySyncedAt)}` : 'The GET /summary payload appears here after the first sync.'}
        >
          {summaryEntries.length ? (
            <div className="cp-definitions">
              {summaryEntries.map(([key, value]) => (
                <div key={key}>
                  <dt>{titleCase(key)}</dt>
                  <dd>{typeof value === 'boolean' ? (value ? 'Yes' : 'No') : valueOrDash(value)}</dd>
                </div>
              ))}
            </div>
          ) : (
            <p className="cp-muted">No programme summary has been stored yet.</p>
          )}
        </Panel>
      </div>

      <Panel
        title="Recent partner activity"
        description="The latest webhook deliveries and polled events. Full payloads stay server-side until opened by an authorised user."
        actions={<Link to="/channel-partners/events" className="cp-btn cp-btn-secondary cp-btn-small">View all events <ArrowRight size={13} /></Link>}
      >
        {data.recentEvents?.length ? (
          <div className="cp-table-wrap">
            <table className="cp-table">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Related partner</th>
                  <th>Received</th>
                </tr>
              </thead>
              <tbody>
                {data.recentEvents.map((event) => (
                  <tr key={event.id}>
                    <td><span className="cp-code">{event.id}</span></td>
                    <td>{event.type}</td>
                    <td><StatusBadge status={event.status} /></td>
                    <td>{valueOrDash(event.partnerId)}</td>
                    <td>{formatDateTime(event.receivedAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="cp-muted">No events have been received yet. Webhooks are primary; polling recovers missed deliveries.</p>
        )}
      </Panel>

      <Panel title="Jump to a section" description="Every screen below is a read-only view of the local mirror.">
        <div className="cp-kpi-grid">
          {QUICK_LINKS.map(({ to, label, icon: Icon, copy }) => (
            <Link key={to} to={to} className="cp-kpi">
              <span className="cp-kpi-icon"><Icon size={18} /></span>
              <span className="cp-kpi-copy">
                <span className="cp-kpi-label">{label}</span>
                <small>{copy}</small>
              </span>
            </Link>
          ))}
          {isAdmin ? (
            <Link to="/channel-partners/settings" className="cp-kpi">
              <span className="cp-kpi-icon"><Clock size={18} /></span>
              <span className="cp-kpi-copy">
                <span className="cp-kpi-label">Integration Settings</span>
                <small>API key, webhook secret and manual reconciliation</small>
              </span>
            </Link>
          ) : null}
        </div>
      </Panel>

      <p className="cp-muted">
        <Radio size={12} /> This module never registers partners, approves applications, adjusts commissions,
        generates payouts or calls any WA HRMS write/payout endpoint.
      </p>
    </div>
  );
}
