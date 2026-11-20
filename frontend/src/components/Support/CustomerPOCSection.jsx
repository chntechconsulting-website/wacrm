import React, { useCallback, useEffect, useRef, useState } from 'react';
import API from '../../services/api';
import {
  AlertCircle,
  BadgeCheck,
  Briefcase,
  Building2,
  Check,
  Loader2,
  Mail,
  MessageCircle,
  Pencil,
  Phone,
  Plus,
  RefreshCw,
  Star,
  UserRound,
  X,
} from 'lucide-react';
import {
  dialPoc,
  openPocEmail,
  pocMethodLabel,
  pocWhatsAppNumber,
} from '../../utils/pocActions';
import './CustomerPOCSection.css';

const EMPTY_FORM = {
  name: '',
  mobile: '',
  alternate_mobile: '',
  whatsapp_number: '',
  email: '',
  designation: '',
  department: '',
  preferred_contact_method: 'CALL',
  notes: '',
  is_primary: false,
};

const formFromPoc = (poc) => ({
  name: poc?.name || '',
  mobile: poc?.mobile || '',
  alternate_mobile: poc?.alternate_mobile || '',
  whatsapp_number: poc?.whatsapp_number || '',
  email: poc?.email || '',
  designation: poc?.designation || '',
  department: poc?.department || '',
  preferred_contact_method: poc?.preferred_contact_method || 'CALL',
  notes: poc?.notes || '',
  is_primary: Boolean(poc?.is_primary),
});

const initials = (name) => {
  const parts = String(name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);
  return parts.map((part) => part[0].toUpperCase()).join('') || 'P';
};

const displayValue = (value) => {
  const text = String(value || '').trim();
  return text || '';
};

const pocSignature = (poc) => [
  poc?.id,
  poc?.name,
  poc?.mobile,
  poc?.alternate_mobile,
  poc?.whatsapp_number,
  poc?.email,
  poc?.designation,
  poc?.department,
  poc?.preferred_contact_method,
  poc?.notes,
  poc?.is_primary ? 1 : 0,
  poc?.updated_at,
].join('|');

// Compare POC collections before updating state so identical API responses do
// not recreate the card elements and make the section flash.
const samePocCollection = (left, right) => {
  const current = Array.isArray(left) ? left : [];
  const next = Array.isArray(right) ? right : [];
  if (current.length !== next.length) return false;
  return current.every((poc, index) => pocSignature(poc) === pocSignature(next[index]));
};

const samePrimaryPoc = (left, right) => {
  if (left === right) return true;
  if (!left || !right) return false;
  return (
    (left.id || null) === (right.id || null) &&
    (left.name || '') === (right.name || '') &&
    (left.mobile || '') === (right.mobile || '')
  );
};

const POCForm = ({
  form,
  setForm,
  editing,
  saving,
  error,
  onCancel,
  onSubmit,
  hasPocs,
}) => {
  const update = (field, value) => setForm((prev) => ({ ...prev, [field]: value }));

  return (
    <form className="customer-poc-form" onSubmit={onSubmit}>
      <div className="customer-poc-form-head">
        <div>
          <strong>{editing ? 'Edit Point of Contact' : 'Add Point of Contact'}</strong>
          <span>
            Saved against this Support customer only. The customer&apos;s main contact
            number is never changed.
          </span>
        </div>
        <button
          type="button"
          className="customer-poc-icon-btn"
          onClick={onCancel}
          title="Close POC form"
        >
          <X size={16} />
        </button>
      </div>

      <div className="customer-poc-form-grid">
        <label>
          POC name <span className="required">*</span>
          <input
            type="text"
            value={form.name}
            onChange={(event) => update('name', event.target.value)}
            placeholder="Full name of the contact"
            maxLength={150}
            autoFocus
          />
        </label>
        <label>
          Mobile <span className="required">*</span>
          <input
            type="tel"
            value={form.mobile}
            onChange={(event) => update('mobile', event.target.value)}
            placeholder="10-digit mobile number"
            maxLength={20}
          />
        </label>
        <label>
          Alternate mobile
          <input
            type="tel"
            value={form.alternate_mobile}
            onChange={(event) => update('alternate_mobile', event.target.value)}
            placeholder="Optional alternate number"
            maxLength={20}
          />
        </label>
        <label>
          WhatsApp number
          <input
            type="tel"
            value={form.whatsapp_number}
            onChange={(event) => update('whatsapp_number', event.target.value)}
            placeholder="Defaults to the POC mobile when blank"
            maxLength={20}
          />
        </label>
        <label>
          Email
          <input
            type="email"
            value={form.email}
            onChange={(event) => update('email', event.target.value)}
            placeholder="name@company.com"
            maxLength={255}
          />
        </label>
        <label>
          Designation
          <input
            type="text"
            value={form.designation}
            onChange={(event) => update('designation', event.target.value)}
            placeholder="e.g. Plant Manager"
            maxLength={120}
          />
        </label>
        <label>
          Department
          <input
            type="text"
            value={form.department}
            onChange={(event) => update('department', event.target.value)}
            placeholder="e.g. Operations"
            maxLength={120}
          />
        </label>
        <label>
          Preferred contact method
          <select
            value={form.preferred_contact_method}
            onChange={(event) => update('preferred_contact_method', event.target.value)}
          >
            <option value="CALL">Call</option>
            <option value="WHATSAPP">WhatsApp</option>
            <option value="EMAIL">Email</option>
          </select>
        </label>
        <label className="full">
          Notes
          <textarea
            rows={2}
            value={form.notes}
            onChange={(event) => update('notes', event.target.value)}
            placeholder="Best time to call, language preference or other context"
          />
        </label>
        {(hasPocs || form.is_primary) && (
          <label className="customer-poc-primary-check">
            <input
              type="checkbox"
              checked={form.is_primary}
              onChange={(event) => update('is_primary', event.target.checked)}
            />
            <span>Set as primary POC for this customer</span>
          </label>
        )}
      </div>

      {error && (
        <div className="customer-poc-form-error">
          <AlertCircle size={14} /> {error}
        </div>
      )}

      <div className="customer-poc-form-actions">
        <button type="button" className="customer-poc-btn secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="customer-poc-btn primary" disabled={saving}>
          {saving ? <Loader2 size={14} className="spin-icon" /> : <Check size={14} />}
          {saving ? 'Saving...' : editing ? 'Update POC' : 'Add POC'}
        </button>
      </div>
    </form>
  );
};

export default function CustomerPOCSection({
  leadId,
  customerId = null,
  lead = null,
  canManage = true,
  onPocsChanged = null,
}) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [pocs, setPocs] = useState([]);
  const [primaryPoc, setPrimaryPoc] = useState(null);

  const [showForm, setShowForm] = useState(false);
  const [editingPocId, setEditingPocId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');
  const [busyPocId, setBusyPocId] = useState(null);

  const [waConfigured, setWaConfigured] = useState(false);
  const [waTarget, setWaTarget] = useState(null);
  const [waBody, setWaBody] = useState('');
  const [waSending, setWaSending] = useState(false);
  const [waError, setWaError] = useState('');

  const [toast, setToast] = useState('');
  const toastTimer = useRef(null);

  const showToast = useCallback((message) => {
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(''), 3500);
  }, []);

  useEffect(() => () => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
  }, []);

  // Keep the latest parent callback in a ref. The parent passes an inline
  // handler, so depending on it directly recreated fetchPocs on every parent
  // render and retriggered the load effect, which made the POC cards blink.
  const onPocsChangedRef = useRef(onPocsChanged);
  useEffect(() => {
    onPocsChangedRef.current = onPocsChanged;
  }, [onPocsChanged]);

  const lastCollectionRef = useRef({
    pocs: [],
    primaryPoc: null,
    initialized: false,
  });
  const requestIdRef = useRef(0);

  const applyCollection = useCallback(
    (payload, message) => {
      const items = Array.isArray(payload?.items)
        ? payload.items
        : Array.isArray(payload?.pocs)
          ? payload.pocs
          : [];
      const nextPrimary = payload?.primary_poc || null;
      const previous = lastCollectionRef.current;
      const collectionChanged =
        !samePocCollection(previous.pocs, items) ||
        !samePrimaryPoc(previous.primaryPoc, nextPrimary);

      // Reuse the existing array/object when nothing changed so React can skip
      // re-rendering the POC cards.
      setPocs((current) => (samePocCollection(current, items) ? current : items));
      setPrimaryPoc((current) => (samePrimaryPoc(current, nextPrimary) ? current : nextPrimary));

      if (message) showToast(message);

      if (
        (collectionChanged || !previous.initialized) &&
        onPocsChangedRef.current
      ) {
        lastCollectionRef.current = {
          pocs: items,
          primaryPoc: nextPrimary,
          initialized: true,
        };
        onPocsChangedRef.current({
          pocs: items,
          primary_poc: nextPrimary,
          poc_count: payload?.poc_count ?? items.length,
        });
      }
    },
    [showToast]
  );

  const fetchPocs = useCallback(async ({ silent = false } = {}) => {
    requestIdRef.current += 1;
    const requestId = requestIdRef.current;

    if (!leadId) {
      setPocs([]);
      setPrimaryPoc(null);
      setLoading(false);
      setRefreshing(false);
      return;
    }

    // A manual refresh keeps the current cards visible; only the initial load
    // for a customer shows the full loading state.
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError('');

    try {
      const params = customerId ? { customer_id: customerId } : {};
      const response = await API.get(`/support/customers/${leadId}/pocs`, { params });
      if (requestId !== requestIdRef.current) return;
      applyCollection(response.data);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setPocs([]);
      setPrimaryPoc(null);
      setError(err.response?.data?.detail || 'Customer POCs could not be loaded.');
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [leadId, customerId, applyCollection]);

  useEffect(() => {
    fetchPocs();
  }, [fetchPocs]);

  useEffect(() => {
    let active = true;
    API.get('/whatsapp/config-status')
      .then((response) => {
        if (active) setWaConfigured(Boolean(response.data?.configured));
      })
      .catch(() => {
        if (active) setWaConfigured(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const openAddForm = () => {
    setEditingPocId(null);
    setForm({ ...EMPTY_FORM, is_primary: pocs.length === 0 });
    setFormError('');
    setShowForm(true);
  };

  const openEditForm = (poc) => {
    setEditingPocId(poc.id);
    setForm(formFromPoc(poc));
    setFormError('');
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingPocId(null);
    setForm({ ...EMPTY_FORM });
    setFormError('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (saving) return;
    if (!form.name.trim()) {
      setFormError('POC name is required.');
      return;
    }
    if (!form.mobile.trim()) {
      setFormError('POC mobile number is required.');
      return;
    }

    setSaving(true);
    setFormError('');
    try {
      const payload = {
        name: form.name.trim(),
        mobile: form.mobile.trim(),
        alternate_mobile: form.alternate_mobile.trim() || null,
        whatsapp_number: form.whatsapp_number.trim() || null,
        email: form.email.trim() || null,
        designation: form.designation.trim() || null,
        department: form.department.trim() || null,
        preferred_contact_method: form.preferred_contact_method,
        notes: form.notes.trim() || null,
        is_primary: Boolean(form.is_primary),
      };
      const response = editingPocId
        ? await API.put(`/support/pocs/${editingPocId}`, payload)
        : await API.post(`/support/customers/${leadId}/pocs`, payload);

      applyCollection(
        response.data,
        editingPocId
          ? 'POC details updated.'
          : `${payload.name} added as a customer POC.`
      );
      closeForm();
    } catch (err) {
      setFormError(err.response?.data?.detail || 'The POC could not be saved.');
    } finally {
      setSaving(false);
    }
  };

  const handleSetPrimary = async (poc) => {
    if (!poc || poc.is_primary || busyPocId) return;
    setBusyPocId(poc.id);
    try {
      const response = await API.put(`/support/pocs/${poc.id}/primary`);
      applyCollection(response.data, `${poc.name} is now the primary POC.`);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Primary POC could not be changed.');
    } finally {
      setBusyPocId(null);
    }
  };

  const openWhatsAppComposer = (poc) => {
    if (!waConfigured) {
      showToast('WhatsApp integration is not configured. Configure it in Settings first.');
      return;
    }
    setWaTarget(poc);
    setWaBody(`Hello ${poc.name}, `);
    setWaError('');
  };

  const closeWhatsAppComposer = () => {
    setWaTarget(null);
    setWaBody('');
    setWaError('');
  };

  const sendWhatsApp = async (event) => {
    event.preventDefault();
    if (!waTarget || waSending) return;
    if (!waBody.trim()) {
      setWaError('Enter a message to send.');
      return;
    }
    setWaSending(true);
    setWaError('');
    try {
      const response = await API.post('/whatsapp/send-message', {
        phone: pocWhatsAppNumber(waTarget),
        lead_id: leadId,
        message_type: 'TEXT',
        body: waBody.trim(),
      });
      if (response.data?.success === false) {
        setWaError(response.data?.error || 'WhatsApp message could not be sent.');
        return;
      }
      showToast(`WhatsApp message sent to ${waTarget.name}.`);
      closeWhatsAppComposer();
    } catch (err) {
      setWaError(
        err.response?.data?.detail || 'WhatsApp message could not be sent.'
      );
    } finally {
      setWaSending(false);
    }
  };

  const callPoc = (poc) => {
    const started = dialPoc(leadId, lead, poc);
    if (!started) showToast('This POC has no mobile number to call.');
  };

  if (!leadId) return null;

  return (
    <section className="customer-poc-section">
      {toast && <div className="customer-poc-toast">{toast}</div>}

      <div className="customer-poc-header">
        <div className="customer-poc-header-title">
          <span className="customer-poc-header-icon">
            <UserRound size={16} />
          </span>
          <div>
            <h4>
              Customer POC Details
              <span className="customer-poc-count">
                {pocs.length} {pocs.length === 1 ? 'contact' : 'contacts'}
              </span>
            </h4>
            <p>
              Customer points of contact for Support calls, WhatsApp and email.
              The company main contact number is never overwritten.
            </p>
          </div>
        </div>
        <div className="customer-poc-header-actions">
          <button
            type="button"
            className="customer-poc-icon-btn"
            onClick={() => fetchPocs({ silent: true })}
            title="Refresh customer POCs"
            disabled={loading || refreshing}
          >
            <RefreshCw size={14} className={loading || refreshing ? 'spin-icon' : ''} />
          </button>
          {canManage && !showForm && (
            <button type="button" className="customer-poc-btn primary" onClick={openAddForm}>
              <Plus size={14} /> Add POC
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="customer-poc-state">
          <Loader2 size={18} className="spin-icon" />
          <span>Loading customer POCs...</span>
        </div>
      ) : error ? (
        <div className="customer-poc-state error">
          <AlertCircle size={18} />
          <span>{error}</span>
          <button type="button" className="customer-poc-btn secondary" onClick={() => fetchPocs()}>
            Retry
          </button>
        </div>
      ) : pocs.length === 0 && !showForm ? (
        <div className="customer-poc-state empty">
          <UserRound size={20} />
          <div>
            <strong>No POC recorded yet</strong>
            <span>
              Add the person Support should contact for this customer. Calls placed
              from a POC use the POC number and stay linked to this customer.
            </span>
          </div>
        </div>
      ) : (
        <div className="customer-poc-list">
          {pocs.map((poc) => (
            <article
              key={poc.id}
              className={`customer-poc-card ${poc.is_primary ? 'primary' : ''}`}
            >
              <div className="customer-poc-card-head">
                <div className="customer-poc-avatar">{initials(poc.name)}</div>
                <div className="customer-poc-identity">
                  <div className="customer-poc-name-row">
                    <strong>{poc.name}</strong>
                    {poc.is_primary && (
                      <span className="customer-poc-primary-badge">
                        <Star size={11} /> Primary
                      </span>
                    )}
                    <span className={`customer-poc-method ${String(poc.preferred_contact_method || 'CALL').toLowerCase()}`}>
                      Prefers {pocMethodLabel(poc.preferred_contact_method)}
                    </span>
                  </div>
                  <div className="customer-poc-meta">
                    {poc.designation && (
                      <span>
                        <Briefcase size={12} /> {poc.designation}
                      </span>
                    )}
                    {poc.department && (
                      <span>
                        <Building2 size={12} /> {poc.department}
                      </span>
                    )}
                    {poc.updated_at && (
                      <span className="customer-poc-updated">
                        Updated {new Date(poc.updated_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="customer-poc-contact-grid">
                <div className="customer-poc-contact-item">
                  <span>Mobile</span>
                  <span>
                    <Phone size={12} /> {displayValue(poc.mobile) || '—'}
                  </span>
                </div>
                <div className="customer-poc-contact-item">
                  <span>Alternate</span>
                  <span>{displayValue(poc.alternate_mobile) || '—'}</span>
                </div>
                <div className="customer-poc-contact-item">
                  <span>WhatsApp</span>
                  <span>{displayValue(poc.whatsapp_number || poc.mobile) || '—'}</span>
                </div>
                <div className="customer-poc-contact-item">
                  <span>Email</span>
                  <span>{displayValue(poc.email) || '—'}</span>
                </div>
              </div>

              {poc.notes && <p className="customer-poc-notes">{poc.notes}</p>}

              <div className="customer-poc-card-actions">
                <button type="button" className="customer-poc-btn call" onClick={() => callPoc(poc)}>
                  <Phone size={13} /> Call
                </button>
                <button
                  type="button"
                  className={`customer-poc-btn whatsapp ${!waConfigured ? 'disabled' : ''}`}
                  onClick={() => openWhatsAppComposer(poc)}
                  title={
                    waConfigured
                      ? `Send a WhatsApp message to ${poc.name}`
                      : 'WhatsApp integration is not configured'
                  }
                >
                  <MessageCircle size={13} /> WhatsApp
                </button>
                <button
                  type="button"
                  className={`customer-poc-btn email ${!poc.email ? 'disabled' : ''}`}
                  onClick={() => {
                    if (!openPocEmail(poc)) showToast('This POC has no email address.');
                  }}
                  title={poc.email ? `Email ${poc.name}` : 'No email address saved'}
                >
                  <Mail size={13} /> Email
                </button>
                <span className="customer-poc-actions-spacer" />
                {canManage && !poc.is_primary && (
                  <button
                    type="button"
                    className="customer-poc-btn secondary"
                    onClick={() => handleSetPrimary(poc)}
                    disabled={busyPocId === poc.id}
                  >
                    {busyPocId === poc.id ? (
                      <Loader2 size={13} className="spin-icon" />
                    ) : (
                      <BadgeCheck size={13} />
                    )}
                    Set primary
                  </button>
                )}
                {canManage && (
                  <button
                    type="button"
                    className="customer-poc-btn secondary"
                    onClick={() => openEditForm(poc)}
                  >
                    <Pencil size={13} /> Edit
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {canManage && showForm && (
        <POCForm
          form={form}
          setForm={setForm}
          editing={Boolean(editingPocId)}
          saving={saving}
          error={formError}
          onCancel={closeForm}
          onSubmit={handleSubmit}
          hasPocs={pocs.length > 0}
        />
      )}

      {waTarget && (
        <div className="customer-poc-modal-backdrop" onClick={closeWhatsAppComposer}>
          <form
            className="customer-poc-modal"
            onClick={(event) => event.stopPropagation()}
            onSubmit={sendWhatsApp}
          >
            <div className="customer-poc-modal-head">
              <strong>
                <MessageCircle size={15} /> WhatsApp {waTarget.name}
              </strong>
              <button
                type="button"
                className="customer-poc-icon-btn"
                onClick={closeWhatsAppComposer}
                title="Close"
              >
                <X size={15} />
              </button>
            </div>
            <p className="customer-poc-modal-phone">
              Sending to {pocWhatsAppNumber(waTarget)} · linked to customer #{leadId}
            </p>
            <textarea
              rows={5}
              value={waBody}
              onChange={(event) => setWaBody(event.target.value)}
              placeholder="Type the WhatsApp message..."
              autoFocus
            />
            {waError && (
              <div className="customer-poc-form-error">
                <AlertCircle size={14} /> {waError}
              </div>
            )}
            <div className="customer-poc-modal-actions">
              <button type="button" className="customer-poc-btn secondary" onClick={closeWhatsAppComposer}>
                Cancel
              </button>
              <button type="submit" className="customer-poc-btn whatsapp-solid" disabled={waSending}>
                {waSending ? <Loader2 size={14} className="spin-icon" /> : <MessageCircle size={14} />}
                {waSending ? 'Sending...' : 'Send message'}
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}

export const CustomerPOCSummaryList = ({
  pocs = [],
  matchedPocId = null,
  emptyLabel = 'No POC recorded for this customer.',
}) => {
  if (!pocs.length) {
    return <p className="customer-poc-summary-empty">{emptyLabel}</p>;
  }
  return (
    <div className="customer-poc-summary-list">
      {pocs.map((poc) => (
        <div
          key={poc.id}
          className={`customer-poc-summary-row ${poc.is_primary ? 'primary' : ''} ${
            matchedPocId && poc.id === matchedPocId ? 'matched' : ''
          }`}
        >
          <div>
            <strong>
              {poc.name}
              {poc.is_primary && <span className="customer-poc-summary-tag">Primary</span>}
              {matchedPocId && poc.id === matchedPocId && (
                <span className="customer-poc-summary-tag matched-tag">This caller</span>
              )}
            </strong>
            <span>
              {poc.designation ? `${poc.designation} · ` : ''}
              {poc.mobile}
              {poc.email ? ` · ${poc.email}` : ''}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
};
