import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import IVRCallModal from '../../components/IVR/IVRCallModal';
import CallAISummaryModal from '../../components/IVR/CallAISummaryModal';
import { 
  PhoneCall, 
  PhoneIncoming, 
  PhoneOutgoing, 
  Search, 
  Clock, 
  CheckCircle2, 
  AlertCircle,
  X,
  RefreshCw,
  Sparkles,
  Radio,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  Play,
  Pause,
  Database,
  UploadCloud
} from 'lucide-react';
import { formatLocalDateTime } from '../../utils/dateUtils';
import PingoEmptyState from '../../components/Common/PingoEmptyState';
import './CallLogsPage.css';

const AudioRecordingPlayer = ({ src, logId }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioDuration, setAudioDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [isReady, setIsReady] = useState(false);
  const [isFailed, setIsFailed] = useState(false);

  const audioRef = useRef(null);

  // Reset audio state when src changes
  useEffect(() => {
    setIsPlaying(false);
    setCurrentTime(0);
    setIsReady(false);
    setIsFailed(false);
    setAudioDuration(0);

    if (audioRef.current) {
      audioRef.current.load();
    }
  }, [src]);

  const formatAudioTime = (seconds) => {
    if (!seconds || isNaN(seconds) || seconds <= 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      const dur = audioRef.current.duration;
      if (dur && !isNaN(dur) && isFinite(dur) && dur > 0) {
        setAudioDuration(dur);
        setIsReady(true);
        setIsFailed(false);
      }
    }
  };

  const handleCanPlay = () => {
    if (audioRef.current) {
      const dur = audioRef.current.duration;
      if (dur && !isNaN(dur) && isFinite(dur) && dur > 0) {
        setAudioDuration(dur);
      }
      setIsReady(true);
      setIsFailed(false);
    }
  };

  const handleError = () => {
    // When audio element cannot load the file (e.g., 404, invalid host, or not ready yet)
    setIsReady(false);
    setIsFailed(true);
  };

  const togglePlay = () => {
    if (!audioRef.current || !isReady) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().then(() => {
        setIsPlaying(true);
      }).catch(err => {
        console.warn("Audio playback error:", err);
      });
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleSeek = (e) => {
    const val = parseFloat(e.target.value);
    if (audioRef.current && !isNaN(val)) {
      audioRef.current.currentTime = val;
      setCurrentTime(val);
    }
  };

  if (!src || isFailed) {
    return <span className="no-recording-text">No recording available</span>;
  }

  return (
    <div className="audio-player-wrapper">
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onLoadedMetadata={handleLoadedMetadata}
        onCanPlay={handleCanPlay}
        onTimeUpdate={handleTimeUpdate}
        onEnded={() => {
          setIsPlaying(false);
          setCurrentTime(0);
        }}
        onError={handleError}
      />

      {isReady ? (
        <div className="audio-recording-player">
          <button
            type="button"
            className={`audio-play-btn ${isPlaying ? 'playing' : ''}`}
            onClick={togglePlay}
            title={isPlaying ? "Pause Recording" : "Play Recording"}
          >
            {isPlaying ? <Pause size={13} /> : <Play size={13} style={{ marginLeft: '1.5px' }} />}
          </button>

          <div className="audio-seek-wrapper">
            <input
              type="range"
              min="0"
              max={audioDuration || 100}
              step="0.1"
              value={currentTime}
              onChange={handleSeek}
              className="audio-seek-slider"
              style={{
                background: `linear-gradient(to right, #2563eb ${audioDuration > 0 ? Math.min(100, Math.max(0, (currentTime / audioDuration) * 100)) : 0}%, #e2e8f0 ${audioDuration > 0 ? Math.min(100, Math.max(0, (currentTime / audioDuration) * 100)) : 0}%)`
              }}
            />
          </div>

          <span className="audio-duration-text">
            {formatAudioTime(currentTime)} / {formatAudioTime(audioDuration)}
          </span>
        </div>
      ) : (
        <span 
          className="recording-status-badge processing" 
          title="Loading audio recording..."
        >
          <span className="recording-pulse-dot" />
          Loading Audio...
        </span>
      )}
    </div>
  );
};

const formatDuration = (sec) => {
  if (!sec || sec <= 0) return '0s';
  const mins = Math.floor(sec / 60);
  const remainingSec = sec % 60;
  if (mins === 0) return `${remainingSec}s`;
  return `${mins}m ${remainingSec}s`;
};

const getInitials = (name) => {
  if (!name) return 'LD';
  const parts = name.trim().split(' ').filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
};

const getAvatarColor = (name) => {
  const colors = [
    'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
    'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
    'linear-gradient(135deg, #059669 0%, #047857 100%)',
    'linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%)',
    'linear-gradient(135deg, #d97706 0%, #b45309 100%)',
    'linear-gradient(135deg, #e11d48 0%, #be123c 100%)'
  ];
  if (!name) return colors[0];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % colors.length;
  return colors[index];
};

const getStatusBadge = (status) => {
  const st = (status || '').toUpperCase();
  switch (st) {
    case 'COMPLETED':
    case 'CONNECTED':
    case 'ANSWERED':
      return (
        <span className="status-pill completed">
          <span className="status-dot-indicator" />
          COMPLETED
        </span>
      );
    case 'RINGING':
    case 'INITIATING':
    case 'INITIATED':
      return (
        <span className="status-pill ringing">
          <span className="status-dot-indicator" />
          RINGING
        </span>
      );
    case 'NO_ANSWER':
    case 'NO ANSWER':
    case 'NOT_ANSWERED':
    case 'NOT ANSWERED':
      return (
        <span className="status-pill no-answer">
          <span className="status-dot-indicator" />
          NO ANSWER
        </span>
      );
    case 'MISSED':
    case 'ABANDON':
    case 'ABANDONED':
    case 'BUSY':
    case 'FAILED':
      return (
        <span className="status-pill failed">
          <span className="status-dot-indicator" />
          {st === 'ABANDON' || st === 'ABANDONED' ? 'MISSED' : st}
        </span>
      );
    default:
      return (
        <span className="status-pill" style={{ background: '#f1f5f9', color: '#475569' }}>
          <span className="status-dot-indicator" />
          {st || 'UNKNOWN'}
        </span>
      );
  }
};

const CallLogsPage = () => {
  const { user } = useAuth();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const initialStatusFromUrl = queryParams.get('status') || queryParams.get('call_status') || '';
  const initialEmployeeFromUrl = queryParams.get('employee_id') || '';

  const [callLogs, setCallLogs] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncNotice, setSyncNotice] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const fileInputRef = useRef(null);
  
  // Filters & Pagination
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState(initialStatusFromUrl);
  const [directionFilter, setDirectionFilter] = useState('');
  const [employeeFilter, setEmployeeFilter] = useState(initialEmployeeFromUrl);
  const [providerFilter, setProviderFilter] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalRecords, setTotalRecords] = useState(0);
  const [metrics, setMetrics] = useState(null);
  
  // Click-To-Call Modal
  const [showCallModal, setShowCallModal] = useState(false);
  const [selectedCallTarget, setSelectedCallTarget] = useState(null);

  // AI Call Summary Modal
  const [selectedCallLog, setSelectedCallLog] = useState(null);
  const [showAIModal, setShowAIModal] = useState(false);

  const callScope = user?.permissions?.calls?.view_scope || (user?.role === 'ADMIN' ? 'company' : (['MANAGER', 'SUPPORT_MANAGER'].includes(user?.role) ? 'team' : 'own'));
  const canFilterEmployees = user?.role === 'ADMIN' || callScope === 'company' || callScope === 'team' || ['MANAGER', 'SUPPORT_MANAGER'].includes(user?.role);

  const visibleEmployees = React.useMemo(() => {
    if (user?.role === 'ADMIN' || callScope === 'company') {
      return employees;
    }
    if (callScope === 'team' || ['MANAGER', 'SUPPORT_MANAGER'].includes(user?.role)) {
      return employees.filter(emp => emp.manager_id === user?.employee_id || emp.id === user?.employee_id);
    }
    return [];
  }, [employees, user, callScope]);

  const fetchEmployees = async () => {
    try {
      const res = await API.get('/employees/?status_filter=ACTIVE');
      setEmployees(res.data || []);
    } catch (e) {
      console.error('Failed to load employees for filter:', e);
    }
  };

  const fastPollTimerRef = useRef(null);
  const fastPollCountRef = useRef(0);

  const fetchCallLogs = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const params = {
        page: currentPage,
        limit: pageSize,
        _t: Date.now()
      };
      if (statusFilter) params.call_status = statusFilter;
      if (directionFilter) params.direction = directionFilter;
      if (employeeFilter) params.employee_id = employeeFilter;
      if (providerFilter) params.provider = providerFilter;
      if (search) params.search = search;
      
      const res = await API.get('/ivr/calls', { params });
      const items = res.data?.items || [];
      setCallLogs(items);
      setTotalRecords(res.data?.total ?? items.length);
      if (res.data?.metrics) {
        setMetrics(res.data.metrics);
      }
      return items;
    } catch (err) {
      console.error("Failed to load call logs:", err);
      return [];
    } finally {
      if (!silent) setLoading(false);
    }
  };

  // Refresh & Fetch All Data without filters
  const handleFetchAllData = async () => {
    setLoading(true);
    setSearch('');
    setStatusFilter('');
    setDirectionFilter('');
    setEmployeeFilter('');
    setProviderFilter('');
    setCurrentPage(1);
    try {
      const res = await API.get('/ivr/calls', {
        params: {
          page: 1,
          limit: pageSize,
          _t: Date.now()
        }
      });
      const items = res.data?.items || [];
      setCallLogs(items);
      setTotalRecords(res.data?.total ?? items.length);
      if (res.data?.metrics) setMetrics(res.data.metrics);
      setSyncNotice({ type: 'success', message: `Refreshed all call records (${res.data?.total || items.length} total).` });
      setTimeout(() => setSyncNotice(null), 4000);
    } catch (err) {
      console.error('Failed to fetch all calls:', err);
      setSyncNotice({ type: 'error', message: 'Failed to retrieve call logs from server.' });
      setTimeout(() => setSyncNotice(null), 4000);
    } finally {
      setLoading(false);
    }
  };

  // Import / Synchronize CDR dump data
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (evt) => {
      try {
        setSyncing(true);
        const text = evt.target.result;
        let records = [];

        if (file.name.endsWith('.json')) {
          const parsed = JSON.parse(text);
          records = Array.isArray(parsed) ? parsed : (parsed.calls || parsed.data || [parsed]);
        } else {
          // Parse CSV / TSV text
          const lines = text.split(/\r?\n/).filter(line => line.trim().length > 0);
          if (lines.length > 1) {
            const headers = lines[0].split(/[\t,]/).map(h => h.trim().toLowerCase().replace(/[^a-z0-9_]/g, ''));
            for (let i = 1; i < lines.length; i++) {
              const parts = lines[i].split(/[\t,]/).map(p => p.trim().replace(/^["']|["']$/g, ''));
              const obj = {};
              headers.forEach((h, idx) => {
                obj[h] = parts[idx] || '';
              });
              // Normalize common CDR column names
              const mapped = {
                uniqueid: obj.uniqueid || obj.callid || obj.id || `cdr_import_${Date.now()}_${i}`,
                phone_number: obj.phone_number || obj.number || obj.customer_number || obj.destination || obj.caller || obj.callee || '',
                caller: obj.caller || obj.from || '',
                callee: obj.callee || obj.to || '',
                station: obj.station || obj.extension || obj.agent_extension || '',
                agent: obj.agent || obj.employee || obj.agent_name || '',
                status: obj.status || obj.call_status || obj.disposition || 'COMPLETED',
                direction: (obj.direction || obj.call_direction || '').toUpperCase() || 'INBOUND',
                duration: parseInt(obj.duration || obj.billsec || obj.talk_time || 0, 10),
                start_time: obj.start_time || obj.started_at || obj.datetime || '',
                recording_url: obj.recording_url || obj.recording || ''
              };
              if (mapped.phone_number || mapped.caller || mapped.callee) {
                records.push(mapped);
              }
            }
          }
        }

        if (records.length === 0) {
          setSyncNotice({ type: 'error', message: 'No valid CDR records found in uploaded file.' });
          setTimeout(() => setSyncNotice(null), 4000);
          return;
        }

        // Post to /ivr/sync-cdr
        const res = await API.post('/ivr/sync-cdr', { calls: records });
        setSyncNotice({
          type: 'success',
          message: `Successfully synchronized ${res.data?.synced_count || records.length} CDR records!`
        });
        setTimeout(() => setSyncNotice(null), 5000);
        fetchCallLogs(false);
      } catch (err) {
        console.error('Failed to import CDR dump:', err);
        setSyncNotice({ type: 'error', message: `Import error: ${err.response?.data?.detail || err.message}` });
        setTimeout(() => setSyncNotice(null), 5000);
      } finally {
        setSyncing(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    };
    reader.readAsText(file);
  };

  const startFastPolling = () => {
    if (fastPollTimerRef.current) clearInterval(fastPollTimerRef.current);
    fastPollCountRef.current = 0;

    // Immediately fetch once
    fetchCallLogs(true);

    fastPollTimerRef.current = setInterval(async () => {
      fastPollCountRef.current += 1;
      const logs = await fetchCallLogs(true);

      // Check if there are any recent calls still waiting for recordings
      const hasPendingCalls = (logs || []).some(log => {
        const isRecRecent = log.started_at || log.created_at;
        const diffMs = isRecRecent ? (Date.now() - new Date(isRecRecent).getTime()) : 0;
        const isRecent = diffMs < 180000; // within last 3 minutes
        const recStatus = String(log.recording_status || '').toUpperCase();
        const callStatus = String(log.call_status || '').toUpperCase();
        const isProcessing = recStatus.includes('PROCESSING');
        const isConnected = ['ANSWERED', 'COMPLETED', 'CONNECTED'].includes(callStatus);
        return isRecent && (isProcessing || (!log.recording_url && isConnected));
      });

      // Stop fast polling once all recent calls have resolved or after 60s (30 ticks)
      if (!hasPendingCalls || fastPollCountRef.current >= 30) {
        if (fastPollTimerRef.current) {
          clearInterval(fastPollTimerRef.current);
          fastPollTimerRef.current = null;
        }
      }
    }, 2000);
  };

  useEffect(() => {
    fetchEmployees();
  }, []);

  // Sync filters if URL search params change
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const urlStatus = params.get('status') || params.get('call_status');
    const urlEmp = params.get('employee_id');
    if (urlStatus !== null) setStatusFilter(urlStatus);
    if (urlEmp !== null) setEmployeeFilter(urlEmp);
  }, [location.search]);

  useEffect(() => {
    fetchCallLogs(false);

    // Instant real-time refresh when a call disconnects or completes
    const handleCallCompleted = (event) => {
      console.log('⚡ [CallLogsPage] Call completed event received. Starting 2-second fast poll for recording:', event.detail);
      startFastPolling();
    };

    window.addEventListener('crm-call-completed', handleCallCompleted);
    window.addEventListener('crm-doocti-call-logged', handleCallCompleted);

    // Continuous auto-polling every 4 seconds as a background fallback
    const timer = setInterval(() => {
      fetchCallLogs(true);
    }, 4000);

    return () => {
      window.removeEventListener('crm-call-completed', handleCallCompleted);
      window.removeEventListener('crm-doocti-call-logged', handleCallCompleted);
      if (fastPollTimerRef.current) clearInterval(fastPollTimerRef.current);
      clearInterval(timer);
    };
  }, [statusFilter, directionFilter, employeeFilter, providerFilter, search, currentPage, pageSize]);

  const handleInitiateNewCall = () => {
    if (window.expandDoocti) {
      window.expandDoocti();
    } else if (window.crmDial) {
      window.crmDial();
    } else {
      setSelectedCallTarget({
        name: 'Direct Call Target',
        phone: '+919876543210'
      });
      setShowCallModal(true);
    }
  };

  const handleCallBackTarget = (log) => {
    const phone = log.customer_phone || log.to_number || log.from_number;
    if (window.dooctiDial) {
      window.dooctiDial(phone, {
        id: log.lead_id,
        name: log.lead_name || 'Lead #' + (log.lead_id || ''),
        phone: phone
      });
    } else if (window.crmDial) {
      window.crmDial(phone, {
        id: log.lead_id,
        name: log.lead_name || 'Lead #' + (log.lead_id || ''),
        phone: phone
      });
    } else {
      setSelectedCallTarget({
        id: log.lead_id,
        name: log.lead_name || 'Lead #' + log.lead_id,
        phone: phone
      });
      setShowCallModal(true);
    }
  };

  const handleCopyText = (text, id) => {
    if (!text) return;
    navigator.clipboard?.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  // Metrics Calculations (authoritative across all matching records from server)
  const totalCalls = metrics?.total_calls ?? (totalRecords || callLogs.length);
  const connectedCalls = metrics?.connected_calls ?? callLogs.filter(c => ['COMPLETED', 'CONNECTED', 'ANSWERED'].includes((c.call_status || '').toUpperCase())).length;
  const missedCalls = metrics?.missed_calls ?? callLogs.filter(c => ['MISSED', 'BUSY', 'FAILED', 'NO_ANSWER', 'NO ANSWER'].includes((c.call_status || '').toUpperCase())).length;
  const totalSecs = metrics?.total_duration_seconds ?? callLogs.reduce((acc, c) => acc + (c.duration_seconds || 0), 0);
  const connectRate = metrics?.connect_rate ?? (totalCalls > 0 ? Math.round((connectedCalls / totalCalls) * 100) : 0);
  const avgDuration = metrics?.avg_duration_seconds ?? (connectedCalls > 0 ? Math.round(totalSecs / connectedCalls) : 0);

  return (
    <div className="call-logs-container">
      {/* -------------------------------------------------------------
          Page Header
      -------------------------------------------------------------- */}
      <div className="call-logs-header">
        <div>
          <div className="call-logs-breadcrumbs">
            <Link to="/dashboard">Dashboard</Link>
            <span>/</span>
            <span>Communication</span>
            <span>/</span>
            <span style={{ color: '#0f172a', fontWeight: 600 }}>Call Logs</span>
          </div>

          <div className="call-logs-title-area">
            <h1 className="call-logs-title">Telephony & Call Intelligence</h1>
            <div className="live-bridge-badge">
              <span className="live-bridge-dot" />
              <span>Doocti Live Bridge Active</span>
            </div>
          </div>

          <p className="call-logs-subtitle">
            Unified telephony ledger tracking inbound & outbound conversations, Doocti PBX recordings, agent productivity, and automated call dispositions.
          </p>
        </div>

        <div className="call-logs-actions">
          {/* Hidden file input for CDR Dump sync */}
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileUpload} 
            accept=".csv,.json,.txt,.tsv" 
            style={{ display: 'none' }} 
          />

          <button 
            onClick={handleFetchAllData} 
            className="btn-refresh-logs btn-get-all" 
            title="Reset filters and fetch all telephony call data"
            disabled={loading || syncing}
          >
            <Database size={15} />
            <span>Get All Data</span>
          </button>

          <button 
            onClick={() => fileInputRef.current && fileInputRef.current.click()} 
            className="btn-refresh-logs" 
            title="Upload raw CDR dump file (CSV/JSON/TSV) to sync missing call logs"
            disabled={syncing}
          >
            <UploadCloud size={15} className={syncing ? 'spin' : ''} />
            <span>{syncing ? 'Syncing...' : 'Sync CDR Dump'}</span>
          </button>

          <button 
            onClick={() => fetchCallLogs(false)} 
            className="btn-refresh-logs" 
            title="Refresh Call Logs from Server"
            disabled={loading || syncing}
          >
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>

          <button 
            onClick={handleInitiateNewCall} 
            className="btn-primary-dial"
            title="Open In-App Doocti Dialer"
          >
            <PhoneCall size={16} />
            <span>Click-to-Call</span>
          </button>
        </div>
      </div>

      {syncNotice && (
        <div style={{
          marginBottom: '20px',
          padding: '12px 18px',
          borderRadius: '9px',
          background: syncNotice.type === 'success' ? '#f0fdf4' : '#fef2f2',
          border: `1px solid ${syncNotice.type === 'success' ? '#bbf7d0' : '#fecaca'}`,
          color: syncNotice.type === 'success' ? '#166534' : '#991b1b',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          fontSize: '0.88rem',
          fontWeight: 600
        }}>
          {syncNotice.type === 'success' ? <CheckCircle2 size={18} color="#16a34a" /> : <AlertCircle size={18} color="#dc2626" />}
          <span>{syncNotice.message}</span>
        </div>
      )}

      {/* -------------------------------------------------------------
          Executive KPI Cards
      -------------------------------------------------------------- */}
      <div className="call-kpi-grid">
        {/* Card 1: Total Calls */}
        <div className="call-kpi-card kpi-blue">
          <div className="call-kpi-top">
            <span className="call-kpi-label">Total Calls Logged</span>
            <div className="call-kpi-icon-badge">
              <Radio size={18} />
            </div>
          </div>
          <div className="call-kpi-value">{totalCalls}</div>
          <div className="call-kpi-footer">
            <span className="call-kpi-pill neutral">All Channels</span>
            <span>Inbound & Outbound</span>
          </div>
        </div>

        {/* Card 2: Connected / Completed */}
        <div className="call-kpi-card kpi-green">
          <div className="call-kpi-top">
            <span className="call-kpi-label">Connected / Completed</span>
            <div className="call-kpi-icon-badge">
              <CheckCircle2 size={18} />
            </div>
          </div>
          <div className="call-kpi-value">{connectedCalls}</div>
          <div className="call-kpi-footer">
            <span className="call-kpi-pill positive">{connectRate}% Connect Rate</span>
            <span>Conversations held</span>
          </div>
        </div>

        {/* Card 3: Missed / No Answer */}
        <div 
          className={`call-kpi-card kpi-amber ${statusFilter === 'Missed' ? 'active-filter-card' : ''}`}
          onClick={() => setStatusFilter(prev => prev === 'Missed' ? '' : 'Missed')}
          style={{ cursor: 'pointer' }}
          title="Click to filter by Missed calls"
        >
          <div className="call-kpi-top">
            <span className="call-kpi-label">Missed / No Answer</span>
            <div className="call-kpi-icon-badge">
              <AlertCircle size={18} />
            </div>
          </div>
          <div className="call-kpi-value">{missedCalls}</div>
          <div className="call-kpi-footer">
            <span className="call-kpi-pill warning">{missedCalls > 0 ? `${missedCalls} Missed` : '0 Missed'}</span>
            <span>Requires follow-up outreach</span>
          </div>
        </div>

        {/* Card 4: Total Talk Time */}
        <div className="call-kpi-card kpi-indigo">
          <div className="call-kpi-top">
            <span className="call-kpi-label">Total Talk Time</span>
            <div className="call-kpi-icon-badge">
              <Clock size={18} />
            </div>
          </div>
          <div className="call-kpi-value">{formatDuration(totalSecs)}</div>
          <div className="call-kpi-footer">
            <span className="call-kpi-pill neutral">Avg: {formatDuration(avgDuration)}/call</span>
            <span>Across connected</span>
          </div>
        </div>
      </div>

      {/* -------------------------------------------------------------
          Filter & Search Toolbar
      -------------------------------------------------------------- */}
      <div className="call-toolbar">
        <div className="call-search-box">
          <Search size={16} className="call-search-icon" />
          <input 
            type="text" 
            placeholder="Search by customer phone, lead name, agent, or call ID..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="call-search-input"
          />
          {search && (
            <button 
              type="button" 
              className="call-search-clear-btn"
              onClick={() => setSearch('')}
              title="Clear search"
            >
              <X size={14} />
            </button>
          )}
        </div>

        <div className="call-filters-group">
          {/* Direction Filter */}
          <div className="select-wrapper">
            <select 
              value={directionFilter} 
              onChange={(e) => setDirectionFilter(e.target.value)}
              className="call-select"
            >
              <option value="">All Directions</option>
              <option value="INBOUND">Inbound Calls</option>
              <option value="OUTBOUND">Outbound Calls</option>
            </select>
          </div>

          {/* Status Filter */}
          <div className="select-wrapper">
            <select 
              value={statusFilter} 
              onChange={(e) => setStatusFilter(e.target.value)}
              className="call-select"
            >
              <option value="">All Statuses</option>
              <option value="Completed">Completed</option>
              <option value="No_Answer">No Answer</option>
              <option value="Missed">Missed</option>
              <option value="Busy">Busy</option>
              <option value="Failed">Failed</option>
              <option value="Initiating">Initiating / Ringing</option>
            </select>
          </div>

          {/* Employee Filter */}
          {canFilterEmployees && visibleEmployees.length > 0 && (
            <div className="select-wrapper">
              <select 
                value={employeeFilter} 
                onChange={(e) => setEmployeeFilter(e.target.value)}
                className="call-select"
              >
                <option value="">{user?.role === 'ADMIN' ? 'All Employees' : 'All Team Members'}</option>
                {visibleEmployees.map(emp => (
                  <option key={emp.id} value={emp.id}>{emp.name} ({emp.phone || 'Ext ' + emp.id})</option>
                ))}
              </select>
            </div>
          )}

          {/* Provider Filter */}
          <div className="select-wrapper">
            <select 
              value={providerFilter} 
              onChange={(e) => setProviderFilter(e.target.value)}
              className="call-select"
            >
              <option value="">All Telephony Providers</option>
              <option value="DOOCTI">Doocti Telephony</option>
              <option value="Smartflo">Tata Smartflo</option>
              <option value="CloudShope">CloudShope</option>
              <option value="TWILIO">Twilio</option>
              <option value="EXOTEL">Exotel</option>
            </select>
          </div>

          {/* Clear Filters */}
          {(search || statusFilter || directionFilter || employeeFilter || providerFilter) && (
            <button
              type="button"
              onClick={() => {
                setSearch('');
                setStatusFilter('');
                setDirectionFilter('');
                setEmployeeFilter('');
                setProviderFilter('');
              }}
              className="btn-clear-filters"
              title="Reset all active filters"
            >
              <X size={14} /> Clear
            </button>
          )}
        </div>
      </div>

      {/* -------------------------------------------------------------
          Enterprise Call Logs Table
      -------------------------------------------------------------- */}
      <div className="call-table-card">
        <div className="call-table-responsive">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th style={{ width: '110px' }}>Direction</th>
                <th style={{ minWidth: '220px' }}>Lead / Customer Phone</th>
                <th style={{ minWidth: '180px' }}>Agent & Extension</th>
                <th style={{ minWidth: '150px' }}>Timestamp</th>
                <th style={{ width: '90px' }}>Duration</th>
                <th style={{ width: '130px' }}>Call Status</th>
                <th style={{ width: '130px' }}>Product Category</th>
                <th style={{ minWidth: '220px' }}>Recording</th>
                <th style={{ width: '170px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && callLogs.length === 0 ? (
                <tr>
                  <td colSpan={9}>
                    <div className="table-empty-state">
                      <RefreshCw size={28} className="spin" style={{ margin: '0 auto', color: '#2563eb' }} />
                      <div className="table-empty-title">Loading IVR telephony logs...</div>
                      <div className="table-empty-desc">Fetching latest synchronized records from MySQL and Doocti PBX.</div>
                    </div>
                  </td>
                </tr>
              ) : callLogs.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ padding: '36px 16px', background: '#f8fafc' }}>
                    <PingoEmptyState
                      pose="inspect"
                      height={120}
                      title="No Call Logs Found"
                      description={(search || statusFilter || employeeFilter || providerFilter) ? "No call records match your current telephony filters." : "No outbound or inbound calls have been logged yet."}
                      secondaryActionLabel={(search || statusFilter || employeeFilter || providerFilter) ? "Clear Filters" : null}
                      onSecondaryAction={() => {
                        setSearch('');
                        setStatusFilter('');
                        setEmployeeFilter('');
                        setProviderFilter('');
                      }}
                    />
                  </td>
                </tr>
              ) : (
                callLogs.map(log => {
                  const isOutbound = (log.call_direction || '').toUpperCase() === 'OUTBOUND';
                  const isExt = (num) => num && String(num).replace(/[^0-9]/g, '').length <= 5;
                  const rawCust = log.customer_phone || '';
                  const rawEmp = log.employee_phone || '';
                  const customerNum = (!isExt(rawCust) && rawCust) ? rawCust : (!isExt(log.to_number) && log.to_number) ? log.to_number : (!isExt(log.from_number) && log.from_number) ? log.from_number : (rawCust || log.to_number || log.from_number || '');
                  const agentExt = log.employee_extension || ((isExt(rawEmp) && rawEmp) ? rawEmp : (isExt(log.from_number) && log.from_number) ? log.from_number : (isExt(log.to_number) && log.to_number) ? log.to_number : '—');
                  const leadName = log.lead_name || (log.lead_id ? `Prospect #${log.lead_id}` : (customerNum ? 'Direct Caller' : 'Call'));
                  const targetPhone = customerNum || '—';
                  const providerName = (log.provider || 'DOOCTI').toUpperCase();
                  const isDoocti = providerName.includes('DOOCTI');
                  const isSmartflo = providerName.includes('SMARTFLO');

                  return (
                    <tr key={log.id}>
                      {/* Direction */}
                      <td>
                        {log.call_direction === 'INBOUND' ? (
                          <span className="direction-pill inbound">
                            <PhoneIncoming size={12} />
                            INBOUND
                          </span>
                        ) : (
                          <span className="direction-pill outbound">
                            <PhoneOutgoing size={12} />
                            OUTBOUND
                          </span>
                        )}
                      </td>

                      {/* Lead / Customer Phone */}
                      <td>
                        <div className="lead-cell">
                          <div 
                            className="lead-avatar" 
                            style={{ background: getAvatarColor(leadName) }}
                          >
                            {getInitials(leadName)}
                          </div>
                          <div>
                            <div className="lead-info-title">{leadName}</div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span className="lead-phone-number">{targetPhone}</span>
                              <button
                                type="button"
                                onClick={() => handleCopyText(targetPhone, `phone-${log.id}`)}
                                style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: '#94a3b8' }}
                                title="Copy Phone Number"
                              >
                                {copiedId === `phone-${log.id}` ? (
                                  <Check size={11} color="#10b981" />
                                ) : (
                                  <Copy size={11} />
                                )}
                              </button>
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Agent & Extension */}
                      <td>
                        <div className="agent-cell">
                          <div>
                            <div className="agent-name-text">
                              {log.employee_name || (agentExt !== '—' ? `Extension ${agentExt}` : 'Unassigned')}
                            </div>
                            <span className="agent-ext-tag">
                              Ext: {agentExt}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Timestamp */}
                      <td>
                        <div style={{ fontSize: '0.82rem', color: '#0f172a', fontWeight: 600 }}>
                          {formatLocalDateTime(log.started_at || log.created_at)}
                        </div>
                      </td>

                      {/* Duration */}
                      <td>
                        <div style={{ fontWeight: 700, color: (log.duration_seconds || 0) > 0 ? '#0f172a' : '#94a3b8' }}>
                          {formatDuration(log.duration_seconds)}
                        </div>
                      </td>

                      {/* Status */}
                      <td>
                        {getStatusBadge(log.call_status)}
                      </td>

                      {/* Product Category */}
                      <td>
                        {(() => {
                          const cat = (log.product_category || 'UNCLASSIFIED').toUpperCase();
                          const isBio = cat === 'BIOMETRIC';
                          const isWahrms = cat === 'WAHRMS';
                          const bg = isBio ? '#eff6ff' : isWahrms ? '#f0fdf4' : '#f1f5f9';
                          const color = isBio ? '#1d4ed8' : isWahrms ? '#15803d' : '#64748b';
                          const border = isBio ? '#bfdbfe' : isWahrms ? '#bbf7d0' : '#cbd5e1';
                          return (
                            <span style={{
                              display: 'inline-block',
                              padding: '3px 8px',
                              borderRadius: '12px',
                              fontSize: '0.74rem',
                              fontWeight: 700,
                              backgroundColor: bg,
                              color: color,
                              border: '1px solid ' + border
                            }}>
                              {cat}
                            </span>
                          );
                        })()}
                      </td>

                      {/* Audio Recording */}
                      <td>
                        {(() => {
                          const recStatus = String(log.recording_status || '').toUpperCase();
                          const isProcessing = recStatus.includes('PROCESSING');
                          
                          if (log.recording_url) {
                            return <AudioRecordingPlayer key={log.id} src={log.recording_url} logId={log.id} />;
                          }
                          if (isProcessing) {
                            return (
                              <span className="recording-status-badge processing" title="Audio recording is currently being processed by Doocti PBX (auto-updating...)">
                                <span className="recording-pulse-dot" />
                                Recording Processing
                              </span>
                            );
                          }
                          return <span className="no-recording-text">No recording available</span>;
                        })()}
                      </td>

                      {/* Actions */}
                      <td style={{ textAlign: 'right' }}>
                        <div className="action-buttons-group">
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedCallLog(log);
                              setShowAIModal(true);
                            }}
                            className="btn-table-action btn-table-ai"
                            title="Generate or view AI Transcript & Discussion Summary"
                          >
                            <Sparkles size={12} />
                            <span>AI Review</span>
                          </button>

                          <button 
                            type="button"
                            onClick={() => handleCallBackTarget(log)} 
                            className="btn-table-action btn-table-call"
                            title="Call this contact back via Doocti"
                          >
                            <PhoneCall size={12} />
                            <span>Call Back</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Enterprise Pagination Toolbar */}
        <div className="call-logs-pagination">
          <div className="pagination-count-summary">
            Showing <span className="highlight-text">{callLogs.length > 0 ? (currentPage - 1) * pageSize + 1 : 0}</span> to <span className="highlight-text">{Math.min(currentPage * pageSize, totalRecords)}</span> of <span className="highlight-text">{totalRecords}</span> calls
          </div>

          <div className="pagination-actions-group">
            <div className="pagination-page-size-wrap">
              <span className="page-size-label">Rows per page:</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setCurrentPage(1);
                }}
                className="pagination-select"
              >
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={250}>250</option>
              </select>
            </div>

            <div className="pagination-nav-buttons">
              <button
                type="button"
                className="btn-pagination-nav"
                disabled={currentPage <= 1 || loading}
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                title="Previous Page"
              >
                <ChevronLeft size={16} />
                <span>Prev</span>
              </button>

              <div className="pagination-page-indicator">
                Page <strong>{currentPage}</strong> of <strong>{Math.max(1, Math.ceil(totalRecords / pageSize))}</strong>
              </div>

              <button
                type="button"
                className="btn-pagination-nav"
                disabled={currentPage >= Math.ceil(totalRecords / pageSize) || loading}
                onClick={() => setCurrentPage(prev => prev + 1)}
                title="Next Page"
              >
                <span>Next</span>
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* -------------------------------------------------------------
          Modals
      -------------------------------------------------------------- */}
      <IVRCallModal 
        isOpen={showCallModal}
        lead={selectedCallTarget?.id ? { id: selectedCallTarget.id, name: selectedCallTarget.name, phone: selectedCallTarget.phone } : null}
        customerPhone={selectedCallTarget?.phone}
        onClose={() => setShowCallModal(false)}
        onCallComplete={() => fetchCallLogs(false)}
      />

      <CallAISummaryModal
        isOpen={showAIModal}
        onClose={() => setShowAIModal(false)}
        callLog={selectedCallLog}
        onSummaryGenerated={(updatedLog) => {
          setSelectedCallLog(updatedLog);
          setCallLogs(prev => prev.map(c => c.id === updatedLog.id ? updatedLog : c));
        }}
      />
    </div>
  );
};

export default CallLogsPage;
