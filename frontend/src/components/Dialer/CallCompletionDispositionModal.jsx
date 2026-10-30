import React, { useState, useEffect, useRef } from 'react';
import API from '../../services/api';
import PingoPopupService from '../../services/pingoPopupService';
import { useAuth } from '../../context/AuthContext';
import {
  PhoneCall,
  PhoneIncoming,
  PhoneOutgoing,
  User,
  Mail,
  Building2,
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
  Calendar,
  CalendarClock,
  UserCheck,
  Briefcase
} from 'lucide-react';

const STATUS_OPTIONS = [
  'NEW LEAD',
  'CONTACTED',
  'INTERESTED',
  'DEMO / MEETING',
  'PROPOSAL SENT',
  'FOLLOW-UP',
  'RNR',
  'WON',
  'LOST',
  'JUNK'
];

const SOURCE_OPTIONS = [
  'Inbound Call',
  'Outbound Call',
  'Referral',
  'Website',
  'Meta',
  'Manual',
  'Other'
];

const FOLLOWUP_TYPES = [
  'Call',
  'Meeting',
  'Demo',
  'WhatsApp',
  'Email'
];

/**
 * CallCompletionDispositionModal
 * Appears ONLY when a new inbound or outbound call has genuinely completed.
 * Allows agents to create a new Lead or update an existing Lead, link call logs,
 * confirm mandatory product classification, and schedule follow-ups.
 */
const CallCompletionDispositionModal = ({
  isOpen,
  callData,
  onClose,
  onSaved
}) => {
  const { currentUser } = useAuth();

  // Call Identification & Metadata
  const [callId, setCallId] = useState('');
  const [callDirection, setCallDirection] = useState('INBOUND');
  const [durationSeconds, setDurationSeconds] = useState(0);
  const [callDateTime, setCallDateTime] = useState('');
  const [isExistingLead, setIsExistingLead] = useState(false);
  const [leadId, setLeadId] = useState(null);

  // Active Employees for assignment
  const [employees, setEmployees] = useState([]);

  // Customer Details Form Fields
  const [customerName, setCustomerName] = useState('');
  const [mobileNumber, setMobileNumber] = useState('');
  const [email, setEmail] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('UNCLASSIFIED');
  const [suggestedCategory, setSuggestedCategory] = useState('UNCLASSIFIED');
  const [existingCategory, setExistingCategory] = useState(null);
  const [requirementNotes, setRequirementNotes] = useState('');
  const [leadSource, setLeadSource] = useState('Inbound Call');
  const [leadStatus, setLeadStatus] = useState('CONTACTED');
  const [assignedEmployeeId, setAssignedEmployeeId] = useState('');
  const [callNotes, setCallNotes] = useState('');

  // Follow-up Section Fields
  const [followupRequired, setFollowupRequired] = useState(false);
  const getTomorrowDate = () => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split('T')[0];
  };
  const [followupDate, setFollowupDate] = useState(getTomorrowDate());
  const [followupTime, setFollowupTime] = useState('10:00 AM');
  const [followupType, setFollowupType] = useState('Call');
  const [followupPriority, setFollowupPriority] = useState('MEDIUM');
  const [followupNotes, setFollowupNotes] = useState('');
  const [followupAssignedTo, setFollowupAssignedTo] = useState('');

  // Form State
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Fetch active employees once
  useEffect(() => {
    let isSubscribed = true;
    const fetchEmployees = async () => {
      try {
        const res = await API.get('/employees/?status_filter=ACTIVE');
        if (isSubscribed && Array.isArray(res.data)) {
          setEmployees(res.data);
        }
      } catch (err) {
        console.warn('Failed to load active employees for disposition modal:', err);
      }
    };
    fetchEmployees();
    return () => {
      isSubscribed = false;
    };
  }, []);

  // Initialize and populate call and lead data
  useEffect(() => {
    if (!isOpen || !callData) return;

    setSaveError('');
    setSaveSuccess(false);

    // 1. Extract call metadata
    const rawCallId = String(
      callData.uniqueid || callData.call_id || callData.provider_call_id || callData.id || ''
    ).trim();
    setCallId(rawCallId);

    // One-time form check: if already processed in this session, do not show
    if (rawCallId) {
      try {
        const handledKey = 'crm_call_lead_form_handled_' + rawCallId;
        if (sessionStorage.getItem(handledKey) === 'true') {
          if (onClose) onClose();
          return;
        }
      } catch (e) {}
    }

    const rawPhone = String(
      callData.phone_number || callData.customer_phone || callData.to_number || callData.from_number || ''
    ).trim();
    const cleanPhone = rawPhone.replace(/[^0-9]/g, '');
    setMobileNumber(rawPhone);

    const dir = String(callData.call_direction || callData.direction || 'INBOUND').toUpperCase();
    setCallDirection(dir);
    setLeadSource(dir === 'INBOUND' ? 'Inbound Call' : 'Outbound Call');

    const dur = Number(callData.duration || callData.duration_seconds || 0);
    setDurationSeconds(dur);

    const timeVal = callData.ended_at || callData.end_time || callData.started_at || callData.start_time || callData.created_at || new Date().toISOString();
    try {
      setCallDateTime(new Date(timeVal).toLocaleString('en-IN', {
        dateStyle: 'medium',
        timeStyle: 'short'
      }));
    } catch (e) {
      setCallDateTime(new Date().toLocaleString());
    }

    // Default assigned employee to current user if available
    const defaultEmpId = currentUser?.employee_id ? String(currentUser.employee_id) : '';
    setAssignedEmployeeId(defaultEmpId);
    setFollowupAssignedTo(defaultEmpId);

    // Initial notes
    const initialNotes = callData.notes || '';
    setCallNotes(initialNotes);

    // Reset follow-up
    setFollowupRequired(false);
    setFollowupDate(getTomorrowDate());
    setFollowupTime('10:00 AM');
    setFollowupType('Call');
    setFollowupPriority('MEDIUM');
    setFollowupNotes('');

    // Pre-populate or check existing lead
    const targetLeadId = callData.lead_id || callData.entity_id || null;
    if (targetLeadId) {
      setLeadId(targetLeadId);
      setIsExistingLead(true);
    } else {
      setLeadId(null);
      setIsExistingLead(false);
    }

    const defaultName = callData.lead_name || callData.name || '';
    setCustomerName(defaultName);

    // Look up customer phone in database
    if (cleanPhone && cleanPhone.length >= 6) {
      API.get(`/doocti/lead-by-number?number=${cleanPhone}&auto_create=false`)
        .then(res => {
          if (res.data?.success && res.data?.lead) {
            const ld = res.data.lead;
            setIsExistingLead(true);
            setLeadId(ld.id);
            if (ld.name) setCustomerName(ld.name);
            if (ld.email) setEmail(ld.email);
            if (ld.company) setCompanyName(ld.company);
            if (ld.requirement_notes) setRequirementNotes(ld.requirement_notes);
            if (ld.source) setLeadSource(ld.source);
            if (ld.status) setLeadStatus(ld.status);
            if (ld.assigned_to) {
              setAssignedEmployeeId(String(ld.assigned_to));
              setFollowupAssignedTo(String(ld.assigned_to));
            }

            const existingCat = ld.product_category || null;
            const isConfirmed = Boolean(ld.product_category_confirmed);
            const suggested = ld.suggested_product_category || ld.product_category || 'UNCLASSIFIED';

            setExistingCategory(existingCat);
            setSuggestedCategory(suggested);

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
            detectFromNotes(initialNotes);
          }
        })
        .catch(() => {
          detectFromNotes(initialNotes);
        });
    } else {
      detectFromNotes(initialNotes);
    }
  }, [isOpen, callData, currentUser]);

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

  // When Lead Status is changed to FOLLOW-UP, automatically enable follow-up section
  const handleStatusChange = (newStatus) => {
    setLeadStatus(newStatus);
    if (newStatus === 'FOLLOW-UP') {
      setFollowupRequired(true);
    }
  };

  // Explicit skip action (closes form and marks call as handled so it never reopens)
  const handleSkip = () => {
    if (callId) {
      try {
        sessionStorage.setItem('crm_call_lead_form_handled_' + callId, 'true');
      } catch (e) {}
    }
    if (onClose) onClose();
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaveError('');

    // Validations
    if (!customerName || !customerName.trim()) {
      setSaveError('Customer Name is required.');
      return;
    }

    const cleanPhone = String(mobileNumber || '').replace(/[^0-9]/g, '');
    if (!cleanPhone || cleanPhone.length < 8) {
      setSaveError('A valid Customer Mobile Number (at least 8-10 digits) is required.');
      return;
    }

    if (followupRequired && !followupDate) {
      setSaveError('Please select a valid Follow-up Date.');
      return;
    }

    setSaving(true);

    try {
      const payload = {
        lead_id: leadId ? Number(leadId) : null,
        call_id: callId || null,
        name: customerName.trim(),
        phone: mobileNumber.trim(),
        email: email.trim() || null,
        company: companyName.trim() || null,
        product_category: selectedCategory,
        requirement_notes: requirementNotes.trim() || null,
        source: leadSource,
        status: leadStatus,
        assigned_to: assignedEmployeeId ? Number(assignedEmployeeId) : null,
        call_notes: callNotes.trim() || null,
        call_direction: callDirection,
        call_duration: durationSeconds,
        agent_email: currentUser?.email || null,
        employee_id: currentUser?.employee_id || null,
        followup_required: Boolean(followupRequired),
        followup_date: followupRequired && followupDate ? followupDate : null,
        followup_time: followupRequired ? (followupTime || '10:00 AM') : null,
        followup_type: followupRequired ? followupType : 'Call',
        followup_notes: followupRequired ? followupNotes.trim() : null,
        followup_priority: followupPriority || 'MEDIUM',
        followup_assigned_to: followupRequired && followupAssignedTo ? Number(followupAssignedTo) : null
      };

      const res = await API.post('/doocti/lead/save-completion', payload);
      const savedLead = res.data?.lead || {};
      const savedLeadId = res.data?.lead_id || leadId || savedLead.id;

      // Mark this call ID as successfully handled in sessionStorage
      if (callId) {
        try {
          sessionStorage.setItem('crm_call_lead_form_handled_' + callId, 'true');
        } catch (e) {}
      }

      setSaveSuccess(true);

      // Trigger CRM events to refresh lead lists and follow-up reminders
      window.dispatchEvent(new Event('leadStatsUpdated'));
      window.dispatchEvent(new Event('followupReminderRefresh'));
      window.dispatchEvent(new CustomEvent('call-disposition-saved', {
        detail: {
          leadId: savedLeadId,
          product_category: selectedCategory,
          status: leadStatus,
          notes: callNotes,
          followup_date: followupRequired ? followupDate : null,
          followup_time: followupRequired ? followupTime : null
        }
      }));

      PingoPopupService.showNotification({
        title: isExistingLead ? 'Lead Updated' : 'Lead Created',
        message: followupRequired
          ? `Lead '${customerName}' saved with follow-up scheduled for ${followupDate}.`
          : `Lead '${customerName}' saved successfully.`,
        type: 'success'
      });

      setTimeout(() => {
        if (onSaved) onSaved({ leadId: savedLeadId, product_category: selectedCategory });
        if (onClose) onClose();
      }, 750);
    } catch (err) {
      console.error('Failed to save call lead details:', err);
      const msg = err.response?.data?.detail || err.response?.data?.message || err.message || 'Failed to save lead. Please check the details and try again.';
      setSaveError(typeof msg === 'string' ? msg : JSON.stringify(msg));
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
      backgroundColor: 'rgba(15, 23, 42, 0.65)',
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
        maxWidth: '720px',
        maxHeight: '90vh',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.28)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        animation: 'fadeIn 0.2s ease-out'
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '16px 22px',
          background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
          color: '#ffffff',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexShrink: 0
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              backgroundColor: 'rgba(255, 255, 255, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#38bdf8'
            }}>
              {callDirection === 'INBOUND' ? <PhoneIncoming size={20} /> : <PhoneOutgoing size={20} />}
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, letterSpacing: '-0.01em' }}>
                {isExistingLead ? 'Call Completed – Update Lead' : 'New Call Completed – Create Lead'}
              </h3>
              <p style={{ margin: 0, fontSize: '0.75rem', color: '#94a3b8' }}>
                Customer Details, Product Classification &amp; Follow-up Scheduling
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleSkip}
            title="Skip and dismiss form"
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
            <X size={20} />
          </button>
        </div>

        {/* Call Summary Banner */}
        <div style={{
          padding: '12px 22px',
          backgroundColor: '#f8fafc',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '10px',
          flexShrink: 0
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: '6px',
              backgroundColor: callDirection === 'INBOUND' ? '#dcfce7' : '#eff6ff',
              color: callDirection === 'INBOUND' ? '#15803d' : '#1d4ed8',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              {callDirection === 'INBOUND' ? <PhoneIncoming size={12} /> : <PhoneOutgoing size={12} />}
              {callDirection} CALL
            </span>
            <span style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: '6px',
              backgroundColor: '#f1f5f9',
              color: '#334155',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <Clock size={12} /> {formatDuration(durationSeconds)}
            </span>
            {callId && (
              <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                Call ID: <strong style={{ color: '#0f172a' }}>{callId.length > 18 ? callId.slice(0, 18) + '...' : callId}</strong>
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {callDateTime && (
              <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                {callDateTime}
              </span>
            )}
            {isExistingLead && leadId && (
              <span style={{
                fontSize: '0.72rem',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: '6px',
                backgroundColor: '#e0e7ff',
                color: '#4338ca'
              }}>
                Existing Lead #{leadId}
              </span>
            )}
          </div>
        </div>

        {/* Scrollable Form Body */}
        <form onSubmit={handleSave} style={{ overflowY: 'auto', padding: '18px 22px', flexGrow: 1 }}>
          {/* 1. Mandatory Product Classification */}
          <div style={{ marginBottom: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label style={{
                fontSize: '0.82rem',
                fontWeight: 800,
                color: '#0f172a',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                <Tag size={15} color="#2563eb" />
                Product Classification *
              </label>
              {existingCategory && (
                <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                  Current: <strong style={{ color: '#0f172a' }}>{existingCategory}</strong>
                </span>
              )}
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '8px',
              marginBottom: '6px'
            }}>
              {/* Option 1: BIOMETRIC */}
              <button
                type="button"
                onClick={() => setSelectedCategory('BIOMETRIC')}
                style={{
                  padding: '9px 8px',
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
                  padding: '9px 8px',
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
                  padding: '9px 8px',
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
                <span style={{ fontSize: '0.66rem', color: '#64748b', fontWeight: 500 }}>General / Ambiguous</span>
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
                gap: '6px',
                marginTop: '4px'
              }}>
                <span>💡 Auto-detected from notes/IVR: <strong>{suggestedCategory}</strong></span>
              </div>
            )}
          </div>

          {/* 2. Customer Details Section */}
          <div style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            padding: '14px 16px',
            marginBottom: '16px'
          }}>
            <h4 style={{
              margin: '0 0 12px 0',
              fontSize: '0.86rem',
              fontWeight: 800,
              color: '#1e293b',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <User size={16} color="#2563eb" />
              Customer Details
            </h4>

            {/* Row 1: Name & Phone */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Customer Name <span style={{ color: '#dc2626' }}>*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. John Doe / Business Contact"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '7px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '0.84rem',
                    color: '#0f172a',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Mobile Number <span style={{ color: '#dc2626' }}>*</span>
                </label>
                <input
                  type="tel"
                  required
                  placeholder="e.g. 9876543210"
                  value={mobileNumber}
                  onChange={(e) => setMobileNumber(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '7px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '0.84rem',
                    color: '#0f172a',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                />
              </div>
            </div>

            {/* Row 2: Email & Company */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Email Address
                </label>
                <input
                  type="email"
                  placeholder="e.g. customer@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '7px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '0.84rem',
                    color: '#0f172a',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Company Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Acme Solutions Pvt Ltd"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '7px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '0.84rem',
                    color: '#0f172a',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                />
              </div>
            </div>

            {/* Row 3: Source, Status & Assigned Employee */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Lead Source
                </label>
                <select
                  value={leadSource}
                  onChange={(e) => setLeadSource(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '7px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '0.84rem',
                    color: '#0f172a',
                    backgroundColor: '#ffffff',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                >
                  {SOURCE_OPTIONS.map(src => (
                    <option key={src} value={src}>{src}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Lead Status
                </label>
                <select
                  value={leadStatus}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '7px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '0.84rem',
                    color: '#0f172a',
                    backgroundColor: '#ffffff',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                >
                  {STATUS_OPTIONS.map(st => (
                    <option key={st} value={st}>{st}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Assigned Employee
                </label>
                <select
                  value={assignedEmployeeId}
                  onChange={(e) => {
                    setAssignedEmployeeId(e.target.value);
                    if (!followupAssignedTo) setFollowupAssignedTo(e.target.value);
                  }}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '7px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '0.84rem',
                    color: '#0f172a',
                    backgroundColor: '#ffffff',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                >
                  <option value="">-- Unassigned --</option>
                  {employees.map(emp => (
                    <option key={emp.id} value={emp.id}>
                      {emp.name} {emp.designation ? `(${emp.designation})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Row 4: Enquiry / Product Requirement */}
            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                Enquiry / Product Requirement
              </label>
              <textarea
                rows={2}
                placeholder="Specific customer requirements, model preferences, employee count, etc."
                value={requirementNotes}
                onChange={(e) => setRequirementNotes(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '7px',
                  border: '1.5px solid #cbd5e1',
                  fontSize: '0.84rem',
                  color: '#0f172a',
                  boxSizing: 'border-box',
                  outline: 'none',
                  resize: 'vertical'
                }}
              />
            </div>

            {/* Row 5: Call Discussion Notes */}
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                Call Discussion Notes
              </label>
              <textarea
                rows={2}
                placeholder="Key points discussed during this call..."
                value={callNotes}
                onChange={(e) => setCallNotes(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '7px',
                  border: '1.5px solid #cbd5e1',
                  fontSize: '0.84rem',
                  color: '#0f172a',
                  boxSizing: 'border-box',
                  outline: 'none',
                  resize: 'vertical'
                }}
              />
            </div>
          </div>

          {/* 3. Follow-up Integration Section (Optional with Toggle) */}
          <div style={{
            backgroundColor: followupRequired ? '#f8fafc' : '#ffffff',
            border: followupRequired ? '1.5px solid #93c5fd' : '1px solid #e2e8f0',
            borderRadius: '12px',
            padding: '14px 16px',
            marginBottom: '16px',
            transition: 'all 0.15s ease'
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: followupRequired ? '12px' : 0
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CalendarClock size={18} color="#2563eb" />
                <div>
                  <h4 style={{ margin: 0, fontSize: '0.86rem', fontWeight: 800, color: '#1e293b' }}>
                    Follow-up Scheduling
                  </h4>
                  <p style={{ margin: 0, fontSize: '0.72rem', color: '#64748b' }}>
                    Create a scheduled task in the Follow-ups module for the assigned agent
                  </p>
                </div>
              </div>

              {/* Yes / No Toggle Button Group */}
              <div style={{
                display: 'inline-flex',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                overflow: 'hidden'
              }}>
                <button
                  type="button"
                  onClick={() => setFollowupRequired(true)}
                  style={{
                    padding: '5px 14px',
                    fontSize: '0.78rem',
                    fontWeight: followupRequired ? 800 : 500,
                    backgroundColor: followupRequired ? '#2563eb' : '#ffffff',
                    color: followupRequired ? '#ffffff' : '#475569',
                    border: 'none',
                    cursor: 'pointer'
                  }}
                >
                  Yes
                </button>
                <button
                  type="button"
                  onClick={() => setFollowupRequired(false)}
                  style={{
                    padding: '5px 14px',
                    fontSize: '0.78rem',
                    fontWeight: !followupRequired ? 800 : 500,
                    backgroundColor: !followupRequired ? '#64748b' : '#ffffff',
                    color: !followupRequired ? '#ffffff' : '#475569',
                    border: 'none',
                    cursor: 'pointer'
                  }}
                >
                  No
                </button>
              </div>
            </div>

            {/* Follow-up Details (Expanded when followupRequired = true) */}
            {followupRequired && (
              <div style={{ marginTop: '12px', borderTop: '1px dashed #cbd5e1', paddingTop: '12px' }}>
                {/* Followup Date & Time */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                      Follow-up Date <span style={{ color: '#dc2626' }}>*</span>
                    </label>
                    <input
                      type="date"
                      required={followupRequired}
                      min={new Date().toISOString().split('T')[0]}
                      value={followupDate}
                      onChange={(e) => setFollowupDate(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: '7px',
                        border: '1.5px solid #cbd5e1',
                        fontSize: '0.84rem',
                        color: '#0f172a',
                        backgroundColor: '#ffffff',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                      Follow-up Time
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. 10:30 AM"
                      value={followupTime}
                      onChange={(e) => setFollowupTime(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: '7px',
                        border: '1.5px solid #cbd5e1',
                        fontSize: '0.84rem',
                        color: '#0f172a',
                        backgroundColor: '#ffffff',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                </div>

                {/* Followup Type & Assigned Employee */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                      Follow-up Type
                    </label>
                    <select
                      value={followupType}
                      onChange={(e) => setFollowupType(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: '7px',
                        border: '1.5px solid #cbd5e1',
                        fontSize: '0.84rem',
                        color: '#0f172a',
                        backgroundColor: '#ffffff',
                        boxSizing: 'border-box'
                      }}
                    >
                      {FOLLOWUP_TYPES.map(ft => (
                        <option key={ft} value={ft}>{ft}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                      Assign Follow-up To
                    </label>
                    <select
                      value={followupAssignedTo}
                      onChange={(e) => setFollowupAssignedTo(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: '7px',
                        border: '1.5px solid #cbd5e1',
                        fontSize: '0.84rem',
                        color: '#0f172a',
                        backgroundColor: '#ffffff',
                        boxSizing: 'border-box'
                      }}
                    >
                      <option value="">-- Same as Lead Owner --</option>
                      {employees.map(emp => (
                        <option key={emp.id} value={emp.id}>
                          {emp.name} {emp.designation ? `(${emp.designation})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Follow-up Notes */}
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Follow-up Notes / Agenda
                  </label>
                  <textarea
                    rows={2}
                    placeholder="Specific items to prepare or discuss during the follow-up..."
                    value={followupNotes}
                    onChange={(e) => setFollowupNotes(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 10px',
                      borderRadius: '7px',
                      border: '1.5px solid #cbd5e1',
                      fontSize: '0.84rem',
                      color: '#0f172a',
                      backgroundColor: '#ffffff',
                      boxSizing: 'border-box',
                      outline: 'none',
                      resize: 'vertical'
                    }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Feedback & Error Alerts */}
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
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
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
              <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
              <span>Lead and disposition saved successfully!</span>
            </div>
          )}

          {/* Action Buttons */}
          <div style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '10px',
            paddingTop: '6px'
          }}>
            <button
              type="button"
              onClick={handleSkip}
              disabled={saving}
              style={{
                padding: '9px 18px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                backgroundColor: '#ffffff',
                color: '#475569',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Skip
            </button>

            <button
              type="submit"
              disabled={saving}
              style={{
                padding: '9px 22px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: '#2563eb',
                color: '#ffffff',
                fontSize: '0.85rem',
                fontWeight: 700,
                cursor: saving ? 'not-allowed' : 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: '0 2px 8px rgba(37, 99, 235, 0.25)',
                opacity: saving ? 0.7 : 1
              }}
            >
              {saving ? <RefreshCw size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
              <span>{isExistingLead ? 'Update Lead Details' : 'Save Lead & Disposition'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CallCompletionDispositionModal;
