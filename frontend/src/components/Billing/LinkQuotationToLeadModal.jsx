import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  ArrowLeft,
  Building2,
  CheckCircle2,
  Link2,
  Loader2,
  Mail,
  Phone,
  Search,
  X,
} from 'lucide-react';
import API from '../../services/api';
import './LinkQuotationToLeadModal.css';

const cleanDocId = (document) =>
  String(document?.rawId ?? document?.id ?? '')
    .replace('local_', '')
    .trim();

const leadName = (lead) => lead?.name || 'Unnamed Lead';

const formatAmount = (value) => {
  const amount = Number(value || 0);
  if (!Number.isFinite(amount)) return '₹0';
  return `₹${amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
};

const LeadAvatar = ({ name }) => (
  <span className="link-lead-avatar" aria-hidden="true">
    {(name || '?').trim().charAt(0).toUpperCase() || '?'}
  </span>
);

const LeadDetails = ({ lead, compact = false }) => (
  <div className={`link-lead-details${compact ? ' link-lead-details--compact' : ''}`}>
    {lead?.company && (
      <div className="link-lead-detail">
        <Building2 size={13} />
        <span>{lead.company}</span>
      </div>
    )}
    {lead?.phone && (
      <div className="link-lead-detail">
        <Phone size={13} />
        <span>{lead.phone}</span>
      </div>
    )}
    {lead?.email && (
      <div className="link-lead-detail">
        <Mail size={13} />
        <span>{lead.email}</span>
      </div>
    )}
  </div>
);

const LinkQuotationToLeadModal = ({ document, onClose, onLinked }) => {
  const docId = cleanDocId(document);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [matches, setMatches] = useState([]);
  const [linkedLead, setLinkedLead] = useState(null);
  const [suggestedLeadId, setSuggestedLeadId] = useState(null);
  const [selectedLeadId, setSelectedLeadId] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const requestSeq = useRef(0);
  const searchRef = useRef(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), 350);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let active = true;
    const sequence = ++requestSeq.current;

    const loadMatches = async () => {
      if (!docId) {
        setLoading(false);
        setError('This document cannot be linked because its id is missing.');
        return;
      }
      setLoading(true);
      setError('');
      try {
        const res = await API.get(
          `/integrations/waquote/documents/${docId}/lead-matches`,
          { params: debouncedSearch ? { search: debouncedSearch } : {} }
        );
        if (!active || sequence !== requestSeq.current) return;
        const payload = res.data || {};
        const nextMatches = Array.isArray(payload.suggestions) ? payload.suggestions : [];
        setMatches(nextMatches);
        setLinkedLead(payload.linkedLead || null);
        setSuggestedLeadId(payload.suggestedLeadId || null);
        setSelectedLeadId((previous) => {
          if (previous && nextMatches.some((item) => item.lead?.id === previous)) {
            return previous;
          }
          // A single exact suggestion may be preselected, but linking always
          // requires the explicit confirmation step below.
          return payload.suggestedLeadId || null;
        });
      } catch (err) {
        if (!active || sequence !== requestSeq.current) return;
        setMatches([]);
        setLinkedLead(null);
        setSuggestedLeadId(null);
        setError(
          err.response?.data?.detail ||
            'Could not load lead suggestions. Please try again.'
        );
      } finally {
        if (active && sequence === requestSeq.current) setLoading(false);
      }
    };

    loadMatches();
    return () => {
      active = false;
    };
  }, [docId, debouncedSearch]);

  useEffect(() => {
    searchRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && !submitting) onClose?.();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose, submitting]);

  const selectedMatch = useMemo(
    () => matches.find((item) => item.lead?.id === selectedLeadId) || null,
    [matches, selectedLeadId]
  );

  const selectedLead = selectedMatch?.lead || null;
  const isAlreadyLinked = Boolean(linkedLead);
  const amount =
    document?.financials?.grandTotal ?? document?.grandTotal ?? document?.grand_total ?? 0;

  const handleConfirm = async () => {
    if (!selectedLeadId || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      const res = await API.post(
        `/integrations/waquote/documents/${docId}/link-lead`,
        { lead_id: selectedLeadId }
      );
      const payload = res.data || {};
      setSuccess(payload.message || 'Quotation linked to lead successfully.');
      onLinked?.(payload);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          'Could not link this quotation to the selected lead. Please try again.'
      );
      setConfirming(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="link-lead-overlay" onClick={() => !submitting && onClose?.()}>
      <div
        className="link-lead-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Link quotation to lead"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="link-lead-header">
          <div className="link-lead-title-group">
            <span className="link-lead-icon">
              <Link2 size={18} />
            </span>
            <div>
              <h3>
                {confirming ? 'Confirm Linking' : 'Link Quotation to Lead'}
              </h3>
              <p>
                {document?.number || 'Quotation'}
                {document?.docType ? ` • ${document.docType}` : ''}
                {amount ? ` • ${formatAmount(amount)}` : ''}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="link-lead-close"
            onClick={() => !submitting && onClose?.()}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="link-lead-body">
          {error && (
            <div className="link-lead-banner link-lead-banner--error">
              <AlertCircle size={15} />
              <span>{error}</span>
            </div>
          )}
          {success && (
            <div className="link-lead-banner link-lead-banner--success">
              <CheckCircle2 size={15} />
              <span>{success}</span>
            </div>
          )}

          {isAlreadyLinked ? (
            <div className="link-lead-linked-state">
              <div className="link-lead-linked-card">
                <LeadAvatar name={linkedLead.name} />
                <div className="link-lead-linked-copy">
                  <strong>{leadName(linkedLead)}</strong>
                  <span className="link-lead-linked-tag">Already linked</span>
                  <LeadDetails lead={linkedLead} compact />
                </div>
              </div>
              <p className="link-lead-hint">
                This quotation is already linked to a lead. Linking another lead
                is not allowed; manage the existing relationship from the
                quotation or lead record.
              </p>
              <div className="link-lead-footer">
                <button type="button" className="btn btn-secondary" onClick={onClose}>
                  Close
                </button>
              </div>
            </div>
          ) : confirming && selectedLead ? (
            <div className="link-lead-confirm">
              <div className="link-lead-confirm-quote">
                <div>
                  <span>Quotation</span>
                  <strong>{document?.number || '—'}</strong>
                </div>
                <div>
                  <span>Amount</span>
                  <strong>{formatAmount(amount)}</strong>
                </div>
                <div>
                  <span>Status</span>
                  <strong>{document?.status || '—'}</strong>
                </div>
              </div>

              <div className="link-lead-confirm-arrow" aria-hidden="true">
                <Link2 size={18} />
              </div>

              <div className="link-lead-confirm-lead">
                <LeadAvatar name={selectedLead.name} />
                <div>
                  <strong>{leadName(selectedLead)}</strong>
                  {selectedLead?.status && (
                    <span className="link-lead-status">{selectedLead.status}</span>
                  )}
                  <LeadDetails lead={selectedLead} compact />
                </div>
              </div>

              <ul className="link-lead-confirm-notes">
                <li>
                  Customer name, company, phone and email on the quotation will
                  be updated from the lead where the lead has a value.
                </li>
                <li>
                  The quotation id, number, amount, status and issue date will be
                  preserved.
                </li>
                <li>
                  A quotation entry will be added to the lead activity timeline.
                </li>
              </ul>

              <div className="link-lead-footer">
                <button
                  type="button"
                  className="btn btn-outline link-lead-back"
                  onClick={() => setConfirming(false)}
                  disabled={submitting}
                >
                  <ArrowLeft size={15} />
                  Back
                </button>
                <button
                  type="button"
                  className="btn btn-primary link-lead-confirm-btn"
                  onClick={handleConfirm}
                  disabled={submitting}
                >
                  {submitting ? (
                    <Loader2 size={15} className="spin" />
                  ) : (
                    <Link2 size={15} />
                  )}
                  {submitting ? 'Linking…' : 'Confirm & Link'}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="link-lead-search-wrap">
                <Search size={16} className="link-lead-search-icon" />
                <input
                  ref={searchRef}
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search lead name, company, mobile or email…"
                  className="link-lead-search"
                  aria-label="Search CRM leads"
                />
                {search && (
                  <button
                    type="button"
                    className="link-lead-search-clear"
                    onClick={() => setSearch('')}
                    aria-label="Clear search"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>

              <div className="link-lead-list-head">
                <span>
                  {debouncedSearch ? 'Search results' : 'Suggested matches'}
                  {!loading && ` (${matches.length})`}
                </span>
                {!debouncedSearch && matches.some((item) => item.matchReasons?.length) && (
                  <span className="link-lead-list-hint">
                    Matched by mobile number, email or company name
                  </span>
                )}
              </div>

              <div className="link-lead-list" role="radiogroup" aria-label="CRM leads">
                {loading ? (
                  <div className="link-lead-empty">
                    <Loader2 size={20} className="spin" />
                    <span>Loading leads…</span>
                  </div>
                ) : matches.length === 0 ? (
                  <div className="link-lead-empty">
                    <Search size={22} />
                    <strong>No leads found</strong>
                    <span>
                      {debouncedSearch
                        ? 'Try a different name, company, mobile number or email.'
                        : 'No mobile, email or company match was found. Search above to select a lead manually.'}
                    </span>
                  </div>
                ) : (
                  matches.map((item) => {
                    const lead = item.lead || {};
                    const selected = selectedLeadId === lead.id;
                    const isCurrent = item.isCurrentLead || linkedLead?.id === lead.id;
                    return (
                      <button
                        type="button"
                        key={lead.id}
                        className={`link-lead-row${selected ? ' is-selected' : ''}`}
                        onClick={() => setSelectedLeadId(lead.id)}
                        role="radio"
                        aria-checked={selected}
                      >
                        <span className={`link-lead-radio${selected ? ' is-selected' : ''}`} />
                        <LeadAvatar name={lead.name} />
                        <span className="link-lead-row-main">
                          <span className="link-lead-row-title">
                            <strong>{leadName(lead)}</strong>
                            {isCurrent && (
                              <span className="link-lead-current-tag">Linked</span>
                            )}
                            {suggestedLeadId === lead.id && (
                              <span className="link-lead-suggested-tag">Best match</span>
                            )}
                          </span>
                          <LeadDetails lead={lead} compact />
                          {Array.isArray(item.matchReasons) && item.matchReasons.length > 0 && (
                            <span className="link-lead-reasons">
                              {item.matchReasons.map((reason) => (
                                <span key={reason} className="link-lead-reason">
                                  <CheckCircle2 size={11} />
                                  {reason}
                                </span>
                              ))}
                            </span>
                          )}
                        </span>
                      </button>
                    );
                  })
                )}
              </div>

              <div className="link-lead-footer">
                <span className="link-lead-selection-note">
                  {selectedLead
                    ? `Selected: ${leadName(selectedLead)}`
                    : 'Select a lead to continue. Nothing is linked until you confirm.'}
                </span>
                <div className="link-lead-footer-actions">
                  <button type="button" className="btn btn-secondary" onClick={onClose}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary link-lead-confirm-btn"
                    disabled={!selectedLead || loading}
                    onClick={() => setConfirming(true)}
                  >
                    <Link2 size={15} />
                    Link to Lead
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default LinkQuotationToLeadModal;
