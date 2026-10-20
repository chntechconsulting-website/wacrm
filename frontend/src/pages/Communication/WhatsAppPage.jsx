import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import WhatsAppChatPanel from '../../components/WhatsApp/WhatsAppChatPanel';
import { 
  MessageCircle, 
  Search, 
  Phone, 
  AlertCircle,
  Archive,
  UserCheck,
  CheckCircle,
  Filter
} from 'lucide-react';

const WhatsAppPage = () => {
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [showMobileChat, setShowMobileChat] = useState(false);
  const [activeTab, setActiveTab] = useState('all'); // all, unread, my, archived
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [configured, setConfigured] = useState(true);
  const [totalUnread, setTotalUnread] = useState(0);

  const fetchConfigStatus = async () => {
    try {
      const res = await API.get('/whatsapp/config-status');
      setConfigured(res.data.configured);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchConversations = async () => {
    try {
      setLoading(true);
      const params = { tab: activeTab };
      if (search) params.search = search;

      const res = await API.get('/whatsapp/conversations', { params });
      setConversations(res.data);
      
      const unreads = res.data.reduce((acc, c) => acc + (c.unread_count || 0), 0);
      setTotalUnread(unreads);

      if (res.data.length > 0 && !activeConvId) {
        setActiveConvId(res.data[0].id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfigStatus();
    fetchConversations();
  }, [activeTab, search]);

  const activeConv = conversations.find(c => c.id === activeConvId) || conversations[0];

  return (
    <div className="page-container" style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 90px)' }}>
      {/* Header */}
      <div className="page-header" style={{ marginBottom: '14px' }}>
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MessageCircle size={26} style={{ color: '#25d366' }} />
            WhatsApp Business Inbox
          </h1>
          <p className="page-subtitle">Engage with prospects, manage unread chats, send templates, and sync lead timeline activities.</p>
        </div>

        <div className="header-actions">
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 14px',
            borderRadius: '20px',
            backgroundColor: configured ? 'rgba(37, 211, 102, 0.12)' : 'rgba(239, 68, 68, 0.12)',
            border: `1px solid ${configured ? '#25d366' : '#ef4444'}`
          }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: configured ? '#25d366' : '#ef4444' }} />
            <span style={{ fontSize: '0.82rem', fontWeight: 600, color: configured ? '#15803d' : '#b91c1c' }}>
              {configured ? 'WhatsApp API Connected' : 'WhatsApp integration not configured'}
            </span>
          </div>
        </div>
      </div>

      {/* Main WhatsApp Layout */}
      <div className="content-card whatsapp-inbox-wrapper">
        {/* Left List Pane */}
        <div className={`whatsapp-list-pane ${showMobileChat ? 'mobile-hidden' : ''}`}>
          {/* Tabs */}
          <div style={{ padding: '12px 12px 0 12px', display: 'flex', gap: '4px', borderBottom: '1px solid #e2e8f0', backgroundColor: '#ffffff' }}>
            <button
              type="button"
              onClick={() => setActiveTab('all')}
              style={{
                flex: 1, padding: '8px 4px', fontSize: '0.78rem', fontWeight: 600,
                borderBottom: activeTab === 'all' ? '3px solid #25d366' : '3px solid transparent',
                color: activeTab === 'all' ? '#0f172a' : '#64748b',
                background: 'none', borderTop: 'none', borderLeft: 'none', borderRight: 'none', cursor: 'pointer'
              }}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('unread')}
              style={{
                flex: 1, padding: '8px 4px', fontSize: '0.78rem', fontWeight: 600,
                borderBottom: activeTab === 'unread' ? '3px solid #25d366' : '3px solid transparent',
                color: activeTab === 'unread' ? '#0f172a' : '#64748b',
                background: 'none', borderTop: 'none', borderLeft: 'none', borderRight: 'none', cursor: 'pointer'
              }}
            >
              Unread {totalUnread > 0 && `(${totalUnread})`}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('my')}
              style={{
                flex: 1, padding: '8px 4px', fontSize: '0.78rem', fontWeight: 600,
                borderBottom: activeTab === 'my' ? '3px solid #25d366' : '3px solid transparent',
                color: activeTab === 'my' ? '#0f172a' : '#64748b',
                background: 'none', borderTop: 'none', borderLeft: 'none', borderRight: 'none', cursor: 'pointer'
              }}
            >
              My Chats
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('archived')}
              style={{
                flex: 1, padding: '8px 4px', fontSize: '0.78rem', fontWeight: 600,
                borderBottom: activeTab === 'archived' ? '3px solid #25d366' : '3px solid transparent',
                color: activeTab === 'archived' ? '#0f172a' : '#64748b',
                background: 'none', borderTop: 'none', borderLeft: 'none', borderRight: 'none', cursor: 'pointer'
              }}
            >
              Archived
            </button>
          </div>

          {/* Search Box */}
          <div style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', backgroundColor: '#ffffff' }}>
            <div className="search-box" style={{ maxWidth: '100%' }}>
              <Search size={16} className="search-icon" />
              <input 
                type="text" 
                placeholder="Search contact, phone or message..." 
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ fontSize: '0.82rem', padding: '8px 12px 8px 34px' }}
              />
            </div>
          </div>

          {/* Conversations List */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {loading ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
                Loading conversations...
              </div>
            ) : conversations.length === 0 ? (
              <div style={{ padding: '30px 16px', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
                <MessageCircle size={28} style={{ opacity: 0.4, marginBottom: '8px' }} />
                <p style={{ margin: 0, fontWeight: 600 }}>No conversations found.</p>
                <p style={{ margin: '4px 0 0 0', fontSize: '0.78rem' }}>Incoming messages will automatically appear here.</p>
              </div>
            ) : (
              conversations.map((conv) => {
                const isActive = conv.id === activeConvId;
                return (
                  <div
                    key={conv.id}
                    onClick={() => {
                      setActiveConvId(conv.id);
                      setShowMobileChat(true);
                    }}
                    style={{
                      padding: '12px 16px',
                      borderBottom: '1px solid #f1f5f9',
                      cursor: 'pointer',
                      backgroundColor: isActive ? '#ffffff' : 'transparent',
                      borderLeft: isActive ? '4px solid #25d366' : '4px solid transparent',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#0f172a' }}>
                        {conv.contact_name || conv.lead_name || conv.phone}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                        {new Date(conv.last_message_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <p style={{ fontSize: '0.78rem', color: '#64748b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '210px', margin: 0 }}>
                        {conv.last_message_text || 'No messages yet'}
                      </p>
                      {conv.unread_count > 0 && (
                        <span style={{
                          backgroundColor: '#25d366',
                          color: '#ffffff',
                          borderRadius: '50%',
                          width: '18px', height: '18px',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: '0.7rem', fontWeight: 700
                        }}>
                          {conv.unread_count}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Active Chat Panel */}
        <div className={`whatsapp-chat-pane ${!showMobileChat ? 'mobile-hidden' : ''}`}>
          {activeConvId ? (
            <WhatsAppChatPanel 
              conversationId={activeConvId}
              onConversationUpdated={fetchConversations}
              onBack={() => setShowMobileChat(false)}
            />
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: '#64748b' }}>
              <MessageCircle size={48} style={{ color: '#25d366', opacity: 0.5, marginBottom: '12px' }} />
              <p style={{ fontWeight: 600, fontSize: '1rem', margin: 0 }}>Select a WhatsApp conversation</p>
              <p style={{ fontSize: '0.82rem', margin: '4px 0 0 0' }}>Or view lead details to start a chat with any lead.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default WhatsAppPage;
