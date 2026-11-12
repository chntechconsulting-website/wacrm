import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  Copy,
  Download,
  ExternalLink,
  FileText,
  Camera,
  KeyRound,
  Layers,
  LayoutDashboard,
  Loader2,
  Play,
  PlugZap,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Unplug,
  Users,
  Wifi,
  X,
  XCircle,
  Zap,
} from 'lucide-react';
import './MetaIntegrationPage.css';

const RANGE_OPTIONS = [
  { value: '24H', label: 'Last 24 hours' },
  { value: '7D', label: 'Last 7 days' },
  { value: '30D', label: 'Last 30 days' },
  { value: '90D', label: 'Last 90 days' },
  { value: 'CUSTOM', label: 'Custom range' },
];

const REQUIRED_SCOPES = [
  'pages_show_list',
  'pages_read_engagement',
  'pages_manage_metadata',
  'leads_retrieval',
  'ads_read',
  'instagram_basic',
];

const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const statusTone = (status) => {
  const value = String(status || '').toUpperCase();
  if (value === 'CONNECTED' || value === 'ACTIVE' || value === 'PROCESSED' || value === 'COMPLETED' || value === 'VALID' || value === 'SUCCESS') return 'success';
  if (value === 'DISCONNECTED' || value === 'INACTIVE' || value === 'IGNORED' || value === 'CANCELLED') return 'muted';
  if (value === 'EXPIRING_SOON' || value === 'RETRYING' || value === 'PENDING' || value === 'RUNNING' || value === 'PARTIAL' || value === 'WARNING' || value === 'IDLE' || value === 'READY') return 'warning';
  return 'danger';
};

const MetaIntegrationPage = () => {
  const [dashboard, setDashboard] = useState(null);
  const [activity, setActivity] = useState([]);
  const [failedEvents, setFailedEvents] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [toast, setToast] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [copied, setCopied] = useState(false);
  const [importRange, setImportRange] = useState('24H');
  const [customRange, setCustomRange] = useState({ since: '', until: '' });
  const [pageFilter, setPageFilter] = useState('ALL');

  const user = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem('crm_user') || '{}');
    } catch {
      return {};
    }
  }, []);
  const canManage = String(user?.role || '').toUpperCase() === 'ADMIN';

  const showToast = (type, message) => {
    setToast({ type, message });
    window.setTimeout(() => setToast(null), 5000);
  };

  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [dashRes, activityRes, eventsRes, jobsRes] = await Promise.all([
        API.get('/integrations/meta/dashboard'),
        API.get('/integrations/meta/activity?limit=60'),
        API.get('/integrations/meta/events?status=FAILED&limit=100'),
        API.get('/integrations/meta/import/jobs?limit=15'),
      ]);
      setDashboard(dashRes.data || null);
      setActivity(activityRes.data?.activity || []);
      setFailedEvents(eventsRes.data?.events || []);
      setJobs(jobsRes.data?.jobs || []);
    } catch (error) {
      showToast(
        'error',
        error.response?.data?.detail || 'Failed to load Facebook & Instagram integration.'
      );
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthStatus = params.get('meta_oauth');
    if (oauthStatus) {
      showToast(
        oauthStatus === 'success' ? 'success' : 'error',
        params.get('message') || (oauthStatus === 'success' ? 'Facebook connected successfully.' : 'Facebook connection failed.')
      );
      params.delete('meta_oauth');
      params.delete('message');
      const query = params.toString();
      window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const active = jobs.some((job) => ['PENDING', 'RUNNING'].includes(job.status));
    if (!active) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const res = await API.get('/integrations/meta/import/jobs?limit=15');
        setJobs(res.data?.jobs || []);
      } catch {
        /* polling failure is non-fatal */
      }
    }, 3500);
    return () => window.clearInterval(timer);
  }, [jobs]);

  const pages = dashboard?.pages || [];
  const forms = dashboard?.forms || [];
  const stats = dashboard?.stats || {};
  const connection = dashboard?.connection;
  const token = dashboard?.token || {};
  const latestImport = jobs[0] || dashboard?.latest_import;

  const scopes = connection?.scopes || [];
  const missingScopes = REQUIRED_SCOPES.filter((scope) => !scopes.includes(scope));
  const filteredForms = pageFilter === 'ALL' ? forms : forms.filter((form) => form.page_id === pageFilter);
  const activePages = pages.filter((page) => page.is_selected);
  const totalFormsCount = forms.length;
  const selectedFormsCount = forms.filter((form) => form.is_selected).length;

  const handleConnect = async () => {
    try {
      setBusy('connect');
      const res = await API.get('/integrations/meta/oauth/start');
      if (!res.data?.authorize_url) throw new Error('Meta authorization URL was not returned.');
      window.location.href = res.data.authorize_url;
    } catch (error) {
      showToast('error', error.response?.data?.detail || error.message || 'Unable to start Facebook OAuth.');
      setBusy('');
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('Disconnect the Facebook account? Auto Sync will stop until you reconnect.')) return;
    try {
      setBusy('disconnect');
      const res = await API.post('/integrations/meta/connection/disconnect');
      showToast('success', res.data?.message || 'Facebook account disconnected.');
      await load(true);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Failed to disconnect Facebook.');
    } finally {
      setBusy('');
    }
  };

  const handleAutoSync = async (enabled) => {
    try {
      setBusy('auto-sync');
      await API.post('/integrations/meta/connection/auto-sync', { enabled });
      showToast('success', `Auto Sync ${enabled ? 'enabled' : 'disabled'}.`);
      await load(true);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Failed to update Auto Sync.');
    } finally {
      setBusy('');
    }
  };

  const handleSyncNow = async () => {
    try {
      setBusy('sync');
      const res = await API.post('/integrations/meta/sync-now', {}, { timeout: 180000 });
      const summary = res.data?.summary || {};
      showToast(
        'success',
        `Sync complete. ${summary.pages ?? 0} Page(s), ${summary.forms ?? 0} form(s), ${summary.events?.processed ?? 0} lead(s) processed.`
      );
      await load(true);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Sync Now failed.');
    } finally {
      setBusy('');
    }
  };

  const handlePageSelect = async (page, selected) => {
    try {
      setBusy(`page-${page.page_id}`);
      const res = await API.post(`/integrations/meta/pages/${page.page_id}/select`, {
        selected,
        auto_sync_enabled: selected ? page.auto_sync_enabled : false,
      });
      if (res.data?.subscription && !res.data.subscription.success) {
        showToast('warning', `Page saved, but webhook subscription failed: ${res.data.subscription.message}`);
      } else {
        showToast('success', `Page ${selected ? 'connected' : 'paused'}.`);
      }
      await load(true);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Failed to update Page selection.');
    } finally {
      setBusy('');
    }
  };

  const handlePageAutoSync = async (page, enabled) => {
    try {
      setBusy(`page-auto-${page.page_id}`);
      await API.post(`/integrations/meta/pages/${page.page_id}/auto-sync`, { enabled });
      await load(true);
      showToast('success', `Auto Sync ${enabled ? 'enabled' : 'disabled'} for ${page.page_name}.`);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Failed to update Page Auto Sync.');
    } finally {
      setBusy('');
    }
  };

  const handleRefreshForms = async (page) => {
    try {
      setBusy(`forms-${page.page_id}`);
      const res = await API.post(`/integrations/meta/pages/${page.page_id}/forms/sync`, {}, { timeout: 90000 });
      showToast('success', `${res.data?.count ?? 0} form(s) refreshed for ${page.page_name}.`);
      await load(true);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Form refresh failed.');
    } finally {
      setBusy('');
    }
  };

  const handleSubscribe = async (page) => {
    try {
      setBusy(`subscribe-${page.page_id}`);
      const res = await API.post(`/integrations/meta/pages/${page.page_id}/subscribe`);
      showToast(res.data?.success ? 'success' : 'warning', res.data?.message || 'Subscription requested.');
      await load(true);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Webhook subscription failed.');
    } finally {
      setBusy('');
    }
  };

  const updateFormSelection = async (formIds, selected) => {
    if (!formIds.length) return;
    try {
      setBusy('forms-selection');
      await API.post('/integrations/meta/forms/selection', {
        form_ids: formIds,
        selected,
      });
      await load(true);
      showToast('success', `${formIds.length} form(s) ${selected ? 'selected' : 'deselected'}.`);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Failed to update form selection.');
    } finally {
      setBusy('');
    }
  };

  const handleStartImport = async () => {
    if (importRange === 'CUSTOM' && (!customRange.since || !customRange.until)) {
      showToast('error', 'Select both a start and end date for the custom range.');
      return;
    }
    try {
      setBusy('import');
      const payload = { range: importRange };
      if (importRange === 'CUSTOM') {
        payload.since = `${customRange.since}T00:00:00`;
        payload.until = `${customRange.until}T23:59:59`;
      }
      const res = await API.post('/integrations/meta/import', payload, { timeout: 60000 });
      showToast('success', res.data?.message || 'Historical import started.');
      await load(true);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Failed to start historical import.');
    } finally {
      setBusy('');
    }
  };

  const handleCancelImport = async (jobId) => {
    try {
      setBusy(`cancel-${jobId}`);
      await API.post(`/integrations/meta/import/jobs/${jobId}/cancel`);
      showToast('success', 'Import cancellation requested.');
      await load(true);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Failed to cancel import.');
    } finally {
      setBusy('');
    }
  };

  const handleRetryAll = async () => {
    try {
      setBusy('retry-all');
      const res = await API.post('/integrations/meta/events/retry-failed');
      showToast('success', res.data?.message || 'Failed leads queued for retry.');
      await load(true);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Retry failed.');
    } finally {
      setBusy('');
    }
  };

  const handleRetryOne = async (eventId) => {
    try {
      setBusy(`retry-${eventId}`);
      const res = await API.post(`/integrations/meta/events/${eventId}/retry`);
      showToast('success', res.data?.message || 'Lead retried.');
      await load(true);
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Retry failed.');
    } finally {
      setBusy('');
    }
  };

  const copyWebhook = () => {
    if (!dashboard?.webhook_url) return;
    navigator.clipboard.writeText(dashboard.webhook_url);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  const tabs = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'pages', label: 'Pages & Forms', icon: Layers, badge: pages.length },
    { id: 'import', label: 'Historical Import', icon: Download },
    { id: 'activity', label: 'Activity & Errors', icon: Activity, badge: failedEvents.length },
  ];

  if (loading) {
    return (
      <div className="meta-page-wrapper">
        <div className="meta-loading">
          <Loader2 className="spin" size={28} />
          <span>Loading Facebook & Instagram integration…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="meta-page-wrapper">
      {toast && (
        <div className={`meta-toast ${toast.type}`}>
          {toast.type === 'success' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          <span>{toast.message}</span>
          <button type="button" onClick={() => setToast(null)} aria-label="Dismiss">
            <X size={16} />
          </button>
        </div>
      )}

      <div className="meta-page-header">
        <div>
          <div className="meta-breadcrumb">
            <Link to="/settings/integrations">
              <ArrowLeft size={14} /> Integrations
            </Link>
            <ChevronRight size={14} />
            <span>Facebook &amp; Instagram</span>
          </div>
          <div className="meta-title-group">
            <div className="meta-header-icon">
              <PlugZap size={26} />
            </div>
            <div>
              <h1 className="meta-page-title">Facebook &amp; Instagram Lead Ads</h1>
              <p className="meta-page-subtitle">
                Official Meta OAuth · Instant Form leads · Page &amp; Form auto-discovery · Historical import
              </p>
            </div>
          </div>
        </div>
        <div className="meta-header-actions">
          <button type="button" className="btn-meta-ghost" onClick={() => load()} disabled={loading}>
            <RefreshCw size={15} /> Refresh
          </button>
          <button
            type="button"
            className="btn-meta-primary"
            onClick={handleSyncNow}
            disabled={!canManage || busy === 'sync' || (!connection && !pages.length)}
          >
            {busy === 'sync' ? <Loader2 size={15} className="spin" /> : <Zap size={15} />}
            Sync Now
          </button>
        </div>
      </div>

      {!dashboard?.configured && (
        <div className="meta-banner info">
          <ShieldCheck size={18} />
          <div>
            <strong>Server configuration required.</strong>
            <p>
              Add <code>META_APP_ID</code>, <code>META_APP_SECRET</code> and{' '}
              <code>META_VERIFY_TOKEN</code> to the backend environment, then reload this page.
            </p>
          </div>
        </div>
      )}

      {connection && ['EXPIRED', 'EXPIRING_SOON'].includes(token.status) && (
        <div className={`meta-banner ${token.status === 'EXPIRED' ? 'danger' : 'warning'}`}>
          <KeyRound size={18} />
          <div>
            <strong>{token.status === 'EXPIRED' ? 'Meta access token expired.' : 'Meta access token expires soon.'}</strong>
            <p>{token.label} Reconnect the Facebook account to keep lead sync running.</p>
          </div>
          {canManage && (
            <button type="button" className="btn-meta-primary" onClick={handleConnect}>
              Reconnect
            </button>
          )}
        </div>
      )}

      {dashboard?.webhook_configured === false && (
        <div className="meta-banner danger">
          <Wifi size={18} />
          <div>
            <strong>Webhook signature verification is not configured.</strong>
            <p>Set <code>META_APP_SECRET</code>. The webhook fails closed until the app secret is present.</p>
          </div>
        </div>
      )}

      <div className="meta-stats-grid">
        <StatCard icon={Users} label="Connected accounts" value={stats.connected_accounts ?? 0} />
        <StatCard icon={Layers} label="Connected Pages" value={`${stats.connected_pages ?? 0}/${stats.total_pages ?? 0}`} />
        <StatCard icon={FileText} label="Lead Forms" value={`${stats.selected_forms ?? 0}/${stats.total_forms ?? 0}`} />
        <StatCard icon={Zap} label="Meta leads" value={stats.total_leads ?? 0} />
        <StatCard icon={Clock} label="Leads today" value={stats.today_leads ?? 0} />
        <StatCard icon={AlertTriangle} label="Failed syncs" value={stats.failed_events ?? 0} tone={stats.failed_events ? 'danger' : ''} />
        <StatCard icon={RefreshCw} label="Last sync" value={formatDateTime(stats.last_sync_at)} compact />
        <StatCard icon={Wifi} label="Webhook" value={dashboard?.webhook_status || '—'} tone={statusTone(dashboard?.webhook_status)} compact />
      </div>

      <div className="meta-tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              type="button"
              className={`meta-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={16} />
              {tab.label}
              {tab.badge ? <span className="meta-tab-badge">{tab.badge}</span> : null}
            </button>
          );
        })}
      </div>

      {activeTab === 'overview' && (
        <div className="meta-grid-2">
          <section className="meta-card">
            <div className="meta-card-head">
              <div>
                <h2>Facebook connection</h2>
                <p>Official Meta OAuth. Tokens stay encrypted on the server.</p>
              </div>
              <span className={`meta-pill ${statusTone(connection?.status)}`}>
                {connection?.status || 'NOT CONNECTED'}
              </span>
            </div>

            {connection ? (
              <>
                <div className="meta-connection-row">
                  <div className="meta-avatar">{(connection.fb_user_name || 'F').charAt(0).toUpperCase()}</div>
                  <div className="meta-connection-meta">
                    <strong>{connection.fb_user_name || 'Facebook account'}</strong>
                    <span>User ID: {connection.fb_user_id}</span>
                    <span>Connected: {formatDateTime(connection.created_at)}</span>
                  </div>
                </div>
                <div className="meta-kv-grid">
                  <KV label="Token status" value={<span className={`meta-pill ${statusTone(token.status)}`}>{token.label || token.status}</span>} />
                  <KV label="Token expiry" value={formatDateTime(token.expires_at)} />
                  <KV label="Last successful sync" value={formatDateTime(stats.last_sync_at)} />
                  <KV label="Last webhook" value={formatDateTime(stats.last_webhook_at)} />
                </div>
                <div className="meta-toggle-row">
                  <div>
                    <strong>Auto Sync</strong>
                    <span>Capture new Instant Form leads automatically.</span>
                  </div>
                  <button
                    type="button"
                    className={`meta-toggle ${connection.auto_sync_enabled ? 'on' : ''}`}
                    onClick={() => handleAutoSync(!connection.auto_sync_enabled)}
                    disabled={!canManage || busy === 'auto-sync'}
                    aria-pressed={connection.auto_sync_enabled}
                  >
                    <span />
                  </button>
                </div>
                <div className="meta-actions">
                  <button type="button" className="btn-meta-primary" onClick={handleConnect} disabled={!canManage}>
                    <RefreshCw size={15} /> Reconnect
                  </button>
                  <button type="button" className="btn-meta-danger" onClick={handleDisconnect} disabled={!canManage || busy === 'disconnect'}>
                    <Unplug size={15} /> Disconnect
                  </button>
                </div>
              </>
            ) : (
              <div className="meta-empty">
                <div className="meta-empty-icon"><PlugZap size={26} /></div>
                <h3>Connect your Facebook Business account</h3>
                <p>
                  Authorize CHN CRM to discover your Pages, Lead Forms and Instant Form leads.
                  Access tokens are encrypted and never sent to the browser.
                </p>
                <button type="button" className="btn-meta-primary" onClick={handleConnect} disabled={!canManage || !dashboard?.configured}>
                  <PlugZap size={16} /> Connect Facebook
                </button>
                {!canManage && <small>Only an administrator can connect Facebook.</small>}
              </div>
            )}
          </section>

          <section className="meta-card">
            <div className="meta-card-head">
              <div>
                <h2>Webhook</h2>
                <p>Meta sends every Instant Form submission to this endpoint.</p>
              </div>
              <span className={`meta-pill ${statusTone(dashboard?.webhook_status)}`}>{dashboard?.webhook_status || '—'}</span>
            </div>
            <label className="meta-label">Callback URL</label>
            <div className="meta-copy-field">
              <code>{dashboard?.webhook_url || '—'}</code>
              <button type="button" onClick={copyWebhook} aria-label="Copy webhook URL">
                {copied ? <Check size={15} /> : <Copy size={15} />}
              </button>
            </div>
            <div className="meta-kv-grid">
              <KV label="API version" value={dashboard?.api_version || '—'} />
              <KV label="Verify token" value={<span className="meta-muted">Configured server-side (META_VERIFY_TOKEN)</span>} />
              <KV label="Signature check" value={dashboard?.webhook_configured ? <span className="meta-ok">Enabled</span> : <span className="meta-bad">Not configured</span>} />
              <KV label="Pending retries" value={stats.pending_events ?? 0} />
            </div>
            <div className="meta-note">
              In Meta App Dashboard → Webhooks, subscribe the <strong>Page</strong> object to the{' '}
              <code>leadgen</code> field using this URL. CHN CRM subscribes each selected Page automatically.
            </div>
          </section>

          <section className="meta-card">
            <div className="meta-card-head">
              <div>
                <h2>Setup checklist</h2>
                <p>Everything required for real-time lead capture.</p>
              </div>
            </div>
            <ChecklistItem done={Boolean(connection)} label="Facebook account connected" />
            <ChecklistItem done={dashboard?.webhook_configured} label="Webhook signature verification configured" />
            <ChecklistItem done={activePages.length > 0} label={`At least one Page selected (${activePages.length})`} />
            <ChecklistItem done={selectedFormsCount > 0} label={`At least one Lead Form selected (${selectedFormsCount})`} />
            <ChecklistItem done={Boolean(connection?.auto_sync_enabled)} label="Auto Sync enabled" />
            <ChecklistItem done={!missingScopes.length} label={missingScopes.length ? `Missing permissions: ${missingScopes.join(', ')}` : 'All recommended permissions granted'} />
          </section>

          <section className="meta-card">
            <div className="meta-card-head">
              <div>
                <h2>Permissions &amp; Instagram</h2>
                <p>Scopes requested by the official OAuth dialog.</p>
              </div>
              <ShieldCheck size={18} className="meta-muted" />
            </div>
            <div className="meta-scope-list">
              {REQUIRED_SCOPES.map((scope) => (
                <span key={scope} className={`meta-scope ${scopes.includes(scope) ? 'granted' : ''}`}>
                  {scopes.includes(scope) ? <Check size={12} /> : <X size={12} />} {scope}
                </span>
              ))}
            </div>
            <div className="meta-note">
              <Camera size={14} /> Instagram business assets linked to your Pages are discovered automatically.
              Instagram Instant Form leads are captured when the authorized Page and Meta app permissions support them;
              not every Instagram account or ad format supports Instant Lead Forms.
            </div>
          </section>
        </div>
      )}

      {activeTab === 'pages' && (
        <div className="meta-stack">
          <section className="meta-card">
            <div className="meta-card-head">
              <div>
                <h2>Pages &amp; Lead Forms</h2>
                <p>All Pages returned by Meta for the connected account. No manual Page or Form ID entry.</p>
              </div>
              <div className="meta-inline-actions">
                <select className="meta-select" value={pageFilter} onChange={(event) => setPageFilter(event.target.value)}>
                  <option value="ALL">All Pages</option>
                  {pages.map((page) => (
                    <option key={page.page_id} value={page.page_id}>{page.page_name}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn-meta-ghost"
                  disabled={!canManage || !pages.length || Boolean(busy)}
                  onClick={async () => {
                    for (const page of pages.filter((item) => item.is_selected)) {
                      await handleRefreshForms(page);
                    }
                  }}
                >
                  <RefreshCw size={14} /> Refresh all forms
                </button>
              </div>
            </div>

            {!pages.length ? (
              <div className="meta-empty">
                <Layers size={26} />
                <h3>No Pages discovered yet</h3>
                <p>Connect Facebook or run Sync Now to retrieve authorized Pages.</p>
              </div>
            ) : (
              <div className="meta-page-list">
                {pages
                  .filter((page) => pageFilter === 'ALL' || page.page_id === pageFilter)
                  .map((page) => {
                    const pageForms = forms.filter((form) => form.page_id === page.page_id);
                    const selectedCount = pageForms.filter((form) => form.is_selected).length;
                    return (
                      <div key={page.page_id} className="meta-page-block">
                        <div className="meta-page-row">
                          <div className="meta-page-avatar">
                            {page.page_picture_url ? (
                              <img src={page.page_picture_url} alt="" />
                            ) : (
                              <span>{(page.page_name || 'P').charAt(0)}</span>
                            )}
                          </div>
                          <div className="meta-page-main">
                            <div className="meta-page-name">
                              <strong>{page.page_name}</strong>
                              <span className={`meta-pill ${statusTone(page.status)}`}>{page.status}</span>
                              {page.instagram_username && (
                                <span className="meta-pill instagram">
                                  <Camera size={12} /> @{page.instagram_username}
                                </span>
                              )}
                            </div>
                            <div className="meta-page-details">
                              <span>Page ID: {page.page_id}</span>
                              <span>{page.form_count} form(s) · {page.selected_form_count} selected</span>
                              <span>{page.lead_count} lead(s)</span>
                              {page.last_synced_at && <span>Synced {formatDateTime(page.last_synced_at)}</span>}
                            </div>
                            {page.error_message && (
                              <div className="meta-inline-error">
                                <AlertTriangle size={13} /> {page.error_message}
                              </div>
                            )}
                          </div>
                          <div className="meta-page-controls">
                            <label className="meta-check">
                              <input
                                type="checkbox"
                                checked={page.is_selected}
                                onChange={(event) => handlePageSelect(page, event.target.checked)}
                                disabled={!canManage || busy === `page-${page.page_id}`}
                              />
                              Connected
                            </label>
                            <label className="meta-check">
                              <input
                                type="checkbox"
                                checked={page.auto_sync_enabled}
                                onChange={(event) => handlePageAutoSync(page, event.target.checked)}
                                disabled={!canManage || !page.is_selected || busy === `page-auto-${page.page_id}`}
                              />
                              Auto Sync
                            </label>
                            <span className={`meta-pill ${page.webhook_subscribed ? 'success' : 'warning'}`}>
                              {page.webhook_subscribed ? 'Webhook active' : 'Webhook missing'}
                            </span>
                            <div className="meta-inline-actions">
                              <button
                                type="button"
                                className="btn-meta-ghost small"
                                onClick={() => handleRefreshForms(page)}
                                disabled={!canManage || busy === `forms-${page.page_id}`}
                              >
                                {busy === `forms-${page.page_id}` ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
                                Forms
                              </button>
                              <button
                                type="button"
                                className="btn-meta-ghost small"
                                onClick={() => handleSubscribe(page)}
                                disabled={!canManage || busy === `subscribe-${page.page_id}`}
                              >
                                <Wifi size={13} /> Subscribe
                              </button>
                            </div>
                          </div>
                        </div>

                        <div className="meta-forms-head">
                          <div>
                            <strong>Lead Forms</strong>
                            <span>{selectedCount} of {pageForms.length} selected</span>
                          </div>
                          <div className="meta-inline-actions">
                            <button type="button" className="btn-meta-link" onClick={() => updateFormSelection(pageForms.map((f) => f.form_id), true)} disabled={!canManage || !pageForms.length}>
                              Select all
                            </button>
                            <button type="button" className="btn-meta-link" onClick={() => updateFormSelection(pageForms.map((f) => f.form_id), false)} disabled={!canManage || !pageForms.length}>
                              Deselect all
                            </button>
                          </div>
                        </div>

                        {pageForms.length ? (
                          <div className="meta-table-wrap">
                            <table className="meta-table">
                              <thead>
                                <tr>
                                  <th style={{ width: 42 }} />
                                  <th>Form name</th>
                                  <th>Form ID</th>
                                  <th>Status</th>
                                  <th>Leads</th>
                                  <th>Last lead</th>
                                </tr>
                              </thead>
                              <tbody>
                                {pageForms.map((form) => (
                                  <tr key={form.form_id} className={form.is_selected ? 'selected' : ''}>
                                    <td>
                                      <input
                                        type="checkbox"
                                        checked={form.is_selected}
                                        onChange={() => updateFormSelection([form.form_id], !form.is_selected)}
                                        disabled={!canManage || busy === 'forms-selection'}
                                      />
                                    </td>
                                    <td><strong>{form.name || 'Untitled form'}</strong></td>
                                    <td><code>{form.form_id}</code></td>
                                    <td><span className={`meta-pill ${statusTone(form.status)}`}>{form.status}</span></td>
                                    <td>{form.leads_count ?? 0}</td>
                                    <td>{formatDateTime(form.last_lead_at)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <div className="meta-empty small">
                            <FileText size={18} />
                            <span>No forms discovered. Click <strong>Forms</strong> to refresh from Meta.</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>
            )}
          </section>
        </div>
      )}

      {activeTab === 'import' && (
        <div className="meta-grid-2">
          <section className="meta-card">
            <div className="meta-card-head">
              <div>
                <h2>Sync previous leads</h2>
                <p>Import historical Instant Form leads. Duplicates are skipped using the Meta Lead ID.</p>
              </div>
              <Download size={18} className="meta-muted" />
            </div>

            <label className="meta-label">Date range</label>
            <div className="meta-range-grid">
              {RANGE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={`meta-range ${importRange === option.value ? 'active' : ''}`}
                  onClick={() => setImportRange(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>

            {importRange === 'CUSTOM' && (
              <div className="meta-date-grid">
                <div>
                  <label className="meta-label">From</label>
                  <input
                    type="date"
                    className="meta-input"
                    value={customRange.since}
                    onChange={(event) => setCustomRange((prev) => ({ ...prev, since: event.target.value }))}
                  />
                </div>
                <div>
                  <label className="meta-label">To</label>
                  <input
                    type="date"
                    className="meta-input"
                    value={customRange.until}
                    onChange={(event) => setCustomRange((prev) => ({ ...prev, until: event.target.value }))}
                  />
                </div>
              </div>
            )}

            <div className="meta-import-scope">
              <div>
                <strong>{activePages.length}</strong>
                <span>selected Page(s)</span>
              </div>
              <div>
                <strong>{selectedFormsCount}</strong>
                <span>selected form(s)</span>
              </div>
            </div>

            <button
              type="button"
              className="btn-meta-primary wide"
              onClick={handleStartImport}
              disabled={!canManage || busy === 'import' || !selectedFormsCount}
            >
              {busy === 'import' ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
              Start historical import
            </button>

            <div className="meta-note">
              Meta only returns lead data while the form and Page are accessible and within Meta's retention rules.
              Older leads may be unavailable. Imported leads keep their original Meta creation date and use the existing
              CRM assignment and re-inquiry rules.
            </div>
          </section>

          <section className="meta-card">
            <div className="meta-card-head">
              <div>
                <h2>Import jobs</h2>
                <p>Progress is persisted and survives page reloads.</p>
              </div>
            </div>
            {!jobs.length ? (
              <div className="meta-empty small">
                <Download size={20} />
                <span>No historical imports have been run yet.</span>
              </div>
            ) : (
              <div className="meta-job-list">
                {jobs.map((job) => (
                  <div key={job.id} className="meta-job">
                    <div className="meta-job-head">
                      <div>
                        <strong>Import #{job.id}</strong>
                        <span>{job.range_preset} · {formatDateTime(job.created_at)}</span>
                      </div>
                      <span className={`meta-pill ${statusTone(job.status)}`}>{job.status}</span>
                    </div>
                    <div className="meta-progress">
                      <span style={{ width: `${Math.max(0, Math.min(100, job.progress || 0))}%` }} />
                    </div>
                    <div className="meta-job-stats">
                      <span><strong>{job.imported}</strong> imported</span>
                      <span><strong>{job.duplicates}</strong> duplicates</span>
                      <span><strong>{job.failed}</strong> failed</span>
                      <span><strong>{job.processed_forms}/{job.total_forms}</strong> forms</span>
                    </div>
                    {job.current_item && <div className="meta-job-current"><Loader2 size={12} className="spin" /> {job.current_item}</div>}
                    {job.error && <div className="meta-inline-error"><AlertTriangle size={13} /> {job.error}</div>}
                    {['PENDING', 'RUNNING'].includes(job.status) && canManage && (
                      <button
                        type="button"
                        className="btn-meta-link"
                        onClick={() => handleCancelImport(job.id)}
                        disabled={busy === `cancel-${job.id}`}
                      >
                        Cancel import
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {activeTab === 'activity' && (
        <div className="meta-stack">
          <section className="meta-card">
            <div className="meta-card-head">
              <div>
                <h2>Failed syncs</h2>
                <p>Failed lead fetches are retried automatically with backoff. You can retry immediately.</p>
              </div>
              <button
                type="button"
                className="btn-meta-primary"
                onClick={handleRetryAll}
                disabled={!canManage || !failedEvents.length || busy === 'retry-all'}
              >
                <RotateCcw size={15} /> Retry failed leads
              </button>
            </div>
            {!failedEvents.length ? (
              <div className="meta-empty small success">
                <CheckCircle2 size={22} />
                <span>No failed lead syncs. Everything is healthy.</span>
              </div>
            ) : (
              <div className="meta-table-wrap">
                <table className="meta-table">
                  <thead>
                    <tr>
                      <th>Leadgen ID</th>
                      <th>Page / Form</th>
                      <th>Attempts</th>
                      <th>Error</th>
                      <th>Last attempt</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {failedEvents.map((event) => (
                      <tr key={event.id}>
                        <td><code>{event.leadgen_id || event.event_key}</code></td>
                        <td>
                          <div className="meta-cell-stack">
                            <strong>{event.page_name || event.page_id || '—'}</strong>
                            <span>{event.form_name || event.form_id || '—'}</span>
                          </div>
                        </td>
                        <td>{event.attempt_count}/{event.max_attempts}</td>
                        <td className="meta-error-cell">{event.last_error || '—'}</td>
                        <td>{formatDateTime(event.created_at)}</td>
                        <td>
                          <button
                            type="button"
                            className="btn-meta-ghost small"
                            onClick={() => handleRetryOne(event.id)}
                            disabled={!canManage || busy === `retry-${event.id}`}
                          >
                            <RotateCcw size={13} /> Retry
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="meta-card">
            <div className="meta-card-head">
              <div>
                <h2>Sync activity log</h2>
                <p>OAuth, asset discovery, webhook and lead-processing history.</p>
              </div>
            </div>
            {!activity.length ? (
              <div className="meta-empty small">
                <Activity size={20} />
                <span>No activity recorded yet.</span>
              </div>
            ) : (
              <div className="meta-timeline">
                {activity.map((item, index) => (
                  <div key={`${item.source}-${item.id}-${index}`} className="meta-timeline-item">
                    <span className={`meta-dot ${statusTone(item.status)}`} />
                    <div>
                      <div className="meta-timeline-head">
                        <strong>{String(item.event_type || '').replaceAll('_', ' ')}</strong>
                        <span>{formatDateTime(item.created_at)}</span>
                      </div>
                      <p>{item.message}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
};

const StatCard = ({ icon: Icon, label, value, tone = '', compact = false }) => (
  <div className={`meta-stat-card ${tone}`}>
    <div className="meta-stat-icon"><Icon size={18} /></div>
    <div className="meta-stat-copy">
      <span>{label}</span>
      <strong className={compact ? 'compact' : ''}>{value}</strong>
    </div>
  </div>
);

const KV = ({ label, value }) => (
  <div className="meta-kv">
    <span>{label}</span>
    <strong>{value ?? '—'}</strong>
  </div>
);

const ChecklistItem = ({ done, label }) => (
  <div className={`meta-checklist-item ${done ? 'done' : ''}`}>
    {done ? <CheckCircle2 size={17} /> : <XCircle size={17} />}
    <span>{label}</span>
  </div>
);

export default MetaIntegrationPage;
