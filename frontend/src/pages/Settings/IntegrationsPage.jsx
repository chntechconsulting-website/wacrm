import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import { 
  Share2, 
  MessageCircle, 
  PhoneCall, 
  Globe, 
  Sliders, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  RefreshCw, 
  Eye, 
  EyeOff, 
  Copy, 
  Check, 
  Key, 
  ShieldCheck, 
  Terminal, 
  ExternalLink,
  X,
  Play,
  Power,
  Settings,
  FileCode,
  Zap,
  FileText,
  Plus,
  Trash2,
  Layers
} from 'lucide-react';
import './IntegrationsPage.css';

const INTEGRATION_ICONS = {
  META: { icon: Share2, className: 'meta' },
  WHATSAPP: { icon: MessageCircle, className: 'whatsapp' },
  IVR: { icon: PhoneCall, className: 'ivr' },
  WEBSITE: { icon: Globe, className: 'website' }
};

const IntegrationsPage = () => {
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [testingType, setTestingType] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);
  
  // Toast state
  const [toast, setToast] = useState(null);

  // Configure Modal State
  const [modalState, setModalState] = useState({
    isOpen: false,
    type: null,
    config: {}
  });
  const [showSecrets, setShowSecrets] = useState({});
  const [savingConfig, setSavingConfig] = useState(false);
  const [copiedField, setCopiedField] = useState(null);

  // Audit Logs state
  const [logs, setLogs] = useState([]);
  const [logFilter, setLogFilter] = useState('ALL');
  const [loadingLogs, setLoadingLogs] = useState(false);

  // Multi-Page Meta State
  const [metaPages, setMetaPages] = useState([]);
  const [loadingPages, setLoadingPages] = useState(false);
  const [pageActionLoading, setPageActionLoading] = useState({});
  const [addPageModalOpen, setAddPageModalOpen] = useState(false);
  const [newPageData, setNewPageData] = useState({ page_id: '', page_name: '', access_token: '' });
  const [addingPage, setAddingPage] = useState(false);
  const [refreshPageModal, setRefreshPageModal] = useState({ isOpen: false, page: null, newAccessToken: '' });
  const [refreshingPage, setRefreshingPage] = useState(false);

  // Initial Data Fetch
  const fetchStatus = async () => {
    try {
      setLoading(true);
      const res = await API.get('/integrations/hub/status');
      setIntegrations(res.data || []);
    } catch (err) {
      showToast('error', 'Failed to fetch integration hub status: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const fetchMetaPages = async () => {
    try {
      setLoadingPages(true);
      const res = await API.get('/integrations/meta/pages');
      setMetaPages(res.data || []);
    } catch (err) {
      console.error('Failed to fetch Meta pages:', err);
    } finally {
      setLoadingPages(false);
    }
  };

  const fetchLogs = async () => {
    try {
      setLoadingLogs(true);
      const res = await API.get('/integrations/hub/logs');
      setLogs(res.data || []);
    } catch (err) {
      console.error('Failed to fetch integration logs:', err);
    } finally {
      setLoadingLogs(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchLogs();
    fetchMetaPages();
  }, []);

  // Multi-Page Handlers
  const handleConnectNewPage = async (e) => {
    e.preventDefault();
    if (!newPageData.page_id || !newPageData.access_token) {
      showToast('error', 'Page ID and Page Access Token are required.');
      return;
    }
    try {
      setAddingPage(true);
      const res = await API.post('/integrations/meta/pages', newPageData);
      if (res.data.success) {
        showToast('success', res.data.message || 'Facebook Page connected successfully!');
      } else {
        showToast('error', `${res.data.message} ${res.data.error_details ? '(' + res.data.error_details + ')' : ''}`);
      }
      setAddPageModalOpen(false);
      setNewPageData({ page_id: '', page_name: '', access_token: '' });
      fetchMetaPages();
      fetchStatus();
      fetchLogs();
    } catch (err) {
      showToast('error', 'Failed to connect Page: ' + (err.response?.data?.detail || err.message));
    } finally {
      setAddingPage(false);
    }
  };

  const handleSyncMetaPage = async (pageId) => {
    try {
      setPageActionLoading(prev => ({ ...prev, [pageId]: 'sync' }));
      const res = await API.post(`/integrations/meta/pages/${pageId}/sync`);
      if (res.data.success) {
        showToast('success', res.data.message);
      } else {
        showToast('error', `${res.data.message} ${res.data.error_details ? '(' + res.data.error_details + ')' : ''}`);
      }
      fetchMetaPages();
      fetchLogs();
    } catch (err) {
      showToast('error', 'Page sync failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setPageActionLoading(prev => ({ ...prev, [pageId]: null }));
    }
  };

  const handleToggleMetaPageStatus = async (page) => {
    const isConnected = page.status === 'CONNECTED';
    const action = isConnected ? 'disconnect' : 'connect';
    try {
      setPageActionLoading(prev => ({ ...prev, [page.page_id]: action }));
      await API.post(`/integrations/meta/pages/${page.page_id}/${action}`);
      showToast('success', `Page '${page.page_name}' ${isConnected ? 'disconnected' : 'connected'}.`);
      fetchMetaPages();
      fetchLogs();
    } catch (err) {
      showToast('error', `Failed to ${action} page: ` + (err.response?.data?.detail || err.message));
    } finally {
      setPageActionLoading(prev => ({ ...prev, [page.page_id]: null }));
    }
  };

  const openRefreshPageModal = (page) => {
    setShowSecrets({});
    setRefreshPageModal({
      isOpen: true,
      page,
      newAccessToken: ''
    });
  };

  const handleRefreshMetaPage = async (e) => {
    e.preventDefault();
    if (!refreshPageModal.newAccessToken) {
      showToast('error', 'Please provide the new Page Access Token.');
      return;
    }
    try {
      setRefreshingPage(true);
      const res = await API.post(`/integrations/meta/pages/${refreshPageModal.page.page_id}/refresh`, {
        access_token: refreshPageModal.newAccessToken
      });
      if (res.data.success) {
        showToast('success', res.data.message);
      } else {
        showToast('error', `${res.data.message} ${res.data.error_details ? '(' + res.data.error_details + ')' : ''}`);
      }
      setRefreshPageModal({ isOpen: false, page: null, newAccessToken: '' });
      fetchMetaPages();
      fetchLogs();
    } catch (err) {
      showToast('error', 'Token refresh failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setRefreshingPage(false);
    }
  };

  const handleDeleteMetaPage = async (pageId, pageName) => {
    if (!window.confirm(`Are you sure you want to remove the connected Facebook Page '${pageName}' (ID: ${pageId}) from CRM?`)) {
      return;
    }
    try {
      setPageActionLoading(prev => ({ ...prev, [pageId]: 'delete' }));
      await API.delete(`/integrations/meta/pages/${pageId}`);
      showToast('success', `Facebook Page '${pageName}' has been removed.`);
      fetchMetaPages();
      fetchStatus();
      fetchLogs();
    } catch (err) {
      showToast('error', 'Failed to remove page: ' + (err.response?.data?.detail || err.message));
    } finally {
      setPageActionLoading(prev => ({ ...prev, [pageId]: null }));
    }
  };

  const showToast = (type, message) => {
    setToast({ type, message });
    setTimeout(() => {
      setToast(null);
    }, 4500);
  };

  const handleCopy = (text, label) => {
    navigator.clipboard.writeText(text);
    setCopiedField(label);
    setTimeout(() => setCopiedField(null), 2000);
  };

  // Connection Test
  const handleTestConnection = async (type) => {
    try {
      setTestingType(type);
      const res = await API.post(`/integrations/hub/${type}/test`);
      if (res.data.success) {
        showToast('success', `${type} Test Passed: ${res.data.message}`);
      } else {
        showToast('error', `${type} Test Failed: ${res.data.message} ${res.data.error_details ? '(' + res.data.error_details + ')' : ''}`);
      }
      fetchStatus();
      fetchLogs();
    } catch (err) {
      showToast('error', `Connection test failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setTestingType(null);
    }
  };

  // Connect / Disconnect Toggle
  const handleToggleConnect = async (item) => {
    const isConnected = item.status === 'CONNECTED';
    const action = isConnected ? 'disconnect' : 'connect';
    try {
      setActionLoading(item.integration_type);
      await API.post(`/integrations/hub/${item.integration_type}/${action}`);
      showToast('success', `${item.name} status updated to ${isConnected ? 'DISCONNECTED' : 'CONNECTED'}.`);
      fetchStatus();
      fetchLogs();
    } catch (err) {
      showToast('error', `Failed to ${action} integration: ${err.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Open Configure Modal
  const openConfigureModal = (item) => {
    setShowSecrets({});
    const initialConfig = { ...item.masked_config };
    if (item.integration_type === 'IVR') {
      const provider = initialConfig.provider || 'SMARTFLO';
      if (provider === 'DOOCTI') {
        if (initialConfig.api_url?.includes('smartflo') || initialConfig.api_url?.includes('tatateleservices')) {
          initialConfig.api_url = 'https://beta3-app.doocti.com/';
        }
        if (initialConfig.account_id?.toLowerCase().includes('smartflo')) {
          initialConfig.account_id = 'chntechnolog';
        }
        if (!initialConfig.phone_number || initialConfig.phone_number === '918069879797' || initialConfig.phone_number === '07969659985') {
          initialConfig.phone_number = '07969671855, 07969671856, 07969671857';
        }
        if (!initialConfig.admin_extension) {
          initialConfig.admin_extension = '1281';
        }
        if (!initialConfig.extensions || initialConfig.extensions === '1282, 1283') {
          initialConfig.extensions = '1281, 1282, 1283, 1286';
        }
      }
    }
    setModalState({
      isOpen: true,
      type: item.integration_type,
      name: item.name,
      webhookUrl: item.webhook_url,
      config: initialConfig
    });
  };

  const closeModal = () => {
    setModalState({ isOpen: false, type: null, config: {} });
    setShowSecrets({});
  };

  const handleConfigChange = (key, value) => {
    setModalState(prev => ({
      ...prev,
      config: {
        ...prev.config,
        [key]: value
      }
    }));
  };

  const handleIvrProviderChange = (newProvider) => {
    setModalState(prev => {
      const prevConfig = prev.config || {};
      let updatedConfig = { ...prevConfig, provider: newProvider };
      if (newProvider === 'DOOCTI') {
        if (!updatedConfig.api_url || updatedConfig.api_url.includes('tatateleservices') || updatedConfig.api_url.includes('smartflo')) {
          updatedConfig.api_url = 'https://beta3-app.doocti.com/';
        }
        if (!updatedConfig.account_id || updatedConfig.account_id.toLowerCase().includes('smartflo')) {
          updatedConfig.account_id = 'chntechnolog';
        }
        if (!updatedConfig.phone_number || updatedConfig.phone_number === '918069879797' || updatedConfig.phone_number === '07969659985') {
          updatedConfig.phone_number = '07969671855, 07969671856, 07969671857';
        }
        if (!updatedConfig.admin_extension) {
          updatedConfig.admin_extension = '1281';
        }
        if (!updatedConfig.agent_extensions) {
          updatedConfig.agent_extensions = '1282, 1283, 1286';
        }
        if (!updatedConfig.extensions || updatedConfig.extensions === '1282, 1283') {
          updatedConfig.extensions = '1281, 1282, 1283, 1286';
        }
      } else if (newProvider === 'SMARTFLO') {
        if (!updatedConfig.api_url || updatedConfig.api_url.includes('doocti')) {
          updatedConfig.api_url = 'https://api-smartflo.tatateleservices.com/v1/click_to_call';
        }
        if (!updatedConfig.account_id || updatedConfig.account_id.includes('chntechnolog')) {
          updatedConfig.account_id = 'Smartflo';
        }
        if (!updatedConfig.phone_number || updatedConfig.phone_number === '07969659985') {
          updatedConfig.phone_number = '918069879797';
        }
      }
      return {
        ...prev,
        config: updatedConfig
      };
    });
  };

  const toggleSecretVisibility = (key) => {
    setShowSecrets(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const generateNewWebsiteKey = () => {
    const randomKey = 'wacrm_site_' + Math.random().toString(36).substring(2, 10) + '_' + Date.now().toString(36);
    handleConfigChange('api_key', randomKey);
    showToast('success', 'New Website API Key generated! Click Save to apply.');
  };

  // Save Config
  const handleSaveConfig = async (e) => {
    e.preventDefault();
    try {
      setSavingConfig(true);
      await API.post(`/integrations/hub/${modalState.type}/configure`, {
        integration_type: modalState.type,
        config_data: modalState.config
      });
      showToast('success', `${modalState.name} configuration saved successfully!`);
      closeModal();
      fetchStatus();
      fetchLogs();
    } catch (err) {
      showToast('error', `Failed to save configuration: ${err.response?.data?.detail || err.message}`);
    } finally {
      setSavingConfig(false);
    }
  };

  const filteredLogs = logs.filter(log => logFilter === 'ALL' || log.integration_type === logFilter);

  const activeIntegrations = integrations.filter(
    (item) => item.integration_type !== 'WAQUOTE' && item.integration_type !== 'QUOTETASK'
  );
  const connectedCount = activeIntegrations.filter(i => i.status === 'CONNECTED').length;

  return (
    <div className="integrations-page">
      {/* Toast Alert */}
      {toast && (
        <div 
          className={`alert`} 
          style={{ 
            position: 'fixed', 
            top: '20px', 
            right: '20px', 
            zIndex: 2000, 
            maxWidth: '450px',
            backgroundColor: toast.type === 'success' ? '#ecfdf5' : '#fef2f2',
            color: toast.type === 'success' ? '#065f46' : '#991b1b',
            border: `1px solid ${toast.type === 'success' ? '#a7f3d0' : '#fecaca'}`,
            borderRadius: '10px',
            padding: '14px 18px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1)'
          }}
        >
          {toast.type === 'success' ? <CheckCircle2 size={20} /> : <XCircle size={20} />}
          <span style={{ fontSize: '0.88rem', fontWeight: 500 }}>{toast.message}</span>
        </div>
      )}

      {/* Header */}
      <div className="integrations-header">
        <div>
          <div className="integrations-breadcrumb">
            <Link to="/dashboard">Dashboard</Link> / <Link to="/settings">Settings</Link> / <span>Integration Hub</span>
          </div>
          <h1 className="integrations-title">CRM Integration Hub</h1>
          <p className="integrations-subtitle">Centralized hub for managing Meta Ads, WhatsApp Cloud API, IVR Telephony, and Website Ingestion.</p>
        </div>

        <button onClick={fetchStatus} className="btn-hub btn-hub-outline" disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          <span>Refresh Hub</span>
        </button>
      </div>

      {/* Summary Banner */}
      <div className="integrations-summary-banner">
        <div className="summary-card">
          <div className="summary-icon meta"><Zap size={22} /></div>
          <div className="summary-details">
            <h4>Integrations Active</h4>
            <p>{connectedCount} of {activeIntegrations.length || 3} Connected</p>
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-icon whatsapp"><ShieldCheck size={22} /></div>
          <div className="summary-details">
            <h4>Security Status</h4>
            <p>API Secrets Masked</p>
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-icon ivr"><Terminal size={22} /></div>
          <div className="summary-details">
            <h4>Webhooks Active</h4>
            <p>All Endpoints Secured</p>
          </div>
        </div>
      </div>

      {/* Integration Cards Grid */}
      {loading && activeIntegrations.length === 0 ? (
        <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
          <RefreshCw size={32} className="spin" style={{ marginBottom: '12px', color: '#2563eb' }} />
          <p>Loading integration cards & status...</p>
        </div>
      ) : (
        <div className="integrations-grid">
          {activeIntegrations.map((item) => {
            const meta = INTEGRATION_ICONS[item.integration_type] || { icon: Sliders, className: 'meta' };
            const IconComp = meta.icon;
            const isTesting = testingType === item.integration_type;
            const isActioning = actionLoading === item.integration_type;

            return (
              <div key={item.integration_type} className="integration-card">
                <div>
                  <div className="card-header-top">
                    <div className="card-title-group">
                      <div className={`card-icon-avatar ${meta.className}`}>
                        <IconComp size={22} />
                      </div>
                      <div>
                        <h3>{item.name}</h3>
                        <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Type: {item.integration_type}</span>
                      </div>
                    </div>

                    <span className={`status-badge ${item.status.toLowerCase()}`}>
                      {item.status === 'CONNECTED' && '🟢 Connected'}
                      {item.status === 'TESTING' && '🟡 Testing'}
                      {item.status === 'ERROR' && '🔴 Error'}
                      {item.status === 'NOT_CONNECTED' && '⚪ Not Connected'}
                      {item.status === 'DISCONNECTED' && '⚪ Disconnected'}
                    </span>
                  </div>

                  <p className="card-description">{item.description}</p>

                  {/* Webhook Box */}
                  {item.webhook_url && (
                    <div className="card-endpoint-box">
                      <div>
                        <span className="endpoint-label">Ingestion Endpoint / Webhook URL</span>
                        <span className="endpoint-url">{window.location.origin}{item.webhook_url}</span>
                      </div>
                      <button 
                        className="btn-copy" 
                        onClick={() => handleCopy(`${window.location.origin}${item.webhook_url}`, item.integration_type)}
                        title="Copy Endpoint URL"
                      >
                        {copiedField === item.integration_type ? <Check size={14} style={{ color: '#10b981' }} /> : <Copy size={14} />}
                      </button>
                    </div>
                  )}

                  {/* Meta Multi-Page Status Strip */}
                  {item.integration_type === 'META' && (
                    <div style={{ 
                      marginTop: '14px', 
                      padding: '12px 14px', 
                      background: '#f5f3ff', 
                      border: '1px solid #ddd6fe', 
                      borderRadius: '10px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '10px',
                      flexWrap: 'wrap'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Layers size={18} style={{ color: '#7c3aed' }} />
                        <div>
                          <div style={{ fontSize: '0.86rem', fontWeight: 700, color: '#5b21b6' }}>
                            {metaPages.length} Facebook {metaPages.length === 1 ? 'Page' : 'Pages'} Connected
                          </div>
                          <div style={{ fontSize: '0.74rem', color: '#7c3aed' }}>
                            Per-page encrypted credentials & independent sync
                          </div>
                        </div>
                      </div>

                      <Link 
                        to="/settings/integrations/meta" 
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          color: '#ffffff',
                          background: '#7c3aed',
                          padding: '6px 12px',
                          borderRadius: '8px',
                          textDecoration: 'none',
                          whiteSpace: 'nowrap'
                        }}
                      >
                        <span>Manage Pages</span>
                        <ExternalLink size={13} />
                      </Link>
                    </div>
                  )}

                  <div className="card-meta-info">
                    <span>
                      <strong>Last Tested:</strong>{' '}
                      {item.last_tested_at ? new Date(item.last_tested_at).toLocaleString() : 'Never'}
                    </span>
                    <span>
                      <strong>Auth Mode:</strong> {item.integration_type === 'META' ? 'Per-Page Encrypted Tokens' : 'Secured API Keys'}
                    </span>
                  </div>
                </div>

                {/* Actions Bar */}
                <div className="card-actions">
                  {item.integration_type === 'META' ? (
                    <Link 
                      to="/settings/integrations/meta"
                      className="btn-hub btn-hub-primary"
                      title="Open dedicated Meta Ads & Pages Hub"
                      style={{ textDecoration: 'none' }}
                    >
                      <Share2 size={15} />
                      <span>Manage Pages</span>
                    </Link>
                  ) : (
                    <button 
                      onClick={() => openConfigureModal(item)}
                      className="btn-hub btn-hub-outline"
                      title="Configure API Keys & Webhook Secret"
                    >
                      <Settings size={15} />
                      <span>Configure</span>
                    </button>
                  )}

                  <button 
                    onClick={() => handleTestConnection(item.integration_type)}
                    className="btn-hub btn-hub-outline"
                    disabled={isTesting}
                    title="Run live backend ping test"
                  >
                    <Play size={15} className={isTesting ? 'spin' : ''} />
                    <span>{isTesting ? 'Testing...' : 'Test Connection'}</span>
                  </button>

                  <button 
                    onClick={() => handleToggleConnect(item)}
                    className={`btn-hub ${item.status === 'CONNECTED' ? 'btn-hub-danger' : 'btn-hub-success'}`}
                    disabled={isActioning}
                  >
                    <Power size={15} className={isActioning ? 'spin' : ''} />
                    <span>{item.status === 'CONNECTED' ? 'Disconnect' : 'Connect'}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Audit Logs Section */}
      <div className="logs-section">
        <div className="logs-header">
          <h3>Integration Activity & Audit Logs</h3>

          <div className="logs-filters">
            <select 
              value={logFilter} 
              onChange={(e) => setLogFilter(e.target.value)}
              className="logs-select"
            >
              <option value="ALL">All Integrations</option>
              <option value="META">Meta Ads</option>
              <option value="WHATSAPP">WhatsApp</option>
              <option value="IVR">IVR Telephony</option>
              <option value="WEBSITE">Website Leads</option>
            </select>

            <button onClick={fetchLogs} className="btn-hub btn-hub-outline" disabled={loadingLogs} style={{ padding: '6px 10px' }}>
              <RefreshCw size={14} className={loadingLogs ? 'spin' : ''} />
            </button>
          </div>
        </div>

        <div className="logs-table-wrapper">
          {filteredLogs.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: '0.88rem', padding: '16px', textAlign: 'center' }}>No integration log events recorded yet.</p>
          ) : (
            <table className="logs-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Integration</th>
                  <th>Event Type</th>
                  <th>Status</th>
                  <th>Log Details</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((log) => (
                  <tr key={log.id}>
                    <td style={{ whiteSpace: 'nowrap', fontSize: '0.8rem', color: '#64748b' }}>
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td>
                      <strong style={{ color: '#0f172a' }}>{log.integration_type}</strong>
                    </td>
                    <td>
                      <span className="log-event-badge">{log.event_type}</span>
                    </td>
                    <td>
                      <span className={`log-status-badge ${log.status}`}>
                        {log.status}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.82rem' }}>{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Configuration Modal */}
      {modalState.isOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Configure {modalState.name}</h3>
              <button className="modal-close-btn" onClick={closeModal}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveConfig}>
              <div className="modal-body">
                {/* META Config Fields */}
                {modalState.type === 'META' && (
                  <>
                    <div className="form-group">
                      <label>Meta App ID</label>
                      <input 
                        type="text" 
                        value={modalState.config.app_id || ''} 
                        onChange={(e) => handleConfigChange('app_id', e.target.value)}
                        placeholder="e.g. 1234567890"
                      />
                    </div>

                    <div className="form-group">
                      <label>Meta App Secret</label>
                      <div className="secret-input-wrapper">
                        <input 
                          type={showSecrets.app_secret ? 'text' : 'password'} 
                          value={modalState.config.app_secret || ''} 
                          onChange={(e) => handleConfigChange('app_secret', e.target.value)}
                          placeholder="••••••••••••"
                        />
                        <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('app_secret')}>
                          {showSecrets.app_secret ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Page Access Token (Long-Lived)</label>
                      <div className="secret-input-wrapper">
                        <input 
                          type={showSecrets.access_token ? 'text' : 'password'} 
                          value={modalState.config.access_token || ''} 
                          onChange={(e) => handleConfigChange('access_token', e.target.value)}
                          placeholder="EAABb..."
                        />
                        <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('access_token')}>
                          {showSecrets.access_token ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Facebook Page ID</label>
                      <input 
                        type="text" 
                        value={modalState.config.page_id || ''} 
                        onChange={(e) => handleConfigChange('page_id', e.target.value)}
                        placeholder="e.g. 1009988776655"
                      />
                    </div>

                    <div className="form-group">
                      <label>Webhook Verify Token</label>
                      <div className="secret-input-wrapper">
                        <input 
                          type={showSecrets.verify_token ? 'text' : 'password'} 
                          value={modalState.config.verify_token || ''} 
                          onChange={(e) => handleConfigChange('verify_token', e.target.value)}
                          placeholder="wacrm_meta_verify_secret"
                        />
                        <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('verify_token')}>
                          {showSecrets.verify_token ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Graph API Version</label>
                      <input 
                        type="text" 
                        value={modalState.config.api_version || 'v20.0'} 
                        onChange={(e) => handleConfigChange('api_version', e.target.value)}
                      />
                    </div>
                  </>
                )}

                {/* WHATSAPP Config Fields */}
                {modalState.type === 'WHATSAPP' && (
                  <>
                    <div className="form-group">
                      <label>WhatsApp Business Account ID</label>
                      <input 
                        type="text" 
                        value={modalState.config.business_account_id || ''} 
                        onChange={(e) => handleConfigChange('business_account_id', e.target.value)}
                        placeholder="e.g. 100987654321"
                      />
                    </div>

                    <div className="form-group">
                      <label>Phone Number ID</label>
                      <input 
                        type="text" 
                        value={modalState.config.phone_number_id || ''} 
                        onChange={(e) => handleConfigChange('phone_number_id', e.target.value)}
                        placeholder="e.g. 105678123456"
                      />
                    </div>

                    <div className="form-group">
                      <label>Permanent Access Token</label>
                      <div className="secret-input-wrapper">
                        <input 
                          type={showSecrets.access_token ? 'text' : 'password'} 
                          value={modalState.config.access_token || ''} 
                          onChange={(e) => handleConfigChange('access_token', e.target.value)}
                          placeholder="EAABb..."
                        />
                        <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('access_token')}>
                          {showSecrets.access_token ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Webhook Verify Token</label>
                      <div className="secret-input-wrapper">
                        <input 
                          type={showSecrets.verify_token ? 'text' : 'password'} 
                          value={modalState.config.verify_token || ''} 
                          onChange={(e) => handleConfigChange('verify_token', e.target.value)}
                          placeholder="wacrm_wa_verify_secret"
                        />
                        <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('verify_token')}>
                          {showSecrets.verify_token ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>

                    <div className="form-group">
                      <label>API Version</label>
                      <input 
                        type="text" 
                        value={modalState.config.api_version || 'v20.0'} 
                        onChange={(e) => handleConfigChange('api_version', e.target.value)}
                      />
                    </div>
                  </>
                )}

                {/* IVR Config Fields */}
                {modalState.type === 'IVR' && (
                  <>
                    <div className="form-group">
                      <label>Telephony Provider</label>
                      <select 
                        value={modalState.config.provider || 'SMARTFLO'} 
                        onChange={(e) => handleIvrProviderChange(e.target.value)}
                      >
                        <option value="DOOCTI">Doocti Telephony (In-App WebRTC Connector)</option>
                        <option value="SMARTFLO">Tata Teleservices Smartflo (Inbound & Outbound)</option>
                        <option value="CLOUDSHOPE">CloudShope IVR (Webhook / CDR)</option>
                        <option value="CUSTOM">Custom SIP / Webhook</option>
                        <option value="EXOTEL">Exotel IVR</option>
                        <option value="TWILIO">Twilio Voice</option>
                        <option value="MYOPERATOR">MyOperator</option>
                      </select>
                    </div>

                    {modalState.config.provider === 'DOOCTI' ? (
                      <>
                        <div className="form-group">
                          <label>Doocti In-App WebRTC Domain</label>
                          <input 
                            type="text" 
                            value={modalState.config.api_url || 'https://beta3-app.doocti.com/'} 
                            onChange={(e) => handleConfigChange('api_url', e.target.value)}
                            placeholder="https://beta3-app.doocti.com/"
                          />
                        </div>

                        <div className="form-group">
                          <label>Tenant ID / Organization Name</label>
                          <input 
                            type="text" 
                            value={modalState.config.account_id || 'chntechnolog'} 
                            onChange={(e) => handleConfigChange('account_id', e.target.value)}
                            placeholder="chntechnolog"
                          />
                        </div>

                        <div className="form-group">
                          <label>DID Numbers (Inbound / Outbound Virtual Numbers)</label>
                          <input 
                            type="text" 
                            value={modalState.config.phone_number || '07969671855, 07969671856, 07969671857'} 
                            onChange={(e) => handleConfigChange('phone_number', e.target.value)}
                            placeholder="07969671855, 07969671856, 07969671857"
                          />
                          <small style={{ color: '#64748b', fontSize: '0.74rem' }}>
                            Configured DIDs: 07969671855, 07969671856, 07969671857
                          </small>
                        </div>

                        <div className="form-group">
                          <label>Admin WebRTC Extension</label>
                          <input 
                            type="text" 
                            value={modalState.config.admin_extension || '1281'} 
                            onChange={(e) => handleConfigChange('admin_extension', e.target.value)}
                            placeholder="1281"
                          />
                          <small style={{ color: '#64748b', fontSize: '0.74rem' }}>
                            Dedicated Admin Extension: 1281 (Admin)
                          </small>
                        </div>

                        <div className="form-group">
                          <label>Agent WebRTC Extensions</label>
                          <input 
                            type="text" 
                            value={modalState.config.extensions || '1282, 1283, 1286'} 
                            onChange={(e) => handleConfigChange('extensions', e.target.value)}
                            placeholder="1282, 1283, 1286"
                          />
                          <small style={{ color: '#64748b', fontSize: '0.74rem' }}>
                            Agent Extensions: 1282 (Sales Executive), 1283 (Sales Manager), 1286 (Support Executive)
                          </small>
                        </div>

                        <div style={{ backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '12px 14px', marginTop: '10px' }}>
                          <span style={{ fontSize: '0.78rem', fontWeight: '700', color: '#166534', display: 'block', marginBottom: '6px' }}>
                            Doocti Integration CRM Endpoints:
                          </span>
                          <p style={{ fontSize: '0.73rem', color: '#14532d', margin: '4px 0' }}>
                            <b>Call Log Push Webhook:</b> <code style={{ backgroundColor: '#ffffff', padding: '2px 6px', borderRadius: '4px' }}>https://www.wapluscrm.in/api/doocti/call-log</code>
                          </p>
                          <p style={{ fontSize: '0.73rem', color: '#14532d', margin: '4px 0' }}>
                            <b>Lead Search & Auto-create:</b> <code style={{ backgroundColor: '#ffffff', padding: '2px 6px', borderRadius: '4px' }}>{`${window.location.origin}/api/doocti/lead-by-number`}</code>
                          </p>
                          <p style={{ fontSize: '0.73rem', color: '#14532d', margin: '4px 0' }}>
                            <b>Contacts Fetch API:</b> <code style={{ backgroundColor: '#ffffff', padding: '2px 6px', borderRadius: '4px' }}>{`${window.location.origin}/api/doocti/contacts`}</code>
                          </p>
                          <p style={{ fontSize: '0.73rem', color: '#14532d', margin: '4px 0' }}>
                            <b>Lead Update API:</b> <code style={{ backgroundColor: '#ffffff', padding: '2px 6px', borderRadius: '4px' }}>{`${window.location.origin}/api/doocti/lead/update`}</code>
                          </p>
                        </div>
                      </>
                    ) : modalState.config.provider === 'SMARTFLO' ? (
                      <>
                        <div className="form-group">
                          <label>Smartflo Click-to-Call Service API Key</label>
                          <div className="secret-input-wrapper">
                            <input 
                              type={showSecrets.api_key ? 'text' : 'password'} 
                              value={modalState.config.api_key || ''} 
                              onChange={(e) => handleConfigChange('api_key', e.target.value)}
                              placeholder="e.g. 62c5d471-63a3-43c9-a12e-d1da29d46f05"
                            />
                            <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('api_key')}>
                              {showSecrets.api_key ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                          </div>
                          <span style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '3px', display: 'block' }}>
                            Campaign or Click-to-Call Service Key created in Services → Click to Call.
                          </span>
                        </div>

                        <div className="form-group">
                          <label>Smartflo API Bearer Token (Optional / If Required)</label>
                          <div className="secret-input-wrapper">
                            <input 
                              type={showSecrets.api_token ? 'text' : 'password'} 
                              value={modalState.config.api_token || ''} 
                              onChange={(e) => handleConfigChange('api_token', e.target.value)}
                              placeholder="Paste Bearer Token from Smartflo Portal"
                            />
                            <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('api_token')}>
                              {showSecrets.api_token ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                          </div>
                          <span style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '3px', display: 'block' }}>
                            Generated under <b>Administration → API Tokens</b> in your Smartflo portal. Resolves 401 Unauthorized errors.
                          </span>
                        </div>

                        <div className="form-group">
                          <label>Smartflo Caller ID / Pilot Number (Optional)</label>
                          <input 
                            type="text" 
                            value={modalState.config.phone_number || ''} 
                            onChange={(e) => handleConfigChange('phone_number', e.target.value)}
                            placeholder="e.g. 080XXXXXXXX (Leave blank for default pilot number)"
                          />
                        </div>

                        <div style={{ backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '10px', padding: '12px 14px', marginTop: '10px' }}>
                          <span style={{ fontSize: '0.78rem', fontWeight: '700', color: '#1e40af', display: 'block', marginBottom: '4px' }}>
                            Smartflo Webhook URL (For Inbound & Outbound Webhooks):
                          </span>
                          <code style={{ fontSize: '0.74rem', color: '#1e3a8a', wordBreak: 'break-all', display: 'block', backgroundColor: '#ffffff', padding: '6px 8px', borderRadius: '6px', border: '1px solid #dbeafe' }}>
                            {`${window.location.origin}/api/ivr/webhook`}
                          </code>
                          <button 
                            type="button" 
                            onClick={() => handleCopy(`${window.location.origin}/api/ivr/webhook`, 'smartflo_url')}
                            style={{ marginTop: '8px', padding: '4px 10px', fontSize: '0.75rem', fontWeight: '700', borderRadius: '6px', backgroundColor: '#2563eb', color: '#ffffff', border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                          >
                            {copiedField === 'smartflo_url' ? <Check size={13} /> : <Copy size={13} />}
                            <span>{copiedField === 'smartflo_url' ? 'Copied URL!' : 'Copy Smartflo Webhook URL'}</span>
                          </button>
                          <p style={{ fontSize: '0.73rem', color: '#64748b', marginTop: '6px', marginBottom: 0 }}>
                            In Smartflo portal: Webhooks → Add Webhook → Select Method <b>POST</b> → Paste URL above → Content Type: <b>JSON</b>.
                          </p>
                        </div>
                      </>
                    ) : modalState.config.provider === 'CLOUDSHOPE' ? (
                      <>
                        <div className="form-group">
                          <label>CloudShope Virtual / Pilot Number (DID)</label>
                          <input 
                            type="text" 
                            value={modalState.config.phone_number || ''} 
                            onChange={(e) => handleConfigChange('phone_number', e.target.value)}
                            placeholder="e.g. 1204362938 or 6746755303"
                          />
                        </div>

                        <div className="form-group">
                          <label>CloudShope API Key / Auth Key (Optional for Outbound Click-to-Call)</label>
                          <div className="secret-input-wrapper">
                            <input 
                              type={showSecrets.api_key ? 'text' : 'password'} 
                              value={modalState.config.api_key || ''} 
                              onChange={(e) => handleConfigChange('api_key', e.target.value)}
                              placeholder="e.g. your_cloudshope_auth_key"
                            />
                            <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('api_key')}>
                              {showSecrets.api_key ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                          </div>
                        </div>

                        <div className="form-group">
                          <label>Click-to-Call Endpoint URL (Optional)</label>
                          <input 
                            type="text" 
                            value={modalState.config.api_url || ''} 
                            onChange={(e) => handleConfigChange('api_url', e.target.value)}
                            placeholder="http://yourmessageapi.com/clicktocall.php"
                          />
                        </div>

                        <div style={{ backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '10px', padding: '12px 14px', marginTop: '10px' }}>
                          <span style={{ fontSize: '0.78rem', fontWeight: '700', color: '#1e40af', display: 'block', marginBottom: '4px' }}>
                            CloudShope Callback / Webhook URL:
                          </span>
                          <code style={{ fontSize: '0.74rem', color: '#1e3a8a', wordBreak: 'break-all', display: 'block', backgroundColor: '#ffffff', padding: '6px 8px', borderRadius: '6px', border: '1px solid #dbeafe' }}>
                            {`${window.location.origin}/api/ivr/webhook?from=%from%&time=%time%&agent_name=%agent_name%&agent_number=%agent_number%&to=%to%&uniqueid=%uniqueid%&unix=%unix%&status=%status%&total_duration=%total_duration%&agent_duration=%agent_duration%&operator=%operator%&circle=%circle%&extension=%extension%&recording=%recording%`}
                          </code>
                          <button 
                            type="button" 
                            onClick={() => handleCopy(`${window.location.origin}/api/ivr/webhook?from=%from%&time=%time%&agent_name=%agent_name%&agent_number=%agent_number%&to=%to%&uniqueid=%uniqueid%&unix=%unix%&status=%status%&total_duration=%total_duration%&agent_duration=%agent_duration%&operator=%operator%&circle=%circle%&extension=%extension%&recording=%recording%`, 'cloudshope_url')}
                            style={{ marginTop: '8px', padding: '4px 10px', fontSize: '0.75rem', fontWeight: '700', borderRadius: '6px', backgroundColor: '#2563eb', color: '#ffffff', border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                          >
                            {copiedField === 'cloudshope_url' ? <Check size={13} /> : <Copy size={13} />}
                            <span>{copiedField === 'cloudshope_url' ? 'Copied URL!' : 'Copy CloudShope Webhook URL'}</span>
                          </button>
                        </div>
                      </>
                    ) : modalState.config.provider === 'EXOTEL' ? (
                      <>
                        <div className="form-group">
                          <label>Account SID</label>
                          <input 
                            type="text" 
                            value={modalState.config.account_id || ''} 
                            onChange={(e) => handleConfigChange('account_id', e.target.value)}
                            placeholder="e.g. chntechnologies1"
                          />
                        </div>

                        <div className="form-group">
                          <label>API Key (Username)</label>
                          <div className="secret-input-wrapper">
                            <input 
                              type={showSecrets.api_key ? 'text' : 'password'} 
                              value={modalState.config.api_key || ''} 
                              onChange={(e) => handleConfigChange('api_key', e.target.value)}
                              placeholder="e.g. 87a53dbe68e08daf..."
                            />
                            <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('api_key')}>
                              {showSecrets.api_key ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                          </div>
                        </div>

                        <div className="form-group">
                          <label>API Token / Secret (Password)</label>
                          <div className="secret-input-wrapper">
                            <input 
                              type={showSecrets.api_secret ? 'text' : 'password'} 
                              value={modalState.config.api_secret || ''} 
                              onChange={(e) => handleConfigChange('api_secret', e.target.value)}
                              placeholder="e.g. f1a423ea03db8834..."
                            />
                            <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('api_secret')}>
                              {showSecrets.api_secret ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                          </div>
                        </div>

                        <div className="form-group">
                          <label>ExoPhone Virtual Number</label>
                          <input 
                            type="text" 
                            value={modalState.config.phone_number || ''} 
                            onChange={(e) => handleConfigChange('phone_number', e.target.value)}
                            placeholder="e.g. 09513886363"
                          />
                        </div>
                      </>
                    ) : modalState.config.provider === 'TWILIO' ? (
                      <>
                        <div className="form-group">
                          <label>Twilio Account SID</label>
                          <input 
                            type="text" 
                            value={modalState.config.account_id || ''} 
                            onChange={(e) => handleConfigChange('account_id', e.target.value)}
                            placeholder="e.g. ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                          />
                        </div>

                        <div className="form-group">
                          <label>Twilio Auth Token</label>
                          <div className="secret-input-wrapper">
                            <input 
                              type={showSecrets.api_key ? 'text' : 'password'} 
                              value={modalState.config.api_key || modalState.config.api_secret || ''} 
                              onChange={(e) => {
                                handleConfigChange('api_key', e.target.value);
                                handleConfigChange('api_secret', e.target.value);
                              }}
                              placeholder="e.g. 25af4d06f9f5486afe198..."
                            />
                            <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('api_key')}>
                              {showSecrets.api_key ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                          </div>
                        </div>

                        <div className="form-group">
                          <label>Twilio Phone Number</label>
                          <input 
                            type="text" 
                            value={modalState.config.phone_number || ''} 
                            onChange={(e) => handleConfigChange('phone_number', e.target.value)}
                            placeholder="e.g. +17372508034"
                          />
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="form-group">
                          <label>Account ID / SID</label>
                          <input 
                            type="text" 
                            value={modalState.config.account_id || ''} 
                            onChange={(e) => handleConfigChange('account_id', e.target.value)}
                            placeholder="e.g. ACxxxxxxxxxxxxxxxx"
                          />
                        </div>

                        <div className="form-group">
                          <label>API Key / Token</label>
                          <div className="secret-input-wrapper">
                            <input 
                              type={showSecrets.api_key ? 'text' : 'password'} 
                              value={modalState.config.api_key || ''} 
                              onChange={(e) => handleConfigChange('api_key', e.target.value)}
                              placeholder="••••••••••••"
                            />
                            <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('api_key')}>
                              {showSecrets.api_key ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                          </div>
                        </div>

                        <div className="form-group">
                          <label>Virtual Phone Number</label>
                          <input 
                            type="text" 
                            value={modalState.config.phone_number || ''} 
                            onChange={(e) => handleConfigChange('phone_number', e.target.value)}
                            placeholder="+18005550199"
                          />
                        </div>
                      </>
                    )}
                  </>
                )}

                {/* WEBSITE Config Fields */}
                {modalState.type === 'WEBSITE' && (
                  <>
                    <div className="form-group">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <label style={{ margin: 0 }}>Website API Authorization Key</label>
                        <button 
                          type="button" 
                          onClick={generateNewWebsiteKey}
                          className="btn-hub btn-hub-outline"
                          style={{ padding: '4px 8px', fontSize: '0.78rem' }}
                        >
                          <Key size={12} />
                          <span>Generate Key</span>
                        </button>
                      </div>
                      <div className="secret-input-wrapper">
                        <input 
                          type={showSecrets.api_key ? 'text' : 'password'} 
                          value={modalState.config.api_key || ''} 
                          onChange={(e) => handleConfigChange('api_key', e.target.value)}
                          placeholder="wacrm_site_api_key_2026"
                        />
                        <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('api_key')}>
                          {showSecrets.api_key ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Allowed Domains (CORS Origins)</label>
                      <input 
                        type="text" 
                        value={Array.isArray(modalState.config.allowed_domains) ? modalState.config.allowed_domains.join(', ') : (modalState.config.allowed_domains || '')} 
                        onChange={(e) => handleConfigChange('allowed_domains', e.target.value.split(',').map(s => s.trim()))}
                        placeholder="http://localhost:5173, https://mycompany.com"
                      />
                      <span style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px', display: 'block' }}>Comma separated URLs allowed to submit website leads.</span>
                    </div>

                    {/* Website Embed Snippet Box */}
                    <div style={{ background: '#0f172a', borderRadius: '10px', padding: '14px', marginTop: '10px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: '0.78rem', marginBottom: '8px' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <FileCode size={14} style={{ color: '#38bdf8' }} /> HTML JavaScript Integration Code Example
                        </span>
                      </div>
                      <pre style={{ color: '#38bdf8', fontSize: '0.78rem', overflowX: 'auto', margin: 0, lineHeight: 1.4 }}>
{`// Submit lead to CRM Endpoint
fetch("${window.location.origin}/api/integrations/website/leads", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Website-Api-Key": "${modalState.config.api_key || 'YOUR_API_KEY'}"
  },
  body: JSON.stringify({
    full_name: "Customer Name",
    phone: "+919876543210",
    email: "lead@example.com",
    source: "WEBSITE",
    website_id: "main_site",
    website_name: "Official Landing Page"
  })
});`}
                      </pre>
                    </div>
                  </>
                )}
              </div>

              <div className="modal-footer">
                <button type="button" className="btn-hub btn-hub-outline" onClick={closeModal}>
                  Cancel
                </button>
                <button type="submit" className="btn-hub btn-hub-primary" disabled={savingConfig}>
                  <RefreshCw size={15} className={savingConfig ? 'spin' : ''} />
                  <span>{savingConfig ? 'Saving...' : 'Save Configuration'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default IntegrationsPage;
