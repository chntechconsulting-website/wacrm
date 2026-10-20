import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { 
  Settings as SettingsIcon, 
  Sliders, 
  Bell, 
  Key, 
  Globe, 
  Check, 
  Save,
  MessageCircle,
  Database,
  Mail,
  Share2,
  CheckCircle,
  AlertCircle,
  ExternalLink,
  HelpCircle,
  RefreshCw,
  Copy,
  PhoneCall,
  ShieldCheck,
  Terminal,
  Lock,
  Zap,
  Clock
} from 'lucide-react';
import IntegrationsPage from './IntegrationsPage';
import MetaIntegrationPage from './MetaIntegrationPage';

const SettingsPage = () => {
  const { user: currentUser } = useAuth();
  const [activeTab, setActiveTab] = useState('meta');
  const [saved, setSaved] = useState(false);
  const [metaStatus, setMetaStatus] = useState(null);
  const [loadingMeta, setLoadingMeta] = useState(false);
  const [copiedField, setCopiedField] = useState(null);

  // Auto-Assignment Configuration State
  const [autoAssignConfig, setAutoAssignConfig] = useState({
    enabled: true,
    waiting_time_minutes: 60,
    assignment_method: 'LEAST_ASSIGNED',
    eligible_roles: 'EMPLOYEE,MANAGER',
    working_hours_enabled: false,
    working_hours_start: '09:00',
    working_hours_end: '18:00'
  });
  const [loadingAutoConfig, setLoadingAutoConfig] = useState(false);
  const [savingAutoConfig, setSavingAutoConfig] = useState(false);
  const [autoConfigSuccess, setAutoConfigSuccess] = useState('');
  const [autoConfigError, setAutoConfigError] = useState('');

  const [generalSettings, setGeneralSettings] = useState({
    companyName: 'WaCRM Solutions Ltd',
    currency: 'INR (₹)',
    timezone: 'Asia/Kolkata (GMT+5:30)',
    dateFormat: 'DD/MM/YYYY',
    emailSender: 'support@wacrm.com'
  });

  const [leadSettings, setLeadSettings] = useState({
    autoAssign: true,
    defaultStatus: 'NEW LEAD',
    duplicateCheck: true,
    autoWhatsAppGreeting: true,
    leadScoreThreshold: '75'
  });

  const [apiSettings, setApiSettings] = useState({
    metaAppId: '1009988776655',
    metaAppSecret: '••••••••••••••••••••',
    metaVerifyToken: 'wacrm_meta_verify_secret',
    metaPageId: '1009988776655',
    whatsappApiKey: 'wa_live_sec_8892183921938',
    whatsappPhoneId: '10928392819',
    ivrEndpoint: '/api/ivr/call',
    smtpHost: 'smtp.gmail.com',
    smtpPort: '587'
  });

  const fetchMetaStatus = async () => {
    try {
      setLoadingMeta(true);
      const res = await API.get('/integrations/meta/status');
      if (res.data) setMetaStatus(res.data);
    } catch (e) {
      console.error("Failed to fetch Meta status:", e);
    } finally {
      setLoadingMeta(false);
    }
  };

  const fetchAutoAssignConfig = async () => {
    try {
      setLoadingAutoConfig(true);
      const res = await API.get('/leads/auto-assign/config');
      if (res.data) {
        setAutoAssignConfig(res.data);
      }
    } catch (e) {
      console.error("Failed to load auto assign config:", e);
    } finally {
      setLoadingAutoConfig(false);
    }
  };

  const handleSaveAutoAssignConfig = async (e) => {
    e.preventDefault();
    if (currentUser?.role !== 'ADMIN') {
      setAutoConfigError('Only System Administrators can modify Auto Lead Assignment settings.');
      return;
    }
    try {
      setSavingAutoConfig(true);
      setAutoConfigError('');
      setAutoConfigSuccess('');
      const res = await API.put('/leads/auto-assign/config', autoAssignConfig);
      if (res.data) {
        setAutoAssignConfig(res.data);
        setAutoConfigSuccess('Auto-assignment settings saved and applied to backend scheduler successfully!');
        setTimeout(() => setAutoConfigSuccess(''), 4000);
      }
    } catch (err) {
      console.error(err);
      setAutoConfigError(err.response?.data?.detail || 'Failed to update auto-assignment settings.');
    } finally {
      setSavingAutoConfig(false);
    }
  };

  useEffect(() => {
    fetchMetaStatus();
    fetchAutoAssignConfig();
  }, []);

  const handleSave = (e) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleCopy = (text, fieldName) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const webhookCallbackUrl = `${window.location.origin}/api/integrations/meta/webhook`;

  return (
    <div className="page-container" style={{ maxWidth: '1000px', margin: '0 auto', paddingBottom: '40px' }}>
      {/* Page Header */}
      <div className="page-header" style={{ marginBottom: '24px' }}>
        <div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
            <Link to="/dashboard" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Dashboard</Link> / {' '}
            <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>Settings</span>
          </div>
          <h1 className="page-title" style={{ fontSize: '1.65rem', fontWeight: '800', margin: 0 }}>CRM System Settings</h1>
          <p className="page-subtitle" style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Manage organization preferences, Meta Lead Ads webhook integration, lead distribution rules, and API keys.
          </p>
        </div>
      </div>

      {saved && (
        <div className="alert alert-success" style={{ backgroundColor: 'var(--success-light)', color: 'var(--success)', border: '1px solid rgba(16,185,129,0.3)', padding: '12px 16px', borderRadius: '10px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Check size={18} />
          <span style={{ fontWeight: '600' }}>System settings updated successfully!</span>
        </div>
      )}

      {/* Segmented Tab Pill Navigation Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        backgroundColor: '#ffffff',
        padding: '6px',
        borderRadius: '16px',
        border: '1px solid #e2e8f0',
        marginBottom: '24px',
        boxShadow: '0 2px 8px rgba(15, 23, 42, 0.04)',
        overflowX: 'auto',
        scrollbarWidth: 'thin'
      }}>
        <button 
          type="button"
          onClick={() => setActiveTab('integrations')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 18px',
            borderRadius: '12px',
            border: 'none',
            backgroundColor: activeTab === 'integrations' ? '#2563eb' : 'transparent',
            color: activeTab === 'integrations' ? '#ffffff' : '#64748b',
            fontWeight: '700',
            fontSize: '0.86rem',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            boxShadow: activeTab === 'integrations' ? '0 4px 12px rgba(37, 99, 235, 0.25)' : 'none',
            transition: 'all 0.2s ease'
          }}
        >
          <Sliders size={17} /> Integration Hub
        </button>

        <button 
          type="button"
          onClick={() => setActiveTab('meta')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 18px',
            borderRadius: '12px',
            border: 'none',
            backgroundColor: activeTab === 'meta' ? '#2563eb' : 'transparent',
            color: activeTab === 'meta' ? '#ffffff' : '#64748b',
            fontWeight: '700',
            fontSize: '0.86rem',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            boxShadow: activeTab === 'meta' ? '0 4px 12px rgba(37, 99, 235, 0.25)' : 'none',
            transition: 'all 0.2s ease'
          }}
        >
          <Share2 size={17} /> Meta Lead Ads
        </button>

        <button 
          type="button"
          onClick={() => setActiveTab('general')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 18px',
            borderRadius: '12px',
            border: 'none',
            backgroundColor: activeTab === 'general' ? '#2563eb' : 'transparent',
            color: activeTab === 'general' ? '#ffffff' : '#64748b',
            fontWeight: '700',
            fontSize: '0.86rem',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            boxShadow: activeTab === 'general' ? '0 4px 12px rgba(37, 99, 235, 0.25)' : 'none',
            transition: 'all 0.2s ease'
          }}
        >
          <Globe size={17} /> General Preferences
        </button>

        <button 
          type="button"
          onClick={() => setActiveTab('leads')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 18px',
            borderRadius: '12px',
            border: 'none',
            backgroundColor: activeTab === 'leads' ? '#2563eb' : 'transparent',
            color: activeTab === 'leads' ? '#ffffff' : '#64748b',
            fontWeight: '700',
            fontSize: '0.86rem',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            boxShadow: activeTab === 'leads' ? '0 4px 12px rgba(37, 99, 235, 0.25)' : 'none',
            transition: 'all 0.2s ease'
          }}
        >
          <Sliders size={17} /> Lead & Assignment Rules
        </button>

        <button 
          type="button"
          onClick={() => setActiveTab('api')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 18px',
            borderRadius: '12px',
            border: 'none',
            backgroundColor: activeTab === 'api' ? '#2563eb' : 'transparent',
            color: activeTab === 'api' ? '#ffffff' : '#64748b',
            fontWeight: '700',
            fontSize: '0.86rem',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            boxShadow: activeTab === 'api' ? '0 4px 12px rgba(37, 99, 235, 0.25)' : 'none',
            transition: 'all 0.2s ease'
          }}
        >
          <Key size={17} /> API Credentials
        </button>
      </div>

      {/* TAB: INTEGRATION HUB */}
      {activeTab === 'integrations' && (
        <div style={{ width: '100%' }}>
          <IntegrationsPage />
        </div>
      )}

      {/* TAB 1: META LEAD ADS INTEGRATION */}
      {activeTab === 'meta' && (
        <div style={{ width: '100%' }}>
          <MetaIntegrationPage />
        </div>
      )}
      {false && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', width: '100%' }}>
          {/* Status Banner Card */}
          <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '14px', background: 'linear-gradient(135deg, #2563eb, #1d4ed8)', color: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 12px rgba(37, 99, 235, 0.25)' }}>
                  <Share2 size={24} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>Meta Lead Ads Integration</h3>
                  <p style={{ fontSize: '0.85rem', color: '#64748b', margin: '2px 0 0 0', fontWeight: 500 }}>
                    Automatic real-time lead ingestion from Facebook & Instagram lead ad forms.
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 14px',
                  borderRadius: '20px',
                  fontSize: '0.78rem',
                  fontWeight: '800',
                  backgroundColor: metaStatus?.configured ? '#d1fae5' : '#fef3c7',
                  color: metaStatus?.configured ? '#047857' : '#d97706',
                  border: metaStatus?.configured ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(217, 119, 6, 0.3)'
                }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: metaStatus?.configured ? '#10b981' : '#f59e0b' }} />
                  {metaStatus?.configured ? 'CONNECTED & ACTIVE' : 'PENDING CONFIGURATION'}
                </span>

                <button 
                  onClick={fetchMetaStatus} 
                  className="btn btn-outline" 
                  style={{ padding: '8px 14px', borderRadius: '10px', fontSize: '0.82rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '6px' }}
                  title="Refresh Meta Webhook Status"
                >
                  <RefreshCw size={15} className={loadingMeta ? 'spin' : ''} />
                  <span>Refresh</span>
                </button>
              </div>
            </div>

            {/* Metrics Breakdown Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', marginTop: '20px' }}>
              <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600', display: 'block' }}>Facebook Page ID</span>
                <span style={{ fontSize: '0.95rem', fontWeight: '800', color: '#0f172a', marginTop: '2px', display: 'block' }}>{metaStatus?.page_id || '1009988776655'}</span>
              </div>
              <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600', display: 'block' }}>Graph API Version</span>
                <span style={{ fontSize: '0.95rem', fontWeight: '800', color: '#2563eb', marginTop: '2px', display: 'block' }}>{metaStatus?.api_version || 'v20.0'}</span>
              </div>
              <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600', display: 'block' }}>Total Meta Leads</span>
                <span style={{ fontSize: '1.2rem', fontWeight: '800', color: '#059669', marginTop: '2px', display: 'block' }}>{metaStatus?.total_meta_leads || 2}</span>
              </div>
              <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '600', display: 'block' }}>Last Webhook Activity</span>
                <span style={{ fontSize: '0.82rem', fontWeight: '700', color: '#0f172a', marginTop: '4px', display: 'block' }}>
                  {metaStatus?.last_webhook_received ? new Date(metaStatus.last_webhook_received).toLocaleString() : 'Active & Listening'}
                </span>
              </div>
            </div>
          </div>

          {/* Webhook Endpoint & Verify Token Card */}
          <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Zap size={20} style={{ color: '#2563eb' }} />
              Webhook Connection Details
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))', gap: '16px' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label style={{ fontSize: '0.82rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>Webhook Callback URL</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input 
                    type="text" 
                    readOnly 
                    value={webhookCallbackUrl}
                    style={{ backgroundColor: '#f8fafc', fontWeight: '600', color: '#0f172a', fontSize: '0.84rem' }}
                  />
                  <button 
                    type="button" 
                    onClick={() => handleCopy(webhookCallbackUrl, 'url')}
                    className="btn btn-outline"
                    style={{ padding: '8px 14px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem' }}
                  >
                    {copiedField === 'url' ? <Check size={16} style={{ color: '#10b981' }} /> : <Copy size={16} />}
                    <span>{copiedField === 'url' ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label style={{ fontSize: '0.82rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>Verify Token (META_VERIFY_TOKEN)</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input 
                    type="text" 
                    readOnly 
                    value={apiSettings.metaVerifyToken}
                    style={{ backgroundColor: '#f8fafc', fontWeight: '600', color: '#0f172a', fontSize: '0.84rem' }}
                  />
                  <button 
                    type="button" 
                    onClick={() => handleCopy(apiSettings.metaVerifyToken, 'token')}
                    className="btn btn-outline"
                    style={{ padding: '8px 14px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem' }}
                  >
                    {copiedField === 'token' ? <Check size={16} style={{ color: '#10b981' }} /> : <Copy size={16} />}
                    <span>{copiedField === 'token' ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Setup Instructions Card */}
          <div className="content-card" style={{ borderRadius: '18px', padding: '24px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <HelpCircle size={20} style={{ color: '#2563eb' }} />
              Step-by-Step Meta Lead Ads Integration Setup Guide
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                  <span style={{ width: '24px', height: '24px', borderRadius: '50%', backgroundColor: '#2563eb', color: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.78rem', fontWeight: '800' }}>1</span>
                  <strong style={{ color: '#0f172a', fontSize: '0.92rem' }}>Step 1: Set Environment Variables in backend/.env</strong>
                </div>
                <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '4px 0 10px 34px' }}>
                  Add your Meta app credentials to <code>backend/.env</code> on your FastAPI server:
                </p>
                <div style={{ marginLeft: '34px' }}>
                  <pre style={{ backgroundColor: '#0f172a', color: '#38bdf8', padding: '14px 16px', borderRadius: '10px', fontSize: '0.82rem', fontFamily: 'monospace', overflowX: 'auto', margin: 0, border: '1px solid #1e293b' }}>
{`META_APP_ID=1009988776655
META_APP_SECRET=your_meta_app_secret
META_ACCESS_TOKEN=EAABb... (Long-Lived Page Access Token)
META_VERIFY_TOKEN=wacrm_meta_verify_secret
META_PAGE_ID=1009988776655
META_API_VERSION=v20.0`}
                  </pre>
                </div>
              </div>

              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                  <span style={{ width: '24px', height: '24px', borderRadius: '50%', backgroundColor: '#2563eb', color: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.78rem', fontWeight: '800' }}>2</span>
                  <strong style={{ color: '#0f172a', fontSize: '0.92rem' }}>Step 2: Configure Webhooks in Meta Developer App</strong>
                </div>
                <ol style={{ paddingLeft: '54px', margin: '6px 0 0 0', fontSize: '0.84rem', color: '#475569', lineHeight: '1.6' }}>
                  <li>Open <strong>Meta Developer Dashboard</strong> &rarr; Add <strong>Webhooks</strong> product to your app.</li>
                  <li>Select <strong>Page</strong> object from the dropdown &rarr; Click <strong>Subscribe to this object</strong>.</li>
                  <li>Paste Callback URL: <code>{webhookCallbackUrl}</code></li>
                  <li>Paste Verify Token: <code>wacrm_meta_verify_secret</code></li>
                  <li>Subscribe to the <strong>leadgen</strong> field event.</li>
                </ol>
              </div>

              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', alignItems: 'center', justify: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ width: '24px', height: '24px', borderRadius: '50%', backgroundColor: '#2563eb', color: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.78rem', fontWeight: '800' }}>3</span>
                    <div>
                      <strong style={{ color: '#0f172a', fontSize: '0.92rem' }}>Step 3: Generate Test Leads with Meta Testing Tool</strong>
                      <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '2px 0 0 0' }}>
                        Use Meta's official Lead Ads Testing tool to send live test webhooks directly into your CRM.
                      </p>
                    </div>
                  </div>

                  <a 
                    href="https://developers.facebook.com/tools/lead-ads-testing/" 
                    target="_blank" 
                    rel="noreferrer" 
                    className="btn btn-outline"
                    style={{ padding: '8px 14px', fontSize: '0.82rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '6px', color: '#2563eb', borderColor: '#bfdbfe' }}
                  >
                    <span>Open Meta Lead Testing Tool</span>
                    <ExternalLink size={15} />
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: GENERAL PREFERENCES */}
      {activeTab === 'general' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '28px', width: '100%' }}>
          <form onSubmit={handleSave}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Globe size={20} style={{ color: '#2563eb' }} /> Organization Preferences & Regional Settings
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>Organization / Company Title</label>
                <input 
                  type="text" 
                  value={generalSettings.companyName}
                  onChange={(e) => setGeneralSettings({ ...generalSettings, companyName: e.target.value })}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
                <div className="form-group" style={{ margin: 0 }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>Default Currency</label>
                  <select 
                    value={generalSettings.currency}
                    onChange={(e) => setGeneralSettings({ ...generalSettings, currency: e.target.value })}
                  >
                    <option value="INR (₹)">INR (₹) - Indian Rupee</option>
                    <option value="USD ($)">USD ($) - US Dollar</option>
                    <option value="EUR (€)">EUR (€) - Euro</option>
                  </select>
                </div>

                <div className="form-group" style={{ margin: 0 }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>System Timezone</label>
                  <input 
                    type="text" 
                    value={generalSettings.timezone}
                    onChange={(e) => setGeneralSettings({ ...generalSettings, timezone: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
                <div className="form-group" style={{ margin: 0 }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>Date Format</label>
                  <select 
                    value={generalSettings.dateFormat}
                    onChange={(e) => setGeneralSettings({ ...generalSettings, dateFormat: e.target.value })}
                  >
                    <option value="DD/MM/YYYY">DD/MM/YYYY (e.g. 25/09/2026)</option>
                    <option value="MM/DD/YYYY">MM/DD/YYYY (e.g. 09/25/2026)</option>
                    <option value="YYYY-MM-DD">YYYY-MM-DD (e.g. 2026-09-25)</option>
                  </select>
                </div>

                <div className="form-group" style={{ margin: 0 }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>Default Email Sender Address</label>
                  <input 
                    type="email" 
                    value={generalSettings.emailSender}
                    onChange={(e) => setGeneralSettings({ ...generalSettings, emailSender: e.target.value })}
                  />
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '28px', paddingTop: '18px', borderTop: '1px solid #e2e8f0' }}>
              <button type="submit" className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Save size={18} />
                <span>Save General Settings</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* TAB 3: LEAD & ASSIGNMENT RULES */}
      {activeTab === 'leads' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '28px', width: '100%' }}>
          <form onSubmit={handleSaveAutoAssignConfig}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Clock size={22} style={{ color: '#2563eb' }} /> Auto Lead Assignment Settings
              </h3>
              <span style={{ 
                fontSize: '0.78rem', 
                padding: '4px 12px', 
                borderRadius: '12px', 
                backgroundColor: currentUser?.role === 'ADMIN' ? '#dcfce7' : '#f1f5f9', 
                color: currentUser?.role === 'ADMIN' ? '#15803d' : '#64748b', 
                fontWeight: '700' 
              }}>
                {currentUser?.role === 'ADMIN' ? 'ADMIN CONFIGURATION' : 'VIEW ONLY (ADMIN ROLE REQUIRED)'}
              </span>
            </div>

            <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '24px' }}>
              Configure automatic lead assignment timing, distribution strategy, team eligibility, and working hours constraints. Settings are stored in the database and applied dynamically to the background engine.
            </p>

            {autoConfigSuccess && (
              <div className="alert alert-success" style={{ backgroundColor: '#dcfce7', color: '#15803d', padding: '12px 16px', borderRadius: '10px', marginBottom: '20px', fontSize: '0.88rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Check size={18} />
                <span>{autoConfigSuccess}</span>
              </div>
            )}

            {autoConfigError && (
              <div className="alert alert-danger" style={{ backgroundColor: '#fee2e2', color: '#991b1b', padding: '12px 16px', borderRadius: '10px', marginBottom: '20px', fontSize: '0.88rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertCircle size={18} />
                <span>{autoConfigError}</span>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* 1. ENABLE / DISABLE TOGGLE */}
              <div style={{ background: '#f8fafc', padding: '18px', borderRadius: '14px', border: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '0.95rem', color: '#0f172a' }}>Auto Assignment Status</strong>
                  <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '3px 0 0 0' }}>Enable or disable background automatic lead distribution for unassigned leads.</p>
                </div>
                <label style={{ display: 'inline-flex', alignItems: 'center', cursor: currentUser?.role === 'ADMIN' ? 'pointer' : 'not-allowed', gap: '8px' }}>
                  <input 
                    type="checkbox" 
                    disabled={currentUser?.role !== 'ADMIN'}
                    checked={autoAssignConfig.enabled}
                    onChange={(e) => setAutoAssignConfig({ ...autoAssignConfig, enabled: e.target.checked })}
                    style={{ width: '22px', height: '22px', accentColor: '#2563eb' }}
                  />
                  <span style={{ fontWeight: '700', fontSize: '0.9rem', color: autoAssignConfig.enabled ? '#16a34a' : '#dc2626' }}>
                    {autoAssignConfig.enabled ? 'ENABLED' : 'DISABLED'}
                  </span>
                </label>
              </div>

              {/* 2. WAITING TIME CONFIGURATION */}
              <div style={{ background: '#f8fafc', padding: '18px', borderRadius: '14px', border: '1px solid #e2e8f0' }}>
                <label style={{ fontSize: '0.92rem', fontWeight: '700', color: '#0f172a', marginBottom: '4px', display: 'block' }}>
                  Unassigned Lead Waiting Time (Timeout before Auto-Assignment)
                </label>
                <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '0 0 14px 0' }}>
                  Duration a lead remains unassigned for Managers/Admins before the background scheduler automatically assigns it.
                </p>

                {/* Preset Duration Selector Buttons */}
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
                  {[
                    { label: '15 Mins', value: 15 },
                    { label: '30 Mins', value: 30 },
                    { label: '45 Mins', value: 45 },
                    { label: '1 Hour (60m)', value: 60 },
                    { label: '2 Hours (120m)', value: 120 },
                    { label: '4 Hours (240m)', value: 240 },
                  ].map(opt => (
                    <button
                      key={opt.value}
                      type="button"
                      disabled={currentUser?.role !== 'ADMIN'}
                      onClick={() => setAutoAssignConfig({ ...autoAssignConfig, waiting_time_minutes: opt.value })}
                      style={{
                        padding: '7px 16px',
                        borderRadius: '8px',
                        border: '1px solid',
                        borderColor: autoAssignConfig.waiting_time_minutes === opt.value ? '#2563eb' : '#cbd5e1',
                        backgroundColor: autoAssignConfig.waiting_time_minutes === opt.value ? '#2563eb' : '#ffffff',
                        color: autoAssignConfig.waiting_time_minutes === opt.value ? '#ffffff' : '#334155',
                        fontWeight: '700',
                        fontSize: '0.82rem',
                        cursor: currentUser?.role === 'ADMIN' ? 'pointer' : 'not-allowed',
                        transition: 'all 0.15s'
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>

                {/* Custom Input */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', maxWidth: '320px' }}>
                  <span style={{ fontSize: '0.85rem', color: '#475569', fontWeight: 600 }}>Custom Waiting Time:</span>
                  <input 
                    type="number" 
                    min="1"
                    max="10080"
                    disabled={currentUser?.role !== 'ADMIN'}
                    value={autoAssignConfig.waiting_time_minutes}
                    onChange={(e) => setAutoAssignConfig({ ...autoAssignConfig, waiting_time_minutes: parseInt(e.target.value) || 1 })}
                    style={{ width: '100px', fontWeight: '700', textAlign: 'center' }}
                  />
                  <span style={{ fontSize: '0.85rem', color: '#64748b' }}>Minutes</span>
                </div>
              </div>

              {/* 3. ASSIGNMENT METHOD */}
              <div style={{ background: '#f8fafc', padding: '18px', borderRadius: '14px', border: '1px solid #e2e8f0' }}>
                <label style={{ fontSize: '0.92rem', fontWeight: '700', color: '#0f172a', marginBottom: '4px', display: 'block' }}>
                  Auto-Assignment Strategy / Method
                </label>
                <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '0 0 14px 0' }}>
                  Select the algorithm used by the background scheduler to choose the target employee.
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
                  {[
                    { id: 'LEAST_ASSIGNED', title: 'Least Assigned (Workload Balancing)', desc: 'Assigns to the eligible employee with fewest active leads.' },
                    { id: 'ROUND_ROBIN', title: 'Round Robin (Sequential)', desc: 'Assigns strictly in turn based on least recent assignment.' },
                    { id: 'HIERARCHICAL', title: 'Hierarchical (Role Rank Priority)', desc: 'Prioritizes Sales Representatives first, then Managers.' },
                  ].map(m => (
                    <div 
                      key={m.id}
                      onClick={() => currentUser?.role === 'ADMIN' && setAutoAssignConfig({ ...autoAssignConfig, assignment_method: m.id })}
                      style={{
                        border: `2px solid ${autoAssignConfig.assignment_method === m.id ? '#2563eb' : '#e2e8f0'}`,
                        backgroundColor: autoAssignConfig.assignment_method === m.id ? '#eff6ff' : '#ffffff',
                        borderRadius: '10px',
                        padding: '14px',
                        cursor: currentUser?.role === 'ADMIN' ? 'pointer' : 'not-allowed',
                        transition: 'all 0.15s'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <input 
                          type="radio" 
                          name="assignment_method"
                          disabled={currentUser?.role !== 'ADMIN'}
                          checked={autoAssignConfig.assignment_method === m.id}
                          onChange={() => setAutoAssignConfig({ ...autoAssignConfig, assignment_method: m.id })}
                          style={{ accentColor: '#2563eb' }}
                        />
                        <strong style={{ fontSize: '0.88rem', color: '#0f172a' }}>{m.title}</strong>
                      </div>
                      <p style={{ fontSize: '0.78rem', color: '#64748b', margin: 0, paddingLeft: '24px' }}>{m.desc}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* 4. ELIGIBLE ROLES / TEAMS */}
              <div style={{ background: '#f8fafc', padding: '18px', borderRadius: '14px', border: '1px solid #e2e8f0' }}>
                <label style={{ fontSize: '0.92rem', fontWeight: '700', color: '#0f172a', marginBottom: '4px', display: 'block' }}>
                  Eligible Employee Roles & Teams
                </label>
                <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '0 0 14px 0' }}>
                  Select which active team roles are eligible to receive auto-assigned leads.
                </p>

                <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: currentUser?.role === 'ADMIN' ? 'pointer' : 'not-allowed', fontSize: '0.88rem', fontWeight: 600 }}>
                    <input 
                      type="checkbox"
                      disabled={currentUser?.role !== 'ADMIN'}
                      checked={autoAssignConfig.eligible_roles.includes('EMPLOYEE')}
                      onChange={(e) => {
                        let roles = autoAssignConfig.eligible_roles.split(',').map(r => r.trim()).filter(Boolean);
                        if (e.target.checked) {
                          if (!roles.includes('EMPLOYEE')) roles.push('EMPLOYEE');
                        } else {
                          roles = roles.filter(r => r !== 'EMPLOYEE');
                        }
                        setAutoAssignConfig({ ...autoAssignConfig, eligible_roles: roles.join(',') });
                      }}
                      style={{ width: '18px', height: '18px', accentColor: '#2563eb' }}
                    />
                    Sales Representatives (EMPLOYEE)
                  </label>

                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: currentUser?.role === 'ADMIN' ? 'pointer' : 'not-allowed', fontSize: '0.88rem', fontWeight: 600 }}>
                    <input 
                      type="checkbox"
                      disabled={currentUser?.role !== 'ADMIN'}
                      checked={autoAssignConfig.eligible_roles.includes('MANAGER')}
                      onChange={(e) => {
                        let roles = autoAssignConfig.eligible_roles.split(',').map(r => r.trim()).filter(Boolean);
                        if (e.target.checked) {
                          if (!roles.includes('MANAGER')) roles.push('MANAGER');
                        } else {
                          roles = roles.filter(r => r !== 'MANAGER');
                        }
                        setAutoAssignConfig({ ...autoAssignConfig, eligible_roles: roles.join(',') });
                      }}
                      style={{ width: '18px', height: '18px', accentColor: '#2563eb' }}
                    />
                    Team Managers (MANAGER)
                  </label>
                </div>
              </div>

              {/* 5. WORKING HOURS CONSTRAINT */}
              <div style={{ background: '#f8fafc', padding: '18px', borderRadius: '14px', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div>
                    <strong style={{ fontSize: '0.92rem', color: '#0f172a' }}>Working Hours Constraint (Optional)</strong>
                    <p style={{ fontSize: '0.82rem', color: '#64748b', margin: '2px 0 0 0' }}>Limit auto-assignment execution strictly during company office hours.</p>
                  </div>
                  <input 
                    type="checkbox" 
                    disabled={currentUser?.role !== 'ADMIN'}
                    checked={autoAssignConfig.working_hours_enabled}
                    onChange={(e) => setAutoAssignConfig({ ...autoAssignConfig, working_hours_enabled: e.target.checked })}
                    style={{ width: '20px', height: '20px', accentColor: '#2563eb', cursor: currentUser?.role === 'ADMIN' ? 'pointer' : 'not-allowed' }}
                  />
                </div>

                {autoAssignConfig.working_hours_enabled && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '14px', paddingTop: '14px', borderTop: '1px dashed #cbd5e1' }}>
                    <div>
                      <label style={{ fontSize: '0.82rem', fontWeight: '700', color: '#475569', marginBottom: '4px', display: 'block' }}>Working Hours Start Time</label>
                      <input 
                        type="time" 
                        disabled={currentUser?.role !== 'ADMIN'}
                        value={autoAssignConfig.working_hours_start}
                        onChange={(e) => setAutoAssignConfig({ ...autoAssignConfig, working_hours_start: e.target.value })}
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '0.82rem', fontWeight: '700', color: '#475569', marginBottom: '4px', display: 'block' }}>Working Hours End Time</label>
                      <input 
                        type="time" 
                        disabled={currentUser?.role !== 'ADMIN'}
                        value={autoAssignConfig.working_hours_end}
                        onChange={(e) => setAutoAssignConfig({ ...autoAssignConfig, working_hours_end: e.target.value })}
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '28px', paddingTop: '18px', borderTop: '1px solid #e2e8f0' }}>
              <button 
                type="submit" 
                className="btn btn-primary" 
                disabled={currentUser?.role !== 'ADMIN' || savingAutoConfig}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px', 
                  backgroundColor: currentUser?.role === 'ADMIN' ? '#2563eb' : '#94a3b8', 
                  cursor: currentUser?.role === 'ADMIN' ? 'pointer' : 'not-allowed' 
                }}
              >
                <Save size={18} />
                <span>{savingAutoConfig ? 'Saving Settings...' : 'Save Auto-Assign Settings'}</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* TAB 4: API & INTEGRATIONS */}
      {activeTab === 'api' && (
        <div className="content-card" style={{ borderRadius: '18px', padding: '28px', width: '100%' }}>
          <form onSubmit={handleSave}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Key size={20} style={{ color: '#2563eb' }} /> Third-Party API Credentials & Endpoints
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* WhatsApp API Section */}
              <div style={{ background: '#f8fafc', padding: '18px', borderRadius: '14px', border: '1px solid #e2e8f0' }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: '700', color: '#0f172a', margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <MessageCircle size={18} style={{ color: '#25d366' }} /> WhatsApp Business Cloud API
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '14px' }}>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label style={{ fontSize: '0.82rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>WhatsApp Access Token</label>
                    <input 
                      type="password" 
                      value={apiSettings.whatsappApiKey}
                      onChange={(e) => setApiSettings({ ...apiSettings, whatsappApiKey: e.target.value })}
                    />
                  </div>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label style={{ fontSize: '0.82rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>Phone Number ID</label>
                    <input 
                      type="text" 
                      value={apiSettings.whatsappPhoneId}
                      onChange={(e) => setApiSettings({ ...apiSettings, whatsappPhoneId: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              {/* IVR Section */}
              <div style={{ background: '#f8fafc', padding: '18px', borderRadius: '14px', border: '1px solid #e2e8f0' }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: '700', color: '#0f172a', margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <PhoneCall size={18} style={{ color: '#2563eb' }} /> Click-to-Call IVR Provider Endpoint
                </h4>
                <div className="form-group" style={{ margin: 0 }}>
                  <label style={{ fontSize: '0.82rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>FastAPI Backend Endpoint</label>
                  <input 
                    type="text" 
                    value={apiSettings.ivrEndpoint}
                    onChange={(e) => setApiSettings({ ...apiSettings, ivrEndpoint: e.target.value })}
                  />
                </div>
              </div>

              {/* SMTP Email Server */}
              <div style={{ background: '#f8fafc', padding: '18px', borderRadius: '14px', border: '1px solid #e2e8f0' }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: '700', color: '#0f172a', margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Mail size={18} style={{ color: '#f59e0b' }} /> SMTP Email Delivery Server
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label style={{ fontSize: '0.82rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>SMTP Host</label>
                    <input 
                      type="text" 
                      value={apiSettings.smtpHost}
                      onChange={(e) => setApiSettings({ ...apiSettings, smtpHost: e.target.value })}
                    />
                  </div>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label style={{ fontSize: '0.82rem', fontWeight: '700', color: '#475569', marginBottom: '6px' }}>SMTP Port</label>
                    <input 
                      type="text" 
                      value={apiSettings.smtpPort}
                      onChange={(e) => setApiSettings({ ...apiSettings, smtpPort: e.target.value })}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '28px', paddingTop: '18px', borderTop: '1px solid #e2e8f0' }}>
              <button type="submit" className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Save size={18} />
                <span>Save API Credentials</span>
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default SettingsPage;
