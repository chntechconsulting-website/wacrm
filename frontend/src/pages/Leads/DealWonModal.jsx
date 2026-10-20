import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../../services/api';
import PingoPopupService from '../../services/pingoPopupService';
import PingoMascot from '../../components/Common/PingoMascot';
import {
  Trophy,
  UserCheck,
  Building,
  DollarSign,
  Users,
  FileText,
  CreditCard,
  AlertCircle,
  X,
  CheckCircle2,
  Package,
  Layers,
  ShieldCheck,
  ExternalLink,
  HardDrive,
  ShoppingCart,
  PlusCircle,
  AlertTriangle,
  Info
} from 'lucide-react';

const formatINR = (val) => {
  if (val === null || val === undefined || isNaN(val)) return '₹0.00';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(val);
};

const DealWonModal = ({ isOpen, onClose, lead, onSuccess }) => {
  const navigate = useNavigate();

  // Support Managers State
  const [supportManagers, setSupportManagers] = useState([]);
  const [loadingManagers, setLoadingManagers] = useState(false);
  const [supportManagerId, setSupportManagerId] = useState('');

  // Proforma Invoices State
  const [proformas, setProformas] = useState([]);
  const [loadingProformas, setLoadingProformas] = useState(false);
  const [selectedProformaId, setSelectedProformaId] = useState('');

  // Deal Handoff Fields
  const [dealAmount, setDealAmount] = useState('');
  const [dealAdjustmentReason, setDealAdjustmentReason] = useState('');
  const [customerUsersCount, setCustomerUsersCount] = useState('');
  const [hasExplicitUsersCount, setHasExplicitUsersCount] = useState(true);
  const [paymentStatus, setPaymentStatus] = useState('PAYMENT_PENDING');
  const [paymentAmount, setPaymentAmount] = useState('0');
  const [requirements, setRequirements] = useState('');

  // Submission State
  const [validationError, setValidationError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Active Selected Proforma
  const selectedProforma = useMemo(() => {
    if (!selectedProformaId || !proformas.length) return null;
    return proformas.find((p) => String(p.id) === String(selectedProformaId)) || null;
  }, [selectedProformaId, proformas]);

  // Initial Fetch on Modal Open
  useEffect(() => {
    if (isOpen && lead) {
      setValidationError('');
      fetchSupportManagers();
      fetchProformaInvoices(lead.id);
      setRequirements(lead.requirement_notes || '');
    }
  }, [isOpen, lead]);

  // Sync fields when selected proforma changes
  useEffect(() => {
    if (selectedProforma) {
      const grandTotal = selectedProforma.grand_total ? String(selectedProforma.grand_total) : '0';
      setDealAmount(grandTotal);
      setDealAdjustmentReason('');

      // Licenced user count
      if (selectedProforma.licence_count && Number(selectedProforma.licence_count) > 0) {
        setCustomerUsersCount(String(selectedProforma.licence_count));
        setHasExplicitUsersCount(true);
      } else {
        setCustomerUsersCount('');
        setHasExplicitUsersCount(false);
      }

      // Payment status & amount
      setPaymentStatus(selectedProforma.payment_status || 'PAYMENT_PENDING');
      setPaymentAmount(selectedProforma.amount_paid ? String(selectedProforma.amount_paid) : '0');
    }
  }, [selectedProforma]);

  const fetchSupportManagers = async () => {
    try {
      setLoadingManagers(true);
      const res = await API.get('/workflow/support-managers');
      const list = res.data || [];
      setSupportManagers(list);
      if (list.length === 1) {
        setSupportManagerId(String(list[0].id));
      } else {
        const kumar = list.find((m) =>
          (m.name || '').toLowerCase().includes('kumar') ||
          (m.username || '').toLowerCase().includes('kumar')
        );
        if (kumar) {
          setSupportManagerId(String(kumar.id));
        }
      }
    } catch (err) {
      console.error('Failed to load support managers', err);
    } finally {
      setLoadingManagers(false);
    }
  };

  const fetchProformaInvoices = async (leadId) => {
    try {
      setLoadingProformas(true);
      const res = await API.get(`/leads/${leadId}/proformas`);
      const list = res.data || [];
      setProformas(list);

      if (list.length > 0) {
        // Automatically select the latest proforma invoice
        setSelectedProformaId(String(list[0].id));
      } else {
        setSelectedProformaId('');
      }
    } catch (err) {
      console.error('Failed to load proforma invoices for deal', err);
      setProformas([]);
      setSelectedProformaId('');
    } finally {
      setLoadingProformas(false);
    }
  };

  const handleCreateProformaClick = () => {
    onClose();
    navigate(`/waquotes?create=proforma&leadId=${lead.id}`);
  };

  const isAmountAdjusted = useMemo(() => {
    if (!selectedProforma) return false;
    const current = parseFloat(dealAmount) || 0;
    const original = parseFloat(selectedProforma.grand_total) || 0;
    return Math.abs(current - original) > 0.01;
  }, [dealAmount, selectedProforma]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setValidationError('');

    // 1. Proforma Invoice Validation
    if (!selectedProforma) {
      setValidationError('A valid Proforma Invoice must be selected before marking this deal as WON.');
      return;
    }

    // 2. Support Manager Assignment Validation
    if (!supportManagerId) {
      setValidationError('Please assign an active Support Manager before marking this deal as WON.');
      return;
    }

    // 3. User Licence Count Validation
    const parsedUserCount = parseInt(customerUsersCount, 10);
    if (isNaN(parsedUserCount) || parsedUserCount <= 0) {
      setValidationError('Please enter a valid employee / user licence count (minimum 1).');
      return;
    }

    // 4. Amount Adjustment Validation
    if (isAmountAdjusted && !dealAdjustmentReason.trim()) {
      setValidationError('The deal amount differs from the Proforma Grand Total. Please provide a reason for this adjustment.');
      return;
    }

    try {
      setSubmitting(true);

      const payload = {
        support_manager_id: parseInt(supportManagerId, 10),
        proforma_id: selectedProforma.id,
        proforma_number: selectedProforma.doc_number,
        product_service: selectedProforma.product_summary || selectedProforma.product_category || 'WAHRMS Business Solution',
        selected_bundle: selectedProforma.selected_bundle || null,
        product_category: selectedProforma.product_category || 'WAHRMS',
        total_deal_amount: parseFloat(dealAmount) || parseFloat(selectedProforma.grand_total) || 0,
        customer_users_count: parsedUserCount,
        biometric_device_count: selectedProforma.biometric_device_count || 0,
        quotation_number: selectedProforma.doc_number,
        payment_status: paymentStatus,
        payment_amount: parseFloat(paymentAmount) || 0,
        deal_adjustment_reason: isAmountAdjusted ? dealAdjustmentReason.trim() : null,
        purchased_products: selectedProforma.purchased_products || selectedProforma.line_items || [],
        addons_summary: selectedProforma.addons || [],
        customer_requirements: requirements.trim() || null
      };

      const res = await API.post(`/leads/${lead.id}/won`, payload);
      const selectedManager = supportManagers.find((m) => String(m.id) === String(supportManagerId));
      const managerName = selectedManager?.name || 'Support Manager';

      PingoPopupService.triggerStatusUpdate({
        module: 'Deal',
        status: 'WON',
        reference: lead.company_name || lead.name || `Lead #${lead.id}`,
        customMessage: `Deal closed for ₹${(parseFloat(dealAmount) || 0).toLocaleString('en-IN')}! Support handoff assigned to ${managerName}.`
      });

      onSuccess(res.data, managerName);
      onClose();
    } catch (err) {
      console.error('Error completing deal won workflow:', err);
      const msg = err.response?.data?.detail || 'Failed to complete Deal WON workflow.';
      setValidationError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen || !lead) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.72)',
        backdropFilter: 'blur(5px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '16px'
      }}
    >
      <div
        style={{
          background: '#ffffff',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '820px',
          maxHeight: '94vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
          overflow: 'hidden'
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '18px 24px',
            borderBottom: '1px solid #e2e8f0',
            background: 'linear-gradient(135deg, #047857 0%, #10b981 100%)',
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div
              style={{
                background: 'rgba(255, 255, 255, 0.2)',
                borderRadius: '14px',
                padding: '4px 8px',
                display: 'flex',
                alignItems: 'flex-end',
                justifyContent: 'center'
              }}
            >
              <PingoMascot pose="victory" height={52} withShadow={false} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#ffffff' }}>
                  Mark Deal as WON
                </h2>
                <span
                  style={{
                    background: '#fef08a',
                    color: '#854d0e',
                    fontSize: '0.72rem',
                    fontWeight: 800,
                    padding: '2px 8px',
                    borderRadius: '999px',
                    textTransform: 'uppercase'
                  }}
                >
                  Proforma-Driven Handoff
                </span>
              </div>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.82rem', color: '#ecfdf5' }}>
                Link verified Proforma Invoice & handoff client onboarding to Support Manager
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'rgba(255, 255, 255, 0.15)',
              border: 'none',
              borderRadius: '8px',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              cursor: 'pointer'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Form Body */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>

            {/* Validation Error Banner */}
            {validationError && (
              <div
                style={{
                  background: '#fef2f2',
                  border: '1px solid #f87171',
                  color: '#b91c1c',
                  borderRadius: '10px',
                  padding: '12px 16px',
                  fontSize: '0.86rem',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  marginBottom: '18px'
                }}
              >
                <AlertCircle size={20} style={{ flexShrink: 0 }} />
                <span>{validationError}</span>
              </div>
            )}

            {/* SECTION 1: Customer & Deal Information */}
            <div
              style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '12px',
                padding: '16px',
                marginBottom: '18px'
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  marginBottom: '12px',
                  color: '#0f172a',
                  fontWeight: 700,
                  fontSize: '0.88rem'
                }}
              >
                <Building size={16} style={{ color: '#059669' }} />
                <span>1. Customer & Deal Information</span>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: '12px',
                  fontSize: '0.82rem'
                }}
              >
                <div>
                  <span style={{ color: '#64748b', display: 'block', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Company / Organization
                  </span>
                  <strong style={{ color: '#0f172a', fontSize: '0.94rem' }}>
                    {lead.company || lead.name}
                  </strong>
                  {lead.company && lead.name && (
                    <div style={{ color: '#475569', fontSize: '0.76rem', marginTop: '2px' }}>
                      Contact: {lead.name}
                    </div>
                  )}
                </div>

                <div>
                  <span style={{ color: '#64748b', display: 'block', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Unified Customer & Deal IDs
                  </span>
                  <strong style={{ color: '#0f172a' }}>
                    Deal #{lead.id} &bull; Lead #{lead.id}
                  </strong>
                  <div style={{ color: '#059669', fontSize: '0.76rem', fontWeight: 600, marginTop: '2px' }}>
                    {lead.customer_id ? `Customer #${lead.customer_id}` : 'Unified Customer Record Preserved'}
                  </div>
                </div>

                <div>
                  <span style={{ color: '#64748b', display: 'block', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Contact Phone & Email
                  </span>
                  <div style={{ color: '#1e293b', fontWeight: 600 }}>{lead.phone || 'No phone'}</div>
                  <div style={{ color: '#64748b', fontSize: '0.76rem' }}>{lead.email || 'No email'}</div>
                </div>
              </div>
            </div>

            {/* SECTION 2: Proforma Invoice Selection */}
            <div
              style={{
                background: '#ffffff',
                border: '1px solid #cbd5e1',
                borderRadius: '12px',
                padding: '16px',
                marginBottom: '18px'
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '12px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#0f172a', fontWeight: 700, fontSize: '0.88rem' }}>
                  <FileText size={16} style={{ color: '#2563eb' }} />
                  <span>2. Select Proforma Invoice <span style={{ color: '#dc2626' }}>*</span></span>
                </div>
                {proformas.length > 0 && (
                  <span style={{ fontSize: '0.75rem', color: '#059669', fontWeight: 600 }}>
                    {proformas.length} Valid Proforma{proformas.length > 1 ? 's' : ''} Found
                  </span>
                )}
              </div>

              {loadingProformas ? (
                <div style={{ padding: '16px', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
                  Loading proforma invoices for this customer...
                </div>
              ) : proformas.length === 0 ? (
                /* NO PROFORMA INVOICE ALERT & ACTION */
                <div
                  style={{
                    background: '#fffbeb',
                    border: '1px solid #fde68a',
                    borderRadius: '10px',
                    padding: '16px',
                    color: '#92400e'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                    <AlertTriangle size={24} style={{ color: '#d97706', flexShrink: 0, marginTop: '2px' }} />
                    <div style={{ flex: 1 }}>
                      <strong style={{ fontSize: '0.92rem', display: 'block', marginBottom: '4px' }}>
                        Proforma Invoice Required Before Handoff
                      </strong>
                      <p style={{ margin: '0 0 12px 0', fontSize: '0.82rem', lineHeight: '1.4' }}>
                        According to CRM business rules, a Deal cannot be marked as WON without an authoritative Proforma Invoice.
                        No active proforma invoices were found for <strong>{lead.company || lead.name}</strong>.
                      </p>
                      <button
                        type="button"
                        onClick={handleCreateProformaClick}
                        style={{
                          background: '#d97706',
                          color: '#ffffff',
                          border: 'none',
                          borderRadius: '8px',
                          padding: '8px 16px',
                          fontSize: '0.84rem',
                          fontWeight: 700,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          cursor: 'pointer'
                        }}
                      >
                        <PlusCircle size={16} />
                        <span>Create Proforma Invoice Now</span>
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                /* SELECT DROPDOWN */
                <div>
                  <select
                    value={selectedProformaId}
                    onChange={(e) => setSelectedProformaId(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      border: '1px solid #94a3b8',
                      backgroundColor: '#ffffff',
                      fontSize: '0.88rem',
                      fontWeight: 600,
                      color: '#0f172a',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="">-- Choose Proforma Invoice --</option>
                    {proformas.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.doc_number} &bull; {p.issue_date_formatted || 'No Date'} &bull; {p.product_summary} &bull; {formatINR(p.grand_total)} ({p.payment_status || 'PENDING'})
                      </option>
                    ))}
                  </select>

                  {selectedProforma && (
                    <div
                      style={{
                        marginTop: '10px',
                        padding: '10px 14px',
                        background: '#f0fdf4',
                        border: '1px solid #bbf7d0',
                        borderRadius: '8px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        fontSize: '0.82rem'
                      }}
                    >
                      <div>
                        <span style={{ color: '#166534', fontWeight: 700 }}>
                          Selected: {selectedProforma.doc_number}
                        </span>
                        <span style={{ color: '#475569', marginLeft: '8px' }}>
                          Issued: {selectedProforma.issue_date_formatted}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          style={{
                            background: selectedProforma.payment_status === 'PAID' ? '#dcfce7' : '#fef3c7',
                            color: selectedProforma.payment_status === 'PAID' ? '#15803d' : '#b45309',
                            padding: '2px 8px',
                            borderRadius: '999px',
                            fontWeight: 700,
                            fontSize: '0.72rem'
                          }}
                        >
                          {selectedProforma.payment_status || 'PAYMENT_PENDING'}
                        </span>
                        <strong style={{ color: '#047857', fontSize: '0.92rem' }}>
                          {formatINR(selectedProforma.grand_total)}
                        </strong>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* SECTION 3: Purchased Products, Bundles & Add-ons */}
            {selectedProforma && (
              <div
                style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px',
                  padding: '16px',
                  marginBottom: '18px'
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '12px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#0f172a', fontWeight: 700, fontSize: '0.88rem' }}>
                    <ShoppingCart size={16} style={{ color: '#059669' }} />
                    <span>3. Purchased Products, Bundles & Add-ons</span>
                  </div>
                  {selectedProforma.selected_bundle && (
                    <span
                      style={{
                        background: '#dbeafe',
                        color: '#1e40af',
                        padding: '3px 10px',
                        borderRadius: '999px',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      <Layers size={12} />
                      Bundle: {selectedProforma.selected_bundle}
                    </span>
                  )}
                </div>

                {/* Line Items Table */}
                <div style={{ overflowX: 'auto', marginBottom: '12px' }}>
                  <table
                    style={{
                      width: '100%',
                      borderCollapse: 'collapse',
                      fontSize: '0.8rem',
                      background: '#ffffff',
                      borderRadius: '8px',
                      overflow: 'hidden',
                      border: '1px solid #e2e8f0'
                    }}
                  >
                    <thead>
                      <tr style={{ background: '#f1f5f9', color: '#475569', textAlign: 'left', borderBottom: '1px solid #cbd5e1' }}>
                        <th style={{ padding: '8px 10px' }}>Product / Module</th>
                        <th style={{ padding: '8px 10px' }}>Category</th>
                        <th style={{ padding: '8px 10px', textAlign: 'center' }}>Qty</th>
                        <th style={{ padding: '8px 10px', textAlign: 'right' }}>Unit Rate</th>
                        <th style={{ padding: '8px 10px', textAlign: 'right' }}>Tax (GST)</th>
                        <th style={{ padding: '8px 10px', textAlign: 'right' }}>Line Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedProforma.purchased_products || []).map((item, idx) => (
                        <tr
                          key={idx}
                          style={{
                            borderBottom: '1px solid #f1f5f9',
                            background: item.is_addon ? '#fcfdfd' : '#ffffff'
                          }}
                        >
                          <td style={{ padding: '8px 10px' }}>
                            <div style={{ fontWeight: 600, color: '#0f172a' }}>{item.name}</div>
                            {item.description && item.description !== item.name && (
                              <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px' }}>
                                {item.description}
                              </div>
                            )}
                            {item.bundle && (
                              <span style={{ fontSize: '0.68rem', background: '#eff6ff', color: '#1d4ed8', padding: '1px 6px', borderRadius: '4px', fontWeight: 600, marginTop: '2px', display: 'inline-block' }}>
                                {item.bundle}
                              </span>
                            )}
                          </td>
                          <td style={{ padding: '8px 10px', color: '#475569' }}>
                            <span
                              style={{
                                background: item.category === 'Biometric' ? '#fef3c7' : '#ecfdf5',
                                color: item.category === 'Biometric' ? '#92400e' : '#065f46',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontSize: '0.72rem',
                                fontWeight: 600
                              }}
                            >
                              {item.category || 'General'}
                            </span>
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'center', fontWeight: 600, color: '#0f172a' }}>
                            {item.quantity}
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', color: '#334155' }}>
                            {formatINR(item.unit_price)}
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', color: '#475569' }}>
                            {formatINR(item.tax_amount)} ({item.gst_rate}%)
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>
                            {formatINR(item.line_total)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Add-ons List if separate */}
                {selectedProforma.addons && selectedProforma.addons.length > 0 && (
                  <div
                    style={{
                      background: '#fffbeb',
                      border: '1px solid #fef3c7',
                      borderRadius: '8px',
                      padding: '10px 12px',
                      fontSize: '0.78rem'
                    }}
                  >
                    <strong style={{ color: '#92400e', display: 'block', marginBottom: '4px' }}>
                      Purchased Add-ons & Integrations:
                    </strong>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {selectedProforma.addons.map((add, idx) => (
                        <span
                          key={idx}
                          style={{
                            background: '#ffffff',
                            border: '1px solid #fde68a',
                            borderRadius: '6px',
                            padding: '3px 8px',
                            color: '#78350f',
                            fontWeight: 600
                          }}
                        >
                          {add.name} (Qty: {add.quantity}) &bull; {formatINR(add.total_amount)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* SECTION 4: Employee / User Licence Details */}
            {selectedProforma && (
              <div
                style={{
                  background: '#ffffff',
                  border: '1px solid #cbd5e1',
                  borderRadius: '12px',
                  padding: '16px',
                  marginBottom: '18px'
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginBottom: '12px',
                    color: '#0f172a',
                    fontWeight: 700,
                    fontSize: '0.88rem'
                  }}
                >
                  <Users size={16} style={{ color: '#4f46e5' }} />
                  <span>4. Employee / User Licence Details <span style={{ color: '#dc2626' }}>*</span></span>
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: selectedProforma.biometric_device_count > 0 ? '1fr 1fr' : '1fr',
                    gap: '14px'
                  }}
                >
                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: '6px' }}>
                      Licensed Employee / User Count
                    </label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <input
                        type="number"
                        min="1"
                        value={customerUsersCount}
                        onChange={(e) => {
                          setCustomerUsersCount(e.target.value);
                          if (validationError) setValidationError('');
                        }}
                        placeholder="e.g. 10"
                        style={{
                          width: '120px',
                          padding: '8px 12px',
                          borderRadius: '8px',
                          border: !customerUsersCount ? '2px solid #ef4444' : '1px solid #cbd5e1',
                          fontSize: '0.92rem',
                          fontWeight: 700,
                          color: '#0f172a'
                        }}
                      />
                      {hasExplicitUsersCount ? (
                        <span
                          style={{
                            background: '#dbeafe',
                            color: '#1e40af',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            fontSize: '0.74rem',
                            fontWeight: 600,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                        >
                          <ShieldCheck size={14} />
                          Detected from Proforma ({selectedProforma.licence_count} Users)
                        </span>
                      ) : (
                        <span
                          style={{
                            background: '#fef3c7',
                            color: '#92400e',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            fontSize: '0.74rem',
                            fontWeight: 600,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                        >
                          <AlertTriangle size={14} />
                          Not specified in proforma &ndash; Please confirm
                        </span>
                      )}
                    </div>
                    <small style={{ color: '#64748b', fontSize: '0.74rem', marginTop: '4px', display: 'block' }}>
                      Determines active customer subscription seats in Support Onboarding.
                    </small>
                  </div>

                  {selectedProforma.biometric_device_count > 0 && (
                    <div
                      style={{
                        background: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                        padding: '10px 14px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px'
                      }}
                    >
                      <div
                        style={{
                          background: '#e0f2fe',
                          color: '#0284c7',
                          borderRadius: '8px',
                          padding: '8px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}
                      >
                        <HardDrive size={22} />
                      </div>
                      <div>
                        <span style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
                          Physical Biometric Terminals
                        </span>
                        <div style={{ fontSize: '1rem', fontWeight: 800, color: '#0369a1' }}>
                          {selectedProforma.biometric_device_count} Device{selectedProforma.biometric_device_count > 1 ? 's' : ''}
                        </div>
                        <small style={{ color: '#64748b', fontSize: '0.72rem' }}>
                          Tracked separately from employee software licences.
                        </small>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* SECTION 5: Payment Summary */}
            {selectedProforma && (
              <div
                style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px',
                  padding: '16px',
                  marginBottom: '18px'
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginBottom: '12px',
                    color: '#0f172a',
                    fontWeight: 700,
                    fontSize: '0.88rem'
                  }}
                >
                  <DollarSign size={16} style={{ color: '#059669' }} />
                  <span>5. Payment Summary</span>
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
                    gap: '14px',
                    marginBottom: '12px'
                  }}
                >
                  {/* Proforma Total Card */}
                  <div style={{ background: '#ffffff', padding: '10px 12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                    <span style={{ color: '#64748b', fontSize: '0.72rem', textTransform: 'uppercase', display: 'block' }}>
                      Proforma Invoice Total
                    </span>
                    <strong style={{ fontSize: '1.05rem', color: '#0f172a' }}>
                      {formatINR(selectedProforma.grand_total)}
                    </strong>
                    <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px' }}>
                      Subtotal: {formatINR(selectedProforma.subtotal)} | Tax: {formatINR(selectedProforma.tax_total)}
                    </div>
                  </div>

                  {/* Final Deal Amount (Editable with Reason) */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                      Total Deal Amount (₹)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={dealAmount}
                      onChange={(e) => setDealAmount(e.target.value)}
                      placeholder="0.00"
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '8px',
                        border: isAmountAdjusted ? '2px solid #f59e0b' : '1px solid #cbd5e1',
                        fontSize: '0.9rem',
                        fontWeight: 700,
                        color: '#0f172a'
                      }}
                    />
                  </div>

                  {/* Payment Status Dropdown */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                      Proforma Payment Status
                    </label>
                    <select
                      value={paymentStatus}
                      onChange={(e) => setPaymentStatus(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '8px',
                        border: '1px solid #cbd5e1',
                        backgroundColor: '#ffffff',
                        fontSize: '0.86rem',
                        fontWeight: 600,
                        color: '#0f172a'
                      }}
                    >
                      <option value="PAYMENT_PENDING">PAYMENT PENDING</option>
                      <option value="PARTIALLY_PAID">PARTIALLY PAID</option>
                      <option value="PAID">PAID (CONFIRMED)</option>
                    </select>
                  </div>
                </div>

                {/* Explicit Reason if Amount Adjusted */}
                {isAmountAdjusted && (
                  <div
                    style={{
                      background: '#fffbeb',
                      border: '1px solid #fde68a',
                      borderRadius: '8px',
                      padding: '12px',
                      marginBottom: '8px'
                    }}
                  >
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#92400e', marginBottom: '4px' }}>
                      Deal Adjustment Reason <span style={{ color: '#dc2626' }}>*</span>
                    </label>
                    <input
                      type="text"
                      value={dealAdjustmentReason}
                      onChange={(e) => setDealAdjustmentReason(e.target.value)}
                      placeholder="Reason for modifying amount from Proforma Grand Total (e.g. Special management discount)..."
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: !dealAdjustmentReason.trim() ? '2px solid #ef4444' : '1px solid #d97706',
                        fontSize: '0.84rem'
                      }}
                    />
                    <small style={{ color: '#b45309', fontSize: '0.72rem', marginTop: '4px', display: 'block' }}>
                      Required: Explicit reason for audit trail when deal amount deviates from the Proforma Invoice.
                    </small>
                  </div>
                )}

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem', color: '#64748b' }}>
                  <Info size={14} />
                  <span>
                    Marking the deal as WON will not silently mark the invoice as PAID. Payment verification follows the Finance workflow.
                  </span>
                </div>
              </div>
            )}

            {/* SECTION 6: Support Manager Assignment */}
            <div
              style={{
                background: '#ffffff',
                border: '1px solid #cbd5e1',
                borderRadius: '12px',
                padding: '16px',
                marginBottom: '18px'
              }}
            >
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.88rem',
                  fontWeight: 700,
                  color: '#0f172a',
                  marginBottom: '6px'
                }}
              >
                <UserCheck size={16} style={{ color: '#059669' }} />
                <span>6. Assign to Support Manager <span style={{ color: '#dc2626' }}>*</span></span>
              </label>

              <select
                value={supportManagerId}
                onChange={(e) => {
                  setSupportManagerId(e.target.value);
                  if (validationError) setValidationError('');
                }}
                disabled={loadingManagers}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  border: validationError && !supportManagerId ? '2px solid #ef4444' : '1px solid #cbd5e1',
                  backgroundColor: '#ffffff',
                  fontSize: '0.9rem',
                  fontWeight: 600,
                  color: '#0f172a'
                }}
              >
                <option value="">-- Select Active Support Manager --</option>
                {supportManagers.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.role.replace('_', ' ')}) &ndash; {m.email || m.username}
                  </option>
                ))}
              </select>
              <small style={{ color: '#64748b', fontSize: '0.74rem', marginTop: '4px', display: 'block' }}>
                Required: Only active users with Support Manager role are eligible for deal onboarding.
              </small>
            </div>

            {/* SECTION 7: Onboarding Requirements / Handover Notes */}
            <div
              style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '12px',
                padding: '16px'
              }}
            >
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.88rem',
                  fontWeight: 700,
                  color: '#0f172a',
                  marginBottom: '6px'
                }}
              >
                <FileText size={16} style={{ color: '#0284c7' }} />
                <span>7. Onboarding Requirements / Handover Notes</span>
              </label>
              <textarea
                rows="3"
                value={requirements}
                onChange={(e) => setRequirements(e.target.value)}
                placeholder="Key handover notes for the Support Manager (e.g. IT contact person, branch locations, preferred go-live date)..."
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.84rem'
                }}
              />
            </div>

          </div>

          {/* Footer Actions */}
          <div
            style={{
              padding: '16px 24px',
              borderTop: '1px solid #e2e8f0',
              background: '#f8fafc',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px'
            }}
          >
            <div>
              {proformas.length === 0 && !loadingProformas && (
                <span style={{ fontSize: '0.8rem', color: '#b45309', fontWeight: 600 }}>
                  Please create a Proforma Invoice to proceed.
                </span>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                style={{
                  padding: '9px 18px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  background: '#ffffff',
                  color: '#475569',
                  fontSize: '0.88rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || proformas.length === 0}
                style={{
                  padding: '9px 24px',
                  borderRadius: '8px',
                  border: 'none',
                  background: (submitting || proformas.length === 0) ? '#94a3b8' : '#059669',
                  color: '#ffffff',
                  fontSize: '0.88rem',
                  fontWeight: 700,
                  cursor: (submitting || proformas.length === 0) ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: (submitting || proformas.length === 0) ? 'none' : '0 4px 6px -1px rgba(5, 150, 105, 0.3)'
                }}
              >
                <CheckCircle2 size={18} />
                <span>{submitting ? 'Confirming Deal WON...' : 'Confirm WON & Hand Off'}</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DealWonModal;
