import React, { useEffect, useState } from 'react';
import { AlertCircle, ChevronLeft, ChevronRight, Inbox, Loader2, RefreshCw, X } from 'lucide-react';
import API from '../../services/api';
import { formatDateDDMMYYYY, formatLocalDateTime } from '../../utils/dateUtils';
import './ChannelPartnersPage.css';

export const formatDateTime = (value) => (value ? formatLocalDateTime(value) : '—');
export const formatDate = (value) => (value ? formatDateDDMMYYYY(value) : '—');

export const formatMoney = (paise, { compact = false } = {}) => {
  if (paise === null || paise === undefined || Number.isNaN(Number(paise))) return '—';
  const amount = Number(paise) / 100;
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: compact ? 0 : 2,
      notation: compact ? 'compact' : 'standard',
    }).format(amount);
  } catch {
    return `₹${amount.toFixed(2)}`;
  }
};

export const formatBps = (bps) => {
  if (bps === null || bps === undefined || Number.isNaN(Number(bps))) return '—';
  const percent = Number(bps) / 100;
  return `${Number.isInteger(percent) ? percent : percent.toFixed(2)}%`;
};

export const titleCase = (value) => {
  if (!value) return '—';
  return String(value)
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
};

export const valueOrDash = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  return value;
};

export const buildQuery = (params) => {
  const query = {};
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query[key] = value;
  });
  return query;
};

export function usePartnerOptions() {
  const [options, setOptions] = useState([]);
  useEffect(() => {
    let cancelled = false;
    API.get('/channel-partners/partners', { params: { limit: 200 } })
      .then((response) => {
        if (cancelled) return;
        const items = Array.isArray(response.data?.items) ? response.data.items : [];
        setOptions(
          items.map((partner) => ({
            value: partner.id,
            label: partner.code ? `${partner.name} (${partner.code})` : partner.name,
          })),
        );
      })
      .catch(() => {
        if (!cancelled) setOptions([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return options;
}

export function PartnerFilter({ value, onChange, options, label = 'Partner' }) {
  return (
    <label className="cp-field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">All partners</option>
        {(options || []).map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}

export function StatusBadge({ status, tone }) {
  const normalized = String(status || '').toLowerCase();
  const toneClass = tone || (
    ['active', 'approved', 'paid', 'available', 'converted', 'qualified', 'processed', 'assigned']
      .includes(normalized) ? 'green'
      : ['pending', 'submitted', 'on_hold', 'draft', 'ignored', 'in_payout']
        .includes(normalized) ? 'amber'
        : ['rejected', 'failed', 'cancelled', 'suspended', 'terminated', 'lost', 'removed', 'ended']
          .includes(normalized) ? 'red'
          : 'slate'
  );
  return (
    <span className={`cp-badge cp-badge-${toneClass}`}>
      {titleCase(status)}
    </span>
  );
}

export function PageHeader({ eyebrow = 'Channel Partners', title, description, actions, children }) {
  return (
    <header className="cp-page-header">
      <div className="cp-page-heading">
        <span className="cp-eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="cp-page-actions">{actions}</div> : null}
      {children}
    </header>
  );
}

export function RefreshButton({ onClick, refreshing, label = 'Refresh' }) {
  return (
    <button type="button" className="cp-btn cp-btn-secondary" onClick={onClick} disabled={refreshing}>
      <RefreshCw size={15} className={refreshing ? 'cp-spin' : undefined} />
      {refreshing ? 'Refreshing…' : label}
    </button>
  );
}

export function KpiCard({ icon: Icon, label, value, hint, tone = 'slate', to }) {
  const content = (
    <>
      <span className="cp-kpi-icon">{Icon ? <Icon size={18} /> : null}</span>
      <div className="cp-kpi-copy">
        <span className="cp-kpi-label">{label}</span>
        <strong>{value}</strong>
        {hint ? <small>{hint}</small> : null}
      </div>
    </>
  );
  if (to) {
    return (
      <a className={`cp-kpi cp-kpi-${tone}`} href={to}>
        {content}
      </a>
    );
  }
  return <div className={`cp-kpi cp-kpi-${tone}`}>{content}</div>;
}

export function Panel({ title, description, actions, children, className = '' }) {
  return (
    <section className={`cp-panel ${className}`.trim()}>
      {(title || actions) ? (
        <div className="cp-panel-head">
          <div>
            {title ? <h2>{title}</h2> : null}
            {description ? <p>{description}</p> : null}
          </div>
          {actions ? <div className="cp-panel-actions">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function LoadingState({ label = 'Loading channel partner data…' }) {
  return (
    <div className="cp-state">
      <Loader2 size={22} className="cp-spin" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="cp-state cp-state-error">
      <AlertCircle size={22} />
      <div>
        <strong>Something went wrong</strong>
        <p>{message || 'The requested channel partner data could not be loaded.'}</p>
      </div>
      {onRetry ? (
        <button type="button" className="cp-btn cp-btn-secondary" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title = 'Nothing here yet', message }) {
  return (
    <div className="cp-state cp-state-empty">
      <Inbox size={22} />
      <div>
        <strong>{title}</strong>
        {message ? <p>{message}</p> : null}
      </div>
    </div>
  );
}

export function Pagination({ pagination, onPage }) {
  if (!pagination) return null;
  const { page = 1, pages = 0, total = 0, hasPrev, hasNext } = pagination;
  return (
    <div className="cp-pagination">
      <span>
        {total.toLocaleString('en-IN')} record{total === 1 ? '' : 's'}
        {pages > 0 ? ` · page ${page} of ${pages}` : ''}
      </span>
      <div className="cp-pagination-buttons">
        <button
          type="button"
          className="cp-icon-btn"
          onClick={() => onPage(page - 1)}
          disabled={!hasPrev}
          aria-label="Previous page"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          type="button"
          className="cp-icon-btn"
          onClick={() => onPage(page + 1)}
          disabled={!hasNext}
          aria-label="Next page"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

export function Modal({ open, title, subtitle, onClose, children, footer, wide = false }) {
  useEffect(() => {
    if (!open) return undefined;
    const handleKey = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKey);
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="cp-modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose?.();
    }}>
      <div className={`cp-modal ${wide ? 'cp-modal-wide' : ''}`} role="dialog" aria-modal="true">
        <div className="cp-modal-head">
          <div>
            <h2>{title}</h2>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          <button type="button" className="cp-icon-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="cp-modal-body">{children}</div>
        {footer ? <div className="cp-modal-footer">{footer}</div> : null}
      </div>
    </div>
  );
}

export function DefinitionList({ items }) {
  const visible = (items || []).filter((item) => item && item.value !== undefined);
  if (!visible.length) return null;
  return (
    <dl className="cp-definitions">
      {visible.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value === null || item.value === '' ? '—' : item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function JsonBlock({ value, label = 'Raw payload' }) {
  if (value === null || value === undefined) return null;
  let text = '';
  try {
    text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  } catch {
    text = String(value);
  }
  return (
    <details className="cp-json">
      <summary>{label}</summary>
      <pre>{text}</pre>
    </details>
  );
}

export function TableShell({ children }) {
  return <div className="cp-table-wrap">{children}</div>;
}
