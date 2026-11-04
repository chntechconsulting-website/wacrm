import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Copy,
  ExternalLink,
  FileText,
  KeyRound,
  Link2,
  Loader2,
  Lock,
  MessageCircle,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Smartphone,
  Unplug,
  Users,
  Webhook,
} from 'lucide-react';
import './WhatsAppConnectionPage.css';

const STATUS_LABELS = {
  PENDING: 'Pending',
  CONNECTED: 'Connected',
  SYNCING: 'Syncing',
  SYNC_COMPLETE: 'Sync complete',
  DISCONNECTED: 'Disconnected',
  ERROR: 'Error',
};

const formatDate = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString();
};

const formatRemaining = (deadline) => {
  if (!deadline) return null;
  const ms = new Date(deadline).getTime() - Date.now();
  if (Number.isNaN(ms)) return null;
  if (ms <= 0) return 'Window closed';
  const totalMinutes = Math.floor(ms / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours <= 0) return `${minutes} min left`;
  return `${hours}h ${minutes}m left`;
};

const safeParse = (value) => {
  if (!value) return {};
  if (typeof value === 'object') return value;
  try {
    return JSON.parse(value);
  } catch {
    return {};
  }
};

const isFacebookOrigin = (origin) => {
  try {
    const url = new URL(origin);
    return (
      url.protocol === 'https:' &&
      (url.hostname === 'facebook.com' || url.hostname.endsWith('.facebook.com'))
    );
  } catch {
    return false;
  }
};

const WhatsAppConnectionPage = () => {
  const { user } = useAuth();
  const isReviewer = user?.role === 'META_REVIEWER';
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sdkReady, setSdkReady] = useState(false);
  const [sdkError, setSdkError] = useState('');
  const [action, setAction] = useState('');
  const [toast, setToast] = useState(null);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [authCode, setAuthCode] = useState('');
  const [exchanging, setExchanging] = useState(false);
  const [showTemplateForm, setShowTemplateForm] = useState(false);
  const [templateForm, setTemplateForm] = useState({
    name: '',
    language: 'en_US',
    category: 'UTILITY',
    body_text: '',
    footer_text: '',
  });
  const [, setClockTick] = useState(0);
  const exchangeStarted = useRef(false);
  const toastTimer = useRef(null);

  const showToast = useCallback((type, message) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ type, message });
    toastTimer.current = setTimeout(() => setToast(null), 6000);
  }, []);

  const fetchStatus = useCallback(async ({ quiet = false } = {}) => {
    try {
      if (!quiet) setLoading(true);
      const response = await API.get('/whatsapp/coexistence/status');
      setStatus(response.data || null);
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      showToast('error', `Could not load connection status: ${detail}`);
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [showToast]);

  const fetchEvents = useCallback(async () => {
    try {
      const response = await API.get('/whatsapp/coexistence/events', { params: { limit: 20 } });
      setEvents(response.data || []);
    } catch {
      // The events panel is diagnostic; a failure must not block onboarding.
    }
  }, []);

  const fetchTemplates = useCallback(async () => {
    try {
      const response = await API.get('/whatsapp/coexistence/templates');
      setTemplates(response.data || []);
    } catch {
      // No active connection yet, or Meta is unreachable. Keep the panel empty.
      setTemplates([]);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchEvents();
  }, [fetchStatus, fetchEvents]);

  useEffect(() => {
    if (!status?.connection) {
      setTemplates([]);
      return;
    }
    fetchTemplates();
  }, [status?.connection?.id, status?.connection?.status, fetchTemplates]);

  useEffect(() => {
    const timer = setInterval(() => setClockTick((tick) => tick + 1), 30000);
    return () => clearInterval(timer);
  }, []);

  // Load the Facebook JS SDK only when the backend has a public app ID.
  useEffect(() => {
    const appId = status?.config?.app_id;
    if (!appId) return;
    if (window.FB) {
      setSdkReady(true);
      return;
    }
    window.fbAsyncInit = () => {
      try {
        window.FB.init({
          appId,
          autoLogAppEvents: true,
          xfbml: true,
          version: status?.config?.api_version || 'v26.0',
        });
        setSdkReady(true);
      } catch (error) {
        setSdkError('Facebook SDK initialisation failed.');
      }
    };
    if (document.getElementById('facebook-jssdk')) return;
    const script = document.createElement('script');
    script.id = 'facebook-jssdk';
    script.src = 'https://connect.facebook.net/en_US/sdk.js';
    script.async = true;
    script.defer = true;
    script.crossOrigin = 'anonymous';
    script.onerror = () => setSdkError('Could not load the Facebook SDK. Check the browser network/proxy.');
    document.body.appendChild(script);
  }, [status?.config?.app_id, status?.config?.api_version]);

  // Session logging. Meta posts a WA_EMBEDDED_SIGNUP message with the asset IDs.
  useEffect(() => {
    const handleMessage = async (event) => {
      if (!isFacebookOrigin(event.origin)) return;
      const payload = safeParse(event.data);
      if (!payload || payload.type !== 'WA_EMBEDDED_SIGNUP') return;

      const data = payload.data || {};
      const eventName = payload.event || data.event || 'UNKNOWN';
      setSessionInfo({ event: eventName, ...data });

      try {
        await API.post('/whatsapp/coexistence/session-log', {
          type: payload.type,
          event: eventName,
          data: { ...data, event: eventName },
        });
      } catch {
        // Session logging is an audit aid; the exchange is still attempted.
      }

      if (eventName === 'CANCEL') {
        showToast('error', 'Embedded Signup was cancelled on the Meta screen.');
      } else if (eventName === 'ERROR') {
        showToast('error', data.error_message || 'Meta reported an error during Embedded Signup.');
      } else if (eventName === 'FINISH') {
        showToast('success', 'Meta finished the signup session. Completing the backend exchange…');
        fetchEvents();
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [fetchEvents, showToast]);

  // The exchange code expires in 30 seconds. Coexistence session events may
  // return only waba_id, so the backend resolves phone_number_id when omitted.
  useEffect(() => {
    const wabaId = sessionInfo?.waba_id;
    const phoneNumberId = sessionInfo?.phone_number_id;
    if (!authCode || !wabaId || exchangeStarted.current) return;

    exchangeStarted.current = true;
    setExchanging(true);
    (async () => {
      try {
        await API.post('/whatsapp/coexistence/exchange', {
          code: authCode,
          waba_id: String(wabaId),
          phone_number_id: phoneNumberId ? String(phoneNumberId) : null,
          business_id: sessionInfo?.business_id ? String(sessionInfo.business_id) : null,
          session_event: sessionInfo?.event || null,
        });
        showToast(
          'success',
          'Number connected. Meta synchronization has started — watch the 24-hour window.'
        );
        await fetchStatus({ quiet: true });
        await fetchEvents();
        await fetchTemplates();
      } catch (error) {
        const detail = error.response?.data?.detail || error.message;
        showToast('error', `Connection exchange failed: ${detail}`);
      } finally {
        setAuthCode('');
        setExchanging(false);
      }
    })();
  }, [authCode, sessionInfo, fetchStatus, fetchEvents, fetchTemplates, showToast]);

  const launchSignup = () => {
    if (!window.FB) {
      showToast('error', 'The Facebook SDK is not ready yet. Reload the page and retry.');
      return;
    }
    exchangeStarted.current = false;
    setAuthCode('');
    setSessionInfo(null);
    window.FB.login(
      (response) => {
        if (response?.authResponse?.code) {
          setAuthCode(response.authResponse.code);
        } else {
          showToast('error', 'Embedded Signup was not authorised. No connection was changed.');
        }
      },
      {
        config_id: status?.config?.config_id,
        response_type: 'code',
        override_default_response_type: true,
        extras: {
          setup: {},
          featureType: 'whatsapp_business_app_onboarding',
          sessionInfoVersion: '3',
        },
      }
    );
  };

  const runAction = async (name, request, successMessage) => {
    try {
      setAction(name);
      await request();
      showToast('success', successMessage);
      await fetchStatus({ quiet: true });
      await fetchEvents();
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      showToast('error', detail);
    } finally {
      setAction('');
    }
  };

  const handleRefresh = () =>
    runAction(
      'refresh',
      () => API.post('/whatsapp/coexistence/refresh'),
      'Connection details refreshed from Meta.'
    );

  const handleSync = (syncType) =>
    runAction(
      `sync-${syncType}`,
      () => API.post('/whatsapp/coexistence/sync', { sync_type: syncType }),
      `${syncType === 'contacts' ? 'Contact' : 'History'} synchronization requested.`
    );

  const handleCreateTemplate = async (event) => {
    event.preventDefault();
    try {
      setAction('template');
      await API.post('/whatsapp/coexistence/templates', templateForm);
      showToast('success', 'Template submitted to Meta for review.');
      setShowTemplateForm(false);
      setTemplateForm({
        name: '',
        language: 'en_US',
        category: 'UTILITY',
        body_text: '',
        footer_text: '',
      });
      await fetchTemplates();
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      showToast('error', detail);
    } finally {
      setAction('');
    }
  };

  const copyText = async (value, label) => {
    try {
      await navigator.clipboard.writeText(value);
      showToast('success', `${label} copied.`);
    } catch {
      showToast('error', 'Could not copy to the clipboard.');
    }
  };

  const connection = status?.connection;
  const config = status?.config;
  const warnings = config?.warnings || [];
  const contactSyncUsed = Boolean(connection?.contacts_sync_requested_at);
  const historySyncUsed = Boolean(connection?.history_sync_requested_at);
  const syncRemaining = formatRemaining(connection?.sync_deadline_at);
  const statusKey = String(connection?.status || 'PENDING').toUpperCase();

  return (
    <div className="wa-conn-page">
      {toast && (
        <div className={`wa-conn-toast ${toast.type}`}>
          {toast.type === 'success' ? (
            <CheckCircle2 size={19} />
          ) : (
            <AlertTriangle size={19} />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      <div className="wa-conn-header">
        <div>
          <div className="wa-conn-breadcrumb">
            <Link to="/settings/integrations">
              <ArrowLeft size={14} /> Back to Integration Hub
            </Link>
          </div>
          <div className="wa-conn-title-row">
            <div className="wa-conn-title-icon">
              <MessageCircle size={25} />
            </div>
            <div>
              <h1>WhatsApp Business App Connection</h1>
              <p>
                Official Meta coexistence onboarding for an existing WhatsApp Business
                App number. No QR automation and no unofficial providers.
              </p>
            </div>
          </div>
        </div>
        <div className="wa-conn-header-actions">
          <button
            type="button"
            className="wa-conn-btn secondary"
            onClick={() => fetchStatus()}
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
            Refresh
          </button>
          {connection && (
            <button
              type="button"
              className="wa-conn-btn secondary"
              onClick={handleRefresh}
              disabled={action === 'refresh' || isReviewer}
            >
              {action === 'refresh' ? <Loader2 size={15} className="spin" /> : <RotateCcw size={15} />}
              Re-read from Meta
            </button>
          )}
        </div>
      </div>

      {isReviewer && (
        <div className="wa-conn-banner info">
          <ShieldCheck size={20} />
          <div>
            <strong>Meta review access</strong>
            <p>
              This account can view the WhatsApp connection status and create
              review templates. Onboarding, re-read, and sync actions are disabled.
            </p>
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <div className={`wa-conn-banner ${config?.ready ? 'info' : 'locked'}`}>
          {config?.ready ? <AlertTriangle size={20} /> : <Lock size={20} />}
          <div>
            <strong>
              {config?.ready
                ? 'Credentials are present, but review the notes below.'
                : 'Onboarding is locked'}
            </strong>
            <ul>
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <div className="wa-conn-grid two-col">
        <section className="wa-conn-card">
          <div className="wa-conn-card-head">
            <div>
              <h2>
                <Smartphone size={18} /> Embedded Signup
              </h2>
              <p>
                The business scans the Meta prompt in Facebook Login for Business and
                keeps using the WhatsApp Business App after onboarding.
              </p>
            </div>
          </div>

          <div className="wa-conn-safety">
            <ShieldCheck size={17} />
            <p>
              Do not connect the production number <strong>7547900900</strong> until
              Tech Provider/App Review approval is complete, the sync code has passed
              tests, and the business owner explicitly confirms live onboarding.
            </p>
          </div>

          <ol className="wa-conn-steps">
            <li>Click <strong>Launch Embedded Signup</strong> and log in with the business Facebook account.</li>
            <li>Select the existing WhatsApp Business App number and approve the permissions.</li>
            <li>The CRM exchanges the one-time code, subscribes its app, and requests the one-time contacts/history sync.</li>
            <li>Keep the number in the Business App. Meta mirrors Business App messages into this CRM inbox.</li>
          </ol>

          {sdkError && <div className="wa-conn-inline-error">{sdkError}</div>}

          <div className="wa-conn-launch-row">
            <button
              type="button"
              className="wa-conn-btn primary"
              onClick={launchSignup}
              disabled={!config?.ready || !sdkReady || exchanging || isReviewer}
            >
              {exchanging ? (
                <Loader2 size={17} className="spin" />
              ) : (
                <ExternalLink size={17} />
              )}
              {exchanging
                ? 'Completing connection…'
                : connection
                  ? 'Reconnect with Meta'
                  : 'Launch Embedded Signup'}
            </button>
            <span className="wa-conn-hint">
              {!config?.enabled
                ? 'Set WHATSAPP_COEXISTENCE_ENABLED=true after approval.'
                : !config?.configured
                  ? 'Add the Facebook Login for Business configuration ID.'
                  : !sdkReady
                    ? 'Waiting for the Facebook SDK…'
                    : 'Facebook Login for Business opens in a Meta popup.'}
            </span>
          </div>

          {(sessionInfo || authCode || exchanging) && (
            <div className="wa-conn-session">
              <div className="wa-conn-session-title">
                <Link2 size={15} /> Session log
              </div>
              <div className="wa-conn-session-grid">
                <span>Event</span>
                <strong>{sessionInfo?.event || 'Waiting for Meta'}</strong>
                <span>WABA ID</span>
                <strong>{sessionInfo?.waba_id || '—'}</strong>
                <span>Phone number ID</span>
                <strong>{sessionInfo?.phone_number_id || '—'}</strong>
                <span>Business ID</span>
                <strong>{sessionInfo?.business_id || '—'}</strong>
                <span>Exchange code</span>
                <strong>{authCode ? 'received (not displayed)' : 'waiting'}</strong>
              </div>
            </div>
          )}

          {connection && (
            <div className={`wa-conn-status-strip ${statusKey.toLowerCase()}`}>
              <div>
                <span className="wa-conn-status-dot" />
                <strong>{STATUS_LABELS[statusKey] || statusKey}</strong>
              </div>
              <span>
                {connection.webhook_subscribed
                  ? 'App subscribed to this WABA'
                  : 'WABA subscription not confirmed'}
              </span>
            </div>
          )}
        </section>

        <section className="wa-conn-card">
          <div className="wa-conn-card-head">
            <div>
              <h2>
                <ShieldCheck size={18} /> Connection status
              </h2>
              <p>Secrets stay encrypted on the backend; this page never receives tokens.</p>
            </div>
          </div>

          {!connection ? (
            <div className="wa-conn-empty">
              <Unplug size={30} />
              <h3>No coexistence connection yet</h3>
              <p>
                Nothing has been changed on Meta. The onboarding flow only creates a
                connection after a business completes Embedded Signup.
              </p>
            </div>
          ) : (
            <>
              <dl className="wa-conn-details">
                <div>
                  <dt>Status</dt>
                  <dd>
                    <span className={`wa-conn-pill ${statusKey.toLowerCase()}`}>
                      {STATUS_LABELS[statusKey] || statusKey}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>Onboarding</dt>
                  <dd>{connection.onboarding_status || '—'}</dd>
                </div>
                <div>
                  <dt>Display number</dt>
                  <dd>{connection.display_phone_number || '—'}</dd>
                </div>
                <div>
                  <dt>Verified name</dt>
                  <dd>{connection.verified_name || '—'}</dd>
                </div>
                <div>
                  <dt>WABA ID</dt>
                  <dd className="mono">{connection.waba_id}</dd>
                </div>
                <div>
                  <dt>Phone number ID</dt>
                  <dd className="mono">{connection.phone_number_id}</dd>
                </div>
                <div>
                  <dt>Business App number</dt>
                  <dd>{connection.is_on_biz_app ? 'Yes (coexistence)' : 'Not reported'}</dd>
                </div>
                <div>
                  <dt>Quality rating</dt>
                  <dd>{connection.quality_rating || '—'}</dd>
                </div>
                <div>
                  <dt>Onboarded</dt>
                  <dd>{formatDate(connection.onboarded_at)}</dd>
                </div>
                <div>
                  <dt>Last webhook</dt>
                  <dd>{formatDate(connection.last_webhook_at)}</dd>
                </div>
              </dl>

              {connection.last_error && (
                <div className="wa-conn-inline-error">
                  <AlertTriangle size={15} /> {connection.last_error}
                </div>
              )}

              <div className="wa-conn-sync-block">
                <div className="wa-conn-sync-head">
                  <h3>
                    <Clock size={16} /> One-time synchronization
                  </h3>
                  {syncRemaining && (
                    <span className={syncRemaining === 'Window closed' ? 'bad' : ''}>
                      {syncRemaining}
                    </span>
                  )}
                </div>
                <p>
                  Meta requires contacts and message history to finish within the
                  sync window. If it does not, the number must be offboarded and
                  re-onboarded.
                </p>

                <div className="wa-conn-progress-row">
                  <div className="wa-conn-progress-label">
                    <span>History progress</span>
                    <strong>{connection.history_progress || 0}%</strong>
                  </div>
                  <div className="wa-conn-progress">
                    <div style={{ width: `${Math.min(100, connection.history_progress || 0)}%` }} />
                  </div>
                </div>

                <div className="wa-conn-sync-stats">
                  <div>
                    <Users size={16} />
                    <span>{connection.contacts_synced || 0}</span>
                    <small>contacts synced</small>
                  </div>
                  <div>
                    <MessageCircle size={16} />
                    <span>{connection.messages_synced || 0}</span>
                    <small>messages synced</small>
                  </div>
                  <div>
                    <Clock size={16} />
                    <span>
                      {connection.history_phase !== null && connection.history_phase !== undefined
                        ? connection.history_phase
                        : '—'}
                    </span>
                    <small>history phase</small>
                  </div>
                </div>

                <div className="wa-conn-sync-actions">
                  <button
                    type="button"
                    className="wa-conn-btn secondary"
                    disabled={contactSyncUsed || action === 'sync-contacts' || isReviewer}
                    onClick={() => handleSync('contacts')}
                    title={
                      contactSyncUsed
                        ? 'Meta allows one contact sync request per onboarding.'
                        : 'Ask Meta to synchronize Business App contacts.'
                    }
                  >
                    {action === 'sync-contacts' ? (
                      <Loader2 size={14} className="spin" />
                    ) : (
                      <Users size={14} />
                    )}
                    {contactSyncUsed ? 'Contacts sync requested' : 'Retry contacts sync'}
                  </button>
                  <button
                    type="button"
                    className="wa-conn-btn secondary"
                    disabled={historySyncUsed || action === 'sync-history' || isReviewer}
                    onClick={() => handleSync('history')}
                    title={
                      historySyncUsed
                        ? 'Meta allows one history sync request per onboarding.'
                        : 'Ask Meta to synchronize Business App history.'
                    }
                  >
                    {action === 'sync-history' ? (
                      <Loader2 size={14} className="spin" />
                    ) : (
                      <FileText size={14} />
                    )}
                    {historySyncUsed ? 'History sync requested' : 'Retry history sync'}
                  </button>
                </div>
              </div>
            </>
          )}
        </section>
      </div>

      <div className="wa-conn-grid two-col">
        <section className="wa-conn-card">
          <div className="wa-conn-card-head">
            <div>
              <h2>
                <Webhook size={18} /> Webhook
              </h2>
              <p>
                One Meta callback handles Click-to-WhatsApp leads and coexistence
                events. Subscription fields are configured in the Meta App Dashboard.
              </p>
            </div>
          </div>

          <div className="wa-conn-copy-row">
            <div>
              <span>Callback URL</span>
              <strong className="mono">{status?.webhook?.callback_url || config?.callback_url || '—'}</strong>
            </div>
            <button
              type="button"
              className="wa-conn-icon-btn"
              onClick={() =>
                copyText(
                  status?.webhook?.callback_url || config?.callback_url || '',
                  'Callback URL'
                )
              }
              disabled={!(status?.webhook?.callback_url || config?.callback_url)}
              title="Copy callback URL"
            >
              <Copy size={15} />
            </button>
          </div>

          <div className="wa-conn-field-list">
            <span>Required subscription fields</span>
            <div>
              {(status?.webhook?.expected_fields || []).map((field) => (
                <code key={field}>{field}</code>
              ))}
            </div>
          </div>

          <p className="wa-conn-muted">{status?.webhook?.note}</p>
        </section>

        <section className="wa-conn-card">
          <div className="wa-conn-card-head">
            <div>
              <h2>
                <KeyRound size={18} /> Configuration checklist
              </h2>
              <p>Non-secret values only. The app secret and business token never leave the backend.</p>
            </div>
          </div>
          <ul className="wa-conn-checklist">
            <li className={config?.enabled ? 'done' : 'pending'}>
              {config?.enabled ? <CheckCircle2 size={16} /> : <Lock size={16} />}
              <div>
                <strong>Onboarding gate</strong>
                <span>
                  {config?.enabled
                    ? 'WHATSAPP_COEXISTENCE_ENABLED=true'
                    : 'Locked (WHATSAPP_COEXISTENCE_ENABLED is not true)'}
                </span>
              </div>
            </li>
            <li className={config?.app_id ? 'done' : 'pending'}>
              {config?.app_id ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              <div>
                <strong>Meta app ID</strong>
                <span>{config?.app_id || 'Missing META_APP_ID'}</span>
              </div>
            </li>
            <li className={config?.config_id ? 'done' : 'pending'}>
              {config?.config_id ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              <div>
                <strong>Facebook Login for Business configuration</strong>
                <span>{config?.config_id || 'Missing WHATSAPP_COEXISTENCE_CONFIG_ID'}</span>
              </div>
            </li>
            <li className={connection?.webhook_subscribed ? 'done' : 'pending'}>
              {connection?.webhook_subscribed ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              <div>
                <strong>WABA subscription</strong>
                <span>
                  {connection?.webhook_subscribed
                    ? 'App is subscribed to the customer WABA'
                    : 'Completed automatically after a successful exchange'}
                </span>
              </div>
            </li>
            <li className="done">
              <ShieldCheck size={16} />
              <div>
                <strong>API version</strong>
                <span>{config?.api_version || status?.webhook?.api_version || '—'}</span>
              </div>
            </li>
          </ul>
        </section>
      </div>

      <section className="wa-conn-card">
        <div className="wa-conn-card-head">
          <div>
            <h2>
              <FileText size={18} /> Message templates
            </h2>
            <p>
              Templates are created on the connected WABA. Approval is handled by Meta
              and is required outside the 24-hour customer service window.
            </p>
          </div>
          <button
            type="button"
            className="wa-conn-btn secondary"
            onClick={() => setShowTemplateForm((open) => !open)}
            disabled={!connection}
          >
            <Plus size={15} /> New template
          </button>
        </div>

        {!connection ? (
          <p className="wa-conn-muted">Connect a number before creating templates.</p>
        ) : (
          <>
            {showTemplateForm && (
              <form className="wa-conn-template-form" onSubmit={handleCreateTemplate}>
                <div className="wa-conn-form-grid">
                  <label>
                    Name
                    <input
                      value={templateForm.name}
                      onChange={(event) =>
                        setTemplateForm((prev) => ({
                          ...prev,
                          name: event.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
                        }))
                      }
                      placeholder="order_update"
                      required
                    />
                  </label>
                  <label>
                    Language
                    <input
                      value={templateForm.language}
                      onChange={(event) =>
                        setTemplateForm((prev) => ({ ...prev, language: event.target.value }))
                      }
                      placeholder="en_US"
                      required
                    />
                  </label>
                  <label>
                    Category
                    <select
                      value={templateForm.category}
                      onChange={(event) =>
                        setTemplateForm((prev) => ({ ...prev, category: event.target.value }))
                      }
                    >
                      <option value="UTILITY">Utility</option>
                      <option value="MARKETING">Marketing</option>
                      <option value="AUTHENTICATION">Authentication</option>
                    </select>
                  </label>
                  <label>
                    Footer (optional)
                    <input
                      value={templateForm.footer_text}
                      onChange={(event) =>
                        setTemplateForm((prev) => ({ ...prev, footer_text: event.target.value }))
                      }
                      maxLength={60}
                      placeholder="Reply STOP to opt out"
                    />
                  </label>
                </div>
                <label className="wa-conn-full">
                  Body text
                  <textarea
                    value={templateForm.body_text}
                    onChange={(event) =>
                      setTemplateForm((prev) => ({ ...prev, body_text: event.target.value }))
                    }
                    rows={3}
                    placeholder="Hello {{1}}, your order {{2}} has been dispatched."
                    required
                  />
                </label>
                <div className="wa-conn-form-actions">
                  <button
                    type="button"
                    className="wa-conn-btn secondary"
                    onClick={() => setShowTemplateForm(false)}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="wa-conn-btn primary" disabled={action === 'template'}>
                    {action === 'template' ? <Loader2 size={15} className="spin" /> : <Plus size={15} />}
                    Submit to Meta
                  </button>
                </div>
              </form>
            )}

            {templates.length === 0 ? (
              <p className="wa-conn-muted">No templates returned by Meta yet.</p>
            ) : (
              <div className="wa-conn-table-wrap">
                <table className="wa-conn-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Category</th>
                      <th>Language</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {templates.map((template) => (
                      <tr key={template.id || `${template.name}-${template.language}`}>
                        <td className="mono">{template.name}</td>
                        <td>{template.category || '—'}</td>
                        <td>{template.language || '—'}</td>
                        <td>
                          <span className={`wa-conn-pill ${String(template.status || '').toLowerCase()}`}>
                            {template.status || 'UNKNOWN'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      <section className="wa-conn-card">
        <div className="wa-conn-card-head">
          <div>
            <h2>
              <Clock size={18} /> Recent coexistence events
            </h2>
            <p>Session logs and webhook processing, newest first. Tokens and codes are never stored here.</p>
          </div>
          <button type="button" className="wa-conn-btn secondary" onClick={fetchEvents}>
            <RefreshCw size={14} /> Reload
          </button>
        </div>

        {events.length === 0 ? (
          <p className="wa-conn-muted">No events recorded yet.</p>
        ) : (
          <div className="wa-conn-table-wrap">
            <table className="wa-conn-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>{formatDate(event.created_at)}</td>
                    <td>
                      <code>{event.event_type}</code>
                    </td>
                    <td>
                      <span className={`wa-conn-pill ${String(event.status || '').toLowerCase()}`}>
                        {event.status}
                      </span>
                    </td>
                    <td className="wrap">{event.detail || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="wa-conn-footer-note">
        <ShieldCheck size={16} />
        <span>
          Official Meta coexistence only. Companion devices, disappearing messages and
          view-once media are disabled by Meta while coexistence is active. Group chats
          and broadcast lists are not synchronized to Cloud API.
        </span>
      </div>
    </div>
  );
};

export default WhatsAppConnectionPage;
