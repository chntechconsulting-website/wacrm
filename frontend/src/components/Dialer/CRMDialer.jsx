import React, { useState, useEffect } from 'react';
import { 
  Phone,
  PhoneCall, 
  PhoneOff, 
  PhoneIncoming, 
  PhoneOutgoing, 
  X, 
  Minus, 
  Maximize2, 
  Clock, 
  Users, 
  Grid, 
  Delete, 
  Smartphone, 
  Volume2, 
  VolumeX, 
  FileText, 
  Search, 
  Check, 
  AlertCircle,
  ExternalLink,
  ChevronDown
} from 'lucide-react';
import { useDialer } from '../../context/DialerContext';
import API from '../../services/api';
import './CRMDialer.css';

const COUNTRY_CODES = [
  { code: '+91', country: 'IN', label: '🇮🇳 India (+91)' },
  { code: '+1', country: 'US', label: '🇺🇸 USA / Canada (+1)' },
  { code: '+44', country: 'UK', label: '🇬🇧 UK (+44)' },
  { code: '+971', country: 'UAE', label: '🇦🇪 UAE (+971)' },
  { code: '+65', country: 'SG', label: '🇸🇬 Singapore (+65)' },
  { code: '+61', country: 'AU', label: '🇦🇺 Australia (+61)' },
  { code: '+966', country: 'SA', label: '🇸🇦 Saudi Arabia (+966)' },
];

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

const CRMDialer = () => {
  const {
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
    getFullPhoneNumber,
    playDtmfTone
  } = useDialer();

  const [activeTab, setActiveTab] = useState('keypad'); // 'keypad' | 'recent' | 'contacts'
  const [contactsSearch, setContactsSearch] = useState('');
  const [searchedLeads, setSearchedLeads] = useState([]);
  const [searchingLeads, setSearchingLeads] = useState(false);
  const [showInCallKeypad, setShowInCallKeypad] = useState(false);
  const [notesSavedToast, setNotesSavedToast] = useState(false);
  const [loggingManual, setLoggingManual] = useState(false);

  const handleLogManualFallback = async () => {
    try {
      setLoggingManual(true);
      const targetNumber = getFullPhoneNumber();
      const leadInfo = activeContact || matchedLead;
      await API.post('/ivr/calls/manual', {
        lead_id: leadInfo?.id || null,
        customer_phone: targetNumber,
        call_status: 'COMPLETED',
        duration_seconds: 60,
        notes: callNotes || 'Direct phone call placed via device app.'
      });
      useDialer().fetchRecentCalls?.();
      resetDialerState();
    } catch (e) {
      console.error('Failed to log manual call:', e);
    } finally {
      setLoggingManual(false);
    }
  };

  // Search leads when typing in Contacts tab
  useEffect(() => {
    if (activeTab === 'contacts') {
      const q = contactsSearch.trim();
      const delay = setTimeout(async () => {
        try {
          setSearchingLeads(true);
          const res = await API.get(`/leads/?search=${encodeURIComponent(q)}&limit=10`);
          setSearchedLeads(res.data?.items || []);
        } catch (e) {
          setSearchedLeads([]);
        } finally {
          setSearchingLeads(false);
        }
      }, 300);
      return () => clearTimeout(delay);
    }
  }, [contactsSearch, activeTab]);

  // Format active call seconds into MM:SS
  const formatTimer = (sec) => {
    const mins = Math.floor(sec / 60).toString().padStart(2, '0');
    const secs = (sec % 60).toString().padStart(2, '0');
    return `${mins}:${secs}`;
  };

  const isCallActive = ['DIALING', 'RINGING', 'CONNECTED', 'ENDING'].includes(callState);

  // Keyboard number entry handler (for container / pad focus)
  const handleKeyDown = (e) => {
    // If typing inside an input or textarea, let the input handle value changes natively.
    // Do NOT append digits here to prevent duplicate entries (double numbers).
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      if (e.key === 'Enter' && !isCallActive && phoneNumber) {
        startIvrCall();
      }
      return;
    }

    if (['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '#', '+'].includes(e.key)) {
      appendDigit(e.key);
    } else if (e.key === 'Backspace') {
      deleteDigit();
    } else if (e.key === 'Enter' && !isCallActive && phoneNumber) {
      startIvrCall();
    }
  };

  // If dialer is not open at all, render only the floating dialer launcher button
  if (!isOpen) {
    return (
      <div className="crm-dialer-launcher" onClick={() => openDialer()} title="Open Phone Dialer">
        <div className="dialer-launcher-btn">
          <PhoneCall size={22} className="launcher-icon" />
          <span className="launcher-label">Dialer</span>
        </div>
      </div>
    );
  }

  // If dialer is open but minimized: show floating mini widget with active timer
  if (isMinimized) {
    return (
      <div 
        className={`crm-dialer-minimized ${isCallActive ? 'in-call' : ''}`}
        onClick={toggleMinimize}
        title="Restore Phone Dialer"
      >
        <div className="minimized-content">
          <div className={`minimized-icon-box ${isCallActive ? 'pulsing' : ''}`}>
            {isCallActive ? <PhoneCall size={18} /> : <PhoneCall size={18} />}
          </div>
          <div className="minimized-info">
            <span className="minimized-title">
              {isCallActive ? (activeContact?.name || phoneNumber || 'Active Call') : 'CRM Dialer'}
            </span>
            <span className="minimized-status">
              {isCallActive ? (
                callState === 'CONNECTED' ? `🟢 ${formatTimer(timerSeconds)}` : `🟡 ${callState}...`
              ) : (
                'Click to open'
              )}
            </span>
          </div>
          <button 
            type="button" 
            className="minimized-restore-btn"
            onClick={(e) => {
              e.stopPropagation();
              toggleMinimize();
            }}
          >
            <Maximize2 size={15} />
          </button>
        </div>
      </div>
    );
  }

  // Main Expanded Dialer Panel
  return (
    <div className="crm-dialer-container" onKeyDown={handleKeyDown} tabIndex="0">
      {/* Dialer Header */}
      <div className="dialer-header">
        <div className="dialer-header-brand">
          <div className={`dialer-header-icon ${isCallActive ? 'live' : ''}`}>
            <PhoneCall size={16} />
          </div>
          <div>
            <h4 className="dialer-header-title">WA! Phone Dialer</h4>
            <span className="dialer-header-sub">
              {isCallActive ? (
                <span className="live-status-pill">{callState} • {formatTimer(timerSeconds)}</span>
              ) : (
                'Direct CRM Dialing'
              )}
            </span>
          </div>
        </div>

        <div className="dialer-header-actions">
          <button 
            type="button" 
            className="dialer-btn-icon" 
            onClick={toggleMinimize} 
            title="Minimize Dialer"
          >
            <Minus size={16} />
          </button>
          <button 
            type="button" 
            className="dialer-btn-icon close" 
            onClick={closeDialer} 
            title="Close Dialer"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* SCREEN 1: ACTIVE CALL IN PROGRESS */}
      {isCallActive && (
        <div className="dialer-call-active-screen">
          <div className="call-avatar-wrapper">
            <div className={`call-avatar-circle ${callState === 'CONNECTED' ? 'pulse-green' : 'pulse-amber'}`}>
              <PhoneCall size={34} />
            </div>
            <div className="call-target-name">
              {activeContact?.name || matchedLead?.name || 'Customer'}
            </div>
            <div className="call-target-number">
              {phoneNumber ? `${selectedCountryCode} ${phoneNumber}` : (activeCall?.customer_phone || 'Calling...')}
            </div>
            {matchedLead && (
              <div className="call-lead-pill">
                <span>{matchedLead.company || 'Lead'}</span>
                <span className="bullet">•</span>
                <span className="status">{matchedLead.status}</span>
              </div>
            )}
          </div>

          <div className="call-status-counter">
            {callState === 'DIALING' && <span className="status-text dialing">Connecting with provider...</span>}
            {callState === 'RINGING' && <span className="status-text ringing">🔔 Ringing customer...</span>}
            {callState === 'CONNECTED' && (
              <div className="timer-badge">
                <span className="live-dot"></span>
                <span className="timer-digits">{formatTimer(timerSeconds)}</span>
              </div>
            )}
            {callState === 'ENDING' && <span className="status-text ending">Ending call...</span>}
          </div>

          {/* In-Call Keypad Toggle */}
          {showInCallKeypad ? (
            <div className="incall-keypad-panel">
              <div className="incall-keypad-grid">
                {KEYPAD_BUTTONS.map((btn) => (
                  <button
                    key={btn.digit}
                    type="button"
                    className="incall-key-btn"
                    onClick={() => appendDigit(btn.digit)}
                  >
                    {btn.digit}
                  </button>
                ))}
              </div>
              <button 
                type="button" 
                className="btn-hide-keypad" 
                onClick={() => setShowInCallKeypad(false)}
              >
                Hide Keypad
              </button>
            </div>
          ) : (
            /* In-Call Action Bar */
            <div className="call-controls-bar">
              <button 
                type="button" 
                className={`control-circle-btn ${isMuted ? 'active-mute' : ''}`}
                onClick={() => setIsMuted(!isMuted)}
                title={isMuted ? 'Unmute' : 'Mute'}
              >
                {isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
                <span>{isMuted ? 'Muted' : 'Mute'}</span>
              </button>

              <button 
                type="button" 
                className="control-circle-btn"
                onClick={() => setShowInCallKeypad(true)}
                title="Open Dialpad for IVR DTMF"
              >
                <Grid size={18} />
                <span>Keypad</span>
              </button>

              <button 
                type="button" 
                className="control-circle-btn"
                onClick={() => {
                  const textarea = document.getElementById('dialer-call-notes');
                  if (textarea) textarea.focus();
                }}
                title="Call Notes"
              >
                <FileText size={18} />
                <span>Notes</span>
              </button>
            </div>
          )}

          {/* Real-time Call Notes */}
          <div className="call-notes-box">
            <label htmlFor="dialer-call-notes">Call Notes & Outcome:</label>
            <textarea
              id="dialer-call-notes"
              value={callNotes}
              onChange={(e) => setCallNotes(e.target.value)}
              placeholder="Record notes, customer requirement, or follow-up reason..."
              rows={2}
            />
          </div>

          {/* End Call Button */}
          <div className="call-end-action">
            <button 
              type="button" 
              className="btn-end-call" 
              onClick={endIvrCall}
              title="End Call"
            >
              <PhoneOff size={22} />
              <span>End Call</span>
            </button>
          </div>
        </div>
      )}

      {/* SCREEN 2: CALL COMPLETED SUMMARY */}
      {callState === 'COMPLETED' && (
        <div className="dialer-completed-screen">
          <div className="completed-check-icon">
            <Check size={32} />
          </div>
          <h3>Call Completed</h3>
          <p className="completed-duration">
            Talk Time: <strong>{formatTimer(timerSeconds)}</strong>
          </p>

          <div className="completed-notes-preview">
            <label>Saved Call Notes:</label>
            <p>{callNotes || 'No notes added for this call.'}</p>
          </div>

          <div className="completed-actions">
            <button 
              type="button" 
              className="btn-completed-action secondary" 
              onClick={() => startIvrCall()}
            >
              <PhoneCall size={15} /> Redial
            </button>
            <button 
              type="button" 
              className="btn-completed-action primary" 
              onClick={resetDialerState}
            >
              New Call
            </button>
          </div>
        </div>
      )}

      {/* SCREEN 3: CALL FAILED / ERROR */}
      {callState === 'FAILED' && (
        <div className="dialer-failed-screen">
          <div className="failed-icon">
            <AlertCircle size={32} />
          </div>
          <h3>Call Failed</h3>
          <p className="failed-reason">{callError || 'Unable to complete call via IVR.'}</p>

          <div className="failed-fallback-box">
            <span style={{ fontWeight: 700, color: '#166534', marginBottom: '8px', display: 'block' }}>⚡ Fallback Options:</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {window.dooctiDial && (
                <button 
                  type="button" 
                  className="btn-device-fallback" 
                  onClick={() => {
                    const targetNum = getFullPhoneNumber();
                    const leadInfo = activeContact || matchedLead;
                    window.dooctiDial(targetNum, leadInfo);
                    closeDialer();
                  }}
                  style={{ 
                    width: '100%', 
                    justifyContent: 'center', 
                    backgroundColor: '#0f172a', 
                    color: '#ffffff', 
                    border: 'none', 
                    fontWeight: 700,
                    padding: '8px 12px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  <Phone size={15} color="#22c55e" /> Dial via Doocti Softphone
                </button>
              )}
              <button 
                type="button" 
                className="btn-device-fallback" 
                onClick={() => startDeviceDial()}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                <Smartphone size={15} /> Dial via Mobile / Phone App
              </button>
              <button 
                type="button" 
                className="btn-device-fallback" 
                onClick={handleLogManualFallback}
                disabled={loggingManual}
                style={{ width: '100%', justifyContent: 'center', backgroundColor: '#f8fafc', color: '#334155', border: '1px solid #cbd5e1' }}
              >
                <FileText size={15} color="#64748b" /> {loggingManual ? 'Logging...' : 'Log Offline Call to CRM'}
              </button>
            </div>
          </div>

          <div className="completed-actions">
            <button 
              type="button" 
              className="btn-completed-action secondary" 
              onClick={() => startIvrCall()}
            >
              Retry Call
            </button>
            <button 
              type="button" 
              className="btn-completed-action primary" 
              onClick={resetDialerState}
            >
              Back to Keypad
            </button>
          </div>
        </div>
      )}

      {/* SCREEN 4: IDLE DIALPAD INTERFACE */}
      {callState === 'IDLE' && (
        <>
          {/* Navigation Tabs */}
          <div className="dialer-tabs">
            <button 
              type="button" 
              className={`dialer-tab-btn ${activeTab === 'keypad' ? 'active' : ''}`}
              onClick={() => setActiveTab('keypad')}
            >
              <Grid size={15} /> Keypad
            </button>
            <button 
              type="button" 
              className={`dialer-tab-btn ${activeTab === 'recent' ? 'active' : ''}`}
              onClick={() => {
                setActiveTab('recent');
                useDialer().fetchRecentCalls?.();
              }}
            >
              <Clock size={15} /> Recents
            </button>
            <button 
              type="button" 
              className={`dialer-tab-btn ${activeTab === 'contacts' ? 'active' : ''}`}
              onClick={() => setActiveTab('contacts')}
            >
              <Users size={15} /> Contacts
            </button>
          </div>

          {/* TAB 1: KEYPAD */}
          {activeTab === 'keypad' && (
            <div className="dialer-keypad-view">
              {/* Phone Input Screen */}
              <div className="dialer-screen">
                <div className="country-code-wrapper">
                  <select 
                    value={selectedCountryCode}
                    onChange={(e) => setSelectedCountryCode(e.target.value)}
                    className="country-select"
                  >
                    {COUNTRY_CODES.map((item) => (
                      <option key={item.code} value={item.code}>
                        {item.country} ({item.code})
                      </option>
                    ))}
                  </select>
                </div>

                <input 
                  type="text"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value.replace(/[^0-9*#+]/g, ''))}
                  onKeyDown={(e) => {
                    if (['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '#', '+'].includes(e.key)) {
                      playDtmfTone?.(e.key);
                    }
                  }}
                  placeholder="Enter phone number..."
                  className="dialer-number-input"
                  autoFocus
                />

                {phoneNumber && (
                  <button 
                    type="button" 
                    className="btn-backspace" 
                    onClick={deleteDigit}
                    onDoubleClick={clearDigits}
                    title="Delete (Double-click to clear)"
                  >
                    <Delete size={18} />
                  </button>
                )}
              </div>

              {/* Matched Contact Card Banner */}
              {matchedLead ? (
                <div className="dialer-matched-contact">
                  <div className="matched-avatar">
                    {(matchedLead.name || 'L').charAt(0).toUpperCase()}
                  </div>
                  <div className="matched-details">
                    <span className="matched-name">{matchedLead.name}</span>
                    <span className="matched-meta">
                      {matchedLead.company ? `${matchedLead.company} • ` : ''}
                      {matchedLead.status || 'Lead'}
                    </span>
                  </div>
                  <span className="matched-badge">CRM Lead</span>
                </div>
              ) : activeContact ? (
                <div className="dialer-matched-contact">
                  <div className="matched-avatar">
                    {(activeContact.name || 'C').charAt(0).toUpperCase()}
                  </div>
                  <div className="matched-details">
                    <span className="matched-name">{activeContact.name}</span>
                    <span className="matched-meta">{activeContact.company || 'Contact'}</span>
                  </div>
                </div>
              ) : null}

              {/* Error Alert Banner */}
              {callError && (
                <div className="dialer-error-banner">
                  <AlertCircle size={14} />
                  <span>{callError}</span>
                </div>
              )}

              {/* 12-Button Keypad Grid */}
              <div className="dialer-keypad-grid">
                {KEYPAD_BUTTONS.map((item) => (
                  <button
                    key={item.digit}
                    type="button"
                    className="keypad-digit-btn"
                    onClick={() => appendDigit(item.digit)}
                  >
                    <span className="key-number">{item.digit}</span>
                    {item.letters && <span className="key-letters">{item.letters}</span>}
                  </button>
                ))}
              </div>

              {/* Action Buttons: Call via CRM & Mobile Dial */}
              <div className="dialer-action-buttons">
                <button 
                  type="button" 
                  className="btn-call-crm"
                  onClick={() => startIvrCall()}
                  disabled={!phoneNumber}
                  title="Call via CRM Cloud Telephony"
                >
                  <PhoneCall size={18} />
                  <span>Call CRM</span>
                </button>

                <button 
                  type="button" 
                  className="btn-call-doocti"
                  onClick={() => {
                    if (window.dooctiDial) {
                      window.dooctiDial(getFullPhoneNumber(), activeContact || matchedLead);
                      closeDialer();
                    }
                  }}
                  disabled={!phoneNumber}
                  style={{
                    backgroundColor: '#0f172a',
                    color: '#ffffff',
                    border: 'none',
                    padding: '0 12px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontWeight: '600',
                    fontSize: '0.85rem'
                  }}
                  title="Dial via Doocti In-App Softphone"
                >
                  <Phone size={15} color="#22c55e" />
                  <span>Doocti</span>
                </button>

                <button 
                  type="button" 
                  className="btn-call-device"
                  onClick={() => startDeviceDial()}
                  disabled={!phoneNumber}
                  title="Dial via Mobile / Device App"
                >
                  <Smartphone size={18} />
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: RECENT CALLS */}
          {activeTab === 'recent' && (
            <div className="dialer-recent-view">
              {loadingRecent ? (
                <div className="dialer-loading-state">
                  <span>Loading recent calls...</span>
                </div>
              ) : recentCalls.length === 0 ? (
                <div className="dialer-empty-state">
                  <Clock size={32} style={{ color: '#94a3b8', marginBottom: '8px' }} />
                  <p>No recent calls found</p>
                  <span>Calls made through CRM will appear here</span>
                </div>
              ) : (
                <div className="recent-calls-list">
                  {recentCalls.map((call) => {
                    const isInbound = (call.call_direction || '').toUpperCase() === 'INBOUND';
                    const targetPhone = call.customer_phone || call.to_number || call.from_number;
                    const contactName = call.lead_name || 'Direct Contact';

                    return (
                      <div key={call.id} className="recent-call-item">
                        <div className={`recent-call-icon ${isInbound ? 'inbound' : 'outbound'}`}>
                          {isInbound ? <PhoneIncoming size={15} /> : <PhoneOutgoing size={15} />}
                        </div>
                        <div className="recent-call-details">
                          <span className="recent-contact-name">{contactName}</span>
                          <span className="recent-phone-number">{targetPhone}</span>
                          <span className="recent-meta-info">
                            {call.call_status} • {call.duration_seconds ? `${call.duration_seconds}s` : '0s'}
                          </span>
                        </div>
                        <button 
                          type="button" 
                          className="btn-quick-call"
                          onClick={() => {
                            setPhoneNumber(targetPhone.replace(/^\+91/, '').replace(/[^0-9]/g, ''));
                            setActiveContact({ name: contactName, phone: targetPhone, id: call.lead_id });
                            setActiveTab('keypad');
                            startIvrCall(targetPhone, { id: call.lead_id, name: contactName });
                          }}
                          title={`Dial ${contactName}`}
                        >
                          <PhoneCall size={14} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: CONTACTS / LEADS SEARCH */}
          {activeTab === 'contacts' && (
            <div className="dialer-contacts-view">
              <div className="contacts-search-box">
                <Search size={16} className="search-icon" />
                <input 
                  type="text" 
                  value={contactsSearch} 
                  onChange={(e) => setContactsSearch(e.target.value)}
                  placeholder="Search leads by name or phone..." 
                  className="contacts-search-input"
                  autoFocus
                />
                {contactsSearch && (
                  <button type="button" onClick={() => setContactsSearch('')} className="search-clear-btn">
                    <X size={14} />
                  </button>
                )}
              </div>

              {searchingLeads ? (
                <div className="dialer-loading-state">
                  <span>Searching CRM leads...</span>
                </div>
              ) : searchedLeads.length === 0 ? (
                <div className="dialer-empty-state">
                  <Users size={32} style={{ color: '#94a3b8', marginBottom: '8px' }} />
                  <p>No leads found</p>
                  <span>Type a name or phone number above</span>
                </div>
              ) : (
                <div className="contacts-list">
                  {searchedLeads.map((lead) => (
                    <div key={lead.id} className="contact-list-item">
                      <div className="contact-avatar">
                        {(lead.name || 'L').charAt(0).toUpperCase()}
                      </div>
                      <div className="contact-info">
                        <span className="contact-name">{lead.name}</span>
                        <span className="contact-phone">{lead.phone || 'No phone'}</span>
                        <span className="contact-company">{lead.company || lead.source}</span>
                      </div>
                      {lead.phone && (
                        <div className="contact-actions">
                          <button 
                            type="button" 
                            className="btn-contact-dial"
                            onClick={() => {
                              openDialer(lead.phone, lead);
                              startIvrCall(lead.phone, lead);
                            }}
                            title={`Call ${lead.name} via CRM`}
                          >
                            <PhoneCall size={14} />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default CRMDialer;
