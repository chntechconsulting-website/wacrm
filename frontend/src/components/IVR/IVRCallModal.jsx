import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import { 
  PhoneCall, 
  PhoneOff, 
  AlertCircle, 
  X, 
  CheckCircle, 
  Clock, 
  Sliders,
  Volume2,
  Mic,
  UserCheck,
  Radio,
  FileText,
  Smartphone,
  Check,
  ExternalLink,
  RotateCcw
} from 'lucide-react';

const IVRCallModal = ({ lead, customerPhone, isOpen, onClose, onCallStarted, onCallComplete }) => {
  const [loading, setLoading] = useState(false);
  const [endingCall, setEndingCall] = useState(false);
  const [error, setError] = useState('');
  const [unconfiguredMsg, setUnconfiguredMsg] = useState('');
  const [activeCall, setActiveCall] = useState(null);
  const [callNotes, setCallNotes] = useState('');

  // Fallback Direct Device / Manual Call States
  const [directCallMode, setDirectCallMode] = useState('none'); // 'none' | 'active' | 'manual'
  const [directTimer, setDirectTimer] = useState(0);
  const [directCallRunning, setDirectCallRunning] = useState(false);
  const [directStatus, setDirectStatus] = useState('COMPLETED');
  const [manualMinutes, setManualMinutes] = useState(1);
  const [savingManual, setSavingManual] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Call Connected Timestamp and Timer
  const [connectedAt, setConnectedAt] = useState(null);
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [isTimerRunning, setIsTimerRunning] = useState(false);

  // Status helper functions
  const isTerminalStatus = (status) => {
    if (!status) return false;
    const upper = status.toUpperCase();
    return ['COMPLETED', 'FAILED', 'MISSED', 'BUSY', 'HANGUP', 'CANCELED', 'NO_ANSWER'].includes(upper);
  };

  const isConnectedStatus = (status) => {
    if (!status) return false;
    const upper = status.toUpperCase();
    return ['CONNECTED', 'ANSWERED', 'IN_PROGRESS', 'IN-PROGRESS'].includes(upper);
  };

  const isRingingStatus = (status) => {
    if (!status) return false;
    return status.toUpperCase() === 'RINGING';
  };

  // Reset modal state on open
  useEffect(() => {
    if (isOpen) {
      setError('');
      setUnconfiguredMsg('');
      setActiveCall(null);
      setCallNotes('');
      setConnectedAt(null);
      setTimerSeconds(0);
      setIsTimerRunning(false);
      setLoading(false);
      setEndingCall(false);
      setDirectCallMode('none');
      setDirectTimer(0);
      setDirectCallRunning(false);
      setDirectStatus('COMPLETED');
      setManualMinutes(1);
      setSavingManual(false);
      setSaveSuccess(false);
    }
  }, [isOpen]);

  // Direct Call Live Timer effect
  useEffect(() => {
    let interval = null;
    if (directCallRunning) {
      interval = setInterval(() => {
        setDirectTimer(prev => prev + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [directCallRunning]);

  // Handle call status transitions and talk duration timer trigger
  useEffect(() => {
    if (!activeCall) return;

    const status = activeCall.call_status || '';

    if (isConnectedStatus(status)) {
      if (!isTimerRunning) {
        setIsTimerRunning(true);
        if (!connectedAt) {
          setConnectedAt(Date.now());
        }
      }
    } else if (isTerminalStatus(status)) {
      setIsTimerRunning(false);
      // If backend returned final duration, sync timer to backend duration
      if (activeCall.duration_seconds && activeCall.duration_seconds > 0) {
        setTimerSeconds(activeCall.duration_seconds);
      }
    } else {
      // Initiating or Ringing state: timer MUST remain 0
      setIsTimerRunning(false);
    }
  }, [activeCall]);

  // Talk Duration Timer interval tick
  useEffect(() => {
    let interval = null;
    if (isTimerRunning && connectedAt) {
      interval = setInterval(() => {
        setTimerSeconds(Math.floor((Date.now() - connectedAt) / 1000));
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isTimerRunning, connectedAt]);

  // Background Provider Status Polling (every 2 seconds while active)
  useEffect(() => {
    let pollInterval = null;

    if (isOpen && activeCall && activeCall.provider_call_id && !isTerminalStatus(activeCall.call_status)) {
      pollInterval = setInterval(async () => {
        try {
          const callId = activeCall.id || activeCall.provider_call_id;
          const res = await API.get(`/ivr/calls/${callId}`);
          setActiveCall(res.data);
          
          if (isTerminalStatus(res.data.call_status) && onCallComplete) {
            onCallComplete(res.data);
          }
        } catch (err) {
          console.error('Error polling call status:', err);
        }
      }, 2000);
    }

    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [isOpen, activeCall]);

  if (!isOpen) return null;

  const targetPhone = customerPhone || (lead ? lead.phone : '');
  const leadName = lead ? lead.name : 'Customer Prospect';

  const handleStartCall = async () => {
    setLoading(true);
    setError('');
    setUnconfiguredMsg('');

    try {
      const payload = {
        lead_id: lead ? lead.id : null,
        customer_phone: targetPhone,
        notes: callNotes || `Click-to-Call initiated for ${leadName}`
      };

      const res = await API.post('/ivr/call', payload);
      setActiveCall(res.data);

      if (onCallStarted) {
        onCallStarted(res.data);
      }
    } catch (err) {
      const detail = err.response?.data?.detail || '';
      if (err.response?.status === 400 && detail.toLowerCase().includes('not configured')) {
        setUnconfiguredMsg("IVR is not configured. Please configure IVR from Settings → Integrations.");
      } else {
        setError(detail || 'Failed to initiate Click-to-Call via IVR provider.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleEndCall = async () => {
    if (!activeCall) return;
    setEndingCall(true);
    try {
      const finalDuration = timerSeconds || activeCall.duration_seconds || 0;
      const res = await API.post(`/ivr/calls/${activeCall.id || activeCall.provider_call_id}/update-status`, {
        call_status: 'COMPLETED',
        duration_seconds: finalDuration,
        recording_url: `https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3`,
        notes: callNotes
      });

      setActiveCall(res.data);
      setIsTimerRunning(false);
      if (onCallComplete) {
        onCallComplete(res.data);
      }
    } catch (err) {
      console.error('Failed to end call:', err);
    } finally {
      setEndingCall(false);
    }
  };

  const handleStartDirectCall = () => {
    setDirectCallMode('active');
    setDirectCallRunning(true);
    setDirectTimer(0);
    setError('');
    // Trigger native device / app dialer
    window.location.href = `tel:${targetPhone}`;
  };

  const handleSaveDirectCall = async (statusOverride = null, durationOverride = null) => {
    setSavingManual(true);
    try {
      const dur = durationOverride !== null ? durationOverride : directTimer;
      const st = statusOverride || directStatus || 'COMPLETED';
      const payload = {
        lead_id: lead ? lead.id : null,
        customer_phone: targetPhone,
        call_status: st,
        duration_seconds: dur,
        notes: callNotes || `Direct device call to ${leadName}`
      };
      const res = await API.post('/ivr/calls/manual', payload);
      setSaveSuccess(true);
      setDirectCallRunning(false);
      if (onCallComplete) {
        onCallComplete(res.data);
      }
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err) {
      console.error('Failed to log direct call:', err);
      alert('Failed to log call: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSavingManual(false);
    }
  };

  const formatTimer = (sec) => {
    const m = Math.floor(sec / 60).toString().padStart(2, '0');
    const s = (sec % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const currentStatus = activeCall ? (activeCall.call_status || '').toUpperCase() : '';
  const isRinging = isRingingStatus(currentStatus);
  const isConnected = isConnectedStatus(currentStatus);
  const isTerminal = isTerminalStatus(currentStatus);

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.7)',
      backdropFilter: 'blur(6px)',
      zIndex: 1100,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      {/* Keyframe animations */}
      <style>{`
        @keyframes bellRingShake {
          0% { transform: rotate(0deg); }
          15% { transform: rotate(14deg); }
          30% { transform: rotate(-14deg); }
          45% { transform: rotate(10deg); }
          60% { transform: rotate(-10deg); }
          75% { transform: rotate(4deg); }
          85% { transform: rotate(-4deg); }
          100% { transform: rotate(0deg); }
        }
        @keyframes bluePulseRing {
          0% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4); }
          70% { box-shadow: 0 0 0 16px rgba(37, 99, 235, 0); }
          100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
        }
        @keyframes greenPulseRing {
          0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.5); }
          70% { box-shadow: 0 0 0 18px rgba(16, 185, 129, 0); }
          100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
        .animate-bell {
          animation: bellRingShake 1.2s infinite ease-in-out;
        }
        .pulse-blue {
          animation: bluePulseRing 2s infinite;
        }
        .pulse-green {
          animation: greenPulseRing 1.8s infinite;
        }
      `}</style>

      <div style={{
        width: '100%',
        maxWidth: 'min(94vw, 480px)',
        maxHeight: '92vh',
        overflowY: 'auto',
        borderRadius: '20px',
        boxShadow: '0 25px 50px -12px rgba(0,0,0,0.3)',
        backgroundColor: '#ffffff',
        padding: '24px',
        position: 'relative'
      }}>
        {/* Modal Header */}
        <div style={{
          display: 'flex',
          justify: 'space-between',
          alignItems: 'center',
          paddingBottom: '16px',
          borderBottom: '1px solid #f1f5f9'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              backgroundColor: '#eff6ff',
              color: '#2563eb',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <PhoneCall size={22} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>Click-to-Call IVR</h3>
              <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Bridge employee phone & customer phone</span>
            </div>
          </div>
          <button 
            onClick={onClose} 
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#94a3b8',
              padding: '6px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Unconfigured Warning State */}
        {unconfiguredMsg ? (
          <div style={{ textAlign: 'center', padding: '24px 12px' }}>
            <div style={{
              width: '60px',
              height: '60px',
              borderRadius: '50%',
              backgroundColor: '#fef2f2',
              color: '#ef4444',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px auto'
            }}>
              <AlertCircle size={32} />
            </div>
            <h4 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>IVR Not Configured</h4>
            <p style={{ fontSize: '0.88rem', color: '#64748b', lineHeight: 1.5, marginBottom: '24px' }}>
              IVR Telephony credentials are not configured in your system. Please set up CloudShope, Twilio, or Exotel in Settings → Integrations.
            </p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button onClick={onClose} className="btn btn-outline" style={{ padding: '8px 18px' }}>Close</button>
              <Link to="/settings/integrations" onClick={onClose} className="btn btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '8px 18px' }}>
                <Sliders size={16} />
                <span>Configure IVR</span>
              </Link>
            </div>
          </div>
        ) : activeCall ? (
          /* Active / In-Progress / Ended Call Display */
          <div style={{ textAlign: 'center', paddingTop: '20px' }}>
            
            {/* Call State Avatar Icon & Animations */}
            <div style={{
              width: '76px',
              height: '76px',
              borderRadius: '50%',
              margin: '0 auto 14px auto',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.3s ease',
              backgroundColor: isConnected 
                ? 'rgba(16, 185, 129, 0.12)' 
                : isRinging 
                  ? 'rgba(245, 158, 11, 0.12)' 
                  : isTerminal 
                    ? '#f1f5f9' 
                    : 'rgba(37, 99, 235, 0.12)',
              color: isConnected 
                ? '#10b981' 
                : isRinging 
                  ? '#d97706' 
                  : isTerminal 
                    ? '#64748b' 
                    : '#2563eb'
            }}
            className={isConnected ? 'pulse-green' : (isRinging || (!isConnected && !isTerminal)) ? 'pulse-blue' : ''}
            >
              {isRinging ? (
                <div className="animate-bell" style={{ fontSize: '1.8rem' }}>🔔</div>
              ) : isConnected ? (
                <Volume2 size={38} />
              ) : isTerminal ? (
                <CheckCircle size={38} color={['COMPLETED', 'Completed'].includes(currentStatus) ? '#10b981' : '#ef4444'} />
              ) : (
                <Radio size={36} />
              )}
            </div>

            {/* Contact Name & Phone */}
            <h4 style={{ fontSize: '1.3rem', fontWeight: 700, color: '#0f172a', margin: '0 0 4px 0' }}>{leadName}</h4>
            <p style={{ fontSize: '1rem', color: '#2563eb', fontWeight: 600, margin: '0 0 16px 0' }}>{targetPhone}</p>

            {/* Status & Timer Box */}
            <div style={{
              backgroundColor: isConnected ? '#ecfdf5' : isRinging ? '#fffbeb' : '#f8fafc',
              border: `1px solid ${isConnected ? '#a7f3d0' : isRinging ? '#fde68a' : '#e2e8f0'}`,
              borderRadius: '14px',
              padding: '14px 20px',
              marginBottom: '20px',
              display: 'inline-block',
              minWidth: '220px'
            }}>
              {/* Status Badge */}
              <div style={{ marginBottom: '6px' }}>
                {isRinging ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '0.92rem', color: '#b45309' }}>
                    <span className="animate-bell">🔔</span> Ringing...
                  </span>
                ) : isConnected ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '0.92rem', color: '#047857' }}>
                    <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#10b981', display: 'inline-block' }} className="pulse-green"></span>
                    🟢 Connected
                  </span>
                ) : isTerminal ? (
                  <span style={{ fontWeight: 700, fontSize: '0.9rem', color: ['COMPLETED'].includes(currentStatus) ? '#047857' : '#b91c1c' }}>
                    {['COMPLETED'].includes(currentStatus) ? '✅ Call Completed' : `❌ Call Ended (${currentStatus})`}
                  </span>
                ) : (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '0.9rem', color: '#1d4ed8' }}>
                    <span className="spinner-sm" style={{ width: '14px', height: '14px', borderWidth: '2px' }} />
                    Calling...
                  </span>
                )}
              </div>

              {/* Talk Duration Timer */}
              <div style={{
                fontSize: '1.8rem',
                fontWeight: 800,
                fontFamily: 'monospace',
                color: isConnected ? '#065f46' : '#1e293b',
                letterSpacing: '1px'
              }}>
                ⏱️ {formatTimer(timerSeconds)}
              </div>
              <span style={{ fontSize: '0.75rem', color: '#64748b', display: 'block', marginTop: '2px' }}>
                {isConnected 
                  ? 'Connected Talk Duration' 
                  : isTerminal 
                    ? 'Total Conversation Duration' 
                    : 'Talk timer starts when customer answers'}
              </span>
            </div>

            {/* Bridging Details Card */}
            <div style={{
              backgroundColor: '#f8fafc',
              padding: '14px 16px',
              borderRadius: '12px',
              border: '1px solid #e2e8f0',
              textAlign: 'left',
              marginBottom: '20px',
              fontSize: '0.84rem'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: '#64748b' }}>Employee Registered Phone:</span>
                <span style={{ fontWeight: 600, color: '#0f172a' }}>{activeCall.employee_phone || activeCall.from_number || 'Agent Line'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: '#64748b' }}>Customer Phone:</span>
                <span style={{ fontWeight: 600, color: '#0f172a' }}>{activeCall.customer_phone || activeCall.to_number}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: '#64748b' }}>Provider & Call ID:</span>
                <span style={{ fontWeight: 600, color: '#0f172a', fontFamily: 'monospace' }}>
                  {activeCall.provider || 'IVR'} ({activeCall.provider_call_id || 'ID'})
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#64748b' }}>Webhook Live Status:</span>
                <span style={{
                  padding: '3px 10px',
                  borderRadius: '12px',
                  fontSize: '0.76rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  backgroundColor: isConnected ? '#dcfce7' : isRinging ? '#fef3c7' : isTerminal ? '#e2e8f0' : '#dbeafe',
                  color: isConnected ? '#15803d' : isRinging ? '#b45309' : isTerminal ? '#475569' : '#1d4ed8'
                }}>
                  {activeCall.call_status}
                </span>
              </div>
            </div>

            {/* Live Audio Playback if Completed & recording present */}
            {activeCall.recording_url && isTerminal && (
              <div style={{
                backgroundColor: '#f1f5f9',
                padding: '12px',
                borderRadius: '12px',
                marginBottom: '20px',
                textAlign: 'left'
              }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#334155', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                  <Volume2 size={16} color="#2563eb" />
                  <span>Call Recording Playback</span>
                </span>
                <audio controls src={activeCall.recording_url} style={{ width: '100%', height: '36px', borderRadius: '8px' }} />
              </div>
            )}

            {/* Action Buttons */}
            <div>
              {!isTerminal ? (
                <button
                  onClick={handleEndCall}
                  disabled={endingCall}
                  style={{
                    width: '100%',
                    backgroundColor: '#ef4444',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '12px',
                    fontSize: '0.95rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    boxShadow: '0 4px 12px rgba(239, 68, 68, 0.25)'
                  }}
                >
                  <PhoneOff size={18} />
                  <span>{endingCall ? 'Ending Call...' : 'Hang Up / End Call'}</span>
                </button>
              ) : (
                <button
                  onClick={onClose}
                  className="btn btn-primary"
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: '12px',
                    fontSize: '0.95rem',
                    fontWeight: 700,
                    backgroundColor: '#10b981',
                    color: '#ffffff',
                    border: 'none',
                    cursor: 'pointer'
                  }}
                >
                  Done / Return to CRM
                </button>
              )}
            </div>

          </div>
        ) : directCallMode === 'active' ? (
          /* SCREEN: ACTIVE DIRECT DEVICE CALL (FALLBACK OPTION 1) */
          <div style={{ textAlign: 'center', paddingTop: '10px' }}>
            <div style={{
              width: '74px',
              height: '74px',
              borderRadius: '50%',
              margin: '0 auto 12px auto',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'rgba(16, 185, 129, 0.12)',
              color: '#10b981'
            }} className="pulse-green">
              <Smartphone size={36} />
            </div>

            <div style={{
              display: 'inline-block',
              backgroundColor: '#ecfdf5',
              color: '#047857',
              fontSize: '0.75rem',
              fontWeight: 700,
              padding: '3px 12px',
              borderRadius: '20px',
              marginBottom: '8px'
            }}>
              ⚡ DIRECT CALL MODE (DEVICE DIALER)
            </div>

            <h4 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', margin: '0 0 2px 0' }}>{leadName}</h4>
            <p style={{ fontSize: '0.95rem', color: '#2563eb', fontWeight: 600, margin: '0 0 16px 0' }}>{targetPhone}</p>

            {/* Live Talk Timer */}
            <div style={{
              backgroundColor: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '14px',
              padding: '14px 20px',
              marginBottom: '18px',
              display: 'inline-block',
              minWidth: '220px'
            }}>
              <span style={{ fontSize: '0.75rem', color: '#64748b', display: 'block', marginBottom: '4px' }}>
                Conversation Talk Duration
              </span>
              <div style={{
                fontSize: '1.9rem',
                fontWeight: 800,
                fontFamily: 'monospace',
                color: '#065f46',
                letterSpacing: '1px'
              }}>
                ⏱️ {formatTimer(directTimer)}
              </div>
              <button 
                type="button"
                onClick={() => setDirectCallRunning(!directCallRunning)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '0.75rem',
                  color: directCallRunning ? '#dc2626' : '#16a34a',
                  fontWeight: 600,
                  cursor: 'pointer',
                  marginTop: '4px'
                }}
              >
                {directCallRunning ? '⏸ Pause Timer' : '▶ Resume Timer'}
              </button>
            </div>

            {/* Call Outcome Selector */}
            <div style={{ textAlign: 'left', marginBottom: '16px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 700, color: '#334155', display: 'block', marginBottom: '8px' }}>
                Select Call Outcome:
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                {[
                  { id: 'COMPLETED', label: '🟢 Answered & Connected', color: '#10b981' },
                  { id: 'NO_ANSWER', label: '📵 No Answer / Unanswered', color: '#f59e0b' },
                  { id: 'BUSY', label: '⏳ Line Busy', color: '#6366f1' },
                  { id: 'FAILED', label: '❌ Call Failed / Wrong No.', color: '#ef4444' }
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setDirectStatus(item.id)}
                    style={{
                      padding: '8px 10px',
                      borderRadius: '8px',
                      border: directStatus === item.id ? `2px solid ${item.color}` : '1px solid #e2e8f0',
                      backgroundColor: directStatus === item.id ? '#f8fafc' : '#ffffff',
                      fontSize: '0.78rem',
                      fontWeight: directStatus === item.id ? 700 : 500,
                      cursor: 'pointer',
                      textAlign: 'left',
                      color: directStatus === item.id ? '#0f172a' : '#64748b'
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Notes */}
            <div style={{ textAlign: 'left', marginBottom: '18px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 700, color: '#334155', display: 'block', marginBottom: '6px' }}>
                Call Notes / Summary:
              </label>
              <textarea
                rows={2}
                placeholder="Enter discussion notes, outcome or next action..."
                value={callNotes}
                onChange={(e) => setCallNotes(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '10px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.85rem',
                  outline: 'none'
                }}
              />
            </div>

            {/* Save Action */}
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                onClick={() => {
                  setDirectCallMode('none');
                  setDirectCallRunning(false);
                }}
                className="btn btn-outline"
                style={{ flex: 1, padding: '10px' }}
              >
                Back / Cancel
              </button>
              <button
                type="button"
                disabled={savingManual || saveSuccess}
                onClick={() => handleSaveDirectCall()}
                style={{
                  flex: 2,
                  backgroundColor: '#10b981',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '10px',
                  padding: '10px 16px',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  cursor: savingManual ? 'not-allowed' : 'pointer'
                }}
              >
                {savingManual ? <div className="spinner-sm" /> : <Check size={18} />}
                <span>{saveSuccess ? 'Saved to CRM!' : 'Save Call Log to CRM'}</span>
              </button>
            </div>
          </div>
        ) : directCallMode === 'manual' ? (
          /* SCREEN: LOG CALL MANUALLY (OFFLINE CALL) */
          <div style={{ paddingTop: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <div style={{
                width: '38px',
                height: '38px',
                borderRadius: '10px',
                backgroundColor: '#eff6ff',
                color: '#2563eb',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <FileText size={20} />
              </div>
              <div>
                <h4 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: '#0f172a' }}>Log Call Manually</h4>
                <span style={{ fontSize: '0.78rem', color: '#64748b' }}>Record call duration & outcome directly to CRM</span>
              </div>
            </div>

            <div style={{
              backgroundColor: '#f8fafc',
              padding: '12px 14px',
              borderRadius: '10px',
              border: '1px solid #e2e8f0',
              marginBottom: '16px',
              fontSize: '0.84rem'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ color: '#64748b' }}>Target Lead:</span>
                <span style={{ fontWeight: 700, color: '#0f172a' }}>{leadName}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>Phone:</span>
                <span style={{ fontWeight: 700, color: '#2563eb' }}>{targetPhone}</span>
              </div>
            </div>

            {/* Outcome */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 700, color: '#334155', display: 'block', marginBottom: '6px' }}>
                Call Outcome:
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                {[
                  { id: 'COMPLETED', label: '🟢 Answered / Connected' },
                  { id: 'NO_ANSWER', label: '📵 No Answer' },
                  { id: 'BUSY', label: '⏳ Busy' },
                  { id: 'FAILED', label: '❌ Failed / Invalid' }
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setDirectStatus(item.id)}
                    style={{
                      padding: '8px 10px',
                      borderRadius: '8px',
                      border: directStatus === item.id ? '2px solid #2563eb' : '1px solid #e2e8f0',
                      backgroundColor: directStatus === item.id ? '#eff6ff' : '#ffffff',
                      fontSize: '0.78rem',
                      fontWeight: directStatus === item.id ? 700 : 500,
                      cursor: 'pointer',
                      textAlign: 'left',
                      color: directStatus === item.id ? '#1e40af' : '#64748b'
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Duration presets */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 700, color: '#334155', display: 'block', marginBottom: '6px' }}>
                Call Duration:
              </label>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                {[0, 1, 2, 5, 10, 15].map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setManualMinutes(m)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '8px',
                      border: manualMinutes === m ? '2px solid #10b981' : '1px solid #cbd5e1',
                      backgroundColor: manualMinutes === m ? '#ecfdf5' : '#ffffff',
                      fontSize: '0.78rem',
                      fontWeight: manualMinutes === m ? 700 : 500,
                      color: manualMinutes === m ? '#047857' : '#334155',
                      cursor: 'pointer'
                    }}
                  >
                    {m === 0 ? 'Missed (0s)' : `${m} min`}
                  </button>
                ))}
              </div>
            </div>

            {/* Notes */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 700, color: '#334155', display: 'block', marginBottom: '6px' }}>
                Notes & Agenda:
              </label>
              <textarea
                rows={2}
                placeholder="Details of the conversation, customer inquiries, etc..."
                value={callNotes}
                onChange={(e) => setCallNotes(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '10px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.85rem',
                  outline: 'none'
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setDirectCallMode('none')}
                className="btn btn-outline"
                style={{ flex: 1, padding: '10px' }}
              >
                Back
              </button>
              <button
                type="button"
                disabled={savingManual || saveSuccess}
                onClick={() => handleSaveDirectCall(directStatus, manualMinutes * 60)}
                style={{
                  flex: 2,
                  backgroundColor: '#2563eb',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '10px',
                  padding: '10px 16px',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  cursor: savingManual ? 'not-allowed' : 'pointer'
                }}
              >
                {savingManual ? <div className="spinner-sm" /> : <Check size={18} />}
                <span>{saveSuccess ? 'Saved to CRM!' : 'Save Manual Call Log'}</span>
              </button>
            </div>
          </div>
        ) : (
          /* INITIAL SETUP FORM BEFORE CALLING */
          <div>
            <div style={{
              backgroundColor: '#f8fafc',
              padding: '16px',
              borderRadius: '12px',
              border: '1px solid #e2e8f0',
              marginBottom: '16px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.82rem', color: '#64748b' }}>Target Lead / Customer:</span>
                <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0f172a' }}>{leadName}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.82rem', color: '#64748b' }}>Target Phone Number:</span>
                <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#2563eb' }}>{targetPhone || 'Not Available'}</span>
              </div>
            </div>

            {/* Error Banner */}
            {error && (
              <div style={{
                marginBottom: '16px',
                backgroundColor: '#fef2f2',
                color: '#b91c1c',
                padding: '12px',
                borderRadius: '10px',
                border: '1px solid #fecaca',
                fontSize: '0.84rem'
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', marginBottom: '4px' }}>
                  <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '2px', color: '#ef4444' }} />
                  <span style={{ fontWeight: 600 }}>{error}</span>
                </div>
              </div>
            )}

            {/* FALLBACK OPTIONS PANEL (PROMINENT WHEN ERROR OCCURS) */}
            {error ? (
              <div style={{
                backgroundColor: '#f0fdf4',
                border: '2px dashed #86efac',
                borderRadius: '14px',
                padding: '16px',
                marginBottom: '18px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span style={{ fontSize: '1.1rem' }}>⚡</span>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 800, color: '#166534', margin: 0 }}>
                    Instant Fallback Options
                  </h4>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#15803d', margin: '0 0 14px 0', lineHeight: 1.4 }}>
                  Telecom gateway returned an authorization issue. Don't let this stop you from reaching the customer! Use one of the options below:
                </p>

                {/* Fallback Option 1: Direct Device Dialing */}
                <button
                  type="button"
                  onClick={handleStartDirectCall}
                  style={{
                    width: '100%',
                    backgroundColor: '#16a34a',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '12px 14px',
                    fontSize: '0.88rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '10px',
                    boxShadow: '0 4px 12px rgba(22, 163, 74, 0.25)',
                    marginBottom: '10px'
                  }}
                >
                  <Smartphone size={20} />
                  <span>Call Directly via Phone App (tel:{targetPhone})</span>
                </button>

                {/* Fallback Option 2: Log Offline Call */}
                <button
                  type="button"
                  onClick={() => setDirectCallMode('manual')}
                  style={{
                    width: '100%',
                    backgroundColor: '#ffffff',
                    color: '#334155',
                    border: '1px solid #cbd5e1',
                    borderRadius: '10px',
                    padding: '10px 14px',
                    fontSize: '0.84rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px'
                  }}
                >
                  <FileText size={16} color="#64748b" />
                  <span>Log Call Outcome & Duration Manually</span>
                </button>

                {/* Smartflo Portal Authentication Guidance */}
                {error.toLowerCase().includes('smartflo') && (
                  <div style={{
                    marginTop: '14px',
                    padding: '10px 12px',
                    backgroundColor: '#eff6ff',
                    borderRadius: '8px',
                    border: '1px solid #bfdbfe',
                    fontSize: '0.76rem',
                    color: '#1e40af',
                    lineHeight: 1.4
                  }}>
                    <strong>💡 Smartflo 401 Setup Tip:</strong> In your Tata Smartflo portal, navigate to <strong>Administration → API Tokens</strong>, generate a Bearer Token, and paste it into{' '}
                    <Link to="/settings/integrations" onClick={onClose} style={{ color: '#2563eb', fontWeight: 700, textDecoration: 'underline' }}>
                      Settings → Integrations
                    </Link>.
                  </div>
                )}
              </div>
            ) : null}

            <div className="form-group" style={{ marginBottom: '18px' }}>
              <label style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <FileText size={14} />
                <span>Initial Call Agenda / Notes (Optional)</span>
              </label>
              <textarea 
                rows={2}
                placeholder="e.g. Discuss product demo and schedule follow-up..."
                value={callNotes}
                onChange={(e) => setCallNotes(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '10px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.88rem',
                  outline: 'none'
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              {!error && (
                <button
                  type="button"
                  onClick={handleStartDirectCall}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#16a34a',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <Smartphone size={16} />
                  <span>Direct Device Call</span>
                </button>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginLeft: 'auto' }}>
                <button 
                  type="button" 
                  onClick={onClose} 
                  className="btn btn-outline" 
                  disabled={loading}
                  style={{ padding: '10px 16px', borderRadius: '10px', fontSize: '0.88rem' }}
                >
                  Cancel
                </button>
                <button 
                  onClick={handleStartCall} 
                  disabled={loading || !targetPhone} 
                  style={{
                    backgroundColor: '#2563eb',
                    color: '#ffffff',
                    padding: '10px 20px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                    borderRadius: '10px',
                    border: 'none',
                    fontWeight: 700,
                    fontSize: '0.88rem',
                    cursor: loading || !targetPhone ? 'not-allowed' : 'pointer',
                    opacity: loading || !targetPhone ? 0.7 : 1
                  }}
                >
                  {loading ? <div className="spinner-sm" /> : <PhoneCall size={17} />}
                  <span>{loading ? 'Initiating...' : (error ? '🔄 Retry IVR Call' : '📞 Call Now')}</span>
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default IVRCallModal;
