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
  const [testingRecordingApi, setTestingRecordingApi] = useState(false);
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

  // WebRTC Extension to Employee Mapping State
  const [employeesList, setEmployeesList] = useState([]);
  const [mappingSaving, setMappingSaving] = useState(false);
  const [newMapping, setNewMapping] = useState({
    extension: '',
    account_type: 'Agent',
    employee_id: '',
    did_number: '',
    is_active: true
  });

  const fetchEmployees = async () => {
    try {
      const res = await API.get('/employees');
      const items = Array.isArray(res.data) ? res.data : (res.data?.items || []);
      setEmployeesList(items);
    } catch (err) {
      console.warn('Failed to fetch employees list for WebRTC mapping:', err);
    }
  };

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
    fetchEmployees();
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
      // Always fetch employee directory
      fetchEmployees();
      // Fetch latest live extension mapping from backend and sync into modal state
      API.get('/doocti/config').then(res => {
        if (res.data) {
          setModalState(prev => ({
            ...prev,
            config: {
              ...prev.config,
              api_url: res.data.api_url || prev.config.api_url || '',
              account_id: res.data.account_id || prev.config.account_id || '',
              portal_url: res.data.portal_url || prev.config.portal_url || '',
              recording_api_configured: Boolean(res.data.recording_api_configured),
              extension_mapping: res.data.extension_mapping || prev.config.extension_mapping || {},
              admin_extension: res.data.admin_extension || prev.config.admin_extension || '',
              agent_extensions: res.data.agent_extensions || prev.config.agent_extensions || []
            }
          }));
        }
      }).catch((err) => {
        console.warn('Could not sync /doocti/config:', err);
      });
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
    setNewMapping({ extension: '', account_type: 'Agent', employee_id: '', did_number: '', is_active: true });
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

  const handleAddExtensionMapping = async () => {
    const ext = String(newMapping.extension || '').trim();
    if (!ext) {
      showToast('error', 'Please enter a WebRTC Extension number (e.g. 101, 102).');
      return;
    }
    if (!newMapping.employee_id) {
      showToast('error', 'Please select a CRM Employee.');
      return;
    }
    if (!newMapping.did_number) {
      showToast('error', 'Please select an Assigned Outbound DID number.');
      return;
    }
    const emp = employeesList.find(e => String(e.id) === String(newMapping.employee_id));
    if (!emp) {
      showToast('error', 'Selected employee not found in employee directory.');
      return;
    }

    const currentMap = { ...(modalState.config?.extension_mapping || {}) };

    // Prevent duplicate mapping of same employee to multiple different extensions unless intended
    const existingExtForEmp = Object.entries(currentMap).find(([k, v]) => String(v.employee_id) === String(emp.id) && k !== ext);
    if (existingExtForEmp) {
      showToast('warning', `Employee ${emp.name} is already assigned to extension ${existingExtForEmp[0]}. Re-assigning to ${ext}.`);
      delete currentMap[existingExtForEmp[0]];
    }

    currentMap[ext] = {
      employee_id: emp.id,
      username: emp.username || '',
      name: emp.name || '',
      role: emp.role || '',
      type: newMapping.account_type.toUpperCase(),
      did_number: String(newMapping.did_number).trim(),
      is_active: newMapping.is_active !== false
    };

    const adminExts = Object.keys(currentMap).filter(k => (currentMap[k].type || '').toUpperCase() === 'ADMIN');
    const agentExts = Object.keys(currentMap).filter(k => (currentMap[k].type || '').toUpperCase() === 'AGENT');

    const updatedConfig = {
      ...modalState.config,
      extension_mapping: currentMap,
      admin_extension: adminExts.join(', ') || modalState.config?.admin_extension || '',
      extensions: agentExts.join(', ') || modalState.config?.extensions || '',
      agent_extensions: agentExts
    };

    setModalState(prev => ({
      ...prev,
      config: updatedConfig
    }));

    setNewMapping({
      extension: '',
      account_type: 'Agent',
      employee_id: '',
      did_number: '',
      is_active: true
    });

    // Auto-save immediately to database so refresh won't lose changes
    try {
      setMappingSaving(true);
      if (modalState.type) {
        await API.post(`/integrations/hub/${modalState.type}/configure`, {
          integration_type: modalState.type,
          config_data: updatedConfig
        });
      }
      if (modalState.type === 'IVR' && (modalState.config?.provider === 'DOOCTI' || updatedConfig.provider === 'DOOCTI')) {
        await API.put('/doocti/config', {
          extension_mapping: currentMap,
          admin_extension: updatedConfig.admin_extension,
          agent_extensions: agentExts,
          did_numbers: typeof updatedConfig.phone_number === 'string' ? updatedConfig.phone_number.split(',').map(s => s.trim()) : updatedConfig.did_numbers,
          api_url: updatedConfig.api_url,
          account_id: updatedConfig.account_id
        });
      }
      fetchStatus();
      showToast('success', `Extension ${ext} assigned to ${emp.name} (DID: ${newMapping.did_number}) and saved!`);
    } catch (saveErr) {
      console.error('Failed to auto-save extension mapping:', saveErr);
      showToast('warning', `Extension ${ext} assigned locally. Please click "Save Configuration" below.`);
    } finally {
      setMappingSaving(false);
    }
  };

  const handleToggleExtensionStatus = async (ext) => {
    const currentMap = { ...(modalState.config?.extension_mapping || {}) };
    if (!currentMap[ext]) return;
    const currentActive = currentMap[ext].is_active !== false;
    currentMap[ext] = {
      ...currentMap[ext],
      is_active: !currentActive
    };

    const adminExts = Object.keys(currentMap).filter(k => (currentMap[k].type || '').toUpperCase() === 'ADMIN');
    const agentExts = Object.keys(currentMap).filter(k => (currentMap[k].type || '').toUpperCase() === 'AGENT');

    const updatedConfig = {
      ...modalState.config,
      extension_mapping: currentMap,
      admin_extension: adminExts.join(', ') || modalState.config?.admin_extension || '',
      extensions: agentExts.join(', ') || modalState.config?.extensions || '',
      agent_extensions: agentExts
    };

    setModalState(prev => ({
      ...prev,
      config: updatedConfig
    }));

    try {
      setMappingSaving(true);
      if (modalState.type) {
        await API.post(`/integrations/hub/${modalState.type}/configure`, {
          integration_type: modalState.type,
          config_data: updatedConfig
        });
      }
      if (modalState.type === 'IVR') {
        await API.put('/doocti/config', {
          extension_mapping: currentMap,
          admin_extension: updatedConfig.admin_extension,
          agent_extensions: agentExts,
          did_numbers: typeof updatedConfig.phone_number === 'string' ? updatedConfig.phone_number.split(',').map(s => s.trim()) : updatedConfig.did_numbers,
          api_url: updatedConfig.api_url,
          account_id: updatedConfig.account_id
        });
      }
      fetchStatus();
      showToast('success', `Extension ${ext} is now ${!currentActive ? 'Active' : 'Inactive'}.`);
    } catch (saveErr) {
      console.error('Failed to toggle extension status:', saveErr);
      showToast('error', 'Failed to update status in database.');
    } finally {
      setMappingSaving(false);
    }
  };

  const handleUpdateExtensionDid = async (ext, newDid) => {
    const currentMap = { ...(modalState.config?.extension_mapping || {}) };
    if (!currentMap[ext]) return;
    currentMap[ext] = {
      ...currentMap[ext],
      did_number: String(newDid).trim()
    };

    const adminExts = Object.keys(currentMap).filter(k => (currentMap[k].type || '').toUpperCase() === 'ADMIN');
    const agentExts = Object.keys(currentMap).filter(k => (currentMap[k].type || '').toUpperCase() === 'AGENT');

    const updatedConfig = {
      ...modalState.config,
      extension_mapping: currentMap,
      admin_extension: adminExts.join(', ') || modalState.config?.admin_extension || '',
      extensions: agentExts.join(', ') || modalState.config?.extensions || '',
      agent_extensions: agentExts
    };

    setModalState(prev => ({
      ...prev,
      config: updatedConfig
    }));

    try {
      setMappingSaving(true);
      if (modalState.type) {
        await API.post(`/integrations/hub/${modalState.type}/configure`, {
          integration_type: modalState.type,
          config_data: updatedConfig
        });
      }
      if (modalState.type === 'IVR') {
        await API.put('/doocti/config', {
          extension_mapping: currentMap,
          admin_extension: updatedConfig.admin_extension,
          agent_extensions: agentExts,
          did_numbers: typeof updatedConfig.phone_number === 'string' ? updatedConfig.phone_number.split(',').map(s => s.trim()) : updatedConfig.did_numbers,
          api_url: updatedConfig.api_url,
          account_id: updatedConfig.account_id
        });
      }
      fetchStatus();
      showToast('success', `DID for Extension ${ext} updated to ${newDid}.`);
    } catch (saveErr) {
      console.error('Failed to update extension DID:', saveErr);
      showToast('error', 'Failed to update DID in database.');
    } finally {
      setMappingSaving(false);
    }
  };

  const handleRemoveExtensionMapping = async (extToRemove) => {
    const currentMap = { ...(modalState.config?.extension_mapping || {}) };
    delete currentMap[extToRemove];

    const adminExts = Object.keys(currentMap).filter(k => (currentMap[k].type || '').toUpperCase() === 'ADMIN');
    const agentExts = Object.keys(currentMap).filter(k => (currentMap[k].type || '').toUpperCase() === 'AGENT');

    const updatedConfig = {
      ...modalState.config,
      extension_mapping: currentMap,
      admin_extension: adminExts.join(', ') || '',
      extensions: agentExts.join(', ') || '',
      agent_extensions: agentExts
    };

    setModalState(prev => ({
      ...prev,
      config: updatedConfig
    }));

    // Auto-save immediately to database so refresh won't lose changes
    try {
      setMappingSaving(true);
      if (modalState.type) {
        await API.post(`/integrations/hub/${modalState.type}/configure`, {
          integration_type: modalState.type,
          config_data: updatedConfig
        });
      }
      if (modalState.type === 'IVR' && (modalState.config?.provider === 'DOOCTI' || updatedConfig.provider === 'DOOCTI')) {
        await API.put('/doocti/config', {
          extension_mapping: currentMap,
          admin_extension: updatedConfig.admin_extension,
          agent_extensions: agentExts,
          did_numbers: typeof updatedConfig.phone_number === 'string' ? updatedConfig.phone_number.split(',').map(s => s.trim()) : updatedConfig.did_numbers,
          api_url: updatedConfig.api_url,
          account_id: updatedConfig.account_id
        });
      }
      fetchStatus();
      showToast('info', `Extension ${extToRemove} removed and saved.`);
    } catch (saveErr) {
      console.error('Failed to auto-save extension removal:', saveErr);
      showToast('warning', `Extension ${extToRemove} removed locally. Please click "Save Configuration" below.`);
    } finally {
      setMappingSaving(false);
    }
  };

  const handleIvrProviderChange = (newProvider) => {
    setModalState(prev => {
      const prevConfig = prev.config || {};
      let updatedConfig = { ...prevConfig, provider: newProvider };
      if (newProvider === 'DOOCTI') {
        fetchEmployees();
        API.get('/doocti/config').then(res => {
          if (res.data) {
            setModalState(curr => ({
              ...curr,
              config: {
                ...curr.config,
                api_url: res.data.api_url || curr.config.api_url || '',
                account_id: res.data.account_id || curr.config.account_id || '',
                portal_url: res.data.portal_url || curr.config.portal_url || '',
                recording_api_configured: Boolean(res.data.recording_api_configured),
                extension_mapping: res.data.extension_mapping || curr.config.extension_mapping || {}
              }
            }));
          }
        }).catch(() => {});
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

  const handleTestRecordingApi = async () => {
    try {
      setTestingRecordingApi(true);
      // Save the fields first so the test uses what is on screen.
      await API.put('/doocti/config', {
        portal_url: modalState.config.portal_url,
        recording_api_url: modalState.config.recording_api_url,
        recording_api_username: modalState.config.recording_api_username,
        recording_api_password: modalState.config.recording_api_password,
        recording_api_token: modalState.config.recording_api_token
      });
      const res = await API.get('/doocti/recording-status');
      if (res.data?.login_ok) {
        const tenant = res.data?.tenant_code ? ` (tenant: ${res.data.tenant_code})` : '';
        showToast('success', `DooCTI recording API connected${tenant}.`);
      } else {
        showToast('error', res.data?.message || 'DooCTI recording API is not connected.');
      }
    } catch (err) {
      showToast('error', `Recording API test failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setTestingRecordingApi(false);
    }
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

      // Synchronize with /api/doocti/config if type is IVR and provider is DOOCTI
      if (modalState.type === 'IVR' && modalState.config?.provider === 'DOOCTI') {
        try {
          await API.put('/doocti/config', {
            extension_mapping: modalState.config.extension_mapping || {},
            admin_extension: modalState.config.admin_extension,
            agent_extensions: modalState.config.agent_extensions || (typeof modalState.config.extensions === 'string' ? modalState.config.extensions.split(',').map(s => s.trim()) : modalState.config.extensions),
            did_numbers: typeof modalState.config.phone_number === 'string' ? modalState.config.phone_number.split(',').map(s => s.trim()) : modalState.config.did_numbers,
            api_url: modalState.config.api_url,
            account_id: modalState.config.account_id,
            portal_url: modalState.config.portal_url,
            recording_api_url: modalState.config.recording_api_url,
            recording_api_username: modalState.config.recording_api_username,
            recording_api_password: modalState.config.recording_api_password,
            recording_api_token: modalState.config.recording_api_token
          });
        } catch (subErr) {
          console.warn('Secondary Doocti config sync notice:', subErr);
        }
      }

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
          <div className={`modal-content ${modalState.type === 'IVR' ? 'modal-content-wide' : ''}`} style={modalState.type === 'IVR' ? { maxWidth: '880px' } : {}} onClick={(e) => e.stopPropagation()}>
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
                          <label>Doocti In-App WebRTC Domain (WebPhone URL)</label>
                          <input 
                            type="text" 
                            value={modalState.config.api_url || ''} 
                            onChange={(e) => handleConfigChange('api_url', e.target.value)}
                            placeholder="e.g. https://beta3-app.doocti.com/"
                          />
                        </div>

                        <div className="form-group">
                          <label>Tenant ID / Organization Name</label>
                          <input 
                            type="text" 
                            value={modalState.config.account_id || ''} 
                            onChange={(e) => handleConfigChange('account_id', e.target.value)}
                            placeholder="e.g. chntechnolog"
                          />
                        </div>

                        {/* Optional DooCTI recording API (used when a call has no usable audio in storage) */}
                        <div style={{ marginTop: '18px', borderTop: '1px solid #e2e8f0', paddingTop: '16px', marginBottom: '16px' }}>
                          <h4 style={{ fontSize: '0.9rem', fontWeight: '700', color: '#0f172a', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <PhoneCall size={15} style={{ color: '#2563eb' }} />
                            <span>Doocti Recording API (Optional)</span>
                          </h4>
                          <p style={{ fontSize: '0.75rem', color: '#64748b', margin: '0 0 12px 0' }}>
                            Some calls have no playable audio file in cloud storage. When these portal credentials
                            are set, WA!CRM asks DooCTI for the recording of that exact call ID instead.
                          </p>

                          <div className="form-group">
                            <label>Portal API Base URL</label>
                            <input
                              type="text"
                              value={modalState.config.recording_api_url || ''}
                              onChange={(e) => handleConfigChange('recording_api_url', e.target.value)}
                              placeholder="https://api-v2.doocti.com"
                            />
                          </div>

                          <div className="form-group">
                            <label>Tenant Portal URL (Optional)</label>
                            <input
                              type="text"
                              value={modalState.config.portal_url || ''}
                              onChange={(e) => handleConfigChange('portal_url', e.target.value)}
                              placeholder="Leave blank to detect from the login response"
                            />
                          </div>

                          <div className="form-group">
                            <label>Doocti Username</label>
                            <input
                              type="text"
                              value={modalState.config.recording_api_username || ''}
                              onChange={(e) => handleConfigChange('recording_api_username', e.target.value)}
                              placeholder="Your DooCTI portal login (agent/admin)"
                              autoComplete="off"
                            />
                          </div>

                          <div className="form-group">
                            <label>Doocti Password</label>
                            <div className="secret-input-wrapper">
                              <input
                                type={showSecrets.recording_api_password ? 'text' : 'password'}
                                value={modalState.config.recording_api_password || ''}
                                onChange={(e) => handleConfigChange('recording_api_password', e.target.value)}
                                placeholder="Stored securely; leave unchanged to keep the saved password"
                                autoComplete="new-password"
                              />
                              <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('recording_api_password')}>
                                {showSecrets.recording_api_password ? <EyeOff size={16} /> : <Eye size={16} />}
                              </button>
                            </div>
                          </div>

                          <div className="form-group">
                            <label>Access Token (Alternative to Username / Password)</label>
                            <div className="secret-input-wrapper">
                              <input
                                type={showSecrets.recording_api_token ? 'text' : 'password'}
                                value={modalState.config.recording_api_token || ''}
                                onChange={(e) => handleConfigChange('recording_api_token', e.target.value)}
                                placeholder="Optional pre-issued Bearer token"
                                autoComplete="new-password"
                              />
                              <button type="button" className="toggle-secret-btn" onClick={() => toggleSecretVisibility('recording_api_token')}>
                                {showSecrets.recording_api_token ? <EyeOff size={16} /> : <Eye size={16} />}
                              </button>
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginTop: '4px' }}>
                            <button
                              type="button"
                              onClick={handleTestRecordingApi}
                              disabled={testingRecordingApi}
                              style={{
                                padding: '7px 14px',
                                borderRadius: '8px',
                                border: '1px solid #bfdbfe',
                                backgroundColor: '#eff6ff',
                                color: '#1d4ed8',
                                fontSize: '0.78rem',
                                fontWeight: '600',
                                cursor: testingRecordingApi ? 'wait' : 'pointer'
                              }}
                            >
                              {testingRecordingApi ? 'Testing…' : 'Test Recording API'}
                            </button>
                            {modalState.config.recording_api_configured ? (
                              <span style={{ fontSize: '0.75rem', color: '#065f46' }}>
                                Recording API is configured. Missing call audio is resolved automatically.
                              </span>
                            ) : null}
                          </div>
                        </div>

                        <div className="form-group">
                          <label>DID Numbers (Comma-separated Virtual / Caller ID Numbers)</label>
                          <input 
                            type="text" 
                            value={modalState.config.phone_number || ''} 
                            onChange={(e) => handleConfigChange('phone_number', e.target.value)}
                            placeholder="e.g. Enter provider DID numbers separated by commas"
                          />
                          <small style={{ color: '#64748b', fontSize: '0.74rem' }}>
                            {modalState.config.phone_number 
                              ? `Configured DIDs: ${modalState.config.phone_number}`
                              : 'No DID numbers entered yet. Enter your Doocti DID numbers above.'}
                          </small>
                        </div>

                        {/* WebRTC Extension to Employee Assignment Table */}
                        <div style={{ marginTop: '20px', borderTop: '1px solid #e2e8f0', paddingTop: '16px', marginBottom: '16px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                            <div>
                              <h4 style={{ fontSize: '0.94rem', fontWeight: '700', color: '#0f172a', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <PhoneCall size={16} style={{ color: '#2563eb' }} />
                                <span>WebRTC Extension Management & Employee Assignment</span>
                              </h4>
                              <p style={{ fontSize: '0.76rem', color: '#64748b', margin: 0 }}>
                                Configure which WebRTC Extension routes to each WA!CRM employee. Inbound and outbound call logs are automatically isolated to the mapped employee.
                              </p>
                            </div>
                            <span style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '4px 10px',
                              backgroundColor: '#ecfdf5',
                              border: '1px solid #a7f3d0',
                              borderRadius: '999px',
                              color: '#065f46',
                              fontSize: '0.72rem',
                              fontWeight: '600'
                            }}>
                              <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10b981', display: 'inline-block' }}></span>
                              {mappingSaving ? 'Saving to Database...' : 'Auto-Saved to Database'}
                            </span>
                          </div>

                          {/* Extensions Table */}
                          <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px', marginBottom: '14px', backgroundColor: '#ffffff' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', textAlign: 'left' }}>
                              <thead>
                                <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569' }}>
                                  <th style={{ padding: '9px 12px', fontWeight: '700' }}>WebRTC Extension</th>
                                  <th style={{ padding: '9px 12px', fontWeight: '700' }}>Account Type</th>
                                  <th style={{ padding: '9px 12px', fontWeight: '700' }}>Employee / Agent</th>
                                  <th style={{ padding: '9px 12px', fontWeight: '700' }}>Assigned Outbound DID</th>
                                  <th style={{ padding: '9px 12px', fontWeight: '700' }}>Status</th>
                                  <th style={{ padding: '9px 12px', fontWeight: '700', textAlign: 'center' }}>Action</th>
                                </tr>
                              </thead>
                              <tbody>
                                {Object.entries(modalState.config?.extension_mapping || {}).length === 0 ? (
                                  <tr>
                                    <td colSpan="6" style={{ padding: '24px', textAlign: 'center', color: '#94a3b8' }}>
                                      No extensions configured yet. Use the form below to assign an extension and DID to an employee.
                                    </td>
                                  </tr>
                                ) : (
                                  Object.entries(modalState.config?.extension_mapping || {}).map(([ext, info]) => {
                                    const isAdmin = (info.type || '').toUpperCase() === 'ADMIN';
                                    const isActive = info.is_active !== false;
                                    const availableDids = (modalState.config?.phone_number || '')
                                      .split(',')
                                      .map(d => d.trim())
                                      .filter(Boolean);
                                    return (
                                      <tr key={ext} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                        <td style={{ padding: '9px 12px', fontWeight: '700', fontFamily: 'monospace', color: '#0f172a' }}>
                                          <span style={{ backgroundColor: '#f1f5f9', border: '1px solid #e2e8f0', padding: '3px 8px', borderRadius: '4px' }}>
                                            {ext}
                                          </span>
                                        </td>
                                        <td style={{ padding: '9px 12px' }}>
                                          <span style={{
                                            padding: '3px 8px',
                                            borderRadius: '999px',
                                            fontSize: '0.72rem',
                                            fontWeight: '700',
                                            backgroundColor: isAdmin ? '#eff6ff' : '#f0fdf4',
                                            color: isAdmin ? '#2563eb' : '#16a34a',
                                            border: `1px solid ${isAdmin ? '#bfdbfe' : '#bbf7d0'}`
                                          }}>
                                            {isAdmin ? 'Admin' : 'Agent'}
                                          </span>
                                        </td>
                                        <td style={{ padding: '9px 12px' }}>
                                          <div style={{ fontWeight: '600', color: '#0f172a' }}>{info.name || 'Unknown'}</div>
                                          <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
                                            {info.username ? `@${info.username}` : ''} • ID: {info.employee_id} • {info.role || 'Staff'}
                                          </div>
                                        </td>
                                        <td style={{ padding: '9px 12px' }}>
                                          <select
                                            value={info.did_number || ''}
                                            onChange={(e) => handleUpdateExtensionDid(ext, e.target.value)}
                                            disabled={mappingSaving}
                                            style={{
                                              padding: '4px 8px',
                                              borderRadius: '6px',
                                              border: '1px solid #cbd5e1',
                                              fontSize: '0.78rem',
                                              fontWeight: '600',
                                              color: info.did_number ? '#0f172a' : '#ef4444',
                                              backgroundColor: '#f8fafc'
                                            }}
                                          >
                                            <option value="">-- No DID Assigned --</option>
                                            {availableDids.map(d => (
                                              <option key={d} value={d}>{d}</option>
                                            ))}
                                          </select>
                                        </td>
                                        <td style={{ padding: '9px 12px' }}>
                                          <button
                                            type="button"
                                            onClick={() => handleToggleExtensionStatus(ext)}
                                            disabled={mappingSaving}
                                            style={{
                                              padding: '3px 9px',
                                              borderRadius: '999px',
                                              fontSize: '0.72rem',
                                              fontWeight: '700',
                                              border: `1px solid ${isActive ? '#bbf7d0' : '#fecaca'}`,
                                              backgroundColor: isActive ? '#f0fdf4' : '#fef2f2',
                                              color: isActive ? '#16a34a' : '#ef4444',
                                              cursor: 'pointer'
                                            }}
                                            title="Click to toggle status"
                                          >
                                            {isActive ? '● Active' : '○ Inactive'}
                                          </button>
                                        </td>
                                        <td style={{ padding: '9px 12px', textAlign: 'center' }}>
                                          <button
                                            type="button"
                                            onClick={() => handleRemoveExtensionMapping(ext)}
                                            disabled={mappingSaving}
                                            style={{
                                              background: 'none',
                                              border: 'none',
                                              color: '#ef4444',
                                              cursor: mappingSaving ? 'not-allowed' : 'pointer',
                                              padding: '4px',
                                              borderRadius: '4px',
                                              opacity: mappingSaving ? 0.5 : 1
                                            }}
                                            title="Delete mapping"
                                          >
                                            <Trash2 size={15} />
                                          </button>
                                        </td>
                                      </tr>
                                    );
                                  })
                                )}
                              </tbody>
                            </table>
                          </div>

                          {/* Add / Map Extension Form */}
                          <div style={{
                            backgroundColor: '#f8fafc',
                            border: '1px solid #e2e8f0',
                            borderRadius: '10px',
                            padding: '12px 14px',
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: '12px',
                            alignItems: 'flex-end'
                          }}>
                            <div style={{ flex: '2', minWidth: '180px' }}>
                              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: '#475569', marginBottom: '4px' }}>
                                Select Employee
                              </label>
                              <select
                                value={newMapping.employee_id}
                                onChange={(e) => setNewMapping(prev => ({ ...prev, employee_id: e.target.value }))}
                                style={{
                                  width: '100%',
                                  padding: '7px 10px',
                                  borderRadius: '6px',
                                  border: '1px solid #cbd5e1',
                                  fontSize: '0.8rem',
                                  backgroundColor: '#ffffff'
                                }}
                              >
                                <option value="">-- Choose Employee --</option>
                                {employeesList.map(emp => (
                                  <option key={emp.id} value={emp.id}>
                                    {emp.name} ({emp.username || `ID ${emp.id}`} - {emp.role})
                                  </option>
                                ))}
                              </select>
                            </div>

                            <div style={{ flex: '1', minWidth: '110px' }}>
                              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: '#475569', marginBottom: '4px' }}>
                                WebRTC Extension
                              </label>
                              <input
                                type="text"
                                placeholder="Extension"
                                value={newMapping.extension}
                                onChange={(e) => setNewMapping(prev => ({ ...prev, extension: e.target.value }))}
                                style={{
                                  width: '100%',
                                  padding: '7px 10px',
                                  borderRadius: '6px',
                                  border: '1px solid #cbd5e1',
                                  fontSize: '0.8rem',
                                  backgroundColor: '#ffffff'
                                }}
                              />
                            </div>

                            <div style={{ flex: '1.2', minWidth: '140px' }}>
                              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: '#475569', marginBottom: '4px' }}>
                                Assigned Outbound DID
                              </label>
                              <select
                                value={newMapping.did_number}
                                onChange={(e) => setNewMapping(prev => ({ ...prev, did_number: e.target.value }))}
                                style={{
                                  width: '100%',
                                  padding: '7px 10px',
                                  borderRadius: '6px',
                                  border: '1px solid #cbd5e1',
                                  fontSize: '0.8rem',
                                  backgroundColor: '#ffffff'
                                }}
                              >
                                <option value="">-- Choose DID --</option>
                                {(modalState.config?.phone_number || '')
                                  .split(',')
                                  .map(d => d.trim())
                                  .filter(Boolean)
                                  .map(d => (
                                    <option key={d} value={d}>{d}</option>
                                  ))}
                              </select>
                            </div>

                            <div style={{ flex: '1', minWidth: '100px' }}>
                              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: '600', color: '#475569', marginBottom: '4px' }}>
                                Account Type
                              </label>
                              <select
                                value={newMapping.account_type}
                                onChange={(e) => setNewMapping(prev => ({ ...prev, account_type: e.target.value }))}
                                style={{
                                  width: '100%',
                                  padding: '7px 10px',
                                  borderRadius: '6px',
                                  border: '1px solid #cbd5e1',
                                  fontSize: '0.8rem',
                                  backgroundColor: '#ffffff'
                                }}
                              >
                                <option value="Agent">Agent</option>
                                <option value="Admin">Admin</option>
                              </select>
                            </div>

                            <button
                              type="button"
                              onClick={handleAddExtensionMapping}
                              disabled={mappingSaving}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '8px 14px',
                                backgroundColor: mappingSaving ? '#94a3b8' : '#2563eb',
                                color: '#ffffff',
                                border: 'none',
                                borderRadius: '6px',
                                fontWeight: '600',
                                fontSize: '0.8rem',
                                cursor: mappingSaving ? 'not-allowed' : 'pointer',
                                height: '35px'
                              }}
                            >
                              <Plus size={15} />
                              <span>{mappingSaving ? 'Saving...' : 'Add / Map'}</span>
                            </button>
                          </div>
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
