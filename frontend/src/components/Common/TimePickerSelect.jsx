import React from 'react';

/**
 * Converts 12-hour time string ("01:00 AM", "02:30 PM") to 24-hour "HH:mm" for <input type="time">.
 */
export const to24Hour = (time12) => {
  if (!time12) return '10:00';
  const clean = String(time12).trim();

  // If already 24-hour "HH:mm"
  if (/^\d{2}:\d{2}$/.test(clean)) return clean;
  if (/^\d{1}:\d{2}$/.test(clean)) return `0${clean}`;

  const match = clean.match(/^(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?$/i);
  if (!match) return '10:00';

  let [, hoursStr, minutes, ampm] = match;
  let hours = parseInt(hoursStr, 10);
  if (ampm) {
    const isPM = ampm.toUpperCase() === 'PM';
    if (isPM && hours < 12) hours += 12;
    if (!isPM && hours === 12) hours = 0;
  }
  return `${String(hours).padStart(2, '0')}:${minutes}`;
};

/**
 * Converts 24-hour "HH:mm" from <input type="time"> to 12-hour "hh:mm AM/PM" string.
 */
export const to12Hour = (time24) => {
  if (!time24) return '10:00 AM';
  const clean = String(time24).trim();
  if (/AM|PM/i.test(clean)) return clean;

  const parts = clean.split(':');
  if (parts.length >= 2) {
    let hours = parseInt(parts[0], 10);
    const minutes = parts[1].slice(0, 2).padStart(2, '0');
    if (!isNaN(hours)) {
      const ampm = hours >= 12 ? 'PM' : 'AM';
      hours = hours % 12 || 12;
      return `${String(hours).padStart(2, '0')}:${minutes} ${ampm}`;
    }
  }
  return clean;
};

/**
 * Standard Clock Time Picker Component.
 * Uses native <input type="time"> just like the Date picker (<input type="date">),
 * featuring the built-in clock icon and hour/minute/AM-PM picker popover without typing.
 */
const TimePickerSelect = ({
  value = '10:00 AM',
  onChange,
  disabled = false,
  style = {},
  className = '',
  name = 'followup_time',
  id,
  required = false
}) => {
  const value24 = to24Hour(value);

  const handleNativeChange = (e) => {
    const raw24 = e.target.value;
    const formatted12 = to12Hour(raw24);
    if (onChange) {
      onChange({
        ...e,
        target: {
          ...e.target,
          name: name || e.target.name,
          value: formatted12
        }
      });
    }
  };

  return (
    <input
      type="time"
      id={id}
      name={name}
      value={value24}
      onChange={handleNativeChange}
      disabled={disabled}
      required={required}
      className={className}
      style={{
        width: '100%',
        paddingLeft: '14px',
        paddingRight: '12px',
        borderRadius: 'var(--radius-md, 8px)',
        border: '1px solid var(--border-color, #cbd5e1)',
        backgroundColor: disabled ? '#f1f5f9' : 'var(--bg-card, #ffffff)',
        color: 'var(--text-color, #0f172a)',
        fontSize: '0.9rem',
        cursor: disabled ? 'not-allowed' : 'pointer',
        ...style
      }}
    />
  );
};

export default TimePickerSelect;
