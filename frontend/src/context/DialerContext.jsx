import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import API from '../services/api';

const DialerContext = createContext(null);

// Audio DTMF sound frequencies for authentic keypad feedback
const DTMF_FREQS = {
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

export const DialerProvider = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [phoneNumber, setPhoneNumber] = useState('');
  const [selectedCountryCode, setSelectedCountryCode] = useState('+91');
  const [activeContact, setActiveContact] = useState(null); // { name, phone, lead_id, company, status }

  // Call Lifecycle States
  // 'IDLE' | 'DIALING' | 'RINGING' | 'CONNECTED' | 'ENDING' | 'COMPLETED' | 'FAILED'
  const [callState, setCallState] = useState('IDLE');
  const [activeCall, setActiveCall] = useState(null); // CallLog object returned by API
  const [callNotes, setCallNotes] = useState('');
  const [callError, setCallError] = useState('');
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [isMuted, setIsMuted] = useState(false);

  // Recent calls & contacts cache for quick access
  const [recentCalls, setRecentCalls] = useState([]);
  const [loadingRecent, setLoadingRecent] = useState(false);
  const [matchedLead, setMatchedLead] = useState(null);

  const audioCtxRef = useRef(null);
  const pollIntervalRef = useRef(null);
  const timerIntervalRef = useRef(null);
  const connectedAtRef = useRef(null);

  // Play standard DTMF tone on button press
  const playDtmfTone = (digit) => {
    try {
      if (!audioCtxRef.current) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          audioCtxRef.current = new AudioCtx();
        }
      }
      const ctx = audioCtxRef.current;
      if (!ctx) return;
      if (ctx.state === 'suspended') {
        ctx.resume();
      }

      const freqs = DTMF_FREQS[digit];
      if (!freqs) return;

      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain = ctx.createGain();

      gain.gain.value = 0.04; // Gentle volume
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.15);

      osc1.frequency.value = freqs[0];
      osc2.frequency.value = freqs[1];

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(ctx.destination);

      osc1.start();
      osc2.start();
      osc1.stop(ctx.currentTime + 0.15);
      osc2.stop(ctx.currentTime + 0.15);
    } catch (e) {
      // Audio autoplay policy fallback
    }
  };

  // Fetch recent call logs for dialer history tab
  const fetchRecentCalls = async () => {
    try {
      setLoadingRecent(true);
      const res = await API.get('/ivr/calls?limit=15');
      setRecentCalls(res.data?.items || []);
    } catch (err) {
      console.error('Failed to load recent dialer calls:', err);
    } finally {
      setLoadingRecent(false);
    }
  };

  // Match phone number with lead as user types
  useEffect(() => {
    const clean = phoneNumber.replace(/[^0-9]/g, '');
    if (clean.length >= 5) {
      const searchNumber = clean.length > 10 ? clean.slice(-10) : clean;
      const timer = setTimeout(async () => {
        try {
          const res = await API.get(`/leads/?search=${searchNumber}&limit=1`);
          const lead = res.data?.items?.[0];
          if (lead) {
            setMatchedLead(lead);
          } else {
            setMatchedLead(null);
          }
        } catch (e) {
          setMatchedLead(null);
        }
      }, 350);
      return () => clearTimeout(timer);
    } else {
      setMatchedLead(null);
    }
  }, [phoneNumber]);

  // Handle active call duration timer
  useEffect(() => {
    if (callState === 'CONNECTED') {
      connectedAtRef.current = Date.now();
      timerIntervalRef.current = setInterval(() => {
        if (connectedAtRef.current) {
          setTimerSeconds(Math.floor((Date.now() - connectedAtRef.current) / 1000));
        }
      }, 1000);
    } else if (['COMPLETED', 'FAILED', 'IDLE'].includes(callState)) {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    }

    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    };
  }, [callState]);

  // Background status polling for active CRM IVR call
  useEffect(() => {
    if (activeCall && ['DIALING', 'RINGING', 'CONNECTED'].includes(callState)) {
      pollIntervalRef.current = setInterval(async () => {
        try {
          const callId = activeCall.id || activeCall.provider_call_id;
          const res = await API.get(`/ivr/calls/${callId}`);
          const callData = res.data;
          setActiveCall(callData);

          const st = (callData.call_status || '').toUpperCase();
          if (['RINGING'].includes(st)) {
            setCallState('RINGING');
          } else if (['CONNECTED', 'ANSWERED', 'IN_PROGRESS', 'IN-PROGRESS'].includes(st)) {
            setCallState('CONNECTED');
          } else if (['COMPLETED', 'HANGUP'].includes(st)) {
            setCallState('COMPLETED');
            if (callData.duration_seconds) {
              setTimerSeconds(callData.duration_seconds);
            }
          } else if (['FAILED', 'MISSED', 'BUSY', 'NO_ANSWER'].includes(st)) {
            setCallState('FAILED');
            setCallError(`Call ${st.toLowerCase()}`);
          }
        } catch (e) {
          console.error('Error polling active call in dialer:', e);
        }
      }, 2500);
    }

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [activeCall, callState]);

  // Public methods
  const openDialer = (numberToDial = '', contactData = null) => {
    let num = numberToDial ? String(numberToDial).trim() : '';
    let code = selectedCountryCode;

    if (num.startsWith('+91')) {
      code = '+91';
      num = num.replace(/^\+91/, '').trim();
    } else if (num.startsWith('+1')) {
      code = '+1';
      num = num.replace(/^\+1/, '').trim();
    } else if (num.startsWith('+44')) {
      code = '+44';
      num = num.replace(/^\+44/, '').trim();
    } else if (num.startsWith('+')) {
      // Keep full
    }

    if (num) {
      setPhoneNumber(num);
    }
    setSelectedCountryCode(code);

    if (contactData) {
      setActiveContact(contactData);
      setMatchedLead(contactData);
    } else {
      setActiveContact(null);
    }

    setIsOpen(true);
    setIsMinimized(false);
    fetchRecentCalls();
  };

  const closeDialer = () => {
    // If call is ongoing, minimize instead of closing completely
    if (['DIALING', 'RINGING', 'CONNECTED'].includes(callState)) {
      setIsMinimized(true);
    } else {
      setIsOpen(false);
      setIsMinimized(false);
      resetDialerState();
    }
  };

  const toggleMinimize = () => {
    setIsMinimized(prev => !prev);
  };

  const resetDialerState = () => {
    setCallState('IDLE');
    setActiveCall(null);
    setCallNotes('');
    setCallError('');
    setTimerSeconds(0);
    setIsMuted(false);
  };

  const appendDigit = (digit) => {
    playDtmfTone(digit);
    setPhoneNumber(prev => prev + digit);
  };

  const deleteDigit = () => {
    setPhoneNumber(prev => prev.slice(0, -1));
  };

  const clearDigits = () => {
    setPhoneNumber('');
    setActiveContact(null);
    setMatchedLead(null);
  };

  // Get full formatted E.164 phone number
  const getFullPhoneNumber = () => {
    const raw = phoneNumber.trim().replace(/[\s-()]/g, '');
    if (!raw) return '';
    if (raw.startsWith('+')) return raw;
    return `${selectedCountryCode}${raw}`;
  };

  // Initiate CRM IVR Call via Backend API
  const startIvrCall = async (customNum = null, contactObj = null) => {
    const targetNumber = customNum || getFullPhoneNumber();
    if (!targetNumber || targetNumber.replace(/[^0-9]/g, '').length < 6) {
      setCallError('Please enter a valid phone number with at least 6 digits.');
      return;
    }

    const leadInfo = contactObj || activeContact || matchedLead;
    setCallError('');
    setCallState('DIALING');
    setTimerSeconds(0);
    setIsMinimized(false);

    try {
      const payload = {
        lead_id: leadInfo ? leadInfo.id : null,
        customer_phone: targetNumber,
        notes: callNotes || `Outbound CRM call to ${leadInfo?.name || targetNumber}`
      };

      const res = await API.post('/ivr/call', payload);
      setActiveCall(res.data);
      
      const st = (res.data.call_status || '').toUpperCase();
      if (['RINGING'].includes(st)) {
        setCallState('RINGING');
      } else if (['CONNECTED', 'ANSWERED'].includes(st)) {
        setCallState('CONNECTED');
      } else {
        setCallState('DIALING');
      }

      fetchRecentCalls();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Call failed to initiate.';
      setCallError(detail);
      setCallState('FAILED');
    }
  };

  // End active CRM IVR call and submit notes
  const endIvrCall = async () => {
    if (!activeCall) {
      resetDialerState();
      return;
    }

    setCallState('ENDING');
    try {
      const callId = activeCall.id || activeCall.provider_call_id;
      const res = await API.post(`/ivr/calls/${callId}/update-status`, {
        call_status: 'COMPLETED',
        duration_seconds: timerSeconds || activeCall.duration_seconds || 0,
        notes: callNotes || `Completed outbound call.`
      });

      setActiveCall(res.data);
      setCallState('COMPLETED');
      fetchRecentCalls();
    } catch (err) {
      console.error('Failed to end call:', err);
      setCallState('COMPLETED');
    }
  };

  // Device Native Dial (`tel:`)
  const startDeviceDial = (customNum = null) => {
    const targetNumber = customNum || getFullPhoneNumber();
    if (!targetNumber) {
      setCallError('Please enter a phone number to dial.');
      return;
    }
    // Launch device/phone dialer via standard tel URI
    window.location.href = `tel:${targetNumber}`;
  };

  // Global window listener for easy click-to-dial anywhere in CRM
  useEffect(() => {
    const handleCrmDialEvent = (event) => {
      const { phone, contact } = event.detail || {};
      if (phone) {
        openDialer(phone, contact);
      } else {
        openDialer();
      }
    };

    window.addEventListener('crm-dial-lead', handleCrmDialEvent);
    window.crmDial = (phone, contact) => {
      if (window.dooctiDial && phone) {
        window.dooctiDial(phone, contact);
        return;
      }
      openDialer(phone, contact);
    };

    return () => {
      window.removeEventListener('crm-dial-lead', handleCrmDialEvent);
      delete window.crmDial;
    };
  }, [selectedCountryCode]);

  return (
    <DialerContext.Provider value={{
      isOpen,
      isMinimized,
      phoneNumber,
      selectedCountryCode,
      activeContact,
      matchedLead,
      callState,
      activeCall,
      callNotes,
      callError,
      timerSeconds,
      isMuted,
      recentCalls,
      loadingRecent,
      openDialer,
      closeDialer,
      toggleMinimize,
      setPhoneNumber,
      setSelectedCountryCode,
      appendDigit,
      deleteDigit,
      clearDigits,
      startIvrCall,
      endIvrCall,
      startDeviceDial,
      setCallNotes,
      setIsMuted,
      resetDialerState,
      fetchRecentCalls,
      getFullPhoneNumber,
      playDtmfTone
    }}>
      {children}
    </DialerContext.Provider>
  );
};

export const useDialer = () => {
  const context = useContext(DialerContext);
  if (!context) {
    throw new Error('useDialer must be used within a DialerProvider');
  }
  return context;
};

export default DialerContext;
