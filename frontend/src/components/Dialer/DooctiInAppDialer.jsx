import React, { useState, useEffect, useRef, useMemo } from 'react';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { 
  Phone, 
  PhoneCall, 
  PhoneOutgoing, 
  PhoneMissed,
  Minus, 
  RotateCw, 
  Settings, 
  ChevronUp,
  Delete,
  Clock,
  Grid,
  Mic,
  MicOff,
  Pause,
  Play,
  Volume2,
  VolumeX,
  Home,
  Users,
  Search,
  X,
  UserCheck,
  Radio,
  Building,
  ArrowUpRight,
  ArrowDownLeft,
  AlertCircle
} from 'lucide-react';
import './DooctiInAppDialer.css';
import { formatLeadReceived } from '../../utils/dateUtils';
import PingoMascot from '../Common/PingoMascot';

// Default configuration loaded dynamically from server with verified DooCTI defaults
const DEFAULT_DOOCTI_CONFIG = {
  domain: 'https://beta3-app.doocti.com/',
  tenantId: 'chntechnolog',
  userEmail: '',
  userId: '',
  userNumber: '',
  cliNumber: '',
  didNumbers: []
};

// Standard ITU-T Dual-Tone Multi-Frequency (DTMF) mapping
const DTMF_FREQUENCIES = {
  '1': [697, 1209],
  '2': [697, 1336],
  '3': [697, 1477],
  '4': [770, 1209],
  '5': [770, 1336],
  '6': [770, 1477],
  '7': [852, 1209],
  '8': [852, 1336],
  '9': [852, 1477],
  '*': [941, 1209],
  '0': [941, 1336],
  '#': [941, 1477],
};

const KEYPAD_BUTTONS = [
  { digit: '1', letters: '' },
  { digit: '2', letters: 'ABC' },
  { digit: '3', letters: 'DEF' },
  { digit: '4', letters: 'GHI' },
  { digit: '5', letters: 'JKL' },
  { digit: '6', letters: 'MNO' },
  { digit: '7', letters: 'PQRS' },
  { digit: '8', letters: 'TUV' },
  { digit: '9', letters: 'WXYZ' },
  { digit: '*', letters: '' },
  { digit: '0', letters: '+' },
  { digit: '#', letters: '' },
];

// Persistent Web Audio context for zero-lag touch-tone playback
let audioCtx = null;

const playDTMF = (digit) => {
  try {
    const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtxClass) return;
    if (!audioCtx) audioCtx = new AudioCtxClass();
    if (audioCtx.state === 'suspended') audioCtx.resume();

    const freqs = DTMF_FREQUENCIES[digit] || [770, 1336];
    const now = audioCtx.currentTime;

    const osc1 = audioCtx.createOscillator();
    const osc2 = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();

    osc1.type = 'sine';
    osc2.type = 'sine';
    osc1.frequency.setValueAtTime(freqs[0], now);
    osc2.frequency.setValueAtTime(freqs[1], now);

    gainNode.gain.setValueAtTime(0, now);
    gainNode.gain.linearRampToValueAtTime(0.14, now + 0.012);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, now + 0.15);

    osc1.connect(gainNode);
    osc2.connect(gainNode);
    gainNode.connect(audioCtx.destination);

    osc1.start(now);
    osc2.start(now);
    osc1.stop(now + 0.15);
    osc2.stop(now + 0.15);
  } catch (err) {
    console.debug('DTMF tone error:', err);
  }
};

const playClickTone = (freq = 440) => {
  try {
    const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtxClass) return;
    if (!audioCtx) audioCtx = new AudioCtxClass();
    if (audioCtx.state === 'suspended') audioCtx.resume();

    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();

    osc.type = 'triangle';
    osc.frequency.setValueAtTime(freq, now);
    gainNode.gain.setValueAtTime(0.08, now);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, now + 0.08);

    osc.connect(gainNode);
    gainNode.connect(audioCtx.destination);

    osc.start(now);
    osc.stop(now + 0.08);
  } catch (err) {}
};

const playCallConnectingTone = () => {
  try {
    const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtxClass) return;
    if (!audioCtx) audioCtx = new AudioCtxClass();
    if (audioCtx.state === 'suspended') audioCtx.resume();

    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(523.25, now); // C5
    osc.frequency.setValueAtTime(659.25, now + 0.09); // E5

    gainNode.gain.setValueAtTime(0.12, now);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, now + 0.22);

    osc.connect(gainNode);
    gainNode.connect(audioCtx.destination);

    osc.start(now);
    osc.stop(now + 0.22);
  } catch (err) {}
};

const formatCallTimer = (sec) => {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
};

const formatDurationBadge = (sec) => {
  if (!sec || sec <= 0) return '00:00';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
};

const formatCallTimestamp = (isoDate) => {
  if (!isoDate) return '';
  const parsed = formatLeadReceived(isoDate);
  if (parsed && parsed.full && parsed.full !== '-') {
    const todayStr = formatLeadReceived(new Date().toISOString()).date;
    if (parsed.date === todayStr) {
      return `Today ${parsed.time}`;
    }
    return `${parsed.date}, ${parsed.time}`;
  }
  return String(isoDate);
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
  return colors[Math.abs(hash) % colors.length];
};

const DooctiInAppDialer = () => {
  const { user } = useAuth();

  // Floating Window State
  const [isMinimized, setIsMinimized] = useState(() => {
    const saved = localStorage.getItem('doocti_minimized');
    return saved !== null ? JSON.parse(saved) : true;
  });

  const [config, setConfig] = useState(() => {
    const saved = localStorage.getItem('doocti_config');
    return saved ? { ...DEFAULT_DOOCTI_CONFIG, ...JSON.parse(saved) } : DEFAULT_DOOCTI_CONFIG;
  });

  // Navigation: 'home' (Calls history), 'dialpad' (Keypad), 'leads' (Lead directory)
  const [activeTab, setActiveTab] = useState('home');
  const [callFilter, setCallFilter] = useState('all'); // 'all' | 'missed'
  const [searchQuery, setSearchQuery] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [tempConfig, setTempConfig] = useState(config);

  // Dynamic user extension resolution based on logged-in user and extension mapping from Admin page
  // Sync agent extension and assigned DID dynamically from backend database mapping
  const [didErrorNotice, setDidErrorNotice] = useState(null);

  useEffect(() => {
    if (!user) return;
    API.get('/doocti/config')
      .then(res => {
        if (res.data?.status === 'success') {
          const mapping = res.data.extension_mapping || {};
          const dids = res.data.did_numbers || [];

          let matchedExt = null;
          let matchedData = null;
          for (const [ext, info] of Object.entries(mapping)) {
            if (
              info.employee_id === user.employee_id ||
              info.employee_id === user.id ||
              (info.username && info.username.toLowerCase() === (user.username || '').toLowerCase())
            ) {
              matchedExt = ext;
              matchedData = info;
              break;
            }
          }
          if (!matchedExt && (user.role === 'ADMIN' || user.username === 'admin')) {
            matchedExt = res.data.admin_extension || Object.keys(mapping).find(k => (mapping[k].type || '').toUpperCase() === 'ADMIN') || null;
            if (matchedExt && mapping[matchedExt]) {
              matchedData = mapping[matchedExt];
            }
          }

          // Check assignment & DID validity
          let assignedDid = matchedData?.did_number || null;
          let isExtActive = matchedData ? matchedData.is_active !== false : true;

          if (!matchedExt) {
            console.warn('[Doocti] Employee/Extension mapping unavailable: No WebRTC extension found for user', { userId: user.id, employeeId: user.employee_id, username: user.username, availableExtensions: Object.keys(mapping) });
            setDidErrorNotice('No WebRTC extension is assigned to your user account. Please contact Administrator to map an extension in Settings → Integrations.');
          } else if (!isExtActive) {
            setDidErrorNotice(`WebRTC extension ${matchedExt} is currently deactivated. Please contact Administrator.`);
          } else if (!assignedDid) {
            setDidErrorNotice(`Extension ${matchedExt} does not have an outbound DID assigned. Outbound calls are disabled until an Admin assigns a DID in Settings.`);
          } else {
            setDidErrorNotice(null);
          }

          setConfig(prev => {
            const nextExt = matchedExt || prev.userNumber || '';
            const updated = {
              ...prev,
              domain: res.data.api_url || res.data.webphone_url || prev.domain || '',
              tenantId: res.data.account_id || res.data.tenant_id || prev.tenantId || '',
              userId: nextExt,
              userNumber: nextExt,
              userEmail: (matchedExt && mapping[matchedExt]?.email) || prev.userEmail || '',
              cliNumber: assignedDid || '',
              didNumbers: Array.isArray(dids) ? dids : []
            };
            localStorage.setItem('doocti_config', JSON.stringify(updated));
            return updated;
          });
        }
      })
      .catch(() => {});
  }, [user]);

  // Keypad & Number State
  const [dialNumber, setDialNumber] = useState('');
  const [matchedLead, setMatchedLead] = useState(null);
  const [dialerNotice, setDialerNotice] = useState(null);

  // In-Call State
  const [activeCall, setActiveCall] = useState(null); // { number, name, startTime, isMuted, isHeld }
  const [callDuration, setCallDuration] = useState(0);
  const [isRinging, setIsRinging] = useState(false);

  // Synchronous refs to prevent race conditions during asynchronous message handling
  const activeCallRef = useRef(null);
  activeCallRef.current = activeCall;

  // Recent Calls & Leads Data
  const [recentCalls, setRecentCalls] = useState([]);
  const [loadingCalls, setLoadingCalls] = useState(false);
  const [leadsList, setLeadsList] = useState([]);
  const [loadingLeads, setLoadingLeads] = useState(false);
  const [leadSearchQuery, setLeadSearchQuery] = useState('');

  // Audio Playback
  const [playingAudioId, setPlayingAudioId] = useState(null);
  const audioPlayerRef = useRef(null);

  const iframeRef = useRef(null);
  const activeSessionRef = useRef(null);
  const timerIntervalRef = useRef(null);
  const connectingTimeoutRef = useRef(null);
  const isEndingCallRef = useRef(false);
  const dialpadInputRef = useRef(null);

  // -------------------------------------------------------------
  // Telephony engine lifecycle
  // -------------------------------------------------------------
  // The DooCTI webphone must be mounted with a real URL. An empty `src` makes the
  // browser load the CRM itself inside the iframe (nested app, no SIP registration).
  const rawTelephonySrc = String(config.domain || '').trim() || 'https://beta3-app.doocti.com/';
  const telephonySrc = rawTelephonySrc && !/^https?:\/\//i.test(rawTelephonySrc)
    ? `https://${rawTelephonySrc}`
    : rawTelephonySrc;
  const [iframeReady, setIframeReady] = useState(false);
  const iframeLoadCountRef = useRef(0);
  const iframeMountedAtRef = useRef(Date.now());
  const [micDiagnostic, setMicDiagnostic] = useState(null);

  // True once the provider document has signalled load, or if it has been mounted long
  // enough that a missing load event cannot be the reason a dial would fail.
  const isTelephonyReady = () =>
    iframeReady || (Date.now() - iframeMountedAtRef.current > 4000 && Boolean(iframeRef.current?.contentWindow));

  // WebRTC (getUserMedia) is unavailable on insecure origins. Without it the agent
  // leg of every call has no microphone: outbound legs are dropped by the PBX and
  // inbound calls ring but can never be answered with audio.
  const mediaDevicesAvailable = typeof navigator !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia);

  // Auto-focus dialpad number input when switching to dialpad tab
  useEffect(() => {
    if (activeTab === 'dialpad' && !isMinimized) {
      const timer = setTimeout(() => {
        dialpadInputRef.current?.focus();
      }, 60);
      return () => clearTimeout(timer);
    }
  }, [activeTab, isMinimized]);

  // Sync minimize state with localStorage
  const toggleMinimize = (minimizedState) => {
    const next = typeof minimizedState === 'boolean' ? minimizedState : !isMinimized;
    setIsMinimized(next);
    localStorage.setItem('doocti_minimized', JSON.stringify(next));
  };

  // Reload iframe in case agent session loses audio connection
  const handleReloadIframe = () => {
    // Reloading the provider document destroys the live SIP session, so it is never
    // allowed while a call is in progress.
    if (activeSessionRef.current || activeCallRef.current) {
      setDialerNotice({
        type: 'warning',
        title: 'Reload Blocked During Call',
        message: 'The WebPhone cannot be reloaded while a call is active: reloading destroys the SIP session. Hang up first.'
      });
      return;
    }
    if (iframeRef.current) {
      const currentSrc = iframeRef.current.src;
      setIframeReady(false);
      iframeMountedAtRef.current = Date.now();
      iframeRef.current.src = 'about:blank';
      setTimeout(() => {
        if (iframeRef.current) {
          iframeRef.current.src = currentSrc;
        }
      }, 150);
    }
    fetchRecentCalls();
  };

  // Tracks provider document (re)loads. A reload during an active call means the
  // provider document was destroyed (token expiry redirect, manual refresh, crash),
  // taking the SIP session with it.
  const handleIframeLoad = () => {
    iframeLoadCountRef.current += 1;
    setIframeReady(true);
    console.info('[Doocti] WebPhone iframe loaded (load #' + iframeLoadCountRef.current + ') from', telephonySrc);

    const session = activeSessionRef.current;
    if (iframeLoadCountRef.current > 1 && session) {
      console.warn('[Doocti] WebPhone document reloaded during an active call — the SIP session no longer exists.', {
        sessionId: session.callId,
        direction: session.direction,
        status: session.status
      });
      setDialerNotice({
        type: 'error',
        title: 'WebPhone Reloaded During Call',
        message: 'The DooCTI phone document reloaded, which terminates the SIP session. The call was ended. Re-open the phone panel and place the call again.'
      });
      handleEndCall('FAILED');
    }
  };

  // Explicit microphone diagnostic: surfaces the exact WebRTC error name
  // (NotAllowedError / NotFoundError / NotReadableError / SecurityError).
  const testMicrophone = async () => {
    setMicDiagnostic('checking');
    if (!mediaDevicesAvailable) {
      setMicDiagnostic('unavailable');
      console.error('[Doocti] getUserMedia unavailable — CRM is not a secure context (HTTPS/localhost required) or the browser blocks media devices.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      setMicDiagnostic('ok');
      console.info('[Doocti] Microphone access granted');
    } catch (err) {
      setMicDiagnostic(err?.name || 'error');
      console.error('[Doocti] Microphone access failed:', err?.name, err?.message);
    }
  };

  // Any change of provider URL re-mounts (and therefore restarts) the WebPhone document.
  useEffect(() => {
    iframeMountedAtRef.current = Date.now();
    setIframeReady(false);
  }, [telephonySrc]);

  // Save custom configuration
  const handleSaveConfig = (e) => {
    e.preventDefault();
    setConfig(tempConfig);
    localStorage.setItem('doocti_config', JSON.stringify(tempConfig));
    setShowSettings(false);
  };

  // Fetch recent calls
  const fetchRecentCalls = async () => {
    setLoadingCalls(true);
    try {
      const res = await API.get('/ivr/calls?limit=40');
      const items = Array.isArray(res.data) ? res.data : (res.data?.items || []);
      setRecentCalls(items);
    } catch (e) {
      console.warn('Failed to fetch recent calls:', e);
      setRecentCalls([]);
    } finally {
      setLoadingCalls(false);
    }
  };

  // Fetch CRM leads for Lead Dial directory
  const fetchLeads = async (searchVal = '') => {
    setLoadingLeads(true);
    try {
      const endpoint = searchVal ? `/leads?search=${encodeURIComponent(searchVal)}&limit=30` : '/leads?limit=30';
      const res = await API.get(endpoint);
      const items = Array.isArray(res.data) ? res.data : (res.data?.items || []);
      setLeadsList(items);
    } catch (err) {
      console.warn('Failed to fetch leads for dialer:', err);
      setLeadsList([]);
    } finally {
      setLoadingLeads(false);
    }
  };

  useEffect(() => {
    fetchRecentCalls();
    // Auto-poll recent calls every 6 seconds so inbound and missed calls appear automatically
    const pollInterval = setInterval(() => {
      if (!activeCall && !isRinging) {
        fetchRecentCalls();
      }
    }, 6000);
    return () => clearInterval(pollInterval);
  }, [activeCall, isRinging]);

  // Live Lead Lookup as user types number (Strictly read-only, never auto-creates)
  useEffect(() => {
    const cleanNum = dialNumber.replace(/[^0-9]/g, '');
    if (cleanNum.length >= 6) {
      API.get(`/doocti/lead-by-number?number=${cleanNum}&auto_create=false`)
        .then(res => {
          if (res.data?.success && res.data?.lead) {
            setMatchedLead(res.data.lead);
          } else {
            setMatchedLead(null);
          }
        })
        .catch(() => setMatchedLead(null));
    } else {
      setMatchedLead(null);
    }
  }, [dialNumber]);

  // Active call duration timer: strictly runs ONLY when client answers / call is connected
  useEffect(() => {
    const isConnected = activeCall && (activeCall.callStatus === 'CONNECTED' || activeCall.callStatus === 'ANSWERED') && activeCall.answeredAt;

    if (isConnected) {
      // Calculate initial duration in seconds
      setCallDuration(Math.max(0, Math.floor((Date.now() - activeCall.answeredAt) / 1000)));

      timerIntervalRef.current = setInterval(() => {
        setCallDuration(Math.max(0, Math.floor((Date.now() - activeCall.answeredAt) / 1000)));
      }, 1000);
    } else {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
      setCallDuration(0);
    }
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    };
  }, [activeCall?.callStatus, activeCall?.answeredAt]);

  // Background server-side status synchronization for active call
  useEffect(() => {
    let pollTimer = null;
    if (activeCall && !['COMPLETED', 'NO_ANSWER', 'BUSY', 'FAILED'].includes(activeCall.callStatus)) {
      pollTimer = setInterval(async () => {
        try {
          const res = await API.get('/ivr/calls?limit=1');
          const latest = res.data?.items?.[0];
          if (!latest) return;

          const session = activeSessionRef.current;
          if (!session) return;
          const cleanTarget = session.customerPhone || activeCall.number;
          const isLatestSameTarget = cleanTarget && (latest.to_number?.includes(cleanTarget) || latest.from_number?.includes(cleanTarget) || latest.customer_phone?.includes(cleanTarget));

          // Guard against matching stale call records from past calls/days
          const callStartTime = session.startTime || 0;
          const latestCreatedTime = latest.created_at ? new Date(latest.created_at).getTime() : 0;
          const latestDirection = String(latest.call_direction || '').toUpperCase();
          const isSameDirection = !latestDirection || latestDirection === session.direction;
          // A record belongs to this session only if it was created after we dialed,
          // or if it carries the exact db/provider id that we already adopted for this session.
          const isNewerThanDial = latestCreatedTime >= callStartTime;
          const isSameCallId = Boolean(session.dbCallId && latest.id === session.dbCallId);
          const isSameProviderId = Boolean(
            session.providerCallId && latest.provider_call_id && latest.provider_call_id === session.providerCallId
          );
          const isCorrelated = isSameCallId || isSameProviderId || isNewerThanDial;

          if (!isLatestSameTarget || !isSameDirection || !isCorrelated) return;

          const st = (latest.call_status || '').toUpperCase();
          if (st === 'RINGING' && activeCall.callStatus === 'CONNECTING') {
            if (connectingTimeoutRef.current) {
              clearTimeout(connectingTimeoutRef.current);
              connectingTimeoutRef.current = null;
            }
            setActiveCall(prev => prev ? ({ ...prev, callStatus: 'RINGING' }) : null);
          } else if (['ANSWERED', 'CONNECTED'].includes(st) && activeCall.callStatus !== 'CONNECTED') {
            if (connectingTimeoutRef.current) {
              clearTimeout(connectingTimeoutRef.current);
              connectingTimeoutRef.current = null;
            }
            // Adopt the identifiers of the correlated server record for the rest of this session
            if (latest.id) session.dbCallId = latest.id;
            if (latest.provider_call_id) session.providerCallId = latest.provider_call_id;
            const ansTime = latest.answered_at ? new Date(latest.answered_at).getTime() : Date.now();
            session.answeredAt = ansTime;
            session.status = 'ANSWERED';
            setActiveCall(prev => prev ? ({
              ...prev,
              callStatus: 'CONNECTED',
              answeredAt: ansTime
            }) : null);
          } else if (['COMPLETED', 'NO_ANSWER', 'BUSY', 'FAILED', 'MISSED'].includes(st)) {
            // Terminal records are only trusted when they are strictly tied to this session.
            // A stale record for the same phone number must never tear down a live call.
            const isStrictlyCorrelated = isSameCallId || isSameProviderId;
            const elapsed = Date.now() - callStartTime;
            if (!isStrictlyCorrelated) {
              if (session.direction === 'OUTBOUND' && elapsed < 10000) return;
              if (latestCreatedTime < callStartTime) return;
            }
            if (latest.ended_at) {
              const diffMs = Date.now() - new Date(latest.ended_at).getTime();
              if (diffMs > 300000 || diffMs < 0) return;
            }
            if (connectingTimeoutRef.current) {
              clearTimeout(connectingTimeoutRef.current);
              connectingTimeoutRef.current = null;
            }
            if (latest.id) session.dbCallId = latest.id;
            if (latest.provider_call_id) session.providerCallId = latest.provider_call_id;
            // The iframe's own terminal event is authoritative; polling is only a fallback.
            console.warn('[Doocti] Terminating local session from server CDR fallback:', {
              status: st,
              callId: latest.id,
              providerCallId: latest.provider_call_id,
              correlatedBy: isSameCallId ? 'dbCallId' : (isSameProviderId ? 'providerCallId' : 'created-after-dial'),
              sessionId: session.callId
            });
            handleEndCall(st);
          }
        } catch (e) {
          // Silent polling error
        }
      }, 2500);
    }

    return () => {
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [activeCall?.callStatus, activeCall?.number]);

  // -------------------------------------------------------------
  // -------------------------------------------------------------
  // Click-To-Call: Dispatches postMessage into Doocti Iframe
  // -------------------------------------------------------------
  const dialLead = (phoneNumber, contactData = {}) => {
    if (!phoneNumber) return;
    setDialerNotice(null);
    setIsRinging(false);

    // The provider must be configured and actually loaded before a C2C dial can be
    // delivered. Without this gate the message is posted into a blank/foreign document.
    if (!telephonySrc) {
      setDialerNotice({
        type: 'error',
        title: 'Call Prevented: WebPhone Not Configured',
        message: 'No DooCTI WebPhone URL is configured for this CRM. Set the DooCTI API / WebPhone URL in the backend IVR integration settings, then reopen the phone panel.'
      });
      toggleMinimize(false);
      return;
    }
    if (!isTelephonyReady()) {
      setDialerNotice({
        type: 'warning',
        title: 'WebPhone Still Loading',
        message: 'The DooCTI phone panel has not finished loading yet. Wait for it to display the agent status, then place the call again.'
      });
      toggleMinimize(false);
      console.info('[Doocti] Dial blocked — phone panel not ready yet', {
        iframeReady,
        loadedAfterMs: Date.now() - iframeMountedAtRef.current
      });
      return;
    }

    // Duplicate-dial guard: a second C2C message while a session is live makes the PBX
    // originate another call to the same agent, which tears the first one down.
    const liveSession = activeSessionRef.current;
    if (liveSession && !isEndingCallRef.current) {
      const liveAge = Date.now() - (liveSession.startTime || 0);
      const isAnsweredOrRinging = ['RINGING', 'ANSWERED'].includes(liveSession.status);
      const isRecentConnecting = liveSession.status === 'CONNECTING' && liveAge < 15000;
      if (isAnsweredOrRinging || isRecentConnecting) {
        console.warn('[Doocti] Dial blocked — a call session is already in progress:', {
          sessionId: liveSession.callId,
          status: liveSession.status,
          ageMs: liveAge
        });
        setDialerNotice({
          type: 'warning',
          title: 'Call Already In Progress',
          message: isAnsweredOrRinging
            ? 'A call is already active in the phone panel. Hang up or decline it before dialing a new number.'
            : 'A call is currently connecting. Click Cancel on the connecting call if you want to dial a new number.'
        });
        toggleMinimize(false);
        return;
      }
    }

    // Validate outbound caller ID (DID) assignment
    let outboundCli = String(config.cliNumber || '').trim();
    if (!outboundCli && config.didNumbers && config.didNumbers.length > 0) {
      outboundCli = String(config.didNumbers[0]).trim();
    }
    if (!outboundCli) {
      setDialerNotice({
        type: 'error',
        title: 'Call Prevented: No Outbound DID Assigned',
        message: didErrorNotice || `Extension ${config.userNumber || ''} has no outbound DID assigned. Outbound calls are prevented to avoid displaying an incorrect Caller ID. Please contact an Administrator.`
      });
      toggleMinimize(false);
      return;
    }

    // Normalize phone number to 10-digit format (strip 91 country code or leading 0)
    let cleanNumber = String(phoneNumber).replace(/[^0-9]/g, '');
    if (cleanNumber.length === 12 && cleanNumber.startsWith('91')) {
      cleanNumber = cleanNumber.slice(2);
    } else if (cleanNumber.length === 11 && cleanNumber.startsWith('0')) {
      cleanNumber = cleanNumber.slice(1);
    } else if (cleanNumber.length > 10) {
      cleanNumber = cleanNumber.slice(-10);
    }

    // Always ensure contactData contains matchedLead if not already provided
    const resolvedContactData = (contactData && (contactData.id || contactData.lead_id))
      ? contactData
      : (matchedLead || contactData || {});

    const leadName = resolvedContactData.name || resolvedContactData.contact_name || resolvedContactData.lead_name || matchedLead?.name || 'Customer';
    const userExt = String(config.userNumber || '').trim();
    if (!userExt) {
      setDialerNotice({
        type: 'error',
        title: 'Call Prevented: No Extension Assigned',
        message: 'No WebRTC extension is assigned to your user account. Please contact Administrator to map an extension in Settings.'
      });
      toggleMinimize(false);
      return;
    }
    const uniqueSessionId = `doocti_${userExt}_${cleanNumber}_${Date.now()}`;

    // Payload formatted specifically for Doocti C2C handler:
    // IMPORTANT: Do NOT include customer_number to ensure Doocti's listener executes branch C,
    // which extracts cli_number and passes it into An(phone, station, id, name, cli_number, unique_id)
    const payload = {
      entity_id: String(resolvedContactData.id || resolvedContactData.lead_id || matchedLead?.id || '0'),
      entity_name: leadName,
      entity_number: cleanNumber,
      entity_type: resolvedContactData.entity_type || (resolvedContactData.company ? 'Contact' : 'Leads'),
      cli_number: outboundCli,
      crm_unique_id: uniqueSessionId,
      station: userExt,
      tenant_id: String(config.tenantId || '').trim(),
      user_email: String(config.userEmail || user?.email || '').trim(),
      user_id: userExt,
      user_number: userExt
    };

    activeSessionRef.current = {
      callId: uniqueSessionId,
      customerPhone: cleanNumber,
      contactData: resolvedContactData,
      startTime: Date.now(),
      answeredAt: null,
      employeeId: user?.employee_id || user?.id,
      agentName: user?.name,
      agentEmail: user?.email,
      direction: 'OUTBOUND',
      status: 'CONNECTING'
    };

    const callObj = {
      number: cleanNumber,
      name: leadName,
      callStatus: 'CONNECTING',
      startedAt: Date.now(),
      answeredAt: null,
      isMuted: false,
      isHeld: false
    };
    activeCallRef.current = callObj;
    setActiveCall(callObj);

    setCallDuration(0);
    toggleMinimize(false);

    // Timeout safety: only if Doocti never sends any telephony signal and call remains strictly in CONNECTING
    // Clear connecting timeout on any new dial attempt
    if (connectingTimeoutRef.current) {
      clearTimeout(connectingTimeoutRef.current);
    }
    connectingTimeoutRef.current = setTimeout(() => {
      const session = activeSessionRef.current;
      const current = activeCallRef.current;
      // ONLY warn if the call is still strictly in CONNECTING state and no answer or progress occurred.
      // Non-destructive: the session is kept so a slow-answering call is never removed from the UI.
      const wasAnswered = Boolean(session?.answeredAt || current?.answeredAt || session?.status === 'ANSWERED');
      if (current && current.callStatus === 'CONNECTING' && !wasAnswered) {
        console.warn('[Doocti] 30s elapsed with no telephony progress signal for call:', session?.callId);
        setDialerNotice({
          type: 'warning',
          title: 'No Call Progress Detected',
          message: 'Doocti WebPhone has not reported progress yet. If the call is not dialing, verify: 1) Agent status in Doocti WebPhone is "Online" (Green) and not Paused, 2) Microphone access is allowed.'
        });
      }
    }, 30000);

    // Dispatch postMessage using wildcard target origin to ensure iframe receipt
    if (iframeRef.current && iframeRef.current.contentWindow) {
      try {
        // Dispatch Click-to-Call message matching Doocti's expected C2C schema
        // Passing entity_number and cli_number routes through Doocti's branch D,
        // which supplies all 6 parameters to An(phone, station, id, customer_name, cli_number, unique_id)
        // and triggers Asterisk Originate via POST /api/crm/call with the agent's assigned outbound DID.
        console.info('[Doocti] Dispatching C2C dial:', {
          number: cleanNumber,
          cli: outboundCli,
          station: userExt,
          sessionId: uniqueSessionId
        });
        iframeRef.current.contentWindow.postMessage({ data: payload }, '*');
      } catch (err) {
        console.error('Failed to dispatch postMessage to Doocti iframe:', err);
      }
    }
  };

  // Answer Call Handler for Incoming Ringing Call
  // The deployed DooCTI iframe exposes no answer command to the parent page: its message
  // handler only supports C2C dialing, Logout, LeadStatus and AutoLogin. The SIP session can
  // therefore only be answered inside the provider's own phone UI (session.answer()).
  // We surface that UI and never fake a CONNECTED/ANSWERED state from the CRM.
  const handleAnswerCall = () => {
    if (connectingTimeoutRef.current) {
      clearTimeout(connectingTimeoutRef.current);
      connectingTimeoutRef.current = null;
    }
    toggleMinimize(false);
  };

  // Cancel connecting call handler: allows agent to immediately abort a stuck dial attempt
  const handleCancelCall = () => {
    if (connectingTimeoutRef.current) {
      clearTimeout(connectingTimeoutRef.current);
      connectingTimeoutRef.current = null;
    }
    handleEndCall('NO_ANSWER');
  };

  // End / Decline Call Handler
  // Invoked only from provider/backend terminal signals (iframe hangup event, CDR polling).
  // The CRM cannot terminate a SIP session itself, so no hangup postMessage is sent.
  const handleEndCall = (outcomeOverride = null, phoneOverride = null) => {
    if (connectingTimeoutRef.current) {
      clearTimeout(connectingTimeoutRef.current);
      connectingTimeoutRef.current = null;
    }
    if (isEndingCallRef.current) return;
    const session = activeSessionRef.current;
    const currentCall = activeCall;
    const wasRinging = isRinging;

    if (!session && !currentCall && !wasRinging) {
      setActiveCall(null);
      activeSessionRef.current = null;
      setDialNumber('');
      setMatchedLead(null);
      setIsRinging(false);
      setCallDuration(0);
      return;
    }

    isEndingCallRef.current = true;

    // 1. Stop timer immediately
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }

    const targetPhone = phoneOverride || (currentCall?.number && currentCall.number !== 'Connected Call' ? currentCall.number : null) || session?.customerPhone || dialNumber || 'Unknown';
    const cleanPhone = String(targetPhone || '').replace(/[^0-9]/g, '');
    const userExt = String(config.userNumber || '').replace(/[^0-9]/g, '');

    const wasAnswered = Boolean(
      currentCall?.answeredAt || 
      session?.answeredAt || 
      currentCall?.callStatus === 'CONNECTED' || 
      currentCall?.callStatus === 'ANSWERED' ||
      session?.status === 'ANSWERED' ||
      callDuration > 0
    );
    const answerTime = currentCall?.answeredAt || session?.answeredAt || (callDuration > 0 ? (Date.now() - callDuration * 1000) : null);
    const endTime = Date.now();

    // Actual talk duration is strictly calculated using ended_at - answered_at or running timer:
    let talkDuration = 0;
    if (wasAnswered) {
      if (answerTime) {
        talkDuration = Math.max(1, Math.round((endTime - answerTime) / 1000));
      } else if (callDuration > 0) {
        talkDuration = callDuration;
      }
    }

    // Determine final status accurately:
    // If the call was answered or had talk duration, it is ALWAYS COMPLETED and NEVER NO_ANSWER!
    let finalStatus = 'COMPLETED';
    const isDirectionInbound = session?.direction === 'INBOUND' || wasRinging;
    if (wasAnswered || talkDuration > 0) {
      finalStatus = 'COMPLETED';
    } else if (outcomeOverride && ['BUSY', 'FAILED', 'MISSED', 'NO_ANSWER'].includes(outcomeOverride)) {
      finalStatus = outcomeOverride;
      talkDuration = 0;
    } else if (wasRinging && !wasAnswered) {
      finalStatus = 'MISSED';
      talkDuration = 0;
    } else if (!wasAnswered) {
      finalStatus = isDirectionInbound ? 'MISSED' : 'NO_ANSWER';
      talkDuration = 0;
    } else {
      finalStatus = 'COMPLETED';
    }

    if (['NO_ANSWER', 'BUSY', 'FAILED', 'MISSED'].includes(finalStatus)) {
      talkDuration = 0;
    }

    // 2. Log CDR to CRM backend if phone has digits
    if (cleanPhone && cleanPhone.length >= 6 && cleanPhone !== userExt) {
      const resolvedEntityId = session?.contactData?.id || session?.contactData?.lead_id || matchedLead?.id || null;
      const pushPayload = {
        uniqueid: session?.callId || `doocti_${userExt}_${cleanPhone}_${Date.now()}`,
        phone_number: cleanPhone,
        station: userExt,
        agent: user?.name || config.userEmail,
        agent_email: user?.email || config.userEmail,
        employee_id: user?.employee_id || user?.id || null,
        status: finalStatus,
        duration: talkDuration,
        call_direction: session?.direction || (isDirectionInbound ? 'INBOUND' : 'OUTBOUND'),
        entity_id: resolvedEntityId,
        entity_type: 'Lead',
        start_time: session?.startTime ? new Date(session.startTime).toISOString() : new Date().toISOString(),
        answer_time: (wasAnswered && answerTime) ? new Date(answerTime).toISOString() : null,
        end_time: new Date(endTime).toISOString()
      };

      API.post('/doocti/call-log', pushPayload)
        .then((res) => {
          const detailData = { ...pushPayload, ...(res.data || {}) };
          window.dispatchEvent(new CustomEvent('crm-call-completed', { detail: detailData }));
          window.dispatchEvent(new CustomEvent('crm-incoming-call-ended', { detail: { callId: pushPayload.uniqueid, status: finalStatus } }));
          fetchRecentCalls();
        })
        .catch(() => {
          window.dispatchEvent(new CustomEvent('crm-call-completed', { detail: pushPayload }));
          window.dispatchEvent(new CustomEvent('crm-incoming-call-ended', { detail: { callId: pushPayload.uniqueid, status: finalStatus } }));
          fetchRecentCalls();
        });
    } else {
      const fallbackPayload = {
        uniqueid: session?.callId,
        phone_number: targetPhone,
        customer_phone: targetPhone,
        status: finalStatus,
        duration: talkDuration,
        call_direction: session?.direction || (isDirectionInbound ? 'INBOUND' : 'OUTBOUND'),
        lead_id: matchedLead?.id || session?.contactData?.id || null,
        lead_name: matchedLead?.name || session?.contactData?.name || null
      };
      window.dispatchEvent(new CustomEvent('crm-call-completed', { detail: fallbackPayload }));
      window.dispatchEvent(new CustomEvent('crm-incoming-call-ended', { detail: { callId: session?.callId, status: finalStatus } }));
    }

    // 3. The CRM never sends hangup/reject commands to the iframe: the deployed DooCTI
    //    webphone does not handle them, so the SIP session must terminate through the
    //    provider's own UI and its terminal event/CDR stays authoritative.

    // 4. Reset active call state cleanly without abrupt iframe reloads that trigger PBX re-ring loops
    activeCallRef.current = null;
    setActiveCall(null);
    activeSessionRef.current = null;
    setDialNumber('');
    setMatchedLead(null);
    setIsRinging(false);
    setCallDuration(0);

    setTimeout(() => {
      isEndingCallRef.current = false;
    }, 1000);
  };

  // Keypad Handlers with DTMF Audio
  const handleDigitClick = (digit) => {
    playDTMF(digit);
    setDialNumber(prev => (prev.length < 25 ? prev + digit : prev));
    dialpadInputRef.current?.focus();
  };

  const handleBackspace = () => {
    playClickTone(380);
    setDialNumber(prev => prev.slice(0, -1));
    dialpadInputRef.current?.focus();
  };

  const handleCallAction = () => {
    playCallConnectingTone();
    const clean = dialNumber.trim();
    if (!clean) {
      if (recentCalls && recentCalls.length > 0) {
        const lastCall = recentCalls[0];
        const lastPhone = lastCall.customer_phone || lastCall.to_number || lastCall.from_number;
        if (lastPhone) {
          setDialNumber(lastPhone);
          return;
        }
      }
      return;
    }
    dialLead(clean, matchedLead || {});
  };

  // Audio recording player toggle
  const handleToggleAudio = (callItem) => {
    if (!callItem.recording_url) {
      playClickTone(520);
      return;
    }
    if (playingAudioId === callItem.id) {
      if (audioPlayerRef.current) audioPlayerRef.current.pause();
      setPlayingAudioId(null);
    } else {
      setPlayingAudioId(callItem.id);
      if (audioPlayerRef.current) {
        audioPlayerRef.current.src = callItem.recording_url;
        audioPlayerRef.current.play().catch(e => console.warn(e));
      }
    }
  };

  // Inbound Window postMessage listener
  useEffect(() => {
    window.dooctiDial = (phone, contact) => dialLead(phone, contact);
    window.crmDial = (phone, contact) => dialLead(phone, contact);
    window.expandDoocti = () => toggleMinimize(false);

    const handleCustomDialEvent = (event) => {
      const { phone, contact } = event.detail || {};
      if (phone) dialLead(phone, contact);
    };
    window.addEventListener('crm-doocti-dial', handleCustomDialEvent);

    const handleWindowMessage = (event) => {
      let dooctiHost = '';
      try {
        dooctiHost = new URL(config.domain).hostname;
      } catch (e) {}
      if (event.origin && !event.origin.includes('doocti') && dooctiHost && !event.origin.includes(dooctiHost)) {
        return;
      }

      let msg = event.data;
      if (!msg) return;
      if (typeof msg === 'string') {
        try { msg = JSON.parse(msg); } catch (e) {}
      }

      const eventType = String(
        msg.type || msg.action || msg.event || msg.status || msg.calltype || msg.event_type || 
        msg.event_name || msg.method || (msg.data && (msg.data.type || msg.data.action || msg.data.event || msg.data.status)) || ''
      ).toLowerCase();
      const callState = String(
        msg.state || msg.call_state || msg.disposition || msg.callstatus || msg.callStatus || 
        (msg.data && (msg.data.state || msg.data.call_state || msg.data.disposition)) || ''
      ).toLowerCase();

      console.debug('[Doocti] WebPhone event:', {
        type: msg.type || msg.action || msg.event || msg.status || msg.calltype || '',
        calltype: msg.calltype || msg.call_type || '',
        phone: msg.phone_number || msg.customer_number || msg.number || '',
        raw: msg
      });

      // Clear connecting timeout on any received telephony progress event
      if (['ringing', 'ring', 'inbound', 'incoming', 'answered', 'connected', 'in-progress', 'inprogress', 'talking', 'busy', 'failed', 'hangup', 'disconnected', 'ended'].some(k => eventType.includes(k) || callState.includes(k))) {
        if (connectingTimeoutRef.current) {
          clearTimeout(connectingTimeoutRef.current);
          connectingTimeoutRef.current = null;
        }
      }

      // Ringing Detection (handles Doocti's { type: "Ringing", phone_number: ... })
      const isRingingSignal = ['ringing', 'ring', 'inbound', 'incoming', 'call_incoming'].some(k => eventType.includes(k) || callState.includes(k));

      if (isRingingSignal) {
        const rawNum = msg.phone_number || msg.customer_number || msg.number || msg.caller || '';
        const inNum = String(rawNum).replace(/[^0-9]/g, '');

        // GUARD: Require a provider-supplied call/session ID or a phone number for a valid ringing signal.
        // Keypad typing, input focus events, and other non-telephony messages will lack these fields.
        const providerCallId = msg.uniqueid || msg.call_id || msg.callid || msg.CallId || msg.id || '';
        const hasProviderIdentifier = Boolean(providerCallId && String(providerCallId).trim());
        const hasPhoneNumber = Boolean(inNum && inNum.length >= 6);

        if (!hasProviderIdentifier && !hasPhoneNumber) {
          // Not a real telephony ringing signal — ignore silently
          return;
        }

        // Check if an outbound call session is currently progressing (using synchronous ref + state)
        const currentSession = activeSessionRef.current;
        // An active outbound session is identified by its direction flag AND by the dialed number.
        // This prevents a ringing signal during an active outbound call from being treated as a new inbound call,
        // while still allowing a genuine inbound call from a different number to ring through.
        const isCurrentOutbound = currentSession?.direction === 'OUTBOUND';
        const sessionPhone = String(currentSession?.customerPhone || '').replace(/[^0-9]/g, '');
        const isMatchingOutboundPhone = Boolean(sessionPhone && inNum && (sessionPhone.includes(inNum) || inNum.includes(sessionPhone)));

        if (isCurrentOutbound && isMatchingOutboundPhone) {
          // Outbound call is progressing and ringing at customer endpoint, OR call already active
          if (activeSessionRef.current && activeSessionRef.current.direction === 'OUTBOUND') {
            activeSessionRef.current.status = 'RINGING';
          }
          const updatedCallObj = {
            ...(activeCallRef.current || activeCall || {}),
            callStatus: 'RINGING',
            number: activeCallRef.current?.number || activeCall?.number || inNum || rawNum,
            name: activeCallRef.current?.name || activeCall?.name || 'Customer'
          };
          activeCallRef.current = updatedCallObj;
          setActiveCall(updatedCallObj);
          return;
        } else {
          // INBOUND CALL ARRIVAL! (e.g. Doocti sending { type: "Ringing", phone_number: m })
          setIsRinging(true);
          toggleMinimize(false);
          const realCallId = providerCallId || `doocti_inbound_${Date.now()}`;

          // Guard against repeated Ringing events for the same inbound call to prevent duplicate logs
          const isSameInboundSession = activeSessionRef.current?.direction === 'INBOUND' && (
            activeSessionRef.current?.callId === realCallId ||
            (inNum && activeSessionRef.current?.customerPhone === inNum)
          );

          if (!isSameInboundSession) {
            activeSessionRef.current = {
              callId: realCallId,
              customerPhone: inNum || rawNum,
              startTime: Date.now(),
              direction: 'INBOUND',
              status: 'RINGING',
              loggedRinging: false
            };
          }

          const newInboundCall = {
            number: inNum || rawNum || 'Incoming Caller',
            name: msg.customer_name || 'Incoming Call',
            callStatus: 'RINGING',
            startedAt: Date.now(),
            answeredAt: null,
            isMuted: false,
            isHeld: false
          };
          activeCallRef.current = newInboundCall;
          setActiveCall(newInboundCall);

          // Only log RINGING to CRM backend once per unique inbound session
          if (!activeSessionRef.current?.loggedRinging) {
            activeSessionRef.current.loggedRinging = true;

            // 1. Fetch CRM lead details for caller ID in real time BEFORE logging RINGING
            if (inNum && inNum.length >= 6) {
              API.get(`/doocti/lead-by-number?number=${inNum}&auto_create=false`)
                .then(res => {
                  const lead = res.data?.lead || null;
                  if (activeSessionRef.current) {
                    activeSessionRef.current.contactData = lead;
                  }
                  const leadName = lead?.name || msg.customer_name || 'Incoming Caller';
                  setActiveCall(prev => prev ? ({
                    ...prev,
                    name: leadName,
                    contactData: lead
                  }) : null);

                  // Register call in CRM DB as RINGING with resolved entity_id to eliminate duplicate leads
                  API.post('/doocti/call-log', {
                    uniqueid: realCallId,
                    phone_number: inNum || rawNum,
                    station: config.userNumber || '',
                    agent: user?.name || config.userEmail,
                    agent_email: user?.email || config.userEmail,
                    employee_id: user?.employee_id || user?.id,
                    entity_id: lead?.id || null,
                    status: 'RINGING',
                    call_direction: 'INBOUND',
                    duration: 0,
                    start_time: new Date().toISOString()
                  }).then(logRes => {
                    if (logRes.data?.call_log_id && activeSessionRef.current) {
                      activeSessionRef.current.dbCallId = logRes.data.call_log_id;
                    }
                  }).catch(() => {});

                  // Dispatch global real-time event for Layout.jsx & other CRM components
                  window.dispatchEvent(new CustomEvent('crm-incoming-call', {
                    detail: {
                      id: activeSessionRef.current?.dbCallId || null,
                      provider_call_id: realCallId,
                      customer_phone: inNum || rawNum,
                      from_number: inNum || rawNum,
                      lead_name: leadName,
                      company: lead?.company || '',
                      lead_status: lead?.status || 'NEW',
                      employee_name: lead?.lead_owner || user?.name || 'Sales Representative',
                      call_status: 'RINGING',
                      call_direction: 'INBOUND',
                      started_at: new Date().toISOString()
                    }
                  }));
                })
                .catch(() => {
                  API.post('/doocti/call-log', {
                    uniqueid: realCallId,
                    phone_number: inNum || rawNum,
                    station: config.userNumber || '',
                    agent: user?.name || config.userEmail,
                    agent_email: user?.email || config.userEmail,
                    employee_id: user?.employee_id || user?.id,
                    status: 'RINGING',
                    call_direction: 'INBOUND',
                    duration: 0,
                    start_time: new Date().toISOString()
                  }).then(logRes => {
                    if (logRes.data?.call_log_id && activeSessionRef.current) {
                      activeSessionRef.current.dbCallId = logRes.data.call_log_id;
                    }
                  }).catch(() => {});

                  window.dispatchEvent(new CustomEvent('crm-incoming-call', {
                    detail: {
                      id: null,
                      provider_call_id: realCallId,
                      customer_phone: inNum || rawNum,
                      from_number: inNum || rawNum,
                      lead_name: msg.customer_name || 'Incoming Caller',
                      company: '',
                      lead_status: 'NEW',
                      employee_name: user?.name || 'Sales Representative',
                      call_status: 'RINGING',
                      call_direction: 'INBOUND',
                      started_at: new Date().toISOString()
                    }
                  }));
                });
            } else {
              API.post('/doocti/call-log', {
                uniqueid: realCallId,
                phone_number: inNum || rawNum,
                station: config.userNumber || '',
                agent: user?.name || config.userEmail,
                agent_email: user?.email || config.userEmail,
                employee_id: user?.employee_id || user?.id,
                status: 'RINGING',
                call_direction: 'INBOUND',
                duration: 0,
                start_time: new Date().toISOString()
              }).then(logRes => {
                if (logRes.data?.call_log_id && activeSessionRef.current) {
                  activeSessionRef.current.dbCallId = logRes.data.call_log_id;
                }
              }).catch(() => {});

              window.dispatchEvent(new CustomEvent('crm-incoming-call', {
                detail: {
                  id: null,
                  provider_call_id: realCallId,
                  customer_phone: rawNum || 'Unknown Caller',
                  from_number: rawNum || 'Unknown Caller',
                  lead_name: 'Incoming Caller',
                  company: '',
                  lead_status: 'NEW',
                  employee_name: user?.name || 'Sales Representative',
                  call_status: 'RINGING',
                  call_direction: 'INBOUND',
                  started_at: new Date().toISOString()
                }
              }));
            }
          }
        }
        return;
      }

      // Call Answered / Connected
      if (['answered', 'connected', 'in-progress', 'inprogress', 'talking', 'call_connected', 'call_answered', 'media_connected'].some(k => eventType.includes(k) || callState.includes(k))) {
        if (connectingTimeoutRef.current) {
          clearTimeout(connectingTimeoutRef.current);
          connectingTimeoutRef.current = null;
        }
        setIsRinging(false);
        const ansTime = Date.now();
        if (activeSessionRef.current) {
          activeSessionRef.current.answeredAt = ansTime;
          activeSessionRef.current.status = 'ANSWERED';
        }
        setActiveCall(prev => prev ? ({
          ...prev,
          callStatus: 'CONNECTED',
          answeredAt: prev.answeredAt || ansTime
        }) : {
          number: msg.phone_number || 'Connected Call',
          name: msg.customer_name || 'Customer',
          callStatus: 'CONNECTED',
          startedAt: ansTime,
          answeredAt: ansTime,
          isMuted: false,
          isHeld: false
        });

        window.dispatchEvent(new CustomEvent('crm-call-answered', {
          detail: {
            callId: activeSessionRef.current?.callId,
            dbCallId: activeSessionRef.current?.dbCallId
          }
        }));
        return;
      }

      const rawTermNum = msg.phone_number || msg.customer_number || msg.number || msg.destination || msg.callee || msg.caller || '';
      const cleanTermNum = String(rawTermNum || '').replace(/[^0-9]/g, '');
      const activeSession = activeSessionRef.current;
      const activePhone = String(activeSession?.customerPhone || activeCallRef.current?.number || '').replace(/[^0-9]/g, '');

      // Guard terminal events:
      // 1. If no active session or call exists, ignore
      if (!activeSession && !activeCallRef.current) {
        return;
      }

      // 2. Direction and phone correlation:
      //    Doocti's terminal event carries the direction in `calltype` and the customer number
      //    in `phone_number`. Only act on events that belong to the live session, and never let a
      //    mismatched or stale event clear a genuine call.
      const msgCallType = String(msg.calltype || msg.call_type || msg.direction || '').toLowerCase();
      if (msgCallType && activeSession?.direction) {
        const sessionDirection = activeSession.direction === 'OUTBOUND' ? 'outbound' : 'inbound';
        if (msgCallType !== sessionDirection) {
          console.debug('[Doocti] Ignoring terminal event for other direction:', msgCallType, 'expected:', sessionDirection);
          return;
        }
      }

      if (cleanTermNum.length >= 6 && activePhone.length >= 6) {
        if (!activePhone.includes(cleanTermNum) && !cleanTermNum.includes(activePhone)) {
          console.debug('[Doocti] Ignoring terminal event for mismatched phone:', cleanTermNum, 'expected:', activePhone);
          return;
        }
      }

      // Specific Terminal Outcomes
      if (['busy', 'line_busy', 'engaged'].some(k => eventType.includes(k) || callState.includes(k))) {
        setIsRinging(false);
        handleEndCall('BUSY', rawTermNum);
      } else if (['failed', 'error', 'call_failed'].some(k => eventType.includes(k) || callState.includes(k))) {
        setIsRinging(false);
        // For incoming calls that weren't answered, mark as MISSED, not FAILED
        const isInc = activeSessionRef.current?.direction === 'INBOUND' || isRinging;
        handleEndCall(isInc ? 'MISSED' : 'FAILED', rawTermNum);
      } else if (['no_answer', 'noanswer', 'unreachable', 'timeout'].some(k => eventType.includes(k) || callState.includes(k))) {
        setIsRinging(false);
        handleEndCall('MISSED', rawTermNum);
      } else if (['hangup', 'disconnected', 'ended', 'call_disconnect', 'call_ended', 'decline', 'rejected', 'terminate'].some(k => eventType.includes(k) || callState.includes(k))) {
        setIsRinging(false);
        handleEndCall(null, rawTermNum);
      }
    };

    // Expose the only supported control: surface the provider phone panel.
    // Answer/hangup cannot be driven from the CRM (no provider command exists).
    window.crmAnswerCall = () => handleAnswerCall();
    window.expandDoocti = () => toggleMinimize(false);

    window.addEventListener('message', handleWindowMessage);

    return () => {
      window.removeEventListener('crm-doocti-dial', handleCustomDialEvent);
      window.removeEventListener('message', handleWindowMessage);
    };
  }, [config, user, activeCall, callDuration, dialNumber]);

  // Filtered calls for Home screen
  const filteredRecentCalls = useMemo(() => {
    return recentCalls.filter(call => {
      const status = (call.call_status || '').toUpperCase();
      const isMissed = ['MISSED', 'NO_ANSWER', 'FAILED', 'BUSY'].includes(status);
      if (callFilter === 'missed' && !isMissed) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const phone = String(call.customer_phone || call.to_number || call.from_number || '').toLowerCase();
        const name = String(call.lead_name || '').toLowerCase();
        return phone.includes(q) || name.includes(q);
      }
      return true;
    });
  }, [recentCalls, callFilter, searchQuery]);

  const missedCount = useMemo(() => {
    return recentCalls.filter(c => ['MISSED', 'NO_ANSWER', 'FAILED', 'BUSY'].includes((c.call_status || '').toUpperCase())).length;
  }, [recentCalls]);

  return (
    <div className="doocti-container">
      {/* Hidden Audio Player for Recordings */}
      <audio 
        ref={audioPlayerRef} 
        onEnded={() => setPlayingAudioId(null)} 
        onError={() => setPlayingAudioId(null)}
        style={{ display: 'none' }}
      />

      {/* -----------------------------------------------------------
          1. Minimized Floating Pill (Docked at Bottom-Right)
      ------------------------------------------------------------ */}
      {isMinimized && (
        <div 
          className="doocti-minimized-pill"
          onClick={() => toggleMinimize(false)}
          title="Click to open CRM Softphone"
        >
          <div className="doocti-status-dot-wrapper">
            <div className={`doocti-status-dot ${isRinging ? 'ringing' : 'pulsing'}`} />
          </div>
          <PingoMascot pose="run" height={26} withShadow={false} />
          <div className="doocti-pill-info">
            <span className="doocti-pill-title">
              {activeCall ? `Active Call (${formatCallTimer(callDuration)})` : (isRinging ? 'Incoming Call...' : 'CRM Softphone')}
            </span>
            <span className="doocti-pill-ext">
              Ext: {config.userNumber} • Online
            </span>
          </div>
          <button 
            type="button" 
            className="doocti-pill-expand-btn"
            onClick={(e) => {
              e.stopPropagation();
              toggleMinimize(false);
            }}
            title="Expand Softphone"
          >
            <ChevronUp size={14} />
          </button>
        </div>
      )}

      {/* -----------------------------------------------------------
          2. Native CRM Softphone Window
          The window is NEVER unmounted or set to display:none: the DooCTI WebPhone
          iframe keeps its SIP registration, timers and audio engine alive while the
          CRM is minimized. It is only moved off-screen.
      ------------------------------------------------------------ */}
      <div 
        className={`native-dialer-window ${isMinimized ? 'is-minimized' : ((activeCall || isRinging) ? 'in-call' : '')}`}
        aria-hidden={isMinimized ? 'true' : 'false'}
      >
        {/* Top Header */}
        <div className="native-dialer-header">
          <div className="dialer-brand-group">
            <PingoMascot pose="run" height={34} withShadow={false} />
            <div className="doocti-status-dot-wrapper">
              <div className={`doocti-status-dot ${isRinging ? 'ringing' : 'pulsing'}`} />
            </div>
            <span className="dialer-brand-title">CRM Softphone</span>
            <span className="dialer-ext-pill">Ext {config.userNumber}</span>
          </div>

          <div className="dialer-header-actions">
            {/* Quick Reload Audio Session */}
            <button
              type="button"
              className="btn-dialer-icon"
              onClick={handleReloadIframe}
              title="Refresh / Reload Audio Session"
            >
              <RotateCw size={14} />
            </button>

            {/* Settings */}
            <button
              type="button"
              className="btn-dialer-icon"
              onClick={() => {
                setTempConfig(config);
                setShowSettings(!showSettings);
              }}
              title="Extension Settings"
            >
              <Settings size={14} />
            </button>

            {/* Minimize */}
            <button
              type="button"
              className="btn-dialer-icon btn-dialer-minimize"
              onClick={() => toggleMinimize(true)}
              title="Minimize Phone"
            >
              <Minus size={16} strokeWidth={2.5} />
            </button>
          </div>
        </div>

        {/* Settings Dropdown */}
        {showSettings && (
          <form className="doocti-settings-panel" onSubmit={handleSaveConfig}>
            <div>
              <label>Agent Extension:</label>
              <input
                type="text"
                value={tempConfig.userNumber}
                onChange={(e) => setTempConfig({ ...tempConfig, userNumber: e.target.value, userId: e.target.value })}
                placeholder="Extension number"
              />
            </div>
            <div>
              <label>Agent Email:</label>
              <input
                type="email"
                value={tempConfig.userEmail}
                onChange={(e) => setTempConfig({ ...tempConfig, userEmail: e.target.value })}
                placeholder="agent@company.com"
              />
            </div>
            <div>
              <label>Outbound Caller DID:</label>
              <select
                value={tempConfig.cliNumber || ''}
                onChange={(e) => setTempConfig({ ...tempConfig, cliNumber: e.target.value })}
                style={{
                  width: '100%',
                  padding: '6px 8px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  fontSize: '12px',
                  backgroundColor: '#fff',
                  marginTop: '4px'
                }}
              >
                <option value="">-- Select Assigned DID --</option>
                {(tempConfig.didNumbers || []).map(did => (
                  <option key={did} value={did}>{did}</option>
                ))}
              </select>
            </div>
            <div className="doocti-settings-actions">
              <button 
                type="button" 
                onClick={() => setShowSettings(false)}
                className="doocti-btn-cancel"
              >
                Cancel
              </button>
              <button type="submit" className="doocti-btn-save">
                Save
              </button>
            </div>

            {/* WebRTC diagnostics */}
            <div style={{ marginTop: '10px', borderTop: '1px solid #e2e8f0', paddingTop: '8px', fontSize: '11px', color: '#475569' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                <span>
                  WebPhone: {telephonySrc ? (iframeReady ? 'loaded' : 'loading…') : 'not configured'}
                </span>
                <button
                  type="button"
                  onClick={testMicrophone}
                  className="doocti-btn-cancel"
                  style={{ padding: '4px 10px' }}
                >
                  Test Microphone
                </button>
              </div>
              {micDiagnostic && (
                <div style={{ marginTop: '4px', color: micDiagnostic === 'ok' ? '#047857' : '#b91c1c' }}>
                  {micDiagnostic === 'checking' && 'Requesting microphone…'}
                  {micDiagnostic === 'ok' && 'Microphone OK'}
                  {micDiagnostic === 'unavailable' && 'getUserMedia unavailable (insecure context)'}
                  {!['checking', 'ok', 'unavailable'].includes(micDiagnostic) && `Microphone error: ${micDiagnostic}`}
                </div>
              )}
            </div>
          </form>
        )}

        {/* Persistent Error / Warning Notice for Unassigned DID or Deactivated Extension */}
        {didErrorNotice && !dialerNotice && (
          <div
            className="dialer-notice-banner"
            style={{
              margin: '10px 12px 4px 12px',
              padding: '10px 12px',
              backgroundColor: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
              fontSize: '12px',
              color: '#991b1b',
              lineHeight: '1.4'
            }}
          >
            <AlertCircle size={18} style={{ color: '#ef4444', flexShrink: 0, marginTop: '2px' }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: '700', marginBottom: '2px', color: '#991b1b' }}>Outbound Calling Disabled</div>
              <div>{didErrorNotice}</div>
            </div>
          </div>
        )}

        {/* Persistent WebRTC / microphone capability warning.
            Without getUserMedia the DooCTI WebPhone cannot attach audio: outbound legs
            are dropped by the PBX and inbound calls ring but cannot be answered. */}
        {!mediaDevicesAvailable && (
          <div
            className="dialer-notice-banner"
            style={{
              margin: '10px 12px 4px 12px',
              padding: '10px 12px',
              backgroundColor: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
              fontSize: '12px',
              color: '#991b1b',
              lineHeight: '1.45'
            }}
          >
            <AlertCircle size={16} style={{ color: '#ef4444', flexShrink: 0, marginTop: '2px' }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, marginBottom: '2px' }}>
                WebRTC Microphone Unavailable — Calls Cannot Connect
              </div>
              <div>
                This page is not running in a secure context (or the browser blocks media
                devices), so <code>navigator.mediaDevices.getUserMedia</code> does not exist.
                Open the CRM over <strong>HTTPS</strong> or <strong>localhost</strong>, allow
                microphone permission, then reload.
              </div>
            </div>
          </div>
        )}


        {/* Diagnostic Alert / Guidance Banner */}
        {dialerNotice && (
          <div
            className="dialer-notice-banner"
            style={{
              margin: '10px 12px 4px 12px',
              padding: '10px 12px',
              backgroundColor: '#fffbeb',
              border: '1px solid #fde68a',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
              fontSize: '12px',
              color: '#92400e',
              lineHeight: '1.45',
              boxShadow: '0 2px 5px rgba(0,0,0,0.05)'
            }}
          >
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px', color: '#d97706' }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, color: '#b45309', marginBottom: '2px' }}>{dialerNotice.title}</div>
              <div>{dialerNotice.message}</div>
            </div>
            <button
              type="button"
              onClick={() => setDialerNotice(null)}
              style={{
                background: 'none',
                border: 'none',
                color: '#b45309',
                cursor: 'pointer',
                padding: '2px',
                display: 'flex',
                alignItems: 'center'
              }}
              title="Dismiss"
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* -----------------------------------------------------------
            Screen 1: Active In-Call / Ringing Status Bar
        ------------------------------------------------------------ */}
        {(activeCall || isRinging) && (
          <div className="active-call-header-bar">
            <div className="active-call-header-lead">
              <div className={`active-call-pulse-ring-sm ${isRinging || activeCall?.callStatus === 'RINGING' ? 'ringing-pulse' : (activeCall?.callStatus === 'CONNECTED' ? 'connected-pulse' : '')}`} />
              <div className="active-call-header-meta">
                <span className="active-call-header-name">
                  {isRinging ? 'Incoming Call' : (activeCall?.name || 'Customer')}
                </span>
                <span className="active-call-header-phone">
                  {activeCall?.number || 'Caller ID'}
                </span>
              </div>
            </div>
            <div className="active-call-header-right">
              {isRinging ? (
                <div className="incoming-actions-guidance">
                  <span className="active-call-timer-badge ringing-badge">
                    Ringing...
                  </span>
                  <span className="active-call-control-hint" style={{ color: '#059669', fontWeight: 600 }}>
                    Click Answer in phone panel below
                  </span>
                </div>
              ) : (
                <>
                  {/* Status Indicator Badge */}
                  {activeCall?.callStatus === 'CONNECTING' ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="active-call-timer-badge connecting-badge">
                        <span className="recording-pulse-dot" style={{ backgroundColor: '#38bdf8' }} />
                        CONNECTING
                      </span>
                      <button
                        type="button"
                        onClick={handleCancelCall}
                        className="btn-cancel-connecting"
                        style={{
                          backgroundColor: '#fef2f2',
                          color: '#dc2626',
                          border: '1px solid #fecaca',
                          borderRadius: '6px',
                          padding: '3px 8px',
                          fontSize: '11px',
                          fontWeight: 700,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                        title="Cancel this connecting call"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : activeCall?.callStatus === 'RINGING' ? (
                    <span className="active-call-timer-badge ringing-badge">
                      <span className="recording-pulse-dot" style={{ backgroundColor: '#fbbf24' }} />
                      RINGING
                    </span>
                  ) : (
                    <span className="active-call-timer-badge connected-badge">
                      <span className="recording-pulse-dot" style={{ backgroundColor: '#34d399' }} />
                      CONNECTED
                    </span>
                  )}

                  {/* Talk Timer: strictly 00:00 until client answers */}
                  <span className="active-call-timer-badge" style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 700 }}>
                    {formatCallTimer(callDuration)}
                  </span>

                  {/* The SIP session can only be controlled from the DooCTI phone panel below. */}
                  <span className="active-call-control-hint">
                    {activeCall?.callStatus === 'CONNECTING' ? 'Phone panel controls active below' : 'Hang up in phone panel below'}
                  </span>
                </>
              )}
            </div>
          </div>
        )}

        {/* -----------------------------------------------------------
            Main Tab Views: Home (Recent Calls) | Dialpad | Lead Dial
        ------------------------------------------------------------ */}
        {!(activeCall || isRinging) && (
          <div className="dialer-body-content" style={{ display: activeTab === 'phone' ? 'none' : 'flex' }}>
            {/* -------------------- TAB 1: HOME (RECENT CALLS) -------------------- */}
            {activeTab === 'home' && (
              <div className="screen-home-calls">
                {/* Sub-Header: All Calls vs Missed Calls */}
                <div className="calls-filter-bar">
                  <button
                    type="button"
                    className={`call-subtab-btn ${callFilter === 'all' ? 'active' : ''}`}
                    onClick={() => setCallFilter('all')}
                  >
                    <span>All Calls</span>
                    <span className="count-pill">{recentCalls.length}</span>
                  </button>
                  <button
                    type="button"
                    className={`call-subtab-btn ${callFilter === 'missed' ? 'active' : ''}`}
                    onClick={() => setCallFilter('missed')}
                  >
                    <span>Missed</span>
                    {missedCount > 0 && <span className="count-pill count-missed">{missedCount}</span>}
                  </button>
                </div>

                {/* Search Bar */}
                <div className="calls-search-box">
                  <Search size={14} className="search-icon" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search name or number..."
                  />
                  {searchQuery && (
                    <button type="button" className="clear-search-btn" onClick={() => setSearchQuery('')}>
                      <X size={13} />
                    </button>
                  )}
                </div>

                {/* Calls Scroll List */}
                <div className="calls-history-list">
                  {loadingCalls ? (
                    <div className="calls-empty-state">
                      <div className="spinner-mini" />
                      <span>Loading call records...</span>
                    </div>
                  ) : filteredRecentCalls.length === 0 ? (
                    <div className="calls-empty-state">
                      <PhoneCall size={32} color="#cbd5e1" />
                      <p>No call logs found</p>
                      <span className="empty-subtitle">Your connected and missed calls will appear here.</span>
                    </div>
                  ) : (
                    filteredRecentCalls.map((item) => {
                      const phone = item.customer_phone || item.to_number || item.from_number || 'Unknown';
                      const name = item.lead_name || 'Customer';
                      const isMissed = ['MISSED', 'NO_ANSWER', 'FAILED', 'BUSY'].includes((item.call_status || '').toUpperCase());
                      const isIncoming = (item.call_direction || '').toUpperCase() === 'INBOUND';
                      const isPlaying = playingAudioId === item.id;

                      return (
                        <div key={item.id} className="call-history-row">
                          <div className={`call-direction-badge ${isMissed ? 'missed' : isIncoming ? 'inbound' : 'outbound'}`}>
                            {isMissed ? (
                              <PhoneMissed size={16} />
                            ) : isIncoming ? (
                              <ArrowDownLeft size={16} />
                            ) : (
                              <ArrowUpRight size={16} />
                            )}
                          </div>

                          <div className="call-info-block">
                            <div className="call-title-row">
                              <span className="call-contact-name" title={name}>{name}</span>
                              <span className={`call-status-tag ${isMissed ? 'missed' : 'completed'}`}>
                                {isMissed ? 'Missed' : 'Completed'}
                              </span>
                            </div>

                            <div className="call-number-row">
                              <span className="call-contact-phone">{phone}</span>
                            </div>

                            <div className="call-meta-row">
                              <span className="call-time-text">{formatCallTimestamp(item.created_at)}</span>
                              <span className="call-duration-text">
                                <Clock size={11} />
                                {formatDurationBadge(item.duration_seconds || item.duration)}
                              </span>
                            </div>
                          </div>

                          <div className="call-actions-block">
                            {/* Audio Recording / Mic Button */}
                            <button
                              type="button"
                              className={`btn-call-audio ${isPlaying ? 'playing' : ''} ${item.recording_url ? 'has-rec' : ''}`}
                              onClick={() => handleToggleAudio(item)}
                              title={item.recording_url ? (isPlaying ? "Stop Recording" : "Play Call Recording") : "Call Duration"}
                            >
                              {isPlaying ? <Volume2 size={15} /> : <Mic size={15} />}
                            </button>

                            {/* 1-Click Dial Button */}
                            <button
                              type="button"
                              className="btn-call-redial"
                              onClick={() => {
                                setDialNumber(phone);
                                dialLead(phone, { name: item.lead_name, id: item.lead_id });
                              }}
                              title={`Dial ${name} (${phone})`}
                            >
                              <PhoneCall size={15} />
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}

            {/* -------------------- TAB 2: DIALPAD -------------------- */}
            {activeTab === 'dialpad' && (
              <div className="dialpad-screen">
                {/* Number Display & Live Contact Match */}
                <div className="dialpad-display-area" onClick={() => dialpadInputRef.current?.focus()}>
                  {matchedLead && (
                    <div className="dialpad-lead-preview">
                      <UserCheck size={12} />
                      <span>{matchedLead.name}</span>
                      {matchedLead.company && <span className="lead-preview-comp">• {matchedLead.company}</span>}
                    </div>
                  )}
                  <div className="dialpad-input-wrapper">
                    <input
                      ref={dialpadInputRef}
                      type="tel"
                      className="dialpad-number-input"
                      value={dialNumber}
                      onChange={(e) => {
                        const val = e.target.value.replace(/[^0-9*#+]/g, '');
                        setDialNumber(val);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleCallAction();
                        } else if (['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '#'].includes(e.key)) {
                          playDTMF(e.key);
                        }
                      }}
                      placeholder="Enter number..."
                      autoComplete="off"
                      spellCheck={false}
                      autoFocus
                    />
                    {dialNumber.length > 0 && (
                      <button 
                        type="button" 
                        className="dialpad-backspace-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleBackspace();
                        }}
                        onDoubleClick={(e) => {
                          e.stopPropagation();
                          playClickTone(350);
                          setDialNumber('');
                          dialpadInputRef.current?.focus();
                        }}
                        title="Backspace (Double-click to clear)"
                      >
                        <Delete size={20} />
                      </button>
                    )}
                  </div>
                </div>

                {/* Number Keypad Grid (3x4) */}
                <div className="dialpad-grid">
                  {KEYPAD_BUTTONS.map((item) => (
                    <button
                      key={item.digit}
                      type="button"
                      className="dialpad-key"
                      onClick={() => handleDigitClick(item.digit)}
                    >
                      <span className="dialpad-digit">{item.digit}</span>
                      {item.letters && <span className="dialpad-letters">{item.letters}</span>}
                    </button>
                  ))}
                </div>

                {/* Big Green Dial / Call Button */}
                <div className="dialpad-actions-area">
                  <button
                    type="button"
                    className="btn-dial-call"
                    onClick={handleCallAction}
                    title={dialNumber ? `Call ${dialNumber}` : "Click to call or redial"}
                  >
                    <PhoneCall size={26} />
                  </button>
                </div>
              </div>
            )}

            {/* -------------------- TAB 3: LEAD DIAL (CRM DIRECTORY) -------------------- */}
            {activeTab === 'leads' && (
              <div className="screen-leads-dial">
                {/* Search Bar for Leads */}
                <div className="calls-search-box">
                  <Search size={14} className="search-icon" />
                  <input
                    type="text"
                    value={leadSearchQuery}
                    onChange={(e) => {
                      setLeadSearchQuery(e.target.value);
                      fetchLeads(e.target.value);
                    }}
                    placeholder="Search CRM leads..."
                  />
                  {leadSearchQuery && (
                    <button 
                      type="button" 
                      className="clear-search-btn" 
                      onClick={() => {
                        setLeadSearchQuery('');
                        fetchLeads('');
                      }}
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>

                {/* Leads Scroll List */}
                <div className="leads-directory-list">
                  {loadingLeads ? (
                    <div className="calls-empty-state">
                      <div className="spinner-mini" />
                      <span>Loading leads...</span>
                    </div>
                  ) : leadsList.length === 0 ? (
                    <div className="calls-empty-state">
                      <Users size={32} color="#cbd5e1" />
                      <p>No leads found</p>
                      <span className="empty-subtitle">Leads assigned to you in CRM will appear here.</span>
                    </div>
                  ) : (
                    leadsList.map((lead) => {
                      const phone = lead.phone || lead.mobile || lead.contact_number;
                      return (
                        <div key={lead.id} className="lead-dial-card">
                          <div className="lead-avatar" style={{ background: getAvatarColor(lead.name) }}>
                            {lead.name ? lead.name[0].toUpperCase() : 'L'}
                          </div>

                          <div className="lead-details-block">
                            <div className="lead-card-header">
                              <span className="lead-name-text" title={lead.name}>{lead.name}</span>
                              {lead.status && (
                                <span className="lead-status-chip">{lead.status}</span>
                              )}
                            </div>

                            <div className="lead-company-text">
                              {lead.company ? (
                                <>
                                  <Building size={11} />
                                  <span>{lead.company}</span>
                                </>
                              ) : (
                                <span>Prospect Lead</span>
                              )}
                            </div>

                            <div className="lead-phone-text">
                              {phone || 'No phone number'}
                            </div>
                          </div>

                          <button
                            type="button"
                            className="btn-lead-call"
                            disabled={!phone}
                            onClick={() => {
                              if (phone) {
                                setDialNumber(phone);
                                dialLead(phone, lead);
                              }
                            }}
                            title={phone ? `Call ${lead.name} (${phone})` : "No phone number available"}
                          >
                            <PhoneCall size={16} />
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* -----------------------------------------------------------
            Bottom Navigation Bar: Home | Dialpad | Lead Dial | WebPhone
        ------------------------------------------------------------ */}
        {!(activeCall || isRinging) && (
          <div className="softphone-bottom-nav">
            <button
              type="button"
              className={`bottom-nav-btn ${activeTab === 'home' ? 'active' : ''}`}
              onClick={() => {
                setActiveTab('home');
                window.focus();
                fetchRecentCalls();
              }}
            >
              <Home size={19} />
              <span>Home</span>
            </button>

            <button
              type="button"
              className={`bottom-nav-btn ${activeTab === 'dialpad' ? 'active' : ''}`}
              onClick={() => {
                setActiveTab('dialpad');
                window.focus();
                setTimeout(() => dialpadInputRef.current?.focus(), 30);
              }}
            >
              <Grid size={19} />
              <span>Dialpad</span>
            </button>

            <button
              type="button"
              className={`bottom-nav-btn ${activeTab === 'leads' ? 'active' : ''}`}
              onClick={() => {
                setActiveTab('leads');
                window.focus();
                fetchLeads(leadSearchQuery);
              }}
            >
              <Users size={19} />
              <span>Lead Dial</span>
            </button>

            <button
              type="button"
              className={`bottom-nav-btn ${activeTab === 'phone' ? 'active' : ''}`}
              onClick={() => setActiveTab('phone')}
              title="Live Doocti WebPhone & Queue Status"
            >
              <Radio size={19} />
              <span>WebPhone</span>
            </button>
          </div>
        )}

        {/* -----------------------------------------------------------
            Doocti Telephony Engine (Active WebPhone during Call or WebPhone Tab)
        ------------------------------------------------------------ */}
        <div className={`doocti-telephony-wrapper ${(activeCall || isRinging) ? 'active-mode' : (activeTab === 'phone' ? 'tab-mode' : 'background-mode')}`}>
          {telephonySrc ? (
            <iframe
              ref={iframeRef}
              src={telephonySrc}
              title="Doocti Telephony Engine"
              className="doocti-telephony-iframe"
              onLoad={handleIframeLoad}
              allow="microphone; camera; autoplay; display-capture; clipboard-read; clipboard-write; speaker-selection"
            />
          ) : (
            <div className="doocti-telephony-missing">
              <AlertCircle size={22} />
              <div>
                <strong>WebPhone Not Configured</strong>
                <p>
                  No DooCTI WebPhone URL is configured. Set it in the backend IVR
                  integration (DooCTI <code>api_url</code> / WebPhone URL), then reload
                  this page.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DooctiInAppDialer;
