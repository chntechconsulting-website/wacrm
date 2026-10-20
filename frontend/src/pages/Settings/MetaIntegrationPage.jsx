import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import { 
  Share2, 
  Layers, 
  Plus, 
  RefreshCw, 
  Power, 
  Key, 
  Trash2, 
  Copy, 
  Check, 
  ExternalLink, 
  ArrowLeft, 
  CheckCircle2, 
  AlertTriangle, 
  HelpCircle, 
  Zap, 
  Eye, 
  EyeOff, 
  X,
  ShieldCheck,
  Globe
} from 'lucide-react';
import './MetaIntegrationPage.css';

const MetaIntegrationPage = () => {
  const [pages, setPages] = useState([]);
  const [metaStatus, setMetaStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pageActionLoading, setPageActionLoading] = useState({});
  const [toast, setToast] = useState(null);
  const [copiedField, setCopiedField] = useState(null);
  const [showSecrets, setShowSecrets] = useState({});

  // Modals
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [newPageData, setNewPageData] = useState({ page_id: '', page_name: '', access_token: '' });
  const [addingPage, setAddingPage] = useState(false);

  const [refreshModal, setRefreshModal] = useState({ isOpen: false, page: null, newAccessToken: '' });
  const [refreshingPage, setRefreshingPage] = useState(false);

  const showToast = (type, message) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4500);
  };

  const handleCopy = (text, label) => {
    navigator.clipboard.writeText(text);
    setCopiedField(label);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const toggleSecret = (key) => {
    setShowSecrets(prev => ({ ...prev, [key]: !prev[key] }));
  };

  // Fetch Data
  const fetchData = async () => {
    try {
      setLoading(true);
      const [pagesRes, statusRes] = await Promise.all([
        API.get('/integrations/meta/pages'),
        API.get('/integrations/meta/status')
      ]);
      setPages(pagesRes.data || []);
      setMetaStatus(statusRes.data || null);
    } catch (err) {
      showToast('error', 'Failed to load Meta integration data: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Page Handlers
  const handleConnectNewPage = async (e) => {
    e.preventDefault();
    if (!newPageData.page_id.trim() || !newPageData.access_token.trim()) {
      showToast('error', 'Page ID and Page Access Token are required.');
      return;
    }
    try {
      setAddingPage(true);
      const res = await API.post('/integrations/meta/pages', newPageData);
      if (res.data.success) {
        showToast('success', res.data.message || 'Facebook Page connected successfully!');
        setAddModalOpen(false);
        setNewPageData({ page_id: '', page_name: '', access_token: '' });
        fetchData();
      } else {
        showToast('error', `${res.data.message} ${res.data.error_details ? '(' + res.data.error_details + ')' : ''}`);
      }
    } catch (err) {
      showToast('error', 'Failed to connect page: ' + (err.response?.data?.detail || err.message));
    } finally {
      setAddingPage(false);
    }
  };

  const handleSyncPage = async (pageId) => {
    try {
      setPageActionLoading(prev => ({ ...prev, [pageId]: 'sync' }));
      const res = await API.post(`/integrations/meta/pages/${pageId}/sync`);
      if (res.data.success) {
        showToast('success', res.data.message);
      } else {
        showToast('error', `${res.data.message} ${res.data.error_details ? '(' + res.data.error_details + ')' : ''}`);
      }
      fetchData();
    } catch (err) {
      showToast('error', 'Sync failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setPageActionLoading(prev => ({ ...prev, [pageId]: null }));
    }
  };

  const handleToggleStatus = async (page) => {
    const isConnected = page.status === 'CONNECTED';
    const action = isConnected ? 'disconnect' : 'connect';
    try {
      setPageActionLoading(prev => ({ ...prev, [page.page_id]: action }));
      await API.post(`/integrations/meta/pages/${page.page_id}/${action}`);
      showToast('success', `Page '${page.page_name}' ${isConnected ? 'disconnected' : 'connected'}.`);
      fetchData();
    } catch (err) {
      showToast('error', `Failed to ${action} page: ` + (err.response?.data?.detail || err.message));
    } finally {
      setPageActionLoading(prev => ({ ...prev, [page.page_id]: null }));
    }
  };

  const handleRefreshPage = async (e) => {
    e.preventDefault();
    if (!refreshModal.newAccessToken.trim()) {
      showToast('error', 'Please provide the new Page Access Token.');
      return;
    }
    try {
      setRefreshingPage(true);
      const res = await API.post(`/integrations/meta/pages/${refreshModal.page.page_id}/refresh`, {
        access_token: refreshModal.newAccessToken.trim()
      });
      if (res.data.success) {
        showToast('success', res.data.message);
        setRefreshModal({ isOpen: false, page: null, newAccessToken: '' });
        fetchData();
      } else {
        showToast('error', `${res.data.message} ${res.data.error_details ? '(' + res.data.error_details + ')' : ''}`);
      }
    } catch (err) {
      showToast('error', 'Token refresh failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setRefreshingPage(false);
    }
  };

  const handleDeletePage = async (pageId, pageName) => {
    if (!window.confirm(`Are you sure you want to remove the connected Facebook Page '${pageName}' (ID: ${pageId})? Leads captured for this page will remain in CRM, but future webhook leads from this page will be paused.`)) {
      return;
    }
    try {
      setPageActionLoading(prev => ({ ...prev, [pageId]: 'delete' }));
      await API.delete(`/integrations/meta/pages/${pageId}`);
      showToast('success', `Facebook Page '${pageName}' removed.`);
      fetchData();
    } catch (err) {
      showToast('error', 'Failed to remove page: ' + (err.response?.data?.detail || err.message));
    } finally {
      setPageActionLoading(prev => ({ ...prev, [pageId]: null }));
    }
  };

  const webhookUrl = `${window.location.origin}/api/integrations/meta/webhook`;
  const verifyToken = 'wacrm_meta_verify_secret';
  const totalLeads = pages.reduce((sum, p) => sum + (p.lead_count || 0), 0) || (metaStatus?.total_meta_leads || 0);
  const activeCount = pages.filter(p => p.status === 'CONNECTED').length;

  return (
    <div className="meta-page-wrapper">
      {/* Toast Alert */}
      {toast && (
        <div 
          style={{ 
            position: 'fixed', 
            top: '20px', 
            right: '20px', 
            zIndex: 3000, 
            maxWidth: '460px',
            backgroundColor: toast.type === 'success' ? '#ecfdf5' : '#fef2f2',
            color: toast.type === 'success' ? '#065f46' : '#991b1b',
            border: `1px solid ${toast.type === 'success' ? '#a7f3d0' : '#fecaca'}`,
            borderRadius: '12px',
            padding: '14px 18px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            fontWeight: 600,
            fontSize: '0.88rem'
          }}
        >
          {toast.type === 'success' ? <CheckCircle2 size={20} color="#059669" /> : <AlertTriangle size={20} color="#dc2626" />}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Header with Navigation */}
      <div className="meta-page-header">
        <div>
          <div className="meta-breadcrumb">
            <Link to="/settings/integrations">
              <ArrowLeft size={14} /> Back to Integration Hub
            </Link>
            <span>/</span>
            <span>Meta Ads Integration</span>
          </div>

          <div className="meta-title-group">
            <div className="meta-header-icon">
              <Share2 size={28} />
            </div>
            <div>
              <h1 className="meta-page-title">Meta Ads Integration Hub</h1>
              <p className="meta-page-subtitle">
                Manage connected Facebook & Instagram Pages, encrypted Page Access Tokens, and webhook ingestion.
              </p>
            </div>
          </div>
        </div>

        <div className="meta-header-actions">
          <button 
            type="button" 
            className="btn-meta-outline"
            onClick={fetchData}
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>

          <button 
            type="button" 
            className="btn-meta-primary"
            onClick={() => setAddModalOpen(true)}
          >
            <Plus size={16} />
            <span>Connect Facebook Page</span>
          </button>
        </div>
      </div>

      {/* 4 Summary Metric Cards */}
      <div className="meta-metrics-grid">
        <div className="meta-metric-card">
          <div className="meta-metric-icon blue">
            <Layers size={18} />
          </div>
          <div className="meta-metric-content">
            <h4>Connected Pages</h4>
            <p>{pages.length} {pages.length === 1 ? 'Page' : 'Pages'} ({activeCount} Active)</p>
          </div>
        </div>

        <div className="meta-metric-card">
          <div className="meta-metric-icon emerald">
            <Zap size={18} />
          </div>
          <div className="meta-metric-content">
            <h4>Total Leads Captured</h4>
            <p>{totalLeads} Leads</p>
          </div>
        </div>

        <div className="meta-metric-card">
          <div className="meta-metric-icon purple">
            <ShieldCheck size={18} />
          </div>
          <div className="meta-metric-content">
            <h4>Webhook Status</h4>
            <p>{metaStatus?.configured ? '🟢 Active & Listening' : '⚪ Setup Ready'}</p>
          </div>
        </div>

        <div className="meta-metric-card">
          <div className="meta-metric-icon amber">
            <Globe size={18} />
          </div>
          <div className="meta-metric-content">
            <h4>Graph API Version</h4>
            <p>{metaStatus?.api_version || 'v20.0'}</p>
          </div>
        </div>
      </div>

      <div className="meta-layout-main">
        {/* Section 1: Connected Facebook Pages */}
        <div className="meta-section-card">
          <div className="meta-section-header">
            <div className="meta-section-title-wrap">
              <h2 className="meta-section-title">Connected Facebook Pages</h2>
              <span className="meta-badge-count">{pages.length} {pages.length === 1 ? 'Page' : 'Pages'}</span>
            </div>

            <button 
              type="button" 
              className="btn-meta-primary" 
              style={{ padding: '8px 16px', fontSize: '0.82rem' }}
              onClick={() => setAddModalOpen(true)}
            >
              <Plus size={15} />
              <span>Add Another Page</span>
            </button>
          </div>

          {pages.length === 0 ? (
            <div className="meta-empty-state">
              <div className="meta-empty-icon">
                <Share2 size={28} />
              </div>
              <h3>No Facebook Pages Connected Yet</h3>
              <p>
                Each Facebook Page requires its own Page Access Token with <code>leads_retrieval</code> permission. 
                Connect your first Page to start ingesting leads automatically.
              </p>
              <button 
                type="button" 
                className="btn-meta-primary"
                onClick={() => setAddModalOpen(true)}
              >
                <Plus size={16} />
                <span>Connect Your First Facebook Page</span>
              </button>
            </div>
          ) : (
            <div className="meta-pages-grid">
              {pages.map((p) => {
                const isActioning = pageActionLoading[p.page_id];
                return (
                  <div key={p.page_id} className="meta-page-card">
                    <div>
                      <div className="meta-card-top">
                        <div className="meta-card-name-group">
                          <div className="meta-page-avatar">
                            {p.page_name ? p.page_name.charAt(0).toUpperCase() : 'F'}
                          </div>
                          <div>
                            <h3 className="meta-page-card-title">{p.page_name}</h3>
                            <div className="meta-page-id-badge">
                              <span>Page ID: {p.page_id}</span>
                              <button 
                                className="meta-btn-copy-mini"
                                onClick={() => handleCopy(p.page_id, p.page_id)}
                                title="Copy Page ID"
                              >
                                {copiedField === p.page_id ? <Check size={12} style={{ color: '#10b981' }} /> : <Copy size={12} />}
                              </button>
                            </div>
                          </div>
                        </div>

                        <span className={`status-badge ${p.status.toLowerCase()}`}>
                          {p.status === 'CONNECTED' && '🟢 Connected'}
                          {p.status === 'DISCONNECTED' && '⚪ Disconnected'}
                          {p.status === 'ERROR' && '🔴 Error'}
                        </span>
                      </div>

                      {p.error_message && (
                        <div className="meta-card-error" style={{ marginTop: '12px' }}>
                          <AlertTriangle size={15} />
                          <span>{p.error_message}</span>
                        </div>
                      )}

                      <div className="meta-card-stats" style={{ marginTop: '14px' }}>
                        <div className="meta-stat-item">
                          <span className="meta-stat-label">Leads Received</span>
                          <span className="meta-stat-val" style={{ color: '#059669', fontSize: '1.05rem' }}>
                            {p.lead_count || 0}
                          </span>
                        </div>

                        <div className="meta-stat-item">
                          <span className="meta-stat-label">Page Token</span>
                          <span className="meta-token-preview">{p.masked_token}</span>
                        </div>

                        <div className="meta-stat-item">
                          <span className="meta-stat-label">Last Synced</span>
                          <span className="meta-stat-val" style={{ fontSize: '0.8rem', color: '#475569' }}>
                            {p.last_synced_at ? new Date(p.last_synced_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' }) : 'Never'}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="meta-card-actions">
                      <button
                        type="button"
                        className="btn-card-action"
                        onClick={() => handleSyncPage(p.page_id)}
                        disabled={Boolean(isActioning)}
                        title="Sync & verify this Page token with Meta Graph API"
                      >
                        <RefreshCw size={13} className={isActioning === 'sync' ? 'spin' : ''} />
                        <span>{isActioning === 'sync' ? 'Syncing...' : 'Sync'}</span>
                      </button>

                      <button
                        type="button"
                        className={`btn-card-action ${p.status === 'CONNECTED' ? 'disconnect' : 'connect'}`}
                        onClick={() => handleToggleStatus(p)}
                        disabled={Boolean(isActioning)}
                        title={p.status === 'CONNECTED' ? 'Pause lead ingestion for this Page' : 'Resume lead ingestion for this Page'}
                      >
                        <Power size={13} />
                        <span>{p.status === 'CONNECTED' ? 'Disconnect' : 'Connect'}</span>
                      </button>

                      <button
                        type="button"
                        className="btn-card-action"
                        onClick={() => {
                          setShowSecrets({});
                          setRefreshModal({ isOpen: true, page: p, newAccessToken: '' });
                        }}
                        disabled={Boolean(isActioning)}
                        title="Update Page Access Token"
                      >
                        <Key size={13} />
                        <span>Refresh Token</span>
                      </button>

                      <button
                        type="button"
                        className="btn-card-action danger"
                        onClick={() => handleDeletePage(p.page_id, p.page_name)}
                        disabled={Boolean(isActioning)}
                        title="Remove this Facebook Page from CRM"
                      >
                        <Trash2 size={13} />
                        <span>Remove</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Section 2: Bottom Grid (Webhook Configuration & Step Guide) */}
        <div className="meta-bottom-grid">
          {/* Card: Webhook Configuration */}
          <div className="meta-section-card">
            <div className="meta-section-header">
              <div className="meta-section-title-wrap">
                <Zap size={20} style={{ color: '#1877f2' }} />
                <h3 className="meta-section-title">Webhook Configuration</h3>
              </div>
            </div>

            <div className="meta-setup-field">
              <label className="meta-setup-label">Callback URL (Webhook Endpoint)</label>
              <div className="meta-input-group">
                <input type="text" readOnly value={webhookUrl} />
                <button 
                  type="button" 
                  className="meta-btn-copy"
                  onClick={() => handleCopy(webhookUrl, 'webhookUrl')}
                >
                  {copiedField === 'webhookUrl' ? <Check size={14} style={{ color: '#10b981' }} /> : <Copy size={14} />}
                  <span>{copiedField === 'webhookUrl' ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            <div className="meta-setup-field">
              <label className="meta-setup-label">Verify Token (hub.verify_token)</label>
              <div className="meta-input-group">
                <input type="text" readOnly value={verifyToken} />
                <button 
                  type="button" 
                  className="meta-btn-copy"
                  onClick={() => handleCopy(verifyToken, 'verifyToken')}
                >
                  {copiedField === 'verifyToken' ? <Check size={14} style={{ color: '#10b981' }} /> : <Copy size={14} />}
                  <span>{copiedField === 'verifyToken' ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '12px', border: '1px solid #e2e8f0', marginTop: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Webhook Object Type</span>
                <strong style={{ fontSize: '0.82rem', color: '#0f172a' }}>page</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Subscribed Field</span>
                <strong style={{ fontSize: '0.82rem', color: '#1877f2' }}>leadgen</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Last Ingested Webhook</span>
                <strong style={{ fontSize: '0.82rem', color: '#0f172a' }}>
                  {metaStatus?.last_webhook_received ? new Date(metaStatus.last_webhook_received).toLocaleString() : 'Ready & Listening'}
                </strong>
              </div>
            </div>
          </div>

          {/* Card: Setup Instructions Guide */}
          <div className="meta-section-card">
            <div className="meta-section-header">
              <div className="meta-section-title-wrap">
                <HelpCircle size={20} style={{ color: '#1877f2' }} />
                <h3 className="meta-section-title">Setup Instructions</h3>
              </div>
              <a 
                href="https://developers.facebook.com/apps" 
                target="_blank" 
                rel="noreferrer"
                className="meta-breadcrumb" 
                style={{ margin: 0, textDecoration: 'none', color: '#1877f2', fontWeight: 600, fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                Meta Developer App <ExternalLink size={13} />
              </a>
            </div>

            <div className="meta-step-item">
              <span className="meta-step-num">1</span>
              <div className="meta-step-body">
                <h4>Configure Webhooks in Meta Developer Portal</h4>
                <p>Go to your Meta App &gt; <strong>Webhooks</strong> &gt; Select <strong>Page</strong> object &gt; Subscribe to the <code>leadgen</code> field using the Callback URL and Verify Token above.</p>
              </div>
            </div>

            <div className="meta-step-item">
              <span className="meta-step-num">2</span>
              <div className="meta-step-body">
                <h4>Generate Page Access Tokens</h4>
                <p>For every Facebook Page running Lead Ads, generate a Page Access Token with <code>leads_retrieval</code> and <code>pages_manage_ads</code> permissions.</p>
              </div>
            </div>

            <div className="meta-step-item">
              <span className="meta-step-num">3</span>
              <div className="meta-step-body">
                <h4>Connect Pages in this Hub</h4>
                <p>Click <strong>"+ Connect Facebook Page"</strong> and paste each Page's ID and token. WaCRM encrypts every token at rest and automatically routes leads to the correct page.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Modal: Connect Facebook Page */}
      {addModalOpen && (
        <div className="modal-overlay" onClick={() => setAddModalOpen(false)}>
          <div className="modal-content" style={{ maxWidth: '540px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>Connect Facebook Page</h3>
                <span style={{ fontSize: '0.82rem', color: '#64748b' }}>
                  Each Page is configured with its own encrypted Page Access Token.
                </span>
              </div>
              <button className="modal-close-btn" onClick={() => setAddModalOpen(false)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleConnectNewPage}>
              <div className="modal-body">
                <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '10px', padding: '12px 14px', marginBottom: '18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, color: '#1d4ed8', fontSize: '0.84rem', marginBottom: '4px' }}>
                    <Layers size={16} /> Multi-Page Isolation
                  </div>
                  <p style={{ fontSize: '0.8rem', color: '#1e40af', margin: 0 }}>
                    When a lead arrives via webhook, WaCRM identifies the Facebook Page ID and retrieves the lead details using that specific Page's access token.
                  </p>
                </div>

                <div className="form-group">
                  <label>Facebook Page ID <span style={{ color: '#ef4444' }}>*</span></label>
                  <input 
                    type="text" 
                    required
                    value={newPageData.page_id} 
                    onChange={(e) => setNewPageData(prev => ({ ...prev, page_id: e.target.value }))}
                    placeholder="e.g. 1320343594494609"
                  />
                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                    Found in Facebook Page &gt; Settings &gt; Page Setup &gt; Page ID.
                  </span>
                </div>

                <div className="form-group">
                  <label>Page Name</label>
                  <input 
                    type="text" 
                    value={newPageData.page_name} 
                    onChange={(e) => setNewPageData(prev => ({ ...prev, page_name: e.target.value }))}
                    placeholder="e.g. Acme Realty Official (optional, auto-detected from Meta)"
                  />
                </div>

                <div className="form-group">
                  <label>Page Access Token (Encrypted) <span style={{ color: '#ef4444' }}>*</span></label>
                  <div className="secret-input-wrapper">
                    <input 
                      type={showSecrets.newPageToken ? 'text' : 'password'} 
                      required
                      value={newPageData.access_token} 
                      onChange={(e) => setNewPageData(prev => ({ ...prev, access_token: e.target.value }))}
                      placeholder="EAABb..."
                    />
                    <button type="button" className="toggle-secret-btn" onClick={() => toggleSecret('newPageToken')}>
                      {showSecrets.newPageToken ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                    Requires <code>leads_retrieval</code> and <code>pages_manage_ads</code> permissions.
                  </span>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn-hub btn-hub-outline" onClick={() => setAddModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-meta-primary" disabled={addingPage}>
                  {addingPage ? <RefreshCw size={15} className="spin" /> : <CheckCircle2 size={15} />}
                  <span>{addingPage ? 'Verifying & Saving...' : 'Verify & Connect Page'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Refresh Page Access Token */}
      {refreshModal.isOpen && (
        <div className="modal-overlay" onClick={() => setRefreshModal({ isOpen: false, page: null, newAccessToken: '' })}>
          <div className="modal-content" style={{ maxWidth: '520px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>Refresh Page Access Token</h3>
                <span style={{ fontSize: '0.82rem', color: '#64748b' }}>
                  {refreshModal.page?.page_name} (Page ID: {refreshModal.page?.page_id})
                </span>
              </div>
              <button className="modal-close-btn" onClick={() => setRefreshModal({ isOpen: false, page: null, newAccessToken: '' })}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleRefreshPage}>
              <div className="modal-body">
                <p style={{ fontSize: '0.86rem', color: '#475569', marginBottom: '16px' }}>
                  Paste the updated Page Access Token below if it expired or was regenerated. It will be encrypted and validated against Meta Graph API.
                </p>

                <div className="form-group">
                  <label>New Page Access Token <span style={{ color: '#ef4444' }}>*</span></label>
                  <div className="secret-input-wrapper">
                    <input 
                      type={showSecrets.refreshToken ? 'text' : 'password'} 
                      required
                      value={refreshModal.newAccessToken} 
                      onChange={(e) => setRefreshModal(prev => ({ ...prev, newAccessToken: e.target.value }))}
                      placeholder="EAABb..."
                    />
                    <button type="button" className="toggle-secret-btn" onClick={() => toggleSecret('refreshToken')}>
                      {showSecrets.refreshToken ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button 
                  type="button" 
                  className="btn-hub btn-hub-outline" 
                  onClick={() => setRefreshModal({ isOpen: false, page: null, newAccessToken: '' })}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-meta-primary" disabled={refreshingPage}>
                  {refreshingPage ? <RefreshCw size={15} className="spin" /> : <RefreshCw size={15} />}
                  <span>{refreshingPage ? 'Updating & Verifying...' : 'Update & Verify Token'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default MetaIntegrationPage;
