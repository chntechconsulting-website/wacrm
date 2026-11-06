import React, { useEffect, useRef, useState } from 'react';
import API from '../../services/api';
import { formatDateDDMMYYYY } from '../../utils/dateUtils';
import {
  AlertCircle,
  CalendarRange,
  ExternalLink,
  FileText,
  Layers,
  Package,
  RefreshCw,
  ShoppingCart,
  UserCheck,
  Users
} from 'lucide-react';
import './CustomerPurchaseDetails.css';

const formatMoney = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  if (Number.isNaN(number)) return '—';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2
  }).format(number);
};

const displayValue = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  return value;
};

const formatDate = (value) => {
  if (!value) return '—';
  return formatDateDDMMYYYY(value);
};

const STATUS_LABELS = {
  deal_won_date: 'Deal WON date',
  proforma_issue_date: 'Proforma issue date'
};

function DetailField({ label, value }) {
  return (
    <div className="cpd-field">
      <span className="cpd-field-label">{label}</span>
      <span className="cpd-field-value">{displayValue(value)}</span>
    </div>
  );
}

/**
 * Read-only Customer Purchase Details shared by the Support queue and the
 * Support Assigned Leads drawer.
 *
 * The component never invents values. Missing quantities, prices or dates are
 * rendered as an em dash so Support sees exactly what Sales handed over.
 */
export default function CustomerPurchaseDetails({
  purchaseDetails,
  leadId,
  customerId,
  compact = false
}) {
  const [details, setDetails] = useState(purchaseDetails || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [openingUrl, setOpeningUrl] = useState(null);
  const [viewError, setViewError] = useState(null);
  const fetchedForRef = useRef(null);

  useEffect(() => {
    if (purchaseDetails) {
      setDetails(purchaseDetails);
      setError(null);
      return;
    }

    const endpoint = leadId
      ? `/leads/${leadId}/purchase-details`
      : customerId
      ? `/customers/${customerId}/purchase-details`
      : null;

    if (!endpoint) {
      setDetails(null);
      return;
    }

    const cacheKey = `${leadId || ''}_${customerId || ''}`;
    if (fetchedForRef.current === cacheKey) {
      return;
    }

    fetchedForRef.current = cacheKey;
    let cancelled = false;
    setDetails(null);
    setLoading(true);
    setError(null);

    API.get(endpoint)
      .then((res) => {
        if (!cancelled) setDetails(res.data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err.response?.data?.detail ||
            'Unable to load purchase details for this customer.'
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [purchaseDetails, leadId, customerId]);

  const handleView = async (doc) => {
    if (!doc?.url) return;
    setViewError(null);

    // External document links are opened directly. Internal PDF routes need
    // the CRM bearer token, so they are fetched as an authorized blob.
    if (!doc.url.startsWith('/')) {
      window.open(doc.url, '_blank', 'noopener,noreferrer');
      return;
    }

    // Open the tab synchronously from the click so popup blockers allow it,
    // then point it at the authorized PDF blob once it has been generated.
    const viewer = window.open('', '_blank');
    if (viewer) {
      try {
        viewer.document.write(
          '<!doctype html><title>Loading PDF...</title>' +
          '<body style="font-family: sans-serif; padding: 24px;">Generating PDF...</body>'
        );
        viewer.document.close();
      } catch (_) {
        // The tab can still be navigated even if writing the placeholder fails.
      }
    }

    setOpeningUrl(doc.url);
    try {
      // In Axios, baseURL is configured as '/api'. Strip the redundant '/api'
      // prefix from doc.url so Axios does not construct '/api/api/...'.
      const requestPath = doc.url.startsWith('/api/')
        ? doc.url.slice(4)
        : doc.url;

      const response = await API.get(requestPath, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const blobUrl = URL.createObjectURL(blob);

      if (viewer && !viewer.closed) {
        viewer.opener = null;
        viewer.location.href = blobUrl;
      } else {
        const link = document.createElement('a');
        link.href = blobUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        document.body.appendChild(link);
        link.click();
        link.remove();
      }
      // Keep the blob alive long enough for the browser PDF viewer to load it.
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
    } catch (err) {
      if (viewer && !viewer.closed) viewer.close();

      let message = 'Unable to open this purchase document.';

      if (err.code === 'ECONNABORTED') {
        message = 'The server took too long to generate this PDF. Please try again.';
      } else if (!err.response) {
        message = 'Unable to reach the server. Please check your connection and try again.';
      } else if (err.response.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          try {
            const json = JSON.parse(text);
            if (json.detail) message = json.detail;
          } catch (_) {
            // Reports a plain-text/HTML server error (for example a PDF
            // generation failure) instead of an unhelpful generic message.
            const status = err.response.status;
            const preview = text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
            if (preview) {
              message = `Unable to open this purchase document (HTTP ${status}): ${preview.slice(0, 200)}`;
            } else {
              message = `Unable to open this purchase document (HTTP ${status}).`;
            }
          }
        } catch (_) {
          message = `Unable to open this purchase document (HTTP ${err.response.status}).`;
        }
      } else if (err.response.data?.detail) {
        message = err.response.data.detail;
      } else if (err.response.status) {
        message = `Unable to open this purchase document (HTTP ${err.response.status}).`;
      }

      setViewError(message);
    } finally {
      setOpeningUrl(null);
    }
  };

  if (loading) {
    return (
      <div className="cpd-state">
        <RefreshCw size={20} className="cpd-spin" />
        <span>Loading customer purchase details...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="cpd-state cpd-state-error">
        <AlertCircle size={20} />
        <span>{error}</span>
      </div>
    );
  }

  if (!details) {
    return (
      <div className="cpd-state">
        <ShoppingCart size={22} />
        <span>Purchase details will appear after Sales hands this deal over to Support.</span>
      </div>
    );
  }

  const customer = details.customer || {};
  const packageInfo = details.package || {};
  const plan = details.plan || {};
  const subscription = details.subscription || {};
  const handover = details.handover || {};
  const addons = Array.isArray(details.addons) ? details.addons : [];
  const documents = Array.isArray(details.documents) ? details.documents : [];
  const employeeQuantity = details.employee_quantity;
  const deviceCount = Number(details.biometric_device_count || 0);
  const duration = subscription.duration_months;
  const startBasis = STATUS_LABELS[subscription.start_basis] || null;
  const supportAssignment = handover.assigned_agent_name || handover.support_manager_name || 'Unassigned';

  return (
    <div className={`cpd-root ${compact ? 'cpd-compact' : ''}`}>
      <section className="cpd-section">
        <div className="cpd-section-head">
          <Package size={17} />
          <h4>Customer Purchase Details</h4>
        </div>

        <div className="cpd-grid">
          <DetailField label="Customer Name" value={customer.name} />
          <DetailField label="Company Name" value={customer.company_name} />
          <DetailField label="Contact Number" value={customer.phone} />
          <DetailField label="Email" value={customer.email} />
          <DetailField label="Customer ID" value={customer.customer_id ? `#${customer.customer_id}` : null} />
          <DetailField label="Package Name" value={packageInfo.name || packageInfo.code} />
          <DetailField label="Selected Plan" value={plan.name || plan.code} />
          <DetailField
            label="Employees Purchased"
            value={employeeQuantity !== null && employeeQuantity !== undefined ? employeeQuantity : null}
          />
          <DetailField
            label="Subscription Duration"
            value={duration ? `${duration} month${Number(duration) === 1 ? '' : 's'}` : null}
          />
          <DetailField label="Subscription Start Date" value={formatDate(subscription.start_date)} />
          <DetailField label="Subscription End Date" value={formatDate(subscription.end_date)} />
          <DetailField label="Handover Date" value={formatDate(handover.won_at || handover.handover_date)} />
          <DetailField label="Sales Handover Ref" value={handover.sales_handover_reference} />
          <DetailField label="Support Assignment" value={supportAssignment} />
          <DetailField label="Sales Representative" value={handover.sales_employee_name} />
          <DetailField label="Support Status" value={handover.support_status} />
          {deviceCount > 0 && (
            <DetailField label="Biometric Devices" value={deviceCount} />
          )}
        </div>

        {startBasis && (
          <p className="cpd-hint">Subscription start is based on the {startBasis.toLowerCase()}.</p>
        )}
      </section>

      <section className="cpd-section">
        <div className="cpd-section-head">
          <Layers size={17} />
          <h4>Purchased Add-ons</h4>
          <span className="cpd-count">{addons.length}</span>
        </div>

        {addons.length === 0 ? (
          <p className="cpd-empty">No add-ons were purchased with this deal.</p>
        ) : (
          <div className="cpd-table-wrap">
            <table className="cpd-table">
              <thead>
                <tr>
                  <th>Add-on Product Title</th>
                  <th>Quantity</th>
                  <th>Unit Price</th>
                  <th>Classification</th>
                </tr>
              </thead>
              <tbody>
                {addons.map((addon, index) => (
                  <tr key={`${addon.code || addon.name}-${index}`}>
                    <td>
                      <span className="cpd-addon-name">{addon.name || addon.code || 'Add-on'}</span>
                      {addon.code && <span className="cpd-addon-code">{addon.code}</span>}
                    </td>
                    <td>{addon.quantity !== null && addon.quantity !== undefined ? addon.quantity : '—'}</td>
                    <td>{formatMoney(addon.unit_price)}</td>
                    <td>
                      <span className={`cpd-badge ${addon.pricing_type === 'one_time' ? 'one-time' : 'recurring'}`}>
                        {addon.classification || (addon.pricing_type === 'one_time' ? 'One-time setup' : 'Recurring')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="cpd-section">
        <div className="cpd-section-head">
          <FileText size={17} />
          <h4>Purchase Documentation</h4>
        </div>

        {documents.length === 0 ? (
          <p className="cpd-empty">No purchase documents are linked to this handover.</p>
        ) : (
          <div className="cpd-docs">
            {documents.map((doc, index) => (
              <div className="cpd-doc" key={`${doc.type}-${doc.number || index}`}>
                <div className="cpd-doc-main">
                  <span className="cpd-doc-label">{doc.label}</span>
                  <span className="cpd-doc-number">{doc.number || 'Number not available'}</span>
                  <span className="cpd-doc-meta">
                    {doc.date ? formatDate(doc.date) : 'Date not available'}
                    {doc.payment_status ? ` • ${String(doc.payment_status).replace(/_/g, ' ')}` : ''}
                  </span>
                </div>
                {doc.url ? (
                  <button
                    type="button"
                    className="cpd-doc-link"
                    onClick={() => handleView(doc)}
                    disabled={openingUrl === doc.url}
                  >
                    {openingUrl === doc.url ? (
                      <RefreshCw size={14} className="cpd-spin" />
                    ) : (
                      <ExternalLink size={14} />
                    )}
                    <span>{openingUrl === doc.url ? 'Opening...' : 'View PDF'}</span>
                  </button>
                ) : (
                  <span className="cpd-doc-unavailable">PDF not available</span>
                )}
              </div>
            ))}
          </div>
        )}

        {viewError && (
          <p className="cpd-download-error">
            <AlertCircle size={14} /> {viewError}
          </p>
        )}
      </section>

      <section className="cpd-handover">
        <div>
          <UserCheck size={15} />
          <span>Sales: {handover.sales_employee_name || '—'}</span>
        </div>
        <div>
          <CalendarRange size={15} />
          <span>Handover: {formatDate(handover.won_at || handover.handover_date)}</span>
        </div>
        {handover.sales_handover_reference && (
          <div>
            <FileText size={15} />
            <span>Ref: {handover.sales_handover_reference}</span>
          </div>
        )}
        <div>
          <Users size={15} />
          <span>Support: {supportAssignment}</span>
        </div>
      </section>
    </div>
  );
}
