/**
 * Helpers for call recordings produced by Asterisk / Doocti.
 *
 * Those MP3 files are raw CBR streams without a Xing/VBRI/Info header, so
 * browsers cannot know the total duration from metadata alone. Chrome reports
 * `Infinity` (or `NaN`) until the whole file has been scanned, which is why
 * custom players show "0:00 / 0:00" while the audio is perfectly playable.
 *
 * Seeking far past the end forces the browser to scan the stream and emit a
 * real `duration` via the `durationchange` event. We immediately rewind once
 * the duration becomes available.
 */

export const isUsableDuration = (value) =>
  typeof value === 'number' && Number.isFinite(value) && value > 0;

export const probeAudioDuration = (el) => {
  if (!el) return;
  if (isUsableDuration(el.duration)) return;
  try {
    // Remember that this cursor position is artificial so it can be rewound.
    if (el.dataset) el.dataset.durationProbe = '1';
    // Any value larger than the media length clamps to the true end.
    el.currentTime = 1e101;
  } catch {
    /* Browsers that reject the seek simply keep the unknown duration */
  }
};

export const rewindAfterProbe = (el) => {
  if (!el) return false;
  const probing = Boolean(el.dataset && el.dataset.durationProbe === '1');
  if (!probing && el.currentTime <= 1e6) return false;
  // The end-seek is still in flight.
  if (el.currentTime > 1e6) return false;
  // Wait until the browser has scanned the stream and knows the duration.
  if (!isUsableDuration(el.duration)) return false;
  if (el.dataset) delete el.dataset.durationProbe;
  // Never interrupt active playback just to reset the probe cursor.
  if (!el.paused) return false;
  try {
    el.currentTime = 0;
  } catch {
    /* ignore */
  }
  return true;
};
