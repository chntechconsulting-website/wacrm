import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import PingoPopupService from '../../services/pingoPopupService';
import { useAuth } from '../../context/AuthContext';
import {
  PhoneCall,
  User,
  Clock,
  Tag,
  CheckCircle2,
  AlertCircle,
  FileText,
  X,
  RefreshCw,
  Cpu,
  Layers,
  HelpCircle,
  Calendar
} from 'lucide-react';

/**
 * CallCompletionDispositionModal
 * Displays after an incoming or outgoing DooCTI / IVR call ends.
 * Enforces mandatory product categorization (BIOMETRIC, WAHRMS, UNCLASSIFIED)
 * along with call notes and disposition status.
 */
const CallCompletionDispositionModal = ({
  isOpen,
  callData,
  onClose,
  onSaved
}) => {
  const { currentUser } = useAuth();
  const [leadName, setLeadName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [callStatus, setCallStatus] = useState('COMPLETED');
  const [durationSeconds, setDurationSeconds] = useState(0);
  const [leadId, setLeadId] = useState(null);
  const [existingCategory, setExistingCategory] = useState(null);
  const [categoryConfirmed, setCategoryConfirmed] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('UNCLASSIFIED');
  const [suggestedCategory, setSuggestedCategory] = useState('UNCLASSIFIED');
  const [callNotes, setCallNotes] = useState('');
  const [dispositionStatus, setDispositionStatus] = useState('CONTACTED');

  // Follow-up specific fields
  const getTomorrowDate = () => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split('T')[0];
  };
  const [followupDate, setFollowupDate] = useState(getTomorrowDate());
  const [followupTime, setFollowupTime] = useState('10:00 AM');
  const [followupPriority, setFollowupPriority] = useState('MEDIUM');

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (!isOpen || !callData) return;

    setSaveError('');
    setSaveSuccess(false);

    const rawPhone = callData.phone_number || callData.customer_phone || callData.to_number || callData.from_number || '';
    const cleanPhone = String(rawPhone || '').replace(/[^0-9]/g, '');
    setPhoneNumber(rawPhone);

    const dur = callData.duration || callData.duration_seconds || 0;
    setDurationSeconds(dur);

    const st = (callData.status || callData.call_status || 'COMPLETED').toUpperCase();
    setCallStatus(st);

    if (['MISSED', 'NO_ANSWER', 'FAILED'].includes(st)) {
      setDispositionStatus('NO_ANSWER');
    } else {
      setDispositionStatus('CONTACTED');
    }

    setFollowupDate(getTomorrowDate());
    setFollowupTime('10:00 AM');
    setFollowupPriority('MEDIUM');

    const initialNotes = callData.notes || '';
    setCallNotes(initialNotes);

    // Initial lead identification
    const targetLeadId = callData.lead_id || callData.entity_id || null;
    if (targetLeadId) {
      setLeadId(targetLeadId);
    }

    const initialName = callData.lead_name || callData.name || (targetLeadId ? `Lead #${targetLeadId}` : 'Caller');
    setLeadName(initialName);

    // Auto-detect or fetch lead info if phone is available
    if (cleanPhone && cleanPhone.length >= 6) {
      API.get(`/doocti/lead-by-number?number=${cleanPhone}&auto_create=false`)
        .then(res => {
          if (res.data?.success && res.data?.lead) {
            const ld = res.data.lead;
            setLeadId(ld.id);
            setLeadName(ld.name || ld.company || `Lead #${ld.id}`);
            
            const existingCat = ld.product_category || null;
            const isConfirmed = Boolean(ld.product_category_confirmed);
            const suggested = ld.suggested_product_category || ld.product_category || 'UNCLASSIFIED';

            setExistingCategory(existingCat);
            setCategoryConfirmed(isConfirmed);
            setSuggestedCategory(suggested);

            // Default selection: if confirmed, keep confirmed; otherwise suggested or unclassified
            if (isConfirmed && existingCat) {
              setSelectedCategory(existingCat);
            } else if (suggested && suggested !== 'UNCLASSIFIED') {
              setSelectedCategory(suggested);
            } else if (existingCat) {
              setSelectedCategory(existingCat);
            } else {
              setSelectedCategory('UNCLASSIFIED');
            }
          } else {
            // Not found in leads - analyze call notes
            detectFromNotes(initialNotes);
          }
        })
        .catch(() => {
          detectFromNotes(initialNotes);
        });
    } else {
      detectFromNotes(initialNotes);
    }
  }, [isOpen, callData]);

  const detectFromNotes = (text) => {
    if (!text) {
      setSelectedCategory('UNCLASSIFIED');
      setSuggestedCategory('UNCLASSIFIED');
      return;
    }
    const t = text.toLowerCase();
    if (t.includes('biometric') || t.includes('fingerprint') || t.includes('mb160') || t.includes('zkteco') || t.includes('machine') || t.includes('terminal')) {
      setSelectedCategory('BIOMETRIC');
      setSuggestedCategory('BIOMETRIC');
    } else if (t.includes('wahrms') || t.includes('hrms') || t.includes('payroll') || t.includes('software') || t.includes('leave')) {
      setSelectedCategory('WAHRMS');
      setSuggestedCategory('WAHRMS');
    } else {
      setSelectedCategory('UNCLASSIFIED');
      setSuggestedCategory('UNCLASSIFIED');
    }
  };

  const formatDuration = (sec) => {
    const s = Number(sec || 0);
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    return `${mins}m ${secs < 10 ? '0' : ''}${secs}s`;
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaveError('');

    // Validation for Follow-up status
    const isFollowup = dispositionStatus === 'FOLLOW-UP';
    if (isFollowup && !followupDate) {
      setSaveError('Please select a valid Follow-up Date.');
      return;
    }

    setSaving(true);

    try {
      const callUniqueId = callData?.uniqueid || callData?.callId || callData?.provider_call_id || null;
      const currentEmpId = currentUser?.employee_id || currentUser?.id || null;

      const payload = {
        status: dispositionStatus,
        call_notes: callNotes,
        product_category: selectedCategory,
        call_id: callUniqueId,
        employee_id: currentEmpId,
        agent_email: currentUser?.email || null,
        followup_date: isFollowup ? followupDate : null,
        followup_time: isFollowup ? (followupTime || '10:00 AM') : null,
        followup_priority: isFollowup ? followupPriority : 'MEDIUM'
      };

      let savedLeadId = leadId;

      // 1. If leadId is present, update Lead through backend API
      if (leadId) {
        await API.post('/doocti/lead/update', {
          ...payload,
          lead_id: leadId
        });
      } else if (phoneNumber) {
        // Find or auto-create lead so disposition is not lost
        const findRes = await API.get(`/doocti/lead-by-number?number=${phoneNumber}&auto_create=true`);
        if (findRes.data?.lead?.id) {
          savedLeadId = findRes.data.lead.id;
          setLeadId(savedLeadId);
          await API.post('/doocti/lead/update', {
            ...payload,
            lead_id: savedLeadId
          });
        }
      }

      setSaveSuccess(true);
      window.dispatchEvent(new Event('leadStatsUpdated'));
      window.dispatchEvent(new Event('followupReminderRefresh'));
      window.dispatchEvent(new CustomEvent('call-disposition-saved', {
        detail: {
          leadId: savedLeadId,
          product_category: selectedCategory,
          status: dispositionStatus,
          notes: callNotes,
          followup_date: isFollowup ? followupDate : null,
          followup_time: isFollowup ? followupTime : null
        }
      }));

      PingoPopupService.showNotification({
        title: 'Call Disposition Saved',
        message: isFollowup 
          ? `Follow-up scheduled for ${followupDate}. Category: ${selectedCategory}.` 
          : `Category: ${selectedCategory}. Notes and status updated successfully.`,
        type: 'success'
      });

      setTimeout(() => {
        if (onSaved) onSaved({ leadId: savedLeadId, product_category: selectedCategory });
        if (onClose) onClose();
      }, 700);
    } catch (err) {
      console.error('Failed to save call disposition:', err);
      const msg = err.response?.data?.detail || err.message || 'Network error: Failed to save call disposition. Please try again.';
      setSaveError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.6)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 99999,
      padding: '16px'
    }}>
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '16px',
        width: '100%',
        maxWidth: '520px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
        overflow: 'hidden',
        animation: 'fadeIn 0.2s ease-out'
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 22px',
          background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
          color: '#ffffff',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#38bdf8'
            }}>
              <PhoneCall size={20} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, letterSpacing: '-0.01em' }}>
                Call Ended &bull; Disposition
              </h3>
              <p style={{ margin: 0, fontSize: '0.75rem', color: '#94a3b8' }}>
                Mandatory Product Classification &amp; Notes
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            title="Dismiss Popup"
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '6px'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Call Summary Banner */}
        <div style={{
          padding: '14px 22px',
          backgroundColor: '#f8fafc',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '8px'
        }}>
          <div>
            <div style={{ fontSize: '0.92rem', fontWeight: 800, color: '#0f172a' }}>
              {leadName || 'Direct Caller'}
            </div>
            <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
              {phoneNumber || 'Unknown Number'} {leadId && `(Lead #${leadId})`}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: '6px',
              backgroundColor: callStatus === 'COMPLETED' ? '#dcfce7' : '#fee2e2',
              color: callStatus === 'COMPLETED' ? '#15803d' : '#b91c1c'
            }}>
              {callStatus}
            </span>
            <span style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: '6px',
              backgroundColor: '#eff6ff',
              color: '#1d4ed8',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <Clock size={12} /> {formatDuration(durationSeconds)}
            </span>
          </div>
        </div>

        {/* Main Disposition Form */}
        <form onSubmit={handleSave} style={{ padding: '20px 22px' }}>
          {/* 1. Mandatory Product Classification */}
          <div style={{ marginBottom: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <label style={{
                fontSize: '0.82rem',
                fontWeight: 800,
                color: '#0f172a',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                <Tag size={14} color="#2563eb" />
                Product Classification *
              </label>
              {existingCategory && (
                <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                  Current: <strong style={{ color: '#0f172a' }}>{existingCategory}</strong>
                  {categoryConfirmed && ' (Confirmed)'}
                </span>
              )}
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: '8px',
              marginBottom: '6px'
            }}>
              {/* Option 1: BIOMETRIC */}
              <button
                type="button"
                onClick={() => setSelectedCategory('BIOMETRIC')}
                style={{
                  padding: '10px 8px',
                  borderRadius: '10px',
                  border: selectedCategory === 'BIOMETRIC' ? '2px solid #2563eb' : '1px solid #cbd5e1',
                  backgroundColor: selectedCategory === 'BIOMETRIC' ? '#eff6ff' : '#ffffff',
                  color: selectedCategory === 'BIOMETRIC' ? '#1d4ed8' : '#334155',
                  cursor: 'pointer',
                  fontWeight: selectedCategory === 'BIOMETRIC' ? 800 : 600,
                  fontSize: '0.82rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'all 0.15s ease'
                }}
              >
                <Cpu size={18} color={selectedCategory === 'BIOMETRIC' ? '#2563eb' : '#64748b'} />
                <span>BIOMETRIC</span>
                <span style={{ fontSize: '0.66rem', color: '#64748b', fontWeight: 500 }}>Hardware / Terminal</span>
              </button>

              {/* Option 2: WAHRMS */}
              <button
                type="button"
                onClick={() => setSelectedCategory('WAHRMS')}
                style={{
                  padding: '10px 8px',
                  borderRadius: '10px',
                  border: selectedCategory === 'WAHRMS' ? '2px solid #16a34a' : '1px solid #cbd5e1',
                  backgroundColor: selectedCategory === 'WAHRMS' ? '#f0fdf4' : '#ffffff',
                  color: selectedCategory === 'WAHRMS' ? '#15803d' : '#334155',
                  cursor: 'pointer',
                  fontWeight: selectedCategory === 'WAHRMS' ? 800 : 600,
                  fontSize: '0.82rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'all 0.15s ease'
                }}
              >
                <Layers size={18} color={selectedCategory === 'WAHRMS' ? '#16a34a' : '#64748b'} />
                <span>WAHRMS</span>
                <span style={{ fontSize: '0.66rem', color: '#64748b', fontWeight: 500 }}>Cloud HR Software</span>
              </button>

              {/* Option 3: UNCLASSIFIED */}
              <button
                type="button"
                onClick={() => setSelectedCategory('UNCLASSIFIED')}
                style={{
                  padding: '10px 8px',
                  borderRadius: '10px',
                  border: selectedCategory === 'UNCLASSIFIED' ? '2px solid #64748b' : '1px solid #cbd5e1',
                  backgroundColor: selectedCategory === 'UNCLASSIFIED' ? '#f1f5f9' : '#ffffff',
                  color: selectedCategory === 'UNCLASSIFIED' ? '#0f172a' : '#334155',
                  cursor: 'pointer',
                  fontWeight: selectedCategory === 'UNCLASSIFIED' ? 800 : 600,
                  fontSize: '0.82rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'all 0.15s ease'
                }}
              >
                <HelpCircle size={18} color={selectedCategory === 'UNCLASSIFIED' ? '#0f172a' : '#64748b'} />
                <span>UNCLASSIFIED</span>
                <span style={{ fontSize: '0.66rem', color: '#64748b', fontWeight: 500 }}>Ambiguous / General</span>
              </button>
            </div>

            {suggestedCategory && suggestedCategory !== 'UNCLASSIFIED' && (
              <div style={{
                fontSize: '0.72rem',
                color: '#2563eb',
                backgroundColor: '#eff6ff',
                padding: '4px 10px',
                borderRadius: '6px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                <span>💡 Auto-detected from lead signals: <strong>{suggestedCategory}</strong></span>
              </div>
            )}
          </div>

          {/* 2. Call Disposition Outcome */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
              Lead Call Disposition
            </label>
            <select
              value={dispositionStatus}
              onChange={(e) => setDispositionStatus(e.target.value)}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '8px',
                border: '1.5px solid #cbd5e1',
                fontSize: '0.86rem',
                fontWeight: 600,
                color: '#0f172a',
                outline: 'none',
                backgroundColor: '#ffffff'
              }}
            >
              <option value="CONTACTED">Contacted / Discussion Completed</option>
              <option value="INTERESTED">Interested / Demo Requested</option>
              <option value="FOLLOW-UP">Follow-up Required</option>
              <option value="RNR">RNR (Ringing No Response)</option>
              <option value="PROPOSAL SENT">Proposal / Quotation Sent</option>
              <option value="NO_ANSWER">No Answer / Busy / Disconnected</option>
              <option value="NOT_INTERESTED">Not Interested / Closed</option>
              <option value="JUNK">Junk / Invalid Lead</option>
            </select>
          </div>

          {/* Conditional Follow-up Scheduling Section */}
          {dispositionStatus === 'FOLLOW-UP' && (
            <div style={{
              marginBottom: '16px',
              padding: '12px 14px',
              backgroundColor: '#eff6ff',
              borderRadius: '10px',
              border: '1px solid #bfdbfe'
            }}>
              <div style={{
                fontSize: '0.8rem',
                fontWeight: 800,
                color: '#1e40af',
                marginBottom: '10px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                <Calendar size={15} color="#2563eb" />
                Schedule Next Follow-up *
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '8px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.74rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Follow-up Date
                  </label>
                  <input
                    type="date"
                    required
                    value={followupDate}
                    onChange={(e) => setFollowupDate(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '7px 10px',
                      borderRadius: '6px',
                      border: '1px solid #cbd5e1',
                      fontSize: '0.82rem',
                      color: '#0f172a',
                      boxSizing: 'border-box',
                      backgroundColor: '#ffffff'
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.74rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Follow-up Time
                  </label>
                  <input
                    type="text"
                    value={followupTime}
                    placeholder="e.g. 10:30 AM"
                    onChange={(e) => setFollowupTime(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '7px 10px',
                      borderRadius: '6px',
                      border: '1px solid #cbd5e1',
                      fontSize: '0.82rem',
                      color: '#0f172a',
                      boxSizing: 'border-box',
                      backgroundColor: '#ffffff'
                    }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.74rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Priority
                </label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {['LOW', 'MEDIUM', 'HIGH'].map(p => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setFollowupPriority(p)}
                      style={{
                        flex: 1,
                        padding: '5px 8px',
                        fontSize: '0.74rem',
                        fontWeight: followupPriority === p ? 800 : 500,
                        borderRadius: '6px',
                        border: followupPriority === p ? '1.5px solid #2563eb' : '1px solid #cbd5e1',
                        backgroundColor: followupPriority === p ? '#dbeafe' : '#ffffff',
                        color: followupPriority === p ? '#1d4ed8' : '#64748b',
                        cursor: 'pointer'
                      }}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* 3. Call Notes */}
          <div style={{ marginBottom: '18px' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
              Call Notes &amp; Client Requirement
            </label>
            <textarea
              rows={3}
              value={callNotes}
              onChange={(e) => setCallNotes(e.target.value)}
              placeholder="Record key discussion points, requirements, and next steps..."
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '8px',
                border: '1.5px solid #cbd5e1',
                fontSize: '0.86rem',
                color: '#0f172a',
                outline: 'none',
                resize: 'vertical',
                boxSizing: 'border-box'
              }}
            />
          </div>

          {/* Feedback & Error states */}
          {saveError && (
            <div style={{
              padding: '10px 14px',
              backgroundColor: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '8px',
              color: '#b91c1c',
              fontSize: '0.82rem',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <AlertCircle size={16} />
              <span>{saveError}</span>
            </div>
          )}

          {saveSuccess && (
            <div style={{
              padding: '10px 14px',
              backgroundColor: '#f0fdf4',
              border: '1px solid #bbf7d0',
              borderRadius: '8px',
              color: '#15803d',
              fontSize: '0.82rem',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <CheckCircle2 size={16} />
              <span>Disposition and product category saved successfully!</span>
            </div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              style={{
                padding: '9px 16px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                backgroundColor: '#ffffff',
                color: '#475569',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Skip / Later
            </button>
            <button
              type="submit"
              disabled={saving}
              style={{
                padding: '9px 20px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: '#2563eb',
                color: '#ffffff',
                fontSize: '0.85rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: '0 2px 8px rgba(37, 99, 235, 0.25)'
              }}
            >
              {saving ? <RefreshCw size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
              <span>Save Call Disposition</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CallCompletionDispositionModal;
