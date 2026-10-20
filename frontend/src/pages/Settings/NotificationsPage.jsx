import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  Bell, 
  CheckCheck, 
  Trash2, 
  Clock, 
  UserPlus, 
  Calendar, 
  PhoneCall,
  Info,
  RefreshCw,
  ExternalLink,
  Filter,
  CheckCircle2
} from 'lucide-react';
import API from '../../services/api';

const getTypeConfig = (type) => {
  switch (type?.toUpperCase()) {
    case 'LEAD':
      return {
        label: 'New Lead',
        icon: UserPlus,
        color: '#7c3aed',
        bgColor: '#f5f3ff',
        borderColor: '#ddd6fe'
      };
    case 'FOLLOWUP':
      return {
        label: 'Follow-up',
        icon: Calendar,
        color: '#f59e0b',
        bgColor: '#fffbeb',
        borderColor: '#fde68a'
      };
    case 'CALL':
      return {
        label: 'Call Log',
        icon: PhoneCall,
        color: '#0284c7',
        bgColor: '#f0f9ff',
        borderColor: '#bae6fd'
      };
    case 'CONVERSION':
      return {
        label: 'Conversion',
        icon: CheckCircle2,
        color: '#10b981',
        bgColor: '#ecfdf5',
        borderColor: '#a7f3d0'
      };
    case 'SYSTEM':
    default:
      return {
        label: 'System Alert',
        icon: Info,
        color: '#2563eb',
        bgColor: '#eff6ff',
        borderColor: '#bfdbfe'
      };
  }
};

const formatTimeAgo = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '';
  const now = new Date();
  const diffInSeconds = Math.floor((now - date) / 1000);

  if (diffInSeconds < 60) return 'Just now';
  const minutes = Math.floor(diffInSeconds / 60);
  if (minutes < 60) return `${minutes} min${minutes > 1 ? 's' : ''} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return date.toLocaleDateString('en-IN', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    hour: '2-digit',
    minute: '2-digit'
  });
};

const NotificationsPage = () => {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [statusFilter, setStatusFilter] = useState('ALL'); // ALL, UNREAD, READ
  const [typeFilter, setTypeFilter] = useState('ALL'); // ALL, LEAD, FOLLOWUP, CALL, CONVERSION

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const res = await API.get('/notifications');
      setNotifications(res.data || []);
    } catch (err) {
      console.error('Failed to load notifications:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, []);

  const handleSyncOriginalData = async () => {
    try {
      setSyncing(true);
      await API.post('/notifications/sync');
      await fetchNotifications();
    } catch (err) {
      console.error('Failed to sync original notifications:', err);
    } finally {
      setSyncing(false);
    }
  };

  const markAllAsRead = async () => {
    try {
      await API.post('/notifications/mark-all-read');
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch (err) {
      console.error('Failed to mark all as read:', err);
    }
  };

  const clearAll = async () => {
    if (!window.confirm('Are you sure you want to clear all notifications?')) return;
    try {
      await API.delete('/notifications/clear-all');
      setNotifications([]);
    } catch (err) {
      console.error('Failed to clear notifications:', err);
    }
  };

  const toggleReadState = async (id) => {
    try {
      const res = await API.put(`/notifications/${id}/read`);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: res.data.is_read } : n));
    } catch (err) {
      console.error('Failed to toggle read state:', err);
    }
  };

  const deleteNotification = async (id, e) => {
    e.stopPropagation();
    try {
      await API.delete(`/notifications/${id}`);
      setNotifications(prev => prev.filter(n => n.id !== id));
    } catch (err) {
      console.error('Failed to delete notification:', err);
    }
  };

  const filteredNotifications = notifications.filter(n => {
    if (statusFilter === 'UNREAD' && n.is_read) return false;
    if (statusFilter === 'READ' && !n.is_read) return false;
    if (typeFilter !== 'ALL' && n.notification_type?.toUpperCase() !== typeFilter) return false;
    return true;
  });

  const unreadCount = notifications.filter(n => !n.is_read).length;
  const readCount = notifications.filter(n => n.is_read).length;

  return (
    <div className="page-container" style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px 20px' }}>
      {/* Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
        <div>
          <div style={{ fontSize: '0.82rem', color: '#64748b', marginBottom: '6px' }}>
            <Link to="/dashboard" style={{ color: '#2563eb', textDecoration: 'none' }}>Dashboard</Link> / {' '}
            <span style={{ color: '#0f172a', fontWeight: 600 }}>Notifications</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 className="page-title" style={{ margin: 0, fontSize: '1.6rem', fontWeight: 700, color: '#0f172a' }}>
              Notification Center
            </h1>
            {unreadCount > 0 && (
              <span style={{ 
                backgroundColor: '#ef4444', 
                color: '#fff', 
                fontSize: '0.75rem', 
                fontWeight: 700, 
                padding: '2px 8px', 
                borderRadius: '12px' 
              }}>
                {unreadCount} new
              </span>
            )}
          </div>
          <p className="page-subtitle" style={{ margin: '4px 0 0 0', color: '#64748b', fontSize: '0.88rem' }}>
            Original CRM alerts, real Meta/Website leads, scheduled follow-ups, and live call logs.
          </p>
        </div>
        
        {/* Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <button 
            onClick={handleSyncOriginalData} 
            disabled={syncing}
            className="btn btn-outline"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', padding: '8px 14px' }}
            title="Resync notifications from actual CRM database records"
          >
            <RefreshCw size={15} className={syncing ? 'spin-animation' : ''} />
            <span>{syncing ? 'Syncing...' : 'Sync Original Data'}</span>
          </button>
          
          <button 
            onClick={markAllAsRead} 
            disabled={unreadCount === 0}
            className="btn btn-outline"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', padding: '8px 14px' }}
          >
            <CheckCheck size={16} />
            <span>Mark All Read</span>
          </button>

          <button 
            onClick={clearAll} 
            disabled={notifications.length === 0}
            className="btn btn-secondary" 
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', padding: '8px 14px', color: '#dc2626', borderColor: '#fecaca', backgroundColor: '#fef2f2' }}
          >
            <Trash2 size={16} />
            <span>Clear All</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs & Categories */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        flexWrap: 'wrap', 
        gap: '12px', 
        marginBottom: '20px',
        padding: '14px 18px',
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
      }}>
        {/* Read / Unread Status Filter */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          <button 
            onClick={() => setStatusFilter('ALL')}
            className={`btn ${statusFilter === 'ALL' ? 'btn-primary' : 'btn-outline'}`}
            style={{ fontSize: '0.82rem', padding: '6px 12px' }}
          >
            All ({notifications.length})
          </button>
          <button 
            onClick={() => setStatusFilter('UNREAD')}
            className={`btn ${statusFilter === 'UNREAD' ? 'btn-primary' : 'btn-outline'}`}
            style={{ fontSize: '0.82rem', padding: '6px 12px' }}
          >
            Unread ({unreadCount})
          </button>
          <button 
            onClick={() => setStatusFilter('READ')}
            className={`btn ${statusFilter === 'READ' ? 'btn-primary' : 'btn-outline'}`}
            style={{ fontSize: '0.82rem', padding: '6px 12px' }}
          >
            Read ({readCount})
          </button>
        </div>

        {/* Type Category Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.8rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Filter size={13} /> Filter:
          </span>
          <select 
            value={typeFilter} 
            onChange={(e) => setTypeFilter(e.target.value)}
            style={{
              padding: '6px 12px',
              fontSize: '0.82rem',
              borderRadius: '8px',
              border: '1px solid #cbd5e1',
              backgroundColor: '#f8fafc',
              color: '#334155',
              cursor: 'pointer'
            }}
          >
            <option value="ALL">All Categories</option>
            <option value="LEAD">Leads Only</option>
            <option value="FOLLOWUP">Follow-ups Only</option>
            <option value="CALL">Call Logs Only</option>
            <option value="CONVERSION">Conversions Only</option>
            <option value="SYSTEM">System Alerts</option>
          </select>
        </div>
      </div>

      {/* Notifications List */}
      <div className="content-card" style={{ padding: '20px', borderRadius: '14px', backgroundColor: '#ffffff', border: '1px solid #e2e8f0', boxShadow: '0 1px 4px rgba(0,0,0,0.04)' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '50px 20px', color: '#64748b' }}>
            <RefreshCw size={32} className="spin-animation" style={{ color: '#2563eb', marginBottom: '12px' }} />
            <p style={{ fontSize: '0.95rem', fontWeight: 500 }}>Loading original CRM notifications...</p>
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <div style={{ 
              width: '60px', 
              height: '60px', 
              borderRadius: '50%', 
              backgroundColor: '#f1f5f9', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              margin: '0 auto 16px' 
            }}>
              <Bell size={28} style={{ color: '#94a3b8' }} />
            </div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#0f172a', margin: '0 0 6px 0' }}>
              {statusFilter === 'ALL' && typeFilter === 'ALL' 
                ? 'No notifications found' 
                : 'No matching notifications'}
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748b', maxWidth: '420px', margin: '0 auto 20px' }}>
              {statusFilter === 'ALL' && typeFilter === 'ALL'
                ? 'Sync with your database to automatically pull in your real leads, call logs, and follow-ups.'
                : 'Try adjusting your filters or sync fresh notifications from original data.'}
            </p>
            <button 
              onClick={handleSyncOriginalData} 
              disabled={syncing}
              className="btn btn-primary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', padding: '8px 16px' }}
            >
              <RefreshCw size={15} className={syncing ? 'spin-animation' : ''} />
              <span>Resync Original CRM Data</span>
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {filteredNotifications.map(n => {
              const config = getTypeConfig(n.notification_type);
              const IconComp = config.icon;
              const timeDisplay = formatTimeAgo(n.created_at);

              return (
                <div 
                  key={n.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '14px 18px',
                    borderRadius: '10px',
                    backgroundColor: n.is_read ? '#ffffff' : '#f8faff',
                    border: `1px solid ${n.is_read ? '#e2e8f0' : '#bfdbfe'}`,
                    borderLeft: `4px solid ${n.is_read ? '#cbd5e1' : config.color}`,
                    transition: 'all 0.15s ease',
                    boxShadow: n.is_read ? 'none' : '0 2px 5px rgba(37,99,235,0.04)'
                  }}
                >
                  {/* Left: Icon & Notification Info */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', flex: 1, minWidth: 0, marginRight: '16px' }}>
                    <div style={{ 
                      width: '40px', 
                      height: '40px', 
                      borderRadius: '10px', 
                      backgroundColor: config.bgColor, 
                      border: `1px solid ${config.borderColor}`,
                      color: config.color, 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center',
                      flexShrink: 0,
                      marginTop: '2px'
                    }}>
                      <IconComp size={19} />
                    </div>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '4px' }}>
                        <span style={{ 
                          fontSize: '0.72rem', 
                          fontWeight: 700, 
                          color: config.color, 
                          backgroundColor: config.bgColor, 
                          padding: '1px 7px', 
                          borderRadius: '6px',
                          textTransform: 'uppercase',
                          letterSpacing: '0.03em'
                        }}>
                          {config.label}
                        </span>

                        <h4 style={{ 
                          fontSize: '0.92rem', 
                          fontWeight: n.is_read ? 600 : 700, 
                          color: '#0f172a', 
                          margin: 0,
                          wordBreak: 'break-word'
                        }}>
                          {n.title}
                        </h4>

                        {!n.is_read && (
                          <span style={{ 
                            width: '8px', 
                            height: '8px', 
                            borderRadius: '50%', 
                            backgroundColor: '#2563eb',
                            display: 'inline-block' 
                          }} title="Unread" />
                        )}
                      </div>

                      <p style={{ 
                        fontSize: '0.84rem', 
                        color: n.is_read ? '#64748b' : '#334155', 
                        margin: '0 0 6px 0',
                        lineHeight: 1.45,
                        wordBreak: 'break-word'
                      }}>
                        {n.message}
                      </p>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.74rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <Clock size={12} /> {timeDisplay}
                        </span>

                        {n.link_url && (
                          <Link 
                            to={n.link_url}
                            style={{ 
                              fontSize: '0.75rem', 
                              color: '#2563eb', 
                              fontWeight: 600, 
                              textDecoration: 'none',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '3px'
                            }}
                          >
                            <span>Open Details</span>
                            <ExternalLink size={12} />
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right: Actions */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                    <button 
                      onClick={() => toggleReadState(n.id)}
                      className="btn btn-outline" 
                      style={{ 
                        fontSize: '0.76rem', 
                        padding: '5px 10px',
                        backgroundColor: n.is_read ? '#f8fafc' : '#ffffff',
                        borderColor: '#cbd5e1'
                      }}
                      title={n.is_read ? 'Mark as Unread' : 'Mark as Read'}
                    >
                      {n.is_read ? 'Mark Unread' : 'Mark Read'}
                    </button>

                    <button 
                      onClick={(e) => deleteNotification(n.id, e)}
                      className="btn" 
                      style={{ 
                        padding: '6px', 
                        color: '#94a3b8', 
                        backgroundColor: 'transparent', 
                        border: 'none',
                        cursor: 'pointer',
                        borderRadius: '6px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.color = '#ef4444'; e.currentTarget.style.backgroundColor = '#fef2f2'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.color = '#94a3b8'; e.currentTarget.style.backgroundColor = 'transparent'; }}
                      title="Delete Notification"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <style>{`
        .spin-animation {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default NotificationsPage;
