import React, { useCallback, useEffect, useRef, useState } from 'react';
import API from '../../services/api';
import { formatDateDDMMYYYY, formatLeadReceivedFull } from '../../utils/dateUtils';
import CustomerPurchaseDetails from './CustomerPurchaseDetails';
import {
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  Clock,
  FilePlus2,
  History,
  Loader2,
  MessageSquare,
  Paperclip,
  RefreshCw,
  ShieldCheck,
  UserCheck,
} from 'lucide-react';
import './SupportHistory.css';

const EMPTY_FORM = {
  interaction_type: 'MANUAL',
  interaction_at: '',
  discussion: '',
  problem_reported: '',
  troubleshooting: '',
  solution_provided: '',
  pending_issues: '',
  customer_commitments: '',
  next_action: '',
  follow_up_at: '',
  notes: '',
};

const toLocalInputValue = (value) => {
  if (!value) return '';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (part) => String(part).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const formatDateTime = (value) => {
  if (!value) return '—';
  const formatted = formatLeadReceivedFull(value);
  return formatted === '-' ? String(value) : formatted;
};

const SummaryRow = ({ label, value, tone }) => (
  <div className={`support-history-summary-row ${tone || ''}`}>
    <span className="support-history-summary-label">{label}</span>
    <span className="support-history-summary-value">{value || '—'}</span>
  </div>
);

const InteractionCard = ({ interaction }) => (
  <article className="support-interaction-card">
    <div className="support-interaction-head">
      <div className="support-interaction-head-main">
        <span className={`support-interaction-type ${(interaction.interaction_type || 'MANUAL').toLowerCase()}`}>
          {interaction.interaction_type || 'MANUAL'}
        </span>
        <span className="support-interaction-time">
          <Clock size={13} /> {formatDateTime(interaction.interaction_at)}
        </span>
      </div>
      <span className="support-interaction-employee">
        <UserCheck size={13} /> {interaction.handling_employee_name || 'Support employee'}
      </span>
    </div>

    <div className="support-interaction-grid">
      {interaction.discussion && (
        <div className="support-interaction-field">
          <span>Discussion</span>
          <p>{interaction.discussion}</p>
        </div>
      )}
      {interaction.problem_reported && (
        <div className="support-interaction-field problem">
          <span>Problem reported</span>
          <p>{interaction.problem_reported}</p>
        </div>
      )}
      {interaction.troubleshooting && (
        <div className="support-interaction-field">
          <span>Troubleshooting</span>
          <p>{interaction.troubleshooting}</p>
        </div>
      )}
      {interaction.solution_provided && (
        <div className="support-interaction-field solution">
          <span>Solution provided</span>
          <p>{interaction.solution_provided}</p>
        </div>
      )}
      {interaction.pending_issues && (
        <div className="support-interaction-field pending">
          <span>Pending issues</span>
          <p>{interaction.pending_issues}</p>
        </div>
      )}
      {interaction.customer_commitments && (
        <div className="support-interaction-field">
          <span>Customer commitments</span>
          <p>{interaction.customer_commitments}</p>
        </div>
      )}
      {interaction.next_action && (
        <div className="support-interaction-field action">
          <span>Next action</span>
          <p>{interaction.next_action}</p>
        </div>
      )}
      {interaction.notes && (
        <div className="support-interaction-field">
          <span>Notes</span>
          <p>{interaction.notes}</p>
        </div>
      )}
    </div>

    <div className="support-interaction-foot">
      {interaction.follow_up_at && (
        <span className="support-interaction-followup">
          <CalendarClock size={13} /> Follow-up {formatDateTime(interaction.follow_up_at)}
        </span>
      )}
      {interaction.original_employee_name && (
        <span className="support-interaction-owner">
          <ShieldCheck size={13} /> Permanent owner: {interaction.original_employee_name}
        </span>
      )}
      {(interaction.attachments || []).length > 0 && (
        <span className="support-interaction-attachments">
          <Paperclip size={13} />
          {interaction.attachments.map((attachment, index) => (
            <a
              key={`${attachment.url}-${index}`}
              href={attachment.url}
              target="_blank"
              rel="noreferrer"
            >
              {attachment.name || `Attachment ${index + 1}`}
            </a>
          ))}
        </span>
      )}
    </div>
  </article>
);

export default function SupportInteractionTimeline({
  leadId,
  customerId,
  canAdd = true,
  onChanged,
  showPurchase = true,
}) {
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM, interaction_at: toLocalInputValue(new Date()) });
  const [files, setFiles] = useState([]);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');
  const toastTimeout = useRef(null);

  const showToast = useCallback((message) => {
    setToast(message);
    if (toastTimeout.current) clearTimeout(toastTimeout.current);
    toastTimeout.current = setTimeout(() => setToast(''), 3500);
  }, []);

  const fetchHistory = useCallback(async () => {
    if (!leadId) return;
    setLoading(true);
    setError('');
    try {
      const params = customerId ? { customer_id: customerId } : {};
      const response = await API.get(`/support/customers/${leadId}/history`, { params });
      setHistory(response.data || null);
    } catch (err) {
      setHistory(null);
      setError(err.response?.data?.detail || 'Support history could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [leadId, customerId]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  useEffect(() => () => {
    if (toastTimeout.current) clearTimeout(toastTimeout.current);
  }, []);

  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!leadId || saving) return;
    const hasContent = [
      'discussion',
      'problem_reported',
      'troubleshooting',
      'solution_provided',
      'pending_issues',
      'customer_commitments',
      'next_action',
      'notes',
    ].some((field) => String(form[field] || '').trim());
    if (!hasContent) {
      showToast('Enter at least one interaction detail, problem, note or action.');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        ...form,
        customer_id: customerId || undefined,
        interaction_at: form.interaction_at ? new Date(form.interaction_at).toISOString() : null,
        follow_up_at: form.follow_up_at ? new Date(form.follow_up_at).toISOString() : null,
        client_reference: `ui-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
      };
      const response = await API.post(`/support/customers/${leadId}/interactions`, payload);
      const interaction = response.data?.interaction;

      if (interaction?.id && files.length > 0) {
        for (const file of files) {
          const data = new FormData();
          data.append('file', file);
          try {
            await API.post(`/support/interactions/${interaction.id}/attachments`, data, {
              headers: { 'Content-Type': 'multipart/form-data' },
            });
          } catch (uploadError) {
            showToast(
              uploadError.response?.data?.detail ||
                `Interaction saved, but ${file.name} could not be uploaded.`
            );
          }
        }
      }

      setForm({ ...EMPTY_FORM, interaction_at: toLocalInputValue(new Date()) });
      setFiles([]);
      setShowForm(false);
      showToast(response.data?.duplicate ? 'This interaction was already saved.' : 'Support interaction recorded.');
      await fetchHistory();
      if (onChanged) onChanged();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to save the Support interaction.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="support-history-state">
        <Loader2 size={22} className="spin-icon" />
        <p>Loading Support history...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="support-history-state error">
        <AlertCircle size={22} />
        <p>{error}</p>
        <button type="button" className="support-history-secondary-btn" onClick={fetchHistory}>
          <RefreshCw size={14} /> Retry
        </button>
      </div>
    );
  }

  if (!history) {
    return (
      <div className="support-history-state">
        <History size={22} />
        <p>No Support history is available for this customer.</p>
      </div>
    );
  }

  const summary = history.summary || {};
  const interactions = history.interactions || [];

  return (
    <div className="support-history">
      {toast && <div className="support-history-toast">{toast}</div>}

      <div className="support-history-profile">
        <div>
          <div className="support-history-name">{history.customer_name || 'Support customer'}</div>
          <div className="support-history-company">
            {history.company_name || 'Individual customer'}
            {history.phone ? ` • ${history.phone}` : ''}
          </div>
        </div>
        <div className="support-history-assignment">
          <span>
            <ShieldCheck size={13} /> Permanent owner:{' '}
            <strong>{history.original_support_employee_name || 'Unassigned'}</strong>
          </span>
          <span>
            <UserCheck size={13} /> Current handler:{' '}
            <strong>{history.current_handling_employee_name || 'Unassigned'}</strong>
          </span>
        </div>
      </div>

      <div className="support-history-summary">
        <SummaryRow label="Latest conversation" value={summary.last_conversation_summary} />
        <SummaryRow label="Last reported problem" value={summary.last_reported_problem} tone="problem" />
        <SummaryRow label="Current unresolved issue" value={summary.current_unresolved_issue} tone="pending" />
        <SummaryRow
          label="Pending follow-up"
          value={
            summary.pending_follow_up
              ? `${formatDateTime(summary.pending_follow_up.follow_up_at)}${
                  summary.pending_follow_up.is_overdue ? ' • OVERDUE' : ''
                }${summary.pending_follow_up.next_action ? ` • ${summary.pending_follow_up.next_action}` : ''}`
              : ''
          }
          tone={summary.pending_follow_up?.is_overdue ? 'pending' : ''}
        />
        <SummaryRow label="Next recommended action" value={summary.next_recommended_action} tone="action" />
        <span className="support-history-generated">
          Deterministic summary from saved interactions • {summary.interaction_count || 0} record(s) • no AI provider used
        </span>
      </div>

      {(history.overdue_follow_ups || []).length > 0 && (
        <div className="support-history-alert">
          <AlertCircle size={15} />
          {(history.overdue_follow_ups || []).length} overdue Support follow-up(s) need attention.
        </div>
      )}

      {((history.upcoming_follow_ups || []).length > 0 ||
        (history.scheduled_followups || []).length > 0) && (
        <div className="support-history-upcoming">
          <h4>
            <CalendarClock size={15} /> Upcoming Support follow-ups
          </h4>
          <div className="support-history-upcoming-list">
            {(history.upcoming_follow_ups || []).slice(0, 8).map((followUp) => (
              <div key={`interaction-${followUp.id}`} className="support-history-upcoming-row">
                <span>{formatDateTime(followUp.follow_up_at)}</span>
                <p>{followUp.next_action || followUp.pending_issues || 'Support follow-up recorded.'}</p>
              </div>
            ))}
            {(history.scheduled_followups || []).slice(0, 8).map((followUp) => (
              <div key={`scheduled-${followUp.id}`} className="support-history-upcoming-row">
                <span>
                  {formatDateDDMMYYYY(followUp.followup_date)}
                  {followUp.followup_time ? ` • ${followUp.followup_time}` : ''}
                </span>
                <p>{followUp.notes || 'Scheduled Support follow-up.'}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="support-history-toolbar">
        <h4>
          <History size={16} /> Append-only interaction timeline ({interactions.length})
        </h4>
        {canAdd && (
          <button
            type="button"
            className="support-history-primary-btn"
            onClick={() => setShowForm((value) => !value)}
          >
            <FilePlus2 size={15} /> {showForm ? 'Close form' : 'Add interaction'}
          </button>
        )}
      </div>

      {canAdd && showForm && (
        <form className="support-interaction-form" onSubmit={handleSubmit}>
          <div className="support-interaction-form-grid">
            <label>
              Interaction type
              <select
                value={form.interaction_type}
                onChange={(event) => updateField('interaction_type', event.target.value)}
              >
                <option value="MANUAL">Manual</option>
                <option value="INBOUND">Inbound</option>
                <option value="OUTBOUND">Outbound</option>
              </select>
            </label>
            <label>
              Interaction date &amp; time
              <input
                type="datetime-local"
                value={form.interaction_at}
                onChange={(event) => updateField('interaction_at', event.target.value)}
              />
            </label>
            <label>
              Follow-up date &amp; time
              <input
                type="datetime-local"
                value={form.follow_up_at}
                onChange={(event) => updateField('follow_up_at', event.target.value)}
              />
            </label>
            <label className="full">
              Discussion
              <textarea
                rows={2}
                value={form.discussion}
                onChange={(event) => updateField('discussion', event.target.value)}
                placeholder="What was discussed with the customer?"
              />
            </label>
            <label>
              Problem reported
              <textarea
                rows={2}
                value={form.problem_reported}
                onChange={(event) => updateField('problem_reported', event.target.value)}
              />
            </label>
            <label>
              Troubleshooting
              <textarea
                rows={2}
                value={form.troubleshooting}
                onChange={(event) => updateField('troubleshooting', event.target.value)}
              />
            </label>
            <label>
              Solution provided
              <textarea
                rows={2}
                value={form.solution_provided}
                onChange={(event) => updateField('solution_provided', event.target.value)}
              />
            </label>
            <label>
              Pending issues
              <textarea
                rows={2}
                value={form.pending_issues}
                onChange={(event) => updateField('pending_issues', event.target.value)}
              />
            </label>
            <label>
              Customer commitments
              <textarea
                rows={2}
                value={form.customer_commitments}
                onChange={(event) => updateField('customer_commitments', event.target.value)}
              />
            </label>
            <label>
              Next action
              <textarea
                rows={2}
                value={form.next_action}
                onChange={(event) => updateField('next_action', event.target.value)}
              />
            </label>
            <label className="full">
              Notes
              <textarea
                rows={2}
                value={form.notes}
                onChange={(event) => updateField('notes', event.target.value)}
              />
            </label>
            <label className="full">
              Attachments (optional, max 10 MB per file)
              <input
                type="file"
                multiple
                onChange={(event) => setFiles(Array.from(event.target.files || []))}
              />
            </label>
          </div>
          <div className="support-interaction-form-actions">
            <span>
              <CheckCircle2 size={14} /> Saved interactions cannot be edited or deleted.
            </span>
            <button type="submit" className="support-history-primary-btn" disabled={saving}>
              {saving ? <Loader2 size={15} className="spin-icon" /> : <MessageSquare size={15} />}
              {saving ? 'Saving...' : 'Save interaction'}
            </button>
          </div>
        </form>
      )}

      {interactions.length === 0 ? (
        <div className="support-history-state">
          <MessageSquare size={22} />
          <p>No Support interactions have been recorded yet.</p>
        </div>
      ) : (
        <div className="support-interaction-list">
          {[...interactions].reverse().map((interaction) => (
            <InteractionCard key={interaction.id} interaction={interaction} />
          ))}
        </div>
      )}

      {showPurchase && history.purchase_details && (
        <div className="support-history-purchase">
          <h4>Purchased package, plan and add-ons</h4>
          <CustomerPurchaseDetails
            purchaseDetails={history.purchase_details}
            leadId={leadId}
            customerId={history.customer_id}
          />
        </div>
      )}
    </div>
  );
}
