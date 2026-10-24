import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import PingoPopupService from '../../services/pingoPopupService';
import TimePickerSelect from '../../components/Common/TimePickerSelect';
import { 
  UserPlus, 
  ArrowLeft, 
  Check, 
  AlertCircle,
  Users,
  CloudUpload,
  Download,
  FileSpreadsheet,
  CheckCircle,
  Upload,
  X
} from 'lucide-react';

const STATUS_OPTIONS = [
  'NEW LEAD',
  'CONTACTED',
  'INTERESTED',
  'QUALIFIED',
  'DEMO / MEETING',
  'PROPOSAL SENT',
  'NEGOTIATION',
  'FOLLOW-UP',
  'WON',
  'LOST'
];

const SOURCE_OPTIONS = ['MANUAL', 'META', 'WEBSITE', 'EXCEL', 'REFERRAL'];
const RATING_OPTIONS = ['Hot', 'Warm', 'Cold'];
const PRIORITY_OPTIONS = ['High', 'Medium', 'Low'];

const formatApiError = (err, fallback = 'Failed to process request.') => {
  const detail = err?.response?.data?.detail;
  if (!detail) return err?.message || fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map(item => {
      if (typeof item === 'string') return item;
      const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : '';
      const msg = item.msg || item.message || JSON.stringify(item);
      return field && field !== 'body' ? `${field}: ${msg}` : msg;
    }).join('; ');
  }
  if (typeof detail === 'object') {
    return detail.msg || detail.message || JSON.stringify(detail);
  }
  return fallback;
};

const CreateLeadPage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user: currentUser } = useAuth();

  // Active sub-tab: 'single' (Create Lead) or 'import' (Import Leads)
  const [activeTab, setActiveTab] = useState(() => {
    return searchParams.get('tab') === 'import' ? 'import' : 'single';
  });

  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam === 'import' && activeTab !== 'import') {
      setActiveTab('import');
    } else if (tabParam !== 'import' && activeTab === 'import' && !tabParam) {
      setActiveTab('single');
    }
  }, [searchParams]);

  const handleTabSwitch = (tab) => {
    setActiveTab(tab);
    setSearchParams(tab === 'import' ? { tab: 'import' } : {});
    setError('');
    setSuccess('');
  };

  // --- SINGLE LEAD CREATION STATE ---
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    whatsapp_number: '',
    email: '',
    designation: '',

    company: '',
    industry: '',
    website: '',
    company_size: '',
    city: '',
    state: '',

    source: 'MANUAL',
    status: 'NEW LEAD',
    campaign_name: '',
    rating: 'Warm',
    assigned_to: '',
    priority: 'Medium',

    requirement_notes: '',

    followup_date: '',
    followup_time: '10:00 AM'
  });

  // --- BULK IMPORT STATE ---
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewData, setPreviewData] = useState([]);
  const [importSummary, setImportSummary] = useState(null);

  useEffect(() => {
    const fetchEmployees = async () => {
      try {
        const res = await API.get('/employees/?status_filter=ACTIVE');
        setEmployees(res.data);
        if (currentUser?.employee_id) {
          setFormData(prev => ({ ...prev, assigned_to: currentUser.employee_id }));
        }
      } catch (err) {
        console.error('Failed to load active employees:', err);
      }
    };
    fetchEmployees();
  }, [currentUser]);

  // SINGLE LEAD SUBMIT
  const handleSingleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!formData.first_name || !formData.last_name || !formData.phone) {
      setError('First Name, Last Name, and Phone Number are required.');
      return;
    }

    try {
      setLoading(true);
      const fullName = `${formData.first_name.trim()} ${formData.last_name.trim()}`.trim();
      const payload = {
        ...formData,
        name: fullName,
        email: formData.email && formData.email.trim() ? formData.email.trim() : null,
        whatsapp_number: formData.whatsapp_number && formData.whatsapp_number.trim() ? formData.whatsapp_number.trim() : null,
        company: formData.company && formData.company.trim() ? formData.company.trim() : null,
        industry: formData.industry && formData.industry.trim() ? formData.industry.trim() : null,
        website: formData.website && formData.website.trim() ? formData.website.trim() : null,
        company_size: formData.company_size && formData.company_size.trim() ? formData.company_size.trim() : null,
        city: formData.city && formData.city.trim() ? formData.city.trim() : null,
        state: formData.state && formData.state.trim() ? formData.state.trim() : null,
        designation: formData.designation && formData.designation.trim() ? formData.designation.trim() : null,
        campaign_name: formData.campaign_name && formData.campaign_name.trim() ? formData.campaign_name.trim() : null,
        requirement_notes: formData.requirement_notes && formData.requirement_notes.trim() ? formData.requirement_notes.trim() : null,
        followup_date: formData.followup_date && formData.followup_date.trim() ? formData.followup_date.trim() : null,
        followup_time: formData.followup_time && formData.followup_time.trim() ? formData.followup_time.trim() : null,
        assigned_to: formData.assigned_to ? parseInt(formData.assigned_to, 10) : null
      };

      const res = await API.post('/leads/', payload);
      if (formData.status?.toUpperCase() === 'PROPOSAL SENT') {
        setSuccess('Lead created with PROPOSAL SENT status! Opening Quotation Creation...');
        setTimeout(() => {
          navigate(`/waquotes?create=quotation&leadId=${res.data.id}`);
        }, 800);
        return;
      }
      if (res.data?.is_reinquiry) {
        setSuccess(`🔁 Existing customer/lead matched! Recorded as RE-INQUIRY #${res.data.reinquiry_count} (Total Enquiries: ${res.data.total_enquiries}). Redirecting to All Leads...`);
      } else {
        setSuccess('Lead created successfully! Redirecting to All Leads...');
      }
      setTimeout(() => {
        navigate('/leads');
      }, 1500);

    } catch (err) {
      console.error(err);
      setError(formatApiError(err, 'Failed to create lead. Please verify all inputs.'));
    } finally {
      setLoading(false);
    }
  };

  // BULK IMPORT FILE CHANGE
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setError('');
      if (file.name.endsWith('.csv')) {
        const reader = new FileReader();
        reader.onload = (event) => {
          try {
            const text = event.target.result;
            const lines = text.split('\n').filter(l => l.trim().length > 0);
            if (lines.length > 1) {
              const rows = lines.slice(1, 11).map((line, idx) => {
                const cols = line.split(',').map(c => c.trim().replace(/^["']|["']$/g, ''));
                return {
                  id: idx + 1,
                  name: cols[0] || 'N/A',
                  phone: cols[1] || 'N/A',
                  email: cols[2] || 'N/A',
                  company: cols[3] || 'N/A',
                  source: 'CSV',
                  status: 'Valid'
                };
              });
              setPreviewData(rows);
            } else {
              setPreviewData([]);
            }
          } catch (err) {
            setPreviewData([]);
          }
        };
        reader.readAsText(file);
      } else {
        setPreviewData([]);
      }
    }
  };

  // DOWNLOAD TEMPLATE
  const downloadSampleTemplate = async () => {
    try {
      const res = await API.get('/leads/export/template', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'Leads_Import_Template.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      PingoPopupService.triggerDownloadSuccess({
        docType: 'Excel Template',
        fileName: 'Leads_Import_Template.xlsx',
        reference: 'Template',
        customMessage: 'Leads Import Template downloaded successfully!'
      });
    } catch (err) {
      setError('Failed to download Excel template. Please try again.');
    }
  };

  // SUBMIT IMPORT
  const handleImportSubmit = async () => {
    if (!selectedFile) {
      setError('Please select an Excel (.xlsx) or CSV file to import.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const uploadData = new FormData();
      uploadData.append('file', selectedFile);
      
      const res = await API.post('/leads/import/excel', uploadData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setImportSummary({
        total: res.data.total_rows ?? res.data.imported ?? 0,
        imported: res.data.imported ?? 0,
        reinquiries: res.data.reinquiries ?? 0,
        duplicates: res.data.duplicates ?? 0,
        failed: res.data.invalid ?? 0,
        invalid_rows: res.data.invalid_rows || []
      });
    } catch (err) {
      setError(formatApiError(err, 'Failed to import spreadsheet file.'));
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadErrors = async () => {
    if (!importSummary?.invalid_rows?.length) return;
    try {
      const res = await API.post('/leads/import/download-errors', importSummary.invalid_rows, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'Import_Errors.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      PingoPopupService.triggerDownloadSuccess({
        docType: 'Excel Report',
        fileName: 'Import_Errors.xlsx',
        reference: 'Errors',
        customMessage: 'Import Errors file downloaded successfully!'
      });
    } catch (e) {
      console.error("Failed to download errors", e);
    }
  };

  return (
    <div className="page-container" style={{ maxWidth: '960px', margin: '0 auto', paddingBottom: '40px' }}>
      {/* Header & Breadcrumb */}
      <div className="page-header" style={{ marginBottom: '20px' }}>
        <div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
            <Link to="/dashboard" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Dashboard</Link> / {' '}
            <Link to="/leads" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Leads</Link> / {' '}
            <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>
              {activeTab === 'single' ? 'Create Lead' : 'Import Leads'}
            </span>
          </div>
          <h1 className="page-title" style={{ fontSize: '1.6rem', fontWeight: '800', margin: 0 }}>
            {activeTab === 'single' ? 'Create New Lead' : 'Bulk Import Leads'}
          </h1>
          <p className="page-subtitle" style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            {activeTab === 'single' 
              ? 'Add a new prospective sales lead manually into your CRM pipeline.' 
              : 'Upload Excel or CSV spreadsheets to import multiple leads in bulk.'}
          </p>
        </div>
        <div className="header-actions">
          {activeTab === 'import' && (
            <button onClick={downloadSampleTemplate} className="btn btn-outline" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Download size={16} />
              <span>Download Excel Template</span>
            </button>
          )}
          <Link to="/leads" className="btn btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ArrowLeft size={16} />
            <span>Back to All Leads</span>
          </Link>
        </div>
      </div>

      {/* Unified Tab Switcher */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '8px', 
        marginBottom: '20px', 
        background: 'var(--bg-card)', 
        padding: '6px', 
        borderRadius: '12px', 
        border: '1px solid var(--border-color)',
        width: 'fit-content'
      }}>
        <button
          type="button"
          onClick={() => handleTabSwitch('single')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 18px',
            borderRadius: '8px',
            border: 'none',
            fontSize: '0.9rem',
            fontWeight: activeTab === 'single' ? 700 : 500,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            backgroundColor: activeTab === 'single' ? 'var(--sidebar-active, #EFE7E0)' : 'transparent',
            color: activeTab === 'single' ? 'var(--sidebar-text, #1c1917)' : 'var(--text-muted)'
          }}
        >
          <UserPlus size={16} />
          <span>Quick Add (Create Lead)</span>
        </button>

        <button
          type="button"
          onClick={() => handleTabSwitch('import')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 18px',
            borderRadius: '8px',
            border: 'none',
            fontSize: '0.9rem',
            fontWeight: activeTab === 'import' ? 700 : 500,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            backgroundColor: activeTab === 'import' ? 'var(--sidebar-active, #EFE7E0)' : 'transparent',
            color: activeTab === 'import' ? 'var(--sidebar-text, #1c1917)' : 'var(--text-muted)'
          }}
        >
          <CloudUpload size={16} />
          <span>Bulk Import (Excel / CSV)</span>
        </button>
      </div>

      {/* Alerts */}
      {error && (
        <div className="alert alert-error mb-4" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <AlertCircle size={18} />
          <span>{typeof error === 'object' ? JSON.stringify(error) : String(error)}</span>
        </div>
      )}

      {success && (
        <div className="alert alert-success mb-4" style={{ backgroundColor: 'var(--success-light)', color: 'var(--success)', border: '1px solid rgba(16,185,129,0.3)', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Check size={18} />
          <span>{success}</span>
        </div>
      )}

      {/* TAB 1: SINGLE LEAD FORM */}
      {activeTab === 'single' && (
        <div className="content-card" style={{ width: '100%', padding: '32px', borderRadius: '18px', boxShadow: '0 4px 20px rgba(15, 23, 42, 0.05)' }}>
          <form onSubmit={handleSingleSubmit}>
            {/* SECTION 1: CONTACT INFORMATION */}
            <div style={{ marginBottom: '28px' }}>
              <h4 style={{ fontSize: '1rem', fontWeight: '700', color: 'var(--primary)', marginBottom: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                Contact Information
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>First Name *</label>
                  <input 
                    type="text" 
                    required 
                    placeholder="Enter first name" 
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Last Name *</label>
                  <input 
                    type="text" 
                    required 
                    placeholder="Enter last name" 
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '12px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Mobile Number *</label>
                  <input 
                    type="tel" 
                    required 
                    placeholder="+91 9876543210" 
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>WhatsApp Number</label>
                  <input 
                    type="tel" 
                    placeholder="+91 9876543210" 
                    value={formData.whatsapp_number}
                    onChange={(e) => setFormData({ ...formData, whatsapp_number: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '12px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Email</label>
                  <input 
                    type="email" 
                    placeholder="name@company.com" 
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Designation</label>
                  <input 
                    type="text" 
                    placeholder="e.g. Sales Manager" 
                    value={formData.designation}
                    onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                  />
                </div>
              </div>
            </div>

            {/* SECTION 2: COMPANY INFORMATION */}
            <div style={{ marginBottom: '28px' }}>
              <h4 style={{ fontSize: '1rem', fontWeight: '700', color: 'var(--primary)', marginBottom: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                Company Information
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Company Name</label>
                  <input 
                    type="text" 
                    placeholder="Enter company name" 
                    value={formData.company}
                    onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Industry</label>
                  <input 
                    type="text" 
                    placeholder="e.g. Technology / Retail" 
                    value={formData.industry}
                    onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '12px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Website</label>
                  <input 
                    type="text" 
                    placeholder="https://example.com" 
                    value={formData.website}
                    onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Company Size</label>
                  <input 
                    type="text" 
                    placeholder="e.g. 10-50 employees" 
                    value={formData.company_size}
                    onChange={(e) => setFormData({ ...formData, company_size: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '12px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>City</label>
                  <input 
                    type="text" 
                    placeholder="e.g. Mumbai" 
                    value={formData.city}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>State</label>
                  <input 
                    type="text" 
                    placeholder="e.g. Maharashtra" 
                    value={formData.state}
                    onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                  />
                </div>
              </div>
            </div>

            {/* SECTION 3: LEAD ATTRIBUTES & ASSIGNMENT */}
            <div style={{ marginBottom: '28px' }}>
              <h4 style={{ fontSize: '1rem', fontWeight: '700', color: 'var(--primary)', marginBottom: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                Lead Details & Assignment
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Lead Source</label>
                  <select 
                    value={formData.source} 
                    onChange={(e) => setFormData({ ...formData, source: e.target.value })}
                  >
                    {SOURCE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Initial Status</label>
                  <select 
                    value={formData.status} 
                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  >
                    {STATUS_OPTIONS.map(st => <option key={st} value={st}>{st}</option>)}
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '12px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Campaign Name</label>
                  <input 
                    type="text" 
                    placeholder="e.g. Summer Promo 2026" 
                    value={formData.campaign_name}
                    onChange={(e) => setFormData({ ...formData, campaign_name: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Rating</label>
                  <select 
                    value={formData.rating} 
                    onChange={(e) => setFormData({ ...formData, rating: e.target.value })}
                  >
                    {RATING_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '12px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Assign To</label>
                  <select 
                    value={formData.assigned_to} 
                    onChange={(e) => setFormData({ ...formData, assigned_to: e.target.value })}
                  >
                    <option value="">-- Unassigned --</option>
                    {employees.map(emp => (
                      <option key={emp.id} value={emp.id}>
                        {emp.name} ({emp.designation || 'Sales Rep'})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Priority</label>
                  <select 
                    value={formData.priority} 
                    onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                  >
                    {PRIORITY_OPTIONS.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
              </div>
            </div>

            {/* SECTION 4: REQUIREMENT NOTES */}
            <div style={{ marginBottom: '28px' }}>
              <h4 style={{ fontSize: '1rem', fontWeight: '700', color: 'var(--primary)', marginBottom: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                Requirement & Discovery Notes
              </h4>
              <div className="form-group">
                <textarea 
                  rows="3" 
                  placeholder="Enter lead requirements or initial conversation notes..." 
                  value={formData.requirement_notes}
                  onChange={(e) => setFormData({ ...formData, requirement_notes: e.target.value })}
                  style={{ width: '100%', paddingTop: '10px' }}
                />
              </div>
            </div>

            {/* SECTION 5: FOLLOW-UP SCHEDULE */}
            <div style={{ marginBottom: '24px' }}>
              <h4 style={{ fontSize: '1rem', fontWeight: '700', color: 'var(--primary)', marginBottom: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                Follow-up Schedule
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Date</label>
                  <input 
                    type="date" 
                    value={formData.followup_date}
                    onChange={(e) => setFormData({ ...formData, followup_date: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '0.88rem' }}>Time</label>
                  <TimePickerSelect 
                    value={formData.followup_time}
                    onChange={(e) => setFormData({ ...formData, followup_time: e.target.value })}
                  />
                </div>
              </div>
            </div>

            {/* Form Actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '32px', paddingTop: '20px', borderTop: '1px solid var(--border-color)' }}>
              <button 
                type="button" 
                className="btn btn-outline" 
                onClick={() => navigate('/leads')}
                disabled={loading}
              >
                Cancel
              </button>
              <button 
                type="submit" 
                className="btn btn-primary"
                disabled={loading}
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                <UserPlus size={18} />
                <span>{loading ? 'Creating...' : 'Create Lead'}</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* TAB 2: BULK IMPORT */}
      {activeTab === 'import' && (
        <div>
          {importSummary ? (
            <div className="content-card" style={{ maxWidth: '750px', margin: '0 auto', textAlign: 'center', padding: '36px', borderRadius: '18px' }}>
              <div style={{ width: '64px', height: '64px', borderRadius: '50%', backgroundColor: 'rgba(16, 185, 129, 0.12)', color: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px auto' }}>
                <CheckCircle size={36} />
              </div>
              <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-main)' }}>Leads Import Complete!</h2>
              <p style={{ color: 'var(--text-muted)', marginTop: '6px', marginBottom: '24px' }}>
                Your spreadsheet was processed successfully into the CRM lead registry.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '12px', marginBottom: '28px' }}>
                <div style={{ background: 'var(--bg-dark, #f8fafc)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-color, #e2e8f0)' }}>
                  <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#10b981', display: 'block' }}>{importSummary.imported}</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>New Leads</span>
                </div>
                <div style={{ background: 'rgba(124, 58, 237, 0.05)', padding: '16px', borderRadius: '10px', border: '1px solid #ddd6fe' }}>
                  <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#7c3aed', display: 'block' }}>{importSummary.reinquiries}</span>
                  <span style={{ fontSize: '0.8rem', color: '#7c3aed', fontWeight: '700' }}>Re-Inquiries Linked</span>
                </div>
                <div style={{ background: 'var(--bg-dark, #f8fafc)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-color, #e2e8f0)' }}>
                  <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f59e0b', display: 'block' }}>{importSummary.duplicates}</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>File Duplicates</span>
                </div>
                <div style={{ background: 'var(--bg-dark, #f8fafc)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-color, #e2e8f0)' }}>
                  <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#ef4444', display: 'block' }}>{importSummary.failed}</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Invalid Rows</span>
                </div>
                <div style={{ background: 'var(--bg-dark, #f8fafc)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-color, #e2e8f0)' }}>
                  <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#2563eb', display: 'block' }}>{importSummary.total}</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Total Rows</span>
                </div>
              </div>

              {importSummary.invalid_rows && importSummary.invalid_rows.length > 0 && (
                <div style={{ marginBottom: '24px' }}>
                  <button 
                    type="button" 
                    onClick={handleDownloadErrors} 
                    className="btn btn-outline" 
                    style={{ color: '#dc2626', borderColor: 'rgba(239, 68, 68, 0.4)', padding: '8px 16px', fontSize: '0.85rem' }}
                  >
                    <Download size={15} /> Download Error Rows Excel
                  </button>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'center', gap: '12px' }}>
                <button onClick={() => { setImportSummary(null); setSelectedFile(null); setPreviewData([]); }} className="btn btn-secondary">
                  Import Another File
                </button>
                <button onClick={() => navigate('/leads')} className="btn btn-primary">
                  View All Leads
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Upload Dropzone */}
              <div className="content-card" style={{ padding: '32px', borderRadius: '18px' }}>
                <div 
                  style={{
                    position: 'relative',
                    border: selectedFile ? '2px solid #2563eb' : '2px dashed #cbd5e1',
                    borderRadius: '12px',
                    padding: '40px 20px',
                    textAlign: 'center',
                    backgroundColor: selectedFile ? '#eff6ff' : 'var(--bg-dark, #f8fafc)',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    overflow: 'hidden'
                  }}
                >
                  <input 
                    id="file-input"
                    type="file" 
                    accept=".csv, .xlsx, .xls"
                    onChange={handleFileChange}
                    style={{
                      position: 'absolute',
                      inset: 0,
                      width: '100%',
                      height: '100%',
                      opacity: 0,
                      cursor: 'pointer',
                      zIndex: 2
                    }}
                  />
                  <div style={{ 
                    width: '56px', 
                    height: '56px', 
                    borderRadius: '14px', 
                    backgroundColor: selectedFile ? 'rgba(37, 99, 235, 0.15)' : 'rgba(37, 99, 235, 0.1)', 
                    color: '#2563eb', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center', 
                    margin: '0 auto 12px auto',
                    pointerEvents: 'none'
                  }}>
                    {selectedFile ? <FileSpreadsheet size={30} /> : <CloudUpload size={30} />}
                  </div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', pointerEvents: 'none' }}>
                    {selectedFile ? selectedFile.name : 'Click or Drag & Drop File to Upload'}
                  </h3>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '6px', pointerEvents: 'none' }}>
                    {selectedFile ? (
                      <span style={{ color: '#16a34a', fontWeight: '600' }}>
                        File Selected: {(selectedFile.size / 1024).toFixed(1)} KB — Tap here to change file
                      </span>
                    ) : (
                      'Supported formats: XLSX, XLS, CSV (Max file size: 10MB)'
                    )}
                  </p>
                </div>

                {/* ACTION BAR: Visible when a file is selected */}
                {selectedFile && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    paddingTop: '20px',
                    marginTop: '20px',
                    borderTop: '1px solid var(--border-color)',
                    flexWrap: 'wrap',
                    gap: '12px'
                  }}>
                    <div style={{ fontSize: '0.88rem', color: 'var(--text-main)' }}>
                      Selected: <strong>{selectedFile.name}</strong> ({(selectedFile.size / 1024).toFixed(1)} KB)
                    </div>
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                      <button 
                        type="button"
                        onClick={() => { setSelectedFile(null); setPreviewData([]); }} 
                        className="btn btn-secondary"
                        disabled={loading}
                      >
                        Clear Selection
                      </button>
                      <button 
                        type="button"
                        onClick={handleImportSubmit} 
                        className="btn btn-primary"
                        disabled={loading}
                        style={{
                          padding: '10px 24px',
                          fontSize: '0.92rem',
                          fontWeight: '700',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px'
                        }}
                      >
                        {loading ? (
                          <>
                            <div className="spinner-sm" />
                            <span>Processing Import...</span>
                          </>
                        ) : (
                          <>
                            <Upload size={18} />
                            <span>Confirm & Import Leads</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Parsed Preview Table (if CSV) */}
              {previewData.length > 0 && (
                <div className="content-card" style={{ padding: '24px', borderRadius: '18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>
                      Import Preview ({previewData.length} records detected)
                    </h3>
                    <span className="brand-badge" style={{ backgroundColor: 'rgba(37, 99, 235, 0.1)', color: '#2563eb' }}>
                      Validation Ready
                    </span>
                  </div>

                  <div className="table-responsive">
                    <table className="custom-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Name</th>
                          <th>Phone</th>
                          <th>Email</th>
                          <th>Company</th>
                          <th>Source</th>
                          <th>Validation</th>
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.map((row, idx) => (
                          <tr key={row.id}>
                            <td>{idx + 1}</td>
                            <td style={{ fontWeight: 600 }}>{row.name}</td>
                            <td>{row.phone}</td>
                            <td>{row.email}</td>
                            <td>{row.company}</td>
                            <td>
                              <span className="role-badge role-employee">{row.source}</span>
                            </td>
                            <td>
                              {row.status === 'Valid' ? (
                                <span className="role-badge role-admin" style={{ backgroundColor: 'rgba(16, 185, 129, 0.1)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                                  <Check size={12} /> Valid
                                </span>
                              ) : (
                                <span className="role-badge role-manager">
                                  <AlertCircle size={12} /> Duplicate
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CreateLeadPage;
