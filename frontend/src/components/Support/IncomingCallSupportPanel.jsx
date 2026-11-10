import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import API from '../../services/api';
import { formatLeadReceivedFull } from '../../utils/dateUtils';
import {
  AlertCircle,
  ArrowUpRight,
  CalendarClock,
  Loader2,
  MessageSquare,
  ShieldCheck,
  UserCheck,
} from 'lucide-react';
import './IncomingCallSupportPanel.css';

const formatDateTime = (value) => {
  if (!value) return '—';
  const formatted = formatLeadReceivedFull(value);
  return formatted === '-' ? String(value) : formatted;
};

const isSupportUser = (user) => {
  const role = String(user?.role || '').toUpperCase();
  const department = String(user?.department || '').toUpperCase();
  return role === 'ADMIN' || role === 'SUPPORT_MANAGER' || role === 'SUPPORT_EXECUTIVE' || department === 'SUPPORT';
};

export default function IncomingCallSupportPanel({ incomingAlert }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const phone = incomingAlert?.customer_phone || incomingAlert?.from_number || '';
  const allowed = isSupportUser(user);

  useEffect(() => {
    if (!allowed || !phone) {
      setContext(null);
      setError('');
      return undefined;
    }
    let active = true;
    setLoading(true);
    setError('');
    API.get('/support/incoming-call-context', { params: { phone } })
      .then((response) => {
        if (active) setContext(response.data || null);
      })
      .catch((err) => {
        if (active) {
          setContext(null);
          setError(err.response?.data?.detail || 'Support context could not be loaded.');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [allowed, phone]);

  if (!allowed || (!loading && !context && !error)) return null;

  if (loading) {
    return (
      <div className="incoming-support-panel">
        <Loader2 size={15} className="spin-icon" />
        <span>Looking up authorized Support history...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="incoming-support-panel muted">
        <ShieldCheck size={15} />
        <span>{error}</span>
      </div>
    );
  }

  if (!context?.found) {
    return (
      <div className="incoming-support-panel muted">
        <MessageSquare size={15} />
        <span>No CRM customer is linked to this number.</span>
      </div>
    );
  }

  if (!context.authorized) {
    return (
      <div className="incoming-support-panel muted">
        <ShieldCheck size={15} />
        <span>{context.message || 'This customer is outside your authorized Support scope.'}</span>
      </div>
    );
  }

  const assignment = context.assignment || {};
  const summary = context.summary || {};

  return (
    <div className="incoming-support-panel">
      <div className="incoming-support-head">
        <strong>{context.customer?.customer_name || 'Support customer'}</strong>
        <span>{context.customer?.company_name || context.customer?.phone || ''}</span>
      </div>

      <div className="incoming-support-owner">
        <span>
          <ShieldCheck size={12} /> Owner: <strong>{assignment.original_support_employee_name || 'Unassigned'}</strong>
        </span>
        <span>
          <UserCheck size={12} /> Handling: <strong>{assignment.current_handling_employee_name || 'Unassigned'}</strong>
        </span>
        {assignment.backup_employee_name && (
          <span className="backup">Backup coverage: {assignment.backup_employee_name}</span>
        )}
      </div>

      <div className="incoming-support-row">
        <span>Last conversation</span>
        <p>{context.last_conversation_summary || summary.last_conversation_summary || 'No Support interaction recorded.'}</p>
      </div>
      {context.unresolved_issue && (
        <div className="incoming-support-row danger">
          <span>Unresolved issue</span>
          <p>{context.unresolved_issue}</p>
        </div>
      )}
      {context.pending_follow_up && (
        <div className="incoming-support-row pending">
          <span>
            <CalendarClock size={12} /> Pending follow-up
          </span>
          <p>
            {formatDateTime(context.pending_follow_up.follow_up_at)}
            {context.pending_follow_up.is_overdue ? ' • OVERDUE' : ''}
            {context.pending_follow_up.next_action ? ` • ${context.pending_follow_up.next_action}` : ''}
          </p>
        </div>
      )}
      <div className="incoming-support-footer">
        <span>{context.interaction_count || 0} Support interaction(s)</span>
        <button type="button" onClick={() => navigate('/support/assigned-leads')}>
          Open Support history <ArrowUpRight size={12} />
        </button>
      </div>
      <div className="incoming-support-note">
        <AlertCircle size={11} />
        Display-only CRM lookup. DooCTI remains authoritative for answer, connect and hangup events.
      </div>
    </div>
  );
}
