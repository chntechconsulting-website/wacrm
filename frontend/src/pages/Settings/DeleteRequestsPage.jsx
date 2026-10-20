import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { 
  ShieldCheck, 
  Trash2, 
  CheckCircle, 
  XCircle, 
  Clock, 
  AlertCircle, 
  Search, 
  RefreshCw,
  User,
  Building,
  Calendar,
  Check,
  X,
  FileText
} from 'lucide-react';

const DeleteRequestsPage = () => {
  const { user } = useAuth();
  const isAdmin = (user?.role || '').toUpperCase() === 'ADMIN';

  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [toastMessage, setToastMessage] = useState('');

  const fetchDeleteRequests = async () => {
    try {
      setLoading(true);
      const params = {};
      if (statusFilter) params.status_filter = statusFilter;
      const res = await API.get('/delete-requests', { params });
      setRequests(res.data || []);
    } catch (err) {
      console.error("Failed to load delete requests:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDeleteRequests();
  }, [statusFilter]);

  const handleApprove = async (reqId) => {
    try {
      setActionLoadingId(reqId);
      const res = await API.post(`/delete-requests/${reqId}/approve`);
      setToastMessage(res.data?.message || 'Delete request approved and record permanently deleted.');
      setTimeout(() => setToastMessage(''), 4000);
      await fetchDeleteRequests();
    } catch (err) {
      console.error(err);
      setToastMessage(err.response?.data?.detail || 'Failed to approve delete request.');
      setTimeout(() => setToastMessage(''), 4000);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleReject = async (reqId) => {
    try {
      setActionLoadingId(reqId);
      const res = await API.post(`/delete-requests/${reqId}/reject`, { reason: 'Rejected by Admin. Record retained.' });
      setToastMessage(res.data?.message || 'Delete request rejected. Record retained.');
      setTimeout(() => setToastMessage(''), 4000);
      await fetchDeleteRequests();
    } catch (err) {
      console.error(err);
      setToastMessage(err.response?.data?.detail || 'Failed to reject delete request.');
      setTimeout(() => setToastMessage(''), 4000);
    } finally {
      setActionLoadingId(null);
    }
  };

  const pendingCount = requests.filter(r => r.status === 'PENDING').length;
  const approvedCount = requests.filter(r => r.status === 'APPROVED').length;
  const rejectedCount = requests.filter(r => r.status === 'REJECTED').length;

  const filteredRequests = requests.filter(r => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      (r.entity_name || '').toLowerCase().includes(s) ||
      (r.entity_type || '').toLowerCase().includes(s) ||
      (r.requested_by_name || '').toLowerCase().includes(s)
    );
  });

  return (
    <div className="page-container" style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <div style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '6px' }}>
            <Link to="/dashboard" style={{ color: '#2563eb', textDecoration: 'none' }}>Dashboard</Link> / {' '}
            <span style={{ color: '#0f172a', fontWeight: 600 }}>Delete Requests & Approvals</span>
          </div>
          <h1 className="page-title" style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <ShieldCheck size={26} style={{ color: '#2563eb' }} />
            <span>Delete Approval Queue</span>
          </h1>
          <p className="page-subtitle" style={{ fontSize: '0.9rem', color: '#64748b' }}>
            {isAdmin 
              ? 'Admin Final Authority: Review manager deletion requests. Permanently delete records or reject requests.'
              : 'Track your submitted deletion requests and status.'}
          </p>
        </div>

        <button onClick={fetchDeleteRequests} className="btn btn-outline" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          <span>Refresh Queue</span>
        </button>
      </div>

      {toastMessage && (
        <div className="alert alert-success" style={{ backgroundColor: '#d1fae5', color: '#047857', border: '1px solid #a7f3d0', padding: '12px 16px', borderRadius: '10px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Check size={18} />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Metrics Banner */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div className="content-card" style={{ padding: '16px 20px', background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
          <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Pending Approval</span>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#d97706', marginTop: '4px' }}>🟡 {pendingCount}</div>
        </div>
        <div className="content-card" style={{ padding: '16px 20px', background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
          <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Approved & Deleted</span>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#059669', marginTop: '4px' }}>🟢 {approvedCount}</div>
        </div>
        <div className="content-card" style={{ padding: '16px 20px', background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
          <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Rejected Requests</span>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#dc2626', marginTop: '4px' }}>🔴 {rejectedCount}</div>
        </div>
      </div>

      {/* Toolbar / Filters */}
      <div style={{ 
        display: 'flex', 
        gap: '12px', 
        flexWrap: 'wrap', 
        marginBottom: '20px', 
        alignItems: 'center', 
        background: '#ffffff', 
        padding: '14px 16px', 
        borderRadius: '12px', 
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)'
      }}>
        <div style={{ flex: '1 1 280px', minWidth: '220px', position: 'relative' }}>
          <Search size={17} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
          <input 
            type="text" 
            placeholder="Search by target record, entity type, or manager name..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ 
              width: '100%', 
              padding: '9px 12px 9px 36px', 
              borderRadius: '8px', 
              border: '1px solid #cbd5e1', 
              fontSize: '0.85rem',
              backgroundColor: '#f8fafc',
              outline: 'none',
              boxSizing: 'border-box'
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <select 
            value={statusFilter} 
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ 
              width: 'auto', 
              minWidth: '210px', 
              padding: '9px 12px', 
              borderRadius: '8px', 
              border: '1px solid #cbd5e1', 
              fontSize: '0.85rem',
              backgroundColor: '#ffffff',
              cursor: 'pointer'
            }}
          >
            <option value="">All Statuses</option>
            <option value="PENDING">Pending Admin Approval</option>
            <option value="APPROVED">Approved (Deleted)</option>
            <option value="REJECTED">Rejected (Retained)</option>
          </select>

          {(search || statusFilter) && (
            <button
              type="button"
              onClick={() => {
                setSearch('');
                setStatusFilter('');
              }}
              className="btn btn-outline"
              style={{
                padding: '8px 12px',
                fontSize: '0.82rem',
                borderRadius: '8px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                color: '#64748b',
                cursor: 'pointer',
                backgroundColor: '#ffffff'
              }}
              title="Clear search and filter"
            >
              <X size={14} /> Clear
            </button>
          )}
        </div>
      </div>

      {/* Requests Table */}
      <div className="content-card" style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="custom-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b', textAlign: 'left' }}>
                <th style={{ padding: '12px 16px' }}>Target Record & Type</th>
                <th style={{ padding: '12px 16px' }}>Requested By</th>
                <th style={{ padding: '12px 16px' }}>Reason / Notes</th>
                <th style={{ padding: '12px 16px' }}>Request Status</th>
                <th style={{ padding: '12px 16px' }}>Requested Date</th>
                {isAdmin && <th style={{ padding: '12px 16px', textAlign: 'right' }}>Admin Final Authority</th>}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={isAdmin ? 6 : 5} style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
                    <RefreshCw size={24} className="spin" style={{ margin: '0 auto 8px auto', color: '#2563eb' }} />
                    <p>Loading deletion approval queue...</p>
                  </td>
                </tr>
              ) : filteredRequests.length === 0 ? (
                <tr>
                  <td colSpan={isAdmin ? 6 : 5} style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
                    No deletion requests match selected filters.
                  </td>
                </tr>
              ) : (
                filteredRequests.map(req => {
                  const isPending = req.status === 'PENDING';
                  const isApproved = req.status === 'APPROVED';

                  return (
                    <tr key={req.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ fontWeight: 700, color: '#0f172a' }}>{req.entity_name || `Record #${req.entity_id}`}</div>
                        <span style={{ fontSize: '0.72rem', fontWeight: 800, padding: '2px 8px', borderRadius: '4px', background: '#eff6ff', color: '#2563eb', display: 'inline-block', marginTop: '4px' }}>
                          {req.entity_type} #{req.entity_id}
                        </span>
                      </td>

                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ fontWeight: 600, color: '#0f172a' }}>{req.requested_by_name || 'Manager'}</div>
                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{req.requested_by_role || 'MANAGER'}</div>
                      </td>

                      <td style={{ padding: '12px 16px', color: '#334155' }}>
                        <div style={{ maxWidth: '280px', fontSize: '0.82rem' }}>{req.reason || 'Requested deletion'}</div>
                        {req.review_notes && (
                          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px', fontStyle: 'italic' }}>
                            Admin Note: {req.review_notes}
                          </div>
                        )}
                      </td>

                      <td style={{ padding: '12px 16px' }}>
                        <span style={{
                          padding: '4px 12px',
                          borderRadius: '12px',
                          fontSize: '0.75rem',
                          fontWeight: 800,
                          backgroundColor: isPending ? '#fef3c7' : isApproved ? '#d1fae5' : '#fee2e2',
                          color: isPending ? '#d97706' : isApproved ? '#047857' : '#dc2626'
                        }}>
                          {isPending ? '🟡 Pending Admin Approval' : isApproved ? '🟢 Approved & Deleted' : '🔴 Rejected'}
                        </span>
                      </td>

                      <td style={{ padding: '12px 16px', color: '#64748b' }}>
                        <div style={{ fontSize: '0.8rem' }}>{new Date(req.created_at).toLocaleDateString()}</div>
                        <div style={{ fontSize: '0.72rem' }}>{new Date(req.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                      </td>

                      {isAdmin && (
                        <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                          {isPending ? (
                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                              <button
                                onClick={() => handleApprove(req.id)}
                                disabled={actionLoadingId === req.id}
                                className="btn btn-primary"
                                style={{ padding: '5px 12px', fontSize: '0.78rem', backgroundColor: '#059669', borderColor: '#059669', display: 'flex', alignItems: 'center', gap: '4px' }}
                              >
                                <Check size={14} /> Approve & Delete
                              </button>
                              <button
                                onClick={() => handleReject(req.id)}
                                disabled={actionLoadingId === req.id}
                                className="btn btn-outline"
                                style={{ padding: '5px 12px', fontSize: '0.78rem', color: '#dc2626', borderColor: '#fca5a5', display: 'flex', alignItems: 'center', gap: '4px' }}
                              >
                                <X size={14} /> Reject
                              </button>
                            </div>
                          ) : (
                            <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                              Reviewed by {req.reviewed_by_name || 'Admin'}
                            </span>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DeleteRequestsPage;
