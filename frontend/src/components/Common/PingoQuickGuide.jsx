import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import PingoMascot from './PingoMascot';
import { 
  Sparkles, 
  X, 
  PlusCircle, 
  PhoneCall, 
  Clock, 
  FileText, 
  MessageCircle, 
  TrendingUp,
  HelpCircle
} from 'lucide-react';
import './PingoQuickGuide.css';

const PINGO_TIPS = [
  "Fast follow-ups convert up to 391% better when called within 15 minutes of inquiry!",
  "Always log notes immediately after each call so client preferences are saved.",
  "Turn every conversation into an opportunity by sharing official WA! Quotations.",
  "Check your Follow-up Reminders at the start of every shift to prioritize hot leads.",
  "Send WhatsApp order confirmations and brochures directly from the chat panel."
];

const PingoQuickGuide = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [tipIndex, setTipIndex] = useState(0);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    // Pick a daily tip based on day of month
    const day = new Date().getDate();
    setTipIndex(day % PINGO_TIPS.length);
  }, []);

  // Close when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleAction = (path) => {
    setIsOpen(false);
    navigate(path);
  };

  return (
    <div className="pingo-guide-wrapper" ref={dropdownRef}>
      <button
        type="button"
        className={`pingo-guide-trigger ${isOpen ? 'active' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        title="Pingo CRM Assistant & Quick Actions"
      >
        <PingoMascot pose="walk" height={32} withShadow={false} />
        <span className="pingo-guide-trigger-label">Pingo</span>
        <span className="pingo-guide-trigger-badge">Tips</span>
      </button>

      {isOpen && (
        <div className="pingo-guide-card">
          <div className="pingo-guide-card-header">
            <div className="pingo-guide-header-left">
              <PingoMascot pose="idea" height={48} withShadow={false} />
              <div>
                <h4 className="pingo-guide-name">Pingo CRM Guide</h4>
                <p className="pingo-guide-sub">Your sales assistant & shortcut launcher</p>
              </div>
            </div>
            <button
              type="button"
              className="pingo-guide-close"
              onClick={() => setIsOpen(false)}
            >
              <X size={16} />
            </button>
          </div>

          <div className="pingo-guide-tip-box">
            <div className="pingo-guide-tip-header">
              <Sparkles size={14} className="pingo-guide-tip-icon" />
              <span>Pingo's Pro Tip</span>
            </div>
            <p className="pingo-guide-tip-text">
              “{PINGO_TIPS[tipIndex]}”
            </p>
          </div>

          <div className="pingo-guide-actions-list">
            <div className="pingo-guide-actions-title">Quick Actions</div>
            <button
              type="button"
              className="pingo-guide-action-item"
              onClick={() => handleAction('/leads/create')}
            >
              <div className="pingo-action-icon bg-blue">
                <PlusCircle size={15} />
              </div>
              <div className="pingo-action-info">
                <strong>New Lead</strong>
                <span>Capture a client inquiry</span>
              </div>
            </button>

            <button
              type="button"
              className="pingo-guide-action-item"
              onClick={() => handleAction('/communication/call-logs')}
            >
              <div className="pingo-action-icon bg-green">
                <PhoneCall size={15} />
              </div>
              <div className="pingo-action-info">
                <strong>Call Logs & Dialer</strong>
                <span>Review call recordings & connect</span>
              </div>
            </button>

            <button
              type="button"
              className="pingo-guide-action-item"
              onClick={() => handleAction('/communication/followups')}
            >
              <div className="pingo-action-icon bg-amber">
                <Clock size={15} />
              </div>
              <div className="pingo-action-info">
                <strong>Follow-up Schedule</strong>
                <span>Track callbacks & deadlines</span>
              </div>
            </button>

            <button
              type="button"
              className="pingo-guide-action-item"
              onClick={() => handleAction('/billing/wa-quotes')}
            >
              <div className="pingo-action-icon bg-purple">
                <FileText size={15} />
              </div>
              <div className="pingo-action-info">
                <strong>Quotations & Invoices</strong>
                <span>Issue professional estimates & PI</span>
              </div>
            </button>

            <button
              type="button"
              className="pingo-guide-action-item"
              onClick={() => handleAction('/communication/whatsapp')}
            >
              <div className="pingo-action-icon bg-emerald">
                <MessageCircle size={15} />
              </div>
              <div className="pingo-action-info">
                <strong>WhatsApp Hub</strong>
                <span>Unified team chat & templates</span>
              </div>
            </button>
          </div>

          <div className="pingo-guide-footer">
            <span>Powered by <strong>WA! CRM</strong></span>
            <button
              type="button"
              className="pingo-guide-next-tip"
              onClick={() => setTipIndex((prev) => (prev + 1) % PINGO_TIPS.length)}
            >
              Next Tip &rarr;
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default PingoQuickGuide;
