import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import IVRCallModal from '../../components/IVR/IVRCallModal';
import { 
  UserCheck, 
  Search, 
  Plus, 
  Mail, 
  Phone, 
  Building, 
  Edit2, 
  Trash2, 
  X,
  PhoneCall
} from 'lucide-react';

const INITIAL_CONTACTS = [
  { id: 1, name: 'Ankit Sharma', title: 'VP Technology', company: 'TechCorp India Ltd', email: 'ankit@techcorp.in', phone: '+91 98111 22233', status: 'ACTIVE' },
  { id: 2, name: 'Priya Verma', title: 'Director of Procurement', company: 'Solar Design Systems', email: 'priya@solardesign.com', phone: '+91 98222 33344', status: 'ACTIVE' },
  { id: 3, name: 'Vikram Patel', title: 'Managing Director', company: 'BuildCon Infrastructure', email: 'vikram@buildcon.org', phone: '+91 98333 44455', status: 'ACTIVE' },
  { id: 4, name: 'Sneha Kapoor', title: 'Head of Operations', company: 'RetailPlus Solutions', email: 'sneha@retailplus.co.in', phone: '+91 98444 55566', status: 'ACTIVE' }
];

const ContactsPage = () => {
  const [contacts, setContacts] = useState(INITIAL_CONTACTS);
  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newContact, setNewContact] = useState({ name: '', title: '', company: 'TechCorp India Ltd', email: '', phone: '' });

  // IVR Call Modal
  const [showCallModal, setShowCallModal] = useState(false);
  const [selectedCallContact, setSelectedCallContact] = useState(null);

  const handleAddContact = (e) => {
    e.preventDefault();
    const item = {
      id: Date.now(),
      ...newContact,
      status: 'ACTIVE'
    };
    setContacts([item, ...contacts]);
    setShowAddModal(false);
    setNewContact({ name: '', title: '', company: 'TechCorp India Ltd', email: '', phone: '' });
  };

  const handleTriggerCall = (contact) => {
    setSelectedCallContact(contact);
    setShowCallModal(true);
  };

  const filteredContacts = contacts.filter(c => 
    c.name.toLowerCase().includes(search.toLowerCase()) || 
    c.company.toLowerCase().includes(search.toLowerCase()) ||
    c.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <div style={{ fontSize: '0.82rem', color: '#64748b', marginBottom: '6px' }}>
            <Link to="/dashboard" style={{ color: '#2563eb', textDecoration: 'none' }}>Dashboard</Link> / {' '}
            <span style={{ color: '#0f172a', fontWeight: 600 }}>Contacts</span>
          </div>
          <h1 className="page-title">Contacts Directory</h1>
          <p className="page-subtitle">Individual business contacts, decision makers, and key stakeholders.</p>
        </div>
        <div className="header-actions">
          <button onClick={() => setShowAddModal(true)} className="btn btn-primary">
            <Plus size={16} />
            <span>Add Contact</span>
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="table-toolbar">
        <div className="search-box">
          <Search size={18} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search by contact name, company, or email..." 
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
                <th>Contact Name</th>
                <th>Title / Designation</th>
                <th>Company</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredContacts.map(c => (
                <tr key={c.id}>
                  <td>
                    <div style={{ fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <UserCheck size={18} style={{ color: '#10b981' }} />
                      {c.name}
                    </div>
                  </td>
                  <td style={{ fontSize: '0.88rem' }}>{c.title || '-'}</td>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.85rem', fontWeight: 500, color: '#2563eb' }}>
                      <Building size={14} /> {c.company}
                    </span>
                  </td>
                  <td>{c.email}</td>
                  <td>{c.phone}</td>
                  <td>
                    <span className="role-badge role-admin" style={{ backgroundColor: 'rgba(16, 185, 129, 0.1)', color: '#10b981' }}>
                      {c.status}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button 
                        onClick={() => handleTriggerCall(c)} 
                        className="btn btn-primary" 
                        style={{ padding: '4px 10px', fontSize: '0.78rem', backgroundColor: '#2563eb', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                        title="Click to Call IVR"
                      >
                        <PhoneCall size={13} /> Call
                      </button>
                      <button className="btn btn-outline" style={{ padding: '4px 8px' }} title="Edit Contact">
                        <Edit2 size={14} />
                      </button>
                    </div>
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
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Add Contact Person</h3>
              <button onClick={() => setShowAddModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleAddContact}>
              <div className="form-group">
                <label>Contact Full Name *</label>
                <input 
                  type="text" 
                  required
                  placeholder="e.g. Rahul Sharma" 
                  value={newContact.name}
                  onChange={(e) => setNewContact({ ...newContact, name: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>Job Title / Designation</label>
                <input 
                  type="text" 
                  placeholder="e.g. Product Manager" 
                  value={newContact.title}
                  onChange={(e) => setNewContact({ ...newContact, title: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>Email Address</label>
                <input 
                  type="email" 
                  placeholder="name@company.com" 
                  value={newContact.email}
                  onChange={(e) => setNewContact({ ...newContact, email: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>Phone Number *</label>
                <input 
                  type="text" 
                  required
                  placeholder="+91 98765 43210" 
                  value={newContact.phone}
                  onChange={(e) => setNewContact({ ...newContact, phone: e.target.value })}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                <button type="button" onClick={() => setShowAddModal(false)} className="btn btn-outline">Cancel</button>
                <button type="submit" className="btn btn-primary">Save Contact</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Click-to-Call IVR Modal */}
      <IVRCallModal 
        isOpen={showCallModal}
        lead={null}
        customerPhone={selectedCallContact?.phone}
        onClose={() => setShowCallModal(false)}
      />
    </div>
  );
};

export default ContactsPage;
