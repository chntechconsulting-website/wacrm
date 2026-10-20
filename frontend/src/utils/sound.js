/**
 * Audio Notification Utility for CRM Reminders
 * High-Volume Urgent Alert Alarm using Web Audio API.
 * Uses dual-pulse harmonic bells and dynamic compression for maximum volume and penetration.
 */

let sharedAudioCtx = null;
let activeOscillators = [];

const getAudioContext = () => {
  if (typeof window === 'undefined') return null;
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) return null;

  if (!sharedAudioCtx || sharedAudioCtx.state === 'closed') {
    sharedAudioCtx = new AudioContextClass();
  }
  return sharedAudioCtx;
};

// Automatically unlock/resume AudioContext on first user interaction (click, keydown, touch)
if (typeof window !== 'undefined') {
  const unlockAudio = () => {
    const ctx = getAudioContext();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
  };

  ['click', 'keydown', 'touchstart'].forEach(event => {
    window.addEventListener(event, unlockAudio, { once: false, passive: true });
  });
}

/**
 * Immediately silences all currently playing reminder sounds.
 */
export const stopReminderChime = () => {
  try {
    activeOscillators.forEach(osc => {
      try {
        osc.stop();
        osc.disconnect();
      } catch (e) {}
    });
    activeOscillators = [];
  } catch (err) {}
};

/**
 * Plays a loud, distinctive double-chime alarm sound for follow-up reminders.
 * Dual-burst high-attention chime: [Ding-Dong, Ding-Dong] with dynamics compression for maximum volume.
 */
export const playReminderChime = (isLoud = true) => {
  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }

    const now = ctx.currentTime;

    // Master Dynamics Compressor: prevents distortion while pumping up loudness
    const compressor = ctx.createDynamicsCompressor();
    compressor.threshold.setValueAtTime(-12, now);
    compressor.knee.setValueAtTime(6, now);
    compressor.ratio.setValueAtTime(12, now);
    compressor.attack.setValueAtTime(0.001, now);
    compressor.release.setValueAtTime(0.18, now);

    const masterGain = ctx.createGain();
    masterGain.gain.setValueAtTime(isLoud ? 1.0 : 0.5, now);

    compressor.connect(masterGain);
    masterGain.connect(ctx.destination);

    // Urgent Dual Alert Ring:
    // Burst 1: 880Hz (A5) -> 1046.5Hz (C6) -> 1318.5Hz (E6)
    // Short 110ms gap
    // Burst 2: 1046.5Hz (C6) -> 1318.5Hz (E6) -> 1760Hz (A6 high ringing bell)
    const pulses = [
      // Burst 1: Ring 1
      { freq: 880.00,  time: 0.00, duration: 0.22, gain: 0.88 },
      { freq: 1046.50, time: 0.12, duration: 0.24, gain: 0.92 },
      { freq: 1318.51, time: 0.25, duration: 0.42, gain: 0.96 },
      // Burst 2: Ring 2 (Higher & louder for maximum urgency)
      { freq: 1046.50, time: 0.52, duration: 0.22, gain: 0.92 },
      { freq: 1318.51, time: 0.63, duration: 0.26, gain: 0.96 },
      { freq: 1760.00, time: 0.76, duration: 0.70, gain: 1.00 }
    ];

    pulses.forEach(({ freq, time, duration, gain: targetGain }) => {
      const startTime = now + time;

      // Primary tone (triangle wave provides rich punchy acoustic bell harmonics)
      const osc = ctx.createOscillator();
      const oscGain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, startTime);

      // Bright chime overtone (sine wave)
      const overtone = ctx.createOscillator();
      const overtoneGain = ctx.createGain();
      overtone.type = 'sine';
      overtone.frequency.setValueAtTime(freq * 1.5, startTime);

      // Instant punchy attack with smooth resonant release
      oscGain.gain.setValueAtTime(0.001, startTime);
      oscGain.gain.exponentialRampToValueAtTime(targetGain, startTime + 0.012);
      oscGain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

      overtoneGain.gain.setValueAtTime(0.001, startTime);
      overtoneGain.gain.exponentialRampToValueAtTime(targetGain * 0.40, startTime + 0.012);
      overtoneGain.gain.exponentialRampToValueAtTime(0.0001, startTime + (duration * 0.65));

      osc.connect(oscGain);
      oscGain.connect(compressor);

      overtone.connect(overtoneGain);
      overtoneGain.connect(compressor);

      osc.start(startTime);
      osc.stop(startTime + duration + 0.05);

      overtone.start(startTime);
      overtone.stop(startTime + duration + 0.05);

      activeOscillators.push(osc, overtone);

      setTimeout(() => {
        activeOscillators = activeOscillators.filter(o => o !== osc && o !== overtone);
      }, (time + duration + 0.1) * 1000);
    });
  } catch (err) {
    console.warn('Unable to play reminder sound:', err);
  }
};
