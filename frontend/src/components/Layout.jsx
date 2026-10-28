import React, { useState, useEffect, useRef } from 'react';
import { Outlet, Link, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar/Sidebar';
import CRMDialer from './Dialer/CRMDialer';
import DooctiInAppDialer from './Dialer/DooctiInAppDialer';
import CallCompletionDispositionModal from './Dialer/CallCompletionDispositionModal';
import FollowupReminderCard from './FollowupReminder/FollowupReminderCard';
import { Menu, Building2, PhoneIncoming, X, ArrowRight } from 'lucide-react';
import API from '../services/api';

const Layout = () => {
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [incomingAlert, setIncomingAlert] = useState(null);
  const [dispositionCallData, setDispositionCallData] = useState(null);
  const [showDispositionModal, setShowDispositionModal] = useState(false);
  const lastCallIdRef = useRef(null);
  const isInitialMount = useRef(true);
  const navigate = useNavigate();

  // Real-time Incoming Call Alert & Polling Management
  useEffect(() => {
    let isMounted = true;

    // 1. Listen for immediate zero-lag real-time incoming call events from Doocti WebPhone
    const handleIncomingCallEvent = (e) => {
      if (!isMounted) return;
      const data = e.detail;
      if (data) {
        setIncomingAlert({
          id: data.id || null,
          provider_call_id: data.provider_call_id,
          customer_phone: data.customer_phone || data.from_number,
          from_number: data.from_number || data.customer_phone,
          lead_name: data.lead_name || 'Incoming Caller',
          company: data.company || '',
          lead_status: data.lead_status || 'NEW',
          employee_name: data.employee_name || 'Assigned Representative',
          call_status: 'RINGING',
          call_direction: 'INBOUND',
          started_at: data.started_at || new Date().toISOString()
        });
      }
    };

    const handleCallAnsweredEvent = (e) => {
      if (!isMounted) return;
      setIncomingAlert(prev => prev ? ({ ...prev, call_status: 'CONNECTED', answered_at: Date.now() }) : null);
    };

    const handleCallEndedEvent = (e) => {
      if (!isMounted) return;
      setIncomingAlert(null);
    };

    const handleCallCompletedDisposition = (e) => {
      if (!isMounted) return;
      const data = e.detail;
      if (data) {
        setDispositionCallData(data);
        setShowDispositionModal(true);
      }
    };

    window.addEventListener('crm-incoming-call', handleIncomingCallEvent);
    window.addEventListener('crm-call-answered', handleCallAnsweredEvent);
    window.addEventListener('crm-incoming-call-ended', handleCallEndedEvent);
    window.addEventListener('crm-call-completed', handleCallEndedEvent);
    window.addEventListener('crm-call-completed', handleCallCompletedDisposition);

    // 2. Resilient background polling: synchronizes active ringing/connected calls across tabs
    const checkRecentCalls = async () => {
      try {
        const res = await API.get('/ivr/calls?limit=1');
        const latest = res.data?.items?.[0];
        if (!latest || !isMounted) return;

        if (isInitialMount.current) {
          lastCallIdRef.current = latest.id;
          isInitialMount.current = false;
          // If already actively ringing on mount, show it
          if (latest.call_direction === 'INBOUND' && (latest.call_status || '').toUpperCase() === 'RINGING') {
            setIncomingAlert(latest);
          }
          return;
        }

        const latestStatus = (latest.call_status || '').toUpperCase();
        const isLatestInbound = (latest.call_direction || '').toUpperCase() === 'INBOUND';

        // ONLY trigger new inbound alert if call is GENUINELY RINGING or CONNECTED (never for finished/failed calls)
        if (latest.id > (lastCallIdRef.current || 0)) {
          lastCallIdRef.current = latest.id;
          if (isLatestInbound && latestStatus === 'RINGING') {
            setIncomingAlert(latest);
          }
        } else if (incomingAlert) {
          // If currently displaying this call, synchronize state transitions
          const matchesCurrent = (incomingAlert.id && incomingAlert.id === latest.id) || 
                                 (incomingAlert.provider_call_id && incomingAlert.provider_call_id === latest.provider_call_id);
          if (matchesCurrent) {
            if (['ANSWERED', 'CONNECTED'].includes(latestStatus)) {
              setIncomingAlert(prev => prev ? ({ ...prev, call_status: 'CONNECTED' }) : null);
            } else if (['COMPLETED', 'MISSED', 'NO_ANSWER', 'FAILED', 'BUSY'].includes(latestStatus)) {
              // Terminal state reached: dismiss active popup
              setIncomingAlert(null);
            }
          }
        }
      } catch (e) {
        // Silent fail on background polling
      }
    };

    checkRecentCalls();
    const interval = setInterval(checkRecentCalls, 3500);

    return () => {
      isMounted = false;
      clearInterval(interval);
      window.removeEventListener('crm-incoming-call', handleIncomingCallEvent);
      window.removeEventListener('crm-call-answered', handleCallAnsweredEvent);
      window.removeEventListener('crm-incoming-call-ended', handleCallEndedEvent);
      window.removeEventListener('crm-call-completed', handleCallEndedEvent);
      window.removeEventListener('crm-call-completed', handleCallCompletedDisposition);
    };
  }, [incomingAlert]);

  // Answer Incoming Call action from global alert
  const handleAnswerIncoming = () => {
    if (window.crmAnswerCall) {
      window.crmAnswerCall();
    }
    if (window.expandDoocti) {
      window.expandDoocti();
    }
    setIncomingAlert(prev => prev ? ({ ...prev, call_status: 'CONNECTED' }) : null);
  };

  // Reject Incoming Call action from global alert
  const handleRejectIncoming = () => {
    const callId = incomingAlert?.id || incomingAlert?.provider_call_id;
    if (window.crmRejectCall) {
      window.crmRejectCall();
    }
    if (window.expandDoocti) {
      window.expandDoocti();
    }
    if (callId) {
      API.post(`/ivr/calls/${callId}/reject`).catch(() => {
        API.post(`/doocti/calls/${callId}/reject`).catch(() => {});
      });
    }
    setIncomingAlert(null);
  };

  // End active connected call action from global alert
  const handleHangupActive = () => {
    const callId = incomingAlert?.id || incomingAlert?.provider_call_id;
    if (window.crmHangupCall) {
      window.crmHangupCall();
    }
    if (callId) {
      API.post(`/ivr/calls/${callId}/disconnect`).catch(() => {
        API.post(`/doocti/calls/${callId}/disconnect`).catch(() => {});
      });
    }
    setIncomingAlert(null);
  };

  return (
    <div className="app-container">
      {/* Global Interactive Incoming Call Alert Banner */}
      {incomingAlert && (
        <div style={{
          position: 'fixed',
          top: '24px',
          right: '24px',
          zIndex: 99999,
          backgroundColor: '#ffffff',
          borderRadius: '18px',
          boxShadow: '0 24px 48px -12px rgba(15, 23, 42, 0.35), 0 0 0 1px rgba(16, 185, 129, 0.3)',
          padding: '16px 20px',
          maxWidth: '430px',
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          animation: 'slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
        }}>
          {/* Header Row */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '42px',
                height: '42px',
                borderRadius: '50%',
                backgroundColor: incomingAlert.call_status === 'CONNECTED' ? '#ecfdf5' : '#fef3c7',
                color: incomingAlert.call_status === 'CONNECTED' ? '#059669' : '#d97706',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <PhoneIncoming size={22} className="animate-pulse" />
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#0f172a', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                    Incoming Call
                  </span>
                  <span style={{
                    fontSize: '0.68rem',
                    padding: '2px 8px',
                    borderRadius: '9999px',
                    backgroundColor: incomingAlert.call_status === 'CONNECTED' ? '#ecfdf5' : '#fef3c7',
                    color: incomingAlert.call_status === 'CONNECTED' ? '#047857' : '#b45309',
                    fontWeight: 700,
                    border: incomingAlert.call_status === 'CONNECTED' ? '1px solid #a7f3d0' : '1px solid #fde68a'
                  }}>
                    {incomingAlert.call_status === 'CONNECTED' ? 'CONNECTED' : 'RINGING...'}
                  </span>
                </div>
                <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0f172a', lineHeight: '1.3', marginTop: '2px' }}>
                  {incomingAlert.lead_name || 'Incoming Caller'}
                </div>
              </div>
            </div>

            <button
              onClick={() => setIncomingAlert(null)}
              style={{
                background: 'none',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer',
                padding: '4px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
              title="Dismiss Alert"
            >
              <X size={18} />
            </button>
          </div>

          {/* Caller Details Card */}
          <div style={{
            backgroundColor: '#f8fafc',
            borderRadius: '12px',
            padding: '10px 14px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            border: '1px solid #f1f5f9'
          }}>
            <div>
              <div style={{ fontSize: '0.86rem', color: '#1e40af', fontWeight: 700 }}>
                {incomingAlert.customer_phone || incomingAlert.from_number}
              </div>
              {incomingAlert.company && (
                <div style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 500, marginTop: '1px' }}>
                  {incomingAlert.company}
                </div>
              )}
            </div>
            {incomingAlert.employee_name && (
              <div style={{ textAlign: 'right' }}>
                <span style={{ fontSize: '0.68rem', color: '#94a3b8', fontWeight: 600, display: 'block', textTransform: 'uppercase' }}>
                  Agent
                </span>
                <span style={{ fontSize: '0.78rem', color: '#334155', fontWeight: 700 }}>
                  {incomingAlert.employee_name}
                </span>
              </div>
            )}
          </div>

          {/* Interactive Call Control Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
            {incomingAlert.call_status === 'CONNECTED' ? (
              <>
                <button
                  type="button"
                  onClick={handleHangupActive}
                  style={{
                    flex: 1,
                    backgroundColor: '#ef4444',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '10px 14px',
                    fontSize: '0.84rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    boxShadow: '0 4px 12px rgba(239, 68, 68, 0.3)'
                  }}
                  title="End Active Call"
                >
                  <PhoneIncoming size={16} style={{ transform: 'rotate(135deg)' }} />
                  <span>End Call</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (window.expandDoocti) window.expandDoocti();
                  }}
                  style={{
                    backgroundColor: '#f1f5f9',
                    color: '#1e293b',
                    border: '1px solid #e2e8f0',
                    borderRadius: '10px',
                    padding: '10px 14px',
                    fontSize: '0.84rem',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Open Softphone
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={handleAnswerIncoming}
                  style={{
                    flex: 1,
                    backgroundColor: '#10b981',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '10px 14px',
                    fontSize: '0.84rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    boxShadow: '0 4px 12px rgba(16, 185, 129, 0.35)'
                  }}
                  title="Answer Call"
                >
                  <PhoneIncoming size={16} />
                  <span>Answer Call</span>
                </button>
                <button
                  type="button"
                  onClick={handleRejectIncoming}
                  style={{
                    flex: 1,
                    backgroundColor: '#ef4444',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '10px 14px',
                    fontSize: '0.84rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    boxShadow: '0 4px 12px rgba(239, 68, 68, 0.35)'
                  }}
                  title="Reject / Decline Call"
                >
                  <X size={16} />
                  <span>Reject</span>
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Sidebar Navigation */}
      <Sidebar 
        isMobileOpen={isMobileOpen}
        onMobileClose={() => setIsMobileOpen(false)}
      />

      {/* Main Right Wrapper */}
      <div className="main-wrapper">
        {/* Mobile Top Header (Visible on screens < 768px) */}
        <header className="mobile-topbar">
          <button 
            type="button"
            className="mobile-hamburger-btn"
            onClick={() => setIsMobileOpen(true)}
            aria-label="Open Navigation Menu"
          >
            <Menu size={22} />
          </button>
          <div className="brand-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img 
              src="/wa-crm-logo-transparent.png" 
              alt="WA! CRM Logo" 
              style={{
                height: '32px',
                width: 'auto',
                maxWidth: '130px',
                objectFit: 'contain',
                borderRadius: '6px'
              }}
            />
          </div>
        </header>

        {/* Dynamic Route Content */}
        <main className="content-area">
          <Outlet />
        </main>
      </div>

      {/* Global CRM Phone Dialer Widget */}
      <CRMDialer />

      {/* Doocti In-App WebRTC Softphone Widget */}
      <DooctiInAppDialer />

      {/* Global Automatic Follow-up Reminder Floating Notification Card */}
      <FollowupReminderCard />

      {/* Mandatory Product Classification & Call Completion Disposition Modal */}
      <CallCompletionDispositionModal
        isOpen={showDispositionModal}
        callData={dispositionCallData}
        onClose={() => {
          setShowDispositionModal(false);
          setDispositionCallData(null);
        }}
        onSaved={() => {
          setShowDispositionModal(false);
          setDispositionCallData(null);
        }}
      />
    </div>
  );
};

export default Layout;
