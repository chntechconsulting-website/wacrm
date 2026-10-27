import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import { 
  Building2, 
  Search, 
  Plus, 
  Globe, 
  Mail, 
  Phone, 
  Users, 
  Edit2, 
  Trash2, 
  X,
  Building,
  TrendingUp,
  FileText,
  DollarSign,
  Receipt,
  ChevronRight
} from 'lucide-react';

const INITIAL_COMPANIES = [
  { id: 1, name: 'Advanced Tooling Technologies', industry: 'Manufacturing & Tools', website: '', email: 'contact@att.in', phone: '+91 9840712794', location: 'Chennai, TN', contacts_count: 1, leads_count: 2 },
  { id: 4, name: 'Mars&Venus', industry: 'Apparel & Lifestyle', website: '', email: 'info@marsvenus.in', phone: '+91 6381672631', location: 'Chennai, TN', contacts_count: 1, leads_count: 1 },
  { id: 23, name: 'Acme Global Solutions Pvt Ltd', industry: 'Information Technology', website: 'https://acmeglobal.com', email: 'sales@acmeglobal.com', phone: '+91 9876543210', location: 'Bengaluru, KA', contacts_count: 2, leads_count: 3 },
  { id: 9, name: 'Karthik Technologies Pvt Ltd', industry: 'Software Solutions', website: '', email: 'karthik@karthiktech.com', phone: '9840123456', location: 'Chennai, TN', contacts_count: 1, leads_count: 1 },
  { id: 7, name: 'ABC Pvt Ltd', industry: 'Corporate Services', website: '', email: 'contact@abc.in', phone: '9876543210', location: 'Mumbai, MH', contacts_count: 2, leads_count: 4 }
];

const CompaniesPage = () => {
  const [companies, setCompanies] = useState(INITIAL_COMPANIES);
  const [revenueData, setRevenueData] = useState([]);
  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newCompany, setNewCompany] = useState({ name: '', industry: 'Technology', website: '', email: '', phone: '', location: '' });

  // Company Invoices / Revenue Inspection Modal
  const [selectedCompanyInvoices, setSelectedCompanyInvoices] = useState(null);

  // Load live company confirmed revenue from backend
  const loadCompanyRevenue = () => {
    API.get('/sales-targets/companies-revenue')
      .then(res => {
        if (Array.isArray(res.data)) {
          setRevenueData(res.data);
          // Merge with companies list if new customers exist
          setCompanies(prev => {
            const existingNames = new Set(prev.map(c => c.name.toLowerCase()));
            const newEntries = [];
            res.data.forEach(item => {
              if (item.company_name && !existingNames.has(item.company_name.toLowerCase())) {
                newEntries.push({
                  id: item.customer_id || Date.now() + Math.random(),
                  name: item.company_name,
                  industry: 'Client Account',
                  website: '',
                  email: item.email || '',
                  phone: item.phone || '',
                  location: 'India',
                  contacts_count: 1,
                  leads_count: 1
                });
                existingNames.add(item.company_name.toLowerCase());
              }
            });
            return [...prev, ...newEntries];
          });
        }
      })
      .catch(err => console.error('Failed to load company revenue', err));
  };

  useEffect(() => {
    loadCompanyRevenue();
  }, []);

  const handleAddCompany = (e) => {
    e.preventDefault();
    const item = {
      id: Date.now(),
      ...newCompany,
      contacts_count: 0,
      leads_count: 0
    };
    setCompanies([item, ...companies]);
    setShowAddModal(false);
    setNewCompany({ name: '', industry: 'Technology', website: '', email: '', phone: '', location: '' });
  };

  const getCompanyRev = (compName) => {
    if (!compName) return null;
    const match = revenueData.find(r => 
      r.company_name.toLowerCase() === compName.toLowerCase() ||
      compName.toLowerCase().includes(r.company_name.toLowerCase()) ||
      r.company_name.toLowerCase().includes(compName.toLowerCase())
    );
    return match || null;
  };

  const handleInspectCompany = (comp) => {
    const rev = getCompanyRev(comp.name);
    setSelectedCompanyInvoices({
      company: comp,
      revenueSummary: rev
    });
  };

  const formatINR = (amt) => {
    return `₹${Math.round(amt || 0).toLocaleString('en-IN')}`;
  };

  const filteredCompanies = companies.filter(c => 
    c.name.toLowerCase().includes(search.toLowerCase()) || 
    c.industry.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <div style={{ fontSize: '0.82rem', color: '#64748b', marginBottom: '6px' }}>
            <Link to="/dashboard" style={{ color: '#2563eb', textDecoration: 'none' }}>Dashboard</Link> / {' '}
            <span style={{ color: '#0f172a', fontWeight: 600 }}>Companies</span>
          </div>
          <h1 className="page-title">Company Directory & Confirmed Revenue</h1>
          <p className="page-subtitle">Manage client accounts, inspect confirmed billing invoices, and audit company revenue.</p>
        </div>
        <div className="header-actions">
          <button onClick={() => setShowAddModal(true)} className="btn btn-primary">
            <Plus size={16} />
            <span>Add Company</span>
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="table-toolbar">
        <div className="search-box">
          <Search size={18} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search by company name or industry..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Table */}
      <div className="content-card">
        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th>Company Name</th>
                <th>Industry</th>
                <th>Contact Info</th>
                <th>Location</th>
                <th style={{ textAlign: 'right' }}>Confirmed Billing</th>
                <th style={{ textAlign: 'right' }}>Collected</th>
                <th>Invoices</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredCompanies.map(comp => {
                const revSummary = getCompanyRev(comp.name);
                const billed = revSummary ? revSummary.total_confirmed_revenue : 0;
                const collected = revSummary ? revSummary.total_collected_revenue : 0;
                const invCount = revSummary ? revSummary.invoices_count : 0;

                return (
                  <tr key={comp.id} style={{ cursor: 'pointer' }} onClick={() => handleInspectCompany(comp)}>
                    <td>
                      <div style={{ fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Building2 size={18} style={{ color: '#2563eb' }} />
                        <span>{comp.name}</span>
                      </div>
                      {comp.website && (
                        <a href={comp.website} target="_blank" rel="noreferrer" style={{ fontSize: '0.78rem', color: '#64748b', textDecoration: 'none' }}>
                          {comp.website}
                        </a>
                      )}
                    </td>
                    <td>
                      <span className="role-badge role-admin" style={{ backgroundColor: 'rgba(37, 99, 235, 0.1)', color: '#2563eb' }}>
                        {comp.industry}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontSize: '0.85rem' }}>{comp.email}</div>
                      <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{comp.phone}</div>
                    </td>
                    <td style={{ fontSize: '0.85rem' }}>{comp.location}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: billed > 0 ? '#16a34a' : '#64748b' }}>
                      {formatINR(billed)}
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: collected > 0 ? '#0284c7' : '#94a3b8' }}>
                      {formatINR(collected)}
                    </td>
                    <td>
                      <span style={{ 
                        fontSize: '0.75rem', 
                        padding: '3px 8px', 
                        borderRadius: '6px', 
                        backgroundColor: invCount > 0 ? '#f0fdf4' : '#f8fafc',
                        color: invCount > 0 ? '#15803d' : '#94a3b8',
                        border: '1px solid #e2e8f0',
                        fontWeight: 600
                      }}>
                        {invCount} Invoices
                      </span>
                    </td>
                    <td>
                      <button 
                        className="btn btn-outline" 
                        style={{ padding: '5px 10px', fontSize: '0.78rem', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                        title="Inspect Invoices & Billing Details"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleInspectCompany(comp);
                        }}
                      >
                        <Receipt size={14} />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Company Confirmed Invoices Inspection Modal */}
      {selectedCompanyInvoices && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(15,23,42,0.6)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px', backdropFilter: 'blur(4px)' }}>
          <div className="content-card" style={{ width: '100%', maxWidth: '780px', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '14px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Building2 size={22} style={{ color: '#2563eb' }} />
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>
                    {selectedCompanyInvoices.company.name}
                  </h3>
                </div>
                <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#64748b' }}>
                  Confirmed Tax Invoices & Sales Billing Records
                </p>
              </div>
              <button 
                onClick={() => setSelectedCompanyInvoices(null)} 
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Quick Metrics Bar */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '20px' }}>
              <div style={{ background: '#f8fafc', padding: '12px 14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase' }}>Billed Revenue</span>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#16a34a', marginTop: '2px' }}>
                  {formatINR(selectedCompanyInvoices.revenueSummary?.total_confirmed_revenue || 0)}
                </div>
              </div>
              <div style={{ background: '#f8fafc', padding: '12px 14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase' }}>Collected Revenue</span>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0284c7', marginTop: '2px' }}>
                  {formatINR(selectedCompanyInvoices.revenueSummary?.total_collected_revenue || 0)}
                </div>
              </div>
              <div style={{ background: '#f8fafc', padding: '12px 14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 700, textTransform: 'uppercase' }}>Confirmed Invoices</span>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a', marginTop: '2px' }}>
                  {selectedCompanyInvoices.revenueSummary?.invoices_count || 0}
                </div>
              </div>
            </div>

            {/* Invoices List */}
            {(!selectedCompanyInvoices.revenueSummary || selectedCompanyInvoices.revenueSummary.invoices.length === 0) ? (
              <div style={{ textAlign: 'center', padding: '36px', color: '#64748b', background: '#f8fafc', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                <Receipt size={32} style={{ color: '#cbd5e1', marginBottom: '8px' }} />
                <p style={{ margin: 0, fontWeight: 600 }}>No confirmed tax invoices found for this company.</p>
                <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Draft quotations and pipeline proposals are excluded from actual revenue.</span>
              </div>
            ) : (
              <div className="table-responsive">
                <table className="custom-table" style={{ fontSize: '0.82rem' }}>
                  <thead>
                    <tr>
                      <th>Invoice #</th>
                      <th>Billing Date</th>
                      <th>Salesperson</th>
                      <th>Subtotal</th>
                      <th>Tax (GST)</th>
                      <th style={{ textAlign: 'right' }}>Total (INR)</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedCompanyInvoices.revenueSummary.invoices.map((inv) => (
                      <tr key={inv.invoice_id}>
                        <td>
                          <strong style={{ color: '#0f172a' }}>{inv.invoice_number}</strong>
                        </td>
                        <td>{inv.invoice_date}</td>
                        <td>{inv.salesperson_name}</td>
                        <td>{formatINR(inv.subtotal)}</td>
                        <td>{formatINR(inv.tax_total)}</td>
                        <td style={{ textAlign: 'right', fontWeight: 700, color: '#16a34a' }}>
                          {formatINR(inv.grand_total)}
                        </td>
                        <td>
                          <span style={{ 
                            fontSize: '0.72rem', 
                            padding: '2px 8px', 
                            borderRadius: '9999px',
                            background: inv.payment_status === 'paid' ? '#dcfce7' : '#fef3c7',
                            color: inv.payment_status === 'paid' ? '#15803d' : '#b45309',
                            fontWeight: 700,
                            textTransform: 'uppercase'
                          }}>
                            {inv.payment_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '20px' }}>
              <button 
                type="button" 
                className="btn btn-outline" 
                onClick={() => setSelectedCompanyInvoices(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Modal */}
      {showAddModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="content-card" style={{ width: '100%', maxWidth: '500px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Add New Company</h3>
              <button onClick={() => setShowAddModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleAddCompany}>
              <div className="form-group">
                <label>Company Name *</label>
                <input 
                  type="text" 
                  required 
                  value={newCompany.name}
                  onChange={(e) => setNewCompany({ ...newCompany, name: e.target.value })}
                  placeholder="e.g. Acme Corporation" 
                />
              </div>
              <div className="form-group">
                <label>Industry</label>
                <input 
                  type="text" 
                  value={newCompany.industry}
                  onChange={(e) => setNewCompany({ ...newCompany, industry: e.target.value })}
                  placeholder="e.g. Software, Manufacturing" 
                />
              </div>
              <div className="form-group">
                <label>Website</label>
                <input 
                  type="url" 
                  value={newCompany.website}
                  onChange={(e) => setNewCompany({ ...newCompany, website: e.target.value })}
                  placeholder="https://example.com" 
                />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input 
                  type="email" 
                  value={newCompany.email}
                  onChange={(e) => setNewCompany({ ...newCompany, email: e.target.value })}
                  placeholder="contact@company.com" 
                />
              </div>
              <div className="form-group">
                <label>Phone</label>
                <input 
                  type="text" 
                  value={newCompany.phone}
                  onChange={(e) => setNewCompany({ ...newCompany, phone: e.target.value })}
                  placeholder="+91 98765 43210" 
                />
              </div>
              <div className="form-group">
                <label>Location</label>
                <input 
                  type="text" 
                  value={newCompany.location}
                  onChange={(e) => setNewCompany({ ...newCompany, location: e.target.value })}
                  placeholder="e.g. Chennai, Tamil Nadu" 
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
                <button type="button" onClick={() => setShowAddModal(false)} className="btn btn-outline">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Company
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CompaniesPage;
