import React, { useState } from 'react';
import { 
  Bell, 
  X, 
  Phone, 
  Clock, 
  Pin, 
  ChevronDown, 
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Volume2,
  VolumeX,
  CheckCircle2
} from 'lucide-react';
import { useFollowupReminder } from '../../context/FollowupReminderContext';

const FollowupReminderCard = () => {
  const { 
    activeReminders, 
    isMuted,
    toggleMute,
    completeFollowup,
    dismissReminder, 
    snoozeReminder, 
    viewLead,
    playChime
  } = useFollowupReminder();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [showSnoozeMenu, setShowSnoozeMenu] = useState(false);
  const [completingId, setCompletingId] = useState(null);

  if (!activeReminders || activeReminders.length === 0) {
    return null;
  }

  // Ensure currentIndex stays within bounds if reminders array shrinks
  const safeIndex = Math.min(currentIndex, activeReminders.length - 1);
  const currentReminder = activeReminders[safeIndex];

  if (!currentReminder) return null;

  const handleNext = () => {
    setCurrentIndex((prev) => (prev + 1) % activeReminders.length);
    setShowSnoozeMenu(false);
  };

  const handlePrev = () => {
    setCurrentIndex((prev) => (prev - 1 + activeReminders.length) % activeReminders.length);
    setShowSnoozeMenu(false);
  };

  const handleSnooze = (minutes) => {
    setShowSnoozeMenu(false);
    snoozeReminder(currentReminder.id, minutes);
  };

  const handleMarkCompleted = async () => {
    setCompletingId(currentReminder.id);
    await completeFollowup(currentReminder.id);
    setCompletingId(null);
  };

  return (
    <div 
      className="followup-reminder-floating-card"
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 9999,
        width: '375px',
        maxWidth: 'calc(100vw - 32px)',
        backgroundColor: '#ffffff',
        borderRadius: '16px',
        boxShadow: '0 20px 50px -10px rgba(15, 23, 42, 0.35), 0 0 0 1px rgba(220, 38, 38, 0.25)',
        border: '1px solid #fecaca',
        overflow: 'hidden',
        animation: 'slideUpBounce 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        fontFamily: 'inherit'
      }}
    >
      {/* Top Animated Alarm Accent Bar */}
      <div 
        style={{ 
          height: '4px', 
          width: '100%',
          background: isMuted 
            ? 'linear-gradient(90deg, #f59e0b, #d97706)' 
            : 'linear-gradient(90deg, #ef4444, #f59e0b, #ef4444)',
          backgroundSize: '200% 100%',
          animation: isMuted ? 'none' : 'gradientSlide 2s linear infinite'
        }} 
      />

      {/* Card Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        backgroundColor: isMuted ? '#fffbeb' : '#fef2f2',
        borderBottom: `1px solid ${isMuted ? '#fef3c7' : '#fee2e2'}`
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '30px',
            height: '30px',
            borderRadius: '50%',
            backgroundColor: isMuted ? '#fef3c7' : '#fee2e2',
            color: isMuted ? '#d97706' : '#dc2626',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: isMuted ? 'none' : '0 0 0 4px rgba(239, 68, 68, 0.2)'
          }}>
            <Bell size={16} className={isMuted ? '' : 'reminder-bell-ring'} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '0.88rem', fontWeight: 800, color: isMuted ? '#92400e' : '#991b1b' }}>
                Follow-up Alert
              </span>
              <span style={{
                fontSize: '0.68rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                padding: '2px 6px',
                borderRadius: '999px',
                backgroundColor: isMuted ? '#fde68a' : '#fecaca',
                color: isMuted ? '#78350f' : '#b91c1c',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px'
              }}>
                {isMuted ? 'Muted' : 'Alarm Ringing'}
              </span>
            </div>
          </div>

          {activeReminders.length > 1 && (
            <span style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              backgroundColor: '#f1f5f9',
              color: '#334155',
              padding: '1px 6px',
              borderRadius: '10px'
            }}>
              {safeIndex + 1}/{activeReminders.length}
            </span>
          )}
        </div>

        {/* Header Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {activeReminders.length > 1 && (
            <>
              <button
                onClick={handlePrev}
                title="Previous Reminder"
                style={{
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  color: '#64748b',
                  padding: '4px',
                  borderRadius: '6px',
                  display: 'flex'
                }}
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={handleNext}
                title="Next Reminder"
                style={{
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  color: '#64748b',
                  padding: '4px',
                  borderRadius: '6px',
                  display: 'flex'
                }}
              >
                <ChevronRight size={16} />
              </button>
            </>
          )}

          {/* Mute/Silence Sound Toggle */}
          <button
            type="button"
            onClick={toggleMute}
            title={isMuted ? 'Unmute alarm sound' : 'Silence / Mute repeating sound'}
            style={{
              border: 'none',
              background: isMuted ? '#f1f5f9' : '#fee2e2',
              color: isMuted ? '#64748b' : '#dc2626',
              cursor: 'pointer',
              padding: '5px 8px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '0.75rem',
              fontWeight: 600,
              marginLeft: '2px',
              transition: 'all 0.15s ease'
            }}
          >
            {isMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
            <span>{isMuted ? 'Muted' : 'Silence'}</span>
          </button>

          {/* Dismiss Card */}
          <button
            onClick={() => dismissReminder(currentReminder.id)}
            title="Dismiss reminder notification"
            style={{
              border: 'none',
              background: 'transparent',
              color: '#64748b',
              cursor: 'pointer',
              padding: '4px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginLeft: '2px'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#f1f5f9'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <X size={17} />
          </button>
        </div>
      </div>

      {/* Card Body */}
      <div style={{ padding: '16px' }}>
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '2px' }}>
            Pending Follow-Up
          </div>
          <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#0f172a', wordBreak: 'break-word', lineHeight: 1.3 }}>
            {currentReminder.lead_name}
          </div>
        </div>

        {/* Details Box */}
        <div style={{ 
          backgroundColor: '#f8fafc', 
          borderRadius: '10px', 
          padding: '12px', 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '8px', 
          marginBottom: '14px',
          border: '1px solid #e2e8f0'
        }}>
          {/* Phone */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.86rem', color: '#334155' }}>
            <Phone size={14} style={{ color: '#2563eb', flexShrink: 0 }} />
            <a 
              href={`tel:${currentReminder.lead_phone}`} 
              style={{ fontWeight: 600, color: '#2563eb', textDecoration: 'none' }}
              title="Click to call"
            >
              {currentReminder.lead_phone || '-'}
            </a>
          </div>

          {/* Scheduled Time */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.86rem', color: '#334155' }}>
            <Clock size={14} style={{ color: '#d97706', flexShrink: 0 }} />
            <span style={{ fontWeight: 600, color: '#0f172a' }}>
              {currentReminder.display_time || currentReminder.followup_time || 'Scheduled'}
            </span>
          </div>

          {/* Notes / Purpose */}
          {currentReminder.notes && (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '0.82rem', color: '#475569' }}>
              <Pin size={14} style={{ color: '#ef4444', flexShrink: 0, marginTop: '2px' }} />
              <span style={{ 
                wordBreak: 'break-word',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical'
              }}>
                {currentReminder.notes}
              </span>
            </div>
          )}
        </div>

        {/* Status Alarm Guidance */}
        <div style={{ 
          fontSize: '0.72rem', 
          color: '#64748b', 
          marginBottom: '12px', 
          display: 'flex', 
          alignItems: 'center', 
          gap: '5px' 
        }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#ef4444', display: 'inline-block' }} />
          <span>Update status to Completed below to stop the reminder sound.</span>
        </div>

        {/* Action Buttons Row */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {/* PRIMARY: Mark Completed Button (Stops Alarm) */}
          <button
            onClick={handleMarkCompleted}
            disabled={completingId === currentReminder.id}
            title="Mark this follow-up as Completed and stop the alert sound"
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              backgroundColor: '#16a34a',
              color: '#ffffff',
              border: 'none',
              borderRadius: '8px',
              padding: '10px 14px',
              fontSize: '0.88rem',
              fontWeight: 700,
              cursor: completingId === currentReminder.id ? 'not-allowed' : 'pointer',
              transition: 'background-color 0.15s ease',
              boxShadow: '0 2px 6px rgba(22, 163, 74, 0.35)'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#15803d'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#16a34a'; }}
          >
            <CheckCircle2 size={16} />
            <span>{completingId === currentReminder.id ? 'Updating Status...' : 'Mark Completed (Stop Sound)'}</span>
          </button>

          {/* Secondary Buttons Row: View Lead & Snooze */}
          <div style={{ display: 'flex', gap: '8px', position: 'relative' }}>
            {/* View Lead Button */}
            <button
              onClick={() => viewLead(currentReminder.lead_id)}
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                backgroundColor: '#2563eb',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                padding: '8px 12px',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'background-color 0.15s ease'
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#1d4ed8'; }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#2563eb'; }}
            >
              <span>View Lead</span>
              <ExternalLink size={13} />
            </button>

            {/* Snooze Button */}
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setShowSnoozeMenu(prev => !prev)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  backgroundColor: '#f1f5f9',
                  color: '#334155',
                  border: '1px solid #cbd5e1',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#e2e8f0'; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#f1f5f9'; }}
              >
                <span>Snooze</span>
                <ChevronDown size={13} />
              </button>

              {/* Snooze Options Popup Menu */}
              {showSnoozeMenu && (
                <div 
                  style={{
                    position: 'absolute',
                    bottom: '100%',
                    right: 0,
                    marginBottom: '8px',
                    backgroundColor: '#ffffff',
                    borderRadius: '10px',
                    boxShadow: '0 10px 25px rgba(0,0,0,0.18), 0 0 0 1px #e2e8f0',
                    padding: '6px',
                    width: '145px',
                    zIndex: 10000,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '2px'
                  }}
                >
                  <div style={{ fontSize: '0.70rem', color: '#94a3b8', fontWeight: 700, padding: '4px 8px', textTransform: 'uppercase' }}>
                    Remind again in
                  </div>
                  {[
                    { label: '10 minutes', mins: 10 },
                    { label: '15 minutes', mins: 15 },
                    { label: '30 minutes', mins: 30 },
                    { label: '1 hour', mins: 60 }
                  ].map(opt => (
                    <button
                      key={opt.mins}
                      onClick={() => handleSnooze(opt.mins)}
                      style={{
                        border: 'none',
                        backgroundColor: 'transparent',
                        textAlign: 'left',
                        padding: '7px 10px',
                        fontSize: '0.82rem',
                        fontWeight: 500,
                        color: '#1e293b',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        transition: 'background 0.15s ease'
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#f8fafc'; e.currentTarget.style.color = '#2563eb'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = '#1e293b'; }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes slideUpBounce {
          0% { transform: translateY(100px); opacity: 0; }
          70% { transform: translateY(-8px); opacity: 1; }
          100% { transform: translateY(0); opacity: 1; }
        }
        @keyframes ring {
          0%, 100% { transform: rotate(0deg); }
          20%, 60% { transform: rotate(18deg); }
          40%, 80% { transform: rotate(-18deg); }
        }
        @keyframes gradientSlide {
          0% { background-position: 0% 50%; }
          100% { background-position: 200% 50%; }
        }
        .reminder-bell-ring {
          animation: ring 1.2s ease infinite;
          transform-origin: top center;
        }
        @media (max-width: 640px) {
          .followup-reminder-floating-card {
            bottom: 16px !important;
            right: 12px !important;
            left: 12px !important;
            width: auto !important;
            max-width: none !important;
          }
        }
      `}</style>
    </div>
  );
};

export default FollowupReminderCard;
