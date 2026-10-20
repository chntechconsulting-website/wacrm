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
  Building
} from 'lucide-react';

const INITIAL_COMPANIES = [
  { id: 1, name: 'TechCorp India Ltd', industry: 'Information Technology', website: 'https://techcorp.in', email: 'contact@techcorp.in', phone: '+91 22 6789 0000', location: 'Mumbai, MH', contacts_count: 4, leads_count: 12 },
  { id: 2, name: 'Solar Design Systems', industry: 'Renewable Energy', website: 'https://solardesign.com', email: 'info@solardesign.com', phone: '+91 80 4111 2222', location: 'Bengaluru, KA', contacts_count: 2, leads_count: 5 },
  { id: 3, name: 'BuildCon Infrastructure', industry: 'Construction & Real Estate', website: 'https://buildcon.org', email: 'sales@buildcon.org', phone: '+91 11 2345 6789', location: 'New Delhi, DL', contacts_count: 3, leads_count: 8 },
  { id: 4, name: 'RetailPlus Solutions', industry: 'Retail & E-commerce', website: 'https://retailplus.co.in', email: 'support@retailplus.co.in', phone: '+91 44 2888 9999', location: 'Chennai, TN', contacts_count: 1, leads_count: 3 }
];

const CompaniesPage = () => {
  const [companies, setCompanies] = useState(INITIAL_COMPANIES);
  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newCompany, setNewCompany] = useState({ name: '', industry: 'Technology', website: '', email: '', phone: '', location: '' });

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
          <h1 className="page-title">Company Directory</h1>
          <p className="page-subtitle">Manage client accounts, corporate profiles, and associated B2B lead accounts.</p>
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
                <th>Contacts</th>
                <th>Leads</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredCompanies.map(comp => (
                <tr key={comp.id}>
                  <td>
                    <div style={{ fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Building2 size={18} style={{ color: '#2563eb' }} />
                      {comp.name}
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
                  <td style={{ fontWeight: 600 }}>{comp.contacts_count}</td>
                  <td style={{ fontWeight: 600 }}>{comp.leads_count}</td>
                  <td>
                    <button className="btn btn-outline" style={{ padding: '4px 8px' }} title="Edit Company">
                      <Edit2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

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
                  placeholder="e.g. Technology, Manufacturing" 
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label>Email</label>
                  <input 
                    type="email" 
                    value={newCompany.email}
                    onChange={(e) => setNewCompany({ ...newCompany, email: e.target.value })}
                    placeholder="info@company.com" 
                  />
                </div>
                <div className="form-group">
                  <label>Phone</label>
                  <input 
                    type="tel" 
                    value={newCompany.phone}
                    onChange={(e) => setNewCompany({ ...newCompany, phone: e.target.value })}
                    placeholder="+91 22 1234 5678" 
                  />
                </div>
              </div>
              <div className="form-group">
                <label>Location / City</label>
                <input 
                  type="text" 
                  value={newCompany.location}
                  onChange={(e) => setNewCompany({ ...newCompany, location: e.target.value })}
                  placeholder="Mumbai, India" 
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
                <button type="button" onClick={() => setShowAddModal(false)} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary">Save Company</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CompaniesPage;
