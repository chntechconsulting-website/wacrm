import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import { probeAudioDuration, rewindAfterProbe } from '../../utils/audioUtils';
import { 
  X, 
  Sparkles, 
  Volume2, 
  VolumeX,
  FileText, 
  Brain, 
  CheckCircle, 
  User, 
  PhoneCall, 
  Clock,
  RefreshCw,
  Copy,
  Check,
  AlertTriangle,
  Flame,
  Target,
  Lightbulb,
  CheckCircle2,
  Calendar
} from 'lucide-react';
import { formatLocalDateTime } from '../../utils/dateUtils';
import './CallAISummaryModal.css';

const CallAISummaryModal = ({ isOpen, onClose, callLog, onSummaryGenerated }) => {
  const [loadingAI, setLoadingAI] = useState(false);
  const [activeTab, setActiveTab] = useState('summary'); // 'summary' | 'transcript'
  const [currentCall, setCurrentCall] = useState(callLog);
  const [copied, setCopied] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    setCurrentCall(callLog);
    setErrorMessage('');
  }, [callLog]);

  if (!isOpen || !currentCall) return null;

  const handleGenerateAISummary = async (force = false) => {
    try {
      setLoadingAI(true);
      setErrorMessage('');
      const url = `/ivr/calls/${currentCall.id}/ai-summary${force ? '?force=true' : ''}`;
      const res = await API.post(url);
      if (res.data) {
        setCurrentCall(res.data);
        if (onSummaryGenerated) {
          onSummaryGenerated(res.data);
        }
      }
    } catch (err) {
      console.error('Failed to generate AI summary:', err);
      setErrorMessage(err.response?.data?.detail || 'Failed to generate AI summary. Please try again.');
    } finally {
      setLoadingAI(false);
    }
  };

  const handleCopyTranscript = () => {
    const textToCopy = activeTab === 'summary' 
      ? (currentCall.ai_summary || '') 
      : (currentCall.transcript || '');
    if (!textToCopy) return;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatDuration = (sec) => {
    if (!sec || sec <= 0) return '0s';
    const mins = Math.floor(sec / 60);
    const remainingSec = sec % 60;
    if (mins === 0) return `${remainingSec}s`;
    return `${mins}m ${remainingSec}s`;
  };

  // Parse lines of transcript into dialogue items
  const parseTranscript = (raw) => {
    if (!raw) return [];
    return raw.split('\n').filter(Boolean).map((line, idx) => {
      const match = line.match(/^\[(.*?)\]:\s*(.*)$/);
      if (match) {
        return { id: idx, sender: match[1], text: match[2] };
      }
      return { id: idx, sender: 'Call Event', text: line };
    });
  };

  // Parse summary lines into structured insight blocks
  const parseSummaryBlocks = (raw) => {
    if (!raw) return [];
    const lines = raw.split('\n').filter(Boolean);
    return lines.map((line, idx) => {
      let icon = <Brain size={16} style={{ color: '#3b82f6' }} />;
      let title = 'Key Insight';
      let content = line;

      if (line.includes('KEY DISCUSSION:')) {
        icon = <Target size={16} style={{ color: '#2563eb' }} />;
        title = 'Key Discussion';
        content = line.replace(/^[^\w]*KEY DISCUSSION:\s*/i, '');
      } else if (line.includes('CUSTOMER NEED:') || line.includes('CUSTOMER STATUS:')) {
        icon = <Lightbulb size={16} style={{ color: '#eab308' }} />;
        title = line.includes('CUSTOMER NEED:') ? 'Customer Need' : 'Customer Status';
        content = line.replace(/^[^\w]*(CUSTOMER NEED|CUSTOMER STATUS):\s*/i, '');
      } else if (line.includes('SENTIMENT:')) {
        icon = <Flame size={16} style={{ color: '#10b981' }} />;
        title = 'Sentiment Analysis';
        content = line.replace(/^[^\w]*SENTIMENT:\s*/i, '');
      } else if (line.includes('ACTION ITEM:') || line.includes('NEXT STEP:')) {
        icon = <CheckCircle2 size={16} style={{ color: '#8b5cf6' }} />;
        title = 'Action Item';
        content = line.replace(/^[^\w]*(ACTION ITEM|NEXT STEP):\s*/i, '');
      }

      return { id: idx, icon, title, content };
    });
  };

  const transcriptItems = parseTranscript(currentCall.transcript);
  const summaryBlocks = parseSummaryBlocks(currentCall.ai_summary);

  const isCompleted = currentCall.call_status === 'COMPLETED' || currentCall.call_status === 'ANSWERED';
  const hasRecording = Boolean(currentCall.recording_url && currentCall.recording_url.trim() !== '');

  return (
    <div className="ai-modal-overlay" onClick={onClose}>
      <div className="ai-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="ai-modal-header">
          <div className="ai-modal-title-wrap">
            <div className="ai-brain-badge">
              <Brain size={24} />
            </div>
            <div>
              <h2 className="ai-modal-title">AI Call Review & Telephony Intelligence</h2>
              <p className="ai-modal-subtitle">
                <span>Employee: <strong>{currentCall.employee_name || 'Unassigned'}</strong></span>
                <span>&bull;</span>
                <span>Customer: <strong>{currentCall.lead_name || currentCall.to_number}</strong></span>
              </p>
            </div>
          </div>

          <button 
            type="button"
            onClick={onClose}
            className="ai-modal-close-btn"
            title="Close Review"
          >
            <X size={18} />
          </button>
        </div>

        {/* Metadata & Audio Strip */}
        <div className="ai-modal-meta-strip">
          <div className="ai-meta-pills-row">
            <div className="ai-meta-item">
              <span>Status:</span>
              <strong style={{ color: isCompleted ? '#059669' : '#dc2626' }}>
                {currentCall.call_status || 'UNKNOWN'}
              </strong>
            </div>

            <div className="ai-meta-item">
              <Clock size={14} />
              <span>Duration:</span>
              <strong>{formatDuration(currentCall.duration_seconds)}</strong>
            </div>

            <div className="ai-meta-item">
              <Calendar size={14} />
              <span>Time (IST):</span>
              <strong>{formatLocalDateTime(currentCall.started_at || currentCall.created_at)}</strong>
            </div>

            {currentCall.sentiment && (
              <span className={`ai-sentiment-badge ai-sentiment-${currentCall.sentiment.toLowerCase()}`}>
                Sentiment: {currentCall.sentiment}
              </span>
            )}
          </div>

          {/* Audio Player or No Audio Banner */}
          {hasRecording ? (
            <div className="ai-audio-box">
              <div className="ai-audio-icon">
                <Volume2 size={20} />
              </div>
              <div className="ai-audio-player-wrap">
                <div className="ai-audio-label">Call Audio Recording Playback</div>
                <audio 
                  controls 
                  src={currentCall.recording_url} 
                  className="ai-native-audio"
                  preload="metadata"
                  onLoadedMetadata={(e) => probeAudioDuration(e.currentTarget)}
                  onDurationChange={(e) => rewindAfterProbe(e.currentTarget)}
                  onTimeUpdate={(e) => rewindAfterProbe(e.currentTarget)}
                />
              </div>
            </div>
          ) : (
            <div className="ai-no-audio-box">
              <VolumeX size={18} />
              <span>
                <strong>No audio recording stream available for this session</strong> — Audio recording was not captured or published by Doocti PBX for this trunk.
              </span>
            </div>
          )}
        </div>

        {/* Tab Navigation */}
        <div className="ai-modal-tabs">
          <button
            type="button"
            onClick={() => setActiveTab('summary')}
            className={`ai-tab-btn ${activeTab === 'summary' ? 'active' : ''}`}
          >
            <Sparkles size={16} />
            <span>AI Executive Summary</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('transcript')}
            className={`ai-tab-btn ${activeTab === 'transcript' ? 'active' : ''}`}
          >
            <FileText size={16} />
            <span>Full Transcript</span>
          </button>
        </div>

        {/* Error Banner if any */}
        {errorMessage && (
          <div style={{ margin: '12px 26px 0', padding: '10px 14px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '10px', color: '#b91c1c', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Modal Body */}
        <div className="ai-modal-body">
          {activeTab === 'summary' ? (
            <div>
              {currentCall.ai_summary ? (
                <div className="ai-summary-grid">
                  {summaryBlocks.map((block) => (
                    <div key={block.id} className="ai-insight-card">
                      <div className="ai-insight-header">
                        {block.icon}
                        <span>{block.title}</span>
                      </div>
                      <div className="ai-insight-body">
                        {block.content}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="ai-empty-state">
                  <div className="ai-empty-icon-wrap">
                    <Brain size={34} />
                  </div>
                  <h3 className="ai-empty-title">No AI Intelligence Generated Yet</h3>
                  <p className="ai-empty-desc">
                    Analyze this call to automatically extract discussion highlights, customer requirements, sentiment classification, and action items.
                  </p>
                  <button
                    type="button"
                    onClick={() => handleGenerateAISummary(false)}
                    disabled={loadingAI}
                    className="btn-generate-ai"
                  >
                    <Sparkles size={16} className={loadingAI ? 'spin-icon' : ''} />
                    <span>{loadingAI ? 'Analyzing Call Conversation...' : 'Generate AI Summary & Transcript'}</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div>
              {currentCall.transcript ? (
                <div className="ai-transcript-list">
                  {transcriptItems.map((item) => {
                    const isAgent = item.sender.toLowerCase().includes('admin') || 
                                    item.sender.toLowerCase().includes('agent') || 
                                    item.sender.toLowerCase().includes('system administrator') ||
                                    item.sender.toLowerCase().includes('sales');
                    return (
                      <div key={item.id} className="ai-transcript-item">
                        <div className={`ai-transcript-avatar ${isAgent ? 'agent' : 'customer'}`}>
                          {item.sender.slice(0, 2).toUpperCase()}
                        </div>
                        <div className={`ai-transcript-bubble ${isAgent ? 'agent-bubble' : ''}`}>
                          <div className="ai-transcript-sender-row">
                            <span className="ai-transcript-sender-name">{item.sender}</span>
                          </div>
                          <div className="ai-transcript-text">{item.text}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="ai-empty-state">
                  <div className="ai-empty-icon-wrap">
                    <FileText size={34} />
                  </div>
                  <h3 className="ai-empty-title">No Transcript Available</h3>
                  <p className="ai-empty-desc">
                    Convert call audio into dialogue speaker turns with speech-to-text intelligence.
                  </p>
                  <button
                    type="button"
                    onClick={() => handleGenerateAISummary(false)}
                    disabled={loadingAI}
                    className="btn-generate-ai"
                  >
                    <Sparkles size={16} className={loadingAI ? 'spin-icon' : ''} />
                    <span>{loadingAI ? 'Transcribing Call Dialogue...' : 'Generate Call Transcript'}</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="ai-modal-footer">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              type="button"
              onClick={() => handleGenerateAISummary(true)}
              disabled={loadingAI}
              className="btn-reanalyze"
              title="Force re-analyze this call log with updated context"
            >
              <RefreshCw size={14} className={loadingAI ? 'spin-icon' : ''} />
              <span>{loadingAI ? 'Re-analyzing...' : 'Re-analyze Call'}</span>
            </button>

            {(currentCall.ai_summary || currentCall.transcript) && (
              <button
                type="button"
                onClick={handleCopyTranscript}
                className="btn-reanalyze"
                title="Copy contents to clipboard"
              >
                {copied ? <Check size={14} style={{ color: '#059669' }} /> : <Copy size={14} />}
                <span>{copied ? 'Copied!' : 'Copy to Clipboard'}</span>
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={onClose}
            className="btn-done-reviewing"
          >
            Done Reviewing
          </button>
        </div>
      </div>
    </div>
  );
};

export default CallAISummaryModal;
