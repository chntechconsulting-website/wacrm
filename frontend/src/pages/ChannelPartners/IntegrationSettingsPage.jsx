import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Database,
  KeyRound,
  Lock,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Webhook,
} from 'lucide-react';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import {
  DefinitionList,
  ErrorState,
  JsonBlock,
  LoadingState,
  PageHeader,
  Panel,
  RefreshButton,
  StatusBadge,
  TableShell,
  formatDateTime,
  titleCase,
  valueOrDash,
} from './ChannelPartnerShared';

const SYNC_SCOPES = [
  { value: 'full', label: 'Full sync (summary, partners, applications, leads, payouts, events)' },
  { value: 'summary', label: 'Summary only' },
  { value: 'partners', label: 'Partners' },
  { value: 'applications', label: 'Applications' },
  { value: 'leads', label: 'Partner leads' },
  { value: 'payouts', label: 'Payouts' },
  { value: 'events', label: 'Events (checkpointed poll)' },
];

const copyText = async (text) => {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // fall through to the legacy path
  }
  try {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(area);
    return ok;
  } catch {
    return false;
  }
};

export default function ChannelPartnerSettingsPage() {
  const { user } = useAuth();
  const isAdmin = (user?.role || '').toUpperCase() === 'ADMIN';

  const [settings, setSettings] = useState(null);
  const [syncStatus, setSyncStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [noticeTone, setNoticeTone] = useState('info');

  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [clearApiKey, setClearApiKey] = useState(false);
  const [webhookSecret, setWebhookSecret] = useState('');
  const [clearWebhookSecret, setClearWebhookSecret] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const [copied, setCopied] = useState(false);

  const [syncScope, setSyncScope] = useState('full');
  const [startingSync, setStartingSync] = useState(false);
  const [pollingEvents, setPollingEvents] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);

  const initialisedForm = useRef(false);

  const loadAll = useCallback(async (isRefresh = false) => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const [settingsRes, statusRes] = await Promise.all([
        API.get('/channel-partners/settings', { skipCache: true }),
        API.get('/channel-partners/sync/status', { skipCache: true }),
      ]);
      const data = settingsRes.data || null;
      setSettings(data);
      setSyncStatus(statusRes.data || null);
      if (data && !initialisedForm.current) {
        setBaseUrl(data.baseUrl || '');
        initialisedForm.current = true;
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Integration settings could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const refreshStatusOnly = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const response = await API.get('/channel-partners/sync/status', { skipCache: true });
      setSyncStatus(response.data || null);
    } catch {
      // Keep the last known status; the manual refresh surfaces errors.
    }
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin) return undefined;
    const timer = setInterval(refreshStatusOnly, 15000);
    return () => clearInterval(timer);
  }, [isAdmin, refreshStatusOnly]);

  const flash = (message, tone = 'info') => {
    setNotice(message);
    setNoticeTone(tone);
  };

  const saveSettings = async (event) => {
    event.preventDefault();
    setSaving(true);
    setNotice('');
    try {
      const payload = {};
      if (baseUrl.trim() !== (settings?.baseUrl || '')) payload.base_url = baseUrl.trim();
      if (clearApiKey) payload.clear_api_key = true;
      else if (apiKey.trim()) payload.api_key = apiKey.trim();
      if (clearWebhookSecret) payload.clear_webhook_secret = true;
      else if (webhookSecret.trim()) payload.webhook_secret = webhookSecret.trim();
      if (!Object.keys(payload).length) {
        flash('Nothing changed. Edit the base URL or enter a new API key / webhook secret first.', 'info');
        return;
      }
      const response = await API.put('/channel-partners/settings', payload);
      setSettings(response.data || settings);
      setApiKey('');
      setClearApiKey(false);
      setWebhookSecret('');
      setClearWebhookSecret(false);
      initialisedForm.current = false;
      flash('Integration settings saved. The API key and webhook secret are encrypted at rest.', 'success');
      await loadAll(true);
    } catch (err) {
      flash(err.response?.data?.detail || 'Settings could not be saved.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const response = await API.post('/channel-partners/settings/test-connection');
      setTestResult(response.data || null);
    } catch (err) {
      setTestResult({
        ok: false,
        status_code: err.response?.status || null,
        message: err.response?.data?.detail || 'Connection test failed before reaching WA HRMS.',
      });
    } finally {
      setTesting(false);
    }
  };

  const startSync = async () => {
    setStartingSync(true);
    setNotice('');
    try {
      const response = await API.post('/channel-partners/sync', { scope: syncScope });
      if (response.data?.status === 'already_running') {
        flash(`A ${response.data.scope} sync is already running (run #${response.data.runId}).`, 'info');
      } else {
        flash(`${titleCase(syncScope)} sync queued (run #${response.data?.runId}). This page refreshes every 15 seconds.`, 'success');
      }
      await refreshStatusOnly();
    } catch (err) {
      flash(err.response?.data?.detail || 'Sync could not be started.', 'error');
    } finally {
      setStartingSync(false);
    }
  };

  const pollEvents = async () => {
    setPollingEvents(true);
    setNotice('');
    try {
      const response = await API.post('/channel-partners/sync/events');
      flash(`Event poll queued (run #${response.data?.runId}).`, 'success');
      await refreshStatusOnly();
    } catch (err) {
      flash(err.response?.data?.detail || 'Event poll could not be started.', 'error');
    } finally {
      setPollingEvents(false);
    }
  };

  const reprocessFailed = async () => {
    setReprocessing(true);
    setNotice('');
    try {
      const response = await API.post('/channel-partners/sync/reprocess-failed', null, {
        params: { limit: 100 },
      });
      flash(`Queued ${response.data?.count ?? 0} failed event(s) for reprocessing.`, 'success');
      await refreshStatusOnly();
    } catch (err) {
      flash(err.response?.data?.detail || 'Failed events could not be queued.', 'error');
    } finally {
      setReprocessing(false);
    }
  };

  const copyWebhookUrl = async () => {
    const url = settings?.webhookUrl || '';
    if (!url) return;
    const ok = await copyText(url);
    setCopied(ok);
    if (ok) setTimeout(() => setCopied(false), 2000);
  };

  if (!isAdmin) {
    return (
      <div className="cp-page">
        <PageHeader title="Integration Settings" description="Channel Partner integration settings are restricted to Admins." />
        <div className="cp-alert">
          <ShieldCheck size={18} />
          <div>
            <strong>Admin only</strong>
            <p>You do not have permission to view or change the WA HRMS Channel Partner configuration.</p>
          </div>
        </div>
      </div>
    );
  }

  if (loading) return <div className="cp-page"><LoadingState label="Loading integration settings…" /></div>;
  if (error) return <div className="cp-page"><ErrorState message={error} onRetry={() => loadAll()} /></div>;

  const latestRun = syncStatus?.latest || settings?.latestSyncRun || null;
  const runs = Array.isArray(syncStatus?.runs) ? syncStatus.runs : [];
  const checkpoint = syncStatus?.checkpoint || {};

  return (
    <div className="cp-page">
      <PageHeader
        title="Channel Partner Integration Settings"
        description="Server-to-server connection to WA HRMS. This CRM is a read-only mirror: no partner, commission or payout writes are ever sent."
        actions={<RefreshButton onClick={() => loadAll(true)} refreshing={refreshing} />}
      />

      {notice ? (
        <div className={`cp-alert ${noticeTone === 'error' ? 'cp-alert-error' : noticeTone === 'success' ? 'cp-alert-info' : ''}`}>
          {noticeTone === 'error' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
          <div><p>{notice}</p></div>
        </div>
      ) : null}

      <div className="cp-kpi-grid">
        <div className={`cp-kpi cp-kpi-${settings?.configured ? 'green' : 'rose'}`}>
          <span className="cp-kpi-icon"><Database size={18} /></span>
          <div className="cp-kpi-copy">
            <span className="cp-kpi-label">API status</span>
            <strong>{settings?.configured ? 'Configured' : 'Not configured'}</strong>
            <small>API key source: {titleCase(settings?.apiKeySource || 'none')}</small>
          </div>
        </div>
        <div className={`cp-kpi cp-kpi-${settings?.webhookConfigured ? 'green' : 'amber'}`}>
          <span className="cp-kpi-icon"><Webhook size={18} /></span>
          <div className="cp-kpi-copy">
            <span className="cp-kpi-label">Webhook secret</span>
            <strong>{settings?.webhookConfigured ? 'Configured' : 'Missing'}</strong>
            <small>Source: {titleCase(settings?.webhookSecretSource || 'none')}</small>
          </div>
        </div>
        <div className="cp-kpi cp-kpi-blue">
          <span className="cp-kpi-icon"><Clock size={18} /></span>
          <div className="cp-kpi-copy">
            <span className="cp-kpi-label">Last sync</span>
            <strong>{settings?.lastSyncAt ? formatDateTime(settings.lastSyncAt) : 'Never'}</strong>
            <small>{settings?.lastSyncStatus ? `Status: ${titleCase(settings.lastSyncStatus)}` : 'No sync run yet'}</small>
          </div>
        </div>
        <div className="cp-kpi cp-kpi-violet">
          <span className="cp-kpi-icon"><RefreshCw size={18} /></span>
          <div className="cp-kpi-copy">
            <span className="cp-kpi-label">Event checkpoint</span>
            <strong>{Number(checkpoint.lastProcessedCheckpoint || settings?.lastProcessedCheckpoint || 0).toLocaleString('en-IN')}</strong>
            <small>{settings?.lastEventPollAt ? `Polled ${formatDateTime(settings.lastEventPollAt)}` : 'No poll yet'}</small>
          </div>
        </div>
      </div>

      <div className="cp-grid-2">
        <Panel
          title="Connection and secrets"
          description="The base URL, API key and webhook signing secret are used only for the documented read-only integration. Secrets are never returned in full."
        >
          <form className="cp-stack" onSubmit={saveSettings}>
            <label className="cp-field">
              <span>API base URL</span>
              <input
                type="url"
                value={baseUrl}
                placeholder="https://api.wahrms.com/api/v1/integrations/channel-partners"
                onChange={(event) => setBaseUrl(event.target.value)}
              />
            </label>
            <p className="cp-muted" style={{ margin: 0 }}>
              Effective source: <span className="cp-raw-tag">{titleCase(settings?.baseUrlSource || 'environment')}</span>.
              Leave blank to fall back to <code className="cp-code">WAHRMS_CHANNEL_PARTNER_BASE_URL</code>.
            </p>

            <label className="cp-field">
              <span>API key {settings?.apiKeyConfigured ? `(current: ${settings.apiKeyMasked})` : ''}</span>
              <input
                type="password"
                value={apiKey}
                autoComplete="new-password"
                placeholder={settings?.apiKeyConfigured ? 'Enter a new key to replace the stored one' : 'Paste the WA HRMS read-scope API key'}
                onChange={(event) => setApiKey(event.target.value)}
              />
            </label>
            <label className="cp-check">
              <input
                type="checkbox"
                checked={clearApiKey}
                onChange={(event) => setClearApiKey(event.target.checked)}
              />
              Clear the stored API key and fall back to the environment value
            </label>

            <label className="cp-field">
              <span>Webhook signing secret {settings?.webhookSecretConfigured ? `(current: ${settings.webhookSecretMasked})` : ''}</span>
              <input
                type="password"
                value={webhookSecret}
                autoComplete="new-password"
                placeholder={settings?.webhookSecretConfigured ? 'Enter a new secret to replace the stored one' : 'Paste the whsec_… secret from WA HRMS'}
                onChange={(event) => setWebhookSecret(event.target.value)}
              />
            </label>
            <p className="cp-muted" style={{ margin: 0 }}>
              Effective source: <span className="cp-raw-tag">{titleCase(settings?.webhookSecretSource || 'none')}</span>.
              Leave blank to fall back to <code className="cp-code">WAHRMS_CHANNEL_PARTNER_WEBHOOK_SECRET</code>.
            </p>
            <label className="cp-check">
              <input
                type="checkbox"
                checked={clearWebhookSecret}
                onChange={(event) => setClearWebhookSecret(event.target.checked)}
              />
              Clear the stored webhook secret and fall back to the environment value
            </label>

            <div className="cp-inline">
              <button type="submit" className="cp-btn cp-btn-primary" disabled={saving}>
                <KeyRound size={15} /> {saving ? 'Saving…' : 'Save settings'}
              </button>
              <button type="button" className="cp-btn cp-btn-secondary" onClick={testConnection} disabled={testing}>
                <Play size={15} /> {testing ? 'Testing…' : 'Test connection'}
              </button>
            </div>
          </form>

          {testResult ? (
            <div className={`cp-alert ${testResult.ok ? 'cp-alert-info' : 'cp-alert-error'}`}>
              {testResult.ok ? <CheckCircle2 size={17} /> : <AlertCircle size={17} />}
              <div>
                <strong>{testResult.ok ? 'Connection succeeded' : 'Connection failed'}</strong>
                <p>{testResult.message || (testResult.ok ? 'WA HRMS accepted the credentials.' : 'No detail was returned.')}</p>
                {testResult.status_code ? <p>HTTP status: {testResult.status_code}</p> : null}
                {testResult.tested_at ? <p className="cp-muted">Tested {formatDateTime(testResult.tested_at)}</p> : null}
                <JsonBlock value={testResult} label="Full connection result" />
              </div>
            </div>
          ) : null}
        </Panel>

        <Panel
          title="Webhook endpoint"
          description="Add this URL in WA HRMS. Deliveries are verified with HMAC-SHA256 over the raw body."
        >
          <div className="cp-copy-row">
            <code className="cp-code">{settings?.webhookUrl || '/webhooks/wahrms'}</code>
            <button type="button" className="cp-btn cp-btn-secondary cp-btn-small" onClick={copyWebhookUrl}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? 'Copied' : 'Copy URL'}
            </button>
          </div>
          <DefinitionList items={[
            { label: 'Path', value: settings?.webhookPath || '/webhooks/wahrms' },
            { label: 'Signing secret', value: settings?.webhookSecretConfigured ? <StatusBadge status="configured" tone="green" /> : <StatusBadge status="missing" tone="amber" /> },
            { label: 'Secret source', value: titleCase(settings?.webhookSecretSource || 'none') },
            { label: 'Masked secret', value: valueOrDash(settings?.webhookSecretMasked) },
            { label: 'Last delivery', value: formatDateTime(settings?.webhookLastReceivedAt) },
            { label: 'Last event type', value: valueOrDash(settings?.webhookLastEventType) },
            { label: 'Payouts scope', value: 'Never requested' },
            { label: 'Mode', value: <span className="cp-raw-tag">Read only</span> },
          ]} />
          <div className="cp-alert">
            <Lock size={17} />
            <div>
              <strong>Secret handling</strong>
              <p>
                Paste the signing secret above to store it encrypted in the CRM database, or leave it blank to use{' '}
                <code className="cp-code">WAHRMS_CHANNEL_PARTNER_WEBHOOK_SECRET</code>.
                It is never stored in the browser or returned by the API. Signature mismatches and timestamps outside
                five minutes are rejected; <code className="cp-code">WAHRMS-Event-Id</code> prevents duplicate processing.
              </p>
            </div>
          </div>
          <ul className="cp-callout-list cp-muted">
            <li>Backend acknowledges within 10 seconds and processes events in the background.</li>
            <li>Event polling with the saved <code className="cp-code">nextAfter</code> checkpoint recovers missed deliveries.</li>
            <li>Firewalls must allow the exact <code className="cp-code">/webhooks/wahrms</code> path through nginx.</li>
          </ul>
        </Panel>
      </div>

      <Panel
        title="Manual sync and reconciliation"
        description="Initial full sync runs automatically once when credentials are present and the mirror is empty. These controls are for manual recovery."
        actions={(
          <button type="button" className="cp-btn cp-btn-secondary cp-btn-small" onClick={refreshStatusOnly}>
            <RefreshCw size={13} /> Refresh status
          </button>
        )}
      >
        <div className="cp-filters">
          <label className="cp-field cp-grow">
            <span>Sync scope</span>
            <select value={syncScope} onChange={(event) => setSyncScope(event.target.value)}>
              {SYNC_SCOPES.map((scope) => <option key={scope.value} value={scope.value}>{scope.label}</option>)}
            </select>
          </label>
          <button type="button" className="cp-btn cp-btn-primary" onClick={startSync} disabled={startingSync || !settings?.configured}>
            <RefreshCw size={15} className={startingSync ? 'cp-spin' : undefined} />
            {startingSync ? 'Queueing…' : 'Start sync'}
          </button>
          <button type="button" className="cp-btn cp-btn-secondary" onClick={pollEvents} disabled={pollingEvents || !settings?.configured}>
            <Play size={15} /> {pollingEvents ? 'Queueing…' : 'Poll events now'}
          </button>
          <button type="button" className="cp-btn cp-btn-secondary" onClick={reprocessFailed} disabled={reprocessing}>
            <RotateCcw size={15} className={reprocessing ? 'cp-spin' : undefined} />
            {reprocessing ? 'Queueing…' : 'Reprocess failed events'}
          </button>
        </div>

        {!settings?.configured ? (
          <div className="cp-alert">
            <AlertCircle size={17} />
            <div>
              <strong>Sync disabled until credentials are saved</strong>
              <p>Save a read-scope API key above, then start a full sync.</p>
            </div>
          </div>
        ) : null}

        {settings?.lastSyncError ? (
          <div className="cp-alert cp-alert-error">
            <AlertCircle size={17} />
            <div><strong>Last sync error</strong><p className="cp-error-text">{settings.lastSyncError}</p></div>
          </div>
        ) : null}
        {settings?.lastEventPollError ? (
          <div className="cp-alert cp-alert-error">
            <AlertCircle size={17} />
            <div><strong>Last event poll error</strong><p className="cp-error-text">{settings.lastEventPollError}</p></div>
          </div>
        ) : null}

        {latestRun ? (
          <div className="cp-sync-run">
            <div>
              <strong>Latest run #{latestRun.id} · {titleCase(latestRun.scope)}</strong>
              <small>
                {titleCase(latestRun.trigger)} · started {formatDateTime(latestRun.startedAt)}
                {latestRun.finishedAt ? ` · finished ${formatDateTime(latestRun.finishedAt)}` : ''}
              </small>
            </div>
            <StatusBadge status={latestRun.status} />
          </div>
        ) : (
          <p className="cp-muted">No synchronisation has run yet.</p>
        )}

        {runs.length ? (
          <TableShell>
            <table className="cp-table">
              <thead>
                <tr><th>Run</th><th>Scope</th><th>Trigger</th><th>Status</th><th>Started</th><th>Finished</th><th>Stats</th></tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>#{run.id}</td>
                    <td>{titleCase(run.scope)}</td>
                    <td>{titleCase(run.trigger)}</td>
                    <td><StatusBadge status={run.status} /></td>
                    <td>{formatDateTime(run.startedAt)}</td>
                    <td>{formatDateTime(run.finishedAt)}</td>
                    <td>
                      {run.stats ? <JsonBlock value={run.stats} label="Stats" /> : '—'}
                      {run.error ? <span className="cp-error-text">{run.error}</span> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
        ) : null}
      </Panel>

      <Panel title="Safety boundaries" description="Why this integration cannot change WA HRMS data.">
        <div className="cp-grid-2">
          <div>
            <DefinitionList items={[
              { label: 'Requested scopes', value: (settings?.scopes || ['read']).join(', ') },
              { label: 'Payouts scope', value: settings?.payoutsScopeEnabled ? 'Enabled' : 'Disabled' },
              { label: 'Write endpoints', value: 'Not called' },
              { label: 'Secret handling', value: valueOrDash(settings?.secretHandling) },
            ]} />
          </div>
          <ul className="cp-callout-list cp-muted">
            <li>Only documented GET endpoints are used. Registration, approval, commission and payout routes are never called.</li>
            <li>Full PAN and bank/Aadhaar data are not stored; PAN is masked and sensitive document URLs are stripped.</li>
            <li>Application document links require Channel Partner edit/approval permission and every view is audited.</li>
            <li>Sync and settings changes are recorded in the CRM audit log.</li>
          </ul>
        </div>
        <div className="cp-inline">
          <Link to="/channel-partners/events" className="cp-btn cp-btn-secondary cp-btn-small">Open event log</Link>
          <Link to="/channel-partners" className="cp-btn cp-btn-secondary cp-btn-small">Back to overview</Link>
        </div>
      </Panel>
    </div>
  );
}
