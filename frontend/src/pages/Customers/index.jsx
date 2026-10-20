import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../../services/api';
import { formatDateDDMMYYYY } from '../../utils/dateUtils';
import QuotationModal from '../../components/Billing/QuotationModal';
import { 
  Users, 
  Search, 
  Building2, 
  Mail, 
  Phone, 
  MapPin, 
  Eye, 
  X,
  Clock,
  CheckCircle,
  FileText,
  FileSpreadsheet
} from 'lucide-react';

const Customers = () => {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerActivities, setCustomerActivities] = useState([]);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);

  const [showCustomerBillingModal, setShowCustomerBillingModal] = useState(false);
  const [customerBillingData, setCustomerBillingData] = useState({});
  const [customerDocs, setCustomerDocs] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [customerDocCategory, setCustomerDocCategory] = useState('all');

  const handleCreateDocForCustomer = (cust, type = 'quotation', category = 'wahrms') => {
    if (!cust) return;
    setCustomerBillingData({
      docType: type,
      productCategory: category,
      customerId: cust.id,
      name: cust.contact_name,
      company: cust.company_name,
      phone: cust.phone,
      email: cust.email,
      address: cust.location || '',
      state: 'Tamil Nadu'
    });
    setShowCustomerBillingModal(true);
  };

  const fetchCustomers = async () => {
    try {
      setLoading(true);
      const res = await API.get('/customers', { params: { search } });
      setCustomers(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, [search]);

  const handleOpenDetailModal = async (cust) => {
    try {
      setSelectedCustomer(null); // Clear previous customer state immediately
      setCustomerActivities([]);
      setCustomerDocs([]);
      setShowDetailModal(true);
      setLoadingActivities(true);
      setLoadingDocs(true);

      const [custRes, actRes, docRes] = await Promise.all([
        API.get(`/customers/${cust.id}`),
        API.get('/activities', { params: { customer_id: cust.id } }),
        API.get('/integrations/waquote/documents', { params: { customerId: cust.id } })
      ]);

      setSelectedCustomer(custRes.data);
      setCustomerActivities(actRes.data || []);
      setCustomerDocs(docRes.data?.documents || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingActivities(false);
      setLoadingDocs(false);
    }
  };

  const handleDownloadDoc = async (doc) => {
    if (!doc) return;
    const cleanId = String(doc.id || doc.rawId || '').replace('local_', '').trim();
    const dType = (doc.docType || 'quotation').toLowerCase();
    const endpoint = dType === 'invoice'
      ? `/integrations/waquote/invoices/${cleanId}/download`
      : (dType === 'proforma' ? `/integrations/waquote/proformas/${cleanId}/download` : `/integrations/waquote/quotations/${cleanId}/download`);
    try {
      const response = await API.get(endpoint, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const cleanNum = (doc.number || doc.doc_number || cleanId).replace(/[\\/]/g, '-');
      link.download = `${dType}_${cleanNum}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      window.open(`/api/v1${endpoint}`, '_blank');
    }
  };

  const handleBillingSuccess = async () => {
    setShowCustomerBillingModal(false);
    if (selectedCustomer) {
      try {
        const docRes = await API.get('/integrations/waquote/documents', { params: { customerId: selectedCustomer.id } });
        setCustomerDocs(docRes.data?.documents || []);
      } catch (_) {}
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Customer Directory</h1>
          <p className="page-subtitle">Converted leads and official customer accounts ({customers.length} total customers).</p>
        </div>
      </div>

      <div className="content-card">
        <div className="table-toolbar">
          <div className="search-box">
            <Search size={18} className="search-icon" />
            <input 
              type="text" 
              placeholder="Search customers by company, contact name, phone, email..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Company Name</th>
                <th>Contact Name</th>
                <th>Phone</th>
                <th>Email</th>
                <th>Location</th>
                <th>Converted Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="8" className="text-center py-4 text-muted">
                    Loading customer records...
                  </td>
                </tr>
              ) : customers.length === 0 ? (
                <tr>
                  <td colSpan="8" className="text-center py-4 text-muted">
                    No customer records converted yet. Change a lead status to CONVERTED to create a customer.
                  </td>
                </tr>
              ) : (
                customers.map((c) => (
                  <tr key={c.id}>
                    <td>{c.id}</td>
                    <td><strong>{c.company_name}</strong></td>
                    <td>{c.contact_name}</td>
                    <td>{c.phone}</td>
                    <td>{c.email || '-'}</td>
                    <td>{c.location || '-'}</td>
                    <td>{formatDateDDMMYYYY(c.created_at)}</td>
                    <td>
                      <button 
                        className="btn btn-outline" 
                        style={{ padding: '6px 12px', fontSize: '0.82rem' }}
                        onClick={() => handleOpenDetailModal(c)}
                      >
                        <Eye size={14} /> Profile
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* DETAIL MODAL */}
      {showDetailModal && (
        <div className="modal-backdrop" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: '740px', maxHeight: '90vh', padding: '28px',
            overflowY: 'auto', boxShadow: 'var(--shadow-lg)'
          }}>
            {!selectedCustomer ? (
              <div className="text-center py-4 text-muted">Loading customer details...</div>
            ) : (
              <>
                <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <h3 style={{ fontSize: '1.2rem', fontWeight: '700' }}>Customer Profile #{selectedCustomer.id}</h3>
                  <button onClick={() => setShowDetailModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
                    <X size={20} />
                  </button>
                </div>

                <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '12px', marginBottom: '20px', border: '1px solid var(--border-color)' }}>
                  <h4 style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--primary)', marginBottom: '8px' }}>{selectedCustomer.company_name}</h4>
                  <p style={{ fontSize: '0.9rem', marginBottom: '12px' }}>Contact Person: <strong>{selectedCustomer.contact_name}</strong></p>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.88rem' }}>
                    <div><Phone size={14} style={{ display: 'inline', marginRight: '6px' }} /> <strong>Phone:</strong> {selectedCustomer.phone}</div>
                    <div><Mail size={14} style={{ display: 'inline', marginRight: '6px' }} /> <strong>Email:</strong> {selectedCustomer.email || '-'}</div>
                    <div><MapPin size={14} style={{ display: 'inline', marginRight: '6px' }} /> <strong>Location:</strong> {selectedCustomer.location || '-'}</div>
                    <div><strong>Joined:</strong> {formatDateDDMMYYYY(selectedCustomer.created_at)}</div>
                  </div>

                  {/* Separate Document Creation Actions for WAHRMS and Biometric */}
                  <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '8px' }}>
                      Create Independent Product Documents
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '8px' }}>
                      <button
                        type="button"
                        onClick={() => handleCreateDocForCustomer(selectedCustomer, 'quotation', 'wahrms')}
                        className="btn btn-outline"
                        style={{ fontSize: '0.78rem', fontWeight: 600, color: '#0369a1', borderColor: '#bae6fd', backgroundColor: '#f0f9ff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '7px 10px' }}
                        title="Create independent WAHRMS Quotation"
                      >
                        <FileText size={13} /> + WAHRMS Quote
                      </button>
                      <button
                        type="button"
                        onClick={() => handleCreateDocForCustomer(selectedCustomer, 'quotation', 'biometric')}
                        className="btn btn-outline"
                        style={{ fontSize: '0.78rem', fontWeight: 600, color: '#b45309', borderColor: '#fde68a', backgroundColor: '#fffbeb', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '7px 10px' }}
                        title="Create independent Biometric Hardware Quotation"
                      >
                        <FileText size={13} /> + Bio Quote
                      </button>
                      <button
                        type="button"
                        onClick={() => handleCreateDocForCustomer(selectedCustomer, 'proforma', 'wahrms')}
                        className="btn btn-outline"
                        style={{ fontSize: '0.78rem', fontWeight: 600, color: '#0f766e', borderColor: '#99f6e4', backgroundColor: '#f0fdfa', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '7px 10px' }}
                        title="Create independent WAHRMS Proforma Invoice"
                      >
                        <FileSpreadsheet size={13} /> + WAHRMS PI
                      </button>
                      <button
                        type="button"
                        onClick={() => handleCreateDocForCustomer(selectedCustomer, 'proforma', 'biometric')}
                        className="btn btn-outline"
                        style={{ fontSize: '0.78rem', fontWeight: 600, color: '#7c3aed', borderColor: '#ddd6fe', backgroundColor: '#f5f3ff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '7px 10px' }}
                        title="Create independent Biometric Proforma Invoice"
                      >
                        <FileSpreadsheet size={13} /> + Bio PI
                      </button>
                    </div>
                  </div>
                </div>

                {/* INDEPENDENT BILLING DOCUMENTS SECTION (WAHRMS & BIOMETRIC) */}
                <div style={{ marginTop: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: '700', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <FileText size={16} /> Customer Billing Documents
                    </h4>

                    {/* Category Filter Tabs */}
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        type="button"
                        onClick={() => setCustomerDocCategory('all')}
                        style={{
                          fontSize: '0.74rem',
                          padding: '3px 9px',
                          borderRadius: '6px',
                          border: '1px solid #cbd5e1',
                          fontWeight: customerDocCategory === 'all' ? 700 : 500,
                          backgroundColor: customerDocCategory === 'all' ? '#0f172a' : '#fff',
                          color: customerDocCategory === 'all' ? '#fff' : '#475569',
                          cursor: 'pointer'
                        }}
                      >
                        All ({customerDocs.length})
                      </button>
                      <button
                        type="button"
                        onClick={() => setCustomerDocCategory('wahrms')}
                        style={{
                          fontSize: '0.74rem',
                          padding: '3px 9px',
                          borderRadius: '6px',
                          border: '1px solid #bae6fd',
                          fontWeight: customerDocCategory === 'wahrms' ? 700 : 500,
                          backgroundColor: customerDocCategory === 'wahrms' ? '#0284c7' : '#f0f9ff',
                          color: customerDocCategory === 'wahrms' ? '#fff' : '#0369a1',
                          cursor: 'pointer'
                        }}
                      >
                        WAHRMS ({customerDocs.filter(d => (d.productCategory || 'wahrms').toLowerCase() === 'wahrms').length})
                      </button>
                      <button
                        type="button"
                        onClick={() => setCustomerDocCategory('biometric')}
                        style={{
                          fontSize: '0.74rem',
                          padding: '3px 9px',
                          borderRadius: '6px',
                          border: '1px solid #fde68a',
                          fontWeight: customerDocCategory === 'biometric' ? 700 : 500,
                          backgroundColor: customerDocCategory === 'biometric' ? '#d97706' : '#fffbeb',
                          color: customerDocCategory === 'biometric' ? '#fff' : '#b45309',
                          cursor: 'pointer'
                        }}
                      >
                        Biometric ({customerDocs.filter(d => (d.productCategory || 'wahrms').toLowerCase() === 'biometric').length})
                      </button>
                    </div>
                  </div>

                  {loadingDocs ? (
                    <div className="text-center py-3 text-muted" style={{ fontSize: '0.85rem' }}>Loading customer documents...</div>
                  ) : customerDocs.length === 0 ? (
                    <div style={{ background: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '0.85rem', color: '#64748b', textAlign: 'center' }}>
                      No quotations or proforma invoices issued for this customer yet. Use the buttons above to create separate WAHRMS or Biometric documents.
                    </div>
                  ) : (
                    <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
                      <table style={{ width: '100%', fontSize: '0.82rem', borderCollapse: 'collapse', textAlign: 'left' }}>
                        <thead style={{ backgroundColor: '#f1f5f9', color: '#475569', borderBottom: '1px solid #e2e8f0' }}>
                          <tr>
                            <th style={{ padding: '8px 12px' }}>Doc #</th>
                            <th style={{ padding: '8px 12px' }}>Category</th>
                            <th style={{ padding: '8px 12px' }}>Type</th>
                            <th style={{ padding: '8px 12px' }}>Date</th>
                            <th style={{ padding: '8px 12px', textAlign: 'right' }}>Amount</th>
                            <th style={{ padding: '8px 12px' }}>Status</th>
                            <th style={{ padding: '8px 12px', textAlign: 'right' }}>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {customerDocs
                            .filter(d => customerDocCategory === 'all' || (d.productCategory || 'wahrms').toLowerCase() === customerDocCategory)
                            .map((d) => {
                              const dType = (d.docType || 'quotation').toLowerCase();
                              const isBio = (d.productCategory || 'wahrms').toLowerCase() === 'biometric';
                              return (
                                <tr key={d.id || d.number} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                  <td style={{ padding: '8px 12px' }}>
                                    <strong>{d.number}</strong>
                                    {d.sourceQuotationNumber && (
                                      <div style={{ fontSize: '0.68rem', color: '#0f766e' }}>
                                        Ref: {d.sourceQuotationNumber}
                                      </div>
                                    )}
                                  </td>
                                  <td style={{ padding: '8px 12px' }}>
                                    <span style={{
                                      fontSize: '0.68rem',
                                      fontWeight: 700,
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      backgroundColor: isBio ? '#fef3c7' : '#e0f2fe',
                                      color: isBio ? '#b45309' : '#0369a1',
                                      textTransform: 'uppercase'
                                    }}>
                                      {isBio ? 'Biometric' : 'WAHRMS'}
                                    </span>
                                  </td>
                                  <td style={{ padding: '8px 12px', textTransform: 'capitalize' }}>
                                    {dType}
                                  </td>
                                  <td style={{ padding: '8px 12px', color: '#64748b' }}>
                                    {d.issueDateFormatted || '—'}
                                  </td>
                                  <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600 }}>
                                    ₹ {(d.grandTotal || 0).toLocaleString('en-IN')}
                                  </td>
                                  <td style={{ padding: '8px 12px' }}>
                                    <span style={{
                                      fontSize: '0.70rem',
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      backgroundColor: d.paymentStatus === 'paid' ? '#dcfce7' : '#fee2e2',
                                      color: d.paymentStatus === 'paid' ? '#166534' : '#991b1b',
                                      textTransform: 'capitalize'
                                    }}>
                                      {d.paymentStatus || d.status || 'issued'}
                                    </span>
                                  </td>
                                  <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                                    <button
                                      type="button"
                                      onClick={() => handleDownloadDoc(d)}
                                      className="btn btn-sm btn-outline"
                                      style={{ fontSize: '0.72rem', padding: '3px 8px', color: '#0f766e', borderColor: '#99f6e4' }}
                                      title="Download PDF"
                                    >
                                      PDF
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* CUSTOMER CONTEXTUAL ACTIVITIES */}
                <div style={{ marginTop: '24px' }}>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: '700', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Clock size={16} /> Customer Activity History
                  </h4>
                  {loadingActivities ? (
                    <div className="text-center py-2 text-muted" style={{ fontSize: '0.85rem' }}>Loading activity logs...</div>
                  ) : customerActivities.length === 0 ? (
                    <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '0.85rem', color: '#64748b' }}>
                      No specific activity history recorded for this customer yet.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {customerActivities.map((act) => (
                        <div key={act.activity_id || act.id} style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '0.85rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600, color: '#0f172a', marginBottom: '4px' }}>
                            <span>{act.activity_type}</span>
                            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                              {act.created_at ? new Date(act.created_at).toLocaleString() : ''}
                            </span>
                          </div>
                          <div style={{ color: '#334155' }}>{act.description}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '24px' }}>
                  <button type="button" className="btn btn-outline" onClick={() => setShowDetailModal(false)}>
                    Close Profile
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Native Quotation Studio Modal */}
      <QuotationModal
        isOpen={showCustomerBillingModal}
        onClose={() => setShowCustomerBillingModal(false)}
        initialData={customerBillingData}
        onSuccess={handleBillingSuccess}
      />
    </div>
  );
};

export default Customers;
