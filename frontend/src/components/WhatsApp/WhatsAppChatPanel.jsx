import React, { useState, useEffect, useRef } from 'react';
import API from '../../services/api';
import { 
  Send, 
  CheckCheck, 
  Phone, 
  AlertCircle, 
  FileText, 
  Image as ImageIcon, 
  Paperclip,
  CheckCircle,
  Archive,
  RefreshCw,
  ArrowLeft
} from 'lucide-react';
import PingoMascot from '../Common/PingoMascot';

const QUICK_TEMPLATES = [
  { name: 'hello_world', label: 'Greeting Template', text: 'Hello! Thank you for connecting with us.' },
  { name: 'catalog_inquiry', label: 'Catalog Link', text: 'Here is our full product catalog and pricing guide.' },
  { name: 'demo_scheduled', label: 'Demo Confirmation', text: 'Your live demo session has been scheduled successfully.' },
  { name: 'follow_up', label: 'Follow-up Note', text: 'Following up regarding your recent inquiry with WaCRM.' }
];

const WhatsAppChatPanel = ({ conversationId, leadId, leadPhone, leadName, onConversationUpdated, onBack }) => {
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [configured, setConfigured] = useState(true);
  
  // Message Form State
  const [messageType, setMessageType] = useState('TEXT'); // TEXT, TEMPLATE, IMAGE, DOCUMENT
  const [textInput, setTextInput] = useState('');
  const [mediaUrlInput, setMediaUrlInput] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('hello_world');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const checkConfigStatus = async () => {
    try {
      const res = await API.get('/whatsapp/config-status');
      setConfigured(res.data.configured);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchConversationData = async () => {
    try {
      setLoading(true);
      setError('');
      let res;
      if (conversationId) {
        res = await API.get(`/whatsapp/conversations/${conversationId}`);
      } else if (leadId) {
        res = await API.get(`/whatsapp/conversations/by-lead/${leadId}`);
      }

      if (res && res.data) {
        setConversation(res.data);
        setMessages(res.data.messages || []);
        if (onConversationUpdated) onConversationUpdated();
      }
    } catch (err) {
      console.error(err);
      setError('Failed to load conversation history.');
    } finally {
      setLoading(false);
      setTimeout(scrollToBottom, 100);
    }
  };

  useEffect(() => {
    checkConfigStatus();
    if (conversationId || leadId) {
      fetchConversationData();
    }
  }, [conversationId, leadId]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (messageType === 'TEXT' && !textInput.trim()) return;
    if ((messageType === 'IMAGE' || messageType === 'DOCUMENT') && !mediaUrlInput.trim()) return;

    try {
      setSending(true);
      const payload = {
        phone: conversation?.phone || leadPhone,
        lead_id: conversation?.lead_id || leadId,
        message_type: messageType,
        body: textInput,
        media_url: mediaUrlInput || null,
        template_name: messageType === 'TEMPLATE' ? selectedTemplate : null
      };

      const res = await API.post('/whatsapp/send-message', payload);
      
      if (res.data.success) {
        setSuccess('WhatsApp message sent!');
        setTextInput('');
        setMediaUrlInput('');
        setMessageType('TEXT');
        fetchConversationData();
      } else {
        setError(res.data.error || 'Failed to send WhatsApp message.');
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'WhatsApp integration not configured or API request failed.');
    } finally {
      setSending(false);
    }
  };

  const handleArchiveToggle = async () => {
    if (!conversation) return;
    try {
      await API.put(`/whatsapp/conversations/${conversation.id}/archive?archive=${!conversation.is_archived}`);
      fetchConversationData();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: '#ffffff' }}>
      {/* WhatsApp Configuration Warning Banner */}
      {!configured && (
        <div style={{
          backgroundColor: 'rgba(239, 68, 68, 0.12)',
          color: '#b91c1c',
          padding: '10px 16px',
          borderBottom: '1px solid rgba(239,68,68,0.2)',
          fontSize: '0.85rem',
          fontWeight: '600',
          display: 'flex',
          alignItems: 'center',
          justify: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle size={18} />
            <span>WhatsApp integration not configured. Credentials missing in .env.</span>
          </div>
          <span style={{ fontSize: '0.75rem', textDecoration: 'underline' }}>Configure WHATSAPP_API_TOKEN</span>
        </div>
      )}

      {/* Header */}
      <div style={{
        padding: '14px 20px',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        justify: 'space-between',
        alignItems: 'center',
        backgroundColor: '#f8fafc'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="btn btn-outline"
              style={{
                padding: '6px 10px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: '#475569'
              }}
              title="Back to conversation list"
            >
              <ArrowLeft size={16} />
              <span>Back</span>
            </button>
          )}
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '50%',
            backgroundColor: '#25d366',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justify: 'center',
            fontWeight: 700,
            fontSize: '1.1rem'
          }}>
            {(conversation?.contact_name || leadName || 'W')[0].toUpperCase()}
          </div>
          <div>
            <h4 style={{ fontSize: '0.98rem', fontWeight: 700, margin: 0, color: '#0f172a' }}>
              {conversation?.contact_name || leadName || 'WhatsApp Contact'}
            </h4>
            <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
              {conversation?.phone || leadPhone || '-'}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button 
            type="button"
            onClick={fetchConversationData} 
            className="btn btn-outline"
            style={{ padding: '6px 10px', fontSize: '0.8rem' }}
            title="Refresh Conversation"
          >
            <RefreshCw size={14} />
          </button>
          {conversation && (
            <button 
              type="button"
              onClick={handleArchiveToggle}
              className="btn btn-outline"
              style={{ padding: '6px 10px', fontSize: '0.8rem' }}
              title={conversation.is_archived ? "Unarchive" : "Archive"}
            >
              <Archive size={14} /> {conversation.is_archived ? 'Unarchive' : 'Archive'}
            </button>
          )}
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div style={{ padding: '8px 16px', backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#dc2626', fontSize: '0.82rem', borderBottom: '1px solid rgba(239,68,68,0.2)' }}>
          <AlertCircle size={14} style={{ display: 'inline', marginRight: '6px' }} /> {error}
        </div>
      )}

      {/* Messages Timeline */}
      <div style={{
        flex: 1,
        padding: '20px',
        overflowY: 'auto',
        backgroundColor: '#efeae2',
        backgroundImage: 'radial-gradient(#d1d5db 1px, transparent 1px)',
        backgroundSize: '16px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        minHeight: '260px'
      }}>
        {loading ? (
          <div style={{ textAlign: 'center', color: '#64748b', fontSize: '0.85rem', marginTop: '20px' }}>
            Loading WhatsApp messages...
          </div>
        ) : messages.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#64748b', fontSize: '0.85rem', padding: '24px 16px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <PingoMascot pose="point-side" height={100} withShadow={true} />
            <p style={{ margin: '12px 0 0 0', fontWeight: 700, color: '#0f172a' }}>No WhatsApp messages yet</p>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.78rem', maxWidth: '280px' }}>Start the conversation by sending a warm greeting or choosing a quick template below.</p>
          </div>
        ) : (
          messages.map((msg) => {
            const isOutbound = msg.direction === 'OUTBOUND';
            return (
              <div 
                key={msg.id}
                style={{
                  alignSelf: isOutbound ? 'flex-end' : 'flex-start',
                  backgroundColor: isOutbound ? '#d9fdd3' : '#ffffff',
                  padding: '10px 14px',
                  borderRadius: '12px',
                  maxWidth: '75%',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
                  wordBreak: 'break-word'
                }}
              >
                {msg.sender_employee_name && isOutbound && (
                  <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#166534', marginBottom: '4px' }}>
                    {msg.sender_employee_name}
                  </div>
                )}

                {msg.message_type === 'IMAGE' && msg.media_url && (
                  <div style={{ marginBottom: '6px' }}>
                    <img src={msg.media_url} alt="WhatsApp attachment" style={{ maxWidth: '100%', borderRadius: '8px' }} />
                  </div>
                )}

                {msg.message_type === 'DOCUMENT' && msg.media_url && (
                  <div style={{ marginBottom: '6px', background: 'rgba(0,0,0,0.05)', padding: '6px 10px', borderRadius: '6px' }}>
                    <a href={msg.media_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#2563eb', fontWeight: 600 }}>
                      📎 Document Attachment
                    </a>
                  </div>
                )}

                <p style={{ margin: 0, fontSize: '0.88rem', color: '#0f172a', whiteSpace: 'pre-wrap' }}>
                  {msg.body}
                </p>

                <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '4px', marginTop: '4px', fontSize: '0.68rem', color: '#64748b' }}>
                  <span>{new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  {isOutbound && (
                    <CheckCheck 
                      size={14} 
                      style={{ color: msg.status === 'READ' ? '#53bdeb' : (msg.status === 'FAILED' ? '#ef4444' : '#94a3b8') }} 
                    />
                  )}
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Type Selector & Templates */}
      <div style={{ padding: '8px 16px', borderTop: '1px solid #e2e8f0', backgroundColor: '#f8fafc', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          type="button"
          onClick={() => setMessageType('TEXT')}
          style={{
            padding: '4px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: '600',
            backgroundColor: messageType === 'TEXT' ? '#25d366' : '#e2e8f0',
            color: messageType === 'TEXT' ? '#ffffff' : '#334155',
            border: 'none', cursor: 'pointer'
          }}
        >
          Text Message
        </button>

        <button
          type="button"
          onClick={() => setMessageType('TEMPLATE')}
          style={{
            padding: '4px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: '600',
            backgroundColor: messageType === 'TEMPLATE' ? '#25d366' : '#e2e8f0',
            color: messageType === 'TEMPLATE' ? '#ffffff' : '#334155',
            border: 'none', cursor: 'pointer'
          }}
        >
          Template
        </button>

        <button
          type="button"
          onClick={() => setMessageType('IMAGE')}
          style={{
            padding: '4px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: '600',
            backgroundColor: messageType === 'IMAGE' ? '#25d366' : '#e2e8f0',
            color: messageType === 'IMAGE' ? '#ffffff' : '#334155',
            border: 'none', cursor: 'pointer'
          }}
        >
          Image URL
        </button>

        <button
          type="button"
          onClick={() => setMessageType('DOCUMENT')}
          style={{
            padding: '4px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: '600',
            backgroundColor: messageType === 'DOCUMENT' ? '#25d366' : '#e2e8f0',
            color: messageType === 'DOCUMENT' ? '#ffffff' : '#334155',
            border: 'none', cursor: 'pointer'
          }}
        >
          Document URL
        </button>
      </div>

      {/* Input Form Area */}
      <form onSubmit={handleSendMessage} style={{ padding: '14px 16px', borderTop: '1px solid #e2e8f0', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {messageType === 'TEMPLATE' && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <select 
              value={selectedTemplate} 
              onChange={(e) => {
                setSelectedTemplate(e.target.value);
                const matched = QUICK_TEMPLATES.find(t => t.name === e.target.value);
                if (matched) setTextInput(matched.text);
              }}
              style={{ flex: 1, padding: '8px', fontSize: '0.85rem' }}
            >
              {QUICK_TEMPLATES.map(t => (
                <option key={t.name} value={t.name}>{t.label} ({t.name})</option>
              ))}
            </select>
          </div>
        )}

        {(messageType === 'IMAGE' || messageType === 'DOCUMENT') && (
          <input 
            type="url" 
            placeholder={`Enter ${messageType.toLowerCase()} HTTPS public URL...`}
            value={mediaUrlInput}
            onChange={(e) => setMediaUrlInput(e.target.value)}
            required
            style={{ padding: '8px 12px', fontSize: '0.85rem' }}
          />
        )}

        <div style={{ display: 'flex', gap: '10px' }}>
          <input 
            type="text" 
            placeholder={messageType === 'TEMPLATE' ? "Optional template parameters / caption..." : "Type your WhatsApp message..."}
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            style={{ flex: 1, padding: '10px 14px' }}
          />
          <button 
            type="submit" 
            className="btn btn-primary" 
            disabled={sending}
            style={{ backgroundColor: '#25d366', borderColor: '#25d366', padding: '10px 20px' }}
          >
            <Send size={16} />
            <span>{sending ? 'Sending...' : 'Send'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};

export default WhatsAppChatPanel;
