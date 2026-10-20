import React, { useState, useEffect, useRef } from 'react';
import PingoMascot from './PingoMascot';
import { PINGO_POPUP_EVENT } from '../../services/pingoPopupService';
import { X, Sparkles, CheckCircle2, Download, FileText, ArrowUpRight } from 'lucide-react';
import './PingoPopup.css';

/**
 * Synthesizes a soft, pleasant Web Audio chime for Pingo notifications
 */
const playPingoChime = (type = 'status') => {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    if (type === 'celebrate') {
      // Ascending triumphant dual-note chime (F5 -> A5)
      osc.frequency.setValueAtTime(698.46, now);
      osc.frequency.exponentialRampToValueAtTime(880.00, now + 0.12);
    } else if (type === 'download') {
      // Soft downward confirmation chime (G5 -> E5)
      osc.frequency.setValueAtTime(783.99, now);
      osc.frequency.exponentialRampToValueAtTime(659.25, now + 0.14);
    } else {
      // Crisp status tick (C6)
      osc.frequency.setValueAtTime(1046.50, now);
    }

    gain.gain.setValueAtTime(0.08, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.36);
  } catch (_) {
    // Non-blocking fallback if browser blocks audio autoplay
  }
};

const PingoPopup = () => {
  const [activePopup, setActivePopup] = useState(null);
  const [isClosing, setIsClosing] = useState(false);
  const timerRef = useRef(null);
  const closeTimerRef = useRef(null);

  const handleDismiss = () => {
    setIsClosing(true);
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    closeTimerRef.current = setTimeout(() => {
      setActivePopup(null);
      setIsClosing(false);
    }, 280);
  };

  useEffect(() => {
    const handleTrigger = (event) => {
      const detail = event.detail;
      if (!detail) return;

      // Clear any pending timers
      if (timerRef.current) clearTimeout(timerRef.current);
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);

      setIsClosing(false);
      setActivePopup(detail);

      // Play subtle chime
      if (detail.sound !== false) {
        playPingoChime(detail.theme === 'celebrate' ? 'celebrate' : (detail.type === 'download' ? 'download' : 'status'));
      }

      // Schedule auto-dismiss
      const duration = detail.duration || 3800;
      timerRef.current = setTimeout(() => {
        handleDismiss();
      }, duration);
    };

    window.addEventListener(PINGO_POPUP_EVENT, handleTrigger);
    return () => {
      window.removeEventListener(PINGO_POPUP_EVENT, handleTrigger);
      if (timerRef.current) clearTimeout(timerRef.current);
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
  }, []);

  // Keyboard accessibility: Escape key dismisses active popup
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && activePopup) {
        handleDismiss();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activePopup]);

  if (!activePopup) return null;

  const duration = activePopup.duration || 3800;

  return (
    <div className="pingo-popup-viewport" aria-live="polite" role="status">
      <div className={`pingo-popup-card theme-${activePopup.theme || 'default'} ${isClosing ? 'closing' : ''}`}>
        {/* Left Mascot Stage */}
        <div className="pingo-popup-mascot-col">
          <PingoMascot pose={activePopup.pose || 'salute'} height={68} withShadow={false} />
        </div>

        {/* Content Column */}
        <div className="pingo-popup-content-col">
          <div className="pingo-popup-header-row">
            <span className="pingo-popup-badge">
              {activePopup.theme === 'celebrate' ? <Sparkles size={11} /> : (activePopup.type === 'download' ? <Download size={11} /> : <CheckCircle2 size={11} />)}
              {activePopup.badge || 'COMPLETED'}
            </span>
            <button
              type="button"
              className="pingo-popup-close-btn"
              onClick={handleDismiss}
              title="Close notification"
              aria-label="Close notification"
            >
              <X size={15} />
            </button>
          </div>

          <h4 className="pingo-popup-title">{activePopup.title}</h4>
          
          {activePopup.subtitle && (
            <p className="pingo-popup-subtitle">{activePopup.subtitle}</p>
          )}

          {activePopup.reference && (
            <div className="pingo-popup-ref-pill">
              <FileText size={10} />
              <span>{activePopup.reference}</span>
            </div>
          )}
        </div>

        {/* Countdown Progress Bar */}
        <div className="pingo-popup-progress-track">
          <div
            className="pingo-popup-progress-fill"
            style={{ animationDuration: `${duration}ms` }}
          />
        </div>
      </div>
    </div>
  );
};

export default PingoPopup;
