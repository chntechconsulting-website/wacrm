import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../../services/api';
import { formatDateDDMMYYYY, formatLeadReceivedFull } from '../../utils/dateUtils';
import SupportInteractionTimeline from './SupportInteractionTimeline';
import {
  AlertCircle,
  ArrowUpRight,
  CalendarClock,
  CalendarDays,
  CheckCircle2,
  Loader2,
  Package,
  Phone,
  RefreshCw,
  ShieldCheck,
  UserCheck,
  Users,
  X,
} from 'lucide-react';
import './SupportHistory.css';

const formatDateTime = (value) => {
  if (!value) return '—';
  const formatted = formatLeadReceivedFull(value);
  return formatted === '-' ? String(value) : formatted;
};

const BackupCustomerCard = ({ customer, onOpen }) => {
  const summary = customer.summary || {};
  return (
    <article className="backup-customer-card">
      <div className="backup-customer-card-head">
        <div>
          <div className="backup-customer-name">
            {customer.customer_name || 'Support customer'}
            {customer.company_name ? <span>{customer.company_name}</span> : null}
          </div>
          <div className="backup-customer-contact">
            {customer.phone ? (
              <span>
                <Phone size={12} /> {customer.phone}
              </span>
            ) : null}
            {customer.product_service ? (
              <span>
                <Package size={12} /> {customer.product_service}
              </span>
            ) : null}
          </div>
        </div>
        <button type="button" className="support-history-primary-btn" onClick={() => onOpen(customer)}>
          Open history <ArrowUpRight size={14} />
        </button>
      </div>

      <div className="backup-customer-coverage">
        <span>
          <ShieldCheck size={13} /> Permanent owner:{' '}
          <strong>{customer.original_support_employee_name || 'Unassigned'}</strong>
        </span>
        <span>
          <UserCheck size={13} /> Temporary handler:{' '}
          <strong>{customer.backup_employee_name || customer.current_handling_employee_name || 'Unassigned'}</strong>
        </span>
        {customer.coverage ? (
          <span>
            <CalendarDays size={13} /> Coverage {formatDateDDMMYYYY(customer.coverage.start_date)} →{' '}
            {formatDateDDMMYYYY(customer.coverage.end_date)}
          </span>
        ) : null}
      </div>

      <div className="backup-customer-facts">
        <div>
          <span>Unresolved problem</span>
          <strong className={summary.current_unresolved_issue ? 'danger' : ''}>
            {summary.current_unresolved_issue || 'None recorded'}
          </strong>
        </div>
        <div>
          <span>Next action</span>
          <strong>{summary.next_recommended_action || 'None recorded'}</strong>
        </div>
        <div>
          <span>Upcoming Support follow-up</span>
          <strong>
            {summary.pending_follow_up
              ? `${formatDateTime(summary.pending_follow_up.follow_up_at)}${
                  summary.pending_follow_up.is_overdue ? ' • OVERDUE' : ''
                }`
              : 'None scheduled'}
          </strong>
        </div>
        <div>
          <span>Support interactions</span>
          <strong>{customer.interactions?.length || summary.interaction_count || 0}</strong>
        </div>
      </div>
    </article>
  );
};

export default function BackupCustomersPanel({ compact = false }) {
  const navigate = useNavigate();
  const [data, setData] = useState({ total: 0, items: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);

  const fetchBackupCustomers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await API.get('/support/backup-customers', {
        params: { include_history: true },
      });
      setData(response.data || { total: 0, items: [] });
    } catch (err) {
      setError(err.response?.data?.detail || 'Backup customer coverage could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBackupCustomers();
  }, [fetchBackupCustomers]);

  const items = compact ? (data.items || []).slice(0, 4) : data.items || [];

  return (
    <section className="backup-customers-section">
      <div className="backup-customers-header">
        <div>
          <h3>
            <Users size={20} /> Backup Customers
          </h3>
          <p>
            Temporary coverage from approved leave. The permanent owner is never changed by this view.
          </p>
        </div>
        <div className="backup-customers-header-actions">
          <span className="backup-customers-count">{data.total || 0} covered</span>
          <button type="button" onClick={fetchBackupCustomers} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin-icon' : ''} /> Refresh
          </button>
          {compact && (
            <button type="button" onClick={() => navigate('/support/backup-customers')}>
              View all <ArrowUpRight size={14} />
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="support-history-state">
          <Loader2 size={22} className="spin-icon" />
          <p>Loading temporary coverage...</p>
        </div>
      ) : error ? (
        <div className="support-history-state error">
          <AlertCircle size={22} />
          <p>{error}</p>
        </div>
      ) : items.length === 0 ? (
        <div className="support-history-state">
          <CheckCircle2 size={22} />
          <p>No active backup customer coverage. Customers appear here only after an approved leave is covered.</p>
        </div>
      ) : (
        <div className="backup-customer-grid">
          {items.map((customer) => (
            <BackupCustomerCard
              key={customer.coverage_id}
              customer={customer}
              onOpen={setSelected}
            />
          ))}
        </div>
      )}

      {selected && (
        <div className="support-manager-modal-backdrop" onClick={() => setSelected(null)}>
          <div className="support-manager-modal backup-customer-modal" onClick={(event) => event.stopPropagation()}>
            <div className="support-manager-modal-head">
              <div>
                <h3>
                  <UserCheck size={18} /> Backup customer history
                </h3>
                <span>
                  {selected.customer_name}
                  {selected.company_name ? ` • ${selected.company_name}` : ''}
                </span>
              </div>
              <button type="button" onClick={() => setSelected(null)} title="Close">
                <X size={18} />
              </button>
            </div>
            <div className="support-manager-modal-body">
              <SupportInteractionTimeline
                leadId={selected.lead_id}
                customerId={selected.customer_id}
                canAdd
                onChanged={fetchBackupCustomers}
                showPurchase
              />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
